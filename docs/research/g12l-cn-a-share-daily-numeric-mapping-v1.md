# G12L China A-share Daily Numeric Mapping v1

## Decision

The exact Tushare `000001.SZ / 2024-01-02` daily response now has a frozen
source-text numeric mapping. JSON number lexemes are parsed directly from the raw
response (`parse_float=str` semantics); binary float values and ambient Decimal
context are not mapping authorities.

This resolves numeric units/scales only. Price-purpose selection and MarketEvent
normalization remain blocked.

## Frozen identity

```text
source daily SHA-256:
  c2950a35c093b983e538f97830b7b3fcb0bba1a7dac98a17bd20f6db9296f846
event-time fixture SHA-256:
  5df297b69479629aa4baf19ea0199fa2f22d2ab42a0ccbb406315052a80a0425
numeric mapping fixture SHA-256:
  8c6f436cfb2c3c41643affcc4a8187e3b04c4293b31b0a76c1893bd60a656b48
mapping hash:
  sha256:8b59762e8820cda614687677733e105ddc62ce4ca84ef6409f1131a7af60c0ad
```

Instrument identity is `xshe:000001`; quote currency is CNY.

## Price fields

All accepted price lexemes use exact scale 2 CNY/share:

| Field | Raw | Units | Scale |
| --- | ---: | ---: | ---: |
| open | `9.39` | 939 | 2 |
| high | `9.42` | 942 | 2 |
| low | `9.21` | 921 | 2 |
| close | `9.21` | 921 | 2 |
| pre-close | `9.39` | 939 | 2 |
| change | `-0.18` | -18 | 2 |

OHLC bounds hold, and `close - pre_close == change` in exact units.

## Percentage change

`pct_chg=-1.9169` maps to signed units `-19169`, scale 4, basis `percent`.
It remains provider-supplied rounded evidence and is not recomputed from change
and pre-close.

## Volume

Tushare daily `vol` is measured in lots. The raw lexeme `1158366.45` maps to:

```text
source units: 115836645
source scale: 2 lots
lot size: 100 shares
normalized units: 115836645
normalized scale: 0 shares
```

The unchanged integer is intentional: multiplying a scale-2 lot value by 100
shares/lot removes the two decimal places.

## Amount

Tushare daily `amount` is measured in thousand CNY. The raw lexeme
`1075742.252` maps to:

```text
source units: 1075742252
source scale: 3 thousand CNY
multiplier: 1000
normalized units: 1075742252
normalized scale: 0 CNY
```

## Remaining purpose blocker

The row is a trade-price daily OHLC source. A single generic event must not be
silently reused across execution-reference and valuation purposes. Before a
normalizer exists, G12B must freeze either separate purpose-specific outputs or a
provider raw-bar schema with an explicit later purpose projection. No settlement,
funding, margin, liquidation, corporate-action, or current-listing semantics may
be inferred from this numeric mapping.
