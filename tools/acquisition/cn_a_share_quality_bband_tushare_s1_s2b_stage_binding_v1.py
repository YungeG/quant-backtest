from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import math
import os
import stat
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import NoReturn

_BASE_COMMIT = "0d373b71b263a53b6b00e50b26ae1508dcfc986f"
_OUTPUT_NAME = "stage-binding-manifest.json"
_EXPECTED_OUTPUT_SIZE = 7323
_EXPECTED_OUTPUT_HASH = "sha256:ba5abfc5fc592ceb88ce1cabc95ebbded24abe9a8b108e9f6a31c96a0cc0878c"
_EXPECTED_MANIFEST_ID = "sha256:c54bac9818a24688699aa585e49e91bde64ddbaf3efa90e0aa18491ff9b86f5c"
_EXPECTED_SET_ID = "sha256:8c679397ff7ecfe67e0bbf68951d9fa388de9f2adfaf53a4f8b5395b0cea2cf6"
_OFFICIAL_COVERAGE_ID = "sha256:f245ebd560bb15644b1b072d277d3847d3477e7125677bd2e683e5a7c0636907"
_OWNER_DECISION_ID = "sha256:629748197e0606baeff184a6eece576a2e7660cf5363d76d10a4e5577af6e1ed"
_PACKET_BODY_HASH = "sha256:aeb8ac2b5aa8a97c5cf04140ff4a12a0c45854ee8ea34c19a8a89792676006bb"
_PROVIDER_ROW_IDS_HASH = "sha256:04e8a893976e36fbdf3a186ea42d51897e03f09d6f849337a214d87f86c531c6"
_O_KEYS_HASH = "sha256:2b053ca7962d49a950bf22bed1f2ec6906b0f7223fc76cc20de2d3b28c045853"
_N_KEYS_HASH = "sha256:a68c15fe52bbea92d0049092843efd339dffe6b3bd52266e537fa5e4fb8e9534"
_API_ORDER = ("income_vip", "balancesheet_vip", "cashflow_vip")
_SOURCE_FIELDS = (
    "snapshot_id",
    "content_tree_hash",
    "provenance_hash",
    "snapshot_file_sha256",
    "receipt_file_sha256",
)
_HASHES = {
    "screen_membership_hash": "sha256:00b6f4487ffd946ca1db05a4fc353f45ba9da235cc954e1248902da3103a8f2b",
    "period_requirements_hash": "sha256:87f0ad15a76bc01561e0347f59a720e26b657829198774bf14893df7ef4fe846",
    "instrument_union_hash": "sha256:25d69f75295afe13549269e96d9fbeb726605ac5c93e78d9cfe46ecf48f30ab0",
    "expected_pairs_hash": "sha256:336efc4e947062036b1c98add7977653c48abdab8f33350516626a521b9b2b3e",
    "expected_member_keys_hash": "sha256:0269e22c9f45b24b827e98a91515ac31ae5486ba0fda668f69112400b088e44b",
}
_EXPECTED_COUNTS = {
    "screen_count": 9,
    "instrument_union_count": 2845,
    "expected_pair_count": 32179,
    "expected_member_count": 96537,
}
_SCREEN_COUNTS = {
    "20170502": 1995,
    "20180502": 2034,
    "20190506": 2053,
    "20200506": 2143,
    "20210506": 2224,
    "20220505": 2434,
    "20230504": 2612,
    "20240506": 2635,
    "20250506": 2667,
}
_SCREEN_HASHES = {
    "20170502": "sha256:277ce5c25c287d4166a3554bf7490c79e51862ac691ac493c54a77936d9ebb46",
    "20180502": "sha256:dbca60e545b16185960fcbfd3df0a2803137a7f2202314f0f47bba5411d38e0e",
    "20190506": "sha256:0e9ac5081536642836f53772ec5b787598646ec486e56911a1c37c8406b1958f",
    "20200506": "sha256:515a898727f5529afe2141c9608385c1c06346a2286745cd9d2f70f8dc6e57b9",
    "20210506": "sha256:b01fd4be16bb3b347d08b3703c9a24893ad725daa0d8e553b4d7db9af61d8ebc",
    "20220505": "sha256:80b2040da451c5810f2c13cb4cad561b1db2ecf0f47d9be1aa35ae0622bfa256",
    "20230504": "sha256:ec803daa73eae7205ef943cf907840501f054e25d0bb754331fa81702fb206f3",
    "20240506": "sha256:0767557ede35189e731c1695d94cb44d1d4bf32575854e155671d82130f7b034",
    "20250506": "sha256:5a0686e15872eeae6e569f3254aebb1504aa2ddafba7da0914c51520ab694036",
}
_LIMITATIONS = sorted((
    "FINANCIAL_PAYLOAD_AND_SCOPE_NOT_QUALIFIED",
    "FORMAL_S2_FALSE",
    "NO_STRATEGY_BACKTEST_VALIDATION_OR_DEPLOYMENT_AUTHORITY",
    "OFFICIAL_CSRC_INDUSTRY_AUTHORITY_FALSE",
    "OFFICIAL_EXCHANGE_AUTHORITY_FALSE",
    "ORIGINAL_S1_AND_S2B_ARTIFACT_BYTES_UNCHANGED",
    "OWNER_APPROVED_TUSHARE_SCOPE_ONLY",
    "STAGE_BINDING_REPLACES_INPUT_AUTHORITY_CLASSIFICATION_ONLY",
    "SURVIVORSHIP_SAFETY_BEYOND_TUSHARE_SCOPE_FALSE",
))
_FLAGS = {
    "owner_approved_tushare_authority": True,
    "formal_s1_qualified": True,
    "provider_scope_exact": True,
    "s2b_exact_cover_complete": True,
    "formal_s2_qualified": False,
    "financial_payload_complete": False,
    "financial_scope_qualified": False,
    "official_exchange_authority": False,
    "official_csrc_industry_authority": False,
    "market_truth_completeness_claimed": False,
    "survivorship_bias_safe_beyond_tushare_scope": False,
    "decision_grade_eligible": False,
    "strategy_authorized": False,
    "strategy_target_authorized": False,
    "backtest_authorized": False,
    "validation_authorized": False,
    "deployment_authorized": False,
}


class QualityBbandTushareS1S2bBindingFailure(str, Enum):
    INPUT_TYPE_SCHEMA_OR_PATH = "INPUT_TYPE_SCHEMA_OR_PATH"
    ARTIFACT_IDENTITY_MISMATCH = "ARTIFACT_IDENTITY_MISMATCH"
    AUTHORITY_REBINDING_MISMATCH = "AUTHORITY_REBINDING_MISMATCH"
    SHARED_SOURCE_BINDING_MISMATCH = "SHARED_SOURCE_BINDING_MISMATCH"
    EXPECTED_SET_EQUIVALENCE_MISMATCH = "EXPECTED_SET_EQUIVALENCE_MISMATCH"
    S2B_CLOSURE_OR_PAYLOAD_MISMATCH = "S2B_CLOSURE_OR_PAYLOAD_MISMATCH"
    FROZEN_OUTPUT_MISMATCH = "FROZEN_OUTPUT_MISMATCH"
    PUBLICATION_INTEGRITY_FAILURE = "PUBLICATION_INTEGRITY_FAILURE"


class _ArtifactIdentityMismatch(ValueError):
    pass


class QualityBbandTushareS1S2bBindingError(RuntimeError):
    def __init__(self, code: QualityBbandTushareS1S2bBindingFailure) -> None:
        if type(code) is not QualityBbandTushareS1S2bBindingFailure:
            raise TypeError("code must be a Tushare S1/S2B binding failure")
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class _FrozenFile:
    name: str
    byte_count: int
    sha256: str


@dataclass(frozen=True, slots=True)
class _ReadMember:
    raw: bytes | None
    byte_count: int
    sha256: str


_S1_FILE = _FrozenFile(
    "tushare-s1-structural-manifest.json",
    40104662,
    "sha256:c8f96831bd68cc1a46a291c59c5c97e10ce0c31eba54e53d9be8929366dfd059",
)
_S2B_FILES = {
    value.name: value
    for value in (
        _FrozenFile(
            "provisional-expected-set.json",
            6587372,
            "sha256:55c4ecdee60e77feec3d2ee8c4d8da5b16a4e6a1e07bf2acc49a08669b8d1a29",
        ),
        _FrozenFile(
            "provider-rows.jsonl",
            90363445,
            "sha256:f4ed00c232930e1067c2796f7e5c3622397e8649e1afa0d5ae8730c964cf7abe",
        ),
        _FrozenFile(
            "official-coverage.json",
            17755,
            "sha256:a0971482128b6e4e2f0bcdbdbb10f1102211974fd98157c0185ec25fc08e5b3b",
        ),
        _FrozenFile(
            "extraction-manifest.json",
            62418,
            "sha256:74c60758f4b6eb9534900f868bdef444e5891ad6b4eee996e6713eb2e8ea876f",
        ),
    )
}
_S1_TOP_LEVEL = {
    "backtest_base_commit", "broad_catalog", "broad_catalog_hash", "counts",
    "expected_member_keys", "expected_pairs", "flags", "hashes", "inputs",
    "instrument_union", "limitations", "manifest_id", "owner_decision_id",
    "packet_body_hash", "period_requirements", "schema_version", "screen_dates",
    "screens", "source_extras", "type",
}
_EXPECTED_TOP_LEVEL = {
    "annual_roster_source_snapshot_id", "authority_level", "derivation",
    "expected_member_count", "expected_member_keys_hash", "expected_pair_count",
    "expected_pairs", "expected_pairs_hash", "expected_set_id", "formal_s1_qualified",
    "instrument_union_count", "instrument_union_hash", "period_requirements",
    "period_requirements_hash", "s0_source_snapshot_id", "schema_version",
    "screen_count", "screen_membership_hash", "screens", "type",
}
_OFFICIAL_TOP_LEVEL = {
    "n_member_count", "n_member_keys", "nonfiling_declarations",
    "nonfiling_publication_ref", "o_member_count", "o_member_keys",
    "official_coverage_id", "pan_hai_backfill", "schema_version", "type",
}
_EXTRACTION_TOP_LEVEL = {
    "accounting", "backtest_authorized", "closure_equation", "decision_grade_eligible",
    "deployment_authorized", "expected_set_id", "financial_payload_complete",
    "financial_scope_qualified", "formal_s1_qualified", "formal_s2_qualified",
    "inputs", "limitations", "manifest_id", "official_coverage_id", "output_members",
    "provisional_exact_cover_complete", "provisional_expected_scope_extracted",
    "schema_version", "source_scan", "strategy_authorized",
    "strategy_target_authorized", "type", "validation_authorized",
}


def _fail(code: QualityBbandTushareS1S2bBindingFailure) -> NoReturn:
    raise QualityBbandTushareS1S2bBindingError(code)


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


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
    if keys is not None and set(value) != keys:
        raise ValueError("JSON object schema mismatch")
    return value


def _list(value: object) -> list[object]:
    if type(value) is not list:
        raise TypeError("expected exact JSON array")
    return value


def _read_exact_member(root_fd: int, frozen: _FrozenFile, *, keep_bytes: bool) -> _ReadMember:
    descriptor = os.open(
        frozen.name,
        os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
        dir_fd=root_fd,
    )
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError("member is not a regular file")
        if metadata.st_size != frozen.byte_count:
            raise _ArtifactIdentityMismatch("member exact byte count mismatch")
        digest = hashlib.sha256()
        chunks: list[bytes] | None = [] if keep_bytes else None
        total = 0
        while True:
            chunk = os.read(descriptor, min(1 << 20, frozen.byte_count - total + 1))
            if not chunk:
                break
            total += len(chunk)
            if total > frozen.byte_count:
                raise _ArtifactIdentityMismatch("member exceeds exact size")
            digest.update(chunk)
            if chunks is not None:
                chunks.append(chunk)
        if total != frozen.byte_count:
            raise _ArtifactIdentityMismatch("member changed during read")
        return _ReadMember(
            None if chunks is None else b"".join(chunks),
            total,
            "sha256:" + digest.hexdigest(),
        )
    finally:
        os.close(descriptor)


def _open_exact_root(root: Path, names: set[str]) -> int:
    descriptor = os.open(
        root,
        os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        if not stat.S_ISDIR(os.fstat(descriptor).st_mode) or set(os.listdir(descriptor)) != names:
            raise ValueError("root member set mismatch")
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _body_id(value: dict[str, object], id_name: str) -> str:
    body = dict(value)
    identifier = body.pop(id_name, None)
    if type(identifier) is not str:
        raise ValueError("missing body identity")
    return identifier if identifier == _canonical_hash(body) else ""


def _validate_instrument(value: object) -> dict[str, object]:
    instrument = _dict(value, keys={"type", "venue", "stable_key"})
    if (
        instrument["type"] != "instrument_id"
        or instrument["venue"] not in {"xshe", "xshg"}
        or type(instrument["stable_key"]) is not str
        or len(instrument["stable_key"]) != 6
        or not str(instrument["stable_key"]).isdigit()
    ):
        raise ValueError("instrument schema mismatch")
    return instrument


def _validate_pair_schema(value: object) -> dict[str, object]:
    pair = _dict(value, keys={"instrument_id", "period", "required_by_screen_dates"})
    _validate_instrument(pair["instrument_id"])
    if type(pair["period"]) is not str or type(pair["required_by_screen_dates"]) is not list:
        raise ValueError("pair schema mismatch")
    return pair


def _load_s1(root: Path) -> tuple[dict[str, object], _ReadMember]:
    root_fd = _open_exact_root(root, {_S1_FILE.name})
    try:
        member = _read_exact_member(root_fd, _S1_FILE, keep_bytes=True)
    finally:
        os.close(root_fd)
    assert member.raw is not None
    manifest = _dict(_strict_json(member.raw), keys=_S1_TOP_LEVEL)
    if (
        manifest["type"] != "quality_bband_tushare_s1_structural_manifest"
        or manifest["schema_version"] != 1
    ):
        raise ValueError("S1 schema mismatch")
    inputs = _dict(manifest["inputs"], keys={"s0", "annual_roster"})
    for name in ("s0", "annual_roster"):
        binding = _dict(inputs[name])
        if not set(_SOURCE_FIELDS) <= set(binding):
            raise ValueError("S1 source binding schema mismatch")
    screens = _list(manifest["screens"])
    for screen in screens:
        value = _dict(screen)
        if not {"screen_date", "eligible_instrument_ids", "eligible_count", "eligible_instrument_ids_hash"} <= set(value):
            raise ValueError("S1 screen schema mismatch")
        for instrument in _list(value["eligible_instrument_ids"]):
            _validate_instrument(instrument)
    for value in _list(manifest["instrument_union"]):
        _validate_instrument(value)
    for value in _list(manifest["expected_pairs"]):
        _validate_pair_schema(value)
    _member_key_set(manifest["expected_member_keys"])
    for requirement in _list(manifest["period_requirements"]):
        value = _dict(requirement, keys={"screen_date", "periods"})
        if type(value["screen_date"]) is not str or any(type(period) is not str for period in _list(value["periods"])):
            raise ValueError("period requirement schema mismatch")
    _dict(manifest["counts"])
    _dict(manifest["hashes"])
    _dict(manifest["flags"])
    for name in ("manifest_id", "owner_decision_id", "packet_body_hash"):
        if type(manifest[name]) is not str:
            raise ValueError(f"{name} schema mismatch")
    return manifest, member


def _parse_expected_set(raw: bytes) -> dict[str, object]:
    expected = _dict(_strict_json(raw), keys=_EXPECTED_TOP_LEVEL)
    if (
        expected["type"] != "quality_bband_s2b_provisional_expected_set"
        or expected["schema_version"] != 1
    ):
        raise ValueError("S2B expected-set schema mismatch")
    derivation = _dict(expected["derivation"])
    if any(type(api_name) is not str for api_name in _list(derivation["api_order"])):
        raise ValueError("API order schema mismatch")
    for screen in _list(expected["screens"]):
        value = _dict(screen, keys={"screen_date", "instrument_ids"})
        for instrument in _list(value["instrument_ids"]):
            _validate_instrument(instrument)
    for pair in _list(expected["expected_pairs"]):
        _validate_pair_schema(pair)
    for requirement in _list(expected["period_requirements"]):
        value = _dict(requirement, keys={"screen_date", "periods"})
        if type(value["screen_date"]) is not str or any(
            type(period) is not str for period in _list(value["periods"])
        ):
            raise ValueError("period requirement schema mismatch")
    if type(expected["expected_set_id"]) is not str:
        raise ValueError("expected_set_id schema mismatch")
    return expected


def _parse_official_coverage(raw: bytes) -> dict[str, object]:
    official = _dict(_strict_json(raw), keys=_OFFICIAL_TOP_LEVEL)
    if (
        official["type"] != "quality_bband_s2b_official_coverage"
        or official["schema_version"] != 1
    ):
        raise ValueError("S2B official-coverage schema mismatch")
    _member_key_set(official["o_member_keys"])
    _member_key_set(official["n_member_keys"])
    if type(official["official_coverage_id"]) is not str:
        raise ValueError("official_coverage_id schema mismatch")
    return official


def _parse_extraction_manifest(raw: bytes) -> dict[str, object]:
    extraction = _dict(_strict_json(raw), keys=_EXTRACTION_TOP_LEVEL)
    if (
        extraction["type"] != "quality_bband_s2b_provisional_exact_extraction_manifest"
        or extraction["schema_version"] != 1
    ):
        raise ValueError("S2B extraction schema mismatch")
    extraction_inputs = _dict(extraction["inputs"])
    for name in ("s0", "annual_roster"):
        binding = _dict(extraction_inputs[name])
        if set(binding) != set(_SOURCE_FIELDS):
            raise ValueError("S2B source binding schema mismatch")
    _dict(extraction["accounting"])
    _dict(extraction["output_members"])
    _list(extraction["limitations"])
    if type(extraction["manifest_id"]) is not str:
        raise ValueError("manifest_id schema mismatch")
    return extraction


def _load_s2b(root: Path) -> tuple[dict[str, object], dict[str, object], dict[str, object], dict[str, _ReadMember]]:
    root_fd = _open_exact_root(root, set(_S2B_FILES))
    members: dict[str, _ReadMember] = {}
    input_error: BaseException | None = None
    identity_error: BaseException | None = None
    try:
        for name, frozen in _S2B_FILES.items():
            try:
                members[name] = _read_exact_member(
                    root_fd,
                    frozen,
                    keep_bytes=name != "provider-rows.jsonl",
                )
            except _ArtifactIdentityMismatch as error:
                identity_error = identity_error or error
            except (OSError, TypeError, ValueError) as error:
                input_error = input_error or error
    finally:
        os.close(root_fd)
    parsed: dict[str, dict[str, object]] = {}
    parsers = {
        "provisional-expected-set.json": _parse_expected_set,
        "official-coverage.json": _parse_official_coverage,
        "extraction-manifest.json": _parse_extraction_manifest,
    }
    for name, parser in parsers.items():
        member = members.get(name)
        if member is None or member.raw is None:
            continue
        try:
            parsed[name] = parser(member.raw)
        except (KeyError, TypeError, ValueError) as error:
            input_error = input_error or error
    if input_error is not None:
        raise input_error
    if identity_error is not None:
        raise identity_error
    expected = parsed["provisional-expected-set.json"]
    official = parsed["official-coverage.json"]
    extraction = parsed["extraction-manifest.json"]
    return expected, official, extraction, members


def _validate_artifact_identities(
    s1: dict[str, object],
    s1_member: _ReadMember,
    expected: dict[str, object],
    official: dict[str, object],
    extraction: dict[str, object],
    s2b_members: dict[str, _ReadMember],
) -> None:
    if (
        s1_member.sha256 != _S1_FILE.sha256
        or _body_id(s1, "manifest_id") != s1["manifest_id"]
        or s1["manifest_id"] != "sha256:dcd0fecbfca29ce090b53462f3972174d4977116e52472309055b4110046df85"
        or s1["owner_decision_id"] != _OWNER_DECISION_ID
        or s1["packet_body_hash"] != _PACKET_BODY_HASH
        or expected["expected_set_id"] != _EXPECTED_SET_ID
        or _body_id(expected, "expected_set_id") != expected["expected_set_id"]
        or official["official_coverage_id"] != _OFFICIAL_COVERAGE_ID
        or _body_id(official, "official_coverage_id") != official["official_coverage_id"]
        or extraction["manifest_id"] != "sha256:e526416335016b9fd421e138655303673e76dc2bf6e2f53a6bb580904ed70d74"
        or _body_id(extraction, "manifest_id") != extraction["manifest_id"]
        or extraction["expected_set_id"] != _EXPECTED_SET_ID
        or extraction["official_coverage_id"] != _OFFICIAL_COVERAGE_ID
        or any(
            member.byte_count != frozen.byte_count or member.sha256 != frozen.sha256
            for name, frozen in _S2B_FILES.items()
            for member in (s2b_members[name],)
        )
    ):
        _fail(QualityBbandTushareS1S2bBindingFailure.ARTIFACT_IDENTITY_MISMATCH)


def _validate_authority(s1: dict[str, object], expected: dict[str, object], extraction: dict[str, object]) -> None:
    s1_flags = _dict(s1["flags"])
    if (
        s1_flags.get("owner_approved_tushare_authority") is not True
        or s1_flags.get("formal_s1_qualified") is not True
        or expected["authority_level"] != "SOURCE_BOUNDED_PROVISIONAL"
        or expected["formal_s1_qualified"] is not False
        or extraction["formal_s1_qualified"] is not False
        or "FORMAL_S1_FALSE" not in _list(extraction["limitations"])
    ):
        _fail(QualityBbandTushareS1S2bBindingFailure.AUTHORITY_REBINDING_MISMATCH)


def _source_binding(value: object) -> dict[str, object]:
    binding = _dict(value)
    return {name: binding.get(name) for name in _SOURCE_FIELDS}


def _validate_shared_sources(s1: dict[str, object], extraction: dict[str, object]) -> None:
    s1_inputs = _dict(s1["inputs"])
    s2b_inputs = _dict(extraction["inputs"])
    if any(
        _source_binding(s1_inputs[name]) != _source_binding(s2b_inputs.get(name))
        for name in ("s0", "annual_roster")
    ):
        _fail(QualityBbandTushareS1S2bBindingFailure.SHARED_SOURCE_BINDING_MISMATCH)


def _derive_s2b_instrument_union(screens: list[object]) -> list[dict[str, object]]:
    union: dict[tuple[str, str], dict[str, object]] = {}
    for screen in screens:
        for value in _list(_dict(screen)["instrument_ids"]):
            instrument = _validate_instrument(value)
            union[(str(instrument["venue"]), str(instrument["stable_key"]))] = instrument
    return [union[key] for key in sorted(union)]


def _derive_s2b_member_keys(expected: dict[str, object]) -> list[list[object]]:
    api_order = _list(_dict(expected["derivation"])["api_order"])
    pairs = _list(expected["expected_pairs"])
    return [
        [api_name, _dict(pair)["instrument_id"], _dict(pair)["period"]]
        for api_name in api_order
        for pair in pairs
    ]


def _validate_equivalence(s1: dict[str, object], expected: dict[str, object]) -> None:
    s1_screens = _list(s1["screens"])
    s2b_screens = _list(expected["screens"])
    s1_membership = [
        {"screen_date": _dict(screen)["screen_date"], "instrument_ids": _dict(screen)["eligible_instrument_ids"]}
        for screen in s1_screens
    ]
    s2b_union = _derive_s2b_instrument_union(s2b_screens)
    s2b_member_keys = _derive_s2b_member_keys(expected)
    calculated_screen_hashes = {
        str(_dict(screen)["screen_date"]): _canonical_hash(_dict(screen)["eligible_instrument_ids"])
        for screen in s1_screens
    }
    s1_hashes = _dict(s1["hashes"])
    s1_counts = _dict(s1["counts"])
    if (
        s1_membership != s2b_screens
        or s1["period_requirements"] != expected["period_requirements"]
        or s1["instrument_union"] != s2b_union
        or s1["expected_pairs"] != expected["expected_pairs"]
        or s1["expected_member_keys"] != s2b_member_keys
        or tuple(_list(_dict(expected["derivation"])["api_order"])) != _API_ORDER
        or len(s1_screens) != _EXPECTED_COUNTS["screen_count"]
        or expected["screen_count"] != _EXPECTED_COUNTS["screen_count"]
        or len(s2b_union) != _EXPECTED_COUNTS["instrument_union_count"]
        or expected["instrument_union_count"] != _EXPECTED_COUNTS["instrument_union_count"]
        or len(_list(expected["expected_pairs"])) != _EXPECTED_COUNTS["expected_pair_count"]
        or expected["expected_pair_count"] != _EXPECTED_COUNTS["expected_pair_count"]
        or len(s2b_member_keys) != _EXPECTED_COUNTS["expected_member_count"]
        or expected["expected_member_count"] != _EXPECTED_COUNTS["expected_member_count"]
        or s1_counts.get("screen_count") != _EXPECTED_COUNTS["screen_count"]
        or s1_counts.get("instrument_union_count") != _EXPECTED_COUNTS["instrument_union_count"]
        or s1_counts.get("expected_pair_count") != _EXPECTED_COUNTS["expected_pair_count"]
        or s1_counts.get("expected_member_key_count") != _EXPECTED_COUNTS["expected_member_count"]
        or {
            str(_dict(screen)["screen_date"]): len(_list(_dict(screen)["eligible_instrument_ids"]))
            for screen in s1_screens
        } != _SCREEN_COUNTS
        or calculated_screen_hashes != _SCREEN_HASHES
        or any(s1_hashes.get(name) != digest or expected.get(name) != digest for name, digest in _HASHES.items())
        or _canonical_hash(s1_membership) != _HASHES["screen_membership_hash"]
        or _canonical_hash(expected["period_requirements"]) != _HASHES["period_requirements_hash"]
        or _canonical_hash(s2b_union) != _HASHES["instrument_union_hash"]
        or _canonical_hash(expected["expected_pairs"]) != _HASHES["expected_pairs_hash"]
        or _canonical_hash(s2b_member_keys) != _HASHES["expected_member_keys_hash"]
    ):
        _fail(QualityBbandTushareS1S2bBindingFailure.EXPECTED_SET_EQUIVALENCE_MISMATCH)


def _member_key_set(values: object) -> set[tuple[str, str, str, str]]:
    result: set[tuple[str, str, str, str]] = set()
    for value in _list(values):
        key = _list(value)
        if len(key) != 3 or type(key[0]) is not str or type(key[2]) is not str:
            raise ValueError("member key schema mismatch")
        instrument = _validate_instrument(key[1])
        canonical = (str(key[0]), str(instrument["venue"]), str(instrument["stable_key"]), str(key[2]))
        if canonical in result:
            raise ValueError("duplicate member key")
        result.add(canonical)
    return result


def _validate_s2b_closure(
    expected: dict[str, object],
    official: dict[str, object],
    extraction: dict[str, object],
    members: dict[str, _ReadMember],
) -> None:
    accounting = _dict(extraction["accounting"])
    outputs = _dict(extraction["output_members"])
    o_keys = _member_key_set(official["o_member_keys"])
    n_keys = _member_key_set(official["n_member_keys"])
    exact_accounting = {
        "expected_member_count": 96537,
        "provider_member_count": 96515,
        "official_filing_member_count": 1,
        "official_nonfiling_member_count": 21,
        "missing_member_count": 0,
        "coverage_extra_member_count": 0,
        "provider_official_filing_overlap_count": 0,
        "provider_official_nonfiling_overlap_count": 0,
        "official_filing_nonfiling_overlap_count": 0,
    }
    false_flags = (
        "formal_s2_qualified", "financial_payload_complete", "financial_scope_qualified",
        "decision_grade_eligible", "strategy_authorized", "strategy_target_authorized",
        "backtest_authorized", "validation_authorized", "deployment_authorized",
    )
    if (
        extraction["closure_equation"] != "96537 = 96515 P + 1 O + 21 N"
        or extraction["provisional_exact_cover_complete"] is not True
        or extraction["provisional_expected_scope_extracted"] is not True
        or any(accounting.get(name) != value for name, value in exact_accounting.items())
        or any(extraction[name] is not False for name in false_flags)
        or expected["expected_member_count"] != 96537
        or official["o_member_count"] != 1
        or len(o_keys) != 1
        or official["n_member_count"] != 21
        or len(n_keys) != 21
        or bool(o_keys & n_keys)
        or _canonical_hash(official["o_member_keys"]) != _O_KEYS_HASH
        or _canonical_hash(official["n_member_keys"]) != _N_KEYS_HASH
        or set(outputs) != {"provisional-expected-set.json", "provider-rows.jsonl", "official-coverage.json"}
        or any(_dict(outputs[name]).get("byte_count") != _S2B_FILES[name].byte_count for name in outputs)
        or any(_dict(outputs[name]).get("sha256") != _S2B_FILES[name].sha256 for name in outputs)
        or _dict(outputs["provisional-expected-set.json"]).get("schema_id") != _EXPECTED_SET_ID
        or _dict(outputs["official-coverage.json"]).get("schema_id") != _OFFICIAL_COVERAGE_ID
        or _dict(outputs["provider-rows.jsonl"]).get("row_count") != 150909
        or _dict(outputs["provider-rows.jsonl"]).get("row_ids_hash") != _PROVIDER_ROW_IDS_HASH
        or any(members[name].sha256 != frozen.sha256 for name, frozen in _S2B_FILES.items())
    ):
        _fail(QualityBbandTushareS1S2bBindingFailure.S2B_CLOSURE_OR_PAYLOAD_MISMATCH)


def _build_manifest(s1: dict[str, object], extraction: dict[str, object]) -> dict[str, object]:
    s1_inputs = _dict(s1["inputs"])
    s2b_inputs = _dict(extraction["inputs"])
    body: dict[str, object] = {
        "type": "quality_bband_tushare_s1_s2b_stage_binding_manifest",
        "schema_version": 1,
        "backtest_base_commit": _BASE_COMMIT,
        "inputs": {
            "formal_s1": {
                "artifact_type": "quality_bband_tushare_s1_structural_manifest",
                "member_name": _S1_FILE.name,
                "manifest_id": "sha256:dcd0fecbfca29ce090b53462f3972174d4977116e52472309055b4110046df85",
                "byte_count": _S1_FILE.byte_count,
                "file_sha256": _S1_FILE.sha256,
                "owner_decision_id": _OWNER_DECISION_ID,
                "packet_body_hash": _PACKET_BODY_HASH,
            },
            "s2b": {
                "artifact_type": "quality_bband_s2b_provisional_exact_extraction_manifest",
                "member_name": "extraction-manifest.json",
                "manifest_id": "sha256:e526416335016b9fd421e138655303673e76dc2bf6e2f53a6bb580904ed70d74",
                "byte_count": _S2B_FILES["extraction-manifest.json"].byte_count,
                "file_sha256": _S2B_FILES["extraction-manifest.json"].sha256,
                "expected_set_id": _EXPECTED_SET_ID,
                "official_coverage_id": _OFFICIAL_COVERAGE_ID,
            },
        },
        "shared_source_bindings": {
            name: _source_binding(s1_inputs[name])
            for name in ("s0", "annual_roster")
            if _source_binding(s1_inputs[name]) == _source_binding(s2b_inputs[name])
        },
        "classification_replacement": {
            "source_expected_set": {
                "authority_level": "SOURCE_BOUNDED_PROVISIONAL",
                "formal_s1_qualified": False,
            },
            "source_extraction": {
                "formal_s1_qualified": False,
                "limitation": "FORMAL_S1_FALSE",
            },
            "bound_stage": {
                "authority_level": "OWNER_APPROVED_TUSHARE_FORMAL_S1",
                "owner_approved_tushare_authority": True,
                "formal_s1_qualified": True,
            },
            "replaced_fields": [
                "extraction-manifest.json:formal_s1_qualified",
                "extraction-manifest.json:limitations/FORMAL_S1_FALSE",
                "provisional-expected-set.json:authority_level",
                "provisional-expected-set.json:formal_s1_qualified",
            ],
            "data_fields_rewritten": [],
            "original_artifact_bytes_modified": False,
        },
        "equivalence": {
            "screen_eligible_instrument_arrays_equal": True,
            "period_requirement_arrays_equal": True,
            "instrument_union_arrays_equal": True,
            "expected_pair_arrays_equal": True,
            "expected_member_key_arrays_equal": True,
            "screen_count": 9,
            "screen_eligible_counts": dict(_SCREEN_COUNTS),
            "screen_eligible_instrument_ids_hashes": dict(_SCREEN_HASHES),
            "instrument_union_count": 2845,
            "expected_pair_count": 32179,
            "expected_member_count": 96537,
            "shared_hashes": dict(_HASHES),
        },
        "s2b_closure": {
            "equation": "96537 = 96515 P + 1 O + 21 N",
            "expected_member_count": 96537,
            "provider_member_count": 96515,
            "official_filing_member_count": 1,
            "official_nonfiling_member_count": 21,
            "missing_member_count": 0,
            "coverage_extra_member_count": 0,
            "provider_official_filing_overlap_count": 0,
            "provider_official_nonfiling_overlap_count": 0,
            "official_filing_nonfiling_overlap_count": 0,
        },
        "preserved_s2b_members": {
            "provisional-expected-set.json": {
                "content_type": "application/json",
                "byte_count": 6587372,
                "sha256": _S2B_FILES["provisional-expected-set.json"].sha256,
                "schema_id": _EXPECTED_SET_ID,
            },
            "provider-rows.jsonl": {
                "content_type": "application/x-ndjson",
                "byte_count": 90363445,
                "sha256": _S2B_FILES["provider-rows.jsonl"].sha256,
                "row_count": 150909,
                "row_ids_hash": _PROVIDER_ROW_IDS_HASH,
            },
            "official-coverage.json": {
                "content_type": "application/json",
                "byte_count": 17755,
                "sha256": _S2B_FILES["official-coverage.json"].sha256,
                "schema_id": _OFFICIAL_COVERAGE_ID,
                "o_member_keys_hash": _O_KEYS_HASH,
                "n_member_keys_hash": _N_KEYS_HASH,
            },
            "extraction-manifest.json": {
                "content_type": "application/json",
                "byte_count": 62418,
                "sha256": _S2B_FILES["extraction-manifest.json"].sha256,
                "manifest_id": "sha256:e526416335016b9fd421e138655303673e76dc2bf6e2f53a6bb580904ed70d74",
            },
        },
        "flags": dict(_FLAGS),
        "limitations": list(_LIMITATIONS),
    }
    return {**body, "manifest_id": _canonical_hash(body)}


def _output_parent_components(output: Path) -> tuple[str, tuple[str, ...]]:
    if output.name in {"", ".", ".."}:
        raise ValueError("invalid output name")
    components = tuple(
        component
        for component in output.parent.parts
        if component not in {output.anchor, "", "."}
    )
    if ".." in components:
        raise ValueError("output parent traversal is forbidden")
    return ("/" if output.is_absolute() else "."), components


def _open_output_parent(output: Path, *, create: bool) -> int:
    anchor, components = _output_parent_components(output)
    flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(anchor, flags)
    try:
        for component in components:
            try:
                child_fd = os.open(component, flags, dir_fd=descriptor)
            except FileNotFoundError:
                if not create:
                    raise
                created = False
                try:
                    os.mkdir(component, 0o700, dir_fd=descriptor)
                    created = True
                except FileExistsError:
                    pass
                child_fd = os.open(component, flags, dir_fd=descriptor)
                if created:
                    os.fchmod(child_fd, 0o700)
                    os.fsync(child_fd)
                    os.fsync(descriptor)
            os.close(descriptor)
            descriptor = child_fd
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _verify_visible_output_parent(output: Path, identity: os.stat_result) -> None:
    current_fd = _open_output_parent(output, create=False)
    try:
        if not _same_inode(os.fstat(current_fd), identity):
            raise OSError("visible output parent changed")
    finally:
        os.close(current_fd)


def _preflight(s1_root: Path, s2b_root: Path, output: Path) -> int:
    if any(not isinstance(path, Path) for path in (s1_root, s2b_root, output)):
        _fail(QualityBbandTushareS1S2bBindingFailure.INPUT_TYPE_SCHEMA_OR_PATH)
    parent_fd = -1
    try:
        _output_parent_components(output)
        resolved_output = output.resolve(strict=False)
        for root in (s1_root, s2b_root):
            if root.is_symlink() or not root.is_dir():
                raise ValueError("unsafe input root")
            resolved_root = root.resolve(strict=True)
            if resolved_output == resolved_root or resolved_root in resolved_output.parents:
                raise ValueError("output is inside input")
        parent_fd = _open_output_parent(output, create=True)
        parent_identity = os.fstat(parent_fd)
        try:
            os.stat(output.name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise ValueError("output exists")
        _verify_visible_output_parent(output, parent_identity)
        return parent_fd
    except (OSError, ValueError) as error:
        if parent_fd >= 0:
            os.close(parent_fd)
        raise QualityBbandTushareS1S2bBindingError(
            QualityBbandTushareS1S2bBindingFailure.INPUT_TYPE_SCHEMA_OR_PATH
        ) from error


def _rename_noreplace_at(parent_fd: int, source_name: str, target_name: str) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is None:
        raise OSError("atomic no-replace rename is unavailable")
    renameat2.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    renameat2.restype = ctypes.c_int
    if renameat2(parent_fd, os.fsencode(source_name), parent_fd, os.fsencode(target_name), 1) != 0:
        error_number = ctypes.get_errno()
        raise OSError(error_number, os.strerror(error_number), target_name)


def _same_inode(left: os.stat_result, right: os.stat_result) -> bool:
    return (left.st_dev, left.st_ino) == (right.st_dev, right.st_ino)


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
    return (
        stat.S_ISREG(metadata.st_mode)
        and metadata.st_size == len(content)
        and total == len(content)
        and b"".join(chunks) == content
    )


def _atomic_publish(output: Path, content: bytes, parent_fd: int) -> None:
    staging_fd = -1
    member_fd = -1
    staging_name = f".{output.name}.staging-{os.getpid()}"
    staging_identity: os.stat_result | None = None
    member_identity: os.stat_result | None = None
    try:
        parent_identity = os.fstat(parent_fd)
        if not stat.S_ISDIR(parent_identity.st_mode):
            raise OSError("publication parent is not a directory")
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
        staging_fd = os.open(
            staging_name,
            os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=parent_fd,
        )
        if not _same_inode(os.fstat(staging_fd), staging_identity):
            raise OSError("staging directory changed before open")
        member_fd = os.open(
            _OUTPUT_NAME,
            os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=staging_fd,
        )
        offset = 0
        while offset < len(content):
            offset += os.write(member_fd, content[offset:])
        os.fchmod(member_fd, 0o600)
        os.fsync(member_fd)
        member_identity = os.fstat(member_fd)
        if not _readback_matches(member_fd, content):
            raise OSError("publication readback mismatch")
        os.fsync(staging_fd)
        if not _same_inode(os.stat(staging_name, dir_fd=parent_fd, follow_symlinks=False), staging_identity):
            raise OSError("staging pathname changed")
        if not _same_inode(os.stat(_OUTPUT_NAME, dir_fd=staging_fd, follow_symlinks=False), member_identity):
            raise OSError("staged member pathname changed")
        _rename_noreplace_at(parent_fd, staging_name, output.name)
        published_fd = os.open(
            output.name,
            os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=parent_fd,
        )
        try:
            if not _same_inode(os.fstat(published_fd), staging_identity):
                raise OSError("published directory inode mismatch")
            published_member_fd = os.open(
                _OUTPUT_NAME,
                os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=published_fd,
            )
            try:
                if (
                    not _same_inode(os.fstat(published_member_fd), member_identity)
                    or not _readback_matches(published_member_fd, content)
                ):
                    raise OSError("published member mismatch")
            finally:
                os.close(published_member_fd)
        finally:
            os.close(published_fd)
        os.fsync(parent_fd)
        _verify_visible_output_parent(output, parent_identity)
    except (FileExistsError, OSError, ValueError) as error:
        try:
            os.fsync(parent_fd)
        except OSError:
            pass
        raise QualityBbandTushareS1S2bBindingError(
            QualityBbandTushareS1S2bBindingFailure.PUBLICATION_INTEGRITY_FAILURE
        ) from error
    finally:
        if member_fd >= 0:
            os.close(member_fd)
        if staging_fd >= 0:
            os.close(staging_fd)


def _build_preflighted(
    *,
    s1_root: Path,
    s2b_root: Path,
    output_dir: Path,
    output_parent_fd: int,
) -> dict[str, object]:
    s1_loaded: tuple[dict[str, object], _ReadMember] | None = None
    s2b_loaded: tuple[
        dict[str, object], dict[str, object], dict[str, object], dict[str, _ReadMember]
    ] | None = None
    input_error: BaseException | None = None
    identity_error: BaseException | None = None
    try:
        s1_loaded = _load_s1(s1_root)
    except _ArtifactIdentityMismatch as error:
        identity_error = error
    except (KeyError, OSError, TypeError, ValueError) as error:
        input_error = error
    try:
        s2b_loaded = _load_s2b(s2b_root)
    except _ArtifactIdentityMismatch as error:
        identity_error = identity_error or error
    except (KeyError, OSError, TypeError, ValueError) as error:
        input_error = input_error or error
    if input_error is not None:
        raise QualityBbandTushareS1S2bBindingError(
            QualityBbandTushareS1S2bBindingFailure.INPUT_TYPE_SCHEMA_OR_PATH
        ) from input_error
    if identity_error is not None:
        raise QualityBbandTushareS1S2bBindingError(
            QualityBbandTushareS1S2bBindingFailure.ARTIFACT_IDENTITY_MISMATCH
        ) from identity_error
    assert s1_loaded is not None and s2b_loaded is not None
    s1, s1_member = s1_loaded
    expected, official, extraction, s2b_members = s2b_loaded
    try:
        _validate_artifact_identities(s1, s1_member, expected, official, extraction, s2b_members)
    except QualityBbandTushareS1S2bBindingError:
        raise
    except (KeyError, TypeError, ValueError) as error:
        raise QualityBbandTushareS1S2bBindingError(
            QualityBbandTushareS1S2bBindingFailure.ARTIFACT_IDENTITY_MISMATCH
        ) from error
    try:
        _validate_authority(s1, expected, extraction)
    except QualityBbandTushareS1S2bBindingError:
        raise
    except (KeyError, TypeError, ValueError) as error:
        raise QualityBbandTushareS1S2bBindingError(
            QualityBbandTushareS1S2bBindingFailure.AUTHORITY_REBINDING_MISMATCH
        ) from error
    try:
        _validate_shared_sources(s1, extraction)
    except QualityBbandTushareS1S2bBindingError:
        raise
    except (KeyError, TypeError, ValueError) as error:
        raise QualityBbandTushareS1S2bBindingError(
            QualityBbandTushareS1S2bBindingFailure.SHARED_SOURCE_BINDING_MISMATCH
        ) from error
    try:
        _validate_equivalence(s1, expected)
    except QualityBbandTushareS1S2bBindingError:
        raise
    except (KeyError, TypeError, ValueError) as error:
        raise QualityBbandTushareS1S2bBindingError(
            QualityBbandTushareS1S2bBindingFailure.EXPECTED_SET_EQUIVALENCE_MISMATCH
        ) from error
    try:
        _validate_s2b_closure(expected, official, extraction, s2b_members)
    except QualityBbandTushareS1S2bBindingError:
        raise
    except (KeyError, TypeError, ValueError) as error:
        raise QualityBbandTushareS1S2bBindingError(
            QualityBbandTushareS1S2bBindingFailure.S2B_CLOSURE_OR_PAYLOAD_MISMATCH
        ) from error
    manifest = _build_manifest(s1, extraction)
    raw = _canonical_json(manifest).encode("utf-8")
    if (
        manifest["manifest_id"] != _EXPECTED_MANIFEST_ID
        or len(raw) != _EXPECTED_OUTPUT_SIZE
        or _bytes_hash(raw) != _EXPECTED_OUTPUT_HASH
        or raw.endswith(b"\n")
    ):
        _fail(QualityBbandTushareS1S2bBindingFailure.FROZEN_OUTPUT_MISMATCH)
    _atomic_publish(output_dir, raw, output_parent_fd)
    return manifest


def build_quality_bband_tushare_s1_s2b_stage_binding_v1(
    *,
    s1_root: Path,
    s2b_root: Path,
    output_dir: Path,
) -> dict[str, object]:
    output_parent_fd = _preflight(s1_root, s2b_root, output_dir)
    try:
        return _build_preflighted(
            s1_root=s1_root,
            s2b_root=s2b_root,
            output_dir=output_dir,
            output_parent_fd=output_parent_fd,
        )
    finally:
        os.close(output_parent_fd)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bind accepted formal Tushare S1 to accepted provisional S2B")
    parser.add_argument("--s1-root", type=Path, required=True)
    parser.add_argument("--s2b-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        manifest = build_quality_bband_tushare_s1_s2b_stage_binding_v1(
            s1_root=args.s1_root,
            s2b_root=args.s2b_root,
            output_dir=args.output_dir,
        )
    except QualityBbandTushareS1S2bBindingError as error:
        print(error.code.value)
        return 1
    print(manifest["manifest_id"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
