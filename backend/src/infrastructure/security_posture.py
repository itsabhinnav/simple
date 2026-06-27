"""Production security posture validation at startup (SAK-041)."""

from __future__ import annotations

import os


def validate_production_security_posture(restrictor_mode: str) -> None:
    """Refuse to boot in production when known exfiltration opt-outs are enabled."""
    if os.environ.get("ENVIRONMENT", "production").lower() != "production":
        return

    violations: list[str] = []

    if restrictor_mode == "off":
        violations.append("ENABLE_NETWORK_RESTRICTIONS=off")
    if restrictor_mode == "allow_lan" and os.environ.get(
        "SAKURA_ALLOW_LAN_EGRESS", "false"
    ).lower() not in ("true", "1", "yes"):
        violations.append(
            "ENABLE_NETWORK_RESTRICTIONS=allow_lan without SAKURA_ALLOW_LAN_EGRESS=true"
        )
    if os.environ.get("SAKURA_LLM_ALLOW_EXTERNAL", "false").lower() in (
        "true",
        "1",
        "yes",
    ):
        violations.append("SAKURA_LLM_ALLOW_EXTERNAL=true")
    if os.environ.get("SAKURA_LLM_ALLOW_REMOTE_OLLAMA", "false").lower() in (
        "true",
        "1",
        "yes",
    ):
        violations.append("SAKURA_LLM_ALLOW_REMOTE_OLLAMA=true")
    if os.environ.get("SAKURA_ALLOW_REMOTE_BROKER", "false").lower() in (
        "true",
        "1",
        "yes",
    ):
        violations.append("SAKURA_ALLOW_REMOTE_BROKER=true")
    if os.environ.get("SAKURA_ALLOW_SPEC_URL_FETCH", "false").lower() in (
        "true",
        "1",
        "yes",
    ):
        violations.append("SAKURA_ALLOW_SPEC_URL_FETCH=true")

    if os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY"):
        violations.append("HTTP_PROXY/HTTPS_PROXY set (egress proxy enabled)")

    if violations:
        raise RuntimeError(
            "Production security posture violation — the following settings enable "
            "outbound data flows and are refused for on-prem LAN deployments: "
            + ", ".join(violations)
        )
