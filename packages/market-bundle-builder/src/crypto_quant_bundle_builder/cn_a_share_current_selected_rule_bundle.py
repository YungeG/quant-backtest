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
    "sha256:4b21421bbe112d47a63ff03578dcb2215946e394d9971ab39a65c381d3d697d1"
)
_CAPABILITY = MarketBundleCapability(
    "cn_a_share.current-selected-development-rule-authorities",
    2,
)
_PHASE = TimelinePhase(0, "market_data")


def project_cn_a_share_current_selected_rule_authority_events_v2(
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

    snapshot = rebuilt["snapshot"]
    coverage = rebuilt["target_coverage"]
    authorities = rebuilt["authorities"]
    qualification = rebuilt["qualification"]
    event_time = UtcInstant(coverage["start_epoch_nanoseconds"])
    available_time = UtcInstant(
        coverage["development_evidence_available_at_epoch_nanoseconds"]
    )
    return tuple(
        MarketEvent(
            event_id=(
                "cn-a-share-current-selected-development-rule-authority-v2:"
                f"{dimension}:{authorities[dimension]['authority_hash']}"
            ),
            stream_key=(
                "cn_a_share.current_selected_development.rule_authority."
                f"{dimension}.v2"
            ),
            event_type=(
                "cn_a_share_current_selected_development_"
                f"{dimension}_authority.v2"
            ),
            capability=_CAPABILITY,
            instrument_id=None,
            event_time=event_time,
            available_time=available_time,
            phase=_PHASE,
            source_sequence=SourceSequence(index),
            revision_id=authorities[dimension]["authority_hash"],
            supersedes_revision_id=None,
            source_key=(
                "equity.cn_a_share.current-selected-development.v2/"
                f"{dimension}"
            ),
            source_hash=authorities[dimension]["canonical_body_hash"],
            payload={
                "declaration_hash": _DECLARATION_HASH,
                "snapshot_key": snapshot["snapshot_key"],
                "snapshot_version": snapshot["snapshot_version"],
                "snapshot_hash": rebuilt["snapshot_hash"],
                "target_scope": snapshot["target_scope"],
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
