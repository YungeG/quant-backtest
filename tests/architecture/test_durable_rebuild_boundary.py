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


def test_no_new_public_facade_operation_or_runtime_recovery_api() -> None:
    assert {
        name
        for name, value in vars(crypto_quant_backtest.BacktestRuntime).items()
        if callable(value) and not name.startswith("_")
    } == {"run", "run_with_cancellation"}
    assert not any("recover" in name.lower() for name in crypto_quant_backtest.__all__)
