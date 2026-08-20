from __future__ import annotations

import json
from dataclasses import dataclass, fields, replace
from importlib import import_module
from pathlib import Path

import pytest
from crypto_quant_backtest.cn_a_share_current_selected_fee_binding import (
    CnAShareCurrentSelectedFeePreparedExecutionV2,
    prepare_cn_a_share_current_selected_fee_execution_v2,
)
from crypto_quant_backtest.cn_a_share_profile import CnAShareProfileComposer
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
    SourceSequence,
    UtcInstant,
    canonical_bytes,
)
from crypto_quant_market_data import EventCursor, LocalMarketBundleReader, MarketEvent

from tests.kernel.profiles.cn_a_share._commission_tax_fixtures import fill as make_fill
from tests.runtime.engine._fixtures import SyntheticExecutionCaseBuilder
from tests.runtime.profiles.cn_a_share.test_route_product_fee_v2_binding import (
    _build_manifest,
    _forge,
    _order,
    _profile,
)

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = (
    ROOT / "fixtures/market_data/rule_authorities/"
    "cn-a-share-current-selected-development-v2/declaration.json"
)
START = 1_783_267_200_000_000_000
END = 1_785_427_200_000_000_000
JULY_15 = 1_784_131_200_000_000_000


def _published_inputs(tmp_path: Path):
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


def _july_order(profile, side: OrderSide):
    order = _order(profile)
    return replace(
        order,
        intent=replace(order.intent, side=side),
        created_at=replace(order.created_at, instant=UtcInstant(JULY_15)),
    )


def _fill(prepared: CnAShareCurrentSelectedFeePreparedExecutionV2, digit: str):
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


def test_current_selected_reader_fan_in_binds_exact_fees_and_replays(
    tmp_path: Path,
) -> None:
    _, manifest, events, report = _published_inputs(tmp_path)
    profile = _profile()
    build = _build_manifest(profile)
    spec = SyntheticExecutionCaseBuilder().semantic_spec()

    def prepare(side: OrderSide):
        return prepare_cn_a_share_current_selected_fee_execution_v2(
            resolved_profile=profile,
            market_bundle_manifest=manifest,
            events=events,
            coverage_report=report,
            build_artifact_manifest=build,
            base_spec=spec,
            order=_july_order(profile, side),
        )

    buy = prepare(OrderSide.BUY)
    replay = prepare(OrderSide.BUY)
    sell = prepare(OrderSide.SELL)

    assert buy == replay
    assert buy.preparation_hash == replay.preparation_hash
    assert type(buy.binding.coverage_report) is dict
    assert buy.binding.coverage_report == report
    assert buy.binding.manifest_hash == (
        "sha256:28fdfafe241c48cd4a12a8b7467ccfafdb1b2b28881e0608d938cbb3b4853989"
    )
    assert buy.binding.market_fee_rule_book.rule_book_hash == (
        "sha256:7dc7d6316ff8e7c88435bb7a070adc18fe9f18db6fd79fd19f927d88b6384c40"
    )
    assert buy.binding.stamp_duty_rule_book.rule_book_hash == (
        "sha256:f8ba2eae8d6d4eefb119a864ffc2c170b97ba0eb0537371ab4caf65bb25b01cb"
    )
    assert buy.binding.authority.authority_hash == (
        "sha256:6019179179ba23ee5d637e95ac09813bcdd228dad2851cc514238a4cf89f7d97"
    )
    assert buy.binding.binding_hash == (
        "sha256:9b022ca0ded3cde20d15e2c9b1608ae05a62c6a49119ff54ac8e093833809bea"
    )
    assert buy.semantic_spec.financial_inputs_hash == (
        "sha256:f39985966cc1c054f4ca8465ba93382291ecfd79b387c5d12943587aa719c8c5"
    )
    assert buy.semantic_spec.semantic_spec_hash == (
        "sha256:799a038b9f60171f11e737966d1a2d9838cb5c332f23377f02986cd4d4282c8b"
    )

    buy_query = buy.reservation_query()
    buy_final = buy.final_fill_query(_fill(buy, "8"))
    sell_query = sell.reservation_query()
    sell_final = sell.final_fill_query(_fill(sell, "9"))
    buy_market, buy_tax = buy.policies()
    sell_market, sell_tax = sell.policies()
    for policy, query in (
        (buy_market, buy_query),
        (buy_market, buy_final),
        (sell_market, sell_query),
        (sell_market, sell_final),
    ):
        assert policy.assess_fees(query).result is not None
    for policy, query in (
        (buy_tax, buy_query),
        (buy_tax, buy_final),
        (sell_tax, sell_query),
        (sell_tax, sell_final),
    ):
        assert policy.assess_taxes(query).result is not None

    market_resolution = buy_market.assess_fees(buy_query).result
    buy_tax_resolution = buy_tax.assess_taxes(buy_query).result
    sell_tax_resolution = sell_tax.assess_taxes(sell_query).result
    assert market_resolution is not None
    assert buy_tax_resolution is not None
    assert sell_tax_resolution is not None
    market_rules = market_resolution.reservation_charge_rules
    assert all(rule.rate is not None for rule in market_rules)
    assert [
        (
            rule.applicability.value,
            rule.rate.units,
            rule.rate.scale.places,
        )
        for rule in market_rules
        if rule.rate is not None
    ] == [
        ("applies", 341, 7),
        ("applies", 2, 5),
        ("applies", 1, 5),
        ("not_applicable", 0, 0),
    ]
    buy_tax_rule = buy_tax_resolution.reservation_charge_rule
    sell_tax_rule = sell_tax_resolution.reservation_charge_rule
    assert buy_tax_rule.rate is not None and sell_tax_rule.rate is not None
    assert (
        buy_tax_rule.applicability.value,
        buy_tax_rule.rate.units,
    ) == ("not_applicable", 0)
    assert (
        sell_tax_rule.applicability.value,
        sell_tax_rule.rate.units,
        sell_tax_rule.rate.scale.places,
    ) == ("applies", 5, 4)


def test_current_selected_substitutions_fail_before_policy_use(tmp_path: Path) -> None:
    _, manifest, events, report = _published_inputs(tmp_path)
    profile = _profile()
    build = _build_manifest(profile)
    spec = SyntheticExecutionCaseBuilder().semantic_spec()
    order = _july_order(profile, OrderSide.BUY)

    def prepare(**changes):
        values = {
            "resolved_profile": profile,
            "market_bundle_manifest": manifest,
            "events": events,
            "coverage_report": report,
            "build_artifact_manifest": build,
            "base_spec": spec,
            "order": order,
        }
        values.update(changes)
        return prepare_cn_a_share_current_selected_fee_execution_v2(**values)

    with pytest.raises(ValueError, match="manifest"):
        prepare(
            market_bundle_manifest=_forge(manifest, content_hash="sha256:" + "0" * 64)
        )
    with pytest.raises(ValueError, match="event identity/order"):
        prepare(events=(events[1], events[0], *events[2:]))
    changed_payload = dict(events[0].payload)
    changed_payload["declaration_hash"] = "sha256:" + "0" * 64
    changed_event = replace(events[0], payload=changed_payload)
    with pytest.raises(ValueError, match="event identity/order"):
        prepare(events=(changed_event, *events[1:]))
    changed_payload = dict(events[0].payload)
    changed_payload["qualification"] = {
        **changed_payload["qualification"],
        "development_projection_authorized": False,
    }
    changed_event = replace(events[0], payload=changed_payload)
    with pytest.raises(ValueError, match="event identity/order"):
        prepare(events=(changed_event, *events[1:]))
    changed_report = dict(report)
    changed_report["declaration_hash"] = "sha256:" + "0" * 64
    with pytest.raises(ValueError, match="coverage"):
        prepare(coverage_report=changed_report)
    for complete in (False, 1):
        changed_report = dict(report)
        changed_report["finite_development_interval_coverage_complete"] = complete
        with pytest.raises(ValueError, match="coverage"):
            prepare(coverage_report=changed_report)

    @dataclass(frozen=True)
    class CnAShareCurrentSelectedRuleCoverageReport:
        body: dict[str, object]

        @property
        def report_hash(self) -> object:
            return self.body["report_hash"]

        def to_canonical_dict(self) -> dict[str, object]:
            return self.body

    with pytest.raises(TypeError, match="exact dict"):
        prepare(coverage_report=CnAShareCurrentSelectedRuleCoverageReport(report))
    with pytest.raises(ValueError, match="fee execution binding failed"):
        prepare(order=replace(order, account_id="account:other"))

    prepared = prepare()
    changed_request = replace(
        profile.request,
        composed_at=replace(
            profile.request.composed_at,
            source_sequence=SourceSequence(1),
        ),
    )
    changed_outcome = CnAShareProfileComposer().compose(changed_request)
    assert changed_outcome.result is not None
    with pytest.raises(ValueError, match="artifact identity"):
        replace(prepared.binding, resolved_profile=changed_outcome.result)
    with pytest.raises(ValueError, match="binding identity"):
        replace(
            prepared.binding,
            market_fee_rule_book=replace(
                prepared.binding.market_fee_rule_book,
                rule_book_key="substituted",
            ),
        )
    with pytest.raises(ValueError, match="binding identity"):
        replace(
            prepared.binding,
            build_artifact_manifest=replace(build, build_key="substituted"),
        )
    with pytest.raises(ValueError, match="hash mismatch"):
        replace(
            prepared.execution_binding,
            order_hash="sha256:" + "0" * 64,
        )

    attacked = object.__new__(MarketEvent)
    for field in fields(events[0]):
        object.__setattr__(attacked, field.name, getattr(events[0], field.name))
    object.__setattr__(attacked, "payload", {"nested": "substitution"})
    with pytest.raises((TypeError, ValueError)):
        prepare(events=(attacked, *events[1:]))
