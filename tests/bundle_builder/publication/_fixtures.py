from __future__ import annotations

import hashlib
from collections import defaultdict
from pathlib import Path

from crypto_quant_domain import canonical_bytes
from crypto_quant_market_data import MarketBundleManifest
from crypto_quant_market_data import MarketBundleRef

from tests.bundle_builder.validation._fixtures import call, synthetic_events


PUBLICATION_RETENTION_POLICY_REF = "retention.local-market-bundle-repository-v1"


def _stream_payload_hash(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def bundle_manifest() -> MarketBundleManifest:
    outcome = call(synthetic_events())
    assert outcome.manifest is not None
    return outcome.manifest


def bundle_key(manifest: MarketBundleManifest) -> str:
    return manifest.bundle_key

def bundle_ref(manifest: MarketBundleManifest) -> MarketBundleRef:
    return MarketBundleRef.from_manifest(manifest)


def manifest_relative_path(manifest: MarketBundleManifest) -> str:
    identity = bundle_ref(manifest)
    return (
        f"bundles/{identity.bundle_key}/"
        f"{identity.manifest_hash.removeprefix('sha256:')}/manifest.json"
    )


def stream_payloads(manifest: MarketBundleManifest) -> dict[str, bytes]:
    events = synthetic_events()
    grouped: dict[str, list[object]] = defaultdict(list)
    for event in events:
        grouped[event.stream_key].append(event)

    payloads: dict[str, bytes] = {}
    for stream in manifest.streams:
        payload_bytes = canonical_bytes(tuple(grouped[stream.stream_key]))
        payloads.setdefault(stream.stream_key, payload_bytes)
        assert _stream_payload_hash(payloads[stream.stream_key]) == stream.content_hash
    return payloads


def stream_payload_hashes(manifest: MarketBundleManifest) -> dict[str, str]:
    return {key: _stream_payload_hash(value) for key, value in stream_payloads(manifest).items()}


def final_directory(manifest: MarketBundleManifest) -> str:
    identity = bundle_ref(manifest)
    return f"bundles/{identity.bundle_key}/{identity.manifest_hash.removeprefix('sha256:')}"


def staging_directory(manifest: MarketBundleManifest, root: Path) -> Path:
    identity = bundle_ref(manifest)
    return root / ".staging" / identity.bundle_key / identity.manifest_hash.removeprefix("sha256:")


def lock_path(manifest: MarketBundleManifest) -> str:
    identity = bundle_ref(manifest)
    return f".locks/{identity.bundle_key}/{identity.manifest_hash.removeprefix('sha256:')}.lock"


def canonical_directory_bytes(directory: Path) -> dict[str, str]:
    return {
        path.relative_to(directory).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def manifest_stream_file_names(manifest: MarketBundleManifest) -> tuple[str, ...]:
    return tuple(f"streams/{index:03d}.payload" for index, _ in enumerate(manifest.streams))

def repository_relative_paths(manifest: MarketBundleManifest) -> dict[str, str]:
    identity = bundle_ref(manifest)
    base = f"bundles/{identity.bundle_key}/{identity.manifest_hash.removeprefix('sha256:')}"
    return {
        "final_directory_relative_path": base,
        "manifest_relative_path": f"{base}/manifest.json",
        "publication_relative_path": f"{base}/publication.json",
        "retention_proof_relative_path": f"{base}/retention-proof.json",
        "stream_relative_paths": tuple(f"{base}/{filename}" for filename in manifest_stream_file_names(manifest)),
    }
