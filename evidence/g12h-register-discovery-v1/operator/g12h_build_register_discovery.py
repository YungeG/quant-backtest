from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict[str, object]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"cannot load {path}: {error}") from error


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


sources = []
for receipt_path in sorted(ROOT.glob("*/*/receipt.json")):
    source_dir = receipt_path.parent
    sums = source_dir / "sha256sums.txt"
    for line in sums.read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        path = source_dir / relative
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise SystemExit(f"checksum mismatch: {path}")
    receipt = load(receipt_path)
    request = load(source_dir / "request.json")
    sources.append(
        {
            "lineage": receipt["lineage"],
            "source_id": receipt["source_id"],
            "request_path": str((source_dir / "request.json").relative_to(ROOT)),
            "request_sha256": digest(source_dir / "request.json"),
            "method": request["method"],
            "url": request["url"],
            "retrieved_at": receipt["retrieved_at"],
            "response_code": receipt["response_code"],
            "raw_file": receipt["raw_file"],
            "raw_sha256": receipt["raw_sha256"],
            "raw_byte_length": receipt["raw_byte_length"],
            "receipt_path": str(receipt_path.relative_to(ROOT)),
            "receipt_sha256": digest(receipt_path),
        }
    )

analysis = ROOT / "analysis/status-register-assessment.json"
private_receipt = ROOT / "private-response-header-store-receipt.json"
operator_manifest = ROOT / "operator/manifest.json"
manifest = {
    "type": "g12h_competent_status_register_capture_manifest_v1",
    "schema_version": 1,
    "generated_at": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
    "status": "ALL_LINEAGES_INSUFFICIENT_NO_COMMON_OFFICIAL_RECORD_AS_OF",
    "source_count": len(sources),
    "sources": sources,
    "analysis": {"path": str(analysis.relative_to(ROOT)), "sha256": digest(analysis)},
    "private_response_header_store": {
        "path": str(private_receipt.relative_to(ROOT)),
        "sha256": digest(private_receipt),
    },
    "operator_manifest": {
        "path": str(operator_manifest.relative_to(ROOT)),
        "sha256": digest(operator_manifest),
    },
    "wave1_reference": {
        "commit": "c253ca506d7c4f63fb650a4dec8794c7213e8ae3",
        "manifest_sha256": "sha256:b54a3e34eb2aa9896306c48c9b3e971dff241dc97c282bc3fdf99b2616dcbe9c",
        "ledger_sha256": "sha256:e57d89fb96ceba34d36c545e7c514d19a1588f9cb6e4da1d5c7110fe7979a610",
    },
    "limitations": [
        "No source-declared post-target record-state timestamp was found for the NPC current-status response.",
        "No. 39 has blank status/repeal/revision fields and no history chain.",
        "Business-rule/repeal categories are not fee-table lineage registers.",
        "Specific HKSCC amendment dispositions do not prove register completeness.",
        "HTML rendered DOM remains unavailable; exact server HTML and deterministic extraction are retained.",
    ],
}
write_json(ROOT / "manifest.json", manifest)
files = sorted(path for path in ROOT.rglob("*") if path.is_file() and path != ROOT / "sha256sums.txt")
(ROOT / "sha256sums.txt").write_text(
    "".join(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(ROOT)}\n" for path in files),
    encoding="utf-8",
)
print(json.dumps({"source_count": len(sources), "files": len(files) + 1, "manifest_sha256": digest(ROOT / "manifest.json")}, indent=2))
