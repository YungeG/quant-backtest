"""Pure canonical action-set mapping for retained 000703 Tushare dividends."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
import re

from crypto_quant_domain import InstrumentId, Money, Scale, canonical_sha256

from .source_snapshots import RawSourceMember, SourceSnapshotProvenance, freeze_source_snapshot


_FIELDS = (
    "ts_code", "end_date", "ann_date", "div_proc", "stk_div", "stk_bo_rate",
    "stk_co_rate", "cash_div", "cash_div_tax", "record_date", "ex_date",
    "pay_date", "div_listdate", "imp_ann_date",
)
_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_TS_CODE = "000703.SZ"
_COVERAGE_START = "20240102"
_COVERAGE_END_EXCLUSIVE = "20260901"
_MEMBER_KEY = "response/dividend.json"
_CNY_SCALE = Scale(2)


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()


def _raw_hash(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _row_hash(value: object) -> str:
    return _raw_hash(_json_bytes(value))


def _text(name: str, value: object) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(f"{name} must be canonical non-empty text")
    return value


def _source_hash(name: str, value: object) -> str:
    if type(value) is not str or _HASH.fullmatch(value) is None:
        raise ValueError(f"{name} must be canonical sha256")
    return value


def _date(name: str, value: object) -> str:
    text = _text(name, value)
    if len(text) != 8 or not text.isascii() or not text.isdigit():
        raise ValueError(f"{name} must be canonical YYYYMMDD")
    try:
        datetime.strptime(text, "%Y%m%d")
    except ValueError as error:
        raise ValueError(f"{name} must be a real calendar date") from error
    return text


def _zero_or_none(value: object) -> bool:
    return value is None or (
        type(value) in (int, float)
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and value == 0
    )


def _cash(value: object) -> Money:
    if type(value) not in (int, float) or isinstance(value, bool):
        raise ValueError("cash dividend must be a finite numeric value")
    if not math.isfinite(float(value)):
        raise ValueError("cash dividend must be a finite numeric value")
    try:
        units = Decimal(str(value)) * 100
    except (InvalidOperation, ValueError) as error:
        raise ValueError("cash dividend must have CNY-cent precision") from error
    if units != units.to_integral_value() or units <= 0:
        raise ValueError("cash dividend must be positive CNY-cent precision")
    return Money(int(units), _CNY_SCALE, "CNY")


def _parse(raw: bytes) -> dict[str, object]:
    def object_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    try:
        value = json.loads(
            raw,
            object_pairs_hook=object_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise ValueError("dividend response must be canonical JSON") from error
    if type(value) is not dict:
        raise ValueError("dividend response must be an object")
    return value


def _receipt(receipt_bytes: bytes, raw_response: bytes) -> dict[str, object]:
    receipt = _parse(receipt_bytes)
    provider = receipt.get("provider_request")
    snapshot = receipt.get("snapshot")
    acquired_at = receipt.get("acquired_at_epoch_nanoseconds")
    expected_request = {
        "type": "tushare_000703_dividend_authority_request_v1",
        "schema_version": 1,
        "ts_code": _TS_CODE,
        "coverage_start_date": _COVERAGE_START,
        "coverage_end_date_exclusive": _COVERAGE_END_EXCLUSIVE,
    }
    expected_receipt_fields = {
        "type", "schema_version", "request", "provider_key", "transport_proxy_key",
        "transport_endpoint", "provider_request", "acquired_at_epoch_nanoseconds",
        "snapshot", "action_selection", "tushare_dividend_assumed_correct",
        "zero_row_authoritative", "source_bounded", "development_only",
        "decision_grade_eligible", "live_eligible", "deployment_authorized",
    }
    expected_provider_fields = {
        "api_name", "params", "fields", "member_key", "auth_mode", "attempts",
        "response_byte_count", "response_sha256", "response_acquired_at_epoch_nanoseconds",
        "returned_row_count", "provider_revision_id", "declared_sha256",
    }
    if (
        set(receipt) != expected_receipt_fields
        or receipt.get("type") != "tushare_000703_dividend_authority_acquisition_receipt_v1"
        or receipt.get("schema_version") != 1
        or receipt.get("request") != expected_request
        or receipt.get("provider_key") != "tushare.pro"
        or receipt.get("transport_proxy_key") != "xiaodefa.approved-tushare-proxy.v1"
        or receipt.get("transport_endpoint") not in {
            "https://fast.xiaodefa.cn", "https://tt.xiaodefa.cn"
        }
        or type(acquired_at) is not int
        or acquired_at < 0
        or type(provider) is not dict
        or set(provider) != expected_provider_fields
        or provider.get("api_name") != "dividend"
        or provider.get("params") != {"ts_code": _TS_CODE}
        or provider.get("fields") != ",".join(_FIELDS)
        or provider.get("member_key") != _MEMBER_KEY
        or provider.get("auth_mode") != "x-api-key"
        or type(provider.get("attempts")) is not int
        or provider["attempts"] not in range(1, 4)
        or provider.get("response_byte_count") != len(raw_response)
        or provider.get("response_sha256") != _raw_hash(raw_response)
        or provider.get("response_acquired_at_epoch_nanoseconds") != acquired_at
        or provider.get("provider_revision_id") is not None
        or provider.get("declared_sha256") is not None
        or receipt.get("tushare_dividend_assumed_correct") is not True
        or receipt.get("zero_row_authoritative") is not True
        or receipt.get("source_bounded") is not True
        or receipt.get("development_only") is not True
        or receipt.get("decision_grade_eligible") is not False
        or receipt.get("live_eligible") is not False
        or receipt.get("deployment_authorized") is not False
        or receipt_bytes != _json_bytes(receipt)
        or type(snapshot) is not dict
    ):
        raise ValueError("dividend receipt does not bind approved action source")
    expected_snapshot = freeze_source_snapshot(
        members=(RawSourceMember(_MEMBER_KEY, raw_response, "0644", acquired_at, None),),
        provenance=SourceSnapshotProvenance(
            "tushare.pro",
            (
                "tushare.pro.via.xiaodefa.approved-proxy."
                f"{receipt['transport_endpoint'].removeprefix('https://')}."
                "000703.sz.dividend.authority.v1"
            ),
            "tushare.pro.terms",
            "backtest.acquisition.candidate",
        ),
    ).snapshot
    if expected_snapshot is None or snapshot != expected_snapshot.to_canonical_dict():
        raise ValueError("dividend receipt snapshot identity mismatch")
    return receipt


@dataclass(frozen=True, slots=True)
class Tushare000703DividendCashActionV2:
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
        _source_hash("source_row_sha256", self.source_row_sha256)
        for name in ("announcement_date", "record_date", "ex_date", "payment_date"):
            _date(name, getattr(self, name))
        if self.ex_date <= self.record_date or self.payment_date < self.ex_date:
            raise ValueError("cash action lifecycle dates are invalid")
        if (
            type(self.cash_per_share) is not Money
            or self.cash_per_share.currency != "CNY"
            or self.cash_per_share.scale != _CNY_SCALE
            or self.cash_per_share.units <= 0
        ):
            raise ValueError("cash_per_share must be positive CNY-cent Money")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "tushare_000703_dividend_cash_action_v2",
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
class Tushare000703DividendActionSetV2:
    instrument_id: InstrumentId
    coverage_start_date: str
    coverage_end_date_exclusive: str
    source_snapshot_hash: str
    source_response_sha256: str
    actions: tuple[Tushare000703DividendCashActionV2, ...]
    tushare_dividend_assumed_correct: bool
    zero_row_authoritative: bool
    development_only: bool
    decision_grade_eligible: bool
    live_eligible: bool
    deployment_authorized: bool
    action_set_hash: str

    def __post_init__(self) -> None:
        if (
            type(self.instrument_id) is not InstrumentId
            or self.instrument_id.stable_key != "000703"
            or self.instrument_id.venue.value != "xshe"
        ):
            raise ValueError("action set must cover xshe:000703")
        start = _date("coverage_start_date", self.coverage_start_date)
        end = _date("coverage_end_date_exclusive", self.coverage_end_date_exclusive)
        if start >= end:
            raise ValueError("action set coverage must be finite and nonempty")
        _source_hash("source_snapshot_hash", self.source_snapshot_hash)
        _source_hash("source_response_sha256", self.source_response_sha256)
        if type(self.actions) is not tuple or not all(
            type(value) is Tushare000703DividendCashActionV2
            for value in self.actions
        ):
            raise TypeError("actions must contain exact Tushare000703DividendCashActionV2")
        if self.actions != tuple(
            sorted(self.actions, key=lambda value: (value.record_date, value.action_id))
        ):
            raise ValueError("actions must be canonical record-date ordered")
        if len({value.action_id for value in self.actions}) != len(self.actions):
            raise ValueError("actions must have unique identities")
        if any(not (start <= value.record_date < end) for value in self.actions):
            raise ValueError("action is outside action set coverage")
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
            raise ValueError("action set must retain the approved development convention")
        if self.action_set_hash != canonical_sha256(self._body()):
            raise ValueError("action set identity mismatch")

    def _body(self) -> dict[str, object]:
        return {
            "type": "tushare_000703_dividend_action_set_v2",
            "schema_version": 2,
            "instrument_id": self.instrument_id,
            "coverage_start_date": self.coverage_start_date,
            "coverage_end_date_exclusive": self.coverage_end_date_exclusive,
            "source_snapshot_hash": self.source_snapshot_hash,
            "source_response_sha256": self.source_response_sha256,
            "actions": self.actions,
            "tushare_dividend_assumed_correct": self.tushare_dividend_assumed_correct,
            "zero_row_authoritative": self.zero_row_authoritative,
            "development_only": self.development_only,
            "decision_grade_eligible": self.decision_grade_eligible,
            "live_eligible": self.live_eligible,
            "deployment_authorized": self.deployment_authorized,
        }

    @classmethod
    def create(
        cls,
        instrument_id: InstrumentId,
        coverage_start_date: str,
        coverage_end_date_exclusive: str,
        source_snapshot_hash: str,
        source_response_sha256: str,
        actions: tuple[Tushare000703DividendCashActionV2, ...],
    ) -> Tushare000703DividendActionSetV2:
        provisional = cls.__new__(cls)
        for name, value in (
            ("instrument_id", instrument_id),
            ("coverage_start_date", coverage_start_date),
            ("coverage_end_date_exclusive", coverage_end_date_exclusive),
            ("source_snapshot_hash", source_snapshot_hash),
            ("source_response_sha256", source_response_sha256),
            ("actions", actions),
            ("tushare_dividend_assumed_correct", True),
            ("zero_row_authoritative", True),
            ("development_only", True),
            ("decision_grade_eligible", False),
            ("live_eligible", False),
            ("deployment_authorized", False),
        ):
            object.__setattr__(provisional, name, value)
        object.__setattr__(
            provisional, "action_set_hash", canonical_sha256(provisional._body())
        )
        provisional.__post_init__()
        return provisional

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "action_set_hash": self.action_set_hash}


def map_tushare_000703_dividend_action_set_v2(
    receipt_bytes: bytes,
    raw_response: bytes,
    instrument_id: InstrumentId,
    /,
) -> Tushare000703DividendActionSetV2:
    if type(receipt_bytes) is not bytes or type(raw_response) is not bytes:
        raise TypeError("receipt_bytes and raw_response must be exact bytes")
    receipt = _receipt(receipt_bytes, raw_response)
    selection = receipt["action_selection"]
    if type(selection) is not dict:
        raise ValueError("dividend receipt action selection is invalid")
    source = _parse(raw_response)
    data = source.get("data")
    if (
        type(data) is not dict
        or data.get("fields") != list(_FIELDS)
        or type(data.get("items")) is not list
    ):
        raise ValueError("dividend response schema mismatch")
    rows = data["items"]
    expected_selection = []
    out_of_scope_implementation_row_count = 0
    actions = []
    for index, row in enumerate(rows):
        if type(row) is not list or len(row) != len(_FIELDS) or row[0] != _TS_CODE:
            raise ValueError("dividend response scope mismatch")
        if row[3] != "实施":
            continue
        record_date = _date("record_date", row[9])
        row_hash = _row_hash(row)
        if not (_COVERAGE_START <= record_date < _COVERAGE_END_EXCLUSIVE):
            out_of_scope_implementation_row_count += 1
            continue
        expected_selection.append(
            {
                "row_index": index,
                "row_sha256": row_hash,
                "record_date": record_date,
                "ex_date": row[10],
            }
        )
        if (
            not _zero_or_none(row[4])
            or not _zero_or_none(row[5])
            or not _zero_or_none(row[6])
            or type(row[8]) not in (int, float)
            or isinstance(row[8], bool)
            or not math.isfinite(float(row[8]))
            or row[8] != row[7]
        ):
            raise ValueError("unsupported selected dividend action")
        cash = _cash(row[7])
        actions.append(
            Tushare000703DividendCashActionV2(
                "tushare.000703.dividend." + row_hash.removeprefix("sha256:"),
                index,
                row_hash,
                _date("announcement_date", row[2]),
                record_date,
                _date("ex_date", row[10]),
                _date("payment_date", row[11]),
                cash,
            )
        )
    if selection != {
        "basis": "div_proc=实施 + record_date",
        "coverage_start_date": _COVERAGE_START,
        "coverage_end_date_exclusive": _COVERAGE_END_EXCLUSIVE,
        "selected_implementation_rows": expected_selection,
        "out_of_scope_implementation_row_count": out_of_scope_implementation_row_count,
    }:
        raise ValueError("selected dividend row hash or scope mismatch")
    snapshot = receipt["snapshot"]
    assert type(snapshot) is dict
    return Tushare000703DividendActionSetV2.create(
        instrument_id,
        _COVERAGE_START,
        _COVERAGE_END_EXCLUSIVE,
        _source_hash("source_snapshot_hash", snapshot["snapshot_id"]),
        _raw_hash(raw_response),
        tuple(sorted(actions, key=lambda value: (value.record_date, value.action_id))),
    )
