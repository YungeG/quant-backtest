from __future__ import annotations

import subprocess
from pathlib import Path

import crypto_quant_backtest as backtest

ROOT = Path(__file__).resolve().parents[2]
ACCEPTED_ANCESTORS = {
    "platform_v2_model": "033344172b24847e73941bb97a06da0490527edf",
    "durable_proof_v3": "cebb9b033b7eeffbbff712715fc017708ac5a247",
}
REQUIRED_PUBLIC_SYMBOLS = (
    "AnalysisArtifactRefV2",
    "BacktestCanonicalPublicationRefV2",
    "VerifiedCompletedPublicationV3",
    "prepare_model_bound_cash_development_backtest",
)


def test_platform_v5_fanin_descends_from_every_accepted_capability() -> None:
    for capability, revision in ACCEPTED_ANCESTORS.items():
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", revision, "HEAD"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"missing accepted capability: {capability}"


def test_platform_v5_public_capabilities_coexist_and_model_tests_are_retained() -> None:
    assert all(name in backtest.__all__ for name in REQUIRED_PUBLIC_SYMBOLS)
    assert all(getattr(backtest, name, None) is not None for name in REQUIRED_PUBLIC_SYMBOLS)
    assert (
        ROOT / "tests/runtime/providers/test_model_bound_cash_development_provider.py"
    ).is_file()
    assert not (ROOT / ".gitleaksignore").exists()
