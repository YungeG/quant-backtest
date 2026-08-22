from __future__ import annotations

import ast
from pathlib import Path

from crypto_quant_backtest.cn_a_share_fixed_singleton_no_trade_profile_v1 import (
    CN_A_SHARE_FIXED_SINGLETON_NO_TRADE_AUTHORITY_V1,
)
from crypto_quant_backtest.ports import SimulationPortType
from crypto_quant_trading import ProfilePortType

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "packages/backtest-runtime/src/crypto_quant_backtest"
MODULE = RUNTIME / "cn_a_share_fixed_singleton_no_trade_profile_v1.py"
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


def test_authority_is_one_off_root_private_module_without_io_or_assessor_imports() -> None:
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
    assert MODULE.name not in PUBLIC_ROOT.read_text(encoding="utf-8")
    assert "CnAShareFixedSingletonNoTradeAuthorityV1" not in PUBLIC_ROOT.read_text(
        encoding="utf-8"
    )


def test_component_applicability_exact_covers_both_port_enums() -> None:
    authority = CN_A_SHARE_FIXED_SINGLETON_NO_TRADE_AUTHORITY_V1
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

    dispositions = {
        value.component_ref.port_type: value.disposition.value for value in simulation
    }
    for port in (
        SimulationPortType.EXECUTION_MODEL,
        SimulationPortType.SLIPPAGE_MODEL,
        SimulationPortType.LATENCY_MODEL,
        SimulationPortType.LIQUIDITY_MODEL,
    ):
        assert dispositions[port] == "inert_by_zero_target_and_zero_order_capacity"


def test_authorized_candidate_does_not_widen_existing_shared_surfaces() -> None:
    changed = {
        line[3:]
        for line in __import__("subprocess")
        .check_output(
            ["git", "status", "--short", "--untracked-files=all"], cwd=ROOT, text=True
        )
        .splitlines()
    }
    allowed = {
        "packages/backtest-runtime/src/crypto_quant_backtest/cn_a_share_fixed_singleton_no_trade_profile_v1.py",
        "tests/runtime/profiles/cn_a_share/test_fixed_singleton_no_trade_profile_v1.py",
        "tests/architecture/test_cn_a_share_fixed_singleton_no_trade_profile_boundary.py",
        "docs/implementation/plans/g12/g12m-tushare-fixed-singleton-profile-build-authority-v1.md",
        "docs/research/g12m-tushare-fixed-singleton-profile-build-authority-v1.md",
        "evidence/g12m-tushare-fixed-singleton-profile-build-authority-v1/decision.json",
        "evidence/g12m-tushare-fixed-singleton-profile-build-authority-v1/manifest.sha256",
    }
    assert changed <= allowed
