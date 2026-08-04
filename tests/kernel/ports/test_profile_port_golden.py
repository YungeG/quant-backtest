from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from crypto_quant_domain import (
    CanonicalizationError,
    InstrumentId,
    SessionId,
    TradingDate,
    UtcInstant,
    VenueId,
    canonical_bytes,
)
from crypto_quant_trading import (
    ProfileComponentRef,
    ProfilePortOutcome,
    ProfilePortType,
)


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests/fixtures/kernel/kernel-profile-ports-v1.json"


@dataclass(frozen=True)
class SessionQuery:
    instant: UtcInstant
    instrument_id: InstrumentId

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "session_query",
            "instant": self.instant,
            "instrument_id": self.instrument_id,
        }


@dataclass(frozen=True)
class SessionResolution:
    session_id: SessionId
    trading_date: TradingDate

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "session_resolution",
            "session_id": self.session_id,
            "trading_date": self.trading_date,
        }


@dataclass(frozen=True)
class SessionFailure:
    failure_kind: str

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "session_failure", "failure_kind": self.failure_kind}


def test_kernel_profile_port_contracts_match_golden_fixture() -> None:
    try:
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"invalid golden fixture: {FIXTURE}") from error
    request = SessionQuery(
        instant=UtcInstant(1_700_000_000_000_000_000),
        instrument_id=InstrumentId(VenueId("test-venue"), "asset-1"),
    )
    reference = ProfileComponentRef(
        port_type=ProfilePortType.SESSION_MODEL,
        component_key="test.session_model.v1",
        component_version=1,
        component_digest="sha256:" + "ab" * 32,
    )
    result = SessionResolution(
        session_id=SessionId("test-venue", "2023-11-15.regular"),
        trading_date=TradingDate("test-venue", date(2023, 11, 15)),
    )

    assert fixture["fixture_id"] == "kernel-profile-ports-v1"
    assert fixture["port_types"] == [value.value for value in ProfilePortType]
    success = ProfilePortOutcome.for_result(reference, request, result)
    failure = ProfilePortOutcome.for_failure(
        reference, request, SessionFailure("no_session")
    )
    try:
        actual_success = json.loads(canonical_bytes(success))
        actual_failure = json.loads(canonical_bytes(failure))
    except (CanonicalizationError, json.JSONDecodeError) as error:
        raise AssertionError("profile port outcome is not canonical JSON") from error
    assert actual_success == fixture["success_outcome"]
    assert actual_failure == fixture["failure_outcome"]
