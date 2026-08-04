from __future__ import annotations

import asyncio
import http.client
import socket
import urllib.request
from collections.abc import Callable
from typing import Any

import pytest


assert getattr(socket.getaddrinfo, "__network_guard__", False), (
    "Network guard must be installed before test-module collection"
)


def assert_network_guard(call: Callable[..., Any], *args: object) -> None:
    assert getattr(call, "__network_guard__", False), (
        f"Network entry point is not guarded: {call!r}"
    )
    with pytest.raises(RuntimeError, match="Network access is disabled during tests"):
        call(*args)


def test_dns_and_socket_entry_points_are_blocked_before_syscall() -> None:
    assert_network_guard(socket.getaddrinfo, "example.invalid", 443)
    assert_network_guard(socket.gethostbyaddr, "192.0.2.1")
    assert_network_guard(socket.create_connection, ("example.invalid", 443))

    assert getattr(socket.socket.connect, "__network_guard__", False)
    assert getattr(socket.socket.bind, "__network_guard__", False)
    assert getattr(socket.socket.sendto, "__network_guard__", False)
    client = socket.socket()
    try:
        with pytest.raises(RuntimeError, match="Network access is disabled during tests"):
            client.connect(("example.invalid", 443))
    finally:
        client.close()


def test_standard_library_http_entry_points_are_blocked_before_syscall() -> None:
    assert_network_guard(urllib.request.urlopen, "https://example.invalid")

    assert getattr(http.client.HTTPConnection.connect, "__network_guard__", False)
    connection = http.client.HTTPSConnection("example.invalid")
    with pytest.raises(RuntimeError, match="Network access is disabled during tests"):
        connection.connect()

    assert getattr(asyncio.open_connection, "__network_guard__", False)
