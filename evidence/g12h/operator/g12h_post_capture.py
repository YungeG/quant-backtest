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
from urllib.parse import urlencode

sys.argv = ['g12h_wave1_capture', sys.argv[1]]
spec = importlib.util.spec_from_file_location('cap', Path(__file__).with_name('g12h_wave1_capture.py'))
cap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cap)
ROOT = Path(sys.argv[1]).resolve()


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00', 'Z')


def capture(source_id: str, page: int) -> dict[str, object]:
    lineage = 'exchange_handling'
    url = 'https://www.szse.cn/api/search/content'
    destination = ROOT / lineage / source_id
    if destination.exists():
        raise RuntimeError(f'{destination} exists')
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=f'.{source_id}.', dir=destination.parent))
    body = urlencode([
        ('keyword', '交易经手费'),
        ('time', '0'),
        ('range', 'title'),
        ('channelCode[]', 'general_news'),
        ('currentPage', str(page)),
        ('pageSize', '50'),
    ]).encode('ascii')
    (temp / 'request.body').write_bytes(body)
    request = {
        'type': 'g12h_official_http_request_v1',
        'schema_version': 1,
        'method': 'POST',
        'url': url,
        'headers': [
            {'name': 'User-Agent', 'value': cap.USER_AGENT},
            {'name': 'Accept', 'value': 'application/json, text/plain, */*'},
            {'name': 'Accept-Language', 'value': 'zh-CN,zh;q=0.9,en;q=0.5'},
            {'name': 'Content-Type', 'value': 'application/x-www-form-urlencoded; charset=UTF-8'},
            {'name': 'Cache-Control', 'value': 'no-cache'},
            {'name': 'Pragma', 'value': 'no-cache'},
        ],
        'request_body_file': 'request.body',
        'request_body_sha256': 'sha256:' + hashlib.sha256(body).hexdigest(),
        'authentication': 'none',
        'redirect_policy': {'follow': True, 'maximum': 10, 'redirect_protocols': ['https']},
    }
    cap.write_json(temp / 'request.json', request)
    raw = temp / 'raw.json'
    headers = temp / 'response.headers'
    transport = temp / 'transport.log'
    started = now()
    command = [
        'curl', '--location', '--max-redirs', '10', '--proto', '=https', '--proto-redir', '=https',
        '--silent', '--show-error', '--connect-timeout', '30', '--max-time', '180', '--retry', '2', '--retry-all-errors',
        '--user-agent', cap.USER_AGENT,
        '--header', 'Accept: application/json, text/plain, */*',
        '--header', 'Accept-Language: zh-CN,zh;q=0.9,en;q=0.5',
        '--header', 'Content-Type: application/x-www-form-urlencoded; charset=UTF-8',
        '--header', 'Cache-Control: no-cache', '--header', 'Pragma: no-cache',
        '--data-binary', '@' + str(temp / 'request.body'),
        '--dump-header', str(headers), '--output', str(raw), '--verbose', '--stderr', str(transport),
        '--write-out', '%{json}\n', url,
    ]
    run = subprocess.run(command, capture_output=True, text=True)
    finished = now()
    metadata = json.loads(run.stdout) if run.stdout.strip() else {}
    cap.write_json(temp / 'curl-metadata.json', metadata)
    blocks = cap.parse_headers(headers)
    cap.write_json(temp / 'redirects.json', {'type': 'g12h_http_response_chain_v1', 'schema_version': 1, 'responses': blocks})
    parse_status: dict[str, object]
    try:
        parsed = json.loads(raw.read_text(encoding='utf-8'))
        cap.write_json(temp / 'rendered.json', parsed)
        parse_status = {'valid': True}
    except Exception as error:
        parse_status = {'valid': False, 'error': str(error)}
    receipt = {
        'type': 'g12h_official_http_capture_receipt_v1',
        'schema_version': 1,
        'lineage': lineage,
        'source_id': source_id,
        'started_at': started,
        'retrieved_at': finished,
        'tool': subprocess.check_output(['curl', '--version'], text=True).splitlines()[0],
        'operator_harness_sha256': 'sha256:' + hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'curl_exit_code': run.returncode,
        'response_code': metadata.get('response_code'),
        'final_url': metadata.get('url_effective'),
        'redirect_count': metadata.get('num_redirects'),
        'content_type': metadata.get('content_type'),
        'raw_file': raw.name,
        'raw_sha256': cap.digest(raw),
        'raw_byte_length': raw.stat().st_size,
        'response_chain_count': len(blocks),
        'derivatives': {'json_parse': parse_status},
        'authority_status': 'DISCOVERY_ONLY_NOT_SUCCESSOR_CLOSURE',
    }
    cap.write_json(temp / 'receipt.json', receipt)
    files = sorted(path for path in temp.rglob('*') if path.is_file() and path.name != 'sha256sums.txt')
    (temp / 'sha256sums.txt').write_text(''.join(f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(temp)}\n' for path in files), encoding='utf-8')
    os.replace(temp, destination)
    return {'source_id': source_id, 'response_code': receipt['response_code'], 'raw_sha256': receipt['raw_sha256'], 'bytes': receipt['raw_byte_length']}

print(json.dumps([
    capture('szse-search-transaction-handling-page-1', 1),
    capture('szse-search-transaction-handling-terminal-page-2', 2),
], ensure_ascii=False, indent=2))
