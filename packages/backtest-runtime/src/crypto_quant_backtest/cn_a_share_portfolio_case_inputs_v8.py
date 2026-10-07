"""Additive source-only V8 CN portfolio Case preimage; no Engine or trade authority.

Old V1-V7 bundle decoders are unchanged. Only explicitly synthetic fixtures are
admitted here; retained bytes and independent MarketBundle/target CAS are checked
on every reopen. No public BacktestRequest or economic result is published.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from crypto_quant_domain import (
    ArtifactEnvelope, ArtifactReadResult, ArtifactRef, ArtifactSchemaRegistration,
    InstrumentId, SchemaCatalog, UtcInstant, canonical_bytes, canonical_sha256,
)
from crypto_quant_market_data import EventCursor, InputValidationFailure, MarketBundleReader, MarketBundleRef, MarketEvent

from .artifact_envelope_publisher import ArtifactEnvelopePublisher
from .artifact_envelope_reader import ArtifactEnvelopeReader
from .cn_a_share_portfolio_preparation_inputs_v1 import CnASharePortfolioPreparationInputsV1
from .execution import BAR_OPEN_CAPABILITY, BarOpenObservation
from .execution_inputs import _read_instrument_catalog, _read_instrument_id, _read_ledger_schema, _read_money, _read_utc
from .target_repository import BacktestTargetStreamRef, BacktestTargetStreamRepository, _artifact_ref
from .target_stream import TARGET_STREAM_EVENT_TYPE

_ARTIFACT_TYPE = "backtest_execution_input_bundle"
_VERSION = 8
_STREAM = "bars.open"
_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")


def _fields(value: object, name: str, expected: set[str]) -> dict:
    if not isinstance(value, Mapping) or set(value) != expected:
        raise ValueError(f"{name} must have exact V8 source fields")
    return dict(value)


def _scope(raw: object) -> CnASharePortfolioPreparationInputsV1:
    fields = _fields(raw, "portfolio scope", {
        "type", "schema_version", "account_id", "instrument_ids", "instrument_catalog",
        "ledger_schema", "initial_cash", "target_stream_ref", "market_bundle_ref",
        "shared_cny_funding_authority_qualified", "trade_authorized",
    })
    if (fields["type"] != "cn_a_share_portfolio_preparation_inputs"
            or type(fields["schema_version"]) is not int or fields["schema_version"] != 1
            or fields["shared_cny_funding_authority_qualified"] is not False
            or fields["trade_authorized"] is not False):
        raise ValueError("portfolio V8 scope must be unqualified input-only")
    target = _fields(fields["target_stream_ref"], "target ref", {"type", "artifact_ref"})
    if target["type"] != "backtest_target_stream_ref":
        raise ValueError("portfolio target ref type mismatch")
    bundle = _fields(fields["market_bundle_ref"], "bundle ref", {"type", "bundle_key", "manifest_hash"})
    if bundle["type"] != "market_bundle_ref":
        raise ValueError("portfolio market bundle ref type mismatch")
    ids = fields["instrument_ids"]
    if not isinstance(ids, (tuple, list)):
        raise ValueError("portfolio instrument_ids must be source sequence")
    result = CnASharePortfolioPreparationInputsV1(
        fields["account_id"], tuple(_read_instrument_id(value) for value in ids),
        _read_instrument_catalog(fields["instrument_catalog"]), _read_ledger_schema(fields["ledger_schema"]),
        _read_money(fields["initial_cash"]), BacktestTargetStreamRef(_artifact_ref(target["artifact_ref"])),
        MarketBundleRef(bundle["bundle_key"], bundle["manifest_hash"]),
    )
    if canonical_bytes(fields) != canonical_bytes(result):
        raise ValueError("portfolio scope source not canonical")
    return result


@dataclass(frozen=True, slots=True)
class CnASharePortfolioCaseInputV8:
    """Verified fixture preimage, not a ResolvedExecutionCase or a Fill."""

    scope: CnASharePortfolioPreparationInputsV1
    target_stream_digest: str
    bar_stream_key: str
    bar_bindings: tuple[tuple[str, str, InstrumentId, UtcInstant], ...]

    def __post_init__(self) -> None:
        if type(self.scope) is not CnASharePortfolioPreparationInputsV1:
            raise TypeError("portfolio Case requires exact declaration")
        if type(self.target_stream_digest) is not str or _HASH.fullmatch(self.target_stream_digest) is None:
            raise ValueError("portfolio Case target digest must be canonical")
        if self.bar_stream_key != _STREAM or type(self.bar_bindings) is not tuple or not self.bar_bindings:
            raise ValueError("portfolio Case needs retained BarOpen bindings")
        if (any(type(b) is not tuple or len(b) != 4 or type(b[0]) is not str or not b[0]
                or type(b[1]) is not str or _HASH.fullmatch(b[1]) is None
                or type(b[2]) is not InstrumentId or type(b[3]) is not UtcInstant
                for b in self.bar_bindings)
                or len({b[0] for b in self.bar_bindings}) != len(self.bar_bindings)
                or {b[2] for b in self.bar_bindings} != set(self.scope.instrument_ids)
                or self.bar_bindings != tuple(sorted(self.bar_bindings,
                    key=lambda b: (b[3].epoch_nanoseconds, b[2].venue.value, b[2].stable_key, b[0])))):
            raise ValueError("portfolio Case opening events must exact-cover sorted instruments")

    @property
    def case_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "cn_a_share_portfolio_case_input", "schema_version": 1,
                "scope": self.scope, "target_stream_digest": self.target_stream_digest,
                "bar_stream_key": self.bar_stream_key, "bar_bindings": self.bar_bindings,
                "synthetic_development_only": True, "trade_authorized": False}


def _read_payload(raw: object) -> CnASharePortfolioCaseInputV8:
    payload = _fields(raw, "V8 payload", {"type", "schema_version", "case"})
    if payload["type"] != "cn_a_share_portfolio_case_input_bundle" or type(payload["schema_version"]) is not int or payload["schema_version"] != 8:
        raise ValueError("expected CN portfolio case input bundle@8")
    data = _fields(payload["case"], "V8 Case", {"type", "schema_version", "scope", "target_stream_digest",
                                                   "bar_stream_key", "bar_bindings", "synthetic_development_only", "trade_authorized"})
    if (data["type"] != "cn_a_share_portfolio_case_input" or type(data["schema_version"]) is not int
            or data["schema_version"] != 1 or data["synthetic_development_only"] is not True
            or data["trade_authorized"] is not False or not isinstance(data["bar_bindings"], (tuple, list))):
        raise ValueError("V8 Case grade or binding schema mismatch")
    bars = []
    for raw_binding in data["bar_bindings"]:
        if not isinstance(raw_binding, (tuple, list)) or len(raw_binding) != 4:
            raise ValueError("V8 BarOpen binding tuple malformed")
        event_id, event_hash, instrument, at = raw_binding
        bars.append((event_id, event_hash, _read_instrument_id(instrument), _read_utc(at)))
    result = CnASharePortfolioCaseInputV8(_scope(data["scope"]), data["target_stream_digest"],
                                          data["bar_stream_key"], tuple(bars))
    if canonical_bytes(data) != canonical_bytes(result):
        raise ValueError("V8 Case source reconstruction mismatch")
    return result


_CATALOG = SchemaCatalog((ArtifactSchemaRegistration(_ARTIFACT_TYPE, _VERSION, _read_payload),))


def _cny_open(event: MarketEvent) -> bool:
    observation = BarOpenObservation.from_event(event)
    return observation.open_price is None or observation.open_price.quote_currency == "CNY"


def _from_sources(scope: CnASharePortfolioPreparationInputsV1, *,
                  target_reader: ArtifactEnvelopeReader, market_reader: MarketBundleReader) -> CnASharePortfolioCaseInputV8:
    if (type(scope) is not CnASharePortfolioPreparationInputsV1
            or not callable(getattr(target_reader, "read", None))
            or not isinstance(market_reader, MarketBundleReader)):
        raise TypeError("portfolio V8 requires exact scope and immutable source readers")
    if (market_reader.bundle_ref != scope.market_bundle_ref
            or MarketBundleRef.from_manifest(market_reader.manifest) != scope.market_bundle_ref
            or market_reader.manifest.instrument_catalog_hash != canonical_sha256(scope.instrument_catalog)):
        raise ValueError("portfolio V8 bundle/catalog identity mismatch")
    if market_reader.validate_requirements(required_capabilities=(BAR_OPEN_CAPABILITY,),
                                           required_streams=(_STREAM,)) is not None:
        raise ValueError("portfolio V8 BarOpen source not retained")
    target = BacktestTargetStreamRepository(reader=target_reader).load(scope.target_stream_ref)
    if not target.target_stream.events:
        raise ValueError("portfolio V8 target stream empty")
    cursor = market_reader.open_cursor(_STREAM, batch_size=64)
    if isinstance(cursor, InputValidationFailure):
        raise ValueError("portfolio V8 opening stream unavailable")
    if type(cursor) is not EventCursor or cursor.stream_manifest.event_count > 4096:
        raise ValueError("portfolio V8 opening stream unsupported or oversized")
    events = []
    while not cursor.exhausted:
        batch, advanced = market_reader.read_batch(cursor)
        if not batch or advanced.position <= cursor.position:
            raise ValueError("portfolio V8 opening source did not advance")
        events.extend(batch)
        cursor = advanced
    if (not events or any(event.instrument_id not in scope.instrument_ids
                          or not event.source_key.startswith(("fixture.", "synthetic."))
                          or not _cny_open(event)
                          for event in events)
            or len({(event.instrument_id, event.event_time) for event in events}) != len(events)):
        raise ValueError("portfolio V8 fixture BarOpen identity/status mismatch")
    by_open: dict[UtcInstant, set[InstrumentId]] = {}
    for event in events:
        by_open.setdefault(event.event_time, set()).add(event.instrument_id)
    if any(codes != set(scope.instrument_ids) for codes in by_open.values()):
        raise ValueError("portfolio V8 opening events must exact-cover every scoped open")
    for target_event in target.target_stream.events:
        if (target_event.event_type != TARGET_STREAM_EVENT_TYPE
                or not target_event.source_key.startswith("fixture.")
                or not any(target_event.event_time < bar.event_time for bar in events)):
            raise ValueError("portfolio V8 target must precede frozen fixture opens")
        candidate = target_event.payload.get("candidate")
        if not isinstance(candidate, Mapping) or not isinstance(candidate.get("targets"), (tuple, list)):
            raise ValueError("portfolio V8 target candidate missing")
        listed = candidate["targets"]
        ids = []
        for item in listed:
            if not isinstance(item, Mapping) or not isinstance(item.get("instrument_id"), Mapping):
                raise ValueError("portfolio V8 target entry malformed")
            ident = item["instrument_id"]
            ids.append(_read_instrument_id({"type": "instrument_id", "venue": ident["venue"],
                                            "stable_key": ident["stable_key"]}))
        if len(set(ids)) != len(ids) or not set(ids).issubset(scope.instrument_ids):
            raise ValueError("portfolio V8 target outside frozen instrument scope")
    bindings = tuple(sorted(((event.event_id, event.event_hash, event.instrument_id, event.event_time)
                             for event in events), key=lambda b: (b[3].epoch_nanoseconds, b[2].venue.value,
                                                                   b[2].stable_key, b[0])))
    return CnASharePortfolioCaseInputV8(scope, target.target_stream.target_stream_digest, _STREAM, bindings)


def retain_cn_a_share_portfolio_case_input_v8(
    scope: CnASharePortfolioPreparationInputsV1, *, target_reader: ArtifactEnvelopeReader,
    market_reader: MarketBundleReader, publisher: ArtifactEnvelopePublisher,
) -> ArtifactRef:
    case = _from_sources(scope, target_reader=target_reader, market_reader=market_reader)
    envelope = _CATALOG.write_version(_ARTIFACT_TYPE, _VERSION,
                                     {"type": "cn_a_share_portfolio_case_input_bundle", "schema_version": 8,
                                      "case": case}).envelope
    ref = ArtifactRef.from_envelope(envelope)
    if not callable(getattr(publisher, "put", None)) or publisher.put(envelope=envelope) != ref:
        raise ValueError("portfolio V8 retained Case publication unavailable or wrong ref")
    return ref


def read_retained_cn_a_share_portfolio_case_input_v8(
    ref: ArtifactRef, *, reader: ArtifactEnvelopeReader,
    target_reader: ArtifactEnvelopeReader, market_reader: MarketBundleReader,
) -> CnASharePortfolioCaseInputV8:
    if type(ref) is not ArtifactRef or ref.artifact_type != _ARTIFACT_TYPE or ref.schema_version != _VERSION:
        raise ValueError("portfolio V8 Case ref type/version mismatch")
    retained = reader.read(ref=ref)
    if (type(retained) is not ArtifactReadResult or ArtifactRef.from_envelope(retained.envelope) != ref
            or retained.source_bytes != canonical_bytes(retained.envelope)
            or retained.source_hash != canonical_sha256(retained.envelope)):
        raise ValueError("portfolio V8 retained raw Case ref/bytes mismatch")
    decoded = _CATALOG.read(retained.source_bytes)
    if type(decoded.artifact) is not CnASharePortfolioCaseInputV8:
        raise ValueError("portfolio V8 independent raw decoder rejected Case")
    rebuilt = _from_sources(decoded.artifact.scope, target_reader=target_reader, market_reader=market_reader)
    if rebuilt != decoded.artifact:
        raise ValueError("portfolio V8 Case disagrees with frozen target or opening sources")
    return rebuilt
