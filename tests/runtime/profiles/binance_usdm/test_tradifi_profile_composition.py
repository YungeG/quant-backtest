from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

import pytest
from crypto_quant_backtest import (
    BinanceUsdmProfileComposer,
    BinanceUsdmTradifiProfileComposer,
    BinanceUsdmTradifiProfileCompositionFailureCode,
    BinanceUsdmTradifiResolvedProfile,
    SimulationComponentRef,
    SimulationPortType,
    SlippageApplicabilityEnvelope,
    SlippageLimitation,
    SlippageModelKind,
    TimelineWindow,
)
from crypto_quant_domain import (
    ArtifactRef,
    InstrumentId,
    Scale,
    UtcInstant,
    canonical_sha256,
)
from crypto_quant_trading.funding_accounting import LinearFundingApplicationKey
from crypto_quant_trading.profiles.binance_usdm import (
    BinanceUsdmDeferredRuleKey,
    BinanceUsdmFundingSourceModel,
    BinanceUsdmOrderRuleModel,
)

from tests.runtime.profiles.binance_usdm._fixtures import (
    composition_request as ordinary_composition_request,
)

from ._tradifi_fixtures import END, HOUR, START, composition_request


def _compose(**overrides):
    return BinanceUsdmTradifiProfileComposer().compose(
        composition_request(**overrides)
    )


def test_composes_separate_tradifi_profiles_registry_and_dispatcher() -> None:
    outcome = _compose()

    assert outcome.failure is None
    assert isinstance(outcome.result, BinanceUsdmTradifiResolvedProfile)
    result = outcome.result
    assert result.market_registration.profile_key == "crypto.binance_usdm.tradifi.v1"
    assert (
        result.simulation_registration.profile_key
        == "bar.next_eligible_trade_event.tradifi.v1"
    )
    assert result.execution_account_registration.profile_key == "binance.usdm.standard-cross.v1"
    assert result.simulation.fill_builder.liquidity_role == "taker"
    assert result.simulation.slippage_model.basis_points_units == 5
    assert (
        result.simulation.slippage_model.component_ref.component_key
        == SlippageModelKind.DETERMINISTIC_BPS_V1.value
    )
    assert (
        result.simulation.component_manifest[0].port_type.value
        == "closeout_policy"
    )
    assert result.profile_registry.market_semantics_profiles == (
        result.market_registration,
    )
    assert result.profile_registry.simulation_profiles == (
        result.simulation_registration,
    )
    assert result.financial_dispatcher_spec.dispatcher_key == (
        "crypto.binance_usdm.tradifi.linear-financial-dispatch.v1"
    )
    assert not result.decision_grade_eligible
    assert not result.deployment_authorized


def test_nonzero_slippage_calibration_changes_simulation_identity() -> None:
    request = composition_request()
    slippage = request.slippage_model
    changed_slippage = replace(
        slippage,
        component_ref=replace(
            slippage.component_ref,
            component_digest=canonical_sha256(
                {
                    "calibration": "koruusdt-first-retained-trade-v2",
                    "basis_points": 6,
                    "envelope": slippage.applicability_envelope.envelope_hash,
                }
            ),
        ),
        calibration_ref=replace(
            slippage.calibration_ref,
            calibration_version=2,
            calibration_digest=canonical_sha256({"basis_points": 6}),
        ),
        basis_points_units=6,
    )

    baseline = _compose()
    changed = _compose(slippage_model=changed_slippage)

    assert baseline.result is not None
    assert changed.result is not None
    assert changed.result.simulation.profile_digest != (
        baseline.result.simulation.profile_digest
    )
    assert changed.result.profile_digest != baseline.result.profile_digest
    assert changed.result.simulation.profile_key == baseline.result.simulation.profile_key
    assert changed.result.simulation.fill_builder.liquidity_role == "taker"


def test_replay_is_stable_and_forged_resolved_profile_is_rejected() -> None:
    request = composition_request()
    composer = BinanceUsdmTradifiProfileComposer()

    first = composer.compose(request)
    replay = composer.compose(request)

    assert first == replay
    assert first.outcome_hash == replay.outcome_hash
    assert first.result is not None
    with pytest.raises(ValueError, match="resolved TradFi profile"):
        replace(first.result, model_digest="sha256:" + "0" * 64)


def test_tradifi_identity_is_disjoint_without_changing_ordinary_hashes() -> None:
    ordinary = BinanceUsdmProfileComposer().compose(ordinary_composition_request())
    tradifi = _compose()

    assert ordinary.result is not None
    assert tradifi.result is not None
    assert ordinary.result.profile_digest == (
        "sha256:5f0ab193c16122b85f12779cce233da2d9e9d239cff2f2239c6e0ae5bdb5b583"
    )
    assert ordinary.result.market_semantics.profile_digest == (
        "sha256:434ffee82c2cb02740b65b571291e0a6a0dec367374c803d460b2776edb99418"
    )
    assert ordinary.result.simulation.profile_digest == (
        "sha256:b4821b5866a8bc5c40d4f7727394279853f9a948519f5b9489840434c7cdb1cd"
    )
    assert tradifi.result.profile_digest != ordinary.result.profile_digest
    assert tradifi.result.market_registration.profile_key != (
        ordinary.result.market_registration.profile_key
    )
    assert tradifi.result.simulation_registration.profile_key != (
        ordinary.result.simulation_registration.profile_key
    )


def _special_funding_sources():
    request = composition_request()
    regular = request.funding_sources[0]
    special = replace(
        regular.selected_record,
        funding_time_milliseconds=(START.epoch_nanoseconds + HOUR) // 1_000_000,
        rate_type="Special",
        event_id="funding:KORUUSDT:special",
    )
    book = replace(
        regular.query.funding_book,
        records=regular.query.funding_book.records + (special,),
    )
    outcome = BinanceUsdmFundingSourceModel().resolve_funding_source(
        replace(regular.query, funding_book=book)
    )
    assert outcome.result is not None
    return (outcome.result,)


def _unsupported_deferred_order_rules():
    request = composition_request()
    order = request.order_rules
    assert order is not None
    band = replace(
        order.active_band,
        deferred_rule_keys=(
            BinanceUsdmDeferredRuleKey.MAX_NUM_ORDERS.value,
            BinanceUsdmDeferredRuleKey.MAX_NUM_ALGO_ORDERS.value,
            BinanceUsdmDeferredRuleKey.PERCENT_PRICE.value,
        ),
    )
    book = replace(order.query.rule_book, bands=(band,))
    outcome = BinanceUsdmOrderRuleModel().resolve_order_rules(
        replace(order.query, rule_book=book)
    )
    assert outcome.result is not None
    return outcome.result


def test_frozen_mixed_invalid_failure_precedence() -> None:
    request = composition_request()
    ordinary_instrument = request.price_purposes[0].query.instrument_metadata
    cases = (
        (
            BinanceUsdmTradifiProfileCompositionFailureCode.MISSING_TRADIFI_INSTRUMENT_METADATA,
            {"instrument_metadata": None, "calendar_refs": (), "account_profile": None},
        ),
        (
            BinanceUsdmTradifiProfileCompositionFailureCode.FOREIGN_INSTRUMENT_METADATA,
            {"instrument_metadata": ordinary_instrument, "calendar_refs": ()},
        ),
        (
            BinanceUsdmTradifiProfileCompositionFailureCode.CROSS_BAND_COVERAGE_MISMATCH,
            {
                "timeline_window": TimelineWindow(
                    UtcInstant(START.epoch_nanoseconds - 20 * HOUR),
                    UtcInstant(START.epoch_nanoseconds - 20 * HOUR),
                    UtcInstant(START.epoch_nanoseconds - 19 * HOUR),
                ),
                "calendar_refs": (),
            },
        ),
        (
            BinanceUsdmTradifiProfileCompositionFailureCode.CALENDAR_REF_MISMATCH,
            {"calendar_refs": (), "post_adjustment_unit_regime_ref": None},
        ),
        (
            BinanceUsdmTradifiProfileCompositionFailureCode.UNIT_REGIME_REF_MISMATCH,
            {"post_adjustment_unit_regime_ref": None, "price_purposes": ()},
        ),
        (
            BinanceUsdmTradifiProfileCompositionFailureCode.MISSING_PRICE_PURPOSE,
            {"price_purposes": (), "funding_sources": (), "account_profile": None},
        ),
        (
            BinanceUsdmTradifiProfileCompositionFailureCode.MISSING_FUNDING_SOURCE,
            {"funding_sources": (), "account_profile": None},
        ),
        (
            BinanceUsdmTradifiProfileCompositionFailureCode.SPECIAL_FUNDING_UNSUPPORTED,
            {"funding_sources": _special_funding_sources(), "account_profile": None},
        ),
        (
            BinanceUsdmTradifiProfileCompositionFailureCode.MISSING_ACCOUNT_PROFILE,
            {"account_profile": None, "account_capacity": None},
        ),
        (
            BinanceUsdmTradifiProfileCompositionFailureCode.MISSING_ACCOUNT_CAPACITY,
            {"account_capacity": None},
        ),
    )
    for expected, overrides in cases:
        outcome = _compose(**overrides)
        assert outcome.result is None
        assert outcome.failure is not None
        assert outcome.failure.code is expected


def test_calendar_and_unit_authority_identities_are_exact_and_ordered() -> None:
    request = composition_request()
    xkrx, arcx = request.calendar_refs
    unit = request.post_adjustment_unit_regime_ref
    assert unit is not None
    cases = (
        (
            BinanceUsdmTradifiProfileCompositionFailureCode.CALENDAR_REF_MISMATCH,
            {
                "calendar_refs": (
                    ArtifactRef("wrong_calendar", 1, xkrx.content_hash),
                    arcx,
                )
            },
        ),
        (
            BinanceUsdmTradifiProfileCompositionFailureCode.CALENDAR_REF_MISMATCH,
            {"calendar_refs": (replace(xkrx, schema_version=2), arcx)},
        ),
        (
            BinanceUsdmTradifiProfileCompositionFailureCode.CALENDAR_REF_MISMATCH,
            {"calendar_refs": (arcx, xkrx)},
        ),
        (
            BinanceUsdmTradifiProfileCompositionFailureCode.UNIT_REGIME_REF_MISMATCH,
            {
                "post_adjustment_unit_regime_ref": ArtifactRef(
                    "wrong_unit_regime", 1, unit.content_hash
                )
            },
        ),
        (
            BinanceUsdmTradifiProfileCompositionFailureCode.UNIT_REGIME_REF_MISMATCH,
            {"post_adjustment_unit_regime_ref": replace(unit, schema_version=2)},
        ),
    )

    for expected, overrides in cases:
        outcome = _compose(**overrides)
        assert outcome.failure is not None
        assert outcome.failure.code is expected


def test_market_authorities_enforce_identity_and_resolved_hashes_cannot_be_forged() -> None:
    outcome = _compose()
    assert outcome.result is not None
    result = outcome.result
    market = result.market_semantics
    xkrx, arcx = market.calendar_refs

    with pytest.raises(ValueError, match="ordered XKRX and ARCX"):
        replace(market, calendar_refs=(arcx, xkrx))
    with pytest.raises(ValueError, match="unit_regime_ref identity"):
        replace(
            market,
            post_adjustment_unit_regime_ref=replace(
                market.post_adjustment_unit_regime_ref,
                artifact_type="wrong_unit_regime",
            ),
        )

    forged_markets = (
        replace(
            market,
            calendar_refs=(
                replace(xkrx, content_hash="sha256:" + "aa" * 32),
                arcx,
            ),
        ),
        replace(
            market,
            post_adjustment_unit_regime_ref=replace(
                market.post_adjustment_unit_regime_ref,
                content_hash="sha256:" + "bb" * 32,
            ),
        ),
    )
    for forged in forged_markets:
        with pytest.raises(ValueError, match="resolved TradFi profile"):
            replace(result, market_semantics=forged)


def test_calendar_unit_and_slippage_admission_bind_model_and_source_manifest() -> None:
    request = composition_request()
    baseline = BinanceUsdmTradifiProfileComposer().compose(request)
    xkrx, arcx = request.calendar_refs
    unit = request.post_adjustment_unit_regime_ref
    assert unit is not None
    changed_outcomes = (
        _compose(
            calendar_refs=(
                replace(xkrx, content_hash="sha256:" + "44" * 32),
                arcx,
            )
        ),
        _compose(
            post_adjustment_unit_regime_ref=replace(
                unit,
                content_hash="sha256:" + "55" * 32,
            )
        ),
        _compose(
            admitted_maximum_quantity=replace(
                request.admitted_maximum_quantity,
                units=request.admitted_maximum_quantity.units - 1,
            )
        ),
    )
    envelope = request.slippage_model.applicability_envelope
    expanded_slippage = replace(
        request.slippage_model,
        applicability_envelope=SlippageApplicabilityEnvelope.create(
            envelope_key=envelope.envelope_key,
            envelope_version=envelope.envelope_version,
            instrument_id=envelope.instrument_id,
            valid_from=envelope.valid_from,
            valid_to_exclusive=envelope.valid_to_exclusive,
            maximum_quantity=envelope.maximum_quantity,
            allowed_market_state_keys=("normal", "stressed"),
        ),
    )
    state_baseline = _compose(slippage_model=expanded_slippage)
    state_changed = _compose(
        slippage_model=expanded_slippage,
        required_market_state_keys=("normal", "stressed"),
    )

    assert baseline.result is not None
    for changed in changed_outcomes:
        assert changed.result is not None
        assert changed.model_digest != baseline.model_digest
        assert changed.result.source_manifest != baseline.result.source_manifest
    assert state_baseline.result is not None
    assert state_changed.result is not None
    assert state_changed.model_digest != state_baseline.model_digest
    assert state_changed.result.source_manifest != state_baseline.result.source_manifest


def test_context_mismatches_precede_coverage_checks() -> None:
    request = composition_request()
    instrument_id = request.slippage_model.applicability_envelope.instrument_id
    foreign = InstrumentId(instrument_id.venue, "foreign-tradifi-context")
    order = deepcopy(request.order_rules)
    margin = deepcopy(request.margin_tiers)
    assert order is not None
    assert margin is not None
    object.__setattr__(order.active_band, "instrument_id", foreign)
    object.__setattr__(margin.active_band, "instrument_id", foreign)

    for overrides in ({"order_rules": order}, {"margin_tiers": margin}):
        outcome = _compose(**overrides)
        assert outcome.failure is not None
        assert outcome.failure.code is (
            BinanceUsdmTradifiProfileCompositionFailureCode.INSTRUMENT_CONTEXT_MISMATCH
        )

    funding = request.funding_sources[0]
    foreign_key = LinearFundingApplicationKey.derive("foreign-account", funding.slot_id)
    funding_outcome = BinanceUsdmFundingSourceModel().resolve_funding_source(
        replace(funding.query, application_key=foreign_key)
    )
    assert funding_outcome.result is not None
    outcome = _compose(funding_sources=(funding_outcome.result,))
    assert outcome.failure is not None
    assert outcome.failure.code is (
        BinanceUsdmTradifiProfileCompositionFailureCode.ACCOUNT_CONTEXT_MISMATCH
    )


def test_order_embedded_query_identity_mismatch_precedes_later_failures() -> None:
    request = composition_request()
    order = deepcopy(request.order_rules)
    assert order is not None
    instrument_id = order.active_band.instrument_id
    foreign = InstrumentId(instrument_id.venue, "foreign-order-query-context")
    object.__setattr__(
        order.query.instrument_metadata.instrument,
        "instrument_id",
        foreign,
    )

    outcome = _compose(order_rules=order, calendar_refs=())

    assert order.active_band.instrument_id == instrument_id
    assert outcome.failure is not None
    assert outcome.failure.code is (
        BinanceUsdmTradifiProfileCompositionFailureCode.INSTRUMENT_CONTEXT_MISMATCH
    )


def test_margin_embedded_book_identity_mismatch_precedes_later_failures() -> None:
    request = composition_request()
    margin = deepcopy(request.margin_tiers)
    assert margin is not None
    instrument_id = margin.active_band.instrument_id
    foreign = InstrumentId(instrument_id.venue, "foreign-margin-book-context")
    object.__setattr__(margin.query.rule_book, "instrument_id", foreign)

    outcome = _compose(margin_tiers=margin, calendar_refs=())

    assert margin.active_band.instrument_id == instrument_id
    assert outcome.failure is not None
    assert outcome.failure.code is (
        BinanceUsdmTradifiProfileCompositionFailureCode.INSTRUMENT_CONTEXT_MISMATCH
    )


def test_account_embedded_book_identity_mismatch_precedes_later_failures() -> None:
    request = composition_request()
    account = deepcopy(request.account_profile)
    assert account is not None
    account_id = account.active_band.account_id
    object.__setattr__(
        account.query.account_profile_book,
        "account_id",
        "foreign-account-book-context",
    )

    outcome = _compose(account_profile=account, calendar_refs=())

    assert account.active_band.account_id == account_id
    assert outcome.failure is not None
    assert outcome.failure.code is (
        BinanceUsdmTradifiProfileCompositionFailureCode.ACCOUNT_CONTEXT_MISMATCH
    )


def test_evidence_unavailable_precedes_later_account_and_capacity_invalidity() -> None:
    request = composition_request()
    future = replace(
        request.composed_at,
        instant=UtcInstant(request.composed_at.instant.epoch_nanoseconds + 1),
    )
    account_query_future = deepcopy(request.account_profile)
    account_band_future = deepcopy(request.account_profile)
    assert account_query_future is not None
    assert account_band_future is not None
    object.__setattr__(account_query_future.query, "captured_at", future)
    object.__setattr__(account_query_future, "can_trade", False)
    object.__setattr__(account_band_future.active_band, "available_at", future)
    object.__setattr__(account_band_future, "margin_type", "ISOLATED")
    assert request.account_capacity is not None
    capacity_future = replace(
        request.account_capacity,
        available_at=future,
        source_key="later-invalid-capacity-source",
    )

    for overrides in (
        {"account_profile": account_query_future},
        {"account_profile": account_band_future},
        {"account_capacity": capacity_future},
    ):
        outcome = _compose(**overrides)
        assert outcome.failure is not None
        assert outcome.failure.code is (
            BinanceUsdmTradifiProfileCompositionFailureCode.EVIDENCE_NOT_AVAILABLE
        )


def test_slippage_admission_quantity_and_required_states_must_fit_envelope() -> None:
    request = composition_request()
    admitted = request.admitted_maximum_quantity
    cases = (
        replace(admitted, units=admitted.units + 1),
        replace(admitted, scale=Scale(admitted.scale.places - 1)),
        replace(admitted, instrument_id="foreign-instrument"),
    )
    for quantity in cases:
        outcome = _compose(admitted_maximum_quantity=quantity)
        assert outcome.failure is not None
        assert outcome.failure.code is (
            BinanceUsdmTradifiProfileCompositionFailureCode.SLIPPAGE_APPLICABILITY_MISMATCH
        )

    state_outcome = _compose(required_market_state_keys=("normal", "stressed"))
    assert state_outcome.failure is not None
    assert state_outcome.failure.code is (
        BinanceUsdmTradifiProfileCompositionFailureCode.SLIPPAGE_APPLICABILITY_MISMATCH
    )


def test_required_market_state_keys_are_canonical_nonempty_and_unique() -> None:
    request = composition_request(required_market_state_keys=("stressed", "normal"))
    assert request.required_market_state_keys == ("normal", "stressed")

    for states in ((), ("normal", "normal")):
        with pytest.raises(ValueError, match="nonempty and unique"):
            composition_request(required_market_state_keys=states)


def test_profile_manifests_reject_duplicate_ports_and_forged_liquidity() -> None:
    outcome = _compose()
    assert outcome.result is not None
    market = outcome.result.market_semantics
    simulation = outcome.result.simulation

    with pytest.raises(ValueError, match="exact-cover ProfilePortType"):
        replace(
            market,
            component_manifest=market.component_manifest
            + (market.component_manifest[0],),
        )
    with pytest.raises(ValueError, match="exact-cover SimulationPortType"):
        replace(
            simulation,
            component_manifest=simulation.component_manifest
            + (simulation.component_manifest[0],),
        )

    forged = tuple(
        replace(value, component_digest="sha256:" + "cc" * 32)
        if value.port_type is SimulationPortType.LIQUIDITY_MODEL
        else value
        for value in simulation.component_manifest
    )
    with pytest.raises(ValueError, match="liquidity component"):
        replace(simulation, component_manifest=forged)


def test_zero_out_of_envelope_and_deferred_rules_fail_in_order() -> None:
    request = composition_request()
    slippage = request.slippage_model
    zero = replace(
        slippage,
        component_ref=SimulationComponentRef(
            SimulationPortType.SLIPPAGE_MODEL,
            SlippageModelKind.ZERO_SLIPPAGE_DEVELOPMENT_V1.value,
            1,
            "sha256:" + "44" * 32,
        ),
        basis_points_units=0,
        basis_points_scale=Scale(0),
        limitations=(SlippageLimitation.ZERO_SLIPPAGE_DEVELOPMENT_ONLY,),
    )
    zero_outcome = _compose(
        slippage_model=zero,
        order_rules=_unsupported_deferred_order_rules(),
    )
    assert zero_outcome.failure is not None
    assert (
        zero_outcome.failure.code
        is BinanceUsdmTradifiProfileCompositionFailureCode.ZERO_SLIPPAGE_UNSUPPORTED
    )

    narrow = replace(
        slippage,
        applicability_envelope=SlippageApplicabilityEnvelope.create(
            envelope_key="koruusdt-too-narrow-v1",
            envelope_version=1,
            instrument_id=slippage.applicability_envelope.instrument_id,
            valid_from=START,
            valid_to_exclusive=UtcInstant(END.epoch_nanoseconds - 1),
            maximum_quantity=slippage.applicability_envelope.maximum_quantity,
            allowed_market_state_keys=("normal",),
        ),
    )
    outside = _compose(
        slippage_model=narrow,
        order_rules=_unsupported_deferred_order_rules(),
    )
    assert outside.failure is not None
    assert outside.failure.code is (
        BinanceUsdmTradifiProfileCompositionFailureCode.SLIPPAGE_APPLICABILITY_MISMATCH
    )

    deferred = _compose(order_rules=_unsupported_deferred_order_rules())
    assert deferred.failure is not None
    assert deferred.failure.code is (
        BinanceUsdmTradifiProfileCompositionFailureCode.DEFERRED_ORDER_RULE_UNSUPPORTED
    )
