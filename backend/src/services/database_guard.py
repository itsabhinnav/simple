"""Shared helpers for destructive database operations."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from src.infrastructure.logging_config import get_logger

logger = get_logger(__name__)


def backup_before_destructive(reason: str, db_path: Optional[Path] = None) -> Optional[Path]:
    """Snapshot the primary DB (and vector sidecar) before a destructive action."""
    try:
        if db_path is not None:
            from src.services.database_backup_service import DatabaseBackupService

            svc = DatabaseBackupService(db_path)
        else:
            from src.infrastructure.dependency_injection import get_database_backup_service

            svc = get_database_backup_service()
        path = svc.create_backup(reason=reason)
        svc.backup_auxiliary_databases(reason=reason)
        return path
    except Exception:
        logger.exception("Pre-destructive backup failed (reason=%s)", reason)
        return None
