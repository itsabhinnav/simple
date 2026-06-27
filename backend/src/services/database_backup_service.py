"""SQLite backup, integrity verification, and automatic recovery.

Provides:
  * hot backups via the SQLite backup API (WAL-safe)
  * PRAGMA integrity_check / quick_check validation
  * restore from the newest valid backup on corruption
  * periodic background snapshots (see ``PeriodicBackupWorker``)
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from src.infrastructure.configuration_manager import get_config_manager
from src.infrastructure.logging_config import get_logger

logger = get_logger(__name__)

_CORRUPTION_MARKERS = (
    "database disk image is malformed",
    "file is not a database",
    "database corruption",
    "sqlite_corrupt",
    "malformed",
)


def is_corruption_error(message: Optional[str]) -> bool:
    if not message:
        return False
    lowered = message.lower()
    return any(marker in lowered for marker in _CORRUPTION_MARKERS)


class DatabaseBackupService:
    """Manages SQLite snapshots and recovery for the primary local database."""

    DEFAULT_INTERVAL_SECONDS = 3600
    DEFAULT_RETENTION = 50

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.backup_dir = self.db_path.parent / "backups"
        self._config = get_config_manager()
        self._lock = threading.RLock()

    def _cfg(self, key: str, default: Any) -> Any:
        return self._config.get_config(key, default)

    @property
    def enabled(self) -> bool:
        return bool(self._cfg("database.backup.enabled", True))

    @property
    def interval_seconds(self) -> float:
        return float(self._cfg("database.backup.interval_seconds", self.DEFAULT_INTERVAL_SECONDS))

    @property
    def retention(self) -> int:
        return int(self._cfg("database.backup.retention", self.DEFAULT_RETENTION))

    def _open(self, path: Path, *, readonly: bool = False) -> sqlite3.Connection:
        uri = f"file:{path.as_posix()}?mode={'ro' if readonly else 'rw'}"
        conn = sqlite3.connect(uri, uri=True, timeout=10.0)
        conn.execute("PRAGMA busy_timeout = 5000")
        if not readonly:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
            conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def verify_database(self, path: Optional[Path] = None) -> Tuple[bool, Optional[str]]:
        """Return (ok, error_message). Runs integrity_check then a smoke SELECT."""
        target = Path(path) if path else self.db_path
        if not target.exists():
            return False, "database file does not exist"
        if target.stat().st_size == 0:
            return False, "database file is empty"

        try:
            conn = self._open(target, readonly=True)
            try:
                row = conn.execute("PRAGMA integrity_check").fetchone()
                if not row or str(row[0]).lower() != "ok":
                    quick = conn.execute("PRAGMA quick_check").fetchone()
                    detail = str(quick[0]) if quick else str(row[0] if row else "unknown")
                    return False, f"integrity_check failed: {detail}"

                conn.execute("SELECT 1").fetchone()
                conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' LIMIT 1"
                ).fetchone()
                return True, None
            finally:
                conn.close()
        except sqlite3.DatabaseError as exc:
            return False, str(exc)
        except OSError as exc:
            return False, str(exc)

    @property
    def secondary_backup_dir(self) -> Optional[Path]:
        raw = self._cfg("database.backup.secondary_path", None)
        if not raw:
            return None
        return Path(os.path.expanduser(str(raw)))

    def _resolve_config_path(self, configured: str) -> Path:
        path = Path(configured)
        if path.is_absolute():
            return path
        return Path.cwd() / path

    def vector_db_path(self) -> Optional[Path]:
        raw = self._cfg("assistant.rag.index_path", "data/local/dev/vectors/sakura_vec.db")
        path = self._resolve_config_path(str(raw))
        return path if path.exists() else None

    def get_status(self) -> Dict[str, Any]:
        """Operational snapshot for health checks and the admin dashboard."""
        ok, err = self.verify_database()
        backups = self.list_backups()
        latest = backups[0] if backups else None
        size_bytes = self.db_path.stat().st_size if self.db_path.exists() else 0
        schema_version = None
        data_version = None
        if ok and self.db_path.exists():
            try:
                conn = self._open(self.db_path, readonly=True)
                try:
                    for key, target in (("schema_version", "schema_version"), ("version", "data_version")):
                        row = conn.execute(
                            "SELECT metadata_value FROM database_metadata WHERE metadata_key = ?",
                            (key,),
                        ).fetchone()
                        if row:
                            if target == "schema_version":
                                schema_version = row[0]
                            else:
                                data_version = row[0]
                finally:
                    conn.close()
            except sqlite3.DatabaseError:
                pass

        vec = self.vector_db_path()
        return {
            "healthy": ok,
            "integrity_error": err,
            "db_path": str(self.db_path),
            "size_bytes": size_bytes,
            "schema_version": schema_version,
            "data_version": data_version,
            "backup_enabled": self.enabled,
            "backup_count": len(backups),
            "last_backup": latest,
            "secondary_backup_dir": str(self.secondary_backup_dir) if self.secondary_backup_dir else None,
            "vector_db_path": str(vec) if vec else None,
            "vector_db_size_bytes": vec.stat().st_size if vec else 0,
        }

    def backup_file(self, source: Path, reason: str) -> Optional[Path]:
        source = Path(source)
        if not source.exists():
            return None
        with self._lock:
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
            safe_reason = "".join(c if c.isalnum() or c in "-_" else "_" for c in reason)
            target = self.backup_dir / f"{source.stem}.{ts}.{safe_reason}.bak"
            try:
                src = self._open(source)
                try:
                    src.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                    dest = sqlite3.connect(str(target))
                    try:
                        src.backup(dest)
                        dest.commit()
                    finally:
                        dest.close()
                finally:
                    src.close()
                ok, err = self.verify_database(target)
                if not ok:
                    target.unlink(missing_ok=True)
                    logger.error("Auxiliary backup rejected: %s", err)
                    return None
                self._copy_to_secondary(target)
                return target
            except Exception:
                logger.exception("Auxiliary backup failed for %s", source)
                target.unlink(missing_ok=True)
                return None

    def backup_auxiliary_databases(self, reason: str = "auxiliary") -> List[Path]:
        created: List[Path] = []
        vec = self.vector_db_path()
        if vec:
            path = self.backup_file(vec, reason=f"vector_{reason}")
            if path:
                created.append(path)
        return created

    def _copy_to_secondary(self, backup_path: Path) -> None:
        secondary = self.secondary_backup_dir
        if not secondary:
            return
        try:
            secondary.mkdir(parents=True, exist_ok=True)
            dest = secondary / backup_path.name
            shutil.copy2(backup_path, dest)
            logger.debug("Copied backup to secondary location: %s", dest)
        except OSError:
            logger.warning("Secondary backup copy failed", exc_info=True)

    def after_main_restore(self) -> None:
        """Invalidate stale vector index and schedule a full reindex."""
        vec = self.vector_db_path()
        if vec:
            for suffix in ("", "-wal", "-shm", "-journal"):
                path = Path(str(vec) + suffix) if suffix else vec
                if path.exists():
                    try:
                        path.unlink()
                    except OSError:
                        logger.debug("Could not remove vector file %s", path)
        try:
            from src.infrastructure.dependency_injection import get_live_indexer

            live = get_live_indexer()
            if live is not None:
                live.trigger_now()
        except Exception:
            logger.debug("Live indexer trigger after restore skipped", exc_info=True)

    def resolve_backup_path(self, backup_name: str) -> Optional[Path]:
        """Resolve a backup file name within the backup directory (path traversal safe)."""
        if not backup_name or ".." in backup_name or "/" in backup_name or "\\" in backup_name:
            return None
        candidate = (self.backup_dir / backup_name).resolve()
        try:
            candidate.relative_to(self.backup_dir.resolve())
        except ValueError:
            return None
        return candidate if candidate.exists() else None

    def create_backup(self, reason: str = "scheduled") -> Optional[Path]:
        """Create a verified hot backup. Returns the backup path or None."""
        if not self.enabled and reason == "scheduled":
            return None
        if not self.db_path.exists():
            return None

        created: Optional[Path] = None
        with self._lock:
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
            safe_reason = "".join(c if c.isalnum() or c in "-_" else "_" for c in reason)
            target = self.backup_dir / f"{self.db_path.stem}.{ts}.{safe_reason}.bak"

            try:
                src = self._open(self.db_path)
                try:
                    src.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                    dest = sqlite3.connect(str(target))
                    try:
                        src.backup(dest)
                        dest.commit()
                    finally:
                        dest.close()
                finally:
                    src.close()

                ok, err = self.verify_database(target)
                if not ok:
                    target.unlink(missing_ok=True)
                    logger.error("Backup rejected — integrity check failed: %s", err)
                    return None

                self._prune_backups()
                self._copy_to_secondary(target)
                logger.info("Database backup created: %s (reason=%s)", target.name, reason)
                created = target
            except Exception:
                logger.exception("Database backup failed")
                target.unlink(missing_ok=True)
                return None

        if created is not None:
            self.backup_auxiliary_databases(reason=reason)
        return created

    def list_backups(self) -> List[Dict[str, Any]]:
        if not self.backup_dir.exists():
            return []
        out: List[Dict[str, Any]] = []
        pattern = f"{self.db_path.stem}.*.bak"
        for p in sorted(self.backup_dir.glob(pattern), key=lambda x: x.stat().st_mtime, reverse=True):
            try:
                stat = p.stat()
                ok, _ = self.verify_database(p)
                out.append({
                    "path": str(p),
                    "name": p.name,
                    "size_bytes": stat.st_size,
                    "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "verified": ok,
                })
            except OSError:
                continue
        return out

    def _finalize_wal(self) -> None:
        """Checkpoint WAL and remove sidecar files so the DB file can be replaced."""
        if not self.db_path.exists():
            return
        try:
            conn = sqlite3.connect(str(self.db_path), timeout=10.0)
            try:
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                conn.execute("PRAGMA journal_mode=DELETE")
                conn.commit()
            finally:
                conn.close()
        except sqlite3.DatabaseError:
            pass
        for suffix in ("-wal", "-shm"):
            sibling = Path(str(self.db_path) + suffix)
            if sibling.exists():
                try:
                    sibling.unlink()
                except OSError:
                    logger.debug("Could not remove %s", sibling, exc_info=True)

    def restore_from(self, backup_path: Path) -> bool:
        """Replace the live database with a verified backup copy."""
        backup_path = Path(backup_path)
        if not backup_path.exists():
            logger.error("Restore failed — backup not found: %s", backup_path)
            return False

        ok, err = self.verify_database(backup_path)
        if not ok:
            logger.error("Restore aborted — backup corrupt: %s", err)
            return False

        with self._lock:
            try:
                self._finalize_wal()

                if self.db_path.exists():
                    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
                    self.backup_dir.mkdir(parents=True, exist_ok=True)
                    quarantine = self.backup_dir / f"{self.db_path.stem}.pre_restore.{ts}.bak"
                    shutil.copy2(self.db_path, quarantine)
                    logger.warning("Quarantined current database to %s", quarantine.name)

                for suffix in ("-wal", "-shm"):
                    sibling = Path(str(self.db_path) + suffix)
                    if sibling.exists():
                        try:
                            sibling.unlink()
                        except OSError:
                            logger.debug("Could not remove %s during restore", sibling)

                if self.db_path.exists():
                    self.db_path.unlink()

                shutil.copy2(backup_path, self.db_path)
                self._finalize_wal()

                ok, err = self.verify_database(self.db_path)
                if not ok:
                    logger.error("Restore completed but live DB still invalid: %s", err)
                    return False

                logger.info("Database restored from %s", backup_path.name)
                self.after_main_restore()
                return True
            except Exception:
                logger.exception("Database restore failed")
                return False

    def restore_latest_valid(self) -> bool:
        """Try backups newest-first until one restores successfully."""
        for entry in self.list_backups():
            if not entry.get("verified"):
                continue
            if self.restore_from(Path(entry["path"])):
                return True
        logger.error("No valid backup available for restore")
        return False

    def ensure_healthy_on_startup(self) -> bool:
        """Verify the live DB; auto-restore from backup when corrupt."""
        if not self.db_path.exists():
            logger.info("No database file yet — skipping integrity check")
            return True

        ok, err = self.verify_database()
        if ok:
            return True

        logger.error("Database integrity check failed on startup: %s", err)
        if self.restore_latest_valid():
            ok, err = self.verify_database()
            if ok:
                logger.info("Database recovered from backup")
                return True
            logger.error("Database still invalid after restore: %s", err)
        return False

    def attempt_recovery_on_error(self, error_message: str) -> bool:
        """Best-effort restore when a query surfaces corruption."""
        if not is_corruption_error(error_message):
            return False
        logger.error("Corruption detected during query — attempting restore")
        return self.restore_latest_valid()

    def _prune_backups(self) -> None:
        try:
            pattern = f"{self.db_path.stem}.*.bak"
            entries = sorted(
                self.backup_dir.glob(pattern),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            for stale in entries[self.retention:]:
                try:
                    stale.unlink(missing_ok=True)
                except OSError:
                    continue
        except Exception:
            logger.debug("Backup pruning failed", exc_info=True)


class PeriodicBackupWorker(threading.Thread):
    """Daemon thread that snapshots the database at a configured interval."""

    def __init__(self, backup_service: DatabaseBackupService):
        super().__init__(daemon=True, name="sakura-db-backup")
        self._svc = backup_service
        self._stop = threading.Event()
        self._interval = max(60.0, float(backup_service.interval_seconds))

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        if not self._svc.enabled:
            logger.info("Periodic database backup disabled")
            return

        if self._stop.wait(30.0):
            return

        while not self._stop.wait(self._interval):
            try:
                ok, _ = self._svc.verify_database()
                if not ok:
                    logger.warning("Skipping scheduled backup — database failed integrity check")
                    self._svc.restore_latest_valid()
                    continue
                self._svc.create_backup(reason="scheduled")
            except Exception:
                logger.exception("Periodic backup tick failed")
