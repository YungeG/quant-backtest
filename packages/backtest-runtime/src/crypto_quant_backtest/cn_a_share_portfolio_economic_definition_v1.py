"""Exact source-only DEVELOPMENT economic DTOs and definition @2/@4 codec."""
from __future__ import annotations

from dataclasses import InitVar, dataclass, field, replace
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
from crypto_quant_trading.profiles.cn_a_share.portfolio_v1 import (
    CnAShareRebalanceExecutionPolicyV1,
)
from .cn_a_share_portfolio_preparation_inputs_v1 import CnASharePortfolioPreparationInputsV1
from .execution import BarLiquidityEvidence
from .target_repository import BacktestTargetStreamRef
from .slippage import DeterministicBpsSlippageModel, SlippageMarketState


from crypto_quant_trading.profiles.cn_a_share.portfolio_economic_v1 import CnAShareCashDividendActionSetV1
from .cn_a_share_portfolio_standard_definition_v1 import CnASharePortfolioMarkBatchDevelopmentV1
from .cn_a_share_portfolio_economic_values_v1 import _read_economic_resolved_mark_v1

@dataclass(frozen=True, slots=True)
class CnASharePortfolioEconomicOpeningTermsV1:
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
    maximum_fill_count: int

    def __post_init__(self) -> None:
        if type(self.maximum_fill_count) is not int:
            raise TypeError("maximum_fill_count must be exact int")
        if self.maximum_fill_count != 1:
            raise ValueError("economic opening permits exactly one full Fill")
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
        if self.slippage_model.basis_points_units < 0:
            raise ValueError("economic opening requires nonnegative deterministic BPS")

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
        return {"type": "cn_a_share_portfolio_economic_opening_terms", "schema_version": 1, **values}


@dataclass(frozen=True, slots=True)
class CnASharePortfolioEconomicDevelopmentInputsV1:
    scope: CnASharePortfolioPreparationInputsV1
    initial_journal: AccountingJournal
    calendars: tuple[CnAShareFrozenCalendar, CnAShareFrozenCalendar]
    execution_policy: CnAShareRebalanceExecutionPolicyV1
    opening_terms: tuple[CnASharePortfolioEconomicOpeningTermsV1, ...]
    initial_marks: CnASharePortfolioMarkBatchDevelopmentV1
    signal_marks: tuple[CnASharePortfolioMarkBatchDevelopmentV1, ...]
    daily_marks: tuple[CnASharePortfolioMarkBatchDevelopmentV1, ...]
    checkpoint_marks: tuple[CnASharePortfolioMarkBatchDevelopmentV1, ...]
    cost_basis_policy: CostBasisPolicy
    notional_quantization: QuantizationPolicy
    dividend_actions: CnAShareCashDividendActionSetV1
    _source_index: InitVar[Mapping | None] = None
    _retained_definition: ArtifactEnvelope = field(init=False, repr=False, compare=False)
    _definition_source_hash: str = field(init=False, repr=False, compare=False)
    source_qualification_verified: bool = field(default=False, init=False)
    broker_shared_pool_verified: bool = field(default=False, init=False)
    trade_authorized: bool = field(default=False, init=False)

    def __post_init__(self, _source_index) -> None:
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
                or any(type(t) is not CnASharePortfolioEconomicOpeningTermsV1 for t in self.opening_terms)):
            raise TypeError("standard portfolio requires frozen opening terms")
        keys = tuple((t.opening_at, t.instrument_id, t.side.value) for t in self.opening_terms)
        if len(set(keys)) != len(keys) or keys != tuple(sorted(keys)):
            raise ValueError("opening terms must have sorted unique time/instrument/side keys")
        scope = set(self.scope.instrument_ids)
        if {t.instrument_id for t in self.opening_terms} != scope:
            raise ValueError("opening term sources do not exactly cover the instrument scope")
        for batches, name in ((self.signal_marks, "signal"), (self.daily_marks, "daily"), (self.checkpoint_marks, "checkpoint")):
            if (type(batches) is not tuple or not batches
                    or any(type(b) is not CnASharePortfolioMarkBatchDevelopmentV1 for b in batches)
                    or tuple(b.at for b in batches) != tuple(sorted({b.at for b in batches}))
                    or any({m.instrument_id for m in b.marks} != scope for b in batches)):
                raise ValueError(name + " marks require sorted distinct instants and exact scope cover")
        if type(self.initial_marks) is not CnASharePortfolioMarkBatchDevelopmentV1:
            raise TypeError("economic initialization requires exact mark batch")
        first = self.initial_marks.at
        if any(e.recorded_at >= first or e.account_id != self.scope.account_id
                or e.entry_type not in (AccountingEntryType.CAPITAL_DEPOSITED, AccountingEntryType.CAPITAL_TRANSFERRED)
                or e.fees or e.realized_pnl or e.financing or e.position_lot_changes
                or any(type(change.key) is not CashBalanceKey for change in e.balance_changes)
                for e in self.initial_journal.entries):
            raise ValueError("initial paper journal must be capital-only, same-account and prior to initialization")
        initial = GenericLedger(self.scope.ledger_schema).project(self.initial_journal)
        if (initial.position_balances or sum(b.amount.units for b in initial.cash_balances) != self.scope.initial_cash.units
                or any(b.amount.units < 0 or b.amount.currency != "CNY" or b.amount.scale != self.scope.initial_cash.scale
                       for b in initial.cash_balances)):
            raise ValueError("initial paper journal does not bind declared CNY capital")
        if self.notional_quantization.target_scale.places != 2:
            raise ValueError("economic notional quantization must target CNY cents")
        clock = self.initial_marks.at
        if (clock.phase.rank != 0 or clock.phase.code != "cn_economic_initial" or clock.source_sequence.value != 0
                or {m.instrument_id for m in self.initial_marks.marks} != scope
                or any(b.at <= clock for b in self.signal_marks)):
            raise ValueError("economic initialization clock/scope/ordering mismatch")
        if len(self.checkpoint_marks) > 65536:
            raise ValueError("economic checkpoints exceed 65536")
        if type(self.dividend_actions) is not CnAShareCashDividendActionSetV1:
            raise TypeError("economic input requires exact ActionSet")
        if (self.dividend_actions.account_id != self.scope.account_id
                or self.dividend_actions.coverage_start != clock.instant
                or any(a.instrument_id not in scope or a.registered_at <= clock for a in self.dividend_actions.actions)):
            raise ValueError("economic ActionSet scope/start/registration mismatch")
        payload = self.economic_payload()
        version = 2
        if _source_index is not None:
            from .cn_a_share_portfolio_economic_source_chunks import _ROLES
            for role in _ROLES:
                del payload[role]
            payload["schema_version"] = 3
            payload["source_index"] = _source_index
            version = 4
        definition = ArtifactEnvelope.create("backtest_profile_portfolio_definition", version, payload)
        object.__setattr__(self, "_retained_definition", definition)
        object.__setattr__(self, "_definition_source_hash", canonical_sha256(definition))
        if _source_index is None:
            canonical_bytes(self)

    @classmethod
    def from_chunked_sources(cls, *, artifact_reader, artifact_publisher, **sources):
        """Retain bounded native source chunks; prepare with the bounded signal profile."""
        from .cn_a_share_portfolio_economic_source_chunks import _ROLES, _publish_economic_source_chunks
        scope_value = dict(sources["scope"].to_canonical_dict())
        scope_value.pop("target_stream_ref")
        index = _publish_economic_source_chunks(publisher=artifact_publisher, reader=artifact_reader,
            scope=scope_value, sections={role: sources[role] for role in _ROLES})
        return cls(**sources, _source_index=index)

    def with_target_stream_ref(self, target_stream_ref: BacktestTargetStreamRef) -> CnASharePortfolioEconomicDevelopmentInputsV1:
        """Bind the published target transport without changing immutable economic sources."""
        if type(target_stream_ref) is not BacktestTargetStreamRef:
            raise TypeError("economic target binding requires exact BacktestTargetStreamRef")
        return replace(self, scope=replace(self.scope, target_stream_ref=target_stream_ref),
            _source_index=self.definition().payload.get("source_index"))

    def economic_payload(self) -> dict[str, object]:
        scope = dict(self.scope.to_canonical_dict())
        scope.pop("target_stream_ref")
        return {"type": "cn_a_share_portfolio_economic_development_definition", "schema_version": 1,
            "scope": scope, "initial_journal": self.initial_journal, "calendars": self.calendars,
            "execution_policy": self.execution_policy, "opening_terms": self.opening_terms,
            "initial_marks": self.initial_marks, "signal_marks": self.signal_marks,
            "daily_marks": self.daily_marks, "checkpoint_marks": self.checkpoint_marks,
            "cost_basis_policy": self.cost_basis_policy, "notional_quantization": self.notional_quantization,
            "cash_dividend_action_set_hash": canonical_sha256(self.dividend_actions),
            "source_qualification_verified": False, "broker_shared_pool_verified": False, "trade_authorized": False}

    def definition(self) -> ArtifactEnvelope:
        return self._retained_definition

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "cn_a_share_portfolio_economic_development_inputs", "schema_version": 1,
            **{name: getattr(self, name) for name in ("scope", "initial_journal", "calendars", "execution_policy",
                "opening_terms", "initial_marks", "signal_marks", "daily_marks", "checkpoint_marks",
                "cost_basis_policy", "notional_quantization", "dividend_actions")},
            "source_qualification_verified": False, "broker_shared_pool_verified": False, "trade_authorized": False}


def _map(value: object, tag: str) -> Mapping:
    if not isinstance(value, Mapping) or value.get("type") != tag:
        raise ValueError("standard portfolio source tag mismatch: " + tag)
    return value


def _read_economic_definition_v1(
    definition: ArtifactEnvelope, target_ref: BacktestTargetStreamRef, action_set: CnAShareCashDividendActionSetV1,
    *, source_reader=None,
) -> CnASharePortfolioEconomicDevelopmentInputsV1:
    if (type(definition) is not ArtifactEnvelope
            or definition.artifact_type != "backtest_profile_portfolio_definition"
            or definition.schema_version not in (2, 4) or type(action_set) is not CnAShareCashDividendActionSetV1 or type(target_ref) is not BacktestTargetStreamRef):
        raise TypeError("standard portfolio requires exact definition and target source reference")
    p = _map(definition.payload, "cn_a_share_portfolio_economic_development_definition")
    fields = {"type", "schema_version", "scope", "initial_journal", "calendars", "execution_policy",
        "opening_terms", "initial_marks", "signal_marks", "daily_marks", "checkpoint_marks", "cost_basis_policy",
        "notional_quantization", "cash_dividend_action_set_hash", "source_qualification_verified",
        "broker_shared_pool_verified", "trade_authorized"}
    expected_version = 1
    if definition.schema_version == 4:
        from .cn_a_share_portfolio_economic_source_chunks import _ROLES
        fields = (fields - set(_ROLES)) | {"source_index"}
        expected_version = 3
    if (set(p) != fields or type(p["schema_version"]) is not int or p["schema_version"] != expected_version
            or any(p[k] is not False for k in ("source_qualification_verified", "broker_shared_pool_verified", "trade_authorized"))):
        raise ValueError("standard portfolio definition exact fields/qualification mismatch")
    if p["cash_dividend_action_set_hash"] != canonical_sha256(action_set):
        raise ValueError("economic definition ActionSet value hash mismatch")
    index = None
    decode = p
    if definition.schema_version == 4:
        from .cn_a_share_portfolio_economic_source_chunks import _open_economic_source_chunks
        if source_reader is None:
            raise ValueError("chunked economic sources require the original artifact reader")
        index = p["source_index"]
        decode = {**p, **_open_economic_source_chunks(reader=source_reader, scope=p["scope"], index=index)}
    values = _read_economic_source_fields_v1(decode, target_ref, signal_field="signal_marks", exact_rows=index is not None)
    result = CnASharePortfolioEconomicDevelopmentInputsV1(**values, dividend_actions=action_set, _source_index=index)
    if (result.definition() != definition if index is not None
            else canonical_bytes(result.economic_payload()) != canonical_bytes(p)):
        raise ValueError("standard portfolio source definition did not reconstruct exactly")
    return result


def _read_economic_mark_batches_v1(raw, *, exact=False) -> tuple[CnASharePortfolioMarkBatchDevelopmentV1, ...]:
    from .execution_inputs import _read_simulation_instant
    result = []
    for value in raw:
        b = _map(value, "cn_a_share_portfolio_mark_batch_development")
        marks = tuple(_read_economic_resolved_mark_v1(v) for v in b["marks"])
        batch = CnASharePortfolioMarkBatchDevelopmentV1(_read_simulation_instant(b["at"]), marks)
        if exact and canonical_bytes(batch) != canonical_bytes(value):
            raise ValueError("economic chunk mark batch did not reconstruct exactly")
        result.append(batch)
    return tuple(result)


def _read_economic_source_fields_v1(p, target_ref, *, signal_field: str, exact_rows: bool = False) -> dict[str, object]:
    # Pure common parsing in V1's original failure order; no DTO/version decisions.
    from .execution_inputs import (
        _read_utc, _read_rate, _read_capability_set, _read_translation_mapping, _read_order_rule_timeline,
        _read_notional_evidence, _read_fee_reservation_rules, _read_final_fee_rules,
        _read_fee_reservation_charge, _read_final_fee_charge, _read_liquidity_evidence,
        _read_slippage_model, _read_journal, _read_cost_basis, _read_quantization,
    )
    from .cn_a_share_portfolio_case_inputs_v8 import _scope
    if signal_field not in ("signal_marks", "retained_signal_marks"):
        raise ValueError("unknown economic source signal field")
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
        t = _map(raw, "cn_a_share_portfolio_economic_opening_terms")
        market, tax = market_resolution(t["market_fee_resolution"]), tax_resolution(t["tax_resolution"])
        s = _map(t["market_state"], "slippage_market_state")
        state = SlippageMarketState(s["state_key"], _read_utc(s["observed_at"]), _read_utc(s["available_at"]),
            s["source_event_id"], s["revision_id"], s["evidence_hash"])
        term = CnASharePortfolioEconomicOpeningTermsV1(
            t["bar_event_id"], t["bar_event_hash"], market.instrument_id, OrderSide(t["side"]),
            _read_capability_set(t["capability_set"]), _read_translation_mapping(t["translation_mapping"]),
            _read_order_rule_timeline(t["rule_timeline"]), _read_notional_evidence(t["notional_evidence"]),
            _read_fee_reservation_rules(t["reservation_rules"]), _read_final_fee_rules(t["final_fill_rules"]),
            _read_final_fee_rules(t["final_order_rules"]), market, tax, _read_liquidity_evidence(t["liquidity"]),
            state, _read_slippage_model(t["slippage_model"]), t["maximum_fill_count"])
        if exact_rows and canonical_bytes(term) != canonical_bytes(raw):
            raise ValueError("economic chunk opening term did not reconstruct exactly")
        terms.append(term)
    calendars = []
    for raw in p["calendars"]:
        c = _map(raw, "cn_a_share_frozen_calendar")
        days = tuple(CnAShareFrozenCalendarDay(date.fromisoformat(d["local_date"]), CnAShareCalendarDayKind(d["kind"]))
                     for d in c["days"])
        calendars.append(CnAShareFrozenCalendar(VenueId(c["venue_id"]["value"]), c["calendar_id"],
            date.fromisoformat(c["coverage_start"]), date.fromisoformat(c["coverage_end_exclusive"]), days,
            c["timezone_name"]))

    policy = CnAShareRebalanceExecutionPolicyV1.create(p["execution_policy"]["policy_key"])
    if len(calendars) != 2:
        raise ValueError("standard portfolio source calendar count mismatch")
    return {"scope": scope, "initial_journal": _read_journal(p["initial_journal"]),
        "calendars": (calendars[0], calendars[1]), "execution_policy": policy, "opening_terms": tuple(terms),
        "initial_marks": _read_economic_mark_batches_v1((p["initial_marks"],))[0],
        signal_field: _read_economic_mark_batches_v1(p[signal_field], exact=exact_rows),
        "daily_marks": _read_economic_mark_batches_v1(p["daily_marks"], exact=exact_rows),
        "checkpoint_marks": _read_economic_mark_batches_v1(p["checkpoint_marks"], exact=exact_rows),
        "cost_basis_policy": _read_cost_basis(p["cost_basis_policy"]),
        "notional_quantization": _read_quantization(p["notional_quantization"])}
