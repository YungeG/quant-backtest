from __future__ import annotations

from pathlib import Path

import pytest
from crypto_quant_backtest import (
    AnalysisArtifactRefV2,
    BacktestAnalysisRuntime,
    BacktestCanonicalPublicationRefV2,
    BacktestEvidenceError,
    BacktestEvidenceFailureCode,
    BacktestEvidenceRepository,
    BacktestRuntime,
    VerifiedBacktestAnalysisV2,
)

from tests.runtime.test_durable_rebuild_facade import (
    _journey_values,
    _local_reader,
    _seed_attempt_graph,
    _Store,
)


def test_analysis_v2_exact_dispatch_and_repository_load(tmp_path: Path) -> None:
    values = _journey_values()
    prepared, _, _, _, request, registry = values
    store = _Store()
    _seed_attempt_graph(store, tmp_path / "seed", values)
    publication_ref = BacktestRuntime(
        registry=registry,
        artifact_reader=store,
        artifact_publisher=store,
        market_reader=_local_reader(tmp_path / "market", prepared.verified_reader),
        publication_root=tmp_path / "publication",
    ).run(request)
    assert type(publication_ref) is BacktestCanonicalPublicationRefV2
    repository = BacktestEvidenceRepository(store)
    completed = repository.load_completed_v3(publication_ref)
    runtime = BacktestAnalysisRuntime(store)
    metric_ref = runtime.publish_metric_profile()
    analysis_ref = runtime.derive(completed, metric_ref)
    assert type(analysis_ref) is AnalysisArtifactRefV2
    loaded = repository.load_analysis_v2(analysis_ref)
    assert type(loaded) is VerifiedBacktestAnalysisV2
    assert loaded.source_publication_ref == publication_ref

    with pytest.raises(TypeError):
        runtime.derive(object(), metric_ref)
    with pytest.raises(BacktestEvidenceError) as error:
        repository.load_analysis(analysis_ref)
    assert error.value.code is BacktestEvidenceFailureCode.PORT_REF_TYPE_MISMATCH
