from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tests.parity._market_bundle_reader_fixtures import projection, publish_reader


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "tools/parity/run_market_bundle_reader_parity.py"
CONTRACT = ROOT / "tests/parity/contracts/market-bundle-reader-g12f-v1.json"
FIXTURES = ROOT / "tests/parity/fixtures/market-bundle-reader-g12f-v1"
EXPECTED = FIXTURES / "expected.json"
ACTUAL = FIXTURES / "actual.json"


def _run(
    expected: Path,
    actual: Path,
    report: Path,
    *,
    root: Path = ROOT,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "--root",
            str(root),
            "--contract",
            str(CONTRACT),
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


def _write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_generated_in_memory_and_local_projections_are_exactly_equal(
    tmp_path: Path,
) -> None:
    in_memory, local = publish_reader(tmp_path / "repository")

    expected = projection(tmp_path / "in-memory", in_memory)
    actual = projection(tmp_path / "local", local)

    assert expected == actual
    assert expected == json.loads(EXPECTED.read_text(encoding="utf-8"))
    assert actual == json.loads(ACTUAL.read_text(encoding="utf-8"))
    assert expected["qualification"] == {
        "decision_grade_eligible": False,
        "deployment_authorized": False,
    }
    auditable = expected["auditable_runs"][0]
    assert auditable["distinct_attempt_ids"]
    assert auditable["distinct_evidence_manifest_hashes"]
    assert len(set(auditable["execution_result_hashes"])) == 1


def test_canonical_projection_reports_match(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"

    completed = _run(EXPECTED, ACTUAL, report_path)

    assert completed.returncode == 0, completed.stderr
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "completed"
    assert report["verdict"] == "MATCH"
    assert report["first_divergence"] is None
    assert report["comparison_counts"] == {
        "approved_change": 0,
        "matched": 8,
        "mismatched": 0,
    }
    assert not report["decision_grade_eligible"]
    assert not report["deployment_authorized"]


def test_stream_sequence_divergence_locates_first_event(tmp_path: Path) -> None:
    actual = json.loads(ACTUAL.read_text(encoding="utf-8"))
    actual["streams"][0]["event_ids"][0] = "mutated-event"
    actual_path = tmp_path / "actual.json"
    _write(actual_path, actual)
    report_path = tmp_path / "report.json"

    completed = _run(EXPECTED, actual_path, report_path, root=Path("/"))

    assert completed.returncode == 1
    divergence = json.loads(report_path.read_text(encoding="utf-8"))[
        "first_divergence"
    ]
    assert divergence["path"] == "/streams/0"
    assert divergence["reason"] == "sequence-item-mismatch"
    assert divergence["expected"]["stream_key"] == "bars.open"
    assert divergence["actual"]["event_ids"][0] == "mutated-event"


def test_timeline_and_execution_divergence_are_not_hidden(tmp_path: Path) -> None:
    timeline_actual = json.loads(ACTUAL.read_text(encoding="utf-8"))
    timeline_actual["timelines"][0]["segments"][0] = "mutated"
    timeline_path = tmp_path / "timeline.json"
    _write(timeline_path, timeline_actual)
    timeline_report = tmp_path / "timeline-report.json"

    timeline_completed = _run(
        EXPECTED, timeline_path, timeline_report, root=Path("/")
    )

    assert timeline_completed.returncode == 1
    assert json.loads(timeline_report.read_text(encoding="utf-8"))[
        "first_divergence"
    ]["path"] == "/timelines/0"

    execution_actual = json.loads(ACTUAL.read_text(encoding="utf-8"))
    execution_actual["executions"][0]["engine_result_hash"] = "sha256:" + "0" * 64
    execution_path = tmp_path / "execution.json"
    _write(execution_path, execution_actual)
    execution_report = tmp_path / "execution-report.json"

    execution_completed = _run(
        EXPECTED, execution_path, execution_report, root=Path("/")
    )

    assert execution_completed.returncode == 1
    assert json.loads(execution_report.read_text(encoding="utf-8"))[
        "first_divergence"
    ]["path"] == "/executions/0"


def test_unclassified_field_and_unsafe_path_fail_closed(tmp_path: Path) -> None:
    actual = json.loads(ACTUAL.read_text(encoding="utf-8"))
    actual["unclassified"] = True
    actual_path = tmp_path / "actual.json"
    _write(actual_path, actual)
    invalid_report = tmp_path / "invalid.json"

    invalid = _run(EXPECTED, actual_path, invalid_report, root=Path("/"))

    assert invalid.returncode == 2
    assert json.loads(invalid_report.read_text(encoding="utf-8"))["status"] == (
        "invalid-contract"
    )

    outside = tmp_path / "outside.json"
    outside.write_text(ACTUAL.read_text(encoding="utf-8"), encoding="utf-8")
    unsafe_report = tmp_path / "unsafe.json"
    unsafe = _run(EXPECTED, outside, unsafe_report)

    assert unsafe.returncode == 2
    blocked = json.loads(unsafe_report.read_text(encoding="utf-8"))
    assert blocked["status"] == "blocked"
    assert blocked["failure"]["code"] == "UNSAFE_PATH"
