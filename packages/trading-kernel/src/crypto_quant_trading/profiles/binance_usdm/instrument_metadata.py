"""Pure offline Binance USD-M instrument metadata normalization."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
import unicodedata

from crypto_quant_domain import (
    CurrencyId,
    InstrumentDefinition,
    InstrumentId,
    InstrumentType,
    Rate,
    Scale,
    SymbolInterval,
    SymbolTimeline,
    UtcInstant,
    VenueId,
    canonical_sha256,
)

from ...ports import ProfileComponentRef, ProfilePortOutcome, ProfilePortType


_SCHEMA_VERSION = 1
_COMPONENT_KEY = "crypto.binance_usdm.instrument_metadata.v1"
_ALGORITHM_KEY = "binance-usdm-instrument-metadata-offline-v1"
_SHA256 = re.compile(r"sha256:[0-9a-f]{64}\Z")
_STABLE_KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z")

BINANCE_USDM_OPEN_ENDED_DELIVERY_AT = UtcInstant(
    4_133_404_800_000_000_000
)


class BinanceUsdmContractStatus(str, Enum):
    PENDING_TRADING = "PENDING_TRADING"
    TRADING = "TRADING"
    PRE_DELIVERING = "PRE_DELIVERING"
    DELIVERING = "DELIVERING"
    DELIVERED = "DELIVERED"
    PRE_SETTLE = "PRE_SETTLE"
    SETTLING = "SETTLING"
    CLOSE = "CLOSE"
    TRADING_HALT = "TRADING_HALT"
    TRADING_CANCEL_ONLY = "TRADING_CANCEL_ONLY"


class BinanceUsdmInstrumentMetadataFailureCode(str, Enum):
    MISSING_REVISION_SET = "missing_revision_set"
    INVALID_REVISION_SET = "invalid_revision_set"
    REVISION_NOT_AVAILABLE = "revision_not_available"
    STABLE_IDENTITY_MISMATCH = "stable_identity_mismatch"
    UNSUPPORTED_CONTRACT_TYPE = "unsupported_contract_type"
    UNSUPPORTED_CONTRACT_STATUS = "unsupported_contract_status"
    INVALID_CURRENCY_CONTEXT = "invalid_currency_context"
    INVALID_LISTING_INTERVAL = "invalid_listing_interval"
    NOT_LISTED_AT_QUERY_INSTANT = "not_listed_at_query_instant"
    SYMBOL_TIMELINE_CONFLICT = "symbol_timeline_conflict"
    METADATA_CONFLICT = "metadata_conflict"


_FAILURE_MESSAGES = {
    code: code.value.replace("_", " ") for code in BinanceUsdmInstrumentMetadataFailureCode
}


def _text(name: str, value: object) -> str:
    if (
        type(value) is not str
        or not value
        or value.strip() != value
        or unicodedata.normalize("NFC", value) != value
    ):
        raise ValueError(f"{name} must be non-empty canonical text")
    return value


def _instant(name: str, value: object) -> UtcInstant:
    if type(value) is not UtcInstant:
        raise TypeError(f"{name} must be exact UtcInstant")
    return value


@dataclass(frozen=True, slots=True)
class BinanceUsdmInstrumentMetadataSourceRef:
    source_key: str
    source_hash: str

    def __post_init__(self) -> None:
        _text("source_key", self.source_key)
        if type(self.source_hash) is not str or _SHA256.fullmatch(self.source_hash) is None:
            raise ValueError("source_hash must be canonical sha256")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_instrument_metadata_source_ref",
            "schema_version": _SCHEMA_VERSION,
            "source_key": self.source_key,
            "source_hash": self.source_hash,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmInstrumentMetadataRevision:
    revision_id: str
    supersedes_revision_id: str | None
    stable_instrument_key: str
    symbol: str
    pair: str
    contract_type: str
    status: str
    onboard_at: UtcInstant
    delivery_at: UtcInstant
    base_asset: str
    quote_asset: str
    margin_asset: str
    effective_from: UtcInstant
    available_at: UtcInstant
    source_ref: BinanceUsdmInstrumentMetadataSourceRef

    def __post_init__(self) -> None:
        _text("revision_id", self.revision_id)
        if self.supersedes_revision_id is not None:
            _text("supersedes_revision_id", self.supersedes_revision_id)
        if (
            type(self.stable_instrument_key) is not str
            or _STABLE_KEY.fullmatch(self.stable_instrument_key) is None
        ):
            raise ValueError("stable_instrument_key must be canonical stable text")
        for name in (
            "symbol",
            "pair",
            "contract_type",
            "status",
            "base_asset",
            "quote_asset",
            "margin_asset",
        ):
            _text(name, getattr(self, name))
        _instant("onboard_at", self.onboard_at)
        _instant("delivery_at", self.delivery_at)
        _instant("effective_from", self.effective_from)
        _instant("available_at", self.available_at)
        if self.available_at < self.effective_from:
            raise ValueError("available_at cannot precede effective_from")
        if type(self.source_ref) is not BinanceUsdmInstrumentMetadataSourceRef:
            raise TypeError("source_ref must be exact BinanceUsdmInstrumentMetadataSourceRef")

    @property
    def revision_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_instrument_metadata_revision",
            "schema_version": _SCHEMA_VERSION,
            "revision_id": self.revision_id,
            "supersedes_revision_id": self.supersedes_revision_id,
            "stable_instrument_key": self.stable_instrument_key,
            "symbol": self.symbol,
            "pair": self.pair,
            "contract_type": self.contract_type,
            "status": self.status,
            "onboard_at": self.onboard_at,
            "delivery_at": self.delivery_at,
            "base_asset": self.base_asset,
            "quote_asset": self.quote_asset,
            "margin_asset": self.margin_asset,
            "effective_from": self.effective_from,
            "available_at": self.available_at,
            "source_ref": self.source_ref,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmInstrumentMetadataQuery:
    stable_instrument_key: str
    effective_at: UtcInstant
    captured_at: UtcInstant
    revisions: tuple[BinanceUsdmInstrumentMetadataRevision, ...]

    def __post_init__(self) -> None:
        if (
            type(self.stable_instrument_key) is not str
            or _STABLE_KEY.fullmatch(self.stable_instrument_key) is None
        ):
            raise ValueError("stable_instrument_key must be canonical stable text")
        _instant("effective_at", self.effective_at)
        _instant("captured_at", self.captured_at)
        if type(self.revisions) is not tuple or not all(
            type(value) is BinanceUsdmInstrumentMetadataRevision
            for value in self.revisions
        ):
            raise TypeError("revisions must be a tuple of exact revisions")
        object.__setattr__(
            self,
            "revisions",
            tuple(
                sorted(
                    self.revisions,
                    key=lambda value: (
                        value.effective_from,
                        value.available_at,
                        value.revision_id,
                    ),
                )
            ),
        )

    @property
    def query_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_instrument_metadata_query",
            "schema_version": _SCHEMA_VERSION,
            "stable_instrument_key": self.stable_instrument_key,
            "effective_at": self.effective_at,
            "captured_at": self.captured_at,
            "revision_hashes": [value.revision_hash for value in self.revisions],
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmListingInterval:
    instrument_id: InstrumentId
    listed_at: UtcInstant
    delisted_at: UtcInstant | None

    def __post_init__(self) -> None:
        if type(self.instrument_id) is not InstrumentId:
            raise TypeError("instrument_id must be exact InstrumentId")
        _instant("listed_at", self.listed_at)
        if self.delisted_at is not None:
            _instant("delisted_at", self.delisted_at)
            if self.delisted_at <= self.listed_at:
                raise ValueError("delisted_at must be after listed_at")

    def contains(self, instant: UtcInstant) -> bool:
        _instant("instant", instant)
        return self.listed_at <= instant and (
            self.delisted_at is None or instant < self.delisted_at
        )

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_listing_interval",
            "schema_version": _SCHEMA_VERSION,
            "instrument_id": self.instrument_id,
            "listed_at": self.listed_at,
            "delisted_at": self.delisted_at,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmLinearContractMetadata:
    instrument_id: InstrumentId
    base_currency: CurrencyId
    quote_currency: CurrencyId
    settlement_currency: CurrencyId
    contract_multiplier: Rate

    def __post_init__(self) -> None:
        if type(self.instrument_id) is not InstrumentId:
            raise TypeError("instrument_id must be exact InstrumentId")
        for name in ("base_currency", "quote_currency", "settlement_currency"):
            if type(getattr(self, name)) is not CurrencyId:
                raise TypeError(f"{name} must be exact CurrencyId")
        if self.quote_currency != self.settlement_currency:
            raise ValueError("quote and settlement currency must match")
        expected = Rate(1, Scale(0), "base_quantity_per_contract")
        if type(self.contract_multiplier) is not Rate or self.contract_multiplier != expected:
            raise ValueError("contract_multiplier must be exact one base quantity per contract")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_linear_contract_metadata",
            "schema_version": _SCHEMA_VERSION,
            "instrument_id": self.instrument_id,
            "base_currency": self.base_currency,
            "quote_currency": self.quote_currency,
            "settlement_currency": self.settlement_currency,
            "contract_multiplier": self.contract_multiplier,
        }


@dataclass(frozen=True, slots=True)
class _ResolutionValues:
    visible_revisions: tuple[BinanceUsdmInstrumentMetadataRevision, ...]
    instrument: InstrumentDefinition
    symbol_timeline: SymbolTimeline
    listing_interval: BinanceUsdmListingInterval
    contract_metadata: BinanceUsdmLinearContractMetadata
    active_revision: BinanceUsdmInstrumentMetadataRevision
    active_symbol: str
    active_pair: str
    status: BinanceUsdmContractStatus
    tradable: bool


@dataclass(frozen=True, slots=True)
class BinanceUsdmInstrumentMetadataResolution:
    query: BinanceUsdmInstrumentMetadataQuery
    visible_revisions: tuple[BinanceUsdmInstrumentMetadataRevision, ...]
    instrument: InstrumentDefinition
    symbol_timeline: SymbolTimeline
    listing_interval: BinanceUsdmListingInterval
    contract_metadata: BinanceUsdmLinearContractMetadata
    active_revision: BinanceUsdmInstrumentMetadataRevision
    active_symbol: str
    active_pair: str
    status: BinanceUsdmContractStatus
    tradable: bool

    def __post_init__(self) -> None:
        if type(self.query) is not BinanceUsdmInstrumentMetadataQuery:
            raise TypeError("query must be exact BinanceUsdmInstrumentMetadataQuery")
        failure = _failure_details(self.query)
        if failure is not None:
            raise ValueError("resolution query has a business failure")
        expected = _resolution_values(self.query)
        actual = tuple(getattr(self, name) for name in expected.__dataclass_fields__)
        if actual != tuple(getattr(expected, name) for name in expected.__dataclass_fields__):
            raise ValueError("resolution fields must match embedded query")

    @property
    def resolution_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_instrument_metadata_resolution",
            "schema_version": _SCHEMA_VERSION,
            "query": self.query,
            "visible_revisions": list(self.visible_revisions),
            "instrument": self.instrument,
            "symbol_timeline": self.symbol_timeline,
            "listing_interval": self.listing_interval,
            "contract_metadata": self.contract_metadata,
            "active_revision": self.active_revision,
            "active_symbol": self.active_symbol,
            "active_pair": self.active_pair,
            "status": self.status.value,
            "tradable": self.tradable,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmInstrumentMetadataFailure:
    query: BinanceUsdmInstrumentMetadataQuery
    code: BinanceUsdmInstrumentMetadataFailureCode
    message: str
    subject_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self.query) is not BinanceUsdmInstrumentMetadataQuery:
            raise TypeError("query must be exact BinanceUsdmInstrumentMetadataQuery")
        if type(self.code) is not BinanceUsdmInstrumentMetadataFailureCode:
            raise TypeError("code must be exact BinanceUsdmInstrumentMetadataFailureCode")
        _text("message", self.message)
        if type(self.subject_ids) is not tuple or not all(
            type(value) is str and bool(value) for value in self.subject_ids
        ):
            raise TypeError("subject_ids must be a tuple of non-empty strings")
        expected = _failure_details(self.query)
        if expected != (self.code, self.message, self.subject_ids):
            raise ValueError("failure fields must match embedded query")

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_instrument_metadata_failure",
            "schema_version": _SCHEMA_VERSION,
            "query": self.query,
            "code": self.code.value,
            "message": self.message,
            "subject_ids": list(self.subject_ids),
        }


BinanceUsdmInstrumentMetadataOutcome = ProfilePortOutcome[
    BinanceUsdmInstrumentMetadataResolution,
    BinanceUsdmInstrumentMetadataFailure,
]


def _details(
    code: BinanceUsdmInstrumentMetadataFailureCode,
    *subject_ids: str,
) -> tuple[
    BinanceUsdmInstrumentMetadataFailureCode,
    str,
    tuple[str, ...],
]:
    return code, _FAILURE_MESSAGES[code], tuple(subject_ids)


def _failure_details(
    query: BinanceUsdmInstrumentMetadataQuery,
) -> tuple[
    BinanceUsdmInstrumentMetadataFailureCode,
    str,
    tuple[str, ...],
] | None:
    revisions = query.revisions
    if not revisions:
        return _details(
            BinanceUsdmInstrumentMetadataFailureCode.MISSING_REVISION_SET,
            query.stable_instrument_key,
        )
    revision_ids = tuple(value.revision_id for value in revisions)
    if (
        len(set(revision_ids)) != len(revision_ids)
        or revisions[0].supersedes_revision_id is not None
        or any(
            current.supersedes_revision_id != previous.revision_id
            or current.effective_from <= previous.effective_from
            or current.available_at < previous.available_at
            for previous, current in zip(revisions, revisions[1:])
        )
    ):
        return _details(
            BinanceUsdmInstrumentMetadataFailureCode.INVALID_REVISION_SET,
            *revision_ids,
        )
    visible = tuple(
        value for value in revisions if value.available_at <= query.captured_at
    )
    if not visible:
        return _details(
            BinanceUsdmInstrumentMetadataFailureCode.REVISION_NOT_AVAILABLE,
            query.stable_instrument_key,
        )
    if any(
        value.stable_instrument_key != query.stable_instrument_key
        for value in revisions
    ):
        return _details(
            BinanceUsdmInstrumentMetadataFailureCode.STABLE_IDENTITY_MISMATCH,
            query.stable_instrument_key,
            *revision_ids,
        )
    if any(value.contract_type != "PERPETUAL" for value in visible):
        return _details(
            BinanceUsdmInstrumentMetadataFailureCode.UNSUPPORTED_CONTRACT_TYPE,
            *(value.revision_id for value in visible),
        )
    try:
        statuses = tuple(BinanceUsdmContractStatus(value.status) for value in visible)
    except ValueError:
        return _details(
            BinanceUsdmInstrumentMetadataFailureCode.UNSUPPORTED_CONTRACT_STATUS,
            *(value.revision_id for value in visible),
        )
    currency_rows: list[tuple[CurrencyId, CurrencyId, CurrencyId]] = []
    try:
        for value in visible:
            currency_rows.append(
                (
                    CurrencyId(value.base_asset),
                    CurrencyId(value.quote_asset),
                    CurrencyId(value.margin_asset),
                )
            )
    except ValueError:
        return _details(
            BinanceUsdmInstrumentMetadataFailureCode.INVALID_CURRENCY_CONTEXT,
            *(value.revision_id for value in visible),
        )
    if any(quote != margin for _, quote, margin in currency_rows) or len(
        set(currency_rows)
    ) != 1:
        return _details(
            BinanceUsdmInstrumentMetadataFailureCode.INVALID_CURRENCY_CONTEXT,
            *(value.revision_id for value in visible),
        )
    latest = visible[-1]
    finite_deliveries = {
        value.delivery_at
        for value in visible
        if value.delivery_at != BINANCE_USDM_OPEN_ENDED_DELIVERY_AT
    }
    if (
        latest.onboard_at > visible[0].effective_from
        or any(value.effective_from < latest.onboard_at for value in visible)
        or any(value.delivery_at <= value.onboard_at for value in visible)
        or len(finite_deliveries) > 1
        or (
            finite_deliveries
            and latest.delivery_at == BINANCE_USDM_OPEN_ENDED_DELIVERY_AT
        )
    ):
        return _details(
            BinanceUsdmInstrumentMetadataFailureCode.INVALID_LISTING_INTERVAL,
            *(value.revision_id for value in visible),
        )
    delisted_at = (
        None
        if latest.delivery_at == BINANCE_USDM_OPEN_ENDED_DELIVERY_AT
        else latest.delivery_at
    )
    if query.effective_at < latest.onboard_at or (
        delisted_at is not None and query.effective_at >= delisted_at
    ):
        return _details(
            BinanceUsdmInstrumentMetadataFailureCode.NOT_LISTED_AT_QUERY_INSTANT,
            query.stable_instrument_key,
        )
    symbol_changes = tuple(
        value
        for index, value in enumerate(visible)
        if index == 0 or value.symbol != visible[index - 1].symbol
    )
    if any(
        delisted_at is not None and value.effective_from >= delisted_at
        for value in symbol_changes[1:]
    ):
        return _details(
            BinanceUsdmInstrumentMetadataFailureCode.SYMBOL_TIMELINE_CONFLICT,
            *(value.revision_id for value in symbol_changes),
        )
    source_rows: dict[str, str] = {}
    for value in visible:
        prior = source_rows.setdefault(
            value.source_ref.source_key, value.source_ref.source_hash
        )
        if prior != value.source_ref.source_hash:
            return _details(
                BinanceUsdmInstrumentMetadataFailureCode.METADATA_CONFLICT,
                value.source_ref.source_key,
            )
    _ = statuses
    return None


def _resolution_values(
    query: BinanceUsdmInstrumentMetadataQuery,
) -> _ResolutionValues:
    visible = tuple(
        value for value in query.revisions if value.available_at <= query.captured_at
    )
    latest = visible[-1]
    applicable = tuple(
        value for value in visible if value.effective_from <= query.effective_at
    )
    active = applicable[-1] if applicable else visible[0]
    instrument_id = InstrumentId(VenueId("binance_usdm"), query.stable_instrument_key)
    base = CurrencyId(latest.base_asset)
    quote = CurrencyId(latest.quote_asset)
    margin = CurrencyId(latest.margin_asset)
    instrument = InstrumentDefinition(
        instrument_id=instrument_id,
        instrument_type=InstrumentType.LINEAR_PERPETUAL,
        base_currency=base,
        quote_currency=quote,
        settlement_currency=margin,
    )
    delisted_at = (
        None
        if latest.delivery_at == BINANCE_USDM_OPEN_ENDED_DELIVERY_AT
        else latest.delivery_at
    )
    changes = [
        value
        for index, value in enumerate(visible)
        if index == 0 or value.symbol != visible[index - 1].symbol
    ]
    intervals = tuple(
        SymbolInterval(
            symbol=value.symbol,
            effective_from=latest.onboard_at if index == 0 else value.effective_from,
            effective_until=(
                changes[index + 1].effective_from
                if index + 1 < len(changes)
                else delisted_at
            ),
        )
        for index, value in enumerate(changes)
    )
    listing_interval = BinanceUsdmListingInterval(
        instrument_id=instrument_id,
        listed_at=latest.onboard_at,
        delisted_at=delisted_at,
    )
    contract_metadata = BinanceUsdmLinearContractMetadata(
        instrument_id=instrument_id,
        base_currency=base,
        quote_currency=quote,
        settlement_currency=margin,
        contract_multiplier=Rate(1, Scale(0), "base_quantity_per_contract"),
    )
    status = BinanceUsdmContractStatus(active.status)
    timeline = SymbolTimeline(instrument_id=instrument_id, intervals=intervals)
    return _ResolutionValues(
        visible_revisions=visible,
        instrument=instrument,
        symbol_timeline=timeline,
        listing_interval=listing_interval,
        contract_metadata=contract_metadata,
        active_revision=active,
        active_symbol=timeline.symbol_at(query.effective_at),
        active_pair=active.pair,
        status=status,
        tradable=status is BinanceUsdmContractStatus.TRADING,
    )


@dataclass(frozen=True, slots=True)
class BinanceUsdmInstrumentModel:
    @property
    def component_ref(self) -> ProfileComponentRef:
        digest = canonical_sha256(
            {
                "type": "binance_usdm_instrument_metadata_component",
                "schema_version": _SCHEMA_VERSION,
                "component_key": _COMPONENT_KEY,
                "component_version": 1,
                "algorithm_key": _ALGORITHM_KEY,
                "open_ended_delivery_at": BINANCE_USDM_OPEN_ENDED_DELIVERY_AT,
                "supported_contract_type": "PERPETUAL",
                "supported_statuses": [value.value for value in BinanceUsdmContractStatus],
                "contract_multiplier": Rate(
                    1, Scale(0), "base_quantity_per_contract"
                ),
            }
        )
        return ProfileComponentRef(
            port_type=ProfilePortType.INSTRUMENT_MODEL,
            component_key=_COMPONENT_KEY,
            component_version=1,
            component_digest=digest,
        )

    def resolve_instrument(
        self, query: BinanceUsdmInstrumentMetadataQuery, /
    ) -> BinanceUsdmInstrumentMetadataOutcome:
        if type(query) is not BinanceUsdmInstrumentMetadataQuery:
            raise TypeError("query must be exact BinanceUsdmInstrumentMetadataQuery")
        failure = _failure_details(query)
        if failure is not None:
            code, message, subject_ids = failure
            return ProfilePortOutcome.for_failure(
                self.component_ref,
                query,
                BinanceUsdmInstrumentMetadataFailure(
                    query=query,
                    code=code,
                    message=message,
                    subject_ids=subject_ids,
                ),
            )
        values = _resolution_values(query)
        return ProfilePortOutcome.for_result(
            self.component_ref,
            query,
            BinanceUsdmInstrumentMetadataResolution(
                query=query,
                **{
                    name: getattr(values, name)
                    for name in values.__dataclass_fields__
                },
            ),
        )
