"""Backtest-internal synthetic multi-stock SOURCE contract, not a prepare operation.

The manifest and every per-stock/venue component are separate CAS artifacts.
An exact readback proves only synthetic schema/identity/coverage; it cannot prove
provider completeness, brokerage qualification or formal economic admission.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field

from crypto_quant_domain import (
    ArtifactReadResult, ArtifactRef, InstrumentId, UtcInstant, VenueId,
    canonical_bytes, canonical_sha256,
)

from .artifact_envelope_reader import ArtifactEnvelopeReader
from .cn_a_share_portfolio_preparation_inputs_v1 import CnASharePortfolioPreparationInputsV1
from .target_repository import _artifact_ref, _exact, _instant, _instrument, _mapping

_BUNDLE = "backtest_cn_a_share_portfolio_source_bundle_draft"
_COMPONENT = "backtest_cn_a_share_portfolio_source_component_draft"
_VERSION = 1
_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_BUNDLE_FIELDS = frozenset({"type", "schema_version", "input_hash", "decision_at", "execution_at",
                           "stock_sources", "venue_fees", "synthetic_only", "formal_qualified"})
_STOCK_FIELDS = frozenset({"instrument_id", "membership", "trade_status", "corporate_action"})
_FEE_FIELDS = frozenset({"venue_id", "fee"})
_COMPONENT_FIELDS = frozenset({"type", "schema_version", "kind", "instrument_id", "venue_id",
                               "effective_from", "effective_to_exclusive", "available_at",
                               "source_key", "source_hash", "revision_id", "facts",
                               "synthetic_only", "trade_authorized"})
_STATUS = frozenset({"listed", "st", "suspended", "upper_limit_open", "lower_limit_open"})
_FEE_FACTS = frozenset({"route", "product_class", "fee_basis", "commission_bps",
                       "minimum_commission_cents", "market_fee_bps", "sell_tax_bps"})


@dataclass(frozen=True, slots=True)
class CnASharePortfolioSourceReadbackDraftV0:
    bundle_ref: ArtifactRef
    instrument_ids: tuple[InstrumentId, ...]
    component_count: int
    decision_at: UtcInstant
    execution_at: UtcInstant
    synthetic_complete: bool = field(default=True, init=False)
    formal_qualified: bool = field(default=False, init=False)
    trade_authorized: bool = field(default=False, init=False)


def _read(ref: ArtifactRef, reader: ArtifactEnvelopeReader, role: str) -> Mapping[str, object]:
    if type(ref) is not ArtifactRef or ref.schema_version != _VERSION or ref.artifact_type != role:
        raise ValueError("draft source artifact type/version mismatch")
    try:
        value = reader.read(ref=ref)
    except Exception as error:
        raise ValueError("draft source artifact missing, tampered or unavailable") from error
    if (type(value) is not ArtifactReadResult or value.envelope.artifact_type != role
            or value.envelope.schema_version != _VERSION
            or ArtifactRef.from_envelope(value.envelope) != ref
            or value.source_bytes != canonical_bytes(value.envelope)
            or value.source_hash != canonical_sha256(value.envelope)):
        raise ValueError("draft source artifact readback identity mismatch")
    return _mapping("draft source payload", value.envelope.payload)


def _list(value: object, name: str) -> tuple[object, ...]:
    if not isinstance(value, (list, tuple)):
        raise TypeError(f"{name} must be a finite sequence")
    return tuple(value)


def _component(
    ref: ArtifactRef, reader: ArtifactEnvelopeReader, kind: str,
    instrument: InstrumentId | None, venue: VenueId, *,
    decision_at: UtcInstant, execution_at: UtcInstant,
) -> None:
    data = _read(ref, reader, _COMPONENT)
    _exact("draft component", data, _COMPONENT_FIELDS)
    if (data["type"] != "cn_a_share_portfolio_source_component_draft"
            or type(data["schema_version"]) is not int or data["schema_version"] != 1
            or data["kind"] != kind or data["synthetic_only"] is not True
            or data["trade_authorized"] is not False
            or _instrument(data["instrument_id"]) != instrument
            or data["venue_id"] != venue.value):
        raise ValueError("draft component grade/kind/subject mismatch")
    start, stop, available = (_instant(data[key]) for key in (
        "effective_from", "effective_to_exclusive", "available_at"))
    if (start >= stop or start > execution_at or execution_at >= stop
            or (kind in {"membership", "corporate_action"} and not start <= decision_at < stop)
            or available > (decision_at if kind == "membership" else execution_at)):
        raise ValueError("draft component effective/availability interval incomplete")
    if (type(data["source_key"]) is not str or not data["source_key"].startswith("synthetic.")
            or type(data["source_hash"]) is not str or _HASH.fullmatch(data["source_hash"]) is None
            or type(data["revision_id"]) is not str or not data["revision_id"].startswith("synthetic.")):
        raise ValueError("draft component lacks explicit synthetic revision source")
    facts = _mapping("draft component facts", data["facts"])
    if kind == "membership":
        _exact(kind, facts, frozenset({"member", "revision_closed"}))
        valid = facts["member"] is True and facts["revision_closed"] is True
    elif kind == "trade_status":
        _exact(kind, facts, _STATUS)
        valid = (facts["listed"] is True and all(facts[key] is False for key in
                 ("st", "suspended", "upper_limit_open", "lower_limit_open")))
    elif kind == "corporate_action":
        _exact(kind, facts, frozenset({"no_action_window", "absence_closed"}))
        valid = facts["no_action_window"] is True and facts["absence_closed"] is True
    elif kind == "fee":
        _exact(kind, facts, _FEE_FACTS)
        valid = (facts["route"] == "domestic" and facts["product_class"] == "ordinary_a_share"
                 and facts["fee_basis"] == "turnover"
                 and all(type(facts[key]) is int and facts[key] > 0 for key in
                         ("commission_bps", "minimum_commission_cents", "market_fee_bps"))
                 and type(facts["sell_tax_bps"]) is int and facts["sell_tax_bps"] >= 0)
    else:
        raise ValueError("unknown draft component kind")
    if not valid:
        raise ValueError("draft source declaration missing, adverse or ineligible")


def read_cn_a_share_portfolio_source_bundle_draft_v0(
    ref: ArtifactRef, *, inputs: CnASharePortfolioPreparationInputsV1,
    reader: ArtifactEnvelopeReader,
) -> CnASharePortfolioSourceReadbackDraftV0:
    """Read each required source from CAS; complete synthetic sample stays non-formal."""
    if type(inputs) is not CnASharePortfolioPreparationInputsV1 or not callable(getattr(reader, "read", None)):
        raise TypeError("draft source readback requires portfolio inputs and artifact reader")
    data = _read(ref, reader, _BUNDLE)
    _exact("draft bundle", data, _BUNDLE_FIELDS)
    if (data["type"] != "cn_a_share_portfolio_source_bundle_draft"
            or type(data["schema_version"]) is not int or data["schema_version"] != 1
            or data["synthetic_only"] is not True or data["formal_qualified"] is not False
            or data["input_hash"] != inputs.input_hash):
        raise ValueError("draft source bundle scope/grade mismatch")
    decision, execution = _instant(data["decision_at"]), _instant(data["execution_at"])
    if decision >= execution:
        raise ValueError("draft decision must precede intended execution")
    stocks = _list(data["stock_sources"], "stock_sources")
    fees = _list(data["venue_fees"], "venue_fees")
    if len(stocks) != len(inputs.instrument_ids) or len(fees) != 2:
        raise ValueError("draft per-stock or SH/SZ fee source coverage incomplete")
    seen: set[ArtifactRef] = {ref}
    components: list[tuple[ArtifactRef, str, InstrumentId | None, VenueId]] = []
    for raw, instrument in zip(stocks, inputs.instrument_ids, strict=True):
        stock = _mapping("stock source", raw)
        _exact("stock source", stock, _STOCK_FIELDS)
        if _instrument(stock["instrument_id"]) != instrument:
            raise ValueError("draft member order/universe mismatch")
        for key, kind in (("membership", "membership"), ("trade_status", "trade_status"),
                          ("corporate_action", "corporate_action")):
            component_ref = _artifact_ref(stock[key])
            if component_ref in seen:
                raise ValueError("draft source refs must be independent and unique")
            seen.add(component_ref)
            components.append((component_ref, kind, instrument, instrument.venue))
    for raw, venue in zip(fees, (VenueId("xshg"), VenueId("xshe")), strict=True):
        item = _mapping("venue fee", raw)
        _exact("venue fee", item, _FEE_FIELDS)
        if item["venue_id"] != venue.value:
            raise ValueError("draft fee venues must cover SH and SZ exactly once in order")
        component_ref = _artifact_ref(item["fee"])
        if component_ref in seen:
            raise ValueError("draft source refs must be independent and unique")
        seen.add(component_ref)
        components.append((component_ref, "fee", None, venue))
    # Validate the entire manifest before any component read: later omissions must not be hidden.
    for component_ref, kind, instrument, venue in components:
        _component(component_ref, reader, kind, instrument, venue,
                   decision_at=decision, execution_at=execution)
    return CnASharePortfolioSourceReadbackDraftV0(
        ref, inputs.instrument_ids, len(seen) - 1, decision, execution)
