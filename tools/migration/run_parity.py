#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from legacy_migration.parity import ComparatorError, invalid_report, run_comparison


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a field-classified parity comparison")
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--expected", required=True, type=Path)
    parser.add_argument("--actual", required=True, type=Path)
    parser.add_argument("--migration-mode", required=True)
    parser.add_argument("--report", required=True, type=Path)
    return parser.parse_args()


def write_report(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    contract = args.contract.resolve()
    expected = args.expected.resolve()
    actual = args.actual.resolve()
    report = args.report.resolve()
    try:
        payload, returncode = run_comparison(
            root, contract, expected, actual, args.migration_mode
        )
    except ComparatorError as error:
        payload = invalid_report(
            error, contract, expected, actual, args.migration_mode
        )
        returncode = 2
        print(f"{error.reason}: {error.path}: {error.message}", file=sys.stderr)
    write_report(report, payload)
    if returncode == 0:
        print(payload["verdict"])
    elif returncode == 1:
        print("MISMATCH", file=sys.stderr)
    return returncode


if __name__ == "__main__":
    raise SystemExit(main())
