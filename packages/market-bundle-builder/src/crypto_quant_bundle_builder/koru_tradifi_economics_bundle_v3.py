"""Target-free publication of the KORU TradFi economics market bundle."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Protocol, runtime_checkable

from crypto_quant_domain import (
    ArtifactEnvelope,
    ArtifactReadResult,
    ArtifactRef,
    InstrumentId,
    Money,
    Scale,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    VenueId,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_market_data import (
    LocalMarketBundleReader,
    MarketBundleCapability,
    MarketBundleManifest,
    MarketBundleRef,
    MarketEvent,
    MarketStreamManifest,
)

from .binance_usdm_koru_tradifi_source_projection_v2 import (
    BinanceUsdmKoruTradifiSourceProjectionResultV2,
    build_binance_usdm_koru_source_profile_authority_v2,
)
from .binance_usdm_koru_tradifi_source_projection_v2 import (
    _trusted_result as _trusted_source_projection,
)
from .local_market_bundle_repository import (
    LocalMarketBundleRepository,
    LocalMarketBundleRepositoryConfig,
)

_SCHEMA_VERSION = 3
_INSTRUMENT = InstrumentId(VenueId("binance_usdm"), "koru-usdt-tradifi-perpetual")
_INSTRUMENT_WIRE = _INSTRUMENT.to_canonical_dict()
_BOUND_PRICE_PURPOSES = ("execution_reference", "liquidation", "margin", "valuation")
_PRICE_PURPOSE_SOURCE_STREAMS = {
    "execution_reference": "binance_usdm.aggregate_trades.execution_reference.koruusdt.tradifi.v1",
    "liquidation": "binance_usdm.mark_price.liquidation.koruusdt.1h.v1",
    "margin": "binance_usdm.mark_price.margin.koruusdt.1h.v1",
    "valuation": "binance_usdm.mark_price.valuation.koruusdt.1h.v1",
}
_REQUIRED_ACCOUNT = "account-1"
_REQUIRED_EQUITY = Money(1_000_000_000_000, Scale(8), "USDT")
_REQUIRED_ALLOCATION = "1"
_REQUIRED_POSITION_NOTIONAL = "1000"
_SOURCE_PROFILE_ARTIFACT = "binance_usdm_koru_source_profile_authority"
_FUNDING_STREAM = "binance_usdm.funding_history.publications.koruusdt.v1"
_ECONOMICS_STREAM = "binance_usdm.tradifi.economics_authority.koruusdt.v3"
_ECONOMICS_EVENT = "koru_tradifi_economics_authority_v3"
_ECONOMICS_CAPABILITY = MarketBundleCapability("binance_usdm.tradifi.economics-authority", 1)
_PRICE_STREAM = "binance_usdm.tradifi.price_purpose.authority.koruusdt.v3"
_PRICE_EVENT = "binance_usdm_tradifi_price_purpose_binding_v3"
_PRICE_CAPABILITY = MarketBundleCapability("binance_usdm.price-purpose-streams", 1)
_ACCOUNT_STREAM = "binance_usdm.tradifi.account.authority.koruusdt.v3"
_ACCOUNT_EVENT = "account_financial_event"
_ACCOUNT_CAPABILITY = MarketBundleCapability("account.financial-event", 1)
_BUNDLE_PREFIX = "koru-tradifi-economics-development-v3-"


def _same(left: object, right: object) -> bool:
    return canonical_bytes(left) == canonical_bytes(right)


def _hash(value: object, name: str) -> str:
    if (
        type(value) is not str
        or len(value) != 71
        or not value.startswith("sha256:")
        or any(character not in "0123456789abcdef" for character in value[7:])
    ):
        raise ValueError(f"{name} must be canonical sha256")
    return value


def _text(value: object, name: str) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(f"{name} must be canonical text")
    return value


def _wire(value: object) -> object:
    """Use only canonical JSON-compatible values in authority payloads."""
    import json

    return json.loads(canonical_bytes(value))


def _binding(event: MarketEvent) -> dict[str, object]:
    return {
        "stream_key": event.stream_key,
        "event_type": event.event_type,
        "event_id": event.event_id,
        "event_hash": event.event_hash,
    }


def _exact_mapping(value: object, keys: frozenset[str], name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != keys or any(type(key) is not str for key in value):
        raise ValueError(name)
    return value


def _event_bindings(value: object, name: str) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, tuple):
        raise TypeError(name)
    return tuple(
        _exact_mapping(
            item, frozenset({"stream_key", "event_type", "event_id", "event_hash"}), name
        )
        for item in value
    )


def _freeze_terms(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze_terms(child) for key, child in value.items()})
    if isinstance(value, tuple):
        return tuple(_freeze_terms(child) for child in value)
    if isinstance(value, list):
        return tuple(_freeze_terms(child) for child in value)
    return value


@runtime_checkable
class KoruEconomicsArtifactStoreV1(Protocol):
    """Builder-local artifact publication/readback contract."""

    def put(self, *, envelope: ArtifactEnvelope) -> ArtifactRef: ...

    def read(self, *, ref: ArtifactRef) -> ArtifactReadResult: ...


@dataclass(frozen=True, slots=True)
class KoruTradifiSourceProjectionContentIdentityV2:
    """Content identity, deliberately not an ArtifactEnvelope reference."""

    source_fragment_digest: str
    source_projection_request_hash: str

    def __post_init__(self) -> None:
        _hash(self.source_fragment_digest, "source_fragment_digest")
        _hash(self.source_projection_request_hash, "source_projection_request_hash")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "koru_tradifi_source_projection_content_identity_v2",
            "schema_version": 2,
            "source_fragment_digest": self.source_fragment_digest,
            "source_projection_request_hash": self.source_projection_request_hash,
        }


@dataclass(frozen=True, slots=True)
class KoruTradifiEconomicsTermsV3:
    """Sealed target-free price, account, funding, and source authority terms."""

    price_purpose_authority: tuple[Mapping[str, object], ...]
    account_authority: Mapping[str, object]
    funding_authority: Mapping[str, object]
    source_stream_manifests: tuple[MarketStreamManifest, ...]
    projection_stream_manifest: MarketStreamManifest
    source_event_bindings: tuple[Mapping[str, object], ...]
    projection_event_bindings: tuple[Mapping[str, object], ...]
    xkrx_calendar_ref: ArtifactRef
    arcx_calendar_ref: ArtifactRef
    post_adjustment_unit_regime_ref: ArtifactRef
    execution_account_id: str
    initial_equity: Money
    allocation_fraction: str

    def __post_init__(self) -> None:
        if type(self.price_purpose_authority) is not tuple or len(self.price_purpose_authority) != 4:
            raise ValueError("price_purpose_authority")
        seen: set[str] = set()
        for value in self.price_purpose_authority:
            binding = _exact_mapping(
                value,
                frozenset({"price_purpose", "stream_manifest", "event_bindings"}),
                "price_purpose_authority",
            )
            purpose = binding.get("price_purpose")
            if type(purpose) is not str or purpose not in _BOUND_PRICE_PURPOSES or purpose in seen:
                raise ValueError("price_purpose_authority")
            seen.add(purpose)
            if type(binding.get("stream_manifest")) is not MarketStreamManifest:
                raise ValueError("price_purpose_authority")
            _event_bindings(binding.get("event_bindings"), "price_purpose_authority")
        if tuple(sorted(seen)) != tuple(sorted(_BOUND_PRICE_PURPOSES)):
            raise ValueError("price_purpose_authority")
        account = _exact_mapping(
            self.account_authority,
            frozenset({"account_id", "initial_equity", "allocation_fraction"}),
            "account_authority",
        )
        if (
            account.get("account_id") != self.execution_account_id
            or not _same(account.get("initial_equity"), self.initial_equity.to_canonical_dict())
            or account.get("allocation_fraction") != self.allocation_fraction
        ):
            raise ValueError("account_authority")
        funding = _exact_mapping(
            self.funding_authority,
            frozenset({"stream_manifest", "event_bindings"}),
            "funding_authority",
        )
        if type(funding.get("stream_manifest")) is not MarketStreamManifest:
            raise ValueError("funding_authority")
        _event_bindings(funding.get("event_bindings"), "funding_authority")
        if (
            type(self.source_stream_manifests) is not tuple
            or not self.source_stream_manifests
            or any(type(value) is not MarketStreamManifest for value in self.source_stream_manifests)
            or len({value.stream_key for value in self.source_stream_manifests}) != len(self.source_stream_manifests)
            or type(self.projection_stream_manifest) is not MarketStreamManifest
            or any(type(value) is not ArtifactRef for value in (
                self.xkrx_calendar_ref, self.arcx_calendar_ref, self.post_adjustment_unit_regime_ref
            ))
        ):
            raise ValueError("source_authority")
        _event_bindings(self.source_event_bindings, "source_event_bindings")
        _event_bindings(self.projection_event_bindings, "projection_event_bindings")
        if _text(self.execution_account_id, "execution_account_id") != _REQUIRED_ACCOUNT:
            raise ValueError("execution_account_id must be exact account-1")
        if type(self.initial_equity) is not Money or self.initial_equity != _REQUIRED_EQUITY:
            raise ValueError("initial_equity must be exact 10000 USDT at scale 8")
        if self.allocation_fraction != _REQUIRED_ALLOCATION:
            raise ValueError("allocation_fraction must be exact full allocation 1")
        object.__setattr__(self, "price_purpose_authority", _freeze_terms(self.price_purpose_authority))
        object.__setattr__(self, "account_authority", _freeze_terms(self.account_authority))
        object.__setattr__(self, "funding_authority", _freeze_terms(self.funding_authority))
        object.__setattr__(self, "source_event_bindings", _freeze_terms(self.source_event_bindings))
        object.__setattr__(self, "projection_event_bindings", _freeze_terms(self.projection_event_bindings))

    @classmethod
    def from_source_projection(
        cls, source_projection: BinanceUsdmKoruTradifiSourceProjectionResultV2, *, execution_account_id: str
    ) -> KoruTradifiEconomicsTermsV3:
        """Build the sole admitted target-free terms from trusted source replay."""
        source = _trusted_source_projection(source_projection)
        if source is None:
            raise ValueError("source_projection")
        manifests = {value.stream_key: value for value in source.stream_manifests}
        by_stream: dict[str, tuple[MarketEvent, ...]] = {
            key: tuple(event for event in source.source_events if event.stream_key == key)
            for key in manifests
        }
        return cls(
            price_purpose_authority=tuple(
                {
                    "price_purpose": purpose,
                    "stream_manifest": manifests[_PRICE_PURPOSE_SOURCE_STREAMS[purpose]],
                    "event_bindings": tuple(_binding(event) for event in by_stream[_PRICE_PURPOSE_SOURCE_STREAMS[purpose]]),
                }
                for purpose in _BOUND_PRICE_PURPOSES
            ),
            account_authority={
                "account_id": execution_account_id,
                "initial_equity": _REQUIRED_EQUITY.to_canonical_dict(),
                "allocation_fraction": _REQUIRED_ALLOCATION,
            },
            funding_authority={
                "stream_manifest": manifests[_FUNDING_STREAM],
                "event_bindings": tuple(_binding(event) for event in by_stream[_FUNDING_STREAM]),
            },
            source_stream_manifests=source.stream_manifests,
            projection_stream_manifest=source.projection_stream_manifest,
            source_event_bindings=tuple(_binding(event) for event in source.source_events),
            projection_event_bindings=tuple(_binding(event) for event in source.projection_events),
            xkrx_calendar_ref=source.xkrx_calendar_ref,
            arcx_calendar_ref=source.arcx_calendar_ref,
            post_adjustment_unit_regime_ref=source.post_adjustment_unit_regime_ref,
            execution_account_id=execution_account_id,
            initial_equity=_REQUIRED_EQUITY,
            allocation_fraction=_REQUIRED_ALLOCATION,
        )

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "koru_tradifi_economics_terms_v3",
            "schema_version": _SCHEMA_VERSION,
            "price_purpose_authority": self.price_purpose_authority,
            "account_authority": self.account_authority,
            "funding_authority": self.funding_authority,
            "source_stream_manifests": self.source_stream_manifests,
            "projection_stream_manifest": self.projection_stream_manifest,
            "source_event_bindings": self.source_event_bindings,
            "projection_event_bindings": self.projection_event_bindings,
            "xkrx_calendar_ref": self.xkrx_calendar_ref,
            "arcx_calendar_ref": self.arcx_calendar_ref,
            "post_adjustment_unit_regime_ref": self.post_adjustment_unit_regime_ref,
            "execution_account_id": self.execution_account_id,
            "initial_equity": self.initial_equity,
            "allocation_fraction": self.allocation_fraction,
        }


@dataclass(frozen=True, slots=True)
class KoruTradifiEconomicsBundleRequestV3:
    """The sole publication input; store and root are operational, not identity."""

    source_projection: BinanceUsdmKoruTradifiSourceProjectionResultV2
    source_projection_content_identity: KoruTradifiSourceProjectionContentIdentityV2
    terms: KoruTradifiEconomicsTermsV3
    artifact_store: KoruEconomicsArtifactStoreV1
    repository_root: Path

    def __post_init__(self) -> None:
        if type(self.source_projection) is not BinanceUsdmKoruTradifiSourceProjectionResultV2:
            raise TypeError("source_projection must be exact SourceProjectionV2")
        if type(self.source_projection_content_identity) is not KoruTradifiSourceProjectionContentIdentityV2:
            raise TypeError("source_projection_content_identity must be exact")
        if type(self.terms) is not KoruTradifiEconomicsTermsV3:
            raise TypeError("terms must be exact KoruTradifiEconomicsTermsV3")
        if not isinstance(self.artifact_store, KoruEconomicsArtifactStoreV1):
            raise TypeError("artifact_store must satisfy KoruEconomicsArtifactStoreV1")
        if not isinstance(self.repository_root, Path) or not self.repository_root.is_absolute():
            raise ValueError("repository_root must be an absolute Path")

    @property
    def request_digest(self) -> str:
        return canonical_sha256(self.to_canonical_dict())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "koru_tradifi_economics_bundle_request_v3",
            "schema_version": _SCHEMA_VERSION,
            "source_projection_content_identity": self.source_projection_content_identity,
            "source_projection": self.source_projection,
            "terms": self.terms,
        }


class KoruTradifiEconomicsBundleFailureCodeV3(str, Enum):
    INVALID_REQUEST = "invalid_request"
    SOURCE_PROJECTION_INVALID = "source_projection_invalid"
    TERMS_INVALID = "terms_invalid"
    ARTIFACT_STORE_INVALID = "artifact_store_invalid"
    ARTIFACT_PUBLICATION_FAILED = "artifact_publication_failed"
    STREAM_ASSEMBLY_INVALID = "stream_assembly_invalid"
    MARKET_PUBLICATION_FAILED = "market_publication_failed"
    REOPEN_FAILED = "reopen_failed"
    RESULT_INVALID = "result_invalid"


@dataclass(frozen=True, slots=True)
class KoruTradifiEconomicsBundleFailureV3:
    code: KoruTradifiEconomicsBundleFailureCodeV3
    subject: str

    def __post_init__(self) -> None:
        if type(self.code) is not KoruTradifiEconomicsBundleFailureCodeV3:
            raise TypeError("code must be exact KoruTradifiEconomicsBundleFailureCodeV3")
        _text(self.subject, "subject")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "koru_tradifi_economics_bundle_failure_v3",
            "schema_version": _SCHEMA_VERSION,
            "code": self.code.value,
            "subject": self.subject,
        }


@dataclass(frozen=True, slots=True)
class KoruTradifiEconomicsBundleV3:
    request: KoruTradifiEconomicsBundleRequestV3
    source_profile_authority: ArtifactEnvelope
    authority_artifacts: tuple[ArtifactEnvelope, ArtifactEnvelope, ArtifactEnvelope, ArtifactEnvelope]
    authority_refs: tuple[ArtifactRef, ArtifactRef, ArtifactRef, ArtifactRef]
    price_purpose_authority_event: MarketEvent
    account_authority_event: MarketEvent
    economics_authority_event: MarketEvent
    manifest: MarketBundleManifest
    bundle_ref: MarketBundleRef
    reader: LocalMarketBundleReader
    authority_digest: str
    result_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if (
            type(self.request) is not KoruTradifiEconomicsBundleRequestV3
            or type(self.source_profile_authority) is not ArtifactEnvelope
            or type(self.authority_artifacts) is not tuple
            or len(self.authority_artifacts) != 4
            or any(type(value) is not ArtifactEnvelope for value in self.authority_artifacts)
            or type(self.authority_refs) is not tuple
            or len(self.authority_refs) != 4
            or any(type(value) is not ArtifactRef for value in self.authority_refs)
            or self.authority_refs != tuple(ArtifactRef.from_envelope(value) for value in self.authority_artifacts)
            or self.authority_artifacts[0] != self.source_profile_authority
            or any(type(value) is not MarketEvent for value in (
                self.price_purpose_authority_event, self.account_authority_event, self.economics_authority_event
            ))
            or type(self.manifest) is not MarketBundleManifest
            or type(self.bundle_ref) is not MarketBundleRef
            or self.bundle_ref != MarketBundleRef.from_manifest(self.manifest)
            or type(self.reader) is not LocalMarketBundleReader
            or self.reader.bundle_ref != self.bundle_ref
            or self.reader.manifest != self.manifest
        ):
            raise ValueError("economics bundle binding")
        _hash(self.authority_digest, "authority_digest")
        if self.economics_authority_event.payload.get("authority_digest") != self.authority_digest:
            raise ValueError("authority_digest binding")
        object.__setattr__(self, "result_digest", canonical_sha256(self._body()))

    def _body(self) -> dict[str, object]:
        return {
            "type": "koru_tradifi_economics_bundle_v3",
            "schema_version": _SCHEMA_VERSION,
            "request": self.request,
            "authority_artifacts": self.authority_artifacts,
            "authority_refs": self.authority_refs,
            "price_purpose_authority_event": self.price_purpose_authority_event,
            "account_authority_event": self.account_authority_event,
            "economics_authority_event": self.economics_authority_event,
            "manifest": self.manifest,
            "bundle_ref": self.bundle_ref,
            "authority_digest": self.authority_digest,
            "development_only": True,
            "deployment_authorized": False,
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "result_digest": self.result_digest}


@dataclass(frozen=True, slots=True)
class KoruTradifiEconomicsBundleOutcomeV3:
    result: KoruTradifiEconomicsBundleV3 | None = None
    failure: KoruTradifiEconomicsBundleFailureV3 | None = None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.failure is None):
            raise ValueError("outcome requires exactly one branch")
        if self.result is not None and type(self.result) is not KoruTradifiEconomicsBundleV3:
            raise TypeError("result must be exact KoruTradifiEconomicsBundleV3")
        if self.failure is not None and type(self.failure) is not KoruTradifiEconomicsBundleFailureV3:
            raise TypeError("failure must be exact KoruTradifiEconomicsBundleFailureV3")


def _failed(code: KoruTradifiEconomicsBundleFailureCodeV3, subject: str) -> KoruTradifiEconomicsBundleOutcomeV3:
    return KoruTradifiEconomicsBundleOutcomeV3(
        failure=KoruTradifiEconomicsBundleFailureV3(code, subject)
    )


def _validate_terms_against_source(
    terms: KoruTradifiEconomicsTermsV3,
    source: BinanceUsdmKoruTradifiSourceProjectionResultV2,
) -> tuple[Mapping[str, object], ...]:
    manifests = {manifest.stream_key: manifest for manifest in source.stream_manifests}
    source_bindings = tuple(_binding(event) for event in source.source_events)
    projection_bindings = tuple(_binding(event) for event in source.projection_events)
    if (
        not _same(terms.source_stream_manifests, source.stream_manifests)
        or not _same(terms.projection_stream_manifest, source.projection_stream_manifest)
        or not _same(terms.source_event_bindings, source_bindings)
        or not _same(terms.projection_event_bindings, projection_bindings)
        or terms.xkrx_calendar_ref != source.xkrx_calendar_ref
        or terms.arcx_calendar_ref != source.arcx_calendar_ref
        or terms.post_adjustment_unit_regime_ref != source.post_adjustment_unit_regime_ref
    ):
        raise ValueError("source_authority")
    price_bindings: list[Mapping[str, object]] = []
    for purpose in _BOUND_PRICE_PURPOSES:
        binding = next(
            item for item in terms.price_purpose_authority if item["price_purpose"] == purpose
        )
        stream_key = _PRICE_PURPOSE_SOURCE_STREAMS[purpose]
        expected_events = tuple(_binding(event) for event in source.source_events if event.stream_key == stream_key)
        if (
            stream_key not in manifests
            or not _same(binding["stream_manifest"], manifests[stream_key])
            or not _same(binding["event_bindings"], expected_events)
            or not expected_events
        ):
            raise ValueError("price_purpose_authority")
        price_bindings.append(binding)
    funding = terms.funding_authority
    funding_events = tuple(_binding(event) for event in source.source_events if event.stream_key == _FUNDING_STREAM)
    if (
        _FUNDING_STREAM not in manifests
        or not funding_events
        or not _same(funding["stream_manifest"], manifests[_FUNDING_STREAM])
        or not _same(funding["event_bindings"], funding_events)
    ):
        raise ValueError("funding_authority")
    return tuple(price_bindings)


def _validate_source(
    request: KoruTradifiEconomicsBundleRequestV3,
) -> tuple[BinanceUsdmKoruTradifiSourceProjectionResultV2, ArtifactEnvelope]:
    # Replay, rather than hashes supplied by the caller, establishes source trust.
    source = _trusted_source_projection(request.source_projection)
    if source is None:
        raise ValueError("source_projection")
    if (
        request.source_projection_content_identity.source_fragment_digest != source.fragment_digest
        or request.source_projection_content_identity.source_projection_request_hash != source.request.request_hash
    ):
        raise ValueError("source_identity")
    source_profile, source_profile_ref = build_binance_usdm_koru_source_profile_authority_v2(source)
    if source_profile_ref != ArtifactRef.from_envelope(source_profile):
        raise ValueError("source_profile")
    return source, source_profile


def _event(
    *, stream_key: str, event_type: str, capability: MarketBundleCapability,
    instant: UtcInstant, phase: TimelinePhase, payload: dict[str, object], instrument: object,
) -> MarketEvent:
    source_hash = canonical_sha256({"type": event_type, "stream_key": stream_key, "payload": payload})
    return MarketEvent(
        event_id=event_type + ":" + source_hash,
        stream_key=stream_key,
        event_type=event_type,
        capability=capability,
        instrument_id=instrument,
        event_time=instant,
        available_time=instant,
        phase=phase,
        source_sequence=SourceSequence(0),
        revision_id=canonical_sha256({"type": event_type + "_revision", "source_hash": source_hash}),
        supersedes_revision_id=None,
        source_key=stream_key,
        source_hash=source_hash,
        payload=payload,
    )


def _assemble(
    request: KoruTradifiEconomicsBundleRequestV3,
    source: BinanceUsdmKoruTradifiSourceProjectionResultV2,
    source_profile: ArtifactEnvelope,
    price_bindings: tuple[Mapping[str, object], ...],
) -> tuple[MarketEvent, MarketEvent, MarketEvent, dict[str, tuple[MarketEvent, ...]], MarketBundleManifest, MarketBundleRef, str]:
    price_payload = {
        "schema_version": _SCHEMA_VERSION,
        "instrument_id": _INSTRUMENT_WIRE,
        "source_projection_content_identity": request.source_projection_content_identity.to_canonical_dict(),
        "price_purpose_bindings": tuple(
            {
                "price_purpose": binding["price_purpose"],
                "source_stream_manifest": _wire(binding["stream_manifest"]),
                "event_bindings": binding["event_bindings"],
            }
            for binding in price_bindings
        ),
    }
    price = _event(
        stream_key=_PRICE_STREAM, event_type=_PRICE_EVENT, capability=_PRICE_CAPABILITY,
        instant=source.request.timeline_window_start, phase=TimelinePhase(0, "market_data"),
        payload=price_payload, instrument=_INSTRUMENT,
    )
    account = _event(
        stream_key=_ACCOUNT_STREAM, event_type=_ACCOUNT_EVENT, capability=_ACCOUNT_CAPABILITY,
        instant=source.request.timeline_window_start, phase=TimelinePhase(110, "account_financial_dispatch"),
        instrument=_INSTRUMENT,
        payload={
            "schema_version": _SCHEMA_VERSION,
            "account_id": request.terms.execution_account_id,
            "initial_equity": request.terms.initial_equity.to_canonical_dict(),
            "allocation_fraction": request.terms.allocation_fraction,
            "position_notional_usdt": _REQUIRED_POSITION_NOTIONAL,
            "operation_authorized": False,
            "order_authorized": False,
            "deployment_authorized": False,
        },
    )
    artifacts = (source_profile, source.xkrx_calendar, source.arcx_calendar, source.post_adjustment_unit_regime)
    refs = tuple(ArtifactRef.from_envelope(value) for value in artifacts)
    wire = {
        "schema_version": _SCHEMA_VERSION,
        "source_projection_content_identity": request.source_projection_content_identity.to_canonical_dict(),
        "source_fragment_digest": source.fragment_digest,
        "full_scope": {
            "start": source.request.timeline_window_start.to_canonical_dict(),
            "end_exclusive": source.request.timeline_window_end_exclusive.to_canonical_dict(),
            "scope_digest": canonical_sha256({
                "start": source.request.timeline_window_start,
                "end_exclusive": source.request.timeline_window_end_exclusive,
            }),
        },
        "terms": _wire(request.terms),
        "artifact_refs": tuple(value.to_canonical_dict() for value in refs),
        "stream_manifests": tuple(value.to_canonical_dict() for value in source.stream_manifests),
        "price_purpose_authority_binding": _binding(price),
        "account_authority_binding": _binding(account),
        "development_only": True,
        "deployment_authorized": False,
    }
    authority_digest = canonical_sha256(wire)
    economics = _event(
        stream_key=_ECONOMICS_STREAM, event_type=_ECONOMICS_EVENT, capability=_ECONOMICS_CAPABILITY,
        instant=source.request.timeline_window_start, phase=TimelinePhase(0, "market_data"),
        instrument=None, payload={**wire, "authority_digest": authority_digest},
    )
    grouped: dict[str, list[MarketEvent]] = defaultdict(list)
    for event in (*source.source_events, *source.projection_events):
        grouped[event.stream_key].append(event)
    streams = {value.stream_key: tuple(grouped.get(value.stream_key, ())) for value in source.stream_manifests}
    for event in (price, account, economics):
        if event.stream_key in streams:
            raise ValueError("authority_stream_collision")
        streams[event.stream_key] = (event,)
    stream_manifests = tuple(MarketStreamManifest.from_events(key, events) for key, events in sorted(streams.items()))
    manifest = MarketBundleManifest.build(
        bundle_key=_BUNDLE_PREFIX + canonical_sha256({
            "source_projection_content_identity": request.source_projection_content_identity,
            "terms": request.terms,
            "authority_digest": authority_digest,
        })[7:],
        schema_version=_SCHEMA_VERSION,
        coverage_start=source.request.timeline_window_start,
        coverage_end_exclusive=source.request.timeline_window_end_exclusive,
        instrument_catalog_hash=source.request.instrument_catalog_hash,
        capabilities=tuple(sorted({value.capability for value in stream_manifests})),
        streams=stream_manifests,
    )
    return price, account, economics, streams, manifest, MarketBundleRef.from_manifest(manifest), authority_digest


def _publish_artifacts(
    store: KoruEconomicsArtifactStoreV1,
    artifacts: tuple[ArtifactEnvelope, ArtifactEnvelope, ArtifactEnvelope, ArtifactEnvelope],
) -> tuple[ArtifactRef, ArtifactRef, ArtifactRef, ArtifactRef]:
    refs: list[ArtifactRef] = []
    for envelope in artifacts:
        ref = store.put(envelope=envelope)
        expected = ArtifactRef.from_envelope(envelope)
        if type(ref) is not ArtifactRef or ref != expected:
            raise ValueError("artifact_ref")
        result = store.read(ref=ref)
        if (
            type(result) is not ArtifactReadResult
            or result.envelope != envelope
            or result.source_bytes != canonical_bytes(envelope)
            or result.source_hash != canonical_sha256(envelope)
            or ArtifactRef.from_envelope(result.envelope) != ref
        ):
            raise ValueError("artifact_readback")
        refs.append(ref)
    return tuple(refs)  # type: ignore[return-value]


def publish_koru_tradifi_economics_bundle_v3(
    request: KoruTradifiEconomicsBundleRequestV3,
) -> KoruTradifiEconomicsBundleOutcomeV3:
    """Publish then locally reopen a target-free economics Market Bundle."""
    if type(request) is not KoruTradifiEconomicsBundleRequestV3:
        return _failed(KoruTradifiEconomicsBundleFailureCodeV3.INVALID_REQUEST, "request")
    try:
        source, source_profile = _validate_source(request)
    except (AttributeError, KeyError, TypeError, ValueError):
        return _failed(KoruTradifiEconomicsBundleFailureCodeV3.SOURCE_PROJECTION_INVALID, "source_projection")
    try:
        price_bindings = _validate_terms_against_source(request.terms, source)
        price, account, economics, streams, manifest, bundle_ref, authority_digest = _assemble(
            request, source, source_profile, price_bindings
        )
    except (AttributeError, KeyError, TypeError, ValueError):
        return _failed(KoruTradifiEconomicsBundleFailureCodeV3.TERMS_INVALID, "terms")
    artifacts = (source_profile, source.xkrx_calendar, source.arcx_calendar, source.post_adjustment_unit_regime)
    try:
        refs = _publish_artifacts(request.artifact_store, artifacts)
    except (AttributeError, TypeError):
        return _failed(KoruTradifiEconomicsBundleFailureCodeV3.ARTIFACT_STORE_INVALID, "artifact_store")
    except (KeyError, ValueError):
        return _failed(KoruTradifiEconomicsBundleFailureCodeV3.ARTIFACT_PUBLICATION_FAILED, "artifact_readback")
    outcome = LocalMarketBundleRepository(
        config=LocalMarketBundleRepositoryConfig(root=request.repository_root)
    ).publish_market_bundle_v1(
        manifest=manifest,
        stream_payloads={key: canonical_bytes(events) for key, events in streams.items()},
        retention_policy_ref="koru-tradifi-economics-v3",
    )
    if outcome.result is None or outcome.result.bundle_ref != bundle_ref:
        return _failed(KoruTradifiEconomicsBundleFailureCodeV3.MARKET_PUBLICATION_FAILED, "market_bundle")
    try:
        reader = LocalMarketBundleReader.open(repository_root=request.repository_root, bundle_ref=bundle_ref)
        if reader.manifest != manifest or reader.bundle_ref != bundle_ref:
            raise ValueError("readback")
    except (AttributeError, OSError, TypeError, ValueError):
        return _failed(KoruTradifiEconomicsBundleFailureCodeV3.REOPEN_FAILED, "market_bundle")
    try:
        return KoruTradifiEconomicsBundleOutcomeV3(
            result=KoruTradifiEconomicsBundleV3(
                request=request,
                source_profile_authority=source_profile,
                authority_artifacts=artifacts,
                authority_refs=refs,
                price_purpose_authority_event=price,
                account_authority_event=account,
                economics_authority_event=economics,
                manifest=manifest,
                bundle_ref=bundle_ref,
                reader=reader,
                authority_digest=authority_digest,
            )
        )
    except (AttributeError, TypeError, ValueError):
        return _failed(KoruTradifiEconomicsBundleFailureCodeV3.RESULT_INVALID, "result")


__all__ = [
    "KoruEconomicsArtifactStoreV1",
    "KoruTradifiEconomicsBundleFailureCodeV3",
    "KoruTradifiEconomicsBundleFailureV3",
    "KoruTradifiEconomicsBundleOutcomeV3",
    "KoruTradifiEconomicsBundleRequestV3",
    "KoruTradifiEconomicsBundleV3",
    "KoruTradifiEconomicsTermsV3",
    "KoruTradifiSourceProjectionContentIdentityV2",
    "publish_koru_tradifi_economics_bundle_v3",
]
