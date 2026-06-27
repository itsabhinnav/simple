#!/usr/bin/env python3
"""Wipe all Sakura data and repopulate with comprehensive AAOS sample data.

Clears requirements, test cases, design tickets, specifications, users,
sessions, cache, activity log, and optional uploads/vector sidecar, then
seeds every entity type with varied field values for UI/filter testing.

Usage::

    cd backend
    python scripts/reset_and_seed_all.py
    python scripts/reset_and_seed_all.py --with-uploads
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from werkzeug.security import generate_password_hash  # noqa: E402

from src.infrastructure.configuration_manager import get_config_manager  # noqa: E402
from src.services.local_database_service import LocalDatabaseService  # noqa: E402
from scripts.seed_aaos_sample_data import (  # noqa: E402
    make_design_tickets,
    make_requirements,
    make_test_cases,
    insert_or_ignore,
    _ensure_design_tickets_table,
)
from scripts.seed_specifications import SPECS, _ensure_columns, _write_stub_file  # noqa: E402

# Dev-only credentials — not for production.
SAMPLE_USERS = [
    ("admin", "admin@sakura.local", "admin123", "System", "Administrator", "admin"),
    ("tester", "tester@sakura.local", "tester123", "Tara", "Tester", "user"),
    ("reviewer", "reviewer@sakura.local", "reviewer123", "Ravi", "Reviewer", "user"),
    ("lead", "lead@sakura.local", "lead123", "Lena", "Lead", "user"),
    ("guest", "guest@sakura.local", "guest123", "Gina", "Guest", "user"),
]

PREFERENCE_KEYS = [
    ("theme", "dark"),
    ("locale", "en"),
    ("dashboard.default_view", "table"),
    ("notifications.email", "true"),
]


def _db_path() -> Path:
    config = get_config_manager()
    db_path = Path(config.get_config("database.local_db_path", "data/local/dev/database/sakura_db.db"))
    if not db_path.is_absolute():
        db_path = BACKEND_DIR / db_path
    return db_path


def _vector_paths() -> list[Path]:
    root = BACKEND_DIR / "data" / "local" / "dev" / "vectors"
    names = ("sakura_vec.db", "sakura_vec.db-wal", "sakura_vec.db-shm", "sakura_vec.db-journal")
    return [root / n for n in names if (root / n).exists()]


def _tables(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return [r[0] for r in rows if r[0] != "sqlite_sequence"]


def clear_all_data(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA foreign_keys = OFF")
    for table in _tables(conn):
        conn.execute(f"DELETE FROM {table}")
    conn.execute("DELETE FROM sqlite_sequence")
    conn.commit()
    conn.execute("PRAGMA foreign_keys = ON")


def _ensure_specifications_table(conn: sqlite3.Connection) -> None:
    from src.services.bulk_import_service import TARGET_CONFIG  # noqa: WPS433

    ddl = TARGET_CONFIG["specifications"]["ddl"]
    if ddl:
        conn.execute(ddl)
        conn.commit()


def seed_users(conn: sqlite3.Connection) -> int:
    secret = generate_password_hash("dev-secret-key")
    count = 0
    for username, email, password, first, last, role in SAMPLE_USERS:
        conn.execute(
            """
            INSERT INTO users (
                username, email, password_hash, secret_key_hash, git_token_encrypted,
                first_name, last_name, role, created_at, updated_at
            ) VALUES (?, ?, ?, ?, NULL, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (username, email, generate_password_hash(password), secret, first, last, role),
        )
        count += 1
    conn.commit()
    return count


def seed_user_preferences(conn: sqlite3.Connection) -> int:
    users = conn.execute("SELECT id, username FROM users").fetchall()
    n = 0
    for user_id, username in users:
        for key, value in PREFERENCE_KEYS:
            conn.execute(
                """
                INSERT INTO user_preferences (user_id, preference_key, preference_value)
                VALUES (?, ?, ?)
                """,
                (user_id, key, value if username != "guest" else f"{value}-guest"),
            )
            n += 1
    conn.commit()
    return n


def seed_specifications(conn: sqlite3.Connection, uploads_root: Path) -> int:
    _ensure_specifications_table(conn)
    _ensure_columns(conn)
    n = 0
    for spec in SPECS:
        file_url = _write_stub_file(spec, uploads_root)
        conn.execute(
            """
            INSERT INTO specifications (
                spec_id, title, project, tags, category, version, status,
                file_url, file_name, source_url, created_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                spec["spec_id"],
                spec["title"],
                spec["project"],
                spec["tags"],
                spec["category"],
                spec["version"],
                spec["status"],
                file_url or "",
                spec.get("file_name") or "",
                spec.get("source_url") or "",
                "admin",
            ),
        )
        n += 1
    conn.commit()
    return n


def enrich_requirements(conn: sqlite3.Connection) -> None:
    """Back-fill extended requirement columns and cross-links."""
    reqs = conn.execute(
        "SELECT id, requirement_id, title, tags FROM requirements ORDER BY id"
    ).fetchall()
    tc_by_req: dict[str, list[str]] = {}
    for row in conn.execute(
        "SELECT test_case_id, associated_requirement_id FROM test_cases "
        "WHERE associated_requirement_id IS NOT NULL"
    ):
        tc_by_req.setdefault(row[1], []).append(row[0])

    dt_by_req: dict[str, list[str]] = {}
    for row in conn.execute(
        "SELECT design_ticket_id, linked_requirement_id FROM design_tickets "
        "WHERE linked_requirement_id IS NOT NULL"
    ):
        dt_by_req.setdefault(row[1], []).append(row[0])

    spec_rows = conn.execute(
        "SELECT spec_id, version, project FROM specifications ORDER BY spec_id, version DESC"
    ).fetchall()
    spec_lookup = {s[0]: (s[1], s[2]) for s in spec_rows}

    regions = ["NA", "EU", "APAC", "ME", "LATAM", "China", "India", "Japan"]
    brands = ["Volvo", "Polestar", "Tata", "Honda", "Renault", "Ford", "GM", "Hyundai"]
    methods = ["Test", "Analysis", "Inspection", "Demonstration"]
    statuses = ["Draft", "Approved", "Implemented", "Tested", "Closed"]

    for idx, (_pk, req_id, title, tags) in enumerate(reqs):
        prefix = req_id.split("_")[1] if "_" in req_id else "GEN"
        feature = (tags or "").split(",")[0] or "General"
        spec_id = f"SPEC_{prefix}" if f"SPEC_{prefix}" in spec_lookup else (spec_rows[idx % len(spec_rows)][0] if spec_rows else None)
        spec_ver, _proj = spec_lookup.get(spec_id, ("1.0.0", "AAOS Platform")) if spec_id else ("1.0.0", "AAOS Platform")
        linked_tcs = ",".join(tc_by_req.get(req_id, [])[:3])
        linked_dts = ",".join(dt_by_req.get(req_id, [])[:2])
        dt_id = dt_by_req.get(req_id, [None])[0]

        conn.execute(
            """
            UPDATE requirements SET
                srs_id = ?,
                feature = ?,
                region = ?,
                brand = ?,
                reference_spec_id = ?,
                reference_spec_version = ?,
                requirement_version = ?,
                verification_method = ?,
                linked_epic_jira_id = ?,
                linked_test_case_ids = ?,
                linked_design_ids = ?,
                design_ticket_id = ?,
                created_by = ?,
                status = ?
            WHERE requirement_id = ?
            """,
            (
                f"SRS-{prefix}-{idx + 1:04d}",
                feature,
                regions[idx % len(regions)],
                brands[idx % len(brands)],
                spec_id,
                spec_ver,
                f"1.{idx % 5}.{idx % 3}",
                methods[idx % len(methods)],
                f"AAOS-{1000 + idx}",
                linked_tcs or None,
                linked_dts or None,
                dt_id,
                "admin" if idx % 3 == 0 else "tester",
                statuses[idx % len(statuses)],
                req_id,
            ),
        )
    conn.commit()


def seed_activity_samples(conn: sqlite3.Connection) -> int:
    samples = [
        ("requirements", "REQ_BT_001", "create", "Created Bluetooth pairing requirement"),
        ("test_cases", "TC_BT_001", "create", "Added positive Bluetooth pairing test"),
        ("design_tickets", "DT_BT_01", "update", "Updated sequence diagram for Bluetooth"),
        ("specifications", "SPEC_BT", "create", "Uploaded Bluetooth spec v2.1.0"),
    ]
    n = 0
    for entity_type, entity_id, action, summary in samples:
        h = hashlib.sha1(f"{entity_type}:{entity_id}:{action}".encode()).hexdigest()[:12]
        conn.execute(
            """
            INSERT INTO activity_log (
                commit_hash, entity_type, entity_id, action, summary, author_username, author_id
            ) VALUES (?, ?, ?, ?, ?, ?, 1)
            """,
            (h, entity_type, entity_id, action, summary, "admin"),
        )
        n += 1
    conn.commit()
    return n


def seed_metadata(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        INSERT INTO database_metadata (metadata_key, metadata_value)
        VALUES ('version', '1')
        ON CONFLICT(metadata_key) DO UPDATE SET metadata_value='1', updated_at=CURRENT_TIMESTAMP
        """
    )
    conn.commit()


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset Sakura DB and seed sample data")
    parser.add_argument("--with-uploads", action="store_true", help="Also delete backend/uploads before re-seeding specs")
    args = parser.parse_args()

    db_path = _db_path()
    uploads_root = BACKEND_DIR / "uploads" / "specs"

    print(f"Target database: {db_path}")
    if not db_path.exists():
        print("Initializing schema …")
        if not LocalDatabaseService().initialize():
            print("Failed to initialize database.", file=sys.stderr)
            return 1

    from src.services.database_guard import backup_before_destructive

    snapshot = backup_before_destructive("pre_reset_seed", db_path=db_path)
    if snapshot:
        print(f"Pre-reset backup: {snapshot}")

    if args.with_uploads and uploads_root.parent.exists():
        shutil.rmtree(uploads_root, ignore_errors=True)
        print(f"Cleared {uploads_root}")

    for vec in _vector_paths():
        try:
            vec.unlink(missing_ok=True)
            print(f"Removed vector sidecar: {vec}")
        except OSError as exc:
            print(f"Skipped vector sidecar (in use): {vec} ({exc})")

    uploads_root.mkdir(parents=True, exist_ok=True)

    requirements = make_requirements()
    test_cases = make_test_cases(requirements)
    design_tickets = make_design_tickets(requirements)

    conn = sqlite3.connect(str(db_path))
    try:
        print("Clearing all tables …")
        before = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in _tables(conn)}
        print(json.dumps(before, indent=2))
        clear_all_data(conn)

        user_count = seed_users(conn)
        pref_count = seed_user_preferences(conn)

        _ensure_design_tickets_table(conn)
        _ensure_specifications_table(conn)

        req_ins, _ = insert_or_ignore(conn, "requirements", requirements, "requirement_id")
        tc_ins, _ = insert_or_ignore(conn, "test_cases", test_cases, "test_case_id")
        dt_ins, _ = insert_or_ignore(conn, "design_tickets", design_tickets, "design_ticket_id")
        spec_count = seed_specifications(conn, uploads_root)

        enrich_requirements(conn)
        activity_count = seed_activity_samples(conn)
        seed_metadata(conn)
    finally:
        conn.close()

    print()
    print("Reset + seed complete:")
    print(f"  users           : {user_count}")
    print(f"  user_preferences: {pref_count}")
    print(f"  requirements    : {req_ins}")
    print(f"  test_cases      : {tc_ins}")
    print(f"  design_tickets  : {dt_ins}")
    print(f"  specifications  : {spec_count}")
    print(f"  activity_log    : {activity_count}")
    print()
    print("Dev logins (password shown once):")
    for username, _email, password, *_rest in SAMPLE_USERS:
        print(f"  {username} / {password}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
