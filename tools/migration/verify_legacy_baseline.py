#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from legacy_migration.baseline import report_payload, verify_baseline
from legacy_migration.source_maps import SourceMapError, load_source_map


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify frozen legacy source evidence")
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--source-map", required=True, type=Path)
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
    source_map_path = args.source_map.resolve()
    report_path = args.report.resolve()
    try:
        source_map = load_source_map(source_map_path)
    except SourceMapError as error:
        write_report(
            report_path,
            {
                "source_repository_reads": 0,
                "sources_verified": 0,
                "status": "invalid-source-map",
                "violations": [
                    {
                        "message": error.message,
                        "path": "<source-map>",
                        "rule": error.rule,
                        "source_id": "<source-map>",
                    }
                ],
            },
        )
        print(f"{error.rule}: {error.message}", file=sys.stderr)
        return 2
    verified, violations = verify_baseline(root, source_map)
    write_report(
        report_path,
        report_payload(source_map_path, source_map, verified, violations),
    )
    if violations:
        for item in violations:
            print(f"{item.rule}: {item.source_id}: {item.path}: {item.message}", file=sys.stderr)
        return 1
    print(f"Legacy baseline passed ({verified} sources verified)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
