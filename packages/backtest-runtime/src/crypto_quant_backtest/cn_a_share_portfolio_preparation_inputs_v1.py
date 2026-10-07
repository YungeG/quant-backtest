"""Standard-Backtest portfolio input identity, before any economic preparation.

This is not a prepare operation. No current multi-stock CN source authority can
produce an Engine case or a BacktestRequest from this declaration.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import NoReturn

from crypto_quant_domain import (
    ArtifactRef, CashBalanceKey, InstrumentCatalog, InstrumentId, InstrumentType, Money,
    PositionBalanceKey, Scale, UtcInstant, canonical_sha256,
)
from crypto_quant_market_data import EventCursor, MarketBundleReader, MarketBundleRef, MarketEvent
from crypto_quant_trading import LedgerSchema

from .artifact_envelope_reader import ArtifactEnvelopeReader
from .execution import BAR_OPEN_CAPABILITY, BarOpenObservation
from .target_repository import BacktestTargetStreamRef, BacktestTargetStreamRepository
from .target_stream import TARGET_STREAM_EVENT_TYPE

_SH = re.compile(r"6[0-9]{5}\Z")
_SZ = re.compile(r"(?:00|30)[0-9]{4}\Z")
_CENT = Scale(2)

_FORMAL_SOURCE_GAPS = (
    "membership_effective_revision_unverified",
    "per_stock_listing_st_suspension_limit_unverified",
    "xshg_xshe_account_fee_effective_interval_unverified",
    "corporate_action_lifecycle_unverified",
    "venue_calendar_complete_unverified",
    "daily_close_mark_series_unverified",
    "economic_account_owner_head_unqualified",
    "historical_provider_revision_availability_unverified",
)


class CnASharePortfolioSourceAdmissionBlockedV1(ValueError):
    """Backtest-internal source gate, not a published economic terminal."""

    def __init__(self) -> None:
        self.reason_codes = _FORMAL_SOURCE_GAPS
        super().__init__("portfolio source qualification unavailable: " + ",".join(self.reason_codes))

@dataclass(frozen=True, slots=True)
class CnASharePortfolioPreparationInputsV1:
    """One account, variable-N sorted SH/SZ equities, both venue CNY keys.

    References and schema are declarations, NOT evidence of member eligibility,
    source publication/availability, trading status, historical fees or fills.
    """

    account_id: str
    instrument_ids: tuple[InstrumentId, ...]
    instrument_catalog: InstrumentCatalog
    ledger_schema: LedgerSchema
    initial_cash: Money
    target_stream_ref: BacktestTargetStreamRef
    market_bundle_ref: MarketBundleRef

    def __post_init__(self) -> None:
        if type(self.account_id) is not str or not self.account_id or self.account_id.strip() != self.account_id:
            raise ValueError("portfolio account_id must be canonical")
        if (type(self.instrument_ids) is not tuple or not self.instrument_ids
                or any(type(value) is not InstrumentId for value in self.instrument_ids)):
            raise ValueError("portfolio instrument_ids must be a nonempty exact tuple")
        ids = self.instrument_ids
        if (len(set(ids)) != len(ids)
                or ids != tuple(sorted(ids, key=lambda value: (value.venue.value, value.stable_key)))
                or any(value.venue.value not in {"xshg", "xshe"}
                       or (value.venue.value == "xshg" and _SH.fullmatch(value.stable_key) is None)
                       or (value.venue.value == "xshe" and _SZ.fullmatch(value.stable_key) is None)
                       for value in ids)):
            raise ValueError("portfolio instruments require unique sorted SH/SZ ordinary A-share codes")
        if (type(self.instrument_catalog) is not InstrumentCatalog
                or type(self.ledger_schema) is not LedgerSchema
                or type(self.initial_cash) is not Money
                or type(self.target_stream_ref) is not BacktestTargetStreamRef
                or type(self.market_bundle_ref) is not MarketBundleRef):
            raise TypeError("portfolio preparation requires exact standard input types")
        if (self.initial_cash.currency != "CNY" or self.initial_cash.scale != _CENT
                or self.initial_cash.units <= 0):
            raise ValueError("portfolio initial cash must be positive CNY cents")
        definitions = self.instrument_catalog.instruments
        if (len(definitions) != len(ids)
                or {item.instrument_id for item in definitions} != set(ids)
                or any(item.instrument_type is not InstrumentType.EQUITY
                       or item.quote_currency.value != "CNY"
                       or item.settlement_currency.value != "CNY" for item in definitions)):
            raise ValueError("portfolio catalog must exactly cover CNY SH/SZ equities")
        cash = [(registration.key, registration.scale) for registration in self.ledger_schema.registrations
                if isinstance(registration.key, CashBalanceKey)]
        positions = [(registration.key, registration.scale) for registration in self.ledger_schema.registrations
                     if isinstance(registration.key, PositionBalanceKey)]
        if (len(cash) != 2 or {key.venue_id.value for key, _ in cash} != {"xshg", "xshe"}
                or any(key.account_id != self.account_id or key.currency_id.value != "CNY"
                       or scale != _CENT for key, scale in cash)
                or len(positions) != len(ids)
                or {key.instrument_id for key, _ in positions} != set(ids)
                or any(key.account_id != self.account_id or key.venue_id != key.instrument_id.venue
                       or scale != Scale(0) for key, scale in positions)):
            raise ValueError("portfolio ledger must register both venue CNY keys and exact same-account positions")

    @property
    def input_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "cn_a_share_portfolio_preparation_inputs", "schema_version": 1,
                "account_id": self.account_id, "instrument_ids": self.instrument_ids,
                "instrument_catalog": self.instrument_catalog, "ledger_schema": self.ledger_schema,
                "initial_cash": self.initial_cash, "target_stream_ref": self.target_stream_ref,
                "market_bundle_ref": self.market_bundle_ref, "shared_cny_funding_authority_qualified": False,
                "trade_authorized": False}


def _require_source_open_binding_v1(
    inputs: CnASharePortfolioPreparationInputsV1, *,
    market_reader: MarketBundleReader, execution_at: UtcInstant,
) -> None:
    """Bind one draft execution instant to retained BarOpen rows; no Fill/eligibility claim."""
    manifest = market_reader.manifest
    if not manifest.coverage_start <= execution_at < manifest.coverage_end_exclusive:
        raise ValueError("portfolio source execution binding mismatch: outside market coverage")
    streams = tuple(stream for stream in manifest.streams if stream.capability == BAR_OPEN_CAPABILITY)
    # ponytail: one bounded opening stream; wider history needs a per-decision source contract first.
    if len(streams) != 1 or not 0 < streams[0].event_count <= 4096:
        raise ValueError("portfolio source execution binding mismatch: unsupported opening stream")
    stream = streams[0]
    cursor = market_reader.open_cursor(stream.stream_key, batch_size=64)
    if (type(cursor) is not EventCursor or cursor.bundle_ref != inputs.market_bundle_ref
            or cursor.stream_manifest != stream or cursor.position != 0):
        raise ValueError("portfolio source opening cursor identity mismatch")
    events: list[MarketEvent] = []
    while not cursor.exhausted:
        batch, advanced = market_reader.read_batch(cursor)
        if (type(batch) is not tuple or not batch or any(type(event) is not MarketEvent for event in batch)
                or type(advanced) is not EventCursor or advanced.bundle_ref != cursor.bundle_ref
                or advanced.stream_manifest != stream or advanced.position != cursor.position + len(batch)):
            raise ValueError("portfolio source opening cursor did not advance exactly")
        events.extend(batch)
        cursor = advanced
    if len(events) != stream.event_count or canonical_sha256(events) != stream.content_hash:
        raise ValueError("portfolio source opening stream digest mismatch")
    if any(event.stream_key != stream.stream_key or event.capability != BAR_OPEN_CAPABILITY
           or event.event_type != "bar_open" for event in events):
        raise ValueError("portfolio source opening stream declaration mismatch")
    selected = tuple(event for event in events if event.event_time == execution_at)
    if (len(selected) != len(inputs.instrument_ids)
            or {event.instrument_id for event in selected} != set(inputs.instrument_ids)
            or any(event.available_time != execution_at for event in selected)):
        raise ValueError("portfolio source execution binding mismatch: opening time/stock exact cover")
    for event in selected:
        observation = BarOpenObservation.from_event(event)
        if observation.open_price is not None and observation.open_price.quote_currency != "CNY":
            raise ValueError("portfolio source opening price must use CNY")

def require_cn_a_share_portfolio_source_qualification_v1(
    inputs: CnASharePortfolioPreparationInputsV1, *, market_reader: MarketBundleReader,
    artifact_reader: ArtifactEnvelopeReader,
    source_bundle_ref: ArtifactRef | None = None,
) -> NoReturn:
    """Read supplied draft sources before Bar/target checks; NEVER grant formal admission.

    BarOpen metadata or complete *synthetic* sources cannot prove real provider
    revisions, tradability, account fees or corporate-action authority.
    """
    if (type(inputs) is not CnASharePortfolioPreparationInputsV1 or not isinstance(market_reader, MarketBundleReader)
            or not callable(getattr(artifact_reader, "read", None))):
        raise TypeError("portfolio source gate requires inputs, market reader and artifact reader")
    if (market_reader.bundle_ref != inputs.market_bundle_ref
            or MarketBundleRef.from_manifest(market_reader.manifest) != inputs.market_bundle_ref
            or market_reader.manifest.instrument_catalog_hash != canonical_sha256(inputs.instrument_catalog)):
        raise ValueError("portfolio market bundle/ref/catalog identity mismatch")
    sources = None
    if source_bundle_ref is not None:
        if type(source_bundle_ref) is not ArtifactRef:
            raise TypeError("portfolio source_bundle_ref must be exact ArtifactRef")
        # Late import avoids a cycle: draft source readback binds these input declarations.
        from .cn_a_share_portfolio_source_bundle_draft_v0 import read_cn_a_share_portfolio_source_bundle_draft_v0
        from .cn_a_share_portfolio_source_pair_draft_v0 import _PAIR, read_cn_a_share_portfolio_source_pair_draft_v0
        sources = (read_cn_a_share_portfolio_source_pair_draft_v0(
            source_bundle_ref, inputs=inputs, reader=artifact_reader)
            if source_bundle_ref.artifact_type == _PAIR else
            (read_cn_a_share_portfolio_source_bundle_draft_v0(
                source_bundle_ref, inputs=inputs, reader=artifact_reader),))
    if market_reader.validate_requirements(required_capabilities=(BAR_OPEN_CAPABILITY,)) is not None:
        raise ValueError("portfolio source lacks BarOpen capability")
    target = BacktestTargetStreamRepository(reader=artifact_reader).load(inputs.target_stream_ref)
    if not target.target_stream.events:
        raise ValueError("portfolio target stream contains no decision")
    if sources is not None:
        # Single V0 or the fixed two-window draft; never implicit coverage of a wider target stream.
        if len(target.target_stream.events) != len(sources):
            raise ValueError("portfolio source decision binding mismatch")
        for source in sources:
            events = target.target_stream.events_at(source.decision_at)
            if len(events) != 1 or events[0].event_type != TARGET_STREAM_EVENT_TYPE:
                raise ValueError("portfolio source decision binding mismatch")
            _require_source_open_binding_v1(
                inputs, market_reader=market_reader, execution_at=source.execution_at)
    raise CnASharePortfolioSourceAdmissionBlockedV1()
