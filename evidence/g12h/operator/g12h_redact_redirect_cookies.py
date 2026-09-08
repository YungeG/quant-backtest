from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

ROOT = Path('/tmp/backtest-g12h-f1-authority/evidence/g12h')
PRIVATE = Path('/srv/bcache-8t/ygguo/backtest/g12h-authority-private/20260820-wave1-response-headers')


def sha_bytes(value: bytes) -> str:
    return 'sha256:' + hashlib.sha256(value).hexdigest()


def sha_file(path: Path) -> str:
    return sha_bytes(path.read_bytes())

for path in PRIVATE.rglob('*'):
    if path.is_dir(): os.chmod(path, 0o700)
    elif path.is_file(): os.chmod(path, 0o600)
os.chmod(PRIVATE, 0o700)

updated = 0
for redirects in sorted(ROOT.glob('*/*/redirects.json')):
    raw = redirects.read_bytes()
    data = json.loads(raw)
    changed = False
    for response in data.get('responses', []):
        for header in response.get('headers', []):
            if header.get('name', '').lower() != 'set-cookie':
                continue
            value = header['value']
            if '<redacted sha256:' in value:
                continue
            cookie, separator, attrs = value.partition(';')
            name, equals, cookie_value = cookie.partition('=')
            if not equals:
                continue
            header['value'] = f'{name}=<redacted {sha_bytes(cookie_value.encode("latin-1"))}>' + (separator + attrs if separator else '')
            changed = True
    if not changed:
        continue
    source_dir = redirects.parent
    private_path = PRIVATE / redirects.relative_to(ROOT)
    private_path.parent.mkdir(parents=True, exist_ok=True)
    private_path.write_bytes(raw)
    record = {
        'tracked_path': str(redirects.relative_to(ROOT)),
        'tracked_redacted_sha256': '',
        'exact_private_path': str(private_path),
        'exact_private_sha256': sha_bytes(raw),
        'redaction': 'Set-Cookie value replaced by its SHA-256; cookie name and attributes retained.',
    }
    redirects.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    record['tracked_redacted_sha256'] = sha_file(redirects)
    receipt_path = source_dir / 'receipt.json'
    receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
    receipt.setdefault('sensitive_response_headers', {'policy': 'Exact server-issued cookie values are excluded from Git and retained in the mode-restricted private evidence store.', 'files': []})
    receipt['sensitive_response_headers']['files'].append(record)
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    source_receipt_path = source_dir / 'sensitive-response-header-receipt.json'
    source_receipt = json.loads(source_receipt_path.read_text(encoding='utf-8'))
    source_receipt['files'].append(record)
    source_receipt_path.write_text(json.dumps(source_receipt, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    files = sorted(path for path in source_dir.rglob('*') if path.is_file() and path.name != 'sha256sums.txt')
    (source_dir / 'sha256sums.txt').write_text(''.join(f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(source_dir)}\n' for path in files), encoding='utf-8')
    updated += 1

records=[]
for receipt_path in sorted(ROOT.glob('*/*/sensitive-response-header-receipt.json')):
    records.append(json.loads(receipt_path.read_text(encoding='utf-8')))
private_manifest = {
    'type': 'g12h_private_response_header_manifest_v1', 'schema_version': 1,
    'policy': 'Private store contains exact response header/redirect/transport bytes with transient server-issued cookie values. It contains no user credentials or request secrets.',
    'record_count': len(records), 'records': records,
}
manifest_path = PRIVATE / 'manifest.json'
manifest_path.write_text(json.dumps(private_manifest, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
public_receipt = {
    'type': 'g12h_private_response_header_store_receipt_v1', 'schema_version': 1,
    'private_store_root': str(PRIVATE), 'private_manifest_sha256': sha_file(manifest_path),
    'source_count': len(records), 'status': 'EXACT_COOKIE_BEARING_HEADERS_PRIVATE_TRACKED_HEADERS_REDACTED',
}
(ROOT / 'private-response-header-store-receipt.json').write_text(json.dumps(public_receipt, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
for path in sorted(PRIVATE.rglob('*'), reverse=True):
    os.chmod(path, 0o500 if path.is_dir() else 0o400)
os.chmod(PRIVATE, 0o500)
print(json.dumps({'updated_redirects': updated, **public_receipt}, indent=2))
