"""Public retained-price-conditioned portfolio Engine diagnostic, never a publication.

Observed prices are transplanted into an explicitly synthetic DEVELOPMENT case.
The source date is retained; it is NOT asserted to equal the template clock or
prove PIT, liquidity, eligibility, fees, NAV, historical returns or OOS.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from decimal import Decimal

from crypto_quant_domain import (
    ArtifactEnvelope, ArtifactReadResult, ArtifactRef, canonical_bytes, canonical_sha256,
)
from crypto_quant_market_data import MarketBundleReader

from .artifact_envelope_publisher import ArtifactEnvelopePublisher
from .artifact_envelope_reader import ArtifactEnvelopeReader
from .cn_a_share_portfolio_case_inputs_v8 import read_retained_cn_a_share_portfolio_case_input_v8
from .cn_a_share_portfolio_engine_case_v2 import ResolvedCnASharePortfolioExecutionCaseV2
from .cn_a_share_portfolio_development_engine_v1 import (
    CnASharePortfolioDevelopmentEngineV1, CnASharePortfolioEngineOutcomeV1,
)
from .execution import BarOpenObservation


def _unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate retained response field")
        result[key] = value
    return result


@dataclass(frozen=True, slots=True)
class CnAShareRetainedOpenConditionV1:
    """Exact raw bytes and source day, not a qualified market-provider declaration."""

    response_bytes: bytes
    response_sha256: str
    ts_code: str
    trade_date: str
    bar_event_id: str
    bar_event_hash: str
    historical_economic_case: bool = field(default=False, init=False)
    trade_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if (type(self.response_bytes) is not bytes or not self.response_bytes
                or len(self.response_bytes) > 2 * 1024 * 1024
                or type(self.response_sha256) is not str
                or self.response_sha256 != "sha256:" + hashlib.sha256(self.response_bytes).hexdigest()
                or type(self.ts_code) is not str
                or re.fullmatch(r"(?:6[0-9]{5}\.SH|(?:00|30)[0-9]{4}\.SZ)", self.ts_code) is None
                or type(self.trade_date) is not str or re.fullmatch(r"[0-9]{8}", self.trade_date) is None
                or type(self.bar_event_id) is not str or not self.bar_event_id
                or type(self.bar_event_hash) is not str
                or re.fullmatch(r"sha256:[0-9a-f]{64}", self.bar_event_hash) is None):
            raise ValueError("retained open condition identity/bytes mismatch")
        self.open_price()

    def open_price(self) -> Decimal:
        try:
            payload = json.loads(self.response_bytes, parse_float=Decimal, object_pairs_hook=_unique,
                                 parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
            if type(payload) is not dict or type(payload.get("code")) is not int or payload["code"] != 0:
                raise ValueError("retained response business failure")
            data = payload["data"]
            fields = data["fields"]
            if fields != ["ts_code", "trade_date", "open", "high", "low", "close", "pre_close", "vol", "amount"]:
                raise ValueError("retained daily fields mismatch")
            items = data["items"]
            if type(items) is not list or not 0 < len(items) < 6000:
                raise ValueError("retained daily rows missing/truncated")
            matches = []
            for item in items:
                if type(item) is not list or len(item) != len(fields):
                    raise ValueError("retained daily row width mismatch")
                if item[0] == self.ts_code:
                    matches.append(item)
            if len(matches) != 1 or matches[0][1] != self.trade_date:
                raise ValueError("retained stock/day absent or ambiguous")
            price = matches[0][2]
            if type(price) not in (int, Decimal) or not Decimal(price).is_finite() or Decimal(price) <= 0:
                raise ValueError("retained open price invalid")
            return Decimal(price)
        except (KeyError, TypeError, UnicodeError, json.JSONDecodeError) as error:
            raise ValueError("retained daily response malformed") from error

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "cn_a_share_retained_open_condition", "schema_version": 1,
                "response_hex": self.response_bytes.hex(), "response_sha256": self.response_sha256,
                "ts_code": self.ts_code, "trade_date": self.trade_date,
                "bar_event_id": self.bar_event_id, "bar_event_hash": self.bar_event_hash,
                "historical_economic_case": False, "formal_publication_eligible": False, "trade_authorized": False}


def _envelope(case: ResolvedCnASharePortfolioExecutionCaseV2,
              conditions: tuple[CnAShareRetainedOpenConditionV1, ...]) -> ArtifactEnvelope:
    if type(case) is not ResolvedCnASharePortfolioExecutionCaseV2:
        raise TypeError("Engine diagnostic prepare needs exact V2 development case")
    if (type(conditions) is not tuple or len(conditions) != len(case.bars)
            or any(type(item) is not CnAShareRetainedOpenConditionV1 for item in conditions)
            or len({item.bar_event_id for item in conditions}) != len(conditions)):
        raise ValueError("retained conditions must exactly cover portfolio opens")
    by_event = {item.bar_event_id: item for item in conditions}
    for event in case.bars:
        condition = by_event.get(event.event_id)
        observation = BarOpenObservation.from_event(event)
        if (condition is None or event.instrument_id is None
                or condition.bar_event_hash != event.event_hash
                or condition.ts_code != event.instrument_id.stable_key + (
                    ".SH" if event.instrument_id.venue.value == "xshg" else ".SZ")
                or observation.open_price is None
                or observation.open_price.units != condition.open_price() * observation.open_price.scale.factor):
            raise ValueError("retained price does not bind exact portfolio Bar")
    return ArtifactEnvelope.create("cn_a_share_portfolio_engine_diagnostic_case", 1,
                                   {"case": case, "conditions": conditions,
                                    "historical_economic_case": False, "formal_publication_eligible": False, "trade_authorized": False})


@dataclass(frozen=True, slots=True)
class PreparedCnASharePortfolioEngineDiagnosticV1:
    case: ResolvedCnASharePortfolioExecutionCaseV2
    conditions: tuple[CnAShareRetainedOpenConditionV1, ...]
    case_ref: ArtifactRef
    preparation_id: str
    artifact_reader: ArtifactEnvelopeReader
    target_reader: ArtifactEnvelopeReader
    market_reader: MarketBundleReader
    diagnostic_only: bool = field(default=True, init=False)
    historical_economic_case: bool = field(default=False, init=False)
    formal_publication_eligible: bool = field(default=False, init=False)
    trade_authorized: bool = field(default=False, init=False)

    def _verify(self) -> None:
        envelope = _envelope(self.case, self.conditions)
        if (type(self.case_ref) is not ArtifactRef or ArtifactRef.from_envelope(envelope) != self.case_ref
                or self.preparation_id != "cn-a-share-portfolio-engine-diagnostic-v1:" + self.case_ref.content_hash):
            raise ValueError("Engine diagnostic preparation identity mismatch")
        retained = self.artifact_reader.read(ref=self.case_ref)
        if (type(retained) is not ArtifactReadResult or retained.envelope != envelope
                or retained.source_bytes != canonical_bytes(envelope)
                or retained.source_hash != canonical_sha256(envelope)):
            raise ValueError("Engine diagnostic retained case bytes mismatch")
        source = read_retained_cn_a_share_portfolio_case_input_v8(
            self.case.source_ref, reader=self.artifact_reader, target_reader=self.target_reader,
            market_reader=self.market_reader)
        if source != self.case.source:
            raise ValueError("Engine diagnostic V8 source mismatch")

    def __post_init__(self) -> None:
        self._verify()

    def run(self) -> CnASharePortfolioEngineOutcomeV1:
        """Re-read before each Engine replay; preserve native failures, publish nothing."""
        self._verify()
        return CnASharePortfolioDevelopmentEngineV1().run(self.case)


def prepare_cn_a_share_portfolio_engine_diagnostic_v1(
    *, case: ResolvedCnASharePortfolioExecutionCaseV2,
    conditions: tuple[CnAShareRetainedOpenConditionV1, ...],
    artifact_reader: ArtifactEnvelopeReader, artifact_publisher: ArtifactEnvelopePublisher,
    target_reader: ArtifactEnvelopeReader, market_reader: MarketBundleReader,
) -> PreparedCnASharePortfolioEngineDiagnosticV1:
    """Retain source-conditioned synthetic case only; no canonical result/grade/NAV."""
    envelope = _envelope(case, conditions)
    # Validate existing V8/target/market closure before writing the new diagnostic artifact.
    if read_retained_cn_a_share_portfolio_case_input_v8(
            case.source_ref, reader=artifact_reader, target_reader=target_reader,
            market_reader=market_reader) != case.source:
        raise ValueError("Engine diagnostic V8 source mismatch")
    ref = ArtifactRef.from_envelope(envelope)
    actual = artifact_publisher.put(envelope=envelope)
    if type(actual) is not ArtifactRef or actual != ref:
        raise ValueError("Engine diagnostic publisher returned wrong ref")
    return PreparedCnASharePortfolioEngineDiagnosticV1(
        case, conditions, ref, "cn-a-share-portfolio-engine-diagnostic-v1:" + ref.content_hash,
        artifact_reader, target_reader, market_reader)
