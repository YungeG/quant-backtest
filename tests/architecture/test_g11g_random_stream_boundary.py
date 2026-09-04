from __future__ import annotations

import ast
import inspect
from pathlib import Path

from crypto_quant_backtest import NamedRandomStream

from tests.runtime.random_streams._fixtures import stream


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/random_streams.py"
GENERIC_RUNTIME = (
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/engine.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/runner.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/timeline.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/observations.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/strategy_state.py",
    ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/target_stream.py",
)
ALLOWED_IMPORTS = {
    "__future__",
    "crypto_quant_domain",
    "dataclasses",
    "hashlib",
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


def test_random_stream_module_uses_only_public_deterministic_contracts() -> None:
    assert MODULE.is_file()
    assert _imports(MODULE) <= ALLOWED_IMPORTS
    source = MODULE.read_text(encoding="utf-8")
    for forbidden in (
        "getrandbits",
        "urandom",
        "randint",
        "randrange",
        "numpy",
        "secrets",
        "uuid",
        "datetime",
        "pathlib",
        "socket",
        "subprocess",
        "requests",
        "urllib",
        "Callable",
        "Protocol",
    ):
        assert forbidden not in source


def test_named_stream_exposes_argument_free_immutable_draw_progression() -> None:
    current = stream()
    value, next_stream = current.draw_u64()

    assert type(current) is NamedRandomStream
    assert type(next_stream) is NamedRandomStream
    assert type(value) is int
    assert current.counter == 0
    assert next_stream.counter == 1
    assert list(inspect.signature(NamedRandomStream.draw_u64).parameters) == ["self"]


def test_generic_runtime_modules_do_not_gain_g11g_branches() -> None:
    for path in GENERIC_RUNTIME:
        assert "NamedRandomStream" not in path.read_text(encoding="utf-8")
