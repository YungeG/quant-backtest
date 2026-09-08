from __future__ import annotations

import stat
from pathlib import Path

import pytest
from crypto_quant_backtest import CanonicalPublicationFailureCode
from crypto_quant_backtest._durable_rebuild import (
    _MANIFEST_PATH,
    _VERIFICATION_PATH,
    DurableRebuildError,
    DurableRebuildPublisherV1,
)
from crypto_quant_backtest._publication import RunPublicationLock

from tests.runtime.durable_rebuild.test_verification import _proof_fixture


def _publish(tmp_path: Path):
    fixture = _proof_fixture(tmp_path)
    publisher = DurableRebuildPublisherV1(
        root=fixture["root"], artifact_reader=fixture["store"]
    )
    lock = RunPublicationLock(
        root=fixture["root"],
        semantic_run_id=fixture["verification"].semantic_run_id,
    )
    lock.__enter__()
    try:
        observation = publisher.publish(
            lock=lock, verification=fixture["verification"]
        )
    finally:
        lock.__exit__(None, None, None)
    return fixture, publisher, observation


def test_publication_has_exact_layout_hashes_modes_and_no_self_entry(tmp_path: Path) -> None:
    fixture, _, observation = _publish(tmp_path)
    manifest = observation.publication_manifest
    final = (
        fixture["root"]
        / "runs"
        / fixture["verification"].semantic_run_id
        / "rebuild-proofs"
        / manifest.proof_id
    )
    assert {path.name for path in final.iterdir()} == {
        _VERIFICATION_PATH,
        _MANIFEST_PATH,
    }
    assert stat.S_IMODE(final.stat().st_mode) == 0o555
    assert all(stat.S_IMODE(path.stat().st_mode) == 0o444 for path in final.iterdir())
    assert [entry.relative_path for entry in manifest.artifacts] == [
        _VERIFICATION_PATH
    ]
    assert manifest.deployment_authorized is False
    assert manifest.proof_id.startswith("proof_")
    assert manifest.publication_id.startswith("proof_publication_")
    entry = manifest.artifacts[0]
    assert entry.content_hash == observation.verification_ref.content_hash
    assert entry.source_hash == observation.verification_source_hash
    assert entry.byte_count == len(observation.verification_source_bytes)


def test_idempotent_exact_final_returns_same_observation_and_bytes(tmp_path: Path) -> None:
    fixture, publisher, first = _publish(tmp_path)
    final = (
        fixture["root"]
        / "runs"
        / fixture["verification"].semantic_run_id
        / "rebuild-proofs"
        / first.publication_manifest.proof_id
    )
    before = {path.name: path.read_bytes() for path in final.iterdir()}
    with RunPublicationLock(
        root=fixture["root"],
        semantic_run_id=fixture["verification"].semantic_run_id,
    ) as lock:
        second = publisher.publish(lock=lock, verification=fixture["verification"])
    assert second == first
    assert {path.name: path.read_bytes() for path in final.iterdir()} == before


def test_structural_constructor_bypass_maps_to_publication_verification_failed(
    tmp_path: Path,
) -> None:
    fixture = _proof_fixture(tmp_path)
    publisher = DurableRebuildPublisherV1(
        root=fixture["root"], artifact_reader=fixture["store"]
    )
    object.__setattr__(fixture["verification"], "claim", "caller_attested")

    with RunPublicationLock(
        root=fixture["root"],
        semantic_run_id=fixture["verification"].semantic_run_id,
    ) as lock, pytest.raises(DurableRebuildError) as error:
        publisher.publish(lock=lock, verification=fixture["verification"])

    assert (
        error.value.code
        is CanonicalPublicationFailureCode.PUBLICATION_VERIFICATION_FAILED
    )


def test_malformed_existing_final_maps_to_publication_verification_failed(
    tmp_path: Path,
) -> None:
    fixture, publisher, observation = _publish(tmp_path)
    final = (
        fixture["root"]
        / "runs"
        / fixture["verification"].semantic_run_id
        / "rebuild-proofs"
        / observation.publication_manifest.proof_id
    )
    (final / _VERIFICATION_PATH).chmod(0o644)

    with RunPublicationLock(
        root=fixture["root"],
        semantic_run_id=fixture["verification"].semantic_run_id,
    ) as lock, pytest.raises(DurableRebuildError) as error:
        publisher.publish(lock=lock, verification=fixture["verification"])

    assert (
        error.value.code
        is CanonicalPublicationFailureCode.PUBLICATION_VERIFICATION_FAILED
    )


def test_requires_exact_held_run_bound_lock(tmp_path: Path) -> None:
    fixture = _proof_fixture(tmp_path)
    publisher = DurableRebuildPublisherV1(
        root=fixture["root"], artifact_reader=fixture["store"]
    )
    lock = RunPublicationLock(
        root=fixture["root"], semantic_run_id=fixture["verification"].semantic_run_id
    )
    with pytest.raises(DurableRebuildError) as error:
        publisher.publish(lock=lock, verification=fixture["verification"])
    assert error.value.code is CanonicalPublicationFailureCode.RUN_LOCK_UNAVAILABLE
    assert not Path(error.value.relative_subject).is_absolute()


def test_staging_precedes_existing_final_and_is_left_for_recovery(tmp_path: Path) -> None:
    fixture, publisher, observation = _publish(tmp_path)
    parent = (
        fixture["root"]
        / "runs"
        / fixture["verification"].semantic_run_id
        / "rebuild-proofs"
    )
    staging = parent / f".{observation.publication_manifest.proof_id}.staging"
    staging.mkdir()
    with RunPublicationLock(
        root=fixture["root"], semantic_run_id=fixture["verification"].semantic_run_id
    ) as lock, pytest.raises(DurableRebuildError) as error:
        publisher.publish(lock=lock, verification=fixture["verification"])
    assert error.value.code is CanonicalPublicationFailureCode.STAGING_EXISTS
    assert staging.exists()


@pytest.mark.parametrize(
    ("seam", "code"),
    [
        ("prepare", CanonicalPublicationFailureCode.STAGING_PREPARE_FAILED),
        ("verification_write", CanonicalPublicationFailureCode.ARTIFACT_WRITE_FAILED),
        ("manifest_write", CanonicalPublicationFailureCode.MANIFEST_WRITE_FAILED),
        ("staged_read", CanonicalPublicationFailureCode.PUBLICATION_VERIFICATION_FAILED),
        ("harden", CanonicalPublicationFailureCode.IMMUTABILITY_FAILED),
        ("rename", CanonicalPublicationFailureCode.ATOMIC_FINALIZE_FAILED),
        ("final_verify", CanonicalPublicationFailureCode.PUBLICATION_VERIFICATION_FAILED),
        ("final_fsync", CanonicalPublicationFailureCode.ATOMIC_FINALIZE_FAILED),
        ("final_read", CanonicalPublicationFailureCode.PUBLICATION_VERIFICATION_FAILED),
    ],
)
def test_failure_mapping_and_scoped_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, seam: str, code
) -> None:
    fixture = _proof_fixture(tmp_path)
    publisher = DurableRebuildPublisherV1(
        root=fixture["root"], artifact_reader=fixture["store"]
    )
    run = fixture["root"] / "runs" / fixture["verification"].semantic_run_id
    parent = run / "rebuild-proofs"
    calls = {"write": 0, "read": 0, "fsync": 0}

    def fail(*args, **kwargs):
        raise OSError("injected absolute /secret must not escape")

    if seam == "prepare":
        monkeypatch.setattr(publisher, "_ensure_directory", fail)
    elif seam in {"verification_write", "manifest_write"}:
        original = publisher._write_file

        def write(path, source):
            calls["write"] += 1
            if calls["write"] == (1 if seam == "verification_write" else 2):
                fail()
            return original(path, source)

        monkeypatch.setattr(publisher, "_write_file", write)
    elif seam in {"staged_read", "final_verify", "final_read"}:
        original = publisher._read_directory
        target = {"staged_read": 1, "final_verify": 2, "final_read": 3}[seam]

        def read(*args, **kwargs):
            calls["read"] += 1
            if calls["read"] == target:
                fail()
            return original(*args, **kwargs)

        monkeypatch.setattr(publisher, "_read_directory", read)
    elif seam == "harden":
        monkeypatch.setattr(publisher, "_prepare_read_only_directory", fail)
    elif seam == "rename":
        monkeypatch.setattr(publisher, "_rename", fail)
    elif seam == "final_fsync":
        original = publisher._fsync_directory

        def fsync(path):
            calls["fsync"] += 1
            # parent after staging create is first; final-directory fsync is second.
            if calls["fsync"] == 2:
                fail()
            return original(path)

        monkeypatch.setattr(publisher, "_fsync_directory", fsync)

    lock = RunPublicationLock(
        root=fixture["root"], semantic_run_id=fixture["verification"].semantic_run_id
    )
    lock.__enter__()
    try:
        with pytest.raises(DurableRebuildError) as error:
            publisher.publish(lock=lock, verification=fixture["verification"])
    finally:
        lock.__exit__(None, None, None)
    assert error.value.code is code
    assert "/secret" not in str(error.value)
    stages = list(parent.glob(".*.staging")) if parent.exists() else []
    if seam in {"final_verify", "final_fsync", "final_read"}:
        assert not stages
        assert any(path.is_dir() and not path.name.startswith(".") for path in parent.iterdir())
    else:
        assert stages == []


def test_pre_rename_destination_recheck_leaves_current_staging(tmp_path: Path, monkeypatch) -> None:
    fixture = _proof_fixture(tmp_path)
    publisher = DurableRebuildPublisherV1(
        root=fixture["root"], artifact_reader=fixture["store"]
    )
    original = publisher._prepare_read_only_directory

    def race(directory):
        original(directory)
        final = directory.with_name(directory.name[1:].removesuffix(".staging"))
        final.mkdir()

    monkeypatch.setattr(publisher, "_prepare_read_only_directory", race)
    with RunPublicationLock(
        root=fixture["root"], semantic_run_id=fixture["verification"].semantic_run_id
    ) as lock, pytest.raises(DurableRebuildError) as error:
        publisher.publish(lock=lock, verification=fixture["verification"])
    assert error.value.code is CanonicalPublicationFailureCode.FINAL_DESTINATION_EXISTS
    parent = fixture["root"] / "runs" / fixture["verification"].semantic_run_id / "rebuild-proofs"
    assert any(path.name.endswith(".staging") for path in parent.iterdir())


def test_cleanup_failure_never_replaces_original_failure(tmp_path: Path, monkeypatch) -> None:
    fixture = _proof_fixture(tmp_path)
    publisher = DurableRebuildPublisherV1(
        root=fixture["root"], artifact_reader=fixture["store"]
    )
    monkeypatch.setattr(publisher, "_write_file", lambda *args: (_ for _ in ()).throw(OSError()))
    monkeypatch.setattr(publisher, "_force_remove", lambda path: False)
    with RunPublicationLock(
        root=fixture["root"], semantic_run_id=fixture["verification"].semantic_run_id
    ) as lock, pytest.raises(DurableRebuildError) as error:
        publisher.publish(lock=lock, verification=fixture["verification"])
    assert error.value.code is CanonicalPublicationFailureCode.ARTIFACT_WRITE_FAILED
