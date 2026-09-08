from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from pathlib import Path

ROOT = Path('/tmp/backtest-g12h-f1-authority/evidence/g12h')
PRIVATE = Path('/srv/bcache-8t/ygguo/backtest/g12h-authority-private/20260820-wave1-response-headers')
COOKIE = re.compile(r'(?i)^(?P<prefix>(?:<\s*)?set-cookie:\s*)(?P<name>[^=;\r\n]+)=(?P<value>[^;\r\n]*)(?P<attrs>.*)$')


def sha_bytes(value: bytes) -> str:
    return 'sha256:' + hashlib.sha256(value).hexdigest()


def sha_file(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def redact_line(line: str) -> tuple[str, bool]:
    ending = ''
    if line.endswith('\r\n'):
        ending = '\r\n'; body = line[:-2]
    elif line.endswith('\n'):
        ending = '\n'; body = line[:-1]
    else:
        body = line
    match = COOKIE.match(body)
    if not match:
        return line, False
    digest = sha_bytes(match.group('value').encode('latin-1'))
    redacted = f"{match.group('prefix')}{match.group('name')}=<redacted {digest}>{match.group('attrs')}{ending}"
    return redacted, True

records = []
for source_dir in sorted(path.parent for path in ROOT.glob('*/*/response.headers')):
    sensitive_files = []
    for name in ('response.headers', 'transport.log'):
        path = source_dir / name
        if not path.exists():
            continue
        raw = path.read_bytes()
        text = raw.decode('latin-1')
        redacted_lines = []
        changed = False
        for line in text.splitlines(keepends=True):
            value, line_changed = redact_line(line)
            redacted_lines.append(value); changed = changed or line_changed
        if not changed:
            continue
        relative = path.relative_to(ROOT)
        private_path = PRIVATE / relative
        private_path.parent.mkdir(parents=True, exist_ok=True)
        private_path.write_bytes(raw)
        os.chmod(private_path, 0o400)
        path.write_bytes(''.join(redacted_lines).encode('latin-1'))
        sensitive_files.append({
            'tracked_path': str(relative),
            'tracked_redacted_sha256': sha_file(path),
            'exact_private_path': str(private_path),
            'exact_private_sha256': sha_bytes(raw),
            'redaction': 'Set-Cookie value replaced by its SHA-256; cookie name and attributes retained.',
        })
    if sensitive_files:
        receipt_path = source_dir / 'receipt.json'
        receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
        receipt['sensitive_response_headers'] = {
            'policy': 'Exact server-issued cookie values are excluded from Git and retained in the mode-restricted private evidence store.',
            'files': sensitive_files,
        }
        receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        source_receipt = {
            'type': 'g12h_sensitive_response_header_receipt_v1',
            'schema_version': 1,
            'source_id': receipt['source_id'],
            'private_store_root': str(PRIVATE),
            'files': sensitive_files,
        }
        (source_dir / 'sensitive-response-header-receipt.json').write_text(json.dumps(source_receipt, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        files = sorted(path for path in source_dir.rglob('*') if path.is_file() and path.name != 'sha256sums.txt')
        (source_dir / 'sha256sums.txt').write_text(''.join(f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(source_dir)}\n' for path in files), encoding='utf-8')
        records.append({'source_id': receipt['source_id'], 'files': sensitive_files})

private_manifest = {
    'type': 'g12h_private_response_header_manifest_v1',
    'schema_version': 1,
    'policy': 'Private store contains exact response header/transport bytes with transient server-issued cookie values. It contains no user credentials or request secrets.',
    'record_count': len(records),
    'records': records,
}
manifest_path = PRIVATE / 'manifest.json'
manifest_path.write_text(json.dumps(private_manifest, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
os.chmod(manifest_path, 0o400)
for directory in sorted((path for path in PRIVATE.rglob('*') if path.is_dir()), reverse=True):
    os.chmod(directory, 0o500)
os.chmod(PRIVATE, 0o500)

public_receipt = {
    'type': 'g12h_private_response_header_store_receipt_v1',
    'schema_version': 1,
    'private_store_root': str(PRIVATE),
    'private_manifest_sha256': sha_file(manifest_path),
    'source_count': len(records),
    'status': 'EXACT_COOKIE_BEARING_HEADERS_PRIVATE_TRACKED_HEADERS_REDACTED',
}
(ROOT / 'private-response-header-store-receipt.json').write_text(json.dumps(public_receipt, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
print(json.dumps(public_receipt, indent=2))
