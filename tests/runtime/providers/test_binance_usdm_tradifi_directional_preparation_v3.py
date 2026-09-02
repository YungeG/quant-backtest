from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from crypto_quant_backtest import (
    BacktestEvidenceError,
    BacktestEvidenceRepository,
    BinanceUsdmTradifiProviderInputs,
    PreparedBacktestExecution,
    prepare_binance_usdm_tradifi_directional_bar_backtest,
    verify_binance_usdm_tradifi_directional_preparation_authority_v3,
)
from crypto_quant_backtest.binance_usdm_tradifi_provider import (
    BinanceUsdmTradifiBarBacktestFailure,
)
from crypto_quant_bundle_builder import (
    BinanceUsdmKoruDirectionalExecutionBundleRequestV3,
    build_binance_usdm_koru_directional_execution_bundle_v3,
    compile_binance_usdm_koru_directional_targets_v1,
    publish_binance_usdm_koru_directional_hybrid_bundle_v3,
)
from crypto_quant_domain import (
    ArtifactEnvelope,
    ArtifactReadResult,
    ArtifactRef,
    canonical_bytes,
    canonical_sha256,
)
from tests.bundle_builder.providers.binance_usdm import (
    test_koru_directional_target_compiler_v1 as compiler_fixture,
)
from tests.bundle_builder.providers.binance_usdm import (
    test_koru_tradifi_execution_bundle_v2 as execution_fixture,
)
from tests.runtime.providers import test_binance_usdm_tradifi_preparation as v1_fixture
from tests.runtime.providers.test_binance_usdm_tradifi_preparation_v2 import _EQUITY
from tests.runtime.resolution._fixtures import build_manifest


class _Artifacts:
    def __init__(self, bundle) -> None:
        self.values: dict[ArtifactRef, ArtifactReadResult] = {}
        for envelope in (*bundle.target_result.artifacts, *bundle.authority_artifacts):
            self.put(envelope=envelope)

    def put(self, *, envelope: ArtifactEnvelope) -> ArtifactRef:
        ref = ArtifactRef.from_envelope(envelope)
        source = canonical_bytes(envelope)
        self.values[ref] = ArtifactReadResult(envelope, object(), source, canonical_sha256(envelope))
        return ref

    def read(self, *, ref: ArtifactRef) -> ArtifactReadResult:
        return self.values[ref]


def _authorities(*, target_key: str = "target.a"):
    source = execution_fixture._source()
    v2 = execution_fixture._build(source)
    compiled = compile_binance_usdm_koru_directional_targets_v1(
        compiler_fixture._request(source, (compiler_fixture._recipe(source, key=target_key),))
    )
    assert compiled.result is not None
    v3 = build_binance_usdm_koru_directional_execution_bundle_v3(
        BinanceUsdmKoruDirectionalExecutionBundleRequestV3(
            compiled.result,
            ArtifactRef("koru_directional_target_compile_result", 1, compiled.result.result_digest),
            ArtifactRef("koru_directional_discovery_scope", 1, compiled.result.request.scope.scope_digest),
            target_key,
        )
    )
    assert v3.result is not None
    return v2, v3.result, _Artifacts(v2)


def _hybrid(v2, v3, tmp_path: Path):
    return publish_binance_usdm_koru_directional_hybrid_bundle_v3(
        v2_market_reader=v2.reader,
        v3_execution_bundle=v3,
        publication_root=tmp_path,
    )


def _prepare(tmp_path: Path):
    v2, v3, artifacts = _authorities()
    prepared = prepare_binance_usdm_tradifi_directional_bar_backtest(
        market_reader=_hybrid(v2, v3, tmp_path),
        provider_inputs=BinanceUsdmTradifiProviderInputs(build_manifest(), _EQUITY),
        artifact_reader=artifacts,
        artifact_publisher=artifacts,
        publication_root=tmp_path,
    )
    assert isinstance(prepared, PreparedBacktestExecution)
    return v2, v3, artifacts, prepared


def test_v3_authority_replays_published_target_without_compilation(tmp_path: Path) -> None:
    v2, v3, _ = _authorities()
    verified = verify_binance_usdm_tradifi_directional_preparation_authority_v3(market_reader=_hybrid(v2, v3, tmp_path))
    assert not isinstance(verified, BinanceUsdmTradifiBarBacktestFailure)
    assert verified.events == v3.selected_stream.events


def test_v3_hybrid_prepares_and_replays_a_bounded_normal_runtime(tmp_path: Path) -> None:
    v2, v3, _, prepared = _prepare(tmp_path)
    assert prepared.execution_request.request.target_stream_digest == v3.selected_stream.target_stream_digest
    assert prepared.execution_request.request.market_bundle_ref != v2.bundle_ref
    # One normal runtime call executes its bounded deterministic replay attempts.
    assert prepared.runtime.run(prepared.execution_request) is not None


def test_v3_hybrid_canonical_cache_replays_the_same_request_and_result(tmp_path: Path) -> None:
    _, _, artifacts, prepared = _prepare(tmp_path)
    first_request = prepared.execution_request.request
    first = prepared.runtime.run(prepared.execution_request)
    with pytest.raises(BacktestEvidenceError, match="accounting_journal_entry"):
        BacktestEvidenceRepository(artifacts).load_completed(first)
    second = prepared.runtime.run(prepared.execution_request)
    assert second == first
    assert canonical_bytes(second) == canonical_bytes(first)
    assert prepared.execution_request.request == first_request
    assert prepared.semantic_run_id.startswith("run_")


def test_v3_hybrid_preserves_v1_v2_authority_bytes(tmp_path: Path) -> None:
    v2, _, _, _ = _prepare(tmp_path)
    v1_bytes = canonical_bytes(v1_fixture._accepted_bundle())
    v2_bytes = canonical_bytes(v2)
    _prepare(tmp_path)
    assert canonical_bytes(v1_fixture._accepted_bundle()) == v1_bytes
    assert canonical_bytes(v2) == v2_bytes


def test_v3_public_preparation_fails_closed_without_complete_v2_authority(tmp_path: Path) -> None:
    _, v3, _ = _authorities()
    with pytest.raises(ValueError, match="v2_bundle"):
        publish_binance_usdm_koru_directional_hybrid_bundle_v3(
            v2_market_reader=v3.reader,
            v3_execution_bundle=v3,
            publication_root=tmp_path,
        )

class _AuthorityMutationReader:
    def __init__(self, base, field: str) -> None:
        self._base = base
        self._field = field

    @property
    def bundle_ref(self):
        return self._base.bundle_ref

    @property
    def manifest(self):
        return self._base.manifest

    def open_cursor(self, stream_key: str, *, batch_size: int):
        return self._base.open_cursor(stream_key, batch_size=batch_size)

    def read_batch(self, cursor):
        events, next_cursor = self._base.read_batch(cursor)
        if cursor.stream_manifest.stream_key == "binance_usdm.tradifi.preparation_authority.koruusdt.v3":
            payload = dict(events[0].payload)
            ref_types = {
                "strategy_ref": "strategy_definition",
                "recipe_ref": "strategy_parameter_set",
            }
            payload[self._field] = (
                ArtifactRef(ref_types[self._field], 1, "sha256:" + "0" * 64).to_canonical_dict()
                if self._field in ref_types
                else "sha256:" + "0" * 64
            )
            events = (
                replace(
                    events[0],
                    payload=payload,
                    source_hash=canonical_sha256({
                        "type": events[0].event_type,
                        "payload": payload,
                    }),
                ),
            )
        return events, next_cursor


@pytest.mark.parametrize("field", ("compiler_result_digest", "scope_digest", "source_fragment_digest", "recipe_digest", "strategy_ref", "recipe_ref", "target_stream_digest"))
def test_v3_authority_rejects_each_sealed_binding_tamper(field: str, tmp_path: Path) -> None:
    v2, v3, _ = _authorities()
    rejected = verify_binance_usdm_tradifi_directional_preparation_authority_v3(
        market_reader=_AuthorityMutationReader(_hybrid(v2, v3, tmp_path), field)
    )
    assert isinstance(rejected, BinanceUsdmTradifiBarBacktestFailure)


class _TargetMutationReader:
    def __init__(self, base, stream_key: str) -> None:
        self._base = base
        self._stream_key = stream_key

    @property
    def bundle_ref(self):
        return self._base.bundle_ref

    @property
    def manifest(self):
        return self._base.manifest

    def open_cursor(self, stream_key: str, *, batch_size: int):
        return self._base.open_cursor(stream_key, batch_size=batch_size)

    def read_batch(self, cursor):
        events, next_cursor = self._base.read_batch(cursor)
        if cursor.stream_manifest.stream_key == self._stream_key:
            events = (replace(events[0], event_id="tampered-v3-target"), *events[1:])
        return events, next_cursor


def test_v3_authority_rejects_target_stream_tamper(tmp_path: Path) -> None:
    v2, v3, _ = _authorities()
    rejected = verify_binance_usdm_tradifi_directional_preparation_authority_v3(
        market_reader=_TargetMutationReader(_hybrid(v2, v3, tmp_path), v3.selected_stream.target_stream_key)
    )
    assert isinstance(rejected, BinanceUsdmTradifiBarBacktestFailure)


def test_v3_rejects_forged_internally_consistent_alternate_scope(tmp_path: Path) -> None:
    v2, v3, _ = _authorities()
    rejected = verify_binance_usdm_tradifi_directional_preparation_authority_v3(
        market_reader=_AuthorityMutationReader(_hybrid(v2, v3, tmp_path), "scope_digest")
    )
    assert isinstance(rejected, BinanceUsdmTradifiBarBacktestFailure)

def test_v3_strategy_authority_isolated_from_v2_targets_and_refs(tmp_path: Path) -> None:
    v2, v3, _, prepared = _prepare(tmp_path)
    authority = verify_binance_usdm_tradifi_directional_preparation_authority_v3(market_reader=_hybrid(v2, v3, tmp_path))
    assert not isinstance(authority, BinanceUsdmTradifiBarBacktestFailure)
    v2_payload = next(
        event.payload
        for event in v2.reader.streams["binance_usdm.tradifi.preparation_authority.v2"]
    )
    v2_strategy_ref = ArtifactRef(**{
        key: value for key, value in v2_payload["strategy_definition_ref"].items()
        if key != "type"
    })
    v2_parameter_ref = ArtifactRef(**{
        key: value for key, value in v2_payload["parameter_target_bindings"][0]["parameter_ref"].items()
        if key != "type"
    })
    assert authority.strategy_ref != v2_strategy_ref
    assert authority.parameter_ref != v2_parameter_ref
    assert prepared.execution_request.request.target_stream_digest == authority.target_stream_digest
    stream_keys = {stream.stream_key for stream in prepared.runtime._market_reader.manifest.streams}
    assert authority.target_stream_key in stream_keys
    assert not any(key.startswith("binance_usdm.tradifi.target.koruusdt.closed_market_range.") for key in stream_keys)


def test_v3_rejects_v1_v2_target_authority_and_stream_collision(tmp_path: Path) -> None:
    v2, _, _ = _authorities()
    _, colliding_v3, _ = _authorities(
        target_key="binance_usdm.tradifi.target.koruusdt.closed_market_range.p01.v2"
    )
    with pytest.raises(ValueError, match="target_stream_collision"):
        publish_binance_usdm_koru_directional_hybrid_bundle_v3(
            v2_market_reader=v2.reader,
            v3_execution_bundle=colliding_v3,
            publication_root=tmp_path,
        )

def test_v3_public_imports_are_stable() -> None:
    from crypto_quant_backtest import KoruDirectionalV3StrategyAuthority
    from crypto_quant_bundle_builder import BinanceUsdmKoruDirectionalExecutionBundleV3

    assert KoruDirectionalV3StrategyAuthority.__name__ == "KoruDirectionalV3StrategyAuthority"
    assert BinanceUsdmKoruDirectionalExecutionBundleV3.__name__.endswith("V3")
