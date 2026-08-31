from __future__ import annotations

from collections import Counter
from dataclasses import replace
from traceback import extract_stack

from crypto_quant_backtest import DeterministicBarEngine
from crypto_quant_backtest.engine import EngineFailureCode
from crypto_quant_domain import canonical_bytes, canonical_sha256
from crypto_quant_trading import (
    LinearDerivativeLedgerProjector,
    LinearDerivativeLedgerReplayRequest,
)

from tests.runtime.providers import (
    test_binance_usdm_tradifi_preparation_v2 as koru_fixture,
)
from tests.runtime.providers import test_binance_usdm_tradifi_provider as koru_provider


def _case():
    prepared = koru_provider._prepare(koru_fixture._raw_scale8_two_funding_bundle())
    assert prepared.failure is None and prepared.result is not None
    assert prepared.result.execution_input_envelope.schema_version == 8
    return prepared.result.execution_case


def test_schema8_funding_artifacts_are_thin() -> None:
    outcome = DeterministicBarEngine().run(_case())

    assert outcome.result is not None
    eligibilities = tuple(
        artifact.payload
        for artifact in outcome.result.financial_artifacts
        if artifact.role.startswith("funding_eligibility.")
    )
    assert len(eligibilities) == 2
    encoded = tuple(canonical_bytes(value) for value in eligibilities)
    assert all(b"availability_projection" not in value for value in encoded)
    assert all(b"accounting_journal" not in value for value in encoded)
    assert max(map(len, encoded)) < 12_000


def test_schema8_rejects_tampered_thin_attestation_before_accounting(
    monkeypatch,
) -> None:
    import crypto_quant_backtest.financial_dispatch as dispatch

    original_derive = dispatch.derive_linear_funding_eligibility_snapshot_v2
    original_assess = dispatch.LinearFundingAccountingV2.assess_financing
    derived_hashes: list[tuple[str, str]] = []
    accounting_calls = 0

    def tampered(**kwargs):
        snapshot = original_derive(**kwargs)
        derived_hashes.append(
            (
                snapshot.eligibility_ledger_state_hash,
                kwargs["eligibility_projection"].ledger_state_hash,
            )
        )
        return replace(
            snapshot,
            eligibility_ledger_state_hash=canonical_sha256(
                {"tampered": snapshot.snapshot_id}
            ),
        )

    def count_assess(self, request, /):
        nonlocal accounting_calls
        accounting_calls += 1
        return original_assess(self, request)

    monkeypatch.setattr(
        dispatch, "derive_linear_funding_eligibility_snapshot_v2", tampered
    )
    monkeypatch.setattr(
        dispatch.LinearFundingAccountingV2, "assess_financing", count_assess
    )
    outcome = DeterministicBarEngine().run(_case())

    assert derived_hashes and all(actual == expected for actual, expected in derived_hashes)
    assert accounting_calls == 0
    assert outcome.result is None
    assert outcome.engine_failure is not None
    assert outcome.engine_failure.code is EngineFailureCode.FINANCIAL_DISPATCH_FAILURE


def test_schema8_reuses_current_and_cutoff_replays_once_per_funding_slot(
    monkeypatch,
) -> None:
    import crypto_quant_backtest.financial_dispatch as dispatch

    counts: Counter[str] = Counter()
    project = LinearDerivativeLedgerProjector.project
    derive = dispatch.derive_linear_funding_eligibility_snapshot_v2
    matches = dispatch.thin_snapshot_v2_matches_replay

    def count_project(self, request, /):
        if type(request) is LinearDerivativeLedgerReplayRequest and any(
            frame.name == "_funding"
            and frame.filename.endswith("financial_dispatch.py")
            for frame in extract_stack()
        ):
            counts["funding_projection"] += 1
        return project(self, request)

    def count_derive(**kwargs):
        counts["derive"] += 1
        return derive(**kwargs)

    def count_matches(*args):
        counts["match"] += 1
        return matches(*args)

    monkeypatch.setattr(LinearDerivativeLedgerProjector, "project", count_project)
    monkeypatch.setattr(
        dispatch, "derive_linear_funding_eligibility_snapshot_v2", count_derive
    )
    monkeypatch.setattr(dispatch, "thin_snapshot_v2_matches_replay", count_matches)

    outcome = DeterministicBarEngine().run(_case())

    assert outcome.result is not None
    assert counts["derive"] == counts["match"] == 2
    # Each funding slot independently replays its current journal and cutoff.
    # The thin derive/match seam must not perform another ledger projection.
    assert counts["funding_projection"] == 4
