"""A staging root for directly verified economic pages (not a canonical publication)."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from itertools import chain

from crypto_quant_domain import (
    ArtifactEnvelope, ArtifactIntegrityError, ArtifactReadResult, ArtifactRef, canonical_bytes, canonical_sha256,
)

from ._segmented_economic_pages import (
    _MAX_PAGES, EconomicPageRef, EconomicPageSeries, iter_economic_pages, publish_economic_series,
)


_KIND = "backtest_economic_paged_result"
_VERSION = 1
_MAX_INDEX_BYTES = 16 * 1024 * 1024
_HEADER_COLLECTIONS = {"decision_batches": "decision_batch", "allocations": "allocation",
    "approved_targets": "approved_target", "normalized_targets": "normalized_target",
    "order_streams": "order_stream", "fills": "fill", "fee_assessments": "fee_assessment",
    "slippage_decisions": "slippage_decision"}
_FINAL_ROLES = frozenset((*_HEADER_COLLECTIONS.values(), "journal_entry", "trace_entry", "reservation_schedule"))


@dataclass(frozen=True, slots=True)
class _VerifiedPagedResult:
    ref: ArtifactRef
    source_hash: str
    byte_count: int
    case_hash: str
    target_stream_digest: str
    trace_hash: str

    @property
    def execution_result_hash(self) -> str:
        return canonical_sha256({"type": "backtest_paged_execution_identity", "schema_version": 1,
            "result_ref": self.ref, "case_hash": self.case_hash,
            "target_stream_digest": self.target_stream_digest, "trace_hash": self.trace_hash})


def _series(case_hash, semantic_run_id):
    return (EconomicPageSeries(semantic_run_id, case_hash, "financial_fact"),
            EconomicPageSeries(semantic_run_id, case_hash, "admission"))


def stage_economic_paged_result(*, publisher, semantic_run_id, case_hash, header, witness, facts, admissions) -> ArtifactRef:
    """Store children and then their index. Success here never implies strict verification."""
    fseries, aseries = _series(case_hash, semantic_run_id)
    fp = publish_economic_series(publisher, fseries, facts)
    ap = publish_economic_series(publisher, aseries, admissions)
    return _stage_index(publisher, fseries, header, witness, fp, ap)


def _source_mapping(value):
    return value if isinstance(value, Mapping) else value.to_canonical_dict()


def _stage_index(publisher, series, header, witness, facts, admissions) -> ArtifactRef:
    def pages(role, rows):
        selected = EconomicPageSeries(series.semantic_run_id, series.case_hash, role)
        return publish_economic_series(publisher, selected, (_source_mapping(row) for row in rows))

    header = dict(header)
    refs = {role: pages(role, header.pop(name)) for name, role in _HEADER_COLLECTIONS.items()}
    for name, member, role in (("trace", "entries", "trace_entry"), ("final_journal", "entries", "journal_entry")):
        raw = header[name] = dict(_source_mapping(header[name]))
        refs[role] = pages(role, raw.pop(member))
    # Keep the complete witness hash and trace commitment. Only its schedules move to pages.
    witness = dict(witness)
    env = witness["payload"] = dict(_source_mapping(witness["payload"]))
    outer = env["payload"] = dict(env["payload"])
    body = outer["economic_witness"] = dict(outer["economic_witness"])
    refs["reservation_schedule"] = pages("reservation_schedule", body.pop("schedules"))
    payload = {"semantic_run_id": series.semantic_run_id, "case_hash": series.case_hash, "header": header,
               "witness": witness, "financial_pages": facts, "admission_pages": admissions, "final_pages": refs}
    if len(canonical_bytes({"artifact_type": _KIND, "schema_version": _VERSION, "payload": payload,
                            "content_hash": "sha256:" + "0" * 64})) > _MAX_INDEX_BYTES:
        raise ValueError("economic paged staging index outside byte cap")
    env = ArtifactEnvelope.create(_KIND, _VERSION, payload)
    expected = ArtifactRef.from_envelope(env)
    if publisher.put(envelope=env) != expected:
        raise ArtifactIntegrityError("publisher returned unexpected economic paged result coordinates")
    return expected


def verify_economic_paged_result(*, reader, source_reader, result_ref, case,
                                 observe_fact=None, observe_header=None, bound_sources=None) -> _VerifiedPagedResult:
    """Verify a trusted result coordinate independently from the retained economic sources."""
    from .cn_a_share_portfolio_economic_result_v1 import _verify_economic_paged_result_v1

    if (type(result_ref) is not ArtifactRef or result_ref.artifact_type != _KIND
            or result_ref.schema_version != _VERSION):
        raise ArtifactIntegrityError("economic paged result version mismatch")
    read = reader.read(ref=result_ref)
    if (type(read) is not ArtifactReadResult or ArtifactRef.from_envelope(read.envelope) != result_ref
            or len(read.source_bytes) > _MAX_INDEX_BYTES):
        raise ArtifactIntegrityError("economic paged result source coordinates mismatch")
    raw = read.envelope.payload
    if not isinstance(raw, Mapping) or set(raw) != {"semantic_run_id", "case_hash", "header", "witness",
                                                    "financial_pages", "admission_pages", "final_pages"}:
        raise ArtifactIntegrityError("economic paged result index fields mismatch")
    run = case.identity_manifest.semantic_run_id
    if raw["semantic_run_id"] != run or raw["case_hash"] != case.case_hash:
        raise ArtifactIntegrityError("economic paged result case owner mismatch")
    fseries, aseries = _series(case.case_hash, run)
    def rows(series, refs):
        if type(refs) is not tuple or len(refs) > _MAX_PAGES:
            raise ArtifactIntegrityError("economic paged index needs bounded page sequences")
        values = tuple(EconomicPageRef.from_wire(ref) for ref in refs)
        return iter_economic_pages(reader, series, values, expected_count=sum(v.row_count for v in values))

    fs = rows(fseries, raw["financial_pages"])
    ads = rows(aseries, raw["admission_pages"])
    final = raw["final_pages"]
    if not isinstance(final, Mapping) or set(final) != _FINAL_ROLES:
        raise ArtifactIntegrityError("economic paged final collection roles mismatch")
    def collection(role):
        series = EconomicPageSeries(run, case.case_hash, role)
        return tuple(chain.from_iterable(rows(series, final[role])))

    def install(parent, name, role):
        if name in parent:
            raise ArtifactIntegrityError("economic paged index embeds a duplicate collection")
        parent[name] = collection(role)

    header, witness = dict(raw["header"]), dict(raw["witness"])
    source_hash, byte_count = read.source_hash, len(read.source_bytes)
    del raw, read
    for name, role in _HEADER_COLLECTIONS.items():
        install(header, name, role)
    for name, role in (("trace", "trace_entry"), ("final_journal", "journal_entry")):
        header[name] = dict(header[name])
        install(header[name], "entries", role)
    env = witness["payload"] = dict(witness["payload"])
    outer = env["payload"] = dict(env["payload"])
    body = outer["economic_witness"] = dict(outer["economic_witness"])
    install(body, "schedules", "reservation_schedule")
    # The strict verifier independently proves trace and witness exact coverage, including
    # the reattached schedules; no encoded legacy result or old financial artifacts are made.
    if observe_fact is not None:
        def observed(pages):
            for page in pages:
                for row in page:
                    observe_fact(row)
                yield page
        fs = observed(fs)
    _verify_economic_paged_result_v1(case=case, reader=source_reader, header=header, witness=witness,
                                    pages=fs, admission_pages=ads, bound_sources=bound_sources)
    if observe_header is not None:
        observe_header(header)
    return _VerifiedPagedResult(result_ref, source_hash, byte_count, case.case_hash,
                                case.target_stream.target_stream_digest, canonical_sha256(header["trace"]))
