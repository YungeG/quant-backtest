from __future__ import annotations

import ast
import inspect
from pathlib import Path

from crypto_quant_backtest import DecisionSchedule, WarmupEligibility

from tests.runtime.decision_schedule._fixtures import bar_window, schedule


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/decision_schedule.py"
GENERIC_RUNTIME = (
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/engine.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/runner.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/timeline.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/target_stream.py",
)
ALLOWED_IMPORTS = {
    "__future__",
    "crypto_quant_domain",
    "dataclasses",
    "observation_windows",
    "observations",
    "timeline",
}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    imports.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    return imports


def test_decision_schedule_module_is_pure_and_uses_frozen_public_seams() -> None:
    assert MODULE.is_file()
    assert _imports(MODULE) <= ALLOWED_IMPORTS
    source = MODULE.read_text(encoding="utf-8")
    for forbidden in (
        "Callable",
        "Protocol",
        "MarketBundleReader",
        "DeterministicTimeline",
        "SessionModel",
        "TradingDate",
        "ZoneInfo",
        "cron",
        "pandas",
        "numpy",
        "pathlib",
        "socket",
        "subprocess",
        "requests",
        "urllib",
        "open(",
    ):
        assert forbidden not in source


def test_schedule_behavior_is_only_hash_serialization_and_eligibility() -> None:
    current = schedule()
    public = {name for name in dir(current) if not name.startswith("_")}

    assert public == {
        "eligibility",
        "entries",
        "key",
        "requirements",
        "schedule_hash",
        "to_canonical_dict",
        "version",
        "window",
    }
    assert list(inspect.signature(DecisionSchedule.eligibility).parameters) == [
        "self",
        "entry",
        "windows",
    ]
    assert type(
        current.eligibility(current.entries[0], (bar_window(),))
    ) is WarmupEligibility


def test_generic_runtime_and_target_stream_do_not_gain_g11e_branches() -> None:
    for path in GENERIC_RUNTIME:
        source = path.read_text(encoding="utf-8")
        assert "WarmupEligibility" not in source
        assert "LookbackRequirement" not in source
        assert "from .decision_schedule" not in source
