from __future__ import annotations

import ast
import dataclasses
import inspect
from pathlib import Path

import crypto_quant_backtest
from crypto_quant_backtest import cn_a_share_fee_v2_binding as binding

ROOT = Path(__file__).resolve().parents[2]
MODULE = (
    ROOT
    / "packages/backtest-runtime/src/crypto_quant_backtest/cn_a_share_fee_v2_binding.py"
)


def test_v2b_is_off_root_runtime_only_and_has_no_builder_or_registry_framework() -> (
    None
):
    for name in (
        "CnAShareFeeProfileBindingV2",
        "CnAShareFeeBuildBindingV2",
        "CnAShareFeeRuntimeExecutionV2",
        "CnAShareFeePreparedExecutionV2",
        "bind_cn_a_share_fee_profile_v2",
        "bind_cn_a_share_fee_build_v2",
        "bind_cn_a_share_fee_execution_v2",
        "bind_cn_a_share_fee_semantic_spec_v2",
        "prepare_cn_a_share_fee_execution_v2",
    ):
        assert not hasattr(crypto_quant_backtest, name)

    tree = ast.parse(MODULE.read_text())
    imports = {
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }
    assert not any(
        forbidden in module
        for module in imports
        for forbidden in (
            "bundle_builder",
            "market_bundle_builder",
            "provider",
            "facade",
            "runner",
        )
    )
    source = MODULE.read_text()
    for forbidden in (
        "class BacktestProfileRegistry",
        "class ProfileResolver",
        "class FinancialEventDispatcher",
        "resample",
        "default_route",
        "default_product",
    ):
        assert forbidden not in source


def test_v2b_shapes_and_binding_signatures_are_additive_and_default_free() -> None:
    assert tuple(
        field.name for field in dataclasses.fields(binding.CnAShareFeeProfileBindingV2)
    ) == (
        "schema_version",
        "resolved_profile",
        "projection",
        "legacy_profile_inputs_hash",
        "market_profile_key",
        "market_profile_version",
        "simulation_profile_key",
        "simulation_profile_version",
        "execution_account_profile_key",
        "execution_account_profile_version",
        "account_id",
        "venue_id",
        "instrument_id",
        "access_route",
        "fee_product_class",
        "authority",
        "authority_hash",
        "scope_hash",
        "selection_hash",
        "market_fee_rule_book_hash",
        "stamp_duty_rule_book_hash",
        "market_fee_component_ref",
        "stamp_duty_component_ref",
        "compatibility_projection_hash",
    )
    assert tuple(
        field.name for field in dataclasses.fields(binding.CnAShareFeeBuildBindingV2)
    ) == (
        "schema_version",
        "build_artifact_manifest",
        "profile_binding",
        "profile_binding_hash",
        "build_artifact_manifest_hash",
        "profile_artifact_hashes",
    )
    assert tuple(
        field.name
        for field in dataclasses.fields(binding.CnAShareFeeRuntimeExecutionV2)
    ) == (
        "schema_version",
        "profile_binding",
        "profile_binding_hash",
        "build_binding",
        "build_binding_hash",
        "authority",
        "authority_hash",
        "execution_binding",
        "order_hash",
    )
    assert tuple(
        field.name
        for field in dataclasses.fields(binding.CnAShareFeePreparedExecutionV2)
    ) == (
        "schema_version",
        "base_spec",
        "profile_binding",
        "build_binding",
        "runtime_execution",
        "semantic_spec",
    )
    for function in (
        binding.bind_cn_a_share_fee_profile_v2,
        binding.bind_cn_a_share_fee_build_v2,
        binding.bind_cn_a_share_fee_execution_v2,
        binding.bind_cn_a_share_fee_semantic_spec_v2,
        binding.prepare_cn_a_share_fee_execution_v2,
    ):
        parameters = tuple(inspect.signature(function).parameters.values())
        assert parameters
        assert all(
            parameter.kind is inspect.Parameter.KEYWORD_ONLY for parameter in parameters
        )
        assert all(
            parameter.default is inspect.Parameter.empty for parameter in parameters
        )
