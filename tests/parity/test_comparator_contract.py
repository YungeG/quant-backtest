from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "tools/migration/run_parity.py"
FIXTURES = ROOT / "tests/parity/fixtures/comparator-v1"


def run_parity(
    contract: Path,
    expected: Path,
    actual: Path,
    report: Path,
    migration_mode: str = "copy_with_parity",
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "--root",
            str(ROOT),
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


def test_exact_contract_ignores_mapping_insertion_order(tmp_path: Path) -> None:
    report = tmp_path / "report.json"

    completed = run_parity(
        FIXTURES / "exact-contract.json",
        FIXTURES / "exact-expected.json",
        FIXTURES / "exact-actual.json",
        report,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["verdict"] == "MATCH"
    assert payload["first_divergence"] is None


def test_quantized_tolerance_and_sequence_rules_can_match(tmp_path: Path) -> None:
    report = tmp_path / "report.json"

    completed = run_parity(
        FIXTURES / "mixed-contract.json",
        FIXTURES / "mixed-expected.json",
        FIXTURES / "mixed-actual-match.json",
        report,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["verdict"] == "MATCH"
    assert payload["comparison_counts"] == {
        "approved_change": 0,
        "matched": 4,
        "mismatched": 0,
    }


def test_sequence_reports_the_first_differing_index(tmp_path: Path) -> None:
    report = tmp_path / "report.json"

    completed = run_parity(
        FIXTURES / "mixed-contract.json",
        FIXTURES / "mixed-expected.json",
        FIXTURES / "mixed-actual-sequence-mismatch.json",
        report,
    )

    assert completed.returncode == 1
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["verdict"] == "MISMATCH"
    assert payload["first_divergence"] == {
        "actual": {"sequence": 3, "type": "cancelled"},
        "comparison": "sequence",
        "expected": {"sequence": 2, "type": "filled"},
        "path": "/events/1",
        "reason": "sequence-item-mismatch",
    }


def test_exact_comparison_is_json_type_sensitive(tmp_path: Path) -> None:
    contract = tmp_path / "contract.json"
    contract.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "id": "type-sensitive-exact",
                "rules": [{"path": "/value", "comparison": "exact"}],
            }
        ),
        encoding="utf-8",
    )
    expected = tmp_path / "expected.json"
    actual = tmp_path / "actual.json"
    expected.write_text('{"value": {"flag": true}}\n', encoding="utf-8")
    actual.write_text('{"value": {"flag": 1}}\n', encoding="utf-8")
    report = tmp_path / "report.json"

    completed = run_parity(contract, expected, actual, report)

    assert completed.returncode == 1
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["first_divergence"]["reason"] == "exact-mismatch"


def test_global_epsilon_is_rejected(tmp_path: Path) -> None:
    contract = tmp_path / "contract.json"
    contract.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "id": "invalid-global-epsilon",
                "epsilon": 0.001,
                "rules": [{"path": "/cash_units", "comparison": "exact"}],
            }
        ),
        encoding="utf-8",
    )
    report = tmp_path / "report.json"

    completed = run_parity(
        contract,
        FIXTURES / "exact-expected.json",
        FIXTURES / "exact-actual.json",
        report,
    )

    assert completed.returncode == 2
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["status"] == "invalid-contract"
    assert payload["first_divergence"]["reason"] == "global-epsilon-forbidden"


def test_unclassified_input_field_fails_closed(tmp_path: Path) -> None:
    actual = tmp_path / "actual.json"
    payload = json.loads((FIXTURES / "exact-actual.json").read_text(encoding="utf-8"))
    payload["undeclared"] = 1
    actual.write_text(json.dumps(payload), encoding="utf-8")
    report = tmp_path / "report.json"

    completed = run_parity(
        FIXTURES / "exact-contract.json",
        FIXTURES / "exact-expected.json",
        actual,
        report,
    )

    assert completed.returncode == 2
    result = json.loads(report.read_text(encoding="utf-8"))
    assert result["first_divergence"]["reason"] == "unclassified-comparator-field"
    assert result["first_divergence"]["path"] == "/undeclared"


def test_approved_change_requires_a_committed_reference(tmp_path: Path) -> None:
    contract = tmp_path / "contract.json"
    contract.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "id": "invalid-approved-change",
                "rules": [{"path": "/currency", "comparison": "approved_change"}],
            }
        ),
        encoding="utf-8",
    )
    report = tmp_path / "report.json"

    completed = run_parity(
        contract,
        FIXTURES / "exact-expected.json",
        FIXTURES / "exact-actual.json",
        report,
    )

    assert completed.returncode == 2
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["first_divergence"]["reason"] == (
        "approved-change-without-reference"
    )


def test_parity_report_is_byte_deterministic(tmp_path: Path) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"

    first_run = run_parity(
        FIXTURES / "mixed-contract.json",
        FIXTURES / "mixed-expected.json",
        FIXTURES / "mixed-actual-sequence-mismatch.json",
        first,
    )
    second_run = run_parity(
        FIXTURES / "mixed-contract.json",
        FIXTURES / "mixed-expected.json",
        FIXTURES / "mixed-actual-sequence-mismatch.json",
        second,
    )

    assert first_run.returncode == second_run.returncode == 1
    assert first.read_bytes() == second.read_bytes()
