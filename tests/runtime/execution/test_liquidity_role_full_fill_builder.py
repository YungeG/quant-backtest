from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from typing import cast

import pytest
from crypto_quant_backtest import (
    FullFillBuilder,
    FullFillConstructionFailure,
    FullFillResult,
    LiquidityRoleFullFillBuilder,
)
from crypto_quant_domain import Quantity, canonical_sha256

from tests.runtime.execution._fixtures import (
    candidate,
    fill_id,
    model,
    request,
    slippage_model,
    slippage_request,
)

_EXISTING_FILL_HASH = "sha256:1cc8fca17f0dff81f3c14929f4e0b7ad8b826932415e62180b16364c9d396a87"
_EXISTING_RESULT_HASH = "sha256:ef2402f16d5190f775ac6da1c125b1cf53df66f4d203034e892e1b44ba454503"
_TAKER_FILL_HASH = "sha256:c9b66eee4ef69d1982ccfc2964cc16d91a4096882366bf4152b25c4810ec3214"
_TAKER_RESULT_HASH = "sha256:059c41a0dbb56a76e42f36a8803b94d7fa90aa8a323c202ae1bd405d95a84693"


def _inputs():
    execution = model().simulate_execution(request(bar_candidate=candidate()))
    assert execution.result is not None
    decision = execution.result
    slippage = slippage_model(decision).decide_slippage(slippage_request(decision))
    return decision, slippage, fill_id()


def test_role_builder_preserves_economics_and_changes_identity_deterministically() -> None:
    decision, slippage, identity = _inputs()

    existing = FullFillBuilder().build(
        decision=decision,
        slippage_outcome=slippage,
        fill_id=identity,
    )
    builder = LiquidityRoleFullFillBuilder("taker")
    taker = builder.build(
        decision=decision,
        slippage_outcome=slippage,
        fill_id=identity,
    )
    replay = builder.build(
        decision=decision,
        slippage_outcome=slippage,
        fill_id=identity,
    )

    assert isinstance(existing, FullFillResult)
    assert isinstance(taker, FullFillResult)
    assert isinstance(replay, FullFillResult)
    assert existing.fill.liquidity == "full"
    assert canonical_sha256(existing.fill) == _EXISTING_FILL_HASH
    assert existing.result_hash == _EXISTING_RESULT_HASH
    assert taker.fill.liquidity == "taker"
    assert replace(taker.fill, liquidity="full") == existing.fill
    assert taker.decision == existing.decision
    assert taker.slippage_decision == existing.slippage_decision
    assert canonical_sha256(taker.fill) == _TAKER_FILL_HASH
    assert taker.result_hash == _TAKER_RESULT_HASH
    assert canonical_sha256(taker.fill) != canonical_sha256(existing.fill)
    assert taker.result_hash != existing.result_hash
    assert replay == taker
    assert canonical_sha256(replay.fill) == canonical_sha256(taker.fill)
    assert replay.result_hash == taker.result_hash


def test_role_builder_propagates_existing_failure_identity() -> None:
    decision, _, identity = _inputs()
    slippage = slippage_model(decision)
    failed_slippage = slippage.decide_slippage(
        replace(
            slippage_request(decision),
            quantity=Quantity(
                decision.fill_quantity.units + 1,
                decision.fill_quantity.scale,
                decision.fill_quantity.instrument_id,
            ),
        )
    )

    existing = FullFillBuilder().build(
        decision=decision,
        slippage_outcome=failed_slippage,
        fill_id=identity,
    )
    wrapped = LiquidityRoleFullFillBuilder("taker").build(
        decision=decision,
        slippage_outcome=failed_slippage,
        fill_id=identity,
    )

    assert isinstance(existing, FullFillConstructionFailure)
    assert isinstance(wrapped, FullFillConstructionFailure)
    assert wrapped == existing
    assert wrapped.code is existing.code
    assert wrapped.failure_id == existing.failure_id


def test_role_builder_accepts_only_frozen_maker_or_taker_roles() -> None:
    decision, slippage, identity = _inputs()
    maker_builder = LiquidityRoleFullFillBuilder("maker")
    maker = maker_builder.build(
        decision=decision,
        slippage_outcome=slippage,
        fill_id=identity,
    )

    assert isinstance(maker, FullFillResult)
    assert maker.fill.liquidity == "maker"
    with pytest.raises(FrozenInstanceError):
        setattr(maker_builder, "liquidity_role", "taker")
    with pytest.raises(ValueError, match="maker or taker"):
        LiquidityRoleFullFillBuilder("full")
    with pytest.raises(TypeError, match="must be str"):
        LiquidityRoleFullFillBuilder(cast(str, None))
