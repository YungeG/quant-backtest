from __future__ import annotations

import copy
import json
import os
import stat
from pathlib import Path
from typing import Any

import pytest

from crypto_quant_bundle_builder.source_snapshots import RawSourceMember, SourceSnapshotProvenance, freeze_source_snapshot
import tools.acquisition.cn_a_share_quality_bband_s1_s2b_prior_balance_binding_v1 as binding


FIELDS = [
    "ts_code", "ann_date", "f_ann_date", "end_date", "report_type", "comp_type",
    "money_cap", "total_assets", "total_liab", "total_hldr_eqy_inc_min_int",
    "total_hldr_eqy_exc_min_int", "minority_int", "total_liab_hldr_eqy", "st_borr",
    "non_cur_liab_due_1y", "lt_borr", "bond_payable", "st_bonds_payable", "update_flag",
]


def _instrument(code: str) -> dict[str, str]:
    return {"type": "instrument_id", "venue": "xshe", "stable_key": code}


def _requirement(code: str, period: str = "20111231") -> dict[str, object]:
    return {
        "api_name": "balancesheet_vip",
        "instrument_id": _instrument(code),
        "period": period,
        "required_by_screen_dates": ["20170502"],
    }


def _row(code: str, update: str, *, assets: int = 10, f_ann_date: str = "20120301") -> list[object]:
    return [
        f"{code}.SZ", "20120201", f_ann_date, "20111231", "1", "1", 1, assets,
        3, 7, 7, 0, 10, 0, 0, 0, 0, 0, update,
    ]


def _envelope(rows: list[list[object]]) -> bytes:
    return binding._canonical_json(
        {
            "request_id": "request",
            "code": 0,
            "data": {"fields": FIELDS, "items": rows, "has_more": False, "count": len(rows)},
            "msg": None,
            "detail": None,
        }
    ).encode()


def _loaded_stage_a(rows: list[list[object]]) -> binding._LoadedSourceRoot:
    member_key = "response/tushare/balancesheet_vip/20111231/member.json"
    raw = _envelope(rows)
    return binding._LoadedSourceRoot(
        {
            "type": "source_snapshot",
            "snapshot_id": "sha256:" + "1" * 64,
            "members": [{"member_key": member_key, "content_hash": binding._bytes_hash(raw)}],
        },
        {
            "request": {"fields": FIELDS},
            "root_tree": {
                "api_name": "balancesheet_vip",
                "period": "20111231",
                "root_member_key": member_key,
                "terminal_leaf_member_keys": [member_key],
            },
        },
        {member_key: raw},
    )


def test_strict_json_rejects_duplicate_invalid_utf8_and_nonfinite_values() -> None:
    for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":1e999}', b'"\xff"'):
        with pytest.raises(ValueError, match="strict JSON"):
            binding._strict_json(raw)


def test_exact_fixed_member_read_is_fd_relative_bounded_and_no_follow(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "member").write_bytes(b"abc")
    descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        frozen = binding._FrozenFile("member", 3, binding._bytes_hash(b"abc"))
        assert binding._read_exact_member(descriptor, frozen, keep_bytes=True).raw == b"abc"
        assert binding._read_exact_member(descriptor, frozen, keep_bytes=False).raw is None
        (root / "member").unlink()
        (root / "member").symlink_to(tmp_path / "outside")
        with pytest.raises(OSError):
            binding._read_exact_member(descriptor, frozen, keep_bytes=True)
    finally:
        os.close(descriptor)


def test_fixed_s2b_root_rejects_member_injected_during_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "s2b"
    root.mkdir()
    for name in binding._S2B_FILES:
        (root / name).write_bytes(b"")
    injected = False

    def racing_read(
        root_fd: int,
        frozen: binding._FrozenFile,
        *,
        keep_bytes: bool,
    ) -> binding._ReadMember:
        nonlocal injected
        if not injected:
            injected = True
            descriptor = os.open(
                "attacker-extra",
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
                dir_fd=root_fd,
            )
            os.close(descriptor)
        return binding._ReadMember(
            b"{}" if keep_bytes else None,
            frozen.byte_count,
            frozen.sha256,
        )

    monkeypatch.setattr(binding, "_read_exact_member", racing_read)
    with pytest.raises(ValueError, match="root changed"):
        binding._load_s2b(root)


def _source_root(tmp_path: Path) -> tuple[Path, str, bytes, binding._FrozenSourceIdentity]:
    root = tmp_path / "source"
    member_key = "response/member.json"
    member_raw = b'{"source":true}'
    provenance = SourceSnapshotProvenance("vendor", "source", "license", "retention")
    frozen = freeze_source_snapshot(
        members=(RawSourceMember(member_key, member_raw, "0644", 1, None),), provenance=provenance
    )
    assert frozen.snapshot is not None
    snapshot_raw = binding._canonical_json(frozen.snapshot.to_canonical_dict()).encode()
    receipt = {"type": "receipt", "request": {"x": 1}, "provider_requests": [], "root_tree": {"x": 2}}
    receipt_raw = binding._canonical_json(receipt).encode()
    (root / "response").mkdir(parents=True)
    (root / member_key).write_bytes(member_raw)
    (root / "source-snapshot.json").write_bytes(snapshot_raw)
    (root / "acquisition-receipt.json").write_bytes(receipt_raw)
    identity = binding._FrozenSourceIdentity(
        frozen.snapshot.snapshot_id,
        frozen.snapshot.content_tree_hash,
        frozen.snapshot.provenance_hash,
        binding._FrozenFile("source-snapshot.json", len(snapshot_raw), binding._bytes_hash(snapshot_raw)),
        binding._FrozenFile("acquisition-receipt.json", len(receipt_raw), binding._bytes_hash(receipt_raw)),
        "receipt",
        1,
        3,
        sum(path.stat().st_size for path in root.rglob("*") if path.is_file()),
        binding._canonical_hash(receipt["request"]),
        binding._canonical_hash(receipt["provider_requests"]),
        binding._canonical_hash(receipt["root_tree"]),
    )
    return root, member_key, member_raw, identity


def test_source_root_catalog_and_declared_member_conflicts_are_distinct(tmp_path: Path) -> None:
    root, member_key, member_raw, identity = _source_root(tmp_path)
    loaded = binding._load_source_root(root, identity)
    assert loaded.member_bytes == {member_key: member_raw}

    (root / member_key).write_bytes(b'{"source":null}')
    with pytest.raises(binding.QualityBbandS1S2bPriorBalanceBindingError) as member_conflict:
        binding._load_source_root(root, identity)
    assert member_conflict.value.code is binding.QualityBbandS1S2bPriorBalanceBindingFailure.SOURCE_MEMBER_CONFLICT

    (root / member_key).write_bytes(member_raw)
    (root / "unexpected").write_bytes(b"")
    with pytest.raises(binding.QualityBbandS1S2bPriorBalanceBindingError) as catalog_conflict:
        binding._load_source_root(root, identity)
    assert catalog_conflict.value.code is binding.QualityBbandS1S2bPriorBalanceBindingFailure.CATALOG_IDENTITY_MISMATCH


def test_second_source_enumeration_rejects_racing_tree_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _member_key, _member_raw, identity = _source_root(tmp_path)
    real_read = binding._read_source_member
    calls = 0

    def racing_read(*args: object, **kwargs: object) -> bytes:
        nonlocal calls
        raw = real_read(*args, **kwargs)  # type: ignore[arg-type]
        calls += 1
        if calls == 3:
            (root / "racing-member").write_bytes(b"")
        return raw

    monkeypatch.setattr(binding, "_read_source_member", racing_read)
    with pytest.raises(binding.QualityBbandS1S2bPriorBalanceBindingError) as raised:
        binding._load_source_root(root, identity)
    assert calls == 3
    assert raised.value.code is binding.QualityBbandS1S2bPriorBalanceBindingFailure.CATALOG_IDENTITY_MISMATCH


def test_second_source_enumeration_rejects_same_size_in_place_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, member_key, member_raw, identity = _source_root(tmp_path)
    replacement = b'{"source":null}'
    assert len(replacement) == len(member_raw)
    real_read = binding._read_source_member
    calls = 0

    def racing_read(*args: object, **kwargs: object) -> bytes:
        nonlocal calls
        raw = real_read(*args, **kwargs)  # type: ignore[arg-type]
        calls += 1
        if calls == 3:
            path = root / member_key
            previous = path.stat()
            descriptor = os.open(path, os.O_WRONLY)
            try:
                assert os.pwrite(descriptor, replacement, 0) == len(replacement)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            os.utime(path, ns=(previous.st_atime_ns, previous.st_mtime_ns + 1_000_000_000))
            assert path.stat().st_size == len(member_raw)
        return raw

    monkeypatch.setattr(binding, "_read_source_member", racing_read)
    with pytest.raises(binding.QualityBbandS1S2bPriorBalanceBindingError) as raised:
        binding._load_source_root(root, identity)
    assert calls == 3
    assert raised.value.code is binding.QualityBbandS1S2bPriorBalanceBindingFailure.CATALOG_IDENTITY_MISMATCH


def test_extract_retains_all_revisions_and_update_flag_never_selects_or_orders() -> None:
    rows = [_row("000001", "0"), _row("000001", "1")]
    extracted = binding._extract_prior_rows(
        _loaded_stage_a(rows), "STAGE_A_2011", [_requirement("000001")], {"20111231"}
    )
    assert len(extracted.records) == 2
    profile = binding._dict(extracted.audit["selected_duplicate_profile"])
    assert profile["update_flag_only_duplicate_key_count"] == 1
    assert [value["source_row_index"] for value in extracted.records] == [0, 1]

    changed = copy.deepcopy(rows)
    changed[0][-1], changed[1][-1] = "9", "8"
    mutated = binding._extract_prior_rows(
        _loaded_stage_a(changed), "STAGE_A_2011", [_requirement("000001")], {"20111231"}
    )
    assert [value["source_row_index"] for value in mutated.records] == [0, 1]
    assert [value["provider_code"] for value in mutated.records] == ["000001.SZ", "000001.SZ"]


def test_duplicate_profiles_distinguish_metadata_and_economic_revisions() -> None:
    rows = [
        _row("000001", "0"), _row("000001", "1"),
        _row("000002", "0"), _row("000002", "1", f_ann_date="20120401"),
        _row("000003", "0"), _row("000003", "1", assets=11),
    ]
    extracted = binding._extract_prior_rows(
        _loaded_stage_a(rows),
        "STAGE_A_2011",
        [_requirement("000001"), _requirement("000002"), _requirement("000003")],
        {"20111231"},
    )
    profile = binding._dict(extracted.audit["selected_duplicate_profile"])
    assert profile["update_flag_only_duplicate_key_count"] == 1
    assert profile["metadata_revision_only_duplicate_key_count"] == 1
    assert profile["economic_revision_conflict_key_count"] == 1
    assert len(binding._list(extracted.audit["retained_revision_conflicts"])) == 2


def test_missing_additive_key_uses_frozen_exact_cover_reason() -> None:
    requirements = binding._PriorRequirementSets([], [], [_requirement("000001")], [], [_requirement("000001")])
    empty = binding._PriorExtraction([], [], set(), {})
    with pytest.raises(binding.QualityBbandS1S2bPriorBalanceBindingError) as raised:
        binding._validate_prior_closure(requirements, empty, empty)
    assert raised.value.code is binding.QualityBbandS1S2bPriorBalanceBindingFailure.BUNDLE_EXACT_COVER_MISMATCH
    assert raised.value.reason == "EXPECTED_MEMBER_MISSING"


def test_payload_count_failure_precedes_partition_overlap() -> None:
    key = ("balancesheet_vip", "xshe", "000001", "20111231")
    requirements = binding._PriorRequirementSets([], [], [_requirement("000001")], [], [_requirement("000001")])
    extraction = binding._PriorExtraction([], [], {key}, {})
    with pytest.raises(binding.QualityBbandS1S2bPriorBalanceBindingError) as raised:
        binding._validate_prior_closure(requirements, extraction, extraction)
    assert raised.value.code is binding.QualityBbandS1S2bPriorBalanceBindingFailure.FINANCIAL_PAYLOAD_INCOMPLETE
    assert raised.value.reason == "PRIOR_BALANCE_ENDPOINT_MISSING"


def test_global_failure_precedence_inspects_all_four_roots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []

    def fail(name: str, code: binding.QualityBbandS1S2bPriorBalanceBindingFailure):
        def loader(*_args: object) -> Any:
            calls.append(name)
            raise binding.QualityBbandS1S2bPriorBalanceBindingError(code)
        return loader

    monkeypatch.setattr(binding, "_load_stage_binding", fail("binding", binding.QualityBbandS1S2bPriorBalanceBindingFailure.FINANCIAL_PAYLOAD_INCOMPLETE))
    monkeypatch.setattr(binding, "_load_s2b", fail("s2b", binding.QualityBbandS1S2bPriorBalanceBindingFailure.BUNDLE_EXACT_COVER_MISMATCH))
    source_calls = iter((
        binding.QualityBbandS1S2bPriorBalanceBindingFailure.SOURCE_MEMBER_CONFLICT,
        binding.QualityBbandS1S2bPriorBalanceBindingFailure.CATALOG_IDENTITY_MISMATCH,
    ))

    def source_loader(*_args: object) -> Any:
        name = "s2a" if len(calls) == 2 else "stage_a"
        calls.append(name)
        raise binding.QualityBbandS1S2bPriorBalanceBindingError(next(source_calls))

    monkeypatch.setattr(binding, "_load_source_root", source_loader)
    output = tmp_path / "candidate"
    parent_fd = binding._open_output_parent(output, create=True)
    try:
        with pytest.raises(binding.QualityBbandS1S2bPriorBalanceBindingError) as raised:
            binding._build_preflighted(
                stage_binding_root=tmp_path / "binding",
                s2b_root=tmp_path / "s2b",
                s2a_root=tmp_path / "s2a",
                stage_a_root=tmp_path / "stage-a",
                output_dir=output,
                output_parent_fd=parent_fd,
            )
    finally:
        os.close(parent_fd)
    assert calls == ["binding", "s2b", "s2a", "stage_a"]
    assert raised.value.code is binding.QualityBbandS1S2bPriorBalanceBindingFailure.CATALOG_IDENTITY_MISMATCH


def _publish(output: Path, contents: dict[str, bytes]) -> None:
    parent_fd = binding._open_output_parent(output, create=True)
    try:
        binding._atomic_publish(output, contents, parent_fd)
    finally:
        os.close(parent_fd)


def _three_members() -> dict[str, bytes]:
    return {name: name.encode() for name in binding._OUTPUT_FILES}


def test_hardened_three_member_publication_is_no_clobber(tmp_path: Path) -> None:
    output = tmp_path / "candidate"
    contents = _three_members()
    _publish(output, contents)
    assert {path.name for path in output.iterdir()} == set(binding._OUTPUT_FILES)
    assert stat.S_IMODE(output.stat().st_mode) == 0o700
    assert all(stat.S_IMODE((output / name).stat().st_mode) == 0o600 for name in binding._OUTPUT_FILES)
    with pytest.raises(binding.QualityBbandS1S2bPriorBalanceBindingError) as raised:
        _publish(output, contents)
    assert raised.value.code is binding.QualityBbandS1S2bPriorBalanceBindingFailure.PUBLICATION_INTEGRITY_FAILURE
    assert {name: (output / name).read_bytes() for name in binding._OUTPUT_FILES} == contents


def test_publication_race_never_deletes_racing_destination_or_quarantined_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "candidate"
    contents = _three_members()
    real_rename = binding._rename_noreplace_at

    def racing_rename(parent_fd: int, source: str, target: str) -> None:
        os.mkdir(target, dir_fd=parent_fd)
        real_rename(parent_fd, source, target)

    monkeypatch.setattr(binding, "_rename_noreplace_at", racing_rename)
    with pytest.raises(binding.QualityBbandS1S2bPriorBalanceBindingError):
        _publish(output, contents)
    assert output.is_dir() and not any(output.iterdir())
    quarantined = list(tmp_path.glob(f".{output.name}.staging-*"))
    assert len(quarantined) == 1
    assert {path.name for path in quarantined[0].iterdir()} == set(binding._OUTPUT_FILES)


def test_publication_rejects_extra_member_injected_during_rename_without_deletion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "candidate"
    contents = _three_members()
    extra_name = "attacker-extra"
    real_rename = binding._rename_noreplace_at

    def inject_extra(parent_fd: int, source: str, target: str) -> None:
        staging_fd = os.open(source, os.O_RDONLY | os.O_DIRECTORY, dir_fd=parent_fd)
        try:
            descriptor = os.open(extra_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=staging_fd)
            os.close(descriptor)
        finally:
            os.close(staging_fd)
        real_rename(parent_fd, source, target)

    monkeypatch.setattr(binding, "_rename_noreplace_at", inject_extra)
    with pytest.raises(binding.QualityBbandS1S2bPriorBalanceBindingError) as raised:
        _publish(output, contents)
    assert raised.value.code is binding.QualityBbandS1S2bPriorBalanceBindingFailure.PUBLICATION_INTEGRITY_FAILURE
    assert {path.name for path in output.iterdir()} == set(binding._OUTPUT_FILES) | {extra_name}
    assert {name: (output / name).read_bytes() for name in binding._OUTPUT_FILES} == contents
    assert (output / extra_name).is_file()


def test_publication_rejects_parent_replacement_after_publish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent = tmp_path / "parent"
    parent.mkdir()
    output = parent / "candidate"
    displaced = tmp_path / "displaced"
    real_rename = binding._rename_noreplace_at

    def replace_parent(parent_fd: int, source: str, target: str) -> None:
        real_rename(parent_fd, source, target)
        parent.rename(displaced)
        parent.mkdir()

    monkeypatch.setattr(binding, "_rename_noreplace_at", replace_parent)
    with pytest.raises(binding.QualityBbandS1S2bPriorBalanceBindingError):
        _publish(output, _three_members())
    assert parent.is_dir() and not any(parent.iterdir())
    assert {path.name for path in (displaced / "candidate").iterdir()} == set(binding._OUTPUT_FILES)


def test_publication_rejects_output_ancestor_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ancestor = tmp_path / "ancestor"
    parent = ancestor / "parent"
    parent.mkdir(parents=True)
    output = parent / "candidate"
    displaced = tmp_path / "displaced-ancestor"
    real_rename = binding._rename_noreplace_at

    def replace_ancestor(parent_fd: int, source: str, target: str) -> None:
        real_rename(parent_fd, source, target)
        ancestor.rename(displaced)
        parent.mkdir(parents=True)

    monkeypatch.setattr(binding, "_rename_noreplace_at", replace_ancestor)
    with pytest.raises(binding.QualityBbandS1S2bPriorBalanceBindingError):
        _publish(output, _three_members())
    assert parent.is_dir() and not any(parent.iterdir())
    assert {path.name for path in (displaced / "parent" / "candidate").iterdir()} == set(binding._OUTPUT_FILES)


def test_publication_rejects_staging_pathname_substitution_without_deleting_attacker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "candidate"
    quarantine = ".original-staging"
    real_rename = binding._rename_noreplace_at

    def substitute_staging(parent_fd: int, source: str, target: str) -> None:
        os.rename(source, quarantine, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
        os.mkdir(source, 0o700, dir_fd=parent_fd)
        attacker_dir_fd = os.open(source, os.O_RDONLY | os.O_DIRECTORY, dir_fd=parent_fd)
        try:
            attacker_fd = os.open("attacker", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=attacker_dir_fd)
            os.close(attacker_fd)
        finally:
            os.close(attacker_dir_fd)
        real_rename(parent_fd, source, target)

    monkeypatch.setattr(binding, "_rename_noreplace_at", substitute_staging)
    with pytest.raises(binding.QualityBbandS1S2bPriorBalanceBindingError):
        _publish(output, _three_members())
    assert {path.name for path in output.iterdir()} == {"attacker"}
    assert {path.name for path in (tmp_path / quarantine).iterdir()} == set(binding._OUTPUT_FILES)


def test_publication_rejects_member_substitution_without_deleting_attacker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "candidate"
    real_rename = binding._rename_noreplace_at
    victim = binding._OUTPUT_FILES[1]

    def substitute_member(parent_fd: int, source: str, target: str) -> None:
        staging_fd = os.open(source, os.O_RDONLY | os.O_DIRECTORY, dir_fd=parent_fd)
        try:
            os.unlink(victim, dir_fd=staging_fd)
            attacker_fd = os.open(victim, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=staging_fd)
            try:
                os.write(attacker_fd, b"attacker")
            finally:
                os.close(attacker_fd)
        finally:
            os.close(staging_fd)
        real_rename(parent_fd, source, target)

    monkeypatch.setattr(binding, "_rename_noreplace_at", substitute_member)
    with pytest.raises(binding.QualityBbandS1S2bPriorBalanceBindingError):
        _publish(output, _three_members())
    assert (output / victim).read_bytes() == b"attacker"


_REAL_ROOT = Path("/srv/bcache-8t/ygguo/quant/artifacts/a-share-quality-bband")
_REAL_BINDING = _REAL_ROOT / "tushare-s1-s2b-stage-bindings/2017-2025/20260827/v1-candidate-02"
_REAL_S2B = _REAL_ROOT / "s2b-provisional-exact-extractions/2017-2025/20260827/v1-candidate-02"
_REAL_S2A = _REAL_ROOT / "s2a-vip-financial-source-snapshots/2012-2024/20260826/v1-candidate-02"
_REAL_STAGE_A = _REAL_ROOT / "s2c-vip-prior-balance-source-snapshots/2011/20260827/v1-candidate-01"


@pytest.mark.skipif(
    os.environ.get("QB_S1_S2B_PRIOR_BALANCE_REAL_ARTIFACT_SENTINEL") != "1",
    reason="set QB_S1_S2B_PRIOR_BALANCE_REAL_ARTIFACT_SENTINEL=1 for READY evidence",
)
def test_real_artifacts_reproduce_all_frozen_outputs_and_revision_evidence(tmp_path: Path) -> None:
    for root in (_REAL_BINDING, _REAL_S2B, _REAL_S2A, _REAL_STAGE_A):
        assert root.is_dir(), f"required READY root is missing: {root}"
    output = tmp_path / "candidate"
    manifest = binding.build_quality_bband_s1_s2b_prior_balance_binding_v1(
        stage_binding_root=_REAL_BINDING,
        s2b_root=_REAL_S2B,
        s2a_root=_REAL_S2A,
        stage_a_root=_REAL_STAGE_A,
        output_dir=output,
    )
    identities = {
        name: (len((output / name).read_bytes()), binding._bytes_hash((output / name).read_bytes()))
        for name in binding._OUTPUT_FILES
    }
    assert identities == {
        binding._OUTPUT_FILES[0]: (binding._EXPECTED_REQUIREMENTS_SIZE, binding._EXPECTED_REQUIREMENTS_HASH),
        binding._OUTPUT_FILES[1]: (binding._EXPECTED_PROVIDER_ROWS_SIZE, binding._EXPECTED_PROVIDER_ROWS_HASH),
        binding._OUTPUT_FILES[2]: (binding._EXPECTED_MANIFEST_SIZE, binding._EXPECTED_MANIFEST_HASH),
    }
    assert manifest["manifest_id"] == binding._EXPECTED_MANIFEST_ID
    assert manifest["requirements_id"] == binding._EXPECTED_REQUIREMENTS_ID
    assert manifest["flags"] == binding._FLAGS
    source_extractions = binding._dict(manifest["source_extractions"])
    assert binding._dict(source_extractions["combined"])["source_row_ids_hash"] == binding._EXPECTED_PROVIDER_ROW_IDS_HASH
    s2a = binding._dict(source_extractions["accepted_s2a"])
    stage_a = binding._dict(source_extractions["stage_a_2011"])
    assert (s2a["selected_key_count"], s2a["selected_row_count"], s2a["extra_source_row_count"]) == (850, 1698, 66209)
    assert (stage_a["selected_key_count"], stage_a["selected_row_count"], stage_a["extra_source_row_count"]) == (1995, 3979, 2456)
    s2a_selected = binding._dict(s2a["selected_duplicate_profile"])
    stage_a_selected = binding._dict(stage_a["selected_duplicate_profile"])
    stage_a_all = binding._dict(stage_a["all_source_duplicate_profile"])
    assert (
        s2a_selected["single_row_key_count"],
        s2a_selected["duplicate_key_count"],
        s2a_selected["update_flag_only_duplicate_key_count"],
        s2a_selected["economic_revision_conflict_key_count"],
    ) == (2, 848, 846, 2)
    assert (
        stage_a_selected["single_row_key_count"],
        stage_a_selected["duplicate_key_count"],
        stage_a_selected["update_flag_only_duplicate_key_count"],
        stage_a_selected["metadata_revision_only_duplicate_key_count"],
        stage_a_selected["economic_revision_conflict_key_count"],
    ) == (11, 1984, 1978, 2, 4)
    assert (
        stage_a_all["row_count"],
        stage_a_all["key_count"],
        stage_a_all["single_row_key_count"],
        stage_a_all["duplicate_key_count"],
    ) == (6435, 3283, 131, 3152)
    requirements = json.loads((output / binding._OUTPUT_FILES[0]).read_bytes())
    assert set(requirements) == {
        "type", "schema_version", "inputs", "derivation", "accounting", "hashes",
        "requirements", "requirements_id",
    }
    assert len(requirements["requirements"]) == 2845
    rows = (output / binding._OUTPUT_FILES[1]).read_bytes().splitlines()
    assert len(rows) == 5677
    assert set(json.loads(rows[0])) == {
        "type", "schema_version", "source_row_id", "source_role", "source_snapshot_id",
        "api_name", "instrument_id", "provider_code", "period", "source_member_key",
        "source_row_index", "row",
    }
    assert json.loads((output / binding._OUTPUT_FILES[2]).read_bytes()) == manifest
