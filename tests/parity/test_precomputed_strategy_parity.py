from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from tests.parity._precomputed_strategy_fixtures import (
    dual_entry_projections,
    entry_only_keys,
)


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "tools/parity/run_precomputed_strategy_parity.py"
CONTRACT = ROOT / "tests/parity/contracts/precomputed-strategy-g11j-v1.json"
FIXTURES = ROOT / "tests/parity/fixtures/precomputed-strategy-g11j-v1"
EXPECTED = FIXTURES / "expected.json"
ACTUAL = FIXTURES / "actual.json"
SIDECAR = FIXTURES / "sidecar.json"
LAYERS = (
    "00_NORMALIZED_ENTRY",
    "01_DECISION_BATCH",
    "02_ALLOCATION",
    "03_PORTFOLIO_RISK",
    "04_NORMALIZED_ACTIVE_TARGET",
    "05_ORDER_PLAN_INTENT",
    "06_ORDER_EVENT",
    "07_FILL",
    "08_SLIPPAGE",
    "09_FEE",
    "10_FINANCIAL_ARTIFACT",
    "11_JOURNAL",
    "12_LEDGER",
    "13_FINAL_SNAPSHOT",
    "14_RUN_END",
    "15_TRACE",
    "16_EXECUTION_RESULT_HASH",
)
LAYER_CASES = tuple(
    (layer, f"/layers/{layer}" + ("/0" if 1 <= index <= 11 else ""))
    for index, layer in enumerate(LAYERS)
)


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
            str(RUNNER),
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


def _write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _stage(
    root: Path,
    *,
    contract_payload: object | None = None,
    actual_payload: object | None = None,
) -> tuple[Path, Path, Path, Path]:
    root.mkdir(parents=True)
    contract = root / "contract.json"
    expected = root / "expected.json"
    actual = root / "actual.json"
    report = root / "report.json"
    if contract_payload is None:
        contract.write_bytes(CONTRACT.read_bytes())
    else:
        _write(contract, contract_payload)
    expected.write_bytes(EXPECTED.read_bytes())
    if actual_payload is None:
        actual.write_bytes(ACTUAL.read_bytes())
    else:
        _write(actual, actual_payload)
    return contract, expected, actual, report


def _mutate_layer(projection: dict[str, Any], layer: str) -> None:
    value = projection["layers"][layer]
    if isinstance(value, list):
        value[0] = {"mutated": layer}
    else:
        projection["layers"][layer] = {"mutated": layer}


def test_dual_entries_generate_exact_static_economic_projections(
    tmp_path: Path,
) -> None:
    expected, actual, sidecar = dual_entry_projections(tmp_path / "auditable")

    assert expected == actual
    assert expected == json.loads(EXPECTED.read_text(encoding="utf-8"))
    assert actual == json.loads(ACTUAL.read_text(encoding="utf-8"))
    assert sidecar == json.loads(SIDECAR.read_text(encoding="utf-8"))
    projected: Any = expected
    normalized_decision = projected["layers"]["00_NORMALIZED_ENTRY"][
        "validated_decisions"
    ][0]
    assert normalized_decision["confidence"] == {
        "basis": "confidence",
        "scale": 12,
        "type": "rate",
        "units": 10**12,
    }
    assert normalized_decision["reason"] == "engine fixture scheduled rebalance"
    assert normalized_decision["evidence"] == {
        "model_revision": "sha256:model-engine-v1"
    }
    assert {
        name: set(values)
        for name, values in sidecar["entry_evidence"].items()
    } == entry_only_keys()
    entry_evidence = sidecar["entry_evidence"]
    assert entry_evidence["precomputed"]["decision_batch_id"].startswith(
        "decision-batch-v1:"
    )
    assert entry_evidence["strategy"]["decision_batch_id"].startswith(
        "decision-batch-v2:"
    )
    assert (
        entry_evidence["precomputed"]["decision_batch_id"]
        != entry_evidence["strategy"]["decision_batch_id"]
    )
    assert (
        entry_evidence["precomputed"]["decision_batch_hash"]
        != entry_evidence["strategy"]["decision_batch_hash"]
    )
    normalized_entry = json.dumps(projected["layers"]["00_NORMALIZED_ENTRY"])
    for evidence in entry_evidence.values():
        assert evidence["decision_batch_id"] not in normalized_entry
        assert evidence["decision_batch_hash"] not in normalized_entry

    g07 = sidecar["g07"]
    assert len(set(g07["attempt_ids"])) == 2
    assert len(set(g07["evidence_manifest_hashes"])) == 2
    assert len(set(g07["semantic_run_ids"])) == 1
    assert len(set(g07["execution_case_hashes"])) == 1
    assert len(set(g07["execution_result_hashes"])) == 1


def test_static_projection_reports_match(tmp_path: Path) -> None:
    root = tmp_path / "evidence"
    contract, expected, actual, report_path = _stage(root)

    completed = _run(root, contract, expected, actual, report_path)

    assert completed.returncode == 0, completed.stderr
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "completed"
    assert report["verdict"] == "MATCH"
    assert report["first_divergence"] is None
    assert report["comparison_counts"] == {
        "approved_change": 0,
        "matched": 20,
        "mismatched": 0,
    }
    assert not report["decision_grade_eligible"]
    assert not report["deployment_authorized"]


@pytest.mark.parametrize(("layer", "divergence_path"), LAYER_CASES)
def test_each_layer_mutation_is_reported(
    tmp_path: Path,
    layer: str,
    divergence_path: str,
) -> None:
    projection = json.loads(ACTUAL.read_text(encoding="utf-8"))
    _mutate_layer(projection, layer)
    root = tmp_path / "evidence"
    contract, expected, actual, report_path = _stage(
        root, actual_payload=projection
    )

    completed = _run(root, contract, expected, actual, report_path)

    assert completed.returncode == 1
    divergence = json.loads(report_path.read_text(encoding="utf-8"))[
        "first_divergence"
    ]
    assert divergence["path"] == divergence_path


@pytest.mark.parametrize(
    ("earlier", "later", "divergence_path"),
    tuple(
        (earlier, later, LAYER_CASES[index][1])
        for index, (earlier, later) in enumerate(zip(LAYERS, LAYERS[1:]))
    ),
)
def test_first_divergence_is_earliest_layer(
    tmp_path: Path,
    earlier: str,
    later: str,
    divergence_path: str,
) -> None:
    projection = json.loads(ACTUAL.read_text(encoding="utf-8"))
    _mutate_layer(projection, later)
    _mutate_layer(projection, earlier)
    root = tmp_path / "evidence"
    contract, expected, actual, report_path = _stage(
        root, actual_payload=projection
    )

    completed = _run(root, contract, expected, actual, report_path)

    assert completed.returncode == 1
    assert json.loads(report_path.read_text(encoding="utf-8"))[
        "first_divergence"
    ]["path"] == divergence_path


@pytest.mark.parametrize("layer", LAYERS)
def test_frozen_contract_rejects_each_missing_layer(
    tmp_path: Path,
    layer: str,
) -> None:
    contract_payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    missing_path = f"/layers/{layer}"
    contract_payload["rules"] = [
        rule for rule in contract_payload["rules"] if rule["path"] != missing_path
    ]
    root = tmp_path / "evidence"
    contract, expected, actual, report_path = _stage(
        root, contract_payload=contract_payload
    )

    completed = _run(root, contract, expected, actual, report_path)

    assert completed.returncode == 2
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "invalid-contract"
    assert report["first_divergence"]["path"] == missing_path
    assert report["first_divergence"]["reason"] == "invalid-comparator-contract"


@pytest.mark.parametrize(
    ("mutation", "failure_path"),
    (
        ("substitute", "/id"),
        ("explicit_tolerance", "/layers/12_LEDGER"),
        ("quantized", "/layers/12_LEDGER"),
        ("approved_change", "/layers/12_LEDGER"),
    ),
)
def test_frozen_contract_rejects_substitutes_and_non_exact_rules(
    tmp_path: Path,
    mutation: str,
    failure_path: str,
) -> None:
    contract_payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    if mutation == "substitute":
        contract_payload["id"] = "substitute-g11j-contract"
    else:
        rule = next(
            rule
            for rule in contract_payload["rules"]
            if rule["path"] == "/layers/12_LEDGER"
        )
        rule["comparison"] = mutation
        if mutation == "explicit_tolerance":
            rule["absolute_tolerance"] = "0"
        elif mutation == "quantized":
            rule["quantum"] = "1"
            rule["rounding"] = "ROUND_HALF_EVEN"
        else:
            rule["reference"] = "docs/adr/g11j-runner-test.md"
    root = tmp_path / "evidence"
    contract, expected, actual, report_path = _stage(
        root, contract_payload=contract_payload
    )
    if mutation == "approved_change":
        reference = root / "docs/adr/g11j-runner-test.md"
        reference.parent.mkdir(parents=True)
        reference.write_text("# test-only reference\n", encoding="utf-8")

    completed = _run(root, contract, expected, actual, report_path)

    assert completed.returncode == 2
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "invalid-contract"
    assert report["first_divergence"]["path"] == failure_path
    assert report["first_divergence"]["reason"] == "invalid-comparator-contract"


def test_unclassified_field_fails_closed(tmp_path: Path) -> None:
    projection = json.loads(ACTUAL.read_text(encoding="utf-8"))
    projection["unclassified"] = True
    root = tmp_path / "evidence"
    contract, expected, actual, report_path = _stage(
        root, actual_payload=projection
    )

    completed = _run(root, contract, expected, actual, report_path)

    assert completed.returncode == 2
    blocked = json.loads(report_path.read_text(encoding="utf-8"))
    assert blocked["status"] == "invalid-contract"
    assert blocked["verdict"] == "BLOCKED"


@pytest.mark.parametrize("name", ("contract", "expected", "actual", "report"))
def test_every_evidence_path_must_be_inside_root(
    tmp_path: Path,
    name: str,
) -> None:
    root = tmp_path / "evidence"
    contract, expected, actual, report = _stage(root)
    paths = {
        "contract": contract,
        "expected": expected,
        "actual": actual,
        "report": report,
    }
    outside = tmp_path / f"outside-{name}.json"
    if name != "report":
        outside.write_bytes(paths[name].read_bytes())
    paths[name] = outside

    completed = _run(
        root,
        paths["contract"],
        paths["expected"],
        paths["actual"],
        paths["report"],
    )

    assert completed.returncode == 2
    assert f"UNSAFE_PATH: /{name}:" in completed.stderr
    if name == "report":
        assert not outside.exists()
    else:
        blocked = json.loads(report.read_text(encoding="utf-8"))
        assert blocked["status"] == "blocked"
        assert blocked["failure"]["code"] == "UNSAFE_PATH"


@pytest.mark.parametrize("name", ("contract", "expected", "actual"))
def test_report_must_not_alias_an_input(tmp_path: Path, name: str) -> None:
    root = tmp_path / "evidence"
    contract, expected, actual, _ = _stage(root)
    paths = {"contract": contract, "expected": expected, "actual": actual}
    report = paths[name]
    original = report.read_bytes()

    completed = _run(root, contract, expected, actual, report)

    assert completed.returncode == 2
    assert "UNSAFE_PATH: /report:" in completed.stderr
    assert report.read_bytes() == original


def test_root_must_be_a_real_directory(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence"
    contract, expected, actual, report = _stage(evidence)
    missing_root = tmp_path / "missing"

    completed = _run(missing_root, contract, expected, actual, report)

    assert completed.returncode == 2
    assert "UNSAFE_PATH: /root:" in completed.stderr
    assert not report.exists()
