from __future__ import annotations

import copy
import json
import os
import stat
from pathlib import Path
from typing import Any

import pytest

import tools.acquisition.cn_a_share_quality_bband_tushare_s1_s2b_stage_binding_v1 as binding


def _instrument(stable_key: str) -> dict[str, str]:
    return {"type": "instrument_id", "venue": "xshe", "stable_key": stable_key}


def _tiny_equivalent(monkeypatch: pytest.MonkeyPatch) -> tuple[dict[str, Any], dict[str, Any]]:
    instruments = [_instrument("000001"), _instrument("000002")]
    screens = [{"screen_date": "20200101", "instrument_ids": instruments}]
    periods = [{"screen_date": "20200101", "periods": ["20191231"]}]
    pairs = [
        {"instrument_id": instrument, "period": "20191231", "required_by_screen_dates": ["20200101"]}
        for instrument in instruments
    ]
    api_order = ["income_vip", "cashflow_vip"]
    member_keys = [[api, pair["instrument_id"], pair["period"]] for api in api_order for pair in pairs]
    hashes = {
        "screen_membership_hash": binding._canonical_hash(screens),
        "period_requirements_hash": binding._canonical_hash(periods),
        "instrument_union_hash": binding._canonical_hash(instruments),
        "expected_pairs_hash": binding._canonical_hash(pairs),
        "expected_member_keys_hash": binding._canonical_hash(member_keys),
    }
    screen_hashes = {"20200101": binding._canonical_hash(instruments)}
    monkeypatch.setattr(binding, "_EXPECTED_COUNTS", {
        "screen_count": 1,
        "instrument_union_count": 2,
        "expected_pair_count": 2,
        "expected_member_count": 4,
    })
    monkeypatch.setattr(binding, "_SCREEN_COUNTS", {"20200101": 2})
    monkeypatch.setattr(binding, "_SCREEN_HASHES", screen_hashes)
    monkeypatch.setattr(binding, "_HASHES", hashes)
    monkeypatch.setattr(binding, "_API_ORDER", tuple(api_order))
    s1 = {
        "screens": [{
            "screen_date": "20200101",
            "eligible_instrument_ids": instruments,
            "eligible_count": 2,
            "eligible_instrument_ids_hash": screen_hashes["20200101"],
        }],
        "period_requirements": periods,
        "instrument_union": instruments,
        "expected_pairs": pairs,
        "expected_member_keys": member_keys,
        "counts": {
            "screen_count": 1,
            "instrument_union_count": 2,
            "expected_pair_count": 2,
            "expected_member_key_count": 4,
        },
        "hashes": hashes,
    }
    expected = {
        "screens": screens,
        "period_requirements": periods,
        "expected_pairs": pairs,
        "derivation": {"api_order": api_order},
        "screen_count": 1,
        "instrument_union_count": 2,
        "expected_pair_count": 2,
        "expected_member_count": 4,
        **hashes,
    }
    return s1, expected


def test_strict_json_rejects_duplicate_invalid_utf8_and_nonfinite_values() -> None:
    for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":1e999}', b'"\xff"'):
        with pytest.raises(ValueError, match="strict JSON"):
            binding._strict_json(raw)


def test_exact_member_read_is_fd_relative_bounded_and_can_stream_hash(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "member.bin").write_bytes(b"abc")
    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        frozen = binding._FrozenFile("member.bin", 3, binding._bytes_hash(b"abc"))
        loaded = binding._read_exact_member(root_fd, frozen, keep_bytes=True)
        assert loaded.raw == b"abc" and loaded.sha256 == frozen.sha256
        streamed = binding._read_exact_member(root_fd, frozen, keep_bytes=False)
        assert streamed.raw is None and streamed.sha256 == frozen.sha256
        (root / "member.bin").write_bytes(b"abcd")
        with pytest.raises(ValueError, match="exact"):
            binding._read_exact_member(root_fd, frozen, keep_bytes=False)
        (root / "member.bin").unlink()
        (root / "member.bin").symlink_to(tmp_path / "outside")
        with pytest.raises(OSError):
            binding._read_exact_member(root_fd, frozen, keep_bytes=True)
    finally:
        os.close(root_fd)


def test_deep_equivalence_rejects_member_pair_and_api_order_changes(monkeypatch: pytest.MonkeyPatch) -> None:
    s1, expected = _tiny_equivalent(monkeypatch)
    binding._validate_equivalence(s1, expected)

    changed_member = copy.deepcopy(expected)
    changed_member["screens"][0]["instrument_ids"].reverse()
    with pytest.raises(binding.QualityBbandTushareS1S2bBindingError) as member_error:
        binding._validate_equivalence(s1, changed_member)
    assert member_error.value.code is binding.QualityBbandTushareS1S2bBindingFailure.EXPECTED_SET_EQUIVALENCE_MISMATCH

    changed_pairs = copy.deepcopy(expected)
    changed_pairs["expected_pairs"].reverse()
    with pytest.raises(binding.QualityBbandTushareS1S2bBindingError) as pair_error:
        binding._validate_equivalence(s1, changed_pairs)
    assert pair_error.value.code is binding.QualityBbandTushareS1S2bBindingFailure.EXPECTED_SET_EQUIVALENCE_MISMATCH

    changed_api = copy.deepcopy(expected)
    changed_api["derivation"]["api_order"].reverse()
    with pytest.raises(binding.QualityBbandTushareS1S2bBindingError) as api_error:
        binding._validate_equivalence(s1, changed_api)
    assert api_error.value.code is binding.QualityBbandTushareS1S2bBindingFailure.EXPECTED_SET_EQUIVALENCE_MISMATCH


def test_authority_rebinding_failure_precedes_equivalence() -> None:
    s1: dict[str, object] = {
        "flags": {"owner_approved_tushare_authority": True, "formal_s1_qualified": True}
    }
    expected: dict[str, object] = {
        "authority_level": "SOURCE_BOUNDED_PROVISIONAL",
        "formal_s1_qualified": True,
    }
    extraction: dict[str, object] = {
        "formal_s1_qualified": False,
        "limitations": ["FORMAL_S1_FALSE"],
    }
    with pytest.raises(binding.QualityBbandTushareS1S2bBindingError) as raised:
        binding._validate_authority(s1, expected, extraction)
    assert raised.value.code is binding.QualityBbandTushareS1S2bBindingFailure.AUTHORITY_REBINDING_MISMATCH


def test_frozen_manifest_is_exact_7323_bytes() -> None:
    source = {
        "snapshot_id": "sha256:b5b7a9243439146181ef07acd07c09e79d16f605bc6cfdc3148746e64359e198",
        "content_tree_hash": "sha256:5533ce876c38ff320b69ca876dff57af763168d654f82142e9c53c90ecca2418",
        "provenance_hash": "sha256:953aecfb488562177a51392283d8dace326470041cc0594d8982fb3482849c36",
        "snapshot_file_sha256": "sha256:b1c8b0edf3f27860c69a1996f6e22360f578c44d518920ec395839adf6ac6235",
        "receipt_file_sha256": "sha256:ee1b32d5ea28a7c923f48676b9e4e05fc58dcd9eaef578a59280e8952a30c722",
    }
    annual = {
        "snapshot_id": "sha256:22585fa4c2070d87544f0ba977be757770aeeaad5bead30188317c1794680ee8",
        "content_tree_hash": "sha256:7e4046b2ffc13993de8ab33ddbe4410aef2f464d8c16b19000998acbb20cbb9e",
        "provenance_hash": "sha256:7bb6d65da4702e6c34649cf52dc0285fb2e2115246fca0e978b434da6176af22",
        "snapshot_file_sha256": "sha256:ed7f01abb90c0b937078beb39739202ec80070e61c26e6d624dd70f8a6181ad1",
        "receipt_file_sha256": "sha256:9eab20190ae05c4a49a8763ad77cfc9d1ed874c7c56e2258f3a595e2a8b7c9d6",
    }
    s1: dict[str, object] = {"inputs": {"s0": source, "annual_roster": annual}}
    extraction: dict[str, object] = {"inputs": {"s0": source, "annual_roster": annual}}
    manifest = binding._build_manifest(s1, extraction)
    raw = binding._canonical_json(manifest).encode()
    assert manifest["manifest_id"] == binding._EXPECTED_MANIFEST_ID
    assert len(raw) == binding._EXPECTED_OUTPUT_SIZE == 7323
    assert binding._bytes_hash(raw) == binding._EXPECTED_OUTPUT_HASH
    assert not raw.endswith(b"\n")


def _publish(output: Path, content: bytes) -> None:
    parent_fd = binding._open_output_parent(output, create=True)
    try:
        binding._atomic_publish(output, content, parent_fd)
    finally:
        os.close(parent_fd)


def test_secure_output_parent_traversal_rejects_symlinks_and_dotdot_at_priority_one(
    tmp_path: Path,
) -> None:
    s1_root = tmp_path / "s1"
    s2b_root = tmp_path / "s2b"
    outside = tmp_path / "outside"
    for directory in (s1_root, s2b_root, outside):
        directory.mkdir()
    (tmp_path / "linked").symlink_to(outside, target_is_directory=True)
    for output in (tmp_path / "linked/candidate", tmp_path / "safe/../candidate"):
        with pytest.raises(binding.QualityBbandTushareS1S2bBindingError) as raised:
            binding.build_quality_bband_tushare_s1_s2b_stage_binding_v1(
                s1_root=s1_root,
                s2b_root=s2b_root,
                output_dir=output,
            )
        assert raised.value.code is binding.QualityBbandTushareS1S2bBindingFailure.INPUT_TYPE_SCHEMA_OR_PATH


def test_preflight_rejects_output_inside_input_without_creating_parent(tmp_path: Path) -> None:
    s1_root = tmp_path / "s1"
    s2b_root = tmp_path / "s2b"
    s1_root.mkdir()
    s2b_root.mkdir()
    output = s1_root / "new" / "candidate"
    with pytest.raises(binding.QualityBbandTushareS1S2bBindingError) as raised:
        binding.build_quality_bband_tushare_s1_s2b_stage_binding_v1(
            s1_root=s1_root,
            s2b_root=s2b_root,
            output_dir=output,
        )
    assert raised.value.code is binding.QualityBbandTushareS1S2bBindingFailure.INPUT_TYPE_SCHEMA_OR_PATH
    assert not output.parent.exists()


def test_global_priority_one_schema_error_precedes_other_input_identity_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "candidate"
    parent_fd = binding._open_output_parent(output, create=True)
    calls: list[str] = []

    def load_s1(_root: Path) -> tuple[dict[str, object], binding._ReadMember]:
        calls.append("s1")
        raise binding._ArtifactIdentityMismatch("S1 size")

    def load_s2b(_root: Path) -> tuple[object, ...]:
        calls.append("s2b")
        raise KeyError("derivation.api_order")

    monkeypatch.setattr(binding, "_load_s1", load_s1)
    monkeypatch.setattr(binding, "_load_s2b", load_s2b)
    try:
        with pytest.raises(binding.QualityBbandTushareS1S2bBindingError) as raised:
            binding._build_preflighted(
                s1_root=tmp_path / "s1",
                s2b_root=tmp_path / "s2b",
                output_dir=output,
                output_parent_fd=parent_fd,
            )
    finally:
        os.close(parent_fd)
    assert calls == ["s1", "s2b"]
    assert raised.value.code is binding.QualityBbandTushareS1S2bBindingFailure.INPUT_TYPE_SCHEMA_OR_PATH


def test_same_s2b_root_later_priority_one_error_beats_earlier_identity_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "s2b"
    root.mkdir()
    for name in binding._S2B_FILES:
        (root / name).write_bytes(b"")
    calls: list[str] = []

    def read_member(
        _root_fd: int,
        frozen: binding._FrozenFile,
        *,
        keep_bytes: bool,
    ) -> binding._ReadMember:
        calls.append(frozen.name)
        if frozen.name == "provisional-expected-set.json":
            raise binding._ArtifactIdentityMismatch("early identity mismatch")
        if frozen.name == "provider-rows.jsonl":
            raise OSError("later nonregular/symlink member")
        return binding._ReadMember(b"{}" if keep_bytes else None, 2, binding._bytes_hash(b"{}"))

    monkeypatch.setattr(binding, "_read_exact_member", read_member)
    monkeypatch.setattr(binding, "_parse_official_coverage", lambda _raw: {})
    monkeypatch.setattr(binding, "_parse_extraction_manifest", lambda _raw: {})
    with pytest.raises(OSError, match="later nonregular"):
        binding._load_s2b(root)
    assert calls == list(binding._S2B_FILES)


def test_atomic_publication_is_no_clobber_and_preserves_racing_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "candidate"
    content = b"frozen"
    _publish(output, content)
    assert (output / binding._OUTPUT_NAME).read_bytes() == content
    assert stat.S_IMODE(output.stat().st_mode) == 0o700
    assert stat.S_IMODE((output / binding._OUTPUT_NAME).stat().st_mode) == 0o600
    with pytest.raises(binding.QualityBbandTushareS1S2bBindingError) as existing:
        _publish(output, content)
    assert existing.value.code is binding.QualityBbandTushareS1S2bBindingFailure.PUBLICATION_INTEGRITY_FAILURE
    assert (output / binding._OUTPUT_NAME).read_bytes() == content

    raced = tmp_path / "raced"
    real_rename = binding._rename_noreplace_at

    def racing_rename(parent_fd: int, source_name: str, target_name: str) -> None:
        os.mkdir(target_name, dir_fd=parent_fd)
        real_rename(parent_fd, source_name, target_name)

    monkeypatch.setattr(binding, "_rename_noreplace_at", racing_rename)
    with pytest.raises(binding.QualityBbandTushareS1S2bBindingError):
        _publish(raced, content)
    assert raced.is_dir() and not any(raced.iterdir())
    staging = list(tmp_path.glob(f".{raced.name}.staging-*"))
    assert len(staging) == 1
    assert (staging[0] / binding._OUTPUT_NAME).read_bytes() == content


def test_atomic_publication_rejects_parent_replacement(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    parent = tmp_path / "parent"
    parent.mkdir()
    output = parent / "candidate"
    displaced = tmp_path / "displaced-parent"
    real_rename = binding._rename_noreplace_at

    def replace_parent(parent_fd: int, source_name: str, target_name: str) -> None:
        real_rename(parent_fd, source_name, target_name)
        parent.rename(displaced)
        parent.mkdir()

    monkeypatch.setattr(binding, "_rename_noreplace_at", replace_parent)
    with pytest.raises(binding.QualityBbandTushareS1S2bBindingError) as raised:
        _publish(output, b"frozen")
    assert raised.value.code is binding.QualityBbandTushareS1S2bBindingFailure.PUBLICATION_INTEGRITY_FAILURE
    assert parent.is_dir() and not any(parent.iterdir())
    assert (displaced / "candidate" / binding._OUTPUT_NAME).read_bytes() == b"frozen"


def test_atomic_publication_rejects_ancestor_replacement(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ancestor = tmp_path / "ancestor"
    parent = ancestor / "parent"
    parent.mkdir(parents=True)
    output = parent / "candidate"
    displaced = tmp_path / "displaced-ancestor"
    real_rename = binding._rename_noreplace_at

    def replace_ancestor(parent_fd: int, source_name: str, target_name: str) -> None:
        real_rename(parent_fd, source_name, target_name)
        ancestor.rename(displaced)
        parent.mkdir(parents=True)

    monkeypatch.setattr(binding, "_rename_noreplace_at", replace_ancestor)
    with pytest.raises(binding.QualityBbandTushareS1S2bBindingError) as raised:
        _publish(output, b"frozen")
    assert raised.value.code is binding.QualityBbandTushareS1S2bBindingFailure.PUBLICATION_INTEGRITY_FAILURE
    assert parent.is_dir() and not any(parent.iterdir())
    assert (displaced / "parent/candidate" / binding._OUTPUT_NAME).read_bytes() == b"frozen"


def test_atomic_publication_never_deletes_directory_substituted_between_mkdir_and_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "candidate"
    real_open = os.open
    substituted = False

    def racing_open(path: object, flags: int, *args: object, **kwargs: object) -> int:
        nonlocal substituted
        dir_fd = kwargs.get("dir_fd")
        if (
            not substituted
            and isinstance(path, str)
            and path.startswith(f".{output.name}.staging-")
            and flags & os.O_DIRECTORY
            and isinstance(dir_fd, int)
        ):
            substituted = True
            os.rename(path, path + ".original", src_dir_fd=dir_fd, dst_dir_fd=dir_fd)
            os.mkdir(path, 0o700, dir_fd=dir_fd)
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(binding.os, "open", racing_open)
    with pytest.raises(binding.QualityBbandTushareS1S2bBindingError) as raised:
        _publish(output, b"frozen")
    assert raised.value.code is binding.QualityBbandTushareS1S2bBindingFailure.PUBLICATION_INTEGRITY_FAILURE
    attacker_dirs = [
        path
        for path in tmp_path.glob(f".{output.name}.staging-*")
        if not path.name.endswith(".original")
    ]
    assert len(attacker_dirs) == 1
    assert not any(attacker_dirs[0].iterdir())


def test_atomic_publication_rejects_staging_inode_substitution_without_deleting_attacker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "candidate"
    real_rename = binding._rename_noreplace_at

    def substitute(parent_fd: int, source_name: str, target_name: str) -> None:
        os.rename(source_name, source_name + ".original", src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
        os.mkdir(source_name, dir_fd=parent_fd)
        real_rename(parent_fd, source_name, target_name)

    monkeypatch.setattr(binding, "_rename_noreplace_at", substitute)
    with pytest.raises(binding.QualityBbandTushareS1S2bBindingError) as raised:
        _publish(output, b"frozen")
    assert raised.value.code is binding.QualityBbandTushareS1S2bBindingFailure.PUBLICATION_INTEGRITY_FAILURE
    assert output.is_dir() and not any(output.iterdir())
    originals = list(tmp_path.glob(f".{output.name}.staging-*.original"))
    assert len(originals) == 1
    assert (originals[0] / binding._OUTPUT_NAME).read_bytes() == b"frozen"


def test_atomic_publication_rejects_member_substitution_without_deleting_attacker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "candidate"
    real_rename = binding._rename_noreplace_at

    def substitute_member(parent_fd: int, source_name: str, target_name: str) -> None:
        staging_fd = os.open(source_name, os.O_RDONLY | os.O_DIRECTORY, dir_fd=parent_fd)
        try:
            os.unlink(binding._OUTPUT_NAME, dir_fd=staging_fd)
            attacker_fd = os.open(
                binding._OUTPUT_NAME,
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

    monkeypatch.setattr(binding, "_rename_noreplace_at", substitute_member)
    with pytest.raises(binding.QualityBbandTushareS1S2bBindingError) as raised:
        _publish(output, b"frozen")
    assert raised.value.code is binding.QualityBbandTushareS1S2bBindingFailure.PUBLICATION_INTEGRITY_FAILURE
    assert (output / binding._OUTPUT_NAME).read_bytes() == b"attacker"


_REAL_ROOT = Path("/srv/bcache-8t/ygguo/quant/artifacts/a-share-quality-bband")
_REAL_S1 = _REAL_ROOT / "tushare-s1-structural-manifests/2017-2025/20260827/v1-candidate-01"
_REAL_S2B = _REAL_ROOT / "s2b-provisional-exact-extractions/2017-2025/20260827/v1-candidate-02"


@pytest.mark.skipif(
    os.environ.get("QB_TUSHARE_S1_S2B_REAL_ARTIFACT_SENTINEL") != "1",
    reason="set QB_TUSHARE_S1_S2B_REAL_ARTIFACT_SENTINEL=1 for required READY evidence",
)
def test_real_accepted_artifacts_reproduce_frozen_binding_and_failure_sentinels(tmp_path: Path) -> None:
    assert _REAL_S1.is_dir(), f"required READY S1 root is missing: {_REAL_S1}"
    assert _REAL_S2B.is_dir(), f"required READY S2B root is missing: {_REAL_S2B}"
    output = tmp_path / "binding"
    manifest = binding.build_quality_bband_tushare_s1_s2b_stage_binding_v1(
        s1_root=_REAL_S1,
        s2b_root=_REAL_S2B,
        output_dir=output,
    )
    raw = (output / binding._OUTPUT_NAME).read_bytes()
    assert manifest["manifest_id"] == binding._EXPECTED_MANIFEST_ID
    assert (len(raw), binding._bytes_hash(raw)) == (
        binding._EXPECTED_OUTPUT_SIZE,
        binding._EXPECTED_OUTPUT_HASH,
    )
    classification = binding._dict(manifest["classification_replacement"])
    assert classification["data_fields_rewritten"] == []
    assert classification["original_artifact_bytes_modified"] is False
    assert manifest["flags"] == binding._FLAGS
    assert json.loads(raw) == manifest

    s1, s1_member = binding._load_s1(_REAL_S1)
    expected, official, extraction, members = binding._load_s2b(_REAL_S2B)

    changed_s1 = dict(s1)
    changed_s1["manifest_id"] = "sha256:" + "0" * 64
    with pytest.raises(binding.QualityBbandTushareS1S2bBindingError) as s1_error:
        binding._validate_artifact_identities(
            changed_s1, s1_member, expected, official, extraction, members
        )
    assert s1_error.value.code is binding.QualityBbandTushareS1S2bBindingFailure.ARTIFACT_IDENTITY_MISMATCH

    changed_expected = dict(expected)
    changed_expected["expected_set_id"] = "sha256:" + "0" * 64
    with pytest.raises(binding.QualityBbandTushareS1S2bBindingError) as expected_error:
        binding._validate_artifact_identities(
            s1, s1_member, changed_expected, official, extraction, members
        )
    assert expected_error.value.code is binding.QualityBbandTushareS1S2bBindingFailure.ARTIFACT_IDENTITY_MISMATCH

    changed_members = dict(members)
    provider = members["provider-rows.jsonl"]
    changed_members["provider-rows.jsonl"] = binding._ReadMember(
        provider.raw,
        provider.byte_count,
        "sha256:" + "0" * 64,
    )
    with pytest.raises(binding.QualityBbandTushareS1S2bBindingError) as provider_error:
        binding._validate_s2b_closure(expected, official, extraction, changed_members)
    assert provider_error.value.code is binding.QualityBbandTushareS1S2bBindingFailure.S2B_CLOSURE_OR_PAYLOAD_MISMATCH

    for key_name in ("o_member_keys", "n_member_keys"):
        changed_official = copy.deepcopy(official)
        changed_keys = binding._list(changed_official[key_name])
        changed_key = binding._list(changed_keys[0])
        binding._dict(changed_key[1])["stable_key"] = "999999"
        with pytest.raises(binding.QualityBbandTushareS1S2bBindingError) as key_error:
            binding._validate_s2b_closure(expected, changed_official, extraction, members)
        assert key_error.value.code is binding.QualityBbandTushareS1S2bBindingFailure.S2B_CLOSURE_OR_PAYLOAD_MISMATCH
