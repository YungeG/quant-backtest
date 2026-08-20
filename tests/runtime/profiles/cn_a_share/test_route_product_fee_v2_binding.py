from __future__ import annotations

import json
from dataclasses import fields, replace

import pytest
from crypto_quant_backtest import (
    BacktestRequest,
    BuildArtifactManifest,
    BuildArtifactRef,
    BuildArtifactRole,
    ProfileResolver,
    RequestedResultGrade,
    StrategyFamily,
)
from crypto_quant_backtest.cn_a_share_fee_v2_binding import (
    CnAShareFeePreparedExecutionV2,
    CnAShareFeeRuntimeExecutionV2,
    bind_cn_a_share_fee_build_v2,
    bind_cn_a_share_fee_execution_v2,
    bind_cn_a_share_fee_profile_v2,
    bind_cn_a_share_fee_semantic_spec_v2,
    prepare_cn_a_share_fee_execution_v2,
)
from crypto_quant_backtest.cn_a_share_profile import (
    CnAShareProfileComposer,
    CnAShareResolvedProfile,
)
from crypto_quant_domain import (
    Money,
    OrderSide,
    Price,
    Quantity,
    SourceSequence,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_market_data import (
    MarketBundleCapability,
    MarketBundleManifest,
    MarketBundleRef,
)
from crypto_quant_trading import ProfileComponentRef
from crypto_quant_trading.profiles.cn_a_share import (
    CnAShareCashFeeRuleQueryV2,
    CnAShareDomesticOrdinaryFeeProjectionV2,
    CnAShareExecutionAccessRoute,
    CnAShareFeeExecutionAuthorityV2,
    CnAShareFeeExecutionScopeV2,
    CnAShareFeeExecutionSelectionV2,
    CnAShareFeeProductClass,
    CnAShareFeeTradeMechanism,
    create_cn_a_share_fee_execution_authority_v2,
    project_cn_a_share_domestic_ordinary_fee_rules_v2,
)
from crypto_quant_trading.profiles.cn_a_share import commission_tax_v2 as kernel_v2

from tests.kernel.profiles.cn_a_share._commission_tax_fixtures import (
    fill as make_fill,
)
from tests.kernel.profiles.cn_a_share._commission_tax_fixtures import (
    local_instant,
    source_order,
)
from tests.runtime.engine._fixtures import SyntheticExecutionCaseBuilder
from tests.runtime.resolution._fixtures import build_manifest
from tests.support.cn_a_share import build_cn_a_share_resolved_request


def _forge(value, /, **changes):
    result = object.__new__(type(value))
    for field in fields(value):
        object.__setattr__(
            result, field.name, changes.get(field.name, getattr(value, field.name))
        )
    return result


def _profile() -> CnAShareResolvedProfile:
    outcome = CnAShareProfileComposer().compose(build_cn_a_share_resolved_request())
    assert outcome.result is not None
    return outcome.result


def _projection_and_authority(
    profile: CnAShareResolvedProfile, *, selection_key: str = "fixture"
) -> tuple[CnAShareDomesticOrdinaryFeeProjectionV2, CnAShareFeeExecutionAuthorityV2]:
    request = profile.request
    instrument_scope = request.instrument_scope
    account_scope = request.account_scope
    assert instrument_scope is not None and account_scope is not None
    venue = account_scope.venue_id
    source_market = type(request.market_fee_rule_book)(
        request.market_fee_rule_book.rule_book_key,
        request.market_fee_rule_book.rule_book_version,
        tuple(
            band
            for band in request.market_fee_rule_book.bands
            if band.venue_id == venue
        ),
    )
    source_stamp = type(request.stamp_duty_rule_book)(
        request.stamp_duty_rule_book.rule_book_key,
        request.stamp_duty_rule_book.rule_book_version,
        tuple(
            band
            for band in request.stamp_duty_rule_book.bands
            if band.venue_id == venue
        ),
    )
    projection = project_cn_a_share_domestic_ordinary_fee_rules_v2(
        source_market, source_stamp
    )
    assert isinstance(projection, CnAShareDomesticOrdinaryFeeProjectionV2)
    scope = CnAShareFeeExecutionScopeV2(
        account_scope.account_id,
        venue,
        instrument_scope.instrument,
        instrument_scope.instrument.instrument_id,
        instrument_scope.instrument.instrument_type,
        instrument_scope.instrument.quote_currency,
        instrument_scope.instrument.settlement_currency,
        CnAShareFeeTradeMechanism.AUCTION,
        projection.market_fee_rule_book.bands[0].effective_from,
        projection.market_fee_rule_book.bands[-1].effective_to_exclusive,
        (OrderSide.BUY, OrderSide.SELL),
        CnAShareExecutionAccessRoute.DOMESTIC,
        CnAShareFeeProductClass.ORDINARY_A_SHARE,
    )
    selection = CnAShareFeeExecutionSelectionV2(
        selection_key,
        1,
        scope.access_route,
        scope.fee_product_class,
        projection.market_fee_rule_book,
        projection.market_fee_rule_book_hash,
        projection.stamp_duty_rule_book,
        projection.stamp_duty_rule_book_hash,
        kernel_v2._market_component(projection.market_fee_rule_book),
        kernel_v2._tax_component(projection.stamp_duty_rule_book),
    )
    authority = create_cn_a_share_fee_execution_authority_v2(scope, selection)
    assert isinstance(authority, CnAShareFeeExecutionAuthorityV2)
    return projection, authority


def _build_manifest(profile: CnAShareResolvedProfile):
    base = build_manifest()
    registrations = (
        profile.market_registration,
        profile.simulation_registration,
        profile.execution_account_registration,
    )
    artifacts = tuple(
        artifact
        for artifact in base.artifacts
        if artifact.role is not BuildArtifactRole.PROFILE_COMPONENT
    ) + tuple(
        BuildArtifactRef(
            BuildArtifactRole.PROFILE_COMPONENT,
            registration.profile_key,
            str(registration.profile_version),
            base.artifacts[0].install_mode,
            base.artifacts[0].source_tree_state,
            registration.profile_digest,
            None,
        )
        for registration in registrations
    )
    return replace(base, build_key="cn-a-share.backtest.build.v2", artifacts=artifacts)


def _order(profile: CnAShareResolvedProfile):
    instrument_scope = profile.request.instrument_scope
    assert instrument_scope is not None
    instrument = instrument_scope.instrument
    original = source_order(
        quantity_units=100,
        side=OrderSide.BUY,
        effective_at=local_instant(26),
    )
    return replace(
        original,
        account_id=profile.execution_account.account_id,
        intent=replace(
            original.intent,
            instrument_id=instrument.instrument_id,
            quantity=Quantity(
                original.intent.quantity.units,
                original.intent.quantity.scale,
                str(instrument.instrument_id),
            ),
        ),
    )


def _bundle(profile: CnAShareResolvedProfile) -> MarketBundleManifest:
    capabilities = {
        *profile.market_registration.required_bundle_capabilities,
        *profile.simulation_registration.required_bundle_capabilities,
        MarketBundleCapability("precomputed_target_stream", 1),
    }
    request = profile.request
    instrument_scope = request.instrument_scope
    assert instrument_scope is not None
    return MarketBundleManifest.build(
        bundle_key="cn-a-share.fee-v2.runtime-binding",
        schema_version=1,
        coverage_start=request.timeline_window.data_start,
        coverage_end_exclusive=request.timeline_window.end_exclusive,
        instrument_catalog_hash=canonical_sha256(instrument_scope.instrument),
        capabilities=capabilities,
        streams=(),
    )


def _request(
    profile: CnAShareResolvedProfile,
    manifest: BuildArtifactManifest,
    bundle: MarketBundleManifest,
    *,
    semantic_hash: str,
    target_stream_digest: str,
) -> BacktestRequest:
    instrument_scope = profile.request.instrument_scope
    assert instrument_scope is not None
    return BacktestRequest(
        1,
        "cn-a-share-fee-v2-runtime-binding",
        profile.request.timeline_window,
        profile.market_registration.profile_key,
        profile.simulation_registration.profile_key,
        profile.execution_account_registration.profile_key,
        profile.execution_account.account_id,
        instrument_scope.instrument.quote_currency,
        MarketBundleRef.from_manifest(bundle),
        target_stream_digest,
        semantic_hash,
        7,
        manifest.manifest_hash,
        StrategyFamily.PRECOMPUTED_TARGET,
        profile.simulation_registration.engine_kind,
        RequestedResultGrade.DEVELOPMENT,
    )


def test_explicit_authority_binds_additive_profile_and_build_identity() -> None:
    profile = _profile()
    projection, authority = _projection_and_authority(profile)
    profile_binding = bind_cn_a_share_fee_profile_v2(
        resolved_profile=profile,
        projection=projection,
        authority=authority,
        access_route=CnAShareExecutionAccessRoute.DOMESTIC,
        fee_product_class=CnAShareFeeProductClass.ORDINARY_A_SHARE,
    )
    build_binding = bind_cn_a_share_fee_build_v2(
        resolved_profile=profile,
        profile_binding=profile_binding,
        build_artifact_manifest=_build_manifest(profile),
    )

    changed_projection, changed_authority = _projection_and_authority(
        profile, selection_key="fixture.changed"
    )
    changed_profile_binding = bind_cn_a_share_fee_profile_v2(
        resolved_profile=profile,
        projection=changed_projection,
        authority=changed_authority,
        access_route=CnAShareExecutionAccessRoute.DOMESTIC,
        fee_product_class=CnAShareFeeProductClass.ORDINARY_A_SHARE,
    )
    changed_build_binding = bind_cn_a_share_fee_build_v2(
        resolved_profile=profile,
        profile_binding=changed_profile_binding,
        build_artifact_manifest=_build_manifest(profile),
    )

    assert (
        profile_binding.profile_binding_hash
        != changed_profile_binding.profile_binding_hash
    )
    assert build_binding.build_binding_hash != changed_build_binding.build_binding_hash
    assert profile.profile_digest == _profile().profile_digest

    request_only_change = replace(
        profile.request,
        composed_at=replace(
            profile.request.composed_at,
            source_sequence=SourceSequence(1),
        ),
    )
    request_only_outcome = CnAShareProfileComposer().compose(request_only_change)
    assert request_only_outcome.result is not None
    request_only_binding = bind_cn_a_share_fee_profile_v2(
        resolved_profile=request_only_outcome.result,
        projection=projection,
        authority=authority,
        access_route=CnAShareExecutionAccessRoute.DOMESTIC,
        fee_product_class=CnAShareFeeProductClass.ORDINARY_A_SHARE,
    )
    assert request_only_outcome.result.profile_digest != profile.profile_digest
    assert (
        request_only_binding.profile_binding_hash
        == profile_binding.profile_binding_hash
    )

    body = json.loads(canonical_bytes(build_binding))
    encoded = json.dumps(body, sort_keys=True)
    for forbidden in (
        "request_hash",
        "financial_dispatcher",
        "semantic_spec",
        "financial_inputs_hash",
        "semantic_run",
    ):
        assert forbidden not in encoded


def test_binding_records_reconstruct_sources_and_reject_nested_forgery() -> None:
    profile = _profile()
    projection, authority = _projection_and_authority(profile)
    profile_binding = bind_cn_a_share_fee_profile_v2(
        resolved_profile=profile,
        projection=projection,
        authority=authority,
        access_route=CnAShareExecutionAccessRoute.DOMESTIC,
        fee_product_class=CnAShareFeeProductClass.ORDINARY_A_SHARE,
    )
    manifest = _build_manifest(profile)
    build_binding = bind_cn_a_share_fee_build_v2(
        resolved_profile=profile,
        profile_binding=profile_binding,
        build_artifact_manifest=manifest,
    )

    forged_profile = _forge(
        profile_binding,
        legacy_profile_inputs_hash="sha256:" + "0" * 64,
    )
    forged_build = _forge(
        build_binding,
        profile_binding=forged_profile,
        profile_binding_hash=forged_profile.profile_binding_hash,
    )
    with pytest.raises(ValueError, match="resolved profile inputs"):
        bind_cn_a_share_fee_execution_v2(
            profile_binding=forged_profile,
            build_binding=forged_build,
            authority=authority,
            order=_order(profile),
        )
    with pytest.raises(ValueError, match="resolved profile inputs"):
        bind_cn_a_share_fee_semantic_spec_v2(
            base_spec=SyntheticExecutionCaseBuilder().semantic_spec(),
            build_binding=forged_build,
        )

    class ComponentRefAttack(ProfileComponentRef):
        pass

    attacked_ref = object.__new__(ComponentRefAttack)
    for field in fields(profile_binding.market_fee_component_ref):
        object.__setattr__(
            attacked_ref,
            field.name,
            getattr(profile_binding.market_fee_component_ref, field.name),
        )
    with pytest.raises(TypeError, match="authority/components"):
        replace(profile_binding, market_fee_component_ref=attacked_ref)

    artifact = manifest.artifacts[0]
    forged_artifact = _forge(artifact, artifact_key="")
    forged_manifest = replace(
        manifest,
        artifacts=(forged_artifact, *manifest.artifacts[1:]),
    )
    with pytest.raises(TypeError, match="build manifest"):
        bind_cn_a_share_fee_build_v2(
            resolved_profile=profile,
            profile_binding=profile_binding,
            build_artifact_manifest=forged_manifest,
        )

    spec = SyntheticExecutionCaseBuilder().semantic_spec()
    forged_rule = _forge(spec.identity_plan[0], ordinal=True)
    forged_spec = replace(spec, identity_plan=(forged_rule, *spec.identity_plan[1:]))
    with pytest.raises(TypeError, match="base_spec"):
        bind_cn_a_share_fee_semantic_spec_v2(
            base_spec=forged_spec,
            build_binding=build_binding,
        )

    prepared = prepare_cn_a_share_fee_execution_v2(
        resolved_profile=profile,
        projection=projection,
        authority=authority,
        access_route=CnAShareExecutionAccessRoute.DOMESTIC,
        fee_product_class=CnAShareFeeProductClass.ORDINARY_A_SHARE,
        build_artifact_manifest=manifest,
        base_spec=spec,
        order=_order(profile),
    )

    class SemanticSpecAttack(type(prepared.semantic_spec)):
        @property
        def semantic_spec_hash(self) -> str:
            return prepared.semantic_spec.semantic_spec_hash

        def to_canonical_dict(self) -> dict[str, object]:
            return {"type": "forged_execution_case_semantic_spec"}

    attacked_spec = object.__new__(SemanticSpecAttack)
    for field in fields(prepared.semantic_spec):
        object.__setattr__(
            attacked_spec,
            field.name,
            getattr(prepared.semantic_spec, field.name),
        )
    with pytest.raises(TypeError, match="prepared semantic_spec"):
        replace(prepared, semantic_spec=attacked_spec)


def test_execution_binding_rejects_authority_and_order_substitution_before_query() -> (
    None
):
    profile = _profile()
    projection, authority = _projection_and_authority(profile)
    profile_binding = bind_cn_a_share_fee_profile_v2(
        resolved_profile=profile,
        projection=projection,
        authority=authority,
        access_route=CnAShareExecutionAccessRoute.DOMESTIC,
        fee_product_class=CnAShareFeeProductClass.ORDINARY_A_SHARE,
    )
    manifest = _build_manifest(profile)
    build_binding = bind_cn_a_share_fee_build_v2(
        resolved_profile=profile,
        profile_binding=profile_binding,
        build_artifact_manifest=manifest,
    )
    prepared = prepare_cn_a_share_fee_execution_v2(
        resolved_profile=profile,
        projection=projection,
        authority=authority,
        access_route=CnAShareExecutionAccessRoute.DOMESTIC,
        fee_product_class=CnAShareFeeProductClass.ORDINARY_A_SHARE,
        build_artifact_manifest=manifest,
        base_spec=SyntheticExecutionCaseBuilder().semantic_spec(),
        order=_order(profile),
    )
    assert isinstance(prepared, CnAShareFeePreparedExecutionV2)
    runtime = prepared.runtime_execution
    assert isinstance(runtime, CnAShareFeeRuntimeExecutionV2)
    assert (
        prepared.semantic_spec.financial_inputs_hash
        != prepared.base_spec.financial_inputs_hash
    )
    query = prepared.reservation_query()
    assert isinstance(query, CnAShareCashFeeRuleQueryV2)
    market_policy, tax_policy = prepared.policies()
    assert market_policy.assess_fees(query).result is not None
    assert tax_policy.assess_taxes(query).result is not None

    order = runtime.execution_binding.order
    base_fill = make_fill(order, "8", local_instant(26, 1))
    instrument = authority.scope.instrument
    price = Price(
        base_fill.price.units,
        base_fill.price.scale,
        str(instrument.instrument_id),
        str(instrument.quote_currency),
    )
    fill = replace(
        base_fill,
        venue_id=instrument.instrument_id.venue,
        instrument_id=instrument.instrument_id,
        quantity=Quantity(
            base_fill.quantity.units,
            base_fill.quantity.scale,
            str(instrument.instrument_id),
        ),
        reference_price=price,
        price=price,
        slippage_amount=Money(
            0, base_fill.slippage_amount.scale, str(instrument.quote_currency)
        ),
    )
    final_query = prepared.final_fill_query(fill)
    assert isinstance(final_query, CnAShareCashFeeRuleQueryV2)
    with pytest.raises(ValueError, match="fill_account_mismatch"):
        runtime.final_fill_query(authority, replace(fill, account_id="account:other"))

    changed_projection, changed_authority = _projection_and_authority(
        profile, selection_key="fixture.changed"
    )
    changed_profile_binding = bind_cn_a_share_fee_profile_v2(
        resolved_profile=profile,
        projection=changed_projection,
        authority=changed_authority,
        access_route=CnAShareExecutionAccessRoute.DOMESTIC,
        fee_product_class=CnAShareFeeProductClass.ORDINARY_A_SHARE,
    )
    assert (
        changed_profile_binding.profile_binding_hash
        != profile_binding.profile_binding_hash
    )
    with pytest.raises(ValueError, match="execution-selected authority"):
        runtime.reservation_query(changed_authority)
    with pytest.raises(ValueError, match="execution-selected authority"):
        runtime.policies(changed_authority)
    with pytest.raises(ValueError, match="explicit route/product"):
        bind_cn_a_share_fee_profile_v2(
            resolved_profile=profile,
            projection=projection,
            authority=authority,
            access_route=CnAShareExecutionAccessRoute.NORTHBOUND_STOCK_CONNECT,
            fee_product_class=CnAShareFeeProductClass.ORDINARY_A_SHARE,
        )
    with pytest.raises(ValueError, match="fee execution binding failed"):
        bind_cn_a_share_fee_execution_v2(
            profile_binding=profile_binding,
            build_binding=build_binding,
            authority=authority,
            order=replace(_order(profile), account_id="account:other"),
        )


def test_build_identity_flows_one_way_into_financial_hash_and_semantic_run() -> None:
    profile = _profile()
    projection, authority = _projection_and_authority(profile)
    manifest = _build_manifest(profile)
    base_spec = SyntheticExecutionCaseBuilder().semantic_spec()
    prepared = prepare_cn_a_share_fee_execution_v2(
        resolved_profile=profile,
        projection=projection,
        authority=authority,
        access_route=CnAShareExecutionAccessRoute.DOMESTIC,
        fee_product_class=CnAShareFeeProductClass.ORDINARY_A_SHARE,
        build_artifact_manifest=manifest,
        base_spec=base_spec,
        order=_order(profile),
    )
    bound_spec = prepared.semantic_spec
    assert bound_spec.financial_inputs_hash != base_spec.financial_inputs_hash
    assert bound_spec.semantic_spec_hash != base_spec.semantic_spec_hash

    changed_projection, changed_authority = _projection_and_authority(
        profile, selection_key="fixture.changed"
    )
    changed_profile_binding = bind_cn_a_share_fee_profile_v2(
        resolved_profile=profile,
        projection=changed_projection,
        authority=changed_authority,
        access_route=CnAShareExecutionAccessRoute.DOMESTIC,
        fee_product_class=CnAShareFeeProductClass.ORDINARY_A_SHARE,
    )
    changed_build_binding = bind_cn_a_share_fee_build_v2(
        resolved_profile=profile,
        profile_binding=changed_profile_binding,
        build_artifact_manifest=manifest,
    )
    changed_prepared = prepare_cn_a_share_fee_execution_v2(
        resolved_profile=profile,
        projection=changed_projection,
        authority=changed_authority,
        access_route=CnAShareExecutionAccessRoute.DOMESTIC,
        fee_product_class=CnAShareFeeProductClass.ORDINARY_A_SHARE,
        build_artifact_manifest=manifest,
        base_spec=base_spec,
        order=_order(profile),
    )
    changed_spec = changed_prepared.semantic_spec
    assert changed_prepared.build_binding == changed_build_binding
    assert changed_spec.financial_inputs_hash != bound_spec.financial_inputs_hash

    bundle = _bundle(profile)
    resolver = ProfileResolver()
    baseline = resolver.resolve(
        request=_request(
            profile,
            manifest,
            bundle,
            semantic_hash=base_spec.semantic_spec_hash,
            target_stream_digest=base_spec.target_stream_digest,
        ),
        registry=profile.profile_registry,
        market_bundle_manifest=bundle,
        build_artifact_manifest=manifest,
    )
    bound = resolver.resolve(
        request=_request(
            profile,
            manifest,
            bundle,
            semantic_hash=bound_spec.semantic_spec_hash,
            target_stream_digest=bound_spec.target_stream_digest,
        ),
        registry=profile.profile_registry,
        market_bundle_manifest=bundle,
        build_artifact_manifest=manifest,
    )
    changed = resolver.resolve(
        request=_request(
            profile,
            manifest,
            bundle,
            semantic_hash=changed_spec.semantic_spec_hash,
            target_stream_digest=changed_spec.target_stream_digest,
        ),
        registry=profile.profile_registry,
        market_bundle_manifest=bundle,
        build_artifact_manifest=manifest,
    )
    assert (
        baseline.resolved is not None
        and bound.resolved is not None
        and changed.resolved is not None
    )
    assert baseline.resolved.semantic_run_id != bound.resolved.semantic_run_id
    assert bound.resolved.semantic_run_id != changed.resolved.semantic_run_id
