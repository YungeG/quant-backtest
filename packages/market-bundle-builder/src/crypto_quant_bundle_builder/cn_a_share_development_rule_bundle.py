from __future__ import annotations

from collections.abc import Mapping
import json

from crypto_quant_domain import (
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_market_data import MarketBundleCapability, MarketEvent


_DIMENSIONS = (
    "calendar",
    "order_rules",
    "market_fees",
    "stamp_duty",
    "corporate_action_entitlements",
)
_DECLARATION_HASH = (
    "sha256:6e0c60a75e957467a5cfe1b4e2bbbb786c463747ae96adf059c54ecef4a1b7b6"
)
_CAPABILITY = MarketBundleCapability(
    "cn_a_share.development-rule-authorities",
    1,
)
_PHASE = TimelinePhase(0, "market_data")


def project_cn_a_share_development_rule_authority_events_v1(
    declaration: Mapping[str, object],
    /,
) -> tuple[MarketEvent, ...]:
    if type(declaration) is not dict:
        raise TypeError("declaration must be exact declaration mapping")
    try:
        rebuilt = json.loads(canonical_bytes(declaration))
    except (TypeError, ValueError) as error:
        raise ValueError("declaration must contain canonical JSON values") from error
    if rebuilt != declaration:
        raise ValueError("declaration must contain exact canonical JSON values")
    if canonical_sha256(rebuilt) != _DECLARATION_HASH:
        raise ValueError("declaration authority mismatch")

    profile = rebuilt["profile"]
    coverage = rebuilt["target_coverage"]
    authorities = rebuilt["authorities"]
    qualification = rebuilt["qualification"]
    event_time = UtcInstant(coverage["start_epoch_nanoseconds"])
    available_time = UtcInstant(coverage["available_at_epoch_nanoseconds"])
    return tuple(
        MarketEvent(
            event_id=(
                "cn-a-share-development-rule-authority-v1:"
                f"{dimension}:{authorities[dimension]['authority_hash']}"
            ),
            stream_key=(
                f"cn_a_share.development.rule_authority.{dimension}.v1"
            ),
            event_type=f"cn_a_share_development_{dimension}_authority.v1",
            capability=_CAPABILITY,
            instrument_id=None,
            event_time=event_time,
            available_time=available_time,
            phase=_PHASE,
            source_sequence=SourceSequence(index),
            revision_id=authorities[dimension]["authority_hash"],
            supersedes_revision_id=None,
            source_key=f"equity.cn_a_share.v1/{dimension}",
            source_hash=authorities[dimension]["canonical_body_hash"],
            payload={
                "declaration_hash": _DECLARATION_HASH,
                "profile": profile,
                "target_coverage": coverage,
                "dimension": dimension,
                "authority_hash": authorities[dimension]["authority_hash"],
                "canonical_body_hash": authorities[dimension][
                    "canonical_body_hash"
                ],
                "authority": authorities[dimension]["body"],
                "qualification": qualification,
            },
        )
        for index, dimension in enumerate(_DIMENSIONS)
    )
