from __future__ import annotations

import re
from dataclasses import dataclass, replace
from enum import Enum
from typing import Any

from crypto_quant_domain import (
    AccountingEntryType,
    AccountingJournalEntry,
    BalanceChange,
    CashBalanceKey,
    CurrencyId,
    DomainId,
    DomainIdKind,
    FeeAssessment,
    FeeBasisType,
    Fill,
    Money,
    OrderSide,
    OrderStatus,
    QuantizationPolicy,
    Rate,
    Scale,
    SessionId,
    SimulationInstant,
    UtcInstant,
    VenueId,
    canonical_bytes,
    canonical_sha256,
)

from .fee_reservations import AccountFeeScheduleRef
from .orders import OrderEventStream
from .ports import ProfileComponentRef, ProfilePortType


_SHA256 = re.compile(r"sha256:[0-9a-f]{64}\Z")
_TERMINAL_ORDER_STATUSES = {
    OrderStatus.FILLED,
    OrderStatus.CANCELLED,
    OrderStatus.EXPIRED,
    OrderStatus.REJECTED,
}


def _require_text(name: str, value: str) -> None:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{name} must be canonical non-empty text")


def _require_hash(name: str, value: str) -> None:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ValueError(f"{name} must be canonical sha256 text")


def _basis_id_text(value: DomainId | SessionId) -> str:
    if isinstance(value, DomainId):
        return value.value
    return f"session:{value.calendar_id}:{value.value}"


def _component_identity(value: ProfileComponentRef) -> str:
    return (
        f"profile:{value.component_key}:v{value.component_version}:"
        f"{value.component_digest}"
    )


def _account_schedule_identity(value: AccountFeeScheduleRef) -> str:
    return (
        f"account-fee:{value.schedule_key}:v{value.schedule_version}:"
        f"{value.schedule_digest}"
    )


class FinalFeeRuleSource(str, Enum):
    MARKET_FEE = "market_fee"
    TAX = "tax"
    ACCOUNT_SCHEDULE = "account_schedule"


_SOURCE_ORDER = {
    FinalFeeRuleSource.MARKET_FEE: 0,
    FinalFeeRuleSource.TAX: 1,
    FinalFeeRuleSource.ACCOUNT_SCHEDULE: 2,
}


class FinalFeeCalculationBasis(str, Enum):
    NOTIONAL_RATE = "notional_rate"
    FLAT_PER_BASIS = "flat_per_basis"
    UNKNOWN = "unknown"


class FinalFeeApplicability(str, Enum):
    ALWAYS = "always"
    MAKER_ONLY = "maker_only"
    TAKER_ONLY = "taker_only"
    SELL_ONLY = "sell_only"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class FinalFeeChargeRule:
    source: FinalFeeRuleSource
    rule_id: str
    basis_type: FeeBasisType
    calculation_basis: FinalFeeCalculationBasis
    applicability: FinalFeeApplicability
    rate: Rate | None
    flat_amount: Money | None
    quantization: QuantizationPolicy

    def __post_init__(self) -> None:
        if not isinstance(self.source, FinalFeeRuleSource):
            raise TypeError("source must be FinalFeeRuleSource")
        _require_text("rule_id", self.rule_id)
        if not isinstance(self.basis_type, FeeBasisType):
            raise TypeError("basis_type must be FeeBasisType")
        if not isinstance(self.calculation_basis, FinalFeeCalculationBasis):
            raise TypeError("calculation_basis must be FinalFeeCalculationBasis")
        if not isinstance(self.applicability, FinalFeeApplicability):
            raise TypeError("applicability must be FinalFeeApplicability")
        if not isinstance(self.quantization, QuantizationPolicy):
            raise TypeError("quantization must be QuantizationPolicy")
        if self.calculation_basis is FinalFeeCalculationBasis.NOTIONAL_RATE:
            if not isinstance(self.rate, Rate) or self.flat_amount is not None:
                raise ValueError("notional_rate requires rate and forbids flat_amount")
            if self.rate.units < 0 or self.rate.basis != "fee_fraction":
                raise ValueError("fee rate must be a non-negative fee_fraction")
        elif self.calculation_basis is FinalFeeCalculationBasis.FLAT_PER_BASIS:
            if not isinstance(self.flat_amount, Money) or self.rate is not None:
                raise ValueError("flat_per_basis requires flat_amount and forbids rate")
            if self.flat_amount.units < 0:
                raise ValueError("flat fee must be non-negative")
        elif self.rate is not None or self.flat_amount is not None:
            raise ValueError("unknown calculation basis cannot carry an amount")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "final_fee_charge_rule",
            "source": self.source.value,
            "rule_id": self.rule_id,
            "basis_type": self.basis_type.value,
            "calculation_basis": self.calculation_basis.value,
            "applicability": self.applicability.value,
            "rate": self.rate,
            "flat_amount": self.flat_amount,
            "quantization": self.quantization,
        }


@dataclass(frozen=True, slots=True)
class FinalFeeMinimum:
    source: FinalFeeRuleSource
    minimum_id: str
    basis_type: FeeBasisType
    charge_rule_ids: tuple[str, ...]
    minimum_amount: Money

    def __post_init__(self) -> None:
        if not isinstance(self.source, FinalFeeRuleSource):
            raise TypeError("source must be FinalFeeRuleSource")
        _require_text("minimum_id", self.minimum_id)
        if self.basis_type not in (FeeBasisType.ORDER, FeeBasisType.SESSION):
            raise ValueError("final fee minimum requires Order or Session basis")
        if not isinstance(self.charge_rule_ids, tuple) or not self.charge_rule_ids:
            raise TypeError("charge_rule_ids must be a non-empty tuple")
        for rule_id in self.charge_rule_ids:
            _require_text("charge_rule_id", rule_id)
        ordered = tuple(sorted(self.charge_rule_ids))
        if len(ordered) != len(set(ordered)):
            raise ValueError("duplicate charge rule in final fee minimum")
        if not isinstance(self.minimum_amount, Money):
            raise TypeError("minimum_amount must be Money")
        if self.minimum_amount.units <= 0:
            raise ValueError("minimum_amount must be positive")
        object.__setattr__(self, "charge_rule_ids", ordered)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "final_fee_minimum",
            "source": self.source.value,
            "minimum_id": self.minimum_id,
            "basis_type": self.basis_type.value,
            "charge_rule_ids": self.charge_rule_ids,
            "minimum_amount": self.minimum_amount,
        }


def _rule_order(rule: FinalFeeChargeRule) -> tuple[str, int, str]:
    return rule.basis_type.value, _SOURCE_ORDER[rule.source], rule.rule_id


def _minimum_order(value: FinalFeeMinimum) -> tuple[str, int, str]:
    return value.basis_type.value, _SOURCE_ORDER[value.source], value.minimum_id


@dataclass(frozen=True, slots=True)
class FinalFeeRuleSet:
    market_fee_policy_ref: ProfileComponentRef
    tax_policy_ref: ProfileComponentRef
    account_fee_schedule_ref: AccountFeeScheduleRef
    assessment_currency: CurrencyId
    assessment_scale: Scale
    charge_rules: tuple[FinalFeeChargeRule, ...]
    minimums: tuple[FinalFeeMinimum, ...]
    config_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.market_fee_policy_ref, ProfileComponentRef) or (
            self.market_fee_policy_ref.port_type
            is not ProfilePortType.FEE_ASSESSMENT_POLICY
        ):
            raise TypeError("market_fee_policy_ref must identify FeeAssessmentPolicy")
        if not isinstance(self.tax_policy_ref, ProfileComponentRef) or (
            self.tax_policy_ref.port_type is not ProfilePortType.TAX_POLICY
        ):
            raise TypeError("tax_policy_ref must identify TaxPolicy")
        if not isinstance(self.account_fee_schedule_ref, AccountFeeScheduleRef):
            raise TypeError("account_fee_schedule_ref must be AccountFeeScheduleRef")
        if not isinstance(self.assessment_currency, CurrencyId):
            raise TypeError("assessment_currency must be CurrencyId")
        if not isinstance(self.assessment_scale, Scale):
            raise TypeError("assessment_scale must be Scale")
        if not isinstance(self.charge_rules, tuple) or not all(
            isinstance(rule, FinalFeeChargeRule) for rule in self.charge_rules
        ):
            raise TypeError("charge_rules must be FinalFeeChargeRule tuple")
        if not isinstance(self.minimums, tuple) or not all(
            isinstance(value, FinalFeeMinimum) for value in self.minimums
        ):
            raise TypeError("minimums must be FinalFeeMinimum tuple")

        ordered_rules = tuple(sorted(self.charge_rules, key=_rule_order))
        rule_ids = tuple(rule.rule_id for rule in ordered_rules)
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("duplicate final fee charge rule identity")
        for rule in ordered_rules:
            if rule.quantization.target_scale != self.assessment_scale:
                raise ValueError("final fee rule currency or Scale mismatch")
            if rule.flat_amount is not None and (
                rule.flat_amount.currency != str(self.assessment_currency)
                or rule.flat_amount.scale != self.assessment_scale
            ):
                raise ValueError("final fee rule currency or Scale mismatch")

        ordered_minimums = tuple(sorted(self.minimums, key=_minimum_order))
        minimum_ids = tuple(value.minimum_id for value in ordered_minimums)
        if len(minimum_ids) != len(set(minimum_ids)):
            raise ValueError("duplicate final fee minimum identity")
        by_id = {rule.rule_id: rule for rule in ordered_rules}
        covered: set[str] = set()
        for minimum in ordered_minimums:
            if (
                minimum.minimum_amount.currency != str(self.assessment_currency)
                or minimum.minimum_amount.scale != self.assessment_scale
            ):
                raise ValueError("final fee minimum currency or Scale mismatch")
            for rule_id in minimum.charge_rule_ids:
                scoped_rule = by_id.get(rule_id)
                if scoped_rule is None:
                    raise ValueError("minimum scope references unknown charge rule")
                if (
                    scoped_rule.source is not minimum.source
                    or scoped_rule.basis_type is not minimum.basis_type
                ):
                    raise ValueError("minimum scope must use same source and basis")
                if rule_id in covered:
                    raise ValueError("charge rule cannot belong to multiple minimums")
                covered.add(rule_id)

        object.__setattr__(self, "charge_rules", ordered_rules)
        object.__setattr__(self, "minimums", ordered_minimums)
        _require_hash("config_hash", self.config_hash)
        if self.config_hash != canonical_sha256(self.config_payload()):
            raise ValueError("config_hash mismatch")

    @classmethod
    def create(
        cls,
        *,
        market_fee_policy_ref: ProfileComponentRef,
        tax_policy_ref: ProfileComponentRef,
        account_fee_schedule_ref: AccountFeeScheduleRef,
        assessment_currency: CurrencyId,
        assessment_scale: Scale,
        charge_rules: tuple[FinalFeeChargeRule, ...],
        minimums: tuple[FinalFeeMinimum, ...],
    ) -> FinalFeeRuleSet:
        provisional = cls.__new__(cls)
        object.__setattr__(provisional, "market_fee_policy_ref", market_fee_policy_ref)
        object.__setattr__(provisional, "tax_policy_ref", tax_policy_ref)
        object.__setattr__(
            provisional, "account_fee_schedule_ref", account_fee_schedule_ref
        )
        object.__setattr__(provisional, "assessment_currency", assessment_currency)
        object.__setattr__(provisional, "assessment_scale", assessment_scale)
        object.__setattr__(
            provisional, "charge_rules", tuple(sorted(charge_rules, key=_rule_order))
        )
        object.__setattr__(
            provisional, "minimums", tuple(sorted(minimums, key=_minimum_order))
        )
        object.__setattr__(
            provisional, "config_hash", canonical_sha256(provisional.config_payload())
        )
        provisional.__post_init__()
        return provisional

    def config_payload(self) -> dict[str, Any]:
        return {
            "type": "final_fee_rule_set_config",
            "schema_version": 1,
            "market_fee_policy_ref": self.market_fee_policy_ref,
            "tax_policy_ref": self.tax_policy_ref,
            "account_fee_schedule_ref": self.account_fee_schedule_ref,
            "assessment_currency": self.assessment_currency,
            "assessment_scale": self.assessment_scale.places,
            "charge_rules": self.charge_rules,
            "minimums": self.minimums,
        }

    @property
    def rule_set_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            **self.config_payload(),
            "type": "final_fee_rule_set",
            "config_hash": self.config_hash,
        }


@dataclass(frozen=True, slots=True)
class FeeBasisClosureRef:
    closure_key: str
    closure_version: int
    source_digest: str
    closed_at: UtcInstant
    closure_hash: str

    def __post_init__(self) -> None:
        _require_text("closure_key", self.closure_key)
        if isinstance(self.closure_version, bool) or not isinstance(
            self.closure_version, int
        ) or self.closure_version <= 0:
            raise ValueError("closure_version must be a positive integer")
        _require_hash("source_digest", self.source_digest)
        if not isinstance(self.closed_at, UtcInstant):
            raise TypeError("closed_at must be UtcInstant")
        _require_hash("closure_hash", self.closure_hash)
        if self.closure_hash != canonical_sha256(self.config_payload()):
            raise ValueError("closure_hash mismatch")

    @classmethod
    def create(
        cls,
        *,
        closure_key: str,
        closure_version: int,
        source_digest: str,
        closed_at: UtcInstant,
    ) -> FeeBasisClosureRef:
        payload = {
            "type": "fee_basis_closure_config",
            "schema_version": 1,
            "closure_key": closure_key,
            "closure_version": closure_version,
            "source_digest": source_digest,
            "closed_at": closed_at,
        }
        return cls(
            closure_key,
            closure_version,
            source_digest,
            closed_at,
            canonical_sha256(payload),
        )

    def config_payload(self) -> dict[str, Any]:
        return {
            "type": "fee_basis_closure_config",
            "schema_version": 1,
            "closure_key": self.closure_key,
            "closure_version": self.closure_version,
            "source_digest": self.source_digest,
            "closed_at": self.closed_at,
        }

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            **self.config_payload(),
            "type": "fee_basis_closure_ref",
            "closure_hash": self.closure_hash,
        }


@dataclass(frozen=True, slots=True)
class FeeAssessmentBasisEvidence:
    basis_type: FeeBasisType
    basis_ids: tuple[DomainId | SessionId, ...]
    account_id: str
    venue_id: VenueId
    direct_fills: tuple[Fill, ...] = ()
    order_streams: tuple[OrderEventStream, ...] = ()
    closure_ref: FeeBasisClosureRef | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.basis_type, FeeBasisType):
            raise TypeError("basis_type must be FeeBasisType")
        if not isinstance(self.basis_ids, tuple) or len(self.basis_ids) != 1:
            raise ValueError("final fee basis requires exactly one basis identity")
        _require_text("account_id", self.account_id)
        if not isinstance(self.venue_id, VenueId):
            raise TypeError("venue_id must be VenueId")
        if not isinstance(self.direct_fills, tuple) or not all(
            isinstance(value, Fill) for value in self.direct_fills
        ):
            raise TypeError("direct_fills must be Fill tuple")
        if not isinstance(self.order_streams, tuple) or not all(
            isinstance(value, OrderEventStream) for value in self.order_streams
        ):
            raise TypeError("order_streams must be OrderEventStream tuple")
        if self.closure_ref is not None and not isinstance(
            self.closure_ref, FeeBasisClosureRef
        ):
            raise TypeError("closure_ref must be FeeBasisClosureRef or None")
        for value in self.direct_fills:
            if value.account_id != self.account_id or value.venue_id != self.venue_id:
                raise ValueError("direct Fill account or Venue mismatch")
        for stream in self.order_streams:
            if (
                stream.order.account_id != self.account_id
                or stream.order.intent.instrument_id.venue != self.venue_id
            ):
                raise ValueError("Order stream account or Venue mismatch")

        if self.basis_type is FeeBasisType.FILL:
            basis_id = self.basis_ids[0]
            if (
                not isinstance(basis_id, DomainId)
                or basis_id.kind is not DomainIdKind.FILL
                or len(self.direct_fills) != 1
                or self.direct_fills[0].fill_id != basis_id
                or self.order_streams
                or self.closure_ref is not None
            ):
                raise ValueError("Fill fee basis evidence shape mismatch")
        elif self.basis_type is FeeBasisType.ORDER:
            basis_id = self.basis_ids[0]
            if (
                not isinstance(basis_id, DomainId)
                or basis_id.kind is not DomainIdKind.ORDER
                or len(self.order_streams) != 1
                or self.order_streams[0].order.order_id != basis_id
                or self.direct_fills
                or self.closure_ref is not None
            ):
                raise ValueError("Order fee basis evidence shape mismatch")
        elif (
            not isinstance(self.basis_ids[0], SessionId)
            or self.direct_fills
            or self.closure_ref is None
        ):
            raise ValueError("Session fee basis evidence shape mismatch")

        object.__setattr__(
            self,
            "direct_fills",
            tuple(sorted(self.direct_fills, key=lambda value: value.fill_id.value)),
        )
        object.__setattr__(
            self,
            "order_streams",
            tuple(
                sorted(
                    self.order_streams,
                    key=lambda value: (value.order.order_id.value, value.stream_hash),
                )
            ),
        )

    @classmethod
    def for_fill(cls, fill: Fill) -> FeeAssessmentBasisEvidence:
        if not isinstance(fill, Fill):
            raise TypeError("fill must be Fill")
        return cls(
            FeeBasisType.FILL,
            (fill.fill_id,),
            fill.account_id,
            fill.venue_id,
            direct_fills=(fill,),
        )

    @classmethod
    def for_order(cls, stream: OrderEventStream) -> FeeAssessmentBasisEvidence:
        if not isinstance(stream, OrderEventStream):
            raise TypeError("stream must be OrderEventStream")
        return cls(
            FeeBasisType.ORDER,
            (stream.order.order_id,),
            stream.order.account_id,
            stream.order.intent.instrument_id.venue,
            order_streams=(stream,),
        )

    @classmethod
    def for_session(
        cls,
        *,
        session_id: SessionId,
        account_id: str,
        venue_id: VenueId,
        order_streams: tuple[OrderEventStream, ...],
        closure_ref: FeeBasisClosureRef,
    ) -> FeeAssessmentBasisEvidence:
        return cls(
            FeeBasisType.SESSION,
            (session_id,),
            account_id,
            venue_id,
            order_streams=order_streams,
            closure_ref=closure_ref,
        )

    @property
    def fills(self) -> tuple[Fill, ...]:
        values = list(self.direct_fills)
        for stream in self.order_streams:
            values.extend(
                record.fill for record in stream.records if record.fill is not None
            )
        return tuple(
            sorted(values, key=lambda value: (value.execution_time, value.fill_id.value))
        )

    @property
    def closed_at(self) -> UtcInstant:
        if self.basis_type is FeeBasisType.FILL:
            return self.direct_fills[0].execution_time
        if self.basis_type is FeeBasisType.SESSION:
            closure_ref = self.closure_ref
            if closure_ref is None:
                raise ValueError("Session fee basis requires closure_ref")
            return closure_ref.closed_at
        stream = self.order_streams[0]
        if not stream.records:
            return stream.order.created_at.instant
        return stream.records[-1].event.occurred_at.instant

    @property
    def basis_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "fee_assessment_basis_evidence",
            "schema_version": 1,
            "basis_type": self.basis_type.value,
            "basis_ids": self.basis_ids,
            "account_id": self.account_id,
            "venue_id": self.venue_id,
            "direct_fills": self.direct_fills,
            "order_streams": self.order_streams,
            "closure_ref": self.closure_ref,
        }


@dataclass(frozen=True, slots=True)
class FinalFeeLine:
    rule: FinalFeeChargeRule
    applicable_fill_ids: tuple[DomainId, ...]
    notional: Money | None
    amount: Money
    applied: bool

    def __post_init__(self) -> None:
        if not isinstance(self.rule, FinalFeeChargeRule):
            raise TypeError("rule must be FinalFeeChargeRule")
        if not isinstance(self.applicable_fill_ids, tuple) or not all(
            isinstance(value, DomainId) and value.kind is DomainIdKind.FILL
            for value in self.applicable_fill_ids
        ):
            raise TypeError("applicable_fill_ids must be Fill DomainId tuple")
        ordered = tuple(sorted(self.applicable_fill_ids, key=lambda value: value.value))
        if len(ordered) != len(set(value.value for value in ordered)):
            raise ValueError("duplicate applicable Fill identity")
        if self.notional is not None and not isinstance(self.notional, Money):
            raise TypeError("notional must be Money or None")
        if not isinstance(self.amount, Money):
            raise TypeError("amount must be Money")
        if not isinstance(self.applied, bool):
            raise TypeError("applied must be bool")
        if self.amount.units < 0:
            raise ValueError("final fee line amount must be non-negative")
        object.__setattr__(self, "applicable_fill_ids", ordered)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "final_fee_line",
            "rule": self.rule,
            "applicable_fill_ids": self.applicable_fill_ids,
            "notional": self.notional,
            "amount": self.amount,
            "applied": self.applied,
        }


@dataclass(frozen=True, slots=True)
class FinalFeeMinimumAdjustment:
    minimum: FinalFeeMinimum
    subtotal: Money
    amount: Money

    def __post_init__(self) -> None:
        if not isinstance(self.minimum, FinalFeeMinimum):
            raise TypeError("minimum must be FinalFeeMinimum")
        if not isinstance(self.subtotal, Money) or not isinstance(self.amount, Money):
            raise TypeError("minimum adjustment values must be Money")
        if self.subtotal.units < 0 or self.amount.units < 0:
            raise ValueError("minimum adjustment values must be non-negative")
        if (
            self.subtotal.currency != self.amount.currency
            or self.subtotal.scale != self.amount.scale
        ):
            raise ValueError("minimum adjustment currency or Scale mismatch")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "final_fee_minimum_adjustment",
            "minimum": self.minimum,
            "subtotal": self.subtotal,
            "amount": self.amount,
        }


@dataclass(frozen=True, slots=True)
class FinalFeeAssessmentResult:
    basis: FeeAssessmentBasisEvidence
    rule_set: FinalFeeRuleSet
    lines: tuple[FinalFeeLine, ...]
    minimum_adjustments: tuple[FinalFeeMinimumAdjustment, ...]
    assessment: FeeAssessment

    def __post_init__(self) -> None:
        if not isinstance(self.basis, FeeAssessmentBasisEvidence):
            raise TypeError("basis must be FeeAssessmentBasisEvidence")
        if not isinstance(self.rule_set, FinalFeeRuleSet):
            raise TypeError("rule_set must be FinalFeeRuleSet")
        if not isinstance(self.lines, tuple) or not all(
            isinstance(value, FinalFeeLine) for value in self.lines
        ):
            raise TypeError("lines must be FinalFeeLine tuple")
        if not isinstance(self.minimum_adjustments, tuple) or not all(
            isinstance(value, FinalFeeMinimumAdjustment)
            for value in self.minimum_adjustments
        ):
            raise TypeError("minimum_adjustments must be tuple")
        if not isinstance(self.assessment, FeeAssessment):
            raise TypeError("assessment must be FeeAssessment")
        if self.assessment.basis_type is not self.basis.basis_type or (
            self.assessment.basis_ids != self.basis.basis_ids
        ):
            raise ValueError("FeeAssessment basis mismatch")
        expected_rules = tuple(
            rule
            for rule in self.rule_set.charge_rules
            if rule.basis_type is self.basis.basis_type
        )
        if tuple(line.rule for line in self.lines) != expected_rules:
            raise ValueError("final fee lines do not exactly cover basis rules")
        _, expected_fills, ambiguous = _unique_streams_and_fills(self.basis)
        if ambiguous or self.lines != tuple(
            _fee_line(rule, expected_fills, self.rule_set)
            for rule in expected_rules
        ):
            raise ValueError("final fee lines do not match basis evidence")
        for line in self.lines:
            if (
                line.amount.currency != str(self.rule_set.assessment_currency)
                or line.amount.scale != self.rule_set.assessment_scale
                or (
                    line.notional is not None
                    and (
                        line.notional.currency
                        != str(self.rule_set.assessment_currency)
                        or line.notional.scale != self.rule_set.assessment_scale
                    )
                )
            ):
                raise ValueError("final fee line currency or Scale mismatch")
        expected_adjustments = _minimum_adjustments(
            self.rule_set, self.basis.basis_type, self.lines
        )
        if self.minimum_adjustments != expected_adjustments:
            raise ValueError("final fee minimum adjustments do not match rule scope")
        expected_units = sum(line.amount.units for line in self.lines) + sum(
            value.amount.units for value in self.minimum_adjustments
        )
        if (
            self.assessment.amount.currency != str(self.rule_set.assessment_currency)
            or self.assessment.amount.scale != self.rule_set.assessment_scale
            or self.assessment.amount.units != expected_units
            or self.assessment.market_fee_rule_id
            != _component_identity(self.rule_set.market_fee_policy_ref)
            or self.assessment.tax_rule_id
            != _component_identity(self.rule_set.tax_policy_ref)
            or self.assessment.account_fee_schedule_id
            != _account_schedule_identity(self.rule_set.account_fee_schedule_ref)
        ):
            raise ValueError("FeeAssessment total or rule identity mismatch")

    @property
    def result_hash(self) -> str:
        return canonical_sha256(self)

    @property
    def rule_identity_ids(self) -> tuple[str, ...]:
        values = {
            _component_identity(self.rule_set.market_fee_policy_ref),
            _component_identity(self.rule_set.tax_policy_ref),
            _account_schedule_identity(self.rule_set.account_fee_schedule_ref),
            f"final-fee-rule-set:{self.rule_set.rule_set_hash}",
            f"fee-basis:{self.basis.basis_hash}",
        }
        values.update(line.rule.rule_id for line in self.lines)
        values.update(
            value.minimum_id
            for value in self.rule_set.minimums
            if value.basis_type is self.basis.basis_type
        )
        return tuple(sorted(values))

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "final_fee_assessment_result",
            "schema_version": 1,
            "basis": self.basis,
            "rule_set": self.rule_set,
            "lines": self.lines,
            "minimum_adjustments": self.minimum_adjustments,
            "assessment": self.assessment,
            "rule_identity_ids": self.rule_identity_ids,
        }


class FinalFeeAssessmentFailureCode(str, Enum):
    INCOMPLETE_BASIS = "incomplete_basis"
    AMBIGUOUS_BASIS = "ambiguous_basis"
    MISSING_RULE_SOURCE = "missing_rule_source"
    UNKNOWN_CALCULATION_BASIS = "unknown_calculation_basis"
    UNKNOWN_APPLICABILITY = "unknown_applicability"
    LIQUIDITY_ROLE_MISSING = "liquidity_role_missing"
    RULE_CONTEXT_MISMATCH = "rule_context_mismatch"
    ASSESSMENT_BEFORE_BASIS_CLOSED = "assessment_before_basis_closed"


@dataclass(frozen=True, slots=True)
class FinalFeeAssessmentFailure:
    basis_hash: str
    rule_set_hash: str
    fee_assessment_id: DomainId
    assessment_time: UtcInstant
    codes: tuple[FinalFeeAssessmentFailureCode, ...]
    subjects: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_hash("basis_hash", self.basis_hash)
        _require_hash("rule_set_hash", self.rule_set_hash)
        if (
            not isinstance(self.fee_assessment_id, DomainId)
            or self.fee_assessment_id.kind is not DomainIdKind.FEE
        ):
            raise TypeError("fee_assessment_id must be Fee DomainId")
        if not isinstance(self.assessment_time, UtcInstant):
            raise TypeError("assessment_time must be UtcInstant")
        if not isinstance(self.codes, tuple) or not self.codes:
            raise TypeError("codes must be non-empty tuple")
        if not all(isinstance(code, FinalFeeAssessmentFailureCode) for code in self.codes):
            raise TypeError("codes must contain FinalFeeAssessmentFailureCode")
        if not isinstance(self.subjects, tuple):
            raise TypeError("subjects must be tuple")
        for value in self.subjects:
            _require_text("failure subject", value)
        object.__setattr__(
            self,
            "codes",
            tuple(sorted(set(self.codes), key=lambda value: value.value)),
        )
        object.__setattr__(self, "subjects", tuple(sorted(set(self.subjects))))

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "final_fee_assessment_failure",
            "basis_hash": self.basis_hash,
            "rule_set_hash": self.rule_set_hash,
            "fee_assessment_id": self.fee_assessment_id,
            "assessment_time": self.assessment_time,
            "codes": tuple(value.value for value in self.codes),
            "subjects": self.subjects,
        }


@dataclass(frozen=True, slots=True)
class FinalFeeAssessmentOutcome:
    result: FinalFeeAssessmentResult | None = None
    failure: FinalFeeAssessmentFailure | None = None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.failure is None):
            raise ValueError("final fee outcome requires exactly one result or failure")
        if self.result is not None and not isinstance(
            self.result, FinalFeeAssessmentResult
        ):
            raise TypeError("result must be FinalFeeAssessmentResult")
        if self.failure is not None and not isinstance(
            self.failure, FinalFeeAssessmentFailure
        ):
            raise TypeError("failure must be FinalFeeAssessmentFailure")

    @property
    def outcome_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "final_fee_assessment_outcome",
            "result": self.result,
            "failure": self.failure,
        }


def _unique_streams_and_fills(
    basis: FeeAssessmentBasisEvidence,
) -> tuple[tuple[OrderEventStream, ...], tuple[Fill, ...], bool]:
    streams_by_order: dict[str, OrderEventStream] = {}
    ambiguous = False
    for stream in basis.order_streams:
        order_id = stream.order.order_id.value
        existing_stream = streams_by_order.get(order_id)
        if existing_stream is None:
            streams_by_order[order_id] = stream
        elif existing_stream.stream_hash != stream.stream_hash:
            ambiguous = True

    fills_by_id: dict[str, Fill] = {}
    for fill in basis.direct_fills:
        fills_by_id[fill.fill_id.value] = fill
    for stream in streams_by_order.values():
        for record in stream.records:
            if record.fill is None:
                continue
            existing_fill = fills_by_id.get(record.fill.fill_id.value)
            if existing_fill is None:
                fills_by_id[record.fill.fill_id.value] = record.fill
            elif canonical_bytes(existing_fill) != canonical_bytes(record.fill):
                ambiguous = True
    return (
        tuple(sorted(streams_by_order.values(), key=lambda value: value.order.order_id.value)),
        tuple(
            sorted(
                fills_by_id.values(),
                key=lambda value: (value.execution_time, value.fill_id.value),
            )
        ),
        ambiguous,
    )


def _applicable_fills(
    rule: FinalFeeChargeRule, fills: tuple[Fill, ...]
) -> tuple[tuple[Fill, ...], bool]:
    if rule.applicability is FinalFeeApplicability.NOT_APPLICABLE:
        return (), False
    if rule.applicability is FinalFeeApplicability.ALWAYS:
        return fills, True
    if rule.applicability is FinalFeeApplicability.SELL_ONLY:
        selected = tuple(fill for fill in fills if fill.side is OrderSide.SELL)
        return selected, bool(selected)
    if rule.applicability in (
        FinalFeeApplicability.MAKER_ONLY,
        FinalFeeApplicability.TAKER_ONLY,
    ):
        if any(fill.liquidity not in ("maker", "taker") for fill in fills):
            raise ValueError("liquidity role missing")
        role = (
            "maker"
            if rule.applicability is FinalFeeApplicability.MAKER_ONLY
            else "taker"
        )
        selected = tuple(fill for fill in fills if fill.liquidity == role)
        return selected, bool(selected)
    raise LookupError("unknown applicability")


def _fee_line(
    rule: FinalFeeChargeRule,
    fills: tuple[Fill, ...],
    rule_set: FinalFeeRuleSet,
) -> FinalFeeLine:
    selected, applies = _applicable_fills(rule, fills)
    applicable_ids = tuple(fill.fill_id for fill in selected)
    if rule.calculation_basis is FinalFeeCalculationBasis.NOTIONAL_RATE:
        if rule.rate is None:
            raise ValueError("missing final fee rate")
        if not selected:
            applies = False
        notional_units = 0
        for fill in selected:
            if fill.price.quote_currency != str(rule_set.assessment_currency):
                raise ArithmeticError("final fee quote currency mismatch")
            notional_units += fill.price.notional(
                fill.quantity,
                result_scale=rule_set.assessment_scale,
                rounding=rule.quantization.rounding,
            ).units
        notional = Money(
            notional_units,
            rule_set.assessment_scale,
            str(rule_set.assessment_currency),
        )
        amount = notional.multiply_by_rate(
            rule.rate,
            result_scale=rule_set.assessment_scale,
            rounding=rule.quantization.rounding,
        )
        return FinalFeeLine(rule, applicable_ids, notional, amount, applies)
    if rule.calculation_basis is FinalFeeCalculationBasis.FLAT_PER_BASIS:
        if rule.flat_amount is None:
            raise ValueError("missing flat final fee")
        amount = rule.flat_amount if applies else Money(
            0, rule_set.assessment_scale, str(rule_set.assessment_currency)
        )
        return FinalFeeLine(rule, applicable_ids, None, amount, applies)
    raise LookupError("unknown calculation basis")


def _minimum_adjustments(
    rule_set: FinalFeeRuleSet,
    basis_type: FeeBasisType,
    lines: tuple[FinalFeeLine, ...],
) -> tuple[FinalFeeMinimumAdjustment, ...]:
    line_by_id = {line.rule.rule_id: line for line in lines}
    adjustments: list[FinalFeeMinimumAdjustment] = []
    for minimum in rule_set.minimums:
        if minimum.basis_type is not basis_type:
            continue
        scoped = tuple(line_by_id[rule_id] for rule_id in minimum.charge_rule_ids)
        if not any(line.applied for line in scoped):
            continue
        subtotal_units = sum(line.amount.units for line in scoped)
        adjustments.append(
            FinalFeeMinimumAdjustment(
                minimum,
                Money(
                    subtotal_units,
                    rule_set.assessment_scale,
                    str(rule_set.assessment_currency),
                ),
                Money(
                    max(minimum.minimum_amount.units - subtotal_units, 0),
                    rule_set.assessment_scale,
                    str(rule_set.assessment_currency),
                ),
            )
        )
    return tuple(adjustments)


class FeeAssessmentEngine:
    def assess(
        self,
        *,
        basis: FeeAssessmentBasisEvidence,
        rule_set: FinalFeeRuleSet,
        fee_assessment_id: DomainId,
        assessment_time: UtcInstant,
    ) -> FinalFeeAssessmentOutcome:
        if not isinstance(basis, FeeAssessmentBasisEvidence):
            raise TypeError("basis must be FeeAssessmentBasisEvidence")
        if not isinstance(rule_set, FinalFeeRuleSet):
            raise TypeError("rule_set must be FinalFeeRuleSet")
        if (
            not isinstance(fee_assessment_id, DomainId)
            or fee_assessment_id.kind is not DomainIdKind.FEE
        ):
            raise TypeError("fee_assessment_id must be Fee DomainId")
        if not isinstance(assessment_time, UtcInstant):
            raise TypeError("assessment_time must be UtcInstant")

        streams, fills, ambiguous = _unique_streams_and_fills(basis)
        normalized_basis = (
            basis
            if ambiguous or basis.basis_type is FeeBasisType.FILL
            else replace(basis, order_streams=streams)
        )
        issues: list[tuple[FinalFeeAssessmentFailureCode, str]] = []
        if ambiguous:
            issues.append((FinalFeeAssessmentFailureCode.AMBIGUOUS_BASIS, "basis"))
        if normalized_basis.basis_type in (FeeBasisType.ORDER, FeeBasisType.SESSION):
            if any(
                stream.state is None or stream.state.status not in _TERMINAL_ORDER_STATUSES
                for stream in streams
            ):
                issues.append((FinalFeeAssessmentFailureCode.INCOMPLETE_BASIS, "basis"))
        latest_stream_instant = max(
            (
                stream.records[-1].event.occurred_at.instant
                for stream in streams
                if stream.records
            ),
            default=None,
        )
        if (
            normalized_basis.basis_type is FeeBasisType.SESSION
            and normalized_basis.closure_ref is not None
            and latest_stream_instant is not None
            and latest_stream_instant > normalized_basis.closure_ref.closed_at
        ):
            issues.append(
                (FinalFeeAssessmentFailureCode.INCOMPLETE_BASIS, "session_closure")
            )
        if assessment_time < normalized_basis.closed_at:
            issues.append(
                (
                    FinalFeeAssessmentFailureCode.ASSESSMENT_BEFORE_BASIS_CLOSED,
                    "assessment_time",
                )
            )

        basis_rules = tuple(
            rule
            for rule in rule_set.charge_rules
            if rule.basis_type is normalized_basis.basis_type
        )
        covered_sources = {rule.source for rule in basis_rules}
        for source in FinalFeeRuleSource:
            if source not in covered_sources:
                issues.append(
                    (FinalFeeAssessmentFailureCode.MISSING_RULE_SOURCE, source.value)
                )
        for rule in basis_rules:
            if rule.calculation_basis is FinalFeeCalculationBasis.UNKNOWN:
                issues.append(
                    (
                        FinalFeeAssessmentFailureCode.UNKNOWN_CALCULATION_BASIS,
                        rule.rule_id,
                    )
                )
            if rule.applicability is FinalFeeApplicability.UNKNOWN:
                issues.append(
                    (
                        FinalFeeAssessmentFailureCode.UNKNOWN_APPLICABILITY,
                        rule.rule_id,
                    )
                )
            if rule.applicability in (
                FinalFeeApplicability.MAKER_ONLY,
                FinalFeeApplicability.TAKER_ONLY,
            ) and any(fill.liquidity not in ("maker", "taker") for fill in fills):
                issues.append(
                    (
                        FinalFeeAssessmentFailureCode.LIQUIDITY_ROLE_MISSING,
                        rule.rule_id,
                    )
                )
            if rule.quantization.target_scale != rule_set.assessment_scale:
                issues.append(
                    (FinalFeeAssessmentFailureCode.RULE_CONTEXT_MISMATCH, rule.rule_id)
                )

        if issues:
            return FinalFeeAssessmentOutcome(
                failure=FinalFeeAssessmentFailure(
                    normalized_basis.basis_hash,
                    rule_set.rule_set_hash,
                    fee_assessment_id,
                    assessment_time,
                    tuple(code for code, _ in issues),
                    tuple(subject for _, subject in issues),
                )
            )

        try:
            lines = tuple(_fee_line(rule, fills, rule_set) for rule in basis_rules)
        except (ArithmeticError, ValueError):
            return FinalFeeAssessmentOutcome(
                failure=FinalFeeAssessmentFailure(
                    normalized_basis.basis_hash,
                    rule_set.rule_set_hash,
                    fee_assessment_id,
                    assessment_time,
                    (FinalFeeAssessmentFailureCode.RULE_CONTEXT_MISMATCH,),
                    ("fee_arithmetic",),
                )
            )

        adjustments = _minimum_adjustments(
            rule_set, normalized_basis.basis_type, lines
        )
        total_units = sum(line.amount.units for line in lines) + sum(
            value.amount.units for value in adjustments
        )
        assessment = FeeAssessment(
            fee_assessment_id=fee_assessment_id,
            basis_type=normalized_basis.basis_type,
            basis_ids=normalized_basis.basis_ids,
            market_fee_rule_id=_component_identity(
                rule_set.market_fee_policy_ref
            ),
            account_fee_schedule_id=_account_schedule_identity(
                rule_set.account_fee_schedule_ref
            ),
            tax_rule_id=_component_identity(rule_set.tax_policy_ref),
            amount=Money(
                total_units,
                rule_set.assessment_scale,
                str(rule_set.assessment_currency),
            ),
            assessment_time=assessment_time,
        )
        return FinalFeeAssessmentOutcome(
            result=FinalFeeAssessmentResult(
                normalized_basis,
                rule_set,
                lines,
                adjustments,
                assessment,
            )
        )


class FeeChargedJournalFailureCode(str, Enum):
    NON_POSITIVE_FEE = "non_positive_fee"
    CASH_CONTEXT_MISMATCH = "cash_context_mismatch"
    RECORDED_BEFORE_ASSESSMENT = "recorded_before_assessment"


@dataclass(frozen=True, slots=True)
class FeeChargedJournalFailure:
    code: FeeChargedJournalFailureCode
    assessment_result_hash: str
    subject_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.code, FeeChargedJournalFailureCode):
            raise TypeError("code must be FeeChargedJournalFailureCode")
        _require_hash("assessment_result_hash", self.assessment_result_hash)
        _require_text("subject_id", self.subject_id)

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "fee_charged_journal_failure",
            "code": self.code.value,
            "assessment_result_hash": self.assessment_result_hash,
            "subject_id": self.subject_id,
        }


@dataclass(frozen=True, slots=True)
class FeeChargedJournalResult:
    assessment_result: FinalFeeAssessmentResult
    journal_entry: AccountingJournalEntry

    def __post_init__(self) -> None:
        if not isinstance(self.assessment_result, FinalFeeAssessmentResult):
            raise TypeError("assessment_result must be FinalFeeAssessmentResult")
        if not isinstance(self.journal_entry, AccountingJournalEntry):
            raise TypeError("journal_entry must be AccountingJournalEntry")
        if self.journal_entry.entry_type is not AccountingEntryType.FEE_CHARGED:
            raise ValueError("journal_entry must be FeeCharged")
        assessment = self.assessment_result.assessment
        required_sources = {
            assessment.fee_assessment_id.value,
            *(
                _basis_id_text(value)
                for value in assessment.basis_ids
            ),
            *self.assessment_result.rule_identity_ids,
        }
        if not required_sources.issubset(self.journal_entry.source_ids):
            raise ValueError("FeeCharged entry must reference all fee evidence")
        balance_key = (
            self.journal_entry.balance_changes[0].key
            if len(self.journal_entry.balance_changes) == 1
            else None
        )
        expected_change = (
            BalanceChange(balance_key, -assessment.amount)
            if isinstance(balance_key, CashBalanceKey)
            else None
        )
        if (
            self.journal_entry.account_id != self.assessment_result.basis.account_id
            or self.journal_entry.venue_id != self.assessment_result.basis.venue_id
            or self.journal_entry.effective_time != assessment.assessment_time
            or self.journal_entry.balance_changes != (expected_change,)
            or self.journal_entry.fees != (assessment.amount,)
            or self.journal_entry.realized_pnl
            or self.journal_entry.financing
        ):
            raise ValueError("FeeCharged Journal economic effect mismatch")

    @property
    def result_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "fee_charged_journal_result",
            "assessment_result": self.assessment_result,
            "journal_entry": self.journal_entry,
        }


@dataclass(frozen=True, slots=True)
class FeeChargedJournalOutcome:
    result: FeeChargedJournalResult | None = None
    failure: FeeChargedJournalFailure | None = None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.failure is None):
            raise ValueError("fee journal outcome requires exactly one result or failure")
        if self.result is not None and not isinstance(
            self.result, FeeChargedJournalResult
        ):
            raise TypeError("result must be FeeChargedJournalResult")
        if self.failure is not None and not isinstance(
            self.failure, FeeChargedJournalFailure
        ):
            raise TypeError("failure must be FeeChargedJournalFailure")

    @property
    def outcome_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "fee_charged_journal_outcome",
            "result": self.result,
            "failure": self.failure,
        }


class FeeChargedJournalTranslator:
    def translate(
        self,
        *,
        result: FinalFeeAssessmentResult,
        cash_key: CashBalanceKey,
        journal_entry_id: DomainId,
        recorded_at: SimulationInstant,
    ) -> FeeChargedJournalOutcome:
        if not isinstance(result, FinalFeeAssessmentResult):
            raise TypeError("result must be FinalFeeAssessmentResult")
        if not isinstance(cash_key, CashBalanceKey):
            raise TypeError("cash_key must be CashBalanceKey")
        if (
            not isinstance(journal_entry_id, DomainId)
            or journal_entry_id.kind is not DomainIdKind.JOURNAL
        ):
            raise TypeError("journal_entry_id must be Journal DomainId")
        if not isinstance(recorded_at, SimulationInstant):
            raise TypeError("recorded_at must be SimulationInstant")
        assessment = result.assessment
        if assessment.amount.units <= 0:
            return FeeChargedJournalOutcome(
                failure=FeeChargedJournalFailure(
                    FeeChargedJournalFailureCode.NON_POSITIVE_FEE,
                    result.result_hash,
                    assessment.fee_assessment_id.value,
                )
            )
        if (
            cash_key.account_id != result.basis.account_id
            or cash_key.venue_id != result.basis.venue_id
            or str(cash_key.currency_id) != assessment.amount.currency
        ):
            return FeeChargedJournalOutcome(
                failure=FeeChargedJournalFailure(
                    FeeChargedJournalFailureCode.CASH_CONTEXT_MISMATCH,
                    result.result_hash,
                    assessment.fee_assessment_id.value,
                )
            )
        if recorded_at.instant < assessment.assessment_time:
            return FeeChargedJournalOutcome(
                failure=FeeChargedJournalFailure(
                    FeeChargedJournalFailureCode.RECORDED_BEFORE_ASSESSMENT,
                    result.result_hash,
                    assessment.fee_assessment_id.value,
                )
            )
        source_ids = {
            assessment.fee_assessment_id.value,
            *(_basis_id_text(value) for value in assessment.basis_ids),
            *result.rule_identity_ids,
        }
        entry = AccountingJournalEntry(
            journal_entry_id=journal_entry_id,
            entry_type=AccountingEntryType.FEE_CHARGED,
            account_id=result.basis.account_id,
            venue_id=result.basis.venue_id,
            effective_time=assessment.assessment_time,
            recorded_at=recorded_at,
            source_ids=tuple(sorted(source_ids)),
            balance_changes=(BalanceChange(cash_key, -assessment.amount),),
            realized_pnl=(),
            fees=(assessment.amount,),
            financing=(),
        )
        return FeeChargedJournalOutcome(
            result=FeeChargedJournalResult(result, entry)
        )
