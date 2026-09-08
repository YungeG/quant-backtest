from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, object]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"cannot load {path}: {error}") from error


def check_schedule(evidence_root: Path, schedule: dict[str, object]) -> None:
    errors: list[str] = []
    for item in schedule["sources"]:
        request = evidence_root / item["request_path"]
        if not request.is_file() or digest(request) != item["request_sha256"]:
            errors.append(str(request))
        body_name = item["request_body_path"]
        if body_name:
            body = evidence_root / body_name
            if not body.is_file() or digest(body) != item["request_body_sha256"]:
                errors.append(str(body))
    if errors:
        raise SystemExit("schedule mismatch:\n" + "\n".join(errors))
    print(f"schedule-check-pass sources={schedule['source_count']}")


def replay(evidence_root: Path, output_root: Path, item: dict[str, object]) -> None:
    destination = output_root / item["lineage"] / item["source_id"]
    destination.mkdir(parents=True, exist_ok=False)
    request = load_json(evidence_root / item["request_path"])
    raw_name = item["captured_raw_file"] or "raw.bin"
    command = [
        "curl",
        "--location",
        "--max-redirs",
        "10",
        "--proto",
        "=http,https",
        "--proto-redir",
        "=https",
        "--silent",
        "--show-error",
        "--connect-timeout",
        "30",
        "--max-time",
        "180",
        "--dump-header",
        str(destination / "response.headers"),
        "--output",
        str(destination / raw_name),
        "--write-out",
        "%{json}\n",
    ]
    for header in request["headers"]:
        command.extend(["--header", f"{header['name']}: {header['value']}"])
    if request["method"] != "GET":
        command.extend(["--request", request["method"]])
    if item["request_body_path"]:
        command.extend(["--data-binary", "@" + str(evidence_root / item["request_body_path"])])
    command.append(request["url"])
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    (destination / "curl-metadata.json").write_text(completed.stdout, encoding="utf-8")
    (destination / "curl-stderr.txt").write_text(completed.stderr, encoding="utf-8")
    (destination / "replay.json").write_text(
        json.dumps(
            {
                "source_id": item["source_id"],
                "curl_exit_code": completed.returncode,
                "historical_captured_raw_sha256": item["captured_exact_raw_sha256"],
                "replayed_raw_sha256": digest(destination / raw_name)
                if (destination / raw_name).is_file()
                else None,
                "historical_bytes_expected_to_reproduce": False,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence_root", type=Path)
    parser.add_argument("output_root", type=Path, nargs="?")
    parser.add_argument("source_ids", nargs="*")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    schedule_path = args.evidence_root / "operator/executed-acquisition-schedule.json"
    schedule = load_json(schedule_path)
    check_schedule(args.evidence_root, schedule)
    if args.check:
        return
    if args.output_root is None:
        parser.error("output_root is required unless --check is used")
    selected = set(args.source_ids)
    for item in schedule["sources"]:
        if not selected or item["source_id"] in selected:
            replay(args.evidence_root, args.output_root, item)


if __name__ == "__main__":
    main()
