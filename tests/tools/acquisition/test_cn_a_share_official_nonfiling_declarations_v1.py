from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest
from crypto_quant_bundle_builder import (
    RawSourceMember,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
)
from crypto_quant_domain import canonical_bytes

from tools.acquisition import cn_a_share_official_nonfiling_declarations_v1 as subject
from tools.acquisition._common import AcquisitionError


def _source_root(root: Path, specs: tuple[subject.DocumentSpec, ...]):
    members = []
    for index, spec in enumerate(specs):
        source = f"official source {spec.member_key}".encode()
        acquired_at = max(spec.published_at_epoch_nanoseconds + 10, 1_800_000_000_000_000_000 + index)
        members.append(RawSourceMember(spec.member_key, source, "0644", acquired_at, None))
        path = root / spec.member_key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(source)
    outcome = freeze_source_snapshot(
        members=tuple(members),
        provenance=SourceSnapshotProvenance(
            vendor_key="official.test",
            source_key="nonfiling.fixture",
            license_ref="test.fixture",
            retention_policy_ref="immutable.fixture",
        ),
    )
    assert outcome.snapshot is not None
    snapshot = outcome.snapshot.to_canonical_dict()
    root.mkdir(parents=True, exist_ok=True)
    (root / "source-snapshot.json").write_text(json.dumps(snapshot))
    (root / "acquisition-receipt.json").write_text(json.dumps({"snapshot": snapshot}))
    return outcome.snapshot


def _boundary_root(root: Path):
    rows = [
        [exchange, day, is_open, previous]
        for exchange in ("SSE", "SZSE")
        for day, is_open, previous in (
            ("20260430", 1, "20260429"),
            ("20260501", 0, "20260430"),
            ("20260502", 0, "20260430"),
            ("20260503", 0, "20260430"),
            ("20260504", 0, "20260430"),
            ("20260505", 0, "20260430"),
            ("20260506", 1, "20260430"),
            ("20260507", 1, "20260506"),
            ("20260508", 1, "20260507"),
            ("20260509", 0, "20260508"),
            ("20260510", 0, "20260508"),
        )
    ]
    files = {
        subject._CALENDAR_MEMBER_KEYS[0]: canonical_bytes({"data": {"items": rows[:11]}}),
        subject._CALENDAR_MEMBER_KEYS[1]: canonical_bytes({"data": {"items": rows[11:]}}),
        "response/neeq/disclosure-search/400267-20250701-20250810-v1.json": b"{}",
        subject._LINEAGE_MEMBER_KEY: b"%PDF-lineage-fixture",
    }
    members = []
    for index, (member_key, source) in enumerate(files.items()):
        path = root / member_key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(source)
        members.append(
            RawSourceMember(
                member_key,
                source,
                "0644",
                1_800_000_000_000_000_100 + index,
                None,
            )
        )
    outcome = freeze_source_snapshot(
        members=tuple(members),
        provenance=SourceSnapshotProvenance(
            vendor_key="official.test",
            source_key="boundary.lineage.fixture",
            license_ref="test.fixture",
            retention_policy_ref="immutable.fixture",
        ),
    )
    assert outcome.snapshot is not None
    snapshot = outcome.snapshot.to_canonical_dict()
    (root / "source-snapshot.json").write_text(json.dumps(snapshot))
    (root / "acquisition-receipt.json").write_text(
        json.dumps({"snapshot": snapshot, "selected_neeq_fact": subject._LINEAGE_METADATA_FACT})
    )
    return outcome.snapshot


def _roots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, Path]:
    parent = tmp_path / "parent"
    supplement = tmp_path / "supplement"
    boundary = tmp_path / "boundary"
    parent_specs = tuple(
        document
        for declaration in subject._DECLARATIONS
        for document in (declaration.initial, declaration.terminal)
        if document.root == "parent"
    )
    supplement_specs = tuple(
        document
        for declaration in subject._DECLARATIONS
        for document in (declaration.initial, declaration.terminal)
        if document.root == "supplement"
    )
    parent_snapshot = _source_root(parent, parent_specs)
    supplement_snapshot = _source_root(supplement, supplement_specs)
    boundary_snapshot = _boundary_root(boundary)
    monkeypatch.setattr(subject, "PARENT_SNAPSHOT_ID", parent_snapshot.snapshot_id)
    monkeypatch.setattr(subject, "SUPPLEMENT_SNAPSHOT_ID", supplement_snapshot.snapshot_id)
    monkeypatch.setattr(subject, "PARENT_RAW_MEMBER_COUNT", len(parent_snapshot.members))
    monkeypatch.setattr(subject, "PARENT_RAW_BYTES", sum(value.byte_count for value in parent_snapshot.members))
    monkeypatch.setattr(subject, "SUPPLEMENT_RAW_MEMBER_COUNT", len(supplement_snapshot.members))
    monkeypatch.setattr(subject, "SUPPLEMENT_RAW_BYTES", sum(value.byte_count for value in supplement_snapshot.members))
    monkeypatch.setattr(subject, "BOUNDARY_LINEAGE_SNAPSHOT_ID", boundary_snapshot.snapshot_id)
    monkeypatch.setattr(subject, "BOUNDARY_LINEAGE_RAW_MEMBER_COUNT", len(boundary_snapshot.members))
    monkeypatch.setattr(subject, "BOUNDARY_LINEAGE_RAW_BYTES", sum(value.byte_count for value in boundary_snapshot.members))
    return parent, supplement, boundary


def test_real_spec_is_exact_seven_issuer_and_twenty_one_member_cover() -> None:
    assert [value.provider_code for value in subject._DECLARATIONS] == [
        "000693.SZ",
        "600090.SH",
        "600146.SH",
        "000038.SZ",
        "000976.SZ",
        "000622.SZ",
        "601028.SH",
    ]
    assert len({doc.member_key for item in subject._DECLARATIONS for doc in (item.initial, item.terminal)}) == 14
    assert all(item.active_interval_end_epoch_nanoseconds > item.deadline_boundary_at_epoch_nanoseconds for item in subject._DECLARATIONS)
    predeadline = {
        item.provider_code: item.initial.authority.value
        for item in subject._DECLARATIONS
        if item.initial.evidence_kind.value == "PREDEADLINE_DEFINITIVE_INABILITY"
    }
    assert predeadline == {
        "000693.SZ": "ISSUER",
        "600146.SH": "SSE",
        "000038.SZ": "ISSUER",
        "000976.SZ": "ISSUER",
        "601028.SH": "ISSUER",
    }


def test_builds_seven_real_shape_declarations_atomically(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    parent, supplement, boundary = _roots(tmp_path, monkeypatch)
    output = tmp_path / "output"
    receipt = subject.build_official_nonfiling_declarations_v1(
        parent_root=parent,
        supplement_root=supplement,
        boundary_lineage_root=boundary,
        output_dir=output,
    )
    files = [value for value in output.rglob("*") if value.is_file()]
    assert len(files) == 29
    assert all(stat.S_IMODE(value.stat().st_mode) == 0o600 for value in files)
    assert receipt["declaration_count"] == 7
    assert receipt["covered_member_count"] == 21
    assert receipt["official_evidence_reviewed"] is True
    assert receipt["calendar_boundary_reviewed"] is True
    assert receipt["issuer_lineage_reviewed"] is True
    assert receipt["nonfiling_declarations_constructed"] is True
    assert receipt["formal_s1_qualified"] is False
    assert receipt["s2b_exact_cover_complete"] is False
    assert receipt["strategy_target_authorized"] is False
    assert receipt["deployment_authorized"] is False
    assert len({row["declaration_id"] for row in receipt["declarations"]}) == 7
    assert all(
        key[1]["type"] == "instrument_id"
        and key[1]["venue"] in {"xshe", "xshg"}
        and len(key[1]["stable_key"]) == 6
        for key in receipt["covered_member_keys"]
    )
    assert (output / "declaration-receipt.json").read_bytes() == canonical_bytes(receipt)
    for row in receipt["declarations"]:
        declaration_bytes = (output / row["declaration_path"]).read_bytes()
        declaration = json.loads(declaration_bytes)
        assert declaration_bytes == canonical_bytes(declaration)
        assert declaration["declaration_id"] == row["declaration_id"]
        assert declaration["filing_status"] == "NOT_FILED_BY_STATUTORY_DEADLINE"
        assert declaration["covered_api_names"] == ["income_vip", "balancesheet_vip", "cashflow_vip"]
        assert declaration["terminal_confirmation"] == "NOT_FILED_THROUGH_LISTING_TERMINATION"
    latest = [
        json.loads((output / row["declaration_path"]).read_bytes())
        for row in receipt["declarations"]
        if row["provider_code"] in {"000622.SZ", "601028.SH"}
    ]
    assert all(value["active_interval_end"]["epoch_nanoseconds"] == 1778031000000000000 for value in latest)
    assert all(
        value["initial_availability"]["calendar_authority_id"]
        == subject.HISTORICAL_CALENDAR_AUTHORITY_ID
        and value["terminal_availability"]["calendar_authority_id"]
        == subject.HISTORICAL_CALENDAR_AUTHORITY_ID
        for value in latest
    )
    assert (
        receipt["boundary_lineage_review"]["calendar_source_snapshot_id"]
        == subject.BOUNDARY_LINEAGE_SNAPSHOT_ID
    )


def test_self_consistent_forged_root_fails_reconstruction(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    parent, supplement, boundary = _roots(tmp_path, monkeypatch)
    first = subject._DECLARATIONS[0].initial.member_key
    original = (parent / first).read_bytes()
    tampered = b"x" * len(original)
    (parent / first).write_bytes(tampered)
    snapshot_path = parent / "source-snapshot.json"
    snapshot = json.loads(snapshot_path.read_bytes())
    member = next(value for value in snapshot["members"] if value["member_key"] == first)
    member["byte_count"] = len(tampered)
    member["content_hash"] = subject._common.sha256(tampered)
    snapshot_path.write_text(json.dumps(snapshot))
    (parent / "acquisition-receipt.json").write_text(json.dumps({"snapshot": snapshot}))
    output = tmp_path / "output"
    with pytest.raises(AcquisitionError, match="reconstruction mismatch"):
        subject.build_official_nonfiling_declarations_v1(
            parent_root=parent,
            supplement_root=supplement,
            boundary_lineage_root=boundary,
            output_dir=output,
        )
    assert not output.exists()


def test_unsafe_snapshot_member_path_is_rejected_before_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    parent, supplement, boundary = _roots(tmp_path, monkeypatch)
    snapshot_path = parent / "source-snapshot.json"
    snapshot = json.loads(snapshot_path.read_bytes())
    snapshot["members"][0]["member_key"] = "../../outside.pdf"
    snapshot_path.write_text(json.dumps(snapshot))
    (parent / "acquisition-receipt.json").write_text(json.dumps({"snapshot": snapshot}))
    output = tmp_path / "output"
    with pytest.raises(AcquisitionError, match="member identity mismatch"):
        subject.build_official_nonfiling_declarations_v1(
            parent_root=parent,
            supplement_root=supplement,
            boundary_lineage_root=boundary,
            output_dir=output,
        )
    assert not output.exists()


@pytest.mark.parametrize("kind", ["oversized", "directory"])
def test_nonregular_or_wrong_size_member_is_rejected_before_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    parent, supplement, boundary = _roots(tmp_path, monkeypatch)
    member = parent / subject._DECLARATIONS[0].initial.member_key
    if kind == "oversized":
        member.write_bytes(member.read_bytes() + b"x")
    else:
        member.unlink()
        member.mkdir()
    output = tmp_path / "output"
    with pytest.raises(AcquisitionError, match="member identity mismatch"):
        subject.build_official_nonfiling_declarations_v1(
            parent_root=parent,
            supplement_root=supplement,
            boundary_lineage_root=boundary,
            output_dir=output,
        )
    assert not output.exists()


@pytest.mark.parametrize("kind", ["root", "metadata"])
def test_symlinked_input_is_rejected_before_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    parent, supplement, boundary = _roots(tmp_path, monkeypatch)
    if kind == "root":
        linked = tmp_path / "parent-link"
        linked.symlink_to(parent, target_is_directory=True)
        parent = linked
    else:
        snapshot = parent / "source-snapshot.json"
        target = tmp_path / "snapshot-copy.json"
        target.write_bytes(snapshot.read_bytes())
        snapshot.unlink()
        snapshot.symlink_to(target)
    output = tmp_path / "output"
    with pytest.raises(AcquisitionError, match="root is unreadable"):
        subject.build_official_nonfiling_declarations_v1(
            parent_root=parent,
            supplement_root=supplement,
            boundary_lineage_root=boundary,
            output_dir=output,
        )
    assert not output.exists()


def test_publication_failure_leaves_no_partial_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    parent, supplement, boundary = _roots(tmp_path, monkeypatch)
    output = tmp_path / "output"

    def fail_rename(_source: Path, _target: Path) -> None:
        raise OSError("injected publication failure")

    monkeypatch.setattr(subject.os, "rename", fail_rename)
    with pytest.raises(AcquisitionError, match="publication failed"):
        subject.build_official_nonfiling_declarations_v1(
            parent_root=parent,
            supplement_root=supplement,
            boundary_lineage_root=boundary,
            output_dir=output,
        )
    assert not output.exists()
    assert not (output.parent / f".{output.name}.staging-nonfiling-v1").exists()


def test_existing_output_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    parent, supplement, boundary = _roots(tmp_path, monkeypatch)
    output = tmp_path / "output"
    output.mkdir()
    with pytest.raises(AcquisitionError, match="output path is not safe"):
        subject.build_official_nonfiling_declarations_v1(
            parent_root=parent,
            supplement_root=supplement,
            boundary_lineage_root=boundary,
            output_dir=output,
        )
