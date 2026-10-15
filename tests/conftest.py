"""Keep entity tests offline; ECHONET responses use the synthetic wire."""

import socket

import pytest


@pytest.fixture(autouse=True)
def no_live_network(monkeypatch):
    def denied(*args, **kwargs):
        pytest.fail("Live network access is forbidden in this offline suite")

    monkeypatch.setattr(socket, "create_connection", denied)
    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "connect_ex", denied)
    monkeypatch.setattr(socket.socket, "sendto", denied)
