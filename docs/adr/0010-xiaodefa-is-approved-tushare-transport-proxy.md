# ADR 0010: Xiaodefa Is an Approved Tushare Transport Proxy

- Status: Accepted
- Date: 2026-08-24
- Scope: exact Backtest-owned Tushare acquisitions through the pinned Xiaodefa transport

## Context

The official Tushare account currently available to Backtest cannot call
`bak_basic`. The project owner approved the documented Xiaodefa service as an
officially accepted transport proxy for Tushare-compatible calls. The proxy exposes
the Tushare request/response grammar over a different transport endpoint and uses a
separate 56-character credential.

Treating the proxy as an untracked endpoint override would lose source identity,
credential boundaries, and deterministic replay. Treating it as a generic provider
would create an unapproved provider extension mechanism.

## Decision

For exact contracts that opt in to this ADR:

- semantic provider identity remains `tushare.pro`;
- transport identity is `xiaodefa.approved-tushare-proxy.v1`;
- accepted HTTPS endpoints are exactly `https://fast.xiaodefa.cn` and
  `https://tt.xiaodefa.cn`;
- one capture uses one exact endpoint; failover creates a new receipt, Snapshot, and
  downstream identity rather than silently continuing the same capture;
- direct HTTP uses `POST /`, canonical JSON, `Accept-Encoding: gzip`, and the
  `x-api-key` header;
- the exact 56-character credential is supplied only through
  `TUSHARE_PROXY_TOKEN` or an external mode-0600 file and never enters request
  bodies, URLs, receipts, logs, exceptions, fixtures, provenance, or source control;
- redirects are disabled; every 3xx is a redacted non-retry failure so the
  credential cannot escape the pinned endpoint;
- calls are spaced by at least 0.5 seconds and use bounded retry only for transport,
  HTTP 429, and HTTP 5xx failures;
- provider business failures fail closed without copying provider text into durable
  authority.

The transport decision is exact-scope, not a registry, Adapter, SDK override,
provider framework, credential service, cache, or fallback policy. Existing official
Tushare tools and artifacts remain unchanged.

## Authority and qualification

Project authority accepts proxy-delivered response bytes as Tushare response bytes
for the exact acquisition contracts that bind this ADR and the exact endpoint in
their receipts. Locally computed hashes still prove only retained byte identity.
This ADR does not claim provider-global completeness, immutable revisions,
correction lineage, terminal finality, authoritative absence, historical listing
lifecycle closure, corporate-action lifecycle closure, decision grade, live use, or
deployment authorization.

Any exposed proxy key must be rotated before live acquisition. Prior accepted raw
bytes, hashes, receipts, Snapshots, reports, Runs, and grades remain immutable.
