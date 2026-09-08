from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
CHECKER = ROOT / "tools/architecture/check_import_boundaries.py"
POLICY = ROOT / "architecture/import-boundaries.toml"
FIXTURE = (
    ROOT
    / "tests/fixtures/architecture/import-boundary-mutations-v1/cases.json"
)


def run_checker(root: Path, policy: Path, report: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(CHECKER),
            "--root",
            str(root),
            "--policy",
            str(policy),
            "--report",
            str(report),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def load_cases() -> list[dict[str, object]]:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert fixture["schema_version"] == 1
    assert fixture["fixture_id"] == "import-boundary-mutations-v1"
    return fixture["cases"]


@pytest.mark.parametrize("case", load_cases(), ids=lambda case: str(case["id"]))
def test_forbidden_import_mutations_fail_with_the_expected_rule(
    tmp_path: Path, case: dict[str, object]
) -> None:
    source_path = tmp_path / str(case["path"])
    source_path.parent.mkdir(parents=True)
    source_path.write_text(str(case["source"]), encoding="utf-8")
    report_path = tmp_path / "report.json"

    completed = run_checker(tmp_path, POLICY, report_path)

    assert completed.returncode == 1, completed.stdout + completed.stderr
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "failed"
    assert [violation["rule"] for violation in report["violations"]] == case[
        "expected_rules"
    ]
    assert report["violations"][0]["source_path"] == str(case["path"])


def test_declared_workspace_dependency_directions_are_allowed(tmp_path: Path) -> None:
    sources = {
        "packages/trading-kernel/src/crypto_quant_trading/allowed.py": (
            "import crypto_quant_domain\n"
        ),
        "packages/market-data-contracts/src/crypto_quant_market_data/allowed.py": (
            "import crypto_quant_domain\n"
        ),
        "packages/market-bundle-builder/src/crypto_quant_bundle_builder/allowed.py": (
            "import crypto_quant_market_data\n"
        ),
        "packages/backtest-runtime/src/crypto_quant_backtest/allowed.py": (
            "import crypto_quant_domain\n"
            "import crypto_quant_market_data\n"
            "import crypto_quant_trading\n"
        ),
    }
    for relative_path, source in sources.items():
        source_path = tmp_path / relative_path
        source_path.parent.mkdir(parents=True)
        source_path.write_text(source, encoding="utf-8")
    report = tmp_path / "report.json"

    completed = run_checker(tmp_path, POLICY, report)

    assert completed.returncode == 0, completed.stdout + completed.stderr
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["violations"] == []


def test_unknown_policy_schema_fails_closed(tmp_path: Path) -> None:
    policy = tmp_path / "policy.toml"
    policy.write_text(
        POLICY.read_text(encoding="utf-8").replace(
            "schema_version = 1", "schema_version = 999", 1
        ),
        encoding="utf-8",
    )
    report = tmp_path / "report.json"

    completed = run_checker(tmp_path, policy, report)

    assert completed.returncode == 2
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["status"] == "invalid-policy"
    assert payload["violations"][0]["rule"] == "unsupported-policy-schema"


def test_dynamic_allowance_requires_an_inferable_matching_prefix(
    tmp_path: Path,
) -> None:
    source_path = (
        tmp_path
        / "packages/backtest-runtime/src/crypto_quant_backtest/plugins.py"
    )
    source_path.parent.mkdir(parents=True)
    source_path.write_text(
        "import importlib\nmodule_name = input()\nimportlib.import_module(module_name)\n",
        encoding="utf-8",
    )
    policy = tmp_path / "policy.toml"
    policy.write_text(
        POLICY.read_text(encoding="utf-8")
        + "\n[[dynamic_import_allowlist]]\n"
        + 'caller = "packages/backtest-runtime/src/crypto_quant_backtest/plugins.py"\n'
        + 'target_prefix = "crypto_quant_domain.plugins"\n'
        + 'reason = "fixture exercises an explicitly scoped plugin namespace"\n',
        encoding="utf-8",
    )
    report = tmp_path / "report.json"

    completed = run_checker(tmp_path, policy, report)

    assert completed.returncode == 1
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert [item["rule"] for item in payload["violations"]] == [
        "undeclared-dynamic-import"
    ]


def test_dynamic_allowance_accepts_only_its_declared_literal_prefix(
    tmp_path: Path,
) -> None:
    source_path = (
        tmp_path
        / "packages/backtest-runtime/src/crypto_quant_backtest/plugins.py"
    )
    source_path.parent.mkdir(parents=True)
    source_path.write_text(
        "import importlib\nname = input()\n"
        "importlib.import_module(f'crypto_quant_domain.plugins.{name}')\n",
        encoding="utf-8",
    )
    policy = tmp_path / "policy.toml"
    policy.write_text(
        POLICY.read_text(encoding="utf-8")
        + "\n[[dynamic_import_allowlist]]\n"
        + 'caller = "packages/backtest-runtime/src/crypto_quant_backtest/plugins.py"\n'
        + 'target_prefix = "crypto_quant_domain.plugins"\n'
        + 'reason = "fixture exercises an explicitly scoped plugin namespace"\n',
        encoding="utf-8",
    )
    report = tmp_path / "report.json"

    completed = run_checker(tmp_path, policy, report)

    assert completed.returncode == 0, completed.stdout + completed.stderr
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["status"] == "passed"


def test_report_violations_have_canonical_sort_order(tmp_path: Path) -> None:
    source_path = (
        tmp_path / "packages/backtest-runtime/src/crypto_quant_backtest/bad.py"
    )
    source_path.parent.mkdir(parents=True)
    source_path.write_text(
        "import socket\nimport crypto_quant_bundle_builder\n", encoding="utf-8"
    )
    report = tmp_path / "report.json"

    assert run_checker(tmp_path, POLICY, report).returncode == 1

    payload = json.loads(report.read_text(encoding="utf-8"))
    assert [item["rule"] for item in payload["violations"]] == [
        "runtime-builder-import",
        "runtime-network-import",
    ]


def test_boundary_report_is_byte_deterministic(tmp_path: Path) -> None:
    case = load_cases()[0]
    source_path = tmp_path / str(case["path"])
    source_path.parent.mkdir(parents=True)
    source_path.write_text(str(case["source"]), encoding="utf-8")
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"

    assert run_checker(tmp_path, POLICY, first).returncode == 1
    assert run_checker(tmp_path, POLICY, second).returncode == 1

    assert first.read_bytes() == second.read_bytes()
