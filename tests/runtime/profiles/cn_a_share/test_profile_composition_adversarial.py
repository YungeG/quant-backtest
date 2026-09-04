from __future__ import annotations

from dataclasses import replace

import pytest

from crypto_quant_backtest.cn_a_share_profile import (
    CnAShareProfileComposer,
    CnAShareProfileCompositionFailureCode,
    CnAShareProfileCompositionOutcome,
)
from crypto_quant_trading.profiles.cn_a_share import (
    CnAShareListingPhase,
    CnAShareRiskClass,
)
from tests.support.cn_a_share import build_cn_a_share_resolved_request


def _failure_code(request: object) -> CnAShareProfileCompositionFailureCode | None:
    outcome = CnAShareProfileComposer().compose(request)  # type: ignore[arg-type]
    return None if outcome.failure is None else outcome.failure.code


def test_revision_declarations_bind_embedded_terminal_evidence() -> None:
    request = build_cn_a_share_resolved_request()
    announcement_set = request.announcement_revision_set
    register_set = request.register_revision_set
    assert announcement_set is not None
    assert register_set is not None
    forged_announcement = replace(
        announcement_set,
        revision_chain=(
            (
                "forged-announcement-revision",
                None,
                announcement_set.revision_chain[0][2],
            ),
        ),
        terminal_revision_id="forged-announcement-revision",
    )
    forged_register = replace(
        register_set,
        revision_chain=(
            (
                "forged-register-revision",
                None,
                register_set.revision_chain[0][2],
            ),
        ),
        terminal_revision_id="forged-register-revision",
    )
    assert _failure_code(
        replace(request, announcement_revision_set=forged_announcement)
    ) is CnAShareProfileCompositionFailureCode.AUTHORITY_CONTEXT_MISMATCH
    assert _failure_code(
        replace(request, register_revision_set=forged_register)
    ) is CnAShareProfileCompositionFailureCode.AUTHORITY_CONTEXT_MISMATCH


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("risk_class", CnAShareRiskClass.RISK_WARNING),
        ("listing_phase", CnAShareListingPhase.IPO_FIRST_FIVE),
    ),
)
def test_unsupported_rule_context_is_instrument_scope_failure(
    field: str,
    value: CnAShareRiskClass | CnAShareListingPhase,
) -> None:
    request = build_cn_a_share_resolved_request()
    instrument_scope = request.instrument_scope
    assert instrument_scope is not None
    rule_context = replace(instrument_scope.rule_context, **{field: value})
    mutated = replace(
        request,
        instrument_scope=replace(instrument_scope, rule_context=rule_context),
    )
    assert _failure_code(
        mutated
    ) is CnAShareProfileCompositionFailureCode.INSTRUMENT_SCOPE_MISMATCH


def test_fee_and_tax_books_require_the_profile_venue() -> None:
    request = build_cn_a_share_resolved_request()
    instrument_scope = request.instrument_scope
    assert instrument_scope is not None
    venue = instrument_scope.instrument.instrument_id.venue
    market_bands = tuple(
        band for band in request.market_fee_rule_book.bands if band.venue_id != venue
    )
    tax_bands = tuple(
        band for band in request.stamp_duty_rule_book.bands if band.venue_id != venue
    )
    assert market_bands
    assert tax_bands
    mutated = replace(
        request,
        market_fee_rule_book=replace(
            request.market_fee_rule_book,
            bands=market_bands,
        ),
        stamp_duty_rule_book=replace(
            request.stamp_duty_rule_book,
            bands=tax_bands,
        ),
    )
    assert _failure_code(
        mutated
    ) is CnAShareProfileCompositionFailureCode.AUTHORITY_CONTEXT_MISMATCH


def test_identity_conflicts_are_detected_across_history_namespaces() -> None:
    request = build_cn_a_share_resolved_request()
    history = request.identity_history
    assert history is not None
    action_key, action_hash = history.corporate_action_hashes[0]
    alternate_hash = history.register_snapshot_hashes[0][1]
    assert action_hash != alternate_hash
    mutated = replace(
        request,
        identity_history=replace(
            history,
            register_snapshot_hashes=((action_key, alternate_hash),),
        ),
    )
    assert _failure_code(
        mutated
    ) is CnAShareProfileCompositionFailureCode.CROSS_QUERY_IDENTITY_CONFLICT


def test_component_manifests_reject_duplicate_port_authorities() -> None:
    outcome = CnAShareProfileComposer().compose(build_cn_a_share_resolved_request())
    assert outcome.result is not None
    market = outcome.result.market_semantics
    simulation = outcome.result.simulation
    with pytest.raises(ValueError):
        replace(
            market,
            component_manifest=market.component_manifest + (market.component_manifest[0],),
        )
    with pytest.raises(ValueError):
        replace(
            simulation,
            component_manifest=(
                simulation.component_manifest + (simulation.component_manifest[0],)
            ),
        )


def test_resolved_profile_rejects_bool_int_equality_forgery() -> None:
    outcome = CnAShareProfileComposer().compose(build_cn_a_share_resolved_request())
    assert outcome.result is not None
    with pytest.raises((TypeError, ValueError)):
        replace(outcome.result, model_version=True)
    with pytest.raises((TypeError, ValueError)):
        replace(outcome.result, decision_grade_eligible=0)
    with pytest.raises((TypeError, ValueError)):
        replace(outcome.result, profile_qualified=0)
    with pytest.raises((TypeError, ValueError)):
        replace(outcome.result, deployment_authorized=0)


def test_outcome_rejects_duck_typed_branch_authority() -> None:
    success = CnAShareProfileComposer().compose(build_cn_a_share_resolved_request())
    assert success.result is not None

    class DuckResult:
        request = success.result.request
        model_digest = success.result.model_digest

    with pytest.raises(TypeError):
        CnAShareProfileCompositionOutcome(
            success.request_hash,
            success.model_digest,
            DuckResult(),  # type: ignore[arg-type]
            None,
        )
