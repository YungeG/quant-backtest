from __future__ import annotations

import csv
import hashlib
import io
import json
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from crypto_quant_bundle_builder import (
    LocalMarketBundleRepository,
    LocalMarketBundleRepositoryConfig,
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
)

from crypto_quant_bundle_builder.binance_usdm_mark_price_archive import (
    BinanceUsdmArchiveCaptureResult,
    BinanceUsdmArchiveFailureCode,
    BinanceUsdmMarkPriceArchiveRequest,
    capture_binance_usdm_mark_price_archive,
    normalize_binance_usdm_mark_price_archive,
)


FIXTURE = (
    Path(__file__).parents[3]
    / "fixtures/market_data/providers/binance_usdm/mark-price-klines-v1"
)
ARCHIVE = (FIXTURE / "BTCUSDT-1m-2024-01-01.zip").read_bytes()
CHECKSUM = (FIXTURE / "BTCUSDT-1m-2024-01-01.zip.CHECKSUM").read_bytes()
EXPECTED = json.loads((FIXTURE / "evidence.expected.json").read_text())
ACQUIRED_AT = EXPECTED["snapshot"]["members"][0][
    "acquired_at_epoch_nanoseconds"
]


class FakeFetch:
    def __init__(self, responses: dict[str, Iterable[tuple[int, bytes]]]) -> None:
        self.responses = {url: iter(values) for url, values in responses.items()}

    def __call__(self, url: str) -> tuple[int, bytes]:
        return next(self.responses[url])


def request() -> BinanceUsdmMarkPriceArchiveRequest:
    return BinanceUsdmMarkPriceArchiveRequest(
        instrument_id=InstrumentId(
            VenueId("binance_usdm"), "btc-usdt-perpetual"
        ),
        acquired_at_epoch_nanoseconds=ACQUIRED_AT,
    )


def test_capture_freezes_exact_real_archive_after_bounded_retry() -> None:
    value = request()
    archive_url, checksum_url = value.urls
    outcome = capture_binance_usdm_mark_price_archive(
        value,
        FakeFetch(
            {
                archive_url: ((500, b""), (200, ARCHIVE)),
                checksum_url: ((429, b""), (200, CHECKSUM)),
            }
        ),
    )

    assert outcome.failure is None
    assert outcome.result is not None
    assert outcome.result.archive_attempts == 2
    assert outcome.result.checksum_attempts == 2
    assert outcome.result.snapshot.to_canonical_dict() == EXPECTED["snapshot"]
    assert outcome.result.decision_grade_eligible is False
    assert outcome.result.deployment_authorized is False


def captured(archive: bytes = ARCHIVE, checksum: bytes = CHECKSUM):
    value = request()
    archive_url, checksum_url = value.urls
    outcome = capture_binance_usdm_mark_price_archive(
        value,
        FakeFetch(
            {
                archive_url: ((200, archive),),
                checksum_url: ((200, checksum),),
            }
        ),
    )
    assert outcome.result is not None
    return outcome.result


def rewritten_archive(mutator) -> tuple[bytes, bytes]:
    with ZipFile(io.BytesIO(ARCHIVE)) as original:
        name = original.namelist()[0]
        rows = list(csv.reader(io.StringIO(original.read(name).decode())))
    mutator(rows)
    output = io.StringIO(newline="")
    csv.writer(output, lineterminator="\n").writerows(rows)
    target = io.BytesIO()
    with ZipFile(target, "w", ZIP_DEFLATED) as rewritten:
        rewritten.writestr(name, output.getvalue().encode())
    archive = target.getvalue()
    digest = hashlib.sha256(archive).hexdigest()
    return archive, f"{digest}  BTCUSDT-1m-2024-01-01.zip\n".encode()


def test_capture_uses_failure_precedence_and_returns_no_partial_snapshot() -> None:
    value = request()
    archive_url, checksum_url = value.urls
    outcome = capture_binance_usdm_mark_price_archive(
        value,
        FakeFetch(
            {
                archive_url: ((404, b""),),
                checksum_url: ((500, b""),) * 3,
            }
        ),
    )

    assert outcome.result is None
    assert outcome.failure is not None
    assert outcome.failure.code is BinanceUsdmArchiveFailureCode.PROVIDER_UNAVAILABLE


@pytest.mark.parametrize(
    ("responses", "expected"),
    [
        (((401, b""),), BinanceUsdmArchiveFailureCode.AUTHENTICATION_REJECTED),
        (((403, b""),), BinanceUsdmArchiveFailureCode.AUTHENTICATION_REJECTED),
        (((429, b""),) * 3, BinanceUsdmArchiveFailureCode.RATE_LIMIT_EXHAUSTED),
        (((418, b""),), BinanceUsdmArchiveFailureCode.SOURCE_SCHEMA_MISMATCH),
    ],
)
def test_capture_maps_provider_statuses_without_partial_snapshot(
    responses: tuple[tuple[int, bytes], ...],
    expected: BinanceUsdmArchiveFailureCode,
) -> None:
    value = request()
    archive_url, checksum_url = value.urls
    outcome = capture_binance_usdm_mark_price_archive(
        value,
        FakeFetch(
            {
                archive_url: responses,
                checksum_url: ((200, CHECKSUM),),
            }
        ),
    )
    assert outcome.result is None
    assert outcome.failure is not None
    assert outcome.failure.code is expected


def test_normalization_emits_three_purpose_separated_streams_with_late_availability() -> None:
    capture_result = captured()
    assert capture_result.request.request_hash == EXPECTED["provider_result"][
        "request_hash"
    ]
    assert capture_result.capture_hash == EXPECTED["provider_result"]["capture_hash"]
    result = normalize_binance_usdm_mark_price_archive(capture_result)

    assert result.failure is None
    assert result.result is not None
    assert len(result.result.events) == 4320
    assert Counter(event.stream_key for event in result.result.events) == {
        "binance_usdm.mark_price.valuation.btcusdt.1m.v1": 1440,
        "binance_usdm.mark_price.margin.btcusdt.1m.v1": 1440,
        "binance_usdm.mark_price.liquidation.btcusdt.1m.v1": 1440,
    }
    valuation, margin, liquidation = result.result.events[:3]
    assert valuation.payload["price_purpose"] == "valuation"
    assert valuation.payload["price_units"] == 4_232_690_000_000
    assert valuation.payload["price_scale"] == 8
    assert margin.payload["price_purpose"] == "margin"
    assert liquidation.payload["price_purpose"] == "liquidation"
    assert liquidation.payload["low_units"] == 4_228_970_000_000
    assert liquidation.payload["high_units"] == 4_232_834_025_532
    assert valuation.event_time == UtcInstant(1_704_067_259_999_000_000)
    assert valuation.available_time == UtcInstant(ACQUIRED_AT)
    trace = result.result.traces[0]
    assert trace.snapshot_id == EXPECTED["snapshot"]["snapshot_id"]
    assert trace.provenance_hash == EXPECTED["snapshot"]["provenance_hash"]
    assert trace.source_key == EXPECTED["snapshot"]["provenance"]["source_key"]
    assert trace.archive_member_key == "archive/BTCUSDT-1m-2024-01-01.zip"
    assert trace.checksum_member_key == "archive/BTCUSDT-1m-2024-01-01.zip.CHECKSUM"
    assert trace.archive_member_hash == EXPECTED["source_hashes"]["archive_sha256"]
    assert trace.checksum_member_hash == EXPECTED["source_hashes"]["checksum_sha256"]
    assert trace.source_record_hash == valuation.payload["source_record_hash"]
    assert trace.event_id == valuation.event_id
    assert trace.event_hash == valuation.event_hash
    assert result.result.decision_grade_eligible is False
    assert result.result.deployment_authorized is False
    assert (
        result.result.normalization_hash
        == EXPECTED["provider_result"]["normalization_hash"]
    )
    assert valuation.event_hash == EXPECTED["provider_result"]["first_event_hash"]
    assert (
        result.result.events[-1].event_hash
        == EXPECTED["provider_result"]["last_event_hash"]
    )


def test_provider_events_flow_through_g12c_and_g12d(tmp_path: Path) -> None:
    normalized = normalize_binance_usdm_mark_price_archive(captured())
    assert normalized.result is not None
    validation = validate_market_bundle_v1(
        bundle_key="binance-usdm-mark-price-btcusdt-2024-01-01",
        schema_version=1,
        coverage_start=UtcInstant(1_704_067_200_000_000_000),
        coverage_end_exclusive=UtcInstant(1_704_153_600_000_000_000),
        instrument_catalog_hash="sha256:" + "0" * 64,
        events=normalized.result.events,
    )
    assert validation.failure is None
    assert validation.manifest is not None
    assert tuple(stream.event_count for stream in validation.manifest.streams) == (
        1440,
        1440,
        1440,
    )
    assert validation.manifest.content_hash == EXPECTED["provider_result"][
        "manifest_content_hash"
    ]
    assert {
        stream.stream_key: stream.content_hash
        for stream in validation.manifest.streams
    } == EXPECTED["provider_result"]["stream_content_hashes"]
    grouped = {
        stream.stream_key: canonical_bytes(
            tuple(
                event
                for event in normalized.result.events
                if event.stream_key == stream.stream_key
            )
        )
        for stream in validation.manifest.streams
    }
    publication = LocalMarketBundleRepository(
        config=LocalMarketBundleRepositoryConfig(tmp_path.resolve())
    ).publish_market_bundle_v1(
        manifest=validation.manifest,
        stream_payloads=grouped,
        retention_policy_ref="retention.g12l-binance-mark-price-klines-v1",
    )
    assert publication.failure is None
    assert publication.result is not None
    assert publication.result.already_published is False
    assert publication.result.bundle_ref.to_canonical_dict() == EXPECTED[
        "provider_result"
    ]["bundle_ref"]
    assert publication.result.retention_proof.proof_hash == EXPECTED[
        "provider_result"
    ]["retention_proof_hash"]


def test_exact_slice_rejects_replacement_missing_checksum_and_invalid_acquisition() -> None:
    archive, checksum = rewritten_archive(lambda rows: rows.__setitem__(1, [*rows[1][:1], "1.00000000", *rows[1][2:]]))
    replacement = capture_binance_usdm_mark_price_archive(
        request(),
        FakeFetch({request().urls[0]: ((200, archive),), request().urls[1]: ((200, checksum),)}),
    )
    assert replacement.result is None
    assert replacement.failure is not None
    assert replacement.failure.code is BinanceUsdmArchiveFailureCode.SOURCE_SCHEMA_MISMATCH

    one_member = freeze_source_snapshot(
        members=(
            RawSourceMember(
                "archive/BTCUSDT-1m-2024-01-01.zip",
                ARCHIVE,
                "0644",
                ACQUIRED_AT,
                EXPECTED["source_hashes"]["archive_sha256"],
            ),
        ),
        provenance=SourceSnapshotProvenance(
            vendor_key="binance.public_data",
            source_key=EXPECTED["snapshot"]["provenance"]["source_key"],
            license_ref="binance.public_data.terms",
            retention_policy_ref="backtest.fixture.retention",
        ),
    ).snapshot
    assert one_member is not None
    missing = normalize_binance_usdm_mark_price_archive(
        BinanceUsdmArchiveCaptureResult(request(), one_member, 1, 1)
    )
    assert missing.result is None
    assert missing.failure is not None
    assert missing.failure.code is BinanceUsdmArchiveFailureCode.CONFIGURATION_INVALID

    wrong_provenance = freeze_source_snapshot(
        members=(
            RawSourceMember(
                "archive/BTCUSDT-1m-2024-01-01.zip",
                ARCHIVE,
                "0644",
                ACQUIRED_AT,
                EXPECTED["source_hashes"]["archive_sha256"],
            ),
            RawSourceMember(
                "archive/BTCUSDT-1m-2024-01-01.zip.CHECKSUM",
                CHECKSUM,
                "0644",
                ACQUIRED_AT,
                EXPECTED["source_hashes"]["checksum_sha256"],
            ),
        ),
        provenance=SourceSnapshotProvenance(
            vendor_key="binance.public_data",
            source_key=EXPECTED["snapshot"]["provenance"]["source_key"],
            license_ref="wrong.license",
            retention_policy_ref="wrong.retention",
        ),
    ).snapshot
    assert wrong_provenance is not None
    rejected_provenance = normalize_binance_usdm_mark_price_archive(
        BinanceUsdmArchiveCaptureResult(request(), wrong_provenance, 1, 1)
    )
    assert rejected_provenance.result is None
    assert rejected_provenance.failure is not None
    assert rejected_provenance.failure.code is BinanceUsdmArchiveFailureCode.CONFIGURATION_INVALID

    with pytest.raises(ValueError, match="frozen source capture"):
        BinanceUsdmMarkPriceArchiveRequest(request().instrument_id, 0)

    encrypted = bytearray(ARCHIVE)
    local = encrypted.index(b"PK\x03\x04")
    central = encrypted.index(b"PK\x01\x02")
    encrypted[local + 6] |= 1
    encrypted[central + 8] |= 1
    encrypted_bytes = bytes(encrypted)
    encrypted_checksum = (
        f"{hashlib.sha256(encrypted_bytes).hexdigest()}  "
        "BTCUSDT-1m-2024-01-01.zip\n"
    ).encode()
    malformed = capture_binance_usdm_mark_price_archive(
        request(),
        FakeFetch(
            {
                request().urls[0]: ((200, encrypted_bytes),),
                request().urls[1]: ((200, encrypted_checksum),),
            }
        ),
    )
    assert malformed.result is None
    assert malformed.failure is not None
    assert malformed.failure.code is BinanceUsdmArchiveFailureCode.SOURCE_SCHEMA_MISMATCH
