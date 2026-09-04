from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "packages/backtest-runtime/src/crypto_quant_backtest"
TRADING = ROOT / "packages/trading-kernel/src/crypto_quant_trading"
COMPOSITION = RUNTIME / "cn_a_share_profile.py"
PUBLIC_INIT = RUNTIME / "__init__.py"
TRADING_INIT = TRADING / "__init__.py"
_PUBLIC_NAMES = {
    "CnAShareInstrumentScopeDeclaration",
    "CnAShareAccountScopeDeclaration",
    "CnAShareAnnouncementRevisionSetDeclaration",
    "CnAShareRegisterRevisionSetDeclaration",
    "CnAShareIdentityHistoryDeclaration",
    "CnAShareProfileCompositionRequest",
    "CnAShareMarketSemanticsProfile",
    "CnAShareSimulationProfile",
    "CnAShareExecutionAccountProfile",
    "CnAShareResolvedProfile",
    "CnAShareProfileCompositionFailureCode",
    "CnAShareProfileCompositionFailure",
    "CnAShareProfileCompositionOutcome",
    "CnAShareProfileComposer",
}


def _imports(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    values: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            values.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            values.append(("." * node.level) + (node.module or ""))
    return tuple(values)


def test_g08h_production_composition_is_one_offline_isolated_module() -> None:
    assert COMPOSITION.is_file(), "intentional RED: G08H production module is absent"
    assert not (RUNTIME / "cn_a_share_profile").exists()
    source = COMPOSITION.read_text(encoding="utf-8")
    imports = _imports(COMPOSITION)
    for forbidden in (
        "MarketBundleReader",
        "DeterministicBarEngine",
        "AuditableBacktestRunner",
        "tests.support",
        "deployment_authorized=True",
        "profile_qualified=True",
        "decision_grade_eligible=True",
    ):
        assert forbidden not in source
    assert not any(
        value.lstrip(".").split(".", 1)[0]
        in {"requests", "urllib", "socket", "subprocess"}
        for value in imports
    )
    assert not any(value.endswith(".engine") or value.endswith(".runner") for value in imports)
    assert "class FinancialEventDispatcher" not in source
    assert "class BacktestProfileRegistry" not in source


def test_g08h_public_exports_are_exact_and_do_not_leak_from_trading_root() -> None:
    runtime_tree = ast.parse(PUBLIC_INIT.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(runtime_tree):
        if isinstance(node, ast.ImportFrom) and node.module == "cn_a_share_profile":
            imported.update(alias.name for alias in node.names)
    assert imported == _PUBLIC_NAMES
    trading_text = TRADING_INIT.read_text(encoding="utf-8")
    for name in _PUBLIC_NAMES:
        assert name not in trading_text


def test_generic_runtime_remains_cn_a_share_branchless() -> None:
    for path in (
        RUNTIME / "engine.py",
        RUNTIME / "runner.py",
        RUNTIME / "timeline.py",
        RUNTIME / "composition.py",
        RUNTIME / "financial_dispatch.py",
        TRADING / "journal.py",
        TRADING / "ledger.py",
    ):
        source = path.read_text(encoding="utf-8")
        assert "CnAShare" not in source
        assert "cn_a_share" not in source
