from __future__ import annotations

from copy import deepcopy
from importlib import import_module
import json
from pathlib import Path

import pytest
from crypto_quant_backtest import CnAShareProfileComposer
from crypto_quant_bundle_builder import (
    LocalMarketBundleRepository,
    LocalMarketBundleRepositoryConfig,
    validate_market_bundle_v1,
)
from crypto_quant_domain import UtcInstant, canonical_bytes, canonical_sha256
from crypto_quant_market_data import MarketEvent
from tests.support.cn_a_share import build_cn_a_share_resolved_request


ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = (
    ROOT / "fixtures/market_data/rule_authorities/cn-a-share-development-v1"
)
DECLARATION = json.loads((FIXTURE_DIR / "declaration.json").read_text())
EXPECTED_PATH = FIXTURE_DIR / "publication.expected.json"
DIMENSIONS = (
    "calendar",
    "order_rules",
    "market_fees",
    "stamp_duty",
    "corporate_action_entitlements",
)


def test_declaration_is_lossless_g08h_development_authority() -> None:
    request = build_cn_a_share_resolved_request()
    outcome = CnAShareProfileComposer().compose(request)
    assert outcome.result is not None
    profile = outcome.result.market_semantics
    authorities = {
        "calendar": (request.calendar.calendar_hash, request.calendar),
        "order_rules": (
            request.order_rule_book.rule_book_hash,
            request.order_rule_book,
        ),
        "market_fees": (
            request.market_fee_rule_book.rule_book_hash,
            request.market_fee_rule_book,
        ),
        "stamp_duty": (
            request.stamp_duty_rule_book.rule_book_hash,
            request.stamp_duty_rule_book,
        ),
        "corporate_action_entitlements": (
            request.corporate_action_rule_book.rule_book_hash,
            request.corporate_action_rule_book,
        ),
    }

    assert DECLARATION["profile"] == {
        "profile_key": profile.profile_key,
        "profile_version": profile.profile_version,
        "profile_request_hash": request.request_hash,
        "market_profile_digest": profile.profile_digest,
        "component_manifest_hash": canonical_sha256(profile.component_manifest),
        "source_manifest_hash": profile.source_manifest_hash,
    }
    assert DECLARATION["target_coverage"] == {
        "start_epoch_nanoseconds": request.timeline_window.data_start.epoch_nanoseconds,
        "end_exclusive_epoch_nanoseconds": (
            request.timeline_window.end_exclusive.epoch_nanoseconds
        ),
        "available_at_epoch_nanoseconds": request.composed_at.instant.epoch_nanoseconds,
    }
    assert set(DECLARATION["authorities"]) == set(DIMENSIONS)
    for dimension, (authority_hash, authority) in authorities.items():
        entry = DECLARATION["authorities"][dimension]
        assert canonical_bytes(entry["body"]) == canonical_bytes(authority)
        assert entry["authority_hash"] == authority_hash
        assert entry["canonical_body_hash"] == canonical_sha256(entry["body"])


def test_rule_authorities_project_five_exact_events_and_publish(tmp_path: Path) -> None:
    bundle = import_module(
        "crypto_quant_bundle_builder.cn_a_share_development_rule_bundle"
    )
    project = getattr(
        bundle,
        "project_cn_a_share_development_rule_authority_events_v1",
        None,
    )
    assert callable(project), "G12H prerequisite RED: missing rule projection"

    events = project(DECLARATION)
    expected = json.loads(EXPECTED_PATH.read_text())

    assert type(events) is tuple
    assert len(events) == 5
    assert all(type(event) is MarketEvent for event in events)
    assert json.loads(canonical_bytes(events)) == expected["events"]
    assert [event.event_hash for event in events] == expected["event_hashes"]
    declaration_hash = canonical_sha256(DECLARATION)
    coverage = DECLARATION["target_coverage"]
    for index, (dimension, event) in enumerate(zip(DIMENSIONS, events, strict=True)):
        authority = DECLARATION["authorities"][dimension]
        assert event.event_id == (
            "cn-a-share-development-rule-authority-v1:"
            f"{dimension}:{authority['authority_hash']}"
        )
        assert event.stream_key == (
            f"cn_a_share.development.rule_authority.{dimension}.v1"
        )
        assert event.event_type == (
            f"cn_a_share_development_{dimension}_authority.v1"
        )
        assert event.capability.identity == (
            "cn_a_share.development-rule-authorities@1"
        )
        assert event.instrument_id is None
        assert event.event_time == UtcInstant(coverage["start_epoch_nanoseconds"])
        assert event.available_time == UtcInstant(
            coverage["available_at_epoch_nanoseconds"]
        )
        assert event.phase.rank == 0 and event.phase.code == "market_data"
        assert event.source_sequence.value == index
        assert event.revision_id == authority["authority_hash"]
        assert event.supersedes_revision_id is None
        assert event.source_key == f"equity.cn_a_share.v1/{dimension}"
        assert event.source_hash == authority["canonical_body_hash"]
        assert canonical_bytes(event.payload) == canonical_bytes({
            "declaration_hash": declaration_hash,
            "profile": DECLARATION["profile"],
            "target_coverage": coverage,
            "dimension": dimension,
            "authority_hash": authority["authority_hash"],
            "canonical_body_hash": authority["canonical_body_hash"],
            "authority": authority["body"],
            "qualification": DECLARATION["qualification"],
        })

    validation = validate_market_bundle_v1(
        bundle_key="cn-a-share-development-rule-authorities-20260706-20260731-v1",
        schema_version=1,
        coverage_start=UtcInstant(coverage["start_epoch_nanoseconds"]),
        coverage_end_exclusive=UtcInstant(
            coverage["end_exclusive_epoch_nanoseconds"]
        ),
        instrument_catalog_hash="sha256:" + "0" * 64,
        events=events,
    )
    assert validation.failure is None and validation.manifest is not None
    manifest = validation.manifest
    assert manifest.content_hash == expected["manifest_content_hash"]
    assert canonical_sha256(manifest) == expected["manifest_hash"]
    assert {
        stream.stream_key: stream.content_hash for stream in manifest.streams
    } == expected["stream_content_hashes"]

    stream_payloads = {
        event.stream_key: canonical_bytes((event,)) for event in events
    }
    repository = LocalMarketBundleRepository(
        config=LocalMarketBundleRepositoryConfig(tmp_path.resolve())
    )
    publication = repository.publish_market_bundle_v1(
        manifest=manifest,
        stream_payloads=stream_payloads,
        retention_policy_ref=(
            "retention.g12cd-cn-a-share-development-rule-authorities-v1"
        ),
    )
    assert publication.failure is None and publication.result is not None
    assert publication.result.already_published is False
    assert publication.result.bundle_ref.to_canonical_dict() == expected["bundle_ref"]
    assert (
        publication.result.retention_proof.proof_hash
        == expected["retention_proof_hash"]
    )
    replay = repository.publish_market_bundle_v1(
        manifest=manifest,
        stream_payloads=stream_payloads,
        retention_policy_ref=(
            "retention.g12cd-cn-a-share-development-rule-authorities-v1"
        ),
    )
    assert replay.failure is None and replay.result is not None
    assert replay.result.already_published is True
    assert replay.result.bundle_ref == publication.result.bundle_ref
    assert replay.result.retention_proof == publication.result.retention_proof


@pytest.mark.parametrize(
    "mutate,match",
    (
        (
            lambda value: value.update({"extra": None}),
            "declaration authority",
        ),
        (
            lambda value: value["profile"].update(
                {"market_profile_digest": "sha256:" + "f" * 64}
            ),
            "declaration authority",
        ),
        (
            lambda value: value["target_coverage"].update(
                {"available_at_epoch_nanoseconds": 0}
            ),
            "declaration authority",
        ),
        (
            lambda value: value["authorities"].pop("market_fees"),
            "declaration authority",
        ),
        (
            lambda value: value["authorities"]["calendar"]["body"].update(
                {"calendar_id": "forged"}
            ),
            "declaration authority",
        ),
        (
            lambda value: value["qualification"].update(
                {"decision_grade_eligible": 0}
            ),
            "declaration authority",
        ),
    ),
)
def test_rule_projection_rejects_forged_declaration_without_partial_output(
    mutate,
    match: str,
) -> None:
    bundle = import_module(
        "crypto_quant_bundle_builder.cn_a_share_development_rule_bundle"
    )
    project = bundle.project_cn_a_share_development_rule_authority_events_v1
    forged = deepcopy(DECLARATION)
    mutate(forged)
    with pytest.raises((TypeError, ValueError), match=match):
        project(forged)

    with pytest.raises(TypeError, match="exact declaration mapping"):
        project(object())


def test_rule_projection_rejects_self_consistent_forged_authority_body() -> None:
    bundle = import_module(
        "crypto_quant_bundle_builder.cn_a_share_development_rule_bundle"
    )
    project = bundle.project_cn_a_share_development_rule_authority_events_v1
    forged = deepcopy(DECLARATION)
    entry = forged["authorities"]["calendar"]
    entry["body"]["calendar_id"] = "forged"
    entry["canonical_body_hash"] = canonical_sha256(entry["body"])
    with pytest.raises(ValueError, match="declaration authority"):
        project(forged)
