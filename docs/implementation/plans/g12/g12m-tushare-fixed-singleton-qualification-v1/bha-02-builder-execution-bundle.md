---
id: G12M-TFS-BHA-02
status: BLOCKED_H1
owner: Builder execution-Bundle writer
produces:
  - minimum causal Builder-owned projections required by accepted Profile/schema-3 contracts
  - one complete G12C/D-published execution Bundle
consumes:
  - G12M-TFS-BHA-01 H1
  - exact accepted G12I Events and catalog identity
depends_on:
  contract: [G12M-TFS-BHA-01-H1, G12C, G12D]
  evidence: [accepted G12I canonical report/publication fixture]
  write_conflict: []
fan_in: [G12M-TFS-BHA-03, G12M-TFS-BHA-04, G12M-TFS-BHA-05]
---

# BHA-02 Build the complete exact execution Bundle

## Outcome

Publish one immutable execution Bundle through existing G12C validation and G12D
`LocalMarketBundleRepository`. The Bundle may differ from the G12I evidence Bundle,
but it preserves the accepted G12I stream and Events exactly and adds only streams
required by the accepted BHA-01 Profile requirements and existing schema-3 execution
contracts. BHA-02 owns Bundle/projection construction; it does not decide Profile or
Build eligibility.

## Required membership

- exact accepted G12I stream key, event type, capability/version, count, content hash,
  and all 19 ordered exact `MarketEvent` values;
- one exact precomputed zero-target stream/event required by the production facade;
- only the minimum causal projection streams required by the accepted H1 Profile
  capabilities and existing schema-3 execution contracts;
- exact accepted instrument catalog identity;
- coverage that contains every Event `event_time` and exact `timeline_instant`, with
  `end_exclusive` after the latest accepted G12I Timeline instant;
- one frozen zero-target decision UTC time strictly after the latest accepted G12I
  `available_time`, with its `SimulationInstant` strictly after every accepted G12I
  `timeline_instant`; any represented source phase is explicitly before the decision
  phase, so all 19 exact source Events are in the prior causal cut;
- one Bundle ref/manifest used by resolver, PREP, Timeline, Runner, assessment, and
  repository proof; and
- exact G12D `retention-proof.json` identity/hash later verified only through
  `LocalMarketBundleReader.open`, recorded for direct BHA-02→BHA-05 H1 evidence.

If the accepted H1 Profile requirements and existing schema-3 contracts genuinely
require a daily-to-`price_bars` or daily-to-`bar_open` projection, this node must first
prove the projection is causal and supported by the source payload; otherwise it
fails. Every projected Event has a new identity and directly binds the source G12I
Event hash, exact provider date, exact payload field, event/availability time,
purpose, revision, and projection hash. It performs no gap fill, and it never relabels
a late-available G12I Event as same-time `bar_open` evidence. The target Event may
be composed only after the latest accepted G12I availability/Timeline instant; no
projection or target stream may consume a source Event first visible at or after the
decision phase.

## Forbidden behavior

- changing accepted G12I Events, availability, revision IDs, or stream bytes;
- calling Runtime or importing Kernel;
- G12G aggregation unless BHA-01 H1 explicitly selects an already-accepted exact
  aggregation contract (the default is no aggregation);
- forward fill, synthetic missing Bar, inferred open, nearby value, implicit purpose
  or capability fallback;
- filler capability with no genuine exact-case consumer;
- second repository, registry, catalog, provider framework, or availability DSL; and
- cross-Bundle references or reads.

## Exact write set

- `packages/market-bundle-builder/src/crypto_quant_bundle_builder/g12m_tushare_fixed_singleton_execution_bundle_v1.py`
- `tests/bundle_builder/providers/tushare/test_g12m_tushare_fixed_singleton_execution_bundle_v1.py`
- `tests/architecture/test_g12m_tushare_fixed_singleton_builder_boundary.py`
- `tests/fixtures/market_data/providers/tushare/g12m-fixed-singleton-execution-bundle-v1/`

No Builder root export, accepted G12I/G12K module or fixture, G12C/D contract,
repository implementation, Runtime, Kernel, Acceptance Matrix, or G12 README edit.

## Failure precedence

1. malformed or unaccepted independent H1 authority;
2. malformed or substituted accepted G12I report/publication;
3. accepted G12I stream/Event membership mismatch;
4. projection source/event/availability mismatch;
5. capability or stream excess/missing conflict;
6. target/accounting stream mismatch;
7. coverage/Timeline window or strict pre-decision causal-cut mismatch;
8. G12C validation failure;
9. G12D publication/replay failure;
10. canonical Bundle report reconstruction mismatch.

No failure returns a partial manifest, projection, Bundle ref, or publication.

## Acceptance

- exact G12I stream and all 19 `(event_id, event_hash, timeline_instant)` values
  survive unchanged;
- every authorized projection has one source Event and mutation tests for all bound
  fields;
- complete capability set minimally satisfies accepted H1 Profile requirements and
  existing schema-3 execution contracts, with no filler capability;
- Bundle coverage/window and target scheduling place every accepted G12I source Event
  in the frozen pre-decision causal cut and make post-decision source selection
  invalid; BHA-03/BHA-04 own exact trace-consumption proof;
- G12C validates and G12D first/repeated publication is immutable/idempotent;
- local persisted Reader replays every stream and manifest hash, and exact G12D
  retention-proof identity/hash is available to BHA-03 and directly to BHA-05;
- accepted G12I/G12K and Binance protected fingerprints remain unchanged; and
- focused Builder/G12C/D/Reader, architecture, Ruff/Pyright, diff, and gitleaks checks
  plus independent identity/causality review pass.
