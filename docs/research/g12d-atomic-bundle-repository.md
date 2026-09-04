# G12D Atomic Local MarketBundle Repository Contract

## Decision

G12D publishes an already-validated `MarketBundleManifest` and exact caller-supplied stream payload bytes into one local `pathlib.Path` content-addressed repository. It provides atomic finalize, immutable old identities, idempotent same-content publication, per-manifest cooperative locking, verification, and a proof of current retrievability.

It does not add a Reader, URI/object-store abstraction, generic repository protocol, wall clock, retention expiry, rebuild trace, coverage qualification, or deployment authority.

## Reused authority

G12D reuses without modifying:

- `crypto_quant_market_data.MarketBundleManifest`;
- `crypto_quant_market_data.MarketBundleRef.from_manifest()`;
- `crypto_quant_domain.canonical_bytes` and `canonical_sha256`.

Builder code may mirror the mechanics in `crypto_quant_backtest._publication` and `crypto_quant_backtest.evidence`—exclusive lock files, hidden staging, fsync, read-only hardening, atomic rename, final verification, and hide/remove rollback—but must never import Runtime.

## Public seam

One production module: `crypto_quant_bundle_builder.local_market_bundle_repository`.

The Builder root adds exactly eight names:

- `LocalMarketBundleRepository`;
- `LocalMarketBundleRepositoryConfig`;
- `MarketBundlePublicationFailureCode`;
- `MarketBundlePublicationFailure`;
- `MarketBundlePublicationOutcome`;
- `MarketBundlePublicationResult`;
- `MarketBundleRepositoryPath`;
- `LocalMarketBundleRetentionProof`.

The only operation is:

```python
LocalMarketBundleRepository.publish_market_bundle_v1(
    *,
    manifest: MarketBundleManifest,
    stream_payloads: Mapping[str, bytes],
    retention_policy_ref: str,
) -> MarketBundlePublicationOutcome
```

No free wrapper function, callback, registry, Reader/Cursor method, URI, or generic Protocol is added.

## Input contract

- Config accepts one absolute `Path` root. The root is operational authority and never enters semantic identity or public evidence.
- `manifest` must be an exact valid `MarketBundleManifest`; its canonical reconstruction must equal the supplied value.
- `stream_payloads` must be an exact mapping whose keys equal the manifest stream-key set and whose values are exact `bytes`.
- Each stream payload hash must equal that stream's `content_hash`. G12D treats bytes as opaque and does not parse, sort, encode, or reinterpret them.
- `retention_policy_ref` is canonical lowercase metadata matching `[a-z][a-z0-9._-]*`; it is not a credential, URL, legal conclusion, duration, or future-retention guarantee.

Because the frozen G12C stream hash is `canonical_sha256(tuple[MarketEvent, ...])`, the first fixture supplies `canonical_bytes(tuple(events_for_stream))` as the opaque payload bytes.

## Identity and layout

`bundle_ref = MarketBundleRef.from_manifest(manifest)` is authoritative. The root path is not identity.

Filesystem segments use the already validated `bundle_key` and the 64 lowercase hex digest from `manifest_hash` without the `sha256:` prefix.

Final layout:

```text
bundles/<bundle_key>/<manifest-digest>/
  manifest.json
  streams/000.payload
  streams/001.payload
  ...
  publication.json
  retention-proof.json
```

Stream files follow `manifest.streams` canonical order. `publication.json` binds schema v1, Bundle ref, repository-relative paths, ordered payload hashes, and retention-proof hash. It contains no attempt ID, UUID, PID, hostname, thread identity, or clock.

Hidden operational paths are outside evidence:

```text
.locks/<bundle_key>/<manifest-digest>.lock
.staging/<bundle_key>/<manifest-digest>/
```

## Durable value types

`MarketBundleRepositoryPath` contains only canonical repository-relative POSIX paths and Bundle identity. `MarketBundlePublicationResult` contains the Bundle ref, repository path, retention proof, and `already_published`.

`LocalMarketBundleRetentionProof` proves only current verified retrievability. Its canonical body contains:

- schema v1 type;
- `bundle_ref`;
- `retention_policy_ref`;
- `manifest_relative_path` and exact manifest source hash;
- ordered stream relative paths and payload hashes;
- `publication_relative_path`;
- `proof_hash = canonical_sha256(body)`.

It contains no absolute root, wall clock, expiry, rebuild window/trace, freshness, decision grade, or deployment claim.

## Failure contract

Failure contains only code, Bundle ref when derivable, and safe repository-relative subject. It never exposes absolute paths, raw payloads, exception text, PID, or platform error details.

Codes and global precedence are exactly:

1. `invalid_input`;
2. `stream_payload_mismatch`;
3. `lock_unavailable`;
4. `final_destination_conflict`;
5. `staging_prepare_failed`;
6. `staging_write_failed`;
7. `staging_verification_failed`;
8. `immutability_failed`;
9. `atomic_finalize_failed`;
10. `unmanaged_publication_state`.

`final_destination_conflict` means a final identity path exists but cannot be verified as the exact same publication. An exact verified final directory is idempotent success, not failure. `unmanaged_publication_state` means rollback could not hide/remove a possibly readable final or staging state; it is last-resort operator-attention evidence, not an automatic retry authorization.

## Publication algorithm

1. Validate input and compute exact payload hashes in canonical stream order.
2. Acquire an exclusive cooperative lock scoped to `(bundle_key, manifest_hash)`; there is no stale-lock breaking or wall-clock expiry.
3. Under the lock, inspect final:
   - exact verified publication → return `already_published=True`;
   - any other existing path/content → conflict.
4. Refuse an existing staging path; G12D never silently adopts or overwrites it.
5. Create staging and write each file through exclusive temporary files, flush and fsync each file, then fsync parent directories.
6. Verify staged path set and all canonical/source hashes exactly.
7. Harden files/directories read-only, fsync, and verify. Permission bits are only accidental-mutation hardening, not the integrity authority.
8. Rename staging to final atomically on the same filesystem, fsync the final parent, then verify the complete final directory again.
9. On pre-final failure, remove staging. On finalize/final-fsync failure, hide and remove the final path. If cleanup cannot prove that no readable partial state remains, return `unmanaged_publication_state`.
10. Release lock. Lock-release failure after verified final publication does not rewrite semantic success; it is local operational residue that causes future `lock_unavailable` until operator recovery.

Old verified final directories are never overwritten or mutated.

## Concurrent deduplication

Different manifest identities may publish concurrently. Same-identity publishers serialize on the per-manifest lock. A contender that observes `lock_unavailable` fails closed; a later retry rechecks final and becomes idempotent success when the first publisher completed.

No in-memory mutex is authoritative and no global repository lock is used.

## Explicit exclusions

- Reader, Cursor, `open_cursor`, `read_batch`, or columnar encoding (G12E);
- partition/batch parity (G12F);
- Source acquisition, normalization, or Bundle validation;
- cloud/object-store/URI/database/network adapters;
- retention duration or future availability guarantee;
- deterministic rebuild proof, coverage, decision grade, deployment authorization;
- OS permission bits as a security boundary;
- automatic stale-lock breaking or ambiguous-state repair.

## Frozen fixture

Fixture ID: `local-market-bundle-repository-v1`.

It must freeze first publish, exact idempotent publish, same-identity conflict, per-manifest lock contention, different-identity concurrency, failure injection at every durable phase, staging/final cleanup, current retrievability proof verification, tampering detection, path/hash repeat parity, and no absolute-path/clock leakage.
