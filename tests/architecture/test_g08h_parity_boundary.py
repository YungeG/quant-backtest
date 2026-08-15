from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PARITY = ROOT / "tools/parity/cn_a_share.py"
RUNNER = ROOT / "tools/parity/run_cn_a_share_parity.py"
RUNTIME = ROOT / "packages/backtest-runtime/src/crypto_quant_backtest"


def _imports(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8")); values: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import): values.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom): values.append(("." * node.level) + (node.module or ""))
    return tuple(values)


def test_g08h_tool_is_isolated_to_stdlib_and_existing_parity_helpers() -> None:
    assert PARITY.is_file(), "intentional RED: G08H parity module is absent"
    assert RUNNER.is_file(), "intentional RED: G08H parity runner is absent"
    source = PARITY.read_text(encoding="utf-8") + RUNNER.read_text(encoding="utf-8")
    imports = _imports(PARITY) + _imports(RUNNER)
    for forbidden in ("crypto_quant_backtest", "crypto_quant_trading", "requests", "urllib", "socket", "subprocess", "provider_sdk", "AuditableBacktestRunner", "DeterministicBarEngine", "deployment_authorized=True"):
        assert forbidden not in source
    allowed_external = {"legacy_migration", "tools.migration.legacy_migration"}
    for value in imports:
        if value.startswith("."): continue
        root = value.split(".", 1)[0]
        assert root in {"argparse", "hashlib", "json", "pathlib", "sys", "tempfile", "typing", "legacy_migration", "tools"} or value in allowed_external


def test_generic_runtime_remains_g08h_parity_branchless() -> None:
    for path in (RUNTIME / "engine.py", RUNTIME / "runner.py", RUNTIME / "timeline.py", RUNTIME / "composition.py", RUNTIME / "financial_dispatch.py"):
        source = path.read_text(encoding="utf-8")
        assert "G08H" not in source
        assert "cn_a_share_parity" not in source
