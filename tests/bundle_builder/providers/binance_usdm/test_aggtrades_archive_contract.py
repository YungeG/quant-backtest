from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import cast

import pytest

from crypto_quant_bundle_builder import (
    LocalMarketBundleRepository,
    LocalMarketBundleRepositoryConfig,
    RawSourceMember,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
    validate_market_bundle_v1,
)
from crypto_quant_bundle_builder.binance_usdm_aggtrades_archive import (
    BinanceUsdmAggregateTradesArchiveRequest,
    BinanceUsdmArchiveCaptureResult,
    BinanceUsdmArchiveFailureCode,
    capture_binance_usdm_aggregate_trades_archive,
    normalize_binance_usdm_aggregate_trades_archive,
)
from crypto_quant_domain import InstrumentId, UtcInstant, VenueId, canonical_bytes


FIXTURE = Path(__file__).parents[3] / "fixtures/market_data/providers/binance_usdm/aggtrades-v1"
EXPECTED = json.loads((FIXTURE / "evidence.expected.json").read_text())
ARCHIVE = (FIXTURE / "BTCUSDT-aggTrades-2020-01-01.zip").read_bytes()
CHECKSUM = (FIXTURE / "BTCUSDT-aggTrades-2020-01-01.zip.CHECKSUM").read_bytes()
ACQUIRED_AT = EXPECTED["snapshot"]["members"][0]["acquired_at_epoch_nanoseconds"]


class FakeFetch:
    def __init__(self, responses: dict[str, tuple[tuple[int, bytes], ...]]) -> None:
        self.responses = {key: list(value) for key, value in responses.items()}
        self.calls: list[str] = []

    def __call__(self, url: str) -> tuple[int, bytes]:
        self.calls.append(url)
        return self.responses[url].pop(0)


def request() -> BinanceUsdmAggregateTradesArchiveRequest:
    return BinanceUsdmAggregateTradesArchiveRequest(
        InstrumentId(VenueId("binance_usdm"), "btc-usdt-perpetual"), ACQUIRED_AT
    )


def captured():
    archive_url, checksum_url = request().urls
    outcome = capture_binance_usdm_aggregate_trades_archive(
        request(), FakeFetch({archive_url: ((200, ARCHIVE),), checksum_url: ((200, CHECKSUM),)})
    )
    assert outcome.failure is None
    assert outcome.result is not None
    return outcome.result


def test_request_and_capture_are_exact_retryable_and_atomic() -> None:
    archive_url, checksum_url = request().urls
    assert archive_url.endswith("/BTCUSDT/BTCUSDT-aggTrades-2020-01-01.zip")
    fetch = FakeFetch(
        {
            archive_url: ((500, b""), (429, b""), (200, ARCHIVE)),
            checksum_url: ((503, b""), (200, CHECKSUM)),
        }
    )
    outcome = capture_binance_usdm_aggregate_trades_archive(request(), fetch)
    assert outcome.failure is None
    assert outcome.result is not None
    assert outcome.result.snapshot.to_canonical_dict() == EXPECTED["snapshot"]
    assert request().request_hash == EXPECTED["provider_result"]["request_hash"]
    assert outcome.result.archive_attempts == 3
    assert outcome.result.checksum_attempts == 2

    replacement = bytearray(ARCHIVE)
    replacement[-1] ^= 1
    failed = capture_binance_usdm_aggregate_trades_archive(
        request(),
        FakeFetch({archive_url: ((200, bytes(replacement)),), checksum_url: ((404, b""),)}),
    )
    assert failed.result is None
    assert failed.failure is not None
    assert failed.failure.code is BinanceUsdmArchiveFailureCode.SOURCE_SCHEMA_MISMATCH

    with pytest.raises(ValueError, match="frozen source capture"):
        BinanceUsdmAggregateTradesArchiveRequest(request().instrument_id, 0)
    with pytest.raises(ValueError, match="exact request"):
        BinanceUsdmArchiveCaptureResult(
            cast(BinanceUsdmAggregateTradesArchiveRequest, object()),
            outcome.result.snapshot,
            1,
            1,
        )


def test_capture_maps_retry_exhaustion_without_partial_snapshot() -> None:
    archive_url, checksum_url = request().urls
    outcome = capture_binance_usdm_aggregate_trades_archive(
        request(),
        FakeFetch(
            {
                archive_url: ((500, b""), (500, b""), (500, b"")),
                checksum_url: ((429, b""), (429, b""), (429, b"")),
            }
        ),
    )
    assert outcome.result is None
    assert outcome.failure is not None
    assert outcome.failure.code is BinanceUsdmArchiveFailureCode.PROVIDER_UNAVAILABLE


def test_normalization_emits_execution_reference_stream_and_publishes(tmp_path: Path) -> None:
    capture = captured()
    assert capture.capture_hash == EXPECTED["provider_result"]["capture_hash"]
    outcome = normalize_binance_usdm_aggregate_trades_archive(capture)
    assert outcome.failure is None
    assert outcome.result is not None
    result = outcome.result
    assert len(result.events) == 71_359
    first, last = result.events[0], result.events[-1]
    assert first.stream_key == "binance_usdm.aggregate_trades.execution_reference.btcusdt.v1"
    assert first.event_type == "binance_usdm_aggregate_trade.v1"
    assert first.payload == {
        "price_purpose": "execution_reference",
        "aggregate_trade_id": 18_374_167,
        "price": "7189.43",
        "price_units": 718_943,
        "price_scale": 2,
        "quantity": "0.030",
        "quantity_units": 30,
        "quantity_scale": 3,
        "first_trade_id": 25_247_504,
        "last_trade_id": 25_247_504,
        "transaction_time_milliseconds": 1_577_836_801_481,
        "is_buyer_maker": True,
        "source_record_hash": first.payload["source_record_hash"],
    }
    assert first.event_time == UtcInstant(1_577_836_801_481_000_000)
    assert first.available_time == UtcInstant(ACQUIRED_AT)
    assert last.payload["aggregate_trade_id"] == 18_445_525
    trace = result.traces[0]
    assert trace.snapshot_id == EXPECTED["snapshot"]["snapshot_id"]
    assert trace.source_record_hash == first.payload["source_record_hash"]
    assert trace.event_id == first.event_id
    assert trace.event_hash == first.event_hash
    assert result.decision_grade_eligible is False
    assert result.deployment_authorized is False
    assert result.normalization_hash == EXPECTED["provider_result"]["normalization_hash"]
    assert first.event_hash == EXPECTED["provider_result"]["first_event_hash"]
    assert last.event_hash == EXPECTED["provider_result"]["last_event_hash"]

    validation = validate_market_bundle_v1(
        bundle_key="binance-usdm-aggregate-trades-btcusdt-2020-01-01",
        schema_version=1,
        coverage_start=UtcInstant(1_577_836_800_000_000_000),
        coverage_end_exclusive=UtcInstant(1_577_923_200_000_000_000),
        instrument_catalog_hash="sha256:" + "0" * 64,
        events=result.events,
    )
    assert validation.failure is None
    assert validation.manifest is not None
    manifest = validation.manifest
    assert manifest.content_hash == EXPECTED["provider_result"]["manifest_content_hash"]
    assert manifest.streams[0].content_hash == EXPECTED["provider_result"]["stream_content_hash"]
    payloads = {manifest.streams[0].stream_key: canonical_bytes(result.events)}
    publication = LocalMarketBundleRepository(
        config=LocalMarketBundleRepositoryConfig(tmp_path.resolve())
    ).publish_market_bundle_v1(
        manifest=manifest,
        stream_payloads=payloads,
        retention_policy_ref="retention.g12l-binance-aggtrades-v1",
    )
    assert publication.failure is None
    assert publication.result is not None
    assert publication.result.bundle_ref.to_canonical_dict() == EXPECTED["provider_result"]["bundle_ref"]
    assert publication.result.retention_proof.proof_hash == EXPECTED["provider_result"]["retention_proof_hash"]


def test_normalizer_rejects_non_authoritative_capture_and_malformed_zip() -> None:
    mutated = captured()
    object.__setattr__(
        mutated.request,
        "instrument_id",
        InstrumentId(VenueId("binance_usdm"), "eth-usdt-perpetual"),
    )
    rejected_request = normalize_binance_usdm_aggregate_trades_archive(mutated)
    assert rejected_request.result is None
    assert rejected_request.failure is not None
    assert rejected_request.failure.code is BinanceUsdmArchiveFailureCode.CONFIGURATION_INVALID

    archive_url, checksum_url = request().urls
    replacement = bytearray(ARCHIVE)
    replacement[-10] ^= 1
    capture = capture_binance_usdm_aggregate_trades_archive(
        request(),
        FakeFetch({archive_url: ((200, bytes(replacement)),), checksum_url: ((200, CHECKSUM),)}),
    )
    assert capture.result is None
    assert capture.failure is not None
    assert capture.failure.code is BinanceUsdmArchiveFailureCode.SOURCE_SCHEMA_MISMATCH

    wrong = freeze_source_snapshot(
        members=(
            RawSourceMember(
                "archive/BTCUSDT-aggTrades-2020-01-01.zip",
                ARCHIVE,
                "0644",
                ACQUIRED_AT,
                EXPECTED["source_hashes"]["archive_sha256"],
            ),
            RawSourceMember(
                "archive/BTCUSDT-aggTrades-2020-01-01.zip.CHECKSUM",
                CHECKSUM,
                "0644",
                ACQUIRED_AT,
                EXPECTED["source_hashes"]["checksum_sha256"],
            ),
        ),
        provenance=SourceSnapshotProvenance(
            vendor_key="binance.public_data",
            source_key="binance.public_data.futures.um.daily.aggtrades.btcusdt.2020-01-01",
            license_ref="wrong.license",
            retention_policy_ref="wrong.retention",
        ),
    ).snapshot
    assert wrong is not None
    rejected = normalize_binance_usdm_aggregate_trades_archive(
        BinanceUsdmArchiveCaptureResult(request(), wrong, 1, 1)
    )
    assert rejected.result is None
    assert rejected.failure is not None
    assert rejected.failure.code is BinanceUsdmArchiveFailureCode.CONFIGURATION_INVALID
    assert hashlib.sha256(ARCHIVE).hexdigest() == EXPECTED["source_hashes"]["archive_sha256"][7:]
