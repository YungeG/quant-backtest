"""Both execution paths share one policy helper instead of shadowing its name."""
from __future__ import annotations

import ast
from pathlib import Path


def test_no_fill_action_has_one_shared_definition() -> None:
    root = Path(__file__).resolve().parents[3]
    path = root / "packages/backtest-runtime/src/crypto_quant_backtest/execution.py"
    tree = ast.parse(path.read_text())
    helpers = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_no_fill_action"
    ]
    assert len(helpers) == 1, "open/close policy helper must not shadow another definition"
    annotations = [argument.annotation for argument in helpers[0].args.args]
    names = [{node.id for node in ast.walk(value) if isinstance(node, ast.Name)} for value in annotations]
    assert names == [
        {"NextBarOpenRequest", "NextBarCloseRequest"},
        {"NextBarOpenApplicability", "NextBarCloseApplicability"},
    ]
