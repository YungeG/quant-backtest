from __future__ import annotations

import asyncio
import http.client
import socket
import urllib.request
from typing import Any


class NetworkAccessBlocked(RuntimeError):
    """A test attempted to cross the process network boundary."""


def deny_network_access(*args: object, **kwargs: object) -> None:
    del args, kwargs
    raise NetworkAccessBlocked("Network access is disabled during tests")


deny_network_access.__network_guard__ = True  # type: ignore[attr-defined]


_NETWORK_ENTRY_POINTS = (
    (socket, "create_connection"),
    (socket, "create_server"),
    (socket, "getaddrinfo"),
    (socket, "gethostbyaddr"),
    (socket, "gethostbyname"),
    (socket, "gethostbyname_ex"),
    (socket, "getnameinfo"),
    (socket.socket, "accept"),
    (socket.socket, "bind"),
    (socket.socket, "connect"),
    (socket.socket, "connect_ex"),
    (socket.socket, "listen"),
    (socket.socket, "sendto"),
    (http.client.HTTPConnection, "connect"),
    (urllib.request, "urlopen"),
    (asyncio, "open_connection"),
    (asyncio, "start_server"),
)
_ORIGINAL_NETWORK_ENTRY_POINTS: list[tuple[object, str, Any]] = []


def install_network_guard() -> None:
    if _ORIGINAL_NETWORK_ENTRY_POINTS:
        return
    for owner, attribute in _NETWORK_ENTRY_POINTS:
        original = getattr(owner, attribute)
        _ORIGINAL_NETWORK_ENTRY_POINTS.append((owner, attribute, original))
        setattr(owner, attribute, deny_network_access)


def pytest_unconfigure(config: object) -> None:
    del config
    for owner, attribute, original in reversed(_ORIGINAL_NETWORK_ENTRY_POINTS):
        setattr(owner, attribute, original)
    _ORIGINAL_NETWORK_ENTRY_POINTS.clear()


# Conftest is imported before test modules are collected. Install immediately so
# import-time code cannot access DNS, sockets, or standard-library HTTP clients.
install_network_guard()
