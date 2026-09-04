#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS / "migration"))

from binance_usdm import G10HParityError, blocked_report, run_plan


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run frozen G10H layered parity")
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--require-match", action="store_true")
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
    plan = args.plan.resolve()
    report_path = args.report.resolve()
    try:
        report = run_plan(root, plan)
    except G10HParityError as error:
        report = blocked_report(plan, error)
        write_report(report_path, report)
        print(f"{error.code}: {error.path}: {error.message}", file=sys.stderr)
        return 2
    write_report(report_path, report)
    verdict = report["comparison_verdict"]
    if args.require_match and (verdict != "MATCH" or not report["coverage_complete"]):
        print(str(verdict), file=sys.stderr)
        return 1
    print(str(verdict))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
