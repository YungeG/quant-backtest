from __future__ import annotations

import ast
from pathlib import Path

from tests._referenced_architecture import generic_runtime_source

import pytest


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


def _assert_generic_branchless(source: str, *, allow_failure_metadata: bool = False) -> None:
    assert "CnAShare" not in source
    tree = ast.parse(source)
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    offsets = [0]
    for line in source.splitlines(keepends=True):
        offsets.append(offsets[-1] + len(line))
    permitted = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str) or "cn_a_share" not in node.value:
            continue
        assert allow_failure_metadata
        assert node.value == "cn_a_share_portfolio_economic_failure_context"
        ancestors = []
        parent = parents.get(node)
        while parent is not None:
            ancestors.append(parent)
            parent = parents.get(parent)
        assert next(n for n in ancestors if isinstance(n, ast.ClassDef)).name == "EngineFailure"
        assert next(n for n in ancestors if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))).name == "__post_init__"
        comparison = parents[node]
        assert isinstance(comparison, ast.Compare)
        assert len(comparison.ops) == 1 and isinstance(comparison.ops[0], ast.NotEq)
        assert comparison.comparators == [node]
        assert ast.unparse(comparison.left) in {"context.artifact_type", "payload['type']"}
        permitted.append((offsets[node.lineno - 1] + node.col_offset, offsets[node.end_lineno - 1] + node.end_col_offset))
    assert len(permitted) == (2 if allow_failure_metadata else 0)
    for start, end in sorted(permitted, reverse=True):
        source = source[:start] + '""' + source[end:]
    assert "cn_a_share" not in source


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
        source = generic_runtime_source(path)
        _assert_generic_branchless(source, allow_failure_metadata=path == RUNTIME / "engine.py")


@pytest.mark.parametrize("mutation", ("unexpected_literal", "wrong_class", "wrong_method", "profile_import"))
def test_generic_branchless_guard_rejects_unexpected_metadata_location_and_import(mutation: str) -> None:
    source = """class EngineFailure:
    def __post_init__(self):
        if context.artifact_type != "cn_a_share_portfolio_economic_failure_context":
            raise TypeError()
        if payload["type"] != "cn_a_share_portfolio_economic_failure_context":
            raise ValueError()
"""
    _assert_generic_branchless(source, allow_failure_metadata=True)
    if mutation == "unexpected_literal":
        source = source.replace("cn_a_share_portfolio_economic_failure_context", "cn_a_share_unapproved_context", 1)
    elif mutation == "wrong_class":
        source = source.replace("class EngineFailure", "class OtherFailure")
    elif mutation == "wrong_method":
        source = source.replace("def __post_init__", "def execute")
    else:
        source += "from crypto_quant_trading.profiles.cn_a_share import forbidden_profile\n"
    with pytest.raises(AssertionError):
        _assert_generic_branchless(source, allow_failure_metadata=True)
