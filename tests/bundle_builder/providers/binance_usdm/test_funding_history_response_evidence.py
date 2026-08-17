from __future__ import annotations

import hashlib
import json
from pathlib import Path

from crypto_quant_bundle_builder import (
    RawSourceMember,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
)


FIXTURE = (
    Path(__file__).parents[3]
    / "fixtures/market_data/providers/binance_usdm/funding-history-v1"
)
RESPONSE = FIXTURE / "BTCUSDT-funding-history-2024-01-01.json"
EXPECTED = json.loads((FIXTURE / "evidence.expected.json").read_text())


def test_real_funding_history_response_has_exact_g10e_fields_and_g12a_identity() -> None:
    response = RESPONSE.read_bytes()
    records = json.loads(response)
    assert hashlib.sha256(response).hexdigest() == EXPECTED["source_hash"][7:]
    assert len(records) == EXPECTED["response"]["record_count"] == 3
    assert [record["fundingTime"] for record in records] == [
        1_704_067_200_000,
        1_704_096_000_000,
        1_704_124_800_000,
    ]
    assert all(
        tuple(record) == (
            "symbol",
            "fundingTime",
            "fundingRate",
            "markPrice",
            "rateType",
        )
        for record in records
    )
    assert all(
        record["symbol"] == "BTCUSDT"
        and record["rateType"] == "Regular"
        and record["fundingRate"]
        and record["markPrice"]
        for record in records
    )

    acquired_at = EXPECTED["snapshot"]["members"][0][
        "acquired_at_epoch_nanoseconds"
    ]
    outcome = freeze_source_snapshot(
        members=(
            RawSourceMember(
                f"response/{RESPONSE.name}",
                response,
                "0644",
                acquired_at,
                EXPECTED["source_hash"],
            ),
        ),
        provenance=SourceSnapshotProvenance(
            vendor_key="binance.fapi",
            source_key="binance.fapi.funding_rate_history.btcusdt.2024-01-01",
            license_ref="binance.api.terms",
            retention_policy_ref="backtest.fixture.retention",
        ),
    )
    assert outcome.failure is None
    assert outcome.snapshot is not None
    assert outcome.snapshot.to_canonical_dict() == EXPECTED["snapshot"]
    assert outcome.snapshot.decision_grade_eligible is False
    assert outcome.snapshot.deployment_authorized is False
