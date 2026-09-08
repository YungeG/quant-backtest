"""Historical mainland China cash-equity order rules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Any

from crypto_quant_domain import (
    InstrumentDefinition,
    InstrumentId,
    InstrumentType,
    Money,
    OrderSide,
    PositionEffect,
    Price,
    Rate,
    RoundingPolicy,
    Scale,
    SessionId,
    TradingDate,
    UtcInstant,
    VenueId,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_trading.market_rules import (
    MarketSessionState,
    OrderRuleInterval,
    OrderRuleSnapshot,
    OrderRuleTimeline,
)
from crypto_quant_trading.ports import (
    ProfileComponentRef,
    ProfilePortOutcome,
    ProfilePortType,
)
from crypto_quant_trading.sizing import QuantityLattice

from .calendar import CnAShareSessionResolution
from .quantity_lattice import (
    CnAShareCashQuantityLatticeModel,
    CnAShareQuantityLatticeQuery,
)


_COMPONENT_KEY = "equity.cn_a_share.cash.order-rules.v1"
_ALGORITHM_KEY = "cn-a-share-historical-order-rules-v1"
_SUPPORTED_VENUES = {VenueId("xshg"), VenueId("xshe")}


class CnAShareBoard(str, Enum):
    MAIN = "main"
    STAR = "star"
    CHINEXT = "chinext"


class CnAShareRiskClass(str, Enum):
    STANDARD = "standard"
    RISK_WARNING = "risk_warning"
    DELISTING = "delisting"


class CnAShareListingPhase(str, Enum):
    SEASONED = "seasoned"
    IPO_FIRST_FIVE = "ipo_first_five"
    RELISTING_FIRST_DAY = "relisting_first_day"
    DELISTING_FIRST_DAY = "delisting_first_day"


class CnAShareTradeStatus(str, Enum):
    NORMAL = "normal"
    SUSPENDED = "suspended"


class CnAShareOrderRuleResolutionKind(str, Enum):
    RULES = "rules"
    NO_TRADE = "no_trade"


class CnAShareOrderRuleFailureCode(str, Enum):
    UNSUPPORTED_VENUE = "unsupported_venue"
    UNSUPPORTED_INSTRUMENT = "unsupported_instrument"
    UNSUPPORTED_CURRENCY = "unsupported_currency"
    UNSUPPORTED_BOARD = "unsupported_board"
    UNSUPPORTED_CLASSIFICATION = "unsupported_classification"
    SESSION_EVIDENCE_MISMATCH = "session_evidence_mismatch"
    MISSING_RULE_INTERVAL = "missing_rule_interval"
    OVERLAPPING_RULE_INTERVALS = "overlapping_rule_intervals"
    MISSING_TRADE_STATUS_EVIDENCE = "missing_trade_status_evidence"
    INVALID_TRADE_STATUS_EVIDENCE = "invalid_trade_status_evidence"
    MISSING_PREVIOUS_CLOSE_EVIDENCE = "missing_previous_close_evidence"
    INVALID_PREVIOUS_CLOSE_EVIDENCE = "invalid_previous_close_evidence"


def _text(name: str, value: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be text")
    if not value or value.strip() != value:
        raise ValueError(f"{name} must be canonical non-empty text")
    canonical_bytes(value)


def _hash(name: str, value: str) -> None:
    digest = value.removeprefix("sha256:") if isinstance(value, str) else ""
    if (
        not isinstance(value, str)
        or not value.startswith("sha256:")
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise ValueError(f"{name} must be a canonical sha256 identity")


def _positive(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value <= 0:
        raise ValueError(f"{name} must be positive")


@dataclass(frozen=True, slots=True)
class CnAShareRuleSourceRef:
    source_key: str
    source_hash: str

    def __post_init__(self) -> None:
        _text("source_key", self.source_key)
        _hash("source_hash", self.source_hash)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "cn_a_share_rule_source_ref",
            "schema_version": 1,
            "source_key": self.source_key,
            "source_hash": self.source_hash,
        }


@dataclass(frozen=True, slots=True)
class CnAShareOrderRuleBand:
    venue_id: VenueId
    board: CnAShareBoard
    effective_from: date
    effective_to_exclusive: date
    daily_price_limit_ratio: Rate
    price_tick_units: int
    max_limit_order_quantity_units: int
    max_market_order_quantity_units: int
    quantity_step_units: int
    buy_lot_units: int
    sell_lot_units: int
    min_quantity_units: int
    odd_lot_close_permitted: bool
    whole_sell_residual_permitted: bool
    source_ref: CnAShareRuleSourceRef

    def __post_init__(self) -> None:
        if self.venue_id not in _SUPPORTED_VENUES:
            raise ValueError("unsupported A-share Venue")
        if not isinstance(self.board, CnAShareBoard):
            raise TypeError("board must be CnAShareBoard")
        if not isinstance(self.effective_from, date) or not isinstance(
            self.effective_to_exclusive, date
        ):
            raise TypeError("effective interval must use date")
        if self.effective_from >= self.effective_to_exclusive:
            raise ValueError("rule band requires a non-empty interval")
        if not isinstance(self.daily_price_limit_ratio, Rate):
            raise TypeError("daily_price_limit_ratio must be Rate")
        if (
            self.daily_price_limit_ratio.basis != "fraction"
            or not 0 < self.daily_price_limit_ratio.units < self.daily_price_limit_ratio.scale.factor
        ):
            raise ValueError("daily price limit ratio must be a positive fraction below one")
        for name in (
            "price_tick_units",
            "max_limit_order_quantity_units",
            "max_market_order_quantity_units",
            "quantity_step_units",
            "buy_lot_units",
            "sell_lot_units",
        ):
            _positive(name, getattr(self, name))
        if isinstance(self.min_quantity_units, bool) or not isinstance(
            self.min_quantity_units, int
        ):
            raise TypeError("min_quantity_units must be an integer")
        if self.min_quantity_units < 0:
            raise ValueError("min_quantity_units cannot be negative")
        if type(self.odd_lot_close_permitted) is not bool or type(
            self.whole_sell_residual_permitted
        ) is not bool:
            raise TypeError("odd-lot flags must be bool")
        if not isinstance(self.source_ref, CnAShareRuleSourceRef):
            raise TypeError("source_ref must be CnAShareRuleSourceRef")
        if self.board is CnAShareBoard.STAR and self.venue_id != VenueId("xshg"):
            raise ValueError("STAR requires XSHG")
        if self.board is CnAShareBoard.CHINEXT and self.venue_id != VenueId("xshe"):
            raise ValueError("ChiNext requires XSHE")

    @property
    def band_hash(self) -> str:
        return canonical_sha256(self)

    def contains(self, trading_date: date) -> bool:
        return self.effective_from <= trading_date < self.effective_to_exclusive

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "cn_a_share_order_rule_band",
            "schema_version": 1,
            "venue_id": self.venue_id,
            "board": self.board.value,
            "effective_from": self.effective_from.isoformat(),
            "effective_to_exclusive": self.effective_to_exclusive.isoformat(),
            "daily_price_limit_ratio": self.daily_price_limit_ratio,
            "price_tick_units": self.price_tick_units,
            "max_limit_order_quantity_units": self.max_limit_order_quantity_units,
            "max_market_order_quantity_units": self.max_market_order_quantity_units,
            "quantity_step_units": self.quantity_step_units,
            "buy_lot_units": self.buy_lot_units,
            "sell_lot_units": self.sell_lot_units,
            "min_quantity_units": self.min_quantity_units,
            "odd_lot_close_permitted": self.odd_lot_close_permitted,
            "whole_sell_residual_permitted": self.whole_sell_residual_permitted,
            "source_ref": self.source_ref,
        }


@dataclass(frozen=True, slots=True)
class CnAShareOrderRuleBook:
    rule_book_key: str
    rule_book_version: int
    bands: tuple[CnAShareOrderRuleBand, ...]

    def __post_init__(self) -> None:
        _text("rule_book_key", self.rule_book_key)
        _positive("rule_book_version", self.rule_book_version)
        if not isinstance(self.bands, tuple) or not self.bands or not all(
            isinstance(value, CnAShareOrderRuleBand) for value in self.bands
        ):
            raise TypeError("bands must contain CnAShareOrderRuleBand")
        ordered = tuple(
            sorted(
                self.bands,
                key=lambda value: (
                    value.venue_id.value,
                    value.board.value,
                    value.effective_from,
                    value.effective_to_exclusive,
                    value.band_hash,
                ),
            )
        )
        object.__setattr__(self, "bands", ordered)

    @property
    def rule_book_hash(self) -> str:
        return canonical_sha256(self)

    def active_bands(
        self, venue_id: VenueId, board: CnAShareBoard, trading_date: date
    ) -> tuple[CnAShareOrderRuleBand, ...]:
        return tuple(
            value
            for value in self.bands
            if value.venue_id == venue_id
            and value.board is board
            and value.contains(trading_date)
        )

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "cn_a_share_order_rule_book",
            "schema_version": 1,
            "rule_book_key": self.rule_book_key,
            "rule_book_version": self.rule_book_version,
            "bands": self.bands,
        }


@dataclass(frozen=True, slots=True)
class CnAShareInstrumentRuleContext:
    board: CnAShareBoard
    risk_class: CnAShareRiskClass
    listing_phase: CnAShareListingPhase
    source_key: str
    source_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.board, CnAShareBoard):
            raise TypeError("board must be CnAShareBoard")
        if not isinstance(self.risk_class, CnAShareRiskClass):
            raise TypeError("risk_class must be CnAShareRiskClass")
        if not isinstance(self.listing_phase, CnAShareListingPhase):
            raise TypeError("listing_phase must be CnAShareListingPhase")
        _text("source_key", self.source_key)
        _hash("source_hash", self.source_hash)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "cn_a_share_instrument_rule_context",
            "schema_version": 1,
            "board": self.board.value,
            "risk_class": self.risk_class.value,
            "listing_phase": self.listing_phase.value,
            "source_key": self.source_key,
            "source_hash": self.source_hash,
        }


@dataclass(frozen=True, slots=True)
class CnAShareTradeStatusEvidence:
    instrument_id: InstrumentId
    session_id: SessionId
    status: CnAShareTradeStatus
    effective_from: UtcInstant
    effective_to_exclusive: UtcInstant
    source_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.instrument_id, InstrumentId):
            raise TypeError("instrument_id must be InstrumentId")
        if not isinstance(self.session_id, SessionId):
            raise TypeError("session_id must be SessionId")
        if not isinstance(self.status, CnAShareTradeStatus):
            raise TypeError("status must be CnAShareTradeStatus")
        if not isinstance(self.effective_from, UtcInstant) or not isinstance(
            self.effective_to_exclusive, UtcInstant
        ):
            raise TypeError("trade-status interval must use UtcInstant")
        if self.effective_from >= self.effective_to_exclusive:
            raise ValueError("trade-status interval must be non-empty")
        _hash("source_hash", self.source_hash)

    @property
    def evidence_hash(self) -> str:
        return canonical_sha256(self)

    def contains(self, instant: UtcInstant) -> bool:
        return self.effective_from <= instant < self.effective_to_exclusive

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "cn_a_share_trade_status_evidence",
            "schema_version": 1,
            "instrument_id": self.instrument_id,
            "session_id": self.session_id,
            "status": self.status.value,
            "effective_from": self.effective_from,
            "effective_to_exclusive": self.effective_to_exclusive,
            "source_hash": self.source_hash,
        }


@dataclass(frozen=True, slots=True)
class CnASharePreviousCloseEvidence:
    instrument_id: InstrumentId
    reference_trading_date: TradingDate
    price: Price
    available_at: UtcInstant
    source_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.instrument_id, InstrumentId):
            raise TypeError("instrument_id must be InstrumentId")
        if not isinstance(self.reference_trading_date, TradingDate):
            raise TypeError("reference_trading_date must be TradingDate")
        if not isinstance(self.price, Price):
            raise TypeError("price must be Price")
        if not isinstance(self.available_at, UtcInstant):
            raise TypeError("available_at must be UtcInstant")
        _hash("source_hash", self.source_hash)

    @property
    def evidence_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "cn_a_share_previous_close_evidence",
            "schema_version": 1,
            "instrument_id": self.instrument_id,
            "reference_trading_date": self.reference_trading_date,
            "price": self.price,
            "available_at": self.available_at,
            "source_hash": self.source_hash,
        }


@dataclass(frozen=True, slots=True)
class CnAShareOrderRuleQuery:
    instrument: InstrumentDefinition
    evaluated_at: UtcInstant
    session: CnAShareSessionResolution
    context: CnAShareInstrumentRuleContext
    trade_status_evidence: CnAShareTradeStatusEvidence | None
    previous_close_evidence: CnASharePreviousCloseEvidence | None

    def __post_init__(self) -> None:
        if not isinstance(self.instrument, InstrumentDefinition):
            raise TypeError("instrument must be InstrumentDefinition")
        if not isinstance(self.evaluated_at, UtcInstant):
            raise TypeError("evaluated_at must be UtcInstant")
        if not isinstance(self.session, CnAShareSessionResolution):
            raise TypeError("session must be CnAShareSessionResolution")
        if not isinstance(self.context, CnAShareInstrumentRuleContext):
            raise TypeError("context must be CnAShareInstrumentRuleContext")
        if self.trade_status_evidence is not None and not isinstance(
            self.trade_status_evidence, CnAShareTradeStatusEvidence
        ):
            raise TypeError("trade_status_evidence has invalid type")
        if self.previous_close_evidence is not None and not isinstance(
            self.previous_close_evidence, CnASharePreviousCloseEvidence
        ):
            raise TypeError("previous_close_evidence has invalid type")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "cn_a_share_order_rule_query",
            "schema_version": 1,
            "instrument": self.instrument,
            "evaluated_at": self.evaluated_at,
            "session": self.session,
            "context": self.context,
            "trade_status_evidence": self.trade_status_evidence,
            "previous_close_evidence": self.previous_close_evidence,
        }


@dataclass(frozen=True, slots=True)
class CnAShareOrderRuleResolution:
    kind: CnAShareOrderRuleResolutionKind
    venue_id: VenueId
    instrument_id: InstrumentId
    evaluated_at: UtcInstant
    board: CnAShareBoard
    rule_band_hash: str | None
    session_resolution_hash: str
    trade_status_evidence_hash: str | None
    previous_close_evidence_hash: str | None
    timeline: OrderRuleTimeline | None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, CnAShareOrderRuleResolutionKind):
            raise TypeError("kind must be CnAShareOrderRuleResolutionKind")
        if not isinstance(self.venue_id, VenueId) or not isinstance(
            self.instrument_id, InstrumentId
        ):
            raise TypeError("resolution identities have invalid type")
        if not isinstance(self.evaluated_at, UtcInstant):
            raise TypeError("evaluated_at must be UtcInstant")
        if not isinstance(self.board, CnAShareBoard):
            raise TypeError("board must be CnAShareBoard")
        _hash("session_resolution_hash", self.session_resolution_hash)
        for name in (
            "rule_band_hash",
            "trade_status_evidence_hash",
            "previous_close_evidence_hash",
        ):
            value = getattr(self, name)
            if value is not None:
                _hash(name, value)
        if self.kind is CnAShareOrderRuleResolutionKind.NO_TRADE:
            if self.timeline is not None or self.rule_band_hash is not None:
                raise ValueError("no-trade resolution cannot contain rules")
        elif not isinstance(self.timeline, OrderRuleTimeline):
            raise TypeError("rules resolution requires OrderRuleTimeline")

    @property
    def resolution_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "cn_a_share_order_rule_resolution",
            "schema_version": 1,
            "kind": self.kind.value,
            "venue_id": self.venue_id,
            "instrument_id": self.instrument_id,
            "evaluated_at": self.evaluated_at,
            "board": self.board.value,
            "rule_band_hash": self.rule_band_hash,
            "session_resolution_hash": self.session_resolution_hash,
            "trade_status_evidence_hash": self.trade_status_evidence_hash,
            "previous_close_evidence_hash": self.previous_close_evidence_hash,
            "timeline": self.timeline,
        }


@dataclass(frozen=True, slots=True)
class CnAShareOrderRuleFailure:
    code: CnAShareOrderRuleFailureCode
    venue_id: VenueId
    instrument_id: InstrumentId
    evaluated_at: UtcInstant
    subject_key: str

    def __post_init__(self) -> None:
        if not isinstance(self.code, CnAShareOrderRuleFailureCode):
            raise TypeError("code must be CnAShareOrderRuleFailureCode")
        if not isinstance(self.venue_id, VenueId) or not isinstance(
            self.instrument_id, InstrumentId
        ):
            raise TypeError("failure identities have invalid type")
        if not isinstance(self.evaluated_at, UtcInstant):
            raise TypeError("evaluated_at must be UtcInstant")
        _text("subject_key", self.subject_key)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "cn_a_share_order_rule_failure",
            "schema_version": 1,
            "code": self.code.value,
            "venue_id": self.venue_id,
            "instrument_id": self.instrument_id,
            "evaluated_at": self.evaluated_at,
            "subject_key": self.subject_key,
        }


def _round_half_up(numerator: int, denominator: int) -> int:
    quotient, remainder = divmod(numerator, denominator)
    return quotient + (1 if remainder * 2 >= denominator else 0)


def _price_limit(previous_close: Price, ratio: Rate, tick_units: int, sign: int) -> Price:
    factor = ratio.scale.factor
    multiplier = factor + sign * ratio.units
    ticks = _round_half_up(
        previous_close.units * multiplier,
        factor * tick_units,
    )
    units = ticks * tick_units
    if abs(units - previous_close.units) < tick_units:
        units = previous_close.units + sign * tick_units
    units = max(units, tick_units)
    return Price(
        units,
        previous_close.scale,
        previous_close.instrument_id,
        previous_close.quote_currency,
    )


class CnAShareOpenObservationState(str, Enum):
    AVAILABLE = "available"
    NO_TRADE = "no_trade"
    DATA_MISSING = "data_missing"


class CnAShareLimitLiquidityDecisionCode(str, Enum):
    CONTINUE = "continue"
    LIQUIDITY_BLOCKED_AT_LIMIT = "liquidity_blocked_at_limit"
    NO_TRADE = "no_trade"
    DATA_MISSING = "data_missing"
    SUSPENDED = "suspended"


@dataclass(frozen=True, slots=True)
class CnAShareLimitLiquidityInput:
    side: OrderSide
    snapshot: OrderRuleSnapshot
    observation_state: CnAShareOpenObservationState
    bar_open: Price | None

    def __post_init__(self) -> None:
        if not isinstance(self.side, OrderSide):
            raise TypeError("side must be OrderSide")
        if not isinstance(self.snapshot, OrderRuleSnapshot):
            raise TypeError("snapshot must be OrderRuleSnapshot")
        if not isinstance(self.observation_state, CnAShareOpenObservationState):
            raise TypeError("observation_state must be CnAShareOpenObservationState")
        if self.bar_open is not None and not isinstance(self.bar_open, Price):
            raise TypeError("bar_open must be Price or None")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "cn_a_share_limit_liquidity_input",
            "schema_version": 1,
            "side": self.side.value,
            "snapshot": self.snapshot,
            "observation_state": self.observation_state.value,
            "bar_open": self.bar_open,
        }


@dataclass(frozen=True, slots=True)
class CnAShareLimitLiquidityDecision:
    code: CnAShareLimitLiquidityDecisionCode
    side: OrderSide
    snapshot_hash: str
    observation_state: CnAShareOpenObservationState
    bar_open: Price | None

    def __post_init__(self) -> None:
        if not isinstance(self.code, CnAShareLimitLiquidityDecisionCode):
            raise TypeError("code must be CnAShareLimitLiquidityDecisionCode")
        if not isinstance(self.side, OrderSide):
            raise TypeError("side must be OrderSide")
        _hash("snapshot_hash", self.snapshot_hash)
        if not isinstance(self.observation_state, CnAShareOpenObservationState):
            raise TypeError("observation_state must be CnAShareOpenObservationState")
        if self.bar_open is not None and not isinstance(self.bar_open, Price):
            raise TypeError("bar_open must be Price or None")

    @property
    def decision_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "cn_a_share_limit_liquidity_decision",
            "schema_version": 1,
            "code": self.code.value,
            "side": self.side.value,
            "snapshot_hash": self.snapshot_hash,
            "observation_state": self.observation_state.value,
            "bar_open": self.bar_open,
        }


@dataclass(frozen=True, slots=True)
class CnAShareBarLimitLiquidityEvaluator:
    def evaluate(
        self, value: CnAShareLimitLiquidityInput, /
    ) -> CnAShareLimitLiquidityDecision:
        if not isinstance(value, CnAShareLimitLiquidityInput):
            raise TypeError("value must be CnAShareLimitLiquidityInput")
        code = CnAShareLimitLiquidityDecisionCode.CONTINUE
        price = value.bar_open
        mismatched_price = price is not None and (
            price.instrument_id != str(value.snapshot.instrument_id)
            or price.quote_currency
            != value.snapshot.quantity_lattice.min_notional.currency
            or price.scale != value.snapshot.price_scale
        )
        if (
            value.observation_state is CnAShareOpenObservationState.DATA_MISSING
            or mismatched_price
        ):
            code = CnAShareLimitLiquidityDecisionCode.DATA_MISSING
        elif value.observation_state is CnAShareOpenObservationState.NO_TRADE:
            code = CnAShareLimitLiquidityDecisionCode.NO_TRADE
        elif price is None:
            code = CnAShareLimitLiquidityDecisionCode.DATA_MISSING
        elif value.snapshot.session_state is MarketSessionState.SUSPENDED:
            code = CnAShareLimitLiquidityDecisionCode.SUSPENDED
        elif (
            value.side is OrderSide.BUY
            and value.snapshot.upper_price_limit is not None
            and price.units == value.snapshot.upper_price_limit.units
        ) or (
            value.side is OrderSide.SELL
            and value.snapshot.lower_price_limit is not None
            and price.units == value.snapshot.lower_price_limit.units
        ):
            code = CnAShareLimitLiquidityDecisionCode.LIQUIDITY_BLOCKED_AT_LIMIT
        return CnAShareLimitLiquidityDecision(
            code=code,
            side=value.side,
            snapshot_hash=value.snapshot.snapshot_hash,
            observation_state=value.observation_state,
            bar_open=price,
        )


@dataclass(frozen=True, slots=True)
class CnAShareCashOrderRuleModel:
    rule_book: CnAShareOrderRuleBook
    notional_scale: Scale

    def __post_init__(self) -> None:
        if not isinstance(self.rule_book, CnAShareOrderRuleBook):
            raise TypeError("rule_book must be CnAShareOrderRuleBook")
        if not isinstance(self.notional_scale, Scale):
            raise TypeError("notional_scale must be Scale")

    @property
    def component_ref(self) -> ProfileComponentRef:
        return ProfileComponentRef(
            port_type=ProfilePortType.ORDER_RULE_MODEL,
            component_key=_COMPONENT_KEY,
            component_version=1,
            component_digest=canonical_sha256(
                {
                    "type": "cn_a_share_cash_order_rule_component",
                    "schema_version": 1,
                    "component_key": _COMPONENT_KEY,
                    "component_version": 1,
                    "algorithm_key": _ALGORITHM_KEY,
                    "rule_book_hash": self.rule_book.rule_book_hash,
                    "notional_scale": self.notional_scale.places,
                }
            ),
        )

    def resolve_order_rules(
        self, query: CnAShareOrderRuleQuery, /
    ) -> ProfilePortOutcome[CnAShareOrderRuleResolution, CnAShareOrderRuleFailure]:
        if not isinstance(query, CnAShareOrderRuleQuery):
            raise TypeError("query must be CnAShareOrderRuleQuery")
        instrument = query.instrument
        venue_id = instrument.instrument_id.venue
        if venue_id not in _SUPPORTED_VENUES:
            return self._failure(query, CnAShareOrderRuleFailureCode.UNSUPPORTED_VENUE)
        if instrument.instrument_type is not InstrumentType.EQUITY:
            return self._failure(query, CnAShareOrderRuleFailureCode.UNSUPPORTED_INSTRUMENT)
        if str(instrument.quote_currency) != "CNY" or str(instrument.settlement_currency) != "CNY":
            return self._failure(query, CnAShareOrderRuleFailureCode.UNSUPPORTED_CURRENCY)
        if (
            query.context.board is CnAShareBoard.STAR and venue_id != VenueId("xshg")
        ) or (
            query.context.board is CnAShareBoard.CHINEXT and venue_id != VenueId("xshe")
        ):
            return self._failure(query, CnAShareOrderRuleFailureCode.UNSUPPORTED_BOARD)
        if (
            query.context.risk_class is not CnAShareRiskClass.STANDARD
            or query.context.listing_phase is not CnAShareListingPhase.SEASONED
        ):
            return self._failure(
                query, CnAShareOrderRuleFailureCode.UNSUPPORTED_CLASSIFICATION
            )
        session = query.session
        if session.venue_id != venue_id or session.instant != query.evaluated_at:
            return self._failure(
                query, CnAShareOrderRuleFailureCode.SESSION_EVIDENCE_MISMATCH
            )
        session_hash = canonical_sha256(session)
        if session.session_id is None:
            return ProfilePortOutcome.for_result(
                self.component_ref,
                query,
                CnAShareOrderRuleResolution(
                    kind=CnAShareOrderRuleResolutionKind.NO_TRADE,
                    venue_id=venue_id,
                    instrument_id=instrument.instrument_id,
                    evaluated_at=query.evaluated_at,
                    board=query.context.board,
                    rule_band_hash=None,
                    session_resolution_hash=session_hash,
                    trade_status_evidence_hash=None,
                    previous_close_evidence_hash=None,
                    timeline=None,
                ),
            )
        if session.trading_date is None or session.phase_start is None or session.phase_end_exclusive is None:
            return self._failure(
                query, CnAShareOrderRuleFailureCode.SESSION_EVIDENCE_MISMATCH
            )
        bands = self.rule_book.active_bands(
            venue_id, query.context.board, session.trading_date.value
        )
        if not bands:
            return self._failure(query, CnAShareOrderRuleFailureCode.MISSING_RULE_INTERVAL)
        if len(bands) != 1:
            return self._failure(
                query, CnAShareOrderRuleFailureCode.OVERLAPPING_RULE_INTERVALS
            )
        status = query.trade_status_evidence
        if status is None:
            return self._failure(
                query, CnAShareOrderRuleFailureCode.MISSING_TRADE_STATUS_EVIDENCE
            )
        if (
            status.instrument_id != instrument.instrument_id
            or status.session_id != session.session_id
            or not status.contains(query.evaluated_at)
        ):
            return self._failure(
                query, CnAShareOrderRuleFailureCode.INVALID_TRADE_STATUS_EVIDENCE
            )
        previous = query.previous_close_evidence
        if previous is None:
            return self._failure(
                query, CnAShareOrderRuleFailureCode.MISSING_PREVIOUS_CLOSE_EVIDENCE
            )
        if (
            previous.instrument_id != instrument.instrument_id
            or previous.price.instrument_id != str(instrument.instrument_id)
            or previous.price.quote_currency != "CNY"
            or previous.price.scale != self.notional_scale
            or previous.price.units <= 0
            or previous.available_at > query.evaluated_at
            or previous.reference_trading_date.calendar_id
            != session.trading_date.calendar_id
            or previous.reference_trading_date.value >= session.trading_date.value
        ):
            return self._failure(
                query, CnAShareOrderRuleFailureCode.INVALID_PREVIOUS_CLOSE_EVIDENCE
            )
        band = bands[0]
        lattice = self._lattice(instrument, band)
        state = (
            MarketSessionState.CLOSED
            if not session.is_open
            else MarketSessionState.SUSPENDED
            if status.status is CnAShareTradeStatus.SUSPENDED
            else MarketSessionState.OPEN
        )
        snapshot = OrderRuleSnapshot.create(
            component_ref=self.component_ref,
            instrument_id=instrument.instrument_id,
            session_id=session.session_id,
            session_state=state,
            quantity_lattice=lattice,
            price_scale=previous.price.scale,
            price_tick_units=band.price_tick_units,
            lower_price_limit=_price_limit(
                previous.price, band.daily_price_limit_ratio, band.price_tick_units, -1
            ),
            upper_price_limit=_price_limit(
                previous.price, band.daily_price_limit_ratio, band.price_tick_units, 1
            ),
            permitted_sides=(OrderSide.BUY, OrderSide.SELL),
            permitted_position_effects=(
                PositionEffect.AUTO,
                PositionEffect.OPEN,
                PositionEffect.CLOSE,
            ),
            reduce_only_required=False,
            notional_rounding=RoundingPolicy.HALF_UP,
            supplemental_decisions=(),
            max_limit_order_quantity_units=band.max_limit_order_quantity_units,
            max_market_order_quantity_units=band.max_market_order_quantity_units,
        )
        interval = OrderRuleInterval.create(
            effective_from=max(session.phase_start, status.effective_from),
            effective_to_exclusive=min(
                session.phase_end_exclusive, status.effective_to_exclusive
            ),
            snapshot=snapshot,
        )
        timeline = OrderRuleTimeline.create(
            timeline_key=(
                f"equity.cn_a_share.cash.{query.context.board.value}."
                f"{instrument.instrument_id.stable_key}.order-rules.v1"
            ),
            timeline_version=1,
            instrument_id=instrument.instrument_id,
            intervals=(interval,),
        )
        return ProfilePortOutcome.for_result(
            self.component_ref,
            query,
            CnAShareOrderRuleResolution(
                kind=CnAShareOrderRuleResolutionKind.RULES,
                venue_id=venue_id,
                instrument_id=instrument.instrument_id,
                evaluated_at=query.evaluated_at,
                board=query.context.board,
                rule_band_hash=band.band_hash,
                session_resolution_hash=session_hash,
                trade_status_evidence_hash=status.evidence_hash,
                previous_close_evidence_hash=previous.evidence_hash,
                timeline=timeline,
            ),
        )

    def _lattice(
        self, instrument: InstrumentDefinition, band: CnAShareOrderRuleBand
    ) -> QuantityLattice:
        if band.board is CnAShareBoard.MAIN:
            result = CnAShareCashQuantityLatticeModel(
                band.venue_id, self.notional_scale
            ).resolve_instrument(CnAShareQuantityLatticeQuery(instrument)).result
            if result is None:  # pragma: no cover - validated above
                raise AssertionError("main-board lattice resolution failed")
            return result.quantity_lattice
        return QuantityLattice.create(
            instrument_id=instrument.instrument_id,
            lattice_key=(
                f"equity.cn_a_share.cash.{band.board.value}.quantity-lattice.v1"
            ),
            lattice_version=1,
            atomic_scale=Scale(0),
            step_units=band.quantity_step_units,
            buy_lot_units=band.buy_lot_units,
            sell_lot_units=band.sell_lot_units,
            min_quantity_units=band.min_quantity_units,
            min_notional=Money(0, self.notional_scale, "CNY"),
            odd_lot_close_permitted=band.odd_lot_close_permitted,
            whole_sell_residual_permitted=band.whole_sell_residual_permitted,
        )

    def _failure(
        self,
        query: CnAShareOrderRuleQuery,
        code: CnAShareOrderRuleFailureCode,
    ) -> ProfilePortOutcome[CnAShareOrderRuleResolution, CnAShareOrderRuleFailure]:
        return ProfilePortOutcome.for_failure(
            self.component_ref,
            query,
            CnAShareOrderRuleFailure(
                code=code,
                venue_id=query.instrument.instrument_id.venue,
                instrument_id=query.instrument.instrument_id,
                evaluated_at=query.evaluated_at,
                subject_key=f"instrument:{query.instrument.instrument_id}",
            ),
        )
