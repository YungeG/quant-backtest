from __future__ import annotations

from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / "evidence/000703-january-2024-statutory-fee-development-v1"
SNAPSHOT = json.loads((EVIDENCE / "snapshot.json").read_text())
TARGET_FROM = 1_704_124_800_000_000_000
TARGET_TO = 1_706_716_800_000_000_000


def _hash(path: Path) -> str:
    return "sha256:" + sha256(path.read_bytes()).hexdigest()


def _rate(value: dict[str, object]) -> Decimal:
    assert value["basis"] == "fee_fraction"
    return Decimal(value["units"]) * (Decimal(10) ** -int(value["scale"]))


def test_snapshot_is_exactly_a_finite_development_authority() -> None:
    assert list(SNAPSHOT) == [
        "candidate_disposition_policy",
        "components",
        "development_evidence_available_at_epoch_nanoseconds",
        "economics",
        "extractions",
        "limitations",
        "qualification",
        "schema_version",
        "semantics_id",
        "snapshot_key",
        "sources",
        "target_from_epoch_nanoseconds",
        "target_scope",
        "target_to_exclusive_epoch_nanoseconds",
        "type",
    ]
    assert SNAPSHOT["type"] == (
        "cn_a_share_january_2024_statutory_fee_development_authority_snapshot"
    )
    assert SNAPSHOT["schema_version"] == 1
    assert SNAPSHOT["semantics_id"] == "current-official-selection-development.v1"
    assert (
        SNAPSHOT["target_from_epoch_nanoseconds"],
        SNAPSHOT["target_to_exclusive_epoch_nanoseconds"],
    ) == (TARGET_FROM, TARGET_TO)
    assert SNAPSHOT["target_scope"] == {
        "access_route": "DOMESTIC",
        "access_route_definition": (
            "order submitted through a mainland securities company directly to XSHE; "
            "excludes northbound Stock Connect submission through HKEX "
            "securities-trading-service companies"
        ),
        "basis": "trade_notional",
        "fee_product_class": "ORDINARY_A_SHARE",
        "instrument_type": "EQUITY",
        "quote_currency": "CNY",
        "settlement_currency": "CNY",
        "trade_mechanism": "AUCTION",
        "venue": "XSHE",
    }
    assert SNAPSHOT["qualification"] == {
        "decision_grade_eligible": False,
        "development_projection_authorized": True,
        "live_eligible": False,
        "official_successor_closure_complete": False,
        "rule_coverage_qualified": False,
        "deployment_authorized": False,
    }


def test_frozen_primary_responses_and_receipts_bind_each_source() -> None:
    sources = SNAPSHOT["sources"]
    assert [source["source_id"] for source in sources] == sorted(
        source["source_id"] for source in sources
    )
    observed_at = []
    for source in sources:
        assert set(source) == {
            "evidence_path",
            "media_type",
            "observed_at_epoch_nanoseconds",
            "receipt_path",
            "receipt_sha256",
            "redirect_chain_path",
            "redirect_chain_sha256",
            "request_path",
            "request_sha256",
            "requested_url",
            "response_headers_path",
            "response_headers_sha256",
            "source_id",
            "source_url",
            "raw_sha256",
            "transport_path",
            "transport_sha256",
        }
        raw = EVIDENCE / source["evidence_path"]
        receipt_path = EVIDENCE / source["receipt_path"]
        headers = EVIDENCE / source["response_headers_path"]
        redirects = EVIDENCE / source["redirect_chain_path"]
        request = EVIDENCE / source["request_path"]
        transport = EVIDENCE / source["transport_path"]
        receipt = json.loads(receipt_path.read_text())
        assert _hash(raw) == source["raw_sha256"] == receipt["raw_sha256"]
        assert _hash(receipt_path) == source["receipt_sha256"]
        assert _hash(headers) == source["response_headers_sha256"] == receipt[
            "response_headers_sha256"
        ]
        assert _hash(redirects) == source["redirect_chain_sha256"] == receipt[
            "redirect_chain_sha256"
        ]
        assert _hash(request) == source["request_sha256"]
        assert _hash(transport) == source["transport_sha256"]
        assert json.loads(request.read_text()) == receipt["request"] == {
            "method": "GET",
            "requested_url": source["requested_url"],
        }
        assert receipt["response"] == {
            "final_url": source["source_url"],
            "media_type": source["media_type"],
            "status_code": 200,
        }
        assert receipt["retrieved_at_epoch_nanoseconds"] == source[
            "observed_at_epoch_nanoseconds"
        ]
        assert json.loads(redirects.read_text()) == []
        assert json.loads(transport.read_text()) == {
            "content_type": source["media_type"],
            "http_code": 200,
            "num_redirects": 0,
            "url_effective": source["source_url"],
        }
        observed_at.append(source["observed_at_epoch_nanoseconds"])
    assert SNAPSHOT["development_evidence_available_at_epoch_nanoseconds"] == max(
        observed_at
    )


def test_stamp_duty_rate_table_attachment_is_bound_to_the_statutory_claim(
    tmp_path: Path,
) -> None:
    sources = {source["source_id"]: source for source in SNAPSHOT["sources"]}
    law = EVIDENCE / sources["sta-stamp-tax-law"]["evidence_path"]
    rate_table = EVIDENCE / sources["sta-stamp-tax-rate-table"]["evidence_path"]
    assert "5193058/files/印花税税目税率表.ppt" in law.read_text()
    assert rate_table.read_bytes().startswith(bytes.fromhex("d0cf11e0a1b11ae1"))

    [extraction_ref] = SNAPSHOT["extractions"]
    extraction_path = EVIDENCE / extraction_ref["extraction_path"]
    extraction = json.loads(extraction_path.read_text())
    artifact = EVIDENCE / extraction_ref["extracted_artifact_path"]
    assert _hash(extraction_path) == extraction_ref["extraction_sha256"]
    assert _hash(artifact) == extraction_ref["extracted_artifact_sha256"]
    assert extraction == {
        "derivation": {
            "container": "Compound",
            "extractor": "7z Compound stream extraction",
            "jpeg_length_bytes": 134338,
            "jpeg_offset_bytes": 126580,
            "picture_stream": "Pictures",
        },
        "extracted_artifact_path": extraction_ref["extracted_artifact_path"],
        "extracted_artifact_sha256": extraction_ref["extracted_artifact_sha256"],
        "schema_version": 1,
        "semantic_claim": {
            "basis": "trade_notional",
            "rate": {"basis": "fee_fraction", "scale": 3, "units": 1},
            "table_row": "证券交易",
        },
        "source_id": "sta-stamp-tax-rate-table",
        "source_raw_sha256": sources["sta-stamp-tax-rate-table"]["raw_sha256"],
        "transcription_method": (
            "visual transcription of the retained official rate-table slide"
        ),
        "type": "official_attachment_rate_table_extraction",
    }
    result = subprocess.run(
        ["7z", "e", "-y", f"-o{tmp_path}", str(rate_table)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    picture_stream = (tmp_path / extraction["derivation"]["picture_stream"]).read_bytes()
    start = extraction["derivation"]["jpeg_offset_bytes"]
    end = start + extraction["derivation"]["jpeg_length_bytes"]
    assert picture_stream[start:end] == artifact.read_bytes()

    stamp = next(
        component
        for component in SNAPSHOT["components"]
        if component["lineage"] == "stamp_duty"
    )
    assert _rate(extraction["semantic_claim"]["rate"]) / 2 == _rate(
        stamp["rate"]
    )
    assert set(stamp["selected_source_ids"]) >= {
        "mof-sta-stamp-duty-2023-39",
        "sta-stamp-tax-law",
        "sta-stamp-tax-rate-table",
    }
    law_candidate = next(
        candidate
        for candidate in stamp["candidate_dispositions"]
        if candidate["candidate_id"] == "stamp-duty-law-2021"
    )
    assert set(law_candidate["evidence_source_ids"]) == {
        "sta-stamp-tax-law",
        "sta-stamp-tax-rate-table",
    }


def test_components_are_complete_dispositioned_january_economics() -> None:
    components: list[dict[str, Any]] = SNAPSHOT["components"]
    assert [component["lineage"] for component in components] == [
        "chinaclear_transfer",
        "exchange_handling",
        "hkscc_transfer",
        "securities_regulatory",
        "stamp_duty",
    ]
    expected = {
        "chinaclear_transfer": ({"buy": True, "sell": True}, Decimal("0.00001")),
        "exchange_handling": ({"buy": True, "sell": True}, Decimal("0.0000341")),
        "hkscc_transfer": ({"buy": False, "sell": False}, Decimal(0)),
        "securities_regulatory": ({"buy": True, "sell": True}, Decimal("0.00002")),
        "stamp_duty": ({"buy": False, "sell": True}, Decimal("0.0005")),
    }
    source_ids = {source["source_id"] for source in SNAPSHOT["sources"]}
    allowed = set(SNAPSHOT["candidate_disposition_policy"]["allowed_dispositions"])
    for component in components:
        applies, expected_rate = expected[component["lineage"]]
        assert component["basis"] == "trade_notional"
        assert component["target_scope"] == SNAPSHOT["target_scope"]
        assert component["applies"] == applies
        assert _rate(component["rate"]) == expected_rate
        assert component["effective_from_epoch_nanoseconds"] <= TARGET_FROM
        end = component["effective_to_exclusive_epoch_nanoseconds"]
        assert end is None or TARGET_TO <= end
        assert component["selected_source_ids"] == sorted(component["selected_source_ids"])
        assert set(component["selected_source_ids"]) <= source_ids
        dispositions = component["candidate_dispositions"]
        assert dispositions == sorted(dispositions, key=lambda item: item["candidate_id"])
        assert all(item["disposition"] in allowed for item in dispositions)
        assert all(item["disposition"] != "unresolved" for item in dispositions)
        assert all(set(item["evidence_source_ids"]) <= source_ids for item in dispositions)

    assert SNAPSHOT["economics"] == {
        "buy_total_rate": {"basis": "fee_fraction", "scale": 7, "units": 641},
        "sell_total_rate": {"basis": "fee_fraction", "scale": 7, "units": 5641},
    }
    buy = sum(
        _rate(component["rate"])
        for component in components
        if component["applies"]["buy"]
    )
    sell = sum(
        _rate(component["rate"])
        for component in components
        if component["applies"]["sell"]
    )
    assert buy == _rate(SNAPSHOT["economics"]["buy_total_rate"])
    assert sell == _rate(SNAPSHOT["economics"]["sell_total_rate"])
