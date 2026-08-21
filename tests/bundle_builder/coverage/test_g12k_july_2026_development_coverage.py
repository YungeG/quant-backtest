from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest
from crypto_quant_backtest.universe import UniverseKind, UniverseMembershipRevision
from crypto_quant_bundle_builder.bundle_validation import validate_market_bundle_v1
from crypto_quant_bundle_builder.coverage_declarations import RevisionTerminalLineage
from crypto_quant_bundle_builder.g12b_universe_corporate_action_payloads import (
    G12BCorporateActionLifecycleRevisionPayloadV1,
    G12BCorporateActionStatusV1,
    G12BListingMembershipRevisionPayloadV1,
    _reconstruct_corporate_action_lifecycle_revision_payload_v1,
    _reconstruct_listing_membership_revision_payload_v1,
)
from crypto_quant_bundle_builder.g12k_july_2026_development_coverage import (
    CorporateActionCoverageReport,
    G12KCoverageScopeV1,
    G12KJuly2026DevelopmentCoverageFailureCode,
    G12KRevisionClosureDeclarationV1,
    UniverseCoverageReport,
    analyze_g12k_july_2026_development_coverage_v1,
)
from crypto_quant_domain import (
    CurrencyId,
    InstrumentCatalog,
    InstrumentDefinition,
    InstrumentId,
    InstrumentType,
    Money,
    Scale,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    TradingDate,
    UtcInstant,
    VenueId,
    canonical_bytes,
)
from crypto_quant_market_data import (
    MarketBundleCapability,
    MarketBundleManifest,
    MarketEvent,
)
from crypto_quant_trading.profiles.cn_a_share.corporate_actions import (
    CnAShareCorporateActionAnnouncementCandidate,
    CnAShareCorporateActionAnnouncementStatus,
    CnAShareCorporateActionSourceRef,
)

FIXTURE = (
    Path(__file__).parents[2]
    / "fixtures/bundle_builder/g12k-july-2026-development-coverage-v1.json"
)
START = UtcInstant(1_783_267_200_000_000_000)
END = UtcInstant(1_785_427_200_000_000_000)
CNY = CurrencyId("CNY")
INSTRUMENT_ID = InstrumentId(VenueId("xshe"), "xshe.corporate-action.stable")
DEFINITION = InstrumentDefinition(INSTRUMENT_ID, InstrumentType.EQUITY, None, CNY, CNY)
CATALOG = InstrumentCatalog((CNY,), (DEFINITION,), ())
CATALOG_HASH = "sha256:954cac9b51cdfae55bcf0f5dd6fbcbda5c7c353baca43fd00fcddeb6c34104bb"
SOURCE_IDENTITY = "synthetic.g12k"
SOURCE_HASH = "sha256:" + "1" * 64
DECLARATION_SOURCE_IDENTITY = "synthetic.g12k.closure"
DECLARATION_SOURCE_HASH = "sha256:" + "2" * 64
PHASE = TimelinePhase(10, "announcement")


def _instant(offset_hours: int, sequence: int) -> SimulationInstant:
    return SimulationInstant(
        UtcInstant(START.epoch_nanoseconds + offset_hours * 3_600_000_000_000),
        PHASE,
        SourceSequence(sequence),
    )


def _event(
    *,
    event_id: str,
    stream_key: str,
    event_type: str,
    capability: MarketBundleCapability,
    payload: dict[str, object],
    available: SimulationInstant,
    revision_id: str,
    supersedes: str | None,
) -> MarketEvent:
    return MarketEvent(
        event_id=event_id,
        stream_key=stream_key,
        event_type=event_type,
        capability=capability,
        instrument_id=INSTRUMENT_ID,
        event_time=available.instant,
        available_time=available.instant,
        phase=available.phase,
        source_sequence=available.source_sequence,
        revision_id=revision_id,
        supersedes_revision_id=supersedes,
        source_key=SOURCE_IDENTITY,
        source_hash=SOURCE_HASH,
        payload=payload,
    )


def _manifest(
    events: tuple[MarketEvent, ...], catalog_hash: str = CATALOG_HASH
) -> MarketBundleManifest:
    outcome = validate_market_bundle_v1(
        bundle_key="g12k-july-2026-development-coverage-v1",
        schema_version=1,
        coverage_start=START,
        coverage_end_exclusive=END,
        instrument_catalog_hash=catalog_hash,
        events=events,
    )
    assert outcome.failure is None
    assert outcome.manifest is not None
    return outcome.manifest


def _closure(
    scope: G12KCoverageScopeV1,
    events: tuple[MarketEvent, ...],
    terminals: tuple[tuple[str, MarketEvent], ...],
) -> G12KRevisionClosureDeclarationV1:
    return G12KRevisionClosureDeclarationV1(
        scope=scope,
        context_key=(
            "equity.cn_a_share.xshe.corporate-action-development.v1|point_in_time|"
            "xshe:xshe.corporate-action.stable"
            if scope is G12KCoverageScopeV1.UNIVERSE
            else "cn-a-share-record-register-entitlement-v1|CN.XSHE|"
            "xshe:xshe.corporate-action.stable"
        ),
        target_start=START,
        target_end_exclusive=END,
        causal_visibility_limit=_instant(5, 99),
        event_hashes=tuple(sorted(event.event_hash for event in events)),
        terminals=tuple(
            RevisionTerminalLineage(key, event.event_hash)
            for key, event in sorted(terminals)
        ),
        source_key=DECLARATION_SOURCE_IDENTITY,
        source_hash=DECLARATION_SOURCE_HASH,
    )


def _case() -> tuple[
    MarketBundleManifest,
    tuple[MarketEvent, ...],
    G12KRevisionClosureDeclarationV1,
    G12KRevisionClosureDeclarationV1,
]:
    listing = G12BListingMembershipRevisionPayloadV1(
        universe_key="equity.cn_a_share.xshe.corporate-action-development.v1",
        membership_key="membership-1",
        listed_at=UtcInstant(START.epoch_nanoseconds - 86_400_000_000_000),
        delisted_at=None,
        member_from=START,
        member_until=None,
    )
    action_v1 = G12BCorporateActionLifecycleRevisionPayloadV1(
        corporate_action_id="action-1",
        status=G12BCorporateActionStatusV1.FINAL_IMPLEMENTATION,
        calendar_id="CN.XSHE",
        record_date="2026-07-15",
        ex_date="2026-07-16",
        payment_date="2026-07-20",
        listing_date=None,
        cash_per_share_units=10,
        cash_per_share_scale=2,
        cash_currency="CNY",
        bonus_rate_units=None,
        bonus_rate_scale=None,
        bonus_rate_basis=None,
        capitalization_rate_units=None,
        capitalization_rate_scale=None,
        capitalization_rate_basis=None,
    )
    action_v2 = replace(action_v1, cash_per_share_units=12)
    universe_event = _event(
        event_id="universe-1",
        stream_key="g12k.universe.listing-membership",
        event_type="listing_membership_revision",
        capability=MarketBundleCapability("universe", 1),
        payload=listing.to_canonical_dict(),
        available=_instant(1, 1),
        revision_id="membership-r1",
        supersedes=None,
    )
    action_event_v1 = _event(
        event_id="action-1-r1",
        stream_key="g12k.corporate-actions.lifecycle",
        event_type="corporate_action_lifecycle_revision",
        capability=MarketBundleCapability("corporate_actions", 1),
        payload=action_v1.to_canonical_dict(),
        available=_instant(2, 2),
        revision_id="action-r1",
        supersedes=None,
    )
    action_event_v2 = _event(
        event_id="action-1-r2",
        stream_key="g12k.corporate-actions.lifecycle",
        event_type="corporate_action_lifecycle_revision",
        capability=MarketBundleCapability("corporate_actions", 1),
        payload=action_v2.to_canonical_dict(),
        available=_instant(3, 3),
        revision_id="action-r2",
        supersedes="action-r1",
    )
    events = (universe_event, action_event_v1, action_event_v2)
    return (
        _manifest(events),
        events,
        _closure(
            G12KCoverageScopeV1.UNIVERSE,
            (universe_event,),
            (("membership-1", universe_event),),
        ),
        _closure(
            G12KCoverageScopeV1.CORPORATE_ACTIONS,
            (action_event_v1, action_event_v2),
            (("action-1", action_event_v2),),
        ),
    )


def _analyze(
    case: tuple[
        MarketBundleManifest,
        tuple[MarketEvent, ...],
        G12KRevisionClosureDeclarationV1,
        G12KRevisionClosureDeclarationV1,
    ],
    *,
    catalog: InstrumentCatalog = CATALOG,
):
    manifest, events, universe, actions = case
    return analyze_g12k_july_2026_development_coverage_v1(
        manifest=manifest,
        instrument_catalog=catalog,
        events=events,
        universe_closure=universe,
        corporate_action_closure=actions,
    )


def test_canonical_corrected_case_is_repeatable_atomic_and_golden() -> None:
    case = _case()
    first = _analyze(case)
    second = _analyze(case)
    assert first.failure is None
    assert type(first.universe_report) is UniverseCoverageReport
    assert type(first.corporate_action_report) is CorporateActionCoverageReport
    assert first.universe_report.member_instrument_ids == (INSTRUMENT_ID,)
    assert first.corporate_action_report.active_corporate_action_ids == ("action-1",)
    assert first.corporate_action_report.cancelled_corporate_action_ids == ()
    assert first.universe_report.relevant_event_hashes == (
        events_hash := case[1][0].event_hash,
    )
    assert first.universe_report.terminal_event_hashes == (events_hash,)
    assert first.corporate_action_report.relevant_event_hashes == tuple(
        sorted(event.event_hash for event in case[1][1:])
    )
    assert first.corporate_action_report.terminal_event_hashes == (
        case[1][2].event_hash,
    )
    assert first == second
    assert canonical_bytes(first) == canonical_bytes(second)
    assert first.outcome_hash == second.outcome_hash
    assert first.to_canonical_dict() == json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert all(
        getattr(first.universe_report, name) is False
        for name in (
            "provider_authority_qualified",
            "provider_revision_completeness_qualified",
            "historical_authority_qualified",
            "survivorship_bias_safe",
            "decision_grade_eligible",
            "profile_qualified",
            "live_eligible",
            "deployment_authorized",
        )
    )


def test_present_empty_declarations_succeed() -> None:
    empty_universe = _closure(G12KCoverageScopeV1.UNIVERSE, (), ())
    empty_actions = _closure(G12KCoverageScopeV1.CORPORATE_ACTIONS, (), ())
    manifest = _manifest(())
    outcome = _analyze((manifest, (), empty_universe, empty_actions))
    assert outcome.failure is None
    assert outcome.universe_report is not None
    assert outcome.corporate_action_report is not None
    assert outcome.universe_report.member_instrument_ids == ()
    assert outcome.corporate_action_report.active_corporate_action_ids == ()
    assert outcome.corporate_action_report.cancelled_corporate_action_ids == ()


def test_each_failure_branch_has_direct_evidence() -> None:
    case = _case()
    manifest, events, universe, actions = case

    invalid = analyze_g12k_july_2026_development_coverage_v1(
        manifest=manifest,
        instrument_catalog=CATALOG,
        events=list(events),  # type: ignore[arg-type]
        universe_closure=universe,
        corporate_action_closure=actions,
    )
    assert invalid.failure is not None
    assert (
        invalid.failure.code is G12KJuly2026DevelopmentCoverageFailureCode.INVALID_INPUT
    )

    bad_order = (events[0], events[2], events[1])
    g12c = _analyze((manifest, bad_order, universe, actions))
    assert g12c.failure is not None
    assert (
        g12c.failure.code
        is G12KJuly2026DevelopmentCoverageFailureCode.G12C_VALIDATION_FAILED
    )

    spoofed_manifest = object.__new__(MarketBundleManifest)
    for name in MarketBundleManifest.__dataclass_fields__:
        object.__setattr__(spoofed_manifest, name, getattr(manifest, name))
    object.__setattr__(spoofed_manifest, "content_hash", "sha256:" + "f" * 64)
    mismatch = _analyze((spoofed_manifest, events, universe, actions))
    assert mismatch.failure is not None
    assert (
        mismatch.failure.code
        is G12KJuly2026DevelopmentCoverageFailureCode.BUNDLE_MANIFEST_MISMATCH
    )

    tushare_manifest = _manifest(events, "sha256:" + "9" * 64)
    catalog = _analyze((tushare_manifest, events, universe, actions))
    assert catalog.failure is not None
    assert (
        catalog.failure.code
        is G12KJuly2026DevelopmentCoverageFailureCode.CATALOG_EVENT_BINDING_MISMATCH
    )

    malformed = replace(events[0], event_type="near_listing_membership_revision")
    malformed_events = (malformed, *events[1:])
    malformed_case = (
        _manifest(malformed_events),
        malformed_events,
        _closure(
            G12KCoverageScopeV1.UNIVERSE, (malformed,), (("membership-1", malformed),)
        ),
        actions,
    )
    event_failure = _analyze(malformed_case)
    assert event_failure.failure is not None
    assert (
        event_failure.failure.code
        is G12KJuly2026DevelopmentCoverageFailureCode.EVENT_CONTRACT_MISMATCH
    )

    omitted = replace(universe, event_hashes=("sha256:" + "0" * 64,))
    closure_failure = _analyze((manifest, events, omitted, actions))
    assert closure_failure.failure is not None
    assert (
        closure_failure.failure.code
        is G12KJuly2026DevelopmentCoverageFailureCode.CLOSURE_MISMATCH
    )

    payload = G12BListingMembershipRevisionPayloadV1(
        universe_key="equity.cn_a_share.xshe.corporate-action-development.v1",
        membership_key="membership-1",
        listed_at=START,
        delisted_at=None,
        member_from=UtcInstant(START.epoch_nanoseconds - 1),
        member_until=None,
    )
    semantic_event = replace(events[0], payload=payload.to_canonical_dict())
    semantic_events = (semantic_event, *events[1:])
    semantic_case = (
        _manifest(semantic_events),
        semantic_events,
        _closure(
            G12KCoverageScopeV1.UNIVERSE,
            (semantic_event,),
            (("membership-1", semantic_event),),
        ),
        actions,
    )
    semantics = _analyze(semantic_case)
    assert semantics.failure is not None
    assert (
        semantics.failure.code
        is G12KJuly2026DevelopmentCoverageFailureCode.COVERAGE_SEMANTICS_MISMATCH
    )


def test_constructor_bypass_catalog_attribute_error_is_contained() -> None:
    case = _case()
    spoofed = object.__new__(InstrumentCatalog)
    object.__setattr__(spoofed, "currencies", (CNY,))
    object.__setattr__(spoofed, "symbol_timelines", ())

    outcome = _analyze(case, catalog=spoofed)

    assert outcome.failure is not None
    assert (
        outcome.failure.code
        is G12KJuly2026DevelopmentCoverageFailureCode.CATALOG_EVENT_BINDING_MISMATCH
    )
    assert outcome.failure.scope is None


def test_invalid_parent_membership_is_not_repaired_by_valid_terminal() -> None:
    _, events, _, actions = _case()
    terminal_payload = _reconstruct_listing_membership_revision_payload_v1(
        events[0].payload
    )
    invalid_parent_payload = replace(
        terminal_payload,
        member_from=UtcInstant(terminal_payload.listed_at.epoch_nanoseconds - 1),
    )
    parent = replace(events[0], payload=invalid_parent_payload.to_canonical_dict())
    terminal = _event(
        event_id="universe-1-r2",
        stream_key="g12k.universe.listing-membership",
        event_type="listing_membership_revision",
        capability=MarketBundleCapability("universe", 1),
        payload=terminal_payload.to_canonical_dict(),
        available=_instant(4, 4),
        revision_id="membership-r2",
        supersedes="membership-r1",
    )
    revised_events = (parent, *events[1:], terminal)
    universe = _closure(
        G12KCoverageScopeV1.UNIVERSE,
        (parent, terminal),
        (("membership-1", terminal),),
    )

    outcome = _analyze((_manifest(revised_events), revised_events, universe, actions))

    assert outcome.failure is not None
    assert (
        outcome.failure.code
        is G12KJuly2026DevelopmentCoverageFailureCode.COVERAGE_SEMANTICS_MISMATCH
    )
    assert outcome.failure.scope is G12KCoverageScopeV1.UNIVERSE
    assert outcome.failure.logical_lineage_key == "membership-1"


@pytest.mark.parametrize(
    "overrides",
    (
        {"cash_per_share_scale": None},
        {"cash_per_share_units": 0},
        {"cash_per_share_scale": 3},
        {"cash_currency": "USD"},
        {
            "bonus_rate_units": 1,
            "bonus_rate_scale": 2,
            "bonus_rate_basis": "per_ten_shares",
        },
        {
            "capitalization_rate_units": -1,
            "capitalization_rate_scale": 2,
            "capitalization_rate_basis": "shares_per_share",
        },
    ),
)
def test_malformed_non_terminal_plan_only_distribution_is_rejected(
    overrides: dict[str, object],
) -> None:
    _, events, universe, _ = _case()
    root_payload = _reconstruct_corporate_action_lifecycle_revision_payload_v1(
        events[1].payload
    )
    malformed_plan = replace(
        root_payload,
        status=G12BCorporateActionStatusV1.PLAN_ONLY,
        **overrides,
    )
    root = replace(events[1], payload=malformed_plan.to_canonical_dict())
    revised_events = (events[0], root, events[2])
    actions = _closure(
        G12KCoverageScopeV1.CORPORATE_ACTIONS,
        (root, events[2]),
        (("action-1", events[2]),),
    )

    outcome = _analyze((_manifest(revised_events), revised_events, universe, actions))

    assert outcome.failure is not None
    assert (
        outcome.failure.code
        is G12KJuly2026DevelopmentCoverageFailureCode.COVERAGE_SEMANTICS_MISMATCH
    )
    assert outcome.failure.logical_lineage_key == "action-1"


def test_unknown_stream_precedes_expected_stream_classification() -> None:
    _, base_events, universe, actions = _case()
    unknown = replace(base_events[1], stream_key="g12k.unknown")
    unknown_events = (base_events[0], unknown, base_events[2])

    direct = _analyze((_manifest(unknown_events), unknown_events, universe, actions))

    assert direct.failure is not None
    assert (
        direct.failure.code
        is G12KJuly2026DevelopmentCoverageFailureCode.EVENT_CONTRACT_MISMATCH
    )
    assert direct.failure.scope is None
    assert direct.failure.logical_lineage_key is None

    malformed = replace(base_events[0], event_type="wrong_membership_revision")
    combined_events = (malformed, unknown, base_events[2])
    combined = _analyze(
        (_manifest(combined_events), combined_events, universe, actions)
    )

    assert combined.failure == direct.failure


def test_event_contract_failure_orders_scope_lineage_then_event_hash() -> None:
    _, base_events, _, actions = _case()
    base_payload = _reconstruct_listing_membership_revision_payload_v1(
        base_events[0].payload
    )
    z_event = _event(
        event_id="invalid-z",
        stream_key="g12k.universe.listing-membership",
        event_type="wrong_membership_revision",
        capability=MarketBundleCapability("universe", 1),
        payload=replace(base_payload, membership_key="z-lineage").to_canonical_dict(),
        available=_instant(1, 10),
        revision_id="z-r1",
        supersedes=None,
    )
    a_event = _event(
        event_id="invalid-a",
        stream_key="g12k.universe.listing-membership",
        event_type="wrong_membership_revision",
        capability=MarketBundleCapability("universe", 1),
        payload=replace(base_payload, membership_key="a-lineage").to_canonical_dict(),
        available=_instant(2, 11),
        revision_id="a-r1",
        supersedes=None,
    )
    unrecoverable = _event(
        event_id="invalid-payload",
        stream_key="g12k.universe.listing-membership",
        event_type="wrong_membership_revision",
        capability=MarketBundleCapability("universe", 1),
        payload={"unexpected": "payload"},
        available=_instant(3, 12),
        revision_id="unknown-r1",
        supersedes=None,
    )
    events = (z_event, a_event, unrecoverable, *base_events[1:])
    universe = _closure(
        G12KCoverageScopeV1.UNIVERSE,
        (z_event, a_event, unrecoverable),
        (("a-lineage", a_event), ("unknown", unrecoverable), ("z-lineage", z_event)),
    )

    outcome = _analyze((_manifest(events), events, universe, actions))

    assert outcome.failure is not None
    assert (
        outcome.failure.code
        is G12KJuly2026DevelopmentCoverageFailureCode.EVENT_CONTRACT_MISMATCH
    )
    assert outcome.failure.scope is G12KCoverageScopeV1.UNIVERSE
    assert outcome.failure.logical_lineage_key == "a-lineage"


def test_revision_graph_failures_are_lineage_attributed() -> None:
    _, base_events, universe, _ = _case()
    universe_event, root, child = base_events
    action_payload = _reconstruct_corporate_action_lifecycle_revision_payload_v1(
        child.payload
    )

    missing_child = replace(child, supersedes_revision_id="missing-r0")
    missing_events = (universe_event, root, missing_child)

    fork = _event(
        event_id="action-1-r3",
        stream_key="g12k.corporate-actions.lifecycle",
        event_type="corporate_action_lifecycle_revision",
        capability=MarketBundleCapability("corporate_actions", 1),
        payload=action_payload.to_canonical_dict(),
        available=_instant(4, 4),
        revision_id="action-r3",
        supersedes="action-r1",
    )
    fork_events = (*base_events, fork)

    cycle_root = replace(root, supersedes_revision_id="action-r2")
    cycle_events = (universe_event, cycle_root, child)

    early_child = replace(
        child,
        event_id="early-child",
        event_time=_instant(2, 20).instant,
        available_time=_instant(2, 20).instant,
        phase=_instant(2, 20).phase,
        source_sequence=_instant(2, 20).source_sequence,
    )
    late_parent = replace(
        root,
        event_id="late-parent",
        event_time=_instant(3, 21).instant,
        available_time=_instant(3, 21).instant,
        phase=_instant(3, 21).phase,
        source_sequence=_instant(3, 21).source_sequence,
    )
    regression_events = (universe_event, early_child, late_parent)

    cases = (
        (missing_events, missing_child),
        (fork_events, fork),
        (cycle_events, child),
        (regression_events, early_child),
    )
    for events, terminal in cases:
        action_events = tuple(event for event in events if event is not universe_event)
        actions = _closure(
            G12KCoverageScopeV1.CORPORATE_ACTIONS,
            action_events,
            (("action-1", terminal),),
        )
        outcome = _analyze((_manifest(events), events, universe, actions))
        assert outcome.failure is not None
        assert (
            outcome.failure.code
            is G12KJuly2026DevelopmentCoverageFailureCode.CLOSURE_MISMATCH
        )
        assert outcome.failure.scope is G12KCoverageScopeV1.CORPORATE_ACTIONS
        assert outcome.failure.logical_lineage_key == "action-1"


def test_terminal_cancellation_uses_nearest_ancestor_record_date() -> None:
    _, events, universe, _ = _case()
    root = events[1]
    cancelled_payload = G12BCorporateActionLifecycleRevisionPayloadV1(
        corporate_action_id="action-1",
        status=G12BCorporateActionStatusV1.CANCELLED,
        calendar_id="CN.XSHE",
        record_date=None,
        ex_date=None,
        payment_date=None,
        listing_date=None,
        cash_per_share_units=None,
        cash_per_share_scale=None,
        cash_currency=None,
        bonus_rate_units=None,
        bonus_rate_scale=None,
        bonus_rate_basis=None,
        capitalization_rate_units=None,
        capitalization_rate_scale=None,
        capitalization_rate_basis=None,
    )
    cancelled = replace(events[2], payload=cancelled_payload.to_canonical_dict())
    revised_events = (events[0], root, cancelled)
    revised_actions = _closure(
        G12KCoverageScopeV1.CORPORATE_ACTIONS,
        (root, cancelled),
        (("action-1", cancelled),),
    )
    outcome = _analyze(
        (_manifest(revised_events), revised_events, universe, revised_actions)
    )
    assert outcome.failure is None
    assert outcome.corporate_action_report is not None
    assert outcome.corporate_action_report.active_corporate_action_ids == ()
    assert outcome.corporate_action_report.cancelled_corporate_action_ids == (
        "action-1",
    )
    assert outcome.corporate_action_report.terminal_event_hashes == (
        cancelled.event_hash,
    )
    assert set(outcome.corporate_action_report.relevant_event_hashes) == {
        root.event_hash,
        cancelled.event_hash,
    }


def test_meaningful_failure_precedence_is_frozen() -> None:
    manifest, events, universe, actions = _case()
    malformed = replace(events[0], event_type="near_listing_membership_revision")
    malformed_events = (malformed, *events[1:])
    malformed_manifest = _manifest(malformed_events)
    malformed_universe = _closure(
        G12KCoverageScopeV1.UNIVERSE,
        (malformed,),
        (("membership-1", malformed),),
    )

    g12c_first = _analyze(
        (manifest, (events[0], events[2], events[1]), universe, actions)
    )
    assert g12c_first.failure is not None
    assert (
        g12c_first.failure.code
        is G12KJuly2026DevelopmentCoverageFailureCode.G12C_VALIDATION_FAILED
    )

    catalog_manifest = _manifest(malformed_events, "sha256:" + "9" * 64)
    catalog_first = _analyze(
        (catalog_manifest, malformed_events, malformed_universe, actions)
    )
    assert catalog_first.failure is not None
    assert (
        catalog_first.failure.code
        is G12KJuly2026DevelopmentCoverageFailureCode.CATALOG_EVENT_BINDING_MISMATCH
    )

    wrong_closure = replace(malformed_universe, event_hashes=("sha256:" + "0" * 64,))
    event_first = _analyze(
        (malformed_manifest, malformed_events, wrong_closure, actions)
    )
    assert event_first.failure is not None
    assert (
        event_first.failure.code
        is G12KJuly2026DevelopmentCoverageFailureCode.EVENT_CONTRACT_MISMATCH
    )

    semantic_payload = G12BListingMembershipRevisionPayloadV1(
        universe_key="equity.cn_a_share.xshe.corporate-action-development.v1",
        membership_key="membership-1",
        listed_at=START,
        delisted_at=None,
        member_from=UtcInstant(START.epoch_nanoseconds - 1),
        member_until=None,
    )
    semantic_event = replace(events[0], payload=semantic_payload.to_canonical_dict())
    semantic_events = (semantic_event, *events[1:])
    omitted = replace(universe, event_hashes=("sha256:" + "0" * 64,))
    closure_first = _analyze(
        (_manifest(semantic_events), semantic_events, omitted, actions)
    )
    assert closure_first.failure is not None
    assert (
        closure_first.failure.code
        is G12KJuly2026DevelopmentCoverageFailureCode.CLOSURE_MISMATCH
    )


def test_full_simulation_instant_order_accepts_later_phase_at_equal_utc() -> None:
    _, events, universe, _ = _case()
    root = events[1]
    later = replace(
        events[2],
        available_time=root.available_time,
        event_time=root.event_time,
        phase=TimelinePhase(root.phase.rank + 1, "correction"),
        source_sequence=SourceSequence(0),
    )
    revised_events = (events[0], root, later)
    revised_actions = _closure(
        G12KCoverageScopeV1.CORPORATE_ACTIONS,
        (root, later),
        (("action-1", later),),
    )
    outcome = _analyze(
        (_manifest(revised_events), revised_events, universe, revised_actions)
    )
    assert outcome.failure is None


def test_payload_hash_spoof_and_qualification_mutation_are_rejected() -> None:
    manifest, events, universe, actions = _case()
    spoof = dict(events[0].payload)
    spoof["payload_hash"] = "sha256:" + "0" * 64
    spoofed_event = replace(events[0], payload=spoof)
    spoofed_events = (spoofed_event, *events[1:])
    outcome = _analyze(
        (
            _manifest(spoofed_events),
            spoofed_events,
            _closure(
                G12KCoverageScopeV1.UNIVERSE,
                (spoofed_event,),
                (("membership-1", spoofed_event),),
            ),
            actions,
        )
    )
    assert outcome.failure is not None
    assert (
        outcome.failure.code
        is G12KJuly2026DevelopmentCoverageFailureCode.EVENT_CONTRACT_MISMATCH
    )

    success = _analyze((manifest, events, universe, actions))
    assert success.universe_report is not None
    object.__setattr__(success.universe_report, "live_eligible", True)
    with pytest.raises(ValueError, match="development-only"):
        success.universe_report.to_canonical_dict()


def test_test_only_g11c_and_g08f_candidate_parity() -> None:
    _, events, _, action_closure = _case()
    listing_event, _, action_event = events
    listing_payload = _reconstruct_listing_membership_revision_payload_v1(
        listing_event.payload
    )
    assert listing_event.instrument_id is not None
    revision = UniverseMembershipRevision(
        universe_key=listing_payload.universe_key,
        membership_key=listing_payload.membership_key,
        kind=UniverseKind.POINT_IN_TIME,
        instrument_id=listing_event.instrument_id,
        listed_at=listing_payload.listed_at,
        delisted_at=listing_payload.delisted_at,
        member_from=listing_payload.member_from,
        member_until=listing_payload.member_until,
        available_at=listing_event.timeline_instant,
        revision_id=listing_event.revision_id,
        supersedes_revision_id=listing_event.supersedes_revision_id,
        source_hash=listing_event.source_hash,
    )
    assert (
        revision.universe_key,
        revision.membership_key,
        revision.kind,
        revision.instrument_id,
        revision.listed_at,
        revision.delisted_at,
        revision.member_from,
        revision.member_until,
        revision.available_at,
        revision.revision_id,
        revision.supersedes_revision_id,
        revision.source_hash,
    ) == (
        listing_payload.universe_key,
        listing_payload.membership_key,
        UniverseKind.POINT_IN_TIME,
        listing_event.instrument_id,
        listing_payload.listed_at,
        listing_payload.delisted_at,
        listing_payload.member_from,
        listing_payload.member_until,
        listing_event.timeline_instant,
        listing_event.revision_id,
        listing_event.supersedes_revision_id,
        listing_event.source_hash,
    )

    action_payload = _reconstruct_corporate_action_lifecycle_revision_payload_v1(
        action_event.payload
    )
    source_refs = (
        CnAShareCorporateActionSourceRef(
            action_event.source_key, action_event.source_hash
        ),
    )
    assert action_payload.cash_per_share_units is not None
    assert action_payload.cash_per_share_scale is not None
    assert action_payload.cash_currency is not None
    cash = Money(
        action_payload.cash_per_share_units,
        Scale(action_payload.cash_per_share_scale),
        action_payload.cash_currency,
    )
    candidate = CnAShareCorporateActionAnnouncementCandidate(
        corporate_action_id=action_payload.corporate_action_id,
        instrument=DEFINITION,
        status=CnAShareCorporateActionAnnouncementStatus(action_payload.status.value),
        event_id=action_event.event_id,
        event_hash=action_event.event_hash,
        event_time=action_event.event_time,
        announcement_available_at=action_event.timeline_instant,
        revision_id=action_event.revision_id,
        supersedes_revision_id=action_event.supersedes_revision_id,
        record_date=TradingDate(
            action_payload.calendar_id,
            date.fromisoformat(action_payload.record_date or ""),
        ),
        ex_date=TradingDate(
            action_payload.calendar_id,
            date.fromisoformat(action_payload.ex_date or ""),
        ),
        payment_date=TradingDate(
            action_payload.calendar_id,
            date.fromisoformat(action_payload.payment_date or ""),
        ),
        listing_date=None,
        cash_per_share=cash,
        bonus_rate=None,
        capitalization_rate=None,
        source_refs=source_refs,
    )
    assert action_closure.context_key.split("|", 1)[0] == (
        "cn-a-share-record-register-entitlement-v1"
    )
    assert (
        candidate.corporate_action_id,
        candidate.instrument,
        candidate.status,
        candidate.event_id,
        candidate.event_hash,
        candidate.event_time,
        candidate.announcement_available_at,
        candidate.revision_id,
        candidate.supersedes_revision_id,
        candidate.record_date,
        candidate.ex_date,
        candidate.payment_date,
        candidate.listing_date,
        candidate.cash_per_share,
        candidate.bonus_rate,
        candidate.capitalization_rate,
        candidate.source_refs,
    ) == (
        action_payload.corporate_action_id,
        DEFINITION,
        CnAShareCorporateActionAnnouncementStatus(action_payload.status.value),
        action_event.event_id,
        action_event.event_hash,
        action_event.event_time,
        action_event.timeline_instant,
        action_event.revision_id,
        action_event.supersedes_revision_id,
        TradingDate(
            action_payload.calendar_id,
            date.fromisoformat(action_payload.record_date or ""),
        ),
        TradingDate(
            action_payload.calendar_id,
            date.fromisoformat(action_payload.ex_date or ""),
        ),
        TradingDate(
            action_payload.calendar_id,
            date.fromisoformat(action_payload.payment_date or ""),
        ),
        None,
        cash,
        None,
        None,
        source_refs,
    )
