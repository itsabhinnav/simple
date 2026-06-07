"""Vector index for the Sakura QA assistant (RAG retrieval layer).

Design notes
------------
- **Storage**: A *dedicated* SQLite file at ``data/local/dev/vectors/sakura_vec.db``
  hosts a ``vec0`` virtual table from the ``sqlite-vec`` extension. We keep
  it out of the main ``sakura_db.db`` so a corrupted index can be deleted
  without touching domain data, and so reindexing doesn't churn the cache
  layer of the live app DB.
- **Change detection**: Each indexed row stores a SHA-256 hash of the
  concatenated content fields. On every reindex tick we recompute the hash
  per row; if it differs we re-embed and overwrite. Rows that no longer
  exist in the source table are deleted. New rows are inserted. This makes
  the indexer idempotent and incremental.
- **Trigger**: ``LiveIndexer`` polls ``LocalDatabaseService.get_database_version()``
  every ``poll_interval_seconds`` (default 15s). The version is bumped by
  :class:`HybridDatabaseService` on every INSERT/UPDATE/DELETE, so we never
  reindex while the data is idle.
- **Fallback**: If ``sqlite-vec`` can't be loaded (missing extension on
  this platform / blocked by SQLite build) the service degrades to an
  in-memory cosine search. Same public API.
- **Embedding provider**: Pulled from the ``VLMRegistry`` using either the
  configured ``assistant.rag.embedding_provider`` or the registry default.
  Falling back to lexical-only retrieval (handled in ``AssistantService``)
  is the next layer of defense if no provider can embed.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from src.infrastructure.configuration_manager import get_config_manager
from src.infrastructure.logging_config import get_logger
from src.interfaces.llm_provider import VLMProviderError

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Source descriptors: where to pull rows from + how to extract text/IDs/routes
# ---------------------------------------------------------------------------

@dataclass
class _SourceField:
    label: str
    field: str
    weight: int = 1  # how many times to repeat in the embedding text (title > body)


@dataclass
class _Source:
    kind: str                               # 'requirement' | 'test_case' | 'design_ticket' | 'spec'
    list_fn: Callable[[], List[Dict[str, Any]]]
    id_field: str
    title_field: str
    fields: List[_SourceField]
    route_fn: Callable[[Dict[str, Any]], str]


def _h(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def _coerce_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return ", ".join(_coerce_text(v) for v in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


@dataclass
class IndexedItem:
    kind: str
    business_id: str    # REQ-001 / TC-001 etc. -- stable for the UI
    title: str
    route: str
    score: float        # vector similarity in [0, 1]; rank fusion happens upstream
    snippet: str
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IndexStatus:
    enabled: bool
    backend: str             # 'sqlite-vec' | 'memory' | 'disabled'
    provider: Optional[str]
    embedding_model: Optional[str]
    dimension: Optional[int]
    total_vectors: int
    per_kind_counts: Dict[str, int]
    last_indexed_at: Optional[float]
    last_indexed_version: Optional[int]
    last_error: Optional[str]
    in_progress: bool


# ---------------------------------------------------------------------------
# VectorIndexService
# ---------------------------------------------------------------------------

class VectorIndexService:
    """Owns the embedded vector store + incremental indexing logic."""

    def __init__(
        self,
        *,
        requirement_service,
        test_case_service,
        design_ticket_service,
        spec_service,
        local_database_service,
        vlm_registry,
    ) -> None:
        self._registry = vlm_registry
        self._local_db = local_database_service
        cfg = get_config_manager()

        self._enabled: bool = bool(cfg.get_config("assistant.rag.enabled", True))
        self._provider_name: Optional[str] = cfg.get_config("assistant.rag.embedding_provider", None)
        self._max_chars_per_row: int = int(cfg.get_config("assistant.rag.max_chars_per_row", 2000) or 2000)

        index_path_cfg = cfg.get_config("assistant.rag.index_path", "data/local/dev/vectors/sakura_vec.db")
        env_override = os.environ.get("SAKURA_VECTOR_DB_PATH")
        base_path = Path(env_override) if env_override else Path(index_path_cfg)
        if not base_path.is_absolute():
            base_path = Path(__file__).resolve().parents[2] / base_path  # backend/
        self._index_path: Path = base_path
        self._index_path.parent.mkdir(parents=True, exist_ok=True)

        self._sources: List[_Source] = [
            _Source(
                kind="requirement",
                list_fn=requirement_service.get_all_requirements,
                id_field="requirement_id",
                title_field="title",
                fields=[
                    _SourceField("Title", "title", weight=2),
                    _SourceField("Description", "description"),
                    _SourceField("Given", "given"),
                    _SourceField("When", "when_action"),
                    _SourceField("Then", "then_result"),
                    _SourceField("Tags", "tags"),
                    _SourceField("Status", "status"),
                    _SourceField("Priority", "priority"),
                ],
                route_fn=lambda r: f"/requirements/{r.get('id')}" if r.get("id") else "/requirements",
            ),
            _Source(
                kind="test_case",
                list_fn=test_case_service.get_all_test_cases,
                id_field="test_case_id",
                title_field="test_objective",
                fields=[
                    _SourceField("Objective", "test_objective", weight=2),
                    _SourceField("Feature", "feature", weight=2),
                    _SourceField("Linked requirement", "associated_requirement_id"),
                    _SourceField("Preconditions", "preconditions"),
                    _SourceField("Steps", "test_steps"),
                    _SourceField("Expected", "expected_result"),
                    _SourceField("Tags", "tags"),
                    _SourceField("Type", "test_type"),
                    _SourceField("Priority", "priority"),
                ],
                route_fn=lambda r: f"/test-cases/{r.get('test_case_id')}" if r.get("test_case_id") else "/test-cases",
            ),
            _Source(
                kind="design_ticket",
                list_fn=design_ticket_service.get_all_design_tickets,
                id_field="design_ticket_id",
                title_field="title",
                fields=[
                    _SourceField("Title", "title", weight=2),
                    _SourceField("Description", "description"),
                    _SourceField("Type", "design_type"),
                    _SourceField("Diagram", "diagram_type"),
                    _SourceField("Linked requirement", "linked_requirement_id"),
                    _SourceField("Tags", "tags"),
                    _SourceField("Status", "status"),
                    _SourceField("Priority", "priority"),
                ],
                route_fn=lambda r: f"/design-tickets/{r.get('id')}" if r.get("id") else "/design-tickets",
            ),
            _Source(
                kind="spec",
                list_fn=spec_service.get_all_specs,
                id_field="spec_id",
                title_field="title",
                fields=[
                    _SourceField("Title", "title", weight=2),
                    _SourceField("Description", "description"),
                    _SourceField("Category", "category"),
                    _SourceField("Version", "version"),
                    _SourceField("Status", "status"),
                ],
                route_fn=lambda r: "/specs",
            ),
        ]

        # Runtime state -----------------------------------------------------
        self._lock = threading.RLock()
        self._in_progress = False
        self._last_error: Optional[str] = None
        self._last_indexed_at: Optional[float] = None
        self._last_indexed_version: Optional[int] = None
        self._dimension: Optional[int] = None
        self._backend: str = "disabled"

        # sqlite-vec backed connection (may be None if extension load failed)
        self._conn: Optional[sqlite3.Connection] = None

        # In-memory fallback store: list of (rowid, kind, business_id, title,
        # route, content_hash, snippet, embedding_vector). Keep tiny.
        self._memory: List[Dict[str, Any]] = []
        self._memory_seq = 0

        if self._enabled:
            self._open_backend()

    # ------------------------------------------------------------------
    # Backend bootstrap
    # ------------------------------------------------------------------
    def _open_backend(self) -> None:
        try:
            # ``isolation_level=None`` puts the connection into autocommit
            # mode so a failed statement does not leave a long-lived
            # transaction holding the database lock. We still wrap multi-
            # statement upserts in ``BEGIN``/``COMMIT`` explicitly below.
            conn = sqlite3.connect(
                str(self._index_path),
                check_same_thread=False,
                timeout=10.0,
                isolation_level=None,
            )
            conn.row_factory = sqlite3.Row
            # WAL + busy_timeout make concurrent reads (e.g. /index/status
            # while the background thread reindexes) coexist without
            # "database is locked" errors on Windows.
            try:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA busy_timeout=5000")
                conn.execute("PRAGMA synchronous=NORMAL")
            except sqlite3.Error as exc:
                logger.debug(f"PRAGMA tuning skipped: {exc}")

            try:
                conn.enable_load_extension(True)
            except (AttributeError, sqlite3.NotSupportedError) as exc:
                raise RuntimeError(f"SQLite build lacks load_extension support: {exc}")

            import sqlite_vec  # type: ignore

            sqlite_vec.load(conn)
            conn.enable_load_extension(False)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS vec_meta (
                    rowid INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind TEXT NOT NULL,
                    business_id TEXT NOT NULL,
                    title TEXT,
                    route TEXT,
                    content_hash TEXT NOT NULL,
                    snippet TEXT,
                    payload TEXT,
                    indexed_at REAL,
                    UNIQUE(kind, business_id)
                )
                """
            )
            self._conn = conn
            self._backend = "sqlite-vec"
            logger.info(f"VectorIndexService using sqlite-vec at {self._index_path}")
        except Exception as exc:  # noqa: BLE001 - graceful fallback
            self._conn = None
            self._backend = "memory"
            logger.warning(f"sqlite-vec unavailable, falling back to in-memory cosine search: {exc}")

    def _ensure_vec_table(self, dim: int) -> None:
        if not self._conn or self._dimension == dim:
            return
        # Drop + recreate when dimensionality changes (e.g. user switched
        # embedding models). The hash diff loop will repopulate everything.
        # The vec_meta side is also wiped so prior rows do not collide with
        # the new (kind, business_id) UNIQUE entries that the next pass
        # re-creates against a fresh embedding space.
        with self._lock:
            try:
                self._conn.execute("DROP TABLE IF EXISTS vec_items")
                self._conn.execute("DELETE FROM vec_meta")
                self._conn.execute(
                    f"CREATE VIRTUAL TABLE vec_items USING vec0(embedding float[{dim}])"
                )
                self._dimension = dim
            except sqlite3.Error as exc:
                logger.error(f"Failed to (re)create vec_items table: {exc}")
                self._conn = None
                self._backend = "memory"

    # ------------------------------------------------------------------
    # Embedding provider resolution
    # ------------------------------------------------------------------
    def _provider(self):
        try:
            prov = self._registry.get(self._provider_name)
        except Exception:
            prov = self._registry.get(None)
        return prov

    def _embed_batch(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        prov = self._provider()
        vectors = prov.embed_text(texts)
        if not vectors:
            raise VLMProviderError(prov.name(), "Empty embedding response")
        return vectors

    # ------------------------------------------------------------------
    # Public: indexing
    # ------------------------------------------------------------------
    def reindex(self, *, force: bool = False) -> Dict[str, Any]:
        """Reindex all sources. Returns a summary dict.

        ``force=True`` rebuilds every row even when the content hash matches
        (used after switching embedding model)."""
        if not self._enabled:
            return {"skipped": True, "reason": "assistant.rag.enabled is false"}

        with self._lock:
            if self._in_progress:
                return {"skipped": True, "reason": "Indexing already in progress"}
            self._in_progress = True

        summary = {"created": 0, "updated": 0, "deleted": 0, "unchanged": 0, "kinds": {}}
        started = time.time()
        try:
            for source in self._sources:
                created, updated, deleted, unchanged = self._reindex_source(source, force=force)
                summary["created"] += created
                summary["updated"] += updated
                summary["deleted"] += deleted
                summary["unchanged"] += unchanged
                summary["kinds"][source.kind] = {
                    "created": created, "updated": updated, "deleted": deleted, "unchanged": unchanged,
                }
            self._last_indexed_at = time.time()
            try:
                self._last_indexed_version = int(self._local_db.get_database_version())
            except Exception:
                self._last_indexed_version = None
            self._last_error = None
            summary["duration_seconds"] = round(time.time() - started, 3)
            return summary
        except VLMProviderError as exc:
            self._safe_rollback()
            self._last_error = exc.message
            logger.warning(f"Reindex aborted — embedding provider error: {exc.message}")
            return {"error": exc.message, **summary}
        except Exception as exc:  # noqa: BLE001
            self._safe_rollback()
            self._last_error = str(exc)
            logger.error(f"Reindex failed: {exc}", exc_info=True)
            return {"error": str(exc), **summary}
        finally:
            with self._lock:
                self._in_progress = False

    def _reindex_source(self, source: _Source, *, force: bool) -> Tuple[int, int, int, int]:
        rows: List[Dict[str, Any]] = []
        try:
            rows = source.list_fn() or []
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Source '{source.kind}' fetch failed: {exc}")
            return 0, 0, 0, 0

        existing = self._load_existing(source.kind)  # business_id -> (rowid, content_hash)
        seen_business_ids: set[str] = set()

        # Dedupe rows by business_id within this pass — the source SQL does
        # not enforce uniqueness on the canonical business id (e.g. two
        # imports can produce two rows with the same requirement_id), so we
        # keep the most-recent occurrence (last-write-wins on the source's
        # default ORDER BY created_at DESC).
        unique_rows: Dict[str, Tuple[Dict[str, Any], str]] = {}
        for row in rows:
            business_id = str(row.get(source.id_field) or row.get("id") or "").strip()
            if not business_id:
                continue
            text = self._row_to_text(source, row)
            if business_id not in unique_rows:
                unique_rows[business_id] = (row, text)
            else:
                logger.debug(
                    f"Reindex: duplicate {source.kind} business_id '{business_id}' "
                    f"in source data — keeping first occurrence"
                )

        unchanged = 0
        to_embed: List[Tuple[Dict[str, Any], str, str]] = []
        for business_id, (row, text) in unique_rows.items():
            seen_business_ids.add(business_id)
            content_hash = _h(text)
            prior = existing.get(business_id)
            if prior and prior[1] == content_hash and not force:
                unchanged += 1
                continue
            to_embed.append((row, text, business_id))

        deleted = 0
        for business_id, (rowid, _) in existing.items():
            if business_id not in seen_business_ids:
                self._delete_row(rowid)
                deleted += 1

        created, updated = 0, 0
        BATCH = 16
        for i in range(0, len(to_embed), BATCH):
            chunk = to_embed[i : i + BATCH]
            texts = [text for _, text, _ in chunk]
            vectors = self._embed_batch(texts)
            if len(vectors) != len(chunk):
                raise VLMProviderError(
                    self._provider().name(),
                    f"Provider returned {len(vectors)} vectors for {len(chunk)} inputs",
                )
            if vectors:
                # Dimensionality change wipes vec_meta — re-read so the
                # subsequent upserts always look "new" instead of trying
                # to UPDATE a rowid that no longer exists.
                prev_dim = self._dimension
                self._ensure_vec_table(len(vectors[0]))
                if prev_dim != self._dimension:
                    existing = self._load_existing(source.kind)
            for (row, text, business_id), vec in zip(chunk, vectors):
                payload = {
                    "kind": source.kind,
                    "business_id": business_id,
                    "title": _coerce_text(row.get(source.title_field) or row.get(source.id_field) or "")[:200],
                    "route": source.route_fn(row),
                    "content_hash": _h(text),
                    "snippet": text[: self._max_chars_per_row],
                    "payload": {k: row.get(k) for k in (source.id_field, source.title_field) if row.get(k)},
                }
                was_new = business_id not in existing
                new_rowid = self._upsert_idempotent(payload, vec)
                # Track rowid for any later duplicates within the same pass
                # (should not happen post-dedupe, but defensive).
                existing[business_id] = (new_rowid, payload["content_hash"])
                if was_new:
                    created += 1
                else:
                    updated += 1

        return created, updated, deleted, unchanged

    def _row_to_text(self, source: _Source, row: Dict[str, Any]) -> str:
        parts: List[str] = [f"{source.kind.upper()} {row.get(source.id_field, '')}"]
        for field_def in source.fields:
            value = _coerce_text(row.get(field_def.field))
            if not value:
                continue
            value = value.strip()
            if not value:
                continue
            chunk = f"{field_def.label}: {value}"
            for _ in range(max(field_def.weight, 1)):
                parts.append(chunk)
        joined = "\n".join(parts)
        if len(joined) > self._max_chars_per_row:
            joined = joined[: self._max_chars_per_row]
        return joined

    # ------------------------------------------------------------------
    # Storage primitives (work for both sqlite-vec and the memory backend)
    # ------------------------------------------------------------------
    def _load_existing(self, kind: str) -> Dict[str, Tuple[int, str]]:
        out: Dict[str, Tuple[int, str]] = {}
        if self._conn:
            with self._lock:
                try:
                    rows = self._conn.execute(
                        "SELECT rowid, business_id, content_hash FROM vec_meta WHERE kind = ?",
                        (kind,),
                    ).fetchall()
                except sqlite3.Error as exc:
                    logger.warning(f"vec_meta read failed for {kind}: {exc}")
                    return out
            for row in rows:
                out[row["business_id"]] = (int(row["rowid"]), str(row["content_hash"]))
            return out
        for item in self._memory:
            if item["kind"] == kind:
                out[item["business_id"]] = (int(item["rowid"]), str(item["content_hash"]))
        return out

    def _delete_row(self, rowid: int) -> None:
        if self._conn:
            with self._lock:
                try:
                    self._conn.execute("BEGIN")
                    try:
                        self._conn.execute("DELETE FROM vec_items WHERE rowid = ?", (rowid,))
                    except sqlite3.OperationalError:
                        pass  # vec_items may not exist yet
                    self._conn.execute("DELETE FROM vec_meta WHERE rowid = ?", (rowid,))
                    self._conn.execute("COMMIT")
                except sqlite3.Error as exc:
                    self._safe_rollback()
                    logger.warning(f"Delete row {rowid} failed: {exc}")
            return
        self._memory = [m for m in self._memory if m["rowid"] != rowid]

    def _safe_rollback(self) -> None:
        """Best-effort transaction rollback that swallows secondary errors so
        the indexer can continue on the next pass instead of perpetually
        seeing 'database is locked'."""
        if not self._conn:
            return
        try:
            self._conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass

    def _upsert_idempotent(self, meta: Dict[str, Any], vector: List[float]) -> int:
        """Insert-or-update a single row keyed by (kind, business_id).

        Uses SQLite UPSERT (``INSERT ... ON CONFLICT ... DO UPDATE``) so a
        duplicate business_id in the source data never raises
        ``IntegrityError`` and a previously-failed pass can be safely
        retried. Returns the resolved ``rowid`` so callers can keep their
        in-memory tracking dict consistent.
        """
        if self._conn:
            payload_json = json.dumps(meta["payload"], ensure_ascii=False)
            now = time.time()
            with self._lock:
                try:
                    self._conn.execute("BEGIN")
                    self._conn.execute(
                        """
                        INSERT INTO vec_meta(kind, business_id, title, route, content_hash, snippet, payload, indexed_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(kind, business_id) DO UPDATE SET
                            title = excluded.title,
                            route = excluded.route,
                            content_hash = excluded.content_hash,
                            snippet = excluded.snippet,
                            payload = excluded.payload,
                            indexed_at = excluded.indexed_at
                        """,
                        (
                            meta["kind"], meta["business_id"], meta["title"], meta["route"],
                            meta["content_hash"], meta["snippet"], payload_json, now,
                        ),
                    )
                    rowid_row = self._conn.execute(
                        "SELECT rowid FROM vec_meta WHERE kind = ? AND business_id = ?",
                        (meta["kind"], meta["business_id"]),
                    ).fetchone()
                    if not rowid_row:
                        raise sqlite3.IntegrityError("vec_meta row vanished mid-upsert")
                    rowid = int(rowid_row["rowid"])
                    # vec_items is a vec0 virtual table — it has no UNIQUE
                    # constraint of its own, so we delete-then-insert to
                    # keep one embedding per rowid.
                    try:
                        self._conn.execute("DELETE FROM vec_items WHERE rowid = ?", (rowid,))
                    except sqlite3.OperationalError:
                        pass  # table may not exist on first insert
                    self._conn.execute(
                        "INSERT INTO vec_items(rowid, embedding) VALUES (?, ?)",
                        (rowid, json.dumps(vector)),
                    )
                    self._conn.execute("COMMIT")
                    return rowid
                except sqlite3.Error:
                    self._safe_rollback()
                    raise

        # Memory backend ---------------------------------------------------
        for item in self._memory:
            if item["kind"] == meta["kind"] and item["business_id"] == meta["business_id"]:
                item.update(meta)
                item["embedding"] = list(vector)
                item["indexed_at"] = time.time()
                return int(item["rowid"])
        self._memory_seq += 1
        self._memory.append({
            "rowid": self._memory_seq,
            **meta,
            "embedding": list(vector),
            "indexed_at": time.time(),
        })
        return self._memory_seq

    # ------------------------------------------------------------------
    # Public: search
    # ------------------------------------------------------------------
    def search(
        self,
        query: str,
        *,
        top_k: int = 12,
        kinds: Optional[Sequence[str]] = None,
    ) -> List[IndexedItem]:
        if not self._enabled or not query.strip():
            return []
        try:
            vectors = self._embed_batch([query])
        except VLMProviderError as exc:
            self._last_error = exc.message
            logger.warning(f"Vector search skipped — embedding failure: {exc.message}")
            return []
        if not vectors:
            return []
        query_vec = vectors[0]

        allowed = set(kinds) if kinds else None

        if self._conn and self._dimension == len(query_vec):
            return self._search_sqlite(query_vec, top_k=top_k, allowed=allowed)
        return self._search_memory(query_vec, top_k=top_k, allowed=allowed)

    def _search_sqlite(self, query_vec: List[float], *, top_k: int, allowed: Optional[set]) -> List[IndexedItem]:
        assert self._conn is not None
        with self._lock:
            try:
                rows = self._conn.execute(
                    """
                    SELECT m.kind, m.business_id, m.title, m.route, m.snippet, m.payload, v.distance
                      FROM vec_items v
                      JOIN vec_meta m ON m.rowid = v.rowid
                     WHERE v.embedding MATCH ? AND k = ?
                     ORDER BY v.distance ASC
                    """,
                    (json.dumps(query_vec), max(top_k * 3, top_k)),
                ).fetchall()
            except sqlite3.OperationalError as exc:
                logger.warning(f"vec_items search failed: {exc}")
                return []
        out: List[IndexedItem] = []
        for row in rows:
            if allowed and row["kind"] not in allowed:
                continue
            similarity = max(0.0, 1.0 - float(row["distance"]))  # cosine distance -> similarity
            try:
                payload = json.loads(row["payload"] or "{}")
            except json.JSONDecodeError:
                payload = {}
            out.append(IndexedItem(
                kind=row["kind"], business_id=row["business_id"], title=row["title"] or "",
                route=row["route"] or "", score=similarity, snippet=row["snippet"] or "",
                payload=payload,
            ))
            if len(out) >= top_k:
                break
        return out

    def _search_memory(self, query_vec: List[float], *, top_k: int, allowed: Optional[set]) -> List[IndexedItem]:
        if not self._memory:
            return []
        qnorm = math.sqrt(sum(x * x for x in query_vec)) or 1.0
        scored: List[Tuple[float, Dict[str, Any]]] = []
        for item in self._memory:
            if allowed and item["kind"] not in allowed:
                continue
            vec = item.get("embedding") or []
            if not vec:
                continue
            dot = sum(a * b for a, b in zip(query_vec, vec))
            norm = math.sqrt(sum(b * b for b in vec)) or 1.0
            similarity = max(0.0, dot / (qnorm * norm))
            scored.append((similarity, item))
        scored.sort(key=lambda x: x[0], reverse=True)
        out: List[IndexedItem] = []
        for similarity, item in scored[:top_k]:
            out.append(IndexedItem(
                kind=item["kind"], business_id=item["business_id"], title=item.get("title") or "",
                route=item.get("route") or "", score=similarity, snippet=item.get("snippet") or "",
                payload=item.get("payload") or {},
            ))
        return out

    # ------------------------------------------------------------------
    # Public: status + helpers used by the controller
    # ------------------------------------------------------------------
    def status(self) -> IndexStatus:
        per_kind: Dict[str, int] = {}
        total = 0
        provider_name: Optional[str] = None
        embedding_model: Optional[str] = None
        try:
            prov = self._provider()
            provider_name = prov.name()
            embedding_model = getattr(prov, "_embedding_model", lambda: None)()
        except Exception:
            pass

        if self._conn:
            with self._lock:
                try:
                    rows = self._conn.execute(
                        "SELECT kind, COUNT(*) AS n FROM vec_meta GROUP BY kind"
                    ).fetchall()
                    for row in rows:
                        per_kind[row["kind"]] = int(row["n"])
                        total += int(row["n"])
                except sqlite3.OperationalError:
                    pass
        else:
            for item in self._memory:
                per_kind[item["kind"]] = per_kind.get(item["kind"], 0) + 1
                total += 1

        return IndexStatus(
            enabled=self._enabled,
            backend=self._backend if self._enabled else "disabled",
            provider=provider_name,
            embedding_model=embedding_model,
            dimension=self._dimension,
            total_vectors=total,
            per_kind_counts=per_kind,
            last_indexed_at=self._last_indexed_at,
            last_indexed_version=self._last_indexed_version,
            last_error=self._last_error,
            in_progress=self._in_progress,
        )

    def current_data_version(self) -> Optional[int]:
        try:
            return int(self._local_db.get_database_version())
        except Exception:
            return None


# ---------------------------------------------------------------------------
# Background indexer thread
# ---------------------------------------------------------------------------

class LiveIndexer(threading.Thread):
    """Polls the local DB version and triggers incremental reindex on bump."""

    def __init__(
        self,
        vector_service: VectorIndexService,
        *,
        poll_interval_seconds: float = 15.0,
        startup_delay_seconds: float = 2.0,
    ) -> None:
        super().__init__(daemon=True, name="sakura-live-indexer")
        self._vec = vector_service
        self._poll = max(2.0, float(poll_interval_seconds))
        self._startup_delay = max(0.0, float(startup_delay_seconds))
        self._stop = threading.Event()
        self._last_seen_version: Optional[int] = None

    def stop(self) -> None:
        self._stop.set()

    def trigger_now(self) -> None:
        """Force the next loop iteration to run immediately."""
        self._last_seen_version = -1  # any new value will look "newer"

    def run(self) -> None:
        if self._stop.wait(self._startup_delay):
            return
        # Always reindex once on startup so a fresh DB without prior vectors
        # gets a baseline. After that, only run when the version changes.
        try:
            logger.info("LiveIndexer: initial full reindex")
            summary = self._vec.reindex()
            logger.info(f"LiveIndexer: initial reindex done — {summary}")
            self._last_seen_version = self._vec.current_data_version()
        except Exception as exc:  # noqa: BLE001
            logger.error(f"LiveIndexer initial reindex failed: {exc}")

        while not self._stop.wait(self._poll):
            try:
                version = self._vec.current_data_version()
                if version is None:
                    continue
                if self._last_seen_version is not None and version <= self._last_seen_version:
                    continue
                logger.info(f"LiveIndexer: DB version bumped {self._last_seen_version} -> {version}, reindexing")
                summary = self._vec.reindex()
                logger.info(f"LiveIndexer: incremental reindex result — {summary}")
                self._last_seen_version = version
            except Exception as exc:  # noqa: BLE001
                logger.error(f"LiveIndexer tick failed: {exc}")
