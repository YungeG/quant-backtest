from crypto_quant_bundle_builder import BuilderStaleMarkPolicy
from crypto_quant_domain import PricePurpose, canonical_sha256
from crypto_quant_trading import StaleMarkPolicy


def test_builder_stale_mark_policy_has_exact_parity_with_kernel() -> None:
    kernel_policy = StaleMarkPolicy(
        policy_key="test.policy",
        policy_version=1,
        price_purpose=PricePurpose.VALUATION,
        max_age_nanoseconds=1000,
        allow_forward_fill=True,
    )

    builder_policy = BuilderStaleMarkPolicy(
        policy_key="test.policy",
        policy_version=1,
        price_purpose=PricePurpose.VALUATION,
        max_age_nanoseconds=1000,
        allow_forward_fill=True,
    )

    assert canonical_sha256(builder_policy) == canonical_sha256(kernel_policy)
    assert builder_policy.policy_hash == kernel_policy.policy_hash
    assert builder_policy.to_canonical_dict() == kernel_policy.to_canonical_dict()
