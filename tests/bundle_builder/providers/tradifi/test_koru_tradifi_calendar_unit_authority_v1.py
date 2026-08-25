from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest
from crypto_quant_backtest.binance_usdm_tradifi_profile import (
    _calendar_refs_match,
    _unit_regime_ref_matches,
)
from crypto_quant_bundle_builder.koru_tradifi_calendar_unit_authority_v1 import (
    APPROVED_MEMBER_HASHES,
    KoruTradifiCalendarUnitAuthorityFailureCode,
    KoruTradifiCalendarUnitAuthorityResultV1,
    build_koru_tradifi_calendar_unit_authority_v1,
    verify_koru_tradifi_calendar_unit_authority_v1,
)
from crypto_quant_bundle_builder.source_snapshots import RawSourceMember
from crypto_quant_domain import ArtifactEnvelope, ArtifactRef, canonical_bytes

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "fixtures/market_data/providers/tradifi/koru-calendar-unit-v1"
CAPTURED_AT_NS = {
    "krx": 1_787_651_082_170_000_000,
    "nyse": 1_787_651_083_172_000_000,
    "binance": 1_787_651_234_087_000_000,
}
GOLDEN = {
    "snapshot_id": "sha256:f4c5e93cc274e9e5ea6ba52f79d90900fff3963a2c569b4c5b97a0668e76e838",
    "xkrx": "sha256:dcffef007cd8a9c00319259663c32cd09812904562229b3a2084d03718624d35",
    "arcx": "sha256:d9a75b431730740b6e5793f99a71978513422ed78f6dd7bda4485f20a75a9926",
    "unit": "sha256:dca20ef381e3e95469e7507d422430317e471677a1d2450b188a918cbb146e18",
}


def _members() -> tuple[RawSourceMember, ...]:
    return tuple(
        RawSourceMember(
            member_key=member_key,
            raw_bytes=(FIXTURES / member_key).read_bytes(),
            mode="0644",
            acquired_at_epoch_nanoseconds=CAPTURED_AT_NS[member_key.partition("/")[0]],
            declared_sha256=expected_hash,
        )
        for member_key, expected_hash in APPROVED_MEMBER_HASHES
    )


def _result() -> KoruTradifiCalendarUnitAuthorityResultV1:
    outcome = build_koru_tradifi_calendar_unit_authority_v1(
        members=_members(), expected_hashes=APPROVED_MEMBER_HASHES
    )
    assert outcome.failure is None
    assert outcome.result is not None
    return outcome.result


def _payload(envelope: ArtifactEnvelope) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(canonical_bytes(envelope.payload)))


def test_builds_one_snapshot_three_golden_artifacts_and_composer_refs() -> None:
    result = _result()

    assert result.source_snapshot.snapshot_id == GOLDEN["snapshot_id"]
    assert [artifact.content_hash for artifact in result.artifacts] == [
        GOLDEN["xkrx"],
        GOLDEN["arcx"],
        GOLDEN["unit"],
    ]
    assert (
        tuple(ArtifactRef.from_envelope(value) for value in result.artifacts)
        == result.refs
    )
    assert _calendar_refs_match(result.refs[:2])
    assert _unit_regime_ref_matches(result.refs[2])
    assert result.source_snapshot.decision_grade_eligible is False
    assert result.source_snapshot.deployment_authorized is False
    assert all(
        artifact.payload["deployment_authorized"] is False
        for artifact in result.artifacts
    )


def test_xkrx_calendar_exact_closures_weekends_and_boundary_sessions() -> None:
    payload = _payload(_result().xkrx_calendar)
    sessions = payload["sessions"]
    dates = [session["session_date"] for session in sessions]

    assert payload["coverage"] == {
        "start": "2026-07-15T10:00:00Z",
        "end_exclusive": "2026-10-05T00:00:00Z",
    }
    assert payload["source_local_regular_hours"] == {
        "open": "09:00:00",
        "close": "15:30:00",
    }
    assert payload["source_timezone"] == "Asia/Seoul"
    assert payload["source_utc_offset"] == "+09:00"
    assert payload["applied_closure_dates"] == [
        "2026-07-17",
        "2026-08-17",
        "2026-09-24",
        "2026-09-25",
    ]
    assert payload["source_retained_not_emitted_boundary_closure_dates"] == [
        "2026-10-05"
    ]
    july_17 = next(
        value
        for value in payload["source_closures_2026"]
        if value["date"] == "2026-07-17"
    )
    assert july_17["reason"] == ""
    assert not {
        "2026-07-17",
        "2026-08-17",
        "2026-09-24",
        "2026-09-25",
        "2026-10-05",
    } & set(dates)
    assert not {"2026-07-18", "2026-07-19", "2026-10-03", "2026-10-04"} & set(dates)
    assert sessions[0]["session_date"] == "2026-07-16"
    assert sessions[0]["open_utc"] == "2026-07-16T00:00:00Z"
    assert sessions[0]["close_utc"] == "2026-07-16T06:30:00Z"
    assert sessions[-1]["session_date"] == "2026-10-02"
    assert len(sessions) == 53


def test_arcx_calendar_exact_labor_day_edt_hours_and_boundaries() -> None:
    payload = _payload(_result().arcx_calendar)
    sessions = payload["sessions"]
    dates = [session["session_date"] for session in sessions]

    assert payload["source_timezone"] == "America/New_York"
    assert payload["source_utc_offset_for_coverage"] == "-04:00"
    assert payload["source_dst_state_for_coverage"] == "EDT"
    assert payload["source_local_core_hours"] == {
        "open": "09:30:00",
        "close": "16:00:00",
    }
    assert payload["applied_closure_dates"] == ["2026-09-07"]
    assert payload["source_early_close_dates_2026"] == ["2026-11-27", "2026-12-24"]
    assert payload["early_close_dates_in_coverage"] == []
    assert "2026-09-07" not in dates
    assert not {"2026-07-18", "2026-07-19", "2026-10-03", "2026-10-04"} & set(dates)
    assert sessions[0] == {
        "session_date": "2026-07-15",
        "open_utc": "2026-07-15T13:30:00Z",
        "close_utc": "2026-07-15T20:00:00Z",
        "source_local_open": "2026-07-15T09:30:00",
        "source_local_close": "2026-07-15T16:00:00",
        "source_timezone": "America/New_York",
        "utc_offset": "-04:00",
        "dst_state": "EDT",
    }
    assert sessions[-1]["session_date"] == "2026-10-02"
    assert sessions[-1]["open_utc"] == "2026-10-02T13:30:00Z"
    assert sessions[-1]["close_utc"] == "2026-10-02T20:00:00Z"
    assert len(sessions) == 57


def test_unit_regime_binds_adjustment_completion_and_admission_scope() -> None:
    payload = _payload(_result().post_adjustment_unit_regime)

    assert payload["instrument"] == "KORUUSDT"
    assert payload["adjustment"] == {
        "starts_at": "2026-07-15T00:15:00Z",
        "scale_factor": 20,
        "share_split_relationship": "20-for-1",
        "price_relationship": "post_adjustment_price=pre_adjustment_price/20",
        "quantity_relationship": "post_adjustment_quantity=pre_adjustment_quantity*20",
        "source_examples": {"price": "800/20=40", "quantity": "20*20=400"},
    }
    assert payload["market_session_states"] == [
        {
            "state": "trading_halt",
            "start": "2026-07-15T00:15:00Z",
            "end_exclusive": "2026-07-15T09:30:00Z",
        },
        {
            "state": "cancel_only",
            "start": "2026-07-15T09:30:00Z",
            "end_exclusive": "2026-07-15T09:35:00Z",
        },
        {
            "state": "continuous_trading",
            "start": "2026-07-15T09:35:00Z",
            "end_exclusive": None,
        },
    ]
    assert payload["authoritative_post_adjustment_admission"] == {
        "start": "2026-07-15T10:00:00Z",
        "end_exclusive": "2026-10-05T00:00:00Z",
        "pre_adjustment_admission": False,
        "cross_regime_admission": False,
    }
    assert [article["article_code"] for article in payload["source_articles"]] == [
        "c226162366c54b78a7f98021b38e10c5",
        "2ce887ba8fe14fdaa088e5bed7553a4e",
    ]


def test_replay_is_canonical_and_source_session_artifact_ref_mutations_fail() -> None:
    result = _result()
    replay = verify_koru_tradifi_calendar_unit_authority_v1(
        result=result, expected_hashes=APPROVED_MEMBER_HASHES
    )
    assert replay.failure is None
    assert replay.result is not None
    assert canonical_bytes(replay.result) == canonical_bytes(result)

    source = bytearray(_members()[0].raw_bytes or b"")
    source[-1] ^= 1
    bad_members = list(_members())
    bad_members[0] = replace(bad_members[0], raw_bytes=bytes(source))
    bad_source = build_koru_tradifi_calendar_unit_authority_v1(
        members=tuple(bad_members), expected_hashes=APPROVED_MEMBER_HASHES
    )
    assert bad_source.result is None
    assert bad_source.failure is not None

    forged_snapshot = replace(
        result.source_snapshot,
        archive_bytes=result.source_snapshot.archive_bytes + b"tampered",
    )
    bad_snapshot_result = replace(result, source_snapshot=forged_snapshot)
    bad_snapshot = verify_koru_tradifi_calendar_unit_authority_v1(
        result=bad_snapshot_result, expected_hashes=APPROVED_MEMBER_HASHES
    )
    assert bad_snapshot.failure is not None
    assert (
        bad_snapshot.failure.code
        is KoruTradifiCalendarUnitAuthorityFailureCode.SOURCE_SNAPSHOT_INVALID
    )

    calendar_payload = _payload(result.xkrx_calendar)
    calendar_payload["sessions"][0]["close_utc"] = "2026-07-16T06:29:59Z"
    changed_calendar = ArtifactEnvelope.create(
        result.xkrx_calendar.artifact_type, 1, calendar_payload
    )
    changed_result = replace(
        result,
        xkrx_calendar=changed_calendar,
        xkrx_calendar_ref=ArtifactRef.from_envelope(changed_calendar),
    )
    changed = verify_koru_tradifi_calendar_unit_authority_v1(
        result=changed_result, expected_hashes=APPROVED_MEMBER_HASHES
    )
    assert changed.failure is not None
    assert (
        changed.failure.code
        is KoruTradifiCalendarUnitAuthorityFailureCode.RESULT_MISMATCH
    )

    with pytest.raises(ValueError, match="artifact/ref identity mismatch"):
        replace(
            result,
            xkrx_calendar_ref=ArtifactRef(
                "xkrx_regular_session_calendar", 1, "sha256:" + "0" * 64
            ),
        )


def test_wrong_expected_hashes_member_modes_and_duplicate_json_keys_are_rejected() -> None:
    wrong_mode = list(_members())
    wrong_mode[0] = replace(wrong_mode[0], mode="0755")
    mode_outcome = build_koru_tradifi_calendar_unit_authority_v1(
        members=tuple(wrong_mode), expected_hashes=APPROVED_MEMBER_HASHES
    )
    assert mode_outcome.result is None
    assert mode_outcome.failure is not None

    wrong = list(APPROVED_MEMBER_HASHES)
    wrong[0] = (wrong[0][0], "sha256:" + "0" * 64)
    outcome = build_koru_tradifi_calendar_unit_authority_v1(
        members=_members(), expected_hashes=tuple(wrong)
    )
    assert outcome.result is None
    assert outcome.failure is not None

    member = next(
        value
        for value in _members()
        if value.member_key == "krx/market-closing-2026.json"
    )
    assert member.raw_bytes is not None
    duplicate = member.raw_bytes.replace(b'{"block1":', b'{"block1":[],"block1":', 1)
    bad = replace(
        member,
        raw_bytes=duplicate,
        declared_sha256="sha256:" + "0" * 64,
    )
    members = tuple(
        bad if value.member_key == bad.member_key else value for value in _members()
    )
    duplicate_outcome = build_koru_tradifi_calendar_unit_authority_v1(
        members=members, expected_hashes=APPROVED_MEMBER_HASHES
    )
    assert duplicate_outcome.result is None
