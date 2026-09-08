from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any


_SCHEMA_NAME = re.compile(r"[a-z][a-z0-9_.-]*\Z")


class CanonicalizationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class CanonicalSchema:
    name: str
    version: int

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or _SCHEMA_NAME.fullmatch(self.name) is None:
            raise ValueError("schema name must be canonical lowercase text")
        if isinstance(self.version, bool) or not isinstance(self.version, int):
            raise TypeError("schema version must be an integer")
        if self.version < 1:
            raise ValueError("schema version must be at least 1")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {"name": self.name, "version": self.version}


@dataclass(frozen=True, slots=True)
class CanonicalEnvelope:
    schema: CanonicalSchema
    payload: Any

    def __post_init__(self) -> None:
        if not isinstance(self.schema, CanonicalSchema):
            raise TypeError("schema must be CanonicalSchema")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema.to_canonical_dict(),
            "payload": self.payload,
        }


def canonical_string(value: str, path: str) -> str:
    if unicodedata.normalize("NFC", value) != value:
        raise CanonicalizationError(f"NFC string required at {path}")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise CanonicalizationError(f"invalid Unicode string at {path}") from error
    return value


def normalize(value: Any, path: str, active: set[int]) -> Any:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return canonical_string(value, path)
    if isinstance(value, float):
        raise CanonicalizationError(f"float is forbidden at {path}")
    if isinstance(value, Decimal):
        raise CanonicalizationError(f"Decimal is forbidden at {path}")
    if isinstance(value, datetime):
        raise CanonicalizationError(f"datetime is forbidden at {path}")
    if isinstance(value, date):
        raise CanonicalizationError(f"date is forbidden at {path}")
    if isinstance(value, bytes):
        raise CanonicalizationError(f"bytes are forbidden at {path}")
    if isinstance(value, (set, frozenset)):
        raise CanonicalizationError(f"set is forbidden at {path}")

    identity = id(value)
    if identity in active:
        raise CanonicalizationError(f"cyclic canonical value at {path}")

    if isinstance(value, Mapping):
        active.add(identity)
        try:
            result: dict[str, Any] = {}
            for key, child in value.items():
                if not isinstance(key, str):
                    raise CanonicalizationError(f"mapping key must be string at {path}")
                canonical_key = canonical_string(key, f"{path}/<key>")
                result[canonical_key] = normalize(
                    child, f"{path}/{canonical_key}", active
                )
            return result
        finally:
            active.remove(identity)

    if isinstance(value, (list, tuple)):
        active.add(identity)
        try:
            return [
                normalize(child, f"{path}/{index}", active)
                for index, child in enumerate(value)
            ]
        finally:
            active.remove(identity)

    to_canonical = getattr(value, "to_canonical_dict", None)
    if callable(to_canonical):
        active.add(identity)
        try:
            canonical_value = to_canonical()
            if not isinstance(canonical_value, Mapping):
                raise CanonicalizationError(
                    f"to_canonical_dict must return mapping at {path}"
                )
            return normalize(canonical_value, path, active)
        finally:
            active.remove(identity)

    raise CanonicalizationError(
        f"unsupported canonical type {type(value).__name__} at {path}"
    )


def _integer_text(value: int) -> str:
    if value == 0:
        return "0"
    sign = "-" if value < 0 else ""
    remaining = abs(value)
    chunks: list[int] = []
    while remaining:
        remaining, chunk = divmod(remaining, 1_000_000_000)
        chunks.append(chunk)
    head = str(chunks.pop())
    tail = "".join(f"{chunk:09d}" for chunk in reversed(chunks))
    return sign + head + tail


def _encode_normalized(value: Any) -> str:
    if value is None:
        return "null"
    if type(value) is bool:
        return "true" if value else "false"
    if isinstance(value, int):
        return _integer_text(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return "[" + ",".join(_encode_normalized(child) for child in value) + "]"
    if isinstance(value, dict):
        return "{" + ",".join(
            json.dumps(key, ensure_ascii=False) + ":" + _encode_normalized(value[key])
            for key in sorted(value)
        ) + "}"
    raise CanonicalizationError(
        f"unsupported normalized canonical type {type(value).__name__}"
    )


def canonical_bytes(value: Any) -> bytes:
    normalized = normalize(value, "$", set())
    try:
        encoded = json.dumps(
            normalized,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except ValueError:
        encoded = _encode_normalized(normalized)
    try:
        return encoded.encode("utf-8")
    except (TypeError, UnicodeEncodeError) as error:
        raise CanonicalizationError(f"canonical JSON encoding failed: {error}") from error


def canonical_sha256(value: Any) -> str:
    return f"sha256:{hashlib.sha256(canonical_bytes(value)).hexdigest()}"
