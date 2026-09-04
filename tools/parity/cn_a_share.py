import hashlib
import json
from pathlib import Path, PurePosixPath
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import Any

from tools.migration.legacy_migration.parity import (
    ComparatorError,
    display,
    exact_equal,
    leaf_paths,
    pointer_get,
    read_json,
    run_comparison,
)
from tools.migration.legacy_migration.snapshots import sha256_file


LAYERS = (
    "00_CASE_INPUT",
    "01_CALENDAR_SESSION",
    "02_PRICE_LIMIT",
    "03_DECISION_BUDGETING",
    "04_ORDER_INTENT",
    "05_FEE_TAX",
    "06_SETTLEMENT_T1",
    "07_CORPORATE_ACTION",
    "08_ACCOUNTING_LEDGER",
    "09_FINAL_RESULT",
)
ROLES = ("LEGACY_CYCLE_ROTATION", "G08H_DEVELOPMENT_RUN")
PAIR_SPECS = (("LEGACY_TO_G08H", "LEGACY_CYCLE_ROTATION", "G08H_DEVELOPMENT_RUN"),)
COVERAGE_STATUSES = {"COMPARABLE", "NOT_COMPARABLE_LEGACY_SCOPE"}
LEGACY_SNAPSHOT_SHA256 = "1fea4f5a4ec8ab12ddb25c6c5bb525f91f8bac9e887f3e5b382b641a948c91c3"
LEGACY_CONTENT_TREE_SHA256 = "65f9812bd86241ac5fcfdfcca1cb8c28868edbdf007d747ecee8cc68ee20d089"


class CnAShareParityError(ValueError):
    def __init__(self, code: str, path: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.path = path
        self.message = message


def _object(value: Any, code: str, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CnAShareParityError(code, path, "expected object")
    return value


def _list(value: Any, code: str, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise CnAShareParityError(code, path, "expected list")
    return value


def _text(value: Any, code: str, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise CnAShareParityError(code, path, "expected non-empty string")
    return value


def _hash(value: Any, code: str, path: str) -> str:
    text = _text(value, code, path)
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise CnAShareParityError(code, path, "expected lowercase SHA-256")
    return text


def _canonical_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _safe_file(root: Path, value: Any, path: str) -> tuple[str, Path]:
    relative = _text(value, "UNSAFE_PATH", path)
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts or "\\" in relative or pure.as_posix() != relative:
        raise CnAShareParityError("UNSAFE_PATH", path, "path must be normalized and repo-relative")
    try:
        resolved = root.joinpath(*pure.parts).resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as error:
        raise CnAShareParityError("UNSAFE_PATH", path, "path escapes root or does not exist") from error
    if not resolved.is_file():
        raise CnAShareParityError("UNSAFE_PATH", path, "path must reference a file")
    return relative, resolved


def _load_plan(plan_path: Path) -> dict[str, Any]:
    try:
        plan = _object(read_json(plan_path), "INVALID_PLAN", "/")
    except ComparatorError as error:
        raise CnAShareParityError("INVALID_PLAN", error.path, error.message) from error
    expected = {"coverage", "decision_grade_eligible", "deployment_authorized", "id", "layer_order", "limitations", "pairs", "schema_version", "sources"}
    if set(plan) != expected or plan.get("schema_version") != 1:
        raise CnAShareParityError("INVALID_PLAN", "/", "invalid plan fields or schema")
    decision_grade_eligible = plan.get("decision_grade_eligible")
    deployment_authorized = plan.get("deployment_authorized")
    if (
        type(decision_grade_eligible) is not bool
        or decision_grade_eligible
        or type(deployment_authorized) is not bool
        or deployment_authorized
    ):
        raise CnAShareParityError("INVALID_PLAN", "/", "qualification flags must be false")
    _text(plan.get("id"), "INVALID_PLAN", "/id")
    limitations = _list(plan.get("limitations"), "INVALID_PLAN", "/limitations")
    if not limitations or limitations != sorted(set(limitations)) or not all(isinstance(value, str) and value for value in limitations):
        raise CnAShareParityError("INVALID_PLAN", "/limitations", "limitations must be sorted and unique")
    return plan


def _validate_paths(root: Path, plan: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    sources = [_object(value, "INVALID_PLAN", "/sources") for value in _list(plan["sources"], "INVALID_PLAN", "/sources")]
    pairs = [_object(value, "INVALID_PLAN", "/pairs") for value in _list(plan["pairs"], "INVALID_PLAN", "/pairs")]
    for index, source in enumerate(sources):
        if set(source) != {"content_tree_sha256", "projection", "projection_sha256", "role", "snapshot_sha256", "source_id"}:
            raise CnAShareParityError("INVALID_PLAN", f"/sources/{index}", "invalid source fields")
        source["projection"], source["_projection_path"] = _safe_file(root, source["projection"], f"/sources/{index}/projection")
    for index, pair in enumerate(pairs):
        if set(pair) != {"actual_role", "contract", "expected_role", "expected_verdict", "id", "migration_mode"}:
            raise CnAShareParityError("INVALID_PLAN", f"/pairs/{index}", "invalid pair fields")
        pair["contract"], pair["_contract_path"] = _safe_file(root, pair["contract"], f"/pairs/{index}/contract")
    return sources, pairs


def _validate_sources(sources: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    if [source.get("role") for source in sources] != list(ROLES):
        raise CnAShareParityError("SOURCE_ROLE_MISMATCH", "/sources", "source roles or order mismatch")
    for index, source in enumerate(sources):
        role = source.get("role", "UNKNOWN")
        snapshot = _hash(source.get("snapshot_sha256"), "SOURCE_SNAPSHOT_MISMATCH", f"/sources/{role}/snapshot_sha256")
        content = _hash(source.get("content_tree_sha256"), "SOURCE_SNAPSHOT_MISMATCH", f"/sources/{role}/content_tree_sha256")
        if index == 0 and (source.get("source_id") != "cycle-rotation-platform" or snapshot != LEGACY_SNAPSHOT_SHA256 or content != LEGACY_CONTENT_TREE_SHA256):
            raise CnAShareParityError("SOURCE_SNAPSHOT_MISMATCH", f"/sources/{role}/snapshot_sha256", "legacy snapshot identity mismatch")
        expected = _hash(source.get("projection_sha256"), "SOURCE_SNAPSHOT_MISMATCH", f"/sources/{role}/projection_sha256")
        if sha256_file(source["_projection_path"]) != expected:
            raise CnAShareParityError("SOURCE_SNAPSHOT_MISMATCH", f"/sources/{role}/projection_sha256", "projection hash mismatch")
        _text(source.get("source_id"), "SOURCE_SNAPSHOT_MISMATCH", f"/sources/{role}/source_id")
    return {source["role"]: source for source in sources}


def _load_projections(sources: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    projections: dict[str, dict[str, Any]] = {}
    for source in sources:
        try:
            projection = _object(read_json(source["_projection_path"]), "SOURCE_ROLE_MISMATCH", "/projection")
        except ComparatorError as error:
            raise CnAShareParityError("SOURCE_ROLE_MISMATCH", error.path, error.message) from error
        if set(projection) != {"case_id", "layers", "projection_id", "schema_version", "source_role"} or projection.get("schema_version") != 1 or projection.get("source_role") != source["role"]:
            raise CnAShareParityError("SOURCE_ROLE_MISMATCH", f"/sources/{source['role']}/projection", "invalid projection schema or role")
        projections[source["role"]] = projection
    return projections


def _validate_pairs(pairs: list[dict[str, Any]], projections: dict[str, dict[str, Any]]) -> None:
    if [(pair.get("id"), pair.get("expected_role"), pair.get("actual_role")) for pair in pairs] != list(PAIR_SPECS):
        raise CnAShareParityError("PAIR_IDENTITY_MISMATCH", "/pairs", "pair identities or order mismatch")
    if len({projection.get("case_id") for projection in projections.values()}) != 1:
        raise CnAShareParityError("PAIR_IDENTITY_MISMATCH", "/sources", "projection case identities differ")
    if any(pair.get("migration_mode") != "copy_with_parity" or pair.get("expected_verdict") not in {"MATCH", "MISMATCH"} for pair in pairs):
        raise CnAShareParityError("PAIR_IDENTITY_MISMATCH", "/pairs", "invalid migration mode or expected verdict")


def _validate_layers(plan: dict[str, Any], projections: dict[str, dict[str, Any]]) -> None:
    if plan.get("layer_order") != list(LAYERS):
        raise CnAShareParityError("LAYER_ORDER_MISMATCH", "/layer_order", "layer order mismatch")
    expected = {"00_CASE_INPUT", "03_DECISION_BUDGETING", "04_ORDER_INTENT"}
    for role, projection in projections.items():
        layers = _object(projection.get("layers"), "LAYER_ORDER_MISMATCH", f"/{role}/layers")
        if set(layers) != expected:
            raise CnAShareParityError("LAYER_ORDER_MISMATCH", f"/{role}/layers", "projection layer coverage mismatch")


def _validate_coverage(plan: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    rows = [_object(value, "COVERAGE_INCOMPLETE", "/coverage") for value in _list(plan["coverage"], "COVERAGE_INCOMPLETE", "/coverage")]
    expected_keys = [(pair[0], layer) for pair in PAIR_SPECS for layer in LAYERS]
    if [(row.get("pair"), row.get("layer")) for row in rows] != expected_keys:
        raise CnAShareParityError("COVERAGE_INCOMPLETE", "/coverage", "coverage rows must exact-cover pair-layer order")
    for index, row in enumerate(rows):
        if set(row) != {"evidence_refs", "layer", "pair", "reason", "status"} or row.get("status") not in COVERAGE_STATUSES:
            raise CnAShareParityError("COVERAGE_INCOMPLETE", f"/coverage/{index}", "invalid coverage row")
        evidence = _list(row.get("evidence_refs"), "COVERAGE_INCOMPLETE", f"/coverage/{index}/evidence_refs")
        if not evidence or evidence != sorted(set(evidence)) or not all(isinstance(value, str) and value for value in evidence):
            raise CnAShareParityError("COVERAGE_INCOMPLETE", f"/coverage/{index}/evidence_refs", "evidence refs must be sorted and unique")
        _text(row.get("reason"), "COVERAGE_INCOMPLETE", f"/coverage/{index}/reason")
    return {(row["pair"], row["layer"]): row for row in rows}


def _contract_layers(root: Path, pair: dict[str, Any]) -> set[str]:
    del root
    try:
        contract = _object(read_json(pair["_contract_path"]), "COMPARATOR_BLOCKED", "/")
    except ComparatorError as error:
        raise CnAShareParityError("COMPARATOR_BLOCKED", error.path, error.message) from error
    rules = [_object(value, "COMPARATOR_BLOCKED", "/rules") for value in _list(contract.get("rules"), "COMPARATOR_BLOCKED", "/rules")]
    return {layer for rule in rules for layer in LAYERS if rule.get("path") == f"/layers/{layer}" or str(rule.get("path", "")).startswith(f"/layers/{layer}/")}


def _validate_rule_coverage(root: Path, pairs: list[dict[str, Any]], coverage: dict[tuple[str, str], dict[str, Any]]) -> None:
    for pair in pairs:
        contract_layers = _contract_layers(root, pair)
        comparable = {layer for layer in LAYERS if coverage[(pair["id"], layer)]["status"] == "COMPARABLE"}
        extra = contract_layers - comparable
        if extra:
            layer = min(extra, key=LAYERS.index)
            raise CnAShareParityError("NOT_COMPARABLE_RULE_CONFLICT", f"/{pair['id']}/{layer}", "not-comparable layer has a rule")
        missing = comparable - contract_layers
        if missing:
            layer = min(missing, key=LAYERS.index)
            raise CnAShareParityError("COMPARABLE_RULE_MISSING", f"/{pair['id']}/{layer}", "comparable layer lacks a rule")


def _filtered_projection(projection: dict[str, Any], pair_id: str, coverage: dict[tuple[str, str], dict[str, Any]]) -> dict[str, Any]:
    return {"case_id": projection["case_id"], "layers": {layer: projection["layers"][layer] for layer in LAYERS if coverage[(pair_id, layer)]["status"] == "COMPARABLE"}}


def _temporary_json(directory: str, value: object) -> Path:
    with NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".json",
        dir=directory,
        delete=False,
    ) as stream:
        stream.write(
            json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
        )
        return Path(stream.name)


def _exact_leaf_divergence(expected: Any, actual: Any, path: str) -> dict[str, Any]:
    relative = next(
        value
        for value in sorted(leaf_paths(expected) | leaf_paths(actual))
        if not exact_equal(pointer_get(expected, value), pointer_get(actual, value))
    )
    return {
        "actual": display(pointer_get(actual, relative)),
        "comparison": "exact",
        "expected": display(pointer_get(expected, relative)),
        "path": path + ("" if relative == "/" else relative),
        "reason": "exact-mismatch",
    }


def _run_pair(root: Path, pair: dict[str, Any], projections: dict[str, dict[str, Any]], sources: dict[str, dict[str, Any]], coverage: dict[tuple[str, str], dict[str, Any]]) -> dict[str, Any]:
    expected = _filtered_projection(projections[pair["expected_role"]], pair["id"], coverage)
    actual = _filtered_projection(projections[pair["actual_role"]], pair["id"], coverage)
    try:
        with TemporaryDirectory() as directory:
            expected_path = _temporary_json(directory, expected)
            actual_path = _temporary_json(directory, actual)
            report, _ = run_comparison(
                root,
                pair["_contract_path"],
                expected_path,
                actual_path,
                pair["migration_mode"],
            )
    except (ComparatorError, OSError, UnicodeError, TypeError) as error:
        if isinstance(error, ComparatorError):
            raise CnAShareParityError("COMPARATOR_BLOCKED", error.path, error.message) from error
        raise CnAShareParityError("COMPARATOR_BLOCKED", f"/pairs/{pair['id']}", str(error)) from error
    first_divergence = report["first_divergence"]
    if first_divergence is not None and first_divergence.get("reason") == "sequence-item-mismatch":
        first_divergence = _exact_leaf_divergence(first_divergence["expected"], first_divergence["actual"], first_divergence["path"])
    return {
        "actual_comparable_sha256": report["actual_sha256"],
        "actual_projection_sha256": sources[pair["actual_role"]]["projection_sha256"],
        "actual_role": pair["actual_role"], "comparison_counts": report["comparison_counts"],
        "contract_id": report["contract_id"], "contract_sha256": report["contract_sha256"],
        "expected_comparable_sha256": report["expected_sha256"],
        "expected_projection_sha256": sources[pair["expected_role"]]["projection_sha256"],
        "expected_role": pair["expected_role"], "first_divergence": first_divergence,
        "id": pair["id"], "migration_mode": pair["migration_mode"], "verdict": report["verdict"],
    }


def run_plan(root: Path, plan_path: Path) -> dict[str, Any]:
    root = root.resolve()
    try:
        plan_resolved = plan_path.resolve(strict=True); plan_resolved.relative_to(root)
    except (OSError, ValueError) as error:
        raise CnAShareParityError("UNSAFE_PATH", "/plan", "plan must be inside root") from error
    plan = _load_plan(plan_resolved)
    sources_list, pairs = _validate_paths(root, plan)
    sources = _validate_sources(sources_list)
    projections = _load_projections(sources_list)
    _validate_pairs(pairs, projections); _validate_layers(plan, projections)
    coverage = _validate_coverage(plan); _validate_rule_coverage(root, pairs, coverage)
    pair_reports = [_run_pair(root, pair, projections, sources, coverage) for pair in pairs]
    for index, pair in enumerate(pairs):
        if pair_reports[index]["verdict"] != pair["expected_verdict"]:
            raise CnAShareParityError("EXPECTED_VERDICT_MISMATCH", f"/pairs/{index}/expected_verdict", f"expected {pair['expected_verdict']}, got {pair_reports[index]['verdict']}")
    coverage_rows = plan["coverage"]
    coverage_complete = all(row["status"] == "COMPARABLE" for row in coverage_rows)
    first_uncovered = next(({"pair": row["pair"], "layer": row["layer"], "status": row["status"]} for row in coverage_rows if row["status"] != "COMPARABLE"), None)
    first_divergence = next(({"pair": value["id"], **value["first_divergence"]} for value in pair_reports if value["first_divergence"] is not None), None)
    pair_verdicts = {value["verdict"] for value in pair_reports}
    aggregate = "MISMATCH" if "MISMATCH" in pair_verdicts else ("MATCH" if coverage_complete else "NOT_COMPARABLE_LEGACY_SCOPE")
    counts = {key: sum(value["comparison_counts"][key] for value in pair_reports) for key in ("approved_change", "matched", "mismatched")}
    report: dict[str, Any] = {
        "comparison_counts": counts, "comparison_verdict": aggregate, "coverage": coverage_rows,
        "coverage_complete": coverage_complete, "decision_grade_eligible": False,
        "deployment_authorized": False, "first_divergence": first_divergence,
        "first_uncovered_layer": first_uncovered, "limitations": plan["limitations"],
        "pair_reports": pair_reports, "plan_id": plan["id"], "plan_sha256": sha256_file(plan_resolved),
        "report_id": "cn-a-share-g08h-parity-report-v1", "schema_version": 1,
        "source_manifest": [{key: source[key] for key in ("content_tree_sha256", "projection", "projection_sha256", "role", "snapshot_sha256", "source_id")} for source in sources_list],
        "status": "completed",
    }
    report["report_hash"] = _canonical_hash(report)
    return report


def blocked_report(plan_path: Path, error: CnAShareParityError) -> dict[str, Any]:
    try:
        plan_sha256 = sha256_file(plan_path) if plan_path.is_file() else None
    except OSError:
        plan_sha256 = None
    report: dict[str, Any] = {
        "decision_grade_eligible": False, "deployment_authorized": False,
        "failure": {"code": error.code, "message": error.message, "path": error.path},
        "plan_sha256": plan_sha256, "report_id": "cn-a-share-g08h-parity-report-v1",
        "schema_version": 1, "status": "blocked",
    }
    report["report_hash"] = _canonical_hash(report)
    return report


__all__ = ["CnAShareParityError", "run_plan", "blocked_report"]
