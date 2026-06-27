"""Unit tests for network egress restrictor (SAK-012/036)."""

import socket

import pytest

from src.infrastructure import network_restrictor as nr


@pytest.fixture(autouse=True)
def reset_hosts(monkeypatch):
    monkeypatch.setenv("SAKURA_RESTRICTOR_MODE", "strict")
    nr.ALLOWED_HOSTS = set(nr.DEFAULT_ALLOWED_HOSTS)


def test_empty_host_not_allowed():
    assert nr.is_host_allowed("") is False


def test_loopback_allowed():
    assert nr.is_host_allowed("127.0.0.1") is True
    assert nr.is_host_allowed("localhost") is True


def test_public_host_blocked_in_strict_mode():
    assert nr.is_host_allowed("8.8.8.8") is False
    assert nr.is_host_allowed("example.com") is False


def test_private_host_blocked_in_strict_mode():
    assert nr.is_host_allowed("10.0.0.5") is False
    assert nr.is_host_allowed("192.168.1.1") is False


def test_private_host_allowed_in_allow_lan_mode(monkeypatch):
    monkeypatch.setenv("SAKURA_RESTRICTOR_MODE", "allow_lan")
    assert nr.is_host_allowed("10.0.0.5") is True


def test_loopback_port_enforcement():
    assert nr.is_port_allowed("127.0.0.1", 11434) is True
    assert nr.is_port_allowed("127.0.0.1", 6379) is True
    assert nr.is_port_allowed("127.0.0.1", 99999) is False


def test_dns_blocked_for_external_host(monkeypatch):
    monkeypatch.setenv("SAKURA_RESTRICTOR_MODE", "strict")
    nr.enable_network_restrictions()
    with pytest.raises(socket.gaierror):
        socket.getaddrinfo("example.com", 80)


def test_dns_allowed_for_loopback(monkeypatch):
    monkeypatch.setenv("SAKURA_RESTRICTOR_MODE", "strict")
    nr.enable_network_restrictions()
    infos = socket.getaddrinfo("127.0.0.1", 5000)
    assert infos
