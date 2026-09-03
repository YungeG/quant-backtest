from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from crypto_quant_backtest import (
    BacktestEvidenceRepository,
    BinanceUsdmTradifiProviderInputs,
    PreparedBacktestExecution,
    prepare_binance_usdm_tradifi_directional_bar_backtest,
    verify_binance_usdm_tradifi_directional_preparation_authority_v3,
)
from crypto_quant_backtest.binance_usdm_koru_directional_profile_v3 import (
    BinanceUsdmKoruDirectionalPlannerV3,
)
from crypto_quant_backtest.binance_usdm_tradifi_directional_preparation import (
    BinanceUsdmTradifiDirectionalPreparationV3,
    BinanceUsdmTradifiDirectionalRequestIntentV3,
)
from crypto_quant_backtest.binance_usdm_tradifi_provider import (
    BinanceUsdmTradifiBarBacktestFailure,
)
from crypto_quant_backtest.koru_tradifi_economics_authority_v3 import (
    resolve_koru_tradifi_economics_authority_v3,
)
from crypto_quant_backtest.resolution import RequestedResultGrade
from crypto_quant_backtest.target_stream import PrecomputedTargetStream
from crypto_quant_backtest.timeline import TimelineWindow
from crypto_quant_bundle_builder import (
    KoruTradifiEconomicsBundleRequestV3,
    KoruTradifiEconomicsTermsV3,
    KoruTradifiSourceProjectionContentIdentityV2,
    KoruTradifiTargetOverlayRequestV3,
    compile_binance_usdm_koru_directional_targets_v1,
    publish_koru_tradifi_economics_bundle_v3,
    publish_koru_tradifi_target_overlay_v3,
)
from crypto_quant_domain import (
    ArtifactEnvelope,
    ArtifactReadResult,
    ArtifactRef,
    CurrencyId,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_market_data import LocalMarketBundleReader

from tests.bundle_builder.providers.binance_usdm import (
    test_koru_closed_market_range_targets_v1 as closed_market_fixture,
)
from tests.bundle_builder.providers.binance_usdm import (
    test_koru_directional_target_compiler_v1 as compiler_fixture,
)
from tests.bundle_builder.providers.binance_usdm import (
    test_koru_tradifi_execution_bundle_v2 as execution_fixture,
)
from tests.runtime.providers.test_binance_usdm_tradifi_preparation_v2 import _EQUITY
from tests.runtime.resolution._fixtures import build_manifest


class _Artifacts:
    def __init__(self) -> None:
        self.values: dict[ArtifactRef, ArtifactReadResult] = {}

    def put(self, *, envelope: ArtifactEnvelope) -> ArtifactRef:
        ref = ArtifactRef.from_envelope(envelope)
        self.values[ref] = ArtifactReadResult(envelope, object(), canonical_bytes(envelope), canonical_sha256(envelope))
        return ref

    def read(self, *, ref: ArtifactRef) -> ArtifactReadResult:
        return self.values[ref]


def _overlay(tmp_path: Path, *, source=None, target_key: str = "target.a"):
    source = execution_fixture._source() if source is None else source
    artifacts = _Artifacts()
    economics = publish_koru_tradifi_economics_bundle_v3(KoruTradifiEconomicsBundleRequestV3(
        source, KoruTradifiSourceProjectionContentIdentityV2(source.fragment_digest, source.request.request_hash),
        KoruTradifiEconomicsTermsV3.from_source_projection(source, execution_account_id="account-1"), artifacts, tmp_path / "economics",
    ))
    assert economics.result is not None
    compiled = compile_binance_usdm_koru_directional_targets_v1(
        compiler_fixture._request(source, (compiler_fixture._recipe(source, key=target_key),))
    )
    assert compiled.result is not None
    overlay = publish_koru_tradifi_target_overlay_v3(KoruTradifiTargetOverlayRequestV3(
        economics.result, compiled.result,
        ArtifactRef("koru_directional_target_compile_result", 1, compiled.result.result_digest),
        ArtifactRef("koru_directional_discovery_scope", 1, compiled.result.request.scope.scope_digest),
        target_key, tmp_path / "overlay",
    ))
    assert overlay.result is not None
    return economics.result, overlay.result, artifacts


def _prepare(tmp_path: Path, *, source=None, target_key: str = "target.a"):
    economics, overlay, artifacts = _overlay(tmp_path, source=source, target_key=target_key)
    prepared = prepare_binance_usdm_tradifi_directional_bar_backtest(
        experiment_id="directional-v3-smoke", market_reader=overlay.reader,
        provider_inputs=BinanceUsdmTradifiProviderInputs(build_manifest(), _EQUITY), artifact_reader=artifacts,
        artifact_publisher=artifacts, publication_root=tmp_path,
    )
    assert isinstance(prepared, PreparedBacktestExecution)
    return economics, overlay, artifacts, prepared


def test_v3_overlay_copies_economics_bytes_and_adds_one_target(tmp_path: Path) -> None:
    economics, overlay, _ = _overlay(tmp_path)
    economics_streams = {stream.stream_key for stream in economics.manifest.streams}
    overlay_streams = {stream.stream_key for stream in overlay.manifest.streams}
    assert economics_streams < overlay_streams
    assert overlay_streams - economics_streams == {
        overlay.selected_stream.target_stream_key,
        "binance_usdm.tradifi.target_overlay_authority.koruusdt.v3",
    }
    for stream in economics.manifest.streams:
        assert canonical_bytes(_events(economics.reader, stream.stream_key)) == canonical_bytes(_events(overlay.reader, stream.stream_key))
    assert not any("closed_market_range" in key or "hybrid_authority" in key for key in overlay_streams)


def test_v3_overlay_prepares_runs_and_loads_completed_financial_evidence(tmp_path: Path) -> None:
    _, _, artifacts, prepared = _prepare(tmp_path, source=_sealed_nonzero_source())
    first = prepared.runtime.run(prepared.execution_request)
    second = prepared.runtime.run(prepared.execution_request)
    assert first == second
    completed = BacktestEvidenceRepository(artifacts).load_completed(first)
    assert completed.execution_summary.fills
    assert completed.execution_summary.final_journal.entry_count > 0


def test_v3_target_verifier_rejects_tampered_overlay_authority(tmp_path: Path) -> None:
    _, overlay, _ = _overlay(tmp_path)
    rejected = verify_binance_usdm_tradifi_directional_preparation_authority_v3(
        market_reader=_TamperReader(overlay.reader, "binance_usdm.tradifi.target_overlay_authority.koruusdt.v3")
    )
    assert isinstance(rejected, BinanceUsdmTradifiBarBacktestFailure)


def test_v3_preparation_rejects_replaced_target_before_planning(tmp_path: Path) -> None:
    _, overlay, artifacts = _overlay(tmp_path)
    authority = verify_binance_usdm_tradifi_directional_preparation_authority_v3(market_reader=overlay.reader)
    assert not isinstance(authority, BinanceUsdmTradifiBarBacktestFailure)
    economics = resolve_koru_tradifi_economics_authority_v3(
        market_reader=overlay.reader, artifact_reader=artifacts,
        provider_inputs=BinanceUsdmTradifiProviderInputs(build_manifest(), _EQUITY), experiment_id="target-tamper",
    )
    assert not isinstance(economics, BinanceUsdmTradifiBarBacktestFailure)
    target = BinanceUsdmKoruDirectionalPlannerV3.target(authority)
    event = replace(target.target_stream.events[0], event_id=target.target_stream.events[0].event_id + "-tampered")
    stream = PrecomputedTargetStream(target.target_stream.stream_key, (event, *target.target_stream.events[1:]))
    tampered = replace(target, target_stream=stream, target_stream_digest=stream.target_stream_digest)
    intent = BinanceUsdmTradifiDirectionalRequestIntentV3(
        "target-tamper", TimelineWindow(overlay.manifest.coverage_start, overlay.manifest.coverage_start, overlay.manifest.coverage_end_exclusive),
        "account-1", CurrencyId("USDT"), 0, overlay.reader.bundle_ref,
        authority.strategy_ref, authority.parameter_ref, authority.strategy_id, authority.sleeve_id, RequestedResultGrade.DEVELOPMENT,
    )

    with pytest.raises(ValueError, match="directional_v3_binding"):
        BinanceUsdmTradifiDirectionalPreparationV3(authority, tampered, economics, intent)


def test_v3_public_preparation_rejects_direct_reader(tmp_path: Path) -> None:
    _, overlay, artifacts = _overlay(tmp_path)
    with pytest.raises(ValueError, match="repository-open"):
        prepare_binance_usdm_tradifi_directional_bar_backtest(
            experiment_id="direct-reader", market_reader=LocalMarketBundleReader(overlay.reader._delegate),
            provider_inputs=BinanceUsdmTradifiProviderInputs(build_manifest(), _EQUITY), artifact_reader=artifacts,
            artifact_publisher=artifacts, publication_root=tmp_path,
        )


def test_v3_rejects_missing_calendar_artifact(tmp_path: Path) -> None:
    _, overlay, artifacts = _overlay(tmp_path)
    calendar_ref = next(ref for ref, value in artifacts.values.items() if value.envelope.artifact_type == "xkrx_regular_session_calendar")
    del artifacts.values[calendar_ref]
    rejected = prepare_binance_usdm_tradifi_directional_bar_backtest(
        experiment_id="missing-calendar", market_reader=overlay.reader,
        provider_inputs=BinanceUsdmTradifiProviderInputs(build_manifest(), _EQUITY), artifact_reader=artifacts,
        artifact_publisher=artifacts, publication_root=tmp_path,
    )
    assert isinstance(rejected, BinanceUsdmTradifiBarBacktestFailure)


def test_v1_v2_sentinels_and_runtime_builder_boundary() -> None:
    assert execution_fixture._build().manifest.schema_version == 2
    source = Path(__import__("crypto_quant_backtest.koru_tradifi_economics_authority_v3", fromlist=["x"]).__file__).read_text()
    assert "crypto_quant_bundle_builder" not in source


def _events(reader, key):
    cursor = reader.open_cursor(key, batch_size=64)
    events = []
    while not cursor.exhausted:
        batch, cursor = reader.read_batch(cursor)
        events.extend(batch)
    return tuple(events)


class _TamperReader:
    def __init__(self, base, key: str) -> None:
        self._base, self._key = base, key

    @property
    def bundle_ref(self):
        return self._base.bundle_ref

    @property
    def manifest(self):
        return self._base.manifest

    def open_cursor(self, stream_key, *, batch_size):
        return self._base.open_cursor(stream_key, batch_size=batch_size)

    def read_batch(self, cursor):
        events, next_cursor = self._base.read_batch(cursor)
        if cursor.stream_manifest.stream_key == self._key:
            events = (replace(events[0], event_id="tampered"),)
        return events, next_cursor


def _sealed_nonzero_source():
    base = closed_market_fixture._weekend_fragment()
    prices = {"open_price": "100.00000000", "high_price": "101.00000000", "low_price": "99.00000000", "close_price": "100.00000000"}
    mark_prices = (
        closed_market_fixture._price_result(closed_market_fixture.price_fixture.BinanceUsdmKoruPriceBarsSourceKindV1.MARK_PRICE, "2026-07-17", {}, **prices),
        closed_market_fixture._price_result(closed_market_fixture.price_fixture.BinanceUsdmKoruPriceBarsSourceKindV1.MARK_PRICE, "2026-07-18", {0: "99.00000000", 1: "99.00000000", 2: "99.00000000"}, **prices),
    )
    from crypto_quant_bundle_builder.binance_usdm_koru_tradifi_source_projection_v1 import (
        build_binance_usdm_koru_tradifi_source_projection_v1,
    )
    source = build_binance_usdm_koru_tradifi_source_projection_v1(replace(base.request, mark_price_results=mark_prices)).result
    assert source is not None
    return execution_fixture._source(v1_source=source)
