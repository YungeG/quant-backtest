from __future__ import annotations

import os
import stat
from pathlib import Path

import crypto_quant_backtest._durable_rebuild as durable
import pytest
from crypto_quant_backtest._durable_rebuild import (
    DurableRebuildError,
    DurableRebuildFailureCode,
)
from crypto_quant_backtest._publication import RunPublicationLock

from tests.runtime.durable_rebuild.test_publication import _publish

_OPERATOR_EXCLUSIVITY = object()


def _stale_lock(run: Path) -> Path:
    lock = run / ".publication.lock"
    lock.write_bytes(b"cooperative-single-writer-v1\n")
    lock.chmod(0o444)
    return lock


def _directory(path: Path, *, immutable: bool) -> None:
    mode = path.lstat().st_mode
    if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
        raise ValueError("unsafe recovery path")
    if immutable and mode & 0o222:
        raise ValueError("unsafe writable final")


def _operator_recover(
    *,
    fixture,
    publisher,
    observation,
    terminal_branch: str = "not_reached",
    evaluation_id: str | None = None,
    operator_exclusivity: object = _OPERATOR_EXCLUSIVITY,
) -> None:
    run_id = fixture["verification"].semantic_run_id
    proof_id = observation.publication_manifest.proof_id
    run = fixture["root"] / "runs" / run_id
    lock = run / ".publication.lock"
    proof_parent = run / "rebuild-proofs"
    proof_staging = proof_parent / f".{proof_id}.staging"
    proof_final = proof_parent / proof_id
    canonical_staging = run / ".canonical-v3.staging"
    canonical_final = run / "canonical-v3"
    evaluation_parent = run / "integrity-evaluations-v2"
    evaluation_staging = (
        evaluation_parent / f".{evaluation_id}.staging" if evaluation_id else None
    )
    evaluation_final = evaluation_parent / evaluation_id if evaluation_id else None
    relative = f"runs/{run_id}"

    try:
        if operator_exclusivity is not _OPERATOR_EXCLUSIVITY:
            raise ValueError("operator exclusivity required")
        _directory(run, immutable=False)
        _directory(proof_parent, immutable=False)
        if {entry.name for entry in proof_parent.iterdir()} - {
            proof_staging.name,
            proof_final.name,
        }:
            raise ValueError("unmanaged proof sibling")
        proof_stage_exists = os.path.lexists(proof_staging)
        proof_final_exists = os.path.lexists(proof_final)
        if proof_stage_exists:
            _directory(proof_staging, immutable=False)
        if proof_final_exists:
            _directory(proof_final, immutable=True)
            publisher._read_directory(
                proof_final,
                (
                    observation.verification_source_bytes,
                    observation.publication_manifest_source_bytes,
                ),
                require_read_only=True,
            )
        if proof_stage_exists and proof_final_exists:
            raise ValueError("proof staging/final coexist")

        canonical_stage_exists = os.path.lexists(canonical_staging)
        canonical_final_exists = os.path.lexists(canonical_final)
        if canonical_stage_exists:
            _directory(canonical_staging, immutable=False)
        if canonical_final_exists:
            # DRP-03 owns the exact canonical-v3 decoder; DRP-02 must not accept it.
            raise ValueError("canonical final requires DRP-03 decoder")

        evaluation_stage_exists = False
        if evaluation_parent.exists():
            _directory(evaluation_parent, immutable=False)
            if evaluation_id is None:
                if tuple(evaluation_parent.iterdir()):
                    raise ValueError("unknown evaluation id")
            else:
                assert evaluation_staging is not None
                assert evaluation_final is not None
                if {entry.name for entry in evaluation_parent.iterdir()} - {
                    evaluation_staging.name,
                    evaluation_final.name,
                }:
                    raise ValueError("unmanaged evaluation sibling")
                evaluation_stage_exists = os.path.lexists(evaluation_staging)
                if evaluation_stage_exists:
                    _directory(evaluation_staging, immutable=False)
                if os.path.lexists(evaluation_final):
                    # DRP-03 owns the exact evaluation-v2 decoder.
                    raise ValueError("evaluation final requires DRP-03 decoder")

        if terminal_branch == "not_reached":
            if canonical_stage_exists or evaluation_stage_exists:
                raise ValueError("terminal branch was not reached")
        elif terminal_branch == "canonical":
            if evaluation_id is not None or evaluation_stage_exists:
                raise ValueError("canonical/evaluation branch conflict")
        elif terminal_branch == "evaluation":
            if evaluation_id is None or canonical_stage_exists:
                raise ValueError("evaluation branch identity mismatch")
        else:
            raise ValueError("unknown terminal branch")
    except (OSError, ValueError):
        raise DurableRebuildError(
            DurableRebuildFailureCode.RECOVERY_UNSAFE,
            relative,
        ) from None

    scopes = [(proof_staging, proof_parent)]
    if terminal_branch == "canonical":
        scopes.append((canonical_staging, run))
    elif terminal_branch == "evaluation":
        assert evaluation_staging is not None
        scopes.append((evaluation_staging, evaluation_parent))
    for staging, parent in scopes:
        if os.path.lexists(staging):
            try:
                if not durable.force_remove(staging):
                    raise OSError("scoped cleanup failed")
                durable.fsync_directory(parent)
            except OSError:
                raise DurableRebuildError(
                    DurableRebuildFailureCode.RECOVERY_CLEANUP_FAILED,
                    relative,
                ) from None
    if os.path.lexists(lock):
        try:
            lock.unlink()
            durable.fsync_directory(run)
        except OSError:
            raise DurableRebuildError(
                DurableRebuildFailureCode.RECOVERY_CLEANUP_FAILED,
                relative,
            ) from None


def _published_state(tmp_path: Path):
    fixture, publisher, observation = _publish(tmp_path)
    run = fixture["root"] / "runs" / fixture["verification"].semantic_run_id
    return fixture, publisher, observation, run


def test_proof_staging_cleanup_then_normal_retry(tmp_path: Path) -> None:
    fixture, publisher, observation, run = _published_state(tmp_path)
    final = run / "rebuild-proofs" / observation.publication_manifest.proof_id
    assert durable.force_remove(final)
    staging = final.with_name(f".{final.name}.staging")
    staging.mkdir()
    lock = _stale_lock(run)

    _operator_recover(
        fixture=fixture,
        publisher=publisher,
        observation=observation,
    )

    assert not staging.exists()
    assert not lock.exists()
    with RunPublicationLock(
        root=fixture["root"], semantic_run_id=fixture["verification"].semantic_run_id
    ) as retry_lock:
        retried = publisher.publish(
            lock=retry_lock, verification=fixture["verification"]
        )
    assert retried == observation


def test_exact_proof_final_is_preserved_then_idempotently_accepted(tmp_path: Path) -> None:
    fixture, publisher, observation, run = _published_state(tmp_path)
    final = run / "rebuild-proofs" / observation.publication_manifest.proof_id
    before = {path.name: path.read_bytes() for path in final.iterdir()}
    lock = _stale_lock(run)

    _operator_recover(
        fixture=fixture,
        publisher=publisher,
        observation=observation,
    )

    assert not lock.exists()
    assert {path.name: path.read_bytes() for path in final.iterdir()} == before
    with RunPublicationLock(
        root=fixture["root"], semantic_run_id=fixture["verification"].semantic_run_id
    ) as retry_lock:
        assert publisher.publish(
            lock=retry_lock, verification=fixture["verification"]
        ) == observation


@pytest.mark.parametrize("branch", ["canonical", "evaluation"])
def test_absent_terminal_staging_cleanup_precedes_lock(
    tmp_path: Path, branch: str
) -> None:
    fixture, publisher, observation, run = _published_state(tmp_path)
    evaluation_id = "evaluation_" + "4" * 64 if branch == "evaluation" else None
    if branch == "canonical":
        staging = run / ".canonical-v3.staging"
    else:
        parent = run / "integrity-evaluations-v2"
        parent.mkdir()
        staging = parent / f".{evaluation_id}.staging"
    staging.mkdir()
    lock = _stale_lock(run)

    _operator_recover(
        fixture=fixture,
        publisher=publisher,
        observation=observation,
        terminal_branch=branch,
        evaluation_id=evaluation_id,
    )

    assert not staging.exists()
    assert not lock.exists()


@pytest.mark.parametrize("branch", ["canonical", "evaluation"])
def test_visible_terminal_final_is_refused_until_drp03_exact_decoder(
    tmp_path: Path, branch: str
) -> None:
    fixture, publisher, observation, run = _published_state(tmp_path)
    evaluation_id = "evaluation_" + "5" * 64 if branch == "evaluation" else None
    if branch == "canonical":
        final = run / "canonical-v3"
    else:
        parent = run / "integrity-evaluations-v2"
        parent.mkdir()
        final = parent / str(evaluation_id)
    final.mkdir()
    (final / "not-exact.json").write_text("{}")
    lock = _stale_lock(run)

    with pytest.raises(DurableRebuildError) as error:
        _operator_recover(
            fixture=fixture,
            publisher=publisher,
            observation=observation,
            terminal_branch=branch,
            evaluation_id=evaluation_id,
        )

    assert error.value.code is DurableRebuildFailureCode.RECOVERY_UNSAFE
    assert lock.exists()
    assert final.exists()


@pytest.mark.parametrize(
    "unsafe",
    ["no_exclusivity", "sibling", "coexist", "symlink", "special", "unknown_eval", "malformed_final"],
)
def test_unsafe_state_refuses_all_mutation(tmp_path: Path, unsafe: str) -> None:
    fixture, publisher, observation, run = _published_state(tmp_path)
    proof_id = observation.publication_manifest.proof_id
    proof_parent = run / "rebuild-proofs"
    final = proof_parent / proof_id
    lock = _stale_lock(run)
    authority = _OPERATOR_EXCLUSIVITY
    if unsafe == "no_exclusivity":
        authority = object()
    elif unsafe == "sibling":
        (proof_parent / "unmanaged").mkdir()
    elif unsafe == "coexist":
        (proof_parent / f".{proof_id}.staging").mkdir()
    elif unsafe == "symlink":
        final.chmod(0o755)
        target = proof_parent / "target"
        final.rename(target)
        final.symlink_to(target.name)
    elif unsafe == "special":
        final.chmod(0o755)
        assert durable.force_remove(final)
        (proof_parent / f".{proof_id}.staging").write_text("not a directory")
    elif unsafe == "unknown_eval":
        parent = run / "integrity-evaluations-v2"
        parent.mkdir()
        (parent / "evaluation_unknown").mkdir()
    else:
        (final / "verification.json").chmod(0o644)

    with pytest.raises(DurableRebuildError) as error:
        _operator_recover(
            fixture=fixture,
            publisher=publisher,
            observation=observation,
            operator_exclusivity=authority,
        )

    assert error.value.code is DurableRebuildFailureCode.RECOVERY_UNSAFE
    assert lock.exists()


def test_cleanup_order_fsyncs_scope_parent_before_lock_unlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture, publisher, observation, run = _published_state(tmp_path)
    final = run / "rebuild-proofs" / observation.publication_manifest.proof_id
    assert durable.force_remove(final)
    staging = final.with_name(f".{final.name}.staging")
    staging.mkdir()
    lock = _stale_lock(run)
    actions: list[str] = []
    original_remove = durable.force_remove
    original_fsync = durable.fsync_directory

    def remove(path: Path) -> bool:
        actions.append(f"remove:{path.name}")
        return original_remove(path)

    def fsync(path: Path) -> None:
        actions.append(f"fsync:{path.name}")
        original_fsync(path)

    monkeypatch.setattr(durable, "force_remove", remove)
    monkeypatch.setattr(durable, "fsync_directory", fsync)
    _operator_recover(
        fixture=fixture,
        publisher=publisher,
        observation=observation,
    )

    assert actions[:2] == [f"remove:{staging.name}", "fsync:rebuild-proofs"]
    assert actions[-1] == f"fsync:{run.name}"
    assert not lock.exists()


def test_cleanup_failure_stops_and_keeps_stale_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture, publisher, observation, run = _published_state(tmp_path)
    final = run / "rebuild-proofs" / observation.publication_manifest.proof_id
    assert durable.force_remove(final)
    staging = final.with_name(f".{final.name}.staging")
    staging.mkdir()
    lock = _stale_lock(run)
    monkeypatch.setattr(durable, "force_remove", lambda path: False)

    with pytest.raises(DurableRebuildError) as error:
        _operator_recover(
            fixture=fixture,
            publisher=publisher,
            observation=observation,
        )

    assert error.value.code is DurableRebuildFailureCode.RECOVERY_CLEANUP_FAILED
    assert lock.exists()
