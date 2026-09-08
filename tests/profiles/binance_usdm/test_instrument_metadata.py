from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from crypto_quant_domain import (
    CurrencyId,
    InstrumentId,
    InstrumentType,
    Rate,
    Scale,
    SymbolInterval,
    UtcInstant,
    VenueId,
    canonical_sha256,
)
from crypto_quant_trading import InstrumentModel, ProfilePortType
from crypto_quant_trading.profiles.binance_usdm import (
    BinanceUsdmContractStatus,
    BinanceUsdmInstrumentMetadataFailureCode,
    BinanceUsdmInstrumentMetadataSourceRef,
    BinanceUsdmInstrumentModel,
    BinanceUsdmLinearContractMetadata,
)
from tests.profiles.binance_usdm._fixtures import (
    DELIST_AT,
    ONBOARD_AT,
    RENAME_AT,
    query,
    revision,
)


def test_open_ended_perpetual_resolves_stable_linear_metadata() -> None:
    source = revision()
    request = query(
        source,
        effective_at=UtcInstant(ONBOARD_AT.epoch_nanoseconds + 10),
        captured_at=UtcInstant(ONBOARD_AT.epoch_nanoseconds + 20),
    )
    model = BinanceUsdmInstrumentModel()

    outcome = model.resolve_instrument(request)

    assert isinstance(model, InstrumentModel)
    assert model.component_ref.port_type is ProfilePortType.INSTRUMENT_MODEL
    assert model.component_ref.component_key == (
        "crypto.binance_usdm.instrument_metadata.v1"
    )
    assert outcome.failure is None
    assert outcome.result is not None
    result = outcome.result
    expected_id = InstrumentId(VenueId("binance_usdm"), "btc-usdt-perpetual")
    assert result.instrument.instrument_id == expected_id
    assert result.instrument.instrument_type is InstrumentType.LINEAR_PERPETUAL
    assert result.instrument.base_currency == CurrencyId("BTC")
    assert result.instrument.quote_currency == CurrencyId("USDT")
    assert result.instrument.settlement_currency == CurrencyId("USDT")
    assert result.active_symbol == "BTCUSDT"
    assert result.active_pair == "BTCUSDT"
    assert result.status is BinanceUsdmContractStatus.TRADING
    assert result.tradable
    assert result.listing_interval.listed_at == ONBOARD_AT
    assert result.listing_interval.delisted_at is None
    assert result.contract_metadata.contract_multiplier == Rate(
        1, Scale(0), "base_quantity_per_contract"
    )
    assert result.symbol_timeline.symbol_at(request.effective_at) == "BTCUSDT"
    assert result.visible_revisions == (source,)
    assert outcome.input_hash == canonical_sha256(request)
    assert result.resolution_hash == canonical_sha256(result)

    with pytest.raises(FrozenInstanceError):
        result.tradable = False  # type: ignore[misc]


def test_explicit_symbol_revision_preserves_identity_and_history() -> None:
    first = revision()
    renamed = revision(
        "btc-v2",
        supersedes_revision_id=first.revision_id,
        symbol="XBTUSDT",
        pair="XBTUSDT",
        effective_from=RENAME_AT,
    )
    request = query(renamed, first)

    outcome = BinanceUsdmInstrumentModel().resolve_instrument(request)

    assert outcome.failure is None
    assert outcome.result is not None
    result = outcome.result
    assert result.instrument.instrument_id == InstrumentId(
        VenueId("binance_usdm"), "btc-usdt-perpetual"
    )
    assert result.active_revision == renamed
    assert result.active_symbol == "XBTUSDT"
    assert [value.symbol for value in result.symbol_timeline.intervals] == [
        "BTCUSDT",
        "XBTUSDT",
    ]
    assert result.symbol_timeline.intervals[0].effective_from == ONBOARD_AT
    assert result.symbol_timeline.intervals[0].effective_until == RENAME_AT
    assert result.symbol_timeline.intervals[1].effective_from == RENAME_AT
    assert result.symbol_timeline.intervals[1].effective_until is None


def test_finite_delivery_closes_listing_without_erasing_history() -> None:
    first = revision()
    delisting = revision(
        "btc-v2",
        supersedes_revision_id=first.revision_id,
        delivery_at=DELIST_AT,
        effective_from=RENAME_AT,
    )
    model = BinanceUsdmInstrumentModel()
    before = query(
        first,
        delisting,
        effective_at=UtcInstant(DELIST_AT.epoch_nanoseconds - 1),
        captured_at=UtcInstant(RENAME_AT.epoch_nanoseconds + 20),
    )
    after = query(
        first,
        delisting,
        effective_at=DELIST_AT,
        captured_at=UtcInstant(DELIST_AT.epoch_nanoseconds + 20),
    )

    listed = model.resolve_instrument(before)
    delisted = model.resolve_instrument(after)

    assert listed.failure is None
    assert listed.result is not None
    assert listed.result.listing_interval.delisted_at == DELIST_AT
    assert listed.result.symbol_timeline.intervals[-1].effective_until == DELIST_AT
    assert delisted.result is None
    assert delisted.failure is not None
    assert delisted.failure.code is (
        BinanceUsdmInstrumentMetadataFailureCode.NOT_LISTED_AT_QUERY_INSTANT
    )
    assert delisted.failure.query == after


def test_captured_at_controls_onboard_correction_visibility() -> None:
    original = revision()
    corrected = revision(
        "btc-v2",
        supersedes_revision_id=original.revision_id,
        onboard_at=UtcInstant(ONBOARD_AT.epoch_nanoseconds - 100),
        effective_from=RENAME_AT,
    )
    effective_at = UtcInstant(ONBOARD_AT.epoch_nanoseconds - 50)
    before = query(
        original,
        corrected,
        effective_at=effective_at,
        captured_at=RENAME_AT,
    )
    after = query(
        corrected,
        original,
        effective_at=effective_at,
        captured_at=UtcInstant(RENAME_AT.epoch_nanoseconds + 2),
    )
    model = BinanceUsdmInstrumentModel()

    old_knowledge = model.resolve_instrument(before)
    corrected_knowledge = model.resolve_instrument(after)

    assert old_knowledge.result is None
    assert old_knowledge.failure is not None
    assert old_knowledge.failure.code is (
        BinanceUsdmInstrumentMetadataFailureCode.NOT_LISTED_AT_QUERY_INSTANT
    )
    assert corrected_knowledge.failure is None
    assert corrected_knowledge.result is not None
    assert corrected_knowledge.result.active_symbol == "BTCUSDT"
    assert corrected_knowledge.result.listing_interval.listed_at == corrected.onboard_at


def test_known_nontrading_status_is_preserved_without_tradable_fallback() -> None:
    first = revision()
    pending = revision(
        "btc-v2",
        supersedes_revision_id=first.revision_id,
        status="PENDING_TRADING",
        effective_from=RENAME_AT,
    )

    outcome = BinanceUsdmInstrumentModel().resolve_instrument(query(first, pending))

    assert outcome.failure is None
    assert outcome.result is not None
    assert outcome.result.status is BinanceUsdmContractStatus.PENDING_TRADING
    assert not outcome.result.tradable


@pytest.mark.parametrize(
    ("query_value", "expected"),
    (
        (query(), BinanceUsdmInstrumentMetadataFailureCode.MISSING_REVISION_SET),
        (
            query(
                revision(),
                revision(
                    "btc-v2",
                    supersedes_revision_id="wrong",
                    effective_from=RENAME_AT,
                ),
            ),
            BinanceUsdmInstrumentMetadataFailureCode.INVALID_REVISION_SET,
        ),
        (
            query(
                revision(supersedes_revision_id="btc-v2"),
                revision(
                    "btc-v2",
                    supersedes_revision_id="btc-v1",
                    effective_from=RENAME_AT,
                ),
            ),
            BinanceUsdmInstrumentMetadataFailureCode.INVALID_REVISION_SET,
        ),
        (
            query(
                revision(available_at=RENAME_AT),
                captured_at=UtcInstant(RENAME_AT.epoch_nanoseconds - 1),
            ),
            BinanceUsdmInstrumentMetadataFailureCode.REVISION_NOT_AVAILABLE,
        ),
        (
            query(
                revision(
                    stable_instrument_key="other-contract",
                    available_at=RENAME_AT,
                ),
                captured_at=UtcInstant(RENAME_AT.epoch_nanoseconds - 1),
            ),
            BinanceUsdmInstrumentMetadataFailureCode.REVISION_NOT_AVAILABLE,
        ),
        (
            query(revision(stable_instrument_key="other-contract")),
            BinanceUsdmInstrumentMetadataFailureCode.STABLE_IDENTITY_MISMATCH,
        ),
        (
            query(revision(contract_type="CURRENT_QUARTER")),
            BinanceUsdmInstrumentMetadataFailureCode.UNSUPPORTED_CONTRACT_TYPE,
        ),
        (
            query(revision(status="UNKNOWN")),
            BinanceUsdmInstrumentMetadataFailureCode.UNSUPPORTED_CONTRACT_STATUS,
        ),
        (
            query(revision(quote_asset="USDC", margin_asset="USDT")),
            BinanceUsdmInstrumentMetadataFailureCode.INVALID_CURRENCY_CONTEXT,
        ),
        (
            query(revision(delivery_at=ONBOARD_AT)),
            BinanceUsdmInstrumentMetadataFailureCode.INVALID_LISTING_INTERVAL,
        ),
        (
            query(
                revision(),
                effective_at=UtcInstant(ONBOARD_AT.epoch_nanoseconds - 1),
            ),
            BinanceUsdmInstrumentMetadataFailureCode.NOT_LISTED_AT_QUERY_INSTANT,
        ),
    ),
)
def test_failure_codes_are_structured_and_ordered(query_value, expected) -> None:
    outcome = BinanceUsdmInstrumentModel().resolve_instrument(query_value)

    assert outcome.result is None
    assert outcome.failure is not None
    assert outcome.failure.code is expected
    assert outcome.failure.failure_hash == canonical_sha256(outcome.failure)


def test_symbol_and_metadata_conflicts_fail_closed() -> None:
    first = revision()
    rename_at_delist = revision(
        "btc-v2",
        supersedes_revision_id=first.revision_id,
        symbol="XBTUSDT",
        delivery_at=DELIST_AT,
        effective_from=DELIST_AT,
        available_at=UtcInstant(DELIST_AT.epoch_nanoseconds + 1),
    )
    symbol_conflict = query(
        first,
        rename_at_delist,
        effective_at=UtcInstant(DELIST_AT.epoch_nanoseconds - 1),
        captured_at=UtcInstant(DELIST_AT.epoch_nanoseconds + 2),
    )
    conflicting_source = replace(
        revision(
            "btc-v2",
            supersedes_revision_id=first.revision_id,
            effective_from=RENAME_AT,
        ),
        source_ref=BinanceUsdmInstrumentMetadataSourceRef(
            source_key=first.source_ref.source_key,
            source_hash=canonical_sha256({"different": True}),
        ),
    )

    symbol_outcome = BinanceUsdmInstrumentModel().resolve_instrument(symbol_conflict)
    metadata_outcome = BinanceUsdmInstrumentModel().resolve_instrument(
        query(first, conflicting_source)
    )

    assert symbol_outcome.failure is not None
    assert symbol_outcome.failure.code is (
        BinanceUsdmInstrumentMetadataFailureCode.SYMBOL_TIMELINE_CONFLICT
    )
    assert metadata_outcome.failure is not None
    assert metadata_outcome.failure.code is (
        BinanceUsdmInstrumentMetadataFailureCode.METADATA_CONFLICT
    )


def test_constructor_revalidation_rejects_forged_authority() -> None:
    request = query(revision())
    outcome = BinanceUsdmInstrumentModel().resolve_instrument(request)
    assert outcome.result is not None
    result = outcome.result

    with pytest.raises(ValueError, match="resolution fields"):
        replace(result, tradable=False)
    with pytest.raises(ValueError, match="resolution fields"):
        replace(result, active_symbol="FORGED")
    with pytest.raises(ValueError, match="resolution fields"):
        replace(result, status=BinanceUsdmContractStatus.PENDING_TRADING)
    with pytest.raises(ValueError, match="resolution fields"):
        replace(result, visible_revisions=())
    with pytest.raises(ValueError, match="resolution fields"):
        replace(
            result,
            instrument=replace(
                result.instrument,
                instrument_id=InstrumentId(VenueId("binance_usdm"), "forged"),
            ),
        )
    with pytest.raises(ValueError, match="resolution fields"):
        replace(
            result,
            symbol_timeline=replace(
                result.symbol_timeline,
                intervals=(
                    SymbolInterval("FORGED", ONBOARD_AT, None),
                ),
            ),
        )
    with pytest.raises(ValueError, match="resolution fields"):
        replace(
            result,
            listing_interval=replace(
                result.listing_interval,
                listed_at=UtcInstant(ONBOARD_AT.epoch_nanoseconds - 1),
            ),
        )
    with pytest.raises(ValueError, match="resolution fields"):
        replace(
            result,
            contract_metadata=replace(
                result.contract_metadata,
                base_currency=CurrencyId("ETH"),
            ),
        )

    failed = BinanceUsdmInstrumentModel().resolve_instrument(query())
    assert failed.failure is not None
    with pytest.raises(ValueError, match="failure fields"):
        replace(failed.failure, message="forged")
    with pytest.raises(ValueError, match="source_hash"):
        BinanceUsdmInstrumentMetadataSourceRef("fixture", "not-a-hash")
    with pytest.raises(ValueError, match="contract_multiplier"):
        BinanceUsdmLinearContractMetadata(
            instrument_id=result.instrument.instrument_id,
            base_currency=CurrencyId("BTC"),
            quote_currency=CurrencyId("USDT"),
            settlement_currency=CurrencyId("USDT"),
            contract_multiplier=Rate(2, Scale(0), "base_quantity_per_contract"),
        )


def test_revision_input_order_is_canonical_and_lineages_are_not_guessed() -> None:
    first = revision()
    renamed = revision(
        "btc-v2",
        supersedes_revision_id=first.revision_id,
        symbol="XBTUSDT",
        effective_from=RENAME_AT,
    )
    ordered = query(first, renamed)
    reordered = query(renamed, first)
    separate = query(
        revision(stable_instrument_key="renamed-btc-usdt"),
        stable_instrument_key="renamed-btc-usdt",
        effective_at=UtcInstant(ONBOARD_AT.epoch_nanoseconds + 10),
        captured_at=UtcInstant(ONBOARD_AT.epoch_nanoseconds + 20),
    )

    first_outcome = BinanceUsdmInstrumentModel().resolve_instrument(ordered)
    reordered_outcome = BinanceUsdmInstrumentModel().resolve_instrument(reordered)
    separate_outcome = BinanceUsdmInstrumentModel().resolve_instrument(separate)

    assert ordered == reordered
    assert canonical_sha256(first_outcome) == canonical_sha256(reordered_outcome)
    assert first_outcome.result is not None
    assert separate_outcome.result is not None
    assert (
        first_outcome.result.instrument.instrument_id
        != separate_outcome.result.instrument.instrument_id
    )
