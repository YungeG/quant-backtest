from __future__ import annotations

import inspect

from crypto_quant_backtest import materialize_execution_input_bundle, materialize_execution_input_bundle_v2


def test_legacy_execution_input_materializers_remain_unchanged() -> None:
    assert str(inspect.signature(materialize_execution_input_bundle)) == "(*, request: 'BacktestRequest', build_artifact_manifest: 'BuildArtifactManifest', execution_case_semantic_spec: 'ExecutionCaseSemanticSpec', timeline_stream_keys: 'tuple[str, ...]', target_stream_key: 'str', timeline_batch_size: 'int', initial_financial_state_template: 'Mapping[str, Any]') -> 'ArtifactEnvelope'"
    assert str(inspect.signature(materialize_execution_input_bundle_v2)) == "(*, resolved_request: 'ResolvedBacktestRequest', execution_case: 'ResolvedExecutionCase') -> 'ArtifactEnvelope'"
