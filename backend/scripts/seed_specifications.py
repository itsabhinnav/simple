#!/usr/bin/env python3
"""Seed 20 specification versions with projects, tags, and document links."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from src.infrastructure.configuration_manager import get_config_manager  # noqa: E402

SPECS = [
    {
        "spec_id": "SPEC_CHG",
        "title": "AAOS Apps & Play Store Specification",
        "project": "AAOS Platform",
        "version": "1.4.0",
        "status": "Official",
        "category": "SRS",
        "tags": "AAOS,apps,play-store,HMI",
        "file_name": "SPEC_CHG_v1.4.0.pdf",
        "source_url": "https://contoso.sharepoint.com/sites/AAOS/Specs/SPEC_CHG_v1.4.0.pdf",
    },
    {
        "spec_id": "SPEC_CHG",
        "title": "AAOS Apps & Play Store Specification",
        "project": "AAOS Platform",
        "version": "1.3.0",
        "status": "Official",
        "category": "SRS",
        "tags": "AAOS,apps,play-store,HMI",
        "file_name": "SPEC_CHG_v1.3.0.pdf",
        "source_url": "https://contoso.sharepoint.com/sites/AAOS/Specs/SPEC_CHG_v1.3.0.pdf",
    },
    {
        "spec_id": "SPEC_NAV",
        "title": "Navigation & Routing HMI Specification",
        "project": "AAOS Platform",
        "version": "3.0.0",
        "status": "Official",
        "category": "SRS",
        "tags": "navigation,routing,HMI,maps",
        "file_name": "SPEC_NAV_v3.0.0.docx",
        "source_url": "https://contoso.sharepoint.com/sites/AAOS/Specs/SPEC_NAV_v3.0.0.docx",
    },
    {
        "spec_id": "SPEC_NAV",
        "title": "Navigation & Routing HMI Specification",
        "project": "AAOS Platform",
        "version": "2.8.1",
        "status": "Draft",
        "category": "SRS",
        "tags": "navigation,routing,HMI,maps",
        "file_name": "SPEC_NAV_v2.8.1.docx",
        "source_url": "https://contoso.sharepoint.com/sites/AAOS/Specs/SPEC_NAV_v2.8.1.docx",
    },
    {
        "spec_id": "SPEC_BT",
        "title": "Bluetooth Pairing & Audio Routing",
        "project": "Connectivity",
        "version": "2.1.0",
        "status": "Official",
        "category": "Interface",
        "tags": "bluetooth,audio,pairing,connectivity",
        "file_name": "SPEC_BT_v2.1.0.pdf",
        "source_url": "https://contoso.sharepoint.com/sites/Connectivity/SPEC_BT_v2.1.0.pdf",
    },
    {
        "spec_id": "SPEC_WIFI",
        "title": "In-Vehicle Wi-Fi Hotspot Requirements",
        "project": "Connectivity",
        "version": "1.0.0",
        "status": "Official",
        "category": "PRD",
        "tags": "wifi,hotspot,TCU,connectivity",
        "file_name": "SPEC_WIFI_v1.0.0.pdf",
        "source_url": "https://contoso.sharepoint.com/sites/Connectivity/SPEC_WIFI_v1.0.0.pdf",
    },
    {
        "spec_id": "SPEC_CARPLAY",
        "title": "Apple CarPlay Integration Specification",
        "project": "Connectivity",
        "version": "2.4.0",
        "status": "Official",
        "category": "SRS",
        "tags": "carplay,projection,USB,wireless",
        "file_name": "SPEC_CARPLAY_v2.4.0.pdf",
        "source_url": "https://contoso.sharepoint.com/sites/Connectivity/SPEC_CARPLAY_v2.4.0.pdf",
    },
    {
        "spec_id": "SPEC_CLIMATE",
        "title": "Climate Control HMI & Signal Specification",
        "project": "HVAC",
        "version": "4.3.0",
        "status": "Draft",
        "category": "SRS",
        "tags": "HVAC,climate,HMI,comfort",
        "file_name": "SPEC_CLIMATE_v4.3.0.xlsx",
        "source_url": "https://contoso.sharepoint.com/sites/HVAC/SPEC_CLIMATE_v4.3.0.xlsx",
    },
    {
        "spec_id": "SPEC_CLIMATE",
        "title": "Climate Control HMI & Signal Specification",
        "project": "HVAC",
        "version": "4.2.0",
        "status": "Official",
        "category": "SRS",
        "tags": "HVAC,climate,HMI,comfort",
        "file_name": "SPEC_CLIMATE_v4.2.0.xlsx",
        "source_url": "https://contoso.sharepoint.com/sites/HVAC/SPEC_CLIMATE_v4.2.0.xlsx",
    },
    {
        "spec_id": "SPEC_SEAT",
        "title": "Seat Heating & Ventilation Control",
        "project": "HVAC",
        "version": "1.1.0",
        "status": "Official",
        "category": "Functional",
        "tags": "seats,heating,ventilation,comfort",
        "file_name": "SPEC_SEAT_v1.1.0.pdf",
        "source_url": "https://contoso.sharepoint.com/sites/HVAC/SPEC_SEAT_v1.1.0.pdf",
    },
    {
        "spec_id": "SPEC_CAM",
        "title": "Surround View Camera System Specification",
        "project": "ADAS",
        "version": "2.1.0",
        "status": "Official",
        "category": "SRS",
        "tags": "ADAS,camera,SVM,parking",
        "file_name": "SPEC_CAM_v2.1.0.pdf",
        "source_url": "https://contoso.sharepoint.com/sites/ADAS/SPEC_CAM_v2.1.0.pdf",
    },
    {
        "spec_id": "SPEC_AEB",
        "title": "Automatic Emergency Braking Requirements",
        "project": "ADAS",
        "version": "1.0.0",
        "status": "Draft",
        "category": "Safety",
        "tags": "AEB,braking,safety,NCAP",
        "file_name": "SPEC_AEB_v1.0.0.pdf",
        "source_url": "https://contoso.sharepoint.com/sites/ADAS/SPEC_AEB_v1.0.0.pdf",
    },
    {
        "spec_id": "SPEC_EV_BMS",
        "title": "Battery Management System Interface Spec",
        "project": "Powertrain",
        "version": "1.0.0",
        "status": "Draft",
        "category": "Interface",
        "tags": "EV,BMS,battery,powertrain",
        "file_name": "SPEC_EV_BMS_v1.0.0.docx",
        "source_url": "https://contoso.sharepoint.com/sites/Powertrain/SPEC_EV_BMS_v1.0.0.docx",
    },
    {
        "spec_id": "SPEC_REGEN",
        "title": "Regenerative Braking Control Specification",
        "project": "Powertrain",
        "version": "2.0.0",
        "status": "Official",
        "category": "Functional",
        "tags": "regen,braking,EV,efficiency",
        "file_name": "SPEC_REGEN_v2.0.0.pdf",
        "source_url": "https://contoso.sharepoint.com/sites/Powertrain/SPEC_REGEN_v2.0.0.pdf",
    },
    {
        "spec_id": "SPEC_HMI_GUIDE",
        "title": "AAOS HMI Design Language Guide",
        "project": "UX Design",
        "version": "3.1.0",
        "status": "Draft",
        "category": "HMI",
        "tags": "UX,HMI,design,tokens",
        "file_name": "SPEC_HMI_GUIDE_v3.1.0.pdf",
        "source_url": "https://contoso.sharepoint.com/sites/UX/SPEC_HMI_GUIDE_v3.1.0.pdf",
    },
    {
        "spec_id": "SPEC_HMI_GUIDE",
        "title": "AAOS HMI Design Language Guide",
        "project": "UX Design",
        "version": "3.0.0",
        "status": "Official",
        "category": "HMI",
        "tags": "UX,HMI,design,tokens",
        "file_name": "SPEC_HMI_GUIDE_v3.0.0.pdf",
        "source_url": "https://contoso.sharepoint.com/sites/UX/SPEC_HMI_GUIDE_v3.0.0.pdf",
    },
    {
        "spec_id": "SPEC_CYBER",
        "title": "Cybersecurity Requirements for IVI",
        "project": "Security",
        "version": "1.0.0",
        "status": "Draft",
        "category": "Security",
        "tags": "cybersecurity,ISO21434,IVI",
        "file_name": "SPEC_CYBER_v1.0.0.pdf",
        "source_url": "https://contoso.sharepoint.com/sites/Security/SPEC_CYBER_v1.0.0.pdf",
    },
    {
        "spec_id": "SPEC_SECURE_BOOT",
        "title": "Secure Boot & Trust Chain Specification",
        "project": "Security",
        "version": "1.2.0",
        "status": "Official",
        "category": "Security",
        "tags": "secure-boot,trust-chain,TEE",
        "file_name": "SPEC_SECURE_BOOT_v1.2.0.pdf",
        "source_url": "https://contoso.sharepoint.com/sites/Security/SPEC_SECURE_BOOT_v1.2.0.pdf",
    },
    {
        "spec_id": "SPEC_UDS",
        "title": "UDS Diagnostic Services over DoIP",
        "project": "Diagnostics",
        "version": "5.0.0",
        "status": "Official",
        "category": "Diagnostic",
        "tags": "UDS,DoIP,OBD,diagnostics",
        "file_name": "SPEC_UDS_v5.0.0.xlsx",
        "source_url": "https://contoso.sharepoint.com/sites/Diagnostics/SPEC_UDS_v5.0.0.xlsx",
    },
    {
        "spec_id": "SPEC_DTC",
        "title": "DTC Catalogue & Fault Memory Layout",
        "project": "Diagnostics",
        "version": "2.0.0",
        "status": "Official",
        "category": "Diagnostic",
        "tags": "DTC,fault-memory,diagnostics",
        "file_name": "SPEC_DTC_v2.0.0.xlsx",
        "source_url": "https://contoso.sharepoint.com/sites/Diagnostics/SPEC_DTC_v2.0.0.xlsx",
    },
]


def _db_path() -> Path:
    config = get_config_manager()
    db_path = Path(config.get_config("database.local_db_path", "data/local/dev/database/sakura_db.db"))
    if not db_path.is_absolute():
        db_path = BACKEND_DIR / db_path
    return db_path


def _ensure_columns(conn: sqlite3.Connection) -> None:
    existing = {row[1] for row in conn.execute("PRAGMA table_info(specifications)")}
    for col, col_type in {
        "tags": "TEXT",
        "file_name": "TEXT",
        "source_url": "TEXT",
        "project": "TEXT",
    }.items():
        if col not in existing:
            conn.execute(f"ALTER TABLE specifications ADD COLUMN {col} {col_type}")
    conn.commit()


def _write_stub_file(spec: dict, uploads_root: Path) -> str | None:
    """Create a tiny local file so Download works in the app."""
    file_name = spec.get("file_name")
    if not file_name:
        return None
    safe_spec = spec["spec_id"].replace(" ", "_")
    dest_dir = uploads_root / safe_spec
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / file_name
    if not dest.exists():
        body = (
            f"Placeholder specification document\n"
            f"Spec ID: {spec['spec_id']}\n"
            f"Version: {spec['version']}\n"
            f"Project: {spec['project']}\n"
            f"Title: {spec['title']}\n"
            f"Source: {spec.get('source_url', '')}\n"
        )
        dest.write_text(body, encoding="utf-8")
    return f"{safe_spec}/{file_name}".replace("\\", "/")


def main() -> int:
    db_path = _db_path()
    uploads_root = BACKEND_DIR / "uploads" / "specs"
    uploads_root.mkdir(parents=True, exist_ok=True)

    print(f"Seeding {len(SPECS)} specifications into {db_path}")
    conn = sqlite3.connect(str(db_path))
    try:
        _ensure_columns(conn)
        inserted = 0
        skipped = 0
        for spec in SPECS:
            cur = conn.execute(
                """
                SELECT id FROM specifications
                WHERE spec_id = ? AND COALESCE(project, '') = ? AND COALESCE(version, '') = ?
                """,
                (spec["spec_id"], spec["project"], spec["version"]),
            )
            if cur.fetchone():
                skipped += 1
                continue

            file_url = _write_stub_file(spec, uploads_root)
            conn.execute(
                """
                INSERT INTO specifications (
                    spec_id, title, project, tags, category, version, status,
                    file_url, file_name, source_url, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
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
                ),
            )
            inserted += 1
        conn.commit()
        total = conn.execute("SELECT COUNT(*) FROM specifications").fetchone()[0]
        print(f"  inserted={inserted} skipped={skipped} total_in_db={total}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
