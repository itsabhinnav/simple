#!/usr/bin/env python3
"""Launch the Celery worker for the hybrid document parsing engine."""

from __future__ import annotations

import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))
sys.path.insert(0, str(backend_dir / "src"))

from src.infrastructure.celery_app import celery
import src.services.parsing.tasks  # noqa: F401 - ensure tasks are registered


def main() -> None:
    celery.worker_main(["worker", "-l", "INFO", "-Q", "parsing", "-c", "2"])


if __name__ == "__main__":
    main()
