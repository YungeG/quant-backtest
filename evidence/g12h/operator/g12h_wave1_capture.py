from __future__ import annotations

import concurrent.futures
import datetime as dt
import hashlib
import html.parser
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(sys.argv[1]).resolve()
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36 G12HAuthorityCapture/1.0"
HEADERS = (
    "Accept: */*",
    "Accept-Language: zh-CN,zh;q=0.9,en;q=0.5",
    "Cache-Control: no-cache",
    "Pragma: no-cache",
)

SOURCES = (
    ("exchange_handling", "szse-fee-table-2026-01-live", "https://www.szse.cn/marketServices/deal/payFees/index.html", "html"),
    ("exchange_handling", "szse-notice-2023-768-html", "https://www.szse.cn/disclosure/notice/general/t20230818_602805.html", "html"),
    ("exchange_handling", "szse-notice-2023-768-json", "https://www.szse.cn/disclosure/notice/general/t20230818_602805.json", "json"),
    ("exchange_handling", "szse-general-notice-index-live", "https://www.szse.cn/disclosure/notice/general/index.html", "html"),
    ("securities_regulatory", "ndrc-2018-917", "https://www.ndrc.gov.cn/xxgk/zcfb/ghxwj/201806/t20180627_960950.html?code=", "html"),
    ("securities_regulatory", "ndrc-2021-1947", "https://www.ndrc.gov.cn/xxgk/zcfb/tz/202201/t20220107_1311590.html", "html"),
    ("securities_regulatory", "ndrc-document-library-regulatory-query-live", "https://www.ndrc.gov.cn/xxgk/wjk/index.html?tab=all&qt=%E8%AF%81%E5%88%B8%E6%9C%9F%E8%B4%A7%E4%B8%9A%E7%9B%91%E7%AE%A1%E8%B4%B9", "html"),
    ("securities_regulatory", "szse-regulatory-collection-table-2026-01-live", "https://www.szse.cn/marketServices/deal/payFees/index.html", "html"),
    ("chinaclear_transfer", "chinaclear-fee-standard-parent-live", "https://www.chinaclear.cn/zdjs/fbzyls/service_tlist.shtml", "html"),
    ("chinaclear_transfer", "chinaclear-fee-standard-iframe-live", "https://www.chinaclear.cn/zdjs/fbzyls/service_tlist/code_0.shtml", "html"),
    ("chinaclear_transfer", "chinaclear-szse-fee-table-2025-12-pdf", "https://www.chinaclear.cn/zdjs/fbzyls/202512/a59388fbfa714c5fa546784891a42e30/files/%E6%B7%B1%E5%9C%B3%E5%B8%82%E5%9C%BA%E8%AF%81%E5%88%B8%E7%99%BB%E8%AE%B0%E7%BB%93%E7%AE%97%E4%B8%9A%E5%8A%A1%E6%94%B6%E8%B4%B9%E5%8F%8A%E4%BB%A3%E6%94%B6%E7%A8%8E%E8%B4%B9%E4%B8%80%E8%A7%88%E8%A1%A8.pdf", "pdf"),
    ("chinaclear_transfer", "chinaclear-stock-transfer-notice-2022", "https://www.chinaclear.cn/zdjs/gszb/202204/837e3c5031104aa099d6597ba381342a.shtml", "html"),
    ("chinaclear_transfer", "chinaclear-notice-center-index-live", "https://www.chinaclear.cn/zdjs/xtzgg/center_flist.shtml", "html"),
    ("hkscc_transfer", "hkscc-operational-procedures-index-live", "https://www.hkex.com.hk/Services/Rules-and-Forms-and-Fees/Rules/HKSCC/Operational-Procedures?sc_lang=en", "html"),
    ("hkscc_transfer", "hkscc-operational-procedures-sec21-live", "https://www.hkex.com.hk/-/media/HKEX-Market/Services/Rules-and-Forms-and-Fees/Rules/HKSCC/Operational-Procedures/SEC21.pdf", "pdf"),
    ("hkscc_transfer", "hkscc-operational-procedures-definitions-live", "https://www.hkex.com.hk/-/media/HKEX-Market/Services/Rules-and-Forms-and-Fees/Rules/HKSCC/Operational-Procedures/Definiti.pdf", "pdf"),
    ("hkscc_transfer", "hkscc-rule-update-index-live", "https://www.hkex.com.hk/Services/Rules-and-Forms-and-Fees/Rules/HKSCC/Rules/Rule-Update_HKSCC-Operational-Procedures?sc_lang=en", "html"),
    ("stamp_duty", "sta-stamp-duty-law", "https://fgk.chinatax.gov.cn/zcfgk/c100009/c5193058/content.html", "html"),
    ("stamp_duty", "sta-announcement-2023-39", "https://fgk.chinatax.gov.cn/zcfgk/c102416/c5211343/content.html", "html"),
    ("stamp_duty", "gov-cn-announcement-2023-39", "https://www.gov.cn/zhengce/zhengceku/202308/content_6900443.htm", "html"),
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
