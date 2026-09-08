from __future__ import annotations

import json
from pathlib import Path

from crypto_quant_bundle_builder import LocalMarketBundleRepository, LocalMarketBundleRepositoryConfig
from crypto_quant_domain import canonical_bytes

from tests.bundle_builder.publication._fixtures import (
    PUBLICATION_RETENTION_POLICY_REF,
    bundle_manifest,
    repository_relative_paths,
    stream_payload_hashes,
    stream_payloads,
)

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "tests/fixtures/market_data/publication"
GOLDEN = FIXTURES / "local-market-bundle-repository-v1.expected.json"


def _publish_golden_payload(root: Path) -> dict[str, object]:
    manifest = bundle_manifest()
    payloads = stream_payloads(manifest)
    repository = LocalMarketBundleRepository(
        config=LocalMarketBundleRepositoryConfig(root=root)
    )

    first = repository.publish_market_bundle_v1(
        manifest=manifest,
        stream_payloads=payloads,
        retention_policy_ref=PUBLICATION_RETENTION_POLICY_REF,
    )
    if first.result is None:
        raise AssertionError("first publish expected success")

    second = repository.publish_market_bundle_v1(
        manifest=manifest,
        stream_payloads=payloads,
        retention_policy_ref=PUBLICATION_RETENTION_POLICY_REF,
    )
    if second.result is None:
        raise AssertionError("second publish expected success")

    final_directory = root / first.result.repository_path.final_directory_relative_path
    publication_payload = json.loads((final_directory / "publication.json").read_bytes())
    retention_payload = json.loads((final_directory / "retention-proof.json").read_bytes())
    manifest_payload = json.loads((final_directory / "manifest.json").read_bytes())

    return {
        "schema_version": 1,
        "fixture_id": "local-market-bundle-repository-v1",
        "paths": repository_relative_paths(manifest),
        "stream_payload_hashes": list(stream_payload_hashes(manifest).values()),
        "first_publish": {
            "already_published": first.result.already_published,
            "manifest": manifest_payload,
            "repository_path": {
                "bundle_ref": first.result.repository_path.bundle_ref.to_canonical_dict(),
                "final_directory_relative_path": first.result.repository_path.final_directory_relative_path,
                "manifest_relative_path": first.result.repository_path.manifest_relative_path,
                "stream_relative_paths": list(first.result.repository_path.stream_relative_paths),
                "publication_relative_path": first.result.repository_path.publication_relative_path,
                "retention_proof_relative_path": first.result.repository_path.retention_proof_relative_path,
            },
            "retention_proof": first.result.retention_proof.to_canonical_dict(),
        },
        "second_publish": {
            "already_published": second.result.already_published,
            "repository_path_eq": second.result.repository_path == first.result.repository_path,
            "retention_proof_eq": second.result.retention_proof == first.result.retention_proof,
        },
        "publication": publication_payload,
        "retention_proof_payload": retention_payload,
        "relative_path_evidence": {
            "manifest_relative_path": first.result.repository_path.manifest_relative_path,
            "retention_proof_relative_path": first.result.repository_path.retention_proof_relative_path,
            "publication_relative_path": first.result.repository_path.publication_relative_path,
        },
        "deterministic_parity": {
            "manifest_source_hash": first.result.retention_proof.manifest_source_hash,
            "publication_hash": publication_payload["publication_hash"],
            "retention_proof_hash": retention_payload["proof_hash"],
            "publication_payload_hash": publication_payload["publication_hash"],
            "retention_payload_proof_hash": retention_payload["proof_hash"],
        },
    }


def test_publication_fixture_matches_static_golden(tmp_path: Path) -> None:
    try:
        expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"invalid G12D golden fixture: {error}") from error

    actual = json.loads(canonical_bytes(_publish_golden_payload(tmp_path)))
    assert actual == expected
