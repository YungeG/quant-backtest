from __future__ import annotations

from pathlib import Path
from typing import Any

from legacy_migration.parity import ComparatorError, invalid_report, run_comparison


class G12FParityError(ValueError):
    def __init__(self, code: str, path: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.path = path
        self.message = message


def _inside(root: Path, path: Path, name: str) -> Path:
    root = root.resolve()
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError):
        raise G12FParityError("UNSAFE_PATH", f"/{name}", f"{name} must be inside root") from None
    if not resolved.is_file():
        raise G12FParityError("UNSAFE_PATH", f"/{name}", f"{name} must be a file")
    return resolved


def run_parity(
    *,
    root: Path,
    contract_path: Path,
    expected_path: Path,
    actual_path: Path,
) -> tuple[dict[str, Any], int]:
    root = root.resolve()
    contract = _inside(root, contract_path, "contract")
    expected = _inside(root, expected_path, "expected")
    actual = _inside(root, actual_path, "actual")
    try:
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
    report["report_id"] = "market-bundle-reader-g12f-parity-report-v1"
    report["decision_grade_eligible"] = False
    report["deployment_authorized"] = False
    return report, returncode


def blocked_report(error: G12FParityError) -> dict[str, object]:
    return {
        "decision_grade_eligible": False,
        "deployment_authorized": False,
        "failure": {
            "code": error.code,
            "message": error.message,
            "path": error.path,
        },
        "first_divergence": None,
        "report_id": "market-bundle-reader-g12f-parity-report-v1",
        "schema_version": 1,
        "status": "blocked",
        "verdict": None,
    }
