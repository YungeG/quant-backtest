from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/parity/fixtures/binance-usdm-g10h-v1"
EXPECTED = FIXTURES / "report.expected.json"


def _run(root: Path, report: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(root / "tools/parity/run_binance_usdm_parity.py"),
            "--root",
            str(root),
            "--plan",
            str(root / "tests/parity/fixtures/binance-usdm-g10h-v1/plan.json"),
            "--report",
            str(report),
        ],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )


def _copy_root(tmp_path: Path) -> Path:
    root = tmp_path / "copy"
    for relative in (
        "docs/adr/0001-g10h-legacy-binance-parity-boundary.md",
        "tests/parity/contracts/binance-usdm-g10h-legacy-to-g10g-v1.json",
        "tests/parity/contracts/binance-usdm-g10h-provider-to-g10g-v1.json",
        "tests/parity/fixtures/binance-usdm-g10h-v1/plan.json",
        "tests/parity/fixtures/binance-usdm-g10h-v1/legacy.expected.json",
        "tests/parity/fixtures/binance-usdm-g10h-v1/g10g.actual.json",
        "tests/parity/fixtures/binance-usdm-g10h-v1/provider.expected.json",
        "tools/migration/legacy_migration/__init__.py",
        "tools/migration/legacy_migration/parity.py",
        "tools/migration/legacy_migration/snapshots.py",
        "tools/migration/legacy_migration/source_maps.py",
        "tools/parity/binance_usdm.py",
        "tools/parity/run_binance_usdm_parity.py",
    ):
        source = ROOT / relative
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return root


def test_g10h_report_matches_static_golden_and_is_root_independent(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.json"
    first_completed = _run(ROOT, first)
    copied_root = _copy_root(tmp_path)
    second = tmp_path / "second.json"
    second_completed = _run(copied_root, second)

    assert first_completed.returncode == 0, first_completed.stderr
    assert second_completed.returncode == 0, second_completed.stderr
    assert first.read_bytes() == EXPECTED.read_bytes()
    assert second.read_bytes() == EXPECTED.read_bytes()
