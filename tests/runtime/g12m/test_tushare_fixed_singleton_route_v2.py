from __future__ import annotations

import json
from dataclasses import fields, replace
from pathlib import Path

import pytest
from crypto_quant_backtest import BacktestRuntime
from crypto_quant_backtest.cn_a_share_fixed_singleton_no_trade_profile_v2 import (
    create_cn_a_share_fixed_singleton_no_trade_authority_v2,
)
from crypto_quant_backtest.g12m_tushare_fixed_singleton_route_v2 import (
    _G12MTushareFixedSingletonRouteResultV2,
    run_g12m_tushare_fixed_singleton_route_v2,
)
from crypto_quant_bundle_builder import (
    LocalMarketBundleRepository,
    LocalMarketBundleRepositoryConfig,
)
from crypto_quant_domain import canonical_bytes
from crypto_quant_market_data import LocalMarketBundleReader

from tests.bundle_builder.providers.tushare.test_g12m_tushare_fixed_singleton_execution_bundle_v2 import (
    _result as _bundle_result,
)
from tests.runtime.test_durable_rebuild_facade import _Store

ROOT = Path(__file__).parents[3]
FIXTURE = (
    ROOT
    / "tests/fixtures/runtime/g12m-tushare-fixed-singleton-production-run-v2/"
    "identity.expected.json"
)


def _reader(tmp_path: Path) -> LocalMarketBundleReader:
    bundle = _bundle_result()
    root = (tmp_path / "market").resolve()
    publication = LocalMarketBundleRepository(
        config=LocalMarketBundleRepositoryConfig(root=root)
    ).publish_market_bundle_v1(
        manifest=bundle.manifest,
        stream_payloads=bundle.stream_payloads,
        retention_policy_ref="g12m.tushare.fixed-singleton.execution-bundle-v2",
    )
    assert publication.failure is None
    return LocalMarketBundleReader.open(
        repository_root=root,
        bundle_ref=bundle.bundle_ref,
    )


def _install_exact_test_artifact_mirror(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = BacktestRuntime._finalize_v3_attempt_locked

    def finalize(self, writer, record, claim):
        finalized = original(self, writer, record, claim)
        ready = record.ready_to_finalize
        if ready is not None:
            store = self._artifact_publisher
            for artifact_type, artifact in (
                ("evidence_manifest", finalized.manifest),
                ("backtest_request", ready.resolved_request.request),
                (
                    "resolved_backtest_environment",
                    ready.resolved_request.environment,
                ),
                (
                    "build_artifact_manifest",
                    ready.resolved_request.build_artifact_manifest,
                ),
                (
                    "market_bundle_ref",
                    ready.resolved_request.environment.market_bundle_ref,
                ),
                (
                    "environment_compatibility_report",
                    ready.resolved_request.environment.compatibility_report,
                ),
                ("attempt_execution_record", record),
                ("engine_execution_result", ready.engine_result),
            ):
                store.put_exact(artifact_type, artifact)
        return finalized

    monkeypatch.setattr(BacktestRuntime, "_finalize_v3_attempt_locked", finalize)


def _identity(result: _G12MTushareFixedSingletonRouteResultV2) -> dict[str, object]:
    engine = result.completed_evidence.first_engine_result
    return {
        "type": "g12m_tushare_fixed_singleton_production_run_identity_v2",
        "schema_version": 2,
        "route_hash": result.route_hash,
        "authority_hash": result.authority_hash,
        "build_manifest_hash": result.build_manifest_hash,
        "profile_digests": result.profile_digests,
        "market_bundle_ref": result.market_bundle_ref,
        "market_bundle_content_hash": result.market_bundle_manifest.content_hash,
        "target_stream_digest": result.target_stream.target_stream_digest,
        "execution_input_ref": result.execution_request.execution_input_bundle_ref,
        "execution_input_source_hash": result.execution_input_source_hash,
        "publication_ref": result.publication_ref,
        "semantic_run_id": result.completed.semantic_run_id,
        "execution_result_hash": result.completed.source_execution_result_hash,
        "trace_hash": result.completed_evidence.trace_hash,
        "static_verification_hash": (
            result.completed_evidence.static_verification_hash
        ),
        "analysis_ref": result.analysis_ref,
        "metric_profile_ref": result.metric_profile_ref,
        "timeline_event_count": sum(
            entry.stage.value == "timeline_event" for entry in engine.trace.entries
        ),
        "order_count": sum(len(value.planned_orders) for value in engine.order_plans),
        "fill_count": len(engine.fills),
        "trade_count": result.analysis.trade_count,
        "result_grade": result.completed.result_grade.value,
    }


def test_exact_schema4_sole_facade_route_and_golden(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_exact_test_artifact_mirror(monkeypatch)
    order: list[str] = []
    authority_type = type(create_cn_a_share_fixed_singleton_no_trade_authority_v2())
    original_validate = authority_type.validate_target_stream

    def validate(self, target_stream):
        order.append("target")
        return original_validate(self, target_stream)

    monkeypatch.setattr(authority_type, "validate_target_stream", validate)
    import crypto_quant_backtest.g12m_tushare_fixed_singleton_route_v2 as route

    original_prepare = route.prepare_multi_resolution_market_data_v1  # pyright: ignore[reportPrivateImportUsage]

    def prepare(**kwargs):
        order.append("prep")
        return original_prepare(**kwargs)

    monkeypatch.setattr(route, "prepare_multi_resolution_market_data_v1", prepare)
    calls = 0
    original_run = BacktestRuntime.run

    def run(self, request):
        nonlocal calls
        calls += 1
        return original_run(self, request)

    monkeypatch.setattr(BacktestRuntime, "run", run)
    store = _Store()
    result = run_g12m_tushare_fixed_singleton_route_v2(
        market_reader=_reader(tmp_path),
        artifact_reader=store,
        artifact_publisher=store,
        publication_root=tmp_path / "publication",
    )

    assert type(result) is _G12MTushareFixedSingletonRouteResultV2
    assert calls == 1
    assert order[:2] == ["target", "prep"]
    assert result.execution_request.schema_version == 4
    assert json.loads(canonical_bytes(_identity(result))) == json.loads(
        FIXTURE.read_text(encoding="utf-8")
    )
    assert canonical_bytes(result) == canonical_bytes(result.to_canonical_dict())


def test_route_result_rejects_input_source_or_nested_identity_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_exact_test_artifact_mirror(monkeypatch)
    store = _Store()
    result = run_g12m_tushare_fixed_singleton_route_v2(
        market_reader=_reader(tmp_path),
        artifact_reader=store,
        artifact_publisher=store,
        publication_root=tmp_path / "publication",
    )
    with pytest.raises(ValueError, match="execution request mismatch"):
        replace(result, execution_input_source_hash="sha256:" + "0" * 64)

    class ResultSubclass(_G12MTushareFixedSingletonRouteResultV2):
        pass

    values = {field.name: getattr(result, field.name) for field in fields(result)}
    with pytest.raises(TypeError, match="exact G12M route result"):
        ResultSubclass(**values)


def test_route_rejects_reader_without_exact_retained_bundle(tmp_path: Path) -> None:
    store = _Store()
    with pytest.raises(ValueError, match="retained Local Reader Bundle"):
        run_g12m_tushare_fixed_singleton_route_v2(
            market_reader=object(),  # type: ignore[arg-type]
            artifact_reader=store,
            artifact_publisher=store,
            publication_root=tmp_path / "publication",
        )
