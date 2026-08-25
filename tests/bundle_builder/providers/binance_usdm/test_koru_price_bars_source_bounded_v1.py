"""Actual-provider authority sentinels plus synthetic mutation coverage.

The captured July 16 bytes authorize only that frozen date, hashes, and availability
receipt. Every future date requires its own captured hashes and availability receipt.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from dataclasses import replace
from pathlib import Path
from typing import TypedDict, Unpack, cast
from zipfile import ZIP_STORED, ZipFile, ZipInfo

import pytest
from crypto_quant_bundle_builder.binance_usdm_koru_price_bars_source_bounded_v1 import (
    BinanceUsdmKoruPriceBarsSourceBoundedCaptureResultV1,
    BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1,
    BinanceUsdmKoruPriceBarsSourceBoundedNormalizationOutcomeV1,
    BinanceUsdmKoruPriceBarsSourceBoundedRequestV1,
    BinanceUsdmKoruPriceBarsSourceKindV1,
    capture_binance_usdm_koru_price_bars_source_bounded_v1,
    normalize_binance_usdm_koru_price_bars_source_bounded_v1,
)
from crypto_quant_domain import InstrumentId, UtcInstant, VenueId
from crypto_quant_market_data import MarketEvent

UTC_DATE = "2026-07-16"
DAY_START_NS = 1_784_160_000_000_000_000
DAY_END_NS = 1_784_246_400_000_000_000
DAY_START_MS = DAY_START_NS // 1_000_000
HOUR_MS = 3_600_000
ARCHIVE_AVAILABLE_AT = DAY_END_NS + 3_600_000_000_000
ACQUIRED_AT = DAY_END_NS + 86_400_000_000_000
HEADER = (
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time",
    "quote_volume",
    "count",
    "taker_buy_volume",
    "taker_buy_quote_volume",
    "ignore",
)
ROWS = (
    (
        str(DAY_START_MS + HOUR_MS),
        "12.34000000",
        "12.50000000",
        "12.25000000",
        "12.45000000",
        "0",
        str(DAY_START_MS + 2 * HOUR_MS - 1),
        "0",
        "60",
        "0",
        "0",
        "0",
    ),
    (
        str(DAY_START_MS + 2 * HOUR_MS),
        "12.45000000",
        "12.60000000",
        "12.40000000",
        "12.55000000",
        "0.00000000",
        str(DAY_START_MS + 3 * HOUR_MS - 1),
        "0.0",
        "0",
        "0",
        "0",
        "0",
    ),
)
SYNTHETIC_FIXTURE_CLASSIFICATION = "synthetic_retained_source_snapshot_fixture"
FIXTURE_ROOT = (
    Path(__file__).parents[3]
    / "fixtures/market_data/providers/binance_usdm/koru-price-bars-v1"
)
ACQUIRED_AT_ACTUAL = 1_787_646_422_400_000_000
ECONOMIC_AVAILABILITY_POLICY_REF = "binance.fapi.completed-kline-close-exclusive.v1"


class ActualFixture(TypedDict):
    directory: str
    fixture_directory: str
    archive_available_at: int
    last_modified: str
    archive_available_at_utc: str
    archive_sha256: str
    checksum_sha256: str


ACTUAL_FIXTURES: dict[BinanceUsdmKoruPriceBarsSourceKindV1, ActualFixture] = {
    BinanceUsdmKoruPriceBarsSourceKindV1.MARK_PRICE: {
        "directory": "markPriceKlines",
        "fixture_directory": "mark",
        "archive_available_at": 1_784_280_367_000_000_000,
        "last_modified": "Fri, 17 Jul 2026 09:26:07 GMT",
        "archive_available_at_utc": "2026-07-17T09:26:07Z",
        "archive_sha256": "sha256:1d24171e3eeeda02f6114da802bb6ed60d655b6b5c19c56825b3d2539f88cf0b",
        "checksum_sha256": "sha256:629977ec493c028e4095f4dbdbc60388d57eaee44976df511f8649aebac24e70",
    },
    BinanceUsdmKoruPriceBarsSourceKindV1.INDEX_PRICE: {
        "directory": "indexPriceKlines",
        "fixture_directory": "index",
        "archive_available_at": 1_784_278_804_000_000_000,
        "last_modified": "Fri, 17 Jul 2026 09:00:04 GMT",
        "archive_available_at_utc": "2026-07-17T09:00:04Z",
        "archive_sha256": "sha256:75ed044992cea272cc807526f489ec5879c43a8a828a72811dec2528d11b0606",
        "checksum_sha256": "sha256:153e5ad46b80a217d849a26355d17935296108ce6a6203b9a982da34a9a59e5b",
    },
}


def sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def csv_bytes(
    rows: tuple[tuple[str, ...], ...] = ROWS,
    *,
    header: tuple[str, ...] = HEADER,
    line_ending: str = "\n",
) -> bytes:
    return (
        line_ending.join(",".join(row) for row in (header,) + rows).encode()
        + line_ending.encode()
    )


def archive_bytes(
    rows: tuple[tuple[str, ...], ...] = ROWS,
    *,
    member_name: str = f"KORUUSDT-1h-{UTC_DATE}.csv",
    header: tuple[str, ...] = HEADER,
    line_ending: str = "\n",
    extra_member: tuple[str, bytes] | None = None,
) -> bytes:
    output = io.BytesIO()
    info = ZipInfo(member_name, (2026, 7, 16, 0, 0, 0))
    info.compress_type = ZIP_STORED
    info.external_attr = 0o644 << 16
    with ZipFile(output, "w") as archive:
        archive.writestr(
            info,
            csv_bytes(rows, header=header, line_ending=line_ending),
        )
        if extra_member is not None:
            archive.writestr(*extra_member)
    return output.getvalue()


def evidence(
    rows: tuple[tuple[str, ...], ...] = ROWS,
    *,
    member_name: str = f"KORUUSDT-1h-{UTC_DATE}.csv",
    checksum_name: str = f"KORUUSDT-1h-{UTC_DATE}.zip",
    checksum_separator: str = "  ",
    header: tuple[str, ...] = HEADER,
    line_ending: str = "\n",
    extra_member: tuple[str, bytes] | None = None,
) -> tuple[bytes, bytes]:
    archive = archive_bytes(
        rows,
        member_name=member_name,
        header=header,
        line_ending=line_ending,
        extra_member=extra_member,
    )
    checksum = (
        sha256(archive)[7:] + checksum_separator + checksum_name + "\n"
    ).encode()
    return archive, checksum


def request_for(
    source_kind: BinanceUsdmKoruPriceBarsSourceKindV1,
    archive: bytes,
    checksum: bytes,
    *,
    instrument_id: InstrumentId | None = None,
    interval: str = "1h",
    utc_date: str = UTC_DATE,
    archive_available_at: int = ARCHIVE_AVAILABLE_AT,
    acquired_at: int = ACQUIRED_AT,
    expected_archive_sha256: str | None = None,
    expected_checksum_sha256: str | None = None,
) -> BinanceUsdmKoruPriceBarsSourceBoundedRequestV1:
    return BinanceUsdmKoruPriceBarsSourceBoundedRequestV1(
        source_kind=source_kind,
        instrument_id=instrument_id
        or InstrumentId(VenueId("binance_usdm"), "koru-usdt-tradifi-perpetual"),
        interval=interval,
        utc_date=utc_date,
        archive_available_at_epoch_nanoseconds=archive_available_at,
        acquired_at_epoch_nanoseconds=acquired_at,
        expected_archive_sha256=expected_archive_sha256 or sha256(archive),
        expected_checksum_sha256=expected_checksum_sha256 or sha256(checksum),
    )


class EvidenceOptions(TypedDict, total=False):
    member_name: str
    checksum_name: str
    checksum_separator: str
    header: tuple[str, ...]
    line_ending: str
    extra_member: tuple[str, bytes] | None


class Fetch:
    def __init__(
        self, responses: dict[str, list[tuple[int, bytes] | Exception]]
    ) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def __call__(self, url: str) -> tuple[int, bytes]:
        self.calls.append(url)
        response = self.responses[url].pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def capture(
    source_kind: BinanceUsdmKoruPriceBarsSourceKindV1,
    rows: tuple[tuple[str, ...], ...] = ROWS,
    **evidence_options: Unpack[EvidenceOptions],
) -> BinanceUsdmKoruPriceBarsSourceBoundedCaptureResultV1:
    archive, checksum = evidence(rows, **evidence_options)
    request = request_for(source_kind, archive, checksum)
    archive_url, checksum_url = request.urls
    outcome = capture_binance_usdm_koru_price_bars_source_bounded_v1(
        request,
        Fetch({archive_url: [(200, archive)], checksum_url: [(200, checksum)]}),
    )
    assert outcome.failure is None
    assert outcome.result is not None
    return outcome.result


def normalize(
    source_kind: BinanceUsdmKoruPriceBarsSourceKindV1,
    rows: tuple[tuple[str, ...], ...] = ROWS,
    **evidence_options: Unpack[EvidenceOptions],
) -> BinanceUsdmKoruPriceBarsSourceBoundedNormalizationOutcomeV1:
    return normalize_binance_usdm_koru_price_bars_source_bounded_v1(
        capture(source_kind, rows, **evidence_options)
    )


def actual_provider_evidence(
    source_kind: BinanceUsdmKoruPriceBarsSourceKindV1,
) -> tuple[BinanceUsdmKoruPriceBarsSourceBoundedRequestV1, bytes, bytes]:
    fixture = ACTUAL_FIXTURES[source_kind]
    fixture_directory = fixture["fixture_directory"]
    root = FIXTURE_ROOT / fixture_directory
    archive = (root / f"KORUUSDT-1h-{UTC_DATE}.zip").read_bytes()
    checksum = (root / f"KORUUSDT-1h-{UTC_DATE}.zip.CHECKSUM").read_bytes()
    request = request_for(
        source_kind,
        archive,
        checksum,
        archive_available_at=fixture["archive_available_at"],
        acquired_at=ACQUIRED_AT_ACTUAL,
        expected_archive_sha256=fixture["archive_sha256"],
        expected_checksum_sha256=fixture["checksum_sha256"],
    )
    return request, archive, checksum


def capture_actual_provider(
    source_kind: BinanceUsdmKoruPriceBarsSourceKindV1,
) -> BinanceUsdmKoruPriceBarsSourceBoundedCaptureResultV1:
    request, archive, checksum = actual_provider_evidence(source_kind)
    archive_url, checksum_url = request.urls
    outcome = capture_binance_usdm_koru_price_bars_source_bounded_v1(
        request,
        Fetch({archive_url: [(200, archive)], checksum_url: [(200, checksum)]}),
    )
    assert outcome.failure is None
    assert outcome.result is not None
    return outcome.result


@pytest.mark.parametrize("source_kind", tuple(BinanceUsdmKoruPriceBarsSourceKindV1))
def test_synthetic_zip_and_checksum_remain_retained_for_mutation_coverage(
    source_kind: BinanceUsdmKoruPriceBarsSourceKindV1,
) -> None:
    captured = capture(source_kind)
    archive, checksum = evidence()
    assert SYNTHETIC_FIXTURE_CLASSIFICATION == (
        "synthetic_retained_source_snapshot_fixture"
    )
    assert (
        captured.snapshot.member_bytes("archive/KORUUSDT-1h-2026-07-16.zip") == archive
    )
    assert (
        captured.snapshot.member_bytes("archive/KORUUSDT-1h-2026-07-16.zip.CHECKSUM")
        == checksum
    )


@pytest.mark.parametrize(
    ("source_kind", "directory"),
    [
        (BinanceUsdmKoruPriceBarsSourceKindV1.MARK_PRICE, "markPriceKlines"),
        (BinanceUsdmKoruPriceBarsSourceKindV1.INDEX_PRICE, "indexPriceKlines"),
    ],
)
def test_capture_urls_snapshot_and_normalization_replay_are_exact(
    source_kind: BinanceUsdmKoruPriceBarsSourceKindV1,
    directory: str,
) -> None:
    captured = capture(source_kind)
    first = normalize_binance_usdm_koru_price_bars_source_bounded_v1(captured)
    replay = normalize_binance_usdm_koru_price_bars_source_bounded_v1(captured)
    assert first.failure is replay.failure is None
    assert first.result is not None
    assert replay.result is not None
    result = first.result

    base = (
        "https://data.binance.vision/data/futures/um/daily/"
        f"{directory}/KORUUSDT/1h/KORUUSDT-1h-2026-07-16.zip"
    )
    assert captured.request.urls == (base, base + ".CHECKSUM")
    assert captured.request.symbol == "KORUUSDT"
    assert result.normalization_hash == replay.result.normalization_hash
    assert result.request_hash == captured.request.request_hash
    assert result.capture_hash == captured.capture_hash
    assert result.source_snapshot_id == captured.snapshot.snapshot_id
    assert (
        result.source_snapshot_hash
        == captured.to_canonical_dict()["source_snapshot_hash"]
    )
    assert result.requested_day_start == UtcInstant(DAY_START_NS)
    assert result.requested_day_end_exclusive == UtcInstant(DAY_END_NS)
    assert result.coverage_start == UtcInstant((DAY_START_MS + HOUR_MS) * 1_000_000)
    assert result.coverage_end_exclusive == UtcInstant(
        (DAY_START_MS + 3 * HOUR_MS) * 1_000_000
    )
    assert result.coverage_start > result.requested_day_start
    assert result.coverage_end_exclusive < result.requested_day_end_exclusive
    assert result.authorized_projection_start == UtcInstant(1_784_109_600_000_000_000)
    assert result.economic_availability_policy_ref == (ECONOMIC_AVAILABILITY_POLICY_REF)
    assert result.prefix_gap_classification == "unknown_unproven"
    assert result.suffix_gap_classification == "unknown_unproven"
    assert result.internal_gap_classification == "none_observed_by_contiguous_hours"
    assert result.retained_row_count == 2
    assert result.projected_row_count == 2
    assert result.excluded_prefix_row_count == 0
    assert result.first_open_time_milliseconds == DAY_START_MS + HOUR_MS
    assert result.last_open_time_milliseconds == DAY_START_MS + 2 * HOUR_MS
    assert result.decision_grade_eligible is False
    assert result.deployment_authorized is False
    assert result.source_kind is source_kind
    assert str(ARCHIVE_AVAILABLE_AT) in captured.snapshot.provenance.source_key
    assert source_kind.value in captured.snapshot.provenance.source_key


def test_july_15_retains_pre_authority_rows_but_projects_only_from_10_utc() -> None:
    july_15_start_ms = 1_784_073_600_000
    rows = (
        (
            str(july_15_start_ms + 9 * HOUR_MS),
            *ROWS[0][1:6],
            str(july_15_start_ms + 10 * HOUR_MS - 1),
            *ROWS[0][7:],
        ),
        (
            str(july_15_start_ms + 10 * HOUR_MS),
            *ROWS[1][1:6],
            str(july_15_start_ms + 11 * HOUR_MS - 1),
            *ROWS[1][7:],
        ),
    )
    utc_date = "2026-07-15"
    archive, checksum = evidence(
        rows,
        member_name=f"KORUUSDT-1h-{utc_date}.csv",
        checksum_name=f"KORUUSDT-1h-{utc_date}.zip",
    )
    request = request_for(
        BinanceUsdmKoruPriceBarsSourceKindV1.MARK_PRICE,
        archive,
        checksum,
        utc_date=utc_date,
        archive_available_at=1_784_160_000_000_000_000,
        acquired_at=1_784_246_400_000_000_000,
    )
    archive_url, checksum_url = request.urls
    captured = capture_binance_usdm_koru_price_bars_source_bounded_v1(
        request,
        Fetch({archive_url: [(200, archive)], checksum_url: [(200, checksum)]}),
    ).result
    assert captured is not None
    result = normalize_binance_usdm_koru_price_bars_source_bounded_v1(captured).result
    assert result is not None
    assert result.coverage_start == UtcInstant(
        (july_15_start_ms + 9 * HOUR_MS) * 1_000_000
    )
    assert result.first_open_time_milliseconds == july_15_start_ms + 9 * HOUR_MS
    assert result.authorized_projection_start == UtcInstant(
        (july_15_start_ms + 10 * HOUR_MS) * 1_000_000
    )
    assert result.prefix_gap_classification == (
        "corporate_action_excluded_before_2026-07-15T10:00:00Z"
    )
    assert result.retained_row_count == 2
    assert result.projected_row_count == 1
    assert result.excluded_prefix_row_count == 1
    assert len(result.events) == 4
    assert {event.payload["open_time_milliseconds"] for event in result.events} == {
        july_15_start_ms + 10 * HOUR_MS
    }


MARK_STREAMS = (
    "binance_usdm.mark_price.strategy.koruusdt.1h.v1",
    "binance_usdm.mark_price.valuation.koruusdt.1h.v1",
    "binance_usdm.mark_price.margin.koruusdt.1h.v1",
    "binance_usdm.mark_price.liquidation.koruusdt.1h.v1",
)
INDEX_STREAMS = ("binance_usdm.index_price.strategy.koruusdt.1h.v1",)


def test_mark_and_index_streams_payloads_and_event_availability_are_exact_and_disjoint() -> (
    None
):
    mark_capture = capture(BinanceUsdmKoruPriceBarsSourceKindV1.MARK_PRICE)
    index_capture = capture(BinanceUsdmKoruPriceBarsSourceKindV1.INDEX_PRICE)
    mark = normalize_binance_usdm_koru_price_bars_source_bounded_v1(mark_capture).result
    index = normalize_binance_usdm_koru_price_bars_source_bounded_v1(
        index_capture
    ).result
    assert mark is not None
    assert index is not None
    assert tuple(event.stream_key for event in mark.events[:4]) == MARK_STREAMS
    assert tuple(event.stream_key for event in index.events[:1]) == INDEX_STREAMS
    assert set(MARK_STREAMS).isdisjoint(INDEX_STREAMS)
    assert len(mark.events) == 8
    assert len(index.events) == 2

    strategy, valuation, margin, liquidation = mark.events[:4]
    assert strategy.event_type == "binance_usdm_koru_mark_price_strategy_bar_v1"
    assert valuation.event_type == "binance_usdm_koru_mark_price_point_v1"
    assert margin.event_type == "binance_usdm_koru_mark_price_point_v1"
    assert liquidation.event_type == ("binance_usdm_koru_mark_price_liquidation_bar_v1")
    assert index.events[0].event_type == (
        "binance_usdm_koru_index_price_strategy_bar_v1"
    )
    assert strategy.capability.identity == "price.bar@1"
    assert valuation.capability.identity == "price.point@1"
    assert liquidation.capability.identity == "price.bar@1"
    assert index.events[0].capability.identity == "price.bar@1"

    raw_close = UtcInstant((DAY_START_MS + 2 * HOUR_MS - 1) * 1_000_000)
    completed = UtcInstant((DAY_START_MS + 2 * HOUR_MS) * 1_000_000)
    for event in mark.events[:4] + index.events[:1]:
        assert event.event_time == completed
        assert event.available_time == completed
        assert event.available_time != raw_close
        assert event.available_time != UtcInstant(ARCHIVE_AVAILABLE_AT)
        assert event.available_time != UtcInstant(ACQUIRED_AT)
        assert event.instrument_id == InstrumentId(
            VenueId("binance_usdm"), "koru-usdt-tradifi-perpetual"
        )
        assert event.payload["interval"] == "1h"
        assert event.payload["open_units"] == 1_234_000_000
        assert event.payload["high_units"] == 1_250_000_000
        assert event.payload["low_units"] == 1_225_000_000
        assert event.payload["close_units"] == 1_245_000_000
        assert event.payload["price_scale"] == 8
        assert event.payload["close_time_milliseconds"] == (
            DAY_START_MS + 2 * HOUR_MS - 1
        )
        assert event.payload["economic_availability_policy_ref"] == (
            ECONOMIC_AVAILABILITY_POLICY_REF
        )
        assert ECONOMIC_AVAILABILITY_POLICY_REF in event.source_key
        assert event.payload["archive_available_at_epoch_nanoseconds"] == (
            ARCHIVE_AVAILABLE_AT
        )
        assert event.payload["acquired_at_epoch_nanoseconds"] == ACQUIRED_AT
        assert event.payload["source_snapshot_id"] in (
            mark_capture.snapshot.snapshot_id,
            index_capture.snapshot.snapshot_id,
        )
        assert "premium" not in str(event.payload).lower()
        assert "adjust" not in str(event.payload).lower()
    assert tuple(event.payload["price_purpose"] for event in mark.events[:4]) == (
        "strategy",
        "valuation",
        "margin",
        "liquidation",
    )
    assert all(event.payload["source_kind"] == "mark_price" for event in mark.events)
    assert all(event.payload["source_kind"] == "index_price" for event in index.events)
    assert valuation.payload["price_units"] == valuation.payload["close_units"]
    assert margin.payload["price_units"] == margin.payload["close_units"]
    assert "price_units" not in strategy.payload
    assert "price_units" not in liquidation.payload
    assert "price_units" not in index.events[0].payload
    assert mark.events[0].event_id != index.events[0].event_id
    assert mark.events[0].event_hash != index.events[0].event_hash


def test_request_rejects_wrong_kind_identity_interval_date_availability_and_hashes() -> (
    None
):
    archive, checksum = evidence()
    kind = BinanceUsdmKoruPriceBarsSourceKindV1.MARK_PRICE
    with pytest.raises(ValueError, match="source_kind"):
        request_for(
            cast(
                BinanceUsdmKoruPriceBarsSourceKindV1,
                cast(object, "mark_price"),
            ),
            archive,
            checksum,
        )
    with pytest.raises(ValueError, match="exact KORU"):
        request_for(
            kind,
            archive,
            checksum,
            instrument_id=InstrumentId(VenueId("binance_usdm"), "btc-usdt-perpetual"),
        )
    with pytest.raises(ValueError, match="exactly 1h"):
        request_for(kind, archive, checksum, interval="1m")
    with pytest.raises(ValueError, match="on or after"):
        request_for(kind, archive, checksum, utc_date="2026-07-14")
    with pytest.raises(ValueError, match="ISO UTC date"):
        request_for(kind, archive, checksum, utc_date="2026-7-16")
    with pytest.raises(ValueError, match="requested UTC day end"):
        request_for(kind, archive, checksum, archive_available_at=DAY_END_NS - 1)
    with pytest.raises(ValueError, match="acquired_at cannot precede"):
        request_for(
            kind,
            archive,
            checksum,
            archive_available_at=DAY_END_NS,
            acquired_at=DAY_END_NS - 1,
        )
    with pytest.raises(ValueError, match="canonical sha256"):
        request_for(
            kind,
            archive,
            checksum,
            expected_archive_sha256="sha256:not-a-hash",
        )

    boundary = request_for(
        kind,
        archive,
        checksum,
        archive_available_at=DAY_END_NS,
        acquired_at=DAY_END_NS,
    )
    assert boundary.archive_available_at_epoch_nanoseconds == DAY_END_NS
    assert boundary.acquired_at_epoch_nanoseconds == DAY_END_NS

    forged = request_for(kind, archive, checksum)
    object.__setattr__(forged, "source_kind", "mark_price")
    outcome = capture_binance_usdm_koru_price_bars_source_bounded_v1(
        forged, lambda _: (200, b"")
    )
    assert outcome.result is None
    assert outcome.failure is not None
    assert (
        outcome.failure.code
        is BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.CONFIGURATION_INVALID
    )


def test_capture_retries_and_classifies_http_failures_without_partial_snapshot() -> (
    None
):
    archive, checksum = evidence()
    request = request_for(
        BinanceUsdmKoruPriceBarsSourceKindV1.MARK_PRICE, archive, checksum
    )
    archive_url, checksum_url = request.urls
    succeeded = capture_binance_usdm_koru_price_bars_source_bounded_v1(
        request,
        Fetch(
            {
                archive_url: [RuntimeError("offline"), (503, b""), (200, archive)],
                checksum_url: [(429, b""), (200, checksum)],
            }
        ),
    )
    assert succeeded.failure is None
    assert succeeded.result is not None
    assert succeeded.result.archive_attempts == 3
    assert succeeded.result.checksum_attempts == 2

    cases: tuple[
        tuple[
            list[tuple[int, bytes] | Exception],
            BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1,
        ],
        ...,
    ] = (
        (
            [(500, b"")] * 3,
            BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.PROVIDER_UNAVAILABLE,
        ),
        (
            [(429, b"")] * 3,
            BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.RATE_LIMIT_EXHAUSTED,
        ),
        (
            [(403, b"")],
            BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.AUTHENTICATION_REJECTED,
        ),
        (
            [(404, b"")],
            BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.DATA_GAP_DETECTED,
        ),
        (
            [(418, b"")],
            BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.SOURCE_SCHEMA_MISMATCH,
        ),
    )
    for responses, code in cases:
        outcome = capture_binance_usdm_koru_price_bars_source_bounded_v1(
            request,
            Fetch(
                {
                    archive_url: responses.copy(),
                    checksum_url: [(200, checksum)],
                }
            ),
        )
        assert outcome.result is None
        assert outcome.failure is not None
        assert outcome.failure.code is code


def test_capture_rejects_wrong_archive_checksum_hash_grammar_and_kind_url() -> None:
    archive, checksum = evidence()
    wrong_hash = request_for(
        BinanceUsdmKoruPriceBarsSourceKindV1.MARK_PRICE,
        archive,
        checksum,
        expected_archive_sha256="sha256:" + "0" * 64,
    )
    archive_url, checksum_url = wrong_hash.urls
    outcome = capture_binance_usdm_koru_price_bars_source_bounded_v1(
        wrong_hash,
        Fetch({archive_url: [(200, archive)], checksum_url: [(200, checksum)]}),
    )
    assert outcome.failure is not None
    assert (
        outcome.failure.code
        is BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.SOURCE_HASH_MISMATCH
    )

    archive, malformed_checksum = evidence(checksum_separator=" ")
    malformed = request_for(
        BinanceUsdmKoruPriceBarsSourceKindV1.MARK_PRICE,
        archive,
        malformed_checksum,
    )
    archive_url, checksum_url = malformed.urls
    outcome = capture_binance_usdm_koru_price_bars_source_bounded_v1(
        malformed,
        Fetch(
            {
                archive_url: [(200, archive)],
                checksum_url: [(200, malformed_checksum)],
            }
        ),
    )
    assert outcome.failure is not None
    assert (
        outcome.failure.code
        is BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.SOURCE_HASH_MISMATCH
    )

    mark = request_for(
        BinanceUsdmKoruPriceBarsSourceKindV1.MARK_PRICE, archive, malformed_checksum
    )
    index = request_for(
        BinanceUsdmKoruPriceBarsSourceKindV1.INDEX_PRICE, archive, malformed_checksum
    )
    assert mark.urls != index.urls
    assert mark.request_hash != index.request_hash


@pytest.mark.parametrize(
    ("rows", "expected_code"),
    [
        (
            (ROWS[0][:-1],),
            BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.SOURCE_SCHEMA_MISMATCH,
        ),
        (
            (("0" + ROWS[0][0],) + ROWS[0][1:],),
            BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.NORMALIZATION_FAILED,
        ),
        (
            ((ROWS[0][0], "01.0") + ROWS[0][2:],),
            BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.NORMALIZATION_FAILED,
        ),
        (
            ((ROWS[0][0], "1e1") + ROWS[0][2:],),
            BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.NORMALIZATION_FAILED,
        ),
        (
            (ROWS[0][:-1] + ("-1",),),
            BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.NORMALIZATION_FAILED,
        ),
        (
            (
                (
                    str(DAY_START_MS + HOUR_MS + 1),
                    *ROWS[0][1:],
                ),
            ),
            BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.NORMALIZATION_FAILED,
        ),
        (
            (ROWS[0][:-6] + (str(int(ROWS[0][6]) - 1),) + ROWS[0][7:],),
            BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.NORMALIZATION_FAILED,
        ),
        (
            (ROWS[0], ROWS[0]),
            BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.DUPLICATE_OR_CONFLICT,
        ),
        (
            (ROWS[0], ROWS[0][:1] + ("12.40000000",) + ROWS[0][2:]),
            BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.DUPLICATE_OR_CONFLICT,
        ),
        (
            (
                ROWS[0],
                (str(DAY_START_MS + 3 * HOUR_MS),)
                + ROWS[1][1:6]
                + (str(DAY_START_MS + 4 * HOUR_MS - 1),)
                + ROWS[1][7:],
            ),
            BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.DATA_GAP_DETECTED,
        ),
        (
            (ROWS[1], ROWS[0]),
            BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.ORDER_VIOLATION,
        ),
        (
            ((ROWS[0][0], "12.34", "12.20", "12.25", "12.30") + ROWS[0][5:],),
            BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.NORMALIZATION_FAILED,
        ),
        (
            (
                (str(DAY_START_MS - HOUR_MS),)
                + ROWS[0][1:6]
                + (str(DAY_START_MS - 1),)
                + ROWS[0][7:],
            ),
            BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.DATA_GAP_DETECTED,
        ),
    ],
)
def test_normalization_rejects_column_decimal_time_alignment_gap_duplicate_order_and_ohlc(
    rows: tuple[tuple[str, ...], ...],
    expected_code: BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1,
) -> None:
    outcome = normalize(BinanceUsdmKoruPriceBarsSourceKindV1.MARK_PRICE, rows)
    assert outcome.result is None
    assert outcome.failure is not None
    assert outcome.failure.code is expected_code


def test_normalization_rejects_member_header_encoding_empty_and_snapshot_mutation() -> (
    None
):
    outcomes = (
        normalize(
            BinanceUsdmKoruPriceBarsSourceKindV1.INDEX_PRICE,
            member_name="KORUUSDT-1h-2026-07-17.csv",
        ),
        normalize(
            BinanceUsdmKoruPriceBarsSourceKindV1.INDEX_PRICE,
            extra_member=("extra.txt", b"x"),
        ),
        normalize(
            BinanceUsdmKoruPriceBarsSourceKindV1.INDEX_PRICE,
            header=HEADER[:-1] + ("wrong",),
        ),
        normalize(
            BinanceUsdmKoruPriceBarsSourceKindV1.INDEX_PRICE,
            line_ending="\r\n",
        ),
    )
    for outcome in outcomes:
        assert outcome.result is None
        assert outcome.failure is not None
        assert (
            outcome.failure.code
            is BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.SOURCE_SCHEMA_MISMATCH
        )

    empty = normalize(
        BinanceUsdmKoruPriceBarsSourceKindV1.INDEX_PRICE,
        (),
    )
    assert empty.failure is not None
    assert (
        empty.failure.code
        is BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.DATA_GAP_DETECTED
    )

    captured = capture(BinanceUsdmKoruPriceBarsSourceKindV1.MARK_PRICE)
    object.__setattr__(
        captured.snapshot,
        "archive_bytes",
        captured.snapshot.archive_bytes + b"x",
    )
    mutated = normalize_binance_usdm_koru_price_bars_source_bounded_v1(captured)
    assert mutated.result is None
    assert mutated.failure is not None
    assert (
        mutated.failure.code
        is BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.CONFIGURATION_INVALID
    )


def test_normalization_result_reconstructs_retained_csv_events_lineage_and_coverage() -> (
    None
):
    result = normalize(BinanceUsdmKoruPriceBarsSourceKindV1.MARK_PRICE).result
    assert result is not None
    first = result.events[0]
    close_time_milliseconds = first.payload["close_time_milliseconds"]
    assert type(close_time_milliseconds) is int
    mutations: tuple[MarketEvent, ...] = (
        replace(first, event_id=first.event_id + "-forged"),
        replace(
            first,
            event_time=UtcInstant(close_time_milliseconds * 1_000_000),
            available_time=UtcInstant(close_time_milliseconds * 1_000_000),
        ),
        replace(first, available_time=UtcInstant(ARCHIVE_AVAILABLE_AT)),
        replace(first, payload={**first.payload, "extra": "forged"}),
        replace(first, payload={**first.payload, "source_kind": "index_price"}),
        replace(first, payload={**first.payload, "price_purpose": "valuation"}),
        replace(first, payload={**first.payload, "open_units": 1}),
        replace(
            first, payload={**first.payload, "source_record_hash": "sha256:" + "0" * 64}
        ),
        replace(
            first, payload={**first.payload, "source_member_hash": "sha256:" + "0" * 64}
        ),
        replace(
            first,
            payload={**first.payload, "checksum_member_hash": "sha256:" + "0" * 64},
        ),
        replace(
            first,
            payload={
                **first.payload,
                "economic_availability_policy_ref": "binance.old-close-time.v0",
            },
        ),
    )
    for mutated_event in mutations:
        with pytest.raises(ValueError, match="exactly reconstruct"):
            replace(result, events=(mutated_event,) + result.events[1:])

    with pytest.raises(ValueError, match="exactly reconstruct"):
        replace(
            result,
            coverage_start=result.requested_day_start,
            coverage_end_exclusive=result.requested_day_end_exclusive,
        )
    with pytest.raises(ValueError, match="exactly reconstruct"):
        replace(
            result,
            source_kind=BinanceUsdmKoruPriceBarsSourceKindV1.INDEX_PRICE,
        )
    with pytest.raises(ValueError, match="exactly reconstruct"):
        replace(result, projected_row_count=result.projected_row_count + 1)
    with pytest.raises(ValueError, match="exactly reconstruct"):
        replace(result, excluded_prefix_row_count=1)
    with pytest.raises(ValueError, match="exactly reconstruct"):
        replace(result, economic_availability_policy_ref="binance.old-close-time.v0")
    with pytest.raises(ValueError, match="qualification flags"):
        replace(result, decision_grade_eligible=True)


def test_normalization_outcome_rejects_post_construction_event_and_capture_mutations() -> (
    None
):
    result = normalize(BinanceUsdmKoruPriceBarsSourceKindV1.INDEX_PRICE).result
    assert result is not None
    object.__setattr__(
        result.events[0], "event_id", result.events[0].event_id + "-forged"
    )
    with pytest.raises(ValueError, match="not canonical"):
        BinanceUsdmKoruPriceBarsSourceBoundedNormalizationOutcomeV1(result=result)

    captured = capture(BinanceUsdmKoruPriceBarsSourceKindV1.MARK_PRICE)
    object.__setattr__(
        captured.request,
        "source_kind",
        BinanceUsdmKoruPriceBarsSourceKindV1.INDEX_PRICE,
    )
    with pytest.raises(ValueError, match="exact verified"):
        BinanceUsdmKoruPriceBarsSourceBoundedCaptureResultV1(
            captured.request,
            captured.snapshot,
            captured.archive_attempts,
            captured.checksum_attempts,
        )


@pytest.mark.parametrize(
    ("source_kind", "expected"),
    [
        (
            BinanceUsdmKoruPriceBarsSourceKindV1.MARK_PRICE,
            {
                "request_hash": "sha256:ad5bb13a2d7d26fab4cea5bbb0cb103aaafbb06a2ee8787df6495505e58aac69",
                "source_member_hash": "sha256:651c489511e554b82c1b8e8531abecc4886025f76fa95e60771d803d9687f08e",
                "first_event_hash": "sha256:2e85c4265ad8b1e60f3b4ec1858ad47f77eebb29db4aff00b8676ec2305df0b9",
                "last_event_hash": "sha256:e07ccd7c1a2a225db95fb82df4631f586c41c800bc961770caabd75466c38785",
                "normalization_hash": "sha256:bc0b1e5099f53480ffa71a2df7bfdca0c3a6459bec97de0fc5b6c5e77d7c7d49",
                "event_count": 96,
            },
        ),
        (
            BinanceUsdmKoruPriceBarsSourceKindV1.INDEX_PRICE,
            {
                "request_hash": "sha256:4a086df29e5851aacd10f5ce84c07b845dfea832397e99e759f63d2e3a9e7dfc",
                "source_member_hash": "sha256:411e7f6ce9bc0c03355a042045ca53a9bf0f70117cb276d160c1c5346fa03858",
                "first_event_hash": "sha256:b4f8599833acfc65e043e15c96aac757a043257c814f54980754706bd7ded041",
                "last_event_hash": "sha256:14df54803a05f17bc0e16a4c658d9700f076d83371fc39058296c6ac2862352f",
                "normalization_hash": "sha256:f11639334808ab1141e7efafee28751e8dc0f0e77e29e72f6ebf9562d5285936",
                "event_count": 24,
            },
        ),
    ],
)
def test_actual_provider_july_16_archive_is_the_successful_authority_sentinel(
    source_kind: BinanceUsdmKoruPriceBarsSourceKindV1,
    expected: dict[str, str | int],
) -> None:
    request, archive, checksum = actual_provider_evidence(source_kind)
    fixture = ACTUAL_FIXTURES[source_kind]
    expected_base = (
        "https://data.binance.vision/data/futures/um/daily/"
        f"{fixture['directory']}/KORUUSDT/1h/KORUUSDT-1h-{UTC_DATE}.zip"
    )
    assert request.urls == (expected_base, expected_base + ".CHECKSUM")
    assert (
        request.archive_available_at_epoch_nanoseconds
        == fixture["archive_available_at"]
    )
    assert request.acquired_at_epoch_nanoseconds == ACQUIRED_AT_ACTUAL
    receipt = json.loads(
        (FIXTURE_ROOT / "acquisition-receipt.json").read_text(encoding="utf-8")
    )
    receipt_records = [
        record
        for record in receipt["records"]
        if record["source_kind"] == source_kind.value
    ]
    assert receipt["captured_at_utc"] == "2026-08-25T08:27:02.400Z"
    assert {record["url"] for record in receipt_records} == set(request.urls)
    assert {record["sha256"] for record in receipt_records} == {
        fixture["archive_sha256"],
        fixture["checksum_sha256"],
    }
    assert {record["last_modified"] for record in receipt_records} == {
        fixture["last_modified"]
    }
    assert {record["archive_available_at_utc"] for record in receipt_records} == {
        fixture["archive_available_at_utc"]
    }
    assert sha256(archive) == fixture["archive_sha256"]
    assert sha256(checksum) == fixture["checksum_sha256"]
    assert checksum == f"{sha256(archive)[7:]}  {request.archive_name}\n".encode()

    with ZipFile(io.BytesIO(archive)) as zip_file:
        assert zip_file.namelist() == [request.csv_name]
        retained_csv = zip_file.read(request.csv_name)
    retained_rows = list(
        csv.reader(io.StringIO(retained_csv.decode("utf-8"), newline=""))
    )
    assert tuple(retained_rows[0]) == HEADER
    assert len(retained_rows) == 25
    assert len(retained_rows[1:]) == 24

    captured = capture_actual_provider(source_kind)
    first = normalize_binance_usdm_koru_price_bars_source_bounded_v1(captured)
    replay = normalize_binance_usdm_koru_price_bars_source_bounded_v1(captured)
    assert first.failure is replay.failure is None
    assert first.result is not None
    assert replay.result is not None
    result = first.result
    assert result.normalization_hash == replay.result.normalization_hash
    assert result.request_hash == expected["request_hash"]
    assert result.source_member_hash == expected["source_member_hash"]
    assert result.retained_row_count == 24
    assert result.projected_row_count == 24
    assert result.excluded_prefix_row_count == 0
    assert result.coverage_start == UtcInstant(DAY_START_NS)
    assert result.coverage_end_exclusive == UtcInstant(DAY_END_NS)
    assert len(result.events) == expected["event_count"]
    assert result.events[0].event_hash == expected["first_event_hash"]
    assert result.events[-1].event_hash == expected["last_event_hash"]
    assert result.normalization_hash == expected["normalization_hash"]


def test_actual_provider_mark_and_index_identities_are_disjoint_and_cross_swap_fails() -> (
    None
):
    mark_request, mark_archive, mark_checksum = actual_provider_evidence(
        BinanceUsdmKoruPriceBarsSourceKindV1.MARK_PRICE
    )
    index_request, index_archive, index_checksum = actual_provider_evidence(
        BinanceUsdmKoruPriceBarsSourceKindV1.INDEX_PRICE
    )
    mark = normalize_binance_usdm_koru_price_bars_source_bounded_v1(
        capture_actual_provider(BinanceUsdmKoruPriceBarsSourceKindV1.MARK_PRICE)
    ).result
    index = normalize_binance_usdm_koru_price_bars_source_bounded_v1(
        capture_actual_provider(BinanceUsdmKoruPriceBarsSourceKindV1.INDEX_PRICE)
    ).result
    assert mark is not None
    assert index is not None
    assert mark_request.request_hash != index_request.request_hash
    assert mark.normalization_hash != index.normalization_hash
    assert {event.event_id for event in mark.events}.isdisjoint(
        event.event_id for event in index.events
    )

    for request, wrong_archive, wrong_checksum in (
        (mark_request, index_archive, index_checksum),
        (index_request, mark_archive, mark_checksum),
    ):
        archive_url, checksum_url = request.urls
        outcome = capture_binance_usdm_koru_price_bars_source_bounded_v1(
            request,
            Fetch(
                {
                    archive_url: [(200, wrong_archive)],
                    checksum_url: [(200, wrong_checksum)],
                }
            ),
        )
        assert outcome.result is None
        assert outcome.failure is not None
        assert outcome.failure.code is (
            BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.SOURCE_HASH_MISMATCH
        )
