from __future__ import annotations

import concurrent.futures
import datetime as dt
import hashlib
import html.parser
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(sys.argv[1]).resolve()
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36 G12HLiveStatusProbe/1.0"
HEADERS = (
    "Accept: */*",
    "Accept-Language: zh-CN,zh;q=0.9,en;q=0.5",
    "Cache-Control: no-cache",
    "Pragma: no-cache",
)

STA_QUERY = {
    "siteCode": "bm29000002",
    "column": "政策法规",
    "searchWord": "财政部 税务总局公告2023年第39号",
    "wordPlace": "0",
    "docType": "财政部税务总局公告",
    "docYear": "2023",
    "docNo": "39",
    "xxgkTaxPolicy": "税收政策",
    "xxgkSonTaxPolicy": "印花税",
    "xxgkFormulatedYear": "2023",
    "orderBy": "5",
    "participleRule": "5",
    "searchSiteName": "GSFFK",
    "pageNum": "0",
}
STA_STATUSES = (
    ("unfiltered", ""),
    ("full-valid", "全文有效"),
    ("modified", "已修改"),
    ("invalid", "全文失效"),
    ("repealed", "全文废止"),
    ("not-yet-effective", "尚未生效"),
)


def sta_url(status: str) -> str:
    return "https://www.chinatax.gov.cn/search5/search/s?" + urlencode(STA_QUERY | {"xxgkAging": status})


SOURCES = (
    ("exchange_handling", "szse-fee-selector-json-live", "https://www.szse.cn/marketServices/deal/payFees/index.json", "json"),
    ("exchange_handling", "szse-fee-document-2026-01-json-live", "https://www.szse.cn/marketServices/deal/payFees/t20251231_618209.json", "json"),
    ("exchange_handling", "szse-fee-document-2026-01-html-live", "https://www.szse.cn/marketServices/deal/payFees/t20251231_618209.html", "html"),
    *(("stamp_duty", f"sta-no39-status-{label}-live", sta_url(status), "json") for label, status in STA_STATUSES),
)

class TextExtractor(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self.skip += 1
        elif tag in {"p", "div", "li", "tr", "br", "h1", "h2", "h3", "h4", "h5", "h6"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self.skip:
            self.skip -= 1
        elif tag in {"p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.skip:
            self.parts.append(data)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_headers(path: Path) -> list[dict[str, object]]:
    text = path.read_bytes().decode("latin-1")
    blocks: list[dict[str, object]] = []
    for raw_block in re.split(r"\r?\n\r?\n", text):
        lines = [line for line in raw_block.splitlines() if line]
        if not lines or not lines[0].startswith("HTTP/"):
            continue
        headers: list[dict[str, str]] = []
        for line in lines[1:]:
            if ":" in line:
                name, value = line.split(":", 1)
                headers.append({"name": name, "value": value.lstrip()})
        blocks.append({"status_line": lines[0], "headers": headers})
    return blocks


def charset_from_headers(blocks: list[dict[str, object]]) -> str:
    if blocks:
        for item in blocks[-1]["headers"]:  # type: ignore[index]
            if item["name"].lower() == "content-type":
                match = re.search(r"charset=([^;\s]+)", item["value"], re.I)
                if match:
                    return match.group(1).strip('"')
    return "utf-8"


def extract_html(raw: Path, output: Path, blocks: list[dict[str, object]]) -> dict[str, object]:
    charset = charset_from_headers(blocks)
    try:
        text = raw.read_bytes().decode(charset)
        decode_errors = False
    except (LookupError, UnicodeDecodeError):
        text = raw.read_bytes().decode("utf-8", errors="replace")
        charset = "utf-8-replacement"
        decode_errors = True
    parser = TextExtractor()
    parser.feed(text)
    lines = [" ".join(line.split()) for line in "".join(parser.parts).splitlines()]
    result = "\n".join(line for line in lines if line) + "\n"
    output.write_text(result, encoding="utf-8")
    return {"charset": charset, "decode_errors": decode_errors}


def render_pdf(raw: Path, base: Path) -> dict[str, object]:
    if not raw.read_bytes().startswith(b"%PDF"):
        return {"pdf_valid": False, "rendered_pages": 0, "extracted": False}
    extracted = base / "extracted.txt"
    text_run = subprocess.run(["pdftotext", "-layout", str(raw), str(extracted)], capture_output=True, text=True)
    rendered = base / "rendered"
    rendered.mkdir()
    render_run = subprocess.run(["pdftoppm", "-png", "-r", "150", str(raw), str(rendered / "page")], capture_output=True, text=True)
    pages = sorted(rendered.glob("page-*.png"))
    return {
        "pdf_valid": True,
        "rendered_pages": len(pages),
        "extracted": text_run.returncode == 0,
        "pdftotext_exit_code": text_run.returncode,
        "pdftotext_stderr": text_run.stderr,
        "pdftoppm_exit_code": render_run.returncode,
        "pdftoppm_stderr": render_run.stderr,
    }


def capture(source: tuple[str, str, str, str]) -> dict[str, object]:
    lineage, source_id, url, extension = source
    destination = ROOT / lineage / source_id
    if destination.exists():
        return {"lineage": lineage, "source_id": source_id, "error": "destination exists"}
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=f".{source_id}.", dir=destination.parent))
    started = utc_now()
    raw = temp / f"raw.{extension}"
    headers_path = temp / "response.headers"
    transport_path = temp / "transport.log"
    metadata_path = temp / "curl-metadata.json"
    request = {
        "type": "g12h_official_http_request_v1",
        "schema_version": 1,
        "method": "GET",
        "url": url,
        "headers": [{"name": "User-Agent", "value": USER_AGENT}] + [
            {"name": value.split(":", 1)[0], "value": value.split(":", 1)[1].strip()} for value in HEADERS
        ],
        "request_body": None,
        "authentication": "none",
        "redirect_policy": {"follow": True, "maximum": 10, "redirect_protocols": ["https"]},
    }
    write_json(temp / "request.json", request)
    command = [
        "curl", "--location", "--max-redirs", "10", "--proto", "=http,https", "--proto-redir", "=https",
        "--silent", "--show-error", "--connect-timeout", "30", "--max-time", "180", "--retry", "2",
        "--retry-all-errors", "--user-agent", USER_AGENT,
    ]
    for header in HEADERS:
        command.extend(["--header", header])
    command.extend([
        "--dump-header", str(headers_path), "--output", str(raw), "--verbose", "--stderr", str(transport_path),
        "--write-out", "%{json}\n", url,
    ])
    run = subprocess.run(command, capture_output=True, text=True)
    finished = utc_now()
    try:
        metadata = json.loads(run.stdout) if run.stdout.strip() else {}
    except json.JSONDecodeError:
        metadata = {"write_out_parse_error": True, "stdout": run.stdout}
    write_json(metadata_path, metadata)
    blocks = parse_headers(headers_path) if headers_path.exists() else []
    write_json(temp / "redirects.json", {"type": "g12h_http_response_chain_v1", "schema_version": 1, "responses": blocks})
    derivatives: dict[str, object] = {}
    if raw.exists() and extension == "html":
        derivatives["text_extraction"] = extract_html(raw, temp / "extracted.txt", blocks)
        derivatives["rendered_dom"] = {"available": False, "reason": "No browser renderer is installed in the acquisition environment; raw server response and deterministic text extraction retained."}
    elif raw.exists() and extension == "json":
        try:
            parsed = json.loads(raw.read_text(encoding="utf-8"))
            write_json(temp / "rendered.json", parsed)
            derivatives["json_parse"] = {"valid": True}
        except Exception as error:
            derivatives["json_parse"] = {"valid": False, "error": str(error)}
    elif raw.exists() and extension == "pdf":
        derivatives["pdf"] = render_pdf(raw, temp)
    tool_version = subprocess.check_output(["curl", "--version"], text=True).splitlines()[0]
    receipt = {
        "type": "g12h_official_http_capture_receipt_v1",
        "schema_version": 1,
        "lineage": lineage,
        "source_id": source_id,
        "started_at": started,
        "retrieved_at": finished,
        "tool": tool_version,
        "operator_harness_sha256": "sha256:" + hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "curl_exit_code": run.returncode,
        "curl_stderr": run.stderr,
        "response_code": metadata.get("response_code"),
        "final_url": metadata.get("url_effective"),
        "redirect_count": metadata.get("num_redirects"),
        "content_type": metadata.get("content_type"),
        "raw_file": raw.name if raw.exists() else None,
        "raw_sha256": digest(raw) if raw.exists() else None,
        "raw_byte_length": raw.stat().st_size if raw.exists() else None,
        "response_chain_count": len(blocks),
        "derivatives": derivatives,
        "authority_status": "CAPTURED_NOT_QUALIFIED",
    }
    write_json(temp / "receipt.json", receipt)
    files = sorted(path for path in temp.rglob("*") if path.is_file() and path.name != "sha256sums.txt")
    (temp / "sha256sums.txt").write_text(
        "".join(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(temp)}\n" for path in files),
        encoding="utf-8",
    )
    os.replace(temp, destination)
    return {"lineage": lineage, "source_id": source_id, "response_code": receipt["response_code"], "exit": run.returncode, "bytes": receipt["raw_byte_length"], "raw_sha256": receipt["raw_sha256"]}


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(capture, SOURCES))
    print(json.dumps(results, ensure_ascii=False, indent=2))
    failed = [item for item in results if item.get("error") or item.get("exit") != 0]
    if failed:
        print(f"capture failures: {len(failed)}", file=sys.stderr)

if __name__ == "__main__":
    main()
