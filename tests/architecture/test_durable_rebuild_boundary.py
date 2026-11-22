from __future__ import annotations

import crypto_quant_backtest


def test_durable_rebuild_v2_adds_only_frozen_public_roots() -> None:
    for name in (
        "BacktestCanonicalPublicationRefV2",
        "AnalysisArtifactRefV2",
        "BacktestAnalysisV2",
        "VerifiedBacktestAnalysisV2",
        "VerifiedCompletedPublicationV3",
    ):
        assert hasattr(crypto_quant_backtest, name)
        assert name in crypto_quant_backtest.__all__
    for private in (
        "CanonicalAttemptRefV2",
        "IntegrityEvaluationContextV2",
        "IntegrityReportV2",
        "CompletedBacktestResultV3",
        "IntegrityEvaluationRecordV2",
        "CanonicalPublicationManifestV2",
        "DurableRebuildVerifierV1",
    ):
        assert not hasattr(crypto_quant_backtest, private)
        assert private not in crypto_quant_backtest.__all__


def test_only_approved_referenced_delivery_extends_the_public_runtime() -> None:
    assert {
        name
        for name, value in vars(crypto_quant_backtest.BacktestRuntime).items()
        if callable(value) and not name.startswith("_")
    } == {"run", "run_with_cancellation", "resume_delivery"}
    assert not any("recover" in name.lower() for name in crypto_quant_backtest.__all__)


def test_durable_source_codec_stays_pure_private_and_finite():
    import ast
    from pathlib import Path
    from crypto_quant_backtest import _durable_artifact_codec as codec
    source = Path(codec.__file__).read_text()
    tree = ast.parse(source)
    imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert not imports & {"evidence_repository", "facade", "_durable_rebuild", "pickle", "importlib", "os", "pathlib"}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            assert node.func.id not in {"open", "eval", "exec", "getattr", "__import__"}
        if isinstance(node.func, ast.Attribute):
            assert node.func.attr not in {"run", "derive", "put", "append", "build_financial_dispatcher", "__new__"}
            if node.func.attr == "read":
                assert ast.unparse(node.func.value) == "inputs._EXECUTION_INPUT_CATALOG"
    for name in ("_DurableDecodeContext", "decode_durable_artifact_source", "_MarketProfileEvidenceHeader",
                 "_SimulationProfileEvidenceHeader", "_AccountProfileEvidenceHeader"):
        assert name not in crypto_quant_backtest.__all__
        assert not hasattr(crypto_quant_backtest, name)
