"""One-shot maintenance script: delete every row from the users table.

Run from the backend folder:

    python scripts/delete_all_users.py

Goes through HybridDatabaseService so the local cache + database
metadata version are invalidated the same way an API write would do.
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND_ROOT = os.path.abspath(os.path.join(HERE, os.pardir))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from src.infrastructure.dependency_injection import (  # noqa: E402
    get_container,
    get_hybrid_database_service,
)


def _count(db) -> int:
    res = db.execute_query("SELECT COUNT(*) AS c FROM users", use_cache=False)
    if not res.get("success"):
        raise RuntimeError(f"count query failed: {res.get('error')}")
    rows = res.get("data") or []
    return int(rows[0]["c"]) if rows else 0


def main() -> int:
    get_container()
    db = get_hybrid_database_service()

    print(f"users before: {_count(db)}")

    res = db.execute_query("DELETE FROM users")
    if not res.get("success"):
        print(f"DELETE failed: {res.get('error')}", file=sys.stderr)
        return 1

    print(f"users after:  {_count(db)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
