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

_API_NAMES = ("income_vip", "balancesheet_vip", "cashflow_vip")
_SCREEN_DATES = (
    "20170502", "20180502", "20190506", "20200506", "20210506",
    "20220505", "20230504", "20240506", "20250506",
)
_DECISION_AT = {
    "20170502": 1493688600000000000,
    "20180502": 1525224600000000000,
    "20190506": 1557106200000000000,
    "20200506": 1588728600000000000,
    "20210506": 1620264600000000000,
    "20220505": 1651714200000000000,
    "20230504": 1683163800000000000,
    "20240506": 1714959000000000000,
    "20250506": 1746495000000000000,
}
_FIELDS = {
    "s0": (
        "ts_code", "symbol", "name", "area", "industry", "fullname", "enname",
        "cnspell", "market", "exchange", "curr_type", "list_status", "list_date",
        "delist_date", "is_hs", "act_name", "act_ent_type",
    ),
    "annual_roster": ("trade_date", "ts_code", "name", "industry", "list_date"),
    "trade_cal": ("exchange", "cal_date", "is_open", "pretrade_date"),
}
_PROVIDER_CODE = re.compile(r"([0-9]{6})\.(SZ|SH)\Z")
_BJ_PROVIDER_CODE = re.compile(r"[0-9]{6}\.BJ\Z")
_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_EXCLUDED_INDUSTRIES = {"银行", "保险", "证券", "多元金融"}
_BASE_COMMIT = "0d373b71b263a53b6b00e50b26ae1508dcfc986f"
_OWNER_DECISION_ID = "sha256:629748197e0606baeff184a6eece576a2e7660cf5363d76d10a4e5577af6e1ed"
_PACKET_BODY_HASH = "sha256:aeb8ac2b5aa8a97c5cf04140ff4a12a0c45854ee8ea34c19a8a89792676006bb"
_OUTPUT_NAME = "tushare-s1-structural-manifest.json"
_EXPECTED_OUTPUT_SIZE = 40104662
_EXPECTED_OUTPUT_HASH = "sha256:c8f96831bd68cc1a46a291c59c5c97e10ce0c31eba54e53d9be8929366dfd059"
_EXPECTED_MANIFEST_ID = "sha256:dcd0fecbfca29ce090b53462f3972174d4977116e52472309055b4110046df85"
_LIMITATIONS = sorted((
    "CURRENT_TUSHARE_MARKET_PROJECTED_AS_CONTROLLING_HISTORICAL_BOARD",
    "OFFICIAL_CSRC_INDUSTRY_AUTHORITY_FALSE",
    "OFFICIAL_EXCHANGE_AUTHORITY_FALSE",
    "OWNER_APPROVED_TUSHARE_SCOPE_ONLY",
    "PROVIDER_ROW_ABSENCE_ACCEPTED_ONLY_FOR_PINNED_SCREEN_RESPONSES",
    "SURVIVORSHIP_SAFETY_BEYOND_TUSHARE_SCOPE_FALSE",
))
_FLAGS = {
    "owner_approved_tushare_authority": True,
    "formal_s1_qualified": True,
    "provider_scope_exact": True,
    "official_exchange_authority": False,
    "official_csrc_industry_authority": False,
    "market_truth_completeness_claimed": False,
    "survivorship_bias_safe_beyond_tushare_scope": False,
    "formal_s2_qualified": False,
    "decision_grade_eligible": False,
    "strategy_authorized": False,
    "strategy_target_authorized": False,
    "backtest_authorized": False,
    "validation_authorized": False,
    "deployment_authorized": False,
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
}
_EXPECTED = {
    "canonical_catalog_count": 5545,
    "canonical_catalog_hash": "sha256:84b8074dd213a5badfc74975bd179d8c08844e304197bad06e51546bc14bcbf3",
    "s0_source_extra_count": 344,
    "s0_source_extras_hash": "sha256:dbbd8ecaea3e9a97b289678738bd662fbcafa04952d6873146c377929d14a4eb",
    "all_disposition_count": 49905,
    "all_dispositions_hash": "sha256:05287a1081e217d24d3911e5826dde980e4d941ce277bd462d379fb1e0333666",
    "screen_membership_hash": "sha256:00b6f4487ffd946ca1db05a4fc353f45ba9da235cc954e1248902da3103a8f2b",
    "period_requirements_hash": "sha256:87f0ad15a76bc01561e0347f59a720e26b657829198774bf14893df7ef4fe846",
    "instrument_union_hash": "sha256:25d69f75295afe13549269e96d9fbeb726605ac5c93e78d9cfe46ecf48f30ab0",
    "expected_pairs_hash": "sha256:336efc4e947062036b1c98add7977653c48abdab8f33350516626a521b9b2b3e",
    "expected_member_keys_hash": "sha256:0269e22c9f45b24b827e98a91515ac31ae5486ba0fda668f69112400b088e44b",
    "instrument_union_count": 2845,
    "expected_pair_count": 32179,
    "expected_member_key_count": 96537,
    "roster_extra_codes_hash": "sha256:98394a9496d7438a6335cb195e7df37c34be591c72c67dafbabc5265d38a51a7",
    "roster_extra_counts_hash": "sha256:d317af4d07959c9a0d8927f03103689c5f94684a771e051d4580ef604dee1f65",
}
_EXPECTED_SCREEN = {
    "20170502": (1995, 3550, "sha256:fea08c7e48a65ab5234365170868a19e0efa664e78c3ddcd1120774ce9105378", "sha256:277ce5c25c287d4166a3554bf7490c79e51862ac691ac493c54a77936d9ebb46"),
    "20180502": (2034, 3511, "sha256:855d59f3043bd3d4ac2ae036db909d396d043b2cfe9e6ba69bb4291cd6a577f3", "sha256:dbca60e545b16185960fcbfd3df0a2803137a7f2202314f0f47bba5411d38e0e"),
    "20190506": (2053, 3492, "sha256:55fe4961f25e33b33bbfd72f9ae2e6bfbdb7eebd985daa808a939156c415a6d3", "sha256:0e9ac5081536642836f53772ec5b787598646ec486e56911a1c37c8406b1958f"),
    "20200506": (2143, 3402, "sha256:4df1da2531659ca1d83ddcbb0ed0c464988907f10bbb4f0a14cdb57f148fc225", "sha256:515a898727f5529afe2141c9608385c1c06346a2286745cd9d2f70f8dc6e57b9"),
    "20210506": (2224, 3321, "sha256:b7e5370610ef49cd9531461aad5c76c9f999a81cea85ad91c100b2fccf3796ad", "sha256:b01fd4be16bb3b347d08b3703c9a24893ad725daa0d8e553b4d7db9af61d8ebc"),
    "20220505": (2434, 3111, "sha256:b906f4465cea6499c5651e168546346df0dae0a2c87c91769f3b4a07060b9fd3", "sha256:80b2040da451c5810f2c13cb4cad561b1db2ecf0f47d9be1aa35ae0622bfa256"),
    "20230504": (2612, 2933, "sha256:fececcd7fe29852b9928b284b3f6a3254534d74a5513050b52659ad3f387d17c", "sha256:ec803daa73eae7205ef943cf907840501f054e25d0bb754331fa81702fb206f3"),
    "20240506": (2635, 2910, "sha256:69fc18da3540bfb085ad02bf7c4c7709caa6109eb427f74b15ad51029df08a5b", "sha256:0767557ede35189e731c1695d94cb44d1d4bf32575854e155671d82130f7b034"),
    "20250506": (2667, 2878, "sha256:264bb0d9fb29dc655a5f7ea0c4cab27bb1dfa1fd891b1a2ddc76155118ad7cba", "sha256:5a0686e15872eeae6e569f3254aebb1504aa2ddafba7da0914c51520ab694036"),
}
_EXPECTED_REASON_COUNTS = {
    "NOT_PRESENT_IN_TUSHARE_SCREEN_ROSTER": 11401,
    "NON_CNY_OR_NON_MAIN_BOARD": 11509,
    "LIST_DATE_UNKNOWN": 60,
    "LISTING_AGE_LT_FIVE_YEARS": 5403,
    "FINANCIAL_INDUSTRY": 735,
    "STRUCTURALLY_ELIGIBLE": 20797,
    "UNRESOLVED_STRUCTURAL_AUTHORITY": 0,
}
_EXPECTED_ROSTER_EXTRA_COUNTS = {
    "20170502": 4, "20180502": 3, "20190506": 2, "20200506": 1,
    "20210506": 7, "20220505": 2, "20230504": 1, "20240506": 250,
    "20250506": 266,
}


class QualityBbandTushareS1Failure(str, Enum):
    INPUT_TYPE_OR_PATH = "INPUT_TYPE_OR_PATH"
    CATALOG_IDENTITY_MISMATCH = "CATALOG_IDENTITY_MISMATCH"
    SOURCE_RECONSTRUCTION_FAILURE = "SOURCE_RECONSTRUCTION_FAILURE"
    SCREEN_CALENDAR_REQUEST_MISMATCH = "SCREEN_CALENDAR_REQUEST_MISMATCH"
    DUPLICATE_ROSTER_ROW = "DUPLICATE_ROSTER_ROW"
    UNRESOLVED_STRUCTURAL_AUTHORITY = "UNRESOLVED_STRUCTURAL_AUTHORITY"
    FROZEN_VALUE_MISMATCH = "FROZEN_VALUE_MISMATCH"
    PUBLICATION_INTEGRITY_FAILURE = "PUBLICATION_INTEGRITY_FAILURE"


class QualityBbandTushareS1Error(RuntimeError):
    def __init__(self, code: QualityBbandTushareS1Failure) -> None:
        if type(code) is not QualityBbandTushareS1Failure:
            raise TypeError("code must be a Tushare S1 failure")
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class _LoadedSourceRoot:
    root: Path
    snapshot: SourceSnapshot
    snapshot_metadata: dict[str, object]
    receipt: dict[str, object]
    member_bytes: dict[str, bytes]


def _fail(code: QualityBbandTushareS1Failure) -> NoReturn:
    raise QualityBbandTushareS1Error(code)


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))


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
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid_constant, parse_float=finite_float)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise ValueError("strict JSON parse failure") from error


def _dict(value: object, *, keys: set[str] | None = None) -> dict[str, object]:
    if type(value) is not dict:
        raise TypeError("expected exact JSON object")
    if keys is not None and set(value) != keys:
        raise ValueError("JSON object schema mismatch")
    return value


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
        raise ValueError("expected exact integer")
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
        _fail(QualityBbandTushareS1Failure.CATALOG_IDENTITY_MISMATCH)
    stable_key, suffix = match.groups()
    return {"type": "instrument_id", "venue": "xshe" if suffix == "SZ" else "xshg", "stable_key": stable_key}


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
        type(member_key) is not str or not member_key or "\\" in member_key
        or relative.is_absolute() or ".." in relative.parts or relative.as_posix() != member_key
        or member_key not in files or type(maximum_bytes) is not int or maximum_bytes <= 0
        or expected_bytes is not None
        and (type(expected_bytes) is not int or expected_bytes < 0 or expected_bytes > maximum_bytes)
    ):
        raise ValueError("unsafe source member")
    descriptor = os.open(root.joinpath(*relative.parts), os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode) or metadata.st_size > maximum_bytes
            or expected_bytes is not None and metadata.st_size != expected_bytes
        ):
            raise ValueError("unsafe source member")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            raw = stream.read(maximum_bytes + 1)
        if len(raw) > maximum_bytes or expected_bytes is not None and len(raw) != expected_bytes:
            raise ValueError("unsafe source member")
        return raw
    finally:
        os.close(descriptor)


def _load_source_root(root: Path, identity: _FrozenSourceIdentity) -> _LoadedSourceRoot:
    try:
        files = _path_files(root)
        if len(files) != identity.regular_file_count:
            raise ValueError
        snapshot_raw = _read_root_member(root, "source-snapshot.json", files, maximum_bytes=16 << 20)
        receipt_raw = _read_root_member(root, "acquisition-receipt.json", files, maximum_bytes=16 << 20)
        if _bytes_hash(snapshot_raw) != identity.snapshot_file_sha256 or _bytes_hash(receipt_raw) != identity.receipt_file_sha256:
            raise ValueError
        snapshot_metadata = _dict(
            _strict_json(snapshot_raw),
            keys={"type", "schema_version", "snapshot_id", "content_tree_hash", "members", "provenance", "provenance_hash", "decision_grade_eligible", "deployment_authorized"},
        )
        receipt = _dict(_strict_json(receipt_raw))
        if (
            snapshot_metadata["type"] != "source_snapshot" or snapshot_metadata["schema_version"] != 1
            or snapshot_metadata["snapshot_id"] != identity.snapshot_id
            or snapshot_metadata["content_tree_hash"] != identity.content_tree_hash
            or snapshot_metadata["provenance_hash"] != identity.provenance_hash
            or snapshot_metadata["decision_grade_eligible"] is not False
            or snapshot_metadata["deployment_authorized"] is not False
        ):
            raise ValueError
        provenance = SourceSnapshotProvenance(**_dict(
            snapshot_metadata["provenance"],
            keys={"vendor_key", "source_key", "license_ref", "retention_policy_ref"},
        ))  # type: ignore[arg-type]
        raw_members: list[RawSourceMember] = []
        member_bytes: dict[str, bytes] = {}
        member_keys: set[str] = set()
        for value in _list(snapshot_metadata["members"]):
            member = _dict(value, keys={"member_key", "content_hash", "byte_count", "mode", "acquired_at_epoch_nanoseconds", "declared_sha256"})
            member_key = _text(member["member_key"])
            if member_key in member_keys:
                raise ValueError
            byte_count = _integer(member["byte_count"])
            raw = _read_root_member(root, member_key, files, maximum_bytes=64 << 20, expected_bytes=byte_count)
            if _bytes_hash(raw) != _sha(member["content_hash"]):
                raise ValueError
            member_keys.add(member_key)
            member_bytes[member_key] = raw
            raw_members.append(RawSourceMember(
                member_key, raw, _text(member["mode"]), _integer(member["acquired_at_epoch_nanoseconds"]),
                None if member["declared_sha256"] is None else _sha(member["declared_sha256"]),
            ))
        if files != member_keys | {"source-snapshot.json", "acquisition-receipt.json"}:
            raise ValueError
        rebuilt = freeze_source_snapshot(members=tuple(raw_members), provenance=provenance)
        if (
            rebuilt.snapshot is None or verify_source_snapshot(rebuilt.snapshot).snapshot is None
            or rebuilt.snapshot.to_canonical_dict() != snapshot_metadata
        ):
            raise ValueError
        return _LoadedSourceRoot(root, rebuilt.snapshot, snapshot_metadata, receipt, member_bytes)
    except (OSError, TypeError, ValueError) as error:
        raise QualityBbandTushareS1Error(QualityBbandTushareS1Failure.SOURCE_RECONSTRUCTION_FAILURE) from error


def _provider_rows(raw: bytes, expected_fields: tuple[str, ...]) -> list[list[object]]:
    envelope = _dict(_strict_json(raw), keys={"request_id", "code", "data", "msg", "detail"})
    data = _dict(envelope["data"], keys={"fields", "items", "has_more", "count"})
    if tuple(_list(data["fields"])) != expected_fields or type(data["has_more"]) is not bool or type(data["count"]) is not int:
        raise ValueError("provider envelope mismatch")
    rows = []
    for value in _list(data["items"]):
        row = _list(value)
        if len(row) != len(expected_fields):
            raise ValueError("provider row width mismatch")
        rows.append(row)
    return rows


def _parse_yyyymmdd(value: object) -> date | None:
    if type(value) is not str or re.fullmatch(r"[0-9]{8}", value) is None:
        return None
    try:
        return date(int(value[:4]), int(value[4:6]), int(value[6:]))
    except ValueError:
        return None


def _fifth_anniversary(listed: date) -> date:
    try:
        return listed.replace(year=listed.year + 5)
    except ValueError:
        return listed.replace(year=listed.year + 5, day=28)


def _derive_catalog_and_extras(s0: _LoadedSourceRoot) -> tuple[list[dict[str, object]], list[str], dict[str, dict[str, object]]]:
    catalog_by_identity: dict[tuple[str, str], dict[str, object]] = {}
    current_by_code: dict[str, dict[str, object]] = {}
    extras: list[str] = []
    try:
        for member_key in sorted(s0.member_bytes):
            for row_index, row in enumerate(_provider_rows(s0.member_bytes[member_key], _FIELDS["s0"])):
                record = dict(zip(_FIELDS["s0"], row, strict=True))
                code = _text(record["ts_code"])
                match = _PROVIDER_CODE.fullmatch(code)
                if match is None:
                    if _BJ_PROVIDER_CODE.fullmatch(code) is not None or code == "T600018.SH":
                        extras.append(code)
                        continue
                    _fail(QualityBbandTushareS1Failure.CATALOG_IDENTITY_MISMATCH)
                stable_key, suffix = match.groups()
                expected_exchange = "SZSE" if suffix == "SZ" else "SSE"
                if record["exchange"] != expected_exchange:
                    _fail(QualityBbandTushareS1Failure.CATALOG_IDENTITY_MISMATCH)
                instrument = _canonical_instrument(code)
                identity = _instrument_sort_key(instrument)
                if identity in catalog_by_identity or code in current_by_code:
                    _fail(QualityBbandTushareS1Failure.CATALOG_IDENTITY_MISMATCH)
                member = {
                    "instrument_id": instrument,
                    "provider_code": code,
                    "source_member_key": member_key,
                    "source_row_index": row_index,
                }
                catalog_by_identity[identity] = member
                current_by_code[code] = record
        catalog = [catalog_by_identity[key] for key in sorted(catalog_by_identity)]
        return catalog, sorted(extras), current_by_code
    except QualityBbandTushareS1Error:
        raise
    except (KeyError, TypeError, ValueError) as error:
        raise QualityBbandTushareS1Error(QualityBbandTushareS1Failure.CATALOG_IDENTITY_MISMATCH) from error


def _utc(epoch_nanoseconds: int) -> dict[str, object]:
    return {"type": "utc_instant", "epoch_nanoseconds": epoch_nanoseconds}


def _build_screen_dispositions(
    catalog: list[dict[str, object]],
    current_by_code: dict[str, dict[str, object]],
    annual_roster: _LoadedSourceRoot,
) -> tuple[list[dict[str, object]], list[dict[str, str]], dict[str, int]]:
    member_by_screen = {
        Path(key).name.split("-", 1)[0]: key
        for key in annual_roster.member_bytes
        if "/bak_basic/" in key
    }
    if set(_SCREEN_DATES) - set(member_by_screen) or "20160503" not in member_by_screen:
        _fail(QualityBbandTushareS1Failure.SCREEN_CALENDAR_REQUEST_MISMATCH)
    screens: list[dict[str, object]] = []
    roster_extras: list[dict[str, str]] = []
    roster_extra_counts: dict[str, int] = {}
    catalog_codes = {str(member["provider_code"]) for member in catalog}
    for screen_date in _SCREEN_DATES:
        member_key = member_by_screen[screen_date]
        roster: dict[str, tuple[dict[str, object], int]] = {}
        try:
            for row_index, row in enumerate(_provider_rows(annual_roster.member_bytes[member_key], _FIELDS["annual_roster"])):
                record = dict(zip(_FIELDS["annual_roster"], row, strict=True))
                code = _text(record["ts_code"])
                if record["trade_date"] != screen_date:
                    _fail(QualityBbandTushareS1Failure.SCREEN_CALENDAR_REQUEST_MISMATCH)
                if code in roster:
                    _fail(QualityBbandTushareS1Failure.DUPLICATE_ROSTER_ROW)
                roster[code] = (record, row_index)
        except QualityBbandTushareS1Error:
            raise
        except (KeyError, TypeError, ValueError) as error:
            raise QualityBbandTushareS1Error(QualityBbandTushareS1Failure.SCREEN_CALENDAR_REQUEST_MISMATCH) from error
        extras = sorted(code for code in roster if code not in catalog_codes)
        roster_extra_counts[screen_date] = len(extras)
        roster_extras.extend({"screen_date": screen_date, "provider_code": code} for code in extras)
        decision_at = _utc(_DECISION_AT[screen_date])
        screen_day = _parse_yyyymmdd(screen_date)
        assert screen_day is not None
        dispositions: list[dict[str, object]] = []
        eligible: list[dict[str, str]] = []
        counts: Counter[str] = Counter()
        for member in catalog:
            code = str(member["provider_code"])
            instrument = member["instrument_id"]
            roster_value = roster.get(code)
            disposition = "STRUCTURALLY_OUT_OF_SCOPE"
            reason: str | None
            roster_member_key: str | None = None
            roster_row_index: int | None = None
            if roster_value is None:
                reason = "NOT_PRESENT_IN_TUSHARE_SCREEN_ROSTER"
            else:
                record, roster_row_index = roster_value
                roster_member_key = member_key
                current = current_by_code[code]
                expected_exchange = "SZSE" if code.endswith(".SZ") else "SSE"
                if current["curr_type"] != "CNY" or current["market"] != "主板" or current["exchange"] != expected_exchange:
                    reason = "NON_CNY_OR_NON_MAIN_BOARD"
                else:
                    listed = _parse_yyyymmdd(record["list_date"])
                    if listed is None:
                        reason = "LIST_DATE_UNKNOWN"
                    elif _fifth_anniversary(listed) > screen_day:
                        reason = "LISTING_AGE_LT_FIVE_YEARS"
                    elif record["industry"] in _EXCLUDED_INDUSTRIES:
                        reason = "FINANCIAL_INDUSTRY"
                    elif record["industry"] is None:
                        disposition = "UNRESOLVED_STRUCTURAL_AUTHORITY"
                        reason = None
                    else:
                        disposition = "STRUCTURALLY_ELIGIBLE"
                        reason = None
                        eligible.append(instrument)  # type: ignore[arg-type]
            count_key = disposition if reason is None else reason
            counts[count_key] += 1
            dispositions.append({
                "screen_date": screen_date,
                "decision_at": decision_at,
                "instrument_id": instrument,
                "provider_code": code,
                "disposition": disposition,
                "reason": reason,
                "s0_source_member_key": member["source_member_key"],
                "s0_source_row_index": member["source_row_index"],
                "roster_source_member_key": roster_member_key,
                "roster_source_row_index": roster_row_index,
            })
        eligible_hash = _canonical_hash(eligible)
        dispositions_hash = _canonical_hash(dispositions)
        out_of_scope = sum(value for key, value in counts.items() if key not in {"STRUCTURALLY_ELIGIBLE", "UNRESOLVED_STRUCTURAL_AUTHORITY"})
        unresolved = counts["UNRESOLVED_STRUCTURAL_AUTHORITY"]
        screens.append({
            "screen_date": screen_date,
            "decision_at": decision_at,
            "calendar_authority_id": _SOURCE_IDENTITIES["annual_roster"].snapshot_id,
            "dispositions": dispositions,
            "dispositions_hash": dispositions_hash,
            "eligible_instrument_ids": eligible,
            "eligible_instrument_ids_hash": eligible_hash,
            "eligible_count": len(eligible),
            "out_of_scope_count": out_of_scope,
            "unresolved_count": unresolved,
            "disposition_counts": dict(sorted(counts.items())),
            "closure_complete": len(dispositions) == len(catalog) == len(eligible) + out_of_scope + unresolved,
        })
    return screens, sorted(roster_extras, key=lambda value: (value["screen_date"], value["provider_code"])), roster_extra_counts


def _build_financial_requirements(
    screens: list[dict[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, str]], list[dict[str, object]], list[list[object]]]:
    period_requirements: list[dict[str, object]] = []
    pair_screens: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    union: dict[tuple[str, str], dict[str, str]] = {}
    membership: list[dict[str, object]] = []
    for screen in screens:
        screen_date = str(screen["screen_date"])
        year = int(screen_date[:4])
        periods = [f"{value}1231" for value in range(year - 5, year)]
        period_requirements.append({"screen_date": screen_date, "periods": periods})
        instruments = screen["eligible_instrument_ids"]
        membership.append({"screen_date": screen_date, "instrument_ids": instruments})
        for instrument in instruments:  # type: ignore[union-attr]
            key = _instrument_sort_key(instrument)
            union[key] = instrument
            for period in periods:
                pair_screens[(key[0], key[1], period)].append(screen_date)
    instrument_union = [union[key] for key in sorted(union)]
    pairs = [{
        "instrument_id": {"type": "instrument_id", "venue": venue, "stable_key": stable_key},
        "period": period,
        "required_by_screen_dates": required_by,
    } for (venue, stable_key, period), required_by in sorted(pair_screens.items())]
    keys = [[api_name, pair["instrument_id"], pair["period"]] for api_name in _API_NAMES for pair in pairs]
    return period_requirements, instrument_union, pairs, keys


def _input_binding(source: _LoadedSourceRoot, identity: _FrozenSourceIdentity) -> dict[str, object]:
    requests = _list(source.receipt["provider_requests"])
    request_hashes = {
        _text(_dict(value)["member_key"]): _canonical_hash({
            "api_name": _dict(value)["api_name"],
            "fields": _dict(value)["fields"],
            "params": _dict(value)["params"],
        })
        for value in requests
    }
    raw_member_hashes = {
        _text(_dict(value)["member_key"]): _sha(_dict(value)["content_hash"])
        for value in _list(source.snapshot_metadata["members"])
    }
    return {
        "snapshot_id": identity.snapshot_id,
        "content_tree_hash": identity.content_tree_hash,
        "provenance_hash": identity.provenance_hash,
        "snapshot_file_sha256": identity.snapshot_file_sha256,
        "receipt_file_sha256": identity.receipt_file_sha256,
        "request_hash": _canonical_hash(source.receipt["request"]),
        "provider_requests_hash": _canonical_hash(requests),
        "request_hashes": request_hashes,
        "raw_member_hashes": raw_member_hashes,
    }


def _validate_frozen_hashes(manifest: dict[str, object]) -> None:
    hashes = _dict(manifest["hashes"])
    counts = _dict(manifest["counts"])
    source_extras = _dict(manifest["source_extras"])
    screens = _list(manifest["screens"])
    if (
        manifest["owner_decision_id"] != _OWNER_DECISION_ID
        or manifest["packet_body_hash"] != _PACKET_BODY_HASH
        or manifest["backtest_base_commit"] != _BASE_COMMIT
        or counts["s0_total_row_count"] != 5889
        or counts["canonical_catalog_count"] != _EXPECTED["canonical_catalog_count"]
        or counts["source_extra_count"] != _EXPECTED["s0_source_extra_count"]
        or counts["screen_count"] != 9
        or counts["all_disposition_count"] != _EXPECTED["all_disposition_count"]
        or counts["instrument_union_count"] != _EXPECTED["instrument_union_count"]
        or counts["expected_pair_count"] != _EXPECTED["expected_pair_count"]
        or counts["expected_member_key_count"] != _EXPECTED["expected_member_key_count"]
        or counts["disposition_counts"] != _EXPECTED_REASON_COUNTS
        or source_extras["roster_extra_counts_by_screen"] != _EXPECTED_ROSTER_EXTRA_COUNTS
        or source_extras["roster_extra_row_count"] != 536
        or any(hashes[key] != value for key, value in _EXPECTED.items() if key.endswith("hash"))
    ):
        _fail(QualityBbandTushareS1Failure.FROZEN_VALUE_MISMATCH)
    for screen in screens:
        value = _dict(screen)
        expected = _EXPECTED_SCREEN[str(value["screen_date"])]
        if (
            value["eligible_count"] != expected[0] or value["out_of_scope_count"] != expected[1]
            or value["unresolved_count"] != 0 or value["dispositions_hash"] != expected[2]
            or value["eligible_instrument_ids_hash"] != expected[3] or value["closure_complete"] is not True
        ):
            _fail(QualityBbandTushareS1Failure.FROZEN_VALUE_MISMATCH)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _ensure_output_parent(
    output: Path,
    *,
    failure: QualityBbandTushareS1Failure = QualityBbandTushareS1Failure.PUBLICATION_INTEGRITY_FAILURE,
) -> None:
    parent = output.parent.absolute()
    missing: list[Path] = []
    current = parent
    try:
        while not os.path.lexists(current):
            missing.append(current)
            if current == current.parent:
                raise ValueError
            current = current.parent
        if current.is_symlink() or not current.is_dir():
            raise ValueError
        for directory in reversed(missing):
            try:
                os.mkdir(directory, 0o700)
            except FileExistsError:
                if directory.is_symlink() or not directory.is_dir():
                    raise ValueError from None
            else:
                os.chmod(directory, 0o700)
                _fsync_directory(directory)
                _fsync_directory(directory.parent)
        if parent.is_symlink() or not parent.is_dir():
            raise ValueError
    except (OSError, ValueError) as error:
        raise QualityBbandTushareS1Error(failure) from error


def _rename_noreplace_at(parent_fd: int, source_name: str, target_name: str) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is None:
        raise OSError("atomic no-replace rename is unavailable")
    renameat2.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    renameat2.restype = ctypes.c_int
    if renameat2(
        parent_fd,
        os.fsencode(source_name),
        parent_fd,
        os.fsencode(target_name),
        1,
    ) != 0:
        error_number = ctypes.get_errno()
        raise OSError(error_number, os.strerror(error_number), target_name)


def _remove_publication_at(parent_fd: int, directory_name: str) -> None:
    try:
        directory_fd = os.open(
            directory_name,
            os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=parent_fd,
        )
    except FileNotFoundError:
        return
    try:
        try:
            os.unlink(_OUTPUT_NAME, dir_fd=directory_fd)
        except FileNotFoundError:
            pass
    finally:
        os.close(directory_fd)
    os.rmdir(directory_name, dir_fd=parent_fd)


def _atomic_publish(output: Path, content: bytes) -> None:
    _ensure_output_parent(output)
    parent_fd = -1
    staging_fd = -1
    staging_name = f".{output.name}.staging-{os.getpid()}"
    renamed = False
    try:
        parent_fd = os.open(
            output.parent,
            os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
        )
        parent_identity = os.fstat(parent_fd)
        for name in (output.name, staging_name):
            try:
                os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise FileExistsError
        os.mkdir(staging_name, 0o700, dir_fd=parent_fd)
        staging_fd = os.open(
            staging_name,
            os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=parent_fd,
        )
        descriptor = os.open(
            _OUTPUT_NAME,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=staging_fd,
        )
        try:
            with os.fdopen(descriptor, "wb", closefd=False) as stream:
                stream.write(content)
                stream.flush()
            os.fsync(descriptor)
            os.fchmod(descriptor, 0o600)
        finally:
            os.close(descriptor)
        read_fd = os.open(
            _OUTPUT_NAME,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=staging_fd,
        )
        try:
            metadata = os.fstat(read_fd)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_size != len(content):
                raise OSError("publication readback mismatch")
            with os.fdopen(read_fd, "rb", closefd=False) as stream:
                readback = stream.read((128 << 20) + 1)
        finally:
            os.close(read_fd)
        if readback != content:
            raise OSError("publication readback mismatch")
        os.fsync(staging_fd)
        staging_identity = os.fstat(staging_fd)
        _rename_noreplace_at(parent_fd, staging_name, output.name)
        renamed = True
        published_fd = os.open(
            output.name,
            os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=parent_fd,
        )
        try:
            published_identity = os.fstat(published_fd)
        finally:
            os.close(published_fd)
        if (published_identity.st_dev, published_identity.st_ino) != (
            staging_identity.st_dev,
            staging_identity.st_ino,
        ):
            raise OSError("publication staging entry changed")
        current_parent_fd = os.open(
            output.parent,
            os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
        )
        try:
            current_identity = os.fstat(current_parent_fd)
        finally:
            os.close(current_parent_fd)
        if (current_identity.st_dev, current_identity.st_ino) != (
            parent_identity.st_dev,
            parent_identity.st_ino,
        ):
            raise OSError("publication parent changed")
        os.fsync(parent_fd)
    except (FileExistsError, OSError, ValueError) as error:
        if parent_fd >= 0:
            try:
                _remove_publication_at(
                    parent_fd,
                    output.name if renamed else staging_name,
                )
            except OSError:
                pass
        raise QualityBbandTushareS1Error(
            QualityBbandTushareS1Failure.PUBLICATION_INTEGRITY_FAILURE
        ) from error
    finally:
        if staging_fd >= 0:
            os.close(staging_fd)
        if parent_fd >= 0:
            os.close(parent_fd)


def _preflight(s0_root: Path, annual_roster_root: Path, output: Path) -> None:
    if any(not isinstance(path, Path) for path in (s0_root, annual_roster_root, output)):
        _fail(QualityBbandTushareS1Failure.INPUT_TYPE_OR_PATH)
    try:
        if output.name in {"", ".", ".."} or output.is_symlink() or output.exists():
            raise ValueError
        resolved_output = output.resolve(strict=False)
        for root in (s0_root, annual_roster_root):
            if root.is_symlink() or not root.is_dir():
                raise ValueError
            resolved = root.resolve(strict=True)
            if resolved == resolved_output or resolved in resolved_output.parents:
                raise ValueError
        _ensure_output_parent(
            output,
            failure=QualityBbandTushareS1Failure.INPUT_TYPE_OR_PATH,
        )
    except (OSError, ValueError) as error:
        raise QualityBbandTushareS1Error(QualityBbandTushareS1Failure.INPUT_TYPE_OR_PATH) from error


def build_quality_bband_tushare_s1_structural_v1(
    *,
    s0_root: Path,
    annual_roster_root: Path,
    output_dir: Path,
) -> dict[str, object]:
    _preflight(s0_root, annual_roster_root, output_dir)
    s0 = _load_source_root(s0_root, _SOURCE_IDENTITIES["s0"])
    annual = _load_source_root(annual_roster_root, _SOURCE_IDENTITIES["annual_roster"])
    catalog, s0_extras, current_by_code = _derive_catalog_and_extras(s0)
    screens, roster_extras, roster_extra_counts = _build_screen_dispositions(catalog, current_by_code, annual)
    if any(_dict(screen)["unresolved_count"] != 0 for screen in screens):
        _fail(QualityBbandTushareS1Failure.UNRESOLVED_STRUCTURAL_AUTHORITY)
    period_requirements, instrument_union, expected_pairs, expected_member_keys = _build_financial_requirements(screens)
    all_dispositions = [disposition for screen in screens for disposition in _list(_dict(screen)["dispositions"])]
    membership = [{"screen_date": _dict(screen)["screen_date"], "instrument_ids": _dict(screen)["eligible_instrument_ids"]} for screen in screens]
    aggregate_counts: Counter[str] = Counter()
    for screen in screens:
        aggregate_counts.update(_dict(_dict(screen)["disposition_counts"]))
    disposition_counts = {key: aggregate_counts[key] for key in _EXPECTED_REASON_COUNTS}
    hashes: dict[str, object] = {
        "canonical_catalog_hash": _canonical_hash(catalog),
        "s0_source_extras_hash": _canonical_hash(s0_extras),
        "roster_extra_codes_hash": _canonical_hash(roster_extras),
        "roster_extra_counts_hash": _canonical_hash(roster_extra_counts),
        "all_dispositions_hash": _canonical_hash(all_dispositions),
        "screen_dispositions_hashes": {str(_dict(screen)["screen_date"]): _dict(screen)["dispositions_hash"] for screen in screens},
        "screen_eligible_instrument_ids_hashes": {str(_dict(screen)["screen_date"]): _dict(screen)["eligible_instrument_ids_hash"] for screen in screens},
        "screen_membership_hash": _canonical_hash(membership),
        "period_requirements_hash": _canonical_hash(period_requirements),
        "instrument_union_hash": _canonical_hash(instrument_union),
        "expected_pairs_hash": _canonical_hash(expected_pairs),
        "expected_member_keys_hash": _canonical_hash(expected_member_keys),
    }
    counts: dict[str, object] = {
        "s0_total_row_count": len(catalog) + len(s0_extras),
        "canonical_catalog_count": len(catalog),
        "source_extra_count": len(s0_extras),
        "screen_count": len(screens),
        "all_disposition_count": len(all_dispositions),
        "disposition_counts": disposition_counts,
        "instrument_union_count": len(instrument_union),
        "expected_pair_count": len(expected_pairs),
        "expected_member_key_count": len(expected_member_keys),
    }
    body: dict[str, object] = {
        "type": "quality_bband_tushare_s1_structural_manifest",
        "schema_version": 1,
        "owner_decision_id": _OWNER_DECISION_ID,
        "packet_body_hash": _PACKET_BODY_HASH,
        "backtest_base_commit": _BASE_COMMIT,
        "inputs": {
            "s0": _input_binding(s0, _SOURCE_IDENTITIES["s0"]),
            "annual_roster": _input_binding(annual, _SOURCE_IDENTITIES["annual_roster"]),
        },
        "screen_dates": list(_SCREEN_DATES),
        "broad_catalog": catalog,
        "broad_catalog_hash": hashes["canonical_catalog_hash"],
        "source_extras": {
            "s0_total_row_count": len(catalog) + len(s0_extras),
            "canonical_catalog_count": len(catalog),
            "source_extra_count": len(s0_extras),
            "bj_extra_count": sum(code.endswith(".BJ") for code in s0_extras),
            "malformed_provider_codes": [code for code in s0_extras if not code.endswith(".BJ")],
            "source_extra_codes_hash": hashes["s0_source_extras_hash"],
            "roster_extra_counts_by_screen": roster_extra_counts,
            "roster_extra_row_count": len(roster_extras),
            "roster_extra_codes_hash": hashes["roster_extra_codes_hash"],
            "roster_extra_counts_hash": hashes["roster_extra_counts_hash"],
        },
        "screens": screens,
        "instrument_union": instrument_union,
        "period_requirements": period_requirements,
        "expected_pairs": expected_pairs,
        "expected_member_keys": expected_member_keys,
        "hashes": hashes,
        "counts": counts,
        "flags": dict(_FLAGS),
        "limitations": list(_LIMITATIONS),
    }
    manifest = {**body, "manifest_id": _canonical_hash(body)}
    _validate_frozen_hashes(manifest)
    raw = _canonical_json(manifest).encode("utf-8")
    parsed = _dict(_strict_json(raw))
    manifest_id = parsed.pop("manifest_id", None)
    if (
        manifest_id != _canonical_hash(parsed) or manifest_id != _EXPECTED_MANIFEST_ID
        or len(raw) != _EXPECTED_OUTPUT_SIZE or _bytes_hash(raw) != _EXPECTED_OUTPUT_HASH
        or raw.endswith(b"\n")
    ):
        _fail(QualityBbandTushareS1Failure.PUBLICATION_INTEGRITY_FAILURE)
    _atomic_publish(output_dir, raw)
    return manifest


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the frozen offline Quality-BBAND Tushare S1 structural manifest")
    parser.add_argument("--s0-root", type=Path, required=True)
    parser.add_argument("--annual-roster-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        manifest = build_quality_bband_tushare_s1_structural_v1(
            s0_root=args.s0_root,
            annual_roster_root=args.annual_roster_root,
            output_dir=args.output_dir,
        )
    except QualityBbandTushareS1Error as error:
        print(error.code.value)
        return 1
    print(manifest["manifest_id"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
