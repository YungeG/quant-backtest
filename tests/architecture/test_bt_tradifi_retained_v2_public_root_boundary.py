from __future__ import annotations

import ast
from pathlib import Path

import crypto_quant_bundle_builder as builder

from tests.bundle_builder.providers.binance_usdm import (
    test_koru_tradifi_source_projection_v2 as source_projection_fixture,
)

THIS_TEST = Path(__file__)
RETAINED_V2_ROOT_EXPORTS = {
    "APPROVED_MEMBER_HASHES",
    "BINANCE_USDM_KORU_AGGREGATE_TRADE_AVAILABILITY_AUTHORITY_V1",
    "BinanceUsdmKoruAggregateIdCoverageGapEvidenceV1",
    "BinanceUsdmKoruAggregateTradeAvailabilityAuthorityV1",
    "BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV1",
    "BinanceUsdmKoruAggregateTradeBoundaryIndexFailureV1",
    "BinanceUsdmKoruAggregateTradeBoundaryIndexOutcomeV1",
    "BinanceUsdmKoruAggregateTradeBoundaryIndexRequestV1",
    "BinanceUsdmKoruAggregateTradeBoundaryIndexResultV2",
    "BinanceUsdmKoruAggregateTradeRawIdGapEvidenceV1",
    "BinanceUsdmKoruAggregateTradesSourceBoundedCaptureOutcomeV1",
    "BinanceUsdmKoruAggregateTradesSourceBoundedCaptureResultV1",
    "BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1",
    "BinanceUsdmKoruAggregateTradesSourceBoundedFailureV1",
    "BinanceUsdmKoruAggregateTradesSourceBoundedNormalizationOutcomeV1",
    "BinanceUsdmKoruAggregateTradesSourceBoundedNormalizationResultV1",
    "BinanceUsdmKoruAggregateTradesSourceBoundedRequestV1",
    "BinanceUsdmKoruClosedMarketRangeTargetsOutcomeV2",
    "BinanceUsdmKoruClosedMarketRangeTargetsRequestV2",
    "BinanceUsdmKoruClosedMarketRangeTargetsResultV2",
    "BinanceUsdmKoruExecutionBoundaryV1",
    "BinanceUsdmKoruFirstRetainedTradeProjectionLineageV2",
    "BinanceUsdmKoruFundingRateHistorySourceBoundedCaptureOutcomeV1",
    "BinanceUsdmKoruFundingRateHistorySourceBoundedCaptureResultV1",
    "BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1",
    "BinanceUsdmKoruFundingRateHistorySourceBoundedFailureV1",
    "BinanceUsdmKoruFundingRateHistorySourceBoundedNormalizationOutcomeV1",
    "BinanceUsdmKoruFundingRateHistorySourceBoundedNormalizationResultV1",
    "BinanceUsdmKoruFundingRateHistorySourceBoundedRequestV1",
    "BinanceUsdmKoruFundingRateHistoryTransportResponseV1",
    "BinanceUsdmKoruMissingAggregateTradeBoundaryV1",
    "BinanceUsdmKoruMissingBoundaryProjectionV2",
    "BinanceUsdmKoruPriceBarsSourceBoundedCaptureOutcomeV1",
    "BinanceUsdmKoruPriceBarsSourceBoundedCaptureResultV1",
    "BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1",
    "BinanceUsdmKoruPriceBarsSourceBoundedFailureV1",
    "BinanceUsdmKoruPriceBarsSourceBoundedNormalizationOutcomeV1",
    "BinanceUsdmKoruPriceBarsSourceBoundedNormalizationResultV1",
    "BinanceUsdmKoruPriceBarsSourceBoundedRequestV1",
    "BinanceUsdmKoruPriceBarsSourceKindV1",
    "BinanceUsdmKoruRawIdGapStreamEvidenceV1",
    "BinanceUsdmKoruRetainedAggregateTradesAuthorityV1",
    "BinanceUsdmKoruRetainedAggregateTradesPageV1",
    "BinanceUsdmKoruRetainedPriceBarsAuthorityV1",
    "BinanceUsdmKoruSelectedAggregateTradeLineageV1",
    "BinanceUsdmKoruTradifiExecutionBundleFailureCodeV2",
    "BinanceUsdmKoruTradifiExecutionBundleFailureV2",
    "BinanceUsdmKoruTradifiExecutionBundleOutcomeV2",
    "BinanceUsdmKoruTradifiExecutionBundleRequestV2",
    "BinanceUsdmKoruTradifiExecutionBundleResultV2",
    "BinanceUsdmKoruTradifiSourceProjectionFailureCodeV2",
    "BinanceUsdmKoruTradifiSourceProjectionFailureV2",
    "BinanceUsdmKoruTradifiSourceProjectionOutcomeV2",
    "BinanceUsdmKoruTradifiSourceProjectionRequestV2",
    "BinanceUsdmKoruTradifiSourceProjectionResultV2",
    "KoruTradifiCalendarUnitAuthorityFailureCode",
    "KoruTradifiCalendarUnitAuthorityFailureV1",
    "KoruTradifiCalendarUnitAuthorityOutcomeV1",
    "KoruTradifiCalendarUnitAuthorityResultV1",
    "RawSourceMember",
    "SourceSnapshot",
    "SourceSnapshotFailure",
    "SourceSnapshotFailureCode",
    "SourceSnapshotMember",
    "SourceSnapshotOutcome",
    "SourceSnapshotProvenance",
    "build_binance_usdm_koru_aggregate_trade_boundary_index_v1",
    "build_binance_usdm_koru_aggregate_trades_retained_rest_evidence_v1",
    "build_binance_usdm_koru_closed_market_range_targets_v2",
    "build_binance_usdm_koru_price_bars_retained_observations_evidence_v1",
    "build_binance_usdm_koru_source_profile_authority_v2",
    "build_binance_usdm_koru_tradifi_execution_bundle_v2",
    "build_binance_usdm_koru_tradifi_source_projection_v2",
    "build_koru_tradifi_calendar_unit_authority_v1",
    "capture_binance_usdm_koru_aggregate_trades_from_retained_rest_v1",
    "capture_binance_usdm_koru_aggregate_trades_source_bounded_v1",
    "capture_binance_usdm_koru_funding_rate_history_source_bounded_v1",
    "capture_binance_usdm_koru_price_bars_from_retained_observations_v1",
    "capture_binance_usdm_koru_price_bars_source_bounded_v1",
    "freeze_source_snapshot",
    "normalize_binance_usdm_koru_aggregate_trades_source_bounded_v1",
    "normalize_binance_usdm_koru_funding_rate_history_source_bounded_v1",
    "normalize_binance_usdm_koru_price_bars_source_bounded_v1",
    "verify_koru_tradifi_calendar_unit_authority_v1",
    "verify_source_snapshot",
}


def _external_retained_acquisition_adapter(
    source_inputs: builder.BinanceUsdmKoruTradifiSourceProjectionRequestV2,
) -> tuple[
    builder.BinanceUsdmKoruTradifiSourceProjectionResultV2,
    builder.BinanceUsdmKoruClosedMarketRangeTargetsResultV2,
]:
    source_outcome = builder.build_binance_usdm_koru_tradifi_source_projection_v2(
        source_inputs
    )
    assert source_outcome.result is not None
    economics_outcome = builder.build_binance_usdm_koru_closed_market_range_targets_v2(
        builder.BinanceUsdmKoruClosedMarketRangeTargetsRequestV2(source_outcome.result)
    )
    assert economics_outcome.result is not None
    return source_outcome.result, economics_outcome.result


def test_retained_v2_root_exports_resolve_without_private_helpers() -> None:
    root = __import__("crypto_quant_bundle_builder", fromlist=builder.__all__)

    assert RETAINED_V2_ROOT_EXPORTS <= set(builder.__all__)
    assert all(getattr(root, name) is getattr(builder, name) for name in builder.__all__)
    assert all(not name.startswith("_") for name in builder.__all__)


def test_external_retained_adapter_imports_only_builder_root_and_constructs_v2_inputs() -> (
    None
):
    tree = ast.parse(THIS_TEST.read_text(encoding="utf-8"))
    builder_imports = {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and (node.module or "").startswith("crypto_quant_bundle_builder")
    }
    direct_builder_imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
        if alias.name.startswith("crypto_quant_bundle_builder")
    }
    assert builder_imports <= {"crypto_quant_bundle_builder"}
    assert direct_builder_imports <= {"crypto_quant_bundle_builder"}

    _, seeded = source_projection_fixture._request()
    source_inputs = builder.BinanceUsdmKoruTradifiSourceProjectionRequestV2(
        timeline_window_start=seeded.timeline_window_start,
        timeline_window_end_exclusive=seeded.timeline_window_end_exclusive,
        instrument_catalog_hash=seeded.instrument_catalog_hash,
        projection_scale=seeded.projection_scale,
        aggregate_trade_boundary_index_result=seeded.aggregate_trade_boundary_index_result,
        mark_price_results=seeded.mark_price_results,
        index_price_results=seeded.index_price_results,
        funding_result=seeded.funding_result,
        authority_result=seeded.authority_result,
    )

    source, economics = _external_retained_acquisition_adapter(source_inputs)
    assert source.request == source_inputs
    assert economics.request.source_projection == source
