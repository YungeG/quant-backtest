from __future__ import annotations

import datetime as dt
import hashlib
import html.parser
import json
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(sys.argv[1]).resolve()


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict[str, object]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"cannot load {path}: {error}") from error


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class TextExtractor(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def text_content(value: str) -> str:
    parser = TextExtractor()
    parser.feed(value)
    return " ".join("".join(parser.parts).split())


sources = []
for receipt_path in sorted(ROOT.glob("*/*/receipt.json")):
    source_dir = receipt_path.parent
    for line in (source_dir / "sha256sums.txt").read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        path = source_dir / relative
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise SystemExit(f"checksum mismatch: {path}")
    receipt = load(receipt_path)
    request = load(source_dir / "request.json")
    if receipt["response_code"] != 200:
        raise SystemExit(f"non-200 source: {receipt['source_id']}")
    sources.append(
        {
            "lineage": receipt["lineage"],
            "source_id": receipt["source_id"],
            "method": request["method"],
            "url": request["url"],
            "retrieved_at": receipt["retrieved_at"],
            "raw_sha256": receipt["raw_sha256"],
            "receipt_sha256": sha(receipt_path),
        }
    )

selector_dir = ROOT / "exchange_handling/szse-fee-selector-json-live"
document_dir = ROOT / "exchange_handling/szse-fee-document-2026-01-json-live"
selector = load(selector_dir / "rendered.json")
document = load(document_dir / "rendered.json")
selector_rows = selector.get("data")
if selector.get("code") != 0 or not isinstance(selector_rows, list) or len(selector_rows) != 1:
    raise SystemExit("SZSE selector shape mismatch")
selector_row = selector_rows[0]
if not isinstance(selector_row, dict):
    raise SystemExit("SZSE selector row mismatch")
expected_json_path = "/marketServices/deal/payFees/t20251231_618209.json"
expected_html_path = "/marketServices/deal/payFees/t20251231_618209.html"
if selector_row.get("jsonPath") != expected_json_path or selector_row.get("url") != expected_html_path:
    raise SystemExit("SZSE selected path changed")
document_data = document.get("data")
if document.get("code") != 0 or not isinstance(document_data, dict):
    raise SystemExit("SZSE document shape mismatch")
for key, expected in (("docId", 618209), ("jsonPath", expected_json_path), ("url", expected_html_path)):
    if document_data.get(key) != expected:
        raise SystemExit(f"SZSE document {key} mismatch")
document_text = text_content(str(document_data.get("content", "")))
for expected in (
    "深交所收费及代收税费标准（2026年1月）",
    "按成交额双边收取0.0341‰",
    "按成交额双边收取0.02‰",
    "代中国证监会收取",
):
    if expected not in document_text:
        raise SystemExit(f"SZSE content assertion missing: {expected}")

sta_expected = {
    "sta-no39-status-unfiltered-live": "",
    "sta-no39-status-full-valid-live": "全文有效",
    "sta-no39-status-modified-live": "已修改",
    "sta-no39-status-invalid-live": "全文失效",
    "sta-no39-status-repealed-live": "全文废止",
    "sta-no39-status-not-yet-effective-live": "尚未生效",
}
sta_results = []
for source_id, status_filter in sta_expected.items():
    source_dir = ROOT / "stamp_duty" / source_id
    request = load(source_dir / "request.json")
    query = parse_qs(urlsplit(str(request["url"])).query, keep_blank_values=True)
    if query.get("xxgkAging") != [status_filter]:
        raise SystemExit(f"STA filter mismatch: {source_id}")
    payload = load(source_dir / "rendered.json")
    result = payload.get("searchResultAll")
    if not isinstance(result, dict) or result.get("status") != 1000:
        raise SystemExit(f"STA response mismatch: {source_id}")
    rows = result.get("searchTotal") or []
    total = result.get("total")
    if status_filter:
        if total != 0 or rows:
            raise SystemExit(f"STA classified status unexpectedly matched: {source_id}")
    else:
        if total != 1 or not isinstance(rows, list) or len(rows) != 1:
            raise SystemExit("STA unfiltered exact record mismatch")
        row = rows[0]
        if not isinstance(row, dict) or row.get("govDoc", {}).get("docNum") != "财政部 税务总局公告2023年第39号":
            raise SystemExit("STA exact act identity mismatch")
        for key in ("xxgk_aging", "xxgk_abolishDate", "xxgk_reviseType"):
            if row.get(key) != "":
                raise SystemExit(f"STA field unexpectedly declared: {key}")
        if result.get("agingList") != [{"doc_count": 1, "key": ""}]:
            raise SystemExit("STA blank aging aggregation mismatch")
    sta_results.append({"source_id": source_id, "status_filter": status_filter, "total": total})

assessment = {
    "type": "g12h_live_status_api_probe_assessment_v1",
    "schema_version": 1,
    "target_to_exclusive": "2026-07-30T16:00:00Z",
    "overall_status": "F1_BLOCKED_NO_COMMON_OFFICIAL_RECORD_AS_OF",
    "exchange_handling": {
        "status": "CURRENT_DOCUMENT_SELECTOR_CONFIRMED_STATUS_UNDECLARED",
        "selector_json_path": selector_row["jsonPath"],
        "selector_pub_time_epoch_ms": selector_row["pubTime"],
        "selector_doc_title_status_time": selector_row["docTitleStatusTime"],
        "document_doc_title_status_time": document_data["docTitleStatusTime"],
        "content_assertions": [
            "深交所收费及代收税费标准（2026年1月）",
            "按成交额双边收取0.0341‰",
            "按成交额双边收取0.02‰",
            "代中国证监会收取",
        ],
        "qualification": "INSUFFICIENT",
        "reason": "The issuer-owned JSON selector identifies the currently selected fee document but exposes no explicit nonblank validity status or complete fee-table successor/correction corpus.",
    },
    "stamp_duty": {
        "status": "NO39_EXPLICITLY_UNCLASSIFIED_ACROSS_PUBLISHED_STATUS_FILTERS",
        "status_filters": sta_results,
        "qualification": "INSUFFICIENT",
        "reason": "The exact No.39 record is returned only without an aging filter; every published status filter returns zero and the record's status, repeal date, and revision type remain blank.",
    },
    "adr_0006_effect": "Neither probe qualifies for receipt-time substitution because no explicit nonblank live-status API result exists for the probed act or fee table.",
    "authorized_next_phase": None,
}
write_json(ROOT / "analysis/live-status-api-probe-assessment.json", assessment)

operator_files = sorted(path for path in (ROOT / "operator").rglob("*.py") if path.is_file())
operator_manifest = {
    "type": "g12h_live_status_api_probe_operator_manifest_v1",
    "schema_version": 1,
    "operators": [
        {
            "path": str(path.relative_to(ROOT)),
            "sha256": sha(path),
            "exact_executed_copy": "/executed/" in f"/{path.relative_to(ROOT)}",
        }
        for path in operator_files
    ],
}
write_json(ROOT / "operator/manifest.json", operator_manifest)

manifest = {
    "type": "g12h_live_status_api_probe_manifest_v1",
    "schema_version": 1,
    "generated_at": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
    "status": assessment["overall_status"],
    "source_count": len(sources),
    "sources": sources,
    "analysis": {
        "path": "analysis/live-status-api-probe-assessment.json",
        "sha256": sha(ROOT / "analysis/live-status-api-probe-assessment.json"),
    },
    "private_response_header_store": {
        "path": "private-response-header-store-receipt.json",
        "sha256": sha(ROOT / "private-response-header-store-receipt.json"),
    },
    "operator_manifest": {"path": "operator/manifest.json", "sha256": sha(ROOT / "operator/manifest.json")},
    "authority_references": {
        "register_discovery_commit": "26f3a040c88d289c236c626c69b7fce8405d140a",
        "adr_0006_commit": "4c663bab458c075ee581becea06fef4908d6a57e",
        "acceptance_registry_commit": "2c531017dd0822a60b48bf8e1965f6eccb7767db",
    },
    "limitations": [
        "SZSE code=0 and message=成功 are retrieval success, not legal validity status.",
        "Blank docTitleStatusTime does not qualify under ADR 0006.",
        "STA status=1000 is search-service success, not legal validity status.",
        "Zero filtered results prove only that No.39 is unclassified under the published filters at capture time.",
        "No probe supplies complete fee-table or announcement successor/correction lineage coverage.",
    ],
}
write_json(ROOT / "manifest.json", manifest)
files = sorted(path for path in ROOT.rglob("*") if path.is_file() and path != ROOT / "sha256sums.txt")
(ROOT / "sha256sums.txt").write_text(
    "".join(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(ROOT)}\n" for path in files),
    encoding="utf-8",
)
print(json.dumps({"sources": len(sources), "files": len(files) + 1, "manifest_sha256": sha(ROOT / "manifest.json")}, indent=2))
