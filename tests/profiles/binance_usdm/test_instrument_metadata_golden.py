from __future__ import annotations

import json
from pathlib import Path

from crypto_quant_domain import UtcInstant, canonical_bytes, canonical_sha256
from crypto_quant_trading.profiles.binance_usdm import BinanceUsdmInstrumentModel
from tests.profiles.binance_usdm._fixtures import (
    DELIST_AT,
    ONBOARD_AT,
    RENAME_AT,
    query,
    revision,
)


ROOT = Path(__file__).resolve().parents[3]
SOURCE_FIXTURE = (
    ROOT / "tests/fixtures/profiles/binance-usdm-exchange-info-revisions-v1.json"
)
GOLDEN_FIXTURE = (
    ROOT / "tests/fixtures/profiles/binance-usdm-instrument-metadata-v1.json"
)


def _decode(value: object) -> object:
    try:
        return json.loads(canonical_bytes(value))
    except json.JSONDecodeError as error:
        raise AssertionError("canonical payload did not decode") from error


def _read(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"cannot read canonical fixture: {path.name}") from error


def build_cases() -> dict[str, object]:
    first = revision()
    renamed = revision(
        "btc-v2",
        supersedes_revision_id=first.revision_id,
        symbol="XBTUSDT",
        pair="XBTUSDT",
        effective_from=RENAME_AT,
    )
    delisted = revision(
        "btc-v2",
        supersedes_revision_id=first.revision_id,
        delivery_at=DELIST_AT,
        effective_from=RENAME_AT,
    )
    corrected = revision(
        "btc-v2",
        supersedes_revision_id=first.revision_id,
        onboard_at=UtcInstant(ONBOARD_AT.epoch_nanoseconds - 100),
        effective_from=RENAME_AT,
    )
    pending = revision(
        "btc-v2",
        supersedes_revision_id=first.revision_id,
        status="TRADING_HALT",
        effective_from=RENAME_AT,
    )
    return {
        "open_ended": query(
            first,
            effective_at=UtcInstant(ONBOARD_AT.epoch_nanoseconds + 10),
            captured_at=UtcInstant(ONBOARD_AT.epoch_nanoseconds + 20),
        ),
        "renamed": query(first, renamed),
        "finite_delist": query(
            first,
            delisted,
            effective_at=UtcInstant(DELIST_AT.epoch_nanoseconds - 1),
            captured_at=UtcInstant(RENAME_AT.epoch_nanoseconds + 20),
        ),
        "corrected_onboard_hidden": query(
            first,
            corrected,
            effective_at=UtcInstant(ONBOARD_AT.epoch_nanoseconds - 50),
            captured_at=RENAME_AT,
        ),
        "corrected_onboard_visible": query(
            first,
            corrected,
            effective_at=UtcInstant(ONBOARD_AT.epoch_nanoseconds - 50),
            captured_at=UtcInstant(RENAME_AT.epoch_nanoseconds + 2),
        ),
        "separate_lineage": query(
            revision(stable_instrument_key="renamed-btc-usdt"),
            stable_instrument_key="renamed-btc-usdt",
            effective_at=UtcInstant(ONBOARD_AT.epoch_nanoseconds + 10),
            captured_at=UtcInstant(ONBOARD_AT.epoch_nanoseconds + 20),
        ),
        "known_nontrading": query(first, pending),
        "pre_listing": query(
            first,
            effective_at=UtcInstant(ONBOARD_AT.epoch_nanoseconds - 1),
        ),
        "post_delisting": query(
            first,
            delisted,
            effective_at=DELIST_AT,
            captured_at=UtcInstant(DELIST_AT.epoch_nanoseconds + 2),
        ),
        "unsupported_type": query(revision(contract_type="CURRENT_QUARTER")),
        "unsupported_status": query(revision(status="UNKNOWN")),
        "invalid_currency": query(
            revision(quote_asset="USDC", margin_asset="USDT")
        ),
    }


def build_source_actual() -> object:
    revisions = {
        name: value.revisions
        for name, value in build_cases().items()
        if value.revisions
    }
    return _decode(
        {
            "fixture_id": "binance-usdm-exchange-info-revisions-v1",
            "provider": "binance_usdm",
            "source_contract": "frozen-normalized-exchange-info-revisions",
            "cases": revisions,
        }
    )


def build_golden_actual() -> object:
    model = BinanceUsdmInstrumentModel()
    cases = build_cases()
    outcomes = {name: model.resolve_instrument(value) for name, value in cases.items()}
    return _decode(
        {
            "fixture_id": "binance-usdm-instrument-metadata-v1",
            "allowed_grade": "development",
            "deployment_authorized": False,
            "component_ref": model.component_ref,
            "queries": cases,
            "outcomes": outcomes,
            "outcome_hashes": {
                name: canonical_sha256(value) for name, value in outcomes.items()
            },
            "limitations": (
                "offline-frozen-source-only",
                "no-tick-step-notional-margin-fee-funding-or-account-mode",
                "no-current-api-history-fallback",
                "no-live-or-deployment-authorization",
            ),
        }
    )


def test_normalized_source_revisions_match_static_fixture() -> None:
    assert build_source_actual() == _read(SOURCE_FIXTURE)


def test_resolutions_and_failures_match_static_golden() -> None:
    assert build_golden_actual() == _read(GOLDEN_FIXTURE)
