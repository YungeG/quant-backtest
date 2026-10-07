"""Explicit CN portfolio MARKET DAY/GTC capability for synthetic development.

The generic capability fixture allows MARKET DAY/IOC only. B2 needs SELL GTC;
this declaration is separate and does not alter its frozen V1 behavior.
Not a broker authorization or permission to send live Orders.
"""
from __future__ import annotations

from crypto_quant_domain import ExecutionStyle, PositionEffect, TimeInForce
from crypto_quant_trading.capabilities import (
    OrderCapabilityKey, OrderCapabilitySet, OrderStyleCapability,
    PriceConstraintShape,
)


def cn_a_share_portfolio_cash_capabilities_development_v1() -> OrderCapabilitySet:
    return OrderCapabilitySet.create(
        capability_set_key="cn_a_share.portfolio.cash.development.v1",
        capability_set_version=1,
        style_capabilities=(OrderStyleCapability(
            ExecutionStyle.MARKET, (PriceConstraintShape.NONE,),
            (TimeInForce.DAY, TimeInForce.GTC)),),
        supports_reduce_only=True,
        supported_position_effects=(PositionEffect.OPEN, PositionEffect.CLOSE),
        declared_capability_keys=tuple(value.value for value in OrderCapabilityKey),
    )
