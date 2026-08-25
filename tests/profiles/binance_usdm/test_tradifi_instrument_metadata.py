from __future__ import annotations

from typing import Any

import pytest
from crypto_quant_domain import (
    CurrencyId,
    InstrumentId,
    InstrumentType,
    Rate,
    Scale,
    UtcInstant,
    VenueId,
    canonical_sha256,
)
from crypto_quant_trading import InstrumentModel, ProfilePortType
from crypto_quant_trading.profiles.binance_usdm import (
    BinanceUsdmContractStatus,
    BinanceUsdmInstrumentMetadataFailureCode,
    BinanceUsdmInstrumentMetadataQuery,
    BinanceUsdmInstrumentMetadataRevision,
    BinanceUsdmInstrumentModel,
    BinanceUsdmTradifiInstrumentMetadataModel,
)

from tests.profiles.binance_usdm._fixtures import DELIST_AT, ONBOARD_AT, query, revision

KORU_STABLE_KEY = "koru-usdt-tradifi-perpetual"
TRADIFI_COMPONENT_KEY = "crypto.binance_usdm.tradifi.instrument-metadata.v1"
TRADIFI_COMPONENT_DIGEST = (
    "sha256:731cc32a54f7921a94e33dcd1a149c33760ca3bb58d5f19b8dc1e1f2fadd3fee"
)
ORDINARY_COMPONENT_DIGEST = (
    "sha256:eb8155ec923c2d21f2ad0dd321fa1ad948c72cbe25c7dccdadf3d0a5268b6963"
)


def tradifi_revision(
    revision_id: str = "koru-v1",
    **kwargs: Any,
) -> BinanceUsdmInstrumentMetadataRevision:
    parameters: dict[str, Any] = {
        "stable_instrument_key": KORU_STABLE_KEY,
        "symbol": "KORUUSDT",
        "pair": "KORUUSDT",
        "contract_type": "TRADIFI_PERPETUAL",
        "base_asset": "KORU",
        "quote_asset": "USDT",
        "margin_asset": "USDT",
    }
    parameters.update(kwargs)
    return revision(revision_id, **parameters)


def test_tradifi_perpetual_accepts_exact_koru_contract() -> None:
    source = tradifi_revision()
    request = query(
        source,
        stable_instrument_key=KORU_STABLE_KEY,
        effective_at=UtcInstant(ONBOARD_AT.epoch_nanoseconds + 10),
        captured_at=UtcInstant(ONBOARD_AT.epoch_nanoseconds + 20),
    )
    model = BinanceUsdmTradifiInstrumentMetadataModel()

    outcome = model.resolve_instrument(request)

    assert isinstance(model, InstrumentModel)
    assert model.component_ref.port_type is ProfilePortType.INSTRUMENT_MODEL
    assert model.component_ref.component_key == TRADIFI_COMPONENT_KEY
    assert model.component_ref.component_digest == TRADIFI_COMPONENT_DIGEST
    assert model.component_ref.component_digest != ORDINARY_COMPONENT_DIGEST
    assert outcome.failure is None
    assert outcome.result is not None
    result = outcome.result
    assert result.instrument.instrument_id == InstrumentId(
        VenueId("binance_usdm"),
        KORU_STABLE_KEY,
    )
    assert result.instrument.instrument_type is InstrumentType.LINEAR_PERPETUAL
    assert result.instrument.base_currency == CurrencyId("KORU")
    assert result.instrument.quote_currency == CurrencyId("USDT")
    assert result.instrument.settlement_currency == CurrencyId("USDT")
    assert result.contract_metadata.contract_multiplier == Rate(
        1, Scale(0), "base_quantity_per_contract"
    )
    assert result.active_symbol == "KORUUSDT"
    assert result.active_pair == "KORUUSDT"
    assert result.active_pair == result.active_symbol
    assert result.status is BinanceUsdmContractStatus.TRADING
    assert result.active_revision.contract_type == "TRADIFI_PERPETUAL"
    assert result.tradable
    assert result.visible_revisions == (source,)
    assert result.symbol_timeline.symbol_at(request.effective_at) == "KORUUSDT"
    assert outcome.input_hash == canonical_sha256(request)
    assert result.resolution_hash == canonical_sha256(result)


@pytest.mark.parametrize(
    "contract_type",
    (
        "PERPETUAL",
        "CURRENT_QUARTER",
    ),
)
def test_tradifi_non_trading_contracts_are_rejected(contract_type: str) -> None:
    model = BinanceUsdmTradifiInstrumentMetadataModel()

    outcome = model.resolve_instrument(
        query(
            tradifi_revision(contract_type=contract_type),
            stable_instrument_key=KORU_STABLE_KEY,
        )
    )

    assert outcome.result is None
    assert outcome.failure is not None
    assert outcome.failure.code is (
        BinanceUsdmInstrumentMetadataFailureCode.UNSUPPORTED_CONTRACT_TYPE
    )


@pytest.mark.parametrize(
    ("query_value", "expected"),
    (
        (
            BinanceUsdmInstrumentMetadataQuery(
                stable_instrument_key=KORU_STABLE_KEY,
                effective_at=UtcInstant(ONBOARD_AT.epoch_nanoseconds + 10),
                captured_at=UtcInstant(ONBOARD_AT.epoch_nanoseconds + 20),
                revisions=(),
            ),
            BinanceUsdmInstrumentMetadataFailureCode.MISSING_REVISION_SET,
        ),
        (
            query(
                tradifi_revision(supersedes_revision_id="wrong"),
                tradifi_revision(
                    "koru-v2",
                    supersedes_revision_id="koru-v1",
                ),
                stable_instrument_key=KORU_STABLE_KEY,
            ),
            BinanceUsdmInstrumentMetadataFailureCode.INVALID_REVISION_SET,
        ),
        (
            query(
                tradifi_revision(quote_asset="USDC", margin_asset="USDT"),
                stable_instrument_key=KORU_STABLE_KEY,
            ),
            BinanceUsdmInstrumentMetadataFailureCode.INVALID_CURRENCY_CONTEXT,
        ),
        (
            query(
                tradifi_revision(delivery_at=ONBOARD_AT),
                stable_instrument_key=KORU_STABLE_KEY,
            ),
            BinanceUsdmInstrumentMetadataFailureCode.INVALID_LISTING_INTERVAL,
        ),
        (
            query(
                tradifi_revision(status="UNKNOWN"),
                stable_instrument_key=KORU_STABLE_KEY,
            ),
            BinanceUsdmInstrumentMetadataFailureCode.UNSUPPORTED_CONTRACT_STATUS,
        ),
        (
            query(
                tradifi_revision(stable_instrument_key="other-tradifi-perpetual"),
                stable_instrument_key=KORU_STABLE_KEY,
            ),
            BinanceUsdmInstrumentMetadataFailureCode.STABLE_IDENTITY_MISMATCH,
        ),
    ),
)
def test_tradifi_failure_precedence(query_value, expected) -> None:
    outcome = BinanceUsdmTradifiInstrumentMetadataModel().resolve_instrument(query_value)

    assert outcome.result is None
    assert outcome.failure is not None
    assert outcome.failure.code is expected
    assert outcome.failure.failure_hash == canonical_sha256(outcome.failure)


@pytest.mark.parametrize(
    ("query_value", "expected"),
    (
        (
            query(
                tradifi_revision(
                    contract_type="PERPETUAL",
                    status="UNKNOWN",
                    supersedes_revision_id="wrong",
                ),
                stable_instrument_key=KORU_STABLE_KEY,
            ),
            BinanceUsdmInstrumentMetadataFailureCode.INVALID_REVISION_SET,
        ),
        (
            query(
                tradifi_revision(
                    contract_type="PERPETUAL",
                    status="UNKNOWN",
                    available_at=DELIST_AT,
                ),
                stable_instrument_key=KORU_STABLE_KEY,
                captured_at=UtcInstant(DELIST_AT.epoch_nanoseconds - 1),
            ),
            BinanceUsdmInstrumentMetadataFailureCode.REVISION_NOT_AVAILABLE,
        ),
        (
            query(
                tradifi_revision(
                    stable_instrument_key="other-tradifi-perpetual",
                    contract_type="PERPETUAL",
                    status="UNKNOWN",
                ),
                stable_instrument_key=KORU_STABLE_KEY,
            ),
            BinanceUsdmInstrumentMetadataFailureCode.STABLE_IDENTITY_MISMATCH,
        ),
        (
            query(
                tradifi_revision(contract_type="PERPETUAL", status="UNKNOWN"),
                stable_instrument_key=KORU_STABLE_KEY,
            ),
            BinanceUsdmInstrumentMetadataFailureCode.UNSUPPORTED_CONTRACT_TYPE,
        ),
        (
            query(
                tradifi_revision(
                    contract_type="PERPETUAL",
                    quote_asset="USDC",
                    margin_asset="USDT",
                ),
                stable_instrument_key=KORU_STABLE_KEY,
            ),
            BinanceUsdmInstrumentMetadataFailureCode.UNSUPPORTED_CONTRACT_TYPE,
        ),
        (
            query(
                tradifi_revision(
                    contract_type="PERPETUAL",
                    delivery_at=ONBOARD_AT,
                ),
                stable_instrument_key=KORU_STABLE_KEY,
            ),
            BinanceUsdmInstrumentMetadataFailureCode.UNSUPPORTED_CONTRACT_TYPE,
        ),
    ),
)
def test_tradifi_mixed_invalid_failure_precedence(query_value, expected) -> None:
    outcome = BinanceUsdmTradifiInstrumentMetadataModel().resolve_instrument(query_value)

    assert outcome.result is None
    assert outcome.failure is not None
    assert outcome.failure.code is expected


def test_stable_canonical_replay_for_tradifi_queries() -> None:
    first = tradifi_revision()
    second = tradifi_revision(
        "koru-v2",
        supersedes_revision_id="koru-v1",
        symbol="KORUV2USDT",
        pair="KORUV2USDT",
        effective_from=DELIST_AT,
        available_at=DELIST_AT,
    )
    ordered = query(
        first,
        second,
        stable_instrument_key=KORU_STABLE_KEY,
        effective_at=UtcInstant(DELIST_AT.epoch_nanoseconds + 10),
        captured_at=UtcInstant(DELIST_AT.epoch_nanoseconds + 20),
    )
    reordered = query(
        second,
        first,
        stable_instrument_key=KORU_STABLE_KEY,
        effective_at=UtcInstant(DELIST_AT.epoch_nanoseconds + 10),
        captured_at=UtcInstant(DELIST_AT.epoch_nanoseconds + 20),
    )

    model = BinanceUsdmTradifiInstrumentMetadataModel()
    first_outcome = model.resolve_instrument(ordered)
    second_outcome = model.resolve_instrument(reordered)

    assert first_outcome.result is not None
    assert second_outcome.result is not None
    assert (
        first_outcome.result.instrument.instrument_id
        == second_outcome.result.instrument.instrument_id
    )
    assert (
        first_outcome.result.visible_revisions
        == second_outcome.result.visible_revisions
    )
    assert first_outcome.result.resolution_hash == second_outcome.result.resolution_hash
    assert canonical_sha256(first_outcome) == canonical_sha256(second_outcome)


def test_ordinary_component_digest_remains_unchanged() -> None:
    assert (
        BinanceUsdmInstrumentModel().component_ref.component_digest
        == ORDINARY_COMPONENT_DIGEST
    )
