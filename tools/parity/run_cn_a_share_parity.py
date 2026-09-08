#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import sys
from tempfile import NamedTemporaryFile


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.parity.cn_a_share import CnAShareParityError, blocked_report, run_plan


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run frozen G08H layered parity")
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--require-match", action="store_true")
    return parser.parse_args()


def _inside_root(root: Path, path: Path, *, must_exist: bool) -> Path:
    candidate = path if path.is_absolute() else root / path
    resolved = candidate.resolve(strict=must_exist)
    resolved.relative_to(root)
    return resolved


def write_report(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".tmp",
        dir=path.parent,
        delete=False,
    ) as stream:
        stream.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        temporary = Path(stream.name)
    temporary.replace(path)


def main() -> int:
    args = parse_args()
    try:
        root = args.root.resolve(strict=True)
        plan = _inside_root(root, args.plan, must_exist=True)
        report_path = _inside_root(root, args.report, must_exist=False)
    except (OSError, ValueError) as error:
        print(f"UNSAFE_PATH: {error}", file=sys.stderr)
        return 2
    try:
        report = run_plan(root, plan)
    except CnAShareParityError as error:
        report = blocked_report(plan, error)
        write_report(report_path, report)
        print(f"{error.code}: {error.path}: {error.message}", file=sys.stderr)
        return 2
    write_report(report_path, report)
    verdict = report["comparison_verdict"]
    if args.require_match and (
        verdict != "MATCH" or not report["coverage_complete"]
    ):
        print(str(verdict), file=sys.stderr)
        return 1
    print(str(verdict))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
