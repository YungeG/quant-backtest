from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
from datetime import date
from pathlib import Path
from typing import cast

import pytest
from crypto_quant_bundle_builder import RawSourceMember, SourceSnapshotProvenance, freeze_source_snapshot

import tools.acquisition.cn_a_share_quality_bband_tushare_s1_structural_v1 as s1


def _raw(fields: tuple[str, ...], rows: list[list[object]]) -> bytes:
    return json.dumps(
        {
            "request_id": "fixture",
            "code": 0,
            "data": {"fields": list(fields), "items": rows, "has_more": False, "count": 0},
            "msg": None,
            "detail": None,
        },
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def _loaded(members: dict[str, bytes], receipt: dict[str, object] | None = None) -> s1._LoadedSourceRoot:
    outcome = freeze_source_snapshot(
        members=tuple(
            RawSourceMember(key, value, "0644", index + 1, None)
            for index, (key, value) in enumerate(sorted(members.items()))
        ),
        provenance=SourceSnapshotProvenance(
            vendor_key="fixture.vendor",
            source_key="fixture.source",
            license_ref="fixture.license",
            retention_policy_ref="fixture.retention",
        ),
    )
    assert outcome.snapshot is not None
    return s1._LoadedSourceRoot(
        Path("/fixture"),
        outcome.snapshot,
        outcome.snapshot.to_canonical_dict(),
        receipt or {},
        members,
    )


def _s0_row(
    code: str,
    *,
    market: str = "主板",
    exchange: str | None = None,
    curr_type: str = "CNY",
) -> list[object]:
    values: dict[str, object] = {field: None for field in s1._FIELDS["s0"]}
    values.update(
        ts_code=code,
        symbol=code[:6],
        name="fixture",
        market=market,
        exchange=exchange or ("SZSE" if code.endswith(".SZ") else "SSE"),
        curr_type=curr_type,
        list_status="L",
        list_date="20100101",
    )
    return [values[field] for field in s1._FIELDS["s0"]]


def _roster_row(
    screen_date: str,
    code: str,
    *,
    industry: object = "制造业",
    list_date: object = "20100101",
) -> list[object]:
    values = {
        "trade_date": screen_date,
        "ts_code": code,
        "name": "fixture",
        "industry": industry,
        "list_date": list_date,
    }
    return [values[field] for field in s1._FIELDS["annual_roster"]]


def _annual(rows_by_screen: dict[str, list[list[object]]]) -> s1._LoadedSourceRoot:
    members = {
        f"response/tushare/bak_basic/{screen}-v1.json": _raw(
            s1._FIELDS["annual_roster"], rows_by_screen.get(screen, [])
        )
        for screen in ("20160503", *s1._SCREEN_DATES)
    }
    return _loaded(members)


def _catalog(codes: list[str]) -> tuple[list[dict[str, object]], dict[str, dict[str, object]]]:
    members: list[dict[str, object]] = []
    current: dict[str, dict[str, object]] = {}
    for index, code in enumerate(codes):
        instrument = s1._canonical_instrument(code)
        members.append(
            {
                "instrument_id": instrument,
                "provider_code": code,
                "source_member_key": "response/s0.json",
                "source_row_index": index,
            }
        )
        current[code] = dict(zip(s1._FIELDS["s0"], _s0_row(code), strict=True))
    members.sort(key=lambda member: s1._instrument_sort_key(member["instrument_id"]))  # type: ignore[arg-type]
    return members, current


def test_strict_json_mapping_and_calendar_anniversary_are_exact() -> None:
    for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":1e999}'):
        with pytest.raises(ValueError, match="strict JSON"):
            s1._strict_json(raw)
    assert s1._canonical_instrument("000001.SZ") == {
        "type": "instrument_id",
        "venue": "xshe",
        "stable_key": "000001",
    }
    assert s1._canonical_instrument("600000.SH")["venue"] == "xshg"
    for value in ("430001.BJ", "600000.sh", "xshg:600000"):
        with pytest.raises(s1.QualityBbandTushareS1Error) as raised:
            s1._canonical_instrument(value)
        assert raised.value.code is s1.QualityBbandTushareS1Failure.CATALOG_IDENTITY_MISMATCH
    assert s1._fifth_anniversary(date(2016, 2, 29)) == date(2021, 2, 28)


def test_catalog_classifies_exact_extras_and_rejects_duplicate_or_venue_conflict() -> None:
    source = _loaded(
        {
            "response/s0-a.json": _raw(
                s1._FIELDS["s0"],
                [_s0_row("600001.SH"), _s0_row("000001.SZ"), _s0_row("430001.BJ"), _s0_row("T600018.SH")],
            )
        }
    )
    catalog, extras, current = s1._derive_catalog_and_extras(source)
    assert [
        (cast(dict[str, str], member["instrument_id"])["venue"], member["provider_code"])
        for member in catalog
    ] == [
        ("xshe", "000001.SZ"),
        ("xshg", "600001.SH"),
    ]
    assert extras == ["430001.BJ", "T600018.SH"]
    assert set(current) == {"000001.SZ", "600001.SH"}

    duplicate = _loaded(
        {
            "response/a.json": _raw(s1._FIELDS["s0"], [_s0_row("000001.SZ")]),
            "response/b.json": _raw(s1._FIELDS["s0"], [_s0_row("000001.SZ")]),
        }
    )
    mismatch = _loaded(
        {"response/a.json": _raw(s1._FIELDS["s0"], [_s0_row("000001.SZ", exchange="SSE")])}
    )
    malformed = _loaded(
        {"response/a.json": _raw(s1._FIELDS["s0"], [_s0_row("600001.sh")])}
    )
    for invalid in (duplicate, mismatch, malformed):
        with pytest.raises(s1.QualityBbandTushareS1Error) as raised:
            s1._derive_catalog_and_extras(invalid)
        assert raised.value.code is s1.QualityBbandTushareS1Failure.CATALOG_IDENTITY_MISMATCH


def test_disposition_first_reason_precedence_and_screen_closure() -> None:
    codes = [f"00000{value}.SZ" for value in range(1, 9)]
    catalog, current = _catalog(codes)
    current[codes[1]]["market"] = "创业板"
    current[codes[7]]["curr_type"] = "USD"
    target_rows = [
        _roster_row("20170502", codes[1], industry=None, list_date="0"),
        _roster_row("20170502", codes[2], industry=None, list_date="0"),
        _roster_row("20170502", codes[3], industry="银行", list_date="20160101"),
        _roster_row("20170502", codes[4], industry="银行"),
        _roster_row("20170502", codes[5], industry=None),
        _roster_row("20170502", codes[6]),
        _roster_row("20170502", codes[7], industry=None, list_date="0"),
        _roster_row("20170502", "600999.SH"),
    ]
    rows_by_screen = {
        screen: [
            _roster_row(screen, code)
            for code in codes
        ]
        for screen in s1._SCREEN_DATES
    }
    rows_by_screen["20170502"] = target_rows
    screens, extras, extra_counts = s1._build_screen_dispositions(
        catalog, current, _annual(rows_by_screen)
    )
    first = screens[0]
    dispositions = cast(list[dict[str, object]], first["dispositions"])
    assert [value["reason"] for value in dispositions] == [
        "NOT_PRESENT_IN_TUSHARE_SCREEN_ROSTER",
        "NON_CNY_OR_NON_MAIN_BOARD",
        "LIST_DATE_UNKNOWN",
        "LISTING_AGE_LT_FIVE_YEARS",
        "FINANCIAL_INDUSTRY",
        None,
        None,
        "NON_CNY_OR_NON_MAIN_BOARD",
    ]
    assert [value["disposition"] for value in dispositions][5:7] == [
        "UNRESOLVED_STRUCTURAL_AUTHORITY",
        "STRUCTURALLY_ELIGIBLE",
    ]
    assert (first["eligible_count"], first["out_of_scope_count"], first["unresolved_count"]) == (1, 6, 1)
    assert first["closure_complete"] is True
    assert extras[0] == {"screen_date": "20170502", "provider_code": "600999.SH"}
    assert extra_counts["20170502"] == 1


def test_duplicate_roster_precedes_industry_and_screen_mismatch_is_separate() -> None:
    catalog, current = _catalog(["000001.SZ"])
    duplicate_rows = {
        screen: [_roster_row(screen, "000001.SZ")]
        for screen in s1._SCREEN_DATES
    }
    duplicate_rows["20170502"] = [
        _roster_row("20170502", "000001.SZ", industry=None),
        _roster_row("20170502", "000001.SZ", industry="银行"),
    ]
    with pytest.raises(s1.QualityBbandTushareS1Error) as duplicate:
        s1._build_screen_dispositions(catalog, current, _annual(duplicate_rows))
    assert duplicate.value.code is s1.QualityBbandTushareS1Failure.DUPLICATE_ROSTER_ROW

    mismatched = {screen: [_roster_row(screen, "000001.SZ")] for screen in s1._SCREEN_DATES}
    mismatched["20170502"] = [_roster_row("20170503", "000001.SZ")]
    with pytest.raises(s1.QualityBbandTushareS1Error) as calendar:
        s1._build_screen_dispositions(catalog, current, _annual(mismatched))
    assert calendar.value.code is s1.QualityBbandTushareS1Failure.SCREEN_CALENDAR_REQUEST_MISMATCH


def test_financial_requirements_preserve_period_pair_and_api_order() -> None:
    instruments = [s1._canonical_instrument("000001.SZ"), s1._canonical_instrument("600001.SH")]
    screens = [
        {"screen_date": "20170502", "eligible_instrument_ids": instruments},
        {"screen_date": "20180502", "eligible_instrument_ids": instruments[:1]},
    ]
    periods, union, pairs, keys = s1._build_financial_requirements(screens)
    assert periods[0]["periods"] == ["20121231", "20131231", "20141231", "20151231", "20161231"]
    assert [(value["venue"], value["stable_key"]) for value in union] == [
        ("xshe", "000001"),
        ("xshg", "600001"),
    ]
    shared = next(
        pair
        for pair in pairs
        if pair["period"] == "20131231"
        and cast(dict[str, str], pair["instrument_id"])["venue"] == "xshe"
    )
    assert shared["required_by_screen_dates"] == ["20170502", "20180502"]
    pair_count = len(pairs)
    assert [keys[index * pair_count][0] for index in range(3)] == list(s1._API_NAMES)


def test_frozen_validator_rejects_any_count_or_hash_drift() -> None:
    manifest = {
        "owner_decision_id": s1._OWNER_DECISION_ID,
        "packet_body_hash": s1._PACKET_BODY_HASH,
        "backtest_base_commit": s1._BASE_COMMIT,
        "hashes": {key: value for key, value in s1._EXPECTED.items() if key.endswith("hash")},
        "counts": {
            "s0_total_row_count": 5889,
            "canonical_catalog_count": 5545,
            "source_extra_count": 344,
            "screen_count": 9,
            "all_disposition_count": 49905,
            "instrument_union_count": 2845,
            "expected_pair_count": 32179,
            "expected_member_key_count": 96537,
            "disposition_counts": dict(s1._EXPECTED_REASON_COUNTS),
        },
        "source_extras": {
            "roster_extra_counts_by_screen": dict(s1._EXPECTED_ROSTER_EXTRA_COUNTS),
            "roster_extra_row_count": 536,
        },
        "screens": [
            {
                "screen_date": screen,
                "eligible_count": expected[0],
                "out_of_scope_count": expected[1],
                "unresolved_count": 0,
                "dispositions_hash": expected[2],
                "eligible_instrument_ids_hash": expected[3],
                "closure_complete": True,
            }
            for screen, expected in s1._EXPECTED_SCREEN.items()
        ],
    }
    s1._validate_frozen_hashes(manifest)
    manifest["counts"]["expected_pair_count"] = 32178
    with pytest.raises(s1.QualityBbandTushareS1Error) as raised:
        s1._validate_frozen_hashes(manifest)
    assert raised.value.code is s1.QualityBbandTushareS1Failure.FROZEN_VALUE_MISMATCH


def test_bounded_source_paths_reject_escape_nonregular_oversize_and_symlink(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    member = root / "member.bin"
    member.write_bytes(b"abc")
    assert s1._read_root_member(root, "member.bin", {"member.bin"}, maximum_bytes=3) == b"abc"
    for key in ("../outside.bin", "/tmp/outside.bin", "a\\b"):
        with pytest.raises(ValueError, match="unsafe source member"):
            s1._read_root_member(root, key, {"member.bin"}, maximum_bytes=3)
    member.write_bytes(b"abcd")
    with pytest.raises(ValueError, match="unsafe source member"):
        s1._read_root_member(root, "member.bin", {"member.bin"}, maximum_bytes=3)
    member.unlink()
    member.mkdir()
    with pytest.raises(ValueError, match="unsafe source member"):
        s1._read_root_member(root, "member.bin", {"member.bin"}, maximum_bytes=3)
    member.rmdir()
    (tmp_path / "target").write_bytes(b"abc")
    member.symlink_to(tmp_path / "target")
    with pytest.raises(ValueError, match="unsafe source root"):
        s1._path_files(root)


def test_source_root_reconstruction_requires_exact_files_and_hashes(tmp_path: Path) -> None:
    member_key = "response/member.json"
    loaded = _loaded({member_key: b"abc"})
    root = tmp_path / "source"
    path = root / member_key
    path.parent.mkdir(parents=True)
    path.write_bytes(b"abc")
    snapshot_raw = s1._canonical_json(loaded.snapshot_metadata).encode()
    receipt_raw = b"{}"
    (root / "source-snapshot.json").write_bytes(snapshot_raw)
    (root / "acquisition-receipt.json").write_bytes(receipt_raw)
    identity = s1._FrozenSourceIdentity(
        loaded.snapshot.snapshot_id,
        loaded.snapshot.content_tree_hash,
        loaded.snapshot.provenance_hash,
        s1._bytes_hash(snapshot_raw),
        s1._bytes_hash(receipt_raw),
        3,
    )
    assert s1._load_source_root(root, identity).member_bytes[member_key] == b"abc"
    path.write_bytes(b"changed")
    with pytest.raises(s1.QualityBbandTushareS1Error) as raised:
        s1._load_source_root(root, identity)
    assert raised.value.code is s1.QualityBbandTushareS1Failure.SOURCE_RECONSTRUCTION_FAILURE


def _publish(output: Path, content: bytes) -> None:
    parent_fd = s1._open_output_parent(output, create=True)
    try:
        s1._atomic_publish(output, content, parent_fd)
    finally:
        os.close(parent_fd)


def test_secure_output_parent_traversal_rejects_symlinks_and_dotdot_at_priority_one(
    tmp_path: Path,
) -> None:
    s0_root = tmp_path / "s0"
    annual_root = tmp_path / "annual"
    outside = tmp_path / "outside"
    for directory in (s0_root, annual_root, outside):
        directory.mkdir()
    (tmp_path / "linked").symlink_to(outside, target_is_directory=True)
    for output in (tmp_path / "linked/candidate", tmp_path / "safe/../candidate"):
        with pytest.raises(s1.QualityBbandTushareS1Error) as raised:
            s1.build_quality_bband_tushare_s1_structural_v1(
                s0_root=s0_root,
                annual_roster_root=annual_root,
                output_dir=output,
            )
        assert raised.value.code is s1.QualityBbandTushareS1Failure.INPUT_TYPE_OR_PATH


def test_preflight_rejects_output_inside_input_without_creating_parent(tmp_path: Path) -> None:
    s0_root = tmp_path / "s0"
    annual_root = tmp_path / "annual"
    s0_root.mkdir()
    annual_root.mkdir()
    output = s0_root / "new" / "candidate"
    with pytest.raises(s1.QualityBbandTushareS1Error) as raised:
        s1.build_quality_bband_tushare_s1_structural_v1(
            s0_root=s0_root,
            annual_roster_root=annual_root,
            output_dir=output,
        )
    assert raised.value.code is s1.QualityBbandTushareS1Failure.INPUT_TYPE_OR_PATH
    assert not output.parent.exists()


def test_atomic_publication_is_no_clobber_exact_mode_and_preserves_racing_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "candidate"
    content = b"frozen"
    _publish(output, content)
    assert (output / s1._OUTPUT_NAME).read_bytes() == content
    assert stat.S_IMODE(output.stat().st_mode) == 0o700
    assert stat.S_IMODE((output / s1._OUTPUT_NAME).stat().st_mode) == 0o600
    with pytest.raises(s1.QualityBbandTushareS1Error) as existing:
        _publish(output, content)
    assert existing.value.code is s1.QualityBbandTushareS1Failure.PUBLICATION_INTEGRITY_FAILURE
    assert (output / s1._OUTPUT_NAME).read_bytes() == content

    raced = tmp_path / "raced"
    real_rename = s1._rename_noreplace_at
    real_fsync = os.fsync
    fsynced: list[tuple[int, int]] = []

    def recording_fsync(descriptor: int) -> None:
        metadata = os.fstat(descriptor)
        fsynced.append((metadata.st_dev, metadata.st_ino))
        real_fsync(descriptor)

    def racing_rename(parent_fd: int, source_name: str, target_name: str) -> None:
        os.mkdir(target_name, dir_fd=parent_fd)
        real_rename(parent_fd, source_name, target_name)

    monkeypatch.setattr(s1.os, "fsync", recording_fsync)
    monkeypatch.setattr(s1, "_rename_noreplace_at", racing_rename)
    with pytest.raises(s1.QualityBbandTushareS1Error) as raised:
        _publish(raced, content)
    assert raised.value.code is s1.QualityBbandTushareS1Failure.PUBLICATION_INTEGRITY_FAILURE
    assert raced.is_dir() and not any(raced.iterdir())
    staging = list(tmp_path.glob(f".{raced.name}.staging-*"))
    assert len(staging) == 1
    assert (staging[0] / s1._OUTPUT_NAME).read_bytes() == content
    parent_metadata = tmp_path.stat()
    assert (parent_metadata.st_dev, parent_metadata.st_ino) in fsynced


def test_atomic_publication_rejects_parent_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent = tmp_path / "parent"
    parent.mkdir()
    output = parent / "candidate"
    displaced = tmp_path / "displaced-parent"
    real_rename = s1._rename_noreplace_at

    def replace_parent(parent_fd: int, source_name: str, target_name: str) -> None:
        real_rename(parent_fd, source_name, target_name)
        parent.rename(displaced)
        parent.mkdir()

    monkeypatch.setattr(s1, "_rename_noreplace_at", replace_parent)
    with pytest.raises(s1.QualityBbandTushareS1Error) as raised:
        _publish(output, b"frozen")
    assert raised.value.code is s1.QualityBbandTushareS1Failure.PUBLICATION_INTEGRITY_FAILURE
    assert parent.is_dir() and not any(parent.iterdir())
    assert (displaced / "candidate" / s1._OUTPUT_NAME).read_bytes() == b"frozen"


def test_atomic_publication_rejects_ancestor_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ancestor = tmp_path / "ancestor"
    parent = ancestor / "parent"
    parent.mkdir(parents=True)
    output = parent / "candidate"
    displaced = tmp_path / "displaced-ancestor"
    real_rename = s1._rename_noreplace_at

    def replace_ancestor(parent_fd: int, source_name: str, target_name: str) -> None:
        real_rename(parent_fd, source_name, target_name)
        ancestor.rename(displaced)
        parent.mkdir(parents=True)

    monkeypatch.setattr(s1, "_rename_noreplace_at", replace_ancestor)
    with pytest.raises(s1.QualityBbandTushareS1Error) as raised:
        _publish(output, b"frozen")
    assert raised.value.code is s1.QualityBbandTushareS1Failure.PUBLICATION_INTEGRITY_FAILURE
    assert parent.is_dir() and not any(parent.iterdir())
    assert (displaced / "parent/candidate" / s1._OUTPUT_NAME).read_bytes() == b"frozen"


def test_atomic_publication_never_deletes_directory_substituted_between_mkdir_and_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "candidate"
    real_open = os.open
    substituted = False

    def racing_open(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        nonlocal substituted
        if (
            not substituted
            and isinstance(path, str)
            and path.startswith(f".{output.name}.staging-")
            and flags & os.O_DIRECTORY
            and dir_fd is not None
        ):
            substituted = True
            os.rename(path, path + ".original", src_dir_fd=dir_fd, dst_dir_fd=dir_fd)
            os.mkdir(path, 0o700, dir_fd=dir_fd)
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(s1.os, "open", racing_open)
    with pytest.raises(s1.QualityBbandTushareS1Error) as raised:
        _publish(output, b"frozen")
    assert raised.value.code is s1.QualityBbandTushareS1Failure.PUBLICATION_INTEGRITY_FAILURE
    attacker_dirs = [
        path
        for path in tmp_path.glob(f".{output.name}.staging-*")
        if not path.name.endswith(".original")
    ]
    assert len(attacker_dirs) == 1
    assert not any(attacker_dirs[0].iterdir())
    originals = list(tmp_path.glob(f".{output.name}.staging-*.original"))
    assert len(originals) == 1 and not any(originals[0].iterdir())


def test_atomic_publication_rejects_staging_inode_substitution_without_deleting_attacker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "candidate"
    real_rename = s1._rename_noreplace_at

    def substitute(parent_fd: int, source_name: str, target_name: str) -> None:
        os.rename(source_name, source_name + ".original", src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
        os.mkdir(source_name, dir_fd=parent_fd)
        real_rename(parent_fd, source_name, target_name)

    monkeypatch.setattr(s1, "_rename_noreplace_at", substitute)
    with pytest.raises(s1.QualityBbandTushareS1Error) as raised:
        _publish(output, b"frozen")
    assert raised.value.code is s1.QualityBbandTushareS1Failure.PUBLICATION_INTEGRITY_FAILURE
    assert output.is_dir() and not any(output.iterdir())
    originals = list(tmp_path.glob(f".{output.name}.staging-*.original"))
    assert len(originals) == 1
    assert (originals[0] / s1._OUTPUT_NAME).read_bytes() == b"frozen"


def test_atomic_publication_rejects_member_substitution_without_deleting_attacker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "candidate"
    real_rename = s1._rename_noreplace_at

    def substitute_member(parent_fd: int, source_name: str, target_name: str) -> None:
        staging_fd = os.open(source_name, os.O_RDONLY | os.O_DIRECTORY, dir_fd=parent_fd)
        try:
            os.unlink(s1._OUTPUT_NAME, dir_fd=staging_fd)
            attacker_fd = os.open(
                s1._OUTPUT_NAME,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
                dir_fd=staging_fd,
            )
            try:
                os.write(attacker_fd, b"attacker")
            finally:
                os.close(attacker_fd)
        finally:
            os.close(staging_fd)
        real_rename(parent_fd, source_name, target_name)

    monkeypatch.setattr(s1, "_rename_noreplace_at", substitute_member)
    with pytest.raises(s1.QualityBbandTushareS1Error) as raised:
        _publish(output, b"frozen")
    assert raised.value.code is s1.QualityBbandTushareS1Failure.PUBLICATION_INTEGRITY_FAILURE
    assert (output / s1._OUTPUT_NAME).read_bytes() == b"attacker"


_REAL_ROOT = Path("/srv/bcache-8t/ygguo/quant/artifacts/a-share-quality-bband")
_REAL_S0 = _REAL_ROOT / "s0-lightweight-source-snapshots/stock-basic/20260826/v1-candidate-01"
_REAL_ANNUAL = _REAL_ROOT / "annual-structural-roster-source-snapshots/2016-2025/20260826/v1-candidate-01"
_REAL_OUTPUT = Path("/tmp/qb-tushare-s1-structural-smoke")


@pytest.mark.skipif(
    os.environ.get("QB_TUSHARE_S1_REAL_ARTIFACT_SENTINEL") != "1"
    or not _REAL_S0.is_dir()
    or not _REAL_ANNUAL.is_dir(),
    reason="real accepted S1 inputs are unavailable or sentinel is not enabled",
)
def test_real_artifacts_reproduce_frozen_manifest() -> None:
    if _REAL_OUTPUT.exists():
        shutil.rmtree(_REAL_OUTPUT)
    manifest = s1.build_quality_bband_tushare_s1_structural_v1(
        s0_root=_REAL_S0,
        annual_roster_root=_REAL_ANNUAL,
        output_dir=_REAL_OUTPUT,
    )
    raw = (_REAL_OUTPUT / s1._OUTPUT_NAME).read_bytes()
    assert len(raw) == s1._EXPECTED_OUTPUT_SIZE
    assert s1._bytes_hash(raw) == s1._EXPECTED_OUTPUT_HASH
    assert manifest["manifest_id"] == s1._EXPECTED_MANIFEST_ID
    body = dict(json.loads(raw))
    manifest_id = body.pop("manifest_id")
    assert manifest_id == "sha256:" + hashlib.sha256(s1._canonical_json(body).encode()).hexdigest()
    assert not raw.endswith(b"\n")
