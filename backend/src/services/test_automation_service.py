"""Invoke a local test-automation runner via subprocess or loopback HTTP."""

from __future__ import annotations

import json
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.infrastructure.configuration_manager import get_config_manager
from src.infrastructure.logging_config import get_logger

logger = get_logger(__name__)

_DEFAULT_CONFIG: Dict[str, Any] = {
    "enabled": False,
    "mode": "subprocess",
    "subprocess": {
        "command": ["python", "scripts/test_automation_runner.py"],
        "working_directory": "backend",
        "timeout_seconds": 300,
        "input_via": "stdin_json",
    },
    "http": {
        "url": "http://127.0.0.1:8080/execute",
        "method": "POST",
        "timeout_seconds": 120,
        "headers": {"Content-Type": "application/json"},
    },
}


class TestAutomationService:
    """Bridge to an external on-machine test runner."""

    def __init__(self) -> None:
        self._config_manager = get_config_manager()

    def _cfg(self) -> Dict[str, Any]:
        raw = self._config_manager.get_config("test_automation", None)
        if not isinstance(raw, dict):
            return dict(_DEFAULT_CONFIG)
        merged = dict(_DEFAULT_CONFIG)
        merged.update({k: v for k, v in raw.items() if k in ("enabled", "mode")})
        for section in ("subprocess", "http"):
            base = dict(_DEFAULT_CONFIG.get(section, {}))
            incoming = raw.get(section)
            if isinstance(incoming, dict):
                base.update(incoming)
            merged[section] = base
        return merged

    def is_enabled(self) -> bool:
        return bool(self._cfg().get("enabled"))

    def get_status(self) -> Dict[str, Any]:
        cfg = self._cfg()
        return {
            "enabled": bool(cfg.get("enabled")),
            "mode": cfg.get("mode", "subprocess"),
        }

    def execute(
        self,
        test_case_ids: List[str],
        *,
        suite_name: Optional[str] = None,
        triggered_by: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        ids = [str(i).strip() for i in (test_case_ids or []) if str(i).strip()]
        if not ids:
            raise ValueError("At least one test_case_id is required")

        cfg = self._cfg()
        if not cfg.get("enabled"):
            raise ValueError(
                "Test automation is disabled. Enable test_automation.enabled in config.yaml."
            )

        payload: Dict[str, Any] = {
            "test_case_ids": ids,
            "count": len(ids),
        }
        if suite_name:
            payload["suite_name"] = suite_name
        if triggered_by:
            payload["triggered_by"] = triggered_by
        if extra:
            payload["extra"] = extra

        mode = (cfg.get("mode") or "subprocess").lower()
        if mode == "http":
            result = self._execute_http(cfg.get("http") or {}, payload)
        else:
            result = self._execute_subprocess(cfg.get("subprocess") or {}, payload)

        result["test_case_ids"] = ids
        result["mode"] = mode
        return result

    def _execute_subprocess(self, cfg: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
        command = cfg.get("command") or _DEFAULT_CONFIG["subprocess"]["command"]
        if isinstance(command, str):
            command = command.split()
        if not isinstance(command, list) or not command:
            raise ValueError("test_automation.subprocess.command must be a non-empty list")

        timeout = int(cfg.get("timeout_seconds") or 300)
        input_via = (cfg.get("input_via") or "stdin_json").lower()

        cwd_raw = cfg.get("working_directory")
        cwd: Optional[Path] = None
        if cwd_raw:
            cwd = Path(str(cwd_raw))
            if not cwd.is_absolute():
                backend_root = Path(__file__).resolve().parents[2]
                cwd = (backend_root / cwd).resolve()

        run_cmd = list(command)
        if input_via == "args":
            run_cmd.extend(payload["test_case_ids"])

        logger.info("Executing test automation subprocess: %s", " ".join(run_cmd))
        try:
            completed = subprocess.run(
                run_cmd,
                input=json.dumps(payload).encode("utf-8") if input_via != "args" else None,
                capture_output=True,
                timeout=timeout,
                cwd=str(cwd) if cwd else None,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(
                f"Test automation subprocess timed out after {timeout}s"
            ) from exc
        except OSError as exc:
            raise RuntimeError(f"Failed to start test automation subprocess: {exc}") from exc

        stdout = (completed.stdout or b"").decode("utf-8", errors="replace").strip()
        stderr = (completed.stderr or b"").decode("utf-8", errors="replace").strip()
        success = completed.returncode == 0

        parsed: Any = None
        if stdout:
            try:
                parsed = json.loads(stdout)
            except json.JSONDecodeError:
                parsed = None

        return {
            "success": success,
            "exit_code": completed.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "response": parsed,
            "message": "Test run completed" if success else "Test run failed",
        }

    def _execute_http(self, cfg: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
        url = cfg.get("url") or _DEFAULT_CONFIG["http"]["url"]
        method = (cfg.get("method") or "POST").upper()
        timeout = int(cfg.get("timeout_seconds") or 120)
        headers = dict(cfg.get("headers") or {"Content-Type": "application/json"})
        body = json.dumps(payload).encode("utf-8")

        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        logger.info("Executing test automation HTTP %s %s", method, url)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                status = getattr(resp, "status", 200)
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            raise RuntimeError(f"Automation HTTP {exc.code}: {raw or exc.reason}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Automation HTTP request failed: {exc.reason}") from exc

        parsed: Any = None
        if raw:
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = raw

        success = 200 <= int(status) < 300
        return {
            "success": success,
            "http_status": status,
            "response": parsed,
            "stdout": raw if isinstance(raw, str) else "",
            "message": "Test run accepted" if success else "Test run rejected",
        }
