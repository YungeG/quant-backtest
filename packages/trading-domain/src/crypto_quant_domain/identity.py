from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any


IDENTITY_ALGORITHM_V1 = "sha256-length-prefixed-v1"
_MAGIC = b"crypto-quant-domain-id\0"
_MAX_ORDINAL = 2**64 - 1
_HEX_64 = re.compile(r"[0-9a-f]{64}\Z")


def require_canonical_text(name: str, value: str) -> None:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
    ):
        raise ValueError(f"{name} must be canonical non-empty text")


@dataclass(frozen=True, slots=True)
class IdentityNamespace:
    value: str
    version: str
    algorithm: str = IDENTITY_ALGORITHM_V1

    def __post_init__(self) -> None:
        require_canonical_text("namespace", self.value)
        require_canonical_text("namespace version", self.version)
        require_canonical_text("identity algorithm", self.algorithm)


@dataclass(frozen=True, slots=True)
class IdentityManifest:
    namespace: IdentityNamespace

    def __post_init__(self) -> None:
        if not isinstance(self.namespace, IdentityNamespace):
            raise TypeError("namespace must be IdentityNamespace")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "identity_manifest",
            "algorithm": self.namespace.algorithm,
            "namespace": self.namespace.value,
            "namespace_version": self.namespace.version,
        }


class DomainIdKind(str, Enum):
    DECISION = "decision"
    ORDER = "order"
    FILL = "fill"
    FEE = "fee"
    SETTLEMENT = "settlement"
    JOURNAL = "journal"
    RESERVATION = "reservation"

    @property
    def prefix(self) -> str:
        return {
            DomainIdKind.DECISION: "dec",
            DomainIdKind.ORDER: "ord",
            DomainIdKind.FILL: "fil",
            DomainIdKind.FEE: "fee",
            DomainIdKind.SETTLEMENT: "stl",
            DomainIdKind.JOURNAL: "jnl",
            DomainIdKind.RESERVATION: "rsv",
        }[self]


@dataclass(frozen=True, slots=True)
class DomainId:
    kind: DomainIdKind
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.kind, DomainIdKind):
            raise TypeError("kind must be DomainIdKind")
        if not isinstance(self.value, str):
            raise TypeError("DomainId value must be a string")
        prefix = f"{self.kind.prefix}_"
        digest = self.value.removeprefix(prefix)
        if not self.value.startswith(prefix) or _HEX_64.fullmatch(digest) is None:
            raise ValueError("DomainId value does not match kind and digest format")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {"type": "domain_id", "kind": self.kind.value, "value": self.value}

    def __str__(self) -> str:
        return self.value


def frame(value: bytes) -> bytes:
    if len(value) > 2**32 - 1:
        raise ValueError("identity frame exceeds uint32 length")
    return len(value).to_bytes(4, "big") + value


def derive_domain_id(
    *,
    namespace: IdentityNamespace,
    kind: DomainIdKind,
    semantic_run_id: str,
    semantic_key: bytes,
    ordinal: int,
) -> DomainId:
    if not isinstance(namespace, IdentityNamespace):
        raise TypeError("namespace must be IdentityNamespace")
    if namespace.algorithm != IDENTITY_ALGORITHM_V1:
        raise ValueError("unsupported identity algorithm")
    if not isinstance(kind, DomainIdKind):
        raise TypeError("kind must be DomainIdKind")
    require_canonical_text("semantic_run_id", semantic_run_id)
    if type(semantic_key) is not bytes or not semantic_key:
        raise ValueError("semantic_key must be non-empty immutable bytes")
    if isinstance(ordinal, bool) or not isinstance(ordinal, int):
        raise TypeError("ordinal must be an integer")
    if not 0 <= ordinal <= _MAX_ORDINAL:
        raise ValueError("ordinal must fit unsigned 64-bit range")

    payload = _MAGIC + b"".join(
        frame(value)
        for value in (
            namespace.algorithm.encode("utf-8"),
            namespace.value.encode("utf-8"),
            namespace.version.encode("utf-8"),
            kind.value.encode("utf-8"),
            semantic_run_id.encode("utf-8"),
        )
    )
    payload += ordinal.to_bytes(8, "big")
    payload += frame(semantic_key)
    digest = hashlib.sha256(payload).hexdigest()
    return DomainId(kind=kind, value=f"{kind.prefix}_{digest}")
