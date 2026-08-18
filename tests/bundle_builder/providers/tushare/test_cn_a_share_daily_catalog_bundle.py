from __future__ import annotations

import hashlib
import inspect
import json
from dataclasses import fields
from datetime import date
from importlib import import_module
from pathlib import Path

import pytest
from crypto_quant_bundle_builder import (
    BarBucket,
    LocalMarketBundleRepository,
    LocalMarketBundleRepositoryConfig,
    RawSourceMember,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
    validate_market_bundle_v1,
)
from crypto_quant_domain import (
    CurrencyId,
    InstrumentCatalog,
    InstrumentDefinition,
    InstrumentId,
    InstrumentType,
    SessionId,
    TradingDate,
    UtcInstant,
    VenueId,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_market_data import MarketEvent

ROOT = Path(__file__).parents[3]
DAILY_FIXTURE = ROOT / "fixtures/market_data/providers/tushare/cn-a-share-daily-listing-v1"
EVENT_TIME_FIXTURE = ROOT / "fixtures/market_data/providers/tushare/cn-a-share-trade-calendar-v1/daily-event-time.expected.json"
EXPECTED_FIXTURE = ROOT / "fixtures/market_data/providers/tushare/cn-a-share-daily-bundle-v2.expected.json"
EXPECTED = json.loads(EXPECTED_FIXTURE.read_text())
DAILY_BYTES = (DAILY_FIXTURE / "daily.json").read_bytes()
STOCK_BYTES = (DAILY_FIXTURE / "stock-basic.json").read_bytes()
ACQUIRED_AT = 1_786_943_026_685_846_805
CATALOG_MEMBER = "response/stock-basic.json"
CATALOG_HASH = "sha256:99df0de0dc3008cf557bb7634caf483fae27488c75016421218100df6a77a6cc"
MODULE = import_module("crypto_quant_bundle_builder.tushare_cn_a_share_daily_catalog_bundle")
NORMALIZER = import_module("crypto_quant_bundle_builder.tushare_cn_a_share_daily")
V1_BUNDLE = import_module("crypto_quant_bundle_builder.tushare_cn_a_share_daily_bundle")


def _bucket() -> BarBucket:
    event_time = json.loads(EVENT_TIME_FIXTURE.read_text())
    spans = tuple(
        (
            UtcInstant(value["start"]["epoch_nanoseconds"]),
            UtcInstant(value["end_exclusive"]["epoch_nanoseconds"]),
        )
        for value in event_time["bucket"]["included_spans"]
    )
    return BarBucket(
        SessionId("CN.XSHE", "2024-01-02.regular"),
        TradingDate("CN.XSHE", date(2024, 1, 2)),
        spans,
        spans[0][0],
        spans[-1][1],
    )


def _normalized_result(
    *,
    stock_bytes: bytes | None = STOCK_BYTES,
    stock_key: str = CATALOG_MEMBER,
    stock_acquired_at: int = ACQUIRED_AT,
    extra_members: tuple[tuple[str, bytes], ...] = (),
    provenance: SourceSnapshotProvenance | None = None,
):
    members = [RawSourceMember("response/daily.json", DAILY_BYTES, "0644", ACQUIRED_AT, None)]
    if stock_bytes is not None:
        members.append(RawSourceMember(stock_key, stock_bytes, "0644", stock_acquired_at, None))
    members.extend(
        RawSourceMember(key, value, "0644", ACQUIRED_AT, None)
        for key, value in extra_members
    )
    snapshot_outcome = freeze_source_snapshot(
        members=tuple(members),
        provenance=provenance
        or SourceSnapshotProvenance(
            "tushare.pro",
            "tushare.pro.daily_listing.000001.sz.20240102",
            "tushare.pro.terms",
            "backtest.acquisition.candidate",
        ),
    )
    assert snapshot_outcome.snapshot is not None
    snapshot = snapshot_outcome.snapshot
    daily_member = next(member for member in snapshot.members if member.member_key == "response/daily.json")
    normalized = NORMALIZER.normalize_tushare_cn_a_share_daily_v1(
        snapshot,
        NORMALIZER.TushareCnAShareDailyNormalizationRequest(
            1,
            snapshot.snapshot_id,
            snapshot.provenance_hash,
            "response/daily.json",
            daily_member.content_hash,
            InstrumentId(VenueId("xshe"), "000001"),
            "20240102",
            _bucket(),
        ),
    )
    assert normalized.failure is None and normalized.result is not None
    return normalized.result


def _stock_json(mutator) -> bytes:
    value = json.loads(STOCK_BYTES)
    mutator(value)
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()


def _failure(result) -> object:
    outcome = MODULE.project_tushare_cn_a_share_daily_catalog_bound_market_event_v2(result)
    assert outcome.result is None and outcome.failure is not None
    return outcome.failure.code


def _forge(value: object, **changes: object) -> object:
    forged = object.__new__(type(value))
    for field in fields(value):
        object.__setattr__(forged, field.name, changes.get(field.name, getattr(value, field.name)))
    return forged


def test_internal_contract_is_exact_and_hashes_are_derived() -> None:
    assert list(MODULE.TushareCnAShareDailyCatalogPublicationFailureCode) == [
        MODULE.TushareCnAShareDailyCatalogPublicationFailureCode.NORMALIZATION_AUTHORITY_INVALID,
        MODULE.TushareCnAShareDailyCatalogPublicationFailureCode.SNAPSHOT_SCOPE_MISMATCH,
        MODULE.TushareCnAShareDailyCatalogPublicationFailureCode.CATALOG_MEMBER_MISSING,
        MODULE.TushareCnAShareDailyCatalogPublicationFailureCode.CATALOG_JSON_INVALID,
        MODULE.TushareCnAShareDailyCatalogPublicationFailureCode.CATALOG_SCHEMA_MISMATCH,
        MODULE.TushareCnAShareDailyCatalogPublicationFailureCode.CATALOG_MEMBER_BINDING_MISMATCH,
    ]
    assert [field.name for field in fields(MODULE.TushareCnAShareAcquisitionCatalogSource)] == [
        "snapshot_id", "provenance_hash", "source_key", "member_key",
        "member_content_hash", "record_index", "acquired_at", "provider_ts_code",
        "provider_symbol", "provider_name", "provider_area", "provider_industry",
        "provider_market", "provider_exchange", "provider_list_status",
        "provider_list_date", "provider_delist_date", "source_record_hash",
        "instrument_catalog_hash", "current_metadata_only", "provider_revision_id",
        "revision_closure_complete", "historical_listing_status_qualified",
        "survivorship_bias_safe", "decision_grade_eligible", "deployment_authorized",
    ]
    assert [field.name for field in fields(MODULE.TushareCnAShareDailyCatalogPublicationFailure)] == ["code"]
    assert [field.name for field in fields(MODULE.TushareCnAShareDailyCatalogPublicationResult)] == [
        "normalization_result", "instrument_catalog", "catalog_source", "market_event"
    ]
    assert [field.name for field in fields(MODULE.TushareCnAShareDailyCatalogPublicationOutcome)] == ["result", "failure"]
    signature = inspect.signature(MODULE.project_tushare_cn_a_share_daily_catalog_bound_market_event_v2)
    assert list(signature.parameters) == ["result"]
    assert signature.return_annotation == "TushareCnAShareDailyCatalogPublicationOutcome"
    with pytest.raises(ValueError, match="exactly one"):
        MODULE.TushareCnAShareDailyCatalogPublicationOutcome()
    with pytest.raises(ValueError, match="exactly one"):
        MODULE.TushareCnAShareDailyCatalogPublicationOutcome(
            result=object(), failure=object()
        )
    failure = MODULE.TushareCnAShareDailyCatalogPublicationFailure(
        MODULE.TushareCnAShareDailyCatalogPublicationFailureCode.CATALOG_JSON_INVALID
    )
    assert failure.failure_hash == canonical_sha256({
        "type": "tushare_cn_a_share_daily_catalog_publication_failure",
        "schema_version": 1,
        "code": "catalog_json_invalid",
    })


def test_exact_catalog_source_event_and_publication_match_golden() -> None:
    result = _normalized_result()
    outcome = MODULE.project_tushare_cn_a_share_daily_catalog_bound_market_event_v2(result)
    assert outcome.failure is None and outcome.result is not None
    publication = outcome.result
    source = publication.catalog_source
    event = publication.market_event
    v1 = V1_BUNDLE.project_tushare_cn_a_share_daily_market_event_v1(result)

    assert type(publication.instrument_catalog) is InstrumentCatalog
    assert publication.instrument_catalog == InstrumentCatalog(
        currencies=(CurrencyId("CNY"),),
        instruments=(InstrumentDefinition(
            InstrumentId(VenueId("xshe"), "000001"), InstrumentType.EQUITY,
            None, CurrencyId("CNY"), CurrencyId("CNY"),
        ),),
        symbol_timelines=(),
    )
    assert json.loads(canonical_bytes(publication.instrument_catalog)) == EXPECTED["instrument_catalog"]
    assert publication.instrument_catalog_hash == CATALOG_HASH == EXPECTED["instrument_catalog_hash"]
    assert source.to_canonical_dict() == EXPECTED["catalog_source"]
    assert source.source_record_hash == EXPECTED["source_record_hash"]
    assert source.catalog_source_hash == EXPECTED["catalog_source_hash"]
    assert publication.catalog_binding_hash == EXPECTED["catalog_binding_hash"]
    assert publication.to_canonical_dict() == EXPECTED["publication"]
    assert publication.publication_hash == EXPECTED["publication_hash"]
    assert json.loads(canonical_bytes(event)) == EXPECTED["event"]
    assert event.event_hash == EXPECTED["event_hash"]

    for attribute in (
        "instrument_id", "event_time", "available_time", "phase", "source_sequence",
        "revision_id", "supersedes_revision_id", "source_key", "source_hash",
    ):
        assert getattr(event, attribute) == getattr(v1, attribute)
    for key in ("normalization_hash", "raw_bar", "source_trace", "execution_reference", "valuation"):
        assert canonical_bytes(event.payload[key]) == canonical_bytes(v1.payload[key])
    assert event.event_id == "tushare-cn-a-share-daily-v2:" + publication.catalog_binding_hash
    assert event.stream_key == "tushare_cn_a_share.daily.publication.xshe.000001.v2"
    assert event.event_type == "tushare_cn_a_share_daily_publication.v2"
    assert event.capability.identity == "tushare_cn_a_share.daily-publications@2"
    assert event.supersedes_revision_id is None
    assert set(event.payload) == {
        "normalization_hash", "raw_bar", "source_trace", "execution_reference", "valuation",
        "instrument_catalog", "instrument_catalog_hash", "catalog_source",
        "catalog_binding_hash", "qualification",
    }
    assert event.payload["qualification"] == {
        "current_metadata_only": True,
        "provider_revision_id": None,
        "provider_revision_closure_complete": False,
        "revision_closure_complete": False,
        "historical_listing_status_qualified": False,
        "survivorship_bias_safe": False,
        "corporate_actions_qualified": False,
        "decision_grade_eligible": False,
        "deployment_authorized": False,
    }


def test_catalog_bound_event_passes_unchanged_through_g12c_and_g12d(tmp_path: Path) -> None:
    result = _normalized_result()
    publication = MODULE.project_tushare_cn_a_share_daily_catalog_bound_market_event_v2(result).result
    assert publication is not None
    embedded = publication.market_event.payload["instrument_catalog"]
    reconstructed = InstrumentCatalog(
        currencies=tuple(CurrencyId(value["value"]) for value in embedded["currencies"]),
        instruments=tuple(InstrumentDefinition(
            InstrumentId(VenueId(value["instrument_id"]["venue"]), value["instrument_id"]["stable_key"]),
            InstrumentType(value["instrument_type"]), None,
            CurrencyId(value["quote_currency"]["value"]),
            CurrencyId(value["settlement_currency"]["value"]),
        ) for value in embedded["instruments"]),
        symbol_timelines=(),
    )
    assert canonical_bytes(reconstructed) == canonical_bytes(publication.instrument_catalog)
    assert (
        publication.instrument_catalog_hash
        == publication.catalog_source.instrument_catalog_hash
        == publication.market_event.payload["instrument_catalog_hash"]
        == canonical_sha256(reconstructed)
    )
    validation = validate_market_bundle_v1(
        bundle_key="tushare-cn-a-share-daily-000001-20240102-v2",
        schema_version=1,
        coverage_start=result.raw_bar.bucket.interval_start,
        coverage_end_exclusive=result.raw_bar.bucket.interval_end_exclusive,
        instrument_catalog_hash=publication.instrument_catalog_hash,
        events=(publication.market_event,),
    )
    assert validation.failure is None and validation.manifest is not None
    manifest = validation.manifest
    assert json.loads(canonical_bytes(manifest)) == EXPECTED["manifest"]
    assert manifest.instrument_catalog_hash == publication.instrument_catalog_hash
    assert manifest.content_hash == EXPECTED["manifest_content_hash"]
    assert manifest.streams[0].content_hash == EXPECTED["stream_content_hash"]
    repository = LocalMarketBundleRepository(
        config=LocalMarketBundleRepositoryConfig(tmp_path.resolve())
    )
    arguments = {
        "manifest": manifest,
        "stream_payloads": {publication.market_event.stream_key: canonical_bytes((publication.market_event,))},
        "retention_policy_ref": "retention.g12cd-tushare-cn-a-share-daily-v2",
    }
    first = repository.publish_market_bundle_v1(**arguments)
    assert first.failure is None and first.result is not None
    assert first.result.already_published is False
    assert first.result.bundle_ref.to_canonical_dict() == EXPECTED["bundle_ref"]
    assert first.result.retention_proof.proof_hash == EXPECTED["retention_proof_hash"]
    before = {path.relative_to(tmp_path): path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    replay = repository.publish_market_bundle_v1(**arguments)
    after = {path.relative_to(tmp_path): path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    assert replay.failure is None and replay.result is not None
    assert replay.result.already_published is True
    assert replay.result.bundle_ref == first.result.bundle_ref
    assert replay.result.retention_proof == first.result.retention_proof
    assert after == before


def test_authority_scope_missing_and_multiple_member_precedence() -> None:
    codes = MODULE.TushareCnAShareDailyCatalogPublicationFailureCode
    assert _failure(object()) is codes.NORMALIZATION_AUTHORITY_INVALID
    result = _normalized_result()
    forged_snapshot = _forge(result.snapshot, archive_bytes=b"not-an-archive")
    assert _failure(_forge(result, snapshot=forged_snapshot)) is codes.NORMALIZATION_AUTHORITY_INVALID

    for name, wrong in (
        ("vendor_key", "other.vendor"),
        ("source_key", "other.source"),
        ("license_ref", "other.terms"),
        ("retention_policy_ref", "other.retention"),
    ):
        values = {
            "vendor_key": "tushare.pro",
            "source_key": "tushare.pro.daily_listing.000001.sz.20240102",
            "license_ref": "tushare.pro.terms",
            "retention_policy_ref": "backtest.acquisition.candidate",
        }
        values[name] = wrong
        scoped = _normalized_result(provenance=SourceSnapshotProvenance(**values))
        assert _failure(scoped) is codes.SNAPSHOT_SCOPE_MISMATCH

    assert _failure(_normalized_result(stock_bytes=None)) is codes.CATALOG_MEMBER_MISSING
    multiple = _normalized_result(extra_members=(("response/other.json", STOCK_BYTES),))
    assert _failure(multiple) is codes.CATALOG_MEMBER_BINDING_MISMATCH
    wrong_scope_missing = _normalized_result(
        stock_bytes=None,
        provenance=SourceSnapshotProvenance("other.vendor", "other.source", "other.terms", "other.retention"),
    )
    assert _failure(wrong_scope_missing) is codes.SNAPSHOT_SCOPE_MISMATCH
    wrong_scope_multiple = _normalized_result(
        extra_members=(("response/other.json", STOCK_BYTES),),
        provenance=SourceSnapshotProvenance("other.vendor", "other.source", "other.terms", "other.retention"),
    )
    assert _failure(wrong_scope_multiple) is codes.SNAPSHOT_SCOPE_MISMATCH


@pytest.mark.parametrize("value", [
    b"\xff", b"{", STOCK_BYTES.replace(b'"code":0', b'"code":0,"code":0'),
    STOCK_BYTES.replace(b'"code":0', b'"code":NaN'),
])
def test_catalog_json_failures_are_atomic(value: bytes) -> None:
    codes = MODULE.TushareCnAShareDailyCatalogPublicationFailureCode
    outcome = MODULE.project_tushare_cn_a_share_daily_catalog_bound_market_event_v2(
        _normalized_result(stock_bytes=value)
    )
    assert outcome.result is None
    assert outcome.failure is not None and outcome.failure.code is codes.CATALOG_JSON_INVALID


@pytest.mark.parametrize("mutator", [
    lambda value: value.__setitem__("extra", None),
    lambda value: value.pop("detail"),
    lambda value: value.__setitem__("request_id", ""),
    lambda value: value.__setitem__("code", False),
    lambda value: value.__setitem__("code", 0.0),
    lambda value: value.__setitem__("msg", "error"),
    lambda value: value.__setitem__("detail", None),
    lambda value: value["data"].__setitem__("extra", None),
    lambda value: value["data"].__setitem__("has_more", True),
    lambda value: value["data"].__setitem__("count", False),
    lambda value: value["data"].__setitem__("count", 1),
    lambda value: value["data"].__setitem__("fields", value["data"]["fields"][:-1]),
    lambda value: value["data"].__setitem__("items", []),
    lambda value: value["data"].__setitem__("items", value["data"]["items"] * 2),
    lambda value: value["data"]["items"][0].__setitem__(0, 1),
    lambda value: value["data"]["items"][0].__setitem__(2, "e\u0301"),
    lambda value: value["data"]["items"][0].append(None),
])
def test_catalog_schema_failures_are_exact(mutator) -> None:
    codes = MODULE.TushareCnAShareDailyCatalogPublicationFailureCode
    assert _failure(_normalized_result(stock_bytes=_stock_json(mutator))) is codes.CATALOG_SCHEMA_MISMATCH


def test_detail_accepts_any_json_string_before_frozen_member_binding() -> None:
    codes = MODULE.TushareCnAShareDailyCatalogPublicationFailureCode
    for detail in (" padded ", "e\u0301"):
        changed = _stock_json(lambda value, detail=detail: value.__setitem__("detail", detail))
        assert _failure(_normalized_result(stock_bytes=changed)) is codes.CATALOG_MEMBER_BINDING_MISMATCH
    changed = _stock_json(lambda value: value.__setitem__("detail", None))
    assert _failure(_normalized_result(stock_bytes=changed)) is codes.CATALOG_SCHEMA_MISMATCH


def test_member_binding_checks_follow_valid_json_and_schema() -> None:
    codes = MODULE.TushareCnAShareDailyCatalogPublicationFailureCode
    assert _failure(_normalized_result(stock_key="response/not-stock-basic.json")) is codes.CATALOG_MEMBER_BINDING_MISMATCH
    assert _failure(_normalized_result(stock_acquired_at=ACQUIRED_AT + 1)) is codes.CATALOG_MEMBER_BINDING_MISMATCH
    assert _failure(_normalized_result(stock_bytes=_stock_json(lambda value: value.__setitem__("request_id", "different")))) is codes.CATALOG_MEMBER_BINDING_MISMATCH
    row = json.loads(STOCK_BYTES)["data"]["items"][0]
    replacements = ["000002.SZ", "000002", "别名", "上海", "证券", "创业板", "SSE", "D", "19910404", "20000101"]
    for index, replacement in enumerate(replacements):
        def mutate(value, index=index, replacement=replacement):
            value["data"]["items"][0][index] = replacement
        assert row[index] != replacement
        assert _failure(_normalized_result(stock_bytes=_stock_json(mutate))) is codes.CATALOG_MEMBER_BINDING_MISMATCH

    malformed = _normalized_result(stock_bytes=b"{")
    assert _failure(malformed) is codes.CATALOG_JSON_INVALID
    schema = _normalized_result(stock_bytes=_stock_json(lambda value: value["data"].__setitem__("count", 1)))
    assert _failure(schema) is codes.CATALOG_SCHEMA_MISMATCH


def test_authority_failures_hide_member_secret_sentinels_without_catching_baseexception() -> None:
    codes = MODULE.TushareCnAShareDailyCatalogPublicationFailureCode
    result = _normalized_result()
    catalog_member = next(member for member in result.snapshot.members if member.member_key == CATALOG_MEMBER)

    class SecretStr(str):
        __hash__ = str.__hash__

        def __eq__(self, other):
            raise RuntimeError("member-secret-sentinel")

    for field_name, value in (
        ("mode", SecretStr("0644")),
        ("content_hash", SecretStr(catalog_member.content_hash)),
        ("declared_sha256", SecretStr("sha256:" + "0" * 64)),
    ):
        forged_member = _forge(catalog_member, **{field_name: value})
        forged_members = tuple(
            forged_member if member.member_key == CATALOG_MEMBER else member
            for member in result.snapshot.members
        )
        forged_result = _forge(result, snapshot=_forge(result.snapshot, members=forged_members))
        outcome = MODULE.project_tushare_cn_a_share_daily_catalog_bound_market_event_v2(forged_result)
        assert outcome.result is None
        assert outcome.failure is not None and outcome.failure.code is codes.NORMALIZATION_AUTHORITY_INVALID
        assert "secret" not in json.dumps(outcome.failure.to_canonical_dict())

    class SecretAbort(BaseException):
        pass

    class AbortStr(str):
        __hash__ = str.__hash__

        def __eq__(self, other):
            raise SecretAbort

    abort_member = _forge(catalog_member, mode=AbortStr("0644"))
    abort_members = tuple(
        abort_member if member.member_key == CATALOG_MEMBER else member
        for member in result.snapshot.members
    )
    with pytest.raises(SecretAbort):
        MODULE.project_tushare_cn_a_share_daily_catalog_bound_market_event_v2(
            _forge(result, snapshot=_forge(result.snapshot, members=abort_members))
        )


def test_deep_authority_reconstruction_rejects_hostile_equivalent_values() -> None:
    publication = MODULE.project_tushare_cn_a_share_daily_catalog_bound_market_event_v2(_normalized_result()).result
    assert publication is not None

    class HostileStr(str):
        def __eq__(self, other):
            return True

        def __hash__(self):
            return str.__hash__(self)

    source_values = {field.name: getattr(publication.catalog_source, field.name) for field in fields(publication.catalog_source)}
    source_values["source_key"] = HostileStr(publication.catalog_source.source_key)
    with pytest.raises((TypeError, ValueError), match="text|source"):
        MODULE.TushareCnAShareAcquisitionCatalogSource(**source_values)

    forged_currency = object.__new__(CurrencyId)
    object.__setattr__(forged_currency, "value", HostileStr("CNY"))
    forged_catalog = _forge(publication.instrument_catalog, currencies=(forged_currency,))
    with pytest.raises((TypeError, ValueError), match="catalog"):
        MODULE.TushareCnAShareDailyCatalogPublicationResult(
            publication.normalization_result, forged_catalog,
            publication.catalog_source, publication.market_event,
        )

    forged_event = _forge(publication.market_event, source_key=HostileStr(publication.market_event.source_key))
    with pytest.raises((TypeError, ValueError), match="event"):
        MODULE.TushareCnAShareDailyCatalogPublicationResult(
            publication.normalization_result, publication.instrument_catalog,
            publication.catalog_source, forged_event,
        )


def test_result_retains_only_reconstructed_catalog_source_and_event() -> None:
    publication = MODULE.project_tushare_cn_a_share_daily_catalog_bound_market_event_v2(_normalized_result()).result
    assert publication is not None
    caller_catalog = publication.instrument_catalog
    caller_source = publication.catalog_source
    caller_event = publication.market_event
    rebuilt = MODULE.TushareCnAShareDailyCatalogPublicationResult(
        publication.normalization_result, caller_catalog, caller_source, caller_event,
    )
    assert rebuilt.instrument_catalog is not caller_catalog
    assert rebuilt.catalog_source is not caller_source
    assert rebuilt.market_event is not caller_event
    expected_hash = rebuilt.publication_hash
    object.__setattr__(caller_catalog, "currencies", ())
    object.__setattr__(caller_source, "source_key", "mutated.source")
    object.__setattr__(caller_event, "source_key", "mutated.source")
    assert rebuilt.publication_hash == expected_hash == EXPECTED["publication_hash"]


def test_nested_constructor_reconstruction_rejects_forged_values() -> None:
    publication = MODULE.project_tushare_cn_a_share_daily_catalog_bound_market_event_v2(_normalized_result()).result
    assert publication is not None
    source_values = {field.name: getattr(publication.catalog_source, field.name) for field in fields(publication.catalog_source)}
    for name, wrong in (
        ("record_index", False),
        ("current_metadata_only", 1),
        ("revision_closure_complete", 0),
        ("provider_revision_id", "revision"),
        ("member_content_hash", "sha256:" + "0" * 64),
        ("source_record_hash", "sha256:" + "0" * 64),
        ("instrument_catalog_hash", "sha256:" + "0" * 64),
    ):
        changed = dict(source_values)
        changed[name] = wrong
        with pytest.raises((TypeError, ValueError)):
            MODULE.TushareCnAShareAcquisitionCatalogSource(**changed)

    forged_currency = object.__new__(CurrencyId)
    object.__setattr__(forged_currency, "value", "cny")
    forged_catalog = _forge(publication.instrument_catalog, currencies=(forged_currency,))
    with pytest.raises((TypeError, ValueError), match="catalog"):
        MODULE.TushareCnAShareDailyCatalogPublicationResult(
            publication.normalization_result, forged_catalog,
            publication.catalog_source, publication.market_event,
        )
    forged_event = _forge(publication.market_event, source_hash="sha256:" + "0" * 64)
    with pytest.raises((TypeError, ValueError), match="event"):
        MODULE.TushareCnAShareDailyCatalogPublicationResult(
            publication.normalization_result, publication.instrument_catalog,
            publication.catalog_source, forged_event,
        )
    for path in (
        ("instrument_catalog_hash",),
        ("catalog_binding_hash",),
        ("catalog_source", "catalog_source_hash"),
        ("instrument_catalog", "instruments", 0, "instrument_id", "venue"),
    ):
        payload = json.loads(canonical_bytes(publication.market_event.payload))
        target = payload
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = "sha256:" + "0" * 64 if path[-1] != "venue" else "xshg"
        changed_event = MarketEvent(
            event_id=publication.market_event.event_id,
            stream_key=publication.market_event.stream_key,
            event_type=publication.market_event.event_type,
            capability=publication.market_event.capability,
            instrument_id=publication.market_event.instrument_id,
            event_time=publication.market_event.event_time,
            available_time=publication.market_event.available_time,
            phase=publication.market_event.phase,
            source_sequence=publication.market_event.source_sequence,
            revision_id=publication.market_event.revision_id,
            supersedes_revision_id=publication.market_event.supersedes_revision_id,
            source_key=publication.market_event.source_key,
            source_hash=publication.market_event.source_hash,
            payload=payload,
        )
        with pytest.raises((TypeError, ValueError), match="event"):
            MODULE.TushareCnAShareDailyCatalogPublicationResult(
                publication.normalization_result, publication.instrument_catalog,
                publication.catalog_source, changed_event,
            )
    forged_source = _forge(publication.catalog_source, decision_grade_eligible=1)
    with pytest.raises((TypeError, ValueError), match="source"):
        MODULE.TushareCnAShareDailyCatalogPublicationResult(
            publication.normalization_result, publication.instrument_catalog,
            forged_source, publication.market_event,
        )


def test_v1_and_frozen_source_bytes_remain_unchanged() -> None:
    expected = {
        "packages/market-bundle-builder/src/crypto_quant_bundle_builder/tushare_cn_a_share_daily.py": "019ec74e369f8bd747342e2be5e3da8b04dfeb226a2b18a5bc49160323bac77d",
        "packages/market-bundle-builder/src/crypto_quant_bundle_builder/tushare_cn_a_share_daily_bundle.py": "561270a78ed856eb37e8e804fdde52fbcc9d52a0bac2fd1d3763e8623aa79ef9",
        "packages/market-bundle-builder/src/crypto_quant_bundle_builder/__init__.py": "ce723694c39feeb0f70976065f8e513a1a2277d93cc35401bbaf046520acc40e",
        "tests/fixtures/market_data/providers/tushare/cn-a-share-daily-bundle-v1.expected.json": "0ccb4ebeb0f71ce45cb67c98aafd3bebd227eb01e2ccc368002660ff022e78f3",
        "tests/fixtures/market_data/providers/tushare/cn-a-share-daily-listing-v1/daily.json": "c2950a35c093b983e538f97830b7b3fcb0bba1a7dac98a17bd20f6db9296f846",
        "tests/fixtures/market_data/providers/tushare/cn-a-share-daily-listing-v1/stock-basic.json": "d78fc472268deacb5af7c59c113325e2a00c5b4619c53fbbfe6fa23c96d471d2",
    }
    repository = ROOT.parent
    for relative, digest in expected.items():
        assert hashlib.sha256((repository / relative).read_bytes()).hexdigest() == digest
