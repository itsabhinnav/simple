"""VLM provider implementations — auto-register on import."""

from __future__ import annotations

from src.infrastructure.logging_config import get_logger
from src.interfaces.llm_provider import get_vlm_registry

logger = get_logger(__name__)


def _register_all() -> None:
    """Register the three built-in VLM provider adapters."""
    registry = get_vlm_registry()

    from src.implementations.llm.ollama_provider import OllamaProvider
    from src.implementations.llm.openai_provider import OpenAIProvider
    from src.implementations.llm.anthropic_provider import AnthropicProvider

    if not registry.has("ollama"):
        registry.register("ollama", lambda: OllamaProvider())
    if not registry.has("openai"):
        registry.register("openai", lambda: OpenAIProvider())
    if not registry.has("anthropic"):
        registry.register("anthropic", lambda: AnthropicProvider())

    try:
        from src.infrastructure.configuration_manager import get_config_manager

        registry.configure_from_config(get_config_manager())
    except Exception as exc:  # noqa: BLE001 - configuration is best-effort
        logger.warning(f"Could not configure VLM registry from config: {exc}")


_register_all()
