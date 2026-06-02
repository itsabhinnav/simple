"""Shared helpers for HTTP-based VLM provider adapters."""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from src.infrastructure.configuration_manager import get_config_manager
from src.infrastructure.logging_config import get_logger
from src.interfaces.llm_provider import VLMProvider, VLMProviderError

logger = get_logger(__name__)


def encode_image_b64(image_path: str) -> str:
    path = Path(image_path)
    if not path.exists():
        raise VLMProviderError("vlm", f"Image not found: {image_path}")
    with path.open("rb") as fh:
        return base64.b64encode(fh.read()).decode("ascii")


def resolve_config(provider: str, key: str, env_var: Optional[str] = None, default: Any = None) -> Any:
    """Resolve a provider config value with env override."""
    if env_var:
        env_value = os.environ.get(env_var)
        if env_value:
            return env_value
    cfg = get_config_manager().get_config(f"parsing.vlm.providers.{provider}.{key}", None)
    if cfg is not None:
        return cfg
    return default


def coerce_json(text: str) -> Dict[str, Any]:
    """Best-effort attempt to parse a model's text response as JSON."""
    if not text:
        return {}
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    try:
        value = json.loads(text)
        if isinstance(value, dict):
            return value
        return {"value": value}
    except json.JSONDecodeError:
        return {"raw_text": text}


__all__ = ["VLMProvider", "VLMProviderError", "encode_image_b64", "resolve_config", "coerce_json"]
