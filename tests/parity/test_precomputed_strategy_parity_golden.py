from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "tests/parity/contracts/precomputed-strategy-g11j-v1.json"
FIXTURES = ROOT / "tests/parity/fixtures/precomputed-strategy-g11j-v1"
EXPECTED_REPORT = FIXTURES / "report.expected.json"


def _stage(root: Path) -> tuple[Path, Path, Path]:
    root.mkdir()
    contract = root / "contract.json"
    expected = root / "expected.json"
    actual = root / "actual.json"
    contract.write_bytes(CONTRACT.read_bytes())
    expected.write_bytes((FIXTURES / "expected.json").read_bytes())
    actual.write_bytes((FIXTURES / "actual.json").read_bytes())
    return contract, expected, actual


def _run(
    root: Path,
    contract: Path,
    expected: Path,
    actual: Path,
    report: Path,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/parity/run_precomputed_strategy_parity.py"),
            "--root",
            str(root),
            "--contract",
            str(contract),
            "--expected",
            str(expected),
            "--actual",
            str(actual),
            "--report",
            str(report),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_g11j_report_matches_static_golden_and_repeats(tmp_path: Path) -> None:
    root = tmp_path / "evidence"
    contract, expected, actual = _stage(root)
    first = root / "first.json"
    second = root / "second.json"

    first_run = _run(root, contract, expected, actual, first)
    second_run = _run(root, contract, expected, actual, second)

    assert first_run.returncode == second_run.returncode == 0
    assert first.read_bytes() == EXPECTED_REPORT.read_bytes()
    assert second.read_bytes() == EXPECTED_REPORT.read_bytes()


def test_g11j_copied_fixture_root_matches_static_golden(tmp_path: Path) -> None:
    root = tmp_path / "copied-fixture-root"
    shutil.copytree(FIXTURES, root)
    contract = root / "contract.json"
    contract.write_bytes(CONTRACT.read_bytes())
    report = root / "report.json"

    completed = _run(
        root,
        contract,
        root / "expected.json",
        root / "actual.json",
        report,
    )

    assert completed.returncode == 0, completed.stderr
    assert report.read_bytes() == EXPECTED_REPORT.read_bytes()
