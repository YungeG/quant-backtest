"""Encode scoped economic page facts with their existing wire commitments."""
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
import json
import re
from types import MappingProxyType

import crypto_quant_domain as d

from crypto_quant_domain import CanonicalSchema, SimulationInstant, canonical_bytes
from .financial_dispatch import _hash, _text


def _object_with_encoded_member(fields: Mapping[str, object], member: str, encoded: bytes) -> bytes:
    parts = tuple(canonical_bytes(key) + b":" +
        (encoded if key == member else canonical_bytes(value))
        for key, value in sorted(fields.items()))
    return b"{" + b",".join(parts) + b"}"


def _digest(source: bytes) -> str:
    return "sha256:" + sha256(source).hexdigest()


def encode_economic_paged_fact(
    *, role: str, source_event_id: str, occurred_at: SimulationInstant, component_key: str,
    component_digest: str, input_hash: str, schema_version: int, payload: Mapping[str, object],
) -> tuple[dict[str, object], str]:
    payload_bytes = canonical_bytes(payload)
    # The original Envelope constructor round-trips through JSON before hashing
    # the payload. Preserve that number-decoder boundary and the normalized values.
    normalized = json.loads(payload_bytes)
    kind = "cn_a_share_portfolio_" + role
    CanonicalSchema(kind, schema_version)
    envelope: dict[str, object] = {"artifact_type": kind, "schema_version": schema_version, "payload": normalized}
    envelope["content_hash"] = _digest(_object_with_encoded_member(envelope, "payload", payload_bytes))
    envelope_bytes = _object_with_encoded_member(envelope, "payload", payload_bytes)
    _text("role", role)
    _text("source_event_id", source_event_id)
    if not isinstance(occurred_at, SimulationInstant):
        raise TypeError("occurred_at must be SimulationInstant")
    _text("component_key", component_key)
    _hash("component_digest", component_digest)
    _hash("input_hash", input_hash)
    row: dict[str, object] = {"type": "financial_dispatch_artifact", "schema_version": 1, "role": role,
        "source_event_id": source_event_id, "occurred_at": occurred_at, "component_key": component_key,
        "component_version": 1, "component_digest": component_digest, "input_hash": input_hash,
        "result_hash": _digest(envelope_bytes), "payload": envelope}
    return row, _digest(_object_with_encoded_member(row, "payload", envelope_bytes))


_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_ROW_FIELDS = {
    "type", "schema_version", "role", "source_event_id", "occurred_at", "component_key",
    "component_version", "component_digest", "input_hash", "result_hash", "payload",
}
_ENVELOPE_FIELDS = {"artifact_type", "schema_version", "payload", "content_hash"}


@dataclass(frozen=True, slots=True)
class _VerifiedEconomicFactEnvelopeV1:
    artifact_type: str
    schema_version: int
    payload: object
    content_hash: str

    def to_canonical_dict(self):
        return {"artifact_type": self.artifact_type, "schema_version": self.schema_version,
                "payload": self.payload, "content_hash": self.content_hash}


@dataclass(frozen=True, slots=True)
class _VerifiedEconomicPagedFactV1:
    role: str
    source_event_id: str
    occurred_at: d.SimulationInstant
    component_key: str
    component_version: int
    component_digest: str
    input_hash: str
    result_hash: str
    payload: _VerifiedEconomicFactEnvelopeV1


def decode_frozen_economic_paged_fact(
    row: MappingProxyType,
) -> tuple[_VerifiedEconomicPagedFactV1, bytes]:
    """Reprove a frozen page row's envelope, wrapper and canonical bytes."""
    from .execution_inputs import _read_simulation_instant

    if type(row) is not MappingProxyType or set(row) != _ROW_FIELDS:
        raise d.ArtifactIntegrityError("economic evidence exact mapping fields mismatch")
    if row["type"] != "financial_dispatch_artifact" or type(row["schema_version"]) is not int or row["schema_version"] != 1:
        raise d.ArtifactIntegrityError("economic financial artifact version mismatch")
    occurred = _read_simulation_instant(row["occurred_at"])
    raw = row["payload"]
    if not isinstance(raw, Mapping) or set(raw) != _ENVELOPE_FIELDS:
        raise d.ArtifactIntegrityError("economic evidence exact mapping fields mismatch")
    kind, version, payload, content_hash = raw["artifact_type"], raw["schema_version"], raw["payload"], raw["content_hash"]
    d.CanonicalSchema(kind, version)
    if not isinstance(content_hash, str) or _HASH.fullmatch(content_hash) is None:
        raise ValueError("content hash must be sha256:<64 lowercase hex>")
    payload_bytes = d.canonical_bytes(payload)
    # Apply the same bounded JSON integer decoding as ArtifactEnvelope.
    json.loads(payload_bytes)
    body = {"artifact_type": kind, "schema_version": version, "payload": payload}
    if _digest(_object_with_encoded_member(body, "payload", payload_bytes)) != content_hash:
        raise ValueError("content hash does not match artifact body")
    role = _text("role", row["role"])
    event_id = _text("source_event_id", row["source_event_id"])
    component_key = _text("component_key", row["component_key"])
    version_num = row["component_version"]
    if type(version_num) is not int or version_num <= 0:
        raise ValueError("component_version must be positive integer")
    component_hash = _hash("component_digest", row["component_digest"])
    input_hash = _hash("input_hash", row["input_hash"])
    result_hash = _hash("result_hash", row["result_hash"])
    source = _object_with_encoded_member(raw, "payload", payload_bytes)
    if _digest(source) != result_hash:
        raise ValueError("result_hash must match payload")
    if d.canonical_bytes(occurred) != d.canonical_bytes(row["occurred_at"]):
        raise d.ArtifactIntegrityError("economic evidence mismatch: financial artifact canonical reconstruction")
    envelope = _VerifiedEconomicFactEnvelopeV1(kind, version, payload, content_hash)
    fact = _VerifiedEconomicPagedFactV1(role, event_id, occurred, component_key, version_num,
                                       component_hash, input_hash, result_hash, envelope)
    return fact, _object_with_encoded_member(row, "payload", source)
