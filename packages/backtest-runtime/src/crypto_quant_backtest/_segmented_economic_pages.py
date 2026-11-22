"""Private CAS pages for opt-in economic evidence; not an economic verifier."""
from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from hashlib import sha256
import re

from crypto_quant_domain import (
    ArtifactEnvelope,
    ArtifactIntegrityError,
    ArtifactReadResult,
    ArtifactRef,
    canonical_bytes,
)

from ._publication import canonical_hash


_PAGE = "backtest_economic_evidence_page"
_VERSION = 1
_MAX_PAGE_ROWS = 64
_MAX_PAGE_BYTES = 8 * 1024 * 1024
_MAX_PAGES = 4096
_PAGE_HASH_SLOT = "sha256:" + "0" * 64
_PAGE_SOURCE_HEAD = canonical_bytes({"artifact_type": _PAGE})[:-1]
_PAGE_CONTENT_FIELD = b',"content_hash":'
_PAGE_SHAPE_PREFIX = _PAGE_SOURCE_HEAD + _PAGE_CONTENT_FIELD + canonical_bytes(_PAGE_HASH_SLOT)
_RUN = re.compile(r"run_[a-f0-9]{64}")
_ROLES = frozenset({"financial_fact", "admission", "journal_entry", "trace_entry", "order_stream",
    "reservation_schedule", "decision_batch", "allocation", "approved_target", "normalized_target",
    "fill", "fee_assessment", "slippage_decision"})


@dataclass(frozen=True, slots=True)
class EconomicPageSeries:
    semantic_run_id: str
    case_hash: str
    role: str

    def __post_init__(self) -> None:
        if type(self.semantic_run_id) is not str or not _RUN.fullmatch(self.semantic_run_id):
            raise ValueError("page series requires a semantic run ID")
        canonical_hash("page series case_hash", self.case_hash)
        if type(self.role) is not str or self.role not in _ROLES:
            raise ValueError("unsupported economic page role")

    def to_canonical_dict(self) -> dict[str, str]:
        return {"semantic_run_id": self.semantic_run_id, "case_hash": self.case_hash, "role": self.role}


@dataclass(frozen=True, slots=True)
class EconomicPageRef:
    artifact_ref: ArtifactRef
    source_hash: str
    byte_count: int
    row_count: int

    def __post_init__(self) -> None:
        if (type(self.artifact_ref) is not ArtifactRef or self.artifact_ref.artifact_type != _PAGE
                or self.artifact_ref.schema_version != _VERSION):
            raise ValueError("economic page requires an exact versioned ref")
        canonical_hash("page source_hash", self.source_hash)
        if type(self.byte_count) is not int or not 1 <= self.byte_count <= _MAX_PAGE_BYTES:
            raise ValueError("economic page byte count outside cap")
        if type(self.row_count) is not int or not 1 <= self.row_count <= _MAX_PAGE_ROWS:
            raise ValueError("economic page row count outside cap")

    def to_canonical_dict(self) -> dict[str, object]:
        return {"artifact_ref": self.artifact_ref, "source_hash": self.source_hash,
                "byte_count": self.byte_count, "row_count": self.row_count}

    @classmethod
    def from_wire(cls, value: object) -> EconomicPageRef:
        if not isinstance(value, Mapping) or set(value) != {"artifact_ref", "source_hash", "byte_count", "row_count"}:
            raise ArtifactIntegrityError("economic page entry fields mismatch")
        ref = value["artifact_ref"]
        if (not isinstance(ref, Mapping) or set(ref) != {"type", "artifact_type", "schema_version", "content_hash"}
                or ref["type"] != "artifact_ref" or type(ref["schema_version"]) is not int):
            raise ArtifactIntegrityError("economic page reference fields mismatch")
        return cls(ArtifactRef(ref["artifact_type"], ref["schema_version"], ref["content_hash"]),
                   value["source_hash"], value["byte_count"], value["row_count"])


def publish_economic_page(publisher, series: EconomicPageSeries, offset: int,
                          rows: tuple[Mapping[str, object], ...]) -> EconomicPageRef:
    if type(series) is not EconomicPageSeries:
        raise TypeError("expected an exact economic page series")
    if type(offset) is not int or not 0 <= offset < _MAX_PAGES * _MAX_PAGE_ROWS:
        raise ValueError("economic page offset outside cap")
    if type(rows) is not tuple or not 1 <= len(rows) <= _MAX_PAGE_ROWS or any(not isinstance(r, Mapping) for r in rows):
        raise ValueError("economic page needs bounded nonempty mapping rows")
    payload = {**series.to_canonical_dict(), "offset": offset, "rows": rows}
    # Check the exact byte budget before CAS normalization/put, using the fixed-length hash slot.
    shape = {"artifact_type": _PAGE, "schema_version": _VERSION, "payload": payload, "content_hash": _PAGE_HASH_SLOT}
    encoded = canonical_bytes(shape)
    size = len(encoded)
    if size > _MAX_PAGE_BYTES:
        raise ValueError("economic page byte count outside cap")
    from ._referenced_evidence import _ReferencedResultObjects

    private_store = type(publisher) is _ReferencedResultObjects
    if private_store:
        # Remove only the reserved hash field to recover the canonical body.
        # ArtifactEnvelope independently validates this body before native writes.
        if not encoded.startswith(_PAGE_SHAPE_PREFIX):
            raise ArtifactIntegrityError("economic page canonical envelope shape mismatch")
        tail = encoded[len(_PAGE_SHAPE_PREFIX):]
        digest = sha256(_PAGE_SOURCE_HEAD)
        digest.update(tail)
        content_hash = "sha256:" + digest.hexdigest()
        envelope = ArtifactEnvelope(_PAGE, _VERSION, payload, content_hash)
        source = _PAGE_SOURCE_HEAD + _PAGE_CONTENT_FIELD + canonical_bytes(content_hash) + tail
    else:
        envelope = ArtifactEnvelope.create(_PAGE, _VERSION, payload)
        source = canonical_bytes(envelope)
    expected = ArtifactRef.from_envelope(envelope)
    if len(source) != size:
        raise ArtifactIntegrityError("economic page size changed during encoding")
    published = (publisher._put_encoded_page(envelope=envelope, encoded=source)
                 if private_store else publisher.put(envelope=envelope))
    if published != expected:
        raise ArtifactIntegrityError("publisher returned unexpected economic page coordinates")
    return EconomicPageRef(expected, "sha256:" + sha256(source).hexdigest(), size, len(rows))


def publish_economic_series(publisher, series: EconomicPageSeries, rows) -> tuple[EconomicPageRef, ...]:
    if type(series) is not EconomicPageSeries:
        raise TypeError("expected an exact economic page series")
    # Budget with the longest allowed offset and the exact versioned envelope shape.
    overhead = len(canonical_bytes({"artifact_type": _PAGE, "schema_version": _VERSION, "content_hash": _PAGE_HASH_SLOT,
        "payload": {**series.to_canonical_dict(), "offset": _MAX_PAGES * _MAX_PAGE_ROWS - 1, "rows": ()}}))
    batch = []
    entries = []
    offset = 0
    size = overhead

    def flush():
        nonlocal size, offset
        if len(entries) == _MAX_PAGES:
            raise ValueError("economic page series outside page cap")
        entries.append(publish_economic_page(publisher, series, offset, tuple(batch)))
        offset += len(batch)
        batch.clear()
        size = overhead

    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("economic page row must be a mapping")
        row_size = len(canonical_bytes(row))
        if overhead + row_size > _MAX_PAGE_BYTES:
            raise ValueError("single economic page row outside cap")
        if len(batch) == _MAX_PAGE_ROWS or size + bool(batch) + row_size > _MAX_PAGE_BYTES:
            flush()
        size += bool(batch) + row_size
        batch.append(row)
    if batch:
        flush()
    return tuple(entries)


def iter_economic_pages(reader, series: EconomicPageSeries, entries: tuple[EconomicPageRef, ...], *,
                        expected_count: int) -> Iterator[tuple[Mapping[str, object], ...]]:
    """Yield one checked page at a time. Consumers must exhaust before accepting the series."""
    if type(series) is not EconomicPageSeries or type(entries) is not tuple or len(entries) > _MAX_PAGES:
        raise ArtifactIntegrityError("economic page series/index mismatch")
    if any(type(entry) is not EconomicPageRef for entry in entries):
        raise ArtifactIntegrityError("economic page entry type mismatch")
    if len({entry.artifact_ref for entry in entries}) != len(entries):
        raise ArtifactIntegrityError("duplicate economic page reference")
    if type(expected_count) is not int or expected_count != sum(entry.row_count for entry in entries):
        raise ArtifactIntegrityError("economic page index does not cover expected rows")
    owner = series.to_canonical_dict()
    offset = 0
    for entry in entries:
        read = reader.read(ref=entry.artifact_ref)
        if (type(read) is not ArtifactReadResult or ArtifactRef.from_envelope(read.envelope) != entry.artifact_ref
                or read.source_hash != entry.source_hash or len(read.source_bytes) != entry.byte_count):
            raise ArtifactIntegrityError("economic page source coordinates mismatch")
        payload = read.envelope.payload
        if not isinstance(payload, Mapping) or payload.keys() != owner.keys() | {"offset", "rows"}:
            raise ArtifactIntegrityError("economic page fields mismatch")
        if any(payload[name] != value for name, value in owner.items()):
            raise ArtifactIntegrityError("economic page owner or role mismatch")
        if type(payload["offset"]) is not int or payload["offset"] != offset:
            raise ArtifactIntegrityError("economic page offset mismatch")
        rows = payload["rows"]
        if type(rows) is not tuple or len(rows) != entry.row_count or any(not isinstance(r, Mapping) for r in rows):
            raise ArtifactIntegrityError("economic page row count or shape mismatch")
        offset += entry.row_count
        del read, payload
        yield rows
        del rows
