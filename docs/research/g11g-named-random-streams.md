# G11G Named Random Streams Research

## Scope

G11G needs one deterministic, provider-neutral random stream for Strategy code. It must be reproducible from the frozen Backtest master seed, isolated by Strategy and purpose name, position-addressable by an explicit counter, immutable/checkpointable, and independent of process-global RNG state.

## Primary authorities

1. [`docs/architecture/backtest-system-design.md`](../architecture/backtest-system-design.md), sections **4.6**, **8.4**, **12.4**, **16.8**, **17.4**, and **20.2**:
   - Strategy randomness must use a named stream assigned to that Strategy;
   - stochastic components derive independent streams from the master seed plus semantic component/purpose identity;
   - the stream records algorithm, version, stream key, and seed derivation;
   - global RNG and unregistered streams are forbidden;
   - replay must preserve stream counters.
2. [`packages/backtest-runtime/src/crypto_quant_backtest/resolution.py`](../../packages/backtest-runtime/src/crypto_quant_backtest/resolution.py), `BacktestRequest`:
   - `master_random_seed` is already a required nonnegative integer in canonical request identity;
   - G11G should consume that caller-supplied value rather than read ambient entropy or invent another seed authority.
3. [`packages/trading-domain/src/crypto_quant_domain/canonical.py`](../../packages/trading-domain/src/crypto_quant_domain/canonical.py):
   - `canonical_bytes` gives a stable, type-safe byte preimage for exact stream/draw identity;
   - `canonical_sha256` already defines repository hash notation and avoids a second canonical serializer.
4. [NIST FIPS 180-4, Secure Hash Standard](https://doi.org/10.6028/NIST.FIPS.180-4):
   - SHA-256 deterministically maps a message to a 256-bit digest;
   - the standard explicitly notes secure hash algorithms as usable in generating random numbers/bits.
5. [Python `hashlib` documentation](https://docs.python.org/3/library/hashlib.html):
   - `hashlib.sha256()` is guaranteed available across Python platforms;
   - `digest()` returns the fixed digest of the exact bytes supplied.
6. [`packages/backtest-runtime/src/crypto_quant_backtest/strategy_state.py`](../../packages/backtest-runtime/src/crypto_quant_backtest/strategy_state.py):
   - G11F establishes immutable Strategy business state and checkpoints but intentionally leaves RNG algorithm/counter authority to G11G;
   - G11I can later aggregate StrategyState and NamedRandomStream hashes without merging their authorities.

## Minimal algorithm

Use a versioned SHA-256 counter stream implemented only with stdlib `hashlib` and Domain canonical bytes.

One `NamedRandomStream` stores:

- `master_random_seed: int`;
- `strategy_id: StrategySleeveId`;
- canonical nonempty `stream_key: str`;
- exact `algorithm="sha256-counter"`;
- exact `algorithm_version=1`;
- nonnegative `counter` naming the next draw.

For counter `c`, the draw preimage is exactly:

```text
{
  type: "named_random_stream_draw",
  schema_version: 1,
  algorithm: "sha256-counter",
  algorithm_version: 1,
  master_random_seed,
  strategy_id,
  stream_key,
  counter: c
}
```

`draw_u64()` computes `sha256(canonical_bytes(preimage)).digest()`, interprets the first eight digest bytes as one unsigned big-endian 64-bit integer, and returns `(value, next_stream)` where `next_stream.counter == c + 1`.

The stream is immutable. A draw never mutates itself or any sibling stream. The current stream value is therefore its own checkpoint: reconstructing the same exact fields/counter replays the same next value and continuation.

## Identity and isolation

The stream canonical body binds algorithm/version, master seed, Strategy identity, stream key, and next counter. Its derived `stream_hash` changes when any of those fields changes.

Isolation follows directly from the draw preimage:

- another Strategy cannot perturb this Strategy’s sequence;
- another stream key cannot perturb this purpose’s sequence;
- drawing an unrelated stream cannot advance this immutable stream;
- input/construction order has no role;
- a saved counter resumes the exact suffix.

The master seed is reproducibility evidence, not secret entropy. SHA-256 here is a deterministic simulation primitive, not a cryptographic security, unpredictability, gambling, or key-generation claim.

## Public behavior

G11G v1 needs only one public class:

- `NamedRandomStream`;
- `stream_hash`;
- `draw_u64() -> tuple[int, NamedRandomStream]`;
- canonical serialization.

Do not add a factory, registry, mutable manager, global stream pool, plugin algorithm interface, `random.Random`, NumPy, a distribution library, or a general sampling API. Bounded/distribution sampling can be a later Gate when an exact unbiased contract is required; raw deterministic 64-bit draws are the smallest independently useful seam.

## Checkpoint integration

G11F `StrategyCheckpoint` and G11G `NamedRandomStream` remain separate immutable authorities. G11I may bind their hashes in one invocation/checkpoint audit. G11F state does not absorb RNG counters, and G11G does not absorb Strategy business fields.

Replay fixture:

1. create stream at counter 0;
2. draw values 0 and 1 uninterrupted;
3. save the stream at counter 1;
4. reconstruct the same stream fields/counter;
5. prove the resumed value and suffix hashes equal uninterrupted continuation;
6. draw unrelated Strategy/key streams and prove the original stream/hash/continuation are unchanged.

## Failure and boundary requirements

Reject:

- bool/negative/non-int master seed or counter;
- empty, padded, or non-NFC stream key;
- algorithm/version other than the exact v1 constants;
- non-`StrategySleeveId` Strategy identity;
- mutation/global RNG/ambient entropy/time/process identity entering output;
- hidden random-module/NumPy/provider dependency;
- claims of statistical quality beyond the frozen raw SHA-256-derived bit stream.

## Explicit exclusions

- bounded integers, floats, normal/lognormal or market-impact distributions;
- parameter search, model selection, Monte Carlo orchestration, calibration, or experiment scheduling;
- system entropy, `secrets`, OS randomness, global/process RNG, wall clock, runtime address, Attempt identity;
- StrategyState business fields, model artifacts, Observation selection, Decision scheduling/invocation;
- EngineCheckpoint or deployment authorization.

## Readiness test shape

One contract file, one static golden, and one architecture boundary should freeze:

- exact draw preimage and first-u64 conversion;
- same seed/Strategy/key replay and counter checkpoint parity;
- different seed/Strategy/key/counter separation;
- unrelated-stream draw isolation;
- immutable draw progression and constructor/`dataclasses.replace` controls;
- no global RNG, entropy, time, dependency, callback, Engine, or provider branch.
