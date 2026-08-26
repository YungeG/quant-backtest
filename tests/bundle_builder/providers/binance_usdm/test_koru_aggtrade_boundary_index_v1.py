from __future__ import annotations

import hashlib
import io
import json
from dataclasses import replace
from datetime import date
from zipfile import ZIP_STORED, ZipFile, ZipInfo

import pytest
from crypto_quant_bundle_builder import (
    binance_usdm_koru_aggtrade_boundary_index_v1 as boundary_index,
)
from crypto_quant_bundle_builder import (
    binance_usdm_koru_aggtrades_source_bounded_v1 as source_v1,
)
from crypto_quant_bundle_builder.binance_usdm_koru_aggtrade_boundary_index_v1 import (
    BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV1,
    BinanceUsdmKoruAggregateTradeBoundaryIndexOutcomeV1,
    BinanceUsdmKoruAggregateTradeBoundaryIndexRequestV1,
    BinanceUsdmKoruExecutionBoundaryV1,
    build_binance_usdm_koru_aggregate_trade_boundary_index_v1,
)
from crypto_quant_bundle_builder.binance_usdm_koru_aggtrades_source_bounded_v1 import (
    BinanceUsdmKoruAggregateTradesSourceBoundedCaptureResultV1,
    BinanceUsdmKoruAggregateTradesSourceBoundedRequestV1,
    capture_binance_usdm_koru_aggregate_trades_from_retained_rest_v1,
    capture_binance_usdm_koru_aggregate_trades_source_bounded_v1,
    normalize_binance_usdm_koru_aggregate_trades_source_bounded_v1,
)
from crypto_quant_bundle_builder.source_snapshots import (
    RawSourceMember,
    freeze_source_snapshot,
)
from crypto_quant_domain import InstrumentId, UtcInstant, VenueId

from tests.bundle_builder.providers.binance_usdm.test_koru_aggtrades_retained_rest_v1 import (
    COVERAGE_END_MS,
    COVERAGE_START_MS,
    DERIVED_NAME,
    SOURCE_PREFIX,
)
from tests.bundle_builder.providers.binance_usdm.test_koru_aggtrades_retained_rest_v1 import (
    DAY_START_MS as RETAINED_DAY_START_MS,
)
from tests.bundle_builder.providers.binance_usdm.test_koru_aggtrades_retained_rest_v1 import (
    WINDOWS as RETAINED_WINDOWS,
)
from tests.bundle_builder.providers.binance_usdm.test_koru_aggtrades_retained_rest_v1 import (
    Evidence as RetainedEvidence,
)
from tests.bundle_builder.providers.binance_usdm.test_koru_aggtrades_retained_rest_v1 import (
    evidence_for as retained_evidence_for,
)
from tests.bundle_builder.providers.binance_usdm.test_koru_aggtrades_retained_rest_v1 import (
    manifest_bytes as retained_manifest_bytes,
)
from tests.bundle_builder.providers.binance_usdm.test_koru_aggtrades_retained_rest_v1 import (
    request_for as retained_request_for,
)

DAY_NS = 86_400_000_000_000
DAY_MS = DAY_NS // 1_000_000
EPOCH = date(1970, 1, 1)
INSTRUMENT = InstrumentId(VenueId("binance_usdm"), "koru-usdt-tradifi-perpetual")


def sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def day_start_ns(utc_date: str) -> int:
    return (date.fromisoformat(utc_date) - EPOCH).days * DAY_NS


def official_capture(
    utc_date: str,
    rows: tuple[tuple[str, ...], ...],
) -> BinanceUsdmKoruAggregateTradesSourceBoundedCaptureResultV1:
    csv_bytes = b"".join((",".join(row) + "\n").encode() for row in rows)
    archive_output = io.BytesIO()
    csv_name = f"KORUUSDT-aggTrades-{utc_date}.csv"
    archive_name = f"KORUUSDT-aggTrades-{utc_date}.zip"
    info = ZipInfo(csv_name, (2026, 1, 1, 0, 0, 0))
    info.compress_type = ZIP_STORED
    info.external_attr = 0o644 << 16
    with ZipFile(archive_output, "w") as archive:
        archive.writestr(info, csv_bytes)
    archive_bytes = archive_output.getvalue()
    checksum_bytes = f"{sha256(archive_bytes)[7:]}  {archive_name}\n".encode()
    start = day_start_ns(utc_date)
    request = BinanceUsdmKoruAggregateTradesSourceBoundedRequestV1(
        INSTRUMENT,
        utc_date,
        start + DAY_NS,
        start + DAY_NS + 1,
        sha256(archive_bytes),
        sha256(checksum_bytes),
    )
    archive_url, checksum_url = request.urls
    evidence = {archive_url: archive_bytes, checksum_url: checksum_bytes}
    outcome = capture_binance_usdm_koru_aggregate_trades_source_bounded_v1(
        request, lambda url: (200, evidence[url])
    )
    assert outcome.failure is None
    assert outcome.result is not None
    return outcome.result


def row(
    aggregate_id: int,
    first_raw_id: int,
    last_raw_id: int,
    transaction_time_ms: int,
    price: str = "12.340",
) -> tuple[str, ...]:
    return (
        str(aggregate_id),
        price,
        "1.250",
        str(first_raw_id),
        str(last_raw_id),
        str(transaction_time_ms),
        "false",
    )


def build_request(
    captures: tuple[BinanceUsdmKoruAggregateTradesSourceBoundedCaptureResultV1, ...],
    start_ns: int,
    end_ns: int,
    boundaries: tuple[tuple[int, int], ...],
) -> BinanceUsdmKoruAggregateTradeBoundaryIndexRequestV1:
    return BinanceUsdmKoruAggregateTradeBoundaryIndexRequestV1(
        captures,
        UtcInstant(start_ns),
        UtcInstant(end_ns),
        tuple(
            BinanceUsdmKoruExecutionBoundaryV1(UtcInstant(boundary), UtcInstant(cutoff))
            for boundary, cutoff in boundaries
        ),
    )


def retained_evidence_with_manifest(
    evidence: RetainedEvidence, manifest: dict[str, object]
) -> RetainedEvidence:
    manifest_value = retained_manifest_bytes(manifest)
    authority = replace(
        evidence.authority,
        execution_manifest_file_sha256=sha256(manifest_value),
        execution_manifest_identity=json.loads(manifest_value)["manifest_sha256"],
    )
    return replace(evidence, manifest=manifest_value, authority=authority)


def forged_retained_capture(
    evidence: RetainedEvidence,
) -> BinanceUsdmKoruAggregateTradesSourceBoundedCaptureResultV1:
    baseline = retained_evidence_for()
    outcome = capture_binance_usdm_koru_aggregate_trades_from_retained_rest_v1(
        retained_request_for(baseline),
        baseline.manifest,
        baseline.pages,
        baseline.derived,
        baseline.archive,
        baseline.checksum,
    )
    assert outcome.result is not None
    request = retained_request_for(evidence)
    authority = request.authority
    assert authority is not None
    availability = source_v1._availability_authority_bytes()
    acquired_at = request.acquired_at_epoch_nanoseconds
    frozen = freeze_source_snapshot(
        members=(
            RawSourceMember(
                source_v1._RETAINED_AVAILABILITY_AUTHORITY_MEMBER_KEY,
                availability,
                "0644",
                acquired_at,
                sha256(availability),
            ),
            RawSourceMember(
                source_v1._RETAINED_EXECUTION_MANIFEST_MEMBER_KEY,
                evidence.manifest,
                "0644",
                acquired_at,
                authority.execution_manifest_file_sha256,
            ),
            *(
                RawSourceMember(
                    "retained/raw/" + page.member_name,
                    raw,
                    "0644",
                    acquired_at,
                    page.content_sha256,
                )
                for page, raw in zip(authority.pages, evidence.pages, strict=True)
            ),
            RawSourceMember(
                source_v1._RETAINED_DERIVED_CSV_MEMBER_KEY,
                evidence.derived,
                "0644",
                acquired_at,
                authority.derived_csv_sha256,
            ),
            RawSourceMember(
                "derived/" + request.archive_name,
                evidence.archive,
                "0644",
                acquired_at,
                request.expected_archive_sha256,
            ),
            RawSourceMember(
                "derived/" + request.checksum_name,
                evidence.checksum,
                "0644",
                acquired_at,
                request.expected_checksum_sha256,
            ),
        ),
        provenance=source_v1._provenance(request),
    )
    assert frozen.snapshot is not None
    object.__setattr__(outcome.result, "request", request)
    object.__setattr__(outcome.result, "snapshot", frozen.snapshot)
    return outcome.result


def test_streaming_selection_matches_v1_and_deduplicates_shared_source_event() -> None:
    start = day_start_ns("2026-07-16")
    start_ms = start // 1_000_000
    capture = official_capture(
        "2026-07-16",
        (
            row(700, 900, 901, start_ms + 1_000),
            row(701, 902, 903, start_ms + 2_000),
            row(702, 904, 905, start_ms + 3_000),
        ),
    )
    normalized = normalize_binance_usdm_koru_aggregate_trades_source_bounded_v1(
        capture
    ).result
    assert normalized is not None
    request = build_request(
        (capture,),
        start,
        start + DAY_NS,
        (
            (start, start + 4_000_000_000),
            (start + 500_000_000, start + 4_000_000_000),
            (start + 1_500_000_000, start + 4_000_000_000),
        ),
    )

    outcome = build_binance_usdm_koru_aggregate_trade_boundary_index_v1(request)

    assert outcome.failure is None
    assert outcome.result is not None
    result = outcome.result
    expected = (normalized.events[0], normalized.events[0], normalized.events[1])
    assert (
        tuple(lineage.source_event for lineage in result.selected_lineage) == expected
    )
    assert result.selected_source_events == (normalized.events[0], normalized.events[1])
    assert tuple(lineage.csv_row_ordinal for lineage in result.selected_lineage) == (
        1,
        1,
        2,
    )
    assert result.streamed_row_count == 3
    assert result.streamed_reconstruction_digest.startswith("sha256:")


def test_missing_cutoff_and_intra_and_cross_date_raw_gap_evidence() -> None:
    first_start = day_start_ns("2026-07-16")
    second_start = first_start + DAY_NS
    first = official_capture(
        "2026-07-16",
        (
            row(700, 900, 901, first_start // 1_000_000 + DAY_MS - 2_000),
            row(701, 905, 906, first_start // 1_000_000 + DAY_MS - 1_000),
        ),
    )
    second = official_capture(
        "2026-07-17",
        (
            row(702, 910, 911, second_start // 1_000_000 + 1_000),
            row(703, 912, 913, second_start // 1_000_000 + 2_000),
        ),
    )
    request = build_request(
        (first, second),
        first_start,
        second_start + DAY_NS,
        ((second_start + 500_000_000, second_start + 900_000_000),),
    )

    outcome = build_binance_usdm_koru_aggregate_trade_boundary_index_v1(request)

    assert outcome.failure is None
    assert outcome.result is not None
    result = outcome.result
    assert not result.selected_lineage
    assert len(result.missing_boundaries) == 1
    assert result.intra_day_raw_id_gap_stream.gap_count == 1
    assert result.intra_day_raw_id_gap_stream.missing_id_count == 3
    assert result.cross_date_raw_id_gap_stream.gap_count == 1
    assert result.cross_date_raw_id_gap_stream.missing_id_count == 3
    assert result.aggregate_id_coverage_gaps == ()


def test_retained_selection_matches_v1_and_declared_missing_prefix_is_exact() -> None:
    evidence = retained_evidence_for()
    capture_outcome = capture_binance_usdm_koru_aggregate_trades_from_retained_rest_v1(
        retained_request_for(evidence),
        evidence.manifest,
        evidence.pages,
        evidence.derived,
        evidence.archive,
        evidence.checksum,
    )
    assert capture_outcome.result is not None
    capture = capture_outcome.result
    normalized = normalize_binance_usdm_koru_aggregate_trades_source_bounded_v1(
        capture
    ).result
    assert normalized is not None
    start = RETAINED_DAY_START_MS * 1_000_000
    end = start + DAY_NS
    request = build_request(
        (capture,),
        start,
        end,
        (
            (start, COVERAGE_END_MS * 1_000_000),
            (COVERAGE_START_MS * 1_000_000, COVERAGE_END_MS * 1_000_000),
        ),
    )

    outcome = build_binance_usdm_koru_aggregate_trade_boundary_index_v1(request)

    assert outcome.failure is None
    assert outcome.result is not None
    assert len(outcome.result.missing_boundaries) == 1
    assert outcome.result.selected_source_events == (normalized.events[0],)
    assert outcome.result.selected_lineage[0].source_event == normalized.events[0]


def test_official_to_retained_aggregate_id_regression_fails() -> None:
    official_start = day_start_ns("2026-08-23")
    official = official_capture(
        "2026-08-23",
        (
            row(
                1_000,
                100,
                100,
                official_start // 1_000_000 + DAY_MS - 1_000,
            ),
        ),
    )
    evidence = retained_evidence_for()
    retained_outcome = capture_binance_usdm_koru_aggregate_trades_from_retained_rest_v1(
        retained_request_for(evidence),
        evidence.manifest,
        evidence.pages,
        evidence.derived,
        evidence.archive,
        evidence.checksum,
    )
    assert retained_outcome.result is not None
    request = build_request(
        (official, retained_outcome.result),
        official_start,
        official_start + 2 * DAY_NS,
        ((COVERAGE_START_MS * 1_000_000, COVERAGE_END_MS * 1_000_000),),
    )

    outcome = build_binance_usdm_koru_aggregate_trade_boundary_index_v1(request)

    assert outcome.result is None
    assert outcome.failure is not None
    assert outcome.failure.code is (
        BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV1.DATA_GAP_DETECTED
    )


def test_aggregate_id_coverage_evidence_rejects_nonpositive_missing_range() -> None:
    with pytest.raises(ValueError, match="exact declared prefix"):
        boundary_index.BinanceUsdmKoruAggregateIdCoverageGapEvidenceV1(
            previous_aggregate_trade_id=1_000,
            current_aggregate_trade_id=700,
            previous_transaction_time_milliseconds=DAY_MS - 1,
            current_transaction_time_milliseconds=COVERAGE_START_MS,
            missing_first_aggregate_trade_id=1_001,
            missing_last_aggregate_trade_id=699,
            missing_aggregate_trade_count=0,
            declared_missing_interval_start=UtcInstant(DAY_MS * 1_000_000),
            declared_missing_interval_end_exclusive=UtcInstant(
                COVERAGE_START_MS * 1_000_000
            ),
            retained_authority_hash="sha256:" + "0" * 64,
        )


def test_official_to_retained_forward_gap_binds_exact_missing_prefix() -> None:
    official_start = day_start_ns("2026-08-23")
    official = official_capture(
        "2026-08-23",
        (
            row(
                600,
                100,
                100,
                official_start // 1_000_000 + DAY_MS - 1_000,
            ),
        ),
    )
    evidence = retained_evidence_for()
    retained_outcome = capture_binance_usdm_koru_aggregate_trades_from_retained_rest_v1(
        retained_request_for(evidence),
        evidence.manifest,
        evidence.pages,
        evidence.derived,
        evidence.archive,
        evidence.checksum,
    )
    assert retained_outcome.result is not None
    request = build_request(
        (official, retained_outcome.result),
        official_start,
        official_start + 2 * DAY_NS,
        ((COVERAGE_START_MS * 1_000_000, COVERAGE_END_MS * 1_000_000),),
    )

    outcome = build_binance_usdm_koru_aggregate_trade_boundary_index_v1(request)

    assert outcome.failure is None
    assert outcome.result is not None
    assert len(outcome.result.aggregate_id_coverage_gaps) == 1
    gap = outcome.result.aggregate_id_coverage_gaps[0]
    assert gap.previous_aggregate_trade_id == 600
    assert gap.current_aggregate_trade_id == 700
    assert gap.missing_first_aggregate_trade_id == 601
    assert gap.missing_last_aggregate_trade_id == 699
    assert gap.missing_aggregate_trade_count == 99
    assert gap.retained_authority_hash == evidence.authority.authority_hash


def test_official_to_official_regression_fails() -> None:
    first_start = day_start_ns("2026-07-16")
    first = official_capture(
        "2026-07-16",
        (row(1_000, 100, 100, first_start // 1_000_000 + DAY_MS - 1_000),),
    )
    second = official_capture(
        "2026-07-17",
        (row(700, 101, 101, first_start // 1_000_000 + DAY_MS + 1_000),),
    )
    request = build_request(
        (first, second),
        first_start,
        first_start + 2 * DAY_NS,
        ((first_start + DAY_NS, first_start + 2 * DAY_NS),),
    )

    outcome = build_binance_usdm_koru_aggregate_trade_boundary_index_v1(request)

    assert outcome.result is None
    assert outcome.failure is not None
    assert outcome.failure.code is (
        BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV1.DATA_GAP_DETECTED
    )


@pytest.mark.parametrize(
    "rows",
    [
        (
            row(700, 900, 901, day_start_ns("2026-07-16") // 1_000_000 + 1_000),
            row(702, 902, 903, day_start_ns("2026-07-16") // 1_000_000 + 2_000),
        ),
        (
            row(700, 900, 901, day_start_ns("2026-07-16") // 1_000_000 + 1_000),
            (
                "701",
                "quoted,price",
                "1.250",
                "902",
                "903",
                str(day_start_ns("2026-07-16") // 1_000_000 + 2_000),
                "false",
            ),
        ),
    ],
)
def test_aggregate_and_row_tamper_fail_closed(
    rows: tuple[tuple[str, ...], ...],
) -> None:
    start = day_start_ns("2026-07-16")
    capture = official_capture("2026-07-16", rows)
    request = build_request(
        (capture,), start, start + DAY_NS, ((start, start + DAY_NS),)
    )

    outcome = build_binance_usdm_koru_aggregate_trade_boundary_index_v1(request)

    assert outcome.result is None
    assert outcome.failure is not None
    assert outcome.failure.code in {
        BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV1.DATA_GAP_DETECTED,
        BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV1.SOURCE_INVALID,
    }


def test_archive_and_boundary_mutation_are_classified_before_streaming() -> None:
    start = day_start_ns("2026-07-16")
    capture = official_capture(
        "2026-07-16", (row(700, 900, 901, start // 1_000_000 + 1_000),)
    )
    request = build_request(
        (capture,), start, start + DAY_NS, ((start, start + DAY_NS),)
    )
    object.__setattr__(
        capture.snapshot, "archive_bytes", capture.snapshot.archive_bytes + b"x"
    )
    archive_tamper = build_binance_usdm_koru_aggregate_trade_boundary_index_v1(request)
    assert archive_tamper.failure is not None
    assert archive_tamper.failure.code is (
        BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV1.CAPTURE_INVALID
    )

    capture = official_capture(
        "2026-07-16", (row(700, 900, 901, start // 1_000_000 + 1_000),)
    )
    request = build_request(
        (capture,), start, start + DAY_NS, ((start, start + DAY_NS),)
    )
    object.__setattr__(request.boundaries[0], "cutoff", UtcInstant(start))
    boundary_tamper = build_binance_usdm_koru_aggregate_trade_boundary_index_v1(request)
    assert boundary_tamper.failure is not None
    assert boundary_tamper.failure.code is (
        BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV1.BOUNDARY_INVALID
    )


def test_trusted_replay_fresh_reconstruction_and_result_tamper() -> None:
    start = day_start_ns("2026-07-16")
    capture = official_capture(
        "2026-07-16", (row(700, 900, 901, start // 1_000_000 + 1_000),)
    )
    request = build_request(
        (capture,), start, start + DAY_NS, ((start, start + DAY_NS),)
    )
    first = build_binance_usdm_koru_aggregate_trade_boundary_index_v1(request).result
    second = build_binance_usdm_koru_aggregate_trade_boundary_index_v1(request).result
    assert first is not None
    assert second is not None
    assert first is not second
    assert first.to_canonical_dict() == second.to_canonical_dict()
    assert boundary_index._trusted_result(first) is not None

    forged = replace(first, streamed_row_count=2)
    assert boundary_index._trusted_result(forged) is None
    forged_gap_stream = replace(
        first.intra_day_raw_id_gap_stream,
        chain_digest=first.streamed_reconstruction_digest,
    )
    forged_gap_result = replace(
        first, intra_day_raw_id_gap_stream=forged_gap_stream
    )
    assert boundary_index._trusted_result(forged_gap_result) is None
    with pytest.raises(ValueError, match="replay exactly"):
        BinanceUsdmKoruAggregateTradeBoundaryIndexOutcomeV1(result=forged)
    with pytest.raises(ValueError, match="replay exactly"):
        BinanceUsdmKoruAggregateTradeBoundaryIndexOutcomeV1(
            result=forged_gap_result
        )


def test_streaming_path_never_uses_v1_full_materialization_and_bounds_10k_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    start = day_start_ns("2026-07-16")
    start_ms = start // 1_000_000
    rows = tuple(
        row(
            10_000 + index,
            20_000 + index * 2,
            20_000 + index * 2,
            start_ms + index,
        )
        for index in range(10_000)
    )
    capture = official_capture("2026-07-16", rows)
    request = build_request(
        (capture,),
        start,
        start + DAY_NS,
        (
            (start, start + DAY_NS),
            (start + 5_000_000_000, start + DAY_NS),
            (start + 9_999_000_000, start + DAY_NS),
        ),
    )

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("full V1 materialization is forbidden")

    monkeypatch.setattr(source_v1, "_csv_rows", forbidden)
    monkeypatch.setattr(
        source_v1,
        "normalize_binance_usdm_koru_aggregate_trades_source_bounded_v1",
        forbidden,
    )
    outcome = build_binance_usdm_koru_aggregate_trade_boundary_index_v1(request)

    assert outcome.failure is None
    assert outcome.result is not None
    assert outcome.result.streamed_row_count == 10_000
    assert len(outcome.result.selected_source_events) == 3
    assert len(outcome.result.selected_lineage) == 3
    gap_stream = outcome.result.intra_day_raw_id_gap_stream
    assert gap_stream.gap_count == 9_999
    assert gap_stream.missing_id_count == 9_999
    assert gap_stream.first_gap_hash is not None
    assert gap_stream.last_gap_hash is not None
    assert len(gap_stream.to_canonical_dict()) == 7


@pytest.mark.parametrize(
    "member_kind", ("derived_csv", "derived_zip", "checksum", "raw_page")
)
def test_retained_fast_verifier_rejects_false_manifest_size(
    member_kind: str,
) -> None:
    evidence = retained_evidence_for()
    manifest = json.loads(evidence.manifest)
    paths = {
        "derived_csv": SOURCE_PREFIX + DERIVED_NAME,
        "derived_zip": SOURCE_PREFIX + DERIVED_NAME.removesuffix(".csv") + ".zip",
        "checksum": (
            SOURCE_PREFIX + DERIVED_NAME.removesuffix(".csv") + ".zip.CHECKSUM"
        ),
        "raw_page": SOURCE_PREFIX + evidence.authority.pages[0].member_name,
    }
    entry = next(
        value for value in manifest["files"] if value["path"] == paths[member_kind]
    )
    entry["size_bytes"] += 1
    forged = forged_retained_capture(
        retained_evidence_with_manifest(evidence, manifest)
    )
    start = RETAINED_DAY_START_MS * 1_000_000

    with pytest.raises(ValueError, match="captures must replay exact"):
        build_request(
            (forged,),
            start,
            start + DAY_NS,
            ((COVERAGE_START_MS * 1_000_000, COVERAGE_END_MS * 1_000_000),),
        )


def test_retained_fast_verifier_rejects_alternate_zip_packaging() -> None:
    evidence = retained_evidence_for()
    output = io.BytesIO()
    member = ZipInfo(DERIVED_NAME, (1980, 1, 1, 0, 0, 0))
    member.compress_type = ZIP_STORED
    member.external_attr = 0o100644 << 16
    with ZipFile(output, "w") as archive:
        archive.writestr(member, evidence.derived)
    alternate_archive = output.getvalue()
    assert alternate_archive != evidence.archive
    archive_name = DERIVED_NAME.removesuffix(".csv") + ".zip"
    alternate_checksum = (
        f"{sha256(alternate_archive)[7:]}  {archive_name}\n".encode()
    )
    manifest = json.loads(evidence.manifest)
    archive_entry = next(
        value
        for value in manifest["files"]
        if value["path"] == SOURCE_PREFIX + archive_name
    )
    archive_entry["sha256"] = sha256(alternate_archive)
    archive_entry["size_bytes"] = len(alternate_archive)
    checksum_entry = next(
        value
        for value in manifest["files"]
        if value["path"] == SOURCE_PREFIX + archive_name + ".CHECKSUM"
    )
    checksum_entry["sha256"] = sha256(alternate_checksum)
    checksum_entry["size_bytes"] = len(alternate_checksum)
    tampered = replace(
        evidence, archive=alternate_archive, checksum=alternate_checksum
    )
    forged = forged_retained_capture(
        retained_evidence_with_manifest(tampered, manifest)
    )
    start = RETAINED_DAY_START_MS * 1_000_000

    with pytest.raises(ValueError, match="captures must replay exact"):
        build_request(
            (forged,),
            start,
            start + DAY_NS,
            ((COVERAGE_START_MS * 1_000_000, COVERAGE_END_MS * 1_000_000),),
        )


def test_retained_10k_streams_pages_without_full_reconstruction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows: list[dict[str, object]] = []
    aggregate_id = 10_000
    for start, _end in RETAINED_WINDOWS:
        for offset in range(2_000):
            rows.append(
                {
                    "T": start + offset,
                    "a": aggregate_id,
                    "f": 20_000 + aggregate_id,
                    "l": 20_000 + aggregate_id,
                    "m": False,
                    "nq": "1.00",
                    "p": "12.340",
                    "q": "1.00",
                }
            )
            aggregate_id += 1
    evidence = retained_evidence_for(tuple(rows))
    capture_outcome = capture_binance_usdm_koru_aggregate_trades_from_retained_rest_v1(
        retained_request_for(evidence),
        evidence.manifest,
        evidence.pages,
        evidence.derived,
        evidence.archive,
        evidence.checksum,
    )
    assert capture_outcome.result is not None
    capture = capture_outcome.result
    authority = capture.request.authority
    assert authority is not None
    assert len(authority.pages) == 10
    assert max(page.row_count for page in authority.pages) == 1000

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("full retained reconstruction is forbidden")

    monkeypatch.setattr(source_v1, "_reconstruct_retained_authority", forbidden)
    monkeypatch.setattr(boundary_index, "_trusted_capture", forbidden)
    start = RETAINED_DAY_START_MS * 1_000_000
    request = build_request(
        (capture,),
        start,
        start + DAY_NS,
        ((COVERAGE_START_MS * 1_000_000, COVERAGE_END_MS * 1_000_000),),
    )

    outcome = build_binance_usdm_koru_aggregate_trade_boundary_index_v1(request)

    assert outcome.failure is None
    assert outcome.result is not None
    assert outcome.result.streamed_row_count == 10_000
    assert len(outcome.result.selected_lineage) == 1
