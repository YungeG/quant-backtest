from __future__ import annotations

import hashlib
import importlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CHECKER = ROOT / "tools/architecture/check_import_boundaries.py"
POLICY = ROOT / "architecture/import-boundaries.toml"
WORKSPACE_FIXTURE = (
    ROOT / "tests/fixtures/architecture/five-package-workspace-v1.expected.json"
)


def test_every_workspace_package_has_an_importable_public_root() -> None:
    workspace = json.loads(WORKSPACE_FIXTURE.read_text(encoding="utf-8"))

    for package in workspace["packages"]:
        module = importlib.import_module(package["module_name"])
        assert module.__name__ == package["module_name"]
        assert module.__package__ == package["module_name"]


def test_g08g_corporate_action_accounting_is_public_only_from_cn_a_share_profile() -> None:
    profile = importlib.import_module("crypto_quant_trading.profiles.cn_a_share")
    top_level = importlib.import_module("crypto_quant_trading")
    names = (
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
    for name in names:
        assert hasattr(profile, name), name
        assert name in profile.__all__
        assert not hasattr(top_level, name), name
        assert name not in top_level.__all__


def git_status() -> str:
    return subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def test_current_cross_package_imports_use_only_public_roots(tmp_path: Path) -> None:
    report_path = tmp_path / "boundary-report.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(CHECKER),
            "--root",
            str(ROOT),
            "--policy",
            str(POLICY),
            "--report",
            str(report_path),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "passed"
    assert report["report_schema_version"] == 1
    assert report["policy_schema_version"] == 1
    assert report["policy_sha256"] == hashlib.sha256(POLICY.read_bytes()).hexdigest()
    assert report["violations"] == []


def test_boundary_checker_writes_only_its_declared_ignored_report() -> None:
    before = git_status()
    report_path = ROOT / "build/acceptance/wp-00b-boundary-report.json"

    completed = subprocess.run(
        [
            sys.executable,
            str(CHECKER),
            "--root",
            str(ROOT),
            "--policy",
            str(POLICY),
            "--report",
            str(report_path),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert report_path.is_file()
    assert git_status() == before


def test_portfolio_v1_public_root_preserves_exact_existing_identities() -> None:
    prefix = "crypto_quant_trading.profiles.cn_a_share"
    facade = importlib.import_module(f"{prefix}.portfolio_v1")
    owners = (
        ("portfolio_order_plan_v1", "CnASharePortfolioOrderPlanV1"),
        ("portfolio_order_plan_v1", "CnASharePortfolioOrderProposalV1"),
        ("portfolio_open_risk_development_v1", "CnASharePortfolioOpenRiskApprovalDevelopmentV1"),
        ("portfolio_rebalance_policy_v1", "CnAShareRebalanceExecutionPolicyV1"),
        ("portfolio_sellability_v1", "CnASharePortfolioSellabilitySnapshotV1"),
        ("portfolio_sellability_v1", "project_cn_a_share_portfolio_sellability_v1"),
        ("shared_cny_cash_v1", "CnAShareSharedCnyCashSnapshotV1"),
        ("shared_cny_cash_v1", "project_cn_a_share_shared_cny_cash_v1"),
    )
    assert facade.__name__ == f"{prefix}.portfolio_v1"
    assert facade.__package__ == facade.__name__
    assert tuple(facade.__all__) == tuple(name for _, name in owners)
    old_roots = (
        ("crypto_quant_trading", "ac4064c96c719f6cd11d2361644b427ae58bbc902f3f1746f6e4cddbd2a7effb"),
        (prefix, "12c6ca1cc6f3e19d866fc66cdeb8fee6f6b29e341d03541135f9d5237ec874f7"),
    )
    for module_name, digest in old_roots:
        module = importlib.import_module(module_name)
        assert hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest() == digest
        for leaf, name in owners:
            assert getattr(facade, name) is getattr(importlib.import_module(f"{prefix}.{leaf}"), name)
            assert name not in module.__all__
            assert not hasattr(module, name)
