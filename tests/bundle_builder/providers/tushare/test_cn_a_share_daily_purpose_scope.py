from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from crypto_quant_bundle_builder import (
    BuilderStaleMarkPolicy,
    PricePurposeRequirement,
)
from crypto_quant_domain import (
    InstrumentId,
    PricePurpose,
    UtcInstant,
    VenueId,
    canonical_sha256,
)
from crypto_quant_market_data import MarketBundleCapability


ROOT = Path(__file__).parents[3]
PUBLICATION_FIXTURE = (
    ROOT
    / "fixtures/market_data/providers/tushare/cn-a-share-daily-bundle-v1.expected.json"
)
PURPOSE_SCOPE_FIXTURE = (
    ROOT
    / "fixtures/market_data/providers/tushare/cn-a-share-daily-purpose-scope-v1.expected.json"
)
STREAM_KEY = "tushare_cn_a_share.daily.publication.xshe.000001.v1"
EVENT_TYPE = "tushare_cn_a_share_daily_publication.v1"
CAPABILITY = MarketBundleCapability("tushare_cn_a_share.daily-publications", 1)
INSTRUMENT_ID = InstrumentId(VenueId("xshe"), "000001")
COVERAGE_START = UtcInstant(1_704_158_100_000_000_000)
COVERAGE_END_EXCLUSIVE = UtcInstant(1_704_178_800_000_000_000)
SOURCE_KEY = "tushare.pro.daily_listing.000001.sz.20240102"
SOURCE_HASH = "sha256:c2950a35c093b983e538f97830b7b3fcb0bba1a7dac98a17bd20f6db9296f846"


def _requirement(purpose: PricePurpose) -> PricePurposeRequirement:
    purpose_key = purpose.value.replace("_", "-")
    policy_suffix = (
        "exact-bucket"
        if purpose is PricePurpose.EXECUTION_REFERENCE
        else "exact-close"
    )
    return PricePurposeRequirement(
        requirement_key=(
            f"tushare_cn_a_share.daily.{purpose_key}.xshe.000001.20240102.v1"
        ),
        requirement_version=1,
        scope_key=(
            "tushare_cn_a_share.daily.purpose-scope.xshe.000001.20240102."
            f"{purpose_key}.v1"
        ),
        instrument_id=INSTRUMENT_ID,
        price_purpose=purpose,
        stream_key=STREAM_KEY,
        event_type=EVENT_TYPE,
        capability=CAPABILITY,
        coverage_start=COVERAGE_START,
        coverage_end_exclusive=COVERAGE_END_EXCLUSIVE,
        stale_policy=BuilderStaleMarkPolicy(
            policy_key=(
                f"tushare_cn_a_share.daily.{purpose_key}.{policy_suffix}.v1"
            ),
            policy_version=1,
            price_purpose=purpose,
            max_age_nanoseconds=0,
            allow_forward_fill=False,
        ),
        source_key=SOURCE_KEY,
        source_hash=SOURCE_HASH,
    )


def _requirements() -> tuple[PricePurposeRequirement, PricePurposeRequirement]:
    return (
        _requirement(PricePurpose.EXECUTION_REFERENCE),
        _requirement(PricePurpose.VALUATION),
    )


def _publication_purpose_binding_body(
    publication: dict[str, object],
    requirements: tuple[PricePurposeRequirement, PricePurposeRequirement],
) -> dict[str, object]:
    event = publication["event"]
    assert isinstance(event, dict)
    return {
        "type": "tushare_cn_a_share_daily_publication_purpose_binding",
        "schema_version": 1,
        "publication_event_id": event["event_id"],
        "publication_event_hash": publication["event_hash"],
        "bundle_ref": publication["bundle_ref"],
        "manifest_content_hash": publication["manifest_content_hash"],
        "stream_content_hash": publication["stream_content_hash"],
        "price_purpose_requirements": [
            {
                "price_purpose": value.price_purpose.value,
                "requirement_hash": value.requirement_hash,
            }
            for value in requirements
        ],
    }


def test_tushare_daily_purpose_scope_fixture_is_exact_and_development_only() -> None:
    expected = json.loads(PURPOSE_SCOPE_FIXTURE.read_text(encoding="utf-8"))
    requirements = _requirements()

    assert [value.to_canonical_dict() for value in requirements] == expected[
        "requirements"
    ]
    assert [value.requirement_hash for value in requirements] == expected[
        "requirement_hashes"
    ]
    assert all(value.decision_grade_eligible is False for value in requirements)
    assert all(value.deployment_authorized is False for value in requirements)
    assert all(value.stale_policy.max_age_nanoseconds == 0 for value in requirements)
    assert all(value.stale_policy.allow_forward_fill is False for value in requirements)
    assert all(value.capability.identity != "price_bars@1" for value in requirements)


def test_tushare_daily_purpose_scope_binds_only_the_passed_publication() -> None:
    expected = json.loads(PURPOSE_SCOPE_FIXTURE.read_text(encoding="utf-8"))
    publication = json.loads(PUBLICATION_FIXTURE.read_text(encoding="utf-8"))
    requirements = _requirements()
    event = publication["event"]
    bucket = event["payload"]["raw_bar"]["bucket"]
    binding_body = _publication_purpose_binding_body(publication, requirements)

    assert expected["publication_binding"] == {
        "event_id": event["event_id"],
        "event_hash": publication["event_hash"],
        "stream_key": event["stream_key"],
        "event_type": event["event_type"],
        "capability": event["capability"],
        "instrument_id": event["instrument_id"],
        "coverage_start": bucket["interval_start"],
        "coverage_end_exclusive": bucket["interval_end_exclusive"],
        "source_key": event["source_key"],
        "source_hash": event["source_hash"],
    }
    assert expected["publication_purpose_binding"] == {
        "binding_body": binding_body,
        "binding_hash": canonical_sha256(binding_body),
    }
    assert expected["qualification"] == {
        "availability_closure_complete": False,
        "revision_closure_complete": False,
        "generic_price_bars_capability": False,
        "g12i_analyzer_ready": False,
        "provider_qualified": False,
        "historical_listing_status_qualified": False,
        "corporate_actions_qualified": False,
        "decision_grade_eligible": False,
        "deployment_authorized": False,
    }


def test_publication_purpose_binding_rejects_replacement_evidence() -> None:
    expected = json.loads(PURPOSE_SCOPE_FIXTURE.read_text(encoding="utf-8"))
    publication = json.loads(PUBLICATION_FIXTURE.read_text(encoding="utf-8"))
    binding_body = _publication_purpose_binding_body(publication, _requirements())
    binding_hash = expected["publication_purpose_binding"]["binding_hash"]

    replacement_publication = deepcopy(binding_body)
    replacement_publication["publication_event_hash"] = "sha256:" + "f" * 64
    assert canonical_sha256(replacement_publication) != binding_hash

    replacement_requirement = deepcopy(binding_body)
    requirement_bindings = replacement_requirement["price_purpose_requirements"]
    assert isinstance(requirement_bindings, list)
    first, second = requirement_bindings
    assert isinstance(first, dict) and isinstance(second, dict)
    first["requirement_hash"] = second["requirement_hash"]
    assert canonical_sha256(replacement_requirement) != binding_hash
