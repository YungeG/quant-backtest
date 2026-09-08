from __future__ import annotations

import ast
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PARITY = ROOT / "tools/parity/precomputed_strategy.py"
RUNNER = ROOT / "tools/parity/run_precomputed_strategy_parity.py"
SUPPORT = ROOT / "tests/parity/_precomputed_strategy_fixtures.py"
GOLDEN = ROOT / "tests/parity/test_precomputed_strategy_parity_golden.py"
CONTRACT = ROOT / "tests/parity/contracts/precomputed-strategy-g11j-v1.json"
GENERIC_RUNTIME = (
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/engine.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/runner.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/timeline.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/target_stream.py",
)
PRODUCTION = (
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest",
    ROOT / "packages/trading-kernel/src/crypto_quant_trading",
)
PUBLIC_APIS = tuple(directory / "__init__.py" for directory in PRODUCTION)
FROZEN_RULES = (
    ("/fixture_id", "exact"),
    ("/layers/00_NORMALIZED_ENTRY", "exact"),
    ("/layers/01_DECISION_BATCH", "sequence"),
    ("/layers/02_ALLOCATION", "sequence"),
    ("/layers/03_PORTFOLIO_RISK", "sequence"),
    ("/layers/04_NORMALIZED_ACTIVE_TARGET", "sequence"),
    ("/layers/05_ORDER_PLAN_INTENT", "sequence"),
    ("/layers/06_ORDER_EVENT", "sequence"),
    ("/layers/07_FILL", "sequence"),
    ("/layers/08_SLIPPAGE", "sequence"),
    ("/layers/09_FEE", "sequence"),
    ("/layers/10_FINANCIAL_ARTIFACT", "sequence"),
    ("/layers/11_JOURNAL", "sequence"),
    ("/layers/12_LEDGER", "exact"),
    ("/layers/13_FINAL_SNAPSHOT", "exact"),
    ("/layers/14_RUN_END", "exact"),
    ("/layers/15_TRACE", "exact"),
    ("/layers/16_EXECUTION_RESULT_HASH", "exact"),
    ("/qualification", "exact"),
    ("/schema_version", "exact"),
)
ALLOWED_TOOL_IMPORTS = {
    "__future__",
    "argparse",
    "json",
    "legacy_migration.parity",
    "pathlib",
    "precomputed_strategy",
    "sys",
}
ALLOWED_SUPPORT_IMPORTS = {
    "__future__",
    "crypto_quant_backtest",
    "crypto_quant_domain",
    "crypto_quant_trading",
    "dataclasses",
    "json",
    "pathlib",
    "tests.runtime.engine._fixtures",
    "tests.runtime.execution_hash._fixtures",
    "tests.runtime.integrity._fixtures",
    "tests.runtime.runner._fixtures",
    "typing",
}


def _tree(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"))


def _imports(path: Path) -> set[str]:
    tree = _tree(path)
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


def _imported_names(path: Path, module: str) -> set[str]:
    return {
        alias.name
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.ImportFrom) and node.module == module
        for alias in node.names
    }


def _call_count(path: Path, name: str) -> int:
    return sum(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == name
        for node in ast.walk(_tree(path))
    )


def test_g11j_contract_is_exact_complete_and_ordered() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    rules = contract["rules"]
    frozen_rules = tuple((rule["path"], rule["comparison"]) for rule in rules)
    paths = [path for path, _ in frozen_rules]
    layer_paths = [path for path in paths if path.startswith("/layers/")]

    assert contract == {
        "id": "precomputed-strategy-g11j-v1",
        "rules": [
            {"comparison": comparison, "path": path}
            for path, comparison in FROZEN_RULES
        ],
        "schema_version": 1,
    }
    assert frozen_rules == FROZEN_RULES
    assert paths == sorted(paths)
    assert len(layer_paths) == 17
    layer_numbers = []
    for path in layer_paths:
        match = re.fullmatch(r"/layers/(\d{2})_[A-Z_]+", path)
        assert match is not None
        layer_numbers.append(int(match.group(1)))
    assert layer_numbers == list(range(17))
    source = CONTRACT.read_text(encoding="utf-8")
    for forbidden in (
        "approved_change",
        "explicit_tolerance",
        "quantized",
        "epsilon",
        "ignore",
        "not_comparable",
    ):
        assert forbidden not in source.lower()


def test_g11j_tool_reuses_only_stdlib_and_existing_comparator() -> None:
    assert PARITY.is_file()
    assert RUNNER.is_file()
    assert SUPPORT.is_file()
    assert _imports(PARITY) <= ALLOWED_TOOL_IMPORTS
    assert _imports(RUNNER) <= ALLOWED_TOOL_IMPORTS
    assert _imports(SUPPORT) <= ALLOWED_SUPPORT_IMPORTS
    assert _imported_names(PARITY, "legacy_migration.parity") == {
        "ComparatorError",
        "invalid_report",
        "load_contract",
        "run_comparison",
    }
    assert _call_count(PARITY, "load_contract") == 1
    assert _call_count(PARITY, "run_comparison") == 1
    assert _call_count(PARITY, "invalid_report") == 1
    source = PARITY.read_text(encoding="utf-8") + RUNNER.read_text(
        encoding="utf-8"
    )
    for forbidden in (
        "crypto_quant_backtest",
        "crypto_quant_domain",
        "crypto_quant_trading",
        "compare_rule",
        "exact_equal",
        "validate_classification",
        "approved_change",
        "explicit_tolerance",
        "quantized",
        "epsilon",
    ):
        assert forbidden not in source
    assert not list((ROOT / "tools/parity").glob("g11j*.py"))


def test_g11j_fixture_and_golden_are_repository_root_independent() -> None:
    source = PARITY.read_text(encoding="utf-8") + RUNNER.read_text(
        encoding="utf-8"
    )
    golden_source = GOLDEN.read_text(encoding="utf-8")

    assert "tests/parity/fixtures" not in source
    assert "fixtures/precomputed-strategy-g11j-v1" not in source
    assert 'parser.add_argument("--root", required=True, type=Path)' in source
    assert "shutil.copytree(FIXTURES, root)" in golden_source
    assert "report.read_bytes() == EXPECTED_REPORT.read_bytes()" in golden_source


def test_production_runtime_remains_branchless_and_has_no_public_export() -> None:
    engine_source = GENERIC_RUNTIME[0].read_text(encoding="utf-8")
    assert engine_source.count("PrecomputedTargetStreamAdapter().inject(") == 1
    for path in GENERIC_RUNTIME:
        source = path.read_text(encoding="utf-8")
        assert "invoke_portfolio_strategies" not in source
        assert "precomputed_strategy" not in source
        assert "dual_entry" not in source
        assert "G11J" not in source

    for directory in PRODUCTION:
        assert not list(directory.rglob("*g11j*"))
        assert not list(directory.rglob("precomputed_strategy.py"))
        for path in directory.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            for forbidden in (
                "G11JParityError",
                "run_precomputed_strategy_parity",
                "precomputed-vs-strategy-g11j",
            ):
                assert forbidden not in source

    for path in PUBLIC_APIS:
        source = path.read_text(encoding="utf-8")
        for forbidden in (
            "G11JParityError",
            "blocked_report",
            "precomputed_strategy",
            "run_parity",
            "safe_report_path",
        ):
            assert forbidden not in source


def test_g11j_is_passed_in_status_authority() -> None:
    matrix = (ROOT / "docs/implementation/acceptance-matrix.md").read_text(
        encoding="utf-8"
    )
    assert "| G11J | PASSED |" in matrix
