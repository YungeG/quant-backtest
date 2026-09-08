#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from legacy_migration.snapshots import freeze_snapshot
from legacy_migration.source_maps import SourceMapError, load_source_map


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze declared legacy source bytes")
    parser.add_argument("--source-map", required=True, type=Path)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        source = load_source_map(args.source_map.resolve()).source(args.source_id)
        result = freeze_snapshot(args.source_root, source, args.output_dir)
    except SourceMapError as error:
        print(f"{error.rule}: {error.message}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "archive": str(result.archive),
                "manifest": str(result.manifest),
                "snapshot_id": result.snapshot_id,
                "source_id": args.source_id,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
