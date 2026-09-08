from __future__ import annotations

import argparse
import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast
from urllib.request import HTTPRedirectHandler, Request, build_opener

from crypto_quant_bundle_builder import RawSourceMember, SourceSnapshotProvenance, freeze_source_snapshot

from ._common import AcquisitionError, json_bytes, publish_directory, require_new_output, sha256

_URL = "https://docs.static.szse.cn/www/lawrules/rule/repeal/rules/W020230217564423808793.pdf"
_SHA256 = "sha256:7018114a6e11deb239c2a72e71e49defc6e8841b3e2c093b3bbf809282c67222"
_MEMBER = "attachment/szse-trading-rules-2023.pdf"
_FLAGS = ("source_bounded", "decision_grade_eligible", "live_eligible", "deployment_authorized")

Fetch = Callable[[str], tuple[int, bytes]]


@dataclass(frozen=True, slots=True)
class SzseTradingRules2023FixedSourceRequestV1:
    source_url: str = field(default_factory=lambda: _URL)
    expected_sha256: str = field(default_factory=lambda: _SHA256)

    def __post_init__(self) -> None:
        if (self.source_url, self.expected_sha256) != (_URL, _SHA256):
            raise ValueError("request must bind the exact official SZSE 2023 attachment")

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "szse_trading_rules_2023_fixed_source_request_v1", "schema_version": 1, "source_url": self.source_url, "expected_sha256": self.expected_sha256}


@dataclass(frozen=True, slots=True)
class SzseTradingRules2023FixedSourceDeclarationV1:
    request: SzseTradingRules2023FixedSourceRequestV1

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "szse_trading_rules_2023_fixed_source_declaration_v1", "schema_version": 1, "request": self.request.to_canonical_dict(), "raw_members": {_MEMBER: _SHA256}, "source_bounded": True, "decision_grade_eligible": False, "live_eligible": False, "deployment_authorized": False}


@dataclass(frozen=True, slots=True)
class SzseTradingRules2023FixedSourceReceiptV1:
    request: SzseTradingRules2023FixedSourceRequestV1
    acquired_at_epoch_nanoseconds: int
    snapshot: dict[str, object]
    declaration_sha256: str

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "szse_trading_rules_2023_fixed_source_acquisition_receipt_v1", "schema_version": 1, "request": self.request.to_canonical_dict(), "http_status": 200, "attachment_sha256": _SHA256, "acquired_at_epoch_nanoseconds": self.acquired_at_epoch_nanoseconds, "snapshot": self.snapshot, "declaration_sha256": self.declaration_sha256, "source_bounded": True, "decision_grade_eligible": False, "live_eligible": False, "deployment_authorized": False}


def _load_json(path: Path) -> tuple[bytes, dict[str, object]]:
    raw = path.read_bytes()
    try:
        value = json.loads(raw, object_pairs_hook=lambda pairs: _unique_object(pairs))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise AcquisitionError("fixed source metadata is not valid JSON") from error
    if type(value) is not dict:
        raise AcquisitionError("fixed source metadata is not a JSON object")
    return raw, value


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _valid_attachment(content: bytes) -> bool:
    return bool(content) and content.startswith(b"%PDF-") and sha256(content) == _SHA256


def acquire_szse_trading_rules_2023_fixed_source_v1(request: SzseTradingRules2023FixedSourceRequestV1, *, output_dir: str | Path, acquired_at_epoch_nanoseconds: int, fetch: Fetch) -> dict[str, object]:
    if type(request) is not SzseTradingRules2023FixedSourceRequestV1:
        raise AcquisitionError("request must be exact fixed SZSE source request")
    if type(acquired_at_epoch_nanoseconds) is not int or acquired_at_epoch_nanoseconds < 0:
        raise AcquisitionError("acquisition time is invalid")
    require_new_output(output_dir)
    status, content = fetch(_URL)
    if status != 200 or not _valid_attachment(content):
        raise AcquisitionError("official SZSE attachment status, format, or checksum mismatch")
    snapshot = freeze_source_snapshot(
        members=(RawSourceMember(_MEMBER, content, "0644", acquired_at_epoch_nanoseconds, _SHA256),),
        provenance=SourceSnapshotProvenance(vendor_key="szse.cn", source_key="szse.cn.trading-rules.2023.fixed-attachment", license_ref="szse.public-rules", retention_policy_ref="backtest.acquisition.candidate"),
    ).snapshot
    if snapshot is None:
        raise AcquisitionError("SourceSnapshot freeze failed")
    declaration = SzseTradingRules2023FixedSourceDeclarationV1(request).to_canonical_dict()
    declaration_bytes = json_bytes(declaration)
    receipt = SzseTradingRules2023FixedSourceReceiptV1(request, acquired_at_epoch_nanoseconds, snapshot.to_canonical_dict(), sha256(declaration_bytes)).to_canonical_dict()
    publish_directory(output_dir, {_MEMBER: content, "source-snapshot.json": json_bytes(snapshot.to_canonical_dict()), "declaration.json": declaration_bytes, "acquisition-receipt.json": json_bytes(receipt)})
    return receipt


def verify_szse_trading_rules_2023_fixed_source_v1(output_dir: str | Path) -> dict[str, object]:
    root = Path(output_dir)
    receipt_bytes, receipt = _load_json(root / "acquisition-receipt.json")
    declaration_bytes, declaration = _load_json(root / "declaration.json")
    snapshot_bytes, snapshot = _load_json(root / "source-snapshot.json")
    content = (root / _MEMBER).read_bytes()
    if {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()} != {_MEMBER, "source-snapshot.json", "declaration.json", "acquisition-receipt.json"}:
        raise AcquisitionError("published file set mismatch")
    request = SzseTradingRules2023FixedSourceRequestV1().to_canonical_dict()
    expected_declaration = SzseTradingRules2023FixedSourceDeclarationV1(SzseTradingRules2023FixedSourceRequestV1()).to_canonical_dict()
    if not _valid_attachment(content) or declaration != expected_declaration or declaration_bytes != json_bytes(declaration):
        raise AcquisitionError("attachment or declaration identity mismatch")
    expected_receipt_fields = {"type", "schema_version", "request", "http_status", "attachment_sha256", "acquired_at_epoch_nanoseconds", "snapshot", "declaration_sha256", *_FLAGS}
    acquired_at = receipt.get("acquired_at_epoch_nanoseconds")
    if (set(receipt) != expected_receipt_fields or receipt.get("type") != "szse_trading_rules_2023_fixed_source_acquisition_receipt_v1" or receipt.get("schema_version") != 1 or receipt.get("request") != request or receipt.get("http_status") != 200 or receipt.get("attachment_sha256") != _SHA256 or type(acquired_at) is not int or cast(int, acquired_at) < 0 or tuple(receipt.get(flag) for flag in _FLAGS) != (True, False, False, False)):
        raise AcquisitionError("receipt schema, source binding, or policy flags mismatch")
    expected_snapshot = freeze_source_snapshot(
        members=(RawSourceMember(_MEMBER, content, "0644", cast(int, acquired_at), _SHA256),),
        provenance=SourceSnapshotProvenance(vendor_key="szse.cn", source_key="szse.cn.trading-rules.2023.fixed-attachment", license_ref="szse.public-rules", retention_policy_ref="backtest.acquisition.candidate"),
    ).snapshot
    if (expected_snapshot is None or snapshot != expected_snapshot.to_canonical_dict() or snapshot_bytes != json_bytes(snapshot) or receipt.get("snapshot") != snapshot or receipt.get("declaration_sha256") != sha256(declaration_bytes) or receipt_bytes != json_bytes(receipt)):
        raise AcquisitionError("receipt, declaration, or snapshot substitution detected")
    return receipt


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req: Request, fp: object, code: int, msg: str, headers: object, newurl: str) -> None:
        return None


def _stdlib_fetch(url: str) -> tuple[int, bytes]:
    try:
        with build_opener(_NoRedirect).open(Request(url), timeout=30) as response:
            return cast(int, response.status), response.read()
    except Exception as error:
        raise AcquisitionError("official attachment fetch failed") from error


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capture the fixed official SZSE 2023 trading-rules attachment")
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        receipt = acquire_szse_trading_rules_2023_fixed_source_v1(SzseTradingRules2023FixedSourceRequestV1(), output_dir=args.output_dir, acquired_at_epoch_nanoseconds=time.time_ns(), fetch=_stdlib_fetch)
    except (AcquisitionError, ValueError) as error:
        raise SystemExit(f"acquisition failed: {error}") from None
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
