from __future__ import annotations

import hashlib
import io
import json
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import pytest
from crypto_quant_bundle_builder.binance_usdm_koru_aggtrades_source_bounded_v1 import (
    BINANCE_USDM_KORU_AGGREGATE_TRADE_AVAILABILITY_AUTHORITY_V1,
    BinanceUsdmKoruAggregateTradeAvailabilityAuthorityV1,
    BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1,
    BinanceUsdmKoruAggregateTradesSourceBoundedRequestV1,
    BinanceUsdmKoruRetainedAggregateTradesAuthorityV1,
    BinanceUsdmKoruRetainedAggregateTradesPageV1,
    build_binance_usdm_koru_aggregate_trades_retained_rest_evidence_v1,
    capture_binance_usdm_koru_aggregate_trades_from_retained_rest_v1,
    capture_binance_usdm_koru_aggregate_trades_source_bounded_v1,
    normalize_binance_usdm_koru_aggregate_trades_source_bounded_v1,
)
from crypto_quant_domain import InstrumentId, UtcInstant, VenueId

UTC_DATE = "2026-08-24"
DAY_START_MS = 1_787_529_600_000
COVERAGE_START_MS = 1_787_553_260_640
COVERAGE_END_MS = 1_787_569_200_000
DAY_END_NS = (DAY_START_MS + 86_400_000) * 1_000_000
LOCAL_ACQUIRED_MS = 1_787_578_224_310
REQUEST_ACQUIRED_NS = DAY_END_NS + 3_600_000_000_000
ENDPOINT = "https://fapi.binance.com/fapi/v1/aggTrades"
SOURCE_PREFIX = "binance_usdm/aggTrades/rest-bounded/2026-08-24/"
DERIVED_NAME = "KORUUSDT-aggTrades-2026-08-24.discovery-bounded.csv"
HEADER = (
    "agg_trade_id,price,quantity,first_trade_id,last_trade_id,transact_time,"
    "is_buyer_maker\n"
)
WINDOWS = (
    (COVERAGE_START_MS, DAY_START_MS + 7 * 3_600_000 - 1),
    (DAY_START_MS + 7 * 3_600_000, DAY_START_MS + 8 * 3_600_000 - 1),
    (DAY_START_MS + 8 * 3_600_000, DAY_START_MS + 9 * 3_600_000 - 1),
    (DAY_START_MS + 9 * 3_600_000, DAY_START_MS + 10 * 3_600_000 - 1),
    (DAY_START_MS + 10 * 3_600_000, COVERAGE_END_MS - 1),
)
ROWS = (
    {"T": COVERAGE_START_MS + 428, "a": 700, "f": 900, "l": 901, "m": False, "nq": "372.00", "p": "19.92000", "q": "372.00"},
    {"T": WINDOWS[1][0] + 275, "a": 701, "f": 905, "l": 906, "m": True, "nq": "1.2", "p": "19.9", "q": "1.20"},
    {"T": WINDOWS[2][0] + 106, "a": 702, "f": 907, "l": 907, "m": False, "nq": "0.48", "p": "19.81000", "q": "0.48"},
    {"T": WINDOWS[3][0] + 295, "a": 703, "f": 908, "l": 910, "m": True, "nq": "230.74", "p": "19.86000", "q": "230.74"},
    {"T": WINDOWS[4][0] + 620, "a": 704, "f": 911, "l": 911, "m": True, "nq": "7.67", "p": "19.98000", "q": "7.67"},
)


def sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def utc_text(value: int) -> str:
    return datetime.fromtimestamp(value / 1000, tz=UTC).strftime(
        "%Y-%m-%dT%H:%M:%S.%fZ"
    )[:-4] + "Z"


def token(value: int) -> str:
    return datetime.fromtimestamp(value / 1000, tz=UTC).strftime("%Y%m%dT%H%M%SZ")


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True
    ).encode()


def zip_bytes(derived: bytes) -> bytes:
    output = io.BytesIO()
    info = ZipInfo(DERIVED_NAME, (1980, 1, 1, 0, 0, 0))
    info.compress_type = ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    with ZipFile(output, "w") as archive:
        archive.writestr(
            info,
            derived,
            compress_type=ZIP_DEFLATED,
            compresslevel=9,
        )
    return output.getvalue()


def manifest_bytes(value: dict[str, object]) -> bytes:
    value["manifest_sha256"] = ""
    value["manifest_sha256"] = sha256(canonical_json(value))
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


@dataclass(frozen=True)
class Evidence:
    manifest: bytes
    pages: tuple[bytes, ...]
    derived: bytes
    archive: bytes
    checksum: bytes
    authority: BinanceUsdmKoruRetainedAggregateTradesAuthorityV1


def evidence_for(
    rows: tuple[dict[str, object], ...] = ROWS,
    *,
    page_url_override: tuple[int, str] | None = None,
    page_hash_override: tuple[int, str] | None = None,
    manifest_changes: dict[str, object] | None = None,
) -> Evidence:
    page_bytes = tuple(canonical_json([row]) for row in rows)
    page_entries: list[dict[str, object]] = []
    pages: list[BinanceUsdmKoruRetainedAggregateTradesPageV1] = []
    for index, ((start, end), raw) in enumerate(zip(WINDOWS, page_bytes, strict=True)):
        member_name = (
            f"KORUUSDT-aggTrades-{token(start)}-{token(end)}-page-0001.json"
        )
        url = (
            f"{ENDPOINT}?symbol=KORUUSDT&startTime={start}&endTime={end}&limit=1000"
        )
        if page_url_override is not None and page_url_override[0] == index:
            url = page_url_override[1]
        digest = sha256(raw)
        if page_hash_override is not None and page_hash_override[0] == index:
            digest = page_hash_override[1]
        page_entries.append(
            {
                "path": SOURCE_PREFIX + member_name,
                "provider_checksum": None,
                "row_count": 1,
                "sha256": digest,
                "size_bytes": len(raw),
                "source_url": url,
                "status": "canonical_rest_response",
            }
        )
        pages.append(
            BinanceUsdmKoruRetainedAggregateTradesPageV1(
                member_name,
                digest,
                url,
                start,
                end,
                1,
                1,
            )
        )
    derived = (
        HEADER
        + "".join(
            f"{row['a']},{row['p']},{row['q']},{row['f']},{row['l']},"
            f"{row['T']},{str(row['m']).lower()}\n"
            for row in rows
        )
    ).encode()
    archive = zip_bytes(derived)
    checksum = f"{sha256(archive)[7:]}  {DERIVED_NAME[:-4]}.zip\n".encode()
    files = [
        {
            "path": SOURCE_PREFIX + DERIVED_NAME,
            "provider_checksum": None,
            "row_count": len(rows),
            "sha256": sha256(derived),
            "size_bytes": len(derived),
            "source_url": ENDPOINT,
            "status": "rest_derived_standard_schema",
        },
        {
            "path": SOURCE_PREFIX + DERIVED_NAME[:-4] + ".zip",
            "provider_checksum": None,
            "row_count": len(rows),
            "sha256": sha256(archive),
            "size_bytes": len(archive),
            "source_url": ENDPOINT,
            "status": "rest_derived_standard_schema",
        },
        {
            "path": SOURCE_PREFIX + DERIVED_NAME[:-4] + ".zip.CHECKSUM",
            "provider_checksum": None,
            "row_count": len(rows),
            "sha256": sha256(checksum),
            "size_bytes": len(checksum),
            "source_url": ENDPOINT,
            "status": "locally_generated_checksum",
        },
        *page_entries,
    ]
    manifest: dict[str, object] = {
        "datasets": {
            "aggTrades": {
                "rest_2026_08_24": {
                    "covered_end_utc_exclusive": "2026-08-24T11:00:00.000Z",
                    "covered_start_utc_inclusive": "2026-08-24T06:34:20.640Z",
                    "max_aggregate_trade_id": rows[-1]["a"],
                    "max_raw_trade_id": rows[-1]["l"],
                    "max_time_ms": rows[-1]["T"],
                    "max_time_utc": utc_text(rows[-1]["T"]),  # type: ignore[arg-type]
                    "min_aggregate_trade_id": rows[0]["a"],
                    "min_raw_trade_id": rows[0]["f"],
                    "min_time_ms": rows[0]["T"],
                    "min_time_utc": utc_text(rows[0]["T"]),  # type: ignore[arg-type]
                    "provenance": "REST-derived; not an official archive",
                    "row_count": len(rows),
                }
            }
        },
        "files": files,
        "generated_at_basis": "frozen base manifest generated_at_utc used as a deterministic offline regeneration marker",
        "generated_at_utc": "2026-08-24T13:30:24.310Z",
        "holdout_protection": {
            "full_2026_08_24_daily_archive_downloaded": False,
            "policy": "No request, retained row, or archive may address this instant or later",
            "rest_end_time_inclusive": COVERAGE_END_MS - 1,
            "start_utc_inclusive": "2026-08-24T11:00:00.000Z",
        },
        "manifest_sha256": "",
        "missing_intervals": [
            {
                "dataset": "aggTrades",
                "end_utc_exclusive": "2026-08-24T06:34:20.640Z",
                "reason": "Binance public aggTrades REST rejected older requests with code -4166; no archive or alternate feed was used for 2026-08-24",
                "start_utc_inclusive": "2026-08-24T00:00:00.000Z",
            }
        ],
        "schema_version": 2,
        "type": "koruusdt_execution_data_manifest",
    }
    if manifest_changes:
        manifest.update(manifest_changes)
    encoded_manifest = manifest_bytes(manifest)
    authority = BinanceUsdmKoruRetainedAggregateTradesAuthorityV1(
        execution_manifest_path="research/koruusdt/data/execution_data_manifest.json",
        execution_manifest_file_sha256=sha256(encoded_manifest),
        execution_manifest_identity=json.loads(encoded_manifest)["manifest_sha256"],
        execution_manifest_generated_at_epoch_nanoseconds=LOCAL_ACQUIRED_MS * 1_000_000,
        pages=tuple(pages),
        selected_coverage_start=UtcInstant(COVERAGE_START_MS * 1_000_000),
        selected_coverage_end_exclusive=UtcInstant(COVERAGE_END_MS * 1_000_000),
        declared_missing_prefix_start=UtcInstant(DAY_START_MS * 1_000_000),
        declared_missing_prefix_end_exclusive=UtcInstant(COVERAGE_START_MS * 1_000_000),
        availability_authority=(
            BINANCE_USDM_KORU_AGGREGATE_TRADE_AVAILABILITY_AUTHORITY_V1
        ),
        derived_csv_member_name=DERIVED_NAME,
        derived_csv_sha256=sha256(derived),
        derived_csv_schema_identity="binance_usdm_aggtrades_csv_7_column_v1",
    )
    return Evidence(encoded_manifest, page_bytes, derived, archive, checksum, authority)


def request_for(evidence: Evidence) -> BinanceUsdmKoruAggregateTradesSourceBoundedRequestV1:
    return BinanceUsdmKoruAggregateTradesSourceBoundedRequestV1(
        InstrumentId(VenueId("binance_usdm"), "koru-usdt-tradifi-perpetual"),
        UTC_DATE,
        REQUEST_ACQUIRED_NS,
        REQUEST_ACQUIRED_NS,
        sha256(evidence.archive),
        sha256(evidence.checksum),
        evidence.authority,
    )


def capture(evidence: Evidence):
    return capture_binance_usdm_koru_aggregate_trades_from_retained_rest_v1(
        request_for(evidence),
        evidence.manifest,
        evidence.pages,
        evidence.derived,
        evidence.archive,
        evidence.checksum,
    )


def retained_result():
    captured = capture(evidence_for()).result
    assert captured is not None
    result = normalize_binance_usdm_koru_aggregate_trades_source_bounded_v1(captured).result
    assert result is not None
    return result


def test_exact_koru_aggregate_trade_availability_authority_is_canonical() -> None:
    authority = BINANCE_USDM_KORU_AGGREGATE_TRADE_AVAILABILITY_AUTHORITY_V1
    assert authority.to_canonical_dict() == {
        "type": "binance_usdm_koru_aggregate_trade_availability_authority_v1",
        "schema_version": 1,
        "policy_key": "binance.fapi.aggtrade.transaction-time",
        "policy_version": 1,
        "approved_commit": "27401e5cbee82a9ba50533285831f5a2458cab6a",
        "contract_file_sha256": "sha256:7b88488086f668406c5e669f4943ec65e85677c08eec3b3f48201fb1de5ec2e4",
        "source_event_field": "T",
        "semantics": "available_time_equals_retained_trade_time",
        "instrument_scope": "KORU",
        "simulation_scope": "first_retained_trade",
        "development_only": True,
        "decision_grade_eligible": False,
        "deployment_authorized": False,
    }
    assert authority.authority_ref == "binance.fapi.aggtrade.transaction-time.v1"
    assert authority.authority_digest == (
        "sha256:17c4ae3199aaa660fe8d8b5e423b5f3eef9c84b4f589b6dc59dacda999d6d076"
    )


def test_mutated_availability_singleton_cannot_authorize_retained_replay() -> None:
    evidence = evidence_for()
    request = request_for(evidence)
    captured = capture(evidence).result
    assert captured is not None
    assert (
        evidence.authority.availability_authority
        is not BINANCE_USDM_KORU_AGGREGATE_TRADE_AVAILABILITY_AUTHORITY_V1
    )
    assert request.authority is not evidence.authority
    assert request.authority is not None
    assert (
        request.authority.availability_authority
        is not BINANCE_USDM_KORU_AGGREGATE_TRADE_AVAILABILITY_AUTHORITY_V1
    )

    singleton = BINANCE_USDM_KORU_AGGREGATE_TRADE_AVAILABILITY_AUTHORITY_V1
    original_semantics = singleton.semantics
    try:
        object.__setattr__(singleton, "semantics", "mutable_singleton_is_not_authority")
        with pytest.raises(ValueError, match="availability authority"):
            evidence_for()
        assert capture(evidence).result is None
        assert (
            normalize_binance_usdm_koru_aggregate_trades_source_bounded_v1(
                captured
            ).result
            is None
        )
    finally:
        object.__setattr__(singleton, "semantics", original_semantics)

    assert capture(evidence).result is not None
    assert (
        normalize_binance_usdm_koru_aggregate_trades_source_bounded_v1(
            captured
        ).result
        is not None
    )


@pytest.mark.parametrize(
    ("field", "wrong"),
    (
        ("policy_key", "caller.selected.transaction-time"),
        ("policy_version", 2),
        ("approved_commit", "0" * 40),
        ("contract_file_sha256", "sha256:" + "0" * 64),
    ),
)
def test_koru_aggregate_trade_availability_authority_rejects_tamper(
    field: str, wrong: object
) -> None:
    values = dict(
        BINANCE_USDM_KORU_AGGREGATE_TRADE_AVAILABILITY_AUTHORITY_V1.to_canonical_dict()
    )
    values.pop("type")
    values.pop("schema_version")
    values[field] = wrong
    with pytest.raises(ValueError, match="availability authority"):
        BinanceUsdmKoruAggregateTradeAvailabilityAuthorityV1(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "missing", ("policy_key", "policy_version", "approved_commit", "contract_file_sha256")
)
def test_koru_aggregate_trade_availability_authority_requires_identity(
    missing: str,
) -> None:
    values = dict(
        BINANCE_USDM_KORU_AGGREGATE_TRADE_AVAILABILITY_AUTHORITY_V1.to_canonical_dict()
    )
    values.pop("type")
    values.pop("schema_version")
    values.pop(missing)
    with pytest.raises(TypeError):
        BinanceUsdmKoruAggregateTradeAvailabilityAuthorityV1(**values)  # type: ignore[arg-type]


def test_retained_capture_freezes_manifest_pages_and_deterministic_derived_evidence() -> None:
    evidence = evidence_for()
    request = request_for(evidence)
    outcome = capture(evidence)
    assert outcome.failure is None
    assert outcome.result is not None
    captured = outcome.result
    request_dict = request.to_canonical_dict()
    assert request_dict["provider_archive_claim"] is False
    assert request_dict["availability_authority_ref"] == (
        BINANCE_USDM_KORU_AGGREGATE_TRADE_AVAILABILITY_AUTHORITY_V1.authority_ref
    )
    assert request_dict["availability_authority_digest"] == (
        BINANCE_USDM_KORU_AGGREGATE_TRADE_AVAILABILITY_AUTHORITY_V1.authority_digest
    )
    assert request_dict["acquired_at_epoch_nanoseconds"] == REQUEST_ACQUIRED_NS
    with pytest.raises(ValueError, match="do not claim provider archive"):
        _ = request.urls
    assert tuple(member.member_key for member in captured.snapshot.members) == tuple(
        sorted(
            (
                "retained/availability/authority.json",
                "retained/execution/manifest.json",
                *("retained/raw/" + page.member_name for page in evidence.authority.pages),
                "derived/" + DERIVED_NAME,
                "derived/" + DERIVED_NAME[:-4] + ".zip",
                "derived/" + DERIVED_NAME[:-4] + ".zip.CHECKSUM",
            )
        )
    )
    assert json.loads(
        captured.snapshot.member_bytes("retained/availability/authority.json")
    ) == BINANCE_USDM_KORU_AGGREGATE_TRADE_AVAILABILITY_AUTHORITY_V1.to_canonical_dict()
    availability_member = next(
        member
        for member in captured.snapshot.members
        if member.member_key == "retained/availability/authority.json"
    )
    assert availability_member.content_hash == (
        BINANCE_USDM_KORU_AGGREGATE_TRADE_AVAILABILITY_AUTHORITY_V1.authority_digest
    )
    assert availability_member.acquired_at_epoch_nanoseconds == REQUEST_ACQUIRED_NS
    assert captured.snapshot.member_bytes("retained/execution/manifest.json") == evidence.manifest
    for page, raw in zip(evidence.authority.pages, evidence.pages, strict=True):
        assert captured.snapshot.member_bytes("retained/raw/" + page.member_name) == raw
    assert build_binance_usdm_koru_aggregate_trades_retained_rest_evidence_v1(
        evidence.authority, evidence.derived
    ) == (evidence.archive, evidence.checksum)


def test_retained_normalization_binds_policy_local_acquisition_and_raw_gap() -> None:
    result = retained_result()
    assert result.coverage_start == UtcInstant(COVERAGE_START_MS * 1_000_000)
    assert result.coverage_end_exclusive == UtcInstant(COVERAGE_END_MS * 1_000_000)
    assert result.prefix_gap_classification == "unknown_unproven"
    assert result.first_aggregate_trade_id == 700
    assert result.last_aggregate_trade_id == 704
    assert len(result.raw_id_gaps) == 1
    assert result.raw_id_gaps[0].missing_trade_count == 3
    retained_authority = result.capture.request.authority
    assert retained_authority is not None
    first = result.events[0]
    assert first.event_time == first.available_time
    assert first.payload["source_mode"] == "execution_manifest_bounded_rest_observations"
    assert first.payload["retained_authority_hash"] == retained_authority.authority_hash
    assert first.payload["availability_authority_ref"] == "binance.fapi.aggtrade.transaction-time.v1"
    assert first.payload["availability_authority_digest"] == (
        BINANCE_USDM_KORU_AGGREGATE_TRADE_AVAILABILITY_AUTHORITY_V1.authority_digest
    )
    assert first.payload["provider_archive_claim"] is False
    assert first.payload["execution_manifest_generated_at_epoch_nanoseconds"] == LOCAL_ACQUIRED_MS * 1_000_000
    assert first.payload["local_retained_acquired_at_epoch_nanoseconds"] == REQUEST_ACQUIRED_NS
    assert first.payload["development_only"] is True
    assert result.events[1].payload["price"] == "19.9"
    assert result.events[1].payload["quantity"] == "1.20"


@pytest.mark.parametrize("member", ("manifest", "page", "derived", "archive", "checksum"))
def test_retained_capture_rejects_tamper(member: str) -> None:
    evidence = evidence_for()
    changed = {
        "manifest": replace(evidence, manifest=evidence.manifest + b" "),
        "page": replace(evidence, pages=(evidence.pages[0] + b" ",) + evidence.pages[1:]),
        "derived": replace(evidence, derived=evidence.derived.replace(b"19.9,1.20", b"19.90,1.20", 1)),
        "archive": replace(evidence, archive=evidence.archive + b"x"),
        "checksum": replace(evidence, checksum=evidence.checksum + b"x"),
    }[member]
    outcome = capture(changed)
    assert outcome.result is None
    assert outcome.failure is not None
    assert outcome.failure.code is BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1.SOURCE_HASH_MISMATCH


def test_wrong_url_holdout_manifest_hash_and_derived_rows_fail_closed() -> None:
    evidence = evidence_for()
    wrong_url = evidence.authority.pages[0].source_url.replace("symbol=KORUUSDT", "symbol=BTCUSDT")
    with pytest.raises(ValueError, match="source URL"):
        replace(evidence.authority.pages[0], source_url=wrong_url)
    with pytest.raises(ValueError, match="holdout"):
        replace(
            evidence.authority.pages[-1],
            request_end_time_milliseconds=COVERAGE_END_MS,
            source_url=evidence.authority.pages[-1].source_url.replace(
                f"endTime={COVERAGE_END_MS - 1}", f"endTime={COVERAGE_END_MS}"
            ),
        )
    with pytest.raises(ValueError, match="availability authority"):
        replace(
            evidence.authority,
            availability_authority=replace(
                BINANCE_USDM_KORU_AGGREGATE_TRADE_AVAILABILITY_AUTHORITY_V1,
                policy_key="caller.selected.transaction-time",
            ),
        )
    wrong_page_hash = evidence_for(
        page_hash_override=(0, "sha256:" + "0" * 64)
    )
    assert capture(wrong_page_hash).failure is not None

    manifest_value = json.loads(evidence.manifest)
    manifest_value["manifest_sha256"] = "sha256:" + "0" * 64
    bad_manifest = replace(
        evidence,
        manifest=(json.dumps(manifest_value, sort_keys=True) + "\n").encode(),
    )
    assert capture(bad_manifest).failure is not None

    changed_rows = tuple(dict(row) for row in ROWS)
    changed_rows[1]["p"] = "19.90"
    fabricated = evidence_for(changed_rows)
    assert fabricated.authority.authority_hash != evidence.authority.authority_hash
    assert capture(replace(fabricated, authority=evidence.authority)).failure is not None


def test_json_order_aggregate_gap_and_holdout_row_fail() -> None:
    evidence = evidence_for()
    noncanonical = json.dumps(
        [dict(reversed(tuple(ROWS[0].items())))], separators=(",", ":")
    ).encode()
    assert noncanonical != evidence.pages[0]
    assert capture(replace(evidence, pages=(noncanonical,) + evidence.pages[1:])).failure is not None

    aggregate_gap_rows = tuple(dict(row) for row in ROWS)
    aggregate_gap_rows[2]["a"] = 703
    aggregate_gap_rows[3]["a"] = 704
    aggregate_gap_rows[4]["a"] = 705
    assert capture(evidence_for(aggregate_gap_rows)).failure is not None

    holdout_rows = tuple(dict(row) for row in ROWS)
    holdout_rows[-1]["T"] = COVERAGE_END_MS
    assert capture(evidence_for(holdout_rows)).failure is not None


def test_official_and_retained_capture_modes_are_strictly_separate() -> None:
    evidence = evidence_for()
    retained_request = request_for(evidence)
    assert capture_binance_usdm_koru_aggregate_trades_source_bounded_v1(
        retained_request, lambda _: (200, b"")
    ).failure is not None
    official_request = replace(retained_request, authority=None, utc_date="2026-08-23")
    outcome = capture_binance_usdm_koru_aggregate_trades_from_retained_rest_v1(
        official_request,
        evidence.manifest,
        evidence.pages,
        evidence.derived,
        evidence.archive,
        evidence.checksum,
    )
    assert outcome.result is None
    assert outcome.failure is not None
    assert outcome.failure.code is BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1.CONFIGURATION_INVALID
