from __future__ import annotations

import hashlib
import inspect
import json
import shutil
from pathlib import Path

import crypto_quant_market_data as market_data
import crypto_quant_market_data.local_market_bundle_reader as local_reader_module
import pytest
from crypto_quant_domain import canonical_bytes, canonical_sha256
from crypto_quant_market_data import LocalMarketBundleReader

from tests.bundle_builder.publication._fixtures import bundle_manifest
from tests.market_data.bundles._local_reader_fixtures import publish


def _open(root: Path):
    ref, final = publish(root, bundle_manifest())
    return ref, final, LocalMarketBundleReader.open(repository_root=root, bundle_ref=ref)


def _rewrite(path: Path, value: object) -> None:
    path.chmod(0o644)
    path.write_bytes(canonical_bytes(value))
    path.chmod(0o444)


def _assert_tampered(reader: LocalMarketBundleReader) -> None:
    with pytest.raises(local_reader_module._LocalReopenTampered) as error:
        reader._reopen_with_provenance_v1()
    assert type(error.value) is local_reader_module._LocalReopenTampered
    assert error.value._durable_reopen_kind_v1 == "tampered"


def test_repository_open_provenance_requires_exact_open_and_reader_type(
    tmp_path: Path,
) -> None:
    ref, _, reader = _open(tmp_path)

    direct = LocalMarketBundleReader(reader._delegate)

    class DerivedLocalMarketBundleReader(LocalMarketBundleReader):
        pass

    derived = DerivedLocalMarketBundleReader.open(
        repository_root=tmp_path,
        bundle_ref=ref,
    )

    assert LocalMarketBundleReader.validate_repository_open_reader_v1(reader) is reader
    with pytest.raises(ValueError, match="repository-open"):
        LocalMarketBundleReader.validate_repository_open_reader_v1(direct)
    with pytest.raises(ValueError, match="repository-open"):
        LocalMarketBundleReader.validate_repository_open_reader_v1(derived)
    assert reader._has_repository_open_provenance_v1() is True
    assert direct._has_repository_open_provenance_v1() is False
    assert derived._has_repository_open_provenance_v1() is False
    assert direct._repository_open_provenance_v1 is None
    assert derived._repository_open_provenance_v1 is None


def test_public_repository_open_validation_rejects_copied_provenance_tuple(
    tmp_path: Path,
) -> None:
    _, _, reader = _open(tmp_path)
    direct = LocalMarketBundleReader(reader._delegate)
    direct._repository_open_provenance_v1 = reader._repository_open_provenance_v1

    assert direct._has_repository_open_provenance_v1() is True
    with pytest.raises(ValueError, match="repository-open"):
        LocalMarketBundleReader.validate_repository_open_reader_v1(direct)


def test_provenance_selection_does_not_dereference_the_filesystem(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, final, reader = _open(tmp_path)
    copied = tmp_path / "copied-tree"
    shutil.copytree(final, copied)
    final.chmod(0o755)
    (final / "streams").chmod(0o755)
    shutil.rmtree(final)
    assert copied.is_dir()

    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError("filesystem dereference")

    for operation in ("resolve", "exists", "lstat", "read_bytes", "iterdir"):
        monkeypatch.setattr(Path, operation, fail)
    assert reader._has_repository_open_provenance_v1() is True


def test_reopen_accepts_byte_identical_tree_replacement_without_origin_claim(
    tmp_path: Path,
) -> None:
    _, final, reader = _open(tmp_path)
    original = reader._repository_open_provenance_v1
    assert type(original) is tuple
    copied = tmp_path / "copied-tree"
    shutil.copytree(final, copied)
    final.chmod(0o755)
    (final / "streams").chmod(0o755)
    shutil.rmtree(final)
    shutil.copytree(copied, final)

    reopened, *reopened_values = reader._reopen_with_provenance_v1()

    assert reopened._has_repository_open_provenance_v1() is True
    assert tuple(reopened_values) == original[3:]


def test_reopen_returns_exact_fresh_bytes_and_hashes_without_root_output(
    tmp_path: Path,
) -> None:
    _, _, reader = _open(tmp_path)
    original = reader._repository_open_provenance_v1
    assert type(original) is tuple

    result = reader._reopen_with_provenance_v1()
    reopened, publication_bytes, publication_source_hash, publication_hash = result[:4]
    retention_bytes, retention_source_hash, proof_hash = result[4:]
    current = reopened._repository_open_provenance_v1

    assert type(current) is tuple
    assert result[1:] == current[3:]
    assert current[1:] == original[1:]
    assert publication_source_hash == f"sha256:{hashlib.sha256(publication_bytes).hexdigest()}"
    assert retention_source_hash == f"sha256:{hashlib.sha256(retention_bytes).hexdigest()}"
    assert publication_hash == json.loads(publication_bytes)["publication_hash"]
    assert proof_hash == json.loads(retention_bytes)["proof_hash"]

    root_bytes = str(tmp_path.resolve()).encode()
    assert root_bytes not in publication_bytes
    assert root_bytes not in retention_bytes
    assert root_bytes not in canonical_bytes(reopened.bundle_ref)
    assert root_bytes not in canonical_bytes(reopened.manifest)


def test_reopen_classifies_missing_tree_as_unavailable(tmp_path: Path) -> None:
    _, final, reader = _open(tmp_path)
    final.chmod(0o755)
    (final / "streams").chmod(0o755)
    shutil.rmtree(final)

    with pytest.raises(local_reader_module._LocalReopenUnavailable) as error:
        reader._reopen_with_provenance_v1()
    assert type(error.value) is local_reader_module._LocalReopenUnavailable
    assert error.value._durable_reopen_kind_v1 == "unavailable"


@pytest.mark.parametrize("operation", ["read_bytes", "lstat", "iterdir", "resolve"])
def test_reopen_classifies_filesystem_oserrors_as_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
) -> None:
    _, _, reader = _open(tmp_path)

    def fail(*args: object, **kwargs: object) -> None:
        raise OSError

    monkeypatch.setattr(Path, operation, fail)
    with pytest.raises(local_reader_module._LocalReopenUnavailable) as error:
        reader._reopen_with_provenance_v1()
    assert type(error.value) is local_reader_module._LocalReopenUnavailable
    assert error.value._durable_reopen_kind_v1 == "unavailable"


@pytest.mark.parametrize("mutation", ["malformed", "hash", "tree", "mode"])
def test_reopen_classifies_content_mutations_as_tampered(
    tmp_path: Path,
    mutation: str,
) -> None:
    _, final, reader = _open(tmp_path)

    if mutation == "malformed":
        path = final / "publication.json"
        path.chmod(0o644)
        path.write_bytes(b"not-json")
        path.chmod(0o444)
    elif mutation == "hash":
        path = final / "streams" / "000.payload"
        path.chmod(0o644)
        path.write_bytes(path.read_bytes() + b"\n")
        path.chmod(0o444)
    elif mutation == "tree":
        final.chmod(0o755)
        extra = final / "extra"
        extra.write_bytes(b"extra")
        extra.chmod(0o444)
        final.chmod(0o555)
    else:
        (final / "publication.json").chmod(0o644)

    _assert_tampered(reader)


def test_reopen_rejects_self_consistent_publication_replacement(tmp_path: Path) -> None:
    _, final, reader = _open(tmp_path)
    publication_path = final / "publication.json"
    retention_path = final / "retention-proof.json"
    publication = json.loads(publication_path.read_bytes())
    retention = json.loads(retention_path.read_bytes())

    retention["retention_policy_ref"] = "retention.replaced.v1"
    retention["proof_hash"] = canonical_sha256(
        {key: value for key, value in retention.items() if key != "proof_hash"}
    )
    publication["retention_policy_ref"] = retention["retention_policy_ref"]
    publication["retention_proof_hash"] = retention["proof_hash"]
    publication["publication_hash"] = canonical_sha256(
        {key: value for key, value in publication.items() if key != "publication_hash"}
    )
    _rewrite(retention_path, retention)
    _rewrite(publication_path, publication)

    replacement = LocalMarketBundleReader.open(
        repository_root=tmp_path,
        bundle_ref=reader.bundle_ref,
    )
    assert replacement._has_repository_open_provenance_v1() is True
    _assert_tampered(reader)


def test_reopen_rejects_original_private_tuple_mutation(tmp_path: Path) -> None:
    _, _, reader = _open(tmp_path)
    original = reader._repository_open_provenance_v1
    assert type(original) is tuple
    reader._repository_open_provenance_v1 = (*original[:3], b"changed", *original[4:])

    assert reader._has_repository_open_provenance_v1() is True
    _assert_tampered(reader)


def test_public_exports_and_reader_signatures_remain_unchanged() -> None:
    assert str(inspect.signature(LocalMarketBundleReader.__init__)) == (
        "(self, delegate: 'InMemoryMarketBundleReader') -> 'None'"
    )
    assert str(inspect.signature(LocalMarketBundleReader.open)) == (
        "(*, repository_root: 'Path', bundle_ref: 'MarketBundleRef') -> "
        "'LocalMarketBundleReader'"
    )
    assert local_reader_module.__all__ == ["LocalMarketBundleReader"]
    assert market_data.__all__ == [
        "EventCursor",
        "InMemoryMarketBundleReader",
        "InputValidationFailure",
        "InputValidationIssue",
        "InputValidationIssueCode",
        "LocalMarketBundleReader",
        "MarketBundleCapability",
        "MarketBundleError",
        "MarketBundleIntegrityError",
        "MarketBundleManifest",
        "MarketBundleReader",
        "MarketBundleRef",
        "MarketBundleStreamError",
        "MarketEvent",
        "MarketStreamManifest",
    ]
    assert not hasattr(market_data, "_LocalReopenUnavailable")
    assert not hasattr(market_data, "_LocalReopenTampered")
