# G12H competent status-register discovery operator provenance

One-off provenance sources for this additive discovery phase.

- GET captures use the immutable Wave 1 harness `evidence/g12h/operator/g12h_wave1_capture.py` (`sha256:85ccf78ce0d595ff9d372c85243d81c49c3bc1be19f868df5936cc2f6977d9ea`).
- `g12h_npc_post_capture.py` captures the exact NPC Stamp Duty Law status query.
- `g12h_redact_register_cookies.py` externalizes exact transient server cookies and leaves SHA-256-redacted tracked copies.
- `g12h_build_register_discovery.py` validates package ledgers and builds the phase manifest/ledger.

Exact executed copies are retained under `operator/executed/`. Root-level NPC/redaction scripts are hardened reconstructions for static checking; they are not substituted for executed-source identity. `redaction-execution-receipt.json` binds the exact redactor hash to the public/private output receipts.
