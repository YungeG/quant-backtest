from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
PRIVATE = Path(sys.argv[2]).resolve()
COOKIE_LINE = re.compile(r"(?i)^(?P<prefix>(?:<\s*)?set-cookie:\s*)(?P<name>[^=;\r\n]+)=(?P<value>[^;\r\n]*)(?P<attrs>.*)$")


def sha_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def sha_file(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def parse_json_bytes(name: str, raw: bytes) -> dict[str, object]:
    try:
        return json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SystemExit(f"invalid JSON in {name}: {error}") from error


def load_json(path: Path) -> dict[str, object]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"cannot load {path}: {error}") from error


def redact_text(raw: bytes) -> tuple[bytes, bool]:
    text = raw.decode("latin-1")
    result: list[str] = []
    changed = False
    for line in text.splitlines(keepends=True):
        ending = "\r\n" if line.endswith("\r\n") else ("\n" if line.endswith("\n") else "")
        body = line[: -len(ending)] if ending else line
        match = COOKIE_LINE.match(body)
        if not match:
            result.append(line)
            continue
        digest = sha_bytes(match.group("value").encode("latin-1"))
        result.append(f"{match.group('prefix')}{match.group('name')}=<redacted {digest}>{match.group('attrs')}{ending}")
        changed = True
    return "".join(result).encode("latin-1"), changed


def redact_redirects(raw: bytes) -> tuple[bytes, bool]:
    data = parse_json_bytes("redirects.json", raw)
    changed = False
    for response in data.get("responses", []):
        for header in response.get("headers", []):
            if header.get("name", "").lower() != "set-cookie":
                continue
            value = header["value"]
            cookie, separator, attrs = value.partition(";")
            name, equals, cookie_value = cookie.partition("=")
            if not equals or "<redacted sha256:" in cookie_value:
                continue
            header["value"] = f"{name}=<redacted {sha_bytes(cookie_value.encode('latin-1'))}>" + (separator + attrs if separator else "")
            changed = True
    return (json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"), changed

PRIVATE.mkdir(parents=True, exist_ok=False, mode=0o700)
records = []
for source_dir in sorted(path.parent for path in ROOT.glob("*/*/response.headers")):
    file_records = []
    for name in ("response.headers", "transport.log", "redirects.json"):
        path = source_dir / name
        if not path.exists():
            continue
        raw = path.read_bytes()
        redacted, changed = redact_redirects(raw) if name == "redirects.json" else redact_text(raw)
        if not changed:
            continue
        private_path = PRIVATE / path.relative_to(ROOT)
        private_path.parent.mkdir(parents=True, exist_ok=True)
        private_path.write_bytes(raw)
        path.write_bytes(redacted)
        file_records.append({
            "tracked_path": str(path.relative_to(ROOT)),
            "tracked_redacted_sha256": sha_file(path),
            "exact_private_path": str(private_path),
            "exact_private_sha256": sha_bytes(raw),
            "redaction": "Set-Cookie value replaced by SHA-256; name and attributes retained.",
        })
    if not file_records:
        continue
    receipt_path = source_dir / "receipt.json"
    receipt = load_json(receipt_path)
    receipt["sensitive_response_headers"] = {
        "policy": "Exact server-issued cookie values are excluded from Git and retained in the mode-restricted private evidence store.",
        "files": file_records,
    }
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    source_receipt = {
        "type": "g12h_live_status_probe_sensitive_response_header_receipt_v1",
        "schema_version": 1,
        "source_id": receipt["source_id"],
        "files": file_records,
    }
    (source_dir / "sensitive-response-header-receipt.json").write_text(json.dumps(source_receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    files = sorted(path for path in source_dir.rglob("*") if path.is_file() and path.name != "sha256sums.txt")
    (source_dir / "sha256sums.txt").write_text("".join(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(source_dir)}\n" for path in files), encoding="utf-8")
    records.append(source_receipt)

manifest = {
    "type": "g12h_live_status_probe_private_header_manifest_v1",
    "schema_version": 1,
    "record_count": len(records),
    "records": records,
}
manifest_path = PRIVATE / "manifest.json"
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
public = {
    "type": "g12h_live_status_probe_private_header_store_receipt_v1",
    "schema_version": 1,
    "private_store_root": str(PRIVATE),
    "private_manifest_sha256": sha_file(manifest_path),
    "source_count": len(records),
    "status": "EXACT_COOKIE_BEARING_HEADERS_PRIVATE_TRACKED_HEADERS_REDACTED",
}
(ROOT / "private-response-header-store-receipt.json").write_text(json.dumps(public, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
for path in sorted(PRIVATE.rglob("*"), reverse=True):
    os.chmod(path, 0o500 if path.is_dir() else 0o400)
os.chmod(PRIVATE, 0o500)
print(json.dumps(public, indent=2))
