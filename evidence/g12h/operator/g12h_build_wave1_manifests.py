from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import urljoin

ROOT = Path('/tmp/backtest-g12h-f1-authority/evidence/g12h')


def sha(path: Path) -> str:
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def clean(value: str) -> str:
    return ' '.join(html.unescape(re.sub(r'<[^>]+>', '', value)).split())


def receipt(directory: Path) -> dict[str, object]:
    return json.loads((directory / 'receipt.json').read_text(encoding='utf-8'))


def source_ref(directory: Path) -> dict[str, object]:
    r = receipt(directory)
    request = json.loads((directory / 'request.json').read_text(encoding='utf-8'))
    return {
        'source_id': r['source_id'],
        'source_directory': str(directory.relative_to(ROOT)),
        'method': request['method'],
        'url': request['url'],
        'retrieved_at': r['retrieved_at'],
        'response_code': r['response_code'],
        'final_url': r['final_url'],
        'raw_sha256': r['raw_sha256'],
        'raw_byte_length': r['raw_byte_length'],
        'content_type': r['content_type'],
        'authority_status': r['authority_status'],
    }


def validate_package(directory: Path) -> None:
    sums = directory / 'sha256sums.txt'
    if not sums.exists():
        raise RuntimeError(f'missing sha256sums: {directory}')
    for line in sums.read_text(encoding='utf-8').splitlines():
        expected, relative = line.split('  ', 1)
        path = directory / relative
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RuntimeError(f'checksum mismatch: {path}')


def szse_general_entries(directory: Path, page_index: int) -> list[dict[str, object]]:
    text = (directory / 'raw.html').read_text(encoding='utf-8', errors='replace')
    pattern = re.compile(
        r'<li>\s*<div class="title">.*?var curHref\s*=\s*[\'\"]([^\'\"]+)[\'\"];.*?'
        r'var curTitle\s*=\s*[\'\"]([^\'\"]*)[\'\"];.*?'
        r'<span class="time">\s*([^<]+?)\s*</span>',
        re.S,
    )
    result = []
    for position, match in enumerate(pattern.finditer(text)):
        href, title, date = match.groups()
        result.append({
            'candidate_id': f'szse-general-{page_index:03d}-{position:02d}',
            'page_index': page_index,
            'position': position,
            'title': clean(title),
            'published_date': date.strip(),
            'url': urljoin('https://www.szse.cn/disclosure/notice/general/', href),
            'source_ref': {'source_id': receipt(directory)['source_id'], 'raw_sha256': receipt(directory)['raw_sha256']},
            'disposition': 'unresolved',
        })
    return result


def build_exchange() -> dict[str, object]:
    base = ROOT / 'exchange_handling'
    current_pages = [(0, base / 'szse-general-notice-index-live')]
    current_pages.extend((i, base / f'szse-general-notice-index-page-{i:02d}') for i in range(1, 16))
    entries = [entry for page, directory in current_pages for entry in szse_general_entries(directory, page)]
    search_dir = base / 'szse-search-transaction-handling-page-1'
    search = json.loads((search_dir / 'rendered.json').read_text(encoding='utf-8'))
    search_candidates = []
    for item in search['data']:
        search_candidates.append({
            'candidate_id': f"szse-search-{item['id']}",
            'title': clean(item['doctitle']),
            'published_epoch_milliseconds': item['docpubtime'],
            'url': item['docpuburl'].replace('http://', 'https://'),
            'json_url': urljoin('https://www.szse.cn', item['docpubjsonurl']),
            'source_ref': {'source_id': receipt(search_dir)['source_id'], 'raw_sha256': receipt(search_dir)['raw_sha256']},
            'disposition': 'unresolved',
        })
    inventory = {
        'type': 'g12h_exchange_handling_candidate_inventory_discovery_v1',
        'schema_version': 1,
        'status': 'DISCOVERY_ONLY_INSUFFICIENT',
        'declared_current_index': {
            'page_count': 16,
            'page_index_range': [0, 15],
            'captured_entry_count': len(entries),
            'latest_source_declared_notice_date': max((x['published_date'] for x in entries), default=None),
            'entries': entries,
        },
        'keyword_search': {
            'keyword': '交易经手费',
            'total_size': search['totalSize'],
            'page_1_source_id': receipt(search_dir)['source_id'],
            'terminal_page_2_source_id': 'szse-search-transaction-handling-terminal-page-2',
            'candidates': search_candidates,
        },
        'out_of_declared_range_captures': [
            {'source_id': 'szse-general-notice-index-page-16', 'reason': 'Accessible but outside page 0..15 declared by the captured current index.'},
            {'source_id': 'szse-general-notice-index-page-17-terminal', 'reason': 'Accessible but outside page 0..15 declared by the captured current index; not accepted as terminal proof.'},
        ],
        'closure_limit': 'Neither the general-notice index nor the keyword result is issuer-declared as a complete fee-table amendment/correction/successor register.',
    }
    write_json(base / 'candidate-inventory.discovery.json', inventory)
    return {'current_index_entries': len(entries), 'keyword_candidates': len(search_candidates), 'latest_notice_date': inventory['declared_current_index']['latest_source_declared_notice_date']}


def build_chinaclear() -> dict[str, object]:
    base = ROOT / 'chinaclear_transfer'
    pages = [(1, base / 'chinaclear-notice-center-iframe-live')]
    pages.extend((i, base / f'chinaclear-notice-center-page-{i:02d}') for i in range(2, 56))
    entries = []
    pattern = re.compile(r'<a class="title" href="([^"]+)"[^>]*>(.*?)</a>\s*<span class="date">([^<]+)</span>', re.S)
    page_receipts = []
    for page, directory in pages:
        text = (directory / 'raw.html').read_text(encoding='utf-8', errors='replace')
        r = receipt(directory)
        found = []
        for position, match in enumerate(pattern.finditer(text)):
            href, title, date = match.groups()
            item = {
                'candidate_id': f'chinaclear-notice-{page:02d}-{position:02d}',
                'page': page,
                'position': position,
                'title': clean(title),
                'published_date': date.strip(),
                'url': urljoin('https://www.chinaclear.cn', href),
                'source_ref': {'source_id': r['source_id'], 'raw_sha256': r['raw_sha256']},
                'disposition': 'unresolved',
            }
            entries.append(item); found.append(item)
        page_receipts.append({'page': page, 'source_id': r['source_id'], 'raw_sha256': r['raw_sha256'], 'response_code': r['response_code'], 'entry_count': len(found)})
    relevant_pattern = re.compile(r'过户费|收费|费用|费率|股票交易', re.I)
    relevant = [x for x in entries if relevant_pattern.search(x['title'])]
    pagination = {
        'type': 'g12h_chinaclear_notice_pagination_receipt_v1', 'schema_version': 1,
        'status': 'RANGE_TERMINATED_DISCOVERY_ONLY', 'declared_total_pages': 55, 'declared_total_count': 1082,
        'captured_total_count': len(entries), 'pages': page_receipts,
        'terminal_request': {
            'source_id': 'chinaclear-notice-center-page-56-terminal', 'response_code': 302,
            'location': 'http://www.chinaclear.cn',
            'meaning': 'Out-of-range page redirects to the issuer homepage; page 55 is the issuer-script-declared final page.',
        },
        'qualification_limit': 'The current notice corpus is not declared as a complete transfer-fee amendment/correction/successor register.',
    }
    inventory = {
        'type': 'g12h_chinaclear_transfer_candidate_inventory_discovery_v1', 'schema_version': 1,
        'status': 'DISCOVERY_ONLY_INSUFFICIENT', 'candidate_count': len(entries),
        'latest_source_declared_notice_date': max((x['published_date'] for x in entries), default=None),
        'fee_keyword_candidate_count': len(relevant), 'fee_keyword_candidate_ids': [x['candidate_id'] for x in relevant],
        'candidates': entries,
    }
    write_json(base / 'index-pagination-receipt.json', pagination)
    write_json(base / 'candidate-inventory.discovery.json', inventory)
    return {'candidates': len(entries), 'keyword_candidates': len(relevant), 'latest_notice_date': inventory['latest_source_declared_notice_date']}


def hkscc_rows(text: str, source_id: str, raw_hash: str) -> list[dict[str, object]]:
    rows = text.split('<div class="whats_on_tdy_row">')[1:]
    result = []
    for position, row in enumerate(rows):
        date_match = re.search(r'<div class="whats_on_tdy_ball_number"><div>([^<]+)</div></div><div>([^<]+)</div>', row)
        title_match = re.search(r'<div class="whats_on_tdy_text_2"><a href="([^"]+)"[^>]*>(.*?)(?:<span|</a>)', row, re.S)
        ref_match = re.search(r'<div class="whats_on_tdy_text_3">(.*?)</div>', row, re.S)
        category_match = re.search(r'<div class="whats_on_tdy_text_1">(.*?)</div>', row, re.S)
        if not date_match or not title_match:
            continue
        day, month_year = date_match.groups()
        href, title = title_match.groups()
        result.append({
            'candidate_id': '',
            'published_date_text': f'{day.strip()} {clean(month_year)}',
            'categories': clean(category_match.group(1)) if category_match else '',
            'title': clean(title),
            'reference_number': clean(ref_match.group(1)) if ref_match else '',
            'url': urljoin('https://www.hkex.com.hk', href),
            'source_ref': {'source_id': source_id, 'raw_sha256': raw_hash},
            'source_position': position,
            'disposition': 'unresolved',
        })
    return result


def build_hkscc() -> dict[str, object]:
    base = ROOT / 'hkscc_transfer'
    chunks = [base / 'hkscc-circular-candidate-index-2025-09-to-2026-08']
    chunks.extend(sorted(base.glob('hkscc-circular-loadmore-current-*')))
    entries = []
    chunks_receipt = []
    terminal_source = None
    for directory in chunks:
        r = receipt(directory)
        fragment = directory / ('raw.html' if directory.name == 'hkscc-circular-candidate-index-2025-09-to-2026-08' else 'rendered-fragment.html')
        if not fragment.exists():
            terminal_source = r['source_id']
            chunks_receipt.append({'source_id': r['source_id'], 'raw_sha256': r['raw_sha256'], 'entry_count': 0, 'terminal': True})
            continue
        found = hkscc_rows(fragment.read_text(encoding='utf-8', errors='replace'), str(r['source_id']), str(r['raw_sha256']))
        entries.extend(found)
        chunks_receipt.append({'source_id': r['source_id'], 'raw_sha256': r['raw_sha256'], 'entry_count': len(found), 'terminal': False})
    unique = []
    seen = set()
    duplicates = []
    for item in entries:
        key = (item['published_date_text'], item['reference_number'], item['url'])
        if key in seen:
            duplicates.append(key); continue
        seen.add(key)
        item['candidate_id'] = f'hkscc-circular-{len(unique):04d}'
        unique.append(item)
    relevant_pattern = re.compile(r'fee|charge|operational procedures|rule|amend|china connect', re.I)
    relevant = [x for x in unique if relevant_pattern.search(x['title'])]
    pagination = {
        'type': 'g12h_hkscc_circular_pagination_receipt_v1', 'schema_version': 1,
        'status': 'RANGE_TERMINATED_DISCOVERY_ONLY', 'date_from': '2025-09-01', 'date_to_inclusive': '2026-08-31',
        'category': 'HKSCC', 'initial_count': 20, 'load_more_count': 20,
        'chunks': chunks_receipt, 'terminal_source_id': terminal_source,
        'captured_candidate_count': len(unique), 'duplicate_count': len(duplicates),
        'qualification_limit': 'This range-terminated circular inventory does not itself prove that §21, Definitions, or the formal Operational Procedures amendment index is current through the target cutoff.',
    }
    latest_date = max((dt.datetime.strptime(x['published_date_text'], '%d %b %Y').date().isoformat() for x in unique), default=None)
    inventory = {
        'type': 'g12h_hkscc_transfer_candidate_inventory_discovery_v1', 'schema_version': 1,
        'status': 'DISCOVERY_ONLY_INSUFFICIENT', 'candidate_count': len(unique),
        'latest_source_declared_notice_date': latest_date,
        'relevance_keyword_candidate_count': len(relevant), 'relevance_keyword_candidate_ids': [x['candidate_id'] for x in relevant],
        'candidates': unique,
    }
    write_json(base / 'circular-pagination-receipt.json', pagination)
    write_json(base / 'candidate-inventory.discovery.json', inventory)
    return {'candidates': len(unique), 'duplicates': len(duplicates), 'keyword_candidates': len(relevant), 'latest_notice_date': latest_date, 'terminal': terminal_source}


def build_ndrc() -> dict[str, object]:
    base = ROOT / 'securities_regulatory'
    query_dirs = sorted(base.glob('ndrc-query-*-page-1'))
    candidates: dict[str, dict[str, object]] = {}
    query_receipts = []
    for directory in query_dirs:
        data = json.loads((directory / 'rendered.json').read_text(encoding='utf-8'))['data']
        r = receipt(directory)
        query_name = directory.name.removeprefix('ndrc-query-').removesuffix('-page-1')
        terminal = base / f'ndrc-query-{query_name}-terminal-page-2'
        query_receipts.append({
            'query_id': query_name, 'page_1_source_id': r['source_id'], 'total_hits': data['totalHits'],
            'terminal_page_2_source_id': receipt(terminal)['source_id'],
            'terminal_result_count': len(json.loads((terminal / 'rendered.json').read_text(encoding='utf-8'))['data'].get('resultList', [])),
        })
        for item in data['resultList']:
            key = item['url']
            candidate = candidates.setdefault(key, {
                'candidate_id': f'ndrc-{len(candidates):03d}', 'title': clean(item['title']), 'published_date': item['docDate'],
                'url': item['url'], 'query_provenance': [], 'source_refs': [], 'disposition': 'unresolved',
            })
            candidate['query_provenance'].append(query_name)
            candidate['source_refs'].append({'source_id': r['source_id'], 'raw_sha256': r['raw_sha256']})
    inventory = {
        'type': 'g12h_securities_regulatory_candidate_inventory_discovery_v1', 'schema_version': 1,
        'status': 'DISCOVERY_ONLY_INSUFFICIENT', 'queries': query_receipts,
        'candidate_count': len(candidates), 'latest_candidate_date': max(x['published_date'] for x in candidates.values()),
        'candidates': list(candidates.values()),
        'closure_limit': 'All located competent-rate candidates are pre-target; the NDRC search corpus is discovery, not an issuer-declared complete amendment/repeal/successor register.',
    }
    write_json(base / 'candidate-inventory.discovery.json', inventory)
    return {'candidates': len(candidates), 'latest_candidate_date': inventory['latest_candidate_date']}


def build_sta() -> dict[str, object]:
    base = ROOT / 'stamp_duty'
    families = {
        'stamp-duty-law-title': [base / 'sta-search-stamp-duty-law-title-page-0', base / 'sta-search-stamp-duty-law-title-page-1', base / 'sta-search-stamp-duty-law-title-terminal-page-2'],
        'securities-transaction-stamp-duty': [base / f'sta-search-securities-transaction-stamp-duty-page-{i}' for i in range(0, 12)] + [base / 'sta-search-securities-transaction-stamp-duty-terminal-page-12'],
        'half-securities-transaction-stamp-duty': [base / 'sta-search-half-securities-transaction-stamp-duty-page-0', base / 'sta-search-half-securities-transaction-stamp-duty-terminal-page-1'],
    }
    candidates: dict[str, dict[str, object]] = {}
    queries = []
    for family, directories in families.items():
        first = json.loads((directories[0] / 'rendered.json').read_text(encoding='utf-8'))['searchResultAll']
        query = first['searchCondition']['allSearchWord']
        page_receipts = []
        for directory in directories:
            data = json.loads((directory / 'rendered.json').read_text(encoding='utf-8'))['searchResultAll']
            r = receipt(directory)
            page_receipts.append({'source_id': r['source_id'], 'raw_sha256': r['raw_sha256'], 'result_count': len(data['searchTotal'])})
            for item in data['searchTotal']:
                key = item.get('id') or item['url']
                candidate = candidates.setdefault(key, {
                    'candidate_id': f'sta-{len(candidates):04d}', 'title': clean(item['title']),
                    'published_at': item.get('pubDate'), 'url': item['url'].replace('http://fgk.', 'https://fgk.'),
                    'column': item.get('column'), 'label': item.get('label'), 'source_owner': item.get('pubName'),
                    'query_provenance': [], 'source_refs': [], 'disposition': 'unresolved',
                })
                candidate['query_provenance'].append(family)
                candidate['source_refs'].append({'source_id': r['source_id'], 'raw_sha256': r['raw_sha256']})
        queries.append({'query_id': family, 'query': query, 'declared_total': first['total'], 'pages': page_receipts})
    exact_dir = base / 'sta-exact-search-schema-2023-39'
    exact = json.loads((exact_dir / 'rendered.json').read_text(encoding='utf-8'))
    inventory = {
        'type': 'g12h_stamp_duty_candidate_inventory_discovery_v1', 'schema_version': 1,
        'status': 'DISCOVERY_ONLY_INSUFFICIENT', 'queries': queries,
        'exact_2023_39_search': {
            'source_id': receipt(exact_dir)['source_id'], 'total': exact['searchResultAll']['total'],
            'response_result': exact.get('ResponseResult'), 'actual_column_id': exact.get('columnId'),
            'actual_columns': [{'id': x.get('id'), 'channel': x.get('channel'), 'label': x.get('label', '')} for x in exact.get('columns', [])],
        },
        'candidate_count': len(candidates),
        'latest_candidate_at': max((x['published_at'] for x in candidates.values() if x['published_at']), default=None),
        'candidates': list(candidates.values()),
        'closure_limit': 'Subject search results include news and policy records and are not a competent legislative amendment/repeal/correction register.',
    }
    write_json(base / 'candidate-inventory.discovery.json', inventory)
    return {'candidates': len(candidates), 'latest_candidate_at': inventory['latest_candidate_at']}


for directory in ROOT.glob('*/*'):
    if directory.is_dir() and (directory / 'receipt.json').exists():
        validate_package(directory)

summaries = {
    'exchange_handling': build_exchange(),
    'chinaclear_transfer': build_chinaclear(),
    'hkscc_transfer': build_hkscc(),
    'securities_regulatory': build_ndrc(),
    'stamp_duty': build_sta(),
}

cutoffs_dir = ROOT / 'cutoffs'; cutoffs_dir.mkdir(exist_ok=True)
cutoffs = {
    'type': 'g12h_cutoff_selection_receipt_v1', 'schema_version': 1,
    'status': 'INSUFFICIENT_NO_COMMON_OFFICIAL_RECORD_AS_OF',
    'target_to_exclusive': '2026-07-30T16:00:00Z',
    'lineage_record_states': [
        {'lineage': 'exchange_handling', 'qualified': False, 'candidate': 'SZSE general-notice index latest dated notice 2026-08-14', 'failure': 'Not a source-declared fee-table amendment/correction/successor record state; fee table label is 2026-01.'},
        {'lineage': 'securities_regulatory.ndrc_mof', 'qualified': False, 'candidate': 'NDRC query latest result 2022-01-07', 'failure': 'Pre-target and search corpus is discovery only.'},
        {'lineage': 'securities_regulatory.szse_collection', 'qualified': False, 'candidate': 'SZSE fee table label 2026-01', 'failure': 'Pre-target mutable collection table; no post-target source-declared status.'},
        {'lineage': 'chinaclear_transfer', 'qualified': False, 'candidate': 'ChinaClear current notice index latest dated notice 2026-08-07', 'failure': 'Notice corpus is not declared as the complete transfer-fee successor/correction register; fee table is updated 2026-01-01.'},
        {'lineage': 'hkscc_transfer', 'qualified': False, 'candidate': 'HKSCC circular range latest visible date 2026-08-20', 'failure': 'Circular corpus does not establish current §21 and Definitions record state; captured PDFs and formal rule-update index are pre-target.'},
        {'lineage': 'stamp_duty', 'qualified': False, 'candidate': 'STA subject-search latest result 2025-10-15 and undated current-page “全文有效” label', 'failure': 'No post-target competent legislative/policy status record or declared complete history register.'},
    ],
    'official_record_as_of': None,
    'query_start_local_date': None,
    'query_end_local_dates': {},
    'final_terminal_source_ref': None,
    'final_terminal_retrieved_at': None,
    'closure_evidence_available_at': None,
    'discovery_windows_not_qualified': {
        'ndrc_end_date': '2026-08-20', 'hkscc_date_from': '2025-09-01', 'hkscc_date_to_inclusive': '2026-08-31',
        'sta_subject_search': 'unbounded', 'szse_keyword_time': '0',
    },
    'stop_reason': 'At least one qualified source-declared post-target record state is missing for every economic lineage; inventory qualification and RuleBook production remain prohibited.',
}
write_json(cutoffs_dir / 'receipt.json', cutoffs)

sources = []
for lineage in ('exchange_handling', 'securities_regulatory', 'chinaclear_transfer', 'hkscc_transfer', 'stamp_duty'):
    for directory in sorted((ROOT / lineage).iterdir()):
        if directory.is_dir() and (directory / 'receipt.json').exists():
            sources.append({'lineage': lineage, **source_ref(directory)})

aggregate_files = []
for path in sorted(ROOT.glob('*/candidate-inventory.discovery.json')) + sorted(ROOT.glob('*/index-pagination-receipt.json')) + sorted(ROOT.glob('*/circular-pagination-receipt.json')) + [cutoffs_dir / 'receipt.json', ROOT / 'private-response-header-store-receipt.json', ROOT / 'scanner-sensitive-exact-byte-store-receipt.json', ROOT / 'operator/manifest.json', ROOT / 'operator/executed-acquisition-schedule.json']:
    aggregate_files.append({'path': str(path.relative_to(ROOT)), 'sha256': sha(path), 'byte_length': path.stat().st_size})

manifest = {
    'type': 'g12h_wave1_capture_manifest_v1', 'schema_version': 1,
    'generated_at': dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00', 'Z'),
    'status': 'WAVE1_CAPTURED_AUTHORITY_INSUFFICIENT',
    'scope_receipt': {'path': 'scope/receipt.json', 'sha256': sha(ROOT / 'scope/receipt.json')},
    'private_response_header_store_receipt': {'path': 'private-response-header-store-receipt.json', 'sha256': sha(ROOT / 'private-response-header-store-receipt.json')},
    'scanner_sensitive_exact_byte_store_receipt': {'path': 'scanner-sensitive-exact-byte-store-receipt.json', 'sha256': sha(ROOT / 'scanner-sensitive-exact-byte-store-receipt.json')},
    'operator_source_manifest': {'path': 'operator/manifest.json', 'sha256': sha(ROOT / 'operator/manifest.json')},
    'executed_acquisition_schedule': {'path': 'operator/executed-acquisition-schedule.json', 'sha256': sha(ROOT / 'operator/executed-acquisition-schedule.json')},
    'source_count': len(sources), 'sources': sources,
    'aggregate_artifacts': aggregate_files, 'summaries': summaries,
    'limitations': [
        'No browser renderer was installed; HTML packages retain exact raw server responses and deterministic text extractions, with rendered DOM explicitly unavailable.',
        'Exact server-issued cookie-bearing response headers are retained in the mode-restricted private store; Git-tracked copies replace cookie values with SHA-256 while retaining cookie names and attributes.',
        'One exact official HTML response containing a public client-side search key is retained in a separate mode-restricted store; its Git-tracked copy replaces the key with SHA-256 solely to satisfy generic secret scanning.',
        'Transport Date/Last-Modified/ETag are retained as transport facts and are not official record-state proof.',
        'All discovery inventories remain unresolved and non-authoritative; no RuleBook value, continuity, correction, or succession is inferred.',
        'The cutoff receipt is intentionally insufficient because no common qualified official_record_as_of exists.',
    ],
}
write_json(ROOT / 'wave1-manifest.json', manifest)

all_files = sorted(path for path in ROOT.rglob('*') if path.is_file() and path.name != 'wave1-sha256sums.txt')
(ROOT / 'wave1-sha256sums.txt').write_text(''.join(f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(ROOT)}\n' for path in all_files), encoding='utf-8')
print(json.dumps({'source_count': len(sources), 'summaries': summaries, 'manifest_sha256': sha(ROOT / 'wave1-manifest.json'), 'tree_files': len(all_files) + 1}, ensure_ascii=False, indent=2))
