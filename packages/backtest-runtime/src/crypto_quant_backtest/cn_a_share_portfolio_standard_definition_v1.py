"""Source-only DEVELOPMENT definition for the standard shared-CNY portfolio route.

No Order, allocation, quantity decision, risk approval, Fill, FeeAssessment or
resolved diagnostic Case belongs in this input. Historical/broker/OOS authority
is not granted by freezing these explicitly modeled facts.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from collections.abc import Mapping
from datetime import date

from crypto_quant_domain import (
    AccountingEntryType, ArtifactEnvelope, CashBalanceKey, InstrumentId, OrderSide, PricePurpose, QuantizationPolicy,
    SimulationInstant, UtcInstant, VenueId, canonical_bytes, canonical_sha256,
)
from crypto_quant_trading import (
    AccountingJournal, CostBasisPolicy, FeeReservationRuleSet, FinalFeeRuleSet, GenericLedger,
    FeeReservationRuleSource, FinalFeeRuleSource,
    OrderCapabilitySet, OrderRuleNotionalEvidence, OrderRuleTimeline,
    OrderTranslationMapping, ResolvedMark,
)
from crypto_quant_trading.profiles.cn_a_share import (
    CnAShareFrozenCalendar, CnAShareMarketFeeRuleResolution,
    CnAShareStampDutyRuleResolution, CnAShareCashFeeRuleQuery, CnAShareFeeTradeMechanism,
    CnAShareMarketFeeBand, CnAShareStampDutyBand, CnAShareFeeRuleSourceRef, CnAShareFeeReservationBuffer,
    CnAShareFrozenCalendarDay, CnAShareCalendarDayKind,
)
from crypto_quant_trading.profiles.cn_a_share.portfolio_rebalance_policy_v1 import (
    CnAShareRebalanceExecutionPolicyV1,
)
from .cn_a_share_portfolio_preparation_inputs_v1 import CnASharePortfolioPreparationInputsV1
from .cn_a_share_portfolio_daily_nav_diagnostic_v1 import CnAShareRetainedDividendGuardV1
from .execution import BarLiquidityEvidence
from .target_repository import BacktestTargetStreamRef
from .slippage import DeterministicBpsSlippageModel, SlippageMarketState


@dataclass(frozen=True, slots=True)
class CnASharePortfolioOpeningTermsDevelopmentV1:
    """Frozen per-Bar/side rule sources, not an approval or prospective trade."""
    bar_event_id: str
    bar_event_hash: str
    instrument_id: InstrumentId
    side: OrderSide
    capability_set: OrderCapabilitySet
    translation_mapping: OrderTranslationMapping
    rule_timeline: OrderRuleTimeline
    notional_evidence: OrderRuleNotionalEvidence
    reservation_rules: FeeReservationRuleSet
    final_fill_rules: FinalFeeRuleSet
    final_order_rules: FinalFeeRuleSet
    market_fee_resolution: CnAShareMarketFeeRuleResolution
    tax_resolution: CnAShareStampDutyRuleResolution
    liquidity: BarLiquidityEvidence
    market_state: SlippageMarketState
    slippage_model: DeterministicBpsSlippageModel
    maximum_fill_count: int = 2

    def __post_init__(self) -> None:
        for value, expected in (
            (self.instrument_id, InstrumentId), (self.side, OrderSide),
            (self.capability_set, OrderCapabilitySet), (self.translation_mapping, OrderTranslationMapping),
            (self.rule_timeline, OrderRuleTimeline), (self.notional_evidence, OrderRuleNotionalEvidence),
            (self.reservation_rules, FeeReservationRuleSet), (self.final_fill_rules, FinalFeeRuleSet),
            (self.final_order_rules, FinalFeeRuleSet),
            (self.market_fee_resolution, CnAShareMarketFeeRuleResolution),
            (self.tax_resolution, CnAShareStampDutyRuleResolution),
            (self.liquidity, BarLiquidityEvidence), (self.market_state, SlippageMarketState),
            (self.slippage_model, DeterministicBpsSlippageModel),
        ):
            if type(value) is not expected:
                raise TypeError("opening terms require exact native source types")
        if (type(self.bar_event_id) is not str or not self.bar_event_id
                or self.bar_event_id != self.bar_event_id.strip()
                or type(self.bar_event_hash) is not str or len(self.bar_event_hash) != 71
                or not self.bar_event_hash.startswith("sha256:")
                or any(c not in "0123456789abcdef" for c in self.bar_event_hash[7:])):
            raise ValueError("opening terms need canonical event identity")
        market, tax = self.market_fee_resolution, self.tax_resolution
        if (self.rule_timeline.instrument_id != self.instrument_id
                or market.instrument_id != self.instrument_id or tax.instrument_id != self.instrument_id
                or market.venue_id != self.instrument_id.venue or tax.venue_id != self.instrument_id.venue
                or market.side is not self.side or tax.side is not self.side
                or market.effective_at != tax.effective_at
                or self.notional_evidence.available_at is None
                or self.notional_evidence.available_at > market.effective_at
                or self.market_state.source_event_id != self.bar_event_id
                or self.liquidity.market_event_id != self.bar_event_id
                or self.liquidity.market_event_hash != self.bar_event_hash
                or self.liquidity.evaluated_at > market.effective_at
                or self.market_state.available_at > market.effective_at
                or self.market_state.observed_at > market.effective_at):
            raise ValueError("opening terms rule/fee/Bar context mismatch")
        for final in (self.final_fill_rules, self.final_order_rules):
            if (final.market_fee_policy_ref != self.reservation_rules.market_fee_policy_ref
                    or final.tax_policy_ref != self.reservation_rules.tax_policy_ref
                    or final.account_fee_schedule_ref != self.reservation_rules.account_fee_schedule_ref):
                raise ValueError("opening terms fee-source references mismatch")
        buffer = CnAShareFeeReservationBuffer.create(market_resolution=market,
            tax_resolution=tax, maximum_fill_count=self.maximum_fill_count)
        expected_reservation = {
            FeeReservationRuleSource.MARKET_FEE: (*market.reservation_charge_rules, buffer.market_charge_rule),
            FeeReservationRuleSource.TAX: (tax.reservation_charge_rule, buffer.tax_charge_rule)}
        for kind, expected in expected_reservation.items():
            actual = tuple(r for r in self.reservation_rules.charge_rules if r.source is kind)
            if sorted(map(canonical_bytes, actual)) != sorted(map(canonical_bytes, expected)):
                raise ValueError("reservation rules disagree with retained fee resolution/buffer")
        for final, expected_market, expected_tax in (
                (self.final_fill_rules, market.final_fill_charge_rules, (tax.final_fill_charge_rule,)),
                (self.final_order_rules, (market.final_order_not_applicable_rule,), (tax.final_order_not_applicable_rule,))):
            for kind, expected in ((FinalFeeRuleSource.MARKET_FEE, expected_market),
                                   (FinalFeeRuleSource.TAX, expected_tax)):
                actual = tuple(r for r in final.charge_rules if r.source is kind)
                if sorted(map(canonical_bytes, actual)) != sorted(map(canonical_bytes, expected)):
                    raise ValueError("final rules disagree with retained fee resolution")
            if any(m.source is not FinalFeeRuleSource.ACCOUNT_SCHEDULE for m in final.minimums):
                raise ValueError("unbound minimum disagrees with retained fee resolution")
        if any(m.source is not FeeReservationRuleSource.ACCOUNT_SCHEDULE for m in self.reservation_rules.minimums):
            raise ValueError("unbound reservation minimum disagrees with retained fee resolution")
        # Zero slippage is an explicit development model, never an auction guarantee.
        if self.slippage_model.basis_points_units != 0:
            raise ValueError("standard portfolio v1 supports the frozen zero-slippage model only")

    @property
    def opening_at(self) -> UtcInstant:
        return self.market_fee_resolution.effective_at

    def to_canonical_dict(self) -> dict[str, object]:
        values = {name: getattr(self, name) for name in self.__dataclass_fields__}
        model = self.slippage_model
        values["slippage_model"] = {
            "component_ref": model.component_ref, "calibration_ref": model.calibration_ref,
            "applicability_envelope": model.applicability_envelope,
            "basis_points_units": model.basis_points_units,
            "basis_points_scale": model.basis_points_scale.places,
            "rounding": model.rounding.value, "limitations": tuple(v.value for v in model.limitations)}
        return {"type": "cn_a_share_portfolio_opening_terms_development", "schema_version": 1, **values}


@dataclass(frozen=True, slots=True)
class CnASharePortfolioMarkBatchDevelopmentV1:
    at: SimulationInstant
    marks: tuple[ResolvedMark, ...]

    def __post_init__(self) -> None:
        if (type(self.at) is not SimulationInstant or type(self.marks) is not tuple
                or not self.marks or any(type(m) is not ResolvedMark for m in self.marks)):
            raise TypeError("mark batch requires exact native time and valuation marks")
        instruments = tuple(m.instrument_id for m in self.marks)
        if len(set(instruments)) != len(instruments) or instruments != tuple(sorted(instruments)):
            raise ValueError("mark batch needs sorted unique instrument source cover")
        if any(type(m.available_at_instant) is not SimulationInstant
               or type(m.resolved_at_instant) is not SimulationInstant for m in self.marks):
            raise ValueError("new source mark batches require both exact full-clock fields")
        if any(m.price_purpose is not PricePurpose.VALUATION or m.quote_currency_id.value != "CNY"
               or m.available_at > self.at.instant or m.resolved_at != self.at.instant
               or m.observed_at > self.at.instant
               or (m.available_at_instant is not None and m.available_at_instant > self.at)
               or (m.resolved_at_instant is not None and m.resolved_at_instant != self.at)
               for m in self.marks):
            raise ValueError("mark batch has future, nonvaluation or foreign-currency source")

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "cn_a_share_portfolio_mark_batch_development", "schema_version": 1,
                "at": self.at, "marks": self.marks}


@dataclass(frozen=True, slots=True)
class CnASharePortfolioStandardDevelopmentInputsV1:
    scope: CnASharePortfolioPreparationInputsV1
    initial_journal: AccountingJournal
    calendars: tuple[CnAShareFrozenCalendar, CnAShareFrozenCalendar]
    execution_policy: CnAShareRebalanceExecutionPolicyV1
    opening_terms: tuple[CnASharePortfolioOpeningTermsDevelopmentV1, ...]
    signal_marks: tuple[CnASharePortfolioMarkBatchDevelopmentV1, ...]
    daily_marks: tuple[CnASharePortfolioMarkBatchDevelopmentV1, ...]
    cost_basis_policy: CostBasisPolicy
    notional_quantization: QuantizationPolicy
    dividend_guards: tuple[CnAShareRetainedDividendGuardV1, ...]
    _retained_definition: ArtifactEnvelope = field(init=False, repr=False, compare=False)
    _definition_source_hash: str = field(init=False, repr=False, compare=False)
    source_qualification_verified: bool = field(default=False, init=False)
    broker_shared_pool_verified: bool = field(default=False, init=False)
    trade_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        for value, expected in ((self.scope, CnASharePortfolioPreparationInputsV1),
                (self.initial_journal, AccountingJournal),
                (self.execution_policy, CnAShareRebalanceExecutionPolicyV1),
                (self.cost_basis_policy, CostBasisPolicy),
                (self.notional_quantization, QuantizationPolicy)):
            if type(value) is not expected:
                raise TypeError("standard portfolio definition requires exact source values")
        if (type(self.calendars) is not tuple or len(self.calendars) != 2
                or any(type(c) is not CnAShareFrozenCalendar for c in self.calendars)
                or tuple(c.venue_id.value for c in self.calendars) != ("xshg", "xshe")):
            raise ValueError("standard portfolio requires ordered SH/SZ calendars")
        if (type(self.opening_terms) is not tuple or not self.opening_terms
                or any(type(t) is not CnASharePortfolioOpeningTermsDevelopmentV1 for t in self.opening_terms)):
            raise TypeError("standard portfolio requires frozen opening terms")
        keys = tuple((t.opening_at, t.instrument_id, t.side.value) for t in self.opening_terms)
        if len(set(keys)) != len(keys) or keys != tuple(sorted(keys)):
            raise ValueError("opening terms must have sorted unique time/instrument/side keys")
        scope = set(self.scope.instrument_ids)
        if {t.instrument_id for t in self.opening_terms} != scope:
            raise ValueError("opening term sources do not exactly cover the instrument scope")
        for batches, name in ((self.signal_marks, "signal"), (self.daily_marks, "daily")):
            if (type(batches) is not tuple or not batches
                    or any(type(b) is not CnASharePortfolioMarkBatchDevelopmentV1 for b in batches)
                    or tuple(b.at for b in batches) != tuple(sorted({b.at for b in batches}))
                    or any({m.instrument_id for m in b.marks} != scope for b in batches)):
                raise ValueError(name + " marks require sorted distinct instants and exact scope cover")
        first = self.signal_marks[0].at
        if any(e.recorded_at >= first or e.account_id != self.scope.account_id
                or e.entry_type not in (AccountingEntryType.CAPITAL_DEPOSITED, AccountingEntryType.CAPITAL_TRANSFERRED)
                or e.fees or e.realized_pnl or e.financing or e.position_lot_changes
                or any(type(change.key) is not CashBalanceKey for change in e.balance_changes)
                for e in self.initial_journal.entries):
            raise ValueError("initial paper journal must be capital-only, same-account and prior to signals")
        initial = GenericLedger(self.scope.ledger_schema).project(self.initial_journal)
        if (initial.position_balances or sum(b.amount.units for b in initial.cash_balances) != self.scope.initial_cash.units
                or any(b.amount.currency != "CNY" or b.amount.scale != self.scope.initial_cash.scale
                       for b in initial.cash_balances)):
            raise ValueError("initial paper journal does not bind declared CNY capital")
        codes = tuple(i.stable_key + (".SH" if i.venue.value == "xshg" else ".SZ")
                      for i in self.scope.instrument_ids)
        if (type(self.dividend_guards) is not tuple
                or any(type(g) is not CnAShareRetainedDividendGuardV1 for g in self.dividend_guards)
                or tuple(g.ts_code for g in self.dividend_guards) != codes):
            raise ValueError("retained dividend guards must exactly cover the frozen scope")
        for guard in self.dividend_guards:
            guard.rows()  # Empty raw rows retain absence_verified=False; no caller assertion.
        definition = ArtifactEnvelope.create("backtest_profile_portfolio_definition", 1, self.economic_payload())
        object.__setattr__(self, "_retained_definition", definition)
        object.__setattr__(self, "_definition_source_hash", canonical_sha256(definition))
        canonical_bytes(self)

    def economic_payload(self) -> dict[str, object]:
        scope = dict(self.scope.to_canonical_dict())
        scope.pop("target_stream_ref")
        return {"type": "cn_a_share_portfolio_standard_development_definition", "schema_version": 1,
            "scope": scope, "initial_journal": self.initial_journal, "calendars": self.calendars,
            "execution_policy": self.execution_policy, "opening_terms": self.opening_terms,
            "signal_marks": self.signal_marks, "daily_marks": self.daily_marks,
            "cost_basis_policy": self.cost_basis_policy,
            "notional_quantization": self.notional_quantization,
            "dividend_guards": self.dividend_guards,
            "source_qualification_verified": False, "broker_shared_pool_verified": False,
            "trade_authorized": False}

    def definition(self) -> ArtifactEnvelope:
        return self._retained_definition

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self.economic_payload(), "target_stream_ref": self.scope.target_stream_ref}


def _map(value: object, tag: str) -> Mapping:
    if not isinstance(value, Mapping) or value.get("type") != tag:
        raise ValueError("standard portfolio source tag mismatch: " + tag)
    return value


def _read_standard_definition_v1(
    definition: ArtifactEnvelope, target_ref: BacktestTargetStreamRef,
) -> CnASharePortfolioStandardDevelopmentInputsV1:
    # Reuse the sole transport's concrete native value readers. This is a
    # profile source DTO reader, not a second execution-input schema catalog.
    from .execution_inputs import (
        _read_utc, _read_rate, _read_simulation_instant, _read_resolved_mark,
        _read_capability_set, _read_translation_mapping, _read_order_rule_timeline,
        _read_notional_evidence, _read_fee_reservation_rules, _read_final_fee_rules,
        _read_fee_reservation_charge, _read_final_fee_charge, _read_liquidity_evidence,
        _read_slippage_model, _read_journal, _read_cost_basis, _read_quantization,
    )
    from .cn_a_share_portfolio_case_inputs_v8 import _scope
    if (type(definition) is not ArtifactEnvelope
            or definition.artifact_type != "backtest_profile_portfolio_definition"
            or definition.schema_version != 1 or type(target_ref) is not BacktestTargetStreamRef):
        raise TypeError("standard portfolio requires exact definition and target source reference")
    p = _map(definition.payload, "cn_a_share_portfolio_standard_development_definition")
    fields = {"type", "schema_version", "scope", "initial_journal", "calendars",
        "execution_policy", "opening_terms", "signal_marks", "daily_marks", "cost_basis_policy",
        "notional_quantization", "dividend_guards", "source_qualification_verified",
        "broker_shared_pool_verified", "trade_authorized"}
    if (set(p) != fields or type(p["schema_version"]) is not int or p["schema_version"] != 1
            or any(p[k] is not False for k in ("source_qualification_verified", "broker_shared_pool_verified", "trade_authorized"))):
        raise ValueError("standard portfolio definition exact fields/qualification mismatch")
    scope_raw = dict(_map(p["scope"], "cn_a_share_portfolio_preparation_inputs"))
    if "target_stream_ref" in scope_raw:
        raise ValueError("target transport reference cannot be part of the economic definition")
    scope_raw["target_stream_ref"] = {"type": "backtest_target_stream_ref",
        "artifact_ref": target_ref.artifact_ref.to_canonical_dict()}
    scope = _scope(scope_raw)

    def sources(raw):
        result = []
        for value in raw:
            s = _map(value, "cn_a_share_fee_rule_source_ref")
            result.append(CnAShareFeeRuleSourceRef(s["source_key"], s["source_hash"]))
        return tuple(result)

    def query(raw):
        q = _map(raw, "cn_a_share_cash_fee_rule_query")
        i = _map(q["instrument"], "instrument_definition")
        ident = i["instrument_id"]
        match = next((v for v in scope.instrument_ids if v.stable_key == ident["stable_key"]
                      and v.venue.value == ident["venue"]), None)
        if match is None:
            raise ValueError("fee source query is outside the instrument scope")
        instrument = scope.instrument_catalog.instrument(match)
        if canonical_bytes(instrument) != canonical_bytes(q["instrument"]):
            raise ValueError("fee source query instrument definition mismatch")
        return CnAShareCashFeeRuleQuery(instrument, OrderSide(q["side"]),
            _read_utc(q["effective_at"]), CnAShareFeeTradeMechanism(q["trade_mechanism"]))

    def market_resolution(raw):
        r = _map(raw, "cn_a_share_market_fee_rule_resolution")
        q = query(r["query"])
        b = _map(r["active_band"], "cn_a_share_market_fee_band")
        band = CnAShareMarketFeeBand(VenueId(b["venue_id"]["value"]),
            _read_utc(b["effective_from"]), _read_utc(b["effective_to_exclusive"]),
            _read_rate(b["handling_rate"]), sources(b["handling_source_refs"]),
            _read_rate(b["regulatory_rate"]), sources(b["regulatory_source_refs"]),
            _read_rate(b["transfer_rate"]), sources(b["transfer_source_refs"]))
        return CnAShareMarketFeeRuleResolution(q.instrument.instrument_id.venue,
            q.instrument.instrument_id, q.side, q.effective_at, q, r["query_hash"], band, r["active_band_hash"],
            tuple(_read_fee_reservation_charge(v) for v in r["reservation_charge_rules"]),
            tuple(_read_final_fee_charge(v) for v in r["final_fill_charge_rules"]),
            _read_final_fee_charge(r["final_order_not_applicable_rule"]))

    def tax_resolution(raw):
        r = _map(raw, "cn_a_share_stamp_duty_rule_resolution")
        q = query(r["query"])
        b = _map(r["active_band"], "cn_a_share_stamp_duty_band")
        band = CnAShareStampDutyBand(VenueId(b["venue_id"]["value"]),
            _read_utc(b["effective_from"]), _read_utc(b["effective_to_exclusive"]),
            _read_rate(b["rate"]), sources(b["source_refs"]))
        return CnAShareStampDutyRuleResolution(q.instrument.instrument_id.venue,
            q.instrument.instrument_id, q.side, q.effective_at, q, r["query_hash"], band, r["active_band_hash"],
            _read_fee_reservation_charge(r["reservation_charge_rule"]),
            _read_final_fee_charge(r["final_fill_charge_rule"]),
            _read_final_fee_charge(r["final_order_not_applicable_rule"]))

    terms = []
    for raw in p["opening_terms"]:
        t = _map(raw, "cn_a_share_portfolio_opening_terms_development")
        market, tax = market_resolution(t["market_fee_resolution"]), tax_resolution(t["tax_resolution"])
        s = _map(t["market_state"], "slippage_market_state")
        state = SlippageMarketState(s["state_key"], _read_utc(s["observed_at"]), _read_utc(s["available_at"]),
            s["source_event_id"], s["revision_id"], s["evidence_hash"])
        terms.append(CnASharePortfolioOpeningTermsDevelopmentV1(
            t["bar_event_id"], t["bar_event_hash"], market.instrument_id, OrderSide(t["side"]),
            _read_capability_set(t["capability_set"]), _read_translation_mapping(t["translation_mapping"]),
            _read_order_rule_timeline(t["rule_timeline"]), _read_notional_evidence(t["notional_evidence"]),
            _read_fee_reservation_rules(t["reservation_rules"]), _read_final_fee_rules(t["final_fill_rules"]),
            _read_final_fee_rules(t["final_order_rules"]), market, tax, _read_liquidity_evidence(t["liquidity"]),
            state, _read_slippage_model(t["slippage_model"]), t["maximum_fill_count"]))
    calendars = []
    for raw in p["calendars"]:
        c = _map(raw, "cn_a_share_frozen_calendar")
        days = tuple(CnAShareFrozenCalendarDay(date.fromisoformat(d["local_date"]), CnAShareCalendarDayKind(d["kind"]))
                     for d in c["days"])
        calendars.append(CnAShareFrozenCalendar(VenueId(c["venue_id"]["value"]), c["calendar_id"],
            date.fromisoformat(c["coverage_start"]), date.fromisoformat(c["coverage_end_exclusive"]), days,
            c["timezone_name"]))

    def mark_batches(raw):
        result = []
        for value in raw:
            b = _map(value, "cn_a_share_portfolio_mark_batch_development")
            marks = []
            for raw_mark in b["marks"]:
                mark = _read_resolved_mark(raw_mark)
                # Preserve the newer full-clock fields without changing the old reader.
                updates = {name: _read_simulation_instant(raw_mark[name]) for name in
                    ("available_at_instant", "resolved_at_instant") if raw_mark.get(name) is not None}
                marks.append(replace(mark, **updates))
            result.append(CnASharePortfolioMarkBatchDevelopmentV1(_read_simulation_instant(b["at"]), tuple(marks)))
        return tuple(result)

    guards = []
    for raw in p["dividend_guards"]:
        g = _map(raw, "cn_a_share_retained_dividend_guard")
        guards.append(CnAShareRetainedDividendGuardV1(bytes.fromhex(g["response_hex"]),
            g["response_sha256"], g["ts_code"]))
    policy = CnAShareRebalanceExecutionPolicyV1.create(p["execution_policy"]["policy_key"])
    if len(calendars) != 2:
        raise ValueError("standard portfolio source calendar count mismatch")
    result = CnASharePortfolioStandardDevelopmentInputsV1(scope, _read_journal(p["initial_journal"]),
        (calendars[0], calendars[1]), policy, tuple(terms), mark_batches(p["signal_marks"]),
        mark_batches(p["daily_marks"]), _read_cost_basis(p["cost_basis_policy"]),
        _read_quantization(p["notional_quantization"]), tuple(guards))
    if canonical_bytes(result.economic_payload()) != canonical_bytes(p):
        raise ValueError("standard portfolio source definition did not reconstruct exactly")
    return result
