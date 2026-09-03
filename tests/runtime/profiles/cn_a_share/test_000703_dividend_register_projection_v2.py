from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from crypto_quant_backtest.cn_a_share_dividend_profile_v2 import (
    compose_tushare_000703_dividend_profile_v2,
)
from crypto_quant_bundle_builder.tushare_000703_dividend_action_set_v2 import (
    map_tushare_000703_dividend_action_set_v2,
)
from crypto_quant_domain import (
    InstrumentId,
    PositionBalance,
    PositionBalanceKey,
    Quantity,
    Scale,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    VenueId,
    canonical_bytes,
)
from crypto_quant_trading import (
    AccountingJournal,
    LedgerBalanceRegistration,
    LedgerSchema,
    LedgerState,
)
from crypto_quant_trading.profiles.cn_a_share.corporate_actions import (
    CnAShareRegisteredPositionSnapshot,
)
from crypto_quant_backtest.cn_a_share_dividend_runtime_v2 import (
    CnAShareDividendRegisterProjectionV2,
    project_tushare_000703_dividend_register_v2,
)


ROOT = Path(__file__).resolve().parents[4]
EVIDENCE = ROOT / "evidence/tushare-000703-dividend-authority-v1"
ACCOUNT = "account:000703-development"
INSTRUMENT = InstrumentId(VenueId("xshe"), "000703")
POSITION_KEY = PositionBalanceKey(ACCOUNT, VenueId("xshe"), INSTRUMENT)
SHANGHAI = ZoneInfo("Asia/Shanghai")


def _profile():
    action_set = map_tushare_000703_dividend_action_set_v2(
        (EVIDENCE / "acquisition-receipt.json").read_bytes(),
        (EVIDENCE / "response/dividend.json").read_bytes(),
        INSTRUMENT,
    )
    return compose_tushare_000703_dividend_profile_v2(
        json.loads(canonical_bytes(action_set)), ACCOUNT
    )


def _ledger(quantity: int) -> LedgerState:
    schema = LedgerSchema((LedgerBalanceRegistration(POSITION_KEY, Scale(0)),))
    positions = ()
    if quantity:
        positions = (
            PositionBalance(
                POSITION_KEY,
                Quantity(quantity, Scale(0), str(INSTRUMENT)),
                (),
            ),
        )
    return LedgerState(
        schema=schema,
        cursor=AccountingJournal.empty().cursor_at(0),
        cash_balances=(),
        position_balances=positions,
        realized_pnl=(),
        fees=(),
        financing=(),
    )


def _record_close(record_date: str, sequence: int) -> SimulationInstant:
    instant = UtcInstant.from_datetime(
        datetime.strptime(record_date, "%Y%m%d").replace(
            hour=15, tzinfo=SHANGHAI
        )
    )
    return SimulationInstant(
        instant,
        TimelinePhase(100, "corporate_action_record"),
        SourceSequence(sequence),
    )


def test_runtime_projection_derives_registered_quantity_from_current_ledger() -> None:
    profile = _profile()
    action = profile.actions[0]
    projection = project_tushare_000703_dividend_register_v2(
        profile,
        action.action_id,
        _record_close(action.record_date, 0),
        _ledger(1_200),
    )
    assert type(projection) is CnAShareDividendRegisterProjectionV2
    assert type(projection.snapshot) is CnAShareRegisteredPositionSnapshot
    assert projection.snapshot.registered_quantity == Quantity(1_200, Scale(0), str(INSTRUMENT))
    assert projection.snapshot.eligibility_instant == projection.snapshot.available_at
    assert projection.snapshot.eligibility_instant == _record_close(action.record_date, 0)
    assert projection.snapshot.source_ref.source_hash == projection.projection_hash


def test_zero_and_nonzero_ledgers_produce_distinct_register_snapshots() -> None:
    profile = _profile()
    action = profile.actions[1]
    zero = project_tushare_000703_dividend_register_v2(
        profile, action.action_id, _record_close(action.record_date, 1), _ledger(0)
    )
    held = project_tushare_000703_dividend_register_v2(
        profile, action.action_id, _record_close(action.record_date, 1), _ledger(75)
    )
    assert zero.snapshot.registered_quantity.units == 0
    assert held.snapshot.registered_quantity.units == 75
    assert zero.ledger_state_hash != held.ledger_state_hash
    assert zero.projection_hash != held.projection_hash


@pytest.mark.parametrize("case", ("missing", "wrong_sequence", "wrong_date"))
def test_unknown_action_or_noncanonical_record_boundary_fails_closed(case: str) -> None:
    profile = _profile()
    action = profile.actions[0]
    action_id = "missing" if case == "missing" else action.action_id
    record_close = (
        _record_close(action.record_date, 1)
        if case == "wrong_sequence"
        else _record_close("20240626", 0)
        if case == "wrong_date"
        else _record_close(action.record_date, 0)
    )
    with pytest.raises(ValueError):
        project_tushare_000703_dividend_register_v2(
            profile, action_id, record_close, _ledger(1)
        )
