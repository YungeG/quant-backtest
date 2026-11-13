"""Exact source-only single-prestart DEVELOPMENT inputs and definition@3 codec."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

from crypto_quant_domain import (
    AccountingEntryType, ArtifactEnvelope, CashBalanceKey, PricePurpose, QuantizationPolicy,
    canonical_bytes, canonical_sha256,
)
from crypto_quant_market_data import MarketEvent
from crypto_quant_trading import AccountingJournal, CostBasisPolicy, GenericLedger, StaleMarkPolicy
from crypto_quant_trading.profiles.cn_a_share import CnAShareFrozenCalendar
from crypto_quant_trading.profiles.cn_a_share.portfolio_economic_v1 import CnAShareCashDividendActionSetV1
from crypto_quant_trading.profiles.cn_a_share.portfolio_v1 import CnAShareRebalanceExecutionPolicyV1

from .cn_a_share_portfolio_economic_definition_v1 import (
    CnASharePortfolioEconomicOpeningTermsV1, _read_economic_source_fields_v1,
)
from .cn_a_share_portfolio_preparation_inputs_v1 import CnASharePortfolioPreparationInputsV1
from .cn_a_share_portfolio_standard_definition_v1 import CnASharePortfolioMarkBatchDevelopmentV1
from .target_repository import BacktestTargetStreamRef
from .target_stream import PrecomputedTargetStream


@dataclass(frozen=True, slots=True)
class CnASharePortfolioEconomicDevelopmentInputsV2:
    scope: CnASharePortfolioPreparationInputsV1
    source_target_stream: PrecomputedTargetStream
    initial_journal: AccountingJournal
    calendars: tuple[CnAShareFrozenCalendar, CnAShareFrozenCalendar]
    execution_policy: CnAShareRebalanceExecutionPolicyV1
    opening_terms: tuple[CnASharePortfolioEconomicOpeningTermsV1, ...]
    initial_marks: CnASharePortfolioMarkBatchDevelopmentV1
    retained_signal_marks: tuple[CnASharePortfolioMarkBatchDevelopmentV1, ...]
    daily_marks: tuple[CnASharePortfolioMarkBatchDevelopmentV1, ...]
    checkpoint_marks: tuple[CnASharePortfolioMarkBatchDevelopmentV1, ...]
    cost_basis_policy: CostBasisPolicy
    notional_quantization: QuantizationPolicy
    dividend_actions: CnAShareCashDividendActionSetV1
    activation_stale_policy: StaleMarkPolicy
    _retained_definition: ArtifactEnvelope = field(init=False, repr=False, compare=False)
    _definition_source_hash: str = field(init=False, repr=False, compare=False)
    source_qualification_verified: bool = field(default=False, init=False)
    broker_shared_pool_verified: bool = field(default=False, init=False)
    trade_authorized: bool = field(default=False, init=False)

    @classmethod
    def from_sources(cls, *, scope: CnASharePortfolioPreparationInputsV1,
        source_target_stream: PrecomputedTargetStream, initial_journal: AccountingJournal,
        calendars: tuple[CnAShareFrozenCalendar, CnAShareFrozenCalendar],
        execution_policy: CnAShareRebalanceExecutionPolicyV1,
        opening_terms: tuple[CnASharePortfolioEconomicOpeningTermsV1, ...],
        initial_marks: CnASharePortfolioMarkBatchDevelopmentV1,
        retained_signal_marks: tuple[CnASharePortfolioMarkBatchDevelopmentV1, ...],
        daily_marks: tuple[CnASharePortfolioMarkBatchDevelopmentV1, ...],
        checkpoint_marks: tuple[CnASharePortfolioMarkBatchDevelopmentV1, ...],
        cost_basis_policy: CostBasisPolicy, notional_quantization: QuantizationPolicy,
        dividend_actions: CnAShareCashDividendActionSetV1,
        activation_stale_policy: StaleMarkPolicy,
    ) -> CnASharePortfolioEconomicDevelopmentInputsV2:
        if cls is not CnASharePortfolioEconomicDevelopmentInputsV2:
            raise TypeError("economic V2 requires the exact public class")
        return cls(scope, source_target_stream, initial_journal, calendars, execution_policy,
            opening_terms, initial_marks, retained_signal_marks, daily_marks, checkpoint_marks,
            cost_basis_policy, notional_quantization, dividend_actions, activation_stale_policy)

    def __post_init__(self) -> None:
        if type(self) is not CnASharePortfolioEconomicDevelopmentInputsV2:
            raise TypeError("economic V2 requires the exact public class")
        for value, expected in ((self.scope, CnASharePortfolioPreparationInputsV1),
                (self.source_target_stream, PrecomputedTargetStream), (self.initial_journal, AccountingJournal),
                (self.execution_policy, CnAShareRebalanceExecutionPolicyV1),
                (self.initial_marks, CnASharePortfolioMarkBatchDevelopmentV1),
                (self.cost_basis_policy, CostBasisPolicy), (self.notional_quantization, QuantizationPolicy)):
            if type(value) is not expected:
                raise TypeError("economic V2 requires exact native source values")
        if (type(self.calendars) is not tuple or len(self.calendars) != 2
                or any(type(c) is not CnAShareFrozenCalendar for c in self.calendars)
                or tuple(c.venue_id.value for c in self.calendars) != ("xshg", "xshe")):
            raise ValueError("economic V2 requires ordered SH/SZ calendars")
        if (type(self.opening_terms) is not tuple or not self.opening_terms
                or any(type(t) is not CnASharePortfolioEconomicOpeningTermsV1 for t in self.opening_terms)):
            raise TypeError("economic V2 requires frozen opening terms")
        keys = tuple((t.opening_at, t.instrument_id, t.side.value) for t in self.opening_terms)
        scope = set(self.scope.instrument_ids)
        if (keys != tuple(sorted(set(keys)))
                or {t.instrument_id for t in self.opening_terms} != scope):
            raise ValueError("economic V2 opening keys/scope mismatch")
        for batches, name in ((self.daily_marks, "daily"), (self.checkpoint_marks, "checkpoint")):
            if (type(batches) is not tuple or not batches
                    or any(type(b) is not CnASharePortfolioMarkBatchDevelopmentV1 for b in batches)
                    or tuple(b.at for b in batches) != tuple(sorted({b.at for b in batches}))
                    or any({m.instrument_id for m in b.marks} != scope for b in batches)):
                raise ValueError(name + " marks require sorted distinct instants and exact scope cover")
        clock = self.initial_marks.at
        if any(e.recorded_at >= clock or e.account_id != self.scope.account_id
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
        if (clock.phase.rank != 0 or clock.phase.code != "cn_economic_initial" or clock.source_sequence.value != 0
                or {m.instrument_id for m in self.initial_marks.marks} != scope):
            raise ValueError("economic V2 initialization clock/scope mismatch")
        if len(self.checkpoint_marks) > 65536:
            raise ValueError("economic checkpoints exceed 65536")
        if (len(self.source_target_stream.events) != 1
                or type(self.source_target_stream.events[0]) is not MarketEvent):
            raise ValueError("economic V2 requires exactly one original source event")
        event = self.source_target_stream.events[0]
        local = event.event_time.to_datetime().astimezone(ZoneInfo("Asia/Shanghai"))
        if (event.event_time != event.available_time or event.event_time >= clock.instant
                or (local.hour, local.minute, local.second, local.microsecond) != (15, 0, 0, 0)
                or event.event_time.epoch_nanoseconds % 1_000_000_000 or event.phase.rank >= 30):
            raise ValueError("economic V2 source must be an original prestart 15:00 full clock")
        from crypto_quant_domain import SimulationInstant
        source_at = SimulationInstant(event.event_time, event.phase, event.source_sequence)
        if (type(self.retained_signal_marks) is not tuple or len(self.retained_signal_marks) != 1
                or type(self.retained_signal_marks[0]) is not CnASharePortfolioMarkBatchDevelopmentV1
                or self.retained_signal_marks[0].at != source_at
                or {m.instrument_id for m in self.retained_signal_marks[0].marks} != scope):
            raise ValueError("economic V2 requires one unchanged source-clock mark batch with exact scope cover")
        if type(self.dividend_actions) is not CnAShareCashDividendActionSetV1:
            raise TypeError("economic V2 requires exact empty ActionSet")
        if (self.dividend_actions.account_id != self.scope.account_id
                or self.dividend_actions.coverage_start != clock.instant or self.dividend_actions.actions):
            raise ValueError("economic V2 requires same-account empty ActionSet starting at initialization")
        if type(self.activation_stale_policy) is not StaleMarkPolicy:
            raise TypeError("economic V2 requires exact native activation stale policy")
        if self.activation_stale_policy.price_purpose is not PricePurpose.VALUATION:
            raise ValueError("economic V2 activation policy must be VALUATION")
        from .cn_a_share_portfolio_economic_activation_v2 import (
            _economic_activation_at_v2, _economic_financial_checkpoints_v2,
            _resolve_retained_economic_marks_v2, _retained_economic_decision_v2,
        )
        derived = _resolve_retained_economic_marks_v2(self, clock)
        if canonical_bytes(derived) != canonical_bytes(self.initial_marks):
            raise ValueError("economic V2 initial marks differ from source-derived initialization")
        _resolve_retained_economic_marks_v2(self, _economic_activation_at_v2(self))
        _economic_financial_checkpoints_v2(self)
        _retained_economic_decision_v2(self)
        definition = ArtifactEnvelope.create("backtest_profile_portfolio_definition", 3, self.economic_payload())
        object.__setattr__(self, "_retained_definition", definition)
        object.__setattr__(self, "_definition_source_hash", canonical_sha256(definition))
        canonical_bytes(self)

    def economic_payload(self) -> dict[str, object]:
        scope = dict(self.scope.to_canonical_dict())
        scope.pop("target_stream_ref")
        return {"type": "cn_a_share_portfolio_economic_development_definition", "schema_version": 2,
            "scope": scope, "initial_journal": self.initial_journal, "calendars": self.calendars,
            "execution_policy": self.execution_policy, "opening_terms": self.opening_terms,
            "initial_marks": self.initial_marks, "retained_signal_marks": self.retained_signal_marks,
            "daily_marks": self.daily_marks, "checkpoint_marks": self.checkpoint_marks,
            "cost_basis_policy": self.cost_basis_policy, "notional_quantization": self.notional_quantization,
            "cash_dividend_action_set_hash": canonical_sha256(self.dividend_actions),
            "source_target_stream_digest": self.source_target_stream.target_stream_digest,
            "activation_stale_policy": self.activation_stale_policy,
            "source_qualification_verified": False, "broker_shared_pool_verified": False, "trade_authorized": False}

    def definition(self) -> ArtifactEnvelope:
        return self._retained_definition

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "cn_a_share_portfolio_economic_development_inputs", "schema_version": 2,
            **{name: getattr(self, name) for name, value in self.__dataclass_fields__.items() if value.init},
            "source_qualification_verified": False, "broker_shared_pool_verified": False, "trade_authorized": False}


def _read_activation_stale_policy_v2(raw) -> StaleMarkPolicy:
    fields = {"type", "policy_key", "policy_version", "price_purpose", "max_age_nanoseconds", "allow_forward_fill"}
    if not isinstance(raw, Mapping) or set(raw) != fields or raw["type"] != "stale_mark_policy":
        raise ValueError("economic V2 activation policy exact fields/tag mismatch")
    policy = StaleMarkPolicy(raw["policy_key"], raw["policy_version"], PricePurpose(raw["price_purpose"]),
        raw["max_age_nanoseconds"], raw["allow_forward_fill"])
    if canonical_bytes(policy) != canonical_bytes(raw):
        raise ValueError("economic V2 activation policy did not reconstruct exactly")
    return policy


def _read_economic_definition_v2(
    definition: ArtifactEnvelope, target_ref: BacktestTargetStreamRef,
    action_set: CnAShareCashDividendActionSetV1, source_target_stream: PrecomputedTargetStream,
) -> CnASharePortfolioEconomicDevelopmentInputsV2:
    if (type(definition) is not ArtifactEnvelope
            or definition.artifact_type != "backtest_profile_portfolio_definition" or definition.schema_version != 3
            or type(target_ref) is not BacktestTargetStreamRef or type(action_set) is not CnAShareCashDividendActionSetV1
            or type(source_target_stream) is not PrecomputedTargetStream):
        raise TypeError("economic V2 requires exact definition@3 and native sources")
    p = definition.payload
    fields = {"type", "schema_version", "scope", "initial_journal", "calendars", "execution_policy",
        "opening_terms", "initial_marks", "retained_signal_marks", "daily_marks", "checkpoint_marks",
        "cost_basis_policy", "notional_quantization", "cash_dividend_action_set_hash",
        "source_target_stream_digest", "activation_stale_policy", "source_qualification_verified",
        "broker_shared_pool_verified", "trade_authorized"}
    if (not isinstance(p, Mapping) or set(p) != fields
            or p["type"] != "cn_a_share_portfolio_economic_development_definition"
            or type(p["schema_version"]) is not int or p["schema_version"] != 2
            or any(p[k] is not False for k in ("source_qualification_verified", "broker_shared_pool_verified", "trade_authorized"))):
        raise ValueError("economic V2 definition exact fields/version/qualification mismatch")
    if action_set.actions or p["cash_dividend_action_set_hash"] != canonical_sha256(action_set):
        raise ValueError("economic V2 definition empty ActionSet/hash mismatch")
    if p["source_target_stream_digest"] != source_target_stream.target_stream_digest:
        raise ValueError("economic V2 definition original source digest mismatch")
    values = _read_economic_source_fields_v1(p, target_ref, signal_field="retained_signal_marks")
    policy = _read_activation_stale_policy_v2(p["activation_stale_policy"])
    result = CnASharePortfolioEconomicDevelopmentInputsV2(**values, source_target_stream=source_target_stream,
        dividend_actions=action_set, activation_stale_policy=policy)
    if (canonical_bytes(result.economic_payload()) != canonical_bytes(p)
            or canonical_bytes(result.definition()) != canonical_bytes(definition)):
        raise ValueError("economic V2 source definition did not reconstruct exactly")
    return result
