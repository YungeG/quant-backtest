"""B2 canonical policy only; does not execute CN portfolio orders or fills."""
from dataclasses import replace

import pytest

from crypto_quant_domain import OrderSide, TimeInForce, canonical_sha256
from crypto_quant_trading.profiles.cn_a_share.portfolio_rebalance_policy_v1 import (
    CnAShareRebalanceExecutionPolicyV1,
)


def test_sell_gtc_buy_day_cash_and_supersession_are_exact_canonical_policy():
    policy = CnAShareRebalanceExecutionPolicyV1.create("cn.pharma.weekly")
    assert policy.time_in_force_for(OrderSide.SELL) is TimeInForce.GTC
    assert policy.time_in_force_for(OrderSide.BUY) is TimeInForce.DAY
    body = policy.to_canonical_dict()
    assert body["type"] == "cn_a_share_portfolio_execution_policy"
    assert body["sells_before_buys"] is True
    assert body["buy_funding"] == "settled_unreserved_cash_after_fees"
    assert body["blocked_sell"] == "retain_until_filled_expired_or_superseded"
    assert body["failed_buy"] == "expire_day_leave_cash"
    assert body["next_target"] == "cancel_or_supersede_old_working_orders"
    assert policy.config_hash == canonical_sha256(policy.config_payload())
    assert policy.policy_hash == canonical_sha256(policy)
    assert policy.config_hash == "sha256:68317e89860b70380d25de8f417c76c4d10740ed749a0f701f96a5ece9614687"
    assert policy.policy_hash == "sha256:747ee7119230faf9e72d98de904a2db7c9a45b724e651edc08aa2f642b72525e"
    assert CnAShareRebalanceExecutionPolicyV1.create("cn.pharma.weekly") == policy
    assert CnAShareRebalanceExecutionPolicyV1.create("cn.pharma.other").policy_hash != policy.policy_hash


@pytest.mark.parametrize("key", ("", " bad", "BAD", "cash/simulator"))
def test_invalid_key_rejected_without_coercion(key):
    with pytest.raises(ValueError, match="policy_key"):
        CnAShareRebalanceExecutionPolicyV1.create(key)


def test_tampered_config_version_or_wrong_side_fails():
    policy = CnAShareRebalanceExecutionPolicyV1.create("cn.pharma.weekly")
    with pytest.raises(ValueError, match="config_hash"):
        replace(policy, config_hash="sha256:" + "0" * 64)
    with pytest.raises(ValueError, match="version"):
        replace(policy, policy_version=2)
    with pytest.raises(TypeError, match="OrderSide"):
        policy.time_in_force_for("buy")  # type: ignore[arg-type]
