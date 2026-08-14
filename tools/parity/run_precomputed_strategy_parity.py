#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS / "migration"))

from precomputed_strategy import (
    G11JParityError,
    blocked_report,
    run_parity,
    safe_report_path,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run frozen G11J precomputed-vs-Strategy parity"
    )
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--expected", required=True, type=Path)
    parser.add_argument("--actual", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    return parser.parse_args()


def write_report(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def main() -> int:
    args = parse_args()
    try:
        report_path = safe_report_path(
            root=args.root,
            report_path=args.report,
            aliases=(args.contract, args.expected, args.actual),
        )
    except G11JParityError as error:
        print(f"{error.code}: {error.path}: {error.message}", file=sys.stderr)
        return 2
    try:
        payload, returncode = run_parity(
            root=args.root,
            contract_path=args.contract,
            expected_path=args.expected,
            actual_path=args.actual,
        )
    except G11JParityError as error:
        payload = blocked_report(error)
        returncode = 2
        print(f"{error.code}: {error.path}: {error.message}", file=sys.stderr)
    write_report(report_path, payload)
    if returncode == 0:
        print("MATCH")
    elif returncode == 1:
        print("MISMATCH", file=sys.stderr)
    return returncode


if __name__ == "__main__":
    raise SystemExit(main())
