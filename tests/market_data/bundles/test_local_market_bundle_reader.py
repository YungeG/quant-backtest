from __future__ import annotations

import json
from pathlib import Path

import pytest

from crypto_quant_domain import canonical_bytes, canonical_sha256
from crypto_quant_market_data import (
    EventCursor,
    InMemoryMarketBundleReader,
    InputValidationFailure,
    InputValidationIssueCode,
    LocalMarketBundleReader,
    MarketBundleCapability,
    MarketBundleReader,
    MarketBundleIntegrityError,
    MarketBundleStreamError,
)
from tests.bundle_builder.publication._fixtures import bundle_manifest, stream_payloads
from tests.market_data.bundles._local_reader_fixtures import collect, publish


def _open(root: Path):
    manifest = bundle_manifest()
    ref, final = publish(root, manifest)
    reader = LocalMarketBundleReader.open(repository_root=root, bundle_ref=ref)
    return manifest, ref, final, reader


def _rewrite(path: Path, value: object) -> None:
    path.chmod(0o644)
    path.write_bytes(canonical_bytes(value))
    path.chmod(0o444)


def _make_mutable(final: Path) -> None:
    final.chmod(0o755)
    (final / "streams").chmod(0o755)


def _reader_events(reader: LocalMarketBundleReader, stream_key: str):
    cursor = reader.open_cursor(stream_key, batch_size=10)
    assert isinstance(cursor, EventCursor)
    return reader.read_batch(cursor)[0]


def test_reader_opens_exact_publication_and_preserves_cursor_parity(
    tmp_path: Path,
) -> None:
    manifest, ref, _, reader = _open(tmp_path)
    stream_key = manifest.streams[0].stream_key
    expected_events = _reader_events(reader, stream_key)
    in_memory = InMemoryMarketBundleReader(
        bundle_ref=ref,
        manifest=manifest,
        streams={stream_key: expected_events},
    )

    assert isinstance(reader, MarketBundleReader)
    assert reader.bundle_ref == ref
    assert reader.manifest == manifest

    for size in (1, 2, 10):
        local_ids, local_hashes, exhausted = collect(
            reader,
            stream_key,
            batch_size=size,
        )
        memory_cursor = in_memory.open_cursor(stream_key, batch_size=size)
        assert isinstance(memory_cursor, EventCursor)
        memory_events: list[object] = []
        while not memory_cursor.exhausted:
            batch, memory_cursor = in_memory.read_batch(memory_cursor)
            memory_events.extend(batch)

        assert local_ids == tuple(event.event_id for event in memory_events)
        assert local_hashes == tuple(event.event_hash for event in memory_events)
        assert exhausted.exhausted
        assert reader.read_batch(exhausted) == ((), exhausted)
        assert reader.resume_cursor(exhausted, batch_size=1).batch_size == 1


def test_reader_preserves_requirement_and_cursor_misuse_behavior(
    tmp_path: Path,
) -> None:
    manifest, _, _, reader = _open(tmp_path)
    stream_key = manifest.streams[0].stream_key

    failure = reader.validate_requirements(
        required_capabilities=(
            MarketBundleCapability(key="funding_publications", version=1),
        ),
        required_streams=("missing.stream",),
    )
    assert isinstance(failure, InputValidationFailure)
    assert tuple(issue.code for issue in failure.issues) == (
        InputValidationIssueCode.MISSING_REQUIRED_CAPABILITY,
        InputValidationIssueCode.UNKNOWN_STREAM,
    )

    unknown = reader.open_cursor("missing.stream", batch_size=1)
    assert isinstance(unknown, InputValidationFailure)
    cursor = reader.open_cursor(stream_key, batch_size=1)
    assert isinstance(cursor, EventCursor)
    with pytest.raises(MarketBundleStreamError, match="batch_size"):
        reader.open_cursor(stream_key, batch_size=0)

    other_root = tmp_path / "other"
    other_root.mkdir()
    other_ref, _ = publish(other_root, manifest)
    other = LocalMarketBundleReader.open(
        repository_root=other_root,
        bundle_ref=other_ref,
    )
    other_cursor = other.open_cursor(stream_key, batch_size=2)
    assert isinstance(other_cursor, EventCursor)
    assert reader.resume_cursor(other_cursor).bundle_ref == reader.bundle_ref

    foreign_manifest = bundle_manifest()
    foreign_ref = type(other_ref)(
        bundle_key="foreign-bundle",
        manifest_hash=other_ref.manifest_hash,
    )
    foreign_cursor = EventCursor(
        bundle_ref=foreign_ref,
        stream_manifest=foreign_manifest.streams[0],
        position=0,
        batch_size=1,
    )
    with pytest.raises(MarketBundleStreamError, match="bundle"):
        reader.resume_cursor(foreign_cursor)


def test_open_rejects_invalid_root_ref_and_path_cover_without_leakage(
    tmp_path: Path,
) -> None:
    manifest = bundle_manifest()
    ref, final = publish(tmp_path, manifest)

    with pytest.raises(MarketBundleIntegrityError, match="repository_root"):
        LocalMarketBundleReader.open(repository_root=Path("relative"), bundle_ref=ref)
    with pytest.raises(MarketBundleIntegrityError, match="bundle_ref"):
        LocalMarketBundleReader.open(repository_root=tmp_path, bundle_ref=None)  # type: ignore[arg-type]
    with pytest.raises(MarketBundleIntegrityError) as missing:
        LocalMarketBundleReader.open(
            repository_root=tmp_path / "missing",
            bundle_ref=ref,
        )
    assert str(tmp_path) not in str(missing.value)
    assert missing.value.__cause__ is None

    _make_mutable(final)
    (final / "extra").write_text("unexpected", encoding="utf-8")
    with pytest.raises(MarketBundleIntegrityError) as extra:
        LocalMarketBundleReader.open(repository_root=tmp_path, bundle_ref=ref)
    assert str(tmp_path) not in str(extra.value)
    assert extra.value.__cause__ is None


def test_open_rejects_writable_symlink_and_missing_entries(tmp_path: Path) -> None:
    manifest = bundle_manifest()

    writable_root = tmp_path / "writable"
    writable_root.mkdir()
    writable_ref, writable_final = publish(writable_root, manifest)
    (writable_final / "streams" / "000.payload").chmod(0o644)
    with pytest.raises(MarketBundleIntegrityError, match="immutable"):
        LocalMarketBundleReader.open(
            repository_root=writable_root,
            bundle_ref=writable_ref,
        )

    symlink_root = tmp_path / "symlink"
    symlink_root.mkdir()
    symlink_ref, symlink_final = publish(symlink_root, manifest)
    _make_mutable(symlink_final)
    manifest_path = symlink_final / "manifest.json"
    target = symlink_final / "manifest.target"
    manifest_path.rename(target)
    manifest_path.symlink_to(target.name)
    with pytest.raises(MarketBundleIntegrityError):
        LocalMarketBundleReader.open(
            repository_root=symlink_root,
            bundle_ref=symlink_ref,
        )

    missing_root = tmp_path / "missing"
    missing_root.mkdir()
    missing_ref, missing_final = publish(missing_root, manifest)
    _make_mutable(missing_final)
    (missing_final / "publication.json").unlink()
    with pytest.raises(MarketBundleIntegrityError):
        LocalMarketBundleReader.open(
            repository_root=missing_root,
            bundle_ref=missing_ref,
        )


def test_open_rejects_tampered_linkage_and_noncanonical_json(
    tmp_path: Path,
) -> None:
    manifest = bundle_manifest()

    publication_root = tmp_path / "publication"
    publication_root.mkdir()
    publication_ref, publication_final = publish(publication_root, manifest)
    publication = json.loads((publication_final / "publication.json").read_bytes())
    publication["manifest_relative_path"] = "/manifest.json"
    publication["publication_hash"] = canonical_sha256(
        {key: value for key, value in publication.items() if key != "publication_hash"}
    )
    _rewrite(publication_final / "publication.json", publication)
    with pytest.raises(MarketBundleIntegrityError):
        LocalMarketBundleReader.open(
            repository_root=publication_root,
            bundle_ref=publication_ref,
        )

    retention_root = tmp_path / "retention"
    retention_root.mkdir()
    retention_ref, retention_final = publish(retention_root, manifest)
    retention = json.loads((retention_final / "retention-proof.json").read_bytes())
    retention["retention_policy_ref"] = "retention.other"
    retention["proof_hash"] = canonical_sha256(
        {key: value for key, value in retention.items() if key != "proof_hash"}
    )
    _rewrite(retention_final / "retention-proof.json", retention)
    with pytest.raises(MarketBundleIntegrityError):
        LocalMarketBundleReader.open(
            repository_root=retention_root,
            bundle_ref=retention_ref,
        )

    json_root = tmp_path / "json"
    json_root.mkdir()
    json_ref, json_final = publish(json_root, manifest)
    manifest_path = json_final / "manifest.json"
    value = json.loads(manifest_path.read_bytes())
    manifest_path.chmod(0o644)
    manifest_path.write_text(json.dumps(value, indent=2), encoding="utf-8")
    manifest_path.chmod(0o444)
    with pytest.raises(MarketBundleIntegrityError, match="manifest"):
        LocalMarketBundleReader.open(repository_root=json_root, bundle_ref=json_ref)


def test_open_rejects_tampered_payload_before_decoding(tmp_path: Path) -> None:
    manifest = bundle_manifest()
    ref, final = publish(tmp_path, manifest)
    stream_path = final / "streams" / "000.payload"
    stream_path.chmod(0o644)
    stream_path.write_bytes(b"tampered")
    stream_path.chmod(0o444)

    with pytest.raises(MarketBundleIntegrityError, match="hash") as error:
        LocalMarketBundleReader.open(repository_root=tmp_path, bundle_ref=ref)
    assert str(tmp_path) not in str(error.value)
    assert "tampered" not in str(error.value)
    assert error.value.__cause__ is None
