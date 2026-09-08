from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import cast

from crypto_quant_domain import (
    CurrencyId,
    InstrumentCatalog,
    InstrumentDefinition,
    InstrumentId,
    InstrumentType,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    VenueId,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_market_data import (
    MarketBundleCapability,
    MarketBundleManifest,
    MarketBundleRef,
    MarketEvent,
    MarketStreamManifest,
)

from .bundle_validation import validate_market_bundle_v1

_SCHEMA_VERSION = 2
_SUCCESSOR_DECISION_HASH = (
    "sha256:7e8ca1ebf63aeb4f5f36ab72073d258db64083028e6e2f4c1662941bd46c7d62"
)
_RUNNABLE_AUTHORITY_HASH = (
    "sha256:3d19c05e552aa61a7f1ff33bc2451d2d0cc13e0d3ee30acde46462bdfa65becf"
)
_G12I_REPORT_HASH = (
    "sha256:ff09c4ad9f8025e66689387b5132d3d85c4101276fbf7330dd5040af111cc029"
)
_G12I_CANONICAL_FILE_SHA256 = (
    "sha256:9cbfc115e41f56d1e83eac520856c3f529f83972b97111238e5dbb1a68c4eae6"
)
_SOURCE_MANIFEST_HASH = (
    "sha256:d9f73a48eeb8b92600cd7fdd9017ba8b0536654cb466ce57c8bc6695f10271df"
)
_SOURCE_MANIFEST_CONTENT_HASH = (
    "sha256:87e1209b5510e9d5489d414e63c1008117282a57e1d05555113103222f06a505"
)
_SOURCE_STREAM_CONTENT_HASH = (
    "sha256:da735d4545e458f8bb1432008b89e45b7c820812f0fed91ebc6610721ad491a1"
)
_TARGET_STREAM_DIGEST = (
    "sha256:8e4bdddbd91e1bafd65363e133d382673df88e4dc4061d1f0dd776a42afc6cee"
)
_TARGET_EVENT_HASH = (
    "sha256:3fa3dfcd9b2136950f0d734deaa9dcd2a5857d0c4d5dcd63c965190ccd29aa53"
)
_EVENT_HASHES = (
    "sha256:2cec41bfe1d766422f35775163d132de63830d91af511830849255a80b30cfe0",
    "sha256:e490329a4c53c6e4bf2c601292d2bafd38f9ff6deaac7591bcf7ece16259df03",
    "sha256:ba785b15c8de8cfb88af252ac69b0bdf908c3e857762fbb2d0406ecdf795a981",
    "sha256:2599f9b8bc06ab0721f5fec93420d8184344b82fdc317bf6280aff482152e7ff",
    "sha256:6fd28561578cfaad903178f5ff81b24a6beb6a44a6b66b3176e4e6213cb506d8",
    "sha256:7a0ba4ae64b8f8ebc481ce4f696f3141ade9049efec0829dbf4fa0002488b558",
    "sha256:694faea1bc49d81937b18bcc009bd914c306638d6155ff01388468d5dbfb7917",
    "sha256:8dad04b9a3fc4c8e6b3b15bad66327c19de858baa307c0f2938931185800e1b0",
    "sha256:4d1dcff1609326d7958719b0f8ba5e00bcc15c5898350685f9036630ed811bd1",
    "sha256:6c02d071cfdee10079274c9c6fcdcdd33a73af50d38a7dedcd3e5b08b4a0cd18",
    "sha256:f3e30d0cc2d4097ba3ed8fe87a902055753e12707e9bea6d4ecd9657cd270172",
    "sha256:263ad147cbb51142f45ec244dfa12af8513829be24a707a74cad09906855d003",
    "sha256:98a6c55bc42b178482625eec8dd8ec774f06e2b019b0dbc7ec31c9c7c2616f71",
    "sha256:31102dbaab5653ad78a430f2890a739dbf10b84b2531ba9f4d1d530bbfce75dc",
    "sha256:f4d067480c920169754bfcbc8a5ade48368d4eed97776d1513ba1ae6947c1ce9",
    "sha256:6caa4852a99ab8f6e32743e01f013d3216db140ce9c42950827cfd9a4250a23c",
    "sha256:f04029ea0a17ed715df0d842f0079d84a1b227ab2fe8e769df7ebf8ae3665def",
    "sha256:74cdf0ce0401c36aaeaa97e2b6b5fe0cee4861c41a80cba1f5639e64b828e44b",
    "sha256:98c41ec26cd76f73e66c8ba20a8a3b410940c01eeb886eec6f9034687e4fb5d5",
)
_INSTRUMENT = InstrumentId(VenueId("xshe"), "000001")
_CATALOG_HASH = (
    "sha256:99df0de0dc3008cf557bb7634caf483fae27488c75016421218100df6a77a6cc"
)
_SOURCE_STREAM_KEY = "tushare_cn_a_share.daily.publication.xshe.000001.v1"
_SOURCE_EVENT_TYPE = "tushare_cn_a_share_daily_publication.v1"
_SOURCE_CAPABILITY = MarketBundleCapability("tushare_cn_a_share.daily-publications", 1)
_PROJECTION_STREAM_KEY = "g12m.tushare.fixed-singleton.bar-open.v2"
_PROJECTION_EVENT_TYPE = "bar_open"
_PROJECTION_CAPABILITY = MarketBundleCapability("bar_open", 1)
_PROJECTION_PHASE = TimelinePhase(20, "bar_open")
_PROJECTION_SOURCE_KEY = "g12m.tushare.fixed-singleton.bar-open-projection.v2"
_TARGET_STREAM_KEY = "cn-a-share-fixed-singleton-zero-target-v1"
_TARGET_EVENT_TYPE = "strategy_decision_candidate"
_TARGET_CAPABILITY = MarketBundleCapability("precomputed_target_stream", 1)
_DECISION_NS = 1_787_292_861_381_694_497
_COVERAGE_START = UtcInstant(1_783_267_200_000_000_000)
_COVERAGE_END_EXCLUSIVE = UtcInstant(_DECISION_NS + 1)
_BUNDLE_KEY = "g12m-tushare-fixed-singleton-execution-bundle-v2"


def _catalog() -> InstrumentCatalog:
    currency = CurrencyId("CNY")
    return InstrumentCatalog(
        currencies=(currency,),
        instruments=(
            InstrumentDefinition(
                _INSTRUMENT,
                InstrumentType.EQUITY,
                None,
                currency,
                currency,
            ),
        ),
        symbol_timelines=(),
    )


def _clone_event(value: object) -> MarketEvent | None:
    if type(value) is not MarketEvent:
        return None
    event = cast(MarketEvent, value)
    try:
        if (
            type(event.capability) is not MarketBundleCapability
            or type(event.event_time) is not UtcInstant
            or type(event.available_time) is not UtcInstant
            or type(event.phase) is not TimelinePhase
            or type(event.source_sequence) is not SourceSequence
            or (
                event.instrument_id is not None
                and (
                    type(event.instrument_id) is not InstrumentId
                    or type(event.instrument_id.venue) is not VenueId
                )
            )
        ):
            return None
        instrument = (
            None
            if event.instrument_id is None
            else InstrumentId(
                VenueId(event.instrument_id.venue.value),
                event.instrument_id.stable_key,
            )
        )
        rebuilt = MarketEvent(
            event_id=event.event_id,
            stream_key=event.stream_key,
            event_type=event.event_type,
            capability=MarketBundleCapability(
                event.capability.key, event.capability.version
            ),
            instrument_id=instrument,
            event_time=UtcInstant(event.event_time.epoch_nanoseconds),
            available_time=UtcInstant(event.available_time.epoch_nanoseconds),
            phase=TimelinePhase(event.phase.rank, event.phase.code),
            source_sequence=SourceSequence(event.source_sequence.value),
            revision_id=event.revision_id,
            supersedes_revision_id=event.supersedes_revision_id,
            source_key=event.source_key,
            source_hash=event.source_hash,
            payload=event.payload,
        )
        if canonical_bytes(rebuilt) != canonical_bytes(event):
            return None
        return rebuilt
    except Exception:  # noqa: BLE001 -- hostile constructor bypass must fail closed.
        return None


def _clone_manifest(value: object) -> MarketBundleManifest | None:
    if type(value) is not MarketBundleManifest:
        return None
    manifest = cast(MarketBundleManifest, value)
    try:
        if (
            type(manifest.coverage_start) is not UtcInstant
            or type(manifest.coverage_end_exclusive) is not UtcInstant
            or type(manifest.capabilities) is not tuple
            or type(manifest.streams) is not tuple
            or any(
                type(item) is not MarketBundleCapability
                for item in manifest.capabilities
            )
            or any(type(item) is not MarketStreamManifest for item in manifest.streams)
        ):
            return None
        rebuilt = MarketBundleManifest.build(
            bundle_key=manifest.bundle_key,
            schema_version=manifest.schema_version,
            coverage_start=UtcInstant(manifest.coverage_start.epoch_nanoseconds),
            coverage_end_exclusive=UtcInstant(
                manifest.coverage_end_exclusive.epoch_nanoseconds
            ),
            instrument_catalog_hash=manifest.instrument_catalog_hash,
            capabilities=tuple(
                MarketBundleCapability(item.key, item.version)
                for item in manifest.capabilities
            ),
            streams=tuple(
                MarketStreamManifest(
                    item.stream_key,
                    item.event_type,
                    MarketBundleCapability(
                        item.capability.key, item.capability.version
                    ),
                    item.event_count,
                    item.content_hash,
                )
                for item in manifest.streams
            ),
        )
        if canonical_bytes(rebuilt) != canonical_bytes(manifest):
            return None
        return rebuilt
    except Exception:  # noqa: BLE001 -- hostile constructor bypass must fail closed.
        return None


def _accepted_source_manifest(value: object) -> MarketBundleManifest | None:
    manifest = _clone_manifest(value)
    if manifest is None:
        return None
    if (
        manifest.bundle_key
        != "tushare-cn-a-share-daily-000001-20260706-20260730-source-bounded-v2"
        or manifest.schema_version != 1
        or manifest.coverage_start != _COVERAGE_START
        or manifest.coverage_end_exclusive != UtcInstant(1_785_427_200_000_000_000)
        or manifest.instrument_catalog_hash != "sha256:" + "0" * 64
        or manifest.capabilities != (_SOURCE_CAPABILITY,)
        or len(manifest.streams) != 1
        or manifest.streams[0]
        != MarketStreamManifest(
            _SOURCE_STREAM_KEY,
            _SOURCE_EVENT_TYPE,
            _SOURCE_CAPABILITY,
            len(_EVENT_HASHES),
            _SOURCE_STREAM_CONTENT_HASH,
        )
        or manifest.content_hash != _SOURCE_MANIFEST_CONTENT_HASH
        or MarketBundleRef.from_manifest(manifest).manifest_hash
        != _SOURCE_MANIFEST_HASH
    ):
        return None
    return manifest


def _accepted_source_events(value: object) -> tuple[MarketEvent, ...] | None:
    if type(value) is not tuple or len(value) != len(_EVENT_HASHES):
        return None
    rebuilt = tuple(_clone_event(item) for item in cast(tuple[object, ...], value))
    if any(item is None for item in rebuilt):
        return None
    events = cast(tuple[MarketEvent, ...], rebuilt)
    if (
        tuple(event.event_hash for event in events) != _EVENT_HASHES
        or canonical_sha256(events) != _SOURCE_STREAM_CONTENT_HASH
        or any(
            event.stream_key != _SOURCE_STREAM_KEY
            or event.event_type != _SOURCE_EVENT_TYPE
            or event.capability != _SOURCE_CAPABILITY
            or event.instrument_id != _INSTRUMENT
            or event.phase != TimelinePhase(0, "market_data")
            or event.source_sequence != SourceSequence(0)
            for event in events
        )
        or tuple(event.ordering_key for event in events)
        != tuple(sorted(event.ordering_key for event in events))
    ):
        return None
    return events


def _accepted_target_events(value: object) -> tuple[MarketEvent, ...] | None:
    if type(value) is not tuple or len(value) != 1:
        return None
    event = _clone_event(cast(tuple[object, ...], value)[0])
    if event is None:
        return None
    stream_body = {
        "type": "precomputed_target_stream",
        "schema_version": 1,
        "stream_key": _TARGET_STREAM_KEY,
        "events": (event,),
    }
    if (
        event.event_hash != _TARGET_EVENT_HASH
        or canonical_sha256(stream_body) != _TARGET_STREAM_DIGEST
        or event.event_id != _TARGET_STREAM_KEY
        or event.stream_key != _TARGET_STREAM_KEY
        or event.event_type != _TARGET_EVENT_TYPE
        or event.capability != _TARGET_CAPABILITY
        or event.instrument_id is not None
        or event.event_time != UtcInstant(_DECISION_NS)
        or event.available_time != UtcInstant(_DECISION_NS)
        or event.phase != TimelinePhase(30, "strategy_decision")
        or event.source_sequence != SourceSequence(1)
    ):
        return None
    return (event,)


def _source_price(value: MarketEvent) -> tuple[int, int, str, str, str, str] | None:
    try:
        payload = value.payload
        if set(payload) != {
            "execution_reference",
            "normalization_hash",
            "qualification",
            "raw_bar",
            "source_trace",
            "valuation",
        }:
            return None
        reference = payload["execution_reference"]
        raw = payload["raw_bar"]
        trace = payload["source_trace"]
        if (
            not isinstance(reference, Mapping)
            or not isinstance(raw, Mapping)
            or not isinstance(trace, Mapping)
        ):
            return None
        expected_reference_keys = {
            "type",
            "schema_version",
            "instrument_id",
            "price_purpose",
            "available_time",
            "bucket",
            "open_price",
            "high_price",
            "low_price",
            "close_price",
            "volume",
            "amount",
            "raw_bar_hash",
            "projection_hash",
        }
        if set(reference) != expected_reference_keys:
            return None
        open_price = reference["open_price"]
        if not isinstance(open_price, Mapping) or set(open_price) != {
            "type",
            "units",
            "scale",
            "instrument_id",
            "quote_currency",
        }:
            return None
        units = open_price["units"]
        scale = open_price["scale"]
        currency = open_price["quote_currency"]
        provider_date = raw.get("provider_trade_date")
        raw_hash = reference["raw_bar_hash"]
        projection_hash = reference["projection_hash"]
        if (
            reference["type"] != "tushare_cn_a_share_daily_execution_reference"
            or reference["schema_version"] != 1
            or reference["price_purpose"] != "execution_reference"
            or reference["instrument_id"] != _INSTRUMENT.to_canonical_dict()
            or reference["available_time"] != value.available_time.to_canonical_dict()
            or open_price["type"] != "price"
            or open_price["instrument_id"] != str(_INSTRUMENT)
            or type(units) is not int
            or units <= 0
            or type(scale) is not int
            or scale < 0
            or currency != "CNY"
            or type(provider_date) is not str
            or len(provider_date) != 8
            or type(raw_hash) is not str
            or type(projection_hash) is not str
            or raw.get("raw_bar_hash") != raw_hash
            or trace.get("raw_bar_hash") != raw_hash
            or trace.get("source_key") != value.source_key
            or trace.get("revision_id") != value.revision_id
        ):
            return None
        return units, scale, currency, provider_date, raw_hash, projection_hash
    except Exception:  # noqa: BLE001 -- malformed accepted payloads fail closed.
        return None


class G12MTushareExecutionBundleFailureCodeV2(str, Enum):
    AUTHORITY_OR_SOURCE_MANIFEST = "authority_or_source_manifest"
    SOURCE_MEMBERSHIP = "source_membership"
    TARGET = "target"
    SOURCE_PAYLOAD = "source_payload"
    PROJECTION = "projection"
    CATALOG_OR_MANIFEST = "catalog_or_manifest"
    CANONICAL_RECONSTRUCTION = "canonical_reconstruction"


@dataclass(frozen=True, slots=True)
class G12MTushareExecutionBundleFailureV2:
    code: G12MTushareExecutionBundleFailureCodeV2

    def __post_init__(self) -> None:
        if type(self.code) is not G12MTushareExecutionBundleFailureCodeV2:
            raise TypeError("code must be exact G12M execution Bundle failure code")

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self._body())

    def _body(self) -> dict[str, object]:
        return {
            "type": "g12m_tushare_fixed_singleton_execution_bundle_failure_v2",
            "schema_version": _SCHEMA_VERSION,
            "code": self.code.value,
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "failure_hash": self.failure_hash}


@dataclass(frozen=True, slots=True)
class G12MTushareBarOpenProjectionLineageV2:
    source_event_id: str
    source_event_hash: str
    source_revision_id: str
    source_event_time: UtcInstant
    source_available_time: UtcInstant
    source_key: str
    source_hash: str
    instrument_id: InstrumentId
    provider_trade_date: str
    raw_bar_hash: str
    source_projection_hash: str
    open_price_units: int
    open_price_scale: int
    open_price_quote_currency: str
    projection_event_id: str
    projection_event_hash: str
    projection_revision_id: str
    projection_source_key: str
    projection_source_hash: str
    lineage_hash: str = field(init=False)

    def __post_init__(self) -> None:
        if (
            type(self.source_event_time) is not UtcInstant
            or type(self.source_available_time) is not UtcInstant
            or type(self.instrument_id) is not InstrumentId
            or type(self.instrument_id.venue) is not VenueId
            or self.instrument_id != _INSTRUMENT
            or type(self.open_price_units) is not int
            or self.open_price_units <= 0
            or type(self.open_price_scale) is not int
            or self.open_price_scale < 0
            or self.open_price_quote_currency != "CNY"
            or type(self.provider_trade_date) is not str
            or len(self.provider_trade_date) != 8
        ):
            raise ValueError("lineage primitive binding mismatch")
        for name in (
            "source_event_id",
            "source_revision_id",
            "source_key",
            "provider_trade_date",
            "projection_event_id",
            "projection_revision_id",
            "projection_source_key",
        ):
            value = getattr(self, name)
            if type(value) is not str or not value or value != value.strip():
                raise ValueError(f"{name} must be canonical text")
        for name in (
            "source_event_hash",
            "source_hash",
            "raw_bar_hash",
            "source_projection_hash",
            "projection_event_hash",
            "projection_source_hash",
        ):
            value = getattr(self, name)
            if (
                type(value) is not str
                or len(value) != 71
                or not value.startswith("sha256:")
            ):
                raise ValueError(f"{name} must be canonical sha256")
        object.__setattr__(self, "lineage_hash", canonical_sha256(self._body()))

    def _body(self) -> dict[str, object]:
        return {
            "type": "g12m_tushare_bar_open_projection_lineage_v2",
            "schema_version": _SCHEMA_VERSION,
            "source_event_id": self.source_event_id,
            "source_event_hash": self.source_event_hash,
            "source_revision_id": self.source_revision_id,
            "source_event_time": self.source_event_time,
            "source_available_time": self.source_available_time,
            "source_key": self.source_key,
            "source_hash": self.source_hash,
            "instrument_id": self.instrument_id,
            "provider_trade_date": self.provider_trade_date,
            "raw_bar_hash": self.raw_bar_hash,
            "source_projection_hash": self.source_projection_hash,
            "open_price_units": self.open_price_units,
            "open_price_scale": self.open_price_scale,
            "open_price_quote_currency": self.open_price_quote_currency,
            "selected_open_price": {
                "type": "price",
                "units": self.open_price_units,
                "scale": self.open_price_scale,
                "instrument_id": str(self.instrument_id),
                "quote_currency": self.open_price_quote_currency,
            },
            "projection_event_id": self.projection_event_id,
            "projection_event_hash": self.projection_event_hash,
            "projection_revision_id": self.projection_revision_id,
            "projection_source_key": self.projection_source_key,
            "projection_source_hash": self.projection_source_hash,
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "lineage_hash": self.lineage_hash}


@dataclass(frozen=True, slots=True)
class G12MTushareFixedSingletonExecutionBundleResultV2:
    source_events: tuple[MarketEvent, ...]
    projection_events: tuple[MarketEvent, ...]
    target_events: tuple[MarketEvent, ...]
    lineage_records: tuple[G12MTushareBarOpenProjectionLineageV2, ...]
    lineage_hash: str
    instrument_catalog: InstrumentCatalog
    instrument_catalog_hash: str
    manifest: MarketBundleManifest
    bundle_ref: MarketBundleRef
    publication_hash: str = field(init=False)
    report_hash: str = field(init=False)

    def __post_init__(self) -> None:
        if not _result_matches(self):
            raise ValueError("execution Bundle result canonical binding mismatch")
        publication_hash = canonical_sha256(self._publication_body())
        object.__setattr__(self, "publication_hash", publication_hash)
        object.__setattr__(
            self,
            "report_hash",
            canonical_sha256({**self._body(), "publication_hash": publication_hash}),
        )

    @property
    def source_stream_payload(self) -> bytes:
        return canonical_bytes(self.source_events)

    @property
    def projection_stream_payload(self) -> bytes:
        return canonical_bytes(self.projection_events)

    @property
    def target_stream_payload(self) -> bytes:
        return canonical_bytes(self.target_events)

    @property
    def stream_payloads(self) -> dict[str, bytes]:
        return {
            _SOURCE_STREAM_KEY: self.source_stream_payload,
            _PROJECTION_STREAM_KEY: self.projection_stream_payload,
            _TARGET_STREAM_KEY: self.target_stream_payload,
        }

    def _body(self) -> dict[str, object]:
        return {
            "type": "g12m_tushare_fixed_singleton_execution_bundle_result_v2",
            "schema_version": _SCHEMA_VERSION,
            "successor_prerequisite_decision_hash": _SUCCESSOR_DECISION_HASH,
            "runnable_authority_hash": _RUNNABLE_AUTHORITY_HASH,
            "g12i_report_hash": _G12I_REPORT_HASH,
            "g12i_canonical_file_sha256": _G12I_CANONICAL_FILE_SHA256,
            "accepted_source_manifest_hash": _SOURCE_MANIFEST_HASH,
            "accepted_source_stream_content_hash": _SOURCE_STREAM_CONTENT_HASH,
            "target_stream_digest": _TARGET_STREAM_DIGEST,
            "source_events": self.source_events,
            "projection_events": self.projection_events,
            "target_events": self.target_events,
            "lineage_records": self.lineage_records,
            "lineage_hash": self.lineage_hash,
            "instrument_catalog": self.instrument_catalog,
            "instrument_catalog_hash": self.instrument_catalog_hash,
            "manifest": self.manifest,
            "bundle_ref": self.bundle_ref,
        }

    def _publication_body(self) -> dict[str, object]:
        return {
            "type": "g12m_tushare_fixed_singleton_execution_bundle_publication_v2",
            "schema_version": _SCHEMA_VERSION,
            "successor_prerequisite_decision_hash": _SUCCESSOR_DECISION_HASH,
            "runnable_authority_hash": _RUNNABLE_AUTHORITY_HASH,
            "bundle_ref": self.bundle_ref,
            "manifest_content_hash": self.manifest.content_hash,
            "instrument_catalog_hash": self.instrument_catalog_hash,
            "lineage_hash": self.lineage_hash,
            "stream_content_hashes": tuple(
                stream.content_hash for stream in self.manifest.streams
            ),
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            **self._body(),
            "publication_hash": self.publication_hash,
            "report_hash": self.report_hash,
        }


@dataclass(frozen=True, slots=True)
class G12MTushareFixedSingletonExecutionBundleOutcomeV2:
    result: G12MTushareFixedSingletonExecutionBundleResultV2 | None = None
    failure: G12MTushareExecutionBundleFailureV2 | None = None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.failure is None):
            raise ValueError("outcome requires exactly one result or failure")
        if (
            self.result is not None
            and type(self.result)
            is not G12MTushareFixedSingletonExecutionBundleResultV2
        ):
            raise TypeError("result must be exact G12M execution Bundle result")
        if (
            self.failure is not None
            and type(self.failure) is not G12MTushareExecutionBundleFailureV2
        ):
            raise TypeError("failure must be exact G12M execution Bundle failure")


def _lineage_preimage(
    source: MarketEvent,
    selected: tuple[int, int, str, str, str, str],
) -> dict[str, object]:
    units, scale, currency, provider_date, raw_hash, projection_hash = selected
    return {
        "type": "g12m_tushare_bar_open_projection_lineage_preimage_v2",
        "schema_version": _SCHEMA_VERSION,
        "source_event_id": source.event_id,
        "source_event_hash": source.event_hash,
        "source_revision_id": source.revision_id,
        "source_event_time": source.event_time,
        "source_available_time": source.available_time,
        "source_key": source.source_key,
        "source_hash": source.source_hash,
        "instrument_id": source.instrument_id,
        "provider_trade_date": provider_date,
        "raw_bar_hash": raw_hash,
        "source_projection_hash": projection_hash,
        "open_price": {
            "type": "price",
            "units": units,
            "scale": scale,
            "instrument_id": str(_INSTRUMENT),
            "quote_currency": currency,
        },
    }


def _project(
    source: MarketEvent,
    selected: tuple[int, int, str, str, str, str],
    index: int,
) -> tuple[MarketEvent, G12MTushareBarOpenProjectionLineageV2]:
    preimage = _lineage_preimage(source, selected)
    event_identity = canonical_sha256(
        {"type": "g12m_tushare_bar_open_event_identity_v2", "lineage": preimage}
    )
    revision_identity = canonical_sha256(
        {"type": "g12m_tushare_bar_open_revision_identity_v2", "lineage": preimage}
    )
    source_identity = canonical_sha256(
        {"type": "g12m_tushare_bar_open_source_identity_v2", "lineage": preimage}
    )
    units, scale, currency, provider_date, raw_hash, projection_hash = selected
    event = MarketEvent(
        event_id="g12m-tushare-bar-open-v2:" + event_identity,
        stream_key=_PROJECTION_STREAM_KEY,
        event_type=_PROJECTION_EVENT_TYPE,
        capability=_PROJECTION_CAPABILITY,
        instrument_id=_INSTRUMENT,
        event_time=source.available_time,
        available_time=source.available_time,
        phase=_PROJECTION_PHASE,
        source_sequence=SourceSequence(index),
        revision_id=revision_identity,
        supersedes_revision_id=None,
        source_key=_PROJECTION_SOURCE_KEY,
        source_hash=source_identity,
        payload={
            "schema_version": 1,
            "bar_kind": "real",
            "open_price": {
                "units": units,
                "scale": scale,
                "quote_currency": currency,
            },
        },
    )
    lineage = G12MTushareBarOpenProjectionLineageV2(
        source_event_id=source.event_id,
        source_event_hash=source.event_hash,
        source_revision_id=source.revision_id,
        source_event_time=source.event_time,
        source_available_time=source.available_time,
        source_key=source.source_key,
        source_hash=source.source_hash,
        instrument_id=_INSTRUMENT,
        provider_trade_date=provider_date,
        raw_bar_hash=raw_hash,
        source_projection_hash=projection_hash,
        open_price_units=units,
        open_price_scale=scale,
        open_price_quote_currency=currency,
        projection_event_id=event.event_id,
        projection_event_hash=event.event_hash,
        projection_revision_id=event.revision_id,
        projection_source_key=event.source_key,
        projection_source_hash=event.source_hash,
    )
    return event, lineage


def _build_manifest(events: tuple[MarketEvent, ...]) -> MarketBundleManifest | None:
    outcome = validate_market_bundle_v1(
        bundle_key=_BUNDLE_KEY,
        schema_version=1,
        coverage_start=_COVERAGE_START,
        coverage_end_exclusive=_COVERAGE_END_EXCLUSIVE,
        instrument_catalog_hash=_CATALOG_HASH,
        events=events,
    )
    if outcome.failure is not None or outcome.manifest is None:
        return None
    manifest = outcome.manifest
    expected = {
        (_SOURCE_STREAM_KEY, _SOURCE_CAPABILITY, len(_EVENT_HASHES)),
        (_PROJECTION_STREAM_KEY, _PROJECTION_CAPABILITY, len(_EVENT_HASHES)),
        (_TARGET_STREAM_KEY, _TARGET_CAPABILITY, 1),
    }
    if (
        len(manifest.capabilities) != 3
        or len(manifest.streams) != 3
        or {
            (stream.stream_key, stream.capability, stream.event_count)
            for stream in manifest.streams
        }
        != expected
    ):
        return None
    return manifest


def _result_matches(value: object) -> bool:
    if type(value) is not G12MTushareFixedSingletonExecutionBundleResultV2:
        return False
    result = cast(G12MTushareFixedSingletonExecutionBundleResultV2, value)
    try:
        source = _accepted_source_events(result.source_events)
        target = _accepted_target_events(result.target_events)
        if source is None or target is None:
            return False
        selected = tuple(_source_price(event) for event in source)
        if any(item is None for item in selected):
            return False
        rebuilt_pairs = tuple(
            _project(event, cast(tuple[int, int, str, str, str, str], item), index)
            for index, (event, item) in enumerate(zip(source, selected, strict=True))
        )
        projections = tuple(item[0] for item in rebuilt_pairs)
        lineages = tuple(item[1] for item in rebuilt_pairs)
        catalog = _catalog()
        manifest = _build_manifest((*source, *projections, *target))
        if manifest is None:
            return False
        return (
            type(result.projection_events) is tuple
            and all(type(item) is MarketEvent for item in result.projection_events)
            and canonical_bytes(result.projection_events)
            == canonical_bytes(projections)
            and type(result.lineage_records) is tuple
            and all(
                type(item) is G12MTushareBarOpenProjectionLineageV2
                for item in result.lineage_records
            )
            and canonical_bytes(result.lineage_records) == canonical_bytes(lineages)
            and result.lineage_hash
            == canonical_sha256(
                {
                    "type": "g12m_tushare_bar_open_projection_lineage_set_v2",
                    "schema_version": _SCHEMA_VERSION,
                    "records": lineages,
                }
            )
            and type(result.instrument_catalog) is InstrumentCatalog
            and canonical_bytes(result.instrument_catalog) == canonical_bytes(catalog)
            and result.instrument_catalog_hash
            == canonical_sha256(catalog)
            == _CATALOG_HASH
            and type(result.manifest) is MarketBundleManifest
            and canonical_bytes(result.manifest) == canonical_bytes(manifest)
            and type(result.bundle_ref) is MarketBundleRef
            and result.bundle_ref == MarketBundleRef.from_manifest(manifest)
        )
    except Exception:  # noqa: BLE001 -- hostile result graphs fail closed.
        return False


def _failed(
    code: G12MTushareExecutionBundleFailureCodeV2,
) -> G12MTushareFixedSingletonExecutionBundleOutcomeV2:
    return G12MTushareFixedSingletonExecutionBundleOutcomeV2(
        failure=G12MTushareExecutionBundleFailureV2(code)
    )


def build_g12m_tushare_fixed_singleton_execution_bundle_v2(
    *,
    successor_prerequisite_decision_hash: str,
    runnable_authority_hash: str,
    source_manifest: MarketBundleManifest,
    source_events: tuple[MarketEvent, ...],
    target_events: tuple[MarketEvent, ...],
) -> G12MTushareFixedSingletonExecutionBundleOutcomeV2:
    if (
        type(successor_prerequisite_decision_hash) is not str
        or successor_prerequisite_decision_hash != _SUCCESSOR_DECISION_HASH
        or type(runnable_authority_hash) is not str
        or runnable_authority_hash != _RUNNABLE_AUTHORITY_HASH
        or _accepted_source_manifest(source_manifest) is None
    ):
        return _failed(
            G12MTushareExecutionBundleFailureCodeV2.AUTHORITY_OR_SOURCE_MANIFEST
        )

    trusted_source = _accepted_source_events(source_events)
    if trusted_source is None:
        return _failed(G12MTushareExecutionBundleFailureCodeV2.SOURCE_MEMBERSHIP)

    trusted_target = _accepted_target_events(target_events)
    if trusted_target is None:
        return _failed(G12MTushareExecutionBundleFailureCodeV2.TARGET)

    selected = tuple(_source_price(event) for event in trusted_source)
    if any(item is None for item in selected):
        return _failed(G12MTushareExecutionBundleFailureCodeV2.SOURCE_PAYLOAD)

    try:
        pairs = tuple(
            _project(event, cast(tuple[int, int, str, str, str, str], item), index)
            for index, (event, item) in enumerate(
                zip(trusted_source, selected, strict=True)
            )
        )
        projection_events = tuple(item[0] for item in pairs)
        lineage_records = tuple(item[1] for item in pairs)
        if len(projection_events) != len(_EVENT_HASHES) or any(
            event.event_time != source.available_time
            or event.available_time != source.available_time
            or event.phase.rank <= source.phase.rank
            or event.timeline_instant >= trusted_target[0].timeline_instant
            for source, event in zip(trusted_source, projection_events, strict=True)
        ):
            raise ValueError("projection causality mismatch")
    except Exception:  # noqa: BLE001 -- projection is atomic and fail closed.
        return _failed(G12MTushareExecutionBundleFailureCodeV2.PROJECTION)

    try:
        catalog = _catalog()
        if canonical_sha256(catalog) != _CATALOG_HASH:
            raise ValueError("catalog identity mismatch")
        manifest = _build_manifest(
            (*trusted_source, *projection_events, *trusted_target)
        )
        if manifest is None:
            raise ValueError("manifest construction failed")
        bundle_ref = MarketBundleRef.from_manifest(manifest)
        lineage_hash = canonical_sha256(
            {
                "type": "g12m_tushare_bar_open_projection_lineage_set_v2",
                "schema_version": _SCHEMA_VERSION,
                "records": lineage_records,
            }
        )
    except Exception:  # noqa: BLE001 -- catalog/manifest construction is atomic.
        return _failed(G12MTushareExecutionBundleFailureCodeV2.CATALOG_OR_MANIFEST)

    try:
        result = G12MTushareFixedSingletonExecutionBundleResultV2(
            source_events=trusted_source,
            projection_events=projection_events,
            target_events=trusted_target,
            lineage_records=lineage_records,
            lineage_hash=lineage_hash,
            instrument_catalog=catalog,
            instrument_catalog_hash=_CATALOG_HASH,
            manifest=manifest,
            bundle_ref=bundle_ref,
        )
        if not _result_matches(result):
            raise ValueError("canonical result reconstruction mismatch")
    except Exception:  # noqa: BLE001 -- no partial result escapes reconstruction.
        return _failed(G12MTushareExecutionBundleFailureCodeV2.CANONICAL_RECONSTRUCTION)
    return G12MTushareFixedSingletonExecutionBundleOutcomeV2(result=result)
