from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
sys.argv = ['g12h_wave1_capture', str(ROOT)]
spec = importlib.util.spec_from_file_location('cap', Path(__file__).with_name('g12h_wave1_capture.py'))
cap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cap)

LINEAGE = 'hkscc_transfer'
INDEX_ID = 'hkscc-circular-candidate-index-2025-09-to-2026-08'
INDEX_URL = 'https://www.hkex.com.hk/Services/Circulars-and-Notices/Participant-and-Members-Circulars?sc_lang=en&Category=HKSCC&DateFrom=2025-09-01&DateTo=2026-08-31'
POST_URL = 'https://www.hkex.com.hk/layouts/HKEX_Common/Tab/NewsCentreDetailsLoad.aspx/DisplayNewsCentreDetailsLoad'
html = (ROOT / LINEAGE / INDEX_ID / 'raw.html').read_text(encoding='utf-8', errors='replace')


def hidden(name: str) -> str:
    tag = re.search(rf'<input[^>]+id=["\']{re.escape(name)}["\'][^>]*>', html, re.I)
    if not tag:
        raise RuntimeError(f'missing hidden field {name}')
    value = re.search(r'value=["\']([^"\']*)["\']', tag.group(0), re.I)
    return value.group(1) if value else ''

base = {
    'pageUrl': hidden('pageUrl'),
    'TopicFieldName': hidden('TopicFieldName'),
    'DateFieldName': hidden('DateFieldName'),
    'FilesFieldName': hidden('FilesFieldName'),
    'ImageFieldName': hidden('ImageFieldName'),
    'ContentFieldName': hidden('ContentFieldName'),
    'Category1FieldName': hidden('Category1FieldName'),
    'Category2FieldName': hidden('Category2FieldName'),
    'Category3FieldName': hidden('Category3FieldName'),
    'loadmorecount': int(hidden('LoadMoreCount')),
    'IsLoadMore': True,
    'isCardView': hidden('isCardView'),
    'TabItemSourceID': hidden('tabItemSourceID'),
    'datefrom': hidden('datefrom'),
    'dateto': hidden('dateto'),
    'category': hidden('category'),
    'keyword': hidden('keyword'),
    'isHideDay': hidden('isHideDay'),
    'category2': hidden('category2'),
    'TargetLanguage': re.search(r'<html[^>]+lang=["\']([^"\']+)', html, re.I).group(1),
    'TargetSite': '',
    'host': hidden('urlHost'),
}


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00', 'Z')


def capture(currentcount: int) -> tuple[dict[str, object], bool]:
    source_id = f'hkscc-circular-loadmore-current-{currentcount:04d}'
    destination = ROOT / LINEAGE / source_id
    if destination.exists():
        raise RuntimeError(f'{destination} exists')
    temp = Path(tempfile.mkdtemp(prefix=f'.{source_id}.', dir=destination.parent))
    payload = {**base, 'currentcount': currentcount}
    body = (json.dumps(payload, ensure_ascii=False, separators=(',', ':')) + '\n').encode('utf-8')
    (temp / 'request.body').write_bytes(body)
    cap.write_json(temp / 'request.json', {
        'type': 'g12h_official_http_request_v1', 'schema_version': 1, 'method': 'POST', 'url': POST_URL,
        'headers': [
            {'name': 'User-Agent', 'value': cap.USER_AGENT},
            {'name': 'Accept', 'value': 'application/json, text/javascript, */*; q=0.01'},
            {'name': 'Accept-Language', 'value': 'en,zh-CN;q=0.8,zh;q=0.7'},
            {'name': 'Content-Type', 'value': 'application/json; charset=utf-8'},
            {'name': 'Origin', 'value': 'https://www.hkex.com.hk'},
            {'name': 'Referer', 'value': INDEX_URL},
            {'name': 'X-Requested-With', 'value': 'XMLHttpRequest'},
        ],
        'request_body_file': 'request.body', 'request_body_sha256': 'sha256:' + hashlib.sha256(body).hexdigest(),
        'authentication': 'none', 'redirect_policy': {'follow': True, 'maximum': 10, 'redirect_protocols': ['https']},
        'derived_from_source_id': INDEX_ID,
    })
    raw = temp / 'raw.json'; headers = temp / 'response.headers'; transport = temp / 'transport.log'
    started = now()
    command = [
        'curl', '--location', '--max-redirs', '10', '--proto', '=https', '--proto-redir', '=https',
        '--silent', '--show-error', '--connect-timeout', '30', '--max-time', '180', '--retry', '2', '--retry-all-errors',
        '--user-agent', cap.USER_AGENT,
        '--header', 'Accept: application/json, text/javascript, */*; q=0.01',
        '--header', 'Accept-Language: en,zh-CN;q=0.8,zh;q=0.7',
        '--header', 'Content-Type: application/json; charset=utf-8',
        '--header', 'Origin: https://www.hkex.com.hk', '--header', f'Referer: {INDEX_URL}',
        '--header', 'X-Requested-With: XMLHttpRequest', '--data-binary', '@' + str(temp / 'request.body'),
        '--dump-header', str(headers), '--output', str(raw), '--verbose', '--stderr', str(transport),
        '--write-out', '%{json}\n', POST_URL,
    ]
    run = subprocess.run(command, capture_output=True, text=True)
    metadata = json.loads(run.stdout) if run.stdout.strip() else {}
    cap.write_json(temp / 'curl-metadata.json', metadata)
    blocks = cap.parse_headers(headers)
    cap.write_json(temp / 'redirects.json', {'type': 'g12h_http_response_chain_v1', 'schema_version': 1, 'responses': blocks})
    try:
        parsed = json.loads(raw.read_text(encoding='utf-8'))
        cap.write_json(temp / 'rendered.json', parsed)
        content = parsed.get('d')
        valid = True
    except Exception as error:
        parsed = None; content = None; valid = False
        (temp / 'parse-error.txt').write_text(str(error) + '\n', encoding='utf-8')
    if isinstance(content, str) and content:
        (temp / 'rendered-fragment.html').write_text(content, encoding='utf-8')
        extractor = cap.TextExtractor(); extractor.feed(content)
        lines = [' '.join(line.split()) for line in ''.join(extractor.parts).splitlines()]
        (temp / 'extracted.txt').write_text('\n'.join(line for line in lines if line) + '\n', encoding='utf-8')
    finished = now()
    receipt = {
        'type': 'g12h_official_http_capture_receipt_v1', 'schema_version': 1, 'lineage': LINEAGE,
        'source_id': source_id, 'started_at': started, 'retrieved_at': finished,
        'tool': subprocess.check_output(['curl', '--version'], text=True).splitlines()[0],
        'operator_harness_sha256': 'sha256:' + hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'curl_exit_code': run.returncode, 'response_code': metadata.get('response_code'),
        'final_url': metadata.get('url_effective'), 'redirect_count': metadata.get('num_redirects'),
        'content_type': metadata.get('content_type'), 'raw_file': raw.name, 'raw_sha256': cap.digest(raw),
        'raw_byte_length': raw.stat().st_size, 'response_chain_count': len(blocks),
        'derivatives': {'json_parse': {'valid': valid}, 'fragment_present': bool(content)},
        'authority_status': 'DISCOVERY_RANGE_CAPTURED_NOT_QUALIFIED',
    }
    cap.write_json(temp / 'receipt.json', receipt)
    files = sorted(path for path in temp.rglob('*') if path.is_file() and path.name != 'sha256sums.txt')
    (temp / 'sha256sums.txt').write_text(''.join(f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(temp)}\n' for path in files), encoding='utf-8')
    os.replace(temp, destination)
    return ({'source_id': source_id, 'response_code': receipt['response_code'], 'bytes': receipt['raw_byte_length'], 'fragment_present': bool(content), 'raw_sha256': receipt['raw_sha256']}, not bool(content))

results=[]
current=int(hidden('currentLoadCount'))
for _ in range(100):
    result, terminal = capture(current)
    results.append(result)
    if terminal:
        break
    current += int(base['loadmorecount'])
else:
    raise RuntimeError('load-more did not terminate within 100 requests')
print(json.dumps(results, ensure_ascii=False, indent=2))
