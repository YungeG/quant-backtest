from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from crypto_quant_domain import VenueId, canonical_bytes
from crypto_quant_trading.profiles.cn_a_share import CnAShareCashSessionModel
from tests.kernel.profiles.cn_a_share._fixtures import frozen_calendar, local_query


ROOT = Path(__file__).resolve().parents[4]
FIXTURE = (
    ROOT
    / "tests/fixtures/kernel/profiles/cn_a_share/calendar-session-v1.json"
)


def _read_json(path: Path) -> dict[str, object]:
    try:
        decoded = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"cannot read canonical JSON: {path}") from error
    assert isinstance(decoded, dict)
    return decoded


def build_actual() -> dict[str, object]:
    shanghai_calendar = frozen_calendar("xshg")
    shenzhen_calendar = frozen_calendar("xshe")
    shanghai = CnAShareCashSessionModel(shanghai_calendar)
    shenzhen = CnAShareCashSessionModel(shenzhen_calendar)
    phase_queries = (
        ("pre_open", 0, 0),
        ("opening_call", 9, 15),
        ("opening_pause", 9, 25),
        ("continuous_morning", 9, 30),
        ("lunch_break", 11, 30),
        ("continuous_afternoon", 13, 0),
        ("closing_call", 14, 57),
        ("post_close", 15, 0),
    )
    phases = {
        key: shanghai.resolve_session(
            local_query(date(2024, 2, 19), hour, minute)
        )
        for key, hour, minute in phase_queries
    }
    pre_open_utc_previous_date = shanghai.resolve_session(
        local_query(date(2024, 2, 19), 0, 30)
    )
    holiday = shanghai.resolve_session(
        local_query(date(2024, 2, 10), 10, 0)
    )
    weekend = shanghai.resolve_session(
        local_query(date(2024, 2, 18), 10, 0)
    )
    coverage_failure = shanghai.resolve_session(
        local_query(date(2024, 2, 20), 10, 0)
    )
    unsupported_venue = shanghai.resolve_session(
        local_query(date(2024, 2, 19), 10, 0, venue="xbse")
    )
    try:
        decoded = json.loads(
            canonical_bytes(
                {
                    "fixture_id": "cn-a-share-calendar-session-v1",
                    "qualification": {
                        "allowed_grade": "development",
                        "current_live": False,
                        "decision_grade": False,
                    },
                    "calendars": {
                        "xshg": {
                            "calendar": shanghai_calendar,
                            "calendar_hash": shanghai_calendar.calendar_hash,
                            "component_ref": shanghai.component_ref,
                        },
                        "xshe": {
                            "calendar": shenzhen_calendar,
                            "calendar_hash": shenzhen_calendar.calendar_hash,
                            "component_ref": shenzhen.component_ref,
                        },
                    },
                    "phase_boundaries": phases,
                    "pre_open_utc_previous_date": pre_open_utc_previous_date,
                    "known_closures": {
                        "frozen_holiday": holiday,
                        "weekend": weekend,
                    },
                    "failures": {
                        "coverage_missing": coverage_failure,
                        "unsupported_venue": unsupported_venue,
                    },
                    "repeat_resolution": shanghai.resolve_session(
                        local_query(date(2024, 2, 19), 9, 15)
                    ),
                    "query_venue_identity": VenueId("xshg"),
                }
            )
        )
    except json.JSONDecodeError as error:
        raise AssertionError("canonical fixture did not decode") from error
    assert isinstance(decoded, dict)
    return decoded


def test_calendar_session_matches_static_golden() -> None:
    assert build_actual() == _read_json(FIXTURE)
