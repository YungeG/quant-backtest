from __future__ import annotations

import inspect
import json
from dataclasses import fields, replace
from importlib import import_module
from pathlib import Path
from typing import Any, cast

import pytest
from crypto_quant_backtest import BarOpenKind, BarOpenObservation
from crypto_quant_bundle_builder import (
    LocalMarketBundleRepository,
    LocalMarketBundleRepositoryConfig,
    validate_market_bundle_v1,
)
from crypto_quant_domain import (
    InstrumentId,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    VenueId,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_market_data import (
    EventCursor,
    LocalMarketBundleReader,
    MarketBundleCapability,
    MarketBundleManifest,
    MarketEvent,
    MarketStreamManifest,
)

MODULE = import_module(
    "crypto_quant_bundle_builder.g12m_tushare_fixed_singleton_execution_bundle_v2"
)
ROOT = Path(__file__).parents[3]
ACCEPTED = (
    ROOT / "fixtures/market_data/providers/tushare/"
    "cn-a-share-daily-source-bounded-v2/publication.expected.json"
)
AUTHORITY = (
    ROOT.parent
    / "evidence/g12m-tushare-fixed-singleton-profile-build-authority-v2/decision.json"
)
FIXTURE = (
    ROOT / "fixtures/market_data/providers/tushare/"
    "g12m-fixed-singleton-execution-bundle-v2"
)
EXPECTED = FIXTURE / "execution-bundle.expected.json"
SUCCESSOR = "sha256:7e8ca1ebf63aeb4f5f36ab72073d258db64083028e6e2f4c1662941bd46c7d62"
RUNNABLE = "sha256:3d19c05e552aa61a7f1ff33bc2451d2d0cc13e0d3ee30acde46462bdfa65becf"
SOURCE_KEY = "tushare_cn_a_share.daily.publication.xshe.000001.v1"
PROJECTION_KEY = "g12m.tushare.fixed-singleton.bar-open.v2"
TARGET_KEY = "cn-a-share-fixed-singleton-zero-target-v1"


def _capability(value: dict[str, Any]) -> MarketBundleCapability:
    assert set(value) == {"type", "key", "version"}
    return MarketBundleCapability(value["key"], value["version"])


def _event(value: dict[str, Any]) -> MarketEvent:
    instrument = value["instrument_id"]
    return MarketEvent(
        event_id=value["event_id"],
        stream_key=value["stream_key"],
        event_type=value["event_type"],
        capability=_capability(value["capability"]),
        instrument_id=(
            None
            if instrument is None
            else InstrumentId(VenueId(instrument["venue"]), instrument["stable_key"])
        ),
        event_time=UtcInstant(value["event_time"]["epoch_nanoseconds"]),
        available_time=UtcInstant(value["available_time"]["epoch_nanoseconds"]),
        phase=TimelinePhase(value["phase"]["rank"], value["phase"]["code"]),
        source_sequence=SourceSequence(value["source_sequence"]["value"]),
        revision_id=value["revision_id"],
        supersedes_revision_id=value["supersedes_revision_id"],
        source_key=value["source_key"],
        source_hash=value["source_hash"],
        payload=value["payload"],
    )


def _manifest(value: dict[str, Any]) -> MarketBundleManifest:
    return MarketBundleManifest(
        bundle_key=value["bundle_key"],
        schema_version=value["schema_version"],
        coverage_start=UtcInstant(value["coverage_start"]["epoch_nanoseconds"]),
        coverage_end_exclusive=UtcInstant(
            value["coverage_end_exclusive"]["epoch_nanoseconds"]
        ),
        instrument_catalog_hash=value["instrument_catalog_hash"],
        capabilities=tuple(_capability(item) for item in value["capabilities"]),
        streams=tuple(
            MarketStreamManifest(
                item["stream_key"],
                item["event_type"],
                _capability(item["capability"]),
                item["event_count"],
                item["content_hash"],
            )
            for item in value["streams"]
        ),
        content_hash=value["content_hash"],
    )


def _inputs() -> tuple[
    MarketBundleManifest, tuple[MarketEvent, ...], tuple[MarketEvent, ...]
]:
    publication = json.loads(ACCEPTED.read_bytes())
    authority = json.loads(AUTHORITY.read_bytes())
    source_manifest = _manifest(publication["manifest"])
    source_events = tuple(_event(item) for item in publication["events"])
    target_events = tuple(
        _event(item) for item in authority["target_commitment"]["stream"]["events"]
    )
    return source_manifest, source_events, target_events


def _build(
    *,
    source_manifest: MarketBundleManifest | None = None,
    source_events: tuple[MarketEvent, ...] | None = None,
    target_events: tuple[MarketEvent, ...] | None = None,
    successor: str = SUCCESSOR,
    runnable: str = RUNNABLE,
):
    accepted_manifest, accepted_source, accepted_target = _inputs()
    return MODULE.build_g12m_tushare_fixed_singleton_execution_bundle_v2(
        successor_prerequisite_decision_hash=successor,
        runnable_authority_hash=runnable,
        source_manifest=accepted_manifest
        if source_manifest is None
        else source_manifest,
        source_events=accepted_source if source_events is None else source_events,
        target_events=accepted_target if target_events is None else target_events,
    )


def _result():
    outcome = _build()
    assert outcome.failure is None and outcome.result is not None
    return outcome.result


def _failure(outcome, code: str) -> None:
    assert outcome.result is None and outcome.failure is not None
    assert outcome.failure.code.value == code
    assert set(outcome.failure.to_canonical_dict()) == {
        "type",
        "schema_version",
        "code",
        "failure_hash",
    }


def _with_event(event: MarketEvent, **changes: object) -> MarketEvent:
    values = {
        item.name: changes.get(item.name, getattr(event, item.name))
        for item in fields(event)
    }
    return MarketEvent(**cast(Any, values))


def _forged(value: Any, **changes: object) -> Any:
    forged = object.__new__(type(value))
    for item in fields(value):
        object.__setattr__(
            forged, item.name, changes.get(item.name, getattr(value, item.name))
        )
    return forged


def _collect(
    reader: LocalMarketBundleReader, stream_key: str
) -> tuple[MarketEvent, ...]:
    cursor = reader.open_cursor(stream_key, batch_size=7)
    assert isinstance(cursor, EventCursor)
    events: list[MarketEvent] = []
    while not cursor.exhausted:
        batch, cursor = reader.read_batch(cursor)
        events.extend(batch)
    return tuple(events)


def test_exact_api_fixture_and_immutable_result() -> None:
    signature = inspect.signature(
        MODULE.build_g12m_tushare_fixed_singleton_execution_bundle_v2
    )
    assert list(signature.parameters) == [
        "successor_prerequisite_decision_hash",
        "runnable_authority_hash",
        "source_manifest",
        "source_events",
        "target_events",
    ]
    assert all(
        item.kind is inspect.Parameter.KEYWORD_ONLY
        for item in signature.parameters.values()
    )
    result = _result()
    expected = EXPECTED.read_bytes()
    assert canonical_bytes(result.to_canonical_dict()) + b"\n" == expected
    assert len(result.source_events) == len(result.projection_events) == 19
    assert len(result.target_events) == 1
    assert len(result.lineage_records) == 19
    assert result.instrument_catalog_hash == (
        "sha256:99df0de0dc3008cf557bb7634caf483fae27488c75016421218100df6a77a6cc"
    )
    assert canonical_sha256(result.instrument_catalog) == result.instrument_catalog_hash
    assert result.bundle_ref.manifest_hash == canonical_sha256(result.manifest)
    assert result.publication_hash == json.loads(expected)["publication_hash"]
    assert result.report_hash == json.loads(expected)["report_hash"]
    assert (
        canonical_bytes(result.instrument_catalog) + b"\n"
        == (FIXTURE / "instrument-catalog.expected.json").read_bytes()
    )
    assert (
        canonical_bytes(result.manifest) + b"\n"
        == (FIXTURE / "manifest.expected.json").read_bytes()
    )
    assert (
        result.source_stream_payload == (FIXTURE / "source.stream.payload").read_bytes()
    )
    assert (
        result.projection_stream_payload
        == (FIXTURE / "projection.stream.payload").read_bytes()
    )
    assert (
        result.target_stream_payload == (FIXTURE / "target.stream.payload").read_bytes()
    )
    assert (
        canonical_bytes(
            {
                "type": "g12m_tushare_bar_open_projection_lineage_set_v2",
                "schema_version": 2,
                "records": result.lineage_records,
                "lineage_hash": result.lineage_hash,
            }
        )
        + b"\n"
        == (FIXTURE / "lineage.expected.json").read_bytes()
    )


def test_source_is_byte_unchanged_and_all_projections_are_real_bar_open() -> None:
    _, accepted_source, _ = _inputs()
    accepted_bytes = canonical_bytes(accepted_source)
    result = _result()
    assert result.source_stream_payload == accepted_bytes
    assert canonical_bytes(result.source_events) == accepted_bytes
    assert tuple(event.event_hash for event in result.source_events) == (
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
    for source, projection, lineage in zip(
        result.source_events,
        result.projection_events,
        result.lineage_records,
        strict=True,
    ):
        observation = BarOpenObservation.from_event(projection)
        selected = cast(dict[str, Any], source.payload["execution_reference"])[
            "open_price"
        ]
        assert observation.kind is BarOpenKind.REAL
        assert observation.open_price is not None
        assert observation.open_price.units == selected["units"]
        assert observation.open_price.scale.places == selected["scale"]
        assert observation.open_price.quote_currency == selected["quote_currency"]
        assert (
            projection.event_time == projection.available_time == source.available_time
        )
        assert source.timeline_instant < projection.timeline_instant
        assert projection.timeline_instant < result.target_events[0].timeline_instant
        assert lineage.source_event_time == source.event_time
        assert lineage.source_available_time == source.available_time
        assert lineage.source_event_hash == source.event_hash
        assert lineage.to_canonical_dict()["selected_open_price"] == selected
        assert lineage.projection_event_hash == projection.event_hash
        assert lineage.projection_event_id == projection.event_id
    assert result.lineage_hash == canonical_sha256(
        {
            "type": "g12m_tushare_bar_open_projection_lineage_set_v2",
            "schema_version": 2,
            "records": result.lineage_records,
        }
    )


def test_exact_three_stream_g12c_publication_reader_reopen_and_retention(
    tmp_path: Path,
) -> None:
    result = _result()
    assert tuple(
        capability.identity for capability in result.manifest.capabilities
    ) == (
        "bar_open@1",
        "precomputed_target_stream@1",
        "tushare_cn_a_share.daily-publications@1",
    )
    assert tuple(stream.stream_key for stream in result.manifest.streams) == (
        TARGET_KEY,
        PROJECTION_KEY,
        SOURCE_KEY,
    )
    validation = validate_market_bundle_v1(
        bundle_key=result.manifest.bundle_key,
        schema_version=result.manifest.schema_version,
        coverage_start=result.manifest.coverage_start,
        coverage_end_exclusive=result.manifest.coverage_end_exclusive,
        instrument_catalog_hash=result.instrument_catalog_hash,
        events=(
            *result.source_events,
            *result.projection_events,
            *result.target_events,
        ),
    )
    assert validation.failure is None and validation.manifest == result.manifest

    repository = LocalMarketBundleRepository(
        config=LocalMarketBundleRepositoryConfig(root=tmp_path.resolve())
    )
    first = repository.publish_market_bundle_v1(
        manifest=result.manifest,
        stream_payloads=result.stream_payloads,
        retention_policy_ref="g12m.tushare.fixed-singleton.execution-bundle-v2",
    )
    assert first.failure is None and first.result is not None
    assert first.result.already_published is False
    first_bytes = {
        path.relative_to(tmp_path).as_posix(): path.read_bytes()
        for path in sorted(tmp_path.rglob("*"))
        if path.is_file()
    }
    repeated = repository.publish_market_bundle_v1(
        manifest=result.manifest,
        stream_payloads=result.stream_payloads,
        retention_policy_ref="g12m.tushare.fixed-singleton.execution-bundle-v2",
    )
    assert repeated.failure is None and repeated.result is not None
    assert repeated.result.already_published is True
    assert repeated.result.retention_proof == first.result.retention_proof
    assert {
        path.relative_to(tmp_path).as_posix(): path.read_bytes()
        for path in sorted(tmp_path.rglob("*"))
        if path.is_file()
    } == first_bytes

    first_reader = LocalMarketBundleReader.open(
        repository_root=tmp_path.resolve(), bundle_ref=result.bundle_ref
    )
    repeated_reader = LocalMarketBundleReader.open(
        repository_root=tmp_path.resolve(), bundle_ref=result.bundle_ref
    )
    for key, expected in (
        (SOURCE_KEY, result.source_events),
        (PROJECTION_KEY, result.projection_events),
        (TARGET_KEY, result.target_events),
    ):
        assert _collect(first_reader, key) == expected
        assert _collect(repeated_reader, key) == expected
    assert first_reader.bundle_ref == repeated_reader.bundle_ref == result.bundle_ref
    assert first_reader.manifest == repeated_reader.manifest == result.manifest


def test_authority_membership_target_payload_and_atomic_failure_precedence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, source, target = _inputs()
    _failure(_build(successor="sha256:" + "f" * 64), "authority_or_source_manifest")
    _failure(_build(runnable="sha256:" + "f" * 64), "authority_or_source_manifest")
    wrong_manifest = MarketBundleManifest.build(
        bundle_key="wrong",
        schema_version=manifest.schema_version,
        coverage_start=manifest.coverage_start,
        coverage_end_exclusive=manifest.coverage_end_exclusive,
        instrument_catalog_hash=manifest.instrument_catalog_hash,
        capabilities=manifest.capabilities,
        streams=manifest.streams,
    )
    _failure(_build(source_manifest=wrong_manifest), "authority_or_source_manifest")

    _failure(_build(source_events=source[:-1]), "source_membership")
    _failure(_build(source_events=(*source, source[-1])), "source_membership")
    _failure(_build(source_events=tuple(reversed(source))), "source_membership")
    changed_time = _with_event(
        source[0], event_time=UtcInstant(source[0].event_time.epoch_nanoseconds + 1)
    )
    _failure(_build(source_events=(changed_time, *source[1:])), "source_membership")
    changed_available = _with_event(
        source[0],
        available_time=UtcInstant(source[0].available_time.epoch_nanoseconds + 1),
    )
    _failure(
        _build(source_events=(changed_available, *source[1:])), "source_membership"
    )
    changed_open = json.loads(canonical_bytes(source[0].payload))
    changed_open["execution_reference"]["open_price"]["units"] += 1
    _failure(
        _build(
            source_events=(_with_event(source[0], payload=changed_open), *source[1:])
        ),
        "source_membership",
    )

    _failure(_build(target_events=()), "target")
    _failure(_build(target_events=(*target, *target)), "target")
    changed_target = _with_event(
        target[0], available_time=UtcInstant(_DECISION_NS_FOR_TEST() + 1)
    )
    _failure(_build(target_events=(changed_target,)), "target")
    _failure(
        _build(
            source_events=source[:-1],
            target_events=(),
            successor="sha256:" + "f" * 64,
        ),
        "authority_or_source_manifest",
    )
    _failure(_build(source_events=source[:-1], target_events=()), "source_membership")

    monkeypatch.setattr(MODULE, "_source_price", lambda event: None)
    _failure(_build(), "source_payload")


def _DECISION_NS_FOR_TEST() -> int:
    return 1_787_292_861_381_694_497


def test_projection_manifest_and_canonical_failures_are_atomic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_project = MODULE._project
    monkeypatch.setattr(
        MODULE,
        "_project",
        lambda *args: (_ for _ in ()).throw(ValueError("projection")),
    )
    _failure(_build(), "projection")
    monkeypatch.setattr(MODULE, "_project", original_project)

    monkeypatch.setattr(MODULE, "_build_manifest", lambda events: None)
    _failure(_build(), "catalog_or_manifest")


def test_result_and_lineage_reject_subclass_and_constructor_bypass() -> None:
    result = _result()
    lineage = result.lineage_records[0]
    forged_lineage = _forged(lineage, source_event_hash="sha256:" + "f" * 64)
    with pytest.raises(ValueError, match="canonical binding"):
        replace(result, lineage_records=(forged_lineage, *result.lineage_records[1:]))

    forged_event = _forged(
        result.projection_events[0], source_hash="sha256:" + "f" * 64
    )
    with pytest.raises(ValueError, match="canonical binding"):
        replace(
            result,
            projection_events=(forged_event, *result.projection_events[1:]),
        )

    class DerivedEvent(MarketEvent):
        pass

    derived = DerivedEvent(
        **{
            item.name: getattr(result.source_events[0], item.name)
            for item in fields(MarketEvent)
        }
    )
    outcome = _build(source_events=(derived, *result.source_events[1:]))
    _failure(outcome, "source_membership")
