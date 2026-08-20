from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
sys.argv = ["capture", str(ROOT)]


def parse_json(name: str, value: str) -> dict[str, object]:
    try:
        return json.loads(value)
    except json.JSONDecodeError as error:
        raise SystemExit(f"invalid JSON in {name}: {error}") from error
spec = importlib.util.spec_from_file_location(
    "cap",
    "/tmp/backtest-g12h-f1-authority/evidence/g12h/operator/g12h_wave1_capture.py",
)
cap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cap)

lineage = "stamp_duty"
source_id = "npc-stamp-duty-law-current-status-search"
url = "https://flk.npc.gov.cn/law-search/search/list"
destination = ROOT / lineage / source_id
if destination.exists():
    raise SystemExit(f"destination exists: {destination}")
destination.parent.mkdir(parents=True, exist_ok=True)
temp = Path(tempfile.mkdtemp(prefix=f".{source_id}.", dir=destination.parent))
payload = {
    "searchRange": 1,
    "searchContent": "中华人民共和国印花税法",
    "searchType": 1,
    "sxx": [3],
    "sxrq": [],
    "gbrq": [],
    "gbrqYear": [],
    "flfgCodeId": [],
    "zdjgCodeId": [],
    "orderByParam": {"order": "-1", "sort": ""},
    "pageNum": 1,
    "pageSize": 20,
}
body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
(temp / "request.body").write_bytes(body)
cap.write_json(
    temp / "request.json",
    {
        "type": "g12h_official_http_request_v1",
        "schema_version": 1,
        "method": "POST",
        "url": url,
        "headers": [
            {"name": "User-Agent", "value": cap.USER_AGENT},
            {"name": "Accept", "value": "application/json, text/plain, */*"},
            {"name": "Accept-Language", "value": "zh-CN,zh;q=0.9,en;q=0.5"},
            {"name": "Content-Type", "value": "application/json;charset=UTF-8"},
            {"name": "Cache-Control", "value": "no-cache"},
            {"name": "Pragma", "value": "no-cache"},
        ],
        "request_body_file": "request.body",
        "request_body_sha256": "sha256:" + hashlib.sha256(body).hexdigest(),
        "authentication": "none",
        "redirect_policy": {
            "follow": True,
            "maximum": 10,
            "redirect_protocols": ["https"],
        },
    },
)
raw = temp / "raw.json"
headers = temp / "response.headers"
transport = temp / "transport.log"
started = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
command = [
    "curl",
    "--location",
    "--max-redirs",
    "10",
    "--proto",
    "=https",
    "--proto-redir",
    "=https",
    "--silent",
    "--show-error",
    "--connect-timeout",
    "30",
    "--max-time",
    "180",
    "--retry",
    "2",
    "--retry-all-errors",
    "--user-agent",
    cap.USER_AGENT,
    "--header",
    "Accept: application/json, text/plain, */*",
    "--header",
    "Accept-Language: zh-CN,zh;q=0.9,en;q=0.5",
    "--header",
    "Content-Type: application/json;charset=UTF-8",
    "--header",
    "Cache-Control: no-cache",
    "--header",
    "Pragma: no-cache",
    "--data-binary",
    "@" + str(temp / "request.body"),
    "--dump-header",
    str(headers),
    "--output",
    str(raw),
    "--verbose",
    "--stderr",
    str(transport),
    "--write-out",
    "%{json}\n",
    url,
]
run = subprocess.run(command, capture_output=True, text=True)
finished = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
metadata = parse_json("curl metadata", run.stdout) if run.stdout.strip() else {}
cap.write_json(temp / "curl-metadata.json", metadata)
blocks = cap.parse_headers(headers)
cap.write_json(
    temp / "redirects.json",
    {
        "type": "g12h_http_response_chain_v1",
        "schema_version": 1,
        "responses": blocks,
    },
)
try:
    parsed = parse_json(str(raw), raw.read_text(encoding="utf-8"))
except OSError as error:
    raise SystemExit(f"cannot read {raw}: {error}") from error
cap.write_json(temp / "rendered.json", parsed)
receipt = {
    "type": "g12h_official_http_capture_receipt_v1",
    "schema_version": 1,
    "lineage": lineage,
    "source_id": source_id,
    "started_at": started,
    "retrieved_at": finished,
    "tool": subprocess.check_output(["curl", "--version"], text=True).splitlines()[0],
    "operator_harness_sha256": "sha256:"
    + hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    "curl_exit_code": run.returncode,
    "response_code": metadata.get("response_code"),
    "final_url": metadata.get("url_effective"),
    "redirect_count": metadata.get("num_redirects"),
    "content_type": metadata.get("content_type"),
    "raw_file": raw.name,
    "raw_sha256": cap.digest(raw),
    "raw_byte_length": raw.stat().st_size,
    "response_chain_count": len(blocks),
    "derivatives": {"json_parse": {"valid": True}},
    "authority_status": "CAPTURED_CURRENT_STATUS_NOT_CUTOFF_CLOSED",
}
cap.write_json(temp / "receipt.json", receipt)
files = sorted(
    path
    for path in temp.rglob("*")
    if path.is_file() and path.name != "sha256sums.txt"
)
(temp / "sha256sums.txt").write_text(
    "".join(
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(temp)}\n"
        for path in files
    ),
    encoding="utf-8",
)
os.replace(temp, destination)
print(json.dumps(receipt, ensure_ascii=False, indent=2))
