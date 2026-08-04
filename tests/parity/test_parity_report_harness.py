from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "tools/migration/run_parity.py"
FIXTURES = ROOT / "tests/parity/fixtures/comparator-v1"


def run_parity(
    root: Path,
    contract: Path,
    expected: Path,
    actual: Path,
    report: Path,
    migration_mode: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "--root",
            str(root),
            "--contract",
            str(contract),
            "--expected",
            str(expected),
            "--actual",
            str(actual),
            "--migration-mode",
            migration_mode,
            "--report",
            str(report),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_first_divergence_report_matches_the_controlled_golden(tmp_path: Path) -> None:
    report = tmp_path / "report.json"

    completed = run_parity(
        ROOT,
        FIXTURES / "mixed-contract.json",
        FIXTURES / "mixed-expected.json",
        FIXTURES / "mixed-actual-sequence-mismatch.json",
        report,
        "reimplement_with_reference",
    )

    assert completed.returncode == 1
    assert report.read_bytes() == (
        FIXTURES / "first-divergence-parity-report-v1.expected.json"
    ).read_bytes()


def approved_change_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    adr = tmp_path / "docs/adr/0001-approved-change.md"
    adr.parent.mkdir(parents=True)
    adr.write_text("# Approved fixture change\n", encoding="utf-8")
    contract = tmp_path / "contract.json"
    contract.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "id": "approved-change-v1",
                "rules": [
                    {
                        "path": "/value",
                        "comparison": "approved_change",
                        "reference": "docs/adr/0001-approved-change.md",
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    expected = tmp_path / "expected.json"
    actual = tmp_path / "actual.json"
    expected.write_text('{"value": 1}\n', encoding="utf-8")
    actual.write_text('{"value": 2}\n', encoding="utf-8")
    return contract, expected, actual


def test_approved_change_records_its_committed_adr_reference(tmp_path: Path) -> None:
    contract, expected, actual = approved_change_fixture(tmp_path)
    report = tmp_path / "report.json"

    completed = run_parity(
        tmp_path,
        contract,
        expected,
        actual,
        report,
        "intentional_semantic_change",
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["verdict"] == "APPROVED_CHANGE"
    assert payload["first_divergence"]["reason"] == (
        "approved-change:docs/adr/0001-approved-change.md"
    )


def test_approved_change_is_blocked_outside_intentional_mode(tmp_path: Path) -> None:
    contract, expected, actual = approved_change_fixture(tmp_path)
    report = tmp_path / "report.json"

    completed = run_parity(
        tmp_path,
        contract,
        expected,
        actual,
        report,
        "copy_with_parity",
    )

    assert completed.returncode == 2
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["verdict"] == "BLOCKED"
    assert payload["first_divergence"]["reason"] == (
        "approved-change-requires-intentional-mode"
    )


def test_intentional_mode_without_approved_rule_is_blocked(tmp_path: Path) -> None:
    report = tmp_path / "report.json"

    completed = run_parity(
        ROOT,
        FIXTURES / "exact-contract.json",
        FIXTURES / "exact-expected.json",
        FIXTURES / "exact-actual.json",
        report,
        "intentional_semantic_change",
    )

    assert completed.returncode == 2
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["first_divergence"]["reason"] == "intentional-change-without-adr"


def test_unknown_migration_mode_is_blocked(tmp_path: Path) -> None:
    report = tmp_path / "report.json"

    completed = run_parity(
        ROOT,
        FIXTURES / "exact-contract.json",
        FIXTURES / "exact-expected.json",
        FIXTURES / "exact-actual.json",
        report,
        "best_effort",
    )

    assert completed.returncode == 2
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["verdict"] == "BLOCKED"
    assert payload["first_divergence"]["reason"] == "unsupported-migration-mode"
