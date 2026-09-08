---
id: G08E-ROUTE-PRODUCT-FEE-V2C
proposed_readiness: SEE_PARENT_ACCEPTANCE_MATRIX
registry_status: SEE_PARENT_ACCEPTANCE_MATRIX
owner: cross-cutting acceptance
produces:
  - final source commit plus fixture/artifact hashes recorded in V2C acceptance closure and parent Acceptance Matrix
  - G12H F1 unblocking registry fact
consumes:
  - G08E-V2A Kernel acceptance closure
  - G08E-V2B Runtime binding acceptance closure
  - immutable v1 byte hashes
depends_on:
  contract: [G08E-ROUTE-PRODUCT-FEE-V2A, G08E-ROUTE-PRODUCT-FEE-V2B]
  evidence: [V2A-parent-registry-PASSED, V2B-parent-registry-PASSED, legacy-parity, full-suite]
  write_conflict: [acceptance-registry]
fan_out: [G12H-EFFECTIVE-UNTIL-SUPERSEDED-V2]
---

# G08E-V2C Route/product fee acceptance

## Status

The parent [Acceptance Matrix](../../acceptance-matrix.md) is the sole current status authority; this frontmatter intentionally delegates status to that registry. This file records acceptance evidence, not a second Gate status. It creates no economics, Runtime selection semantics, profile/build fields, canonical preimages, fixtures, or publication artifacts.

## Required acceptance closure

V2C requires all of the following closure evidence:

1. V2A proof that exact pure Kernel contract/golden/architecture tests pass, including MISSING_FILL, upper execution-time bound, query provenance, separate ChinaClear/HKSCC, XSHE-only projection, source refs, IDs, and exports.
2. V2B proof that explicit immutable Runtime selection and additive v2 profile/build/Semantic Run binding pass, and direct structurally valid Authority substitution changes identity and is rejected before fee use.
3. Legacy G08E/G08H parity and the full repository suite.
4. The five protected raw fixture SHA-256 records, import-boundary report, mypy, lock check, gitleaks, clean diff/index/status, and independent review records.
5. Verification that no provider/archive completeness, July-2026 closure, decision grade, live/deployment, account-statement parity, or non-notional-cost claim was introduced.

## Acceptance decision

Only a separate authorized parent Acceptance Matrix `PASSED` registry fact after every closure item is present may mark V2C accepted. V2C records the final source commit plus fixture/artifact hashes in this plan's acceptance closure and the parent Acceptance Matrix; it does not create a new receipt file. That registry fact authorizes G12H F1 to resume only for `DOMESTIC + ORDINARY_A_SHARE`; it does not pass F1, create a RuleBook authority for July 2026, or alter its closure/publication/analyzer gates.

Any missing, stale, contradictory, or byte-mutating closure item leaves V2C blocked. No merge or push belongs to the acceptance plan.

## Acceptance closure

Status: `PASSED` at final implementation source `5cbc3da58293d16571c662a1f1d2158f3c0f0017`.

Accepted immutable implementation sources:

- V2A Kernel: `b9f959a68a6e42d668253d0592ae65a08cedaeb5`;
- V2B Runtime binding: `a186d6512cbbb381ec8fb1db2137f5a994fe8389`;
- parent fan-in base: `5cbc3da58293d16571c662a1f1d2158f3c0f0017`.

Accepted artifact and protected-byte hashes:

```text
5f0241887237a568f411a7d4a664482848ee134202d930903404aaf367f463e0  tests/fixtures/kernel/profiles/cn_a_share/commission-tax-v2.json
d61d324aa02a07c368e2377f76d9da37ea0e952367b158155d7076aadaac4dbd  packages/backtest-runtime/src/crypto_quant_backtest/cn_a_share_fee_v2_binding.py
3ef26743bc9cebfe546f77812c6773cbdf3353e0337d03ed512d5f1c396f702b  tests/fixtures/kernel/profiles/cn_a_share/commission-tax-v1.json
aa032668a5207b61b6c8815894e0087f1c1e734d41e9707c7d32111b6c1cd79f  tests/fixtures/runtime/profiles/cn-a-share-resolved-profile-composition-v1.json
08358c1c0d2144fb23c1b1c8862fa6c879bd285533e5fa415e5cc0273013e905  tests/fixtures/runtime/engine/cn-a-share-resolved-profile-development-journey-v1.json
19017a07fbfd2da954483648fb168d87212f88e92fccca7c28fb0a514b202515  tests/fixtures/market_data/rule_authorities/cn-a-share-development-v1/declaration.json
7a95188cf05d401fcaed80b548f82f22f0b9bc23f6423c6ff1190de775291f7d  tests/fixtures/market_data/rule_authorities/cn-a-share-development-v1/publication.expected.json
```

Validation closure (commands were executed from the named V2 worktrees unless marked clean-detached):

```text
uv run --locked pytest -q tests/kernel/profiles/cn_a_share/test_commission_tax.py tests/kernel/profiles/cn_a_share/test_commission_tax_v2.py tests/kernel/profiles/cn_a_share/test_commission_tax_v2_contract.py tests/kernel/profiles/cn_a_share/test_commission_tax_v2_architecture.py tests/architecture/test_g08h_cn_a_share_composition_boundary.py
=> V2A compatibility: 42 passed

uv run --locked pytest -q
=> V2A live: 2091 passed
=> V2A clean-detached at b9f959a: 2091 passed

uv run --locked pytest -q tests/runtime/profiles/cn_a_share/test_route_product_fee_v2_binding.py tests/architecture/test_g08e_route_product_fee_v2_runtime_boundary.py
=> V2B focused: 6 passed

uv run --locked pytest -q tests/runtime/profiles/cn_a_share tests/architecture/test_g08h_cn_a_share_composition_boundary.py tests/architecture/test_g08e_route_product_fee_v2_runtime_boundary.py tests/runtime/resolution/test_execution_case_identity.py tests/runtime/engine/test_financial_dispatch_contracts.py tests/kernel/profiles/cn_a_share/test_commission_tax_v2.py tests/kernel/profiles/cn_a_share/test_commission_tax_v2_contract.py
=> V2B broader profile/identity/financial: 86 passed

uv run --locked pytest -q
=> V2B live: 2097 passed
=> V2B clean-detached at a186d65: 2097 passed

uv run --offline --with pyright pyright --pythonpath .venv/bin/python packages/trading-kernel/src/crypto_quant_trading/profiles/cn_a_share/commission_tax_v2.py
=> V2A Pyright: 0 errors

uv run --offline --with pyright pyright --pythonpath .venv/bin/python packages/backtest-runtime/src/crypto_quant_backtest/cn_a_share_fee_v2_binding.py tests/runtime/profiles/cn_a_share/test_route_product_fee_v2_binding.py tests/architecture/test_g08e_route_product_fee_v2_runtime_boundary.py
=> V2B Pyright: 0 errors

uv run --offline --with mypy mypy packages/backtest-runtime/src/crypto_quant_backtest/cn_a_share_fee_v2_binding.py
=> V2B mypy: Success, no issues found

uv run --locked python tools/architecture/check_import_boundaries.py --root . --policy architecture/import-boundaries.toml --report <report>
=> V2A: 119 files, no violations; live/clean report sha256:05ba82639476ab7f8f968801ee7431f0bf2c6b9fdd3e075a3a34b4ed1e90b632
=> V2B: 120 files, no violations; live/clean report sha256:2ec2585cf7a8b5b4db3db4e230c2aa2c76edef5904dd052b5c69943d9acada10

uvx --offline ruff format --check <changed V2 files> && uvx --offline ruff check <changed V2 files>
uv run --locked python -m compileall -q <changed package src> && uv lock --check && git diff --check
gitleaks detect --no-banner --source . --no-git
=> passed; gitleaks reported no leaks
```

Final independent correctness, security, identity, economics, governance, and acceptance reviews reported no blocker, high, or medium implementation finding. The first V2C evidence review blocked the registry wording until these exact commands and complete hashes were added; this closure includes that correction.

The acceptance authorizes G12H F1 work to resume only for execution-enforced `DOMESTIC + ORDINARY_A_SHARE`. It introduces no Northbound/preferred/ETF economics, July-2026 authority, provider/archive completeness, decision-grade, live/deployment, account-statement parity, or non-notional-cost claim.
