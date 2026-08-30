from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

import pytest
from crypto_quant_bundle_builder.binance_usdm_koru_price_bars_source_bounded_v1 import (
    BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1,
    BinanceUsdmKoruPriceBarsSourceBoundedRequestV1,
    BinanceUsdmKoruPriceBarsSourceKindV1,
    BinanceUsdmKoruRetainedPriceBarsAuthorityV1,
    build_binance_usdm_koru_price_bars_retained_observations_evidence_v1,
    capture_binance_usdm_koru_price_bars_from_retained_observations_v1,
    capture_binance_usdm_koru_price_bars_source_bounded_v1,
    normalize_binance_usdm_koru_price_bars_source_bounded_v1,
)
from crypto_quant_domain import InstrumentId, UtcInstant, VenueId, canonical_sha256

UTC_DATE = "2026-08-24"
DAY_START_MS = 1_787_529_600_000
HOUR_MS = 3_600_000
COVERAGE_END_MS = DAY_START_MS + 11 * HOUR_MS
ORIGINAL_START_MS = 1_782_136_500_000
ORIGINAL_END_MS = 1_787_569_200_000
AUTHORITY_REF = "binance.fapi.completed-kline-close-exclusive.v1"
SCHEMA_IDENTITY = (
    "binance_usdm_koru_price_bars_discovery_bounded_csv_7_column_scale8_v1"
)
HEADER = (
    "open_time_utc",
    "open",
    "high",
    "low",
    "close",
    "close_time_utc",
    "volume",
)
RESEARCH_DATA = (
    Path(__file__).resolve().parents[3]
    / "fixtures/market_data/providers/binance_usdm/koru-price-bars-retained-v1"
)
ACTUAL_MANIFEST_SHA256 = "sha256:c20ab7e8444e4f2a60e6e2b10e9faf57345e68c6cd10a4682c744f3fe4f91a80"
ACTUAL_SOURCE_SHA256 = {
    BinanceUsdmKoruPriceBarsSourceKindV1.MARK_PRICE: "sha256:e46fd0296dea518616fa11905db3a07e6d8ab672d9867298f88be12e771918d4",
    BinanceUsdmKoruPriceBarsSourceKindV1.INDEX_PRICE: "sha256:a67e4be307cf2701b0c16b76a193129907e86bc4b7294b52ce11b304ce278046",
}


def sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()



def manifest_bytes(value: dict[str, object]) -> bytes:
    value["manifest_sha256"] = ""
    value["manifest_sha256"] = sha256(
        json.dumps(
            value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        ).encode()
    )
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


@dataclass(frozen=True)
class Evidence:
    source: bytes
    manifest: bytes
    derived: bytes
    archive: bytes
    checksum: bytes


def source_details(source_kind: BinanceUsdmKoruPriceBarsSourceKindV1):
    if source_kind is BinanceUsdmKoruPriceBarsSourceKindV1.MARK_PRICE:
        return (
            "https://fapi.binance.com/fapi/v1/markPriceKlines",
            "binance_mark_raw.csv",
            "symbol",
            "2026-08-24T13:26:17.763Z",
        )
    return (
        "https://fapi.binance.com/fapi/v1/indexPriceKlines",
        "binance_index_raw.csv",
        "pair",
        "2026-08-24T13:26:18.248Z",
    )


def retained_authority(
    source_kind: BinanceUsdmKoruPriceBarsSourceKindV1,
    source: bytes,
    manifest: bytes,
    derived: bytes,
    **changes: object,
) -> BinanceUsdmKoruRetainedPriceBarsAuthorityV1:
    endpoint, artifact_name, instrument_parameter, acquired = source_details(
        source_kind
    )
    manifest_value = json.loads(manifest)
    parameters = {
        "endTime": ORIGINAL_END_MS - 1,
        "interval": "1h",
        "limit": 1000,
        "startTime": ORIGINAL_START_MS,
        instrument_parameter: "KORUUSDT",
    }
    acquired_ms = int(
        datetime.fromisoformat(acquired).timestamp() * 1000
    )
    values: dict[str, object] = {
        "source_artifact_type": "binance_fapi_price_bars_raw_csv_v1",
        "source_artifact_path": f"research/koruusdt/data/{artifact_name}",
        "source_artifact_sha256": sha256(source),
        "source_acquired_at_epoch_nanoseconds": acquired_ms * 1_000_000,
        "base_manifest_path": "research/koruusdt/data/manifest.json",
        "base_manifest_file_sha256": sha256(manifest),
        "base_manifest_identity": manifest_value["manifest_sha256"],
        "original_binance_endpoint": endpoint,
        "original_binance_parameter_sha256": canonical_sha256(parameters),
        "original_request_start": UtcInstant(ORIGINAL_START_MS * 1_000_000),
        "original_request_end_exclusive": UtcInstant(ORIGINAL_END_MS * 1_000_000),
        "provider_availability_authority_ref": AUTHORITY_REF,
        "selected_coverage_start": UtcInstant(DAY_START_MS * 1_000_000),
        "selected_coverage_end_exclusive": UtcInstant(COVERAGE_END_MS * 1_000_000),
        "derived_csv_member_name": "KORUUSDT-1h-2026-08-24.discovery-bounded.csv",
        "derived_csv_sha256": sha256(derived),
        "derived_csv_schema_identity": SCHEMA_IDENTITY,
    }
    values.update(changes)
    return BinanceUsdmKoruRetainedPriceBarsAuthorityV1(**values)  # type: ignore[arg-type]


def evidence_for(
    source_kind: BinanceUsdmKoruPriceBarsSourceKindV1,
) -> tuple[BinanceUsdmKoruRetainedPriceBarsAuthorityV1, Evidence]:
    _, artifact_name, _, _ = source_details(source_kind)
    source = (RESEARCH_DATA / artifact_name).read_bytes()
    manifest = (RESEARCH_DATA / "manifest.json").read_bytes()
    lines = source.splitlines(keepends=True)
    derived = lines[0] + b"".join(
        line for line in lines[1:] if line.startswith(b"2026-08-24T")
    )
    authority = retained_authority(source_kind, source, manifest, derived)
    archive, checksum = build_binance_usdm_koru_price_bars_retained_observations_evidence_v1(
        authority, derived
    )
    return authority, Evidence(source, manifest, derived, archive, checksum)



def request_for(
    source_kind: BinanceUsdmKoruPriceBarsSourceKindV1,
    authority: BinanceUsdmKoruRetainedPriceBarsAuthorityV1,
    evidence: Evidence,
) -> BinanceUsdmKoruPriceBarsSourceBoundedRequestV1:
    return BinanceUsdmKoruPriceBarsSourceBoundedRequestV1(
        source_kind=source_kind,
        instrument_id=InstrumentId(VenueId("binance_usdm"), "koru-usdt-tradifi-perpetual"),
        interval="1h",
        utc_date=UTC_DATE,
        archive_available_at_epoch_nanoseconds=(DAY_START_MS + 25 * HOUR_MS) * 1_000_000,
        acquired_at_epoch_nanoseconds=(DAY_START_MS + 26 * HOUR_MS) * 1_000_000,
        expected_archive_sha256=sha256(evidence.archive),
        expected_checksum_sha256=sha256(evidence.checksum),
        authority=authority,
    )


def capture(request: BinanceUsdmKoruPriceBarsSourceBoundedRequestV1, evidence: Evidence):
    return capture_binance_usdm_koru_price_bars_from_retained_observations_v1(
        request,
        evidence.source,
        evidence.manifest,
        evidence.derived,
        evidence.archive,
        evidence.checksum,
    )


def retained_result(source_kind: BinanceUsdmKoruPriceBarsSourceKindV1):
    authority, evidence = evidence_for(source_kind)
    captured = capture(request_for(source_kind, authority, evidence), evidence).result
    assert captured is not None
    result = normalize_binance_usdm_koru_price_bars_source_bounded_v1(captured).result
    assert result is not None
    return result


def close_available_time(event) -> int:
    close_time = event.payload["close_time_milliseconds"]
    assert type(close_time) is int
    return (close_time + 1) * 1_000_000


@pytest.mark.parametrize("source_kind", tuple(BinanceUsdmKoruPriceBarsSourceKindV1))
def test_retained_capture_freezes_all_authority_bytes_and_replays_exactly(source_kind):
    authority, evidence = evidence_for(source_kind)
    request = request_for(source_kind, authority, evidence)
    captured = capture(request, evidence).result
    assert captured is not None
    assert sha256(evidence.manifest) == ACTUAL_MANIFEST_SHA256
    assert sha256(evidence.source) == ACTUAL_SOURCE_SHA256[source_kind]
    assert len(captured.snapshot.members) == 5
    assert {member.member_key for member in captured.snapshot.members} == {
        "retained/base/manifest.json",
        f"retained/source/{authority.source_artifact_path.rsplit('/', 1)[-1]}",
        "derived/KORUUSDT-1h-2026-08-24.discovery-bounded.csv",
        "derived/KORUUSDT-1h-2026-08-24.zip",
        "derived/KORUUSDT-1h-2026-08-24.zip.CHECKSUM",
    }
    assert captured.snapshot.member_bytes("retained/base/manifest.json") == evidence.manifest
    assert captured.snapshot.member_bytes(
        f"retained/source/{authority.source_artifact_path.rsplit('/', 1)[-1]}"
    ) == evidence.source
    assert captured.snapshot.member_bytes(
        "derived/KORUUSDT-1h-2026-08-24.discovery-bounded.csv"
    ) == evidence.derived
    assert captured.snapshot.member_bytes(
        "derived/KORUUSDT-1h-2026-08-24.zip"
    ) == evidence.archive
    assert captured.snapshot.member_bytes(
        "derived/KORUUSDT-1h-2026-08-24.zip.CHECKSUM"
    ) == evidence.checksum
    first = normalize_binance_usdm_koru_price_bars_source_bounded_v1(captured).result
    replay = normalize_binance_usdm_koru_price_bars_source_bounded_v1(captured).result
    assert first is not None and replay is not None
    assert first.normalization_hash == replay.normalization_hash
    assert first.retained_row_count == first.projected_row_count == 11
    assert all(
        event.available_time.epoch_nanoseconds == close_available_time(event)
        and event.payload["provider_availability_authority_ref"] == AUTHORITY_REF
        and event.payload["source_acquired_at_epoch_nanoseconds"]
        == authority.source_acquired_at_epoch_nanoseconds
        and event.payload["local_retained_acquired_at_epoch_nanoseconds"]
        == request.acquired_at_epoch_nanoseconds
        for event in first.events
    )


def test_real_mixed_precision_is_quantized_to_scale8_without_float() -> None:
    result = retained_result(BinanceUsdmKoruPriceBarsSourceKindV1.MARK_PRICE)
    strategy = tuple(
        event for event in result.events if event.payload["price_purpose"] == "strategy"
    )
    assert strategy[0].payload["low_units"] == 2_049_000_000  # 20.49
    assert strategy[-1].payload["close_units"] == 1_970_000_000  # 19.7
    assert result.capture.snapshot.member_bytes(
        "derived/KORUUSDT-1h-2026-08-24.discovery-bounded.csv"
    ).endswith(b",19.7,2026-08-24T10:59:59.999Z,0.0\n")


@pytest.mark.parametrize("bad", ["01", "1.", ".1", "1e1", "1.000000000"])
def test_retained_decimal_grammar_rejects_noncanonical_or_over_scale(bad: str) -> None:
    authority, evidence = evidence_for(BinanceUsdmKoruPriceBarsSourceKindV1.MARK_PRICE)
    changed = evidence.derived.replace(b"21.09668125", bad.encode(), 1)
    fabricated = replace(authority, derived_csv_sha256=sha256(changed))
    archive, checksum = build_binance_usdm_koru_price_bars_retained_observations_evidence_v1(fabricated, changed)
    fabricated_evidence = replace(evidence, derived=changed, archive=archive, checksum=checksum)
    outcome = capture(
        request_for(BinanceUsdmKoruPriceBarsSourceKindV1.MARK_PRICE, fabricated, fabricated_evidence),
        fabricated_evidence,
    )
    assert outcome.failure is not None
    assert outcome.failure.code is BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.SOURCE_HASH_MISMATCH


def test_caller_hashes_and_lexeme_equivalent_rows_cannot_self_attest() -> None:
    kind = BinanceUsdmKoruPriceBarsSourceKindV1.MARK_PRICE
    authority, evidence = evidence_for(kind)
    fabricated_hash = replace(authority, source_artifact_sha256="sha256:" + "1" * 64)
    assert capture(request_for(kind, fabricated_hash, evidence), evidence).failure is not None

    changed = evidence.derived.replace(b"20.49", b"20.49000000", 1)
    changed_source = evidence.source.replace(b"20.49", b"20.49000000", 1)
    changed_manifest_value = json.loads(evidence.manifest)
    mark_artifact = next(
        artifact
        for artifact in changed_manifest_value["artifacts"]
        if artifact["path"] == "binance_mark_raw.csv"
    )
    mark_artifact["sha256"] = sha256(changed_source)
    changed_manifest = manifest_bytes(changed_manifest_value)
    fabricated_rows = replace(
        authority,
        source_artifact_sha256=sha256(changed_source),
        base_manifest_file_sha256=sha256(changed_manifest),
        base_manifest_identity=json.loads(changed_manifest)["manifest_sha256"],
        derived_csv_sha256=sha256(changed),
    )
    archive, checksum = build_binance_usdm_koru_price_bars_retained_observations_evidence_v1(fabricated_rows, changed)
    fabricated_evidence = replace(
        evidence,
        source=changed_source,
        manifest=changed_manifest,
        derived=changed,
        archive=archive,
        checksum=checksum,
    )
    outcome = capture(request_for(kind, fabricated_rows, fabricated_evidence), fabricated_evidence)
    assert outcome.failure is not None
    assert outcome.failure.subject == "retained_authority"


def test_manifest_original_request_binding_is_not_selected_coverage() -> None:
    kind = BinanceUsdmKoruPriceBarsSourceKindV1.INDEX_PRICE
    authority, evidence = evidence_for(kind)
    assert authority.original_request_start == UtcInstant(ORIGINAL_START_MS * 1_000_000)
    assert authority.original_request_end_exclusive == UtcInstant(ORIGINAL_END_MS * 1_000_000)
    assert authority.selected_coverage_start == UtcInstant(DAY_START_MS * 1_000_000)
    assert authority.original_binance_parameter_sha256 == canonical_sha256(
        {"endTime": ORIGINAL_END_MS - 1, "interval": "1h", "limit": 1000, "pair": "KORUUSDT", "startTime": ORIGINAL_START_MS}
    )
    assert capture(request_for(kind, authority, evidence), evidence).result is not None


def test_wrong_endpoint_or_provider_authority_ref_fails() -> None:
    kind = BinanceUsdmKoruPriceBarsSourceKindV1.MARK_PRICE
    authority, evidence = evidence_for(kind)
    with pytest.raises(ValueError, match="availability authority"):
        replace(authority, provider_availability_authority_ref="caller.selected.v1")

    manifest = json.loads(evidence.manifest)
    mark_source = next(
        source
        for source in manifest["sources"]
        if source["source_id"] == "binance_futures_mark_price_kline"
    )
    mark_source["endpoint"] = "https://fapi.binance.com/fapi/v1/indexPriceKlines"
    changed_manifest = manifest_bytes(manifest)
    changed_evidence = replace(evidence, manifest=changed_manifest)
    changed_authority = replace(
        authority,
        base_manifest_file_sha256=sha256(changed_manifest),
        base_manifest_identity=json.loads(changed_manifest)["manifest_sha256"],
    )
    assert capture(request_for(kind, changed_authority, changed_evidence), changed_evidence).failure is not None


def test_capture_modes_remain_strictly_separate() -> None:
    kind = BinanceUsdmKoruPriceBarsSourceKindV1.MARK_PRICE
    authority, evidence = evidence_for(kind)
    request = request_for(kind, authority, evidence)
    assert capture_binance_usdm_koru_price_bars_source_bounded_v1(request, lambda _: (200, b"")).failure is not None
    official_request = replace(request, authority=None, utc_date="2026-08-23")
    assert capture(official_request, evidence).failure is not None


def test_retained_raw_price_preflight_covers_strategy_liquidation_margin_valuation_and_funding() -> None:
    """Before p01, all raw-price purposes are checked against execution's tick lattice."""
    import csv
    from decimal import Decimal

    root = RESEARCH_DATA
    bars = tuple(
        value
        for name in ("binance_mark_raw.csv", "binance_index_raw.csv")
        for value in csv.DictReader((root / name).read_text().splitlines())
    )
    funding = json.loads(
        (root.parent / "koru-funding-history-v1" / "funding-history.json").read_text()
    )
    tick = Decimal("0.01")
    non_tick = lambda value: Decimal(value) % tick != 0
    assert any(non_tick(row[key]) for row in bars for key in ("open", "high", "low", "close"))
    assert any(non_tick(row["markPrice"]) for row in funding)

    from tests.bundle_builder.providers.binance_usdm.test_koru_aggtrades_retained_rest_v1 import ROWS
    assert ROWS and all(not non_tick(row["p"]) for row in ROWS)
