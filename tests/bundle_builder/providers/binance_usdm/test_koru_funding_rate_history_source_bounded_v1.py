from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest
from crypto_quant_bundle_builder.binance_usdm_koru_funding_rate_history_source_bounded_v1 import (
    BinanceUsdmKoruFundingRateHistorySourceBoundedCaptureResultV1,
    BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1,
    BinanceUsdmKoruFundingRateHistorySourceBoundedNormalizationOutcomeV1,
    BinanceUsdmKoruFundingRateHistorySourceBoundedRequestV1,
    BinanceUsdmKoruFundingRateHistoryTransportResponseV1,
    capture_binance_usdm_koru_funding_rate_history_source_bounded_v1,
    normalize_binance_usdm_koru_funding_rate_history_source_bounded_v1,
)
from crypto_quant_bundle_builder.source_snapshots import (
    RawSourceMember,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
)
from crypto_quant_domain import (
    InstrumentId,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    VenueId,
)
from crypto_quant_market_data import MarketEvent

ROOT = Path(__file__).resolve().parents[3]
FIXTURE_ROOT = (
    ROOT / "fixtures/market_data/providers/binance_usdm/koru-funding-history-v1"
)
RAW = (FIXTURE_ROOT / "funding-history.json").read_bytes()
RECEIPT = (FIXTURE_ROOT / "acquisition-receipt.json").read_bytes()
RECEIPT_VALUE = json.loads(RECEIPT)
START = 1_784_109_600_000
END = 1_787_569_199_999
OBSERVED_AT = 1_787_647_683_000_000_000
ACQUIRED_AT = 1_787_647_683_858_000_000
DATE_HEADER = "Tue, 25 Aug 2026 08:48:03 GMT"
RESPONSE_HASH = (
    "sha256:ace9f779682989befac94ffd1c835e7a6e97b2b8103e6ad347ec8dc38fa6c960"
)
INSTRUMENT = InstrumentId(VenueId("binance_usdm"), "koru-usdt-tradifi-perpetual")


def sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def compact(rows: list[dict[str, object]]) -> bytes:
    return json.dumps(rows, ensure_ascii=False, separators=(",", ":")).encode()


def request_for(
    raw: bytes = RAW,
    *,
    instrument_id: InstrumentId = INSTRUMENT,
    start: int = START,
    end: int = END,
    limit: int = 1000,
    expected_hash: str | None = None,
) -> BinanceUsdmKoruFundingRateHistorySourceBoundedRequestV1:
    return BinanceUsdmKoruFundingRateHistorySourceBoundedRequestV1(
        instrument_id,
        start,
        end,
        limit,
        expected_hash or sha256(raw),
    )


def transport_response(
    raw: bytes = RAW,
    *,
    status: int = 200,
    method: str = "GET",
    requested_url: str | None = None,
    final_url: str | None = None,
    date_header: str = DATE_HEADER,
    acquired_at: int = ACQUIRED_AT,
) -> BinanceUsdmKoruFundingRateHistoryTransportResponseV1:
    url = request_for(raw).url
    return BinanceUsdmKoruFundingRateHistoryTransportResponseV1(
        method,
        requested_url or url,
        final_url or url,
        status,
        raw,
        date_header,
        acquired_at,
    )


class Fetch:
    def __init__(
        self,
        responses: list[
            BinanceUsdmKoruFundingRateHistoryTransportResponseV1 | Exception
        ],
    ) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def __call__(
        self, url: str
    ) -> BinanceUsdmKoruFundingRateHistoryTransportResponseV1:
        self.calls.append(url)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def capture(
    raw: bytes = RAW,
) -> BinanceUsdmKoruFundingRateHistorySourceBoundedCaptureResultV1:
    outcome = capture_binance_usdm_koru_funding_rate_history_source_bounded_v1(
        request_for(raw), Fetch([transport_response(raw)])
    )
    assert outcome.failure is None
    assert outcome.result is not None
    return outcome.result


def normalize(raw: bytes):
    return normalize_binance_usdm_koru_funding_rate_history_source_bounded_v1(
        capture(raw)
    )


def row(
    funding_time: int,
    *,
    symbol: str = "KORUUSDT",
    funding_rate: str = "0.00010000",
    mark_price: str = "20.00000000",
    rate_type: str | None = "Regular",
) -> dict[str, object]:
    value: dict[str, object] = {
        "symbol": symbol,
        "fundingTime": funding_time,
        "fundingRate": funding_rate,
        "markPrice": mark_price,
    }
    if rate_type is not None:
        value["rateType"] = rate_type
    return value


def test_actual_fixture_capture_normalization_goldens_and_replay() -> None:
    captured = capture()
    first = normalize_binance_usdm_koru_funding_rate_history_source_bounded_v1(captured)
    replay = normalize_binance_usdm_koru_funding_rate_history_source_bounded_v1(
        captured
    )
    assert first.failure is replay.failure is None
    assert first.result is not None
    assert replay.result is not None
    result = first.result

    assert captured.request.url == (
        "https://fapi.binance.com/fapi/v1/fundingRate?symbol=KORUUSDT&"
        "startTime=1784109600000&endTime=1787569199999&limit=1000"
    )
    assert captured.request.request_hash == (
        "sha256:fb7a977893ebc36a86fb2e228e8d7e6f4e6e01298568037c3f62fc853031780d"
    )
    assert captured.capture_hash == (
        "sha256:da30923844175d15c0c2fca00bd64c33f4bef46509159fcef045f0c22c3cc3e8"
    )
    assert captured.snapshot.member_bytes("response/funding-history.json") == RAW
    assert (
        captured.snapshot.member_bytes("acquisition/acquisition-receipt.json")
        == RECEIPT
    )
    assert (
        result.normalization_hash
        == replay.result.normalization_hash
        == ("sha256:27a6d00659b9d3a27647f850fff97cfebd5630895ba6dc09243b741e9f297631")
    )
    assert result.row_count == 120
    assert result.first_funding_time_milliseconds == 1_784_131_200_001
    assert result.last_funding_time_milliseconds == 1_787_558_400_001
    assert result.coverage_start == UtcInstant(1_784_131_200_001_000_000)
    assert result.coverage_end_exclusive == UtcInstant(1_787_558_400_001_000_001)
    assert result.requested_start == UtcInstant(START * 1_000_000)
    assert result.requested_end_inclusive == UtcInstant(END * 1_000_000)
    assert result.prefix_gap_classification == "unknown_unproven"
    assert result.suffix_gap_classification == "unknown_unproven"
    assert result.completeness_classification == "provider_completeness_unknown"
    assert (
        result.regular_count,
        result.special_count,
        result.missing_rate_type_count,
    ) == (
        120,
        0,
        0,
    )
    assert result.economic_policy_ref == (
        "binance.fapi.funding-rate-effective-at-funding-time.v1"
    )
    assert result.decision_grade_eligible is result.deployment_authorized is False

    first_event, last_event = result.events[0], result.events[-1]
    assert first_event.event_hash == (
        "sha256:99fb217f2d61159a28fca10d7f16587cfee364d5572e21554c65c31d70f647e7"
    )
    assert last_event.event_hash == (
        "sha256:56f00c494ea98ba0c4cd02138946cf92f01fce4450e2054bc38b43eaa75b2855"
    )
    assert first_event.stream_key == (
        "binance_usdm.funding_history.publications.koruusdt.v1"
    )
    assert first_event.event_type == "binance_usdm_koru_funding_history_publication_v1"
    assert first_event.capability.identity == "binance_usdm.funding-publications@1"
    assert first_event.instrument_id == INSTRUMENT
    assert first_event.event_time == first_event.available_time == result.coverage_start
    assert first_event.phase == TimelinePhase(110, "funding_settlement")
    assert first_event.source_sequence == SourceSequence(0)
    assert all(event.phase == first_event.phase for event in result.events)
    assert all(event.source_sequence == SourceSequence(0) for event in result.events)
    assert first_event.payload["funding_rate_units"] == 34_570
    assert first_event.payload["funding_rate_scale"] == 8
    assert first_event.payload["raw_funding_rate"] == "0.00034570"
    assert first_event.payload["mark_price_units"] == 2_098_000_000
    assert first_event.payload["mark_price_scale"] == 8
    assert first_event.payload["raw_mark_price"] == "20.98000000"
    assert first_event.payload["rate_type"] == "Regular"
    assert first_event.payload["request_hash"] == result.request_hash
    assert first_event.payload["capture_hash"] == result.capture_hash
    assert first_event.payload["source_snapshot_id"] == result.source_snapshot_id
    assert first_event.payload["receipt_hash"] == result.receipt_hash
    assert first_event.payload["observed_at_epoch_nanoseconds"] == OBSERVED_AT
    assert first_event.payload["acquired_at_epoch_nanoseconds"] == ACQUIRED_AT
    assert DATE_HEADER == RECEIPT_VALUE["date_header"]
    assert captured.snapshot.members[0].acquired_at_epoch_nanoseconds == ACQUIRED_AT


@pytest.mark.parametrize(
    "response",
    [
        transport_response(method="POST"),
        transport_response(requested_url=request_for().url + "&mutated=true"),
        transport_response(final_url=request_for().url + "&mutated=true"),
        transport_response(date_header="Mon, 24 Aug 2026 10:59:59 GMT"),
        transport_response(acquired_at=OBSERVED_AT - 1),
    ],
)
def test_actual_fixture_transport_fact_mutations_fail_capture(
    response: BinanceUsdmKoruFundingRateHistoryTransportResponseV1,
) -> None:
    outcome = capture_binance_usdm_koru_funding_rate_history_source_bounded_v1(
        request_for(), Fetch([response])
    )
    assert outcome.result is None
    assert outcome.failure is not None


def test_request_scope_is_exact_and_post_adjustment_bounded() -> None:
    with pytest.raises(ValueError, match="exact KORU"):
        request_for(
            instrument_id=InstrumentId(VenueId("binance_usdm"), "btc-usdt-perpetual")
        )
    with pytest.raises(ValueError, match="on or after"):
        request_for(start=START - 1)
    with pytest.raises(ValueError, match="after start"):
        request_for(end=START)
    with pytest.raises(ValueError, match="1 through 1000"):
        request_for(limit=0)
    with pytest.raises(ValueError, match="1 through 1000"):
        request_for(limit=1001)
    assert set(request_for().to_canonical_dict()).isdisjoint(
        {
            "observed_at_epoch_nanoseconds",
            "acquired_at_epoch_nanoseconds",
            "date_header",
        }
    )


def test_capture_retries_and_classifies_http_failures_deterministically() -> None:
    final_date = "Thu, 27 Aug 2026 08:48:03 GMT"
    final_acquired_at = ACQUIRED_AT + 2 * 86_400_000_000_000
    retried = capture_binance_usdm_koru_funding_rate_history_source_bounded_v1(
        request_for(),
        Fetch(
            [
                RuntimeError("offline"),
                transport_response(b"", status=503),
                transport_response(
                    date_header=final_date, acquired_at=final_acquired_at
                ),
            ]
        ),
    )
    assert retried.failure is None
    assert retried.result is not None
    assert retried.result.attempts == 3
    retry_receipt = json.loads(
        retried.result.snapshot.member_bytes("acquisition/acquisition-receipt.json")
    )
    assert retry_receipt["date_header"] == final_date
    assert all(
        member.acquired_at_epoch_nanoseconds == final_acquired_at
        for member in retried.result.snapshot.members
    )

    for responses, code in (
        (
            [
                transport_response(b"", status=500),
                transport_response(b"", status=500),
                transport_response(b"", status=500),
            ],
            BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.PROVIDER_UNAVAILABLE,
        ),
        (
            [
                transport_response(b"", status=429),
                transport_response(b"", status=429),
                transport_response(b"", status=429),
            ],
            BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.RATE_LIMIT_EXHAUSTED,
        ),
        (
            [transport_response(b"", status=403)],
            BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.AUTHENTICATION_REJECTED,
        ),
        (
            [transport_response(b"", status=404)],
            BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.DATA_GAP_DETECTED,
        ),
    ):
        outcome = capture_binance_usdm_koru_funding_rate_history_source_bounded_v1(
            request_for(), Fetch(list(responses))
        )
        assert outcome.result is None
        assert outcome.failure is not None
        assert outcome.failure.code is code


def test_capture_rejects_wrong_hash_noncanonical_json_and_wrong_receipt() -> None:
    wrong_hash = capture_binance_usdm_koru_funding_rate_history_source_bounded_v1(
        request_for(expected_hash="sha256:" + "0" * 64),
        Fetch([transport_response()]),
    )
    assert wrong_hash.failure is not None
    assert (
        wrong_hash.failure.code
        is BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.SOURCE_HASH_MISMATCH
    )

    noncanonical = b'[ {"symbol":"KORUUSDT"} ]'
    bad_json = capture_binance_usdm_koru_funding_rate_history_source_bounded_v1(
        request_for(noncanonical), Fetch([transport_response(noncanonical)])
    )
    assert bad_json.failure is not None
    assert (
        bad_json.failure.code
        is BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.SOURCE_SCHEMA_MISMATCH
    )

    captured = capture()
    frozen = freeze_source_snapshot(
        members=(
            RawSourceMember(
                "acquisition/acquisition-receipt.json",
                RECEIPT + b"x",
                "0644",
                ACQUIRED_AT,
                sha256(RECEIPT + b"x"),
            ),
            RawSourceMember(
                "response/funding-history.json",
                RAW,
                "0644",
                ACQUIRED_AT,
                RESPONSE_HASH,
            ),
        ),
        provenance=SourceSnapshotProvenance(
            "binance.fapi",
            captured.snapshot.provenance.source_key,
            "binance.api.terms",
            "backtest.fixture.retention",
        ),
    )
    assert frozen.snapshot is not None
    with pytest.raises(ValueError, match="exact verified"):
        BinanceUsdmKoruFundingRateHistorySourceBoundedCaptureResultV1(
            captured.request, frozen.snapshot, 1
        )


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        (
            b'[{"symbol":"KORUUSDT","symbol":"KORUUSDT","fundingTime":1784131200001,"fundingRate":"0.1","markPrice":"20.0"}]',
            BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.SOURCE_SCHEMA_MISMATCH,
        ),
        (
            b'[{"symbol":"KORUUSDT","fundingTime":1784131200001,"fundingRate":NaN,"markPrice":"20.0"}]',
            BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.SOURCE_SCHEMA_MISMATCH,
        ),
        (
            b'[{"symbol":"KORUUSDT","fundingTime":1784131200001,"fundingRate":0.1,"markPrice":"20.0"}]',
            BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.SOURCE_SCHEMA_MISMATCH,
        ),
    ],
)
def test_strict_json_rejects_duplicate_nonfinite_and_numeric_decimal_values(
    raw: bytes, code: BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1
) -> None:
    outcome = capture_binance_usdm_koru_funding_rate_history_source_bounded_v1(
        request_for(raw), Fetch([transport_response(raw)])
    )
    assert outcome.failure is not None
    assert outcome.failure.code is code


def test_missing_rate_type_is_none_special_is_retained_and_present_empty_is_rejected() -> (
    None
):
    outcome = normalize(
        compact(
            [
                row(START + 1, rate_type=None),
                row(START + 2, funding_rate="-0.00020000", rate_type="Special"),
            ]
        )
    )
    assert outcome.failure is None
    assert outcome.result is not None
    result = outcome.result
    assert (
        result.regular_count,
        result.special_count,
        result.missing_rate_type_count,
    ) == (
        0,
        1,
        1,
    )
    assert tuple(event.payload["rate_type"] for event in result.events) == (
        None,
        "Special",
    )

    rejected = normalize(compact([row(START + 1, rate_type="")]))
    assert rejected.result is None
    assert rejected.failure is not None
    assert rejected.failure.code is (
        BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.NORMALIZATION_FAILED
    )


def test_rate_type_field_presence_changes_source_record_identity() -> None:
    missing = normalize(compact([row(START + 1, rate_type=None)])).result
    regular = normalize(compact([row(START + 1, rate_type="Regular")])).result
    assert missing is not None
    assert regular is not None
    assert (
        missing.events[0].payload["source_record_hash"]
        != regular.events[0].payload["source_record_hash"]
    )
    assert missing.events[0].event_id != regular.events[0].event_id


@pytest.mark.parametrize(
    ("rows", "code"),
    [
        (
            [row(START + 1), row(START + 1)],
            BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.DUPLICATE_OR_CONFLICT,
        ),
        (
            [row(START + 1), row(START + 1, funding_rate="0.00020000")],
            BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.DUPLICATE_OR_CONFLICT,
        ),
        (
            [row(START + 2), row(START + 1)],
            BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.ORDER_VIOLATION,
        ),
        (
            [row(START - 1)],
            BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.DATA_GAP_DETECTED,
        ),
        (
            [row(END + 1)],
            BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.DATA_GAP_DETECTED,
        ),
        (
            [row(START + 1, symbol="BTCUSDT")],
            BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.DATA_GAP_DETECTED,
        ),
        (
            [row(START + 1, funding_rate="+0.00010000")],
            BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.NORMALIZATION_FAILED,
        ),
        (
            [row(START + 1, mark_price="0.00000000")],
            BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.NORMALIZATION_FAILED,
        ),
        (
            [row(START + 1, rate_type="regular")],
            BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.NORMALIZATION_FAILED,
        ),
        (
            [row(START + 1, rate_type="")],
            BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.NORMALIZATION_FAILED,
        ),
        (
            [row(START + 1, funding_rate="-0")],
            BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.NORMALIZATION_FAILED,
        ),
        (
            [row(START + 1, funding_rate="-0.00000000")],
            BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.NORMALIZATION_FAILED,
        ),
        (
            [row(START + 1, funding_rate="0.000000001")],
            BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.NORMALIZATION_FAILED,
        ),
        (
            [row(START + 1, funding_rate="00.1")],
            BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.NORMALIZATION_FAILED,
        ),
        (
            [row(START + 1, mark_price="020")],
            BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.NORMALIZATION_FAILED,
        ),
        (
            [row(START + 1, mark_price="20.000000000")],
            BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.NORMALIZATION_FAILED,
        ),
    ],
)
def test_normalization_rejects_duplicate_conflict_order_window_symbol_decimal_mark_and_type(
    rows: list[dict[str, object]],
    code: BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1,
) -> None:
    outcome = normalize(compact(rows))
    assert outcome.result is None
    assert outcome.failure is not None
    assert outcome.failure.code is code


def test_integer_and_trailing_zero_provider_lexemes_normalize_and_remain_raw() -> None:
    result = normalize(
        compact(
            [
                row(START + 1, funding_rate="0", mark_price="20"),
                row(START + 2, funding_rate="0.00010000", mark_price="20.00000000"),
            ]
        )
    ).result
    assert result is not None
    assert tuple(
        (
            event.payload["funding_rate_units"],
            event.payload["raw_funding_rate"],
            event.payload["mark_price_units"],
            event.payload["raw_mark_price"],
        )
        for event in result.events
    ) == (
        (0, "0", 2_000_000_000, "20"),
        (10_000, "0.00010000", 2_000_000_000, "20.00000000"),
    )


def test_normalization_result_reconstructs_complete_event_and_lineage_payload() -> None:
    result = normalize(compact([row(START + 1)])).result
    assert result is not None
    event = result.events[0]
    mutations: tuple[MarketEvent, ...] = (
        replace(
            event, available_time=UtcInstant(event.available_time.epoch_nanoseconds + 1)
        ),
        replace(event, event_id=event.event_id + "-forged"),
        replace(event, payload={**event.payload, "extra": "forged"}),
        replace(event, phase=TimelinePhase(0, "market_data")),
        replace(event, source_sequence=SourceSequence(1)),
        replace(event, payload={**event.payload, "rate_type": "Regular-forged"}),
        replace(event, payload={**event.payload, "raw_funding_rate": "0.0001"}),
        replace(event, payload={**event.payload, "raw_mark_price": "20"}),
        replace(
            event,
            payload={**event.payload, "receipt_hash": "sha256:" + "0" * 64},
        ),
    )
    for mutated in mutations:
        with pytest.raises(ValueError, match="exactly reconstruct"):
            replace(result, events=(mutated,))

    object.__setattr__(
        result.events[0], "event_id", result.events[0].event_id + "-forged"
    )
    with pytest.raises(ValueError, match="not canonical"):
        BinanceUsdmKoruFundingRateHistorySourceBoundedNormalizationOutcomeV1(
            result=result
        )


def test_btc_fixture_bytes_and_request_cannot_satisfy_koru_source() -> None:
    btc = (
        ROOT
        / "fixtures/market_data/providers/binance_usdm/funding-history-source-bounded-v2/response/funding-history.json"
    ).read_bytes()
    outcome = normalize(btc)
    assert outcome.result is None
    assert outcome.failure is not None
    assert (
        outcome.failure.code
        is BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.DATA_GAP_DETECTED
    )
    assert "BTCUSDT" not in request_for().url
