"""Versioned A-share portfolio order-lifetime declaration; not an Order planner.

The old single-TimeInForce RebalancePolicy and its canonical bytes remain intact.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from crypto_quant_domain import OrderSide, TimeInForce, canonical_sha256

_KEY = re.compile(r"[a-z][a-z0-9._-]*\Z")


def _payload(key: str) -> dict[str, object]:
    return {
        "type": "cn_a_share_portfolio_execution_policy_config", "schema_version": 1,
        "policy_key": key, "policy_version": 1,
        "sell_time_in_force": TimeInForce.GTC.value,
        "buy_time_in_force": TimeInForce.DAY.value,
        "sells_before_buys": True,
        "buy_funding": "settled_unreserved_cash_after_fees",
        "blocked_sell": "retain_until_filled_expired_or_superseded",
        "failed_buy": "expire_day_leave_cash",
        "next_target": "cancel_or_supersede_old_working_orders",
    }


@dataclass(frozen=True, slots=True)
class CnAShareRebalanceExecutionPolicyV1:
    policy_key: str
    policy_version: int
    config_hash: str

    def __post_init__(self) -> None:
        if type(self.policy_key) is not str or _KEY.fullmatch(self.policy_key) is None:
            raise ValueError("policy_key must be canonical")
        if type(self.policy_version) is not int or self.policy_version != 1:
            raise ValueError("portfolio execution policy version must be 1")
        if type(self.config_hash) is not str or self.config_hash != canonical_sha256(_payload(self.policy_key)):
            raise ValueError("portfolio execution policy config_hash mismatch")

    @classmethod
    def create(cls, policy_key: str) -> CnAShareRebalanceExecutionPolicyV1:
        return cls(policy_key, 1, canonical_sha256(_payload(policy_key)))

    def config_payload(self) -> dict[str, object]:
        return _payload(self.policy_key)

    @property
    def policy_hash(self) -> str:
        return canonical_sha256(self)

    def time_in_force_for(self, side: OrderSide) -> TimeInForce:
        if type(side) is not OrderSide:
            raise TypeError("side must be exact OrderSide")
        return TimeInForce.GTC if side is OrderSide.SELL else TimeInForce.DAY

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self.config_payload(), "type": "cn_a_share_portfolio_execution_policy",
                "config_hash": self.config_hash}
