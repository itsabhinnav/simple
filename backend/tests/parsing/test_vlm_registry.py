"""Tests for the VLM provider registry."""

from __future__ import annotations

import pytest

from src.interfaces.llm_provider import VLMProvider, VLMProviderError, VLMRegistry


class _FakeProvider(VLMProvider):
    def __init__(self, name: str = "fake-a"):
        self._name = name

    def name(self) -> str:
        return self._name

    def caption_image(self, image_path, prompt, context=None):  # noqa: D401, ANN001
        return "caption"

    def describe_layout(self, image_path, prompt):  # noqa: ANN001
        return {"regions": []}

    def extract_structured(self, image_path, prompt, schema_hint):  # noqa: ANN001
        return {"ok": True}


@pytest.fixture()
def fresh_registry():
    reg = VLMRegistry()
    yield reg


def test_default_provider_returned_after_set(fresh_registry):
    fresh_registry.register("fake-a", lambda: _FakeProvider("fake-a"))
    fresh_registry.register("fake-b", lambda: _FakeProvider("fake-b"))
    fresh_registry.set_default("fake-a")
    assert fresh_registry.get_default_name() == "fake-a"
    assert fresh_registry.get().name() == "fake-a"


def test_switch_provider(fresh_registry):
    fresh_registry.register("fake-a", lambda: _FakeProvider("fake-a"))
    fresh_registry.register("fake-b", lambda: _FakeProvider("fake-b"))
    fresh_registry.set_default("fake-a")
    assert fresh_registry.get("fake-b").name() == "fake-b"
    fresh_registry.set_default("fake-b")
    assert fresh_registry.get().name() == "fake-b"


def test_unknown_provider_fails_cleanly(fresh_registry):
    fresh_registry.register("fake-a", lambda: _FakeProvider("fake-a"))
    fresh_registry.set_default("fake-a")
    with pytest.raises(VLMProviderError):
        fresh_registry.get("does-not-exist")


def test_unknown_default_raises(fresh_registry):
    with pytest.raises(VLMProviderError):
        fresh_registry.set_default("nothing-registered")


def test_global_singleton_has_local_builtin_providers():
    from src.interfaces.llm_provider import get_vlm_registry, remote_providers_allowed
    import src.implementations.llm  # noqa: F401 - auto-registers

    reg = get_vlm_registry()
    providers = reg.list_providers()
    assert {"ollama", "ollama-lite"}.issubset(set(providers))
    if remote_providers_allowed():
        assert {"openai", "anthropic"}.issubset(set(providers))
