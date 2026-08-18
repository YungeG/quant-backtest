# Platform Integration v2 model seam acceptance

- **Contract:** `integration-v2-model-build-v1`
- **Contract fixture SHA-256:** `4d6c764b6e0b6374daab462b8b74ce8c9f75b73b68d96979d3e7d3a99bd441bb`
- **Implementation revision:** `82c83c2f0822bd7a3cff736757f64f29f1fdf94b`
- **Backtest owner:** `YungeG`
- **Accepted at:** `2026-08-18T03:59:54.688159Z`
- **Status:** ACCEPTED

## Accepted behavior

- `prepare_model_bound_cash_development_backtest` accepts one public `ModelRevisionTimeline`, an expected model key, and the exact expected `artifact_ref_hash`.
- Preparation selects the point-in-time terminal model and fails before request publication or Attempt creation for unavailable, wrong-key, or substituted evidence.
- `ModelRequestBinding` records only strategy/input names and Backtest-owned timeline/artifact hashes; it does not duplicate `ModelArtifactRef`.
- Nonempty binding evidence enters the Backtest request hash, SemanticRun identity, completed engine execution context, canonical cache validation, and repository reconstruction.
- The existing cash-development path omits the optional binding field and preserves its canonical request bytes.
- One completed and one BLOCKED model-bound run are covered, including replay and hidden-future revision behavior.

## Verification

- Focused provider/model suite: `45 passed`.
- Provider, model revision, resolution, evidence repository, integrity, and architecture suite: `112 passed`.
- Full clean-worktree suite: `1861 passed`.
- Primary and auxiliary LSP diagnostics: clean on all changed Python files.
- Ruff syntax/import-use checks (`E4,E7,E9,F`): clean on all changed Python files.
- Gitleaks working-tree scan with exact canonical-ID fingerprints: no leaks found.

## Exclusions

This acceptance adds no model bytes, deserializer, loader, inference callback, training, feature computation, framework SDK, mutable model registry, private resolved-object exposure, Live authorization, or deployment behavior.
