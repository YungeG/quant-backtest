from __future__ import annotations

import json
from dataclasses import replace
from importlib import import_module
from pathlib import Path

from crypto_quant_backtest import BuildArtifactRef, BuildArtifactRole
from crypto_quant_backtest.cn_a_share_current_selected_fee_binding import (
    CnAShareCurrentSelectedFeePreparedExecutionV2,
)
from crypto_quant_backtest.cn_a_share_profile import (
    CnAShareProfileComposer,
    CnAShareResolvedProfile,
)
from crypto_quant_bundle_builder import (
    LocalMarketBundleRepository,
    LocalMarketBundleRepositoryConfig,
    validate_market_bundle_v1,
)
from crypto_quant_bundle_builder.cn_a_share_current_selected_rule_coverage import (
    analyze_cn_a_share_current_selected_rule_coverage_v1,
)
from crypto_quant_domain import (
    Money,
    OrderSide,
    Price,
    Quantity,
    UtcInstant,
    canonical_bytes,
)
from crypto_quant_market_data import EventCursor, LocalMarketBundleReader

from tests.kernel.profiles.cn_a_share._commission_tax_fixtures import fill as make_fill
from tests.kernel.profiles.cn_a_share._commission_tax_fixtures import (
    local_instant,
    source_order,
)
from tests.runtime.resolution._fixtures import build_manifest
from tests.support.cn_a_share import build_cn_a_share_resolved_request

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = (
    ROOT / "fixtures/market_data/rule_authorities/"
    "cn-a-share-current-selected-development-v2/declaration.json"
)
START = 1_783_267_200_000_000_000
END = 1_785_427_200_000_000_000
JULY_15 = 1_784_131_200_000_000_000


def resolved_profile() -> CnAShareResolvedProfile:
    outcome = CnAShareProfileComposer().compose(build_cn_a_share_resolved_request())
    assert outcome.result is not None
    return outcome.result


def build_artifact_manifest(profile: CnAShareResolvedProfile):
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


def published_inputs(tmp_path: Path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    declaration = json.loads(FIXTURE.read_text())
    events = import_module(
        "crypto_quant_bundle_builder.cn_a_share_current_selected_rule_bundle"
    ).project_cn_a_share_current_selected_rule_authority_events_v2(declaration)
    validation = validate_market_bundle_v1(
        bundle_key=declaration["publication"]["bundle_key"],
        schema_version=2,
        coverage_start=UtcInstant(START),
        coverage_end_exclusive=UtcInstant(END),
        instrument_catalog_hash="sha256:" + "0" * 64,
        events=events,
    )
    assert validation.failure is None and validation.manifest is not None
    publication = LocalMarketBundleRepository(
        config=LocalMarketBundleRepositoryConfig(tmp_path.resolve())
    ).publish_market_bundle_v1(
        manifest=validation.manifest,
        stream_payloads={
            event.stream_key: canonical_bytes((event,)) for event in events
        },
        retention_policy_ref=declaration["publication"]["retention_policy_ref"],
    )
    assert publication.failure is None and publication.result is not None
    reader = LocalMarketBundleReader.open(
        repository_root=tmp_path.resolve(),
        bundle_ref=publication.result.bundle_ref,
    )
    read_events = []
    for event in events:
        cursor = reader.open_cursor(event.stream_key, batch_size=1)
        assert isinstance(cursor, EventCursor)
        batch, cursor = reader.read_batch(cursor)
        assert cursor.exhausted and len(batch) == 1
        read_events.extend(batch)
    report = analyze_cn_a_share_current_selected_rule_coverage_v1(declaration)
    return declaration, reader.manifest, tuple(read_events), report.to_canonical_dict()


def july_order(profile: CnAShareResolvedProfile, side: OrderSide):
    instrument_scope = profile.request.instrument_scope
    assert instrument_scope is not None
    instrument = instrument_scope.instrument
    order = source_order(
        quantity_units=100,
        side=OrderSide.BUY,
        effective_at=local_instant(26),
    )
    order = replace(
        order,
        account_id=profile.execution_account.account_id,
        intent=replace(
            order.intent,
            instrument_id=instrument.instrument_id,
            quantity=Quantity(
                order.intent.quantity.units,
                order.intent.quantity.scale,
                str(instrument.instrument_id),
            ),
        ),
    )
    return replace(
        order,
        intent=replace(order.intent, side=side),
        created_at=replace(order.created_at, instant=UtcInstant(JULY_15)),
    )


def current_selected_fill(
    prepared: CnAShareCurrentSelectedFeePreparedExecutionV2,
    digit: str,
):
    order = prepared.execution_binding.order
    base = make_fill(order, digit, UtcInstant(JULY_15 + 3_600_000_000_000))
    instrument = prepared.binding.authority.scope.instrument
    price = Price(
        base.price.units,
        base.price.scale,
        str(instrument.instrument_id),
        str(instrument.quote_currency),
    )
    return replace(
        base,
        account_id=order.account_id,
        venue_id=instrument.instrument_id.venue,
        instrument_id=instrument.instrument_id,
        side=order.intent.side,
        quantity=Quantity(
            base.quantity.units,
            base.quantity.scale,
            str(instrument.instrument_id),
        ),
        reference_price=price,
        price=price,
        slippage_amount=Money(
            0, base.slippage_amount.scale, str(instrument.quote_currency)
        ),
    )
