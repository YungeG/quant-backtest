# ADR 0011: January 2024 Current Official Fee Development Projection

- Status: Accepted
- Date: 2026-09-02
- Scope: Ticket #32 / Ticket #26

## Context

ADR 0007 authorizes a current-official development projection only for its finite July 2026 XSHE target. The January 2024 `000703.SZ` development route needs a finite statutory execution-fee authority before it can compose account-level commission scenarios. The existing August 2023 and July 2026 artifacts cannot be relabeled as January authority.

Strict ADR 0004 successor closure remains unavailable for the target: the public source corpus does not establish a complete authoritative successor index. Treating that absence as a general fee authority or as strict historical closure would be invalid. Refusing every finite development projection, however, would make the source-bounded January route unable to consume its explicitly selected current official fee representations.

## Decision

Authorize one additive current-official **development projection** for exactly:

```text
[target_from, target_to_exclusive)
= [2024-01-02T00:00:00+08:00, 2024-02-01T00:00:00+08:00)
```

The only permitted execution scope is:

```text
XSHE + EQUITY + CNY quote/settlement + AUCTION
+ DOMESTIC + ORDINARY_A_SHARE + trade_notional
```

The projection may use official representations captured after the target only when every selected representation retains exact raw bytes, requested/final URL, media type, receipt time, response/header/redirect identities, source hash, parsed economics, and a receipt-derived observation time. It must bind each selected component’s effective interval, calculation basis, side applicability, route/product scope, and source identity.

Every known material authority candidate must be dispositioned as one of `selected`, `no_economic_effect`, `before_target_already_represented`, `after_target`, `prospective_not_implemented`, or `unresolved`. An unresolved candidate, conflicting selected economics, source/hash mismatch, target/scope drift, or an undispositioned material candidate fails closed.

The development waiver is limited to corpus completeness. It does not create `official_record_as_of`, strict ADR 0004 successor closure, an open-ended fee interval, or a fallback to current/nearest rules. It does not permit HKSCC to become an applied zero charge: domestic route exclusion remains an explicit, separately identified non-applicability disposition.

## Consequences

- The resulting January authority remains finite and development-only. Decision-grade, live, and deployment qualifications remain false.
- ADR 0004 source/economic lineage requirements still apply wherever the selected evidence can establish them; this ADR does not amend strict closure semantics.
- ADR 0005 route/product discrimination remains required. The projection cannot be generalized to Stock Connect, ETFs, preferred stock, XSHG, other months, or other accounts.
- ADR 0007 and all July 2026 artifacts remain byte-identical and unchanged.
- The next work is source/evidence-only. It may not add RuleBooks, commission scenarios, Runtime preparation, Backtest execution, or a provider abstraction until the January authority artifact passes its own verification.
