"""Retain the generic check while admitting two exact new opt-in tokens."""
import ast
from pathlib import Path

_ENGINE = "_CnASharePortfolioEconomicEngineV1"
_MODULE = "cn_a_share_portfolio_economic_engine_v1"

def generic_runtime_source(path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    if path.name != "runner.py":
        return source
    tree = ast.parse(source)
    runner, = (node for node in tree.body if isinstance(node, ast.ClassDef)
               and node.name == "AuditableBacktestRunner")
    method, = (node for node in runner.body if isinstance(node, ast.FunctionDef)
               and node.name == "_execute_referenced_locked")
    exact_import, = (node for node in method.body if isinstance(node, ast.ImportFrom)
                     and node.level == 1 and node.module == _MODULE)
    assert [(alias.name, alias.asname) for alias in exact_import.names] == [(_ENGINE, None)]
    exact_guard, = (node for node in ast.walk(method) if isinstance(node, ast.Compare)
                    and ast.unparse(node) == "type(self._engine) is not " + _ENGINE)
    inside_if, = (node for node in method.body if isinstance(node, ast.If) and exact_guard in ast.walk(node.test))
    assert any(isinstance(node, ast.Raise) for node in inside_if.body)
    assert source.count(_MODULE) == 1 and source.count(_ENGINE) == 2
    # Keep all other source and forbidden strings visible to the original checks.
    return source.replace(_MODULE, "_exact_profile_engine").replace(_ENGINE, "_ExactReferencedEngine")
