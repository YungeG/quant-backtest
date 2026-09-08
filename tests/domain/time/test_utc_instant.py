from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from crypto_quant_domain import UtcInstant


def test_aware_datetime_converts_without_float_timestamp() -> None:
    local = datetime(
        1970,
        1,
        1,
        7,
        59,
        59,
        123456,
        tzinfo=timezone(timedelta(hours=8)),
    )

    instant = UtcInstant.from_datetime(local)

    assert instant.epoch_nanoseconds == -876544000
    assert instant.to_datetime() == local.astimezone(timezone.utc)


def test_naive_datetime_is_rejected() -> None:
    with pytest.raises(ValueError, match="naive"):
        UtcInstant.from_datetime(datetime(2024, 1, 1))


def test_submicrosecond_datetime_conversion_fails_closed() -> None:
    instant = UtcInstant(epoch_nanoseconds=1)

    with pytest.raises(ValueError, match="microsecond"):
        instant.to_datetime()


def test_utc_instant_canonical_form_is_epoch_nanoseconds_only() -> None:
    instant = UtcInstant(epoch_nanoseconds=1730611800000000001)

    assert instant.to_canonical_dict() == {
        "type": "utc_instant",
        "epoch_nanoseconds": 1730611800000000001,
    }


def test_epoch_nanoseconds_reject_bool_and_float() -> None:
    with pytest.raises(TypeError, match="integer"):
        UtcInstant(epoch_nanoseconds=True)
    with pytest.raises(TypeError, match="integer"):
        UtcInstant(epoch_nanoseconds=1.0)  # type: ignore[arg-type]
