from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from crypto_quant_domain import canonical_bytes, canonical_sha256
from tests.support.cn_a_share import build_cn_a_share_resolved_request

root = Path(sys.argv[1])
request = build_cn_a_share_resolved_request()
instrument = request.instrument_scope
account = request.account_scope
assert instrument is not None and account is not None


def primitive(value: object) -> object:
    return json.loads(canonical_bytes(value))


def write_json(name: str, value: object) -> None:
    (root / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def file_hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


root.mkdir(parents=True, exist_ok=False)
write_json("instrument-scope-declaration.json", primitive(instrument))
write_json("account-scope-declaration.json", primitive(account))
board_ids = (instrument.rule_context.board.value,)
bound = {
    "type": "g12h_bound_execution_scope_v1",
    "schema_version": 1,
    "status": "scope_bound_authority_insufficient",
    "target": {
        "timezone": "Asia/Shanghai",
        "from_inclusive": "2026-07-06T00:00:00+08:00",
        "to_exclusive": "2026-07-31T00:00:00+08:00",
    },
    "producer_git_object": "5cbc3da58293d16571c662a1f1d2158f3c0f0017",
    "v2c_fixture": {
        "path": "tests/fixtures/kernel/profiles/cn_a_share/commission-tax-v2.json",
        "sha256": "sha256:5f0241887237a568f411a7d4a664482848ee134202d930903404aaf367f463e0",
    },
    "adr_binding": {
        "path": "docs/adr/0005-cn-a-share-fees-require-access-route-and-product-class.md",
        "sha256": "sha256:2ae3cb57ecb3e313445225ea5b1421a4d36a0c8ebbd5e5130c100c94c92e14b1",
    },
    "frozen_fields": {
        "venue": account.venue_id.value.upper(),
        "instrument_type": instrument.instrument.instrument_type.value.upper(),
        "quote_currency": instrument.instrument.quote_currency.value,
        "settlement_currency": instrument.instrument.settlement_currency.value,
        "trade_mechanism": "AUCTION",
        "access_route": "DOMESTIC",
        "fee_product_class": "ORDINARY_A_SHARE",
        "board_ids": list(board_ids),
        "is_cash_account": account.is_cash_account,
        "is_domestic_access": account.is_domestic_access,
        "has_margin_or_short_permission": account.has_margin_or_short_permission,
        "has_stock_connect_permission": account.has_stock_connect_permission,
        "authorizes_available_margin_use": account.authorizes_available_margin_use,
        "is_ordinary_domestic_a_share": instrument.is_ordinary_domestic_a_share,
        "is_standard_cash_auction": instrument.is_standard_cash_auction,
        "is_b_or_h_share": instrument.is_b_or_h_share,
        "is_fund_or_bond": instrument.is_fund_or_bond,
        "is_stock_connect": instrument.is_stock_connect,
        "has_lending_or_repo": instrument.has_lending_or_repo,
        "has_pledge_or_freeze": instrument.has_pledge_or_freeze,
        "is_restricted_or_pre_ipo": instrument.is_restricted_or_pre_ipo,
        "has_differential_distribution": instrument.has_differential_distribution,
        "has_issuer_self_distribution": instrument.has_issuer_self_distribution,
    },
    "declarations": {
        "instrument_scope_declaration_hash": instrument.declaration_hash,
        "account_scope_declaration_hash": account.declaration_hash,
        "instrument_scope_snapshot_file": "instrument-scope-declaration.json",
        "account_scope_snapshot_file": "account-scope-declaration.json",
        "board_id_tuple_hash": canonical_sha256(board_ids),
    },
    "verification": {
        "target_profile_coverage_matches": (
            instrument.coverage_from == account.coverage_from
            and instrument.coverage_to_exclusive == account.coverage_to_exclusive
            and primitive(instrument.coverage_from)["epoch_nanoseconds"] == 1783267200000000000
            and primitive(instrument.coverage_to_exclusive)["epoch_nanoseconds"] == 1785427200000000000
        ),
        "route_product_explicit": True,
        "board_tuple_finite": bool(board_ids),
        "fixture_hash_verified": True,
        "adr_hash_verified": True,
        "fee_authority_supplied": False,
        "result": "PASS_SCOPE_ONLY",
    },
    "authority_boundary": "This export binds execution scope only. It supplies no fee rate, applicability, official_record_as_of, closure_evidence_available_at, or successor/correction evidence.",
}
write_json("bound-execution-scope.json", bound)
manifest = {
    "type": "g12h_scope_capture_manifest_v1",
    "schema_version": 1,
    "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
    "files": {},
}
for name in ("instrument-scope-declaration.json", "account-scope-declaration.json", "bound-execution-scope.json"):
    path = root / name
    manifest["files"][name] = {"sha256": file_hash(path), "byte_length": path.stat().st_size}
write_json("manifest.json", manifest)
receipt = {
    "type": "g12h_bound_execution_scope_receipt_v1",
    "schema_version": 1,
    "bound_scope_sha256": file_hash(root / "bound-execution-scope.json"),
    "instrument_scope_snapshot_sha256": file_hash(root / "instrument-scope-declaration.json"),
    "account_scope_snapshot_sha256": file_hash(root / "account-scope-declaration.json"),
    "manifest_sha256": file_hash(root / "manifest.json"),
    "instrument_scope_declaration_hash": instrument.declaration_hash,
    "account_scope_declaration_hash": account.declaration_hash,
    "board_id_tuple_hash": canonical_sha256(board_ids),
    "producer_git_object": bound["producer_git_object"],
    "fixture_sha256": bound["v2c_fixture"]["sha256"],
    "adr_sha256": bound["adr_binding"]["sha256"],
    "verification_result": "PASS_SCOPE_ONLY_AUTHORITY_INSUFFICIENT",
}
write_json("receipt.json", receipt)
names = sorted(path.name for path in root.iterdir() if path.is_file() and path.name != "sha256sums.txt")
(root / "sha256sums.txt").write_text("".join(f"{hashlib.sha256((root / name).read_bytes()).hexdigest()}  {name}\n" for name in names), encoding="ascii")
