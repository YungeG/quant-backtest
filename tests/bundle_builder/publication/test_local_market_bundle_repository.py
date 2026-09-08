from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

import pytest

from crypto_quant_bundle_builder import (
    LocalMarketBundleRepository,
    LocalMarketBundleRepositoryConfig,
    LocalMarketBundleRetentionProof,
    MarketBundlePublicationFailureCode,
)
from tests.bundle_builder.publication._fixtures import (
    PUBLICATION_RETENTION_POLICY_REF,
    bundle_manifest,
    bundle_ref,
    final_directory,
    manifest_stream_file_names,
    repository_relative_paths,
    stream_payload_hashes,
    stream_payloads,
)


def _publish(manifest, payloads: Mapping[str, bytes], root: Path, *, retention_policy_ref: str):
    return LocalMarketBundleRepository(
        config=LocalMarketBundleRepositoryConfig(root=root)
    ).publish_market_bundle_v1(
        manifest=manifest,
        stream_payloads=payloads,
        retention_policy_ref=retention_policy_ref,
    )


def test_first_publish_is_content_addressed_and_immutable(tmp_path: Path) -> None:
    manifest = bundle_manifest()
    payloads = stream_payloads(manifest)
    outcome = _publish(manifest, payloads, tmp_path, retention_policy_ref=PUBLICATION_RETENTION_POLICY_REF)

    assert outcome.failure is None
    result = outcome.result
    assert result is not None
    assert result.already_published is False
    assert result.repository_path.final_directory_relative_path == final_directory(manifest)

    final = tmp_path / result.repository_path.final_directory_relative_path
    assert final.is_dir()
    assert final.is_dir() and {path.name for path in final.iterdir()} == {
        "manifest.json",
        "streams",
        "publication.json",
        "retention-proof.json",
    }
    assert all(path.stat().st_mode & 0o222 == 0 for path in final.iterdir())

    proof = json.loads((final / "retention-proof.json").read_bytes())
    publication = json.loads((final / "publication.json").read_bytes())
    repository_paths = repository_relative_paths(manifest)
    assert result.repository_path.manifest_relative_path == repository_paths["manifest_relative_path"]
    assert result.repository_path.publication_relative_path == repository_paths["publication_relative_path"]
    assert result.repository_path.retention_proof_relative_path == repository_paths["retention_proof_relative_path"]
    assert proof["stream_relative_paths"] == list(repository_paths["stream_relative_paths"])
    assert publication["stream_relative_paths"] == list(repository_paths["stream_relative_paths"])
    assert proof["retention_policy_ref"] == PUBLICATION_RETENTION_POLICY_REF
    assert isinstance(result.retention_proof, LocalMarketBundleRetentionProof)


def test_second_publish_is_idempotent(tmp_path: Path) -> None:
    manifest = bundle_manifest()
    payloads = stream_payloads(manifest)

    first = _publish(manifest, payloads, tmp_path, retention_policy_ref=PUBLICATION_RETENTION_POLICY_REF)
    assert first.result is not None

    second = _publish(manifest, payloads, tmp_path, retention_policy_ref=PUBLICATION_RETENTION_POLICY_REF)
    assert second.result is not None
    assert second.result.already_published is True
    assert second.result.repository_path == first.result.repository_path
    assert second.result.retention_proof == first.result.retention_proof


def test_payload_and_input_errors_fail_before_lock_conflicts(tmp_path: Path) -> None:
    manifest = bundle_manifest()
    payloads = stream_payloads(manifest)

    mismatched_key = _publish(manifest, {**payloads, "new.stream": b"bad"}, tmp_path, retention_policy_ref=PUBLICATION_RETENTION_POLICY_REF)
    assert mismatched_key.failure is not None
    assert mismatched_key.failure.code is MarketBundlePublicationFailureCode.STREAM_PAYLOAD_MISMATCH

    mismatched_hash = dict(payloads)
    some_key = next(iter(mismatched_hash))
    mismatched_hash[some_key] = b"tampered"
    mismatched_hash_value = _publish(manifest, mismatched_hash, tmp_path, retention_policy_ref=PUBLICATION_RETENTION_POLICY_REF)
    assert mismatched_hash_value.failure is not None
    assert mismatched_hash_value.failure.code is MarketBundlePublicationFailureCode.STREAM_PAYLOAD_MISMATCH

    bad_policy = _publish(manifest, payloads, tmp_path, retention_policy_ref="bad policy")
    assert bad_policy.failure is not None
    assert bad_policy.failure.code is MarketBundlePublicationFailureCode.INVALID_INPUT

    invalid_manifest = _publish(object(), payloads, tmp_path, retention_policy_ref=PUBLICATION_RETENTION_POLICY_REF)
    assert invalid_manifest.failure is not None
    assert invalid_manifest.failure.code is MarketBundlePublicationFailureCode.INVALID_INPUT


def test_staging_conflict_and_lock_conflict(tmp_path: Path) -> None:
    manifest = bundle_manifest()
    payloads = stream_payloads(manifest)
    staging = tmp_path / ".staging" / bundle_ref(manifest).bundle_key / bundle_ref(manifest).manifest_hash.removeprefix("sha256:")
    staging.mkdir(parents=True)

    repository = LocalMarketBundleRepository(config=LocalMarketBundleRepositoryConfig(root=tmp_path))
    staging_outcome = repository.publish_market_bundle_v1(
        manifest=manifest,
        stream_payloads=payloads,
        retention_policy_ref=PUBLICATION_RETENTION_POLICY_REF,
    )
    assert staging_outcome.failure is not None
    assert staging_outcome.failure.code is MarketBundlePublicationFailureCode.STAGING_PREPARE_FAILED

    lock = tmp_path / ".locks" / bundle_ref(manifest).bundle_key / f"{bundle_ref(manifest).manifest_hash.removeprefix('sha256:')}.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text("reserved", encoding="utf-8")

    lock_outcome = repository.publish_market_bundle_v1(
        manifest=manifest,
        stream_payloads=payloads,
        retention_policy_ref=PUBLICATION_RETENTION_POLICY_REF,
    )
    assert lock_outcome.failure is not None
    assert lock_outcome.failure.code is MarketBundlePublicationFailureCode.LOCK_UNAVAILABLE


def test_final_destination_conflict(tmp_path: Path) -> None:
    manifest = bundle_manifest()
    payloads = stream_payloads(manifest)
    first = _publish(manifest, payloads, tmp_path, retention_policy_ref=PUBLICATION_RETENTION_POLICY_REF)
    assert first.result is not None

    final = tmp_path / final_directory(manifest)
    final.chmod(0o755)
    (final / "tampered.txt").write_text("tampered", encoding="utf-8")

    conflict = _publish(manifest, payloads, tmp_path, retention_policy_ref=PUBLICATION_RETENTION_POLICY_REF)
    assert conflict.failure is not None
    assert conflict.failure.code is MarketBundlePublicationFailureCode.FINAL_DESTINATION_CONFLICT


def test_no_absolute_subject_in_failures(tmp_path: Path) -> None:
    manifest = bundle_manifest()
    payloads = stream_payloads(manifest)
    tampered = dict(payloads)
    tampered[next(iter(payloads))] = b"corrupt"
    outcome = _publish(manifest, tampered, tmp_path, retention_policy_ref=PUBLICATION_RETENTION_POLICY_REF)
    assert outcome.failure is not None
    assert not outcome.failure.relative_subject.startswith(str(tmp_path))
    assert "/" not in outcome.failure.relative_subject.lstrip("./")


def test_publication_contract_fails_without_partial_visible_state(monkeypatch, tmp_path: Path) -> None:
    import crypto_quant_bundle_builder.local_market_bundle_repository as module

    manifest = bundle_manifest()
    payloads = stream_payloads(manifest)
    repository = LocalMarketBundleRepository(
        config=LocalMarketBundleRepositoryConfig(root=tmp_path)
    )

    def fail(*_args, **_kwargs) -> None:
        raise ValueError("forced final verify failure")

    monkeypatch.setattr(module.LocalMarketBundleRepository, "_verify_staging", staticmethod(fail))
    outcome = repository.publish_market_bundle_v1(
        manifest=manifest,
        stream_payloads=payloads,
        retention_policy_ref=PUBLICATION_RETENTION_POLICY_REF,
    )
    assert outcome.failure is not None
    assert outcome.failure.code in {
        MarketBundlePublicationFailureCode.STAGING_VERIFICATION_FAILED,
        MarketBundlePublicationFailureCode.UNMANAGED_PUBLICATION_STATE,
    }
    final = tmp_path / final_directory(manifest)
    assert not final.exists()
    assert not (
        tmp_path
        / ".staging"
        / bundle_ref(manifest).bundle_key
        / bundle_ref(manifest).manifest_hash.removeprefix("sha256:")
    ).exists()


def test_tamper_detection_for_current_retrievability(tmp_path: Path) -> None:
    manifest = bundle_manifest()
    payloads = stream_payloads(manifest)
    published = _publish(manifest, payloads, tmp_path, retention_policy_ref=PUBLICATION_RETENTION_POLICY_REF)
    assert published.result is not None
    final = tmp_path / published.result.repository_path.final_directory_relative_path
    publication = json.loads((final / "publication.json").read_bytes())
    proof = json.loads((final / "retention-proof.json").read_bytes())

    assert publication["stream_relative_paths"] == list(
        published.result.repository_path.stream_relative_paths
    )
    assert proof["stream_payload_hashes"] == list(stream_payload_hashes(manifest).values())

    # local proof only validates exact file-level coverage; corrupt payload should invalidate verification call
    from crypto_quant_bundle_builder.local_market_bundle_repository import LocalMarketBundleRepository as Repo
    payload_path = final / manifest_stream_file_names(manifest)[0]
    payload_path.chmod(0o644)
    payload_path.write_text("corrupt", encoding="utf-8")

    assert not Repo(
        config=LocalMarketBundleRepositoryConfig(root=tmp_path)
    )._verify_final(
        final,
        manifest_source_hash=published.result.retention_proof.manifest_source_hash,
        stream_relative_paths=published.result.repository_path.stream_relative_paths,
        stream_payload_values=tuple(payloads.values()),
        stream_payload_hashes=tuple(stream_payload_hashes(manifest).values()),
        publication_payload=(final / "publication.json").read_bytes(),
        retention_payload=(final / "retention-proof.json").read_bytes(),
        retention_proof=published.result.retention_proof,
    )
