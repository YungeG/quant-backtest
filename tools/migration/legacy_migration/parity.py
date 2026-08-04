from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from decimal import (
    ROUND_CEILING,
    ROUND_DOWN,
    ROUND_FLOOR,
    ROUND_HALF_DOWN,
    ROUND_HALF_EVEN,
    ROUND_HALF_UP,
    ROUND_UP,
    Decimal,
    InvalidOperation,
)
from pathlib import Path, PurePosixPath
from typing import Any

from .snapshots import sha256_file
from .source_maps import MIGRATION_MODES


COMPARATOR_SCHEMA_VERSION = 1
PARITY_REPORT_SCHEMA_VERSION = 1
COMPARISONS = frozenset(
    {"approved_change", "exact", "explicit_tolerance", "quantized", "sequence"}
)
ROUNDING = {
    "ROUND_CEILING": ROUND_CEILING,
    "ROUND_DOWN": ROUND_DOWN,
    "ROUND_FLOOR": ROUND_FLOOR,
    "ROUND_HALF_DOWN": ROUND_HALF_DOWN,
    "ROUND_HALF_EVEN": ROUND_HALF_EVEN,
    "ROUND_HALF_UP": ROUND_HALF_UP,
    "ROUND_UP": ROUND_UP,
}
MISSING = object()


class ComparatorError(ValueError):
    def __init__(self, reason: str, path: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason
        self.path = path
        self.message = message


@dataclass(frozen=True)
class ComparatorRule:
    path: str
    comparison: str
    quantum: str | None = None
    rounding: str | None = None
    absolute_tolerance: str | None = None
    relative_tolerance: str | None = None
    reference: str | None = None


@dataclass(frozen=True)
class ComparatorContract:
    id: str
    rules: tuple[ComparatorRule, ...]


@dataclass(frozen=True)
class Divergence:
    actual: Any
    comparison: str
    expected: Any
    path: str
    reason: str


@dataclass(frozen=True)
class RuleResult:
    state: str
    divergence: Divergence | None


def reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ComparatorError(
                "invalid-json-input", f"/{key}", "Duplicate JSON object key"
            )
        result[key] = value
    return result


def read_json(path: Path) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=reject_duplicate_json_keys,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ComparatorError("invalid-json-input", "/", str(error)) from error


def require_nonempty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ComparatorError("invalid-comparator-contract", field, "Expected string")
    return value


def validate_decimal(value: Any, field: str, positive: bool = False) -> str:
    text = require_nonempty_string(value, field)
    try:
        number = Decimal(text)
    except InvalidOperation as error:
        raise ComparatorError("invalid-explicit-tolerance", field, "Invalid decimal") from error
    if not number.is_finite() or number < 0 or (positive and number == 0):
        raise ComparatorError("invalid-explicit-tolerance", field, "Invalid decimal range")
    return text


def safe_reference(root: Path, value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ComparatorError(
            "approved-change-without-reference", field, "Committed docs/adr reference required"
        )
    reference = value
    pure = PurePosixPath(reference)
    if (
        pure.is_absolute()
        or ".." in pure.parts
        or "\\" in reference
        or not reference.startswith("docs/adr/")
        or not root.joinpath(*pure.parts).is_file()
    ):
        raise ComparatorError(
            "approved-change-without-reference", field, "Committed docs/adr reference required"
        )
    return reference


def validate_pointer(value: Any, field: str) -> str:
    path = require_nonempty_string(value, field)
    if not path.startswith("/") or path == "/" or "//" in path:
        raise ComparatorError("invalid-comparator-contract", path, "Invalid JSON pointer")
    return path


def load_contract(path: Path, root: Path) -> ComparatorContract:
    raw = read_json(path)
    if not isinstance(raw, dict):
        raise ComparatorError("invalid-comparator-contract", "/", "Contract must be object")
    if "epsilon" in raw or "global_epsilon" in raw:
        raise ComparatorError(
            "global-epsilon-forbidden", "/", "Global epsilon is not a valid contract field"
        )
    if set(raw) != {"schema_version", "id", "rules"}:
        raise ComparatorError(
            "invalid-comparator-contract", "/", "Unknown or missing contract fields"
        )
    if raw["schema_version"] != COMPARATOR_SCHEMA_VERSION:
        raise ComparatorError(
            "invalid-comparator-contract", "/schema_version", "Unsupported schema"
        )
    contract_id = require_nonempty_string(raw["id"], "/id")
    rows = raw["rules"]
    if not isinstance(rows, list) or not rows:
        raise ComparatorError("invalid-comparator-contract", "/rules", "Rules required")

    rules: list[ComparatorRule] = []
    paths: list[str] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ComparatorError(
                "invalid-comparator-contract", f"/rules/{index}", "Rule must be object"
            )
        rule_path = validate_pointer(row.get("path"), f"/rules/{index}/path")
        comparison = require_nonempty_string(
            row.get("comparison"), f"/rules/{index}/comparison"
        )
        if comparison == "epsilon":
            raise ComparatorError("global-epsilon-forbidden", rule_path, "epsilon forbidden")
        if comparison not in COMPARISONS:
            raise ComparatorError(
                "invalid-comparator-contract", rule_path, f"Unknown comparison: {comparison}"
            )
        allowed_keys = {"comparison", "path"}
        values: dict[str, str | None] = {
            "absolute_tolerance": None,
            "quantum": None,
            "reference": None,
            "relative_tolerance": None,
            "rounding": None,
        }
        if comparison == "quantized":
            allowed_keys |= {"quantum", "rounding"}
            try:
                quantum = validate_decimal(row.get("quantum"), rule_path, positive=True)
            except ComparatorError as error:
                raise ComparatorError(
                    "invalid-quantization-policy", rule_path, error.message
                ) from error
            rounding = row.get("rounding")
            if rounding not in ROUNDING:
                raise ComparatorError(
                    "invalid-quantization-policy", rule_path, "Unknown rounding policy"
                )
            values["quantum"] = quantum
            values["rounding"] = str(rounding)
        elif comparison == "explicit_tolerance":
            allowed_keys |= {"absolute_tolerance", "relative_tolerance"}
            absolute = row.get("absolute_tolerance")
            relative = row.get("relative_tolerance")
            if absolute is None and relative is None:
                raise ComparatorError(
                    "invalid-explicit-tolerance", rule_path, "A tolerance is required"
                )
            values["absolute_tolerance"] = (
                validate_decimal(absolute, rule_path) if absolute is not None else "0"
            )
            values["relative_tolerance"] = (
                validate_decimal(relative, rule_path) if relative is not None else "0"
            )
        elif comparison == "approved_change":
            allowed_keys.add("reference")
            values["reference"] = safe_reference(root, row.get("reference"), rule_path)
        if set(row) != allowed_keys:
            raise ComparatorError(
                "invalid-comparator-contract", rule_path, "Unexpected fields for comparison"
            )
        paths.append(rule_path)
        rules.append(
            ComparatorRule(path=rule_path, comparison=comparison, **values)
        )

    if paths != sorted(paths) or len(paths) != len(set(paths)):
        raise ComparatorError(
            "invalid-comparator-contract", "/rules", "Rule paths must be unique and sorted"
        )
    for index, parent in enumerate(paths):
        for child in paths[index + 1 :]:
            if child.startswith(parent + "/"):
                raise ComparatorError(
                    "invalid-comparator-contract",
                    child,
                    "Overlapping comparator paths are forbidden",
                )
    return ComparatorContract(contract_id, tuple(rules))


def pointer_segments(path: str) -> list[str]:
    return [segment.replace("~1", "/").replace("~0", "~") for segment in path[1:].split("/")]


def pointer_get(value: Any, path: str) -> Any:
    current = value
    for segment in pointer_segments(path):
        if isinstance(current, dict) and segment in current:
            current = current[segment]
        elif isinstance(current, list) and segment.isdigit() and int(segment) < len(current):
            current = current[int(segment)]
        else:
            return MISSING
    return current


def leaf_paths(value: Any, path: str = "") -> set[str]:
    if isinstance(value, dict) and value:
        result: set[str] = set()
        for key, child in value.items():
            escaped = str(key).replace("~", "~0").replace("/", "~1")
            result |= leaf_paths(child, f"{path}/{escaped}")
        return result
    if isinstance(value, list) and value:
        result = set()
        for index, child in enumerate(value):
            result |= leaf_paths(child, f"{path}/{index}")
        return result
    return {path or "/"}


def display(value: Any) -> Any:
    return {"missing": True} if value is MISSING else value


def exact_equal(expected: Any, actual: Any) -> bool:
    if type(expected) is not type(actual):
        return False
    if isinstance(expected, dict):
        return expected.keys() == actual.keys() and all(
            exact_equal(expected[key], actual[key]) for key in expected
        )
    if isinstance(expected, list):
        return len(expected) == len(actual) and all(
            exact_equal(expected_item, actual_item)
            for expected_item, actual_item in zip(expected, actual, strict=True)
        )
    return expected == actual


def decimal_value(value: Any, path: str, reason: str) -> Decimal:
    if isinstance(value, bool) or value is MISSING or isinstance(value, (dict, list)):
        raise ComparatorError(reason, path, "Numeric scalar required")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise ComparatorError(reason, path, "Invalid numeric scalar") from error
    if not number.is_finite():
        raise ComparatorError(reason, path, "Finite numeric scalar required")
    return number


def mismatch(
    rule: ComparatorRule, expected: Any, actual: Any, reason: str, path: str | None = None
) -> RuleResult:
    return RuleResult(
        "mismatched",
        Divergence(
            actual=display(actual),
            comparison=rule.comparison,
            expected=display(expected),
            path=path or rule.path,
            reason=reason,
        ),
    )


def compare_rule(rule: ComparatorRule, expected: Any, actual: Any) -> RuleResult:
    if expected is MISSING or actual is MISSING:
        return mismatch(rule, expected, actual, "missing-value")
    if rule.comparison == "exact":
        return RuleResult("matched", None) if exact_equal(expected, actual) else mismatch(
            rule, expected, actual, "exact-mismatch"
        )
    if rule.comparison == "sequence":
        if not isinstance(expected, list) or not isinstance(actual, list):
            raise ComparatorError("invalid-comparator-contract", rule.path, "Lists required")
        for index in range(min(len(expected), len(actual))):
            if not exact_equal(expected[index], actual[index]):
                return mismatch(
                    rule,
                    expected[index],
                    actual[index],
                    "sequence-item-mismatch",
                    f"{rule.path}/{index}",
                )
        if len(expected) != len(actual):
            index = min(len(expected), len(actual))
            expected_item = expected[index] if index < len(expected) else MISSING
            actual_item = actual[index] if index < len(actual) else MISSING
            return mismatch(
                rule,
                expected_item,
                actual_item,
                "sequence-length-mismatch",
                f"{rule.path}/{index}",
            )
        return RuleResult("matched", None)
    if rule.comparison == "quantized":
        assert rule.quantum is not None and rule.rounding is not None
        expected_number = decimal_value(expected, rule.path, "invalid-quantization-policy")
        actual_number = decimal_value(actual, rule.path, "invalid-quantization-policy")
        quantum = Decimal(rule.quantum)
        rounding = ROUNDING[rule.rounding]
        try:
            expected_quantized = expected_number.quantize(quantum, rounding=rounding)
            actual_quantized = actual_number.quantize(quantum, rounding=rounding)
        except InvalidOperation as error:
            raise ComparatorError(
                "invalid-quantization-policy", rule.path, "Value cannot be quantized"
            ) from error
        if expected_quantized == actual_quantized:
            return RuleResult("matched", None)
        return mismatch(rule, expected, actual, "quantized-mismatch")
    if rule.comparison == "explicit_tolerance":
        expected_number = decimal_value(expected, rule.path, "invalid-explicit-tolerance")
        actual_number = decimal_value(actual, rule.path, "invalid-explicit-tolerance")
        absolute = Decimal(rule.absolute_tolerance or "0")
        relative = Decimal(rule.relative_tolerance or "0")
        allowed = absolute + relative * abs(expected_number)
        if abs(actual_number - expected_number) <= allowed:
            return RuleResult("matched", None)
        return mismatch(rule, expected, actual, "explicit-tolerance-mismatch")
    if rule.comparison == "approved_change":
        if exact_equal(expected, actual):
            return RuleResult("matched", None)
        return RuleResult(
            "approved_change",
            Divergence(
                actual=display(actual),
                comparison=rule.comparison,
                expected=display(expected),
                path=rule.path,
                reason=f"approved-change:{rule.reference}",
            ),
        )
    raise ComparatorError("invalid-comparator-contract", rule.path, "Unhandled comparison")


def validate_classification(
    contract: ComparatorContract, expected: Any, actual: Any
) -> None:
    rule_paths = [rule.path for rule in contract.rules]
    for path in sorted(leaf_paths(expected) | leaf_paths(actual)):
        if not any(path == rule_path or path.startswith(rule_path + "/") for rule_path in rule_paths):
            raise ComparatorError(
                "unclassified-comparator-field", path, "Every input field needs a rule"
            )


def run_comparison(
    root: Path,
    contract_path: Path,
    expected_path: Path,
    actual_path: Path,
    migration_mode: str,
) -> tuple[dict[str, Any], int]:
    if migration_mode not in MIGRATION_MODES:
        raise ComparatorError(
            "unsupported-migration-mode", "/migration_mode", migration_mode
        )
    contract = load_contract(contract_path, root)
    has_approved_change = any(
        rule.comparison == "approved_change" for rule in contract.rules
    )
    if migration_mode == "intentional_semantic_change" and not has_approved_change:
        raise ComparatorError(
            "intentional-change-without-adr",
            "/migration_mode",
            "intentional_semantic_change requires an approved_change rule",
        )
    if migration_mode != "intentional_semantic_change" and has_approved_change:
        raise ComparatorError(
            "approved-change-requires-intentional-mode",
            "/migration_mode",
            "approved_change requires intentional_semantic_change mode",
        )
    expected = read_json(expected_path)
    actual = read_json(actual_path)
    validate_classification(contract, expected, actual)

    results: list[RuleResult] = []
    for rule in contract.rules:
        results.append(
            compare_rule(
                rule, pointer_get(expected, rule.path), pointer_get(actual, rule.path)
            )
        )
    divergences = [result.divergence for result in results if result.divergence]
    mismatches = sum(result.state == "mismatched" for result in results)
    approved = sum(result.state == "approved_change" for result in results)
    verdict = "MISMATCH" if mismatches else "APPROVED_CHANGE" if approved else "MATCH"
    report = {
        "actual_sha256": sha256_file(actual_path),
        "comparison_counts": {
            "approved_change": approved,
            "matched": sum(result.state == "matched" for result in results),
            "mismatched": mismatches,
        },
        "contract_id": contract.id,
        "contract_sha256": sha256_file(contract_path),
        "expected_sha256": sha256_file(expected_path),
        "first_divergence": asdict(divergences[0]) if divergences else None,
        "migration_mode": migration_mode,
        "schema_version": PARITY_REPORT_SCHEMA_VERSION,
        "status": "completed",
        "verdict": verdict,
    }
    return report, 1 if mismatches else 0


def invalid_report(
    error: ComparatorError,
    contract_path: Path,
    expected_path: Path,
    actual_path: Path,
    migration_mode: str,
) -> dict[str, Any]:
    def existing_hash(path: Path) -> str | None:
        return sha256_file(path) if path.is_file() else None

    return {
        "actual_sha256": existing_hash(actual_path),
        "comparison_counts": None,
        "contract_id": None,
        "contract_sha256": existing_hash(contract_path),
        "expected_sha256": existing_hash(expected_path),
        "first_divergence": {
            "actual": None,
            "comparison": "contract-validation",
            "expected": None,
            "path": error.path,
            "reason": error.reason,
        },
        "migration_mode": migration_mode,
        "schema_version": PARITY_REPORT_SCHEMA_VERSION,
        "status": "invalid-contract",
        "verdict": "BLOCKED",
    }
