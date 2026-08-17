# G12L China A-share Daily Event-Time Declaration v1

## Decision

The `000001.SZ / 2024-01-02` Tushare daily row now has a frozen Builder-owned
session bucket declaration accepted with trade-calendar acquisition commit
`10638db8225f68256c027b1dd1373bacff0d112c`. This resolves the date/session-to-economic-time
blocker for that exact slice without adding a Builder production import of the
Trading Kernel.

It does not resolve decimal/unit mapping, provider revision closure, historical
listing status, or availability.

## Trading-date authority

Backtest's additive acquisition tool captures one exact Tushare `trade_cal`
response:

```bash
TUSHARE_TOKEN=... uv run --locked python \
  -m tools.acquisition.cn_a_share_tushare_trade_calendar \
  --exchange SZSE --trade-date 20240102 \
  --output-dir <new-directory>
```

The response exact-covers one row:

```text
exchange: SZSE
cal_date: 20240102
is_open: 1
pretrade_date: 20231229
```

Frozen identities:

```text
response_sha256: aead455c7bb4ab5ff3966fb06c8c5b640b537767f38ebf99249fad05a8211bf9
receipt_sha256: 42a6bec925179f1262d8c0ca8e3e43b411eb6627da394acba7f326e0e7a8d4c1
snapshot_id: sha256:a887fba46165ac884ce8a8961446f9017c0959d5dbb96863c04915aa94637cc3
content_tree_hash: sha256:51d363114572121b303793ea5d751ab6caee623087650066f610609d30fce7a3
provenance_hash: sha256:7025ec8e72371d2cefb2f7a877c5b7bb98cafff9a35d92cf114b6a845ab17b5b
```

Tushare provides no declared response checksum; G12A `declared_sha256` remains
`null`.

## Session-phase authority

The accepted G08H cash-session implementation freezes Asia/Shanghai phases:

- opening call `[09:15, 09:25)`;
- continuous morning `[09:30, 11:30)`;
- continuous afternoon `[13:00, 14:57)`;
- closing call `[14:57, 15:00)`.

The declaration binds exact implementation and contract evidence:

```text
calendar module SHA-256:
  0382ec521bb5d716064304faabdf976d9fe8f72eb7858eb03a673f5881b69532
G08H calendar/session fixture SHA-256:
  ef2ed7296ca9da16791ca7839583b93f151b1425734f53b02dd6e8556c0dd26d
component key:
  equity.cn_a_share.cash.session.v1
```

The G08H static fixture does not cover `2024-01-02`; it authorizes phase
semantics, while the exact Tushare `trade_cal` response authorizes that this SZSE
date is open. A test-only one-day Kernel calendar verifies the composition. No
production Builder code imports or calls the Kernel.

## Frozen Builder bucket

The existing G12G `BarBucket` contract represents the daily session with four
disjoint open spans and the regular session identity:

```text
session_id: CN.XSHE / 2024-01-02.regular
trading_date: CN.XSHE / 2024-01-02
interval_start: 2024-01-02T01:15:00Z
interval_end_exclusive: 2024-01-02T07:00:00Z
bucket_hash: sha256:b58489aeffd996cfa583caac981bfeb39edf0b93280f787d63b0f6b0855dc7b7
```

For a future canonical daily Bar:

- `event_time` follows the frozen G12G Bar convention and equals
  `interval_start`;
- finality/closed time equals `interval_end_exclusive`;
- lunch and opening pauses remain excluded spans;
- `available_time` remains the separate, much later Tushare daily-response G12A
  acquisition timestamp.

## Remaining limit

This declaration authorizes only the economic session interval for one provider
row. It does not authorize same-day availability, current `stock_basic` as
historical listing state, source corrections, corporate actions, normalization,
G12C/D publication, G12I/K/M, decision-grade, live, or deployment use.
