from __future__ import annotations

import ast
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
DERIVATIVE_MODULES = (
    ROOT / "packages/trading-kernel/src/crypto_quant_trading/derivatives.py",
    ROOT / "packages/trading-kernel/src/crypto_quant_trading/derivative_accounting.py",
    ROOT / "packages/trading-kernel/src/crypto_quant_trading/funding.py",
    ROOT / "packages/trading-kernel/src/crypto_quant_trading/funding_accounting.py",
    ROOT / "packages/trading-kernel/src/crypto_quant_trading/margin.py",
    ROOT / "packages/trading-kernel/src/crypto_quant_trading/account_margin.py",
)
GENERIC_MODULES = (
    ROOT / "packages/trading-kernel/src/crypto_quant_trading/ledger.py",
    ROOT / "packages/trading-kernel/src/crypto_quant_trading/snapshots.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/engine.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/runner.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/timeline.py",
)
ACCOUNT_MARGIN_GENERIC_MODULES = GENERIC_MODULES + (
    ROOT / "packages/trading-kernel/src/crypto_quant_trading/pretrade_risk.py",
    ROOT / "packages/trading-kernel/src/crypto_quant_trading/reservations.py",
)
ACCOUNT_MARGIN_PREFIXES = (
    "LinearAccountMargin",
    "LinearPositionValuation",
    "LinearPositionUnrealized",
    "ExactLinearUnrealized",
)

DERIVATIVE_SYMBOL_PREFIXES = (
    "LinearPerpetual",
    "LinearPosition",
    "ExactAverageEntryBasis",
    "ExactLinearRealizedPnl",
    "LinearDerivative",
    "LinearFunding",
    "LinearInstrumentMargin",
    "LinearMargin",
    "ExactLinearMargin",
    "LinearAccountMargin",
    "LinearPositionValuation",
    "LinearPositionUnrealized",
    "ExactLinearUnrealized",
    "FundingSlotId",
    "Funding",
)
DERIVATIVE_LITERALS = (
    "linear_perpetual",
    "linearperpetual",
    "linear_position",
    "linearposition",
    "exact_average_entry_basis",
    "exactaverageentrybasis",
    "linear_derivative",
    "linearderivative",
    "exact_linear_realized_pnl",
    "exactlinearrealizedpnl",
    "linear_funding",
    "linearfunding",
    "funding_eligibility",
    "fundingslotid",
    "funding_slot_id",
    "funding_applied",
    "fundingapplied",
    "linear_margin",
    "linearmargin",
    "margin_requirement",
    "marginrequirement",
    "account_margin",
    "accountmargin",
    "funding",
    "__import__",
)


def _constant_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _constant_string(node.left)
        right = _constant_string(node.right)
        if left is not None and right is not None:
            return left + right
    if isinstance(node, ast.JoinedStr):
        values = [_constant_string(value) for value in node.values]
        if all(value is not None for value in values):
            return "".join(value for value in values if value is not None)
    return None


def _has_derivative_literal(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in DERIVATIVE_LITERALS)


def _generic_derivative_violations(source: str) -> set[str]:
    tree = ast.parse(source)
    violations: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if any(
                marker in module
                for marker in (
                    "derivatives",
                    "derivative_accounting",
                    "funding",
                    "margin",
                )
            ):
                violations.add(f"import:{node.module}")
            for alias in node.names:
                if alias.name == "*" and node.module == "crypto_quant_trading":
                    violations.add("import:crypto_quant_trading.*")
                if alias.name.startswith(DERIVATIVE_SYMBOL_PREFIXES):
                    violations.add(f"symbol:{alias.name}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if any(
                    marker in alias.name
                    for marker in (
                        "derivatives",
                        "derivative_accounting",
                        "funding",
                        "margin",
                    )
                ):
                    violations.add(f"import:{alias.name}")
        elif isinstance(node, ast.Name) and (
            node.id.startswith(DERIVATIVE_SYMBOL_PREFIXES)
            or "funding" in node.id.lower()
        ):
            violations.add(f"name:{node.id}")
        elif isinstance(node, ast.Name) and node.id == "__import__":
            violations.add("dynamic:__import__")
        elif isinstance(node, ast.Attribute) and (
            node.attr in {"LINEAR_PERPETUAL", "FUNDING_APPLIED"}
            or node.attr.startswith(DERIVATIVE_SYMBOL_PREFIXES)
            or "funding" in node.attr.lower()
        ):
            violations.add(f"attribute:{node.attr}")
        else:
            literal = _constant_string(node)
            if literal is not None and _has_derivative_literal(literal):
                violations.add(f"literal:{literal}")
    return violations


def _generic_account_margin_violations(source: str) -> set[str]:
    tree = ast.parse(source)
    violations: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and "account_margin" in (node.module or ""):
            violations.add(f"import:{node.module}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if "account_margin" in alias.name:
                    violations.add(f"import:{alias.name}")
        elif isinstance(node, ast.Name) and node.id.startswith(ACCOUNT_MARGIN_PREFIXES):
            violations.add(f"name:{node.id}")
        elif isinstance(node, ast.Attribute) and node.attr.startswith(
            ACCOUNT_MARGIN_PREFIXES
        ):
            violations.add(f"attribute:{node.attr}")
        else:
            literal = _constant_string(node)
            if literal is not None and any(
                marker in literal.lower()
                for marker in ("account_margin", "accountmargin")
            ):
                violations.add(f"literal:{literal}")
    return violations


def _module_suite(statements: list[ast.stmt]) -> list[ast.stmt]:
    values: list[ast.stmt] = []
    for statement in statements:
        values.append(statement)
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        nested_suites: list[list[ast.stmt]] = []
        for name in ("body", "orelse", "finalbody"):
            nested = getattr(statement, name, None)
            if isinstance(nested, list):
                nested_suites.append(nested)
        nested_suites.extend(
            handler.body for handler in getattr(statement, "handlers", ())
        )
        nested_suites.extend(case.body for case in getattr(statement, "cases", ()))
        for nested in nested_suites:
            values.extend(_module_suite(nested))
    return values


def _purity_violations(source: str) -> set[str]:
    tree = ast.parse(source)
    violations: set[str] = set()
    allowed_imports = {
        "__future__",
        "dataclasses",
        "enum",
        "math",
        "typing",
        "re",
        "unicodedata",
        "crypto_quant_domain",
        "derivative_accounting",
        "derivatives",
        "funding",
        "journal",
        "ledger",
        "margin",
        "marks",
        "ports",
        "reservations",
    }
    mutable_values = (
        ast.Dict,
        ast.DictComp,
        ast.List,
        ast.ListComp,
        ast.Set,
        ast.SetComp,
    )
    mutable_constructors = {"bytearray", "defaultdict", "dict", "list", "set"}
    immutable_module_constructors = {"SourceSequence", "TimelinePhase", "dataclass"}
    mutating_methods = {
        "add",
        "append",
        "clear",
        "discard",
        "extend",
        "insert",
        "pop",
        "remove",
        "setdefault",
        "sort",
        "update",
    }
    side_effect_calls = {
        "bind",
        "connect",
        "create_connection",
        "execute",
        "popen",
        "run",
        "send",
        "sendto",
        "system",
        "unlink",
        "urlopen",
        "write",
        "writelines",
    }

    def call_name(call: ast.Call) -> str:
        if isinstance(call.func, ast.Name):
            return call.func.id
        if isinstance(call.func, ast.Attribute):
            return call.func.attr
        return ""

    def mutable_expression(value: ast.AST | None) -> bool:
        if value is None:
            return False
        return any(
            isinstance(node, mutable_values)
            or (
                isinstance(node, ast.Call)
                and call_name(node) in mutable_constructors
            )
            or (
                isinstance(node, ast.Call)
                and call_name(node) not in immutable_module_constructors
            )
            for node in ast.walk(value)
        )

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if (node.module or "") not in allowed_imports:
                violations.add(f"import:{node.module}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name not in allowed_imports:
                    violations.add(f"import:{alias.name}")
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            violations.add(f"scope:{type(node).__name__}")
        elif isinstance(node, ast.Name) and node.id in {
            "Decimal",
            "Path",
            "__builtins__",
            "float",
            "open",
        }:
            violations.add(f"name:{node.id}")
        elif isinstance(node, ast.Call):
            name = call_name(node)
            if name in {"__import__", "compile", "eval", "exec", "open"}:
                violations.add(f"dynamic:{name}")
            if name in side_effect_calls:
                violations.add(f"side_effect:{name}")

    for node in _module_suite(tree.body):
        value: ast.AST | None = None
        targets: tuple[ast.expr, ...] = ()
        expressions: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            value = node.value
            targets = tuple(node.targets)
        elif isinstance(node, ast.AnnAssign):
            value = node.value
            targets = (node.target,)
        elif isinstance(node, ast.AugAssign):
            targets = (node.target,)
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            if call_name(node.value) in mutating_methods:
                violations.add(f"module_mutation:{call_name(node.value)}")
        if isinstance(node, (ast.If, ast.While)):
            expressions.append(node.test)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            expressions.extend(node.decorator_list)
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            expressions.extend(item.context_expr for item in node.items)
        if mutable_expression(value) or any(
            mutable_expression(expression) for expression in expressions
        ):
            violations.add("module_state:mutable_expression")
        if any(isinstance(target, (ast.Attribute, ast.Subscript)) for target in targets):
            violations.add("module_mutation:assignment")
        for expression in expressions:
            if any(
                isinstance(nested, ast.Call)
                and call_name(nested) in mutating_methods
                for nested in ast.walk(expression)
            ):
                violations.add("module_mutation:expression")
    return violations


def test_generic_financial_and_runtime_modules_do_not_reference_derivatives() -> None:
    for path in GENERIC_MODULES:
        assert not _generic_derivative_violations(
            path.read_text(encoding="utf-8")
        ), path.relative_to(ROOT)


def test_generic_modules_do_not_reference_account_margin_projection() -> None:
    for path in ACCOUNT_MARGIN_GENERIC_MODULES:
        assert not _generic_account_margin_violations(
            path.read_text(encoding="utf-8")
        ), path.relative_to(ROOT)


@pytest.mark.parametrize(
    "source",
    (
        "from crypto_quant_trading import *",
        "from crypto_quant_trading import LinearPositionState",
        "from crypto_quant_trading import LinearPositionState as LPS",
        "import crypto_quant_trading.derivatives as derivatives",
        "if isinstance(value, LinearPositionState):\n    pass",
        "VALUE = 'linear_perpetual'",
        "VALUE = getattr(module, 'Exact' + 'AverageEntryBasis')",
        "VALUE = module.__dict__['Linear' + 'PositionState']",
        "VALUE = 'funding_applied'",
        "VALUE = getattr(module, 'Funding' + 'SlotId')",
        "VALUE = __import__('crypto_quant_trading.funding')",
        "loader = getattr(__builtins__, '__im' + 'port__')\nVALUE = loader('safe_name')",
        "funding_state = object()",
    ),
)
def test_generic_derivative_scanner_rejects_import_and_reference_bypasses(
    source: str,
) -> None:
    assert _generic_derivative_violations(source)


def test_derivative_modules_are_pure_and_have_no_mutable_module_state() -> None:
    for path in DERIVATIVE_MODULES:
        assert not _purity_violations(path.read_text(encoding="utf-8")), path.name


@pytest.mark.parametrize(
    "source",
    (
        "CACHE = bytearray()",
        "CACHE = dict()",
        "CACHE = CustomMutableSingleton()",
        "if True:\n    CACHE = []",
        "class Cache:\n    values = set()",
        "CACHE = []\n@CACHE.append(1)\ndef decorated():\n    pass",
        "def load():\n    return __import__('os')",
        "def write():\n    return __builtins__['open']('x', 'w').write('x')",
        "import os\nos.system('true')",
        "from pathlib import Path",
        "STATE = {}\nSTATE['x'] = 1",
        "STATE = []\nSTATE.append(1)",
        "STATE = 0\ndef change():\n    global STATE",
    ),
)
def test_derivative_purity_scanner_rejects_state_and_side_effect_bypasses(
    source: str,
) -> None:
    assert _purity_violations(source)
