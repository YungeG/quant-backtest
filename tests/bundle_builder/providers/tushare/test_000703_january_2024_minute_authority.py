from __future__ import annotations

import json
from pathlib import Path

import pytest
from crypto_quant_bundle_builder import (
    LocalMarketBundleRepository,
    LocalMarketBundleRepositoryConfig,
    MarketBundlePublicationFailureCode,
    RawSourceMember,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
    validate_market_bundle_v1,
)
from crypto_quant_domain import (
    InstrumentId,
    UtcInstant,
    VenueId,
    canonical_bytes,
    canonical_sha256,
)
from tools.acquisition._common import sha256
from tools.acquisition.cn_a_share_tushare_minute_source_bounded_v2 import (
    verify_tushare_minute_source_bounded_receipt_v2,
)
from tools.acquisition.cn_a_share_tushare_proxy_trade_calendar_month_source_bounded_v2 import (
    verify_tushare_proxy_trade_calendar_month_source_bounded_receipt_v2,
)
import crypto_quant_bundle_builder.tushare_cn_a_share_minute as minute
from crypto_quant_bundle_builder.tushare_000703_january_2024_minute_authority import (
    build_tushare_000703_january_2024_minute_authority_v1,
)


WORKLIST = (
    "20240102", "20240103", "20240104", "20240105", "20240108", "20240109",
    "20240110", "20240111", "20240112", "20240115", "20240116", "20240117",
    "20240118", "20240119", "20240122", "20240123", "20240124", "20240125",
    "20240126", "20240129", "20240130", "20240131",
)
START = UtcInstant(1_704_124_800_000_000_000)
END = UtcInstant(1_706_716_800_000_000_000)
ROOT = Path(__file__).resolve().parents[4]
RETAINED_CALENDAR = ROOT / "evidence/tushare-calendar-szse-development-month-202401-v3"
RETAINED_MINUTES = ROOT / "evidence/tushare-minute-000703-development-month-202401-v2/sessions"
RETAINED_AUTHORITY = ROOT / "evidence/tushare-000703-development-month-authority-202401-v1"


def _result(day: str, index: int):
    rows = [
        ["000703.SZ", label, 10.50, 10.00, 11.00, 9.50, 100, 1000.00]
        for label in minute._expected_labels(day)
    ]
    source = json.dumps(
        {
            "request_id": f"synthetic-{day}",
            "code": 0,
            "data": {
                "fields": list(minute._FIELDS),
                "items": rows,
                "has_more": False,
                "count": 0,
            },
            "msg": "",
            "detail": "",
        },
        separators=(",", ":"),
    ).encode()
    snapshot = freeze_source_snapshot(
        members=(
            RawSourceMember(
                "response/stk-mins.json", source, "0644", index + 1, None
            ),
        ),
        provenance=SourceSnapshotProvenance(
            "tushare.pro",
            f"tushare.pro.stk_mins.000703.sz.{day}.5min",
            "tushare.pro.terms",
            "backtest.acquisition.candidate",
        ),
    ).snapshot
    assert snapshot is not None
    member = snapshot.members[0]
    outcome = minute.normalize_tushare_cn_a_share_minute_v1(
        snapshot,
        minute.TushareCnAShareMinuteNormalizationRequest(
            1,
            snapshot.snapshot_id,
            snapshot.provenance_hash,
            member.member_key,
            member.content_hash,
            InstrumentId(VenueId("xshe"), "000703"),
            day,
        ),
    )
    assert outcome.result is not None
    return outcome.result


def _results():
    return tuple(_result(day, index) for index, day in enumerate(WORKLIST))


def _retained_snapshot(root: Path, member_key: str):
    receipt_bytes = (root / "acquisition-receipt.json").read_bytes()
    raw = (root / member_key).read_bytes()
    receipt = json.loads(receipt_bytes)
    snapshot = receipt["snapshot"]
    provenance = snapshot["provenance"]
    [member] = snapshot["members"]
    frozen = freeze_source_snapshot(
        members=(
            RawSourceMember(
                member_key,
                raw,
                "0644",
                member["acquired_at_epoch_nanoseconds"],
                None,
            ),
        ),
        provenance=SourceSnapshotProvenance(
            provenance["vendor_key"],
            provenance["source_key"],
            provenance["license_ref"],
            provenance["retention_policy_ref"],
        ),
    ).snapshot
    assert frozen is not None
    return receipt_bytes, frozen


def test_month_authority_exact_covers_sessions_and_publishes_with_retention(
    tmp_path: Path,
) -> None:
    authority = build_tushare_000703_january_2024_minute_authority_v1(_results())
    assert authority.manifest.coverage_start == START
    assert authority.manifest.coverage_end_exclusive == END
    assert len(authority.events) == len(WORKLIST) * 48
    assert authority.events[0].event_time == authority.events[0].available_time
    assert authority.events[0].payload["bar_kind"] == "real"
    assert authority.events[0].payload["interval_start"]["epoch_nanoseconds"] > (
        START.epoch_nanoseconds
    )
    assert tuple(event.event_time for event in authority.events) == tuple(
        sorted(event.event_time for event in authority.events)
    )

    validation = validate_market_bundle_v1(
        bundle_key=authority.manifest.bundle_key,
        schema_version=authority.manifest.schema_version,
        coverage_start=authority.manifest.coverage_start,
        coverage_end_exclusive=authority.manifest.coverage_end_exclusive,
        instrument_catalog_hash=authority.manifest.instrument_catalog_hash,
        events=authority.events,
    )
    assert validation.failure is None and validation.manifest == authority.manifest

    repository = LocalMarketBundleRepository(
        config=LocalMarketBundleRepositoryConfig(root=tmp_path)
    )
    payloads = {authority.events[0].stream_key: canonical_bytes(authority.events)}
    first = repository.publish_market_bundle_v1(
        manifest=authority.manifest,
        stream_payloads=payloads,
        retention_policy_ref="retention.tushare-000703-minute-202401-v1",
    )
    assert first.result is not None and first.result.already_published is False
    repeated = repository.publish_market_bundle_v1(
        manifest=authority.manifest,
        stream_payloads=payloads,
        retention_policy_ref="retention.tushare-000703-minute-202401-v1",
    )
    assert repeated.result is not None and repeated.result.already_published is True
    assert repeated.result.retention_proof == first.result.retention_proof

    final = tmp_path / first.result.repository_path.final_directory_relative_path
    stream_payload = final / "streams/000.payload"
    stream_payload.chmod(0o600)
    stream_payload.write_bytes(b"corrupted")
    corrupted = repository.publish_market_bundle_v1(
        manifest=authority.manifest,
        stream_payloads=payloads,
        retention_policy_ref="retention.tushare-000703-minute-202401-v1",
    )
    assert corrupted.result is None
    assert corrupted.failure is not None
    assert (
        corrupted.failure.code
        is MarketBundlePublicationFailureCode.FINAL_DESTINATION_CONFLICT
    )


def test_retained_month_authority_replays_its_source_receipts_and_retention() -> None:
    calendar_bytes, calendar_snapshot = _retained_snapshot(
        RETAINED_CALENDAR, "response/trade-calendar.json"
    )
    calendar_hash = sha256(calendar_bytes)
    calendar = verify_tushare_proxy_trade_calendar_month_source_bounded_receipt_v2(
        calendar_bytes, calendar_snapshot, calendar_hash
    )
    assert tuple(calendar["open_sessions"]) == WORKLIST

    minute_hashes: dict[str, str] = {}
    results = []
    for day in WORKLIST:
        receipt_bytes, snapshot = _retained_snapshot(
            RETAINED_MINUTES / day, "response/stk-mins.json"
        )
        receipt_hash = sha256(receipt_bytes)
        receipt = verify_tushare_minute_source_bounded_receipt_v2(
            receipt_bytes, snapshot, receipt_hash
        )
        assert receipt["request"]["trade_date"] == day
        member = snapshot.members[0]
        outcome = minute.normalize_tushare_cn_a_share_minute_v1(
            snapshot,
            minute.TushareCnAShareMinuteNormalizationRequest(
                1,
                snapshot.snapshot_id,
                snapshot.provenance_hash,
                member.member_key,
                member.content_hash,
                InstrumentId(VenueId("xshe"), "000703"),
                day,
            ),
        )
        assert outcome.result is not None
        minute_hashes[day] = receipt_hash
        results.append(outcome.result)

    authority = build_tushare_000703_january_2024_minute_authority_v1(
        tuple(results)
    )
    receipt = json.loads((RETAINED_AUTHORITY / "authority-receipt.json").read_bytes())
    assert set(receipt) == {
        "type",
        "schema_version",
        "calendar_receipt_sha256",
        "minute_receipt_sha256",
        "normalization_hashes",
        "manifest_hash",
        "bundle_ref",
        "retention_proof",
        "retention_policy_ref",
        "development_only",
        "decision_grade_eligible",
        "live_eligible",
        "deployment_authorized",
    }
    assert receipt["type"] == "tushare_000703_january_2024_minute_authority_receipt"
    assert receipt["schema_version"] == 1
    assert receipt["calendar_receipt_sha256"] == calendar_hash
    assert receipt["minute_receipt_sha256"] == minute_hashes
    assert receipt["normalization_hashes"] == [
        result.normalization_hash for result in results
    ]
    assert receipt["manifest_hash"] == canonical_sha256(authority.manifest)
    assert receipt["retention_policy_ref"] == "retention.tushare-000703-minute-202401-v1"
    assert receipt["development_only"] is True
    assert receipt["decision_grade_eligible"] is False
    assert receipt["live_eligible"] is False
    assert receipt["deployment_authorized"] is False
    publication = LocalMarketBundleRepository(
        config=LocalMarketBundleRepositoryConfig(root=RETAINED_AUTHORITY.resolve())
    ).publish_market_bundle_v1(
        manifest=authority.manifest,
        stream_payloads={authority.events[0].stream_key: canonical_bytes(authority.events)},
        retention_policy_ref=receipt["retention_policy_ref"],
    )
    assert publication.result is not None and publication.result.already_published
    assert publication.result.bundle_ref.to_canonical_dict() == receipt["bundle_ref"]
    assert json.loads(canonical_bytes(publication.result.retention_proof)) == receipt[
        "retention_proof"
    ]


@pytest.mark.parametrize("results", (_results()[:-1], tuple(reversed(_results()))))
def test_missing_or_unordered_open_session_fails_closed(results: tuple[object, ...]) -> None:
    with pytest.raises(ValueError, match="January worklist"):
        build_tushare_000703_january_2024_minute_authority_v1(results)
