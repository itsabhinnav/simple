"""Ollama sidecar process manager for the bundled local-VLM deployment.

The desktop installer ships an `ollama.exe` (or `ollama` on macOS/Linux) plus
pre-pulled GGUF model blobs alongside the Flask backend. This module is the
single seam responsible for:

    1. Detecting whether an Ollama daemon is already reachable on
       ``parsing.vlm.providers.ollama.base_url`` (default
       ``http://localhost:11434``). If yes, it stays out of the way.
    2. Otherwise spawning the bundled binary as a child process with
       ``OLLAMA_HOST`` and ``OLLAMA_MODELS`` pointed at the vendored model
       directory so the daemon serves the pre-pulled ``qwen2.5vl:7b``
       blobs without ever reaching the public internet.
    3. Tearing the child down on interpreter exit (``atexit``) so the
       installer doesn't leak orphaned processes between launches.

The whole thing is best-effort. Ollama not being available is never fatal —
the existing :class:`OllamaProvider` retry/backoff in
``src/implementations/llm/ollama_provider.py`` will surface a clean
``VLMProviderError`` and the Smart Import wizard degrades gracefully.

Lookup order for the executable (first hit wins):

    1. Env var ``SAKURA_OLLAMA_EXE``
    2. Config key ``parsing.vlm.providers.ollama.executable``
    3. ``<backend_dir>/resources/ollama/ollama.exe`` (Windows installer layout)
    4. ``<backend_dir>/../resources/ollama/ollama.exe`` (PyInstaller _MEIPASS)
    5. ``ollama`` on ``PATH`` (developer machines that already installed it)

Lookup order for the models directory (where blobs live):

    1. Env var ``OLLAMA_MODELS`` if already exported
    2. Config key ``parsing.vlm.providers.ollama.models_dir``
    3. ``%LOCALAPPDATA%\\sakura\\ollama\\models`` on Windows,
       ``~/.local/share/sakura/ollama/models`` elsewhere
"""

from __future__ import annotations

import atexit
import os
import platform
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from src.infrastructure.configuration_manager import get_config_manager
from src.infrastructure.logging_config import get_logger

logger = get_logger(__name__)


_SIDECAR_LOCK = threading.Lock()
_SIDECAR_PROC: Optional[subprocess.Popen] = None


def _is_windows() -> bool:
    return platform.system().lower().startswith("win")


def _backend_dir() -> Path:
    # `src/infrastructure/ollama_sidecar.py` -> backend root is two parents up.
    return Path(__file__).resolve().parents[2]


def _resolve_executable() -> Optional[str]:
    env_exe = os.environ.get("SAKURA_OLLAMA_EXE")
    if env_exe and Path(env_exe).is_file():
        return env_exe

    cm = get_config_manager()
    cfg_exe = cm.get_config("parsing.vlm.providers.ollama.executable", None)
    if cfg_exe and Path(cfg_exe).is_file():
        return cfg_exe

    binary = "ollama.exe" if _is_windows() else "ollama"
    candidates = [
        _backend_dir() / "resources" / "ollama" / binary,
        _backend_dir().parent / "resources" / "ollama" / binary,
    ]
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "resources" / "ollama" / binary)

    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)

    on_path = shutil.which("ollama")
    if on_path:
        return on_path
    return None


def _resolve_models_dir() -> Path:
    env_dir = os.environ.get("OLLAMA_MODELS")
    if env_dir:
        return Path(env_dir).expanduser()

    cm = get_config_manager()
    cfg_dir = cm.get_config("parsing.vlm.providers.ollama.models_dir", None)
    if cfg_dir:
        return Path(cfg_dir).expanduser()

    if _is_windows():
        local_app = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(local_app) / "sakura" / "ollama" / "models"
    return Path.home() / ".local" / "share" / "sakura" / "ollama" / "models"


def _resolve_host() -> tuple[str, int]:
    cm = get_config_manager()
    base_url = cm.get_config("parsing.vlm.providers.ollama.base_url", "http://localhost:11434")
    try:
        parsed = urlparse(base_url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 11434
    except Exception:
        host, port = "127.0.0.1", 11434
    return host, port


def _is_daemon_up(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _wait_until_up(host: str, port: int, deadline_s: float = 15.0) -> bool:
    start = time.time()
    while time.time() - start < deadline_s:
        if _is_daemon_up(host, port, timeout=0.4):
            return True
        time.sleep(0.4)
    return False


def ensure_ollama_running() -> Optional[subprocess.Popen]:
    """Start the bundled Ollama daemon if one isn't already listening.

    Returns the spawned :class:`subprocess.Popen` (or ``None`` if no spawn
    was needed / possible). Idempotent and safe to call multiple times — a
    second call with an already-running child is a no-op.
    """
    global _SIDECAR_PROC

    with _SIDECAR_LOCK:
        host, port = _resolve_host()

        if _SIDECAR_PROC is not None and _SIDECAR_PROC.poll() is None:
            logger.debug(f"Ollama sidecar already managed by us (pid={_SIDECAR_PROC.pid})")
            return _SIDECAR_PROC

        if _is_daemon_up(host, port):
            logger.info(f"Ollama already reachable at {host}:{port}; skipping sidecar spawn")
            return None

        executable = _resolve_executable()
        if not executable:
            logger.warning(
                "Ollama executable not found (looked in SAKURA_OLLAMA_EXE, "
                "parsing.vlm.providers.ollama.executable, resources/ollama/, PATH). "
                "Smart Import VLM features will be unavailable until the daemon is started manually."
            )
            return None

        models_dir = _resolve_models_dir()
        try:
            models_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logger.warning(f"Could not create Ollama models dir {models_dir}: {exc}")

        env = os.environ.copy()
        env.setdefault("OLLAMA_HOST", f"{host}:{port}")
        env.setdefault("OLLAMA_MODELS", str(models_dir))
        # CPU-only desktop deployments thrash on parallel decodes; pin to 1.
        env.setdefault("OLLAMA_NUM_PARALLEL", "1")
        env.setdefault("OLLAMA_MAX_LOADED_MODELS", "1")

        creationflags = 0
        startupinfo = None
        if _is_windows():
            # CREATE_NO_WINDOW (0x08000000) keeps the daemon's console hidden
            # behind the Sakura installer launcher.
            creationflags = 0x08000000
            try:
                startupinfo = subprocess.STARTUPINFO()  # type: ignore[attr-defined]
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # type: ignore[attr-defined]
            except Exception:
                startupinfo = None

        try:
            logger.info(
                f"Spawning Ollama sidecar: {executable} serve "
                f"(host={env['OLLAMA_HOST']}, models={env['OLLAMA_MODELS']})"
            )
            proc = subprocess.Popen(
                [executable, "serve"],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                creationflags=creationflags,
                startupinfo=startupinfo,
                close_fds=not _is_windows(),
            )
        except OSError as exc:
            logger.error(f"Failed to spawn Ollama sidecar: {exc}")
            return None

        _SIDECAR_PROC = proc
        atexit.register(_terminate_sidecar)

        if _wait_until_up(host, port, deadline_s=15.0):
            logger.info(f"Ollama sidecar ready at {host}:{port} (pid={proc.pid})")
        else:
            logger.warning(
                f"Ollama sidecar pid={proc.pid} did not start listening within 15s. "
                "VLM calls will retry against http://{host}:{port} as the daemon comes up."
            )
        return proc


def _terminate_sidecar() -> None:
    global _SIDECAR_PROC
    proc = _SIDECAR_PROC
    if proc is None:
        return
    if proc.poll() is not None:
        _SIDECAR_PROC = None
        return
    try:
        logger.info(f"Stopping Ollama sidecar pid={proc.pid}")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    except Exception as exc:  # noqa: BLE001 - best-effort cleanup
        logger.warning(f"Ollama sidecar shutdown raised: {exc}")
    finally:
        _SIDECAR_PROC = None


__all__ = ["ensure_ollama_running"]
