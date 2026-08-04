from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, cast

from crypto_quant_domain import (
    CashBalanceKey,
    CurrencyId,
    Money,
    PortfolioSnapshot,
    PositionBalanceKey,
    PricePurpose,
    QuantizationPolicy,
    Scale,
    UtcInstant,
    ValuationMarkReference,
    canonical_bytes,
    canonical_sha256,
)

from .ledger import LedgerState
from .marks import ResolvedMark
from .valuation import CurrencyValuationResolution


_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class PortfolioValueKind(str, Enum):
    CASH = "cash"
    POSITION_MARKET_VALUE = "position_market_value"
    REALIZED_PNL = "realized_pnl"
    UNREALIZED_PNL = "unrealized_pnl"
    FEES = "fees"
    FINANCING = "financing"


_CASH_KINDS = {
    PortfolioValueKind.CASH,
    PortfolioValueKind.REALIZED_PNL,
    PortfolioValueKind.FEES,
    PortfolioValueKind.FINANCING,
}
_POSITION_KINDS = {
    PortfolioValueKind.POSITION_MARKET_VALUE,
    PortfolioValueKind.UNREALIZED_PNL,
}


def _require_hash(name: str, value: str) -> None:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{name} must be a canonical sha256 identity")


@dataclass(frozen=True, slots=True)
class PortfolioValueRef:
    kind: PortfolioValueKind
    balance_key: CashBalanceKey | PositionBalanceKey

    def __post_init__(self) -> None:
        if not isinstance(self.kind, PortfolioValueKind):
            raise TypeError("kind must be PortfolioValueKind")
        if self.kind in _CASH_KINDS and not isinstance(
            self.balance_key, CashBalanceKey
        ):
            raise TypeError(f"{self.kind.value} requires CashBalanceKey")
        if self.kind in _POSITION_KINDS and not isinstance(
            self.balance_key, PositionBalanceKey
        ):
            raise TypeError(f"{self.kind.value} requires PositionBalanceKey")

    @property
    def ref_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "portfolio_value_ref",
            "kind": self.kind.value,
            "balance_key": self.balance_key,
        }


@dataclass(frozen=True, slots=True)
class ReportingCurrencyValuation:
    value_ref: PortfolioValueRef
    native_value: Money
    reporting_value: Money
    resolution: CurrencyValuationResolution
    currency_valuation_graph_hash: str
    quantization_policy: QuantizationPolicy | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.value_ref, PortfolioValueRef):
            raise TypeError("value_ref must be PortfolioValueRef")
        if not isinstance(self.native_value, Money):
            raise TypeError("native_value must be Money")
        if not isinstance(self.reporting_value, Money):
            raise TypeError("reporting_value must be Money")
        if not isinstance(self.resolution, CurrencyValuationResolution):
            raise TypeError("resolution must be CurrencyValuationResolution")
        _require_hash(
            "currency_valuation_graph_hash", self.currency_valuation_graph_hash
        )
        path = self.resolution.path
        if path.source_currency_id != CurrencyId(self.native_value.currency):
            raise ValueError("valuation path source must match native currency")
        if path.reporting_currency_id != CurrencyId(self.reporting_value.currency):
            raise ValueError("valuation path target must match reporting currency")
        if self.value_ref.kind is PortfolioValueKind.POSITION_MARKET_VALUE:
            if not isinstance(self.quantization_policy, QuantizationPolicy):
                raise ValueError(
                    "Position market value requires QuantizationPolicy"
                )
            if self.quantization_policy.target_scale != self.native_value.scale:
                raise ValueError(
                    "Position market QuantizationPolicy scale must match native value"
                )
        elif self.quantization_policy is not None:
            raise ValueError(
                "QuantizationPolicy is only valid for Position market value"
            )
        if path.is_identity and self.native_value != self.reporting_value:
            raise ValueError("identity currency path requires an exact value identity")

    @property
    def valuation_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "reporting_currency_valuation",
            "value_ref": self.value_ref,
            "native_value": self.native_value,
            "reporting_value": self.reporting_value,
            "resolution": self.resolution,
            "currency_valuation_graph_hash": self.currency_valuation_graph_hash,
            "quantization_policy": self.quantization_policy,
        }


class SnapshotProjectionFailureCode(str, Enum):
    MULTIPLE_ACCOUNTS = "multiple_accounts"
    VALUATION_COVERAGE_MISMATCH = "valuation_coverage_mismatch"
    NATIVE_VALUE_MISMATCH = "native_value_mismatch"
    REPORTING_CONTEXT_MISMATCH = "reporting_context_mismatch"
    VALUATION_PATH_MISMATCH = "valuation_path_mismatch"
    CURRENCY_GRAPH_MISMATCH = "currency_graph_mismatch"
    MARK_COVERAGE_MISMATCH = "mark_coverage_mismatch"
    POSITION_MARK_MISMATCH = "position_mark_mismatch"
    POSITION_NOTIONAL_MISMATCH = "position_notional_mismatch"


@dataclass(frozen=True, slots=True)
class SnapshotProjectionFailure:
    code: SnapshotProjectionFailureCode
    ledger_state_hash: str
    subject_hashes: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.code, SnapshotProjectionFailureCode):
            raise TypeError("code must be SnapshotProjectionFailureCode")
        _require_hash("ledger_state_hash", self.ledger_state_hash)
        if not isinstance(self.subject_hashes, tuple):
            raise TypeError("subject_hashes must be a tuple")
        if any(
            not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None
            for value in self.subject_hashes
        ):
            raise ValueError("subject_hashes must contain canonical sha256 identities")
        ordered = tuple(sorted(set(self.subject_hashes)))
        object.__setattr__(self, "subject_hashes", ordered)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "type": "snapshot_projection_failure",
            "code": self.code.value,
            "ledger_state_hash": self.ledger_state_hash,
            "subject_hashes": self.subject_hashes,
        }


@dataclass(frozen=True, slots=True)
class SnapshotProjectionOutcome:
    snapshot: PortfolioSnapshot | None
    failure: SnapshotProjectionFailure | None

    def __post_init__(self) -> None:
        if (self.snapshot is None) == (self.failure is None):
            raise ValueError(
                "SnapshotProjectionOutcome requires exactly one snapshot or failure"
            )
        if self.snapshot is not None and not isinstance(
            self.snapshot, PortfolioSnapshot
        ):
            raise TypeError("snapshot must be PortfolioSnapshot")
        if self.failure is not None and not isinstance(
            self.failure, SnapshotProjectionFailure
        ):
            raise TypeError("failure must be SnapshotProjectionFailure")

    def to_canonical_dict(self) -> dict[str, Any]:
        if self.snapshot is not None:
            return {
                "type": "snapshot_projection_outcome",
                "status": "projected",
                "snapshot": self.snapshot,
            }
        return {
            "type": "snapshot_projection_outcome",
            "status": "failed",
            "failure": self.failure,
        }


@dataclass(frozen=True, slots=True)
class PortfolioSnapshotProjector:
    def project(
        self,
        *,
        ledger_state: LedgerState,
        resolved_marks: tuple[ResolvedMark, ...],
        valuations: tuple[ReportingCurrencyValuation, ...],
        reporting_currency: CurrencyId,
        reporting_scale: Scale,
        timestamp: UtcInstant,
        currency_valuation_graph_hash: str,
    ) -> SnapshotProjectionOutcome:
        self._validate_input_types(
            ledger_state,
            resolved_marks,
            valuations,
            reporting_currency,
            reporting_scale,
            timestamp,
            currency_valuation_graph_hash,
        )
        accounts = {
            registration.key.account_id
            for registration in ledger_state.schema.registrations
        }
        if len(accounts) != 1:
            return self._failure(
                SnapshotProjectionFailureCode.MULTIPLE_ACCOUNTS,
                ledger_state,
                ledger_state.schema,
            )

        expected = self._expected_refs(ledger_state)
        valuation_by_ref: dict[PortfolioValueRef, ReportingCurrencyValuation] = {}
        for valuation in valuations:
            if valuation.value_ref in valuation_by_ref:
                return self._failure(
                    SnapshotProjectionFailureCode.VALUATION_COVERAGE_MISMATCH,
                    ledger_state,
                    *(item.value_ref for item in valuations),
                )
            valuation_by_ref[valuation.value_ref] = valuation
        if set(valuation_by_ref) != expected:
            return self._failure(
                SnapshotProjectionFailureCode.VALUATION_COVERAGE_MISMATCH,
                ledger_state,
                *expected,
                *valuation_by_ref,
            )

        for valuation in valuation_by_ref.values():
            if (
                valuation.reporting_value.currency != str(reporting_currency)
                or valuation.reporting_value.scale != reporting_scale
            ):
                return self._failure(
                    SnapshotProjectionFailureCode.REPORTING_CONTEXT_MISMATCH,
                    ledger_state,
                    valuation,
                )
            path = valuation.resolution.path
            if (
                path.valuation_at != timestamp
                or path.price_purpose is not PricePurpose.VALUATION
                or path.source_currency_id
                != CurrencyId(valuation.native_value.currency)
                or path.reporting_currency_id != reporting_currency
            ):
                return self._failure(
                    SnapshotProjectionFailureCode.VALUATION_PATH_MISMATCH,
                    ledger_state,
                    valuation,
                )
            if (
                valuation.currency_valuation_graph_hash
                != currency_valuation_graph_hash
            ):
                return self._failure(
                    SnapshotProjectionFailureCode.CURRENCY_GRAPH_MISMATCH,
                    ledger_state,
                    valuation,
                )

            expected_native = self._ledger_native_value(
                ledger_state, valuation.value_ref
            )
            if expected_native is not None and valuation.native_value != expected_native:
                return self._failure(
                    SnapshotProjectionFailureCode.NATIVE_VALUE_MISMATCH,
                    ledger_state,
                    valuation,
                    expected_native,
                )

        position_marks = self._position_marks(
            ledger_state, resolved_marks, timestamp
        )
        if position_marks is None:
            return self._failure(
                SnapshotProjectionFailureCode.POSITION_MARK_MISMATCH,
                ledger_state,
                *resolved_marks,
            )

        for position in ledger_state.position_balances:
            mark = position_marks[position.key]
            market_ref = PortfolioValueRef(
                PortfolioValueKind.POSITION_MARKET_VALUE, position.key
            )
            unrealized_ref = PortfolioValueRef(
                PortfolioValueKind.UNREALIZED_PNL, position.key
            )
            market = valuation_by_ref[market_ref]
            unrealized = valuation_by_ref[unrealized_ref]
            if (
                market.native_value.currency != str(mark.quote_currency_id)
                or unrealized.native_value.currency != str(mark.quote_currency_id)
            ):
                return self._failure(
                    SnapshotProjectionFailureCode.POSITION_MARK_MISMATCH,
                    ledger_state,
                    mark,
                    market,
                    unrealized,
                )
            quantization = cast(QuantizationPolicy, market.quantization_policy)
            expected_market_value = mark.price.notional(
                position.quantity,
                result_scale=market.native_value.scale,
                rounding=quantization.rounding,
            )
            if market.native_value != expected_market_value:
                return self._failure(
                    SnapshotProjectionFailureCode.POSITION_NOTIONAL_MISMATCH,
                    ledger_state,
                    market,
                    expected_market_value,
                    mark,
                )

        required_mark_ids = {
            mark.mark_id for mark in position_marks.values()
        }
        for valuation in valuation_by_ref.values():
            required_mark_ids.update(
                edge.resolved_mark.mark_id
                for edge in valuation.resolution.path.edges
            )
        supplied_mark_ids = {mark.mark_id for mark in resolved_marks}
        if (
            len(supplied_mark_ids) != len(resolved_marks)
            or supplied_mark_ids != required_mark_ids
            or any(
                mark.resolved_at != timestamp
                or mark.price_purpose is not PricePurpose.VALUATION
                or mark.observed_at > timestamp
                for mark in resolved_marks
            )
        ):
            return self._failure(
                SnapshotProjectionFailureCode.MARK_COVERAGE_MISMATCH,
                ledger_state,
                *resolved_marks,
            )

        ordered_valuations = tuple(
            sorted(valuation_by_ref.values(), key=canonical_bytes)
        )
        mark_references = tuple(
            sorted(
                (
                    ValuationMarkReference(
                        mark.mark_id,
                        mark.instrument_id,
                        mark.price_purpose,
                        mark.observed_at,
                    )
                    for mark in resolved_marks
                ),
                key=canonical_bytes,
            )
        )
        snapshot = PortfolioSnapshot(
            account_id=next(iter(accounts)),
            timestamp=timestamp,
            reporting_currency=reporting_currency,
            cash=ledger_state.cash_balances,
            positions=ledger_state.position_balances,
            realized_pnl=self._sum_kind(
                ordered_valuations,
                PortfolioValueKind.REALIZED_PNL,
                reporting_currency,
                reporting_scale,
            ),
            unrealized_pnl=self._sum_kind(
                ordered_valuations,
                PortfolioValueKind.UNREALIZED_PNL,
                reporting_currency,
                reporting_scale,
            ),
            fees=self._sum_kind(
                ordered_valuations,
                PortfolioValueKind.FEES,
                reporting_currency,
                reporting_scale,
            ),
            financing=self._sum_kind(
                ordered_valuations,
                PortfolioValueKind.FINANCING,
                reporting_currency,
                reporting_scale,
            ),
            equity=self._sum_kinds(
                ordered_valuations,
                {
                    PortfolioValueKind.CASH,
                    PortfolioValueKind.POSITION_MARKET_VALUE,
                },
                reporting_currency,
                reporting_scale,
            ),
            valuation_marks=mark_references,
            journal_state_hash=ledger_state.state_hash,
            valuation_mark_set_hash=canonical_sha256(mark_references),
            valuation_staleness_report_hash=self._staleness_hash(resolved_marks),
            currency_valuation_graph_hash=currency_valuation_graph_hash,
        )
        return SnapshotProjectionOutcome(snapshot, None)

    @staticmethod
    def _validate_input_types(
        ledger_state: LedgerState,
        resolved_marks: tuple[ResolvedMark, ...],
        valuations: tuple[ReportingCurrencyValuation, ...],
        reporting_currency: CurrencyId,
        reporting_scale: Scale,
        timestamp: UtcInstant,
        currency_valuation_graph_hash: str,
    ) -> None:
        if not isinstance(ledger_state, LedgerState):
            raise TypeError("ledger_state must be LedgerState")
        if not isinstance(resolved_marks, tuple) or not all(
            isinstance(value, ResolvedMark) for value in resolved_marks
        ):
            raise TypeError("resolved_marks must be a tuple of ResolvedMark")
        if not isinstance(valuations, tuple) or not all(
            isinstance(value, ReportingCurrencyValuation) for value in valuations
        ):
            raise TypeError(
                "valuations must be a tuple of ReportingCurrencyValuation"
            )
        if not isinstance(reporting_currency, CurrencyId):
            raise TypeError("reporting_currency must be CurrencyId")
        if not isinstance(reporting_scale, Scale):
            raise TypeError("reporting_scale must be Scale")
        if not isinstance(timestamp, UtcInstant):
            raise TypeError("timestamp must be UtcInstant")
        _require_hash(
            "currency_valuation_graph_hash", currency_valuation_graph_hash
        )

    @staticmethod
    def _expected_refs(ledger_state: LedgerState) -> set[PortfolioValueRef]:
        refs = {
            PortfolioValueRef(PortfolioValueKind.CASH, balance.key)
            for balance in ledger_state.cash_balances
        }
        refs.update(
            PortfolioValueRef(PortfolioValueKind.REALIZED_PNL, balance.key)
            for balance in ledger_state.realized_pnl
        )
        refs.update(
            PortfolioValueRef(PortfolioValueKind.FEES, balance.key)
            for balance in ledger_state.fees
        )
        refs.update(
            PortfolioValueRef(PortfolioValueKind.FINANCING, balance.key)
            for balance in ledger_state.financing
        )
        for balance in ledger_state.position_balances:
            refs.add(
                PortfolioValueRef(
                    PortfolioValueKind.POSITION_MARKET_VALUE, balance.key
                )
            )
            refs.add(
                PortfolioValueRef(PortfolioValueKind.UNREALIZED_PNL, balance.key)
            )
        return refs

    @staticmethod
    def _position_marks(
        ledger_state: LedgerState,
        resolved_marks: tuple[ResolvedMark, ...],
        timestamp: UtcInstant,
    ) -> dict[PositionBalanceKey, ResolvedMark] | None:
        result: dict[PositionBalanceKey, ResolvedMark] = {}
        for position in ledger_state.position_balances:
            matches = tuple(
                mark
                for mark in resolved_marks
                if mark.instrument_id == position.key.instrument_id
                and mark.price_purpose is PricePurpose.VALUATION
                and mark.resolved_at == timestamp
            )
            if len(matches) != 1:
                return None
            result[position.key] = matches[0]
        return result

    @staticmethod
    def _ledger_native_value(
        ledger_state: LedgerState, value_ref: PortfolioValueRef
    ) -> Money | None:
        if not isinstance(value_ref.balance_key, CashBalanceKey):
            return None
        key = value_ref.balance_key
        if value_ref.kind is PortfolioValueKind.CASH:
            return ledger_state.cash_amount(key)
        if value_ref.kind is PortfolioValueKind.REALIZED_PNL:
            return ledger_state.realized_pnl_amount(key)
        if value_ref.kind is PortfolioValueKind.FEES:
            return ledger_state.fee_amount(key)
        if value_ref.kind is PortfolioValueKind.FINANCING:
            return ledger_state.financing_amount(key)
        return None

    @staticmethod
    def _sum_kind(
        valuations: tuple[ReportingCurrencyValuation, ...],
        kind: PortfolioValueKind,
        currency: CurrencyId,
        scale: Scale,
    ) -> Money:
        return PortfolioSnapshotProjector._sum_kinds(
            valuations, {kind}, currency, scale
        )

    @staticmethod
    def _sum_kinds(
        valuations: tuple[ReportingCurrencyValuation, ...],
        kinds: set[PortfolioValueKind],
        currency: CurrencyId,
        scale: Scale,
    ) -> Money:
        return Money(
            sum(
                valuation.reporting_value.units
                for valuation in valuations
                if valuation.value_ref.kind in kinds
            ),
            scale,
            str(currency),
        )

    @staticmethod
    def _staleness_hash(resolved_marks: tuple[ResolvedMark, ...]) -> str:
        evidence = tuple(
            sorted(
                (
                    {
                        "mark_id": mark.mark_id,
                        "age_nanoseconds": mark.age_nanoseconds,
                        "stale_policy_key": mark.stale_policy_key,
                        "stale_policy_version": mark.stale_policy_version,
                        "stale_policy_hash": mark.stale_policy_hash,
                    }
                    for mark in resolved_marks
                ),
                key=canonical_bytes,
            )
        )
        return canonical_sha256(evidence)

    @staticmethod
    def _failure(
        code: SnapshotProjectionFailureCode,
        ledger_state: LedgerState,
        *subjects: object,
    ) -> SnapshotProjectionOutcome:
        hashes = tuple(canonical_sha256(subject) for subject in subjects)
        return SnapshotProjectionOutcome(
            None,
            SnapshotProjectionFailure(code, ledger_state.state_hash, hashes),
        )
