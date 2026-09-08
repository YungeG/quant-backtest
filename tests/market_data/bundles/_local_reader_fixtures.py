from __future__ import annotations

import json
from pathlib import Path

from crypto_quant_bundle_builder import (
    LocalMarketBundleRepository,
    LocalMarketBundleRepositoryConfig,
)
from crypto_quant_domain import canonical_bytes
from crypto_quant_market_data import (
    EventCursor,
    InputValidationFailure,
    LocalMarketBundleReader,
    MarketBundleCapability,
    MarketBundleManifest,
    MarketBundleRef,
)
from tests.bundle_builder.publication._fixtures import (
    PUBLICATION_RETENTION_POLICY_REF,
    repository_relative_paths,
    stream_payload_hashes,
    stream_payloads,
)


def publish(
    root: Path,
    manifest: MarketBundleManifest,
) -> tuple[MarketBundleRef, Path]:
    outcome = LocalMarketBundleRepository(
        config=LocalMarketBundleRepositoryConfig(root=root)
    ).publish_market_bundle_v1(
        manifest=manifest,
        stream_payloads=stream_payloads(manifest),
        retention_policy_ref=PUBLICATION_RETENTION_POLICY_REF,
    )
    if outcome.result is None:
        raise AssertionError("expected publication success")
    return (
        outcome.result.bundle_ref,
        root / outcome.result.repository_path.final_directory_relative_path,
    )


def collect(
    reader: LocalMarketBundleReader,
    stream_key: str,
    *,
    batch_size: int,
    cursor: EventCursor | None = None,
) -> tuple[tuple[str, ...], tuple[str, ...], EventCursor]:
    current = cursor or reader.open_cursor(stream_key, batch_size=batch_size)
    if isinstance(current, InputValidationFailure):
        raise AssertionError("expected cursor")

    event_ids: list[str] = []
    event_hashes: list[str] = []
    while not current.exhausted:
        batch, current = reader.read_batch(current)
        event_ids.extend(event.event_id for event in batch)
        event_hashes.extend(event.event_hash for event in batch)
    return tuple(event_ids), tuple(event_hashes), current


def golden_payload(root: Path, manifest: MarketBundleManifest) -> dict[str, object]:
    ref, final = publish(root, manifest)
    reader = LocalMarketBundleReader.open(repository_root=root, bundle_ref=ref)
    stream_key = manifest.streams[0].stream_key
    missing_capability = reader.validate_requirements(
        required_capabilities=(
            MarketBundleCapability(key="funding_publications", version=1),
        )
    )
    missing_stream = reader.open_cursor("missing.stream", batch_size=1)
    if not isinstance(missing_capability, InputValidationFailure) or not isinstance(
        missing_stream, InputValidationFailure
    ):
        raise AssertionError("expected structured validation failures")

    event_ids, event_hashes, exhausted = collect(
        reader,
        stream_key,
        batch_size=2,
    )
    batch_orders = {
        str(size): list(collect(reader, stream_key, batch_size=size)[0])
        for size in (1, 2, 10)
    }

    return json.loads(
        canonical_bytes(
            {
                "schema_version": 1,
                "fixture_id": "local-market-bundle-reader-v1",
                "bundle_ref": ref.to_canonical_dict(),
                "manifest": reader.manifest.to_canonical_dict(),
                "publication": json.loads((final / "publication.json").read_bytes()),
                "retention_proof": json.loads(
                    (final / "retention-proof.json").read_bytes()
                ),
                "paths": repository_relative_paths(manifest),
                "stream_payload_hashes": list(
                    stream_payload_hashes(manifest).values()
                ),
                "event_ids": event_ids,
                "event_hashes": event_hashes,
                "batch_orders": batch_orders,
                "exhausted_cursor": exhausted.to_canonical_dict(),
                "missing_capability": missing_capability.to_canonical_dict(),
                "missing_stream": missing_stream.to_canonical_dict(),
            }
        )
    )
