from __future__ import annotations

import ast
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[2]
_RUNTIME = _ROOT / "packages/backtest-runtime/src/crypto_quant_backtest"
_EXECUTION_INPUTS = _RUNTIME / "execution_inputs.py"
_PUBLIC_INIT = _RUNTIME / "__init__.py"
_GENERIC_RUNTIME = (
    _RUNTIME / "composition.py",
    _RUNTIME / "engine.py",
    _RUNTIME / "execution_inputs.py",
    _RUNTIME / "resolution.py",
    _RUNTIME / "runner.py",
)


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_v2_adds_only_the_materializer_to_the_public_root() -> None:
    source = _PUBLIC_INIT.read_text(encoding="utf-8")
    assert "materialize_execution_input_bundle_v2" in source, (
        "BT-GAP-02C RED: v2 materializer is not root-exported"
    )
    for forbidden in (
        "ExecutionCasePlan",
        "ExecutionCaseBuilder",
        "ProfileExecutionPlan",
        "RuntimeProfileAdapter",
        "ExecutionPlanRegistry",
    ):
        assert forbidden not in source


def test_v1_materializer_interface_remains_exactly_unchanged() -> None:
    tree = _tree(_EXECUTION_INPUTS)
    materializer = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "materialize_execution_input_bundle"
    )
    assert tuple(argument.arg for argument in materializer.args.kwonlyargs) == (
        "request",
        "build_artifact_manifest",
        "execution_case_semantic_spec",
        "timeline_stream_keys",
        "target_stream_key",
        "timeline_batch_size",
        "initial_financial_state_template",
    )


def test_v2_uses_the_existing_catalog_and_no_second_selector() -> None:
    source = _EXECUTION_INPUTS.read_text(encoding="utf-8")
    assert "materialize_execution_input_bundle_v2" in source, (
        "BT-GAP-02C RED: v2 implementation is absent"
    )
    assert source.count("SchemaCatalog(") == 1
    assert source.count("CanonicalSchema(") == 2, (
        "BT-GAP-02C RED: bundle@2 must be a second registration in the existing catalog"
    )
    generic_source = "\n".join(
        path.read_text(encoding="utf-8") for path in _GENERIC_RUNTIME
    )
    for forbidden in (
        "CnAShare",
        "BinanceUsdm",
        "cn_a_share_profile",
        "binance_usdm_profile",
        "crypto_quant_platform",
        "crypto_quant_foundation",
        "tests.support",
    ):
        assert forbidden not in generic_source


def test_execution_closure_remains_data_not_a_new_artifact_or_repository() -> None:
    source = _EXECUTION_INPUTS.read_text(encoding="utf-8")
    for forbidden in (
        "ExecutionCasePlanRef",
        "ProfileExecutionPlanRef",
        "ExecutionCasePlanRepository",
        "ExecutionPlanCache",
        "execution_plan_path",
        "profile_plan_path",
    ):
        assert forbidden not in source


def test_typed_reader_and_executable_profile_do_not_forge_runtime_objects() -> None:
    execution_inputs = _EXECUTION_INPUTS.read_text(encoding="utf-8")
    binance_profile = (_RUNTIME / "binance_usdm_profile.py").read_text(
        encoding="utf-8"
    )
    for forbidden in (
        "object.__new__",
        "_dataclass_shell",
        "_CanonicalPlanValue",
        "get_type_hints",
    ):
        assert forbidden not in execution_inputs
    assert "def __getattr__(" not in binance_profile
