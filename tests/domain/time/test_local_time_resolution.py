from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from crypto_quant_domain import LocalTimeDisambiguation, resolve_local_datetime


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests/fixtures/domain/time-dst-boundaries-v1.json"


def fixture() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_ambiguous_local_time_requires_explicit_earlier_or_later() -> None:
    case = fixture()
    local = datetime.fromisoformat(str(case["ambiguous_local"]))
    zone = ZoneInfo(str(case["zone"]))

    earlier = resolve_local_datetime(
        local, zone, LocalTimeDisambiguation.EARLIER
    )
    later = resolve_local_datetime(local, zone, LocalTimeDisambiguation.LATER)

    assert earlier.epoch_nanoseconds == case[
        "ambiguous_earlier_epoch_nanoseconds"
    ]
    assert later.epoch_nanoseconds == case["ambiguous_later_epoch_nanoseconds"]
    with pytest.raises(ValueError, match="ambiguous"):
        resolve_local_datetime(local, zone, LocalTimeDisambiguation.REJECT)


def test_nonexistent_local_time_is_always_rejected() -> None:
    case = fixture()
    local = datetime.fromisoformat(str(case["nonexistent_local"]))
    zone = ZoneInfo(str(case["zone"]))

    for policy in LocalTimeDisambiguation:
        with pytest.raises(ValueError, match="nonexistent"):
            resolve_local_datetime(local, zone, policy)


def test_local_resolver_rejects_aware_input() -> None:
    with pytest.raises(ValueError, match="naive local"):
        resolve_local_datetime(
            datetime.fromisoformat("2024-01-01T00:00:00+00:00"),
            ZoneInfo("UTC"),
            LocalTimeDisambiguation.REJECT,
        )
