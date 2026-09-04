from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import Any

from legacy_migration.parity import ComparatorError, load_contract, read_json, run_comparison
from legacy_migration.snapshots import sha256_file


LAYERS = (
    "SOURCE_IDENTITY",
    "DECISION",
    "ORDER_INTENT",
    "ORDER_EVENT",
    "FILL",
    "FEE",
    "POSITION_PNL",
    "FUNDING",
    "JOURNAL_LEDGER",
    "MARGIN_SNAPSHOT",
    "LIQUIDATION_AUDIT",
    "LIQUIDATION_EXECUTION",
    "FINAL_RESULT",
)
ROLES = (
    "LEGACY_CRYPT_GEMINI",
    "G10G_DEVELOPMENT_RUN",
    "BINANCE_ACCOUNT_RECORDS",
)
PAIR_SPECS = (
    ("LEGACY_TO_G10G", "LEGACY_CRYPT_GEMINI", "G10G_DEVELOPMENT_RUN"),
    ("BINANCE_TO_G10G", "BINANCE_ACCOUNT_RECORDS", "G10G_DEVELOPMENT_RUN"),
)
COVERAGE_STATUSES = {
    "COMPARABLE",
    "NOT_COMPARABLE_LEGACY_SCOPE",
    "NOT_COMPARABLE_PROVIDER_EVIDENCE",
    "NOT_COMPARABLE_ARCHIVE_COMPLETENESS",
}
LEGACY_SNAPSHOT_SHA256 = "d6e6feca46b61586e890a441443738dc9e911a58428c940e86055459361eda80"
LEGACY_CONTENT_TREE_SHA256 = "704dee87020ad119e417fbec3831875f8203787ba06206f625a07e2414a068bb"


class G10HParityError(ValueError):
    def __init__(self, code: str, path: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.path = path
        self.message = message


def _object(value: Any, code: str, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise G10HParityError(code, path, "expected object")
    return value


def _list(value: Any, code: str, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise G10HParityError(code, path, "expected list")
    return value


def _text(value: Any, code: str, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise G10HParityError(code, path, "expected non-empty string")
    return value


def _hash(value: Any, code: str, path: str) -> str:
    text = _text(value, code, path)
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise G10HParityError(code, path, "expected lowercase SHA-256")
    return text


def _canonical_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _safe_file(root: Path, value: Any, path: str) -> tuple[str, Path]:
    relative = _text(value, "UNSAFE_PATH", path)
    pure = PurePosixPath(relative)
    if (
        pure.is_absolute()
        or ".." in pure.parts
        or "\\" in relative
        or pure.as_posix() != relative
    ):
        raise G10HParityError("UNSAFE_PATH", path, "path must be normalized and repo-relative")
    candidate = root.joinpath(*pure.parts)
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as error:
        raise G10HParityError("UNSAFE_PATH", path, "path escapes root or does not exist") from error
    if not resolved.is_file():
        raise G10HParityError("UNSAFE_PATH", path, "path must reference a file")
    return relative, resolved


def _load_plan(plan_path: Path) -> dict[str, Any]:
    try:
        plan = read_json(plan_path)
    except ComparatorError as error:
        raise G10HParityError("INVALID_PLAN", error.path, error.message) from error
    plan = _object(plan, "INVALID_PLAN", "/")
    expected = {
        "coverage",
        "decision_grade_eligible",
        "deployment_authorized",
        "id",
        "layer_order",
        "limitations",
        "pairs",
        "schema_version",
        "sources",
    }
    if set(plan) != expected or plan.get("schema_version") != 1:
        raise G10HParityError("INVALID_PLAN", "/", "invalid plan fields or schema")
    if (
        type(plan.get("decision_grade_eligible")) is not bool
        or plan["decision_grade_eligible"]
        or type(plan.get("deployment_authorized")) is not bool
        or plan["deployment_authorized"]
    ):
        raise G10HParityError("INVALID_PLAN", "/", "qualification flags must be false")
    _text(plan.get("id"), "INVALID_PLAN", "/id")
    limitations = _list(plan.get("limitations"), "INVALID_PLAN", "/limitations")
    if not limitations or limitations != sorted(set(limitations)) or not all(
        isinstance(value, str) and value for value in limitations
    ):
        raise G10HParityError("INVALID_PLAN", "/limitations", "limitations must be sorted and unique")
    return plan


def _validate_paths(
    root: Path, plan: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    sources = [_object(value, "INVALID_PLAN", "/sources") for value in _list(plan["sources"], "INVALID_PLAN", "/sources")]
    pairs = [_object(value, "INVALID_PLAN", "/pairs") for value in _list(plan["pairs"], "INVALID_PLAN", "/pairs")]
    for index, source in enumerate(sources):
        if set(source) != {
            "content_tree_sha256",
            "projection",
            "projection_sha256",
            "role",
            "snapshot_sha256",
            "source_id",
        }:
            raise G10HParityError("INVALID_PLAN", f"/sources/{index}", "invalid source fields")
        relative, resolved = _safe_file(root, source["projection"], f"/sources/{index}/projection")
        source["projection"] = relative
        source["_projection_path"] = resolved
    for index, pair in enumerate(pairs):
        if set(pair) != {
            "actual_role",
            "contract",
            "expected_role",
            "expected_verdict",
            "id",
            "migration_mode",
        }:
            raise G10HParityError("INVALID_PLAN", f"/pairs/{index}", "invalid pair fields")
        relative, resolved = _safe_file(root, pair["contract"], f"/pairs/{index}/contract")
        pair["contract"] = relative
        pair["_contract_path"] = resolved
    return sources, pairs


def _validate_sources(sources: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    legacy = sources[0] if sources else {}
    if (
        legacy.get("source_id") != "crypt-gemini"
        or legacy.get("snapshot_sha256") != LEGACY_SNAPSHOT_SHA256
        or legacy.get("content_tree_sha256") != LEGACY_CONTENT_TREE_SHA256
    ):
        raise G10HParityError("SOURCE_SNAPSHOT_MISMATCH", "/sources/0", "legacy snapshot identity mismatch")
    for index, source in enumerate(sources):
        _text(source.get("source_id"), "SOURCE_SNAPSHOT_MISMATCH", f"/sources/{index}/source_id")
        _hash(source.get("snapshot_sha256"), "SOURCE_SNAPSHOT_MISMATCH", f"/sources/{index}/snapshot_sha256")
        _hash(source.get("content_tree_sha256"), "SOURCE_SNAPSHOT_MISMATCH", f"/sources/{index}/content_tree_sha256")
        expected = _hash(source.get("projection_sha256"), "SOURCE_SNAPSHOT_MISMATCH", f"/sources/{index}/projection_sha256")
        if sha256_file(source["_projection_path"]) != expected:
            raise G10HParityError("SOURCE_SNAPSHOT_MISMATCH", f"/sources/{index}/projection_sha256", "projection hash mismatch")
    if [source.get("role") for source in sources] != list(ROLES):
        raise G10HParityError("SOURCE_ROLE_MISMATCH", "/sources", "source roles or order mismatch")
    return {source["role"]: source for source in sources}


def _load_projections(sources: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    projections: dict[str, dict[str, Any]] = {}
    for index, source in enumerate(sources):
        try:
            projection = read_json(source["_projection_path"])
        except ComparatorError as error:
            raise G10HParityError("SOURCE_ROLE_MISMATCH", error.path, error.message) from error
        projection = _object(projection, "SOURCE_ROLE_MISMATCH", f"/sources/{index}/projection")
        if set(projection) != {"case_id", "layers", "projection_id", "schema_version", "source_role"} or projection.get("schema_version") != 1:
            raise G10HParityError("SOURCE_ROLE_MISMATCH", f"/sources/{index}/projection", "invalid projection schema")
        if projection.get("source_role") != source["role"]:
            raise G10HParityError("SOURCE_ROLE_MISMATCH", f"/sources/{index}/projection/source_role", "projection role mismatch")
        _text(projection.get("projection_id"), "SOURCE_ROLE_MISMATCH", f"/sources/{index}/projection/projection_id")
        projections[source["role"]] = projection
    return projections


def _validate_pairs(pairs: list[dict[str, Any]], projections: dict[str, dict[str, Any]]) -> None:
    if [
        (pair.get("id"), pair.get("expected_role"), pair.get("actual_role"))
        for pair in pairs
    ] != list(PAIR_SPECS):
        raise G10HParityError("PAIR_IDENTITY_MISMATCH", "/pairs", "pair identities or order mismatch")
    case_ids = {
        _text(projection.get("case_id"), "PAIR_IDENTITY_MISMATCH", "/case_id")
        for projection in projections.values()
    }
    if len(case_ids) != 1:
        raise G10HParityError("PAIR_IDENTITY_MISMATCH", "/sources", "projection case identities differ")
    if any(pair.get("expected_verdict") not in {"MATCH", "MISMATCH", "APPROVED_CHANGE", "NOT_COMPARABLE"} for pair in pairs):
        raise G10HParityError("PAIR_IDENTITY_MISMATCH", "/pairs", "invalid expected verdict")


def _layer_key(layer: str) -> str:
    return f"{LAYERS.index(layer):02d}_{layer}"


def _validate_layers(plan: dict[str, Any], projections: dict[str, dict[str, Any]]) -> None:
    if plan.get("layer_order") != list(LAYERS):
        raise G10HParityError("LAYER_ORDER_MISMATCH", "/layer_order", "layer order mismatch")
    expected_keys = {_layer_key(layer) for layer in LAYERS}
    for role, projection in projections.items():
        layers = _object(projection.get("layers"), "LAYER_ORDER_MISMATCH", f"/{role}/layers")
        if set(layers) != expected_keys:
            raise G10HParityError("LAYER_ORDER_MISMATCH", f"/{role}/layers", "projection layer coverage mismatch")


def _validate_coverage(plan: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    rows = [_object(value, "COVERAGE_MISMATCH", "/coverage") for value in _list(plan["coverage"], "COVERAGE_MISMATCH", "/coverage")]
    expected_keys = [(pair[0], layer) for pair in PAIR_SPECS for layer in LAYERS]
    actual_keys = [(row.get("pair"), row.get("layer")) for row in rows]
    if actual_keys != expected_keys:
        raise G10HParityError("COVERAGE_MISMATCH", "/coverage", "coverage rows must exact-cover pair-layer order")
    for index, row in enumerate(rows):
        if set(row) != {"evidence_refs", "layer", "pair", "reason", "status"}:
            raise G10HParityError("COVERAGE_MISMATCH", f"/coverage/{index}", "invalid coverage fields")
        if row.get("status") not in COVERAGE_STATUSES:
            raise G10HParityError("COVERAGE_MISMATCH", f"/coverage/{index}/status", "invalid coverage status")
        _text(row.get("reason"), "COVERAGE_MISMATCH", f"/coverage/{index}/reason")
        evidence = _list(row.get("evidence_refs"), "COVERAGE_MISMATCH", f"/coverage/{index}/evidence_refs")
        if not evidence or evidence != sorted(set(evidence)) or not all(isinstance(value, str) and value for value in evidence):
            raise G10HParityError("COVERAGE_MISMATCH", f"/coverage/{index}/evidence_refs", "evidence refs must be sorted and unique")
    return {(row["pair"], row["layer"]): row for row in rows}


def _contract_layers(root: Path, pair: dict[str, Any]) -> set[str]:
    try:
        contract = load_contract(pair["_contract_path"], root)
    except ComparatorError as error:
        raise G10HParityError("COMPARATOR_BLOCKED", error.path, error.message) from error
    result: set[str] = set()
    for rule in contract.rules:
        for layer in LAYERS:
            prefix = f"/layers/{_layer_key(layer)}"
            if rule.path == prefix or rule.path.startswith(prefix + "/"):
                result.add(layer)
    return result


def _validate_rule_coverage(
    root: Path,
    pairs: list[dict[str, Any]],
    coverage: dict[tuple[str, str], dict[str, Any]],
) -> None:
    for pair in pairs:
        contract_layers = _contract_layers(root, pair)
        comparable = {
            layer
            for layer in LAYERS
            if coverage[(pair["id"], layer)]["status"] == "COMPARABLE"
        }
        extra = contract_layers - comparable
        if extra:
            layer = min(extra, key=LAYERS.index)
            raise G10HParityError("NOT_COMPARABLE_RULE_CONFLICT", f"/{pair['id']}/{layer}", "not-comparable layer has a rule")
        missing = comparable - contract_layers
        if missing:
            layer = min(missing, key=LAYERS.index)
            raise G10HParityError("COMPARABLE_RULE_MISSING", f"/{pair['id']}/{layer}", "comparable layer lacks a rule")


def _validate_provider_identity(projection: dict[str, Any]) -> None:
    layers = projection["layers"]
    fills = layers[_layer_key("FILL")]
    if not isinstance(fills, list):
        raise G10HParityError("PROVIDER_IDENTITY_CONFLICT", "/layers/04_FILL", "provider fills must be a list")
    required_fill_fields = {
        "account_id",
        "commission",
        "commission_asset",
        "maker",
        "order_id",
        "position_side",
        "price",
        "quantity",
        "quote_quantity",
        "realized_pnl",
        "side",
        "symbol",
        "trade_id",
        "trade_time",
    }
    identities: list[tuple[Any, Any, Any]] = []
    fills_by_trade: dict[Any, dict[str, Any]] = {}
    for index, value in enumerate(fills):
        row = _object(value, "PROVIDER_IDENTITY_CONFLICT", f"/layers/04_FILL/{index}")
        if set(row) != required_fill_fields:
            raise G10HParityError("PROVIDER_IDENTITY_CONFLICT", f"/layers/04_FILL/{index}", "provider fill fields are incomplete")
        identity = (row["account_id"], row["symbol"], row["trade_id"])
        identities.append(identity)
        fills_by_trade[row["trade_id"]] = row
    if len(identities) != len(set(identities)):
        raise G10HParityError("PROVIDER_IDENTITY_CONFLICT", "/layers/04_FILL", "duplicate provider trade identity")

    events = layers[_layer_key("ORDER_EVENT")]
    if not isinstance(events, list) or any(
        not isinstance(row, dict)
        or set(row) != {"event_time", "execution_type", "order_id", "status", "trade_id", "transaction_time"}
        for row in events
    ):
        raise G10HParityError("PROVIDER_IDENTITY_CONFLICT", "/layers/03_ORDER_EVENT", "provider order event fields are incomplete")

    income_identities: list[tuple[str, Any]] = []
    fees = layers[_layer_key("FEE")]
    if not isinstance(fees, list):
        raise G10HParityError("PROVIDER_IDENTITY_CONFLICT", "/layers/05_FEE", "provider fee rows must be a list")
    for index, value in enumerate(fees):
        row = _object(value, "PROVIDER_IDENTITY_CONFLICT", f"/layers/05_FEE/{index}")
        fill = fills_by_trade.get(row.get("trade_id"))
        if (
            row.get("income_type") != "COMMISSION"
            or fill is None
            or row.get("amount") != fill["commission"]
            or row.get("asset") != fill["commission_asset"]
            or row.get("maker") != fill["maker"]
        ):
            raise G10HParityError("PROVIDER_IDENTITY_CONFLICT", f"/layers/05_FEE/{index}", "commission row is not linked to one account trade")
        income_identities.append((row["income_type"], row.get("income_tran_id")))

    position = _object(layers[_layer_key("POSITION_PNL")], "PROVIDER_IDENTITY_CONFLICT", "/layers/06_POSITION_PNL")
    income_rows = _list(position.get("income_rows"), "PROVIDER_IDENTITY_CONFLICT", "/layers/06_POSITION_PNL/income_rows")
    for index, value in enumerate(income_rows):
        row = _object(value, "PROVIDER_IDENTITY_CONFLICT", f"/layers/06_POSITION_PNL/income_rows/{index}")
        if row.get("income_type") != "REALIZED_PNL":
            raise G10HParityError("PROVIDER_IDENTITY_CONFLICT", f"/layers/06_POSITION_PNL/income_rows/{index}", "unexpected realized pnl income type")
        income_identities.append((row["income_type"], row.get("income_tran_id")))

    funding = layers[_layer_key("FUNDING")]
    if not isinstance(funding, list):
        raise G10HParityError("PROVIDER_IDENTITY_CONFLICT", "/layers/07_FUNDING", "provider funding rows must be a list")
    for index, value in enumerate(funding):
        row = _object(value, "PROVIDER_IDENTITY_CONFLICT", f"/layers/07_FUNDING/{index}")
        if row.get("income_type") != "FUNDING_FEE":
            raise G10HParityError("PROVIDER_IDENTITY_CONFLICT", f"/layers/07_FUNDING/{index}", "unexpected funding income type")
        income_identities.append((row["income_type"], row.get("income_tran_id")))
    if any(identity[1] is None for identity in income_identities) or len(income_identities) != len(set(income_identities)):
        raise G10HParityError("PROVIDER_IDENTITY_CONFLICT", "/layers", "duplicate or missing income identity")

    margin = _object(layers[_layer_key("MARGIN_SNAPSHOT")], "PROVIDER_IDENTITY_CONFLICT", "/layers/09_MARGIN_SNAPSHOT")
    for field in (
        "account_update_balance_change",
        "account_update_event_reason",
        "account_update_event_time",
        "account_update_transaction_time",
    ):
        if field not in margin:
            raise G10HParityError("PROVIDER_IDENTITY_CONFLICT", f"/layers/09_MARGIN_SNAPSHOT/{field}", "account update field is missing")


def _filtered_projection(
    projection: dict[str, Any], pair_id: str, coverage: dict[tuple[str, str], dict[str, Any]]
) -> dict[str, Any]:
    return {
        "case_id": projection["case_id"],
        "layers": {
            _layer_key(layer): projection["layers"][_layer_key(layer)]
            for layer in LAYERS
            if coverage[(pair_id, layer)]["status"] == "COMPARABLE"
        },
    }


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _run_pair(
    root: Path,
    pair: dict[str, Any],
    projections: dict[str, dict[str, Any]],
    sources: dict[str, dict[str, Any]],
    coverage: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    comparable = [layer for layer in LAYERS if coverage[(pair["id"], layer)]["status"] == "COMPARABLE"]
    if not comparable:
        return {
            "actual_role": pair["actual_role"],
            "comparison_counts": {"approved_change": 0, "matched": 0, "mismatched": 0},
            "contract_id": None,
            "contract_sha256": sha256_file(pair["_contract_path"]),
            "expected_role": pair["expected_role"],
            "first_divergence": None,
            "id": pair["id"],
            "migration_mode": pair["migration_mode"],
            "verdict": "NOT_COMPARABLE",
        }
    expected = _filtered_projection(projections[pair["expected_role"]], pair["id"], coverage)
    actual = _filtered_projection(projections[pair["actual_role"]], pair["id"], coverage)
    try:
        with TemporaryDirectory() as directory:
            temporary = Path(directory)
            expected_path = temporary / "expected.json"
            actual_path = temporary / "actual.json"
            _write_json(expected_path, expected)
            _write_json(actual_path, actual)
            report, _ = run_comparison(
                root,
                pair["_contract_path"],
                expected_path,
                actual_path,
                pair["migration_mode"],
            )
    except (ComparatorError, OSError, UnicodeError, TypeError) as error:
        if isinstance(error, ComparatorError):
            raise G10HParityError("COMPARATOR_BLOCKED", error.path, error.message) from error
        raise G10HParityError("COMPARATOR_BLOCKED", f"/pairs/{pair['id']}", str(error)) from error
    return {
        "actual_comparable_sha256": report["actual_sha256"],
        "actual_projection_sha256": sources[pair["actual_role"]]["projection_sha256"],
        "actual_role": pair["actual_role"],
        "comparison_counts": report["comparison_counts"],
        "contract_id": report["contract_id"],
        "contract_sha256": report["contract_sha256"],
        "expected_comparable_sha256": report["expected_sha256"],
        "expected_projection_sha256": sources[pair["expected_role"]]["projection_sha256"],
        "expected_role": pair["expected_role"],
        "first_divergence": report["first_divergence"],
        "id": pair["id"],
        "migration_mode": pair["migration_mode"],
        "verdict": report["verdict"],
    }


def _comparison_verdict(pair_reports: list[dict[str, Any]]) -> str:
    verdicts = {report["verdict"] for report in pair_reports}
    for verdict in ("MISMATCH", "APPROVED_CHANGE", "NOT_COMPARABLE", "MATCH"):
        if verdict in verdicts:
            return verdict
    raise AssertionError("unreachable parity verdict")


def _first_divergence(pair_reports: list[dict[str, Any]]) -> dict[str, Any] | None:
    for report in pair_reports:
        divergence = report["first_divergence"]
        if divergence is not None:
            return {"pair": report["id"], **divergence}
    return None


def run_plan(root: Path, plan_path: Path) -> dict[str, Any]:
    root = root.resolve()
    try:
        plan_resolved = plan_path.resolve(strict=True)
        plan_resolved.relative_to(root)
    except (OSError, ValueError) as error:
        raise G10HParityError("UNSAFE_PATH", "/plan", "plan must be inside root") from error
    plan = _load_plan(plan_resolved)
    sources_list, pairs = _validate_paths(root, plan)
    sources = _validate_sources(sources_list)
    projections = _load_projections(sources_list)
    _validate_pairs(pairs, projections)
    _validate_layers(plan, projections)
    coverage = _validate_coverage(plan)
    _validate_rule_coverage(root, pairs, coverage)
    _validate_provider_identity(projections["BINANCE_ACCOUNT_RECORDS"])
    pair_reports = [
        _run_pair(root, pair, projections, sources, coverage) for pair in pairs
    ]
    for index, pair in enumerate(pairs):
        if pair_reports[index]["verdict"] != pair["expected_verdict"]:
            raise G10HParityError(
                "EXPECTED_VERDICT_MISMATCH",
                f"/pairs/{index}/expected_verdict",
                f"expected {pair['expected_verdict']}, got {pair_reports[index]['verdict']}",
            )
    counts = {
        key: sum(report["comparison_counts"][key] for report in pair_reports)
        for key in ("approved_change", "matched", "mismatched")
    }
    coverage_rows = plan["coverage"]
    report: dict[str, Any] = {
        "comparison_counts": counts,
        "comparison_verdict": _comparison_verdict(pair_reports),
        "coverage": coverage_rows,
        "coverage_complete": all(row["status"] == "COMPARABLE" for row in coverage_rows),
        "decision_grade_eligible": False,
        "deployment_authorized": False,
        "first_divergence": _first_divergence(pair_reports),
        "limitations": plan["limitations"],
        "pair_reports": pair_reports,
        "plan_id": plan["id"],
        "plan_sha256": sha256_file(plan_resolved),
        "report_id": "binance-usdm-g10h-parity-report-v1",
        "schema_version": 1,
        "source_manifest": [
            {
                key: source[key]
                for key in (
                    "content_tree_sha256",
                    "projection",
                    "projection_sha256",
                    "role",
                    "snapshot_sha256",
                    "source_id",
                )
            }
            for source in sources_list
        ],
        "status": "completed",
    }
    report["report_hash"] = _canonical_hash(report)
    return report


def blocked_report(plan_path: Path, error: G10HParityError) -> dict[str, Any]:
    try:
        plan_sha256 = sha256_file(plan_path) if plan_path.is_file() else None
    except OSError:
        plan_sha256 = None
    report: dict[str, Any] = {
        "decision_grade_eligible": False,
        "deployment_authorized": False,
        "failure": {"code": error.code, "message": error.message, "path": error.path},
        "plan_sha256": plan_sha256,
        "report_id": "binance-usdm-g10h-parity-report-v1",
        "schema_version": 1,
        "status": "blocked",
    }
    report["report_hash"] = _canonical_hash(report)
    return report
