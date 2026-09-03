"""Additive 000703 Tushare-dividend profile contract under ADR 0012."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Any, Mapping

from crypto_quant_domain import (
    InstrumentId,
    Money,
    PositionBalanceKey,
    Scale,
    VenueId,
    canonical_sha256,
)


_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_ACTION_SET_FIELDS = {
    "type",
    "schema_version",
    "instrument_id",
    "coverage_start_date",
    "coverage_end_date_exclusive",
    "source_snapshot_hash",
    "source_response_sha256",
    "actions",
    "tushare_dividend_assumed_correct",
    "zero_row_authoritative",
    "development_only",
    "decision_grade_eligible",
    "live_eligible",
    "deployment_authorized",
    "action_set_hash",
}
_ACTION_FIELDS = {
    "type",
    "schema_version",
    "action_id",
    "source_row_index",
    "source_row_sha256",
    "announcement_date",
    "record_date",
    "ex_date",
    "payment_date",
    "cash_per_share",
}


def _text(name: str, value: object) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(f"{name} must be canonical nonempty text")
    return value


def _hash(name: str, value: object) -> str:
    if type(value) is not str or _HASH.fullmatch(value) is None:
        raise ValueError(f"{name} must be canonical sha256")
    return value


def _date(name: str, value: object) -> str:
    result = _text(name, value)
    try:
        datetime.strptime(result, "%Y%m%d")
    except ValueError as error:
        raise ValueError(f"{name} must be a real YYYYMMDD date") from error
    return result


def _mapping(name: str, value: object, fields: set[str]) -> Mapping[str, object]:
    if type(value) is not dict or set(value) != fields:
        raise ValueError(f"{name} has an invalid canonical shape")
    return value


def _money(value: object) -> Money:
    data = _mapping("cash_per_share", value, {"type", "units", "scale", "currency"})
    if (
        data["type"] != "money"
        or type(data["units"]) is not int
        or type(data["scale"]) is not int
        or type(data["currency"]) is not str
    ):
        raise ValueError("cash_per_share has an invalid canonical shape")
    result = Money(data["units"], Scale(data["scale"]), data["currency"])
    if result.currency != "CNY" or result.scale != Scale(2) or result.units <= 0:
        raise ValueError("cash_per_share must be positive CNY-cent money")
    return result


def _instrument(value: object) -> InstrumentId:
    data = _mapping("instrument_id", value, {"type", "venue", "stable_key"})
    if data["type"] != "instrument_id" or data["venue"] != "xshe" or data["stable_key"] != "000703":
        raise ValueError("action set must cover xshe:000703")
    return InstrumentId(VenueId("xshe"), "000703")


@dataclass(frozen=True, slots=True)
class CnAShareDividendCashActionProfileV2:
    action_id: str
    source_row_index: int
    source_row_sha256: str
    announcement_date: str
    record_date: str
    ex_date: str
    payment_date: str
    cash_per_share: Money

    def __post_init__(self) -> None:
        _text("action_id", self.action_id)
        if type(self.source_row_index) is not int or self.source_row_index < 0:
            raise ValueError("source_row_index must be nonnegative int")
        _hash("source_row_sha256", self.source_row_sha256)
        for name in ("announcement_date", "record_date", "ex_date", "payment_date"):
            _date(name, getattr(self, name))
        if self.ex_date <= self.record_date or self.payment_date < self.ex_date:
            raise ValueError("cash action lifecycle dates are invalid")
        if type(self.cash_per_share) is not Money or self.cash_per_share.currency != "CNY" or self.cash_per_share.scale != Scale(2) or self.cash_per_share.units <= 0:
            raise ValueError("cash_per_share must be positive CNY-cent money")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_dividend_cash_action_profile_v2",
            "schema_version": 2,
            "action_id": self.action_id,
            "source_row_index": self.source_row_index,
            "source_row_sha256": self.source_row_sha256,
            "announcement_date": self.announcement_date,
            "record_date": self.record_date,
            "ex_date": self.ex_date,
            "payment_date": self.payment_date,
            "cash_per_share": self.cash_per_share,
        }


@dataclass(frozen=True, slots=True)
class CnAShareSimulatedRegisterPolicyV2:
    account_id: str
    position_key: PositionBalanceKey
    record_close_timezone: str
    record_close_local_time: str
    record_close_phase: tuple[int, str]

    def __post_init__(self) -> None:
        _text("account_id", self.account_id)
        if type(self.position_key) is not PositionBalanceKey:
            raise TypeError("position_key must be exact PositionBalanceKey")
        if self.position_key.account_id != self.account_id or self.position_key.instrument_id != InstrumentId(VenueId("xshe"), "000703"):
            raise ValueError("simulated register policy scope mismatch")
        if self.record_close_timezone != "Asia/Shanghai" or self.record_close_local_time != "15:00":
            raise ValueError("simulated register policy must use Shanghai 15:00")
        if self.record_close_phase != (100, "corporate_action_record"):
            raise ValueError("simulated register policy must use record-close phase")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_simulated_register_policy_v2",
            "schema_version": 2,
            "account_id": self.account_id,
            "position_key": self.position_key,
            "record_close_timezone": self.record_close_timezone,
            "record_close_local_time": self.record_close_local_time,
            "record_close_phase": self.record_close_phase,
        }


@dataclass(frozen=True, slots=True)
class CnAShareDividendProfileV2:
    instrument_id: InstrumentId
    coverage_start_date: str
    coverage_end_date_exclusive: str
    source_snapshot_hash: str
    source_response_sha256: str
    source_action_set_hash: str
    actions: tuple[CnAShareDividendCashActionProfileV2, ...]
    simulated_register_policy: CnAShareSimulatedRegisterPolicyV2
    tushare_dividend_assumed_correct: bool
    zero_row_authoritative: bool
    development_only: bool
    decision_grade_eligible: bool
    live_eligible: bool
    deployment_authorized: bool
    source_manifest: tuple[str, ...]
    profile_hash: str

    def __post_init__(self) -> None:
        if type(self.instrument_id) is not InstrumentId or self.instrument_id != InstrumentId(VenueId("xshe"), "000703"):
            raise ValueError("profile must cover xshe:000703")
        start = _date("coverage_start_date", self.coverage_start_date)
        end = _date("coverage_end_date_exclusive", self.coverage_end_date_exclusive)
        if start >= end:
            raise ValueError("profile coverage must be finite and nonempty")
        for name in ("source_snapshot_hash", "source_response_sha256", "source_action_set_hash"):
            _hash(name, getattr(self, name))
        if type(self.actions) is not tuple or not all(type(value) is CnAShareDividendCashActionProfileV2 for value in self.actions):
            raise TypeError("actions must contain exact CnAShareDividendCashActionProfileV2")
        if self.actions != tuple(sorted(self.actions, key=lambda value: (value.record_date, value.action_id))):
            raise ValueError("actions must be canonical record-date ordered")
        if len({value.action_id for value in self.actions}) != len(self.actions):
            raise ValueError("actions must have unique identities")
        if any(not (start <= value.record_date < end) for value in self.actions):
            raise ValueError("action is outside profile coverage")
        if type(self.simulated_register_policy) is not CnAShareSimulatedRegisterPolicyV2:
            raise TypeError("simulated_register_policy must be exact V2 policy")
        if (
            type(self.tushare_dividend_assumed_correct) is not bool
            or type(self.zero_row_authoritative) is not bool
            or type(self.development_only) is not bool
            or type(self.decision_grade_eligible) is not bool
            or type(self.live_eligible) is not bool
            or type(self.deployment_authorized) is not bool
            or not self.tushare_dividend_assumed_correct
            or not self.zero_row_authoritative
            or not self.development_only
            or self.decision_grade_eligible
            or self.live_eligible
            or self.deployment_authorized
        ):
            raise ValueError("profile must retain the approved development convention")
        if type(self.source_manifest) is not tuple or self.source_manifest != tuple(sorted(set(self.source_manifest))):
            raise ValueError("source_manifest must be canonical unique tuple")
        if self.source_manifest != tuple(sorted((self.source_snapshot_hash, self.source_response_sha256, self.source_action_set_hash))):
            raise ValueError("source_manifest must exact-cover action identities")
        if self.profile_hash != canonical_sha256(self._body()):
            raise ValueError("profile identity mismatch")

    def _body(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_dividend_profile_v2",
            "schema_version": 2,
            "instrument_id": self.instrument_id,
            "coverage_start_date": self.coverage_start_date,
            "coverage_end_date_exclusive": self.coverage_end_date_exclusive,
            "source_snapshot_hash": self.source_snapshot_hash,
            "source_response_sha256": self.source_response_sha256,
            "source_action_set_hash": self.source_action_set_hash,
            "actions": self.actions,
            "simulated_register_policy": self.simulated_register_policy,
            "tushare_dividend_assumed_correct": self.tushare_dividend_assumed_correct,
            "zero_row_authoritative": self.zero_row_authoritative,
            "development_only": self.development_only,
            "decision_grade_eligible": self.decision_grade_eligible,
            "live_eligible": self.live_eligible,
            "deployment_authorized": self.deployment_authorized,
            "source_manifest": self.source_manifest,
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "profile_hash": self.profile_hash}


def _action(value: object) -> CnAShareDividendCashActionProfileV2:
    data = _mapping("action", value, _ACTION_FIELDS)
    if data["type"] != "tushare_000703_dividend_cash_action_v2" or data["schema_version"] != 2:
        raise ValueError("action has an invalid canonical type")
    return CnAShareDividendCashActionProfileV2(
        _text("action_id", data["action_id"]),
        data["source_row_index"],
        _hash("source_row_sha256", data["source_row_sha256"]),
        _date("announcement_date", data["announcement_date"]),
        _date("record_date", data["record_date"]),
        _date("ex_date", data["ex_date"]),
        _date("payment_date", data["payment_date"]),
        _money(data["cash_per_share"]),
    )


def compose_tushare_000703_dividend_profile_v2(
    action_set_payload: object,
    account_id: str,
    /,
) -> CnAShareDividendProfileV2:
    data = _mapping("action_set_payload", action_set_payload, _ACTION_SET_FIELDS)
    body = dict(data)
    action_set_hash = body.pop("action_set_hash")
    if (
        body["type"] != "tushare_000703_dividend_action_set_v2"
        or body["schema_version"] != 2
        or _hash("action_set_hash", action_set_hash) != canonical_sha256(body)
    ):
        raise ValueError("action_set_payload identity mismatch")
    instrument = _instrument(data["instrument_id"])
    start = _date("coverage_start_date", data["coverage_start_date"])
    end = _date("coverage_end_date_exclusive", data["coverage_end_date_exclusive"])
    actions_data = data["actions"]
    if type(actions_data) is not list:
        raise ValueError("action_set_payload actions must be a list")
    actions = tuple(_action(value) for value in actions_data)
    policy = CnAShareSimulatedRegisterPolicyV2(
        _text("account_id", account_id),
        PositionBalanceKey(
            _text("account_id", account_id), instrument.venue, instrument
        ),
        "Asia/Shanghai",
        "15:00",
        (100, "corporate_action_record"),
    )
    snapshot_hash = _hash("source_snapshot_hash", data["source_snapshot_hash"])
    response_hash = _hash("source_response_sha256", data["source_response_sha256"])
    manifest = tuple(sorted((snapshot_hash, response_hash, action_set_hash)))
    provisional = CnAShareDividendProfileV2.__new__(CnAShareDividendProfileV2)
    for name, value in (
        ("instrument_id", instrument),
        ("coverage_start_date", start),
        ("coverage_end_date_exclusive", end),
        ("source_snapshot_hash", snapshot_hash),
        ("source_response_sha256", response_hash),
        ("source_action_set_hash", action_set_hash),
        ("actions", actions),
        ("simulated_register_policy", policy),
        ("tushare_dividend_assumed_correct", data["tushare_dividend_assumed_correct"]),
        ("zero_row_authoritative", data["zero_row_authoritative"]),
        ("development_only", data["development_only"]),
        ("decision_grade_eligible", data["decision_grade_eligible"]),
        ("live_eligible", data["live_eligible"]),
        ("deployment_authorized", data["deployment_authorized"]),
        ("source_manifest", manifest),
    ):
        object.__setattr__(provisional, name, value)
    object.__setattr__(provisional, "profile_hash", canonical_sha256(provisional._body()))
    provisional.__post_init__()
    return provisional
