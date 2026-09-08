# G12H live-status API probe operator provenance

One-off additive capture for the post-ADR-0006 bounded probes.

- `g12h_capture_live_status_api_probes.py` captured three SZSE current-document endpoints and six STA No.39 aging-filter requests.
- `g12h_redact_live_status_probe_cookies.py` externalized exact transient cookie-bearing response bytes to the mode-restricted private store.
- `g12h_build_live_status_api_probes.py` validates package ledgers and exact response semantics, then builds the assessment, operator manifest, root manifest, and root ledger.
- `executed/` contains byte-identical copies of the sources actually run. Root copies are retained for static checks and are not substituted for executed-source identity.
