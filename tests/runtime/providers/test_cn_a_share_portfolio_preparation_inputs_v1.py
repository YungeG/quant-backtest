"""Standard request input identity; source-unqualified portfolios never prepare."""
from __future__ import annotations

from dataclasses import replace

import pytest

from crypto_quant_backtest import (
    BAR_OPEN_CAPABILITY, TARGET_STREAM_CAPABILITY, TARGET_STREAM_EVENT_TYPE,
    BacktestTargetStreamError, BacktestTargetStreamFailureCode, BacktestTargetStreamRef,
    BacktestTargetStreamRepository,
    PrecomputedTargetStream,
)
from crypto_quant_backtest.cn_a_share_portfolio_preparation_inputs_v1 import (
    CnASharePortfolioPreparationInputsV1, CnASharePortfolioSourceAdmissionBlockedV1,
    require_cn_a_share_portfolio_source_qualification_v1,
)
from crypto_quant_domain import (
    ArtifactEnvelope, ArtifactNotFoundError, ArtifactReadResult, ArtifactRef,
    CashBalanceKey, CurrencyId, InstrumentCatalog, InstrumentDefinition, InstrumentId,
    InstrumentType, Money, PositionBalanceKey, Scale, SourceSequence, TimelinePhase,
    UtcInstant, VenueId, canonical_bytes, canonical_sha256,
)
from crypto_quant_market_data import InMemoryMarketBundleReader, MarketBundleCapability, MarketEvent
from crypto_quant_trading import LedgerBalanceRegistration, LedgerSchema

_ACCOUNT = "pharma.cash.account"
_CNY = CurrencyId("CNY")
_CODES = ("600000.SH", "600001.SH", "603000.SH", "688001.SH", "000001.SZ",
          "000002.SZ", "002001.SZ", "002002.SZ", "300001.SZ", "301001.SZ")

class _Cas:
    def __init__(self):
        self.values = {}
        self.reads = {}

    def put(self, *, envelope):
        ref = ArtifactRef.from_envelope(envelope)
        self.values[ref] = envelope
        return ref

    def read(self, *, ref):
        self.reads[ref] = self.reads.get(ref, 0) + 1
        if ref not in self.values:
            raise ArtifactNotFoundError(ref.content_hash)
        envelope = self.values[ref]
        return ArtifactReadResult(envelope, None, canonical_bytes(envelope), canonical_sha256(envelope))


def _target_event(ids):
    instant = UtcInstant(100)
    return MarketEvent(
        event_id="pharma-weekly-target", stream_key="targets",
        event_type=TARGET_STREAM_EVENT_TYPE, capability=TARGET_STREAM_CAPABILITY,
        instrument_id=None, event_time=instant, available_time=instant,
        phase=TimelinePhase(30, "strategy_decision"), source_sequence=SourceSequence(1),
        revision_id="fixture.rev1", supersedes_revision_id=None,
        source_key="fixture.pharma.targets", source_hash="sha256:" + "a" * 64,
        payload={"schema_version": 1, "candidate": {
            "schema_version": 1, "strategy_id": "pharma.v1", "sleeve_id": "pharma.weekly",
            "decision_time": 100, "observed_through": 99, "effective_time": 100, "expires_at": 250,
            "targets": [{"instrument_id": {"venue": value.venue.value,
                                            "stable_key": value.stable_key},
                         "value": "1" if len(ids) == 1 else "0.5" if len(ids) == 2 else "0.1"}
                        for value in ids],
            "confidence": "1", "reason": "structural input only",
            "evidence": {"revision": "fixture"},
        }},
    )

def _inputs(codes, *, account_id=_ACCOUNT):
    ids = tuple(sorted((InstrumentId(VenueId("xshg" if code.endswith(".SH") else "xshe"), code[:6])
                        for code in codes), key=lambda ident: (ident.venue.value, ident.stable_key)))
    catalog = InstrumentCatalog((_CNY,), tuple(
        InstrumentDefinition(ident, InstrumentType.EQUITY, None, _CNY, _CNY) for ident in ids), ())
    schema = LedgerSchema((
        *(LedgerBalanceRegistration(CashBalanceKey(account_id, VenueId(venue), _CNY), Scale(2))
          for venue in ("xshg", "xshe")),
        *(LedgerBalanceRegistration(PositionBalanceKey(account_id, ident.venue, ident), Scale(0))
          for ident in ids),
    ))
    manifest = InMemoryMarketBundleReader.build(
        bundle_key="pharma.inputs.v1", schema_version=1,
        coverage_start=UtcInstant(1), coverage_end_exclusive=UtcInstant(2),
        instrument_catalog_hash=canonical_sha256(catalog), capabilities=(), streams={},
    )
    store = _Cas()
    target_ref = BacktestTargetStreamRepository(reader=store, publisher=store).publish(
        ArtifactRef("fixture_context", 1, "sha256:" + "9" * 64),
        PrecomputedTargetStream("targets", (_target_event(ids),)),
    )
    declaration = CnASharePortfolioPreparationInputsV1(
        account_id, ids, catalog, schema, Money(100_000, Scale(2), "CNY"),
        target_ref, manifest.bundle_ref,
    )
    return declaration, manifest, store


@pytest.mark.parametrize("count", (1, 2, 10))
def test_variable_n_sh_sz_one_account_cny_input_identity_only(count):
    scope, _, _ = _inputs((_CODES[0],) if count == 1 else (_CODES[0], _CODES[4]) if count == 2 else _CODES)
    assert len(scope.instrument_ids) == count
    assert len(scope.ledger_schema.cash_registrations) == 2
    assert scope.input_hash == canonical_sha256(scope)
    assert not scope.to_canonical_dict()["trade_authorized"]
    assert not scope.to_canonical_dict()["shared_cny_funding_authority_qualified"]
    assert replace(scope, target_stream_ref=BacktestTargetStreamRef(
        ArtifactRef("backtest_target_stream", 1, "sha256:" + "2" * 64))).input_hash != scope.input_hash


@pytest.mark.parametrize(("mutation", "reason"), [
    ("duplicate", "unique sorted"), ("reverse", "unique sorted"),
    ("bj", "unique sorted"), ("foreign_code", "unique sorted"),
    ("wrong_account", "same-account"), ("missing_cash", "both venue"),
    ("missing_position", "same-account"), ("wrong_currency", "positive CNY"),
])
def test_reject_noncanonical_or_split_cash_identity(mutation, reason):
    scope, _, _ = _inputs((_CODES[0], _CODES[4]))
    if mutation == "duplicate":
        changed = {"instrument_ids": (scope.instrument_ids[0],) * 2}
    elif mutation == "reverse":
        changed = {"instrument_ids": tuple(reversed(scope.instrument_ids))}
    elif mutation in {"bj", "foreign_code"}:
        venue, key = ("bj", "430001") if mutation == "bj" else ("xshg", "900001")
        changed = {"instrument_ids": (InstrumentId(VenueId(venue), key), scope.instrument_ids[1])}
    elif mutation == "wrong_account":
        registrations = tuple(
            replace(registration, key=CashBalanceKey("other", registration.key.venue_id, _CNY))
            if isinstance(registration.key, CashBalanceKey) and registration.key.venue_id.value == "xshe"
            else registration for registration in scope.ledger_schema.registrations)
        changed = {"ledger_schema": LedgerSchema(registrations)}
    elif mutation in {"missing_cash", "missing_position"}:
        registration_type = CashBalanceKey if mutation == "missing_cash" else PositionBalanceKey
        changed = {"ledger_schema": LedgerSchema(tuple(
            registration for registration in scope.ledger_schema.registrations
            if not isinstance(registration.key, registration_type)
            or registration.key.venue_id.value != "xshe"))}
    else:
        changed = {"initial_cash": Money(100_000, Scale(2), "USD")}
    with pytest.raises(ValueError, match=reason):
        replace(scope, **changed)


def test_source_preflight_rejects_absent_bar_and_insufficient_capability_metadata():
    scope, empty, store = _inputs((_CODES[0], _CODES[4]))
    with pytest.raises(ValueError, match="BarOpen capability"):
        require_cn_a_share_portfolio_source_qualification_v1(
            scope, market_reader=empty, artifact_reader=store)
    claimed = InMemoryMarketBundleReader.build(
        bundle_key="pharma.claimed.v1", schema_version=1,
        coverage_start=UtcInstant(1), coverage_end_exclusive=UtcInstant(2),
        instrument_catalog_hash=canonical_sha256(scope.instrument_catalog),
        capabilities=(BAR_OPEN_CAPABILITY,), streams={},
    )
    with pytest.raises(ValueError, match="source qualification unavailable"):
        require_cn_a_share_portfolio_source_qualification_v1(
            replace(scope, market_bundle_ref=claimed.bundle_ref), market_reader=claimed, artifact_reader=store)
    with pytest.raises(ValueError, match="bundle/ref/catalog identity mismatch"):
        require_cn_a_share_portfolio_source_qualification_v1(
            scope, market_reader=claimed, artifact_reader=store)
    assert store.reads[scope.target_stream_ref.artifact_ref] == 1


def test_source_gate_rejects_tampered_retained_target_ref_before_authority():
    scope, _, store = _inputs((_CODES[0], _CODES[4]))
    claimed = InMemoryMarketBundleReader.build(
        bundle_key="pharma.claimed.v1", schema_version=1,
        coverage_start=UtcInstant(1), coverage_end_exclusive=UtcInstant(2),
        instrument_catalog_hash=canonical_sha256(scope.instrument_catalog),
        capabilities=(BAR_OPEN_CAPABILITY,), streams={},
    )
    bad = ArtifactEnvelope.create("backtest_target_stream", 1, {
        "producer_context_ref": ArtifactRef("fixture_context", 1, "sha256:" + "9" * 64),
        "target_stream": PrecomputedTargetStream("targets", ()),
    })
    store.values[scope.target_stream_ref.artifact_ref] = bad
    with pytest.raises(BacktestTargetStreamError) as failure:
        require_cn_a_share_portfolio_source_qualification_v1(
            replace(scope, market_bundle_ref=claimed.bundle_ref), market_reader=claimed,
            artifact_reader=store)
    assert failure.value.code is BacktestTargetStreamFailureCode.TAMPERED


def test_real_looking_n10_bar_and_claimed_status_mark_capabilities_cannot_qualify_history():
    scope, _, store = _inputs(_CODES)
    bars = tuple(MarketEvent(
        event_id=f"real-looking-open-{index}", stream_key="bars.open",
        event_type="bar_open", capability=BAR_OPEN_CAPABILITY,
        instrument_id=instrument, event_time=UtcInstant(200), available_time=UtcInstant(200),
        phase=TimelinePhase(60, "bar_open"), source_sequence=SourceSequence(index),
        revision_id="locally-labelled-2026", supersedes_revision_id=None,
        source_key=f"tushare.daily.20240108.{instrument.stable_key}",
        source_hash=canonical_sha256({"fake_raw": str(instrument)}),
        payload={"schema_version": 1, "bar_kind": "real",
                 "open_price": {"units": 1000 + index, "scale": 2, "quote_currency": "CNY"}},
    ) for index, instrument in enumerate(scope.instrument_ids, 1))
    reader = InMemoryMarketBundleReader.build(
        bundle_key="looks-real-but-unqualified", schema_version=1,
        coverage_start=UtcInstant(199), coverage_end_exclusive=UtcInstant(300),
        instrument_catalog_hash=canonical_sha256(scope.instrument_catalog),
        capabilities=(BAR_OPEN_CAPABILITY, MarketBundleCapability("cn_stock_status", 1),
                      MarketBundleCapability("daily_closing_mark", 1)),
        streams={"bars.open": bars})
    original_count = len(store.values)
    with pytest.raises(CnASharePortfolioSourceAdmissionBlockedV1) as failure:
        require_cn_a_share_portfolio_source_qualification_v1(
            replace(scope, market_bundle_ref=reader.bundle_ref),
            market_reader=reader, artifact_reader=store)
    assert set(failure.value.reason_codes) == {
        "membership_effective_revision_unverified",
        "per_stock_listing_st_suspension_limit_unverified",
        "xshg_xshe_account_fee_effective_interval_unverified",
        "corporate_action_lifecycle_unverified",
        "venue_calendar_complete_unverified",
        "daily_close_mark_series_unverified",
        "economic_account_owner_head_unqualified",
        "historical_provider_revision_availability_unverified",
    }
    assert len(store.values) == original_count  # No case/result publication on fake metadata.
