from __future__ import annotations

import json
from pathlib import Path

import pytest

from crypto_quant_bundle_builder import (
    LocalMarketBundleRepository,
    LocalMarketBundleRepositoryConfig,
    RawSourceMember,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
    validate_market_bundle_v1,
)
from crypto_quant_bundle_builder.binance_usdm_funding_rate_archive import (
    BinanceUsdmArchiveCaptureResult,
    BinanceUsdmArchiveFailureCode,
    BinanceUsdmFundingRateArchiveRequest,
    capture_binance_usdm_funding_rate_archive,
    normalize_binance_usdm_funding_rate_archive,
)
from crypto_quant_domain import InstrumentId, UtcInstant, VenueId, canonical_bytes


FIXTURE = Path(__file__).parents[3] / "fixtures/market_data/providers/binance_usdm/funding-rate-v1"
EXPECTED = json.loads((FIXTURE / "evidence.expected.json").read_text())
ARCHIVE = (FIXTURE / "BTCUSDT-fundingRate-2020-01.zip").read_bytes()
CHECKSUM = (FIXTURE / "BTCUSDT-fundingRate-2020-01.zip.CHECKSUM").read_bytes()
ACQUIRED_AT = EXPECTED["snapshot"]["members"][0]["acquired_at_epoch_nanoseconds"]


class FakeFetch:
    def __init__(self, responses: dict[str, tuple[tuple[int, bytes], ...]]) -> None:
        self.responses = {key: list(value) for key, value in responses.items()}

    def __call__(self, url: str) -> tuple[int, bytes]:
        return self.responses[url].pop(0)


def request() -> BinanceUsdmFundingRateArchiveRequest:
    return BinanceUsdmFundingRateArchiveRequest(
        InstrumentId(VenueId("binance_usdm"), "btc-usdt-perpetual"), ACQUIRED_AT
    )


def captured() -> BinanceUsdmArchiveCaptureResult:
    archive_url, checksum_url = request().urls
    outcome = capture_binance_usdm_funding_rate_archive(
        request(), FakeFetch({archive_url: ((200, ARCHIVE),), checksum_url: ((200, CHECKSUM),)})
    )
    assert outcome.failure is None
    assert outcome.result is not None
    return outcome.result


def test_request_capture_retry_precedence_and_atomicity() -> None:
    archive_url, checksum_url = request().urls
    assert archive_url.endswith("/BTCUSDT/BTCUSDT-fundingRate-2020-01.zip")
    outcome = capture_binance_usdm_funding_rate_archive(
        request(),
        FakeFetch(
            {
                archive_url: ((500, b""), (429, b""), (200, ARCHIVE)),
                checksum_url: ((503, b""), (200, CHECKSUM)),
            }
        ),
    )
    assert outcome.failure is None
    assert outcome.result is not None
    assert outcome.result.snapshot.to_canonical_dict() == EXPECTED["snapshot"]
    assert request().request_hash == EXPECTED["provider_result"]["request_hash"]
    assert outcome.result.archive_attempts == 3
    assert outcome.result.checksum_attempts == 2

    replacement = bytearray(ARCHIVE)
    replacement[-1] ^= 1
    failed = capture_binance_usdm_funding_rate_archive(
        request(),
        FakeFetch({archive_url: ((200, bytes(replacement)),), checksum_url: ((404, b""),)}),
    )
    assert failed.result is None
    assert failed.failure is not None
    assert failed.failure.code is BinanceUsdmArchiveFailureCode.SOURCE_SCHEMA_MISMATCH

    with pytest.raises(ValueError, match="frozen source capture"):
        BinanceUsdmFundingRateArchiveRequest(request().instrument_id, 0)


@pytest.mark.parametrize(
    ("archive_responses", "checksum_responses", "expected"),
    (
        (((500, b""),) * 3, ((200, CHECKSUM),), BinanceUsdmArchiveFailureCode.PROVIDER_UNAVAILABLE),
        (((401, b""),), ((429, b""),) * 3, BinanceUsdmArchiveFailureCode.AUTHENTICATION_REJECTED),
        (((429, b""),) * 3, ((404, b""),), BinanceUsdmArchiveFailureCode.RATE_LIMIT_EXHAUSTED),
        (((404, b""),), ((200, CHECKSUM),), BinanceUsdmArchiveFailureCode.DATA_GAP_DETECTED),
    ),
)
def test_exhausted_and_mixed_provider_failures_are_atomic(
    archive_responses: tuple[tuple[int, bytes], ...],
    checksum_responses: tuple[tuple[int, bytes], ...],
    expected: BinanceUsdmArchiveFailureCode,
) -> None:
    archive_url, checksum_url = request().urls
    outcome = capture_binance_usdm_funding_rate_archive(
        request(),
        FakeFetch({archive_url: archive_responses, checksum_url: checksum_responses}),
    )
    assert outcome.result is None
    assert outcome.failure is not None
    assert outcome.failure.code is expected


def test_restart_and_duplicate_response_preserve_content_identity() -> None:
    archive_url, checksum_url = request().urls
    interrupted = capture_binance_usdm_funding_rate_archive(
        request(),
        FakeFetch(
            {
                archive_url: ((500, b""),) * 3,
                checksum_url: ((200, CHECKSUM),),
            }
        ),
    )
    assert interrupted.result is None

    duplicate_fetch = FakeFetch(
        {
            archive_url: ((200, ARCHIVE), (200, ARCHIVE)),
            checksum_url: ((200, CHECKSUM), (200, CHECKSUM)),
        }
    )
    first = capture_binance_usdm_funding_rate_archive(request(), duplicate_fetch)
    restarted = capture_binance_usdm_funding_rate_archive(request(), duplicate_fetch)
    assert first.result is not None
    assert restarted.result is not None
    assert first.result.capture_hash == restarted.result.capture_hash
    first_normalized = normalize_binance_usdm_funding_rate_archive(first.result)
    restarted_normalized = normalize_binance_usdm_funding_rate_archive(restarted.result)
    assert first_normalized.result is not None
    assert restarted_normalized.result is not None
    assert (
        first_normalized.result.normalization_hash
        == restarted_normalized.result.normalization_hash
    )


def test_normalization_preserves_jitter_raw_rate_and_exact_decimal(tmp_path: Path) -> None:
    capture = captured()
    assert capture.capture_hash == EXPECTED["provider_result"]["capture_hash"]
    outcome = normalize_binance_usdm_funding_rate_archive(capture)
    assert outcome.failure is None
    assert outcome.result is not None
    result = outcome.result
    assert len(result.events) == 93
    first, scientific, last = result.events[0], result.events[10], result.events[-1]
    assert first.stream_key == "binance_usdm.funding_rate.publications.btcusdt.v1"
    assert first.event_type == "binance_usdm_funding_rate_publication.v1"
    assert first.capability.key == "binance_usdm.funding-publications"
    assert first.payload == {
        "funding_purpose": "funding",
        "calc_time_milliseconds": 1_577_836_800_000,
        "nominal_slot_time_milliseconds": 1_577_836_800_000,
        "slot_jitter_milliseconds": 0,
        "funding_interval_hours": 8,
        "raw_funding_rate": "-0.00012359",
        "funding_rate": "-0.00012359",
        "funding_rate_units": -12_359,
        "funding_rate_scale": 8,
        "source_record_hash": first.payload["source_record_hash"],
    }
    assert scientific.payload["raw_funding_rate"] == "8.4E-7"
    assert scientific.payload["funding_rate"] == "0.00000084"
    assert scientific.payload["funding_rate_units"] == 84
    assert scientific.payload["funding_rate_scale"] == 8
    assert "mark_price" not in scientific.payload
    assert first.event_time == UtcInstant(1_577_836_800_000_000_000)
    assert first.available_time == UtcInstant(ACQUIRED_AT)
    assert last.payload["slot_jitter_milliseconds"] == 0
    trace = result.traces[0]
    assert trace.snapshot_id == EXPECTED["snapshot"]["snapshot_id"]
    assert trace.source_record_hash == first.payload["source_record_hash"]
    assert trace.event_id == first.event_id
    assert trace.event_hash == first.event_hash
    assert result.decision_grade_eligible is False
    assert result.deployment_authorized is False
    assert result.normalization_hash == EXPECTED["provider_result"]["normalization_hash"]
    assert first.event_hash == EXPECTED["provider_result"]["first_event_hash"]
    assert scientific.event_hash == EXPECTED["provider_result"]["scientific_event_hash"]
    assert last.event_hash == EXPECTED["provider_result"]["last_event_hash"]

    validation = validate_market_bundle_v1(
        bundle_key="binance-usdm-funding-rate-btcusdt-2020-01",
        schema_version=1,
        coverage_start=UtcInstant(1_577_836_800_000_000_000),
        coverage_end_exclusive=UtcInstant(1_580_486_400_003_000_000),
        instrument_catalog_hash="sha256:" + "0" * 64,
        events=result.events,
    )
    assert validation.failure is None
    assert validation.manifest is not None
    manifest = validation.manifest
    assert manifest.content_hash == EXPECTED["provider_result"]["manifest_content_hash"]
    assert manifest.streams[0].content_hash == EXPECTED["provider_result"]["stream_content_hash"]
    publication = LocalMarketBundleRepository(
        config=LocalMarketBundleRepositoryConfig(tmp_path.resolve())
    ).publish_market_bundle_v1(
        manifest=manifest,
        stream_payloads={manifest.streams[0].stream_key: canonical_bytes(result.events)},
        retention_policy_ref="retention.g12l-binance-funding-rate-v1",
    )
    assert publication.failure is None
    assert publication.result is not None
    assert publication.result.bundle_ref.to_canonical_dict() == EXPECTED["provider_result"]["bundle_ref"]
    assert publication.result.retention_proof.proof_hash == EXPECTED["provider_result"]["retention_proof_hash"]


def test_normalizer_rejects_wrong_provenance_and_request_mutation() -> None:
    capture = captured()
    object.__setattr__(
        capture.request,
        "instrument_id",
        InstrumentId(VenueId("binance_usdm"), "eth-usdt-perpetual"),
    )
    rejected_request = normalize_binance_usdm_funding_rate_archive(capture)
    assert rejected_request.result is None
    assert rejected_request.failure is not None
    assert rejected_request.failure.code is BinanceUsdmArchiveFailureCode.CONFIGURATION_INVALID

    wrong = freeze_source_snapshot(
        members=(
            RawSourceMember(
                "archive/BTCUSDT-fundingRate-2020-01.zip",
                ARCHIVE,
                "0644",
                ACQUIRED_AT,
                EXPECTED["source_hashes"]["archive_sha256"],
            ),
            RawSourceMember(
                "archive/BTCUSDT-fundingRate-2020-01.zip.CHECKSUM",
                CHECKSUM,
                "0644",
                ACQUIRED_AT,
                EXPECTED["source_hashes"]["checksum_sha256"],
            ),
        ),
        provenance=SourceSnapshotProvenance(
            vendor_key="binance.public_data",
            source_key="binance.public_data.futures.um.monthly.funding_rate.btcusdt.2020-01",
            license_ref="wrong.license",
            retention_policy_ref="wrong.retention",
        ),
    ).snapshot
    assert wrong is not None
    rejected = normalize_binance_usdm_funding_rate_archive(
        BinanceUsdmArchiveCaptureResult(request(), wrong, 1, 1)
    )
    assert rejected.result is None
    assert rejected.failure is not None
    assert rejected.failure.code is BinanceUsdmArchiveFailureCode.CONFIGURATION_INVALID
