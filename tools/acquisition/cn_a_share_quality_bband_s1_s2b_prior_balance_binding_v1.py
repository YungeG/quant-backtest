from __future__ import annotations

import argparse
import collections
import ctypes
import hashlib
import json
import math
import os
import re
import stat
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import NoReturn

from crypto_quant_bundle_builder.source_snapshots import (
    RawSourceMember,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
    verify_source_snapshot,
)

_BASE_COMMIT = "0c00c8266c2fe904e11f982979d804ff5d205700"
_OUTPUT_FILES = (
    "prior-balance-requirements.json",
    "prior-balance-provider-rows.jsonl",
    "prior-balance-binding-manifest.json",
)
_EXPECTED_REQUIREMENTS_ID = "sha256:226c7f1e5e678e1d8b35eca4a52a7427030b83605088199bbb14a297020e1a6e"
_EXPECTED_REQUIREMENTS_SIZE = 486611
_EXPECTED_REQUIREMENTS_HASH = "sha256:b51724cc10ce8fb2556ed59bb75e654a7dfff60f1a142ae0abf2bd7eede357cb"
_EXPECTED_PROVIDER_ROWS = 5677
_EXPECTED_PROVIDER_ROW_IDS_HASH = "sha256:1418102e92a50c28b379751fdc012af4f6751b90dc420f1b2711abf4f3fd63b3"
_EXPECTED_PROVIDER_ROWS_SIZE = 4237509
_EXPECTED_PROVIDER_ROWS_HASH = "sha256:2b83d008ce3783f10e0a4e505e3cf165baa04baba885e6e1f4d9fe54345ae4bc"
_EXPECTED_MANIFEST_ID = "sha256:1b34a72179420bd0da6ca336d0ee6a46c039177117c23993c79afed2e888d674"
_EXPECTED_MANIFEST_SIZE = 19299
_EXPECTED_MANIFEST_HASH = "sha256:f5c4c2f83352f68948e31a9cb049d8dfba20e6e12bcd9d6adc8e37152fdee124"
_FIELD_SET_HASH = "sha256:478395530452a41e1629230ecfae47b60010660f812052bd72030eb21e88c1ef"
_REQUIREMENT_HASHES = {
    "prior_endpoint_requirements_hash": "sha256:25c51af2a2f6423628e45ad9a53a61f49abce56e94ab10fd99d97b37fa55f70d",
    "prior_endpoint_member_keys_hash": "sha256:1a8c67951afffef40913eef9a09ed9c2aa15dc16163a6dca277fa266e26ee23a",
    "existing_core_requirements_hash": "sha256:ca92075c42cb2c671067765a18aa6141deb037e6bb83ec5f906531230c93fd85",
    "existing_core_member_keys_hash": "sha256:f014f802696a51a3c555bc23dd06bc175b3ec40d96a54db9f29e45c42469cd65",
    "additive_requirements_hash": "sha256:1f3e1b7f235b7eb44af41e547312d88c7cc51acf609faeb9edde9cade49b0410",
    "additive_member_keys_hash": "sha256:22df5bc4326477e0f4a3ff4da69a8a9681d7b7e0065c59f9d98b38179546918e",
    "accepted_s2a_requirements_hash": "sha256:7cb4cd30074489cd0d11659ed917511ad4597ea21e7b5cdaaba621f64ea285f9",
    "accepted_s2a_simple_keys_hash": "sha256:3105da5d6545d147c569f9d7319a9c265d68f187a877fb9861d790affbe9dc5a",
    "stage_a_2011_requirements_hash": "sha256:a796d90e6b6b29368854207f7a4a85e16cc7bd8a28d7de93f04e90866c139a68",
    "stage_a_2011_simple_keys_hash": "sha256:5b89864342028b6485ba38d170b52edb9e2df312e6615c35047407679406f0b5",
}
_PERIOD_COUNTS = {
    "20111231": (1995, 0, 1995),
    "20121231": (2034, 1987, 47),
    "20131231": (2053, 2027, 26),
    "20141231": (2143, 2035, 108),
    "20151231": (2224, 2125, 99),
    "20161231": (2434, 2205, 229),
    "20171231": (2612, 2404, 208),
    "20181231": (2635, 2577, 58),
    "20191231": (2667, 2592, 75),
}
_FLAGS = {
    "owner_approved_tushare_authority": True,
    "formal_s1_qualified": True,
    "provider_scope_exact": True,
    "s2b_exact_cover_complete": True,
    "prior_balance_provider_scope_exact": True,
    "prior_balance_endpoint_cover_complete": True,
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
_LIMITATIONS = sorted(
    (
        "FINANCIAL_PAYLOAD_AND_SCOPE_NOT_QUALIFIED",
        "FORMAL_S2_FALSE",
        "NO_REVISION_SUPERSESSION_SELECTION",
        "NO_STRATEGY_BACKTEST_VALIDATION_OR_DEPLOYMENT_AUTHORITY",
        "ORIGINAL_UPSTREAM_ARTIFACT_BYTES_UNCHANGED",
        "PRIOR_BALANCE_BINDING_ADDS_ENDPOINT_COVER_ONLY",
        "PROVIDER_DATES_NOT_AVAILABILITY_AUTHORITY",
        "REVISION_CANDIDATES_RETAINED_WITHOUT_UPDATE_FLAG_SELECTION",
    )
)


class QualityBbandS1S2bPriorBalanceBindingFailure(str, Enum):
    INPUT_TYPE_MISMATCH = "INPUT_TYPE_MISMATCH"
    CATALOG_IDENTITY_MISMATCH = "CATALOG_IDENTITY_MISMATCH"
    SOURCE_MEMBER_CONFLICT = "SOURCE_MEMBER_CONFLICT"
    FINANCIAL_REVISION_MISMATCH = "FINANCIAL_REVISION_MISMATCH"
    FINANCIAL_PAYLOAD_INCOMPLETE = "FINANCIAL_PAYLOAD_INCOMPLETE"
    BUNDLE_EXACT_COVER_MISMATCH = "BUNDLE_EXACT_COVER_MISMATCH"
    PUBLICATION_INTEGRITY_FAILURE = "PUBLICATION_INTEGRITY_FAILURE"


class QualityBbandS1S2bPriorBalanceBindingError(RuntimeError):
    def __init__(
        self,
        code: QualityBbandS1S2bPriorBalanceBindingFailure,
        reason: str | None = None,
    ) -> None:
        if type(code) is not QualityBbandS1S2bPriorBalanceBindingFailure:
            raise TypeError("code must be a prior-balance binding failure")
        self.code = code
        self.reason = reason
        super().__init__(code.value if reason is None else f"{code.value}/{reason}")


@dataclass(frozen=True, slots=True)
class _FrozenFile:
    name: str
    byte_count: int
    sha256: str


@dataclass(frozen=True, slots=True)
class _FrozenSourceIdentity:
    snapshot_id: str
    content_tree_hash: str
    provenance_hash: str
    snapshot_file: _FrozenFile
    receipt_file: _FrozenFile
    receipt_type: str
    snapshot_member_count: int
    regular_file_count: int
    root_byte_count: int
    request_hash: str
    provider_requests_hash: str
    root_trees_hash: str


@dataclass(frozen=True, slots=True)
class _ReadMember:
    raw: bytes | None
    byte_count: int
    sha256: str


@dataclass(frozen=True, slots=True)
class _SourceFileObservation:
    device: int
    inode: int
    byte_count: int
    mtime_ns: int
    ctime_ns: int


@dataclass(frozen=True, slots=True)
class _LoadedSourceRoot:
    snapshot_metadata: dict[str, object]
    receipt: dict[str, object]
    member_bytes: dict[str, bytes]


@dataclass(frozen=True, slots=True)
class _PriorRequirementSets:
    all: list[dict[str, object]]
    core: list[dict[str, object]]
    additive: list[dict[str, object]]
    s2a: list[dict[str, object]]
    stage_a: list[dict[str, object]]


@dataclass(frozen=True, slots=True)
class _PriorExtraction:
    records: list[dict[str, object]]
    row_ids: list[str]
    keys: set[tuple[str, str, str, str]]
    audit: dict[str, object]


_STAGE_BINDING_FILE = _FrozenFile(
    "stage-binding-manifest.json",
    7323,
    "sha256:ba5abfc5fc592ceb88ce1cabc95ebbded24abe9a8b108e9f6a31c96a0cc0878c",
)
_S2B_FILES = {
    value.name: value
    for value in (
        _FrozenFile("provisional-expected-set.json", 6587372, "sha256:55c4ecdee60e77feec3d2ee8c4d8da5b16a4e6a1e07bf2acc49a08669b8d1a29"),
        _FrozenFile("provider-rows.jsonl", 90363445, "sha256:f4ed00c232930e1067c2796f7e5c3622397e8649e1afa0d5ae8730c964cf7abe"),
        _FrozenFile("official-coverage.json", 17755, "sha256:a0971482128b6e4e2f0bcdbdbb10f1102211974fd98157c0185ec25fc08e5b3b"),
        _FrozenFile("extraction-manifest.json", 62418, "sha256:74c60758f4b6eb9534900f868bdef444e5891ad6b4eee996e6713eb2e8ea876f"),
    )
}
_S2A_IDENTITY = _FrozenSourceIdentity(
    "sha256:4e6574363c36f6cebe7f0ad46585a3a9e31b623546240196a2b8bcf55ec57160",
    "sha256:3316ea2f6c71f092f5bd803aad6731039b2bc6956c7f176c67183ecaded3e199",
    "sha256:fb1bfdc0646988d4881bb8a7c1abef61ebce91f46844b6cc83eb6925dc560e09",
    _FrozenFile("source-snapshot.json", 69608, "sha256:f0f1d394e98b298d0bb59990370c6ffb26ad70b89cb99aade3026f732aa1cba3"),
    _FrozenFile("acquisition-receipt.json", 352402, "sha256:30afdba09e0a04da1257489a7e13fcee062f41233006fe1d5d8bc33c748791a9"),
    "tushare_s2a_vip_financial_source_bounded_acquisition_receipt_v1",
    245,
    247,
    181320534,
    "sha256:1f6425374a2712c31f874f722fe99c31d102c252d40d255d0f8bf7e87dd57255",
    "sha256:921b08212a67329d08712558332c2466139fdff8cd6b7d1da5fe55544cf28902",
    "sha256:f78c5e30403aeac09fabb8c42cacacfcb8b730a87ed57c66a5dc8ea2e70698a7",
)
_STAGE_A_IDENTITY = _FrozenSourceIdentity(
    "sha256:2bad85751bb5d6fb67509ea0119e61298f8b3083986c62bb3fe9fae35c0b34d9",
    "sha256:7f853c028026313ad1662214830b199ef9ff72fd7518e34b0bcbf1d751309f66",
    "sha256:452088d651f253b405e641b48b27f25aa0d2adcbe40af48c060ec3a924dc2dad",
    _FrozenFile("source-snapshot.json", 907, "sha256:768810d6d5e68b47566629830a12e55400982af59cc97e0c20b7370893eefff9"),
    _FrozenFile("acquisition-receipt.json", 4679, "sha256:89a8e968ab5dae799a60de0973481e830e3189b8523bb3613e3a2d685c802081"),
    "tushare_s2c_2011_prior_balance_source_bounded_acquisition_receipt_v1",
    1,
    3,
    1174490,
    "sha256:006acb5db4946a31ee474e4cec70f67f02a0d094c0016d8cf9e86b326a8d82e6",
    "sha256:9c2bdb291bda9a3c0bc67d98a84e111fc59eef5a710582f907252013bbd218df",
    "sha256:ee80ae157b2bae7716fdcf38cbe37fb479fa3c5eec4a4b2d1356d6c86fedebf4",
)


def _fail(
    code: QualityBbandS1S2bPriorBalanceBindingFailure,
    reason: str | None = None,
) -> NoReturn:
    raise QualityBbandS1S2bPriorBalanceBindingError(code, reason)


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


def _integer(value: object) -> int:
    if type(value) is not int:
        raise TypeError("expected exact JSON integer")
    return value


def _text_or_none(value: object) -> str | None:
    if value is not None and type(value) is not str:
        raise TypeError("expected JSON text or null")
    return value


def _body_id(value: dict[str, object], name: str) -> str:
    body = dict(value)
    identifier = body.pop(name, None)
    return identifier if type(identifier) is str and identifier == _canonical_hash(body) else ""


def _read_exact_member(root_fd: int, frozen: _FrozenFile, *, keep_bytes: bool) -> _ReadMember:
    descriptor = os.open(frozen.name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=root_fd)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError("member is not regular")
        if metadata.st_size != frozen.byte_count:
            raise ValueError("member byte count mismatch")
        digest = hashlib.sha256()
        chunks: list[bytes] | None = [] if keep_bytes else None
        total = 0
        while True:
            chunk = os.read(descriptor, min(1 << 20, frozen.byte_count - total + 1))
            if not chunk:
                break
            total += len(chunk)
            if total > frozen.byte_count:
                raise ValueError("member exceeds frozen size")
            digest.update(chunk)
            if chunks is not None:
                chunks.append(chunk)
        if total != frozen.byte_count:
            raise ValueError("member changed during read")
        return _ReadMember(None if chunks is None else b"".join(chunks), total, "sha256:" + digest.hexdigest())
    finally:
        os.close(descriptor)


def _open_exact_fixed_root(root: Path, names: set[str]) -> int:
    descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0))
    try:
        if set(os.listdir(descriptor)) != names:
            raise ValueError("fixed root member set mismatch")
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _load_stage_binding(root: Path) -> dict[str, object]:
    descriptor = _open_exact_fixed_root(root, {_STAGE_BINDING_FILE.name})
    try:
        member = _read_exact_member(descriptor, _STAGE_BINDING_FILE, keep_bytes=True)
        if set(os.listdir(descriptor)) != {_STAGE_BINDING_FILE.name}:
            raise ValueError("stage binding root changed during read")
    finally:
        os.close(descriptor)
    if member.sha256 != _STAGE_BINDING_FILE.sha256 or member.raw is None:
        raise ValueError("stage binding identity mismatch")
    manifest = _dict(_strict_json(member.raw))
    if (
        manifest.get("type") != "quality_bband_tushare_s1_s2b_stage_binding_manifest"
        or manifest.get("schema_version") != 1
        or manifest.get("manifest_id") != "sha256:c54bac9818a24688699aa585e49e91bde64ddbaf3efa90e0aa18491ff9b86f5c"
        or _body_id(manifest, "manifest_id") != manifest["manifest_id"]
    ):
        raise ValueError("stage binding manifest mismatch")
    return manifest


def _load_s2b(root: Path) -> tuple[dict[str, object], dict[str, object], dict[str, object], dict[str, _ReadMember]]:
    descriptor = _open_exact_fixed_root(root, set(_S2B_FILES))
    members: dict[str, _ReadMember] = {}
    try:
        for name, frozen in _S2B_FILES.items():
            members[name] = _read_exact_member(descriptor, frozen, keep_bytes=name != "provider-rows.jsonl")
        if set(os.listdir(descriptor)) != set(_S2B_FILES):
            raise ValueError("S2B root changed during read")
    finally:
        os.close(descriptor)
    if any(members[name].sha256 != frozen.sha256 for name, frozen in _S2B_FILES.items()):
        raise ValueError("S2B member identity mismatch")
    expected = _dict(_strict_json(members["provisional-expected-set.json"].raw or b""))
    official = _dict(_strict_json(members["official-coverage.json"].raw or b""))
    extraction = _dict(_strict_json(members["extraction-manifest.json"].raw or b""))
    if (
        expected.get("type") != "quality_bband_s2b_provisional_expected_set"
        or expected.get("expected_set_id") != "sha256:8c679397ff7ecfe67e0bbf68951d9fa388de9f2adfaf53a4f8b5395b0cea2cf6"
        or _body_id(expected, "expected_set_id") != expected["expected_set_id"]
        or official.get("type") != "quality_bband_s2b_official_coverage"
        or official.get("official_coverage_id") != "sha256:f245ebd560bb15644b1b072d277d3847d3477e7125677bd2e683e5a7c0636907"
        or _body_id(official, "official_coverage_id") != official["official_coverage_id"]
        or extraction.get("type") != "quality_bband_s2b_provisional_exact_extraction_manifest"
        or extraction.get("manifest_id") != "sha256:e526416335016b9fd421e138655303673e76dc2bf6e2f53a6bb580904ed70d74"
        or _body_id(extraction, "manifest_id") != extraction["manifest_id"]
    ):
        raise ValueError("S2B catalog identity mismatch")
    return expected, official, extraction, members


def _source_file_observation(metadata: os.stat_result) -> _SourceFileObservation:
    return _SourceFileObservation(
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _enumerate_source_files(root_fd: int) -> dict[str, _SourceFileObservation]:
    files: dict[str, _SourceFileObservation] = {}

    def visit(directory_fd: int, prefix: str) -> None:
        for name in sorted(os.listdir(directory_fd)):
            path_metadata = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            member_key = f"{prefix}/{name}" if prefix else name
            if stat.S_ISDIR(path_metadata.st_mode):
                child_fd = os.open(
                    name,
                    os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
                    dir_fd=directory_fd,
                )
                try:
                    visit(child_fd, member_key)
                finally:
                    os.close(child_fd)
            elif stat.S_ISREG(path_metadata.st_mode):
                member_fd = os.open(name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=directory_fd)
                try:
                    descriptor_metadata = os.fstat(member_fd)
                    current_path_metadata = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
                    observation = _source_file_observation(descriptor_metadata)
                    if (
                        not stat.S_ISREG(descriptor_metadata.st_mode)
                        or _source_file_observation(path_metadata) != observation
                        or _source_file_observation(current_path_metadata) != observation
                    ):
                        raise ValueError("source member changed during enumeration")
                    files[member_key] = observation
                finally:
                    os.close(member_fd)
            else:
                raise ValueError("source tree contains non-file member")

    visit(root_fd, "")
    return files


class _DeclaredPayloadConflict(ValueError):
    pass


def _read_source_member(
    root_fd: int,
    member_key: str,
    expected_observation: _SourceFileObservation,
    expected_bytes: int,
    maximum_bytes: int = 64 << 20,
) -> bytes:
    parts = member_key.split("/")
    if not parts or member_key.startswith("/") or any(part in {"", ".", ".."} for part in parts):
        raise ValueError("unsafe source member key")
    descriptor = os.dup(root_fd)
    try:
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0), dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        member_fd = os.open(parts[-1], os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=descriptor)
        try:
            metadata = os.fstat(member_fd)
            if (
                not stat.S_ISREG(metadata.st_mode)
                or _source_file_observation(metadata) != expected_observation
                or expected_bytes > maximum_bytes
            ):
                raise ValueError("unsafe source member")
            if metadata.st_size != expected_bytes:
                raise _DeclaredPayloadConflict("declared source member byte count mismatch")
            chunks: list[bytes] = []
            total = 0
            while total <= expected_bytes:
                chunk = os.read(member_fd, expected_bytes - total + 1)
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
            if total != expected_bytes:
                raise _DeclaredPayloadConflict("declared source member changed during read")
            return b"".join(chunks)
        finally:
            os.close(member_fd)
    finally:
        os.close(descriptor)


def _load_source_root_checked(root: Path, identity: _FrozenSourceIdentity) -> _LoadedSourceRoot:
    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0))
    try:
        files = _enumerate_source_files(root_fd)
        if len(files) != identity.regular_file_count or sum(value.byte_count for value in files.values()) != identity.root_byte_count:
            raise ValueError("source root count mismatch")
        snapshot_raw = _read_source_member(
            root_fd,
            identity.snapshot_file.name,
            files[identity.snapshot_file.name],
            identity.snapshot_file.byte_count,
            16 << 20,
        )
        receipt_raw = _read_source_member(
            root_fd,
            identity.receipt_file.name,
            files[identity.receipt_file.name],
            identity.receipt_file.byte_count,
            16 << 20,
        )
        if _bytes_hash(snapshot_raw) != identity.snapshot_file.sha256 or _bytes_hash(receipt_raw) != identity.receipt_file.sha256:
            raise ValueError("source fixed file identity mismatch")
        snapshot = _dict(_strict_json(snapshot_raw))
        receipt = _dict(_strict_json(receipt_raw))
        if (
            snapshot.get("type") != "source_snapshot"
            or snapshot.get("schema_version") != 1
            or snapshot.get("snapshot_id") != identity.snapshot_id
            or snapshot.get("content_tree_hash") != identity.content_tree_hash
            or snapshot.get("provenance_hash") != identity.provenance_hash
            or snapshot.get("decision_grade_eligible") is not False
            or snapshot.get("deployment_authorized") is not False
            or receipt.get("type") != identity.receipt_type
            or _canonical_hash(receipt.get("request")) != identity.request_hash
            or _canonical_hash(receipt.get("provider_requests")) != identity.provider_requests_hash
        ):
            raise ValueError("source snapshot or receipt identity mismatch")
        trees = receipt.get("root_trees") if "root_trees" in receipt else receipt.get("root_tree")
        if _canonical_hash(trees) != identity.root_trees_hash:
            raise ValueError("source root tree mismatch")
        provenance_value = _dict(snapshot.get("provenance"))
        provenance = SourceSnapshotProvenance(**provenance_value)  # type: ignore[arg-type]
        member_bytes: dict[str, bytes] = {}
        declared_member_keys: set[str] = set()
        raw_members: list[RawSourceMember] = []
        member_conflict = False
        members = _list(snapshot.get("members"))
        if len(members) != identity.snapshot_member_count:
            raise ValueError("source snapshot member count mismatch")
        for value in members:
            member = _dict(value)
            member_key = member.get("member_key")
            byte_count = member.get("byte_count")
            content_hash = member.get("content_hash")
            if (
                type(member_key) is not str
                or type(byte_count) is not int
                or byte_count < 0
                or type(content_hash) is not str
                or re.fullmatch(r"sha256:[0-9a-f]{64}", content_hash) is None
                or member_key in declared_member_keys
                or member_key not in files
            ):
                raise ValueError("source member metadata mismatch")
            declared_member_keys.add(member_key)
            try:
                raw = _read_source_member(root_fd, member_key, files[member_key], byte_count)
            except _DeclaredPayloadConflict:
                member_conflict = True
                continue
            if _bytes_hash(raw) != content_hash:
                member_conflict = True
            member_bytes[member_key] = raw
            raw_members.append(
                RawSourceMember(
                    member_key,
                    raw,
                    str(member.get("mode")),
                    _integer(member.get("acquired_at_epoch_nanoseconds")),
                    _text_or_none(member.get("declared_sha256")),
                )
            )
        if set(files) != declared_member_keys | {identity.snapshot_file.name, identity.receipt_file.name}:
            raise ValueError("source root exact member mismatch")
        after_files = _enumerate_source_files(root_fd)
        if (
            files != after_files
            or len(after_files) != identity.regular_file_count
            or sum(value.byte_count for value in after_files.values()) != identity.root_byte_count
        ):
            raise ValueError("source root changed during read")
        if member_conflict:
            _fail(QualityBbandS1S2bPriorBalanceBindingFailure.SOURCE_MEMBER_CONFLICT)
        rebuilt = freeze_source_snapshot(members=tuple(raw_members), provenance=provenance)
        if (
            rebuilt.snapshot is None
            or verify_source_snapshot(rebuilt.snapshot).snapshot is None
            or rebuilt.snapshot.to_canonical_dict() != snapshot
        ):
            raise ValueError("source snapshot reconstruction mismatch")
        return _LoadedSourceRoot(snapshot, receipt, member_bytes)
    finally:
        os.close(root_fd)


def _load_source_root(root: Path, identity: _FrozenSourceIdentity) -> _LoadedSourceRoot:
    try:
        return _load_source_root_checked(root, identity)
    except QualityBbandS1S2bPriorBalanceBindingError:
        raise
    except (KeyError, OSError, TypeError, ValueError) as error:
        raise QualityBbandS1S2bPriorBalanceBindingError(
            QualityBbandS1S2bPriorBalanceBindingFailure.CATALOG_IDENTITY_MISMATCH
        ) from error


def _validate_upstream_authority(
    binding: dict[str, object],
    expected: dict[str, object],
    official: dict[str, object],
    extraction: dict[str, object],
) -> None:
    flags = _dict(binding.get("flags"))
    accounting = _dict(extraction.get("accounting"))
    false_names = (
        "formal_s2_qualified", "financial_payload_complete", "financial_scope_qualified",
        "decision_grade_eligible", "strategy_authorized", "strategy_target_authorized",
        "backtest_authorized", "validation_authorized", "deployment_authorized",
    )
    if (
        flags.get("owner_approved_tushare_authority") is not True
        or flags.get("formal_s1_qualified") is not True
        or flags.get("s2b_exact_cover_complete") is not True
        or any(flags.get(name) is not False for name in false_names)
        or expected.get("expected_member_count") != 96537
        or extraction.get("closure_equation") != "96537 = 96515 P + 1 O + 21 N"
        or extraction.get("provisional_exact_cover_complete") is not True
        or accounting.get("provider_member_count") != 96515
        or accounting.get("official_filing_member_count") != 1
        or accounting.get("official_nonfiling_member_count") != 21
        or official.get("o_member_count") != 1
        or official.get("n_member_count") != 21
        or any(extraction.get(name) is not False for name in false_names)
    ):
        raise ValueError("upstream authority mismatch")


def _instrument(provider_code: str) -> dict[str, str]:
    if re.fullmatch(r"\d{6}\.SZ", provider_code):
        return {"type": "instrument_id", "venue": "xshe", "stable_key": provider_code[:6]}
    if re.fullmatch(r"\d{6}\.SH", provider_code):
        return {"type": "instrument_id", "venue": "xshg", "stable_key": provider_code[:6]}
    raise ValueError("noncanonical provider code")


def _requirement_key(value: dict[str, object]) -> tuple[str, str, str]:
    instrument = _dict(value["instrument_id"])
    return str(instrument["venue"]), str(instrument["stable_key"]), str(value["period"])


def _member_keys(values: list[dict[str, object]]) -> list[list[object]]:
    return [[value["api_name"], value["instrument_id"], value["period"]] for value in values]


def _simple_keys(values: list[dict[str, object]]) -> list[list[object]]:
    return [
        [value["api_name"], _dict(value["instrument_id"])["venue"], _dict(value["instrument_id"])["stable_key"], value["period"]]
        for value in values
    ]


def _period_counts(values: list[dict[str, object]]) -> dict[str, int]:
    return dict(sorted(collections.Counter(str(value["period"]) for value in values).items()))


def _derive_prior_requirements(expected: dict[str, object]) -> _PriorRequirementSets:
    core_keys = {
        (str(_dict(pair)["instrument_id"]["venue"]), str(_dict(pair)["instrument_id"]["stable_key"]), str(_dict(pair)["period"]))  # type: ignore[index]
        for pair in _list(expected.get("expected_pairs"))
    }
    all_requirements: list[dict[str, object]] = []
    for screen_value in _list(expected.get("screens")):
        screen = _dict(screen_value)
        screen_date = str(screen["screen_date"])
        period = f"{int(screen_date[:4]) - 6}1231"
        for instrument in _list(screen["instrument_ids"]):
            all_requirements.append(
                {
                    "api_name": "balancesheet_vip",
                    "instrument_id": instrument,
                    "period": period,
                    "required_by_screen_dates": [screen_date],
                }
            )
    all_requirements.sort(key=_requirement_key)
    core = [value for value in all_requirements if _requirement_key(value) in core_keys]
    additive = [value for value in all_requirements if _requirement_key(value) not in core_keys]
    s2a = [value for value in additive if value["period"] != "20111231"]
    stage_a = [value for value in additive if value["period"] == "20111231"]
    hashes = {
        "prior_endpoint_requirements_hash": _canonical_hash(all_requirements),
        "prior_endpoint_member_keys_hash": _canonical_hash(_member_keys(all_requirements)),
        "existing_core_requirements_hash": _canonical_hash(core),
        "existing_core_member_keys_hash": _canonical_hash(_member_keys(core)),
        "additive_requirements_hash": _canonical_hash(additive),
        "additive_member_keys_hash": _canonical_hash(_member_keys(additive)),
        "accepted_s2a_requirements_hash": _canonical_hash(s2a),
        "accepted_s2a_simple_keys_hash": _canonical_hash(_simple_keys(s2a)),
        "stage_a_2011_requirements_hash": _canonical_hash(stage_a),
        "stage_a_2011_simple_keys_hash": _canonical_hash(_simple_keys(stage_a)),
    }
    period_counts = {period: (len([v for v in all_requirements if v["period"] == period]), len([v for v in core if v["period"] == period]), len([v for v in additive if v["period"] == period])) for period in _PERIOD_COUNTS}
    if (
        (len(all_requirements), len(core), len(additive), len(s2a), len(stage_a)) != (20797, 17952, 2845, 850, 1995)
        or hashes != _REQUIREMENT_HASHES
        or period_counts != _PERIOD_COUNTS
    ):
        _fail(QualityBbandS1S2bPriorBalanceBindingFailure.BUNDLE_EXACT_COVER_MISMATCH, "PAIR_DISPOSITION_CLOSURE_MISMATCH")
    return _PriorRequirementSets(all_requirements, core, additive, s2a, stage_a)


def _build_requirements(
    binding: dict[str, object], expected: dict[str, object], requirements: _PriorRequirementSets
) -> dict[str, object]:
    body: dict[str, object] = {
        "type": "quality_bband_prior_balance_requirements",
        "schema_version": 1,
        "inputs": {
            "stage_binding_manifest_id": binding["manifest_id"],
            "s2b_expected_set_id": expected["expected_set_id"],
            "s2b_expected_pairs_hash": expected["expected_pairs_hash"],
            "s2b_expected_member_keys_hash": expected["expected_member_keys_hash"],
        },
        "derivation": {
            "api_name": "balancesheet_vip",
            "screen_date_order": [_dict(value)["screen_date"] for value in _list(expected["screens"])],
            "prior_period_rule": "December 31 of screen year minus 6",
            "core_membership_rule": "same [api_name,instrument_id,period] exists in S2B expected member keys",
            "source_partition_rule": "core first, then accepted S2A for 20121231-20191231, then Stage A for 20111231",
            "requirement_order": ["instrument_id.venue", "instrument_id.stable_key", "period"],
            "required_by_screen_date_order": "ascending",
        },
        "accounting": {
            "prior_endpoint_requirement_count": len(requirements.all),
            "existing_core_balance_key_count": len(requirements.core),
            "additive_balance_key_count": len(requirements.additive),
            "accepted_s2a_balance_key_count": len(requirements.s2a),
            "stage_a_2011_balance_key_count": len(requirements.stage_a),
            "augmented_statement_member_requirement_count": _integer(expected["expected_member_count"]) + len(requirements.additive),
            "prior_period_counts": _period_counts(requirements.all),
            "existing_core_period_counts": _period_counts(requirements.core),
            "additive_period_counts": _period_counts(requirements.additive),
        },
        "hashes": dict(_REQUIREMENT_HASHES),
        "requirements": requirements.additive,
    }
    return {**body, "requirements_id": _canonical_hash(body)}


def _provider_rows(raw: bytes, fields: list[str]) -> list[list[object]]:
    envelope = _dict(_strict_json(raw), keys={"request_id", "code", "data", "msg", "detail"})
    data = _dict(envelope["data"], keys={"fields", "items", "has_more", "count"})
    if data["fields"] != fields or type(data["items"]) is not list:
        raise ValueError("provider envelope mismatch")
    rows: list[list[object]] = []
    for value in _list(data["items"]):
        row = _list(value)
        if len(row) != len(fields):
            raise ValueError("provider row width mismatch")
        rows.append(row)
    return rows


def _source_row_id(
    *, role: str, snapshot_id: str, member_key: str, member_hash: str,
    row_index: int, fields_hash: str, row: list[object]
) -> str:
    return _canonical_hash(
        {
            "type": "quality_bband_prior_balance_source_row_identity",
            "schema_version": 1,
            "source_role": role,
            "source_snapshot_id": snapshot_id,
            "source_member_key": member_key,
            "source_member_content_hash": member_hash,
            "source_row_index": row_index,
            "api_name": "balancesheet_vip",
            "field_set_hash": fields_hash,
            "row": row,
        }
    )


def _classify_duplicate_rows(
    groups: dict[tuple[str, str], list[tuple[str, int, list[object], str]]], *, canonical: bool
) -> tuple[dict[str, object], list[list[object]], list[list[object]]]:
    counts: collections.Counter[str] = collections.Counter()
    economic: list[list[object]] = []
    metadata: list[list[object]] = []
    for (code, period), values in groups.items():
        rows = [value[2] for value in values]
        if len(rows) == 1:
            counts["single"] += 1
        elif len({tuple(row[:-1]) for row in rows}) == 1:
            counts["update"] += 1
        elif len({tuple(row[6:-1]) for row in rows}) == 1:
            counts["metadata"] += 1
            metadata.append(["balancesheet_vip", _instrument(code) if canonical else code, period])
        else:
            counts["economic"] += 1
            economic.append(["balancesheet_vip", _instrument(code) if canonical else code, period])
    if canonical:
        order = lambda value: (value[1]["venue"], value[1]["stable_key"], value[2])  # type: ignore[index]
    else:
        order = lambda value: (value[1], value[2])
    economic.sort(key=order)
    metadata.sort(key=order)
    profile = {
        "key_count": len(groups),
        "row_count": sum(len(values) for values in groups.values()),
        "revision_surplus_row_count": sum(len(values) - 1 for values in groups.values()),
        "single_row_key_count": counts["single"],
        "duplicate_key_count": len(groups) - counts["single"],
        "update_flag_only_duplicate_key_count": counts["update"],
        "metadata_revision_only_duplicate_key_count": counts["metadata"],
        "economic_revision_conflict_key_count": counts["economic"],
        "economic_revision_conflict_member_keys_hash": _canonical_hash(economic),
        "metadata_revision_only_member_keys_hash": _canonical_hash(metadata),
        "maximum_rows_per_key": max(map(len, groups.values())),
    }
    return profile, economic, metadata


def _extract_prior_rows(
    source: _LoadedSourceRoot,
    role: str,
    requirements: list[dict[str, object]],
    periods: set[str],
) -> _PriorExtraction:
    snapshot = source.snapshot_metadata
    receipt = source.receipt
    members = {str(_dict(value)["member_key"]): _dict(value) for value in _list(snapshot["members"])}
    fields_value = _dict(receipt["request"])["field_sets"]["balancesheet_vip"] if role == "ACCEPTED_S2A" else _dict(receipt["request"])["fields"]  # type: ignore[index]
    fields = [str(value) for value in _list(fields_value)]
    if len(fields) != 19 or _canonical_hash(fields) != _FIELD_SET_HASH:
        raise ValueError("financial field set mismatch")
    needed = {
        (str(_dict(value["instrument_id"])["stable_key"]) + (".SZ" if _dict(value["instrument_id"])["venue"] == "xshe" else ".SH"), str(value["period"]))
        for value in requirements
    }
    tree_values = _list(receipt["root_trees"]) if role == "ACCEPTED_S2A" else [receipt["root_tree"]]
    trees = sorted(
        (_dict(value) for value in tree_values if _dict(value).get("api_name") == "balancesheet_vip" and _dict(value).get("period") in periods),
        key=lambda value: (str(value["period"]), str(value["root_member_key"])),
    )
    records: list[dict[str, object]] = []
    all_ids: list[str] = []
    extra_ids: list[str] = []
    groups: dict[tuple[str, str], list[tuple[str, int, list[object], str]]] = collections.defaultdict(list)
    all_groups: dict[tuple[str, str], list[tuple[str, int, list[object], str]]] = collections.defaultdict(list)
    leaves: list[dict[str, object]] = []
    extra_codes: set[str] = set()
    extra_keys: set[tuple[str, str, str]] = set()
    for tree in trees:
        for member_key_value in sorted(str(value) for value in _list(tree["terminal_leaf_member_keys"])):
            member_key = member_key_value
            if member_key not in source.member_bytes or member_key not in members:
                raise ValueError("terminal source member missing")
            rows = _provider_rows(source.member_bytes[member_key], fields)
            selected_count = 0
            extra_count = 0
            for row_index, row in enumerate(rows):
                if type(row[0]) is not str or type(row[3]) is not str:
                    raise ValueError("financial row key mismatch")
                code, period = row[0], row[3]
                row_id = _source_row_id(
                    role=role,
                    snapshot_id=str(snapshot["snapshot_id"]),
                    member_key=member_key,
                    member_hash=str(members[member_key]["content_hash"]),
                    row_index=row_index,
                    fields_hash=_FIELD_SET_HASH,
                    row=row,
                )
                all_ids.append(row_id)
                all_groups[(code, period)].append((member_key, row_index, row, row_id))
                if (code, period) in needed:
                    instrument = _instrument(code)
                    groups[(code, period)].append((member_key, row_index, row, row_id))
                    selected_count += 1
                    records.append(
                        {
                            "type": "quality_bband_prior_balance_provider_row",
                            "schema_version": 1,
                            "source_row_id": row_id,
                            "source_role": role,
                            "source_snapshot_id": snapshot["snapshot_id"],
                            "api_name": "balancesheet_vip",
                            "instrument_id": instrument,
                            "provider_code": code,
                            "period": period,
                            "source_member_key": member_key,
                            "source_row_index": row_index,
                            "row": row,
                        }
                    )
                else:
                    extra_count += 1
                    extra_ids.append(row_id)
                    extra_codes.add(code)
                    extra_keys.add(("balancesheet_vip", code, period))
            leaves.append(
                {
                    "api_name": "balancesheet_vip",
                    "period": tree["period"],
                    "member_key": member_key,
                    "member_content_hash": members[member_key]["content_hash"],
                    "field_set_hash": _FIELD_SET_HASH,
                    "terminal_row_count": len(rows),
                    "selected_row_count": selected_count,
                    "extra_row_count": extra_count,
                }
            )
    records.sort(key=lambda value: (
        _dict(value["instrument_id"])["venue"], _dict(value["instrument_id"])["stable_key"], value["period"],
        value["source_role"], value["source_member_key"], value["source_row_index"], value["source_row_id"],
    ))
    selected_profile, economic, metadata = _classify_duplicate_rows(groups, canonical=True)
    all_profile, _, _ = _classify_duplicate_rows(all_groups, canonical=False)
    selected_keys = sorted(["balancesheet_vip", _instrument(code)["venue"], _instrument(code)["stable_key"], period] for code, period in groups)
    extra_key_values = [list(value) for value in sorted(extra_keys)]
    sh_sz = sorted(code for code in extra_codes if re.fullmatch(r"\d{6}\.(SZ|SH)", code))
    bj = sorted(code for code in extra_codes if re.fullmatch(r"\d{6}\.BJ", code))
    noncanonical = sorted(extra_codes - set(sh_sz) - set(bj))
    conflicts: list[dict[str, object]] = []
    for member_key_value in economic + metadata:
        instrument = _dict(member_key_value[1])
        code = str(instrument["stable_key"]) + (".SZ" if instrument["venue"] == "xshe" else ".SH")
        period = str(member_key_value[2])
        conflicts.append(
            {
                "member_key": member_key_value,
                "rows": [
                    {
                        "source_member_key": member_key,
                        "source_row_index": row_index,
                        "source_row_id": row_id,
                        "update_flag": row[-1],
                        "f_ann_date": row[2],
                    }
                    for member_key, row_index, row, row_id in groups[(code, period)]
                ],
            }
        )
    audit: dict[str, object] = {
        "source_role": role,
        "periods": sorted(periods),
        "root_tree_count": len(trees),
        "terminal_leaf_member_count": len(leaves),
        "terminal_leaf_members_hash": _canonical_hash(leaves),
        "terminal_source_row_count": len(all_ids),
        "terminal_source_row_ids_hash": _canonical_hash(all_ids),
        "selected_key_count": len(groups),
        "selected_row_count": len(records),
        "selected_revision_surplus_row_count": len(records) - len(groups),
        "selected_source_row_ids_hash": _canonical_hash([str(value["source_row_id"]) for value in records]),
        "selected_simple_keys_hash": _canonical_hash(selected_keys),
        "extra_source_row_count": len(extra_ids),
        "extra_source_row_ids_hash": _canonical_hash(extra_ids),
        "extra_source_key_count": len(extra_key_values),
        "extra_source_keys_hash": _canonical_hash(extra_key_values),
        "extra_provider_code_count": len(extra_codes),
        "extra_sh_sz_provider_code_count": len(sh_sz),
        "extra_sh_sz_provider_codes_hash": _canonical_hash(sh_sz),
        "extra_bj_provider_code_count": len(bj),
        "extra_bj_provider_codes_hash": _canonical_hash(bj),
        "extra_noncanonical_provider_code_count": len(noncanonical),
        "extra_noncanonical_provider_codes": noncanonical,
        "selected_duplicate_profile": selected_profile,
        "all_source_duplicate_profile": all_profile,
        "retained_revision_conflicts": conflicts,
    }
    keys = {("balancesheet_vip", _instrument(code)["venue"], _instrument(code)["stable_key"], period) for code, period in groups}
    return _PriorExtraction(records, [str(value["source_row_id"]) for value in records], keys, audit)


def _validate_prior_closure(
    requirements: _PriorRequirementSets,
    s2a: _PriorExtraction,
    stage_a: _PriorExtraction,
) -> tuple[list[dict[str, object]], list[str], set[tuple[str, str, str, str]]]:
    expected_s2a = {tuple(value) for value in _simple_keys(requirements.s2a)}
    expected_stage_a = {tuple(value) for value in _simple_keys(requirements.stage_a)}
    overlap = s2a.keys & stage_a.keys
    output_keys = s2a.keys | stage_a.keys
    expected = expected_s2a | expected_stage_a
    extra = output_keys - expected
    missing = expected - output_keys
    records = sorted(s2a.records + stage_a.records, key=lambda value: (
        _dict(value["instrument_id"])["venue"], _dict(value["instrument_id"])["stable_key"], value["period"],
        value["source_role"], value["source_member_key"], value["source_row_index"], value["source_row_id"],
    ))
    row_ids = [str(value["source_row_id"]) for value in records]
    payload_incomplete = output_keys == expected and len(records) != _EXPECTED_PROVIDER_ROWS
    exact_cover_failure = (
        "PAIR_DISPOSITION_CLOSURE_MISMATCH" if overlap else
        "STAGE_INPUT_SCOPE_MISMATCH" if extra else
        "EXPECTED_MEMBER_MISSING" if missing else
        None
    )
    if payload_incomplete:
        _fail(QualityBbandS1S2bPriorBalanceBindingFailure.FINANCIAL_PAYLOAD_INCOMPLETE, "PRIOR_BALANCE_ENDPOINT_MISSING")
    if exact_cover_failure is not None:
        _fail(QualityBbandS1S2bPriorBalanceBindingFailure.BUNDLE_EXACT_COVER_MISMATCH, exact_cover_failure)
    return records, row_ids, output_keys


def _file_identity(raw: bytes) -> dict[str, object]:
    return {"byte_count": len(raw), "sha256": _bytes_hash(raw)}


def _source_input(identity: _FrozenSourceIdentity, loaded: _LoadedSourceRoot, *, stage_a: bool) -> dict[str, object]:
    value: dict[str, object] = {
        "snapshot_type": loaded.snapshot_metadata["type"],
        "receipt_type": loaded.receipt["type"],
        "snapshot_id": identity.snapshot_id,
        "content_tree_hash": identity.content_tree_hash,
        "provenance_hash": identity.provenance_hash,
        "snapshot_member_count": identity.snapshot_member_count,
        "regular_file_count": identity.regular_file_count,
        "root_byte_count": identity.root_byte_count,
        "source_snapshot_file": {"byte_count": identity.snapshot_file.byte_count, "sha256": identity.snapshot_file.sha256},
        "acquisition_receipt_file": {"byte_count": identity.receipt_file.byte_count, "sha256": identity.receipt_file.sha256},
    }
    if stage_a:
        member = _dict(_list(loaded.snapshot_metadata["members"])[0])
        value["response_member"] = {"member_key": member["member_key"], "byte_count": member["byte_count"], "sha256": member["content_hash"]}
    value.update(
        {
            "request_hash": identity.request_hash,
            "provider_requests_hash": identity.provider_requests_hash,
            "root_tree_hash" if stage_a else "root_trees_hash": identity.root_trees_hash,
        }
    )
    return value


def _build_manifest(
    *, binding: dict[str, object], expected: dict[str, object], official: dict[str, object],
    extraction: dict[str, object], requirements: dict[str, object], requirements_raw: bytes,
    rows_raw: bytes, records: list[dict[str, object]], row_ids: list[str], output_keys: set[tuple[str, str, str, str]],
    s2a_source: _LoadedSourceRoot, stage_a_source: _LoadedSourceRoot,
    s2a_extraction: _PriorExtraction, stage_a_extraction: _PriorExtraction,
) -> dict[str, object]:
    s2a_audit = dict(s2a_extraction.audit)
    s2a_audit["legacy_s2b_row_schema_proof"] = {
        "byte_count": 1030659,
        "sha256": "sha256:704ada4176dbdd1d8f8f3f901651b57e13223c65ad3599a1f2e2d06928116f3c",
        "row_ids_hash": "sha256:cb0db295e029bfd3dc3bcf901c89ebcbd9c86d67de7f60e37c1f945689b5559e",
    }
    s2b_members = _dict(binding["preserved_s2b_members"])
    fields = _list(_dict(s2a_source.receipt["request"])["field_sets"]["balancesheet_vip"])  # type: ignore[index]
    s2a_profile = _dict(s2a_audit["selected_duplicate_profile"])
    stage_a_profile = _dict(stage_a_extraction.audit["selected_duplicate_profile"])
    s2a_economic = _integer(s2a_profile["economic_revision_conflict_key_count"])
    stage_a_economic = _integer(stage_a_profile["economic_revision_conflict_key_count"])
    s2a_metadata = _integer(s2a_profile["metadata_revision_only_duplicate_key_count"])
    stage_a_metadata = _integer(stage_a_profile["metadata_revision_only_duplicate_key_count"])
    s2a_update_only = _integer(s2a_profile["update_flag_only_duplicate_key_count"])
    stage_a_update_only = _integer(stage_a_profile["update_flag_only_duplicate_key_count"])
    s2a_single = _integer(s2a_profile["single_row_key_count"])
    stage_a_single = _integer(stage_a_profile["single_row_key_count"])
    body: dict[str, object] = {
        "type": "quality_bband_s1_s2b_prior_balance_binding_manifest",
        "schema_version": 1,
        "backtest_base_commit": _BASE_COMMIT,
        "inputs": {
            "stage_binding": {
                "artifact_type": binding["type"],
                "member_name": _STAGE_BINDING_FILE.name,
                "manifest_id": binding["manifest_id"],
                "byte_count": _STAGE_BINDING_FILE.byte_count,
                "sha256": _STAGE_BINDING_FILE.sha256,
            },
            "s2b": {
                "artifact_type": extraction["type"],
                "manifest_id": extraction["manifest_id"],
                "expected_set_id": expected["expected_set_id"],
                "official_coverage_id": official["official_coverage_id"],
                "regular_file_count": 4,
                "root_byte_count": 97030990,
                "members": s2b_members,
            },
            "accepted_s2a": _source_input(_S2A_IDENTITY, s2a_source, stage_a=False),
            "stage_a_2011": _source_input(_STAGE_A_IDENTITY, stage_a_source, stage_a=True),
        },
        "requirements_id": requirements["requirements_id"],
        "source_extractions": {
            "api_name": "balancesheet_vip",
            "fields": fields,
            "field_set_hash": _FIELD_SET_HASH,
            "row_identity_type": "quality_bband_prior_balance_source_row_identity",
            "provider_row_type": "quality_bband_prior_balance_provider_row",
            "provider_row_order": ["instrument_id.venue", "instrument_id.stable_key", "period", "source_role", "source_member_key", "source_row_index", "source_row_id"],
            "accepted_s2a": s2a_audit,
            "stage_a_2011": stage_a_extraction.audit,
            "combined": {
                "selected_key_count": len(output_keys),
                "selected_simple_keys_hash": _canonical_hash([list(value) for value in sorted(output_keys)]),
                "selected_row_count": len(records),
                "revision_surplus_row_count": len(records) - len(output_keys),
                "source_row_ids_hash": _canonical_hash(row_ids),
                "s2a_stage_a_key_overlap_count": len(s2a_extraction.keys & stage_a_extraction.keys),
            },
        },
        "closure": {
            "prior_endpoint_equation": "20797 = 17952 core + 850 accepted S2A + 1995 Stage A",
            "augmented_member_equation": "99382 = 96537 core + 2845 prior balance",
            "prior_endpoint_requirement_count": 20797,
            "existing_core_balance_reference_count": 17952,
            "existing_core_provider_reference_count": 17952,
            "existing_core_official_filing_reference_count": 0,
            "existing_core_official_nonfiling_reference_count": 0,
            "additive_requirement_count": 2845,
            "additive_provider_key_count": len(output_keys),
            "additive_provider_row_count": len(records),
            "missing_additive_key_count": 0,
            "extra_output_key_count": 0,
            "source_partition_overlap_key_count": 0,
            "source_partition_conflict_key_count": 0,
            "economic_revision_conflict_key_count": s2a_economic + stage_a_economic,
            "metadata_revision_only_duplicate_key_count": s2a_metadata + stage_a_metadata,
            "update_flag_only_duplicate_key_count": s2a_update_only + stage_a_update_only,
            "single_row_key_count": s2a_single + stage_a_single,
            "original_upstream_artifact_bytes_modified": False,
        },
        "preserved_s2b_members": s2b_members,
        "output_members": {
            "prior-balance-requirements.json": {
                "content_type": "application/json", "byte_count": len(requirements_raw),
                "sha256": _bytes_hash(requirements_raw), "schema_id": requirements["requirements_id"],
            },
            "prior-balance-provider-rows.jsonl": {
                "content_type": "application/x-ndjson", "byte_count": len(rows_raw),
                "sha256": _bytes_hash(rows_raw), "row_count": len(records),
                "row_ids_hash": _canonical_hash(row_ids),
            },
        },
        "flags": dict(_FLAGS),
        "limitations": list(_LIMITATIONS),
    }
    return {**body, "manifest_id": _canonical_hash(body)}


def _output_parent_components(output: Path) -> tuple[str, tuple[str, ...]]:
    if output.name in {"", ".", ".."}:
        raise ValueError("invalid output name")
    components = tuple(component for component in output.parent.parts if component not in {output.anchor, "", "."})
    if ".." in components:
        raise ValueError("output traversal forbidden")
    return ("/" if output.is_absolute() else "."), components


def _open_output_parent(output: Path, *, create: bool) -> int:
    anchor, components = _output_parent_components(output)
    flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(anchor, flags)
    try:
        for component in components:
            try:
                child = os.open(component, flags, dir_fd=descriptor)
            except FileNotFoundError:
                if not create:
                    raise
                created = False
                try:
                    os.mkdir(component, 0o700, dir_fd=descriptor)
                    created = True
                except FileExistsError:
                    pass
                child = os.open(component, flags, dir_fd=descriptor)
                if created:
                    os.fchmod(child, 0o700)
                    os.fsync(child)
                    os.fsync(descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _same_inode(left: os.stat_result, right: os.stat_result) -> bool:
    return (left.st_dev, left.st_ino) == (right.st_dev, right.st_ino)


def _verify_visible_output_parent(output: Path, identity: os.stat_result) -> None:
    descriptor = _open_output_parent(output, create=False)
    try:
        if not _same_inode(os.fstat(descriptor), identity):
            raise OSError("visible output parent changed")
    finally:
        os.close(descriptor)


def _rename_noreplace_at(parent_fd: int, source: str, target: str) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is None:
        raise OSError("renameat2 unavailable")
    renameat2.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    renameat2.restype = ctypes.c_int
    if renameat2(parent_fd, os.fsencode(source), parent_fd, os.fsencode(target), 1) != 0:
        number = ctypes.get_errno()
        raise OSError(number, os.strerror(number), target)


def _readback_matches(descriptor: int, content: bytes) -> bool:
    metadata = os.fstat(descriptor)
    os.lseek(descriptor, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    total = 0
    while total <= len(content):
        chunk = os.read(descriptor, len(content) - total + 1)
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
    return stat.S_ISREG(metadata.st_mode) and metadata.st_size == len(content) and total == len(content) and b"".join(chunks) == content


def _atomic_publish(output: Path, contents: dict[str, bytes], parent_fd: int) -> None:
    staging_name = f".{output.name}.staging-{os.getpid()}"
    staging_fd = -1
    member_fds: dict[str, int] = {}
    identities: dict[str, os.stat_result] = {}
    try:
        parent_identity = os.fstat(parent_fd)
        _verify_visible_output_parent(output, parent_identity)
        for name in (output.name, staging_name):
            try:
                os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise FileExistsError(name)
        os.mkdir(staging_name, 0o700, dir_fd=parent_fd)
        staging_identity = os.stat(staging_name, dir_fd=parent_fd, follow_symlinks=False)
        staging_fd = os.open(staging_name, os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0), dir_fd=parent_fd)
        if not _same_inode(os.fstat(staging_fd), staging_identity):
            raise OSError("staging directory changed")
        for name in _OUTPUT_FILES:
            content = contents[name]
            descriptor = os.open(name, os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600, dir_fd=staging_fd)
            member_fds[name] = descriptor
            offset = 0
            while offset < len(content):
                offset += os.write(descriptor, content[offset:])
            os.fchmod(descriptor, 0o600)
            os.fsync(descriptor)
            identities[name] = os.fstat(descriptor)
            if not _readback_matches(descriptor, content):
                raise OSError("staged member readback mismatch")
        os.fsync(staging_fd)
        if not _same_inode(os.stat(staging_name, dir_fd=parent_fd, follow_symlinks=False), staging_identity):
            raise OSError("staging pathname changed")
        for name in _OUTPUT_FILES:
            if not _same_inode(os.stat(name, dir_fd=staging_fd, follow_symlinks=False), identities[name]):
                raise OSError("staged member pathname changed")
        if set(os.listdir(staging_fd)) != set(_OUTPUT_FILES):
            raise OSError("staging member set mismatch")
        _rename_noreplace_at(parent_fd, staging_name, output.name)
        published_fd = os.open(output.name, os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0), dir_fd=parent_fd)
        try:
            if not _same_inode(os.fstat(published_fd), staging_identity):
                raise OSError("published directory changed")
            if set(os.listdir(published_fd)) != set(_OUTPUT_FILES):
                raise OSError("published member set mismatch")
            for name in _OUTPUT_FILES:
                descriptor = os.open(name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=published_fd)
                try:
                    if not _same_inode(os.fstat(descriptor), identities[name]) or not _readback_matches(descriptor, contents[name]):
                        raise OSError("published member mismatch")
                finally:
                    os.close(descriptor)
            if set(os.listdir(published_fd)) != set(_OUTPUT_FILES):
                raise OSError("published member set changed")
        finally:
            os.close(published_fd)
        os.fsync(parent_fd)
        _verify_visible_output_parent(output, parent_identity)
    except (FileExistsError, OSError, ValueError) as error:
        try:
            os.fsync(parent_fd)
        except OSError:
            pass
        raise QualityBbandS1S2bPriorBalanceBindingError(QualityBbandS1S2bPriorBalanceBindingFailure.PUBLICATION_INTEGRITY_FAILURE) from error
    finally:
        for descriptor in member_fds.values():
            os.close(descriptor)
        if staging_fd >= 0:
            os.close(staging_fd)


def _preflight(paths: tuple[Path, Path, Path, Path, Path]) -> int:
    if any(not isinstance(path, Path) for path in paths):
        _fail(QualityBbandS1S2bPriorBalanceBindingFailure.INPUT_TYPE_MISMATCH)
    stage_binding_root, s2b_root, s2a_root, stage_a_root, output = paths
    roots = (stage_binding_root, s2b_root, s2a_root, stage_a_root)
    parent_fd = -1
    try:
        resolved_output = output.resolve(strict=False)
        resolved_roots: list[Path] = []
        for root in roots:
            if root.is_symlink() or not root.is_dir():
                raise ValueError("unsafe input root")
            resolved = root.resolve(strict=True)
            resolved_roots.append(resolved)
            if resolved_output == resolved or resolved in resolved_output.parents:
                raise ValueError("output inside input root")
        if len(set(resolved_roots)) != 4:
            raise ValueError("input roots must be distinct")
        parent_fd = _open_output_parent(output, create=True)
        identity = os.fstat(parent_fd)
        try:
            os.stat(output.name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise ValueError("output exists")
        _verify_visible_output_parent(output, identity)
        return parent_fd
    except (OSError, ValueError) as error:
        if parent_fd >= 0:
            os.close(parent_fd)
        raise QualityBbandS1S2bPriorBalanceBindingError(QualityBbandS1S2bPriorBalanceBindingFailure.INPUT_TYPE_MISMATCH) from error


def _build_preflighted(
    *, stage_binding_root: Path, s2b_root: Path, s2a_root: Path, stage_a_root: Path,
    output_dir: Path, output_parent_fd: int,
) -> dict[str, object]:
    loaded: dict[str, object] = {}
    errors: list[QualityBbandS1S2bPriorBalanceBindingError] = []
    loaders = (
        ("binding", lambda: _load_stage_binding(stage_binding_root), QualityBbandS1S2bPriorBalanceBindingFailure.CATALOG_IDENTITY_MISMATCH),
        ("s2b", lambda: _load_s2b(s2b_root), QualityBbandS1S2bPriorBalanceBindingFailure.CATALOG_IDENTITY_MISMATCH),
        ("s2a", lambda: _load_source_root(s2a_root, _S2A_IDENTITY), QualityBbandS1S2bPriorBalanceBindingFailure.CATALOG_IDENTITY_MISMATCH),
        ("stage_a", lambda: _load_source_root(stage_a_root, _STAGE_A_IDENTITY), QualityBbandS1S2bPriorBalanceBindingFailure.CATALOG_IDENTITY_MISMATCH),
    )
    for name, loader, failure in loaders:
        try:
            loaded[name] = loader()
        except QualityBbandS1S2bPriorBalanceBindingError as error:
            errors.append(error)
        except (KeyError, OSError, TypeError, ValueError) as error:
            errors.append(QualityBbandS1S2bPriorBalanceBindingError(failure))
    if errors:
        order = list(QualityBbandS1S2bPriorBalanceBindingFailure)
        raise min(errors, key=lambda error: order.index(error.code))
    binding = loaded["binding"]
    expected, official, extraction, _members = loaded["s2b"]  # type: ignore[misc]
    s2a_source = loaded["s2a"]
    stage_a_source = loaded["stage_a"]
    assert isinstance(binding, dict) and isinstance(s2a_source, _LoadedSourceRoot) and isinstance(stage_a_source, _LoadedSourceRoot)
    try:
        _validate_upstream_authority(binding, expected, official, extraction)
    except (KeyError, TypeError, ValueError) as error:
        raise QualityBbandS1S2bPriorBalanceBindingError(QualityBbandS1S2bPriorBalanceBindingFailure.FINANCIAL_REVISION_MISMATCH) from error
    requirements_sets = _derive_prior_requirements(expected)
    requirements = _build_requirements(binding, expected, requirements_sets)
    requirements_raw = _canonical_json(requirements).encode("utf-8")
    if (
        requirements["requirements_id"] != _EXPECTED_REQUIREMENTS_ID
        or len(requirements_raw) != _EXPECTED_REQUIREMENTS_SIZE
        or _bytes_hash(requirements_raw) != _EXPECTED_REQUIREMENTS_HASH
    ):
        _fail(QualityBbandS1S2bPriorBalanceBindingFailure.BUNDLE_EXACT_COVER_MISMATCH, "PAIR_DISPOSITION_CLOSURE_MISMATCH")
    try:
        s2a_extraction = _extract_prior_rows(s2a_source, "ACCEPTED_S2A", requirements_sets.s2a, {str(value["period"]) for value in requirements_sets.s2a})
        stage_a_extraction = _extract_prior_rows(stage_a_source, "STAGE_A_2011", requirements_sets.stage_a, {"20111231"})
    except (KeyError, TypeError, ValueError) as error:
        raise QualityBbandS1S2bPriorBalanceBindingError(QualityBbandS1S2bPriorBalanceBindingFailure.FINANCIAL_REVISION_MISMATCH) from error
    records, row_ids, output_keys = _validate_prior_closure(requirements_sets, s2a_extraction, stage_a_extraction)
    rows_raw = b"".join(_canonical_json(value).encode("utf-8") + b"\n" for value in records)
    if (
        len(records) != _EXPECTED_PROVIDER_ROWS
        or _canonical_hash(row_ids) != _EXPECTED_PROVIDER_ROW_IDS_HASH
        or len(rows_raw) != _EXPECTED_PROVIDER_ROWS_SIZE
        or _bytes_hash(rows_raw) != _EXPECTED_PROVIDER_ROWS_HASH
    ):
        _fail(QualityBbandS1S2bPriorBalanceBindingFailure.FINANCIAL_PAYLOAD_INCOMPLETE)
    manifest = _build_manifest(
        binding=binding, expected=expected, official=official, extraction=extraction,
        requirements=requirements, requirements_raw=requirements_raw, rows_raw=rows_raw,
        records=records, row_ids=row_ids, output_keys=output_keys, s2a_source=s2a_source,
        stage_a_source=stage_a_source, s2a_extraction=s2a_extraction,
        stage_a_extraction=stage_a_extraction,
    )
    manifest_raw = _canonical_json(manifest).encode("utf-8")
    if (
        manifest["manifest_id"] != _EXPECTED_MANIFEST_ID
        or len(manifest_raw) != _EXPECTED_MANIFEST_SIZE
        or _bytes_hash(manifest_raw) != _EXPECTED_MANIFEST_HASH
    ):
        _fail(QualityBbandS1S2bPriorBalanceBindingFailure.BUNDLE_EXACT_COVER_MISMATCH, "PAIR_DISPOSITION_CLOSURE_MISMATCH")
    _atomic_publish(
        output_dir,
        {
            _OUTPUT_FILES[0]: requirements_raw,
            _OUTPUT_FILES[1]: rows_raw,
            _OUTPUT_FILES[2]: manifest_raw,
        },
        output_parent_fd,
    )
    return manifest


def build_quality_bband_s1_s2b_prior_balance_binding_v1(
    *,
    stage_binding_root: Path,
    s2b_root: Path,
    s2a_root: Path,
    stage_a_root: Path,
    output_dir: Path,
) -> dict[str, object]:
    parent_fd = _preflight((stage_binding_root, s2b_root, s2a_root, stage_a_root, output_dir))
    try:
        return _build_preflighted(
            stage_binding_root=stage_binding_root,
            s2b_root=s2b_root,
            s2a_root=s2a_root,
            stage_a_root=stage_a_root,
            output_dir=output_dir,
            output_parent_fd=parent_fd,
        )
    finally:
        os.close(parent_fd)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bind all prior balance revisions to accepted quality-bband S1/S2B")
    parser.add_argument("--stage-binding-root", type=Path, required=True)
    parser.add_argument("--s2b-root", type=Path, required=True)
    parser.add_argument("--s2a-root", type=Path, required=True)
    parser.add_argument("--stage-a-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        manifest = build_quality_bband_s1_s2b_prior_balance_binding_v1(
            stage_binding_root=args.stage_binding_root,
            s2b_root=args.s2b_root,
            s2a_root=args.s2a_root,
            stage_a_root=args.stage_a_root,
            output_dir=args.output_dir,
        )
    except QualityBbandS1S2bPriorBalanceBindingError as error:
        print(str(error))
        return 1
    print(manifest["manifest_id"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
