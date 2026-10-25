"""Strict pure economic values. No I/O, execution catalog or contextful result decoding."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

import crypto_quant_domain as d
import crypto_quant_trading as t
import crypto_quant_trading.profiles.cn_a_share.portfolio_economic_v1 as e


def _same(value, raw):
    if d.canonical_bytes(value) != d.canonical_bytes(raw):
        raise ValueError("economic value did not reconstruct canonical bytes exactly")
    return value


def _fields(raw, tag, names, *, version=True):
    if not isinstance(raw, Mapping):
        raise TypeError("economic value must be a mapping")
    expected = {"type", *names} | ({"schema_version"} if version else set())
    if set(raw) != expected or raw["type"] != tag:
        raise ValueError("economic value exact fields/tag mismatch: " + tag)
    if version and (type(raw["schema_version"]) is not int or raw["schema_version"] != 1):
        raise ValueError("economic value schema must be exact integer one")
    return raw


def _sequence(raw, reader):
    if type(raw) not in (tuple, list):
        raise TypeError("economic sequence must be tuple or list")
    return tuple(reader(v) for v in raw)


def _optional(raw, reader):
    return None if raw is None else reader(raw)


def _raw(value):
    return value


def _record(raw, tag, cls, readers):
    data = _fields(raw, tag, readers)
    return _same(cls(**{name: reader(data[name]) for name, reader in readers.items()}), raw)


def _read_economic_resolved_mark_v1(raw):
    from . import execution_inputs as x
    names = ("mark_id", "instrument_id", "quote_currency_id", "price_purpose", "price", "observed_at",
        "available_at", "resolved_at", "age_nanoseconds", "stream_id", "source_event_id", "revision_id",
        "stale_policy_key", "stale_policy_version", "stale_policy_hash", "available_at_instant", "resolved_at_instant")
    data = _fields(raw, "resolved_mark", names, version=False)
    if data["available_at_instant"] is None or data["resolved_at_instant"] is None:
        raise ValueError("economic marks require both complete availability/resolution clocks")
    value = replace(x._read_resolved_mark(data),
        available_at_instant=x._read_simulation_instant(data["available_at_instant"]),
        resolved_at_instant=x._read_simulation_instant(data["resolved_at_instant"]))
    return _same(value, raw)


def _read_cn_a_share_cash_dividend_claim_v1(raw):
    from . import execution_inputs as x
    def event(row):
        if type(row) not in (list, tuple) or len(row) != 4:
            raise ValueError("economic applied event must have four fields")
        return row[0], row[1], x._read_simulation_instant(row[2]), row[3]
    return _record(raw, "cn_a_share_cash_dividend_claim", e.CnAShareCashDividendClaimV1, {
        "account_id": _raw, "action_id": _raw, "instrument_id": x._read_instrument_id,
        "action_terms_hash": _raw, "tax_policy_hash": _raw, "record_journal_hash": _raw,
        "registered_at": x._read_simulation_instant, "entitlement_at": x._read_simulation_instant,
        "payment_due_at": x._read_simulation_instant, "entitled_quantity": _raw, "tax_mode": _raw,
        "tax_due_at": lambda v: _optional(v, x._read_simulation_instant),
        "recognized_gross": x._read_money, "gross_paid": x._read_money,
        "tax_assessed": x._read_money, "tax_settled": x._read_money,
        "applied_events": lambda v: _sequence(v, event)})


def _read_cn_a_share_cash_dividend_state_v1(raw):
    from . import execution_inputs as x
    return _record(raw, "cn_a_share_cash_dividend_state", e.CnAShareCashDividendStateV1, {
        "account_id": _raw, "as_of": x._read_simulation_instant,
        "claims": lambda v: _sequence(v, _read_cn_a_share_cash_dividend_claim_v1)})


def _read_cn_a_share_cash_dividend_tax_policy_v1(raw):
    from . import execution_inputs as x
    return _record(raw, "cn_a_share_cash_dividend_tax_policy", e.CnAShareCashDividendTaxPolicyV1, {
        "policy_id": _raw, "account_id": _raw, "mode": _raw, "numerator": _raw, "denominator": _raw,
        "quantization": x._read_quantization, "due_at": lambda v: _optional(v, x._read_simulation_instant)})


def _read_cn_a_share_cash_dividend_action_v1(raw):
    from . import execution_inputs as x
    def ref(v):
        data = _fields(v, "artifact_ref", ("artifact_type", "schema_version", "content_hash"), version=False)
        return _same(d.ArtifactRef(data["artifact_type"], data["schema_version"], data["content_hash"]), v)
    return _record(raw, "cn_a_share_cash_dividend_action", e.CnAShareCashDividendActionV1, {
        "action_id": _raw, "instrument_id": x._read_instrument_id, "registered_at": x._read_simulation_instant,
        "entitlement_at": x._read_simulation_instant, "payment_due_at": x._read_simulation_instant,
        "cash_per_share": x._read_money, "gross_quantization": x._read_quantization,
        "tax_policy": _read_cn_a_share_cash_dividend_tax_policy_v1,
        "fact_event_time": lambda v: _optional(v, x._read_utc),
        "provider_available_at": lambda v: _optional(v, x._read_utc),
        "acquired_at": lambda v: _optional(v, x._read_utc), "source_evidence_refs": lambda v: _sequence(v, ref)})


def _read_cn_a_share_cash_dividend_action_set_v1(raw):
    from . import execution_inputs as x
    return _record(raw, "cn_a_share_cash_dividend_action_set", e.CnAShareCashDividendActionSetV1, {
        "account_id": _raw, "coverage_start": x._read_utc, "coverage_end_exclusive": x._read_utc,
        "declaration_basis": _raw, "actions": lambda v: _sequence(v, _read_cn_a_share_cash_dividend_action_v1)})


def _native_fields():
    from . import execution_inputs as x
    from .cn_a_share_portfolio_settlement_development_v1 import read_cn_a_share_portfolio_settlement_book_source_v1
    return {"journal": x._read_economic_journal_v1, "ledger_schema": x._read_ledger_schema,
        "settlement_book": read_cn_a_share_portfolio_settlement_book_source_v1,
        "order_streams": lambda v: _sequence(v, x._read_order_event_stream),
        "reservation_schedules": lambda v: _sequence(v, x._read_reservation_schedule),
        "market_rules": x._read_settlement_rules, "instrument_catalog": x._read_instrument_catalog,
        "dividend_state": _read_cn_a_share_cash_dividend_state_v1, "as_of": x._read_simulation_instant}


def _read_cn_a_share_cash_dividend_history_inputs_v1(raw):
    from . import execution_inputs as x
    def identity(row):
        if type(row) not in (list, tuple) or len(row) != 2:
            raise ValueError("journal identity row must have two fields")
        return row[0], x._read_domain_id(row[1])
    return _record(raw, "cn_a_share_cash_dividend_history_inputs", e.CnAShareCashDividendHistoryInputsV1, {
        **_native_fields(), "action_set": _read_cn_a_share_cash_dividend_action_set_v1,
        "journal_entry_ids": lambda v: _sequence(v, identity)})


def _read_cn_a_share_cash_dividend_transition_inputs_v1(raw):
    from . import execution_inputs as x
    return _record(raw, "cn_a_share_cash_dividend_transition_inputs", e.CnAShareCashDividendTransitionInputsV1, {
        "history": _read_cn_a_share_cash_dividend_history_inputs_v1, "action_id": _raw,
        "instrument_id": x._read_instrument_id, "kind": _raw})


def _read_cn_a_share_cash_dividend_transition_v1(raw):
    from . import execution_inputs as x
    return _record(raw, "cn_a_share_cash_dividend_transition", e.CnAShareCashDividendTransitionV1, {
        "action_set_hash": _raw, "action_terms_hash": _raw, "tax_policy_hash": _raw, "kind": _raw,
        "event_id": _raw, "event_at": x._read_simulation_instant, "payload_hash": _raw,
        "input_journal_hash": _raw, "input_state_hash": _raw,
        "journal_entries": lambda v: _sequence(v, x._read_economic_journal_entry_v1), "output_journal_hash": _raw,
        "state_after": _read_cn_a_share_cash_dividend_state_v1})


def _read_cn_a_share_cash_dividend_transition_failure_v1(raw):
    return _record(raw, "cn_a_share_cash_dividend_transition_failure", e.CnAShareCashDividendTransitionFailureV1, {
        "code": e.CnAShareCashDividendTransitionFailureCodeV1, "subject_hashes": lambda v: _sequence(v, _raw)})


def _read_cn_a_share_cash_dividend_transition_outcome_v1(raw):
    return _record(raw, "cn_a_share_cash_dividend_transition_outcome", e.CnAShareCashDividendTransitionOutcomeV1, {
        "transition": lambda v: _optional(v, _read_cn_a_share_cash_dividend_transition_v1),
        "failure": lambda v: _optional(v, _read_cn_a_share_cash_dividend_transition_failure_v1)})


def _read_cn_a_share_economic_cash_row_v1(raw):
    from . import execution_inputs as x
    readers = {name: x._read_money for name in ("ledger_cash", "pending_cash", "reserved_principal",
        "reserved_fees", "native_available", "tax_liability", "tax_hold", "tax_shortfall", "spendable")}
    return _record(raw, "cn_a_share_economic_cash_row", e.CnAShareEconomicCashRowV1, {"key": x._read_cash_key, **readers})


def _read_cn_a_share_portfolio_economic_projection_v1(raw):
    from . import execution_inputs as x
    return _record(raw, "cn_a_share_portfolio_economic_projection", e.CnASharePortfolioEconomicProjectionV1, {
        "account_id": _raw, "as_of": x._read_simulation_instant, "native_source_hash": _raw,
        "dividend_state_hash": _raw, "base_snapshot": x._read_portfolio_snapshot, "snapshot": x._read_portfolio_snapshot,
        "gross_receivable": x._read_money, "tax_liability": x._read_money,
        "cash_rows": lambda v: _sequence(v, _read_cn_a_share_economic_cash_row_v1),
        "spendable": x._read_money, "tax_shortfall": x._read_money, "buy_budget": x._read_money})


def _read_currency_graph_v1(raw):
    from . import execution_inputs as x
    data = _fields(raw, "currency_valuation_graph", ("valuation_at", "price_purpose", "edges"), version=False)
    def edge(v):
        f = _fields(v, "currency_valuation_edge", ("edge_id", "source_currency_id", "target_currency_id", "resolved_mark"), version=False)
        return _same(t.CurrencyValuationEdge(x._read_currency(f["source_currency_id"]),
            _read_economic_resolved_mark_v1(f["resolved_mark"])), v)
    return _same(t.CurrencyValuationGraph(x._read_utc(data["valuation_at"]), d.PricePurpose(data["price_purpose"]),
                                        _sequence(data["edges"], edge)), raw)


def _read_cn_a_share_portfolio_economic_projection_inputs_v1(raw):
    from . import execution_inputs as x
    return _record(raw, "cn_a_share_portfolio_economic_projection_inputs", e.CnASharePortfolioEconomicProjectionInputsV1, {
        **_native_fields(), "marks": lambda v: _sequence(v, _read_economic_resolved_mark_v1),
        "currency_valuation_graph": _read_currency_graph_v1, "notional_quantization": x._read_quantization})


def _read_cn_a_share_economic_projection_failure_v1(raw):
    from . import execution_inputs as x
    def native(v):
        data = _fields(v, "snapshot_projection_failure", ("code", "ledger_state_hash", "subject_hashes"), version=False)
        return _same(t.SnapshotProjectionFailure(t.SnapshotProjectionFailureCode(data["code"]), data["ledger_state_hash"],
                                               _sequence(data["subject_hashes"], _raw)), v)
    return _record(raw, "cn_a_share_economic_projection_failure", e.CnAShareEconomicProjectionFailureV1, {
        "code": e.CnAShareEconomicProjectionFailureCodeV1, "subject_hashes": lambda v: _sequence(v, _raw),
        "native_snapshot_failure": lambda v: _optional(v, native)})


def _read_cn_a_share_economic_projection_outcome_v1(raw):
    return _record(raw, "cn_a_share_economic_projection_outcome", e.CnAShareEconomicProjectionOutcomeV1, {
        "projection": lambda v: _optional(v, _read_cn_a_share_portfolio_economic_projection_v1),
        "failure": lambda v: _optional(v, _read_cn_a_share_economic_projection_failure_v1)})
