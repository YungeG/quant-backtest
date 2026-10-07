"""Additive true-date retained-value admission to a two-week DEVELOPMENT diagnostic.

Does not modify V8 or assert provider publication/revision, PIT, status/action
completeness, actual account fees, fills in the real market or formal economics.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime
from zoneinfo import ZoneInfo

from crypto_quant_domain import ArtifactEnvelope, ArtifactReadResult, ArtifactRef, UtcInstant, VenueId, canonical_bytes, canonical_sha256
from crypto_quant_market_data import MarketBundleReader
from crypto_quant_trading.profiles.cn_a_share import CnAShareCalendarDayKind, CnAShareFrozenCalendar, CnAShareFrozenCalendarDay

from .artifact_envelope_publisher import ArtifactEnvelopePublisher
from .artifact_envelope_reader import ArtifactEnvelopeReader
from .cn_a_share_portfolio_case_inputs_v8 import read_retained_cn_a_share_portfolio_case_input_v8
from .cn_a_share_portfolio_development_engine_v1 import CnASharePortfolioDevelopmentEngineV1, CnASharePortfolioEngineOutcomeV1
from .cn_a_share_portfolio_engine_case_v3 import ResolvedCnASharePortfolioExecutionCaseV3
from .cn_a_share_portfolio_engine_diagnostic_prepare_v1 import CnAShareRetainedOpenConditionV1, _unique
from .execution import BarOpenObservation

_TZ = ZoneInfo("Asia/Shanghai")


@dataclass(frozen=True, slots=True)
class CnAShareRetainedCalendarConditionV1:
    response_bytes: bytes
    response_sha256: str
    venue_id: VenueId

    def __post_init__(self) -> None:
        if (type(self.response_bytes) is not bytes or not self.response_bytes
                or len(self.response_bytes) > 65536 or type(self.venue_id) is not VenueId
                or self.venue_id.value not in {"xshg", "xshe"}
                or self.response_sha256 != "sha256:" + hashlib.sha256(self.response_bytes).hexdigest()):
            raise ValueError("retained calendar condition identity mismatch")
        self.calendar()

    def calendar(self) -> CnAShareFrozenCalendar:
        obj = json.loads(self.response_bytes, object_pairs_hook=_unique)
        if type(obj.get("code")) is not int or obj["code"] != 0:
            raise ValueError("retained calendar business failure")
        data = obj["data"]
        if data["fields"] != ["exchange", "cal_date", "is_open", "pretrade_date"]:
            raise ValueError("retained calendar fields mismatch")
        rows = data["items"]
        if type(rows) is not list or len(rows) != 25:
            raise ValueError("retained calendar coverage mismatch")
        exchange = "SSE" if self.venue_id.value == "xshg" else "SZSE"
        days = []
        for row in rows:
            if (type(row) is not list or len(row) != 4 or row[0] != exchange
                    or type(row[2]) is not int or row[2] not in (0, 1)):
                raise ValueError("retained calendar row malformed")
            day = date.fromisoformat(row[1][:4] + "-" + row[1][4:6] + "-" + row[1][6:])
            # FROZEN_HOLIDAY is a closed-session projection here, not proof of closure cause.
            kind = (CnAShareCalendarDayKind.TRADING if row[2] else
                    CnAShareCalendarDayKind.WEEKEND if day.weekday() >= 5 else
                    CnAShareCalendarDayKind.FROZEN_HOLIDAY)
            days.append(CnAShareFrozenCalendarDay(day, kind))
        return CnAShareFrozenCalendar(self.venue_id,
            "CN.XSHG" if self.venue_id.value == "xshg" else "CN.XSHE",
            date(2024, 10, 1), date(2024, 10, 26), tuple(days))

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "cn_a_share_retained_calendar_condition", "schema_version": 1,
                "response_hex": self.response_bytes.hex(), "response_sha256": self.response_sha256,
                "venue_id": self.venue_id, "provider_available_at": None,
                "provider_revision_id": None, "closure_cause_verified": False,
                "formal_publication_eligible": False}


def _envelope(case: ResolvedCnASharePortfolioExecutionCaseV3,
              opens: tuple[CnAShareRetainedOpenConditionV1, ...],
              calendars: tuple[CnAShareRetainedCalendarConditionV1, ...]) -> ArtifactEnvelope:
    if type(case) is not ResolvedCnASharePortfolioExecutionCaseV3:
        raise TypeError("true-date diagnostic requires exact paired V3 model case")
    if (type(opens) is not tuple or len(opens) != len(case.first_bars) + len(case.second_bars)
            or any(type(c) is not CnAShareRetainedOpenConditionV1 for c in opens)
            or len({c.bar_event_id for c in opens}) != len(opens)
            or type(calendars) is not tuple or len(calendars) != 2
            or any(type(c) is not CnAShareRetainedCalendarConditionV1 for c in calendars)
            or {c.venue_id.value for c in calendars} != {"xshg", "xshe"}):
        raise ValueError("true-date conditions need complete two-week stock/venue cover")
    native = {c.venue_id: c.calendar() for c in calendars}
    if any(c != native[c.venue_id] for c in (*case.first_calendars, *case.second_calendars)):
        raise ValueError("true-date native calendar differs from retained rows")
    by_event = {c.bar_event_id: c for c in opens}
    for bars, target, decision, opening in zip(
            (case.first_bars, case.second_bars), case.target_events,
            (date(2024, 10, 11), date(2024, 10, 18)),
            (date(2024, 10, 14), date(2024, 10, 21)), strict=True):
        expected_target = UtcInstant.from_datetime(datetime(decision.year, decision.month, decision.day, 23, 59, 59, tzinfo=_TZ))
        if target.event_time != expected_target or target.available_time != expected_target:
            raise ValueError("true-date weekly decision cutoff mismatch")
        for bar in bars:
            condition = by_event.get(bar.event_id)
            expected_open = UtcInstant.from_datetime(datetime(opening.year, opening.month, opening.day, 9, 30, tzinfo=_TZ))
            observation = BarOpenObservation.from_event(bar)
            if (condition is None or bar.instrument_id is None or bar.event_time != expected_open
                    or bar.available_time != expected_open
                    or condition.trade_date != opening.strftime("%Y%m%d")
                    or condition.bar_event_hash != bar.event_hash
                    or condition.ts_code != bar.instrument_id.stable_key + (
                        ".SH" if bar.instrument_id.venue.value == "xshg" else ".SZ")
                    or observation.open_price is None
                    or observation.open_price.units != condition.open_price() * observation.open_price.scale.factor):
                raise ValueError("true-date retained open binding mismatch")
            candidates = [d.local_date for d in native[bar.instrument_id.venue].days
                          if d.kind is CnAShareCalendarDayKind.TRADING and d.local_date > decision]
            if not candidates or min(candidates) != opening:
                raise ValueError("true-date venue-calendar next opening mismatch")
    return ArtifactEnvelope.create("cn_a_share_portfolio_true_date_diagnostic_input", 1,
        {"case": case, "open_conditions": opens, "calendar_conditions": calendars,
         "source_dates_bound": True, "diagnostic_only": True, "fee_basis": "explicit_model_not_account_invoice",
         "provider_available_at": None, "provider_revision_id": None,
         "historical_source_qualified": False, "formal_publication_eligible": False, "trade_authorized": False})


@dataclass(frozen=True, slots=True)
class PreparedCnAShareTrueDateDiagnosticV1:
    case: ResolvedCnASharePortfolioExecutionCaseV3
    open_conditions: tuple[CnAShareRetainedOpenConditionV1, ...]
    calendar_conditions: tuple[CnAShareRetainedCalendarConditionV1, ...]
    input_ref: ArtifactRef
    artifact_reader: ArtifactEnvelopeReader
    target_reader: ArtifactEnvelopeReader
    market_reader: MarketBundleReader
    source_dates_bound: bool = field(default=True, init=False)
    historical_source_qualified: bool = field(default=False, init=False)
    formal_publication_eligible: bool = field(default=False, init=False)
    trade_authorized: bool = field(default=False, init=False)

    def _verify(self) -> None:
        envelope = _envelope(self.case, self.open_conditions, self.calendar_conditions)
        if type(self.input_ref) is not ArtifactRef or self.input_ref != ArtifactRef.from_envelope(envelope):
            raise ValueError("true-date diagnostic input ref mismatch")
        retained = self.artifact_reader.read(ref=self.input_ref)
        if (type(retained) is not ArtifactReadResult or retained.envelope != envelope
                or retained.source_bytes != canonical_bytes(envelope)
                or retained.source_hash != canonical_sha256(envelope)):
            raise ValueError("true-date diagnostic input bytes mismatch")
        if read_retained_cn_a_share_portfolio_case_input_v8(
                self.case.source_ref, reader=self.artifact_reader, target_reader=self.target_reader,
                market_reader=self.market_reader) != self.case.source:
            raise ValueError("true-date diagnostic model input mismatch")

    def __post_init__(self) -> None:
        self._verify()

    def run(self) -> CnASharePortfolioEngineOutcomeV1:
        self._verify()
        return CnASharePortfolioDevelopmentEngineV1().run(self.case)


def prepare_cn_a_share_portfolio_true_date_diagnostic_v1(
    *, case: ResolvedCnASharePortfolioExecutionCaseV3,
    open_conditions: tuple[CnAShareRetainedOpenConditionV1, ...],
    calendar_conditions: tuple[CnAShareRetainedCalendarConditionV1, ...],
    artifact_reader: ArtifactEnvelopeReader, artifact_publisher: ArtifactEnvelopePublisher,
    target_reader: ArtifactEnvelopeReader, market_reader: MarketBundleReader,
) -> PreparedCnAShareTrueDateDiagnosticV1:
    """Admit exact observed dates into diagnostics only; retain before native execution."""
    envelope = _envelope(case, open_conditions, calendar_conditions)
    if read_retained_cn_a_share_portfolio_case_input_v8(
            case.source_ref, reader=artifact_reader, target_reader=target_reader,
            market_reader=market_reader) != case.source:
        raise ValueError("true-date diagnostic model input mismatch")
    ref = ArtifactRef.from_envelope(envelope)
    actual = artifact_publisher.put(envelope=envelope)
    if type(actual) is not ArtifactRef or actual != ref:
        raise ValueError("true-date diagnostic publisher returned wrong ref")
    return PreparedCnAShareTrueDateDiagnosticV1(case, open_conditions, calendar_conditions,
        ref, artifact_reader, target_reader, market_reader)
