"""Bounded, source-only transport for one immutable economic definition."""
from collections.abc import Mapping
from itertools import islice

import crypto_quant_domain as d

from .cash_development_provider import _publish, _verify_published
from .target_repository import _artifact_ref

_ROLES = ("opening_terms", "signal_marks", "daily_marks", "checkpoint_marks")
_TYPE = "backtest_economic_definition_source_chunk"
_MAX_CHUNK_ROWS = 64
_MAX_SECTION_ROWS = 65536


def _fields(value, expected):
    if not isinstance(value, Mapping) or set(value) != expected:
        raise d.ArtifactIntegrityError("economic source chunk fields mismatch")
    return value


def _bounded_section_size(value):
    if type(value) is not int or not 0 < value <= _MAX_SECTION_ROWS:
        raise d.ArtifactIntegrityError("economic source section row count outside bounds")
    return value


def _publish_economic_source_chunks(*, publisher, reader, scope, sections):
    _fields(sections, set(_ROLES))
    scope_hash = d.canonical_sha256(scope)
    index = {}
    for role in _ROLES:
        values = sections[role]
        count = _bounded_section_size(len(values))
        chunks, cursor = [], iter(values)
        for offset in range(0, count, _MAX_CHUNK_ROWS):
            rows = tuple(islice(cursor, _MAX_CHUNK_ROWS))
            if len(rows) != min(_MAX_CHUNK_ROWS, count - offset):
                raise d.ArtifactIntegrityError("economic source section row count mismatch")
            envelope = d.ArtifactEnvelope.create(_TYPE, 1,
                {"scope_hash": scope_hash, "role": role, "offset": offset, "rows": rows})
            ref = _publish(publisher, envelope)
            _verify_published(reader, ref, envelope)
            chunks.append(ref)
        index[role] = {"count": count, "chunks": tuple(chunks)}
    return index


def _open_economic_source_chunks(*, reader, scope, index):
    """Validate the index before opening chunks. Row decoding stays with Backtest."""
    _fields(index, set(_ROLES))
    scope_hash = d.canonical_sha256(scope)
    plans = {}
    seen = set()
    for role in _ROLES:
        entry = _fields(index[role], {"count", "chunks"})
        count = _bounded_section_size(entry["count"])
        raw = entry["chunks"]
        if type(raw) is not tuple or len(raw) != (count + _MAX_CHUNK_ROWS - 1) // _MAX_CHUNK_ROWS:
            raise d.ArtifactIntegrityError("economic source chunk count mismatch")
        refs = []
        for item in raw:
            ref = _artifact_ref(item)
            if ref.artifact_type != _TYPE or ref.schema_version != 1 or ref in seen:
                raise d.ArtifactIntegrityError("economic source chunk type/version or duplicate reference")
            refs.append(ref)
            seen.add(ref)
        plans[role] = (count, tuple(refs))

    def read_rows(role):
        from .cn_a_share_portfolio_economic_case_v1 import _read_exact_economic_source_v1
        count, refs = plans[role]
        for i, ref in enumerate(refs):
            envelope = _read_exact_economic_source_v1(reader, ref)
            data = _fields(envelope.payload, {"scope_hash", "role", "offset", "rows"})
            offset = i * _MAX_CHUNK_ROWS
            if (data["scope_hash"] != scope_hash or data["role"] != role
                    or type(data["offset"]) is not int or data["offset"] != offset
                    or type(data["rows"]) is not tuple or len(data["rows"]) != min(_MAX_CHUNK_ROWS, count - offset)):
                raise d.ArtifactIntegrityError("economic source chunk coordinate or row count mismatch")
            yield from data["rows"]

    return {role: read_rows(role) for role in _ROLES}
