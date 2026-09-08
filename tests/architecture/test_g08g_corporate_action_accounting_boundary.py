from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "packages/trading-kernel/src/crypto_quant_trading/profiles/cn_a_share/corporate_action_accounting.py"
PROFILE_INIT = ROOT / "packages/trading-kernel/src/crypto_quant_trading/profiles/cn_a_share/__init__.py"
TOP_LEVEL_INIT = ROOT / "packages/trading-kernel/src/crypto_quant_trading/__init__.py"

PUBLIC_NAMES = (
    "CnAShareCorporateActionTaxDisposition",
    "CnAShareCorporateActionDeliveryStatus",
    "CnAShareCashPaymentEvidence",
    "CnAShareShareDeliveryEvidence",
    "CnAShareCashPaymentRequest",
    "CnAShareShareDeliveryRequest",
    "CnAShareCorporateActionTranslationFailureCode",
    "CnAShareCorporateActionTranslationFailure",
    "CnAShareCashPaymentOutcome",
    "CnAShareShareDeliveryOutcome",
    "translate_corporate_action_cash_payment",
    "translate_corporate_action_share_delivery",
)
VALUE_CLASS_NAMES = set(PUBLIC_NAMES[:-2])
FORBIDDEN_IMPORT_PREFIXES = (
    "asyncio", "builtins", "ctypes", "http", "importlib", "multiprocessing",
    "os", "pathlib", "requests", "socket", "sqlite3", "subprocess", "time", "urllib",
)
FORBIDDEN_NAMES = {
    "Protocol", "ProfilePortType", "ProfilePortOutcome", "Runtime", "Dispatcher",
    "Adapter", "Registry", "Service", "Settlement", "AvailabilityState",
}


def _tree() -> ast.Module:
    assert MODULE.is_file(), "G08G production module is absent"
    return ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))


def test_g08g_adds_one_pure_profile_module_without_forbidden_io_or_frameworks() -> None:
    tree = _tree()
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in {"open", "exec", "eval", "compile", "__import__"}
    assert not [name for name in imports if name.startswith(FORBIDDEN_IMPORT_PREFIXES)]
    referenced = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert not (referenced & FORBIDDEN_NAMES)


def test_g08g_declares_only_the_frozen_value_classes_and_two_public_translators() -> None:
    tree = _tree()
    classes = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
    public_functions = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_")
    }
    assert classes == VALUE_CLASS_NAMES
    assert public_functions == set(PUBLIC_NAMES[-2:])


def test_g08g_is_exported_from_profile_only_not_top_level_kernel() -> None:
    _tree()
    profile_text = PROFILE_INIT.read_text(encoding="utf-8")
    top_level_text = TOP_LEVEL_INIT.read_text(encoding="utf-8")
    for name in PUBLIC_NAMES:
        assert name in profile_text
        assert name not in top_level_text
    assert "from .corporate_action_accounting import" in profile_text
