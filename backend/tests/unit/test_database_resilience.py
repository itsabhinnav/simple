"""Unit tests for database backup and migration services."""

import sqlite3
from pathlib import Path

import pytest

from src.services.database_backup_service import (
    DatabaseBackupService,
    is_corruption_error,
)
from src.services.database_migration_service import DatabaseMigrationService
from src.services.local_database_service import LocalDatabaseService


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE database_metadata (
            metadata_key TEXT UNIQUE,
            metadata_value TEXT
        )
        """
    )
    conn.execute(
        "INSERT INTO database_metadata (metadata_key, metadata_value) VALUES ('version', '1')"
    )
    conn.execute(
        """
        CREATE TABLE requirements (
            id INTEGER PRIMARY KEY,
            requirement_id TEXT UNIQUE,
            title TEXT,
            status TEXT,
            priority TEXT,
            version TEXT
        )
        """
    )
    conn.execute(
        "INSERT INTO requirements (requirement_id, title) VALUES ('REQ-1', 'Legacy row')"
    )
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def backup_service(temp_db, monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "test")
    svc = DatabaseBackupService(temp_db)
    svc.retention  # property access
    return svc


@pytest.fixture
def local_db(temp_db, monkeypatch):
    monkeypatch.setenv("SAKURA_LOCAL_DB_PATH", str(temp_db))
    return LocalDatabaseService()


class TestCorruptionDetection:
    def test_is_corruption_error_positive(self):
        assert is_corruption_error("database disk image is malformed")

    def test_is_corruption_error_negative(self):
        assert not is_corruption_error("no such table: foo")


class TestDatabaseBackupService:
    def test_verify_healthy_database(self, backup_service):
        ok, err = backup_service.verify_database()
        assert ok, err

    def test_create_and_list_backup(self, backup_service):
        path = backup_service.create_backup(reason="test")
        assert path is not None
        assert path.exists()
        backups = backup_service.list_backups()
        assert len(backups) == 1
        assert backups[0]["verified"] is True

    def test_restore_from_backup(self, backup_service, temp_db):
        path = backup_service.create_backup(reason="test")
        assert path is not None

        data = temp_db.read_bytes()
        temp_db.write_bytes(b"NOT A VALID SQLITE FILE" + data[24:])

        ok, _ = backup_service.verify_database()
        assert not ok

        assert backup_service.restore_from(path)
        ok, _ = backup_service.verify_database()
        assert ok

        conn = sqlite3.connect(str(temp_db))
        row = conn.execute(
            "SELECT title FROM requirements WHERE requirement_id='REQ-1'"
        ).fetchone()
        conn.close()
        assert row[0] == "Legacy row"

    def test_restore_latest_valid(self, backup_service, temp_db):
        backup_service.create_backup(reason="test")
        data = temp_db.read_bytes()
        temp_db.write_bytes(b"CORRUPTED" + data[9:])
        assert backup_service.restore_latest_valid()
        ok, _ = backup_service.verify_database()
        assert ok


class TestDatabaseMigrationService:
    def test_adds_missing_columns_and_defaults(self, local_db, temp_db):
        svc = DatabaseMigrationService(local_db)
        assert svc.run_all()

        with sqlite3.connect(str(temp_db)) as conn:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(requirements)")}
            assert "given" in cols
            row = conn.execute(
                "SELECT status, priority, version FROM requirements WHERE requirement_id='REQ-1'"
            ).fetchone()
        assert row == ("Draft", "P2", "1.0")

    def test_retired_column_forwarding(self, local_db, temp_db):
        with sqlite3.connect(str(temp_db)) as conn:
            conn.execute(
                """
                CREATE TABLE test_cases (
                    id INTEGER PRIMARY KEY,
                    test_case_id TEXT UNIQUE,
                    description TEXT,
                    test_objective TEXT,
                    vehicle_mode TEXT,
                    vehicle_specification TEXT
                )
                """
            )
            conn.execute(
                "INSERT INTO test_cases (test_case_id, description, vehicle_mode) "
                "VALUES ('TC-1', 'legacy desc', 'EV')"
            )
            conn.commit()

        svc = DatabaseMigrationService(local_db)
        svc.run_all()

        with sqlite3.connect(str(temp_db)) as conn:
            row = conn.execute(
                "SELECT test_objective, vehicle_specification FROM test_cases WHERE test_case_id='TC-1'"
            ).fetchone()
        assert row == ("legacy desc", "EV")
