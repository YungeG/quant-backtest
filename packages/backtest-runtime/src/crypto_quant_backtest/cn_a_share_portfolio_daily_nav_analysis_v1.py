"""Versioned CN portfolio close NAV analysis; old analysis schemas stay frozen.

Values are declarations, not evidence. Only the source-bound Runtime and the
Repository's cold verification can admit a stored analysis. No OOS authority.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, time
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
import json
import re
from typing import Any
from zoneinfo import ZoneInfo

import crypto_quant_domain as d
import crypto_quant_trading as t
from crypto_quant_trading.profiles.cn_a_share import CnAShareCalendarDayKind

from .analysis_derivation import _calculate_simple_period_return
from .artifact_envelope_reader import ArtifactEnvelopeReader
from .artifact_envelope_publisher import ArtifactEnvelopePublisher
from .integrity import ResultGrade
from .publication_refs import BacktestCanonicalPublicationRef

_PROFILE_TYPE = "cn_a_share_portfolio_daily_nav_metric_profile"
_ANALYSIS_TYPE = "cn_a_share_portfolio_daily_nav_analysis"
_ZONE = ZoneInfo("Asia/Shanghai")
_CENT = d.Scale(2)
_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_QUANTUM = Decimal("0.000000000000000001")


def _hash(value: object) -> None:
    if type(value) is not str or _HASH.fullmatch(value) is None:
        raise ValueError("NAV source hash must be canonical sha256")


def _money(value: object) -> None:
    if type(value) is not d.Money or value.currency != "CNY" or value.scale != _CENT or value.units <= 0:
        raise ValueError("NAV requires positive CNY-cent equity")


def _ref(value: object, artifact_type: str, version: int) -> None:
    if type(value) is not d.ArtifactRef or (value.artifact_type, value.schema_version) != (artifact_type, version):
        raise TypeError("NAV source requires exact " + artifact_type + "@" + str(version))


@dataclass(frozen=True, slots=True)
class CnASharePortfolioDailyNavMetricProfileV1:
    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": _PROFILE_TYPE, "schema_version": 1,
                "profile_key": "cn.shared-cny.native-close.return-maxdd.fill-count.v1",
                "reporting_currency": "CNY", "equity_scale": 2,
                "drawdown_sampling": "initial_peak_and_every_frozen_trading_close",
                "close_time": "15:00:00 Asia/Shanghai",
                "external_cash_flows": "reject_except_net_zero_modeled_venue_transfers",
                "rounding": "half_even_18_decimal_places", "accepted_grade": "development",
                "validation_eligible": False, "deployment_authorized": False}


_PROFILE = CnASharePortfolioDailyNavMetricProfileV1()
_PROFILE_ENVELOPE = d.ArtifactEnvelope.create(_PROFILE_TYPE, 1, _PROFILE)
_PROFILE_REF = d.ArtifactRef.from_envelope(_PROFILE_ENVELOPE)


@dataclass(frozen=True, slots=True)
class CnASharePortfolioDailyNavPointV1:
    trade_date: str
    occurred_at: d.SimulationInstant
    equity: d.Money
    snapshot_hash: str
    journal_prefix_hash: str
    mark_batch_hash: str
    native_fact_hash: str

    def __post_init__(self) -> None:
        if type(self.trade_date) is not str or date.fromisoformat(self.trade_date).isoformat() != self.trade_date:
            raise ValueError("NAV date must be canonical ISO date")
        if type(self.occurred_at) is not d.SimulationInstant:
            raise TypeError("NAV observation requires the full SimulationInstant")
        local = self.occurred_at.instant.to_datetime().astimezone(_ZONE)
        if (local.date().isoformat() != self.trade_date or local.time() != time(15)
                or self.occurred_at.instant.epoch_nanoseconds % 1_000_000_000):
            raise ValueError("NAV observation must be at the exact declared trading close")
        _money(self.equity)
        for value in (self.snapshot_hash, self.journal_prefix_hash, self.mark_batch_hash, self.native_fact_hash):
            _hash(value)

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "cn_a_share_portfolio_daily_nav_point", "schema_version": 1,
                "trade_date": self.trade_date, "occurred_at": self.occurred_at, "equity": self.equity,
                "snapshot_hash": self.snapshot_hash, "journal_prefix_hash": self.journal_prefix_hash,
                "mark_batch_hash": self.mark_batch_hash, "native_fact_hash": self.native_fact_hash}


def _metrics(initial: d.Money, points: tuple[CnASharePortfolioDailyNavPointV1, ...]) -> tuple[str, str]:
    returned = _calculate_simple_period_return(initial, points[-1].equity, ())
    if returned is None:
        raise ValueError("NAV source is incompatible with the accepted return policy")
    with localcontext() as context:
        context.prec = max(len(str(initial.units)), *(len(str(p.equity.units)) for p in points)) + 50
        context.rounding = ROUND_HALF_EVEN
        peak, maximum = Decimal(initial.units), Decimal(0)
        for point in points:
            value = Decimal(point.equity.units)
            peak = max(peak, value)
            maximum = max(maximum, (peak - value) / peak)
        maximum = maximum.quantize(_QUANTUM, rounding=ROUND_HALF_EVEN)
    text = format(maximum, "f").rstrip("0").rstrip(".") if maximum else "0"
    return returned, text


@dataclass(frozen=True, slots=True)
class CnASharePortfolioDailyNavAnalysisV1:
    metric_profile_ref: d.ArtifactRef
    source_publication_ref: BacktestCanonicalPublicationRef
    execution_input_ref: d.ArtifactRef
    definition_ref: d.ArtifactRef
    engine_result_ref: d.ArtifactRef
    source_execution_result_hash: str
    starting_snapshot_hash: str
    initial_equity: d.Money
    points: tuple[CnASharePortfolioDailyNavPointV1, ...]
    trade_count: int
    result_grade: ResultGrade = ResultGrade.DEVELOPMENT
    simple_period_return: str = field(init=False)
    maximum_drawdown: str = field(init=False)

    def __post_init__(self) -> None:
        _ref(self.metric_profile_ref, _PROFILE_TYPE, 1)
        if self.metric_profile_ref != _PROFILE_REF:
            raise ValueError("NAV metric profile is not the accepted exact version")
        if type(self.source_publication_ref) is not BacktestCanonicalPublicationRef:
            raise TypeError("NAV requires exact standard canonical publication ref")
        for value, name, version in ((self.execution_input_ref, "backtest_execution_input_bundle", 8),
                (self.definition_ref, "backtest_profile_portfolio_definition", 1),
                (self.engine_result_ref, "engine_execution_result", 1)):
            _ref(value, name, version)
        _hash(self.source_execution_result_hash)
        _hash(self.starting_snapshot_hash)
        _money(self.initial_equity)
        if (type(self.points) is not tuple or not 0 < len(self.points) <= 4096
                or any(type(p) is not CnASharePortfolioDailyNavPointV1 for p in self.points)):
            raise ValueError("NAV needs a bounded exact close series")
        days = tuple(p.trade_date for p in self.points)
        if days != tuple(sorted(set(days))):
            raise ValueError("NAV dates must be strictly increasing and unique")
        if type(self.trade_count) is not int or self.trade_count < 0:
            raise ValueError("NAV fill count must be a nonnegative integer")
        if type(self.result_grade) is not ResultGrade or self.result_grade is not ResultGrade.DEVELOPMENT:
            raise ValueError("NAV v1 accepts development only, never upgrades a grade")
        returned, maximum = _metrics(self.initial_equity, self.points)
        object.__setattr__(self, "simple_period_return", returned)
        object.__setattr__(self, "maximum_drawdown", maximum)

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": _ANALYSIS_TYPE, "schema_version": 1,
                "metric_profile_ref": self.metric_profile_ref, "source_publication_ref": self.source_publication_ref,
                "execution_input_ref": self.execution_input_ref, "definition_ref": self.definition_ref,
                "engine_result_ref": self.engine_result_ref, "source_execution_result_hash": self.source_execution_result_hash,
                "starting_snapshot_hash": self.starting_snapshot_hash, "initial_equity": self.initial_equity,
                "points": self.points, "trade_count": self.trade_count, "result_grade": self.result_grade.value,
                "simple_period_return": self.simple_period_return, "maximum_drawdown": self.maximum_drawdown,
                "source_qualification_verified": False, "formal_publication_eligible": False,
                "validation_eligible": False, "deployment_authorized": False,
                "provider_availability_verified": False, "account_fees_verified": False, "trade_authorized": False}


@dataclass(frozen=True, slots=True)
class CnASharePortfolioDailyNavAnalysisRefV1:
    artifact_ref: d.ArtifactRef

    def __post_init__(self) -> None:
        _ref(self.artifact_ref, _ANALYSIS_TYPE, 1)

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "cn_a_share_portfolio_daily_nav_analysis_ref", "schema_version": 1,
                "artifact_ref": self.artifact_ref}


def _map(value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or any(type(k) is not str for k in value):
        raise TypeError("NAV source requires a canonical mapping")
    return value


def _seq(value: object) -> tuple[Any, ...]:
    if not isinstance(value, (list, tuple)):
        raise TypeError("NAV source requires a canonical sequence")
    return tuple(value)


def _wire_ref(value: object) -> d.ArtifactRef:
    from .target_repository import _artifact_ref
    return _artifact_ref(value)


def _read_envelope(reader: ArtifactEnvelopeReader, ref: d.ArtifactRef) -> d.ArtifactEnvelope:
    read = reader.read(ref=ref)
    if (type(read) is not d.ArtifactReadResult or type(read.envelope) is not d.ArtifactEnvelope
            or d.ArtifactRef.from_envelope(read.envelope) != ref
            or read.source_bytes != d.canonical_bytes(read.envelope)
            or read.source_hash != d.canonical_sha256(read.envelope)):
        raise ValueError("NAV retained source byte/ref binding mismatch")
    return read.envelope


def _raw(envelope: d.ArtifactEnvelope) -> Mapping[str, Any]:
    return _map(json.loads(d.canonical_bytes(envelope.payload)))


def _read_nav_profile(value: object) -> CnASharePortfolioDailyNavMetricProfileV1:
    if d.canonical_bytes(value) != d.canonical_bytes(_PROFILE):
        raise ValueError("NAV profile payload is not the accepted exact version")
    return _PROFILE


def _read_nav_analysis(value: object) -> CnASharePortfolioDailyNavAnalysisV1:
    from .execution_inputs import _read_money, _read_simulation_instant
    raw = _map(value)
    publication = _map(raw["source_publication_ref"])
    if set(publication) != {"type", "artifact_ref"} or publication["type"] != "backtest_canonical_publication_ref":
        raise ValueError("NAV publication must be the exact nominal canonical ref")
    points = []
    for item in _seq(raw["points"]):
        row = _map(item)
        point = CnASharePortfolioDailyNavPointV1(row["trade_date"], _read_simulation_instant(row["occurred_at"]),
            _read_money(row["equity"]), row["snapshot_hash"], row["journal_prefix_hash"],
            row["mark_batch_hash"], row["native_fact_hash"])
        if d.canonical_bytes(point) != d.canonical_bytes(row):
            raise ValueError("NAV point must reconstruct exact canonical fields")
        points.append(point)
    result = CnASharePortfolioDailyNavAnalysisV1(_wire_ref(raw["metric_profile_ref"]),
        BacktestCanonicalPublicationRef(_wire_ref(publication["artifact_ref"])),
        _wire_ref(raw["execution_input_ref"]), _wire_ref(raw["definition_ref"]), _wire_ref(raw["engine_result_ref"]),
        raw["source_execution_result_hash"], raw["starting_snapshot_hash"], _read_money(raw["initial_equity"]),
        tuple(points), raw["trade_count"], ResultGrade(raw["result_grade"]))
    if d.canonical_bytes(result) != d.canonical_bytes(raw):
        raise ValueError("NAV analysis fields, metrics or qualification claims do not reconstruct")
    return result


def _build_nav_analysis(reader: ArtifactEnvelopeReader, publication_ref: BacktestCanonicalPublicationRef,
                        input_ref: d.ArtifactRef) -> CnASharePortfolioDailyNavAnalysisV1:
    # Import the repository locally: its new schema decoder delegates to this
    # module, but source loading must remain with the one existing repository.
    from .evidence_repository import BacktestEvidenceRepository
    from .execution_inputs import (_EXECUTION_INPUT_CATALOG, _DecodedExecutionInputBundleV8,
                                   _read_portfolio_snapshot, _read_simulation_instant, _read_timeline_window)
    from .cn_a_share_portfolio_standard_definition_v1 import _read_standard_definition_v1
    from .cn_a_share_portfolio_standard_case_v1 import _native_initial_financial_state_v1
    from .cn_a_share_portfolio_standard_native_state_v1 import _native_snapshot_at_v1
    from .cn_a_share_portfolio_standard_engine_v1 import _COMPONENT, _COMPONENT_HASH, _RUN_END_MARK_POLICY
    from .cn_a_share_portfolio_daily_nav_diagnostic_v1 import _reject_unmodeled_dividends_v1
    from .target_repository import BacktestTargetStreamRef, BacktestTargetStreamRepository

    _ref(input_ref, "backtest_execution_input_bundle", 8)
    completed = BacktestEvidenceRepository(reader).load_completed(publication_ref)
    if completed.result_grade is not ResultGrade.DEVELOPMENT:
        raise ValueError("NAV v1 only supports the native development profile")
    manifest = _raw(_read_envelope(reader, publication_ref.artifact_ref))
    entry = next(v for v in _seq(manifest["artifacts"]) if v["relative_path"] == "result.json")
    result = _raw(_read_envelope(reader, d.ArtifactRef(entry["artifact_type"], entry["schema_version"], entry["content_hash"])))
    request = _map(_map(result["resolved_request"])["request"])
    evidence = _raw(_read_envelope(reader, _wire_ref(result["canonical_evidence_manifest_ref"])))
    entry = next(v for v in _seq(evidence["artifacts"]) if v["role"] == "engine_execution_result")
    engine_ref = d.ArtifactRef(entry["artifact_type"], entry["schema_version"], entry["content_hash"])
    engine = _raw(_read_envelope(reader, engine_ref))
    input_envelope = _read_envelope(reader, input_ref)
    decoded = _EXECUTION_INPUT_CATALOG.read(d.canonical_bytes(input_envelope)).artifact
    if type(decoded) is not _DecodedExecutionInputBundleV8:
        raise ValueError("NAV requires the sole native input8 decoder")
    plan, spec = decoded.execution_case_plan, decoded.execution_case_semantic_spec
    if (decoded.request_hash != result["request_hash"] or decoded.semantic_run_id != completed.semantic_run_id
            or spec.semantic_spec_hash != completed.engine_context.semantic_spec_hash
            or decoded.target_stream.target_stream_digest != completed.engine_context.target_stream_digest
            or spec.case_key != "cn.portfolio.shared-cny.standard.development.v1"
            or decoded.build_artifact_manifest.manifest_hash != request["build_artifact_manifest_hash"]
            or d.canonical_bytes(plan.financial_state) != d.canonical_bytes(completed.engine_context.financial_state)):
        raise ValueError("NAV input8 does not bind the original request/run/native state")
    refs = dict(plan.source_refs)
    if set(refs) != {"definition", "target_stream"}:
        raise ValueError("NAV input8 source roles must be exact")
    definition_ref = refs["definition"]
    definition = _read_envelope(reader, definition_ref)
    if (d.canonical_bytes(definition) != d.canonical_bytes(plan.definition)
            or spec.snapshot_inputs_hash != d.canonical_sha256({"role": "portfolio_snapshots", "definition": definition})):
        raise ValueError("NAV definition/snapshot semantic source binding mismatch")
    target_ref = BacktestTargetStreamRef(refs["target_stream"])
    target = BacktestTargetStreamRepository(reader=reader).load(target_ref)
    if d.canonical_bytes(target.target_stream) != d.canonical_bytes(decoded.target_stream):
        raise ValueError("NAV retained target stream differs from input8")
    inputs = _read_standard_definition_v1(definition, target_ref)
    if (d.canonical_bytes(_native_initial_financial_state_v1(inputs)) != d.canonical_bytes(plan.financial_state)
            or d.canonical_bytes(inputs.scope.market_bundle_ref) != d.canonical_bytes(request["market_bundle_ref"])
            or inputs.scope.account_id != completed.starting_snapshot.account_id):
        raise ValueError("NAV definition/native initial/bundle/account binding mismatch")
    window = _read_timeline_window(request["timeline_window"])
    start = min(t.opening_at for t in inputs.opening_terms).to_datetime().astimezone(_ZONE).date()
    end_local = window.end_exclusive.to_datetime().astimezone(_ZONE)
    end = end_local.date()
    if end_local.time() != time() or window.end_exclusive.epoch_nanoseconds % 1_000_000_000:
        raise ValueError("NAV v1 requires a finite midnight-exclusive complete-day window")
    calendars = inputs.calendars
    if any(c.coverage_start > start or c.coverage_end_exclusive < end for c in calendars):
        raise ValueError("NAV calendar does not cover the complete execution window")
    dates = tuple(tuple(day.local_date for day in c.days if start <= day.local_date < end
                        and day.kind is CnAShareCalendarDayKind.TRADING) for c in calendars)
    actual_days = tuple(mark.at.instant.to_datetime().astimezone(_ZONE).date() for mark in inputs.daily_marks)
    if dates[0] != dates[1] or actual_days != dates[0]:
        raise ValueError("NAV frozen close dates do not exact-cover both trading calendars")
    if any(not window.trading_start <= mark.at.instant < window.end_exclusive for mark in inputs.daily_marks):
        raise ValueError("NAV close is outside its original window")
    journal = completed.execution_summary.final_journal
    after_initial = journal.entries[completed.initial_journal_entry_count:]
    if any(e.entry_type in (d.AccountingEntryType.CAPITAL_DEPOSITED, d.AccountingEntryType.CAPITAL_WITHDRAWN)
           for e in after_initial):
        raise ValueError("NAV v1 rejects external cash flows after initial capital")
    transfer_groups: dict[tuple, list[d.AccountingJournalEntry]] = {}
    for entry in after_initial:
        if entry.entry_type is not d.AccountingEntryType.CAPITAL_TRANSFERRED:
            continue
        if (len(entry.source_ids) != 1 or not entry.source_ids[0].startswith(
                "cn.portfolio.live-venue-funding.development.v1:sha256:") or len(entry.balance_changes) != 1):
            raise ValueError("NAV only permits the original paired native venue funding model")
        change = entry.balance_changes[0]
        if (type(change.key) is not d.CashBalanceKey or change.key.account_id != inputs.scope.account_id
                or type(change.value) is not d.Money or change.value.currency != "CNY"
                or change.value.scale != _CENT or change.value.units == 0):
            raise ValueError("NAV modeled transfer must be same-account CNY-cent cash")
        key = (entry.source_ids, entry.recorded_at.instant, entry.recorded_at.phase)
        transfer_groups.setdefault(key, []).append(entry)
    for group in transfer_groups.values():
        if (len(group) != 2 or {e.balance_changes[0].key.venue_id.value for e in group} != {"xshg", "xshe"}
                or sum(e.balance_changes[0].value.units for e in group) != 0):
            raise ValueError("NAV venue funding requires same-clock opposite SH/SZ cash legs")
    _reject_unmodeled_dividends_v1(journal=journal, schema=inputs.scope.ledger_schema,
        account=inputs.scope.account_id, instruments=inputs.scope.instrument_ids, guards=inputs.dividend_guards,
        start=start, end_exclusive=end)
    native = tuple(_map(v) for v in _seq(engine["financial_artifacts"]))
    days = sorted((v for v in native if v["role"] == "native_daily_snapshot"),
                  key=lambda v: _read_simulation_instant(v["occurred_at"]))
    witnesses = tuple(v for v in native if v["role"] == "native_attempt_witness")
    if len(days) != len(inputs.daily_marks) or len(witnesses) != 1:
        raise ValueError("NAV requires exact daily facts and one original attempt witness")
    points = []
    prior_count = completed.initial_journal_entry_count
    def fact(artifact: Mapping[str, Any]) -> d.ArtifactEnvelope:
        if (set(artifact) != {"type", "schema_version", "role", "component_key", "component_version",
                "component_digest", "input_hash", "result_hash", "source_event_id", "occurred_at", "payload"}
                or artifact["type"] != "financial_dispatch_artifact" or type(artifact["schema_version"]) is not int
                or artifact["schema_version"] != 1 or type(artifact["component_version"]) is not int):
            raise ValueError("NAV native financial artifact has unknown schema fields")
        inline = _map(artifact["payload"])
        value = d.ArtifactEnvelope.create("cn_a_share_portfolio_" + artifact["role"], 1, inline["payload"])
        if (d.canonical_bytes(value) != d.canonical_bytes(inline)
                or artifact["component_key"] != _COMPONENT or artifact["component_version"] != 1
                or artifact["component_digest"] != _COMPONENT_HASH
                or artifact["input_hash"] != d.canonical_sha256(definition)
                or artifact["result_hash"] != d.canonical_sha256(value)):
            raise ValueError("NAV native fact envelope/component/definition binding mismatch")
        return value
    witness = _map(fact(witnesses[0]).payload)
    final_ledger = t.GenericLedger(inputs.scope.ledger_schema).project(journal)
    if d.canonical_bytes(final_ledger) != d.canonical_bytes(engine["final_ledger_state"]):
        raise ValueError("NAV final Ledger differs from the native complete Journal projection")
    if (witness["type"] != "cn_a_share_portfolio_standard_native_witness" or witness["schema_version"] != 1
            or witness["initial_journal_hash"] != inputs.initial_journal.journal_hash
            or witness["target_stream_digest"] != decoded.target_stream.target_stream_digest
            or witness["final_ledger_hash"] != final_ledger.state_hash
            or witness["run_end_report_hash"] != d.canonical_sha256(engine["run_end_report"])
            or witness["final_journal_hash"] != journal.journal_hash or witness["daily_count"] != len(days)
            or witness["definition_hash"] != d.canonical_sha256(definition)
            or witness["case_hash"] != completed.engine_context.case_hash
            or d.canonical_bytes(witness["run_end_mark_policy"]) != d.canonical_bytes(_RUN_END_MARK_POLICY)
            or any(witness[k] is not False for k in ("source_qualification_verified", "broker_shared_pool_verified", "trade_authorized"))):
        raise ValueError("NAV original attempt witness does not bind the final native head")
    for artifact, mark in zip(days, inputs.daily_marks, strict=True):
        envelope = fact(artifact)
        row = _map(envelope.payload)
        if set(row) != {"marks", "snapshot", "journal_count", "book", "pending_intentions"}:
            raise ValueError("NAV native daily fact has unknown or missing source fields")
        at = _read_simulation_instant(artifact["occurred_at"])
        count = row["journal_count"]
        visible = sum(e.recorded_at <= mark.at for e in journal.entries)
        if (type(count) is not int or count != visible or not prior_count <= count <= journal.entry_count
                or d.canonical_bytes(row["marks"]) != d.canonical_bytes(mark) or at != mark.at
                or artifact["source_event_id"] != "daily." + str(at.instant.epoch_nanoseconds)):
            raise ValueError("NAV close/source/maximal full-clock Journal head mismatch")
        prefix = t.AccountingJournal.from_entries(journal.entries[:count])
        stored = _read_portfolio_snapshot(row["snapshot"])
        projected = _native_snapshot_at_v1(inputs, prefix, mark)
        if d.canonical_bytes(stored) != d.canonical_bytes(projected):
            raise ValueError("NAV snapshot differs from the actual native Journal/marks projection")
        points.append(CnASharePortfolioDailyNavPointV1(at.instant.to_datetime().astimezone(_ZONE).date().isoformat(),
            at, projected.equity, d.canonical_sha256(projected), prefix.journal_hash,
            d.canonical_sha256(mark), envelope.content_hash))
        prior_count = count
    if prior_count != journal.entry_count or points[-1].equity != completed.execution_summary.final_portfolio_snapshot.equity:
        raise ValueError("NAV final close must bind the complete final native head/equity")
    return CnASharePortfolioDailyNavAnalysisV1(_PROFILE_REF, publication_ref, input_ref, definition_ref, engine_ref,
        completed.source_execution_result_hash, d.canonical_sha256(completed.starting_snapshot),
        completed.starting_snapshot.equity, tuple(points), len(completed.execution_summary.fills), completed.result_grade)


class CnASharePortfolioDailyNavAnalysisRuntimeV1:
    def __init__(self, *, reader: ArtifactEnvelopeReader, publisher: ArtifactEnvelopePublisher) -> None:
        if not callable(getattr(reader, "read", None)) or not callable(getattr(publisher, "put", None)):
            raise TypeError("NAV Runtime requires the existing artifact reader/publisher protocols")
        self._reader, self._publisher = reader, publisher

    def publish_metric_profile(self) -> d.ArtifactRef:
        ref = self._publisher.put(envelope=_PROFILE_ENVELOPE)
        if type(ref) is not d.ArtifactRef or ref != _PROFILE_REF:
            raise ValueError("publisher did not bind the exact NAV profile")
        return ref

    def derive(self, *, publication_ref: BacktestCanonicalPublicationRef,
               execution_input_ref: d.ArtifactRef, metric_profile_ref: d.ArtifactRef,
               ) -> CnASharePortfolioDailyNavAnalysisRefV1:
        if type(publication_ref) is not BacktestCanonicalPublicationRef:
            raise TypeError("exact standard canonical publication ref required")
        _ref(execution_input_ref, "backtest_execution_input_bundle", 8)
        _ref(metric_profile_ref, _PROFILE_TYPE, 1)
        if metric_profile_ref != _PROFILE_REF:
            raise ValueError("NAV profile must be the accepted exact identity")
        profile = _read_envelope(self._reader, metric_profile_ref)
        _read_nav_profile(profile.payload)
        value = _build_nav_analysis(self._reader, publication_ref, execution_input_ref)
        envelope = d.ArtifactEnvelope.create(_ANALYSIS_TYPE, 1, value)
        expected = d.ArtifactRef.from_envelope(envelope)
        stored = self._publisher.put(envelope=envelope)
        if type(stored) is not d.ArtifactRef or stored != expected:
            raise ValueError("publisher did not bind the source-derived NAV analysis")
        return CnASharePortfolioDailyNavAnalysisRefV1(stored)
