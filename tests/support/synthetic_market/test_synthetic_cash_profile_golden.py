from __future__ import annotations

import json
from pathlib import Path

from crypto_quant_domain import canonical_bytes

from tests.support.synthetic_market import (
    SYNTHETIC_PROFILE_KEY,
    TestProfileRegistry,
    build_synthetic_bundle,
    build_synthetic_execution_case,
    build_synthetic_target_stream,
)


ROOT = Path(__file__).resolve().parents[3]
GOLDEN = ROOT / "tests/fixtures/support/synthetic-cash-development-profile-v1.json"


def test_synthetic_cash_profile_matches_static_golden_artifact() -> None:
    lookup = TestProfileRegistry(allow_development_profiles=True).lookup(
        SYNTHETIC_PROFILE_KEY
    )
    assert lookup.profile is not None
    profile = lookup.profile
    bundle = build_synthetic_bundle(profile)
    targets = build_synthetic_target_stream(profile)
    execution_case = build_synthetic_execution_case(profile, timeline_batch_size=1)

    try:
        actual = json.loads(
            canonical_bytes(
                {
                    "profile": profile,
                    "profile_digest": profile.profile_digest,
                    "market_profile_digest": profile.market_semantics.profile_digest,
                    "simulation_profile_digest": profile.simulation.profile_digest,
                    "execution_account_profile_digest": (
                        profile.execution_account.profile_digest
                    ),
                    "bundle_ref": bundle.bundle_ref,
                    "target_stream_digest": targets.target_stream_digest,
                    "execution_case_hash": execution_case.case_hash,
                }
            )
        )
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise AssertionError("synthetic profile evidence is not canonical") from error
    try:
        expected_text = GOLDEN.read_text(encoding="utf-8")
        expected = json.loads(expected_text)
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"invalid static golden artifact: {GOLDEN}") from error

    assert actual == expected
