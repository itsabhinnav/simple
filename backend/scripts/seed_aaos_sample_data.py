#!/usr/bin/env python3
"""Seed the local SQLite database with a generous, AAOS-themed sample
dataset: requirements, design tickets, test cases (using the new
title/description/vehicle_model/severity columns), and specifications.

Idempotent. Re-running it INSERTs only rows whose primary IDs are not
already in the database, so it is safe to run repeatedly.

Usage::

    cd backend
    python scripts/seed_aaos_sample_data.py

The script targets the same DB path the running backend uses
(``backend/data/local/dev/database/sakura_db.db`` by default, or
whatever ``database.local_db_path`` is set to in config.yaml).
"""
from __future__ import annotations

import random
import sqlite3
import sys
from pathlib import Path

# Make the backend package importable so we can reuse its config helpers
# and table-creation logic.
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from src.infrastructure.configuration_manager import get_config_manager  # noqa: E402
from src.services.local_database_service import LocalDatabaseService  # noqa: E402
from src.services.bulk_import_service import TARGET_CONFIG  # noqa: E402

RANDOM_SEED = 24  # deterministic IDs so repeat runs are clean
random.seed(RANDOM_SEED)


# ---------------------------------------------------------------------------
# AAOS sample data pools
# ---------------------------------------------------------------------------

VEHICLE_MODELS = [
    "Volvo EX90", "Polestar 3", "Polestar 4", "Tata Curvv.ev",
    "Honda 0 SUV", "Renault Scenic E-Tech", "Ford F-150 Lightning",
    "Lucid Air", "Rivian R1S", "Genesis GV70", "Lotus Eletre",
    "Cadillac Escalade IQ",
]

REGIONS = ["NA", "EU", "APAC", "ME", "LATAM", "China", "India", "Japan"]
BRANDS = ["Volvo", "Polestar", "Tata", "Honda", "Renault", "Ford", "GM", "Hyundai"]
TEST_TYPES = ["Positive", "Negative", "Boundary", "Performance"]
PRIORITIES = ["P1", "P2", "P3"]
SEVERITIES = ["Blocker", "Critical", "Major", "Minor", "Trivial"]
TESTSUITE_TYPES = ["Smoke", "Regression", "Sanity", "End-to-End", "Sanity-OTA"]
REQUIREMENT_TYPES = ["Functional", "HMI", "Safety", "Performance", "Usability"]
REQ_STATUSES = ["Draft", "Approved", "Implemented", "Tested", "Closed"]
DESIGN_TYPES = [
    "Sequence Diagram", "State Flow Diagram", "Architecture Diagram",
    "Component Diagram", "HMI Wireframe", "User Flow", "Service Diagram",
]
ASSIGNEES = [
    "Alice Chen", "Bob Singh", "Carla Rossi", "Diego Martín",
    "Elena Kim", "Frederik Vogel", "Geeta Iyer", "Hiroshi Tanaka",
]

# Each feature area defines:
#   prefix      → used in test_case_id (e.g. TC_BT_001)
#   description → used both for requirement description templates and TC titles
AAOS_FEATURES = [
    ("Bluetooth", "BT", [
        "Pair phone via Bluetooth",
        "Auto-reconnect after engine restart",
        "Handle PBAP contact sync",
        "Hands-free call audio routing",
        "Stream media via A2DP",
        "Unpair device cleanly",
        "Bluetooth LE Audio multi-stream",
        "Reject pairing with unsupported profile",
    ]),
    ("Radio", "RAD", [
        "Tune AM/FM/DAB station",
        "Auto-store presets",
        "Switch source FM ↔ DAB",
        "Display RDS metadata",
        "Resume last station on cold boot",
        "Handle weak-signal degradation",
    ]),
    ("Phone Calls", "TEL", [
        "Place outgoing call via voice",
        "Receive incoming call popup",
        "End call from steering wheel",
        "Switch audio to handset",
        "Mute microphone during call",
        "Display recent call list",
    ]),
    ("Navigation", "NAV", [
        "Set destination via search",
        "Reroute on missed turn",
        "Display 3D landmarks",
        "Estimate EV range to destination",
        "Add waypoint mid-route",
        "Handle GPS dropout in tunnel",
        "Show traffic-aware ETA",
        "Switch to off-line map tiles",
    ]),
    ("Voice Assistant", "VA", [
        "Wake word activates assistant",
        "Send SMS via voice",
        "Open Google Maps via voice",
        "Reject wake when window open at speed",
        "Multi-turn climate command",
        "Privacy mute toggle disables wake",
    ]),
    ("Climate Control", "CLI", [
        "Adjust driver temperature",
        "Sync passenger temperature",
        "Activate defrost mode",
        "Auto fan-speed on AUTO mode",
        "Heat seat from cold-start",
        "Restore last climate state on key-on",
    ]),
    ("EV Charging", "CHG", [
        "Start AC charging session",
        "Schedule overnight charging",
        "Stop charging on user lock",
        "Display charge curve and SoC",
        "Handle public charger error E03",
        "Resume after temporary unplug",
    ]),
    ("Driver Display", "DD", [
        "Show speed and tachometer",
        "Display ADAS warnings",
        "Switch driver view layout",
        "Show navigation turn-by-turn",
        "Render low-beam icon at night",
    ]),
    ("Apps & Play Store", "APP", [
        "Install Spotify from Play Store",
        "Update YouTube Music silently",
        "Uninstall non-default app",
        "Background app survives ignition cycle",
        "Restrict driver-distraction app while moving",
    ]),
    ("OTA", "OTA", [
        "Detect available OTA update",
        "Download update on Wi-Fi only",
        "Defer install while driving",
        "Resume interrupted download",
        "Rollback on failed install",
    ]),
    ("HMI Shell", "HMI", [
        "Dark mode toggles on dusk",
        "Multi-user profile switch",
        "Notification center renders priority items",
        "App tray sorts by usage",
        "Quick settings respond < 200ms",
    ]),
    ("Connectivity", "CON", [
        "Connect to vehicle Wi-Fi hotspot",
        "Switch APN automatically by region",
        "Handle 5G ↔ 4G cell handover",
        "Verify VPN tunnel for fleet vehicles",
    ]),
]


def _id_pad(n: int, width: int = 3) -> str:
    return f"{n:0{width}d}"


def make_requirements() -> list[dict]:
    """Build a list of requirements covering every AAOS feature area."""
    items: list[dict] = []
    counter = 0
    for feature, prefix, examples in AAOS_FEATURES:
        for sub in examples:
            counter += 1
            req_type = random.choice(REQUIREMENT_TYPES)
            items.append({
                "requirement_id": f"REQ_{prefix}_{_id_pad(counter)}",
                "title": f"{feature}: {sub}",
                "description": (
                    f"As an AAOS driver, the system shall support `{sub.lower()}` "
                    f"reliably across supported vehicle platforms."
                ),
                "given": f"the vehicle is in READY state with {feature} subsystem powered",
                "when_action": f"the user attempts to {sub.lower()}",
                "then_result": (
                    f"the system completes the action with no driver-visible "
                    f"errors and reports success within the SLA"
                ),
                "requirement_type": req_type,
                "priority": random.choice(PRIORITIES + ["P4"]),
                "status": random.choice(REQ_STATUSES),
                "assignee": random.choice(ASSIGNEES),
                "tags": f"{feature},{req_type},AAOS",
            })
    return items


def make_test_cases(requirements: list[dict]) -> list[dict]:
    """Build test cases that reference the seeded requirements and exercise
    the new title/description/vehicle_model/severity columns."""
    items: list[dict] = []
    req_lookup: dict[str, list[dict]] = {}
    for req in requirements:
        # Group requirements by feature prefix so each test case can pick a
        # related requirement to cross-link.
        key = req["requirement_id"].split("_")[1]
        req_lookup.setdefault(key, []).append(req)

    counter = 0
    for feature, prefix, examples in AAOS_FEATURES:
        # 2 variants per example × N examples → reasonable coverage per area
        for sub in examples:
            for variant_idx, variant in enumerate(("Positive", "Negative"), start=1):
                counter += 1
                related = random.choice(req_lookup.get(prefix, [{"requirement_id": None}]))
                model = random.choice(VEHICLE_MODELS)
                severity = random.choice(SEVERITIES)
                items.append({
                    "test_case_id": f"TC_{prefix}_{_id_pad(counter)}",
                    "title": f"{sub} — {variant} path on {model}",
                    "description": (
                        f"Validates the {variant.lower()} path for `{sub.lower()}` on "
                        f"{model}. Covers AAOS {feature} stack including HU UI, "
                        f"connectivity layer, and downstream services."
                    ),
                    "vehicle_model": model,
                    "severity": severity,
                    "feature": feature,
                    "test_type": variant if variant in TEST_TYPES else "Positive",
                    "priority": random.choice(PRIORITIES),
                    "testsuite_type": random.choice(TESTSUITE_TYPES),
                    "region": random.choice(REGIONS),
                    "brand": random.choice(BRANDS),
                    "vehicle_variant": random.choice(["Standard", "Premium", "Long Range", "Performance"]),
                    "vehicle_specification": f"{model} - {random.choice(['LHD', 'RHD'])}",
                    "env_dependency": random.choice(["HU FW >= 24.06", "AOSP 14", "AAOS Auto API 7", "Lab bench HU"]),
                    "requirement_type": random.choice(REQUIREMENT_TYPES),
                    "regulation": random.choice(["UN-R155", "FMVSS 138", "GDPR", "—"]),
                    "test_objective": f"Verify {sub.lower()} on {model} produces expected {variant.lower()} outcome.",
                    "preconditions": (
                        f"Vehicle is in READY state. {feature} subsystem powered. "
                        f"User '{random.choice(ASSIGNEES)}' is signed into the HU. "
                        f"Bench/network simulator is configured for region {random.choice(REGIONS)}."
                    ),
                    "procedure": (
                        f"1. Open AAOS {feature} app from the launcher.\n"
                        f"2. Trigger the `{sub.lower()}` flow.\n"
                        f"3. Observe HU UI, audio routing, and CAN traces.\n"
                        f"4. Capture screenshots and logcat between t=0 and t=10s."
                    ),
                    "expected_behavior": (
                        f"The HU completes the flow within the published SLA, "
                        f"no UI freezes occur, and the relevant CAN signals/Carrier "
                        f"telemetry confirm success ({variant.lower()} expected)."
                    ),
                    "associated_requirement_id": related.get("requirement_id"),
                    "screen_id": f"SCR_{prefix}_{_id_pad(variant_idx, 2)}",
                    "reference_document": f"AAOS-{feature.replace(' ', '_')}-SPEC v1.{counter % 7}",
                    "dr_applicable_screens": f"SCR_{prefix}_01,SCR_{prefix}_02",
                    "dr_id": f"DR_{prefix}_{_id_pad(counter)}",
                })
    return items


def make_design_tickets(requirements: list[dict]) -> list[dict]:
    items: list[dict] = []
    for idx, feature_block in enumerate(AAOS_FEATURES, start=1):
        feature, prefix, examples = feature_block
        for j, sub in enumerate(examples[:3], start=1):  # 3 designs per feature
            related = next(
                (r for r in requirements if r["requirement_id"].split("_")[1] == prefix),
                None,
            )
            items.append({
                "design_ticket_id": f"DT_{prefix}_{_id_pad(j, 2)}",
                "title": f"{feature} — design for {sub}",
                "description": (
                    f"Architectural design covering {sub.lower()}. Includes HU "
                    f"component boundaries, AAOS Auto API surface, "
                    f"and CAN/Service binding for the {feature} subsystem."
                ),
                "design_type": random.choice(DESIGN_TYPES),
                "diagram_type": random.choice(DESIGN_TYPES),
                "image_url": None,
                "priority": random.choice(PRIORITIES + ["P4"]),
                "status": random.choice(["Draft", "Review", "Approved", "In Progress"]),
                "linked_requirement_id": related["requirement_id"] if related else None,
                "assignee": random.choice(ASSIGNEES),
                "tags": f"{feature},AAOS,design",
            })
    return items


def make_specifications() -> list[dict]:
    items: list[dict] = []
    for feature, prefix, _ in AAOS_FEATURES:
        items.append({
            "spec_id": f"SPEC_{prefix}",
            "title": f"AAOS {feature} Specification",
            "description": (
                f"Functional and HMI specification for the {feature} subsystem "
                f"in AAOS-based vehicles. Defines public APIs, signal contracts, "
                f"and HMI invariants."
            ),
            "category": "Functional",
            "version": f"1.{random.randint(0, 9)}.{random.randint(0, 9)}",
            "status": random.choice(["Draft", "Approved", "Released"]),
            "file_url": None,
        })
    return items


# ---------------------------------------------------------------------------
# Insertion helpers — use parameterized INSERT OR IGNORE so reruns are safe.
# ---------------------------------------------------------------------------

def _ensure_design_tickets_table(conn: sqlite3.Connection) -> None:
    """`design_tickets` is created lazily by BulkImportService — make sure
    it exists before we try to seed it."""
    ddl = TARGET_CONFIG["design_tickets"]["ddl"]
    if ddl:
        conn.execute(ddl)
        conn.commit()


def insert_or_ignore(conn: sqlite3.Connection, table: str, rows: list[dict], id_field: str) -> tuple[int, int]:
    """Bulk-insert ``rows`` into ``table`` skipping any that already exist
    (matched by ``id_field``). Returns ``(inserted, skipped)``."""
    if not rows:
        return 0, 0
    inserted = 0
    skipped = 0
    cur = conn.cursor()
    for row in rows:
        cur.execute(f"SELECT 1 FROM {table} WHERE {id_field} = ?", (row[id_field],))
        if cur.fetchone():
            skipped += 1
            continue
        cols = list(row.keys())
        placeholders = ", ".join("?" for _ in cols)
        cols_sql = ", ".join(cols)
        values = tuple(row[c] for c in cols)
        cur.execute(
            f"INSERT INTO {table} ({cols_sql}, created_at, updated_at) "
            f"VALUES ({placeholders}, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
            values,
        )
        inserted += 1
    conn.commit()
    return inserted, skipped


def main() -> int:
    config = get_config_manager()
    db_path = Path(config.get_config("database.local_db_path", "data/local/dev/database/sakura_db.db"))
    if not db_path.is_absolute():
        db_path = BACKEND_DIR / db_path

    print(f"Seeding sample AAOS data into: {db_path}")
    if not db_path.exists():
        print("DB does not exist yet — initializing schema via LocalDatabaseService …")
        svc = LocalDatabaseService()
        if not svc.initialize():
            print("Failed to initialize the local database.", file=sys.stderr)
            return 1

    # Build the dataset once so cross-references (TC → REQ, DT → REQ) line up.
    requirements = make_requirements()
    test_cases = make_test_cases(requirements)
    design_tickets = make_design_tickets(requirements)
    specifications = make_specifications()

    conn = sqlite3.connect(str(db_path))
    try:
        _ensure_design_tickets_table(conn)

        req_ins, req_skip = insert_or_ignore(conn, "requirements", requirements, "requirement_id")
        tc_ins, tc_skip = insert_or_ignore(conn, "test_cases", test_cases, "test_case_id")
        dt_ins, dt_skip = insert_or_ignore(conn, "design_tickets", design_tickets, "design_ticket_id")
        spec_ins, spec_skip = insert_or_ignore(conn, "specifications", specifications, "spec_id")
    finally:
        conn.close()

    print()
    print("Seed complete:")
    print(f"  requirements  : inserted={req_ins:<4d} skipped={req_skip} (total source rows {len(requirements)})")
    print(f"  test_cases    : inserted={tc_ins:<4d} skipped={tc_skip} (total source rows {len(test_cases)})")
    print(f"  design_tickets: inserted={dt_ins:<4d} skipped={dt_skip} (total source rows {len(design_tickets)})")
    print(f"  specifications: inserted={spec_ins:<4d} skipped={spec_skip} (total source rows {len(specifications)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
