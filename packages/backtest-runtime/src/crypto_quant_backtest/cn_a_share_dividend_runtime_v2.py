"""Runtime-only simulated-register projection for ADR 0012 dividend actions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from crypto_quant_domain import (
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    canonical_sha256,
)
from crypto_quant_trading import LedgerState
from crypto_quant_trading.profiles.cn_a_share.corporate_actions import (
    CnAShareCorporateActionSourceRef,
    CnAShareRegisteredPositionSnapshot,
)

from .cn_a_share_dividend_profile_v2 import CnAShareDividendProfileV2


_SHANGHAI = ZoneInfo("Asia/Shanghai")
_SOURCE_KEY = "tushare.000703.simulated-register.v2"
_REGISTER_SERIES_ID = "tushare.000703.simulated-ledger-register.v2"


def _action(profile: CnAShareDividendProfileV2, action_id: str) -> tuple[int, object]:
    if type(action_id) is not str:
        raise TypeError("action_id must be str")
    matches = tuple(
        (index, value)
        for index, value in enumerate(profile.actions)
        if value.action_id == action_id
    )
    if len(matches) != 1:
        raise ValueError("action_id must identify exactly one profile action")
    return matches[0]


def _record_close(
    profile: CnAShareDividendProfileV2, action_id: str
) -> SimulationInstant:
    index, action = _action(profile, action_id)
    try:
        local = datetime.strptime(action.record_date, "%Y%m%d").replace(
            hour=15,
            tzinfo=_SHANGHAI,
        )
    except ValueError as error:
        raise ValueError("action record_date is invalid") from error
    phase_rank, phase_code = profile.simulated_register_policy.record_close_phase
    return SimulationInstant(
        UtcInstant.from_datetime(local),
        TimelinePhase(phase_rank, phase_code),
        SourceSequence(index),
    )


def _identity(
    profile: CnAShareDividendProfileV2,
    action_id: str,
    record_close_at: SimulationInstant,
    ledger_state: LedgerState,
) -> str:
    return canonical_sha256(
        {
            "type": "cn_a_share_dividend_simulated_register_projection",
            "schema_version": 2,
            "profile_hash": profile.profile_hash,
            "action_id": action_id,
            "record_close_at": record_close_at,
            "ledger_state_hash": ledger_state.state_hash,
            "registered_quantity": ledger_state.position_quantity(
                profile.simulated_register_policy.position_key
            ),
        }
    )


def _snapshot(
    profile: CnAShareDividendProfileV2,
    action_id: str,
    record_close_at: SimulationInstant,
    ledger_state: LedgerState,
) -> CnAShareRegisteredPositionSnapshot:
    policy = profile.simulated_register_policy
    identity = _identity(profile, action_id, record_close_at, ledger_state)
    source = CnAShareCorporateActionSourceRef(_SOURCE_KEY, identity)
    return CnAShareRegisteredPositionSnapshot(
        f"tushare.000703.simulated-register:{identity}",
        _REGISTER_SERIES_ID,
        f"tushare.000703.simulated-register-revision:{identity}",
        None,
        policy.account_id,
        policy.position_key,
        record_close_at,
        record_close_at,
        ledger_state.position_quantity(policy.position_key),
        source,
    )


@dataclass(frozen=True, slots=True)
class CnAShareDividendRegisterProjectionV2:
    profile: CnAShareDividendProfileV2
    action_id: str
    record_close_at: SimulationInstant
    ledger_state: LedgerState
    snapshot: CnAShareRegisteredPositionSnapshot

    def __post_init__(self) -> None:
        if type(self.profile) is not CnAShareDividendProfileV2:
            raise TypeError("profile must be exact CnAShareDividendProfileV2")
        if type(self.record_close_at) is not SimulationInstant:
            raise TypeError("record_close_at must be exact SimulationInstant")
        if type(self.ledger_state) is not LedgerState:
            raise TypeError("ledger_state must be exact LedgerState")
        if type(self.snapshot) is not CnAShareRegisteredPositionSnapshot:
            raise TypeError("snapshot must be exact CnAShareRegisteredPositionSnapshot")
        if self.record_close_at != _record_close(self.profile, self.action_id):
            raise ValueError("record_close_at does not match profile action boundary")
        expected = _snapshot(
            self.profile,
            self.action_id,
            self.record_close_at,
            self.ledger_state,
        )
        if self.snapshot != expected:
            raise ValueError("simulated register snapshot identity mismatch")

    @property
    def ledger_state_hash(self) -> str:
        return self.ledger_state.state_hash

    @property
    def projection_hash(self) -> str:
        return _identity(
            self.profile,
            self.action_id,
            self.record_close_at,
            self.ledger_state,
        )

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_dividend_register_projection_v2",
            "schema_version": 2,
            "profile_hash": self.profile.profile_hash,
            "action_id": self.action_id,
            "record_close_at": self.record_close_at,
            "ledger_state_hash": self.ledger_state_hash,
            "snapshot": self.snapshot,
            "projection_hash": self.projection_hash,
        }


def project_tushare_000703_dividend_register_v2(
    profile: CnAShareDividendProfileV2,
    action_id: str,
    record_close_at: SimulationInstant,
    ledger_state: LedgerState,
    /,
) -> CnAShareDividendRegisterProjectionV2:
    if type(profile) is not CnAShareDividendProfileV2:
        raise TypeError("profile must be exact CnAShareDividendProfileV2")
    if type(record_close_at) is not SimulationInstant:
        raise TypeError("record_close_at must be exact SimulationInstant")
    if type(ledger_state) is not LedgerState:
        raise TypeError("ledger_state must be exact LedgerState")
    return CnAShareDividendRegisterProjectionV2(
        profile,
        action_id,
        record_close_at,
        ledger_state,
        _snapshot(profile, action_id, record_close_at, ledger_state),
    )
