"""DRAFT portfolio daily NAV/MaxDD arithmetic; never accepted Backtest analysis.

Caller-declared closes and hashes are NOT independently published/qualified EOD
marks, fees, actions, or owner heads. No public metric profile is registered.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal, localcontext

from crypto_quant_domain import Money, Scale, canonical_sha256

from .analysis_derivation import _calculate_simple_period_return

_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_QUANTUM = Decimal("0.000000000000000001")
_CENT = Scale(2)


@dataclass(frozen=True, slots=True)
class DraftDailyCloseEquityV0:
    trade_date: str
    equity: Money
    external_cash_flow: Money
    ledger_state_hash: str
    close_mark_source_hash: str
    fee_source_hash: str
    action_source_hash: str
    owner_head_hash: str

    def __post_init__(self) -> None:
        if type(self.trade_date) is not str:
            raise TypeError("draft daily close date must be canonical ISO text")
        try:
            if date.fromisoformat(self.trade_date).isoformat() != self.trade_date:
                raise ValueError("noncanonical date")
        except ValueError as error:
            raise ValueError("draft daily close date invalid") from error
        if (type(self.equity) is not Money or self.equity.currency != "CNY"
                or self.equity.scale != _CENT or self.equity.units <= 0
                or type(self.external_cash_flow) is not Money
                or self.external_cash_flow.currency != "CNY"
                or self.external_cash_flow.scale != _CENT
                or self.external_cash_flow.units != 0):
            raise ValueError("draft NAV requires positive CNY equity and no external flows")
        for value in (self.ledger_state_hash, self.close_mark_source_hash,
                      self.fee_source_hash, self.action_source_hash, self.owner_head_hash):
            if type(value) is not str or _HASH.fullmatch(value) is None:
                raise ValueError("draft daily close needs exact source-hash syntax")

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "draft_cn_portfolio_daily_close_equity", "schema_version": 0,
                "trade_date": self.trade_date, "equity": self.equity,
                "external_cash_flow": self.external_cash_flow,
                "ledger_state_hash": self.ledger_state_hash,
                "close_mark_source_hash": self.close_mark_source_hash,
                "fee_source_hash": self.fee_source_hash,
                "action_source_hash": self.action_source_hash,
                "owner_head_hash": self.owner_head_hash,
                "source_qualification_verified": False}


@dataclass(frozen=True, slots=True)
class DraftPortfolioDailyNavMetricProfileV0:
    """A diagnostic contract, NOT BacktestMetricProfile@2 or a publication ref."""

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "draft_cn_portfolio_daily_nav_metric_profile",
                "schema_version": 0, "drawdown_sampling": "each_declared_trading_close",
                "starting_equity_is_initial_peak": True,
                "external_cash_flow_policy": "reject_after_initial_funding",
                "maximum_fractional_digits": 18, "rounding": "half_even",
                "source_qualification_verified": False,
                "validation_eligible": False}


@dataclass(frozen=True, slots=True)
class DraftPortfolioDailyNavMetricsV0:
    profile: DraftPortfolioDailyNavMetricProfileV0
    observed_dates: tuple[str, ...]
    source_hash: str
    simple_period_return: str
    maximum_drawdown: str
    source_qualification_verified: bool = field(default=False, init=False)
    validation_eligible: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if (type(self.profile) is not DraftPortfolioDailyNavMetricProfileV0
                or type(self.observed_dates) is not tuple or not self.observed_dates
                or type(self.source_hash) is not str or _HASH.fullmatch(self.source_hash) is None
                or type(self.simple_period_return) is not str
                or type(self.maximum_drawdown) is not str):
            raise ValueError("draft portfolio metrics identity incomplete")

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "draft_cn_portfolio_daily_nav_metrics", "schema_version": 0,
                "profile": self.profile, "observed_dates": self.observed_dates,
                "source_hash": self.source_hash,
                "simple_period_return": self.simple_period_return,
                "maximum_drawdown": self.maximum_drawdown,
                "source_qualification_verified": False, "validation_eligible": False}


def derive_draft_cn_portfolio_daily_nav_v0(
    *, initial_equity: Money, expected_trading_dates: tuple[str, ...],
    observations: tuple[DraftDailyCloseEquityV0, ...],
) -> DraftPortfolioDailyNavMetricsV0:
    """Freeze arithmetic only. Any real performance claim needs verified Backtest publication."""
    if (type(initial_equity) is not Money or initial_equity.currency != "CNY"
            or initial_equity.scale != _CENT or initial_equity.units <= 0
            or type(expected_trading_dates) is not tuple or not expected_trading_dates
            or type(observations) is not tuple or not observations
            or any(type(obs) is not DraftDailyCloseEquityV0 for obs in observations)):
        raise ValueError("draft NAV requires a positive CNY initial peak and typed full close series")
    actual = tuple(obs.trade_date for obs in observations)
    if actual != expected_trading_dates or actual != tuple(sorted(set(actual))):
        raise ValueError("draft NAV daily observation dates must exact-cover ordered calendar")
    with localcontext() as context:
        context.prec = max(len(str(initial_equity.units)),
                           *(len(str(obs.equity.units)) for obs in observations)) + 50
        context.rounding = ROUND_HALF_EVEN
        peak = Decimal(initial_equity.units)
        maximum = Decimal(0)
        for obs in observations:
            value = Decimal(obs.equity.units)
            peak = max(peak, value)
            maximum = max(maximum, (peak - value) / peak)
        maximum = maximum.quantize(_QUANTUM, rounding=ROUND_HALF_EVEN)
    maximum_text = format(maximum, "f").rstrip("0").rstrip(".") if maximum else "0"
    returned = _calculate_simple_period_return(initial_equity, observations[-1].equity, ())
    if returned is None:
        raise ValueError("draft NAV source failed accepted simple-return policy")
    return DraftPortfolioDailyNavMetricsV0(
        DraftPortfolioDailyNavMetricProfileV0(), actual,
        canonical_sha256({"initial_equity": initial_equity,
                          "expected_trading_dates": expected_trading_dates,
                          "observations": observations}), returned, maximum_text)
