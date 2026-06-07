# Sakura Backend

Flask backend for the Sakura thick client. See `main.py` for the Flask entry point
and `src/` for the application code.

## Hybrid Document Parsing

A pluggable parsing engine that ingests `.xlsx` and `.docx` files (spec / design /
requirements / test cases) and returns a validated structured payload. The pipeline
follows the user-provided architecture:

```
[Uploaded File]
        |
        +--> Deterministic Engine (openpyxl / zipfile / lxml)
        |                   in parallel with
        +--> Visual Preprocessor (LibreOffice page snapshots)
                           |
                           v
               Hybrid Context Assembly
            (bbox text matrices + layout tags)
                           |
                           v
                  Pluggable VLM Engine
                           |
                           v
              Strict Reconciliation
       (deterministic cell text OVERRIDES VLM text)
                           |
                           v
            Validated Structured Payload
```

### Install

```bash
python -m pip install -r requirements.txt
# also install optional system deps:
#   * LibreOffice (`soffice` on PATH) for page snapshots
#   * Poppler (`pdftoppm` on PATH) OR `pypdfium2` for PDF → PNG conversion
#   * Redis 6+ as the Celery broker/backend
```

If LibreOffice or Redis is missing the parser still runs deterministically — the
orchestrator skips the affected stage and records a warning.

### Run

```bash
# 1. Start Redis (broker + result backend)
redis-server

# 2. Start the Celery worker (queue=parsing)
python scripts/run_celery_worker.py

# 3. Start the Flask backend
python main.py
```

### Submit a document

Asynchronous (default):

```bash
curl -X POST http://localhost:5000/api/parsing/parse \
    -F "file=@./samples/spec.xlsx" \
    -F "provider=ollama"
# => {"success":true,"data":{"task_id":"...","status_url":"/api/parsing/tasks/...","result_url":"/api/parsing/tasks/.../result"}}
```

Synchronous (for tests / dev — runs the orchestrator in-process):

```bash
curl -X POST http://localhost:5000/api/parsing/parse \
    -F "file=@./samples/spec.xlsx" \
    -F "mode=sync" \
    -F "enable_vlm=false"
```

Poll status / result:

```bash
curl http://localhost:5000/api/parsing/tasks/<task_id>
curl http://localhost:5000/api/parsing/tasks/<task_id>/result
```

List available VLM providers:

```bash
curl http://localhost:5000/api/parsing/providers
# => {"success":true,"data":{"default":"ollama","providers":["anthropic","ollama","openai"]}}
```

### Configuration

All parsing-related keys live under `parsing.*` in `config/config.yaml`:

```yaml
parsing:
  tmp_dir: data/tmp/parsing      # where uploads + extracted images land
  spatial_radius: 4              # rows/cols around each image anchor
  vlm:
    default_provider: ollama
    providers:
      ollama:
        base_url: http://localhost:11434
        model: qwen2.5vl:7b      # default VLM (Q4_K_M ~6GB, ~7GB resident, CPU-OK)
        lite_model: qwen2.5vl:3b # used when the Smart Import "Speed" preset is selected
      openai:
        base_url: https://api.openai.com/v1
        model: gpt-4o-mini       # OPENAI_API_KEY env or parsing.vlm.providers.openai.api_key
      anthropic:
        base_url: https://api.anthropic.com
        model: claude-3-5-sonnet-latest  # ANTHROPIC_API_KEY env or config
  celery:
    broker_url: redis://localhost:6379/0
    result_backend: redis://localhost:6379/1
```

Environment overrides: `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`,
`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `SAKURA_OLLAMA_EXE`,
`SAKURA_DISABLE_OLLAMA_SIDECAR`.

### Bundled Ollama sidecar (offline desktop deployments)

For the packaged Windows installer Sakura ships its own `ollama.exe` plus
pre-pulled `qwen2.5vl:7b` (and optionally `qwen2.5vl:3b` for the Smart
Import "Speed" preset). On startup `main.py` calls
`src/infrastructure/ollama_sidecar.py::ensure_ollama_running()` which:

- Skips if a daemon is already listening on `parsing.vlm.providers.ollama.base_url`.
- Otherwise spawns `<install>/resources/ollama/ollama.exe serve` with
  `OLLAMA_HOST=127.0.0.1:11434` and `OLLAMA_MODELS` pointed at
  `%LOCALAPPDATA%\sakura\ollama\models` (override via
  `parsing.vlm.providers.ollama.models_dir` or `OLLAMA_MODELS`).
- Pins `OLLAMA_NUM_PARALLEL=1` and `OLLAMA_MAX_LOADED_MODELS=1` to avoid
  swap-thrash on CPU-only machines.
- Registers an `atexit` hook to terminate the child on shutdown.

Set `SAKURA_DISABLE_OLLAMA_SIDECAR=true` to opt out (e.g. when developing
against a system-installed `ollama` on a different port).

To prepare the installer payload, run
`backend/scripts/prepare_ollama_resources.ps1` on the build machine. It
vendors `ollama.exe` and the model blobs into `backend/resources/ollama/`
which the sidecar's lookup chain prefers over `PATH`.

#### PyInstaller portable build with Ollama bundled

`build_portable.py` accepts `--with-ollama` to fold the staged
`backend/resources/ollama/` (binary + model blobs) into the PyInstaller
payload. End-to-end:

```bash
# 1. Stage ollama.exe + the qwen2.5vl model blobs:
pwsh backend/scripts/prepare_ollama_resources.ps1

# 2. Build the portable distribution with the runtime + models embedded:
python build_portable.py --with-ollama
```

`portable_entry.py` exports `SAKURA_OLLAMA_EXE` and `OLLAMA_MODELS`
pointing at the extracted resources, so the in-process sidecar finds the
daemon without touching `PATH` and the user gets a fully offline first
launch. Use **one-folder mode** (the default) when bundling models —
`--onefile` works but extracts multi-GB blobs into the temp dir on every
launch, adding 30–60 s of cold-start.

### Add a new VLM provider

1. Create `src/implementations/llm/my_provider.py` exposing a class that
   subclasses `src.interfaces.llm_provider.VLMProvider`.
2. Register it from `src/implementations/llm/__init__.py`:

   ```python
   from src.implementations.llm.my_provider import MyProvider
   registry.register("my-provider", lambda: MyProvider())
   ```

3. Add a `parsing.vlm.providers.my-provider.*` block to `config/config.yaml`.
4. Optionally set `parsing.vlm.default_provider: my-provider`.

### Pipeline guarantees

- Deterministic cell values always win in conflicts. Conflicts are recorded in
  `HybridParseResult.conflicts` with the VLM's claim for audit.
- The VLM may contribute: semantic labels, row→image associations, image
  descriptions, and inferred table boundaries the deterministic engine missed.
- Excel parser clamps row iteration to the `<dimension>` tag (no million-row
  scans) and skips hidden rows/cols while still recording them in
  `result.hidden`.
- Image anchors are converted from EMU + 0-indexed XDR coords to A1-style refs.

### Tests

```bash
python -m pytest tests/parsing -q -m "not integration"
```

Integration tests (require Redis / Celery / Ollama) are guarded behind the
`integration` marker.
