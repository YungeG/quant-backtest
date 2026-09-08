from __future__ import annotations

from copy import deepcopy
from dataclasses import fields, replace
from datetime import datetime
from hashlib import sha256
from importlib import import_module
import json
from pathlib import Path
from typing import Any

import pytest
from crypto_quant_bundle_builder import (
    LocalMarketBundleRepository,
    LocalMarketBundleRepositoryConfig,
    validate_market_bundle_v1,
)
from crypto_quant_domain import (
    Rate,
    Scale,
    UtcInstant,
    VenueId,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_market_data import MarketEvent
from crypto_quant_trading.profiles.cn_a_share import (
    CnAShareExecutionAccessRoute,
    CnAShareFeeProductClass,
    CnAShareFeeRuleSourceRef,
    CnAShareMarketFeeBandV2,
    CnAShareMarketFeeRuleBookV2,
    CnAShareStampDutyBandV2,
    CnAShareStampDutyRuleBookV2,
)


ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = (
    ROOT
    / "fixtures/market_data/rule_authorities/"
    "cn-a-share-current-selected-development-v2"
)
V1_FIXTURE_DIR = (
    ROOT / "fixtures/market_data/rule_authorities/cn-a-share-development-v1"
)
SNAPSHOT = json.loads((FIXTURE_DIR / "snapshot.json").read_text())
DECLARATION = json.loads((FIXTURE_DIR / "declaration.json").read_text())
EXPECTED = json.loads((FIXTURE_DIR / "publication.expected.json").read_text())
DIMENSIONS = (
    "calendar",
    "order_rules",
    "market_fees",
    "stamp_duty",
    "corporate_action_entitlements",
)
LINEAGES = (
    "exchange_handling",
    "securities_regulatory",
    "chinaclear_transfer",
    "hkscc_transfer",
    "stamp_duty",
)
START = 1783267200000000000
END = 1785427200000000000
QUALIFICATION = {
    "official_successor_closure_complete": False,
    "provider_authority_qualified": False,
    "provider_completeness_qualified": False,
    "rule_coverage_qualified": False,
    "decision_grade_eligible": False,
    "live_eligible": False,
    "deployment_authorized": False,
    "development_projection_authorized": True,
}
ECONOMICS = {
    "exchange_handling": (True, 341, 7, True, True),
    "securities_regulatory": (True, 2, 5, True, True),
    "chinaclear_transfer": (True, 1, 5, True, True),
    "hkscc_transfer": (False, 0, 0, False, False),
    "stamp_duty": (True, 5, 4, False, True),
}
INVENTORY_HASHES = {
    "exchange_handling": "sha256:e3171077dd5984a328bd708a98d62409523b3f35665ff16ca9328c75d60a346e",
    "securities_regulatory": "sha256:a38bce21f55877dd67ac526d580f4639853c0b460f8839f2f08a066351982598",
    "chinaclear_transfer": "sha256:2cfc94559bea753d3cce3484b68515f14bd945764d0b732fe284b8fe2f9094fb",
    "hkscc_transfer": "sha256:c490d2a566270ad3b1fed4027d7b33bbb72b9a4c6b848db66b52a246f42f9aa5",
    "stamp_duty": "sha256:811e2cb1e84021b19a9be7e9363d4e986b13be81c2dd11365c44d3069fe09b92",
}
STATUS_ASSESSMENT = {
    "path": "evidence/g12h-register-discovery-v1/analysis/status-register-assessment.json",
    "sha256": "sha256:57a3a3aa7c5cb75eb2d2f347a64f54a267ecc6ea4c872e9e0029ee89068fa0fc",
    "purpose": "identifies result-affecting material candidates",
}
LIVE_ASSESSMENT = {
    "path": "evidence/g12h-live-status-api-probes-v1/analysis/live-status-api-probe-assessment.json",
    "sha256": "sha256:cf1b6b25192dd83652af8b96aca0424082fd3e22afd1a11cceaa585a67be80cf",
    "purpose": "identifies result-affecting material candidates",
}
EXPECTED_CANDIDATES = {
    "exchange_handling": {
        "szse-current-fee-table-2026-01": (
            "selected",
            {
                "szse-fee-selector-json-live",
                "szse-fee-document-2026-01-json-live",
                "szse-fee-document-2026-01-html-live",
            },
        ),
        "szse-notice-2023-768": (
            "before_target_already_represented",
            {"szse-notice-2023-768-json", "szse-notice-2023-768-html"},
        ),
    },
    "securities_regulatory": {
        "ndrc-000": (
            "selected",
            {
                "ndrc-2018-917",
                "ndrc-query-ndrc-2018-917-exact-page-1",
                "ndrc-query-ndrc-2018-917-exact-terminal-page-2",
                "ndrc-query-securities-business-regulatory-fee-page-1",
                "ndrc-query-securities-business-regulatory-fee-terminal-page-2",
                "ndrc-query-securities-futures-regulatory-fee-page-1",
                "ndrc-query-securities-futures-regulatory-fee-terminal-page-2",
                "ndrc-query-securities-transaction-regulatory-fee-page-1",
                "ndrc-query-securities-transaction-regulatory-fee-terminal-page-2",
            },
        ),
        "ndrc-001": (
            "no_economic_effect",
            {
                "ndrc-2021-1947",
                "ndrc-query-securities-business-regulatory-fee-page-1",
                "ndrc-query-securities-business-regulatory-fee-terminal-page-2",
                "ndrc-query-securities-futures-regulatory-fee-page-1",
                "ndrc-query-securities-futures-regulatory-fee-terminal-page-2",
                "ndrc-query-securities-transaction-regulatory-fee-page-1",
                "ndrc-query-securities-transaction-regulatory-fee-terminal-page-2",
            },
        ),
        "ndrc-002": (
            "before_target_already_represented",
            {
                "ndrc-query-securities-futures-regulatory-fee-page-1",
                "ndrc-query-securities-futures-regulatory-fee-terminal-page-2",
            },
        ),
        "ndrc-003": (
            "before_target_already_represented",
            {
                "ndrc-query-securities-futures-regulatory-fee-page-1",
                "ndrc-query-securities-futures-regulatory-fee-terminal-page-2",
                "ndrc-query-securities-transaction-regulatory-fee-page-1",
                "ndrc-query-securities-transaction-regulatory-fee-terminal-page-2",
            },
        ),
        "ndrc-004": (
            "before_target_already_represented",
            {
                "ndrc-query-securities-transaction-regulatory-fee-page-1",
                "ndrc-query-securities-transaction-regulatory-fee-terminal-page-2",
            },
        ),
        "ndrc-005": (
            "before_target_already_represented",
            {
                "ndrc-query-securities-transaction-regulatory-fee-page-1",
                "ndrc-query-securities-transaction-regulatory-fee-terminal-page-2",
            },
        ),
        "szse-current-regulatory-collection-table-2026-01": (
            "selected",
            {
                "szse-fee-selector-json-live",
                "szse-fee-document-2026-01-json-live",
                "szse-fee-document-2026-01-html-live",
            },
        ),
    },
    "chinaclear_transfer": {
        "chinaclear-current-szse-fee-table-2025-12": (
            "selected",
            {
                "chinaclear-fee-standard-parent-live",
                "chinaclear-fee-standard-iframe-live",
                "chinaclear-szse-fee-table-2025-12-pdf",
            },
        ),
        "chinaclear-stock-transfer-notice-2022": (
            "before_target_already_represented",
            {"chinaclear-stock-transfer-notice-2022"},
        ),
    },
    "hkscc_transfer": {
        "hkscc-current-operational-procedures": (
            "selected",
            {
                "hkscc-operational-procedures-index-live",
                "hkscc-operational-procedures-definitions-live",
                "hkscc-operational-procedures-sec21-live",
            },
        ),
        "hkscc-019-2025": (
            "before_target_already_represented",
            {"hkscc-circular-019-2025", "hkscc-rule-update-019-2025"},
        ),
        "hkscc-022-2025": (
            "no_economic_effect",
            {"hkscc-rule-update-022-2025-stmc-markup"},
        ),
        "hkscc-038-2025": (
            "no_economic_effect",
            {"hkscc-circular-038-2025", "hkscc-rule-update-038-2025-markup"},
        ),
        "hkscc-100-2026-usm": (
            "prospective_not_implemented",
            {"hkscc-circular-100-2026-usm"},
        ),
        "hkscc-dps-005-2026-usm": (
            "prospective_not_implemented",
            {"hkscc-circular-dps-005-2026-usm"},
        ),
        "hkscc-usm-draft-operational-procedures-2026": (
            "prospective_not_implemented",
            {"hkscc-usm-page-live", "hkscc-usm-draft-op-markup-2026"},
        ),
    },
    "stamp_duty": {
        "mof-announcement-2023-39": (
            "selected",
            {"mof-announcement-2023-39"},
        ),
        "npc-stamp-duty-law-current-status": (
            "selected",
            {
                "npc-stamp-duty-law-current-status-search",
                "npc-stamp-duty-law-current-status-detail",
            },
        ),
        "sta-no39-status-full-valid-live": (
            "no_economic_effect",
            {"sta-no39-status-full-valid-live"},
        ),
        "sta-no39-status-invalid-live": (
            "no_economic_effect",
            {"sta-no39-status-invalid-live"},
        ),
        "sta-no39-status-modified-live": (
            "no_economic_effect",
            {"sta-no39-status-modified-live"},
        ),
        "sta-no39-status-not-yet-effective-live": (
            "no_economic_effect",
            {"sta-no39-status-not-yet-effective-live"},
        ),
        "sta-no39-status-repealed-live": (
            "no_economic_effect",
            {"sta-no39-status-repealed-live"},
        ),
        "sta-no39-status-unfiltered-live": (
            "selected",
            {"sta-no39-status-unfiltered-live"},
        ),
    },
}
EXPECTED_SOURCE_IDS = {
    "exchange_handling": {
        "szse-fee-selector-json-live",
        "szse-fee-document-2026-01-json-live",
        "szse-fee-document-2026-01-html-live",
        "szse-notice-2023-768-json",
        "szse-notice-2023-768-html",
    },
    "securities_regulatory": {
        "ndrc-2018-917",
        "ndrc-2021-1947",
        "ndrc-query-ndrc-2018-917-exact-page-1",
        "ndrc-query-ndrc-2018-917-exact-terminal-page-2",
        "ndrc-query-securities-business-regulatory-fee-page-1",
        "ndrc-query-securities-business-regulatory-fee-terminal-page-2",
        "ndrc-query-securities-futures-regulatory-fee-page-1",
        "ndrc-query-securities-futures-regulatory-fee-terminal-page-2",
        "ndrc-query-securities-transaction-regulatory-fee-page-1",
        "ndrc-query-securities-transaction-regulatory-fee-terminal-page-2",
        "szse-fee-selector-json-live",
        "szse-fee-document-2026-01-json-live",
        "szse-fee-document-2026-01-html-live",
    },
    "chinaclear_transfer": {
        "chinaclear-fee-standard-parent-live",
        "chinaclear-fee-standard-iframe-live",
        "chinaclear-szse-fee-table-2025-12-pdf",
        "chinaclear-stock-transfer-notice-2022",
    },
    "hkscc_transfer": {
        "hkscc-operational-procedures-index-live",
        "hkscc-operational-procedures-definitions-live",
        "hkscc-operational-procedures-sec21-live",
        "hkscc-rule-update-index-live",
        "hkscc-circular-019-2025",
        "hkscc-rule-update-019-2025",
        "hkscc-rule-update-022-2025-stmc-markup",
        "hkscc-circular-038-2025",
        "hkscc-rule-update-038-2025-markup",
        "hkscc-circular-100-2026-usm",
        "hkscc-circular-dps-005-2026-usm",
        "hkscc-usm-page-live",
        "hkscc-usm-draft-op-markup-2026",
    },
    "stamp_duty": {
        "npc-stamp-duty-law-current-status-search",
        "npc-stamp-duty-law-current-status-detail",
        "mof-announcement-2023-39",
        "sta-no39-status-unfiltered-live",
        "sta-no39-status-full-valid-live",
        "sta-no39-status-modified-live",
        "sta-no39-status-invalid-live",
        "sta-no39-status-repealed-live",
        "sta-no39-status-not-yet-effective-live",
    },
}
ALLOWED_DISPOSITIONS = {
    "selected",
    "no_economic_effect",
    "before_target_already_represented",
    "after_target",
    "prospective_not_implemented",
}


def _file_hash(path: Path) -> str:
    return "sha256:" + sha256(path.read_bytes()).hexdigest()


def _epoch_nanoseconds(value: str) -> int:
    instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return int(instant.timestamp()) * 1_000_000_000 + instant.microsecond * 1_000


def _contains_key(value: object, key: str) -> bool:
    if isinstance(value, dict):
        return key in value or any(_contains_key(item, key) for item in value.values())
    if isinstance(value, list):
        return any(_contains_key(item, key) for item in value)
    return False


def _assert_snapshot(snapshot: dict[str, Any]) -> None:
    assert list(snapshot) == [
        "candidate_disposition_policy",
        "components",
        "development_evidence_available_at",
        "economics",
        "limitations",
        "qualification",
        "schema_version",
        "semantics_id",
        "snapshot_key",
        "snapshot_version",
        "target_from",
        "target_scope",
        "target_to_exclusive",
        "type",
    ]
    assert snapshot["type"] == (
        "cn_a_share_current_selected_development_authority_snapshot"
    )
    assert snapshot["schema_version"] == snapshot["snapshot_version"] == 1
    assert snapshot["semantics_id"] == "current-official-selection-development.v1"
    assert snapshot["target_from"] == START
    assert snapshot["target_to_exclusive"] == END
    assert snapshot["target_scope"] == {
        "access_route": "DOMESTIC",
        "basis": "trade_notional",
        "board_ids": ["main"],
        "fee_product_class": "ORDINARY_A_SHARE",
        "instrument_type": "EQUITY",
        "quote_currency": "CNY",
        "settlement_currency": "CNY",
        "trade_mechanism": "AUCTION",
        "venue": "XSHE",
    }
    assert snapshot["qualification"] == QUALIFICATION
    assert snapshot["candidate_disposition_policy"] == {
        "corpus_completeness_required": False,
        "corpus_completeness_waiver": "ADR-0007 current-selected development",
        "inventory_row_semantics": "discovery_entry_not_candidate_disposition",
        "material_candidate_rule": (
            "every result-affecting material candidate identified by the frozen "
            "assessments is individually dispositioned"
        ),
    }
    assert not _contains_key(snapshot, "official_record_as_of")
    assert "official_record_as_of" not in canonical_bytes(snapshot).decode()

    components = snapshot["components"]
    assert [component["lineage"] for component in components] == list(LINEAGES)
    observed_at = []
    for component in components:
        lineage = component["lineage"]
        inventory = component["discovery_inventory"]
        inventory_path = f"evidence/g12h/{lineage}/candidate-inventory.discovery.json"
        assert inventory == {
            "path": inventory_path,
            "purpose": (
                "raw rows are broad discovery entries, not candidate dispositions"
            ),
            "sha256": INVENTORY_HASHES[lineage],
        }
        assert _file_hash(ROOT.parent / inventory_path) == INVENTORY_HASHES[lineage]
        expected_assessments = [STATUS_ASSESSMENT]
        if lineage in {"exchange_handling", "stamp_duty"}:
            expected_assessments.append(LIVE_ASSESSMENT)
        assert component["assessment_refs"] == expected_assessments
        for assessment in component["assessment_refs"]:
            assert _file_hash(ROOT.parent / assessment["path"]) == assessment["sha256"]

        sources = component["sources"]
        source_ids = {source["source_id"] for source in sources}
        assert source_ids == EXPECTED_SOURCE_IDS[lineage]
        dispositions = component["candidate_dispositions"]
        assert dispositions == sorted(dispositions, key=lambda item: item["candidate_id"])
        actual_candidates = {
            item["candidate_id"]: (
                item["disposition"],
                set(item["evidence_source_ids"]),
            )
            for item in dispositions
        }
        assert actual_candidates == EXPECTED_CANDIDATES[lineage]
        if lineage == "securities_regulatory":
            assert component["candidate_disposition_basis"] == (
                "2018 No.917 expressly replaces the 2016 authority; ndrc-002 "
                "through ndrc-005 are predecessor rate history already represented "
                "by the selected 917 state for this finite development snapshot"
            )
            assert {
                candidate_id: actual_candidates[candidate_id][0]
                for candidate_id in (
                    "ndrc-000",
                    "ndrc-001",
                    "ndrc-002",
                    "ndrc-003",
                    "ndrc-004",
                    "ndrc-005",
                )
            } == {
                "ndrc-000": "selected",
                "ndrc-001": "no_economic_effect",
                "ndrc-002": "before_target_already_represented",
                "ndrc-003": "before_target_already_represented",
                "ndrc-004": "before_target_already_represented",
                "ndrc-005": "before_target_already_represented",
            }
        else:
            assert "candidate_disposition_basis" not in component
        assert all(
            item["evidence_source_ids"] == sorted(item["evidence_source_ids"])
            for item in dispositions
        )
        actual_dispositions = {
            candidate_id: value[0]
            for candidate_id, value in actual_candidates.items()
        }
        assert set(actual_dispositions.values()) <= ALLOWED_DISPOSITIONS
        assert "unresolved" not in actual_dispositions.values()
        assert set(actual_dispositions) != source_ids
        assert set(actual_dispositions.values()) != {"selected"}
        assert set().union(
            *(evidence_ids for _, evidence_ids in actual_candidates.values())
        ) <= source_ids
        for source in sources:
            raw_path = ROOT.parent / source["evidence_path"]
            receipt_path = ROOT.parent / source["receipt_path"]
            headers_path = ROOT.parent / source["response_headers_path"]
            redirects_path = ROOT.parent / source["redirect_chain_path"]
            receipt = json.loads(receipt_path.read_text())
            assert _file_hash(raw_path) == source["raw_sha256"]
            assert _file_hash(receipt_path) == source["receipt_sha256"]
            assert _file_hash(headers_path) == source["response_headers_sha256"]
            assert _file_hash(redirects_path) == source["redirect_chain_sha256"]
            assert receipt["raw_sha256"] == source["raw_sha256"]
            assert receipt["final_url"] == source["source_url"]
            assert receipt["retrieved_at"] == source["observed_at"]
            observed_at.append(source["observed_at"])
    assert snapshot["development_evidence_available_at"] == max(
        _epoch_nanoseconds(value) for value in observed_at
    )
    assert snapshot["development_evidence_available_at"] == 1787218900204605000
    assert max(observed_at) == "2026-08-20T09:41:40.204605Z"

    economics = snapshot["economics"]
    assert set(economics) == set(LINEAGES)
    for lineage, (applies, units, scale, buy, sell) in ECONOMICS.items():
        value = economics[lineage]
        assert value["basis"] == "trade_notional"
        assert (value["applies"], value["buy"], value["sell"]) == (
            applies,
            buy,
            sell,
        )
        assert value["rate"] == {
            "basis": "fee_fraction",
            "scale": scale,
            "units": units,
        }
        assert value["source_ref"]["source_key"]
        assert value["source_ref"]["source_hash"] == canonical_sha256(
            value["source_semantics"]
        )
        assert value["source_semantics"] == {
            "applies": applies,
            "assessment_basis": "trade_notional",
            "buy": buy,
            "lineage": lineage,
            "rate": value["rate"],
            "sell": sell,
            "semantics_id": "cn-a-share-finite-target-economic-authority.v1",
            "target_from": START,
            "target_scope": snapshot["target_scope"],
            "target_to_exclusive": END,
        }
    hkscc = economics["hkscc_transfer"]
    assert hkscc["applies"] is False
    assert hkscc["rate"] == {"basis": "fee_fraction", "scale": 0, "units": 0}
    assert hkscc["source_ref"]["source_key"]


def _source_ref(lineage: str) -> CnAShareFeeRuleSourceRef:
    value = SNAPSHOT["economics"][lineage]["source_ref"]
    return CnAShareFeeRuleSourceRef(value["source_key"], value["source_hash"])


def _rule_books() -> tuple[CnAShareMarketFeeRuleBookV2, CnAShareStampDutyRuleBookV2]:
    market = CnAShareMarketFeeRuleBookV2(
        "equity.cn_a_share.cash.market-fees.domestic.ordinary-a-share."
        "current-selected-development.v2",
        2,
        CnAShareExecutionAccessRoute.DOMESTIC,
        CnAShareFeeProductClass.ORDINARY_A_SHARE,
        (
            CnAShareMarketFeeBandV2(
                VenueId("xshe"),
                UtcInstant(START),
                UtcInstant(END),
                True,
                Rate(341, Scale(7), "fee_fraction"),
                (_source_ref("exchange_handling"),),
                True,
                Rate(2, Scale(5), "fee_fraction"),
                (_source_ref("securities_regulatory"),),
                True,
                Rate(1, Scale(5), "fee_fraction"),
                (_source_ref("chinaclear_transfer"),),
                False,
                Rate(0, Scale(0), "fee_fraction"),
                (_source_ref("hkscc_transfer"),),
            ),
        ),
    )
    stamp = CnAShareStampDutyRuleBookV2(
        "equity.cn_a_share.cash.stamp-duty.domestic.ordinary-a-share."
        "current-selected-development.v2",
        2,
        CnAShareExecutionAccessRoute.DOMESTIC,
        CnAShareFeeProductClass.ORDINARY_A_SHARE,
        (
            CnAShareStampDutyBandV2(
                VenueId("xshe"),
                UtcInstant(START),
                UtcInstant(END),
                True,
                Rate(5, Scale(4), "fee_fraction"),
                (_source_ref("stamp_duty"),),
            ),
        ),
    )
    return market, stamp


def test_snapshot_and_declaration_exactly_bind_evidence_and_finite_v2_values() -> None:
    _assert_snapshot(SNAPSHOT)
    assert DECLARATION["snapshot"] == SNAPSHOT
    assert DECLARATION["snapshot_hash"] == canonical_sha256(SNAPSHOT)
    assert DECLARATION["qualification"] == QUALIFICATION
    assert DECLARATION["target_coverage"] == {
        "development_evidence_available_at_epoch_nanoseconds": (
            SNAPSHOT["development_evidence_available_at"]
        ),
        "end_exclusive_epoch_nanoseconds": END,
        "start_epoch_nanoseconds": START,
    }
    assert not _contains_key(DECLARATION, "official_record_as_of")
    assert "official_record_as_of" not in canonical_bytes(DECLARATION).decode()

    market, stamp = _rule_books()
    authorities = DECLARATION["authorities"]
    assert set(authorities) == set(DIMENSIONS)
    assert canonical_bytes(market) == canonical_bytes(authorities["market_fees"]["body"])
    assert market.rule_book_hash == authorities["market_fees"]["authority_hash"]
    assert canonical_bytes(stamp) == canonical_bytes(authorities["stamp_duty"]["body"])
    assert stamp.rule_book_hash == authorities["stamp_duty"]["authority_hash"]

    band = market.bands[0]
    assert type(band) is CnAShareMarketFeeBandV2
    assert (band.effective_from, band.effective_to_exclusive) == (
        UtcInstant(START),
        UtcInstant(END),
    )
    assert (band.handling_applies, band.handling_rate) == (
        True,
        Rate(341, Scale(7), "fee_fraction"),
    )
    assert (band.regulatory_applies, band.regulatory_rate) == (
        True,
        Rate(2, Scale(5), "fee_fraction"),
    )
    assert (
        band.chinaclear_transfer_applies,
        band.chinaclear_transfer_rate,
    ) == (True, Rate(1, Scale(5), "fee_fraction"))
    assert (band.hkscc_transfer_applies, band.hkscc_transfer_rate) == (
        False,
        Rate(0, Scale(0), "fee_fraction"),
    )
    assert band.chinaclear_transfer_source_refs != band.hkscc_transfer_source_refs
    assert stamp.bands[0].applies_to_sell is True
    assert SNAPSHOT["economics"]["stamp_duty"]["buy"] is False

    v1 = json.loads((V1_FIXTURE_DIR / "declaration.json").read_text())
    for dimension in ("calendar", "order_rules", "corporate_action_entitlements"):
        assert canonical_bytes(authorities[dimension]["body"]) == canonical_bytes(
            v1["authorities"][dimension]["body"]
        )


def test_nested_constructor_bypass_and_snapshot_overclaims_fail_closed() -> None:
    market, _ = _rule_books()
    band = market.bands[0]
    forged = object.__new__(CnAShareMarketFeeBandV2)
    for field in fields(band):
        object.__setattr__(forged, field.name, getattr(band, field.name))
    object.__setattr__(
        forged,
        "hkscc_transfer_rate",
        Rate(1, Scale(5), "fee_fraction"),
    )
    with pytest.raises(TypeError, match="concrete CnAShareMarketFeeBandV2"):
        replace(market, bands=(forged,))

    for mutate in (
        lambda value: value.update({"target_from": 0}),
        lambda value: value["components"][0]["sources"][0].update(
            {"raw_sha256": "sha256:" + "f" * 64}
        ),
        lambda value: value["components"][0]["candidate_dispositions"][0].update(
            {"disposition": "unresolved"}
        ),
        lambda value: value["economics"]["hkscc_transfer"]["rate"].update(
            {"units": 1}
        ),
        lambda value: value["qualification"].update(
            {"rule_coverage_qualified": True}
        ),
    ):
        forged_snapshot = deepcopy(SNAPSHOT)
        mutate(forged_snapshot)
        with pytest.raises(AssertionError):
            _assert_snapshot(forged_snapshot)


def test_current_selected_rule_authorities_project_and_publish_idempotently(
    tmp_path: Path,
) -> None:
    bundle = import_module(
        "crypto_quant_bundle_builder.cn_a_share_current_selected_rule_bundle"
    )
    events = bundle.project_cn_a_share_current_selected_rule_authority_events_v2(
        DECLARATION
    )
    assert type(events) is tuple and len(events) == 5
    assert all(type(event) is MarketEvent for event in events)
    assert json.loads(canonical_bytes(events)) == EXPECTED["events"]
    assert [event.event_hash for event in events] == EXPECTED["event_hashes"]

    declaration_hash = canonical_sha256(DECLARATION)
    coverage = DECLARATION["target_coverage"]
    authorities = DECLARATION["authorities"]
    for index, (dimension, event) in enumerate(zip(DIMENSIONS, events, strict=True)):
        authority = authorities[dimension]
        assert event.event_id == (
            "cn-a-share-current-selected-development-rule-authority-v2:"
            f"{dimension}:{authority['authority_hash']}"
        )
        assert event.stream_key == (
            "cn_a_share.current_selected_development.rule_authority."
            f"{dimension}.v2"
        )
        assert event.event_type == (
            "cn_a_share_current_selected_development_"
            f"{dimension}_authority.v2"
        )
        assert event.capability.identity == (
            "cn_a_share.current-selected-development-rule-authorities@2"
        )
        assert event.event_time == UtcInstant(START)
        assert event.available_time == UtcInstant(
            SNAPSHOT["development_evidence_available_at"]
        )
        assert event.source_sequence.value == index
        assert event.revision_id == authority["authority_hash"]
        assert event.source_key == (
            f"equity.cn_a_share.current-selected-development.v2/{dimension}"
        )
        assert event.source_hash == authority["canonical_body_hash"]
        assert event.payload["declaration_hash"] == declaration_hash
        assert event.payload["snapshot_hash"] == DECLARATION["snapshot_hash"]
        assert event.payload["qualification"] == QUALIFICATION
        assert canonical_bytes(event.payload["authority"]) == canonical_bytes(
            authority["body"]
        )

    validation = validate_market_bundle_v1(
        bundle_key=DECLARATION["publication"]["bundle_key"],
        schema_version=2,
        coverage_start=UtcInstant(START),
        coverage_end_exclusive=UtcInstant(END),
        instrument_catalog_hash="sha256:" + "0" * 64,
        events=events,
    )
    assert validation.failure is None and validation.manifest is not None
    manifest = validation.manifest
    assert manifest.content_hash == EXPECTED["manifest_content_hash"]
    assert canonical_sha256(manifest) == EXPECTED["manifest_hash"]
    assert {
        stream.stream_key: stream.content_hash for stream in manifest.streams
    } == EXPECTED["stream_content_hashes"]

    stream_payloads = {
        event.stream_key: canonical_bytes((event,)) for event in events
    }
    repository = LocalMarketBundleRepository(
        config=LocalMarketBundleRepositoryConfig(tmp_path.resolve())
    )
    publication = repository.publish_market_bundle_v1(
        manifest=manifest,
        stream_payloads=stream_payloads,
        retention_policy_ref=DECLARATION["publication"]["retention_policy_ref"],
    )
    assert publication.failure is None and publication.result is not None
    assert publication.result.already_published is False
    assert publication.result.bundle_ref.to_canonical_dict() == EXPECTED["bundle_ref"]
    assert (
        publication.result.retention_proof.proof_hash
        == EXPECTED["retention_proof_hash"]
    )
    replay = repository.publish_market_bundle_v1(
        manifest=manifest,
        stream_payloads=stream_payloads,
        retention_policy_ref=DECLARATION["publication"]["retention_policy_ref"],
    )
    assert replay.failure is None and replay.result is not None
    assert replay.result.already_published is True
    assert replay.result.bundle_ref == publication.result.bundle_ref
    assert replay.result.retention_proof == publication.result.retention_proof


@pytest.mark.parametrize(
    "mutate",
    (
        lambda value: value.update({"extra": None}),
        lambda value: value["snapshot"].update({"target_from": 0}),
        lambda value: value["snapshot"].update(
            {"snapshot_hash": "sha256:" + "f" * 64}
        ),
        lambda value: value["qualification"].update(
            {"development_projection_authorized": False}
        ),
        lambda value: value["authorities"].pop("market_fees"),
    ),
)
def test_current_selected_projection_rejects_forged_declaration(mutate) -> None:
    project = import_module(
        "crypto_quant_bundle_builder.cn_a_share_current_selected_rule_bundle"
    ).project_cn_a_share_current_selected_rule_authority_events_v2
    forged = deepcopy(DECLARATION)
    mutate(forged)
    with pytest.raises(ValueError, match="declaration authority"):
        project(forged)
    with pytest.raises(TypeError, match="exact declaration mapping"):
        project(object())


def test_frozen_v1_declaration_and_publication_hashes_remain_unchanged() -> None:
    declaration_path = V1_FIXTURE_DIR / "declaration.json"
    publication_path = V1_FIXTURE_DIR / "publication.expected.json"
    assert _file_hash(declaration_path) == (
        "sha256:19017a07fbfd2da954483648fb168d87212f88e92fccca7c28fb0a514b202515"
    )
    assert canonical_sha256(json.loads(declaration_path.read_text())) == (
        "sha256:6e0c60a75e957467a5cfe1b4e2bbbb786c463747ae96adf059c54ecef4a1b7b6"
    )
    assert _file_hash(publication_path) == (
        "sha256:7a95188cf05d401fcaed80b548f82f22f0b9bc23f6423c6ff1190de775291f7d"
    )
    assert canonical_sha256(json.loads(publication_path.read_text())) == (
        "sha256:80295bc6f8069351e70f9cc6bcf3aae5ff39af6cdedeebfc67a65cfc52b329e9"
    )
