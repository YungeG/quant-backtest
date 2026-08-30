from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from copy import deepcopy
from dataclasses import replace
from typing import cast

import pytest
from crypto_quant_backtest import (
    BinanceUsdmTradifiProfileComposer,
    BinanceUsdmTradifiProfileCompositionFailureCode,
    BinanceUsdmTradifiProfileCompositionRequest,
    decode_binance_usdm_tradifi_profile_composition_request_v1,
)
from crypto_quant_domain import ArtifactRef, canonical_bytes, canonical_sha256
from crypto_quant_trading.profiles.binance_usdm import (
    BinanceUsdmAccountProfileModel,
    BinanceUsdmFundingSourceModel,
)

from ._tradifi_fixtures import HOUR, START, composition_request

_ERROR = "invalid Binance USD-M TradFi profile composition wire"


def _wire(
    request: BinanceUsdmTradifiProfileCompositionRequest | None = None,
) -> dict[str, object]:
    return json.loads(canonical_bytes(request or composition_request()))


def _decode(wire: Mapping[str, object]) -> BinanceUsdmTradifiProfileCompositionRequest:
    try:
        expected_hash = canonical_sha256(wire)
    except ValueError:
        expected_hash = "sha256:" + "0" * 64
    return decode_binance_usdm_tradifi_profile_composition_request_v1(
        wire, expected_hash
    )


def test_exact_wire_decodes_replays_and_matches_golden_hash() -> None:
    wire = _wire()

    first = _decode(wire)
    replay = _decode(deepcopy(wire))

    assert type(first) is BinanceUsdmTradifiProfileCompositionRequest
    assert first == replay
    assert canonical_bytes(first) == canonical_bytes(wire)
    assert first.request_hash == (
        "sha256:624253e3418ffb2009a6a946e7b304b3b338e5250a92bce4a4b6a53c98dbcedb"
    )


def test_raw_exact_valuation_authority_is_explicit_and_hash_bound() -> None:
    ordinary = composition_request()
    raw = replace(ordinary, raw_exact_valuation=True)

    assert "raw_exact_valuation" not in _wire(ordinary)
    wire = _wire(raw)
    assert wire["raw_exact_valuation"] is True
    decoded = _decode(wire)
    assert decoded.raw_exact_valuation is True
    assert decoded.request_hash == canonical_sha256(wire)
    assert decoded.request_hash != ordinary.request_hash


def test_raw_exact_margin_authority_is_explicit_and_hash_bound() -> None:
    ordinary = composition_request()
    raw = replace(ordinary, raw_exact_margin=True)

    assert "raw_exact_margin" not in _wire(ordinary)
    wire = _wire(raw)
    assert wire["raw_exact_margin"] is True
    decoded = _decode(wire)
    assert decoded.raw_exact_margin is True
    assert decoded.request_hash == canonical_sha256(wire)
    assert decoded.request_hash != ordinary.request_hash


def test_raw_exact_valuation_false_is_not_a_valid_wire_authority() -> None:
    wire = _wire()
    wire["raw_exact_valuation"] = False

    with pytest.raises(ValueError, match=f"^{_ERROR}$"):
        _decode(wire)

    wire = _wire()
    wire["raw_exact_margin"] = False
    with pytest.raises(ValueError, match=f"^{_ERROR}$"):
        _decode(wire)


@pytest.mark.parametrize(
    "mutate",
    (
        lambda wire: wire.__setitem__("unexpected", None),
        lambda wire: wire.pop("timeline_window"),
        lambda wire: wire["price_purposes"].reverse(),
        lambda wire: wire["funding_sources"][0]["query"]["funding_book"]["records"][
            0
        ].__setitem__("rate_type", "Special"),
        lambda wire: wire["account_profile"]["fee_reservation_rule_set"].__setitem__(
            "config_hash", "sha256:" + "0" * 64
        ),
        lambda wire: wire["slippage_model"]["applicability_envelope"].__setitem__(
            "config_hash", "sha256:" + "0" * 64
        ),
        lambda wire: wire["order_rules"]["query"]["rule_book"]["bands"][0].__setitem__(
            "tick_size", "0.010"
        ),
        lambda wire: wire["admitted_maximum_quantity"].__setitem__("units", 1.0),
        lambda wire: wire["account_capacity"].__setitem__("max_num_orders", True),
    ),
)
def test_any_top_or_nested_mutation_is_rejected(mutate) -> None:
    wire = _wire()
    mutate(wire)

    with pytest.raises(ValueError, match=f"^{_ERROR}$"):
        _decode(wire)


class _DuplicateKeyMapping(Mapping[str, object]):
    def __getitem__(self, key: str) -> object:
        return _wire()[key]

    def __iter__(self) -> Iterator[str]:
        yield "type"
        yield "type"

    def __len__(self) -> int:
        return 2


def test_constructor_business_failure_domain_round_trips_to_composer() -> None:
    request = composition_request()
    ordinary = request.price_purposes[0].query.instrument_metadata
    xkrx, arcx = request.calendar_refs
    cases = (
        (
            BinanceUsdmTradifiProfileCompositionFailureCode.MISSING_TRADIFI_INSTRUMENT_METADATA,
            {"instrument_metadata": None},
        ),
        (
            BinanceUsdmTradifiProfileCompositionFailureCode.FOREIGN_INSTRUMENT_METADATA,
            {"instrument_metadata": ordinary},
        ),
        (
            BinanceUsdmTradifiProfileCompositionFailureCode.CROSS_BAND_COVERAGE_MISMATCH,
            {"order_rules": None},
        ),
        (
            BinanceUsdmTradifiProfileCompositionFailureCode.CROSS_BAND_COVERAGE_MISMATCH,
            {"margin_tiers": None},
        ),
        (
            BinanceUsdmTradifiProfileCompositionFailureCode.MISSING_ACCOUNT_PROFILE,
            {"account_profile": None},
        ),
        (
            BinanceUsdmTradifiProfileCompositionFailureCode.MISSING_ACCOUNT_CAPACITY,
            {"account_capacity": None},
        ),
        (
            BinanceUsdmTradifiProfileCompositionFailureCode.CALENDAR_REF_MISMATCH,
            {
                "calendar_refs": (
                    ArtifactRef("arbitrary_calendar", 7, "sha256:" + "44" * 32),
                    arcx,
                    xkrx,
                )
            },
        ),
        (
            BinanceUsdmTradifiProfileCompositionFailureCode.UNIT_REGIME_REF_MISMATCH,
            {"post_adjustment_unit_regime_ref": None},
        ),
        (
            BinanceUsdmTradifiProfileCompositionFailureCode.UNIT_REGIME_REF_MISMATCH,
            {
                "post_adjustment_unit_regime_ref": ArtifactRef(
                    "arbitrary_unit_regime", 9, "sha256:" + "55" * 32
                )
            },
        ),
    )

    for expected, overrides in cases:
        original = composition_request(**overrides)
        decoded = _decode(_wire(original))
        outcome = BinanceUsdmTradifiProfileComposer().compose(decoded)

        assert canonical_bytes(decoded) == canonical_bytes(original)
        assert outcome.failure is not None
        assert outcome.failure.code is expected


def _funding_with_source_record(rate_type: str | None):
    funding = composition_request().funding_sources[0]
    extra = replace(
        funding.selected_record,
        funding_time_milliseconds=(START.epoch_nanoseconds + HOUR) // 1_000_000,
        rate_type=rate_type,
        event_id=f"funding:KORUUSDT:extra:{rate_type}",
    )
    book = replace(
        funding.query.funding_book,
        records=funding.query.funding_book.records + (extra,),
    )
    outcome = BinanceUsdmFundingSourceModel().resolve_funding_source(
        replace(funding.query, funding_book=book)
    )
    assert outcome.result is not None
    return outcome.result


@pytest.mark.parametrize("rate_type", (None, "Regular", "Special"))
def test_missing_regular_and_special_source_records_round_trip(
    rate_type: str | None,
) -> None:
    original = composition_request(
        funding_sources=(_funding_with_source_record(rate_type),)
    )
    decoded = _decode(_wire(original))

    assert canonical_bytes(decoded) == canonical_bytes(original)
    assert (
        decoded.funding_sources[0].query.funding_book.records[1].rate_type == rate_type
    )
    composed = BinanceUsdmTradifiProfileComposer().compose(decoded)
    if rate_type == "Special":
        assert composed.failure is not None
        assert composed.failure.code is (
            BinanceUsdmTradifiProfileCompositionFailureCode.SPECIAL_FUNDING_UNSUPPORTED
        )
    else:
        assert composed.result is not None


@pytest.mark.parametrize(
    ("fee_tier", "maker_rate", "taker_rate"),
    (
        (0, "0", "0"),
        (1, "0.00010000", "0.00040000"),
        (2, "-0", "0.00030000"),
    ),
)
def test_account_fee_variants_round_trip(
    fee_tier: int, maker_rate: str, taker_rate: str
) -> None:
    account = composition_request().account_profile
    assert account is not None
    band = replace(
        account.active_band,
        fee_tier=fee_tier,
        maker_commission_rate=maker_rate,
        taker_commission_rate=taker_rate,
    )
    book = replace(account.query.account_profile_book, bands=(band,))
    outcome = BinanceUsdmAccountProfileModel().resolve_account_profile(
        replace(account.query, account_profile_book=book)
    )
    assert outcome.result is not None
    original = composition_request(account_profile=outcome.result)

    decoded = _decode(_wire(original))

    assert canonical_bytes(decoded) == canonical_bytes(original)


class _RuntimeIteratorMapping(Mapping[str, object]):
    def __getitem__(self, key: str) -> object:
        raise AssertionError

    def __iter__(self) -> Iterator[str]:
        raise RuntimeError("private iterator detail")

    def __len__(self) -> int:
        return 1


class _RuntimeGetitemMapping(Mapping[str, object]):
    def __getitem__(self, key: str) -> object:
        raise RuntimeError("private getitem detail")

    def __iter__(self) -> Iterator[str]:
        yield "type"

    def __len__(self) -> int:
        return 1


class _NestedDuplicateMapping(Mapping[str, object]):
    def __getitem__(self, key: str) -> object:
        timeline = cast(dict[str, object], _wire()["timeline_window"])
        return timeline[key]

    def __iter__(self) -> Iterator[str]:
        yield "type"
        yield "type"

    def __len__(self) -> int:
        return 2


@pytest.mark.parametrize(
    "wire",
    (
        _DuplicateKeyMapping(),
        _RuntimeIteratorMapping(),
        _RuntimeGetitemMapping(),
    ),
)
def test_mapping_protocol_failures_are_redacted(wire: Mapping[str, object]) -> None:
    with pytest.raises(ValueError, match=f"^{_ERROR}$"):
        decode_binance_usdm_tradifi_profile_composition_request_v1(
            wire, "sha256:" + "0" * 64
        )


def test_nested_duplicate_mapping_and_wrong_expected_hash_are_rejected() -> None:
    wire = _wire()
    wire["timeline_window"] = _NestedDuplicateMapping()
    with pytest.raises(ValueError, match=f"^{_ERROR}$"):
        decode_binance_usdm_tradifi_profile_composition_request_v1(
            wire, "sha256:" + "0" * 64
        )

    wire = _wire()
    with pytest.raises(ValueError, match=f"^{_ERROR}$"):
        decode_binance_usdm_tradifi_profile_composition_request_v1(
            wire, "sha256:" + "0" * 64
        )


def test_hidden_metadata_revision_hash_is_rejected() -> None:
    wire = _wire()
    instrument = cast(dict[str, object], wire["instrument_metadata"])
    query = cast(dict[str, object], instrument["query"])
    revision_hashes = cast(list[object], query["revision_hashes"])
    revision_hashes.append("sha256:" + "99" * 32)

    with pytest.raises(ValueError, match=f"^{_ERROR}$"):
        _decode(wire)

@pytest.mark.parametrize("authority", ("raw_exact_strategy", "raw_exact_liquidation"))
def test_raw_strategy_and_liquidation_authorities_are_explicit_hash_bound(authority: str) -> None:
    raw = replace(composition_request(), **{authority: True})
    wire = _wire(raw)
    assert wire[authority] is True
    assert getattr(_decode(wire), authority) is True
    wire[authority] = False
    with pytest.raises(ValueError, match=f"^{_ERROR}$"):
        _decode(wire)
