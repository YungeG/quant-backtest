from __future__ import annotations

import json

import pytest
from crypto_quant_bundle_builder import (
    BinanceUsdmKoruAggregateTradeBoundaryIndexRequestV3,
    BinanceUsdmKoruExecutionBoundaryV1,
    BinanceUsdmKoruTradifiSourceProjectionFailureCodeV3,
    BinanceUsdmKoruTradifiSourceProjectionRequestV3,
    build_binance_usdm_koru_aggregate_trade_boundary_index_v3,
    build_binance_usdm_koru_tradifi_source_projection_v3,
    create_binance_usdm_koru_tradifi_source_projection_authority_v3,
    open_binance_usdm_koru_tradifi_source_projection_authority_v3,
)
from crypto_quant_bundle_builder import (
    binance_usdm_koru_aggtrade_boundary_index_v1 as boundary_index,
)
from crypto_quant_domain import ArtifactEnvelope, canonical_bytes
from tests.bundle_builder.providers.binance_usdm import (
    test_koru_tradifi_source_projection_v1 as source_fixture,
)


def _request() -> BinanceUsdmKoruTradifiSourceProjectionRequestV3:
    v1 = source_fixture._request(((source_fixture.aggregate_fixture.DAY_START_MS + 22 * 3_600_000 + 30_000, "12.340"),))
    v1_result = source_fixture.build_binance_usdm_koru_tradifi_source_projection_v1(v1).result
    assert v1_result is not None
    boundaries = tuple(
        BinanceUsdmKoruExecutionBoundaryV1(
            value.hourly_boundary, value.next_cash_market_open_or_window_end
        )
        for value in sorted(
            (*v1_result.projection_lineage, *v1_result.missing_boundaries),
            key=lambda value: value.hourly_boundary.epoch_nanoseconds,
        )
    )
    boundary = build_binance_usdm_koru_aggregate_trade_boundary_index_v3(
        BinanceUsdmKoruAggregateTradeBoundaryIndexRequestV3(
            tuple(value.capture for value in v1.aggregate_trade_results),
            v1.timeline_window_start,
            v1.timeline_window_end_exclusive,
            boundaries,
        )
    ).result
    assert boundary is not None
    return BinanceUsdmKoruTradifiSourceProjectionRequestV3(
        v1.timeline_window_start,
        v1.timeline_window_end_exclusive,
        v1.instrument_catalog_hash,
        v1.projection_scale,
        boundary,
        v1.mark_price_results,
        v1.index_price_results,
        v1.funding_result,
        v1.authority_result,
    )


def test_v3_consumes_boundary_result_without_aggregate_replay(monkeypatch) -> None:
    request = _request()
    monkeypatch.setattr(
        boundary_index, "_build_v3", lambda _request: (_ for _ in ()).throw(AssertionError("no boundary replay"))
    )
    monkeypatch.setattr(
        boundary_index, "_parse_row", lambda *_args: (_ for _ in ()).throw(AssertionError("no aggregate parse"))
    )

    outcome = build_binance_usdm_koru_tradifi_source_projection_v3(request)

    assert outcome.result is not None
    assert outcome.result.request.aggregate_trade_boundary_index_result.result_digest == request.aggregate_trade_boundary_index_result.result_digest
    assert outcome.result.aggregate_trade_capture_final_evidence == request.aggregate_trade_boundary_index_result.capture_final_evidence


@pytest.mark.parametrize(
    ("tamper", "code"),
    (
        (lambda request: object.__setattr__(request.aggregate_trade_boundary_index_result, "result_digest", "sha256:" + "0" * 64), BinanceUsdmKoruTradifiSourceProjectionFailureCodeV3.AGGREGATE_TRADES_INVALID),
        (lambda request: object.__setattr__(request.mark_price_results[0], "projected_row_count", 0), BinanceUsdmKoruTradifiSourceProjectionFailureCodeV3.PRICE_BARS_INVALID),
        (lambda request: object.__setattr__(request.funding_result, "regular_count", 0), BinanceUsdmKoruTradifiSourceProjectionFailureCodeV3.FUNDING_INVALID),
        (lambda request: object.__setattr__(request.authority_result.xkrx_calendar, "content_hash", "sha256:" + "0" * 64), BinanceUsdmKoruTradifiSourceProjectionFailureCodeV3.AUTHORITY_INVALID),
        (lambda request: object.__setattr__(request.authority_result.post_adjustment_unit_regime, "content_hash", "sha256:" + "0" * 64), BinanceUsdmKoruTradifiSourceProjectionFailureCodeV3.AUTHORITY_INVALID),
    ),
)
def test_v3_boundary_and_verified_input_tampering_fails_closed(tamper, code) -> None:
    request = _request()
    tamper(request)

    outcome = build_binance_usdm_koru_tradifi_source_projection_v3(request)

    assert outcome.result is None
    assert outcome.failure is not None
    assert outcome.failure.code is code


def test_v3_authority_tampering_fails_closed() -> None:
    outcome = build_binance_usdm_koru_tradifi_source_projection_v3(_request())
    assert outcome.result is not None
    envelope, _ = create_binance_usdm_koru_tradifi_source_projection_authority_v3(outcome.result)
    payload = json.loads(canonical_bytes(envelope.payload))
    payload["boundary_index_identity"]["result_digest"] = "sha256:" + "0" * 64
    forged = ArtifactEnvelope.create(envelope.artifact_type, envelope.schema_version, payload)

    with pytest.raises(ValueError, match="identity binding"):
        open_binance_usdm_koru_tradifi_source_projection_authority_v3(canonical_bytes(forged))
