from __future__ import annotations

from pathlib import Path

from legacy_migration.parity import (
    ComparatorError,
    invalid_report,
    load_contract,
    run_comparison,
)


_FROZEN_RULES = (
    ("/fixture_id", "exact"),
    ("/layers/00_NORMALIZED_ENTRY", "exact"),
    ("/layers/01_DECISION_BATCH", "sequence"),
    ("/layers/02_ALLOCATION", "sequence"),
    ("/layers/03_PORTFOLIO_RISK", "sequence"),
    ("/layers/04_NORMALIZED_ACTIVE_TARGET", "sequence"),
    ("/layers/05_ORDER_PLAN_INTENT", "sequence"),
    ("/layers/06_ORDER_EVENT", "sequence"),
    ("/layers/07_FILL", "sequence"),
    ("/layers/08_SLIPPAGE", "sequence"),
    ("/layers/09_FEE", "sequence"),
    ("/layers/10_FINANCIAL_ARTIFACT", "sequence"),
    ("/layers/11_JOURNAL", "sequence"),
    ("/layers/12_LEDGER", "exact"),
    ("/layers/13_FINAL_SNAPSHOT", "exact"),
    ("/layers/14_RUN_END", "exact"),
    ("/layers/15_TRACE", "exact"),
    ("/layers/16_EXECUTION_RESULT_HASH", "exact"),
    ("/qualification", "exact"),
    ("/schema_version", "exact"),
)


class G11JParityError(ValueError):
    def __init__(self, code: str, path: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.path = path
        self.message = message


def _root(path: Path) -> Path:
    try:
        resolved = path.resolve(strict=True)
    except OSError:
        raise G11JParityError(
            "UNSAFE_PATH", "/root", "root must be an existing directory"
        ) from None
    if not resolved.is_dir() or resolved == Path(resolved.anchor):
        raise G11JParityError(
            "UNSAFE_PATH", "/root", "root must be an existing contained directory"
        )
    return resolved


def _inside(root: Path, path: Path, name: str) -> Path:
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError):
        raise G11JParityError(
            "UNSAFE_PATH", f"/{name}", f"{name} must be inside root"
        ) from None
    if not resolved.is_file():
        raise G11JParityError("UNSAFE_PATH", f"/{name}", f"{name} must be a file")
    return resolved


def safe_report_path(
    *,
    root: Path,
    report_path: Path,
    aliases: tuple[Path, ...],
) -> Path:
    resolved_root = _root(root)
    try:
        resolved = report_path.resolve(strict=False)
        resolved.relative_to(resolved_root)
    except (OSError, ValueError):
        raise G11JParityError(
            "UNSAFE_PATH", "/report", "report must be inside root"
        ) from None
    if resolved.exists() and not resolved.is_file():
        raise G11JParityError(
            "UNSAFE_PATH", "/report", "report must be a file"
        )
    for alias in aliases:
        alias = alias.resolve(strict=False)
        try:
            same_file = resolved == alias or (
                resolved.exists() and alias.exists() and resolved.samefile(alias)
            )
        except OSError:
            same_file = resolved == alias
        if same_file:
            raise G11JParityError(
                "UNSAFE_PATH",
                "/report",
                "report must not alias contract, expected, or actual",
            )
    return resolved


def _require_frozen_contract(root: Path, path: Path) -> None:
    contract = load_contract(path, root)
    if contract.id != "precomputed-strategy-g11j-v1":
        raise ComparatorError(
            "invalid-comparator-contract",
            "/id",
            "Contract must match frozen G11J v1",
        )
    actual = {rule.path: rule.comparison for rule in contract.rules}
    for rule_path, comparison in _FROZEN_RULES:
        if actual.get(rule_path) != comparison:
            raise ComparatorError(
                "invalid-comparator-contract",
                rule_path,
                "Contract must match frozen G11J v1",
            )
    expected_paths = {path for path, _ in _FROZEN_RULES}
    extra = next(
        (rule.path for rule in contract.rules if rule.path not in expected_paths), None
    )
    if extra is not None or len(contract.rules) != len(_FROZEN_RULES):
        raise ComparatorError(
            "invalid-comparator-contract",
            extra or "/rules",
            "Contract must match frozen G11J v1",
        )


def run_parity(
    *,
    root: Path,
    contract_path: Path,
    expected_path: Path,
    actual_path: Path,
) -> tuple[dict[str, object], int]:
    root = _root(root)
    contract = _inside(root, contract_path, "contract")
    expected = _inside(root, expected_path, "expected")
    actual = _inside(root, actual_path, "actual")
    try:
        _require_frozen_contract(root, contract)
        report, returncode = run_comparison(
            root,
            contract,
            expected,
            actual,
            "copy_with_parity",
        )
    except ComparatorError as error:
        return (
            invalid_report(
                error,
                contract,
                expected,
                actual,
                "copy_with_parity",
            ),
            2,
        )
    report["report_id"] = "precomputed-vs-strategy-g11j-parity-report-v1"
    report["decision_grade_eligible"] = False
    report["deployment_authorized"] = False
    return report, returncode


def blocked_report(error: G11JParityError) -> dict[str, object]:
    return {
        "decision_grade_eligible": False,
        "deployment_authorized": False,
        "failure": {
            "code": error.code,
            "message": error.message,
            "path": error.path,
        },
        "first_divergence": None,
        "report_id": "precomputed-vs-strategy-g11j-parity-report-v1",
        "schema_version": 1,
        "status": "blocked",
        "verdict": "BLOCKED",
    }
