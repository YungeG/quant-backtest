# G12M Binance funding revision authority evidence

## Scope

BHA-01B research evidence for correction/revision semantics of settled Binance
USDⓈ-M `GET /fapi/v1/fundingRate` rows. The acceptance basis is exact
unauthenticated first-party bytes. Search-provider excerpts remain secondary
acquisition aids and are not SourceSnapshot members.

## Accepted raw source index

| ID | First-party source and fixed scope | Receipt (UTC) | HTTP | Raw bytes / SHA-256 | Acceptance use |
| --- | --- | --- | --- | --- | --- |
| G1 | Official `binance/binance-futures-connector-python`, commit `d30576a6d8e6edb706c8b013eb11167b58e9c33a` (2022-08-29), `binance/um_futures/market.py` | 2026-08-21T14:48:17.712267Z | 200; exact headers in receipt | `raw/github/funding-rate-request-2022.py`, 18,300 bytes, `e50bd98895e218893124db4cce7126dd128d3621d7d0d14f3545ee9bbf8e3533` | Target-preceding endpoint/request shape only. |
| G2 | Official `binance/binance-connector-python`, commit `38996023660752a75acf7ebbc4f9a504e10e336f` (2025-07-17), generated Funding Rate History response model | 2026-08-21T14:48:18.324983Z | 200; exact headers in receipt | `raw/github/funding-rate-response-model-2025.py`, 3,783 bytes, `263f23947d53df86ca13d4955dedaf6fc8e13d64bd83542a99171e7c8929d32d` | Post-target named response fields; not target-effective. |
| G3 | Same official repository, commit `e44cdc9e57c76154f08676764bb6f21fbdb49c4a` (2026-07-28), generated response model | 2026-08-21T14:48:18.800206Z | 200; exact headers in receipt | `raw/github/funding-rate-response-model-2026.py`, 4,304 bytes, `b3aa5b35ad034d409f60616ef7bed10fe6b553c6ad6eb145fdb32806a9d459d4` | Current named response fields including post-target `rateType`. |
| G4 | Same official repository/commit, USDⓈ-M Futures connector changelog | 2026-08-21T14:48:19.295036Z | 200; exact headers in receipt | `raw/github/usds-futures-changelog-2026.md`, 33,834 bytes, `d360c5215dd600b5f21d0fe186d0d504c2bc1216ba1201d94848eea5b9745ddc` | Dates `rateType` response change to 2026-07-28. |
| API1 | Binance Futures public testnet, unauthenticated `GET /fapi/v1/fundingRate?symbol=BTCUSDT&limit=2` | 2026-08-21T14:48:19.521632Z | 200; exact headers in receipt | `raw/api/testnet-funding-rate-response.json`, 212 bytes, `919927e6693079c947eb7030fe96027aa4ae12bb4d7bb821f3b3064f43534b62` | Independent current response-shape observation; testnet, not production or 2024 authority. |

Each `receipts/*.json` records authentication=`none`, exact request URL/scope,
start/completion epoch nanoseconds, resolved address, HTTP status, raw response
headers, byte count, body SHA-256, and (for GitHub) pinned repository path/commit
and Git blob OID.

## Canonical SourceSnapshot

`source-snapshot.json` is the canonical mapping produced by the existing G12A
contract over the five accepted raw members:

- snapshot ID: `sha256:e8faeb5a146c0ff85f5afca6f740ee9a925a3d47134c4d3495b26fdb5e4b8f25`;
- content tree: `sha256:935355b119ac9445a17fc7e3be19eeb8156914081df21519604182a9fed73f5a`;
- provenance hash: `sha256:9e0f8eaf21ec1feaaa5f1e3a7149fc5bf6777f26e6eff16df71b13bd2f5d6311`;
- `decision_grade_eligible=false`; `deployment_authorized=false`.

The archive is deterministically reconstructed from retained member bytes, modes,
receipt completion times, declared hashes, and provenance. It is not separately
committed because G12A canonical identity intentionally omits archive bytes.

## Upstream/local replay

The four GitHub members were compared byte-for-byte with:

```text
git show <pinned-commit>:<repository-path>
```

in fresh clones of the official repositories. The local SHA-256 values match both
the raw HTTP bodies and `git show` output. Git blob OIDs are retained in receipts.
`manifest.sha256` replays every committed BHA-01B artifact except itself.

## Network fake-IP limitation

This runtime resolved the following hosts into `198.18.0.0/15`:

- `developers.binance.com` → `198.18.3.250`;
- `fapi.binance.com` → `198.18.1.87`;
- `raw.githubusercontent.com` → `198.18.0.75`;
- `testnet.binancefuture.com` → `198.18.4.140`.

Direct developer-doc and production API attempts ended with curl exit 35 before an
HTTP response. GitHub raw and testnet requests succeeded despite their fake-IP
resolution. Exact failure times/scopes/stderr are in
`receipts/network-fake-ip-limitations.json`. No credential, cookie, API key,
authorization header, environment value, or authenticated profile was used.

## Secondary acquisition aids

The `excerpts/` files and `negative-searches.md` preserve the bounded search path
that located candidate first-party material. Their hashes remain replayable, but
they are excluded from `source-snapshot.json` and cannot independently satisfy a
claim or override the accepted raw bytes.

## Acceptance and residual boundary

See `primary-source-review.md`. The raw evidence independently establishes bounded
request/response capability and post-target schema evolution. It does not establish
a production 2024 response vintage, actual correction of a settled row, provider
revision lineage, or permanent finality. Conclusion: `UNKNOWN_CAUSAL_BLOCKER`.
