from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from crypto_quant_backtest import (
    BacktestEvidenceRepository,
    BinanceUsdmTradifiProviderInputs,
    PreparedBacktestExecution,
    prepare_binance_usdm_tradifi_directional_bar_backtest_v4,
    verify_binance_usdm_tradifi_directional_preparation_authority_v4,
)
from crypto_quant_backtest.binance_usdm_koru_directional_profile_v4 import (
    BinanceUsdmKoruDirectionalPlannerV4,
)
from crypto_quant_backtest.binance_usdm_tradifi_directional_preparation_v4 import (
    BinanceUsdmTradifiDirectionalPreparationV4,
    BinanceUsdmTradifiDirectionalRequestIntentV4,
)
from crypto_quant_backtest.binance_usdm_tradifi_provider import (
    BinanceUsdmTradifiBarBacktestFailure,
)
from crypto_quant_backtest.koru_tradifi_economics_authority_v4 import (
    resolve_koru_tradifi_economics_authority_v4,
)
from crypto_quant_backtest.resolution import RequestedResultGrade
from crypto_quant_backtest.target_stream import PrecomputedTargetStream
from crypto_quant_backtest.timeline import TimelineWindow
from crypto_quant_bundle_builder import (
    BinanceUsdmKoruAggregateTradeBoundaryIndexRequestV3,
    BinanceUsdmKoruExecutionBoundaryV1,
    BinanceUsdmKoruTradifiSourceProjectionRequestV3,
    KoruDirectionalDiscoveryScopeV1,
    KoruDirectionalTargetCompileRequestV2,
    KoruTradifiEconomicsBundleRequestV4,
    KoruTradifiEconomicsTermsV4,
    KoruTradifiSourceProjectionContentIdentityV3,
    KoruTradifiTargetOverlayRequestV4,
    build_binance_usdm_koru_aggregate_trade_boundary_index_v3,
    build_binance_usdm_koru_tradifi_source_projection_v3,
    compile_binance_usdm_koru_directional_targets_v2,
    create_binance_usdm_koru_tradifi_source_projection_authority_v3,
    publish_koru_tradifi_economics_bundle_v4,
    publish_koru_tradifi_target_overlay_v4,
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
        self.put_count = 0

    def put(self, *, envelope: ArtifactEnvelope) -> ArtifactRef:
        self.put_count += 1
        ref = ArtifactRef.from_envelope(envelope)
        self.values[ref] = ArtifactReadResult(envelope, object(), canonical_bytes(envelope), canonical_sha256(envelope))
        return ref

    def read(self, *, ref: ArtifactRef) -> ArtifactReadResult:
        return self.values[ref]


def _overlay(tmp_path: Path, *, source=None, target_key: str = "target.a"):
    source, authority, authority_ref = _funded_source_and_authority() if source is None else _source_authority(source)
    artifacts = _Artifacts()
    identity = KoruTradifiSourceProjectionContentIdentityV3(
        authority_ref, authority.content_hash, source.fragment_digest, source.request.request_hash,
    )
    economics = publish_koru_tradifi_economics_bundle_v4(KoruTradifiEconomicsBundleRequestV4(
        source, identity, KoruTradifiEconomicsTermsV4.from_source_projection(source, execution_account_id="account-1"), artifacts, tmp_path / "economics",
    ))
    assert economics.result is not None
    recipe = compiler_fixture._recipe(source, key=target_key)
    compiled = compile_binance_usdm_koru_directional_targets_v2(KoruDirectionalTargetCompileRequestV2(
        source, authority_ref, authority.content_hash, KoruDirectionalDiscoveryScopeV1(), (recipe,),
    ))
    assert compiled.result is not None
    overlay = publish_koru_tradifi_target_overlay_v4(KoruTradifiTargetOverlayRequestV4(
        economics.result, compiled.result,
        ArtifactRef("koru_directional_target_compile_result", 2, compiled.result.result_digest),
        ArtifactRef("koru_directional_discovery_scope", 1, compiled.result.request.scope.scope_digest),
        target_key, tmp_path / "overlay",
    ))
    assert overlay.result is not None
    return economics.result, overlay.result, artifacts


def _source_authority(source):
    authority, ref = create_binance_usdm_koru_tradifi_source_projection_authority_v3(source)
    return source, authority, ref


def _funded_source_and_authority():
    from tests.bundle_builder.providers.binance_usdm import (
        test_koru_tradifi_source_projection_v1 as source_v1,
    )

    hour = 3_600_000
    request = source_v1._request(
        (
            (source_v1.aggregate_fixture.DAY_START_MS + 22 * hour + 30_000, "12.340"),
            (source_v1.aggregate_fixture.DAY_START_MS + 24 * hour + 30_000, "12.340"),
        ),
        start_hour=20,
        end_hour=25,
    )
    def premium_prices(utc_date: str):
        day_start = source_v1._day_start_ms(utc_date)
        rows = [
            (row[0], row[1], "12.50000000", "11.50000000", "12.00000000", *row[5:])
            if int(row[0]) < day_start + 22 * hour else row
            for row in source_v1._price_rows(day_start)
        ]
        archive, checksum = source_v1.price_fixture.evidence(
            tuple(rows), member_name=f"KORUUSDT-1h-{utc_date}.csv", checksum_name=f"KORUUSDT-1h-{utc_date}.zip",
        )
        day_start_ns = source_v1._day_start_ms(utc_date) * 1_000_000
        price_request = source_v1.price_fixture.request_for(
            source_v1._KIND.MARK_PRICE, archive, checksum, utc_date=utc_date,
            archive_available_at=day_start_ns + source_v1._DAY_NS, acquired_at=day_start_ns + 2 * source_v1._DAY_NS,
        )
        archive_url, checksum_url = price_request.urls
        capture = source_v1.price_fixture.capture_binance_usdm_koru_price_bars_source_bounded_v1(
            price_request, source_v1.price_fixture.Fetch({archive_url: [(200, archive)], checksum_url: [(200, checksum)]}),
        ).result
        assert capture is not None
        result = source_v1.price_fixture.normalize_binance_usdm_koru_price_bars_source_bounded_v1(capture).result
        assert result is not None
        return result

    request = replace(
        request,
        mark_price_results=tuple(premium_prices(value.capture.request.utc_date) for value in request.mark_price_results),
    )
    v1 = source_v1.build_binance_usdm_koru_tradifi_source_projection_v1(request).result
    assert v1 is not None
    boundaries = tuple(
        BinanceUsdmKoruExecutionBoundaryV1(value.hourly_boundary, value.next_cash_market_open_or_window_end)
        for value in sorted((*v1.projection_lineage, *v1.missing_boundaries), key=lambda value: value.hourly_boundary.epoch_nanoseconds)
    )
    boundary = build_binance_usdm_koru_aggregate_trade_boundary_index_v3(
        BinanceUsdmKoruAggregateTradeBoundaryIndexRequestV3(
            tuple(value.capture for value in request.aggregate_trade_results),
            request.timeline_window_start, request.timeline_window_end_exclusive, boundaries,
        )
    ).result
    assert boundary is not None
    source = build_binance_usdm_koru_tradifi_source_projection_v3(
        BinanceUsdmKoruTradifiSourceProjectionRequestV3(
            request.timeline_window_start, request.timeline_window_end_exclusive, request.instrument_catalog_hash,
            request.projection_scale, boundary, request.mark_price_results, request.index_price_results,
            request.funding_result, request.authority_result,
        )
    ).result
    assert source is not None
    return _source_authority(source)

def _prepare(tmp_path: Path, *, source=None, target_key: str = "target.a"):
    economics, overlay, artifacts = _overlay(tmp_path, source=source, target_key=target_key)
    prepared = prepare_binance_usdm_tradifi_directional_bar_backtest_v4(
        experiment_id="directional-v4-smoke", market_reader=overlay.reader,
        provider_inputs=BinanceUsdmTradifiProviderInputs(build_manifest(), _EQUITY), artifact_reader=artifacts,
        artifact_publisher=artifacts, publication_root=tmp_path,
    )
    assert isinstance(prepared, PreparedBacktestExecution)
    return economics, overlay, artifacts, prepared


@pytest.fixture(scope="module")
def _v4_tamper_overlay(tmp_path_factory):
    return _overlay(tmp_path_factory.mktemp("v4-tamper-overlay"))


@pytest.fixture
def v4_tamper_inputs(_v4_tamper_overlay):
    _, overlay, artifacts = _v4_tamper_overlay
    copied = _Artifacts()
    copied.values = dict(artifacts.values)
    return overlay, copied


def test_v4_overlay_copies_economics_bytes_and_adds_one_target(tmp_path: Path) -> None:
    economics, overlay, _ = _overlay(tmp_path)
    economics_streams = {stream.stream_key for stream in economics.manifest.streams}
    overlay_streams = {stream.stream_key for stream in overlay.manifest.streams}
    assert economics_streams < overlay_streams
    assert overlay_streams - economics_streams == {
        overlay.selected_stream.target_stream_key,
        "binance_usdm.tradifi.target_overlay_authority.koruusdt.v4",
    }
    for stream in economics.manifest.streams:
        assert canonical_bytes(_events(economics.reader, stream.stream_key)) == canonical_bytes(_events(overlay.reader, stream.stream_key))
    assert not any("closed_market_range" in key or "hybrid_authority" in key for key in overlay_streams)


def test_v4_overlay_prepares_runs_and_loads_completed_financial_evidence(tmp_path: Path) -> None:
    _, _, artifacts, prepared = _prepare(tmp_path, source=None)
    first = prepared.runtime.run(prepared.execution_request)
    second = prepared.runtime.run(prepared.execution_request)
    assert first == second
    completed = BacktestEvidenceRepository(artifacts).load_completed(first)
    assert completed.execution_summary.fills
    assert completed.execution_summary.final_journal.entry_count > 0


def test_v4_target_verifier_rejects_tampered_overlay_authority(tmp_path: Path) -> None:
    _, overlay, _ = _overlay(tmp_path)
    rejected = verify_binance_usdm_tradifi_directional_preparation_authority_v4(
        market_reader=_TamperReader(overlay.reader, "binance_usdm.tradifi.target_overlay_authority.koruusdt.v4")
    )
    assert isinstance(rejected, BinanceUsdmTradifiBarBacktestFailure)


def test_v4_preparation_rejects_replaced_target_before_planning(tmp_path: Path) -> None:
    _, overlay, artifacts = _overlay(tmp_path)
    authority = verify_binance_usdm_tradifi_directional_preparation_authority_v4(market_reader=overlay.reader)
    assert not isinstance(authority, BinanceUsdmTradifiBarBacktestFailure)
    economics = resolve_koru_tradifi_economics_authority_v4(
        market_reader=overlay.reader, artifact_reader=artifacts,
        provider_inputs=BinanceUsdmTradifiProviderInputs(build_manifest(), _EQUITY), experiment_id="target-tamper",
    )
    assert not isinstance(economics, BinanceUsdmTradifiBarBacktestFailure)
    target = BinanceUsdmKoruDirectionalPlannerV4.target(authority)
    event = replace(target.target_stream.events[0], event_id=target.target_stream.events[0].event_id + "-tampered")
    stream = PrecomputedTargetStream(target.target_stream.stream_key, (event, *target.target_stream.events[1:]))
    tampered = replace(target, target_stream=stream, target_stream_digest=stream.target_stream_digest)
    intent = BinanceUsdmTradifiDirectionalRequestIntentV4(
        "target-tamper", TimelineWindow(overlay.manifest.coverage_start, overlay.manifest.coverage_start, overlay.manifest.coverage_end_exclusive),
        "account-1", CurrencyId("USDT"), 0, overlay.reader.bundle_ref,
        authority.strategy_ref, authority.parameter_ref, authority.strategy_id, authority.sleeve_id, RequestedResultGrade.DEVELOPMENT,
    )

    with pytest.raises(ValueError, match="directional_v4_binding"):
        BinanceUsdmTradifiDirectionalPreparationV4(authority, tampered, economics, intent)


def test_v4_public_preparation_rejects_direct_reader(tmp_path: Path) -> None:
    _, overlay, artifacts = _overlay(tmp_path)
    with pytest.raises(ValueError, match="repository-open"):
        prepare_binance_usdm_tradifi_directional_bar_backtest_v4(
            experiment_id="direct-reader", market_reader=LocalMarketBundleReader(overlay.reader._delegate),
            provider_inputs=BinanceUsdmTradifiProviderInputs(build_manifest(), _EQUITY), artifact_reader=artifacts,
            artifact_publisher=artifacts, publication_root=tmp_path,
        )


def test_v4_rejects_missing_calendar_artifact(tmp_path: Path) -> None:
    _, overlay, artifacts = _overlay(tmp_path)
    calendar_ref = next(ref for ref, value in artifacts.values.items() if value.envelope.artifact_type == "xkrx_regular_session_calendar")
    del artifacts.values[calendar_ref]
    rejected = prepare_binance_usdm_tradifi_directional_bar_backtest_v4(
        experiment_id="missing-calendar", market_reader=overlay.reader,
        provider_inputs=BinanceUsdmTradifiProviderInputs(build_manifest(), _EQUITY), artifact_reader=artifacts,
        artifact_publisher=artifacts, publication_root=tmp_path,
    )
    assert isinstance(rejected, BinanceUsdmTradifiBarBacktestFailure)


@pytest.mark.parametrize("field", ("ref", "content_hash", "request_hash", "fragment"))
def test_v4_public_preparation_rejects_source_authority_permutations_before_publication(
    tmp_path: Path, field: str, v4_tamper_inputs,
) -> None:
    overlay, artifacts = v4_tamper_inputs

    def tamper(payload):
        if field == "ref":
            value = dict(payload["source_projection_authority_ref"])
            value["artifact_type"] = "tampered_source_authority"
            payload["source_projection_authority_ref"] = value
        elif field == "content_hash":
            payload["source_projection_authority_content_hash"] = _ZERO_DIGEST
        elif field == "request_hash":
            payload["source_projection_request_hash"] = _ZERO_DIGEST
        else:
            payload["source_fragment_digest"] = _ZERO_DIGEST

    _assert_public_rejection(tmp_path, _tampered_overlay_reader(overlay.reader, _OVERLAY_AUTHORITY_STREAM, tamper), artifacts)


@pytest.mark.parametrize("field", ("ref", "digest", "authority", "price", "account"))
def test_v4_public_preparation_rejects_economics_authority_permutations_before_publication(
    tmp_path: Path, field: str, v4_tamper_inputs,
) -> None:
    overlay, artifacts = v4_tamper_inputs

    def tamper(payload):
        if field == "ref":
            value = dict(payload["economics_bundle_ref"])
            value["manifest_hash"] = _ZERO_DIGEST
            payload["economics_bundle_ref"] = value
        elif field == "digest":
            payload["economics_bundle_digest"] = _ZERO_DIGEST
        elif field == "authority":
            payload["economics_authority_digest"] = _ZERO_DIGEST
        else:
            binding_key = {
                "price": "price_purpose_authority_binding",
                "account": "account_authority_binding",
            }[field]
            value = dict(payload[binding_key])
            value["event_id"] = "tampered"
            payload[binding_key] = value

    _assert_public_rejection(tmp_path, _tampered_overlay_reader(overlay.reader, _OVERLAY_AUTHORITY_STREAM, tamper), artifacts)


@pytest.mark.parametrize("field", ("ref", "schema", "digest"))
def test_v4_public_preparation_rejects_compiler_result_permutations_before_publication(
    tmp_path: Path, field: str, v4_tamper_inputs,
) -> None:
    overlay, artifacts = v4_tamper_inputs

    def tamper(payload):
        if field == "ref":
            value = dict(payload["compiler_result_ref"])
            value["artifact_type"] = "tampered_compiler_result"
            payload["compiler_result_ref"] = value
        elif field == "schema":
            value = dict(payload["compiler_result_ref"])
            value["schema_version"] = 1
            payload["compiler_result_ref"] = value
        else:
            payload["compiler_result_digest"] = _ZERO_DIGEST

    _assert_public_rejection(tmp_path, _tampered_overlay_reader(overlay.reader, _OVERLAY_AUTHORITY_STREAM, tamper), artifacts)


@pytest.mark.parametrize("field", ("readback", "ref", "envelope"))
def test_v4_public_preparation_rejects_source_profile_permutations_before_publication(
    tmp_path: Path, field: str, v4_tamper_inputs,
) -> None:
    overlay, artifacts = v4_tamper_inputs
    reader = overlay.reader
    if field == "ref":
        reader = _tampered_overlay_reader(
            reader, _OVERLAY_AUTHORITY_STREAM,
            lambda payload: payload.update({"source_profile_authority_ref": {**payload["source_profile_authority_ref"], "content_hash": _ZERO_DIGEST}}),
        )
    elif field == "envelope":
        reader = _tampered_overlay_reader(
            reader, _OVERLAY_AUTHORITY_STREAM,
            lambda payload: payload["source_profile_authority_envelope"].update({"content_hash": _ZERO_DIGEST}),
        )
    else:
        ref = next(ref for ref, value in artifacts.values.items() if value.envelope.artifact_type == "binance_usdm_koru_source_profile_authority")
        artifacts.values[ref] = _forged_readback(artifacts.values[ref])

    _assert_public_rejection(tmp_path, reader, artifacts)


@pytest.mark.parametrize("field", ("digest", "manifest", "event"))
def test_v4_public_preparation_rejects_target_stream_permutations_before_publication(
    tmp_path: Path, field: str, v4_tamper_inputs,
) -> None:
    overlay, artifacts = v4_tamper_inputs

    def tamper(payload):
        if field == "digest":
            payload["target_stream_digest"] = _ZERO_DIGEST
        elif field == "manifest":
            value = dict(payload["target_stream_manifest"])
            value["content_hash"] = _ZERO_DIGEST
            payload["target_stream_manifest"] = value
        else:
            events = list(payload["target_events"])
            events[0] = {**events[0], "event_id": "tampered"}
            payload["target_events"] = tuple(events)

    _assert_public_rejection(tmp_path, _tampered_overlay_reader(overlay.reader, _OVERLAY_AUTHORITY_STREAM, tamper), artifacts)


def test_v4_public_preparation_rejects_v3_reader_before_publication(tmp_path: Path) -> None:
    from tests.runtime.providers import (
        test_binance_usdm_tradifi_directional_preparation_v3 as v3_fixture,
    )

    _, overlay, _ = v3_fixture._overlay(tmp_path / "v3")
    _assert_public_rejection(tmp_path, overlay.reader, _Artifacts())


def test_v1_v2_sentinels_and_runtime_builder_boundary() -> None:
    assert execution_fixture._build().manifest.schema_version == 2
    source = Path(__import__("crypto_quant_backtest.koru_tradifi_economics_authority_v4", fromlist=["x"]).__file__).read_text()
    assert "crypto_quant_bundle_builder" not in source


def _events(reader, key):
    cursor = reader.open_cursor(key, batch_size=64)
    events = []
    while not cursor.exhausted:
        batch, cursor = reader.read_batch(cursor)
        events.extend(batch)
    return tuple(events)


_OVERLAY_AUTHORITY_STREAM = "binance_usdm.tradifi.target_overlay_authority.koruusdt.v4"
_ZERO_DIGEST = "sha256:" + "0" * 64


def _assert_public_rejection(tmp_path: Path, reader, artifacts: _Artifacts) -> None:
    artifacts.put_count = 0
    publication_root = tmp_path / "blocked"
    rejected = prepare_binance_usdm_tradifi_directional_bar_backtest_v4(
        experiment_id="tampered-v4", market_reader=reader,
        provider_inputs=BinanceUsdmTradifiProviderInputs(build_manifest(), _EQUITY),
        artifact_reader=artifacts, artifact_publisher=artifacts, publication_root=publication_root,
    )
    assert isinstance(rejected, BinanceUsdmTradifiBarBacktestFailure)
    assert artifacts.put_count == 0
    assert not any(
        value.envelope.artifact_type in {"backtest_request", "backtest_execution_input_bundle"}
        for value in artifacts.values.values()
    )
    assert not publication_root.exists()


class _TamperedOverlayDelegate:
    def __init__(self, base, key: str, tamper) -> None:
        self._base, self._key, self._tamper = base, key, tamper

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
            payload = dict(events[0].payload)
            self._tamper(payload)
            events = (replace(events[0], payload=payload),)
        return events, next_cursor

    def resume_cursor(self, cursor, *, batch_size=None):
        return self._base.resume_cursor(cursor, batch_size=batch_size)


def _tampered_overlay_reader(base: LocalMarketBundleReader, key: str, tamper):
    reader = LocalMarketBundleReader(base._delegate)
    reader._repository_open_provenance_v1 = base._repository_open_provenance_v1
    reader._repository_open_identity_capability_v1 = base._repository_open_identity_capability_v1
    reader._delegate = _TamperedOverlayDelegate(base._delegate, key, tamper)
    return reader


def _forged_readback(value: ArtifactReadResult) -> ArtifactReadResult:
    forged = object.__new__(ArtifactReadResult)
    object.__setattr__(forged, "envelope", value.envelope)
    object.__setattr__(forged, "artifact", value.artifact)
    object.__setattr__(forged, "source_bytes", b"tampered")
    object.__setattr__(forged, "source_hash", _ZERO_DIGEST)
    return forged


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
