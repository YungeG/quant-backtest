from __future__ import annotations

import ast
import subprocess
from pathlib import Path

from crypto_quant_backtest.cn_a_share_fixed_singleton_no_trade_profile_v2 import (
    CN_A_SHARE_FIXED_SINGLETON_NO_TRADE_AUTHORITY_V2,
)
from crypto_quant_backtest.ports import SimulationPortType
from crypto_quant_trading import ProfilePortType

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "packages/backtest-runtime/src/crypto_quant_backtest"
MODULE = RUNTIME / "cn_a_share_fixed_singleton_no_trade_profile_v2.py"
PUBLIC_ROOT = RUNTIME / "__init__.py"


def _imports(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    values: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            values.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            values.append(("." * node.level) + (node.module or ""))
    return tuple(values)


def test_v2_authority_is_off_root_without_io_framework_or_assessor_imports() -> None:
    assert MODULE.is_file()
    source = MODULE.read_text(encoding="utf-8")
    imports = _imports(MODULE)
    assert not any(
        name.lstrip(".").split(".", 1)[0]
        in {
            "crypto_quant_bundle_builder",
            "g12m",
            "json",
            "os",
            "pathlib",
            "requests",
            "socket",
            "subprocess",
            "urllib",
        }
        for name in imports
    )
    for forbidden in (
        "Builder",
        "Assessor",
        "BacktestProfileRegistry",
        "ProfileResolver",
        "Protocol",
        "Factory",
        "DSL",
        "open(",
    ):
        assert forbidden not in source
    root = PUBLIC_ROOT.read_text(encoding="utf-8")
    assert MODULE.name not in root
    assert "CN_A_SHARE_FIXED_SINGLETON_NO_TRADE_AUTHORITY_V2" not in root


def test_v2_exposes_only_constant_constructor_and_target_delegate() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    assignment = next(
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "__all__"
            for target in node.targets
        )
    )
    assert isinstance(assignment.value, ast.List)
    assert tuple(
        value.value
        for value in assignment.value.elts
        if isinstance(value, ast.Constant)
    ) == (
        "CN_A_SHARE_FIXED_SINGLETON_NO_TRADE_AUTHORITY_V2",
        "create_cn_a_share_fixed_singleton_no_trade_authority_v2",
        "validate_cn_a_share_fixed_singleton_no_trade_target_stream_v2",
    )


def test_component_applicability_exact_covers_ports_and_six_replacements() -> None:
    authority = CN_A_SHARE_FIXED_SINGLETON_NO_TRADE_AUTHORITY_V2
    profile = tuple(
        value
        for value in authority.component_applicability
        if type(value.component_ref).__name__ == "ProfileComponentRef"
    )
    simulation = tuple(
        value
        for value in authority.component_applicability
        if type(value.component_ref).__name__ == "SimulationComponentRef"
    )
    assert {value.component_ref.port_type for value in profile} == set(ProfilePortType)
    assert {value.component_ref.port_type for value in simulation} == set(
        SimulationPortType
    )
    assert len(profile) == len(ProfilePortType)
    assert len(simulation) == len(SimulationPortType)
    replaced = {
        value.component_ref.port_type
        for value in authority.component_applicability
        if value.predecessor_component_ref is not None
    }
    assert replaced == {
        ProfilePortType.POSITION_ACCOUNTING_MODEL,
        ProfilePortType.FINANCING_MODEL,
        ProfilePortType.MARGIN_MODEL,
        SimulationPortType.EXECUTION_MODEL,
        SimulationPortType.CLOSEOUT_POLICY,
        SimulationPortType.LIQUIDATION_AUDIT_MODEL,
    }


def test_authorized_candidate_write_set_is_not_widened() -> None:
    changed = {
        line[3:]
        for line in subprocess.check_output(
            ["git", "status", "--short", "--untracked-files=all"],
            cwd=ROOT,
            text=True,
        ).splitlines()
    }
    allowed = {
        "packages/backtest-runtime/src/crypto_quant_backtest/cn_a_share_fixed_singleton_no_trade_profile_v2.py",
        "tests/runtime/profiles/cn_a_share/test_fixed_singleton_no_trade_profile_v2.py",
        "tests/architecture/test_cn_a_share_fixed_singleton_no_trade_profile_v2_boundary.py",
        "docs/implementation/plans/g12/g12m-tushare-fixed-singleton-profile-build-authority-v2.md",
        "docs/research/g12m-tushare-fixed-singleton-profile-build-authority-v2.md",
        "evidence/g12m-tushare-fixed-singleton-profile-build-authority-v2/decision.json",
        "evidence/g12m-tushare-fixed-singleton-profile-build-authority-v2/manifest.sha256",
    }
    assert changed <= allowed
