"""Private, finite durable wire grammar. No provider artifact, I/O or execution."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any

import crypto_quant_domain as d
import crypto_quant_trading as t
from crypto_quant_market_data import MarketBundleRef
from . import execution_inputs as inputs
from . import resolution as r
from . import runner
from . import engine
from . import slippage as s
from . import run_end as end
from .financial_dispatch import FinancialDispatchArtifact
from .evidence import EvidenceArtifactEntry, EvidenceArtifactRole, EvidenceManifest, EvidencePublicationStatus


@dataclass(frozen=True, slots=True)
class _DurableDecodeContext:
    execution_input_ref: d.ArtifactRef
    execution_input_source_hash: str
    request_hash: str
    semantic_run_id: str
    ledger_schema: t.LedgerSchema
    build_artifact_manifest: r.BuildArtifactManifest
    slippage_envelopes: tuple[s.SlippageApplicabilityEnvelope, ...]

    def __post_init__(self):
        if (type(self.execution_input_ref) is not d.ArtifactRef
                or self.execution_input_ref.artifact_type != "backtest_execution_input_bundle"
                or self.execution_input_ref.schema_version not in (3, 4)
                or type(self.ledger_schema) is not t.LedgerSchema
                or type(self.build_artifact_manifest) is not r.BuildArtifactManifest
                or type(self.slippage_envelopes) is not tuple
                or not all(type(e) is s.SlippageApplicabilityEnvelope for e in self.slippage_envelopes)):
            raise TypeError("invalid durable decode context")
        hashes = tuple(e.envelope_hash for e in self.slippage_envelopes)
        if hashes != tuple(sorted(set(hashes))):
            raise ValueError("context envelopes must be hash-ordered and unique")


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate durable JSON key")
        result[key] = value
    return result


def _number(value):
    raise ValueError("durable JSON numbers must be exact integers")


def _source(source: d.ArtifactReadResult, ref: d.ArtifactRef) -> d.ArtifactEnvelope:
    if (type(source) is not d.ArtifactReadResult or type(ref) is not d.ArtifactRef
            or type(ref.schema_version) is not int):
        raise TypeError("exact durable source/ref and integer version required")
    value = json.loads(source.source_bytes, object_pairs_hook=_pairs,
                       parse_float=_number, parse_constant=_number)
    if (type(value) is not dict or set(value) != {"artifact_type", "schema_version", "payload", "content_hash"}
            or type(value["schema_version"]) is not int):
        raise ValueError("invalid durable envelope header")
    envelope = d.ArtifactEnvelope(**value)
    if (d.ArtifactRef.from_envelope(envelope) != ref
            or d.canonical_bytes(envelope) != source.source_bytes
            or envelope != source.envelope
            or source.source_hash != "sha256:" + hashlib.sha256(source.source_bytes).hexdigest()):
        raise ValueError("durable source/ref/hash binding mismatch")
    return envelope


def _input_envelopes(decoded) -> tuple[s.SlippageApplicabilityEnvelope, ...]:
    values = {}
    for bar in decoded.execution_case_plan.bar_executions:
        value = bar.slippage_model.applicability_envelope
        if type(value) is not s.SlippageApplicabilityEnvelope:
            raise TypeError("input Bar must own a native slippage envelope")
        old = values.setdefault(value.envelope_hash, value)
        if d.canonical_bytes(old) != d.canonical_bytes(value):
            raise ValueError("conflicting slippage envelope hash")
    return tuple(values[key] for key in sorted(values))


def _context_from_verified_inputs(source, decoded, request, expected_build_manifest, expected_semantic_run_id):
    if type(request) is not inputs.BacktestExecutionRequest or request.schema_version not in (3, 4):
        raise TypeError("context requires input3/4 request")
    envelope = _source(source, request.execution_input_bundle_ref)
    # Existing pure exact decoder, not a live registry or provider payload.
    bound = inputs._EXECUTION_INPUT_CATALOG.read(source.source_bytes).artifact
    if type(decoded) is not inputs._DecodedExecutionInputBundleV3 or type(bound) is not inputs._DecodedExecutionInputBundleV3:
        raise TypeError("context requires decoded input3/4")
    schema = bound.execution_case_plan.financial_state.ledger_schema
    envelopes = _input_envelopes(bound)
    if (envelope.schema_version != request.schema_version
            or bound.request_hash != request.request.request_hash
            or decoded.request_hash != bound.request_hash
            or decoded.semantic_run_id != bound.semantic_run_id
            or bound.semantic_run_id != expected_semantic_run_id
            or d.canonical_bytes(decoded.build_artifact_manifest) != d.canonical_bytes(bound.build_artifact_manifest)
            or d.canonical_bytes(bound.build_artifact_manifest) != d.canonical_bytes(expected_build_manifest)
            or request.request.build_artifact_manifest_hash != expected_build_manifest.manifest_hash
            or d.canonical_bytes(decoded.execution_case_plan.financial_state.ledger_schema) != d.canonical_bytes(schema)
            or d.canonical_bytes(_input_envelopes(decoded)) != d.canonical_bytes(envelopes)):
        raise ValueError("context input/request/run/schema/build binding mismatch")
    return _DurableDecodeContext(request.execution_input_bundle_ref, source.source_hash,
        bound.request_hash, bound.semantic_run_id, schema, bound.build_artifact_manifest, envelopes)


def _same_resolved_source_roots(source_resolved, live_resolved) -> bool:
    return (type(source_resolved) is r.ResolvedBacktestRequest
            and type(live_resolved) is r.ResolvedBacktestRequest
            and d.canonical_bytes(source_resolved) == d.canonical_bytes(live_resolved)
            and d.canonical_bytes(source_resolved.build_artifact_manifest) == d.canonical_bytes(live_resolved.build_artifact_manifest))


def _roundtrip(value, result):
    if d.canonical_bytes(value) != d.canonical_bytes(result):
        raise ValueError("durable value did not reconstruct exactly")
    return result


def _tag(value, name):
    if type(value) is not dict or value.get("type") != name:
        raise ValueError("wrong durable value tag")
    return value


def _make(value, tag, cls, fields, context=None, *, overrides=None, optional=()):
    data = _tag(value, tag)
    overrides = overrides or {}
    names = tuple(fields.split()) + tuple(name for name in optional if name in data)
    args = {name: overrides[name](data[name]) if name in overrides else _value(data[name], context) for name in names}
    return _roundtrip(data, cls(**args))


def _read_request(value):
    return _make(value, "backtest_request", r.BacktestRequest,
        "schema_version experiment_id timeline_window market_semantics_profile_key simulation_profile_key execution_account_profile_key execution_account_id reporting_currency market_bundle_ref target_stream_digest execution_case_semantic_hash master_random_seed build_artifact_manifest_hash strategy_family engine_kind result_grade_requested",
        overrides={"strategy_family": r.StrategyFamily, "result_grade_requested": r.RequestedResultGrade,
                   "model_binding": r.ModelRequestBinding.from_canonical_dict}, optional=("model_binding",))


def _read_compatibility(value):
    return _make(value, "environment_compatibility_report", r.EnvironmentCompatibilityReport,
        "request_hash market_bundle_manifest_hash profile_digests checks allowed_grade limitations",
        overrides={"allowed_grade": r.RequestedResultGrade})


def _read_environment(value):
    return _make(value, "resolved_backtest_environment", r.ResolvedBacktestEnvironment,
                 "market_semantics simulation execution_account market_bundle_ref compatibility_report limitations deployment_authorized")


def _read_market_registration(value):
    data = _tag(value, "market_semantics_profile_registration")
    components = tuple(inputs._read_profile_component_ref(v) for v in data["component_manifest"])
    spec = inputs._read_financial_dispatcher_spec(data["financial_dispatcher_spec"]) if "financial_dispatcher_spec" in data else None
    header = r._MarketProfileEvidenceHeader(data["profile_digest"], components, spec)
    return _roundtrip(data, r.MarketSemanticsProfileRegistration(
        data["profile_key"], data["profile_version"], data["profile_digest"], header,
        data["venue_id"], tuple(inputs._read_market_bundle_capability(v) for v in data["required_bundle_capabilities"]),
        components, r.RequestedResultGrade(data["grade"]), tuple(data["limitations"]), data["decision_grade_eligible"], spec))


def _read_simulation_registration(value):
    data = _tag(value, "simulation_profile_registration")
    components = tuple(inputs._read_simulation_component_ref(v) for v in data["component_manifest"])
    header = r._SimulationProfileEvidenceHeader(data["profile_digest"], components)
    return _roundtrip(data, r.SimulationProfileRegistration(
        data["profile_key"], data["profile_version"], data["profile_digest"], header, data["engine_kind"],
        tuple(r.StrategyFamily(v) for v in data["supported_strategy_families"]),
        tuple(inputs._read_market_bundle_capability(v) for v in data["required_bundle_capabilities"]),
        components, r.RequestedResultGrade(data["grade"]), tuple(data["limitations"]), data["decision_grade_eligible"]))


def _read_account_registration(value):
    data = _tag(value, "execution_account_profile_registration")
    return _roundtrip(data, r.ExecutionAccountProfileRegistration(
        data["profile_key"], data["profile_version"], data["profile_digest"], r._AccountProfileEvidenceHeader(data["profile_digest"]),
        data["account_id"], data["venue_id"], data["account_type"], data["margin_mode"],
        tuple(inputs._read_currency(v) for v in data["supported_reporting_currencies"]),
        r.RequestedResultGrade(data["grade"]), tuple(data["limitations"]), data["decision_grade_eligible"]))


def _read_manifest(value):
    data = _tag(value, "evidence_manifest_identity")
    return _roundtrip(data, EvidenceManifest(data["semantic_run_id"], data["attempt_id"],
        EvidencePublicationStatus(data["status"]), runner.BacktestRunOutcome(data["terminal_outcome"]) if data["terminal_outcome"] is not None else None,
        tuple(EvidenceArtifactEntry(v["relative_path"], EvidenceArtifactRole(v["role"]), v["artifact_type"], v["schema_version"],
                                   v["content_hash"], v["source_hash"], v["byte_count"]) for v in data["artifacts"]),
        data["market_bundle_ref_hash"], data["attempt_record_hash"], data["deployment_authorized"]))


def _read_ledger_state(value, *, schema):
    data = _tag(value, "ledger_state")
    if data["schema_hash"] != schema.schema_hash:
        raise ValueError("ledger schema hash mismatch")
    return _roundtrip(data, t.LedgerState(schema, t.JournalReplayCursor(data["cursor"]["position"], data["cursor"]["prefix_hash"]),
        tuple(_value(v) for v in data["cash_balances"]), tuple(inputs._read_position_balance(v) for v in data["position_balances"]),
        tuple(_value(v) for v in data["realized_pnl"]), tuple(_value(v) for v in data["fees"]), tuple(_value(v) for v in data["financing"])))


def _read_slippage_applicability_result(value, *, request, context):
    data = _tag(value, "slippage_applicability_result")
    if type(context) is not _DurableDecodeContext:
        raise TypeError("slippage requires bound input context")
    matches = tuple(e for e in context.slippage_envelopes if e.envelope_hash == data["envelope_hash"])
    if len(matches) != 1 or request.market_state.state_hash != data["market_state_hash"]:
        raise ValueError("slippage envelope/state binding mismatch")
    return _roundtrip(data, s.SlippageApplicabilityResult(matches[0], request.market_state,
        tuple(s.SlippageApplicabilityDimension(v) for v in data["checked_dimensions"]), data["applicable"]))


def _read_slippage(value, context):
    data = _tag(value, "slippage_decision")
    request = _value(data["request"], context)
    return _roundtrip(data, s.SlippageDecision(request, _value(data["component_ref"]), _value(data["calibration_ref"]),
        _read_slippage_applicability_result(data["applicability"], request=request, context=context),
        data["basis_points_units"], d.Scale(data["basis_points_scale"]), d.RoundingPolicy(data["rounding"]),
        inputs._read_price(data["slippage_amount"]), inputs._read_price(data["execution_price"]),
        tuple(s.SlippageLimitation(v) for v in data["limitations"])))


def _read_resolved(value, context):
    data = _tag(value, "resolved_backtest_request")
    if type(context) is not _DurableDecodeContext or data["build_artifact_manifest_hash"] != context.build_artifact_manifest.manifest_hash:
        raise ValueError("resolved request needs matching build context")
    result = r.ResolvedBacktestRequest(_read_request(data["request"]),
        _make(data["normalized_request"], "normalized_backtest_request", r.NormalizedBacktestRequest, "request request_hash"),
        _read_environment(data["environment"]), context.build_artifact_manifest, data["semantic_run_id"])
    if result.semantic_run_id != context.semantic_run_id or result.request.request_hash != context.request_hash:
        raise ValueError("resolved request input/run mismatch")
    return _roundtrip(data, result)


def _read_record(value, context):
    data = _tag(value, "attempt_execution_record")
    if type(context) is not _DurableDecodeContext or data["status"] != runner.AttemptExecutionStatus.READY_TO_FINALIZE.value:
        raise ValueError("durable proof requires ready record and input context")
    ready = data["ready_to_finalize"]
    result = runner.AttemptExecutionRecord(ready_to_finalize=runner.ReadyToFinalizeAttempt(
        _value(ready["attempt"]), _read_resolved(ready["resolved_request"], context),
        runner.InputOrigin(ready["input_origin"]), ready["execution_case_hash"], _read_engine(ready["engine_result"], context)))
    return _roundtrip(data, result)


def _read_engine(value, context):
    if type(context) is not _DurableDecodeContext:
        raise TypeError("Engine source requires bound input context")
    data = _tag(value, "engine_execution_result")
    return _make(data, "engine_execution_result", engine.EngineExecutionResult,
        "case_hash target_stream_digest trace decision_batches allocations approved_targets normalized_targets order_plans order_streams fills slippage_decisions fee_assessments financial_artifacts final_journal final_ledger_state final_portfolio_snapshot run_end_report", context)


def decode_durable_artifact_source(source, ref, expected_type, *, context=None):
    envelope = _source(source, ref)
    types = {EvidenceManifest: "evidence_manifest", r.BacktestRequest: "backtest_request",
        r.BuildArtifactManifest: "build_artifact_manifest", MarketBundleRef: "market_bundle_ref",
        r.EnvironmentCompatibilityReport: "environment_compatibility_report", r.ResolvedBacktestEnvironment: "resolved_backtest_environment",
        runner.AttemptExecutionRecord: "attempt_execution_record", engine.EngineExecutionResult: "engine_execution_result"}
    if expected_type not in types or ref.artifact_type != types[expected_type] or ref.schema_version != 1:
        raise TypeError("unsupported durable artifact type/version")
    payload = json.loads(d.canonical_bytes(envelope.payload))
    if expected_type is EvidenceManifest:
        value = _read_manifest(payload)
    elif expected_type is runner.AttemptExecutionRecord:
        value = _read_record(payload, context)
    elif expected_type is engine.EngineExecutionResult:
        value = _read_engine(payload, context)
    else:
        value = _value(payload, context)
    if type(value) is not expected_type:
        raise TypeError("wrong durable native type")
    if d.canonical_bytes(d.ArtifactEnvelope.create(ref.artifact_type, 1, value)) != source.source_bytes:
        raise ValueError("durable artifact canonical roundtrip mismatch")
    return d.ArtifactReadResult(envelope=envelope, artifact=value,
                               source_bytes=source.source_bytes, source_hash=source.source_hash)


# Finite grammar for the original eight durable sources and their typed values.
# Every constructor is static; this is not a class-name/plugin/reflection registry.
def _value(value, context=None):
    if value is None or type(value) in (str, int, bool):
        return value
    if type(value) is list:
        return tuple(_value(v, context) for v in value)
    if type(value) is not dict:
        raise TypeError("unsupported durable wire value")
    tag = value.get("type")
    if tag in _INPUT_READERS:
        return _roundtrip(value, _INPUT_READERS[tag](value))
    if tag in _STATIC_READERS:
        return _STATIC_READERS[tag](value, context)
    if tag == "ledger_state":
        if type(context) is not _DurableDecodeContext:
            raise TypeError("ledger requires bound input context")
        return _read_ledger_state(value, schema=context.ledger_schema)
    if tag == "slippage_decision":
        return _read_slippage(value, context)
    if tag == "engine_execution_result":
        return _read_engine(value, context)
    raise ValueError("unsupported durable value tag")


_INPUT_READERS = {
    "money": inputs._read_money, "price": inputs._read_price, "quantity": inputs._read_quantity,
    "rate": inputs._read_rate, "utc_instant": inputs._read_utc, "simulation_instant": inputs._read_simulation_instant,
    "instrument_id": inputs._read_instrument_id, "currency_id": inputs._read_currency,
    "venue_id": inputs._read_venue, "domain_id": inputs._read_domain_id,
    "source_sequence": inputs._read_source_sequence, "timeline_phase": inputs._read_timeline_phase,
    "cash_balance_key": inputs._read_cash_key, "position_balance_key": inputs._read_position_key,
    "order": inputs._read_order,
    "order_event": inputs._read_order_event, "order_event_record": inputs._read_order_event_record,
    "order_event_stream": inputs._read_order_event_stream, "fill": inputs._read_fill,
    "position_lot": inputs._read_position_lot, "position_balance": inputs._read_position_balance,
    "accounting_journal": inputs._read_journal, "accounting_journal_entry": inputs._read_journal_entry,
    "balance_change": inputs._read_balance_change, "portfolio_snapshot": inputs._read_portfolio_snapshot,
    "valuation_mark_reference": inputs._read_valuation_mark_reference,
    "profile_component_ref": inputs._read_profile_component_ref, "simulation_component_ref": inputs._read_simulation_component_ref,
    "timeline_window": inputs._read_timeline_window, "build_artifact_manifest": inputs._read_build_manifest,
    "market_bundle_capability": inputs._read_market_bundle_capability,
    "instrument_sizing_input": inputs._read_sizing_input, "quantity_lattice": inputs._read_quantity_lattice,
    "position_sizing_policy": inputs._read_sizing_policy, "rebalance_policy": inputs._read_rebalance_policy,
    "resolved_mark": inputs._read_resolved_mark, "cost_basis_policy": inputs._read_cost_basis,
    "capital_allocation_policy_ref": inputs._read_capital_policy_ref,
    "strategy_allocation": inputs._read_allocation, "portfolio_risk_limit": inputs._read_portfolio_risk_limit,
}

def _enums(cls):
    return lambda values: tuple(cls(value) for value in values)


def _read_trace(value, context):
    data = _tag(value, "execution_trace")
    return _roundtrip(data, engine.ExecutionTrace(tuple(engine.ExecutionTraceEntry(
        v["sequence"], engine.EngineStage(v["stage"]), inputs._read_simulation_instant(v["instant"]),
        v["subject_id"], v["evidence_hash"]) for v in data["entries"])))


def _read_active(value, context):
    return _make(value, "active_portfolio_target", d.ActivePortfolioTarget,
        "source_decision_batch_id materialized_at quantities", context,
        overrides={"quantities": lambda rows: tuple((inputs._read_instrument_id(row["instrument_id"]),
                                                   inputs._read_quantity(row["quantity"])) for row in rows)},
        optional=("materialized_instant",))


_STATIC_READERS = {
    "backtest_request": lambda v, c: _read_request(v),
    "build_artifact_manifest": lambda v, c: inputs._read_build_manifest(v),
    "market_bundle_ref": lambda v, c: _roundtrip(v, MarketBundleRef(v["bundle_key"], v["manifest_hash"])),
    "environment_compatibility_report": lambda v, c: _read_compatibility(v),
    "environment_compatibility_check": lambda v, c: _make(v, "environment_compatibility_check", r.EnvironmentCompatibilityCheck, "code passed subjects", overrides={"code": r.EnvironmentCompatibilityCheckCode}),
    "resolved_backtest_environment": lambda v, c: _read_environment(v),
    "market_semantics_profile_registration": lambda v, c: _read_market_registration(v),
    "simulation_profile_registration": lambda v, c: _read_simulation_registration(v),
    "execution_account_profile_registration": lambda v, c: _read_account_registration(v),
    "normalized_backtest_request": lambda v, c: _make(v, "normalized_backtest_request", r.NormalizedBacktestRequest, "request request_hash"),
    "attempt_identity": lambda v, c: _make(v, "attempt_identity", runner.AttemptIdentity, "semantic_run_id attempt_id ordinal parent_attempt_id"),
    "cash_balance": lambda v, c: _make(v, "cash_balance", d.CashBalance, "key amount"),
    "strategy_sleeve_id": lambda v, c: _roundtrip(v, d.StrategySleeveId(v["value"])),
    "target_exposure_fraction": lambda v, c: _make(v, "target_exposure_fraction", d.TargetExposureFraction, "instrument_id units scale", overrides={"scale": d.Scale}),
    "target_snapshot": lambda v, c: _make(v, "target_snapshot", d.TargetSnapshot, "sleeve_id effective_time expires_at targets"),
    "strategy_decision": lambda v, c: _make(v, "strategy_decision", d.StrategyDecision, "strategy_id decision_time observed_through target_snapshot confidence reason evidence", overrides={"evidence": inputs._read_canonical_data}, optional=("decision_instant",)),
    "decision_batch": lambda v, c: _make(v, "decision_batch", d.DecisionBatch, "decision_batch_id decision_time decisions", optional=("decision_instant",)),
    "portfolio_allocation": lambda v, c: _make(v, "portfolio_allocation", t.PortfolioAllocation, "allocation_id valuation_time valuation_currency target_notional_scale policy_ref source_sleeve_state_hash source_portfolio_snapshot_hash allocations total_allocation_nav sleeve_targets net_targets", overrides={"target_notional_scale": d.Scale}, optional=("valuation_instant",)),
    "sleeve_target_notional": lambda v, c: _make(v, "sleeve_target_notional", t.SleeveTargetNotional, "strategy_id sleeve_id instrument_id target_fraction allocation_nav target_notional"),
    "net_instrument_target": lambda v, c: _make(v, "net_instrument_target", t.NetInstrumentTarget, "instrument_id valuation_currency target_notional sleeve_attributions"),
    "portfolio_risk_policy_ref": lambda v, c: _make(v, "portfolio_risk_policy_ref", t.PortfolioRiskPolicyRef, "policy_key policy_version config_hash"),
    "portfolio_risk_decision": lambda v, c: _make(v, "portfolio_risk_decision", t.PortfolioRiskDecision, "scope action reason_code limit_id policy_ref before_notional after_notional limit_notional instrument_id", overrides={"scope": t.PortfolioRiskScope, "action": t.PortfolioRiskAction, "reason_code": t.PortfolioRiskReasonCode}),
    "approved_instrument_target": lambda v, c: _make(v, "approved_instrument_target", t.ApprovedInstrumentTarget, "source_target approved_notional"),
    "approved_portfolio_target": lambda v, c: _make(v, "approved_portfolio_target", t.ApprovedPortfolioTarget, "approved_target_id approved_at source_allocation_id source_allocation_hash policy_ref targets gross_exposure net_exposure decisions", optional=("approved_instant",)),
    "active_portfolio_target": _read_active,
    "position_sizing_decision": lambda v, c: _make(v, "position_sizing_decision", t.PositionSizingDecision, "instrument_id approved_notional current_quantity raw_quantity final_quantity residual_quantity final_notional applied_lot_units actions reason_codes mark_id lattice_hash policy_hash", overrides={"actions": _enums(t.PositionSizingAction), "reason_codes": _enums(t.PositionSizingReasonCode)}),
    "normalized_instrument_target": lambda v, c: _make(v, "normalized_instrument_target", t.NormalizedInstrumentTarget, "source_target sizing_input decision"),
    "normalized_portfolio_target": lambda v, c: _make(v, "normalized_portfolio_target", t.NormalizedPortfolioTarget, "normalized_target_id source_decision_batch_id materialized_at source_approved_target_id source_approved_target_hash policy targets active_target", optional=("materialized_instant",)),
    "order_intent": lambda v, c: _make(v, "order_intent", d.OrderIntent, "instrument_id side quantity execution_style price_constraint time_in_force reduce_only position_effect urgency reason parent_id", overrides={"side": d.OrderSide, "execution_style": d.ExecutionStyle, "time_in_force": d.TimeInForce, "position_effect": d.PositionEffect}),
    "price_constraint": lambda v, c: _make(v, "price_constraint", d.PriceConstraint, "limit_price trigger_price"),
    "lot_consumption": lambda v, c: _make(v, "lot_consumption", t.LotConsumption, "lot_id source_fill_id quantity unit_cost allocated_fees", optional=("total_cost_basis",)),
    "cancel_intent": lambda v, c: _make(v, "cancel_intent", t.CancelIntent, "cancel_intent_id order_id instrument_id reason_code normalized_target_id"),
    "planning_omission": lambda v, c: _make(v, "planning_omission", t.PlanningOmission, "instrument_id code current_quantity target_quantity retained_working_coverage", overrides={"code": t.PlanningOmissionCode}),
    "pending_fee_assessment_ref": lambda v, c: _make(v, "pending_fee_assessment_ref", end.PendingFeeAssessmentRef, "basis_type basis_ids basis_hash closed_at", overrides={"basis_type": d.FeeBasisType}),
    "order_terminated_by_run_end": lambda v, c: _make(v, "order_terminated_by_run_end", end.OrderTerminatedByRunEnd, "order_id stream_hash state_hash prior_status remaining_quantity terminated_at", overrides={"prior_status": d.OrderStatus}),
    "run_end_reservation_release": lambda v, c: _make(v, "run_end_reservation_release", end.RunEndReservationRelease, "order_id reservation_hash commitment released_at"),
    "reservation_commitment": lambda v, c: _roundtrip(v, inputs._read_reservation_commitment(v)),
    "planned_order": lambda v, c: _make(v, "planned_order", t.PlannedOrder, "planned_order_id instrument_id intent current_quantity target_quantity retained_working_coverage planned_delta policy_hash"),
    "order_plan": lambda v, c: _make(v, "order_plan", t.OrderPlan, "plan_id account_id created_at based_on_normalized_target_id based_on_normalized_target_hash based_on_target_validity_hash based_on_portfolio_snapshot_hash based_on_working_order_set_hash based_on_reservation_state_hash based_on_availability_state_hash policy valid_until planned_orders cancel_intents omissions supersedes_plan_id"),
    "fee_assessment": lambda v, c: _make(v, "fee_assessment", d.FeeAssessment, "fee_assessment_id basis_type basis_ids market_fee_rule_id account_fee_schedule_id tax_rule_id amount assessment_time", overrides={"basis_type": d.FeeBasisType}),
    "execution_reference_price": lambda v, c: _make(v, "execution_reference_price", s.ExecutionReferencePrice, "mark"),
    "slippage_market_state": lambda v, c: _make(v, "slippage_market_state", s.SlippageMarketState, "state_key observed_at available_at source_event_id revision_id evidence_hash"),
    "slippage_calibration_ref": lambda v, c: _make(v, "slippage_calibration_ref", s.SlippageCalibrationRef, "calibration_key calibration_version calibration_digest"),
    "slippage_request": lambda v, c: _make(v, "slippage_request", s.SlippageRequest, "reference_price side quantity market_state", overrides={"side": d.OrderSide}),
    "execution_trace": _read_trace,
    "financial_dispatch_artifact": lambda v, c: _make(v, "financial_dispatch_artifact", FinancialDispatchArtifact, "role source_event_id occurred_at component_key component_version component_digest input_hash result_hash payload", c),
    "cash_fill_accounting_result": lambda v, c: _make(v, "cash_fill_accounting_result", t.CashFillAccountingResult, "journal_entry open_lots opened_lot lot_consumptions price_cost_basis gross_realized_pnl cost_basis_policy"),
    "run_end_report": lambda v, c: _make(v, "run_end_report", end.RunEndReport, "account_id trading_end_exclusive run_end_evidence_hash timeline_cursor_hash final_snapshot_hash journal_state_hash reservation_state_hash settlement_state_hash terminated_orders released_reservations open_positions pending_settlements pending_fee_assessments last_valuation_mark_ids closeout_component_ref closeout_outcome_hash closeout_mode closeout_status", overrides={"closeout_mode": end.RunEndCloseoutMode, "closeout_status": end.RunEndCloseoutStatus}),
}
