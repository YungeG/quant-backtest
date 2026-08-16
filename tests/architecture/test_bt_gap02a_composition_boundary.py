from __future__ import annotations

import ast
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[2]
_RUNTIME = _ROOT / "packages/backtest-runtime/src/crypto_quant_backtest"
_COMPOSITION = _RUNTIME / "composition.py"
_PUBLIC_INIT = _RUNTIME / "__init__.py"
_PROFILE_MODULES = (
    _RUNTIME / "cn_a_share_profile.py",
    _RUNTIME / "binance_usdm_profile.py",
)
_GENERIC_MODULES = (
    _RUNTIME / "composition.py",
    _RUNTIME / "engine.py",
    _RUNTIME / "execution_inputs.py",
    _RUNTIME / "resolution.py",
    _RUNTIME / "runner.py",
)
_FORBIDDEN_PROFILE_IMPORT_ROOTS = {
    "crypto_quant_foundation",
    "crypto_quant_promotion",
    "crypto_quant_research",
    "crypto_quant_validation",
    "httpx",
    "_publication",
    "publication_refs",
    "requests",
    "runner",
    "socket",
    "subprocess",
    "tests",
    "urllib",
}
_FORBIDDEN_NEW_PUBLIC_SUFFIXES = (
    "Builder",
    "Dispatcher",
    "Factory",
    "Plugin",
    "Protocol",
    "Registry",
    "Resolver",
)


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _class(tree: ast.Module, name: str) -> ast.ClassDef:
    return next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == name
    )


def test_no_public_surface_or_second_selector_is_added() -> None:
    composition_tree = _tree(_COMPOSITION)
    public_definitions = {
        node.name
        for node in composition_tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    }
    assert public_definitions == {"ExecutionCaseComposer"}
    assert not any(
        name.endswith(_FORBIDDEN_NEW_PUBLIC_SUFFIXES)
        for name in public_definitions
    )

    public_source = _PUBLIC_INIT.read_text(encoding="utf-8")
    for private_name in (
        "_compose_execution_case",
        "_build_execution_case",
        "HydratedExecutionInputs",
        "ProductionExecutionCaseBuilder",
    ):
        assert private_name not in public_source

    generic_source = "\n".join(path.read_text(encoding="utf-8") for path in _GENERIC_MODULES)
    for concrete_name in ("CnAShare", "BinanceUsdm"):
        assert concrete_name not in generic_source
    for concrete_module in ("cn_a_share_profile", "binance_usdm_profile"):
        assert concrete_module not in generic_source


def test_private_entry_delegates_directly_to_the_already_selected_implementation() -> None:
    tree = _tree(_COMPOSITION)
    entry = next(
        (
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "_compose_execution_case"
        ),
        None,
    )
    assert entry is not None, "BT-GAP-02A RED: private composition entry is absent"
    source = ast.unparse(entry)
    assert (
        "resolved_request.environment.simulation.implementation._build_execution_case"
        in source
    )
    assert "BacktestProfileRegistry" not in source
    assert ".market_semantics(" not in source
    assert ".simulation(" not in source
    assert ".execution_account(" not in source
    assert "fallback" not in source.lower()


def test_only_both_frozen_simulation_implementations_gain_private_ownership() -> None:
    expected = {
        "cn_a_share_profile.py": "CnAShareSimulationProfile",
        "binance_usdm_profile.py": "BinanceUsdmSimulationProfile",
    }
    for path in _PROFILE_MODULES:
        tree = _tree(path)
        owner = _class(tree, expected[path.name])
        owner_methods = {
            node.name
            for node in owner.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        assert "_build_execution_case" in owner_methods, (
            f"BT-GAP-02A RED: {expected[path.name]} lacks private construction"
        )
        for node in tree.body:
            if not isinstance(node, ast.ClassDef) or node is owner:
                continue
            methods = {
                child.name
                for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
            assert "_build_execution_case" not in methods
            assert not (
                not node.name.startswith("_")
                and node.name.endswith(_FORBIDDEN_NEW_PUBLIC_SUFFIXES)
            )


def test_narrow_profile_purity_supersession_still_forbids_io_runner_and_publication() -> None:
    for path in _PROFILE_MODULES:
        tree = _tree(path)
        source = path.read_text(encoding="utf-8")
        imported_roots: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_roots.add(node.module.split(".")[0])
        assert imported_roots.isdisjoint(_FORBIDDEN_PROFILE_IMPORT_ROOTS)
        assert "AuditableBacktestRunner" not in source
        assert "DeterministicBarEngine" not in source
        assert "tests.support" not in source
