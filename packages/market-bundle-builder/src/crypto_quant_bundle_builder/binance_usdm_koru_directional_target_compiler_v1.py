"""Discovery-only, causal KORU directional target compilation."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import cast

from crypto_quant_domain import (
    ArtifactRef,
    InstrumentId,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_market_data import (
    MarketBundleCapability,
    MarketEvent,
    MarketStreamManifest,
)

from .binance_usdm_koru_tradifi_source_projection_v2 import (
    BinanceUsdmKoruFirstRetainedTradeProjectionLineageV2,
    BinanceUsdmKoruTradifiSourceProjectionResultV2,
)
from .binance_usdm_koru_tradifi_source_projection_v2 import (
    _trusted_result as _trusted_source_result,
)

_SCHEMA_VERSION = 1
_REQUEST_SCHEMA_VERSION = "koru_directional_target_compile_v1"
_DISCOVERY_START = 1_784_109_600_000_000_000
_DISCOVERY_END = 1_787_569_200_000_000_000
_HOUR_NS = 3_600_000_000_000
_CAPABILITY = MarketBundleCapability("precomputed_target_stream", 1)
_PHASE = TimelinePhase(30, "strategy_decision")
_EVENT_TYPE = "strategy_decision_candidate"
_SOURCE_KEY = "binance_usdm.koru.directional_target_compiler.v1"
_SOURCE_PROJECTION_ARTIFACT_TYPE = "binance_usdm_koru_source_projection"
_SOURCE_PROJECTION_SCHEMA_VERSION = 2


# SourceProjectionV2 and TargetV2 deliberately remain the existing public shapes.
type SourceProjectionV2 = BinanceUsdmKoruTradifiSourceProjectionResultV2
type TargetV2 = MarketEvent


def _canonical_text(name: str, value: object) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(f"{name} must be canonical text")
    return value


def _decimal(name: str, value: object, *, nonnegative: bool = True) -> Decimal:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(f"{name} must be a canonical decimal string")
    try:
        parsed = Decimal(value)
    except InvalidOperation as error:
        raise ValueError(f"{name} must be a canonical decimal string") from error
    if not parsed.is_finite() or parsed != Decimal(value) or str(parsed) != value:
        raise ValueError(f"{name} must be a canonical decimal string")
    if nonnegative and parsed < 0:
        raise ValueError(f"{name} must be non-negative")
    return parsed


def _hash(name: str, value: object) -> str:
    if (
        type(value) is not str
        or len(value) != 71
        or not value.startswith("sha256:")
        or any(char not in "0123456789abcdef" for char in value[7:])
    ):
        raise ValueError(f"{name} must be a canonical sha256 digest")
    return value


def _same(left: object, right: object) -> bool:
    return canonical_bytes(left) == canonical_bytes(right)


@dataclass(frozen=True, slots=True)
class KoruDirectionalDiscoveryScopeV1:
    discovery_start: UtcInstant = field(default_factory=lambda: UtcInstant(_DISCOVERY_START))
    discovery_end_exclusive: UtcInstant = field(default_factory=lambda: UtcInstant(_DISCOVERY_END))
    holdout_start: UtcInstant = field(default_factory=lambda: UtcInstant(_DISCOVERY_END))

    def __post_init__(self) -> None:
        if (
            type(self.discovery_start) is not UtcInstant
            or type(self.discovery_end_exclusive) is not UtcInstant
            or type(self.holdout_start) is not UtcInstant
            or self.discovery_start.epoch_nanoseconds != _DISCOVERY_START
            or self.discovery_end_exclusive.epoch_nanoseconds != _DISCOVERY_END
            or self.discovery_end_exclusive != self.holdout_start
        ):
            raise ValueError("scope must be the frozen discovery interval before holdout")

    @property
    def scope_digest(self) -> str:
        return canonical_sha256(self.to_canonical_dict())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "koru_directional_discovery_scope_v1",
            "schema_version": _SCHEMA_VERSION,
            "discovery_start": self.discovery_start,
            "discovery_end_exclusive": self.discovery_end_exclusive,
            "holdout_start": self.holdout_start,
        }


@dataclass(frozen=True, slots=True)
class KoruMarkIndexPremiumParametersV1:
    entry_premium_bps: str
    exit_premium_bps: str
    max_hold_hours: int
    flat_when_inside_band: bool = True

    def __post_init__(self) -> None:
        _decimal("entry_premium_bps", self.entry_premium_bps)
        _decimal("exit_premium_bps", self.exit_premium_bps)
        if type(self.max_hold_hours) is not int or self.max_hold_hours <= 0:
            raise ValueError("max_hold_hours must be positive")
        if type(self.flat_when_inside_band) is not bool or not self.flat_when_inside_band:
            raise ValueError("flat_when_inside_band must be true")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "koru_mark_index_premium_parameters_v1",
            "entry_premium_bps": self.entry_premium_bps,
            "exit_premium_bps": self.exit_premium_bps,
            "max_hold_hours": self.max_hold_hours,
            "flat_when_inside_band": self.flat_when_inside_band,
        }


@dataclass(frozen=True, slots=True)
class KoruDirectionalUnsupportedParametersV1:
    """A sealed marker for a v1 family whose evidence projection is unavailable."""

    family: str

    def __post_init__(self) -> None:
        if self.family not in {"breakout", "funding_carry", "cash_open_momentum"}:
            raise ValueError("unsupported parameters must name a sealed family")

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "koru_directional_unsupported_parameters_v1", "family": self.family}


@dataclass(frozen=True, slots=True)
class KoruDirectionalTargetRecipeV1:
    family: str
    recipe_id: str
    strategy_id: str
    sleeve_id: str
    strategy_ref: ArtifactRef
    parameter_ref: ArtifactRef
    target_stream_key: str
    instrument_id: InstrumentId
    target_exposure: str
    bar_interval: str
    parameters: KoruMarkIndexPremiumParametersV1 | KoruDirectionalUnsupportedParametersV1

    def __post_init__(self) -> None:
        if self.family not in {
            "breakout",
            "mark_index_premium",
            "funding_carry",
            "cash_open_momentum",
        }:
            raise ValueError("family is unsupported")
        for name in ("recipe_id", "strategy_id", "sleeve_id", "target_stream_key"):
            _canonical_text(name, getattr(self, name))
        if type(self.strategy_ref) is not ArtifactRef or type(self.parameter_ref) is not ArtifactRef:
            raise TypeError("recipe refs must be exact ArtifactRef values")
        if type(self.instrument_id) is not InstrumentId:
            raise TypeError("instrument_id must be exact InstrumentId")
        if type(self.target_exposure) is not str or _decimal("target_exposure", self.target_exposure) <= 0:
            raise ValueError("target_exposure must be a positive canonical decimal string")
        if type(self.bar_interval) is not str or self.bar_interval != "1h":
            raise ValueError("bar_interval must be exactly 1h")
        if self.family == "mark_index_premium":
            if type(self.parameters) is not KoruMarkIndexPremiumParametersV1:
                raise TypeError("premium recipes require premium parameters")
        elif (
            type(self.parameters) is not KoruDirectionalUnsupportedParametersV1
            or self.parameters.family != self.family
        ):
            raise TypeError("unsupported recipes require their sealed parameters")

    @property
    def recipe_digest(self) -> str:
        return canonical_sha256(self.to_canonical_dict())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "koru_directional_target_recipe_v1",
            "schema_version": _SCHEMA_VERSION,
            "family": self.family,
            "recipe_id": self.recipe_id,
            "strategy_id": self.strategy_id,
            "sleeve_id": self.sleeve_id,
            "strategy_ref": self.strategy_ref,
            "parameter_ref": self.parameter_ref,
            "target_stream_key": self.target_stream_key,
            "instrument_id": self.instrument_id,
            "target_exposure": self.target_exposure,
            "bar_interval": self.bar_interval,
            "parameters": self.parameters,
        }


class KoruDirectionalTargetCompileFailureCodeV1(str, Enum):
    INVALID_REQUEST = "INVALID_REQUEST"
    SOURCE_PROJECTION_INVALID = "SOURCE_PROJECTION_INVALID"
    HOLDOUT_SOURCE_INPUT = "HOLDOUT_SOURCE_INPUT"
    SOURCE_OUT_OF_SCOPE = "SOURCE_OUT_OF_SCOPE"
    DUPLICATE_IDENTITY = "DUPLICATE_IDENTITY"
    PAIRED_BAR_INVALID = "PAIRED_BAR_INVALID"
    REVISION_INVALID = "REVISION_INVALID"
    AVAILABILITY_INVALID = "AVAILABILITY_INVALID"
    CALENDAR_AVAILABILITY_UNPROVEN = "CALENDAR_AVAILABILITY_UNPROVEN"
    UNSUPPORTED_RECIPE_FAMILY = "UNSUPPORTED_RECIPE_FAMILY"
    NEXT_BOUNDARY_EVIDENCE_MISSING = "NEXT_BOUNDARY_EVIDENCE_MISSING"
    TARGET_RULE_INVALID = "TARGET_RULE_INVALID"
    RESULT_INVALID = "RESULT_INVALID"


@dataclass(frozen=True, slots=True)
class KoruDirectionalTargetCompileFailureV1:
    code: KoruDirectionalTargetCompileFailureCodeV1
    subject: str

    def __post_init__(self) -> None:
        if type(self.code) is not KoruDirectionalTargetCompileFailureCodeV1:
            raise TypeError("code must be an exact compiler failure code")
        _canonical_text("subject", self.subject)

    @property
    def failure_digest(self) -> str:
        return canonical_sha256(self.to_canonical_dict())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "koru_directional_target_compile_failure_v1",
            "schema_version": _SCHEMA_VERSION,
            "code": self.code.value,
            "subject": self.subject,
        }


@dataclass(frozen=True, slots=True)
class KoruDirectionalTargetCompileRequestV1:
    source_projection: SourceProjectionV2
    source_projection_ref: ArtifactRef
    source_fragment_digest: str
    scope: KoruDirectionalDiscoveryScopeV1
    recipes: tuple[KoruDirectionalTargetRecipeV1, ...]
    schema_version: str = _REQUEST_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if (
            type(self.source_projection)
            is not BinanceUsdmKoruTradifiSourceProjectionResultV2
            or type(self.source_projection_ref) is not ArtifactRef
        ):
            raise TypeError("request must use the exact SourceProjectionV2 and ArtifactRef")
        _hash("source_fragment_digest", self.source_fragment_digest)
        if (
            self.source_projection_ref.artifact_type != _SOURCE_PROJECTION_ARTIFACT_TYPE
            or self.source_projection_ref.schema_version != _SOURCE_PROJECTION_SCHEMA_VERSION
            or self.source_projection_ref.content_hash != self.source_fragment_digest
        ):
            raise ValueError("source_projection_ref must bind the exact V2 source fragment")
        if type(self.scope) is not KoruDirectionalDiscoveryScopeV1:
            raise TypeError("scope must be exact KoruDirectionalDiscoveryScopeV1")
        if (
            type(self.recipes) is not tuple
            or not self.recipes
            or any(type(recipe) is not KoruDirectionalTargetRecipeV1 for recipe in self.recipes)
        ):
            raise ValueError("recipes must be a non-empty exact recipe tuple")
        if self.schema_version != _REQUEST_SCHEMA_VERSION:
            raise ValueError("request schema_version is invalid")

    @property
    def request_digest(self) -> str:
        return canonical_sha256(self.to_canonical_dict())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "koru_directional_target_compile_request_v1",
            "schema_version": self.schema_version,
            "source_projection": self.source_projection,
            "source_projection_ref": self.source_projection_ref,
            "source_fragment_digest": self.source_fragment_digest,
            "scope": self.scope,
            "recipes": self.recipes,
        }


@dataclass(frozen=True, slots=True)
class KoruDirectionalTargetEvidenceIdentityV1:
    event_id: str
    event_hash: str
    revision_id: str
    event_time: UtcInstant
    available_time: UtcInstant

    def __post_init__(self) -> None:
        _canonical_text("event_id", self.event_id)
        _hash("event_hash", self.event_hash)
        _hash("revision_id", self.revision_id)
        if type(self.event_time) is not UtcInstant or type(self.available_time) is not UtcInstant:
            raise TypeError("evidence times must be exact UtcInstant")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "koru_directional_target_evidence_identity_v1",
            "event_id": self.event_id,
            "event_hash": self.event_hash,
            "revision_id": self.revision_id,
            "event_time": self.event_time,
            "available_time": self.available_time,
        }


@dataclass(frozen=True, slots=True)
class KoruDirectionalTargetStreamV1:
    recipe_ref: ArtifactRef
    source_fragment_digest: str
    target_stream_key: str
    events: tuple[TargetV2, ...]
    manifest: MarketStreamManifest
    target_stream_digest: str
    evidence: tuple[KoruDirectionalTargetEvidenceIdentityV1, ...]

    def __post_init__(self) -> None:
        if type(self.recipe_ref) is not ArtifactRef:
            raise TypeError("recipe_ref must be exact ArtifactRef")
        _hash("source_fragment_digest", self.source_fragment_digest)
        _canonical_text("target_stream_key", self.target_stream_key)
        if type(self.events) is not tuple or any(type(event) is not MarketEvent for event in self.events):
            raise TypeError("events must be an exact TargetV2 tuple")
        if any(event.stream_key != self.target_stream_key for event in self.events):
            raise ValueError("target event stream mismatch")
        expected_manifest = _manifest(self.target_stream_key, self.events)
        if type(self.manifest) is not MarketStreamManifest or not _same(self.manifest, expected_manifest):
            raise ValueError("target stream manifest mismatch")
        if self.target_stream_digest != _stream_digest(self.target_stream_key, self.events):
            raise ValueError("target stream digest mismatch")
        if type(self.evidence) is not tuple or any(type(value) is not KoruDirectionalTargetEvidenceIdentityV1 for value in self.evidence):
            raise TypeError("evidence must be an exact identity tuple")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "koru_directional_target_stream_v1",
            "schema_version": _SCHEMA_VERSION,
            "recipe_ref": self.recipe_ref,
            "source_fragment_digest": self.source_fragment_digest,
            "target_stream_key": self.target_stream_key,
            "events": self.events,
            "manifest": self.manifest,
            "target_stream_digest": self.target_stream_digest,
            "evidence": self.evidence,
        }


@dataclass(frozen=True, slots=True)
class KoruDirectionalTargetCompileResultV1:
    request: KoruDirectionalTargetCompileRequestV1
    streams: tuple[KoruDirectionalTargetStreamV1, ...]
    result_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.request) is not KoruDirectionalTargetCompileRequestV1:
            raise TypeError("result request must be exact")
        if type(self.streams) is not tuple or any(type(stream) is not KoruDirectionalTargetStreamV1 for stream in self.streams):
            raise TypeError("streams must be an exact stream tuple")
        try:
            trusted = _trusted_request(self.request)
            expected_streams = _compile(trusted)
        except (AttributeError, KeyError, TypeError, ValueError) as error:
            raise ValueError("result request cannot be compiled") from error
        if not _same(self.request, trusted) or not _same(self.streams, expected_streams):
            raise ValueError("result must exactly replay the request")
        if tuple(stream.target_stream_key for stream in self.streams) != tuple(sorted(stream.target_stream_key for stream in self.streams)):
            raise ValueError("stream manifests must be sorted by stream key")
        object.__setattr__(self, "result_digest", canonical_sha256(self._body()))

    def _body(self) -> dict[str, object]:
        return {
            "type": "koru_directional_target_compile_result_v1",
            "schema_version": _SCHEMA_VERSION,
            "request": self.request,
            "request_digest": self.request.request_digest,
            "streams": self.streams,
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "result_digest": self.result_digest}


@dataclass(frozen=True, slots=True)
class KoruDirectionalTargetCompileOutcomeV1:
    result: KoruDirectionalTargetCompileResultV1 | None = None
    failure: KoruDirectionalTargetCompileFailureV1 | None = None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.failure is None):
            raise ValueError("outcome must contain exactly one branch")
        if self.result is not None and _trusted_result(self.result) is None:
            raise ValueError("result must be an exact replayed compilation")
        if self.failure is not None and type(self.failure) is not KoruDirectionalTargetCompileFailureV1:
            raise TypeError("failure must be exact")


class _CompileError(ValueError):
    def __init__(self, code: KoruDirectionalTargetCompileFailureCodeV1, subject: str) -> None:
        super().__init__(subject)
        self.code = code
        self.subject = subject


def _manifest(stream_key: str, events: tuple[MarketEvent, ...]) -> MarketStreamManifest:
    if events:
        return MarketStreamManifest.from_events(stream_key, events)
    return MarketStreamManifest(stream_key, _EVENT_TYPE, _CAPABILITY, 0, canonical_sha256(()))


def _stream_digest(stream_key: str, events: tuple[MarketEvent, ...]) -> str:
    return canonical_sha256({"type": "precomputed_target_stream", "schema_version": 1, "stream_key": stream_key, "events": events})


def _rebuild_parameters(
    value: KoruMarkIndexPremiumParametersV1 | KoruDirectionalUnsupportedParametersV1,
) -> KoruMarkIndexPremiumParametersV1 | KoruDirectionalUnsupportedParametersV1:
    if type(value) is KoruMarkIndexPremiumParametersV1:
        return KoruMarkIndexPremiumParametersV1(
            value.entry_premium_bps,
            value.exit_premium_bps,
            value.max_hold_hours,
            value.flat_when_inside_band,
        )
    if type(value) is KoruDirectionalUnsupportedParametersV1:
        return KoruDirectionalUnsupportedParametersV1(value.family)
    raise TypeError("recipe parameters must be exact")


def _trusted_request(value: object) -> KoruDirectionalTargetCompileRequestV1:
    if type(value) is not KoruDirectionalTargetCompileRequestV1:
        raise _CompileError(KoruDirectionalTargetCompileFailureCodeV1.INVALID_REQUEST, "request_type")
    try:
        scope = KoruDirectionalDiscoveryScopeV1(
            value.scope.discovery_start,
            value.scope.discovery_end_exclusive,
            value.scope.holdout_start,
        )
        recipes = tuple(
            KoruDirectionalTargetRecipeV1(
                recipe.family,
                recipe.recipe_id,
                recipe.strategy_id,
                recipe.sleeve_id,
                ArtifactRef(
                    recipe.strategy_ref.artifact_type,
                    recipe.strategy_ref.schema_version,
                    recipe.strategy_ref.content_hash,
                ),
                ArtifactRef(
                    recipe.parameter_ref.artifact_type,
                    recipe.parameter_ref.schema_version,
                    recipe.parameter_ref.content_hash,
                ),
                recipe.target_stream_key,
                recipe.instrument_id,
                recipe.target_exposure,
                recipe.bar_interval,
                _rebuild_parameters(recipe.parameters),
            )
            for recipe in value.recipes
        )
        rebuilt = KoruDirectionalTargetCompileRequestV1(
            value.source_projection,
            ArtifactRef(
                value.source_projection_ref.artifact_type,
                value.source_projection_ref.schema_version,
                value.source_projection_ref.content_hash,
            ),
            value.source_fragment_digest,
            scope,
            recipes,
            value.schema_version,
        )
    except (AttributeError, TypeError, ValueError) as error:
        raise _CompileError(KoruDirectionalTargetCompileFailureCodeV1.INVALID_REQUEST, "request") from error
    if not _same(rebuilt, value):
        raise _CompileError(KoruDirectionalTargetCompileFailureCodeV1.INVALID_REQUEST, "request_binding")
    order = tuple((recipe.family, recipe.recipe_id, recipe.parameter_ref.content_hash, recipe.target_stream_key) for recipe in rebuilt.recipes)
    if order != tuple(sorted(order)):
        raise _CompileError(KoruDirectionalTargetCompileFailureCodeV1.INVALID_REQUEST, "recipe_order")
    if (
        len({recipe.recipe_id for recipe in rebuilt.recipes}) != len(rebuilt.recipes)
        or len({(recipe.strategy_id, recipe.parameter_ref.content_hash) for recipe in rebuilt.recipes}) != len(rebuilt.recipes)
        or len({recipe.target_stream_key for recipe in rebuilt.recipes}) != len(rebuilt.recipes)
    ):
        raise _CompileError(KoruDirectionalTargetCompileFailureCodeV1.INVALID_REQUEST, "recipe_identity")
    return rebuilt


def _trusted_source(request: KoruDirectionalTargetCompileRequestV1) -> SourceProjectionV2:
    source = _trusted_source_result(request.source_projection)
    if source is None or source.fragment_digest != request.source_fragment_digest:
        raise _CompileError(KoruDirectionalTargetCompileFailureCodeV1.SOURCE_PROJECTION_INVALID, "source_projection")
    start = source.request.timeline_window_start
    end = source.request.timeline_window_end_exclusive
    if end > request.scope.holdout_start:
        raise _CompileError(KoruDirectionalTargetCompileFailureCodeV1.HOLDOUT_SOURCE_INPUT, "source_window")
    if start < request.scope.discovery_start or end > request.scope.discovery_end_exclusive:
        raise _CompileError(KoruDirectionalTargetCompileFailureCodeV1.SOURCE_OUT_OF_SCOPE, "source_window")
    if len({event.event_id for event in source.source_events}) != len(source.source_events):
        raise _CompileError(KoruDirectionalTargetCompileFailureCodeV1.DUPLICATE_IDENTITY, "source_event_id")
    if any(
        event.event_time < request.scope.discovery_start
        or event.event_time >= request.scope.holdout_start
        for event in (*source.source_events, *source.projection_events)
    ):
        raise _CompileError(KoruDirectionalTargetCompileFailureCodeV1.HOLDOUT_SOURCE_INPUT, "source_event")
    return source


def _premium_pairs(source: SourceProjectionV2, scope: KoruDirectionalDiscoveryScopeV1) -> tuple[tuple[MarketEvent, MarketEvent], ...]:
    selected: dict[tuple[str, int], MarketEvent] = {}
    for event in source.source_events:
        payload = event.payload
        if payload.get("interval") != "1h" or payload.get("price_purpose") != "strategy":
            continue
        kind = payload.get("source_kind")
        if not isinstance(kind, str) or kind not in {"mark_price", "index_price"}:
            continue
        try:
            opened = payload["open_time_milliseconds"]
            closed = payload["close_time_milliseconds"]
            scale = payload["price_scale"]
            price = payload["close_units"]
        except KeyError as error:
            raise _CompileError(KoruDirectionalTargetCompileFailureCodeV1.PAIRED_BAR_INVALID, "price_payload") from error
        if (
            type(opened) is not int or type(closed) is not int or type(scale) is not int
            or type(price) is not int or price <= 0 or scale != 8
            or event.event_time.epoch_nanoseconds != (closed + 1) * 1_000_000
        ):
            raise _CompileError(KoruDirectionalTargetCompileFailureCodeV1.PAIRED_BAR_INVALID, event.event_id)
        if event.supersedes_revision_id is not None:
            raise _CompileError(KoruDirectionalTargetCompileFailureCodeV1.REVISION_INVALID, event.event_id)
        try:
            _hash("revision_id", event.revision_id)
        except ValueError as error:
            raise _CompileError(KoruDirectionalTargetCompileFailureCodeV1.REVISION_INVALID, event.event_id) from error
        if event.available_time != event.event_time:
            raise _CompileError(KoruDirectionalTargetCompileFailureCodeV1.AVAILABILITY_INVALID, event.event_id)
        if not (scope.discovery_start <= event.event_time < scope.discovery_end_exclusive):
            raise _CompileError(KoruDirectionalTargetCompileFailureCodeV1.SOURCE_OUT_OF_SCOPE, event.event_id)
        key = (kind, opened)
        if key in selected:
            raise _CompileError(KoruDirectionalTargetCompileFailureCodeV1.DUPLICATE_IDENTITY, f"{kind}:{opened}")
        selected[key] = event
    pairs: list[tuple[MarketEvent, MarketEvent]] = []
    opens = sorted({opened for _, opened in selected})
    for opened in opens:
        mark = selected.get(("mark_price", opened))
        index = selected.get(("index_price", opened))
        if mark is None or index is None:
            raise _CompileError(KoruDirectionalTargetCompileFailureCodeV1.PAIRED_BAR_INVALID, str(opened))
        if (
            mark.event_time != index.event_time
            or mark.payload["close_time_milliseconds"] != index.payload["close_time_milliseconds"]
            or mark.available_time > mark.event_time
            or index.available_time > index.event_time
        ):
            raise _CompileError(KoruDirectionalTargetCompileFailureCodeV1.PAIRED_BAR_INVALID, str(opened))
        pairs.append((mark, index))
    return tuple(pairs)


def _next_boundary(source: SourceProjectionV2, decision: UtcInstant) -> BinanceUsdmKoruFirstRetainedTradeProjectionLineageV2 | None:
    boundary = UtcInstant(decision.epoch_nanoseconds + _HOUR_NS)
    return next(
        (
            value
            for value in source.projection_lineage
            if value.hourly_boundary == boundary
            and value.source_event_time >= value.hourly_boundary
        ),
        None,
    )


def _evidence(event: MarketEvent) -> KoruDirectionalTargetEvidenceIdentityV1:
    return KoruDirectionalTargetEvidenceIdentityV1(event.event_id, event.event_hash, event.revision_id, event.event_time, event.available_time)


def _event_evidence(value: KoruDirectionalTargetEvidenceIdentityV1) -> dict[str, object]:
    return {
        "event_id": value.event_id,
        "event_hash": value.event_hash,
        "revision_id": value.revision_id,
        "event_time": value.event_time.epoch_nanoseconds,
        "available_time": value.available_time.epoch_nanoseconds,
    }


def _target_event(stream_key: str, sequence: int, candidate: dict[str, object]) -> MarketEvent:
    preimage = {"type": "binance_usdm_koru_directional_target_preimage_v1", "schema_version": _SCHEMA_VERSION, "stream_key": stream_key, "candidate": candidate}
    event_hash = canonical_sha256({"identity": "event", "preimage": preimage})
    return MarketEvent(
        event_id="binance-usdm-koru-directional-target-v1:" + event_hash,
        stream_key=stream_key,
        event_type=_EVENT_TYPE,
        capability=_CAPABILITY,
        instrument_id=None,
        event_time=UtcInstant(candidate["decision_time"]),  # type: ignore[arg-type]
        available_time=UtcInstant(candidate["decision_time"]),  # type: ignore[arg-type]
        phase=_PHASE,
        source_sequence=SourceSequence(sequence),
        revision_id=canonical_sha256({"identity": "revision", "preimage": preimage}),
        supersedes_revision_id=None,
        source_key=_SOURCE_KEY,
        source_hash=canonical_sha256({"identity": "source", "preimage": preimage}),
        payload={"schema_version": 1, "candidate": candidate},
    )


def _premium_stream(source: SourceProjectionV2, recipe: KoruDirectionalTargetRecipeV1, scope: KoruDirectionalDiscoveryScopeV1) -> KoruDirectionalTargetStreamV1:
    if type(recipe.parameters) is not KoruMarkIndexPremiumParametersV1:
        raise _CompileError(KoruDirectionalTargetCompileFailureCodeV1.TARGET_RULE_INVALID, recipe.recipe_id)
    params = recipe.parameters
    entry, exit_band = (_decimal("entry_premium_bps", params.entry_premium_bps), _decimal("exit_premium_bps", params.exit_premium_bps))
    exposure = _decimal("target_exposure", recipe.target_exposure)
    target = Decimal(0)
    held_at: int | None = None
    candidates: list[dict[str, object]] = []
    identities: list[KoruDirectionalTargetEvidenceIdentityV1] = []
    for mark, index in _premium_pairs(source, scope):
        decision = mark.event_time
        if mark.available_time > decision or index.available_time > decision:
            raise _CompileError(KoruDirectionalTargetCompileFailureCodeV1.AVAILABILITY_INVALID, mark.event_id)
        mark_close = cast(int, mark.payload["close_units"])
        index_close = cast(int, index.payload["close_units"])
        premium = Decimal(10_000) * (Decimal(mark_close) - Decimal(index_close)) / Decimal(index_close)
        desired = Decimal(0)
        if premium <= -entry:
            desired = exposure
        elif premium >= entry:
            desired = -exposure
        if target and (
            premium == 0
            or abs(premium) <= exit_band
            or (held_at is not None and decision.epoch_nanoseconds - held_at >= params.max_hold_hours * _HOUR_NS)
        ):
            desired = Decimal(0)
        terminal = decision.epoch_nanoseconds + _HOUR_NS == source.request.timeline_window_end_exclusive.epoch_nanoseconds
        if terminal:
            desired = Decimal(0)
        changed = desired != target
        boundary = _next_boundary(source, decision)
        if not terminal and boundary is None:
            raise _CompileError(KoruDirectionalTargetCompileFailureCodeV1.NEXT_BOUNDARY_EVIDENCE_MISSING, recipe.recipe_id)
        if changed:
            target = desired
            held_at = decision.epoch_nanoseconds if target else None
        evidence = [_evidence(mark), _evidence(index)]
        if boundary is not None:
            projection = next(event for event in source.projection_events if event.event_id == boundary.projection_event_id)
            evidence.append(_evidence(projection))
        identities.extend(evidence)
        candidates.append({
            "schema_version": 1,
            "strategy_id": recipe.strategy_id,
            "sleeve_id": recipe.sleeve_id,
            "decision_time": decision.epoch_nanoseconds,
            "observed_through": decision.epoch_nanoseconds,
            "effective_time": decision.epoch_nanoseconds,
            "expires_at": min(decision.epoch_nanoseconds + _HOUR_NS, source.request.timeline_window_end_exclusive.epoch_nanoseconds),
            "targets": ({"instrument_id": {"venue": recipe.instrument_id.venue.value, "stable_key": recipe.instrument_id.stable_key}, "value": str(target)},),
            "confidence": 1,
            "reason": "mark_index_premium",
            "evidence": {"source_events": tuple(_event_evidence(value) for value in evidence)},
        })
    events = tuple(_target_event(recipe.target_stream_key, sequence, candidate) for sequence, candidate in enumerate(candidates))
    evidence = tuple(sorted({value.event_id: value for value in identities}.values(), key=lambda value: (value.event_time.epoch_nanoseconds, value.event_id)))
    return KoruDirectionalTargetStreamV1(
        recipe_ref=recipe.parameter_ref,
        source_fragment_digest=source.fragment_digest,
        target_stream_key=recipe.target_stream_key,
        events=events,
        manifest=_manifest(recipe.target_stream_key, events),
        target_stream_digest=_stream_digest(recipe.target_stream_key, events),
        evidence=evidence,
    )


def _compile(request: KoruDirectionalTargetCompileRequestV1) -> tuple[KoruDirectionalTargetStreamV1, ...]:
    return _compile_trusted(_trusted_request(request))


def _compile_trusted(request: KoruDirectionalTargetCompileRequestV1) -> tuple[KoruDirectionalTargetStreamV1, ...]:
    source = _trusted_source(request)
    streams: list[KoruDirectionalTargetStreamV1] = []
    for recipe in request.recipes:
        if recipe.family == "breakout":
            raise _CompileError(KoruDirectionalTargetCompileFailureCodeV1.CALENDAR_AVAILABILITY_UNPROVEN, recipe.recipe_id)
        if recipe.family in {"funding_carry", "cash_open_momentum"}:
            raise _CompileError(KoruDirectionalTargetCompileFailureCodeV1.UNSUPPORTED_RECIPE_FAMILY, recipe.recipe_id)
        streams.append(_premium_stream(source, recipe, request.scope))
    return tuple(sorted(streams, key=lambda stream: stream.target_stream_key))


def _trusted_result(value: object) -> KoruDirectionalTargetCompileResultV1 | None:
    if type(value) is not KoruDirectionalTargetCompileResultV1:
        return None
    try:
        trusted = _trusted_request(value.request)
        rebuilt = KoruDirectionalTargetCompileResultV1(trusted, _compile(trusted))
        if not _same(trusted, value.request) or not _same(rebuilt, value):
            return None
        if value.result_digest != canonical_sha256(value._body()):
            return None
    except (AttributeError, KeyError, TypeError, ValueError, _CompileError):
        return None
    return rebuilt


def compile_binance_usdm_koru_directional_targets_v1(request: KoruDirectionalTargetCompileRequestV1) -> KoruDirectionalTargetCompileOutcomeV1:
    """Compile validated discovery observations into absolute precomputed targets."""
    try:
        trusted = _trusted_request(request)
        return KoruDirectionalTargetCompileOutcomeV1(result=KoruDirectionalTargetCompileResultV1(trusted, _compile(trusted)))
    except _CompileError as error:
        return KoruDirectionalTargetCompileOutcomeV1(failure=KoruDirectionalTargetCompileFailureV1(error.code, error.subject))
    except (AttributeError, KeyError, TypeError, ValueError) as error:
        return KoruDirectionalTargetCompileOutcomeV1(failure=KoruDirectionalTargetCompileFailureV1(KoruDirectionalTargetCompileFailureCodeV1.RESULT_INVALID, type(error).__name__))


__all__ = [
    "KoruDirectionalDiscoveryScopeV1",
    "KoruDirectionalTargetCompileFailureCodeV1",
    "KoruDirectionalTargetCompileFailureV1",
    "KoruDirectionalTargetCompileOutcomeV1",
    "KoruDirectionalTargetCompileRequestV1",
    "KoruDirectionalTargetCompileResultV1",
    "KoruDirectionalTargetEvidenceIdentityV1",
    "KoruDirectionalTargetRecipeV1",
    "KoruDirectionalTargetStreamV1",
    "KoruDirectionalUnsupportedParametersV1",
    "KoruMarkIndexPremiumParametersV1",
    "SourceProjectionV2",
    "TargetV2",
    "compile_binance_usdm_koru_directional_targets_v1",
]
