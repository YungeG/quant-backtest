# G12H Wave 1 operator provenance

One-off acquisition and evidence-derivation sources. They are provenance, not installed tools or public APIs.

- `executed-acquisition-schedule.json` freezes all 151 executed request packages, headers, bodies, harness hashes, and captured response hashes.
- `replay_captured_requests.py --check evidence/g12h` verifies the retained schedule; pass an output directory to replay selected or all requests without overwriting evidence.
- Mutable issuer endpoints are not expected to reproduce historical response bytes.
- Private exact-byte stores are required where tracked copies were secret-scanner redacted.
