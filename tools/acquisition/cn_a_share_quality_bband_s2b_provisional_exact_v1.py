from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import math
import os
import re
import shutil
import stat
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import NoReturn

from crypto_quant_bundle_builder import (
    RawSourceMember,
    SourceSnapshot,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
    verify_source_snapshot,
)
from crypto_quant_domain import InstrumentId, UtcInstant, VenueId, canonical_sha256

import crypto_quant_bundle_builder.official_annual_report_nonfiling_v1 as nonfiling
import crypto_quant_bundle_builder.pan_hai_2014_official_balance_backfill_v1 as pan_hai

_API_NAMES = ("income_vip", "balancesheet_vip", "cashflow_vip")
_EXCLUDED_INDUSTRIES = ("银行", "保险", "证券", "多元金融")
_PROVIDER_CODE = re.compile(r"([0-9]{6})\.(SZ|SH)\Z")
_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_BASE_COMMIT = "8d532da4a58eea22dd6e9f6ce7f5b13cfafbfbe0"

_FIELDS = {
    "s0": (
        "ts_code", "symbol", "name", "area", "industry", "fullname", "enname",
        "cnspell", "market", "exchange", "curr_type", "list_status", "list_date",
        "delist_date", "is_hs", "act_name", "act_ent_type",
    ),
    "annual_roster": ("trade_date", "ts_code", "name", "industry", "list_date"),
    "income_vip": (
        "ts_code", "ann_date", "f_ann_date", "end_date", "report_type", "comp_type",
        "revenue", "operate_profit", "total_profit", "income_tax", "n_income",
        "n_income_attr_p", "minority_gain", "fin_exp_int_exp", "ebit", "ebitda",
        "update_flag",
    ),
    "balancesheet_vip": (
        "ts_code", "ann_date", "f_ann_date", "end_date", "report_type", "comp_type",
        "money_cap", "total_assets", "total_liab", "total_hldr_eqy_inc_min_int",
        "total_hldr_eqy_exc_min_int", "minority_int", "total_liab_hldr_eqy", "st_borr",
        "non_cur_liab_due_1y", "lt_borr", "bond_payable", "st_bonds_payable",
        "update_flag",
    ),
    "cashflow_vip": (
        "ts_code", "ann_date", "f_ann_date", "end_date", "report_type", "comp_type",
        "n_cashflow_act", "c_pay_acq_const_fiolta", "depr_fa_coga_dpba",
        "use_right_asset_dep", "amort_intang_assets", "lt_amort_deferred_exp",
        "c_cash_equ_end_period", "free_cashflow", "update_flag",
    ),
}


@dataclass(frozen=True, slots=True)
class _FrozenSourceIdentity:
    snapshot_id: str
    content_tree_hash: str
    provenance_hash: str
    snapshot_file_sha256: str
    receipt_file_sha256: str
    regular_file_count: int


_SOURCE_IDENTITIES = {
    "s0": _FrozenSourceIdentity(
        "sha256:b5b7a9243439146181ef07acd07c09e79d16f605bc6cfdc3148746e64359e198",
        "sha256:5533ce876c38ff320b69ca876dff57af763168d654f82142e9c53c90ecca2418",
        "sha256:953aecfb488562177a51392283d8dace326470041cc0594d8982fb3482849c36",
        "sha256:b1c8b0edf3f27860c69a1996f6e22360f578c44d518920ec395839adf6ac6235",
        "sha256:ee1b32d5ea28a7c923f48676b9e4e05fc58dcd9eaef578a59280e8952a30c722",
        5,
    ),
    "annual_roster": _FrozenSourceIdentity(
        "sha256:22585fa4c2070d87544f0ba977be757770aeeaad5bead30188317c1794680ee8",
        "sha256:7e4046b2ffc13993de8ab33ddbe4410aef2f464d8c16b19000998acbb20cbb9e",
        "sha256:7bb6d65da4702e6c34649cf52dc0285fb2e2115246fca0e978b434da6176af22",
        "sha256:ed7f01abb90c0b937078beb39739202ec80070e61c26e6d624dd70f8a6181ad1",
        "sha256:9eab20190ae05c4a49a8763ad77cfc9d1ed874c7c56e2258f3a595e2a8b7c9d6",
        13,
    ),
    "s2a": _FrozenSourceIdentity(
        "sha256:4e6574363c36f6cebe7f0ad46585a3a9e31b623546240196a2b8bcf55ec57160",
        "sha256:3316ea2f6c71f092f5bd803aad6731039b2bc6956c7f176c67183ecaded3e199",
        "sha256:fb1bfdc0646988d4881bb8a7c1abef61ebce91f46844b6cc83eb6925dc560e09",
        "sha256:f0f1d394e98b298d0bb59990370c6ffb26ad70b89cb99aade3026f732aa1cba3",
        "sha256:30afdba09e0a04da1257489a7e13fcee062f41233006fe1d5d8bc33c748791a9",
        247,
    ),
    "pan_hai": _FrozenSourceIdentity(
        "sha256:8195e9d9e99949802c829f218929bdbf740b336152d83ad789a060e0355d116e",
        "sha256:c315b9b36d5817fc058da240b50e2c170f530f2b2b4b49808554ef6ddedac15b",
        "sha256:cbce2903c280938647526abfc0511cc497d85d61f5486e79469ab0714a9c05a2",
        "sha256:78448e043e966b929d48db6c547be22e2102a498bd6c2a73c1ce47f9208d7294",
        "sha256:6d60f18e75ca87a1762430d34b43b2af08d141f5103af39573779dde09144fa7",
        24,
    ),
}

_EXPECTED_SET_HASHES = {
    "screen_membership_hash": "sha256:00b6f4487ffd946ca1db05a4fc353f45ba9da235cc954e1248902da3103a8f2b",
    "period_requirements_hash": "sha256:87f0ad15a76bc01561e0347f59a720e26b657829198774bf14893df7ef4fe846",
    "instrument_union_hash": "sha256:25d69f75295afe13549269e96d9fbeb726605ac5c93e78d9cfe46ecf48f30ab0",
    "expected_pairs_hash": "sha256:336efc4e947062036b1c98add7977653c48abdab8f33350516626a521b9b2b3e",
    "expected_member_keys_hash": "sha256:0269e22c9f45b24b827e98a91515ac31ae5486ba0fda668f69112400b088e44b",
}
_EXPECTED_SCREEN_COUNTS = (1995, 2034, 2053, 2143, 2224, 2434, 2612, 2635, 2667)
_EXPECTED_OUTPUTS = {
    "provisional-expected-set.json": (6587372, "sha256:55c4ecdee60e77feec3d2ee8c4d8da5b16a4e6a1e07bf2acc49a08669b8d1a29"),
    "provider-rows.jsonl": (90363445, "sha256:f4ed00c232930e1067c2796f7e5c3622397e8649e1afa0d5ae8730c964cf7abe"),
    "official-coverage.json": (17755, "sha256:a0971482128b6e4e2f0bcdbdbb10f1102211974fd98157c0185ec25fc08e5b3b"),
    "extraction-manifest.json": (62418, "sha256:74c60758f4b6eb9534900f868bdef444e5891ad6b4eee996e6713eb2e8ea876f"),
}
_EXPECTED_IDS = {
    "expected_set": "sha256:8c679397ff7ecfe67e0bbf68951d9fa388de9f2adfaf53a4f8b5395b0cea2cf6",
    "official_coverage": "sha256:f245ebd560bb15644b1b072d277d3847d3477e7125677bd2e683e5a7c0636907",
    "manifest": "sha256:e526416335016b9fd421e138655303673e76dc2bf6e2f53a6bb580904ed70d74",
    "provider_row_ids": "sha256:04e8a893976e36fbdf3a186ea42d51897e03f09d6f849337a214d87f86c531c6",
    "pan_hai_backfill": "sha256:a19316973eb26196cf5cdd1292387cc41e55d2340d5ff98f8c66ba3e65dcd28a",
    "nonfiling_publication": "sha256:4a6f1e3231a1b840ac3b4320c4ca445f6ebf40b402a7ac6ac1efd1ad989a4c97",
}
_NONFILING_RECEIPT_SHA256 = "sha256:6c20ed90b6928b0de19c2a49832d8a68f3cea2f31cc15ad20d0b6d5ca91c78ce"
_NONFILING_DECLARATION_IDS = (
    "sha256:7b62db5d3872239d950ffde56e554031f9664697a5509bf6e702a33a92e57249",
    "sha256:f89e297bca2ec6c155d067a66c2d4077e7879c9fdbe6c8a38541ee37d4ab9bf1",
    "sha256:15f33287200634b56e902dbc34eab6f620968eb93c490b548e8e011e55bb4140",
    "sha256:410f32d6c1f57a49207ef365ce548134ab4137ab361bc2d3fbcd9794153d7f91",
    "sha256:b0434c86b036188c632c64552bcdea5ab57aae043f6e3ef0515bacc4fabc50f7",
    "sha256:766084db597d13e209eadbc87723e42e6054f88446092e793891db7d8f203c0e",
    "sha256:d5db185b8b864e1960dad88487ed9e265e663d64e1f5b5e9e679047fd7305b14",
)


class QualityBbandS2bProvisionalExactExtractionFailure(str, Enum):
    INPUT_TYPE_MISMATCH = "INPUT_TYPE_MISMATCH"
    CATALOG_IDENTITY_MISMATCH = "CATALOG_IDENTITY_MISMATCH"
    SOURCE_MEMBER_CONFLICT = "SOURCE_MEMBER_CONFLICT"
    FINANCIAL_REVISION_MISMATCH = "FINANCIAL_REVISION_MISMATCH"
    FINANCIAL_PAYLOAD_INCOMPLETE = "FINANCIAL_PAYLOAD_INCOMPLETE"
    PUBLICATION_INTEGRITY_FAILURE = "PUBLICATION_INTEGRITY_FAILURE"
    BUNDLE_EXACT_COVER_MISMATCH = "BUNDLE_EXACT_COVER_MISMATCH"


class QualityBbandS2bProvisionalExactExtractionError(RuntimeError):
    def __init__(
        self,
        code: QualityBbandS2bProvisionalExactExtractionFailure,
        reason: str | None = None,
    ) -> None:
        if type(code) is not QualityBbandS2bProvisionalExactExtractionFailure:
            raise TypeError("code must be an exact extraction failure")
        if reason is not None and (type(reason) is not str or not reason or "/" in reason):
            raise ValueError("reason must be a redacted stage-local token")
        self.code = code
        self.reason = reason
        super().__init__(code.value if reason is None else f"{code.value}/{reason}")


@dataclass(frozen=True, slots=True)
class _LoadedSourceRoot:
    root: Path
    snapshot: SourceSnapshot
    snapshot_metadata: dict[str, object]
    receipt: dict[str, object]
    member_bytes: dict[str, bytes]


def _fail(
    code: QualityBbandS2bProvisionalExactExtractionFailure,
    reason: str | None = None,
) -> NoReturn:
    raise QualityBbandS2bProvisionalExactExtractionError(code, reason)


def _json_value(value: object) -> object:
    if isinstance(value, (InstrumentId, UtcInstant)):
        return _json_value(value.to_canonical_dict())
    if type(value) is date:
        return value.isoformat()
    if type(value) is Decimal:
        return format(value, "f")
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    return value


def _canonical_json(value: object) -> str:
    return json.dumps(
        _json_value(value),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _json_bytes(value: object) -> bytes:
    return (_canonical_json(value) + "\n").encode("utf-8")


def _canonical_hash(value: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _bytes_hash(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _strict_json(raw: bytes) -> object:
    def pairs(values: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in values:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def invalid_constant(value: str) -> NoReturn:
        raise ValueError(f"nonfinite JSON value {value}")

    def finite_float(value: str) -> float:
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError(f"nonfinite JSON value {value}")
        return parsed

    try:
        return json.loads(
            raw,
            object_pairs_hook=pairs,
            parse_constant=invalid_constant,
            parse_float=finite_float,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise ValueError("strict JSON parse failure") from error


def _dict(value: object, *, keys: set[str] | None = None) -> dict[str, object]:
    if type(value) is not dict:
        raise TypeError("expected exact JSON object")
    result = value
    if keys is not None and set(result) != keys:
        raise ValueError("JSON object schema mismatch")
    return result


def _list(value: object) -> list[object]:
    if type(value) is not list:
        raise TypeError("expected exact JSON array")
    return value


def _text(value: object) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError("expected canonical non-empty text")
    return value


def _integer(value: object, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError("expected exact nonnegative integer")
    return value


def _sha(value: object) -> str:
    text = _text(value)
    if _HASH.fullmatch(text) is None:
        raise ValueError("expected canonical sha256")
    return text


def _canonical_instrument(provider_code: object) -> dict[str, str]:
    code = _text(provider_code)
    match = _PROVIDER_CODE.fullmatch(code)
    if match is None:
        _fail(QualityBbandS2bProvisionalExactExtractionFailure.CATALOG_IDENTITY_MISMATCH)
    stable_key, suffix = match.groups()
    return {
        "type": "instrument_id",
        "venue": "xshe" if suffix == "SZ" else "xshg",
        "stable_key": stable_key,
    }


def _instrument_sort_key(value: dict[str, str]) -> tuple[str, str]:
    return value["venue"], value["stable_key"]


def _path_files(root: Path) -> set[str]:
    files: set[str] = set()
    try:
        if root.is_symlink() or not root.is_dir():
            raise ValueError
        for directory, names, filenames in os.walk(root, followlinks=False):
            current = Path(directory)
            if current.is_symlink() or any((current / name).is_symlink() for name in names):
                raise ValueError
            for filename in filenames:
                path = current / filename
                mode = path.lstat().st_mode
                if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
                    raise ValueError
                files.add(path.relative_to(root).as_posix())
    except (OSError, ValueError) as error:
        raise ValueError("unsafe source root") from error
    return files


def _read_root_member(
    root: Path,
    member_key: str,
    files: set[str],
    *,
    maximum_bytes: int,
    expected_bytes: int | None = None,
) -> bytes:
    relative = PurePosixPath(member_key)
    if (
        type(member_key) is not str
        or not member_key
        or "\\" in member_key
        or relative.is_absolute()
        or ".." in relative.parts
        or relative.as_posix() != member_key
        or member_key not in files
        or type(maximum_bytes) is not int
        or maximum_bytes <= 0
        or expected_bytes is not None
        and (type(expected_bytes) is not int or expected_bytes < 0 or expected_bytes > maximum_bytes)
    ):
        raise ValueError("unsafe source member")
    path = root.joinpath(*relative.parts)
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_size > maximum_bytes
            or expected_bytes is not None
            and metadata.st_size != expected_bytes
        ):
            raise ValueError("unsafe source member")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            raw = stream.read(maximum_bytes + 1)
        if len(raw) > maximum_bytes or expected_bytes is not None and len(raw) != expected_bytes:
            raise ValueError("unsafe source member")
        return raw
    finally:
        os.close(descriptor)


def _load_source_root(
    root: Path,
    identity: _FrozenSourceIdentity,
) -> _LoadedSourceRoot:
    try:
        files = _path_files(root)
        if len(files) != identity.regular_file_count:
            raise ValueError
        snapshot_raw = _read_root_member(
            root,
            "source-snapshot.json",
            files,
            maximum_bytes=16 << 20,
        )
        receipt_raw = _read_root_member(
            root,
            "acquisition-receipt.json",
            files,
            maximum_bytes=16 << 20,
        )
        if (
            _bytes_hash(snapshot_raw) != identity.snapshot_file_sha256
            or _bytes_hash(receipt_raw) != identity.receipt_file_sha256
        ):
            raise ValueError
        snapshot_metadata = _dict(
            _strict_json(snapshot_raw),
            keys={
                "type", "schema_version", "snapshot_id", "content_tree_hash", "members",
                "provenance", "provenance_hash", "decision_grade_eligible",
                "deployment_authorized",
            },
        )
        receipt = _dict(_strict_json(receipt_raw))
        if (
            snapshot_metadata["type"] != "source_snapshot"
            or snapshot_metadata["schema_version"] != 1
            or snapshot_metadata["snapshot_id"] != identity.snapshot_id
            or snapshot_metadata["content_tree_hash"] != identity.content_tree_hash
            or snapshot_metadata["provenance_hash"] != identity.provenance_hash
            or snapshot_metadata["decision_grade_eligible"] is not False
            or snapshot_metadata["deployment_authorized"] is not False
        ):
            raise ValueError
        provenance_dict = _dict(
            snapshot_metadata["provenance"],
            keys={"vendor_key", "source_key", "license_ref", "retention_policy_ref"},
        )
        provenance = SourceSnapshotProvenance(**provenance_dict)  # type: ignore[arg-type]
        raw_members: list[RawSourceMember] = []
        member_bytes: dict[str, bytes] = {}
        member_keys: set[str] = set()
        for value in _list(snapshot_metadata["members"]):
            member = _dict(
                value,
                keys={
                    "member_key", "content_hash", "byte_count", "mode",
                    "acquired_at_epoch_nanoseconds", "declared_sha256",
                },
            )
            member_key = _text(member["member_key"])
            if member_key in member_keys or member_key not in files:
                raise ValueError
            byte_count = _integer(member["byte_count"])
            raw = _read_root_member(
                root,
                member_key,
                files,
                maximum_bytes=64 << 20,
                expected_bytes=byte_count,
            )
            if _bytes_hash(raw) != _sha(member["content_hash"]):
                raise ValueError
            member_keys.add(member_key)
            member_bytes[member_key] = raw
            raw_members.append(
                RawSourceMember(
                    member_key,
                    raw,
                    _text(member["mode"]),
                    _integer(member["acquired_at_epoch_nanoseconds"]),
                    None if member["declared_sha256"] is None else _sha(member["declared_sha256"]),
                )
            )
        if files != member_keys | {"source-snapshot.json", "acquisition-receipt.json"}:
            raise ValueError
        rebuilt = freeze_source_snapshot(members=tuple(raw_members), provenance=provenance)
        if (
            rebuilt.snapshot is None
            or verify_source_snapshot(rebuilt.snapshot).snapshot is None
            or rebuilt.snapshot.to_canonical_dict() != snapshot_metadata
        ):
            raise ValueError
        return _LoadedSourceRoot(root, rebuilt.snapshot, snapshot_metadata, receipt, member_bytes)
    except QualityBbandS2bProvisionalExactExtractionError:
        raise
    except (OSError, TypeError, ValueError) as error:
        _fail(QualityBbandS2bProvisionalExactExtractionFailure.SOURCE_MEMBER_CONFLICT)


def _provider_rows(raw: bytes, expected_fields: tuple[str, ...]) -> list[list[object]]:
    envelope = _dict(
        _strict_json(raw),
        keys={"request_id", "code", "data", "msg", "detail"},
    )
    data = _dict(
        envelope["data"],
        keys={"fields", "items", "has_more", "count"},
    )
    fields = _list(data["fields"])
    if tuple(fields) != expected_fields:
        raise ValueError("provider field schema mismatch")
    if type(data["has_more"]) is not bool or type(data["count"]) is not int:
        raise ValueError("provider envelope type mismatch")
    rows: list[list[object]] = []
    for value in _list(data["items"]):
        row = _list(value)
        if len(row) != len(expected_fields):
            raise ValueError("provider row width mismatch")
        rows.append(row)
    return rows


def _derive_provisional_expected_set(
    s0: _LoadedSourceRoot,
    annual_roster: _LoadedSourceRoot,
) -> tuple[dict[str, object], set[tuple[str, str, str, str]], set[tuple[str, str, str]]]:
    try:
        current_rows: dict[str, dict[str, object]] = {}
        for member_key in sorted(s0.member_bytes):
            rows = _provider_rows(s0.member_bytes[member_key], _FIELDS["s0"])
            for row in rows:
                record = dict(zip(_FIELDS["s0"], row, strict=True))
                code = _text(record["ts_code"])
                prior = current_rows.get(code)
                if prior is not None:
                    _fail(QualityBbandS2bProvisionalExactExtractionFailure.CATALOG_IDENTITY_MISMATCH)
                current_rows[code] = record

        screens: list[dict[str, object]] = []
        pair_screens: dict[tuple[str, str, str], list[str]] = defaultdict(list)
        roster_members = sorted(
            key for key in annual_roster.member_bytes if "/bak_basic/" in key
        )
        for member_key in roster_members:
            screen_date = Path(member_key).name.split("-", 1)[0]
            if screen_date == "20160503":
                continue
            screen = date.fromisoformat(
                f"{screen_date[:4]}-{screen_date[4:6]}-{screen_date[6:]}"
            )
            cutoff = screen.replace(year=screen.year - 5)
            instruments: list[dict[str, str]] = []
            seen: set[str] = set()
            for row in _provider_rows(
                annual_roster.member_bytes[member_key], _FIELDS["annual_roster"]
            ):
                record = dict(zip(_FIELDS["annual_roster"], row, strict=True))
                provider_code = _text(record["ts_code"])
                if provider_code in seen:
                    _fail(QualityBbandS2bProvisionalExactExtractionFailure.CATALOG_IDENTITY_MISMATCH)
                seen.add(provider_code)
                current = current_rows.get(provider_code)
                if current is None or current["market"] != "主板" or record["list_date"] == "0":
                    continue
                list_date_text = _text(record["list_date"])
                listed = date.fromisoformat(
                    f"{list_date_text[:4]}-{list_date_text[4:6]}-{list_date_text[6:]}"
                )
                if listed > cutoff or record["industry"] in _EXCLUDED_INDUSTRIES:
                    continue
                instruments.append(_canonical_instrument(provider_code))
            instruments.sort(key=_instrument_sort_key)
            screens.append({"screen_date": screen_date, "instrument_ids": instruments})
            for instrument in instruments:
                for year in range(screen.year - 5, screen.year):
                    pair_screens[
                        (instrument["venue"], instrument["stable_key"], f"{year}1231")
                    ].append(screen_date)

        period_requirements = [
            {
                "screen_date": screen["screen_date"],
                "periods": [
                    f"{year}1231"
                    for year in range(int(str(screen["screen_date"])[:4]) - 5, int(str(screen["screen_date"])[:4]))
                ],
            }
            for screen in screens
        ]
        instrument_union = [
            {"type": "instrument_id", "venue": venue, "stable_key": stable_key}
            for venue, stable_key in sorted(
                {
                    (instrument["venue"], instrument["stable_key"])
                    for screen in screens
                    for instrument in screen["instrument_ids"]  # type: ignore[union-attr]
                }
            )
        ]
        pairs = [
            {
                "instrument_id": {
                    "type": "instrument_id", "venue": venue, "stable_key": stable_key
                },
                "period": period,
                "required_by_screen_dates": required_by,
            }
            for (venue, stable_key, period), required_by in sorted(pair_screens.items())
        ]
        keys = [
            [api_name, pair["instrument_id"], pair["period"]]
            for api_name in _API_NAMES
            for pair in pairs
        ]
        expected_simple = {
            (api_name, instrument["venue"], instrument["stable_key"], period)
            for api_name, instrument, period in keys
        }
        expected_provider = {
            (
                api_name,
                stable_key + (".SZ" if venue == "xshe" else ".SH"),
                period,
            )
            for api_name, venue, stable_key, period in expected_simple
        }
        body: dict[str, object] = {
            "type": "quality_bband_s2b_provisional_expected_set",
            "schema_version": 1,
            "authority_level": "SOURCE_BOUNDED_PROVISIONAL",
            "formal_s1_qualified": False,
            "s0_source_snapshot_id": _SOURCE_IDENTITIES["s0"].snapshot_id,
            "annual_roster_source_snapshot_id": _SOURCE_IDENTITIES["annual_roster"].snapshot_id,
            "derivation": {
                "screen_dates": [screen["screen_date"] for screen in screens],
                "join_key": "exact provider ts_code",
                "current_s0_market_required": "主板",
                "roster_listing_age_calendar_years": 5,
                "roster_unknown_list_date_policy": "EXCLUDE_FROM_PROVISIONAL_EXPECTED_SET",
                "excluded_roster_industries": list(_EXCLUDED_INDUSTRIES),
                "null_or_other_roster_industry_policy": "RETAIN",
                "canonical_provider_code_mapping": {
                    "([0-9]{6}).SZ": "xshe:<code>",
                    "([0-9]{6}).SH": "xshg:<code>",
                },
                "period_rule": "five preceding December 31 annual periods per screen year",
                "api_order": list(_API_NAMES),
            },
            "screens": screens,
            "period_requirements": period_requirements,
            "expected_pairs": pairs,
            "screen_membership_hash": _canonical_hash(screens),
            "period_requirements_hash": _canonical_hash(period_requirements),
            "instrument_union_hash": _canonical_hash(instrument_union),
            "expected_pairs_hash": _canonical_hash(pairs),
            "expected_member_keys_hash": _canonical_hash(keys),
            "screen_count": len(screens),
            "instrument_union_count": len(instrument_union),
            "expected_pair_count": len(pairs),
            "expected_member_count": len(keys),
        }
        return {**body, "expected_set_id": _canonical_hash(body)}, expected_simple, expected_provider
    except QualityBbandS2bProvisionalExactExtractionError:
        raise
    except (TypeError, ValueError) as error:
        raise QualityBbandS2bProvisionalExactExtractionError(
            QualityBbandS2bProvisionalExactExtractionFailure.INPUT_TYPE_MISMATCH
        ) from error


def _require_frozen_expected_set(expected: dict[str, object]) -> None:
    if (
        tuple(len(screen["instrument_ids"]) for screen in expected["screens"]) != _EXPECTED_SCREEN_COUNTS  # type: ignore[index]
        or expected["screen_count"] != 9
        or expected["instrument_union_count"] != 2845
        or expected["expected_pair_count"] != 32179
        or expected["expected_member_count"] != 96537
        or any(expected[name] != value for name, value in _EXPECTED_SET_HASHES.items())
        or expected["expected_set_id"] != _EXPECTED_IDS["expected_set"]
    ):
        _fail(
            QualityBbandS2bProvisionalExactExtractionFailure.BUNDLE_EXACT_COVER_MISMATCH,
            "STAGE_INPUT_SCOPE_MISMATCH",
        )


def _extract_terminal_provider_rows(
    s2a: _LoadedSourceRoot,
    expected_provider: set[tuple[str, str, str]],
) -> tuple[bytes, set[tuple[str, str, str, str]], dict[str, object]]:
    try:
        receipt = s2a.receipt
        root_trees = _list(receipt["root_trees"])
        snapshot_members = {
            member.member_key: member for member in s2a.snapshot.members
        }
        all_ids: list[str] = []
        selected_ids: list[str] = []
        extra_ids: list[str] = []
        selected_records: list[dict[str, object]] = []
        extra_codes: set[str] = set()
        extra_keys: set[tuple[str, str, str]] = set()
        leaf_summaries: list[dict[str, object]] = []
        provider_keys: set[tuple[str, str, str, str]] = set()
        rows_per_key: Counter[tuple[str, str, str, str]] = Counter()
        per_api: dict[str, dict[str, int]] = {
            api_name: {
                "terminal_rows": 0, "selected_rows": 0, "extra_rows": 0,
                "selected_keys": 0,
            }
            for api_name in _API_NAMES
        }
        selected_keys_per_api: dict[str, set[tuple[str, str, str, str]]] = {
            api_name: set() for api_name in _API_NAMES
        }
        terminal_keys: list[str] = []
        for tree_value in root_trees:
            tree = _dict(tree_value)
            api_name = _text(tree["api_name"])
            if api_name not in _API_NAMES:
                raise ValueError
            period = _text(tree["period"])
            for member_value in _list(tree["terminal_leaf_member_keys"]):
                member_key = _text(member_value)
                terminal_keys.append(member_key)
                member = snapshot_members.get(member_key)
                if member is None:
                    raise ValueError
                rows = _provider_rows(s2a.member_bytes[member_key], _FIELDS[api_name])
                fields = list(_FIELDS[api_name])
                field_set_hash = _canonical_hash(fields)
                selected_count = extra_count = 0
                for row_index, row in enumerate(rows):
                    provider_code = _text(row[0])
                    row_period = _text(row[3])
                    identity = {
                        "type": "quality_bband_s2b_source_row_identity",
                        "schema_version": 1,
                        "s2a_source_snapshot_id": _SOURCE_IDENTITIES["s2a"].snapshot_id,
                        "source_member_key": member_key,
                        "source_member_content_hash": member.content_hash,
                        "source_row_index": row_index,
                        "api_name": api_name,
                        "field_set_hash": field_set_hash,
                        "row": row,
                    }
                    row_id = _canonical_hash(identity)
                    all_ids.append(row_id)
                    per_api[api_name]["terminal_rows"] += 1
                    if (api_name, provider_code, row_period) in expected_provider:
                        instrument = _canonical_instrument(provider_code)
                        key = (
                            api_name, instrument["venue"], instrument["stable_key"], row_period
                        )
                        provider_keys.add(key)
                        selected_keys_per_api[api_name].add(key)
                        rows_per_key[key] += 1
                        selected_ids.append(row_id)
                        selected_count += 1
                        per_api[api_name]["selected_rows"] += 1
                        selected_records.append(
                            {
                                "type": "quality_bband_s2b_provider_row",
                                "schema_version": 1,
                                "source_row_id": row_id,
                                "api_name": api_name,
                                "instrument_id": instrument,
                                "provider_code": provider_code,
                                "period": row_period,
                                "source_member_key": member_key,
                                "source_row_index": row_index,
                                "row": row,
                            }
                        )
                    else:
                        extra_ids.append(row_id)
                        extra_count += 1
                        per_api[api_name]["extra_rows"] += 1
                        extra_codes.add(provider_code)
                        extra_keys.add((api_name, provider_code, row_period))
                leaf_summaries.append(
                    {
                        "api_name": api_name,
                        "period": period,
                        "member_key": member_key,
                        "member_content_hash": member.content_hash,
                        "field_set_hash": field_set_hash,
                        "terminal_row_count": len(rows),
                        "selected_row_count": selected_count,
                        "extra_row_count": extra_count,
                    }
                )
        if len(terminal_keys) != len(set(terminal_keys)):
            raise ValueError
        for api_name in _API_NAMES:
            per_api[api_name]["selected_keys"] = len(selected_keys_per_api[api_name])
        provider_bytes = b"".join(_json_bytes(record) for record in selected_records)
        extra_codes_sorted = sorted(extra_codes)
        extra_keys_sorted = [
            list(value)
            for value in sorted(
                extra_keys,
                key=lambda value: (_API_NAMES.index(value[0]), value[1], value[2]),
            )
        ]
        extra_sh_sz = sorted(
            code for code in extra_codes if re.fullmatch(r"\d{6}\.(SZ|SH)", code)
        )
        extra_bj = sorted(code for code in extra_codes if re.fullmatch(r"\d{6}\.BJ", code))
        extra_noncanonical = sorted(extra_codes - set(extra_sh_sz) - set(extra_bj))
        provider_requests = _list(receipt["provider_requests"])
        parent_pages = [
            _dict(value)
            for value in provider_requests
            if _dict(value).get("terminal") is False
        ]
        details: dict[str, object] = {
            "selected_ids": selected_ids,
            "source_scan": {
                "field_sets": _dict(receipt["request"])["field_sets"],
                "terminal_leaf_members": leaf_summaries,
                "terminal_source_row_ids_hash": _canonical_hash(all_ids),
                "selected_source_row_ids_hash": _canonical_hash(selected_ids),
                "extra_source_row_ids_hash": _canonical_hash(extra_ids),
                "extra_provider_codes_hash": _canonical_hash(extra_codes_sorted),
                "extra_source_keys_hash": _canonical_hash(extra_keys_sorted),
                "extra_sh_sz_provider_codes_hash": _canonical_hash(extra_sh_sz),
                "extra_bj_provider_codes_hash": _canonical_hash(extra_bj),
                "extra_noncanonical_provider_codes": extra_noncanonical,
            },
            "accounting": {
                "terminal_leaf_page_count": len(leaf_summaries),
                "terminal_leaf_row_count": len(all_ids),
                "nonterminal_parent_page_count": len(parent_pages),
                "nonterminal_parent_row_count": sum(
                    _integer(value["returned_row_count"]) for value in parent_pages
                ),
                "provider_retained_row_count": len(selected_records),
                "provider_revision_surplus_row_count": sum(
                    count - 1 for count in rows_per_key.values()
                ),
                "provider_keys_with_multiple_rows": sum(
                    count > 1 for count in rows_per_key.values()
                ),
                "maximum_provider_rows_per_key": max(rows_per_key.values()),
                "extra_source_row_count": len(extra_ids),
                "extra_source_key_count": len(extra_keys),
                "extra_provider_code_count": len(extra_codes),
                "extra_sh_sz_provider_code_count": len(extra_sh_sz),
                "extra_bj_provider_code_count": len(extra_bj),
                "extra_noncanonical_provider_code_count": len(extra_noncanonical),
                "per_api": per_api,
            },
        }
        return provider_bytes, provider_keys, details
    except QualityBbandS2bProvisionalExactExtractionError:
        raise
    except (KeyError, TypeError, ValueError) as error:
        raise QualityBbandS2bProvisionalExactExtractionError(
            QualityBbandS2bProvisionalExactExtractionFailure.INPUT_TYPE_MISMATCH
        ) from error


def _build_pan_hai_o(source: _LoadedSourceRoot) -> tuple[dict[str, object], set[tuple[str, str, str, str]]]:
    try:
        field_reviews = tuple(
            pan_hai.PanHai2014BalanceFieldReviewV1(
                type="pan_hai_2014_balance_field_review",
                schema_version=1,
                field_key=field_key,
                source_label=source_label,
                pdf_page=pdf_page,
                applicability=pan_hai.BalanceFieldApplicability(applicability),
                value_decimal_text=value,
            )
            for field_key, source_label, pdf_page, applicability, value in pan_hai._FIELD_SPECS
        )
        evidence = pan_hai.PanHai2014ReviewedBalanceEvidenceV1(
            type="pan_hai_2014_reviewed_balance_evidence",
            schema_version=1,
            reviewer_key="quality-bband-pan-hai-2014-balance-review-v1",
            reviewed_at_epoch_nanoseconds=max(
                member.acquired_at_epoch_nanoseconds for member in source.snapshot.members
            ) + 1,
            pdf_member_key=pan_hai._PDF_MEMBER,
            metadata_member_key=pan_hai._METADATA_MEMBER,
            statement_pages=(77, 78, 79),
            audit_page=76,
            statement_title="合并资产负债表",
            issuer_name="泛海控股股份有限公司",
            provider_code="000046.SZ",
            fiscal_period_end_date=date(2014, 12, 31),
            publication_date=date(2015, 4, 4),
            currency="CNY",
            unit_text="人民币元",
            unit_multiplier=Decimal("1"),
            consolidation="CONSOLIDATED",
            company_layout="MIXED_REAL_ESTATE_SECURITIES_CONSOLIDATION",
            audit_opinion="STANDARD_UNQUALIFIED",
            audit_report_date=date(2015, 4, 3),
            audit_report_number="信会师报字[2015]第310292号",
            field_reviews=field_reviews,
            limitations=pan_hai._LIMITATIONS,
        )
        instant = pan_hai._CONSERVATIVE_AVAILABLE
        availability_body = {
            "type": "pan_hai_2014_balance_availability",
            "schema_version": 1,
            "pdf_member_key": pan_hai._PDF_MEMBER,
            "source_publication_date": "2015-04-04",
            "source_visibility_at": instant.to_canonical_dict(),
            "publication_boundary_at": instant.to_canonical_dict(),
            "available_at": instant.to_canonical_dict(),
            "calendar_authority_id": pan_hai._CALENDAR_AUTHORITY_ID,
            "source_availability_id": pan_hai._SOURCE_AVAILABILITY_ID,
        }
        availability = pan_hai.PanHai2014BalanceAvailabilityV1(
            type="pan_hai_2014_balance_availability",
            schema_version=1,
            availability_id=canonical_sha256(availability_body),
            pdf_member_key=pan_hai._PDF_MEMBER,
            source_publication_date=date(2015, 4, 4),
            source_visibility_at=instant,
            publication_boundary_at=instant,
            available_at=instant,
            calendar_authority_id=pan_hai._CALENDAR_AUTHORITY_ID,
            source_availability_id=pan_hai._SOURCE_AVAILABILITY_ID,
        )
        outcome = pan_hai.build_pan_hai_2014_official_balance_backfill_v1(
            pan_hai.PanHai2014OfficialBalanceBackfillRequestV1(
                type="pan_hai_2014_official_balance_backfill_request",
                schema_version=1,
                source_snapshot=source.snapshot,
                reviewed_evidence=evidence,
                availability=availability,
            )
        )
        if outcome.failure is not None:
            _fail(QualityBbandS2bProvisionalExactExtractionFailure(outcome.failure.value))
        if outcome.backfill is None:
            raise ValueError
        backfill = outcome.backfill.to_canonical_dict()
        if (
            backfill["backfill_id"] != _EXPECTED_IDS["pan_hai_backfill"]
            or backfill["financial_payload_complete"] is not False
            or backfill["financial_scope_qualified"] is not False
            or backfill["scope_reason"] != "STATEMENT_SCOPE_UNSUPPORTED"
        ):
            _fail(QualityBbandS2bProvisionalExactExtractionFailure.PUBLICATION_INTEGRITY_FAILURE)
        return backfill, {("balancesheet_vip", "xshe", "000046", "20141231")}
    except QualityBbandS2bProvisionalExactExtractionError:
        raise
    except (AttributeError, TypeError, ValueError) as error:
        raise QualityBbandS2bProvisionalExactExtractionError(
            QualityBbandS2bProvisionalExactExtractionFailure.PUBLICATION_INTEGRITY_FAILURE
        ) from error


def _utc(value: object) -> UtcInstant:
    data = _dict(value, keys={"type", "epoch_nanoseconds"})
    if data["type"] != "utc_instant":
        raise ValueError
    return UtcInstant(_integer(data["epoch_nanoseconds"]))


def _instrument_object(value: object) -> InstrumentId:
    data = _dict(value, keys={"type", "venue", "stable_key"})
    if data["type"] != "instrument_id":
        raise ValueError
    return InstrumentId(VenueId(_text(data["venue"])), _text(data["stable_key"]))


def _document(value: object) -> nonfiling.ReviewedNonFilingDocumentV1:
    data = _dict(value)
    return nonfiling.ReviewedNonFilingDocumentV1(
        type=_text(data["type"]),  # type: ignore[arg-type]
        schema_version=_integer(data["schema_version"]),  # type: ignore[arg-type]
        role=nonfiling.NonFilingDocumentRole(_text(data["role"])),
        evidence_kind=nonfiling.NonFilingEvidenceKind(_text(data["evidence_kind"])),
        authority=nonfiling.NonFilingAuthority(_text(data["authority"])),
        member_key=_text(data["member_key"]),
        source_url=_text(data["source_url"]),
        published_date=date.fromisoformat(_text(data["published_date"])),
        publication_precision=_text(data["publication_precision"]),  # type: ignore[arg-type]
        published_at_epoch_nanoseconds=(
            None if data["published_at_epoch_nanoseconds"] is None
            else _integer(data["published_at_epoch_nanoseconds"])
        ),
        content_hash=_sha(data["content_hash"]),
        byte_count=_integer(data["byte_count"], minimum=1),
        reviewed_pages=tuple(_integer(page, minimum=1) for page in _list(data["reviewed_pages"])),
        reviewed_excerpt=_text(data["reviewed_excerpt"]),
        issuer_assertion=_text(data["issuer_assertion"]),
        period_assertion=_text(data["period_assertion"]),
        supersedes_member_key=(
            None if data["supersedes_member_key"] is None else _text(data["supersedes_member_key"])
        ),
        reviewer_key=_text(data["reviewer_key"]),  # type: ignore[arg-type]
        reviewed_at_epoch_nanoseconds=_integer(data["reviewed_at_epoch_nanoseconds"]),
    )


def _nonfiling_availability(value: object) -> nonfiling.OfficialNonFilingAvailabilityV1:
    data = _dict(value)
    return nonfiling.OfficialNonFilingAvailabilityV1(
        type=_text(data["type"]),  # type: ignore[arg-type]
        schema_version=_integer(data["schema_version"]),  # type: ignore[arg-type]
        availability_id=_sha(data["availability_id"]),
        document_member_key=_text(data["document_member_key"]),
        source_visibility_at=_utc(data["source_visibility_at"]),
        deadline_boundary_at=_utc(data["deadline_boundary_at"]),
        available_at=_utc(data["available_at"]),
        calendar_authority_id=_sha(data["calendar_authority_id"]),
        source_availability_id=_sha(data["source_availability_id"]),
    )


def _validate_nonfiling_source_files(root: Path) -> None:
    try:
        files = _path_files(root)
        receipt_raw = _read_root_member(
            root,
            "declaration-receipt.json",
            files,
            maximum_bytes=8 << 20,
        )
        if _bytes_hash(receipt_raw) != _NONFILING_RECEIPT_SHA256:
            raise ValueError
        receipt = _dict(_strict_json(receipt_raw))
        rows = _list(receipt["declarations"])
        if (
            receipt["publication_id"] != _EXPECTED_IDS["nonfiling_publication"]
            or receipt["declaration_count"] != 7
            or receipt["covered_member_count"] != 21
            or tuple(_dict(row)["declaration_id"] for row in rows)
            != _NONFILING_DECLARATION_IDS
        ):
            raise ValueError
        expected_files = {"declaration-receipt.json"}
        for row_value in rows:
            row = _dict(row_value)
            declaration_path = _text(row["declaration_path"])
            snapshot_path = _text(row["source_snapshot_path"])
            declaration_raw = _read_root_member(
                root,
                declaration_path,
                files,
                maximum_bytes=8 << 20,
            )
            snapshot_raw = _read_root_member(
                root,
                snapshot_path,
                files,
                maximum_bytes=8 << 20,
            )
            declaration = _dict(_strict_json(declaration_raw))
            snapshot_metadata = _dict(_strict_json(snapshot_raw))
            if (
                declaration_raw != _canonical_json(declaration).encode("utf-8")
                or snapshot_raw != _canonical_json(snapshot_metadata).encode("utf-8")
            ):
                raise ValueError
            raw_members: list[RawSourceMember] = []
            member_paths: set[str] = set()
            for member_value in _list(snapshot_metadata["members"]):
                member = _dict(member_value)
                member_key = _text(member["member_key"])
                byte_count = _integer(member["byte_count"])
                raw = _read_root_member(
                    root,
                    member_key,
                    files,
                    maximum_bytes=16 << 20,
                    expected_bytes=byte_count,
                )
                if _bytes_hash(raw) != _sha(member["content_hash"]):
                    raise ValueError
                member_paths.add(member_key)
                raw_members.append(
                    RawSourceMember(
                        member_key,
                        raw,
                        _text(member["mode"]),
                        _integer(member["acquired_at_epoch_nanoseconds"]),
                        None
                        if member["declared_sha256"] is None
                        else _sha(member["declared_sha256"]),
                    )
                )
            provenance = SourceSnapshotProvenance(
                **_dict(snapshot_metadata["provenance"])
            )  # type: ignore[arg-type]
            rebuilt = freeze_source_snapshot(
                members=tuple(raw_members),
                provenance=provenance,
            )
            if (
                rebuilt.snapshot is None
                or verify_source_snapshot(rebuilt.snapshot).snapshot is None
                or rebuilt.snapshot.to_canonical_dict() != snapshot_metadata
                or snapshot_metadata["snapshot_id"] != row["source_snapshot_id"]
                or snapshot_metadata["content_tree_hash"]
                != row["source_content_tree_hash"]
                or snapshot_metadata["provenance_hash"]
                != row["source_provenance_hash"]
            ):
                raise ValueError
            expected_files.update(
                {declaration_path, snapshot_path, *member_paths}
            )
        if files != expected_files or len(files) != 29:
            raise ValueError
    except (OSError, KeyError, TypeError, ValueError) as error:
        raise QualityBbandS2bProvisionalExactExtractionError(
            QualityBbandS2bProvisionalExactExtractionFailure.SOURCE_MEMBER_CONFLICT
        ) from error


def _load_nonfiling_n(
    root: Path,
) -> tuple[dict[str, object], list[dict[str, object]], set[tuple[str, str, str, str]]]:
    try:
        files = _path_files(root)
        receipt_raw = _read_root_member(
            root,
            "declaration-receipt.json",
            files,
            maximum_bytes=8 << 20,
        )
        if _bytes_hash(receipt_raw) != _NONFILING_RECEIPT_SHA256:
            raise ValueError
        receipt = _dict(_strict_json(receipt_raw))
        rows = _list(receipt["declarations"])
        if (
            receipt["publication_id"] != _EXPECTED_IDS["nonfiling_publication"]
            or receipt["declaration_count"] != 7
            or receipt["covered_member_count"] != 21
            or tuple(_dict(row)["declaration_id"] for row in rows) != _NONFILING_DECLARATION_IDS
        ):
            raise ValueError
        expected_files = {"declaration-receipt.json"}
        declaration_refs: list[dict[str, object]] = []
        n_keys: list[list[object]] = []
        n_set: set[tuple[str, str, str, str]] = set()
        for row_value in rows:
            row = _dict(row_value)
            declaration_path = _text(row["declaration_path"])
            snapshot_path = _text(row["source_snapshot_path"])
            declaration_raw = _read_root_member(
                root,
                declaration_path,
                files,
                maximum_bytes=8 << 20,
            )
            snapshot_raw = _read_root_member(
                root,
                snapshot_path,
                files,
                maximum_bytes=8 << 20,
            )
            declaration = _dict(_strict_json(declaration_raw))
            snapshot_metadata = _dict(_strict_json(snapshot_raw))
            if (
                declaration_raw != _canonical_json(declaration).encode("utf-8")
                or snapshot_raw != _canonical_json(snapshot_metadata).encode("utf-8")
            ):
                raise ValueError
            raw_members: list[RawSourceMember] = []
            member_paths: set[str] = set()
            for member_value in _list(snapshot_metadata["members"]):
                member = _dict(member_value)
                member_key = _text(member["member_key"])
                byte_count = _integer(member["byte_count"])
                raw = _read_root_member(
                    root,
                    member_key,
                    files,
                    maximum_bytes=16 << 20,
                    expected_bytes=byte_count,
                )
                if _bytes_hash(raw) != _sha(member["content_hash"]):
                    raise ValueError
                member_paths.add(member_key)
                raw_members.append(
                    RawSourceMember(
                        member_key,
                        raw,
                        _text(member["mode"]),
                        _integer(member["acquired_at_epoch_nanoseconds"]),
                        None if member["declared_sha256"] is None else _sha(member["declared_sha256"]),
                    )
                )
            provenance = SourceSnapshotProvenance(**_dict(snapshot_metadata["provenance"]))  # type: ignore[arg-type]
            rebuilt = freeze_source_snapshot(members=tuple(raw_members), provenance=provenance)
            if (
                rebuilt.snapshot is None
                or verify_source_snapshot(rebuilt.snapshot).snapshot is None
                or rebuilt.snapshot.to_canonical_dict() != snapshot_metadata
                or snapshot_metadata["snapshot_id"] != row["source_snapshot_id"]
                or snapshot_metadata["content_tree_hash"] != row["source_content_tree_hash"]
                or snapshot_metadata["provenance_hash"] != row["source_provenance_hash"]
            ):
                raise ValueError
            documents = tuple(_document(value) for value in _list(declaration["source_document_refs"]))
            if len(documents) != 2:
                raise ValueError
            outcome = nonfiling.declare_official_annual_report_nonfiling_v1(
                nonfiling.OfficialAnnualReportNonFilingRequestV1(
                    type="official_annual_report_nonfiling_request",
                    schema_version=1,
                    instrument_id=_instrument_object(declaration["instrument_id"]),
                    provider_code=_text(declaration["provider_code"]),
                    fiscal_period_end_date=date.fromisoformat(_text(declaration["fiscal_period_end_date"])),
                    statutory_deadline_date=date.fromisoformat(_text(declaration["statutory_deadline_date"])),
                    source_snapshot=rebuilt.snapshot,
                    source_documents=documents,  # type: ignore[arg-type]
                    initial_availability=_nonfiling_availability(declaration["initial_availability"]),
                    terminal_availability=_nonfiling_availability(declaration["terminal_availability"]),
                    active_interval_end=_utc(declaration["active_interval_end"]),
                    terminal_confirmation_fact_date=date.fromisoformat(
                        _text(declaration["terminal_confirmation_fact_date"])
                    ),
                    limitations=tuple(_text(value) for value in _list(declaration["limitations"])),
                )
            )
            if outcome.failure is not None:
                _fail(QualityBbandS2bProvisionalExactExtractionFailure(outcome.failure.value))
            if (
                outcome.declaration is None
                or _canonical_json(outcome.declaration.to_canonical_dict())
                != _canonical_json(declaration)
            ):
                _fail(QualityBbandS2bProvisionalExactExtractionFailure.PUBLICATION_INTEGRITY_FAILURE)
            instrument = declaration["instrument_id"]
            period = _text(declaration["fiscal_period_end_date"]).replace("-", "")
            covered = [[api_name, instrument, period] for api_name in _API_NAMES]
            n_keys.extend(covered)
            instrument_dict = _dict(instrument)
            n_set.update(
                (api_name, _text(instrument_dict["venue"]), _text(instrument_dict["stable_key"]), period)
                for api_name in _API_NAMES
            )
            declaration_refs.append(
                {
                    "provider_code": row["provider_code"],
                    "fiscal_period_end_date": row["fiscal_period_end_date"],
                    "declaration_id": row["declaration_id"],
                    "declaration_path": declaration_path,
                    "declaration_file_sha256": _bytes_hash(declaration_raw),
                    "source_snapshot_path": snapshot_path,
                    "source_snapshot_file_sha256": _bytes_hash(snapshot_raw),
                    "source_snapshot_id": row["source_snapshot_id"],
                    "source_content_tree_hash": row["source_content_tree_hash"],
                    "source_provenance_hash": row["source_provenance_hash"],
                    "covered_member_keys": covered,
                }
            )
            expected_files.update({declaration_path, snapshot_path, *member_paths})
        if files != expected_files or len(files) != 29:
            raise ValueError
        n_keys.sort(
            key=lambda value: (
                _API_NAMES.index(value[0]),  # type: ignore[arg-type]
                value[1]["venue"],  # type: ignore[index]
                value[1]["stable_key"],  # type: ignore[index]
                value[2],
            )
        )
        return receipt, declaration_refs, n_set
    except QualityBbandS2bProvisionalExactExtractionError:
        raise
    except (OSError, KeyError, TypeError, ValueError) as error:
        raise QualityBbandS2bProvisionalExactExtractionError(
            QualityBbandS2bProvisionalExactExtractionFailure.SOURCE_MEMBER_CONFLICT
        ) from error


def _ensure_output_parent(output: Path) -> None:
    parent = output.parent.absolute()
    missing: list[Path] = []
    current = parent
    try:
        while not os.path.lexists(current):
            missing.append(current)
            if current == current.parent:
                raise ValueError("output parent is invalid")
            current = current.parent
        if current.is_symlink() or not current.is_dir():
            raise ValueError("output parent is invalid")
        for directory in reversed(missing):
            try:
                os.mkdir(directory, 0o700)
            except FileExistsError:
                if directory.is_symlink() or not directory.is_dir():
                    raise ValueError("output parent is invalid") from None
            else:
                os.chmod(directory, 0o700)
        if parent.is_symlink() or not parent.is_dir():
            raise ValueError("output parent is invalid")
    except (OSError, ValueError) as error:
        raise QualityBbandS2bProvisionalExactExtractionError(
            QualityBbandS2bProvisionalExactExtractionFailure.PUBLICATION_INTEGRITY_FAILURE
        ) from error


def _rename_noreplace(source: Path, target: Path) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is None:
        raise OSError("atomic no-replace rename is unavailable")
    renameat2.argtypes = (
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    )
    renameat2.restype = ctypes.c_int
    if renameat2(
        -100,
        os.fsencode(source),
        -100,
        os.fsencode(target),
        1,
    ) != 0:
        error_number = ctypes.get_errno()
        raise OSError(error_number, os.strerror(error_number), os.fspath(target))


def _atomic_publish(output: Path, published: dict[str, bytes]) -> None:
    _ensure_output_parent(output)
    staging = output.parent / f".{output.name}.staging-{os.getpid()}"
    try:
        if output.exists() or output.is_symlink() or staging.exists() or staging.is_symlink():
            raise FileExistsError
        os.mkdir(staging, 0o700)
        os.chmod(staging, 0o700)
        for name, content in published.items():
            path = staging / name
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                with os.fdopen(descriptor, "wb", closefd=False) as stream:
                    stream.write(content)
                    stream.flush()
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            os.chmod(path, 0o600)
            expected_size, expected_hash = _EXPECTED_OUTPUTS[name]
            readback = path.read_bytes()
            if len(readback) != expected_size or _bytes_hash(readback) != expected_hash:
                raise OSError("publication readback mismatch")
        directory_fd = os.open(staging, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        if output.exists() or output.is_symlink():
            raise FileExistsError
        _rename_noreplace(staging, output)
        parent_fd = os.open(output.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    except (FileExistsError, OSError) as error:
        if staging.exists() and staging.is_dir() and not staging.is_symlink():
            shutil.rmtree(staging)
        raise QualityBbandS2bProvisionalExactExtractionError(
            QualityBbandS2bProvisionalExactExtractionFailure.PUBLICATION_INTEGRITY_FAILURE
        ) from error


def _preflight(paths: tuple[Path, ...], output: Path) -> None:
    if any(not isinstance(path, Path) for path in (*paths, output)):
        _fail(QualityBbandS2bProvisionalExactExtractionFailure.INPUT_TYPE_MISMATCH)
    try:
        if output.name in {"", ".", ".."} or output.is_symlink() or output.exists():
            raise ValueError
        _ensure_output_parent(output)
        if output.parent.is_symlink() or not output.parent.is_dir():
            raise ValueError
        resolved_output = output.resolve(strict=False)
        for path in paths:
            if path.is_symlink() or not path.is_dir():
                raise ValueError
            resolved = path.resolve(strict=True)
            if resolved == resolved_output or resolved in resolved_output.parents:
                raise ValueError
    except (OSError, ValueError) as error:
        raise QualityBbandS2bProvisionalExactExtractionError(
            QualityBbandS2bProvisionalExactExtractionFailure.PUBLICATION_INTEGRITY_FAILURE
        ) from error


def _validate_exact_closure(
    expected_set: set[tuple[str, str, str, str]],
    p_set: set[tuple[str, str, str, str]],
    o_set: set[tuple[str, str, str, str]],
    n_set: set[tuple[str, str, str, str]],
) -> tuple[set[tuple[str, str, str, str]], set[tuple[str, str, str, str]]]:
    if p_set & o_set or p_set & n_set or o_set & n_set:
        _fail(
            QualityBbandS2bProvisionalExactExtractionFailure.BUNDLE_EXACT_COVER_MISMATCH
        )
    coverage = p_set | o_set | n_set
    missing = expected_set - coverage
    extras = coverage - expected_set
    if missing:
        _fail(
            QualityBbandS2bProvisionalExactExtractionFailure.BUNDLE_EXACT_COVER_MISMATCH,
            "EXPECTED_MEMBER_MISSING",
        )
    if extras:
        _fail(
            QualityBbandS2bProvisionalExactExtractionFailure.BUNDLE_EXACT_COVER_MISMATCH
        )
    return missing, extras


def extract_quality_bband_s2b_provisional_exact_v1(
    *,
    s0_root: Path,
    annual_roster_root: Path,
    s2a_root: Path,
    official_remediation_root: Path,
    nonfiling_publication_root: Path,
    output_dir: Path,
) -> dict[str, object]:
    roots = (
        s0_root, annual_roster_root, s2a_root, official_remediation_root,
        nonfiling_publication_root,
    )
    _preflight(roots, output_dir)

    s0 = _load_source_root(s0_root, _SOURCE_IDENTITIES["s0"])
    annual = _load_source_root(annual_roster_root, _SOURCE_IDENTITIES["annual_roster"])
    s2a = _load_source_root(s2a_root, _SOURCE_IDENTITIES["s2a"])
    pan_hai_source = _load_source_root(
        official_remediation_root, _SOURCE_IDENTITIES["pan_hai"]
    )
    _validate_nonfiling_source_files(nonfiling_publication_root)
    nonfiling_receipt, nonfiling_refs, n_set = _load_nonfiling_n(
        nonfiling_publication_root
    )
    pan_hai_backfill, o_set = _build_pan_hai_o(pan_hai_source)

    expected, expected_set, expected_provider = _derive_provisional_expected_set(s0, annual)
    _require_frozen_expected_set(expected)
    expected_bytes = _json_bytes(expected)
    provider_bytes, p_set, provider_details = _extract_terminal_provider_rows(
        s2a, expected_provider
    )

    missing, extras = _validate_exact_closure(
        expected_set,
        p_set,
        o_set,
        n_set,
    )

    o_keys = [["balancesheet_vip", _canonical_instrument("000046.SZ"), "20141231"]]

    def n_key_order(value: list[object]) -> tuple[int, str, str, str]:
        instrument = _dict(value[1])
        return (
            _API_NAMES.index(_text(value[0])),
            _text(instrument["venue"]),
            _text(instrument["stable_key"]),
            _text(value[2]),
        )

    n_keys: list[list[object]] = sorted(
        [
            [api_name, {"type": "instrument_id", "venue": venue, "stable_key": stable_key}, period]
            for api_name, venue, stable_key, period in n_set
        ],
        key=n_key_order,
    )
    official_body: dict[str, object] = {
        "type": "quality_bband_s2b_official_coverage",
        "schema_version": 1,
        "pan_hai_backfill": pan_hai_backfill,
        "nonfiling_publication_ref": {
            "publication_id": nonfiling_receipt["publication_id"],
            "receipt_file_sha256": _NONFILING_RECEIPT_SHA256,
            "declaration_count": nonfiling_receipt["declaration_count"],
            "covered_member_count": nonfiling_receipt["covered_member_count"],
        },
        "nonfiling_declarations": nonfiling_refs,
        "o_member_keys": o_keys,
        "n_member_keys": n_keys,
        "o_member_count": len(o_set),
        "n_member_count": len(n_set),
    }
    official = {**official_body, "official_coverage_id": _canonical_hash(official_body)}
    official_bytes = _json_bytes(official)

    accounting = {
        "expected_member_count": len(expected_set),
        "provider_member_count": len(p_set),
        "official_filing_member_count": len(o_set),
        "official_nonfiling_member_count": len(n_set),
        "provider_official_filing_overlap_count": len(p_set & o_set),
        "provider_official_nonfiling_overlap_count": len(p_set & n_set),
        "official_filing_nonfiling_overlap_count": len(o_set & n_set),
        "missing_member_count": len(missing),
        "coverage_extra_member_count": len(extras),
        **_dict(provider_details["accounting"]),
    }
    inputs = {
        "backtest_base_commit": _BASE_COMMIT,
        "s0": {
            "snapshot_id": _SOURCE_IDENTITIES["s0"].snapshot_id,
            "content_tree_hash": _SOURCE_IDENTITIES["s0"].content_tree_hash,
            "provenance_hash": _SOURCE_IDENTITIES["s0"].provenance_hash,
            "snapshot_file_sha256": _SOURCE_IDENTITIES["s0"].snapshot_file_sha256,
            "receipt_file_sha256": _SOURCE_IDENTITIES["s0"].receipt_file_sha256,
        },
        "annual_roster": {
            "snapshot_id": _SOURCE_IDENTITIES["annual_roster"].snapshot_id,
            "content_tree_hash": _SOURCE_IDENTITIES["annual_roster"].content_tree_hash,
            "provenance_hash": _SOURCE_IDENTITIES["annual_roster"].provenance_hash,
            "snapshot_file_sha256": _SOURCE_IDENTITIES["annual_roster"].snapshot_file_sha256,
            "receipt_file_sha256": _SOURCE_IDENTITIES["annual_roster"].receipt_file_sha256,
        },
        "s2a": {
            "snapshot_id": _SOURCE_IDENTITIES["s2a"].snapshot_id,
            "content_tree_hash": _SOURCE_IDENTITIES["s2a"].content_tree_hash,
            "provenance_hash": _SOURCE_IDENTITIES["s2a"].provenance_hash,
            "snapshot_file_sha256": _SOURCE_IDENTITIES["s2a"].snapshot_file_sha256,
            "receipt_file_sha256": _SOURCE_IDENTITIES["s2a"].receipt_file_sha256,
            "provider_requests_hash": _canonical_hash(s2a.receipt["provider_requests"]),
            "root_trees_hash": _canonical_hash(s2a.receipt["root_trees"]),
        },
        "pan_hai_source": {
            "snapshot_id": _SOURCE_IDENTITIES["pan_hai"].snapshot_id,
            "content_tree_hash": _SOURCE_IDENTITIES["pan_hai"].content_tree_hash,
            "provenance_hash": _SOURCE_IDENTITIES["pan_hai"].provenance_hash,
            "snapshot_file_sha256": _SOURCE_IDENTITIES["pan_hai"].snapshot_file_sha256,
            "receipt_file_sha256": _SOURCE_IDENTITIES["pan_hai"].receipt_file_sha256,
            "builder_commit": "7b4587237f52bc9a33104f14365615e209de45a0",
        },
        "official_nonfiling_publication": {
            "publication_id": nonfiling_receipt["publication_id"],
            "receipt_file_sha256": _NONFILING_RECEIPT_SHA256,
        },
    }
    selected_ids = _list(provider_details["selected_ids"])
    output_members = {
        "provisional-expected-set.json": {
            "content_type": "application/json",
            "byte_count": len(expected_bytes),
            "sha256": _bytes_hash(expected_bytes),
            "schema_id": expected["expected_set_id"],
        },
        "provider-rows.jsonl": {
            "content_type": "application/x-ndjson",
            "byte_count": len(provider_bytes),
            "sha256": _bytes_hash(provider_bytes),
            "row_count": len(selected_ids),
            "row_ids_hash": _canonical_hash(selected_ids),
        },
        "official-coverage.json": {
            "content_type": "application/json",
            "byte_count": len(official_bytes),
            "sha256": _bytes_hash(official_bytes),
            "schema_id": official["official_coverage_id"],
        },
    }
    manifest_body: dict[str, object] = {
        "type": "quality_bband_s2b_provisional_exact_extraction_manifest",
        "schema_version": 1,
        "inputs": inputs,
        "expected_set_id": expected["expected_set_id"],
        "source_scan": provider_details["source_scan"],
        "official_coverage_id": official["official_coverage_id"],
        "closure_equation": "96537 = 96515 P + 1 O + 21 N",
        "accounting": accounting,
        "output_members": output_members,
        "limitations": [
            "SOURCE_BOUNDED_PROVISIONAL_EXPECTED_SET",
            "FORMAL_S1_FALSE",
            "FINANCIAL_PAYLOAD_AND_SCOPE_NOT_QUALIFIED",
            "NO_STRATEGY_BACKTEST_VALIDATION_OR_DEPLOYMENT_AUTHORITY",
        ],
        "provisional_expected_scope_extracted": True,
        "provisional_exact_cover_complete": True,
        "formal_s1_qualified": False,
        "formal_s2_qualified": False,
        "financial_payload_complete": False,
        "financial_scope_qualified": False,
        "decision_grade_eligible": False,
        "strategy_authorized": False,
        "strategy_target_authorized": False,
        "backtest_authorized": False,
        "validation_authorized": False,
        "deployment_authorized": False,
    }
    manifest = {**manifest_body, "manifest_id": _canonical_hash(manifest_body)}
    manifest_bytes = _json_bytes(manifest)
    published = {
        "provisional-expected-set.json": expected_bytes,
        "provider-rows.jsonl": provider_bytes,
        "official-coverage.json": official_bytes,
        "extraction-manifest.json": manifest_bytes,
    }
    if (
        expected["expected_set_id"] != _EXPECTED_IDS["expected_set"]
        or official["official_coverage_id"] != _EXPECTED_IDS["official_coverage"]
        or manifest["manifest_id"] != _EXPECTED_IDS["manifest"]
        or _canonical_hash(selected_ids) != _EXPECTED_IDS["provider_row_ids"]
        or any(
            len(content) != _EXPECTED_OUTPUTS[name][0]
            or _bytes_hash(content) != _EXPECTED_OUTPUTS[name][1]
            for name, content in published.items()
        )
    ):
        _fail(QualityBbandS2bProvisionalExactExtractionFailure.PUBLICATION_INTEGRITY_FAILURE)
    _atomic_publish(output_dir, published)
    return manifest


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--s0-root", required=True, type=Path)
    parser.add_argument("--annual-roster-root", required=True, type=Path)
    parser.add_argument("--s2a-root", required=True, type=Path)
    parser.add_argument("--official-remediation-root", required=True, type=Path)
    parser.add_argument("--nonfiling-publication-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        manifest = extract_quality_bband_s2b_provisional_exact_v1(
            s0_root=args.s0_root,
            annual_roster_root=args.annual_roster_root,
            s2a_root=args.s2a_root,
            official_remediation_root=args.official_remediation_root,
            nonfiling_publication_root=args.nonfiling_publication_root,
            output_dir=args.output_dir,
        )
    except QualityBbandS2bProvisionalExactExtractionError as error:
        print(str(error))
        return 1
    print(_canonical_json(manifest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
