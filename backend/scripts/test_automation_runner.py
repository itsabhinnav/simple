#!/usr/bin/env python3
"""Example local test-automation runner invoked by Sakura.

Configure in config.yaml:

  test_automation:
    enabled: true
    mode: subprocess
    subprocess:
      command: ["python", "scripts/test_automation_runner.py"]
      working_directory: backend
      timeout_seconds: 300
      input_via: stdin_json

Reads a JSON payload from stdin and prints a JSON result to stdout.
Replace this script with your real harness (pytest, Robot, custom UI driver, …).
"""

from __future__ import annotations

import json
import sys
from typing import Any, Dict, List


def main() -> int:
    raw = sys.stdin.read().strip()
    payload: Dict[str, Any]
    if raw:
        payload = json.loads(raw)
    else:
        payload = {"test_case_ids": sys.argv[1:]}

    ids: List[str] = [str(x) for x in payload.get("test_case_ids") or []]
    suite = payload.get("suite_name")
    print(
        json.dumps(
            {
                "accepted": True,
                "message": f"Queued {len(ids)} test case(s)"
                + (f" for suite {suite!r}" if suite else ""),
                "test_case_ids": ids,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
