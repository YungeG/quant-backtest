from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/parity/fixtures/market-bundle-reader-g12f-v1"
EXPECTED_REPORT = FIXTURES / "report.expected.json"


def _run(report: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/parity/run_market_bundle_reader_parity.py"),
            "--root",
            str(ROOT),
            "--contract",
            str(ROOT / "tests/parity/contracts/market-bundle-reader-g12f-v1.json"),
            "--expected",
            str(FIXTURES / "expected.json"),
            "--actual",
            str(FIXTURES / "actual.json"),
            "--report",
            str(report),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_g12f_report_matches_static_golden_and_repeats(tmp_path: Path) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"

    first_run = _run(first)
    second_run = _run(second)

    assert first_run.returncode == second_run.returncode == 0
    assert first.read_bytes() == EXPECTED_REPORT.read_bytes()
    assert second.read_bytes() == EXPECTED_REPORT.read_bytes()
