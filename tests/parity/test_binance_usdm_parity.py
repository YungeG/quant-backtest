from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "tools/parity/run_binance_usdm_parity.py"
FIXTURES = ROOT / "tests/parity/fixtures/binance-usdm-g10h-v1"
PLAN = FIXTURES / "plan.json"


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise AssertionError(f"failed to read test JSON: {path}") from error


def _write_json(path: Path, value: object) -> None:
    try:
        payload = json.dumps(value, indent=2, sort_keys=True) + "\n"
        path.write_text(payload, encoding="utf-8")
    except (OSError, UnicodeError, TypeError) as error:
        raise AssertionError(f"failed to write test JSON: {path}") from error


def _read_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as error:
        raise AssertionError(f"failed to read test file: {path}") from error


def _sha256(path: Path) -> str:
    return hashlib.sha256(_read_bytes(path)).hexdigest()


def _run(root: Path, plan: Path, report: Path, *, require_match: bool = False):
    command = [
        sys.executable,
        str(root / "tools/parity/run_binance_usdm_parity.py"),
        "--root",
        str(root),
        "--plan",
        str(plan),
        "--report",
        str(report),
    ]
    if require_match:
        command.append("--require-match")
    return subprocess.run(
        command,
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )


def _copy_root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
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


def test_canonical_plan_reports_approved_change_and_partial_coverage(
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "report.json"

    completed = _run(ROOT, PLAN, report_path)

    assert completed.returncode == 0, completed.stderr
    report = _read_json(report_path)
    assert report["status"] == "completed"
    assert report["comparison_verdict"] == "APPROVED_CHANGE"
    assert [pair["verdict"] for pair in report["pair_reports"]] == [
        "APPROVED_CHANGE",
        "MATCH",
    ]
    assert not report["coverage_complete"]
    assert report["first_divergence"]["pair"] == "LEGACY_TO_G10G"
    assert report["first_divergence"]["path"] == "/layers/01_DECISION"
    assert report["first_divergence"]["reason"].startswith("approved-change:docs/adr/")
    assert not report["decision_grade_eligible"]
    assert not report["deployment_authorized"]


def test_frozen_legacy_snapshot_identity_fails_closed(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    plan_path = root / "tests/parity/fixtures/binance-usdm-g10h-v1/plan.json"
    plan = _read_json(plan_path)
    plan["sources"][0]["snapshot_sha256"] = "0" * 64
    _write_json(plan_path, plan)
    report_path = tmp_path / "blocked.json"

    completed = _run(root, plan_path, report_path)

    assert completed.returncode == 2
    report = _read_json(report_path)
    assert report["status"] == "blocked"
    assert report["failure"]["code"] == "SOURCE_SNAPSHOT_MISMATCH"


def test_completed_mismatch_is_evidence_unless_match_is_required(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    plan_path = root / "tests/parity/fixtures/binance-usdm-g10h-v1/plan.json"
    projection_path = (
        root / "tests/parity/fixtures/binance-usdm-g10h-v1/provider.expected.json"
    )
    projection = _read_json(projection_path)
    projection["layers"]["04_FILL"][1]["commission"] = "0.16"
    projection["layers"]["05_FEE"][1]["amount"] = "0.16"
    _write_json(projection_path, projection)
    plan = _read_json(plan_path)
    plan["sources"][2]["projection_sha256"] = _sha256(projection_path)
    plan["pairs"][1]["expected_verdict"] = "MISMATCH"
    _write_json(plan_path, plan)

    completed_report = tmp_path / "mismatch.json"
    completed = _run(root, plan_path, completed_report)
    required_report = tmp_path / "required.json"
    required = _run(root, plan_path, required_report, require_match=True)

    report = _read_json(completed_report)
    assert completed.returncode == 0
    assert report["comparison_verdict"] == "MISMATCH"
    assert report["first_divergence"]["pair"] == "LEGACY_TO_G10G"
    assert required.returncode == 1
    assert _read_bytes(required_report) == _read_bytes(completed_report)


def test_comparable_layer_without_a_rule_fails_closed(tmp_path: Path) -> None:
    root = _copy_root(tmp_path)
    plan_path = root / "tests/parity/fixtures/binance-usdm-g10h-v1/plan.json"
    plan = _read_json(plan_path)
    row = next(
        item
        for item in plan["coverage"]
        if item["pair"] == "LEGACY_TO_G10G"
        and item["layer"] == "LIQUIDATION_EXECUTION"
    )
    row["status"] = "COMPARABLE"
    _write_json(plan_path, plan)
    report_path = tmp_path / "blocked.json"

    completed = _run(root, plan_path, report_path)

    assert completed.returncode == 2
    report = _read_json(report_path)
    assert report["failure"]["code"] == "COMPARABLE_RULE_MISSING"
