from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_RUNTIME = _ROOT / "packages/backtest-runtime/src/crypto_quant_backtest"
_COMPOSITION = _RUNTIME / "composition.py"
_EXECUTION_INPUTS = _RUNTIME / "execution_inputs.py"
_PUBLIC_INIT = _RUNTIME / "__init__.py"
_GENERIC_MODULES = (
    _RUNTIME / "composition.py",
    _RUNTIME / "engine.py",
    _RUNTIME / "execution_inputs.py",
    _RUNTIME / "resolution.py",
    _RUNTIME / "runner.py",
)


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_composition_adds_only_private_typed_runtime_closure() -> None:
    tree = _tree(_COMPOSITION)
    public_definitions = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    }
    assert public_definitions == {"ExecutionCaseComposer"}

    private_definitions = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert "_HydratedExecutionCaseInputs" in private_definitions, (
        "BT-GAP-02A RED: typed composition input is absent"
    )
    assert "_ExecutionCasePlan" in private_definitions, (
        "BT-GAP-02A RED: typed plan authority is not owned by composition"
    )
    assert "_compose_execution_case" in private_definitions, (
        "BT-GAP-02A RED: package-private composition entry is absent"
    )

    public_source = _PUBLIC_INIT.read_text(encoding="utf-8")
    for private_name in (
        "_HydratedExecutionCaseInputs",
        "_ExecutionCasePlan",
        "_compose_execution_case",
    ):
        assert private_name not in public_source


def test_execution_inputs_remains_the_only_canonical_decoder_and_catalog() -> None:
    composition_source = _COMPOSITION.read_text(encoding="utf-8")
    execution_source = _EXECUTION_INPUTS.read_text(encoding="utf-8")
    assert "SchemaCatalog" not in composition_source
    assert "CanonicalSchema" not in composition_source
    assert "from_canonical_dict" not in composition_source
    assert "json." not in composition_source
    assert "_read_" not in composition_source
    assert execution_source.count("SchemaCatalog(") == 1
    assert execution_source.count("CanonicalSchema(") == 3


def test_generic_runtime_has_no_profile_branch_or_hidden_registration_builder() -> None:
    source = "\n".join(path.read_text(encoding="utf-8") for path in _GENERIC_MODULES)
    for forbidden in (
        "CnAShare",
        "BinanceUsdm",
        "cn_a_share_profile",
        "binance_usdm_profile",
        "._build_execution_case",
        "implementation._build_execution_case",
        "BacktestProfileRegistry(",
        "tests.support",
        "crypto_quant_platform",
        "crypto_quant_foundation",
    ):
        assert forbidden not in source


def test_private_composition_does_not_create_attempt_publication_or_storage() -> None:
    source = _COMPOSITION.read_text(encoding="utf-8")
    for forbidden in (
        "AttemptIdentity",
        "AuditableBacktestRunner",
        "AttemptEvidenceWriter",
        "CanonicalRunPublisher",
        "ArtifactEnvelopeReader",
        "Repository",
        "Path(",
        "requests",
        "httpx",
        "socket",
        "subprocess",
    ):
        assert forbidden not in source
    tree = _tree(_COMPOSITION)
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "open"
        for node in ast.walk(tree)
    )
