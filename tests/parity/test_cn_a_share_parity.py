from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

import pytest

from tools.parity.cn_a_share import CnAShareParityError, run_plan


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/parity/fixtures/cn-a-share-g08h-v1"
PLAN = FIXTURES / "plan.json"
CONTRACT = ROOT / "tests/parity/contracts/cn-a-share-g08h-legacy-to-g08h-v1.json"
LEGACY_ARCHIVE = ROOT / ("tests/parity/fixtures/legacy-sources/" "cycle-rotation-platform-1fea4f5a4ec8ab12ddb25c6c5bb525f91f8bac9e887f3e5b382b641a948c91c3.tar.gz")
LEGACY_MANIFEST = LEGACY_ARCHIVE.with_suffix("").with_suffix(".manifest.json")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"invalid JSON fixture: {path}") from error
    assert isinstance(value, dict)
    return value


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _sandbox(tmp_path: Path) -> tuple[Path, Path]:
    fixture_dir = tmp_path / "tests/parity/fixtures/cn-a-share-g08h-v1"
    contract_dir = tmp_path / "tests/parity/contracts"
    legacy_dir = tmp_path / "tests/parity/fixtures/legacy-sources"
    fixture_dir.mkdir(parents=True); contract_dir.mkdir(parents=True); legacy_dir.mkdir(parents=True)
    for source in FIXTURES.iterdir(): shutil.copy2(source, fixture_dir / source.name)
    shutil.copy2(CONTRACT, contract_dir / CONTRACT.name)
    shutil.copy2(LEGACY_ARCHIVE, legacy_dir / LEGACY_ARCHIVE.name)
    shutil.copy2(LEGACY_MANIFEST, legacy_dir / LEGACY_MANIFEST.name)
    return tmp_path, fixture_dir / "plan.json"


def test_g08h_parity_reports_legacy_scope_without_claiming_match() -> None:
    report = run_plan(ROOT, PLAN)
    assert report["status"] == "completed"
    assert report["comparison_verdict"] == "NOT_COMPARABLE_LEGACY_SCOPE"
    assert not report["coverage_complete"]
    assert report["first_divergence"] is None
    assert report["first_uncovered_layer"] == {"pair": "LEGACY_TO_G08H", "layer": "01_CALENDAR_SESSION", "status": "NOT_COMPARABLE_LEGACY_SCOPE"}
    assert not report["decision_grade_eligible"]
    assert not report["deployment_authorized"]


def test_g08h_comparable_mismatch_reports_exact_first_path(tmp_path: Path) -> None:
    root, plan_path = _sandbox(tmp_path)
    actual_path = root / "tests/parity/fixtures/cn-a-share-g08h-v1/g08h.actual.json"
    actual = _read_json(actual_path)
    actual["layers"]["04_ORDER_INTENT"][0]["quantity_units"] = 9400
    _write_json(actual_path, actual)
    plan = _read_json(plan_path)
    plan["sources"][1]["projection_sha256"] = _sha256(actual_path)
    plan["pairs"][0]["expected_verdict"] = "MISMATCH"
    _write_json(plan_path, plan)
    report = run_plan(root, plan_path)
    assert report["comparison_verdict"] == "MISMATCH"
    assert report["first_divergence"]["pair"] == "LEGACY_TO_G08H"
    assert report["first_divergence"]["path"] == "/layers/04_ORDER_INTENT/0/quantity_units"
    assert report["first_divergence"]["reason"] == "exact-mismatch"


def test_g08h_missing_coverage_row_fails_closed(tmp_path: Path) -> None:
    root, plan_path = _sandbox(tmp_path)
    plan = _read_json(plan_path); plan["coverage"] = plan["coverage"][:-1]; _write_json(plan_path, plan)
    with pytest.raises(CnAShareParityError) as caught: run_plan(root, plan_path)
    assert caught.value.code == "COVERAGE_INCOMPLETE"
    assert caught.value.path == "/coverage"


def test_g08h_not_comparable_layer_cannot_have_comparator_rule(tmp_path: Path) -> None:
    root, plan_path = _sandbox(tmp_path)
    contract_path = root / "tests/parity/contracts/cn-a-share-g08h-legacy-to-g08h-v1.json"
    contract = _read_json(contract_path)
    contract["rules"].append({"path": "/layers/01_CALENDAR_SESSION", "comparison": "exact"})
    _write_json(contract_path, contract)
    with pytest.raises(CnAShareParityError) as caught: run_plan(root, plan_path)
    assert caught.value.code == "NOT_COMPARABLE_RULE_CONFLICT"
    assert caught.value.path == "/LEGACY_TO_G08H/01_CALENDAR_SESSION"


def test_g08h_legacy_source_identity_is_immutable(tmp_path: Path) -> None:
    root, plan_path = _sandbox(tmp_path)
    plan = _read_json(plan_path); plan["sources"][0]["snapshot_sha256"] = "0" * 64; _write_json(plan_path, plan)
    with pytest.raises(CnAShareParityError) as caught: run_plan(root, plan_path)
    assert caught.value.code == "SOURCE_SNAPSHOT_MISMATCH"
    assert caught.value.path == "/sources/LEGACY_CYCLE_ROTATION/snapshot_sha256"
