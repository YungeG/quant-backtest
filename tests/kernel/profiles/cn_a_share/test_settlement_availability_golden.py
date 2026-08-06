from __future__ import annotations

import json
from pathlib import Path

from crypto_quant_domain import OrderSide, canonical_bytes
from crypto_quant_trading import SettlementBookState
from tests.kernel.profiles.cn_a_share._fixtures import (
    settlement_journey,
    settlement_model,
    settlement_query,
)


ROOT = Path(__file__).resolve().parents[4]
FIXTURE = (
    ROOT
    / "tests/fixtures/kernel/profiles/cn_a_share/settlement-availability-v1.json"
)


def _read_json(path: Path) -> dict[str, object]:
    try:
        decoded = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"cannot read canonical JSON: {path.name}") from error
    assert isinstance(decoded, dict)
    return decoded


def _settlement_state_evidence(
    state: SettlementBookState,
) -> dict[str, object]:
    return {
        "cursor": state.cursor,
        "pending_ids": tuple(
            value.obligation.settlement_obligation_id.value
            for value in state.pending_obligations
        ),
        "applied_ids": tuple(
            value.obligation.settlement_obligation_id.value
            for value in state.applied_obligations
        ),
        "state_hash": state.state_hash,
    }


def _venue_evidence(venue: str) -> dict[str, object]:
    journey = settlement_journey(venue)
    model = settlement_model(venue)
    return {
        "calendar_ref": {
            "venue_id": model.calendar.venue_id,
            "calendar_id": model.calendar.calendar_id,
            "calendar_hash": model.calendar.calendar_hash,
        },
        "component_ref": model.component_ref,
        "queries": journey.queries,
        "resolutions": journey.resolutions,
        "journal": {
            "entries": journey.journal.entries,
            "journal_hash": journey.journal.journal_hash,
        },
        "ledger": journey.ledger,
        "rules": journey.rules,
        "reservations": journey.reservations,
        "settlement_book": {
            "account_id": journey.forward_book.account_id,
            "obligations": journey.forward_book.obligations,
            "events": journey.forward_book.events,
            "book_hash": journey.forward_book.book_hash,
        },
        "states": {
            "position_boundary_before": _settlement_state_evidence(
                journey.position_boundary_before
            ),
            "position_boundary_after": _settlement_state_evidence(
                journey.position_boundary_after
            ),
            "cash_boundary_before": _settlement_state_evidence(
                journey.cash_boundary_before
            ),
            "cash_boundary_after": _settlement_state_evidence(
                journey.cash_boundary_after
            ),
            "full": _settlement_state_evidence(journey.full_state),
            "resumed": _settlement_state_evidence(journey.resumed_state),
        },
        "availability": {
            "before": journey.before_availability,
            "position_available": journey.position_available,
            "cash_available": journey.cash_available,
        },
        "hashes": {
            "journal": journey.journal.journal_hash,
            "ledger": journey.ledger.state_hash,
            "rules": journey.rules.rules_hash,
            "reservations": journey.reservations.state_hash,
            "settlement_book": journey.forward_book.book_hash,
            "settlement_state": journey.full_state.state_hash,
            "before_availability": journey.before_availability.state_hash,
            "position_available": journey.position_available.state_hash,
            "cash_available": journey.cash_available.state_hash,
        },
    }


def build_actual() -> dict[str, object]:
    xshg = settlement_journey("xshg")
    xshe = settlement_journey("xshe")
    failure_queries = {
        "unsupported_venue": settlement_query(OrderSide.BUY, venue="xshe"),
        "calendar_coverage_missing": settlement_query(
            OrderSide.BUY,
            local_date=xshg.resolutions[0].next_trading_date.value,
        ),
        "trade_time_not_open": settlement_query(OrderSide.BUY, hour=12),
    }
    failures = {
        key: settlement_model().resolve_settlement(query)
        for key, query in failure_queries.items()
    }
    normalized_xshg = tuple(
        obligation.units
        for resolution in xshg.resolutions
        for obligation in resolution.obligations
    )
    normalized_xshe = tuple(
        obligation.units
        for resolution in xshe.resolutions
        for obligation in resolution.obligations
    )
    payload = {
        "fixture_id": "cn-a-share-settlement-availability-v1",
        "qualification": {
            "grade": "development",
            "current_live_calendar_claimed": False,
            "deployment_authorized": False,
        },
        "caller_preconditions": (
            "ordinary-rmb-a-share",
            "cash-account",
            "authoritative-journal-prefix-includes-fill-entries",
        ),
        "system_conventions": {
            "buy_position_availability": "next-trading-date-local-00:00",
            "sell_cash_withdrawal": "next-trading-date-local-16:00",
            "negative_delivery": "fill-execution-time",
        },
        "xshg": _venue_evidence("xshg"),
        "xshe": _venue_evidence("xshe"),
        "failures": failures,
        "cross_venue": {
            "normalized_obligation_units_equal": normalized_xshg == normalized_xshe,
            "settlement_book_hashes_differ": (
                xshg.forward_book.book_hash != xshe.forward_book.book_hash
            ),
            "rules_hashes_differ": xshg.rules.rules_hash != xshe.rules.rules_hash,
            "availability_hashes_differ": (
                xshg.before_availability.state_hash
                != xshe.before_availability.state_hash
            ),
        },
    }
    try:
        decoded = json.loads(canonical_bytes(payload))
    except json.JSONDecodeError as error:
        raise AssertionError("canonical fixture did not decode") from error
    assert isinstance(decoded, dict)
    return decoded


def test_settlement_availability_matches_static_golden() -> None:
    assert build_actual() == _read_json(FIXTURE)
