from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path('/tmp/backtest-g12h-f1-authority/evidence/g12h')
SOURCE = ROOT / 'securities_regulatory/ndrc-document-library-regulatory-query-live'
RAW = SOURCE / 'raw.html'
PRIVATE = Path('/srv/bcache-8t/ygguo/backtest/g12h-authority-private/20260820-wave1-scanner-sensitive-exact-bytes')
KEY = sys.argv[1]


def sha_bytes(value: bytes) -> str:
    return 'sha256:' + hashlib.sha256(value).hexdigest()

def sha_file(path: Path) -> str:
    return sha_bytes(path.read_bytes())

PRIVATE.mkdir(parents=True, exist_ok=False, mode=0o700)
exact = RAW.read_bytes()
text = exact.decode('utf-8')
count = text.count(KEY)
if count != 2:
    raise RuntimeError(f'expected two public API key literals, found {count}')
private_raw = PRIVATE / RAW.relative_to(ROOT)
private_raw.parent.mkdir(parents=True, exist_ok=True)
private_raw.write_bytes(exact)
redaction = f'<redacted {sha_bytes(KEY.encode("ascii"))}>'
RAW.write_text(text.replace(KEY, redaction), encoding='utf-8')
record = {
    'tracked_path': str(RAW.relative_to(ROOT)),
    'tracked_redacted_sha256': sha_file(RAW),
    'tracked_redacted_byte_length': RAW.stat().st_size,
    'exact_private_path': str(private_raw),
    'exact_private_sha256': sha_bytes(exact),
    'exact_private_byte_length': len(exact),
    'redaction': 'Public client-side NDRC search key replaced by its SHA-256 in Git to satisfy secret scanning; exact official bytes retained externally.',
}
receipt_path = SOURCE / 'receipt.json'
receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
receipt['scanner_sensitive_exact_bytes'] = record
receipt['tracked_raw_sha256'] = record['tracked_redacted_sha256']
receipt['tracked_raw_byte_length'] = record['tracked_redacted_byte_length']
receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
source_receipt = {'type': 'g12h_scanner_sensitive_exact_byte_receipt_v1', 'schema_version': 1, 'source_id': receipt['source_id'], **record}
(SOURCE / 'scanner-sensitive-exact-byte-receipt.json').write_text(json.dumps(source_receipt, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
files = sorted(path for path in SOURCE.rglob('*') if path.is_file() and path.name != 'sha256sums.txt')
(SOURCE / 'sha256sums.txt').write_text(''.join(f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(SOURCE)}\n' for path in files), encoding='utf-8')
manifest = {
    'type': 'g12h_scanner_sensitive_exact_byte_store_manifest_v1', 'schema_version': 1,
    'policy': 'Store contains exact official public response bytes whose embedded client-side search key triggers generic secret scanning. It contains no user credentials.',
    'records': [record],
}
manifest_path = PRIVATE / 'manifest.json'
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
public = {
    'type': 'g12h_scanner_sensitive_exact_byte_store_receipt_v1', 'schema_version': 1,
    'private_store_root': str(PRIVATE), 'private_manifest_sha256': sha_file(manifest_path),
    'source_count': 1, 'status': 'EXACT_PUBLIC_BYTES_EXTERNAL_TRACKED_COPY_REDACTED',
}
(ROOT / 'scanner-sensitive-exact-byte-store-receipt.json').write_text(json.dumps(public, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
for path in sorted(PRIVATE.rglob('*'), reverse=True): os.chmod(path, 0o500 if path.is_dir() else 0o400)
os.chmod(PRIVATE, 0o500)
print(json.dumps(public, indent=2))
