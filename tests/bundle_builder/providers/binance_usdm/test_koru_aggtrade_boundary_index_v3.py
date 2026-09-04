from __future__ import annotations

import io
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZIP_STORED, ZipFile, ZipInfo

import pytest
from crypto_quant_bundle_builder import (
    BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV3,
    BinanceUsdmKoruAggregateTradeBoundaryIndexRequestV3,
    BinanceUsdmKoruExecutionBoundaryV1,
    RawBlobSnapshotSourceMember,
    RawBlobSnapshotView,
    build_binance_usdm_koru_aggregate_trade_boundary_index_v3,
    create_binance_usdm_koru_aggregate_trade_boundary_index_authority_v3,
    create_raw_blob_snapshot_manifest,
    open_binance_usdm_koru_aggregate_trade_boundary_index_authority_v3,
)
from crypto_quant_bundle_builder import (
    binance_usdm_koru_aggtrade_boundary_index_v1 as boundary_index,
)
from crypto_quant_bundle_builder.binance_usdm_koru_aggtrades_source_bounded_v1 import (
    _RETAINED_AVAILABILITY_AUTHORITY_MEMBER_KEY,
    capture_binance_usdm_koru_aggregate_trades_from_retained_rest_v1,
)
from crypto_quant_domain import (
    ArtifactEnvelope,
    ArtifactRef,
    UtcInstant,
    canonical_bytes,
)

from tests.bundle_builder.providers.binance_usdm.test_koru_aggtrade_boundary_index_v1 import (
    DAY_NS,
    build_request,
    day_start_ns,
    official_capture,
    row,
)
from tests.bundle_builder.providers.binance_usdm.test_koru_aggtrades_retained_rest_v1 import (
    COVERAGE_END_MS,
    COVERAGE_START_MS,
)
from tests.bundle_builder.providers.binance_usdm.test_koru_aggtrades_retained_rest_v1 import (
    DAY_START_MS as RETAINED_DAY_START_MS,
)
from tests.bundle_builder.providers.binance_usdm.test_koru_aggtrades_retained_rest_v1 import (
    evidence_for as retained_evidence_for,
)
from tests.bundle_builder.providers.binance_usdm.test_koru_aggtrades_retained_rest_v1 import (
    request_for as retained_request_for,
)


def v3_request(captures, start: int, end: int, boundaries: tuple[tuple[int, int], ...]):
    return BinanceUsdmKoruAggregateTradeBoundaryIndexRequestV3(
        captures,
        UtcInstant(start),
        UtcInstant(end),
        tuple(
            BinanceUsdmKoruExecutionBoundaryV1(UtcInstant(boundary), UtcInstant(cutoff))
            for boundary, cutoff in boundaries
        ),
    )


class _RawBlobReader:
    def __init__(self, paths: dict[str, Path]) -> None:
        self._paths = paths

    def raw_blob_path(self, *, ref) -> Path:
        return self._paths[ref.content_hash]


def _raw_view(
    tmp_path: Path, captures: tuple[object, ...], *, absent: frozenset[tuple[int, str]] = frozenset(),
) -> RawBlobSnapshotView:
    source_members = []
    paths: dict[str, Path] = {}
    for ordinal, capture in enumerate(captures, start=1):
        for member in capture.snapshot.members:
            if (ordinal, member.member_key) in absent:
                continue
            raw = capture.snapshot.member_bytes(member.member_key)
            source = RawBlobSnapshotSourceMember(
                f"raw/{ordinal}/{member.member_key}", raw, member.mode
            )
            source_members.append(source)
            path = tmp_path / source.raw_blob_ref.content_hash[7:]
            if not path.exists():
                path.write_bytes(raw)
            paths[source.raw_blob_ref.content_hash] = path
    manifest = create_raw_blob_snapshot_manifest(
        members=tuple(source_members), provenance={"fixture": "boundary-v3-generated"}
    )
    return RawBlobSnapshotView.open(manifest, _RawBlobReader(paths))


def _raw_identity(view: RawBlobSnapshotView) -> dict[str, object]:
    return {"type": "test.raw.snapshot.v1", "snapshot_id": view.manifest.snapshot_id}


def _retained_v3_result():
    evidence = retained_evidence_for()
    retained = capture_binance_usdm_koru_aggregate_trades_from_retained_rest_v1(
        retained_request_for(evidence),
        evidence.manifest,
        evidence.pages,
        evidence.derived,
        evidence.archive,
        evidence.checksum,
    ).result
    assert retained is not None
    start = RETAINED_DAY_START_MS * 1_000_000
    outcome = build_binance_usdm_koru_aggregate_trade_boundary_index_v3(
        v3_request(
            (retained,),
            start,
            start + DAY_NS,
            ((COVERAGE_START_MS * 1_000_000, COVERAGE_END_MS * 1_000_000),),
        )
    )
    assert outcome.result is not None
    return retained, outcome.result


def test_v3_scans_each_csv_member_once_and_matches_v2_selection_semantics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    start = day_start_ns("2026-07-16")
    start_ms = start // 1_000_000
    capture = official_capture(
        "2026-07-16",
        (
            row(700, 900, 900, start_ms + 1_000),
            row(701, 902, 903, start_ms + 2_000),
        ),
        include_header=True,
    )
    boundaries = (
        (start, start + 4_000_000_000),
        (start + 500_000_000, start + 4_000_000_000),
        (start + 1_500_000_000, start + 2_000_000_000),
        (start + 3_000_000_000, start + 4_000_000_000),
    )
    v2 = boundary_index.build_binance_usdm_koru_aggregate_trade_boundary_index_v1(
        build_request((capture,), start, start + DAY_NS, boundaries)
    ).result
    assert v2 is not None
    opened = 0
    original_open = boundary_index.ZipFile.open

    def counted_open(self, name, *args, **kwargs):
        nonlocal opened
        if name == capture.request.csv_name:
            opened += 1
        return original_open(self, name, *args, **kwargs)

    monkeypatch.setattr(boundary_index.ZipFile, "open", counted_open)
    outcome = build_binance_usdm_koru_aggregate_trade_boundary_index_v3(
        v3_request((capture,), start, start + DAY_NS, boundaries)
    )

    assert outcome.failure is None
    assert outcome.result is not None
    result = outcome.result
    assert opened == 1
    assert result.selected_source_events == v2.selected_source_events
    assert result.selected_lineage == v2.selected_lineage
    assert result.missing_boundaries == v2.missing_boundaries
    assert result.aggregate_id_coverage_gaps == v2.aggregate_id_coverage_gaps
    assert (
        result.intra_day_raw_id_gap_stream.gap_count,
        result.intra_day_raw_id_gap_stream.missing_id_count,
        result.intra_day_raw_id_gap_stream.first_gap_hash,
        result.intra_day_raw_id_gap_stream.last_gap_hash,
    ) == (
        v2.intra_day_raw_id_gap_stream.gap_count,
        v2.intra_day_raw_id_gap_stream.missing_id_count,
        v2.intra_day_raw_id_gap_stream.first_gap_hash,
        v2.intra_day_raw_id_gap_stream.last_gap_hash,
    )
    assert result.cross_date_raw_id_gap_stream.gap_count == v2.cross_date_raw_id_gap_stream.gap_count
    assert result.capture_final_evidence[0].selected_boundary_indexes == (0, 1)
    assert result.capture_final_evidence[0].missing_boundary_indexes == (2, 3)
    assert result.streamed_reconstruction_digest != v2.streamed_reconstruction_digest


def test_v3_two_capture_retained_continuity_matches_v2_and_opens_each_member_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    official_start = day_start_ns("2026-08-23")
    retained_start = official_start + DAY_NS
    official_time_ms = official_start // 1_000_000 + DAY_NS // 1_000_000 - 1_000
    official = official_capture(
        "2026-08-23", (row(600, 800, 800, official_time_ms),)
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
    retained = retained_outcome.result
    first_retained_time = (COVERAGE_START_MS + 428) * 1_000_000
    boundaries = (
        (official_time_ms * 1_000_000, retained_start),
        (retained_start, COVERAGE_END_MS * 1_000_000),
        (COVERAGE_START_MS * 1_000_000, first_retained_time),
        ((COVERAGE_START_MS + 1) * 1_000_000, COVERAGE_END_MS * 1_000_000),
        (COVERAGE_END_MS * 1_000_000, official_start + 2 * DAY_NS),
    )
    v2_outcome = boundary_index.build_binance_usdm_koru_aggregate_trade_boundary_index_v1(
        build_request((official, retained), official_start, official_start + 2 * DAY_NS, boundaries)
    )
    assert v2_outcome.failure is None
    assert v2_outcome.result is not None
    v2 = v2_outcome.result

    member_opens = {
        official.request.csv_name: 0,
        retained.request.csv_name: 0,
    }
    original_open = boundary_index.ZipFile.open

    def counted_open(self, name, *args, **kwargs):
        if name in member_opens:
            member_opens[name] += 1
        return original_open(self, name, *args, **kwargs)

    monkeypatch.setattr(boundary_index.ZipFile, "open", counted_open)
    v3_outcome = build_binance_usdm_koru_aggregate_trade_boundary_index_v3(
        v3_request((official, retained), official_start, official_start + 2 * DAY_NS, boundaries)
    )

    assert v3_outcome.failure is None
    assert v3_outcome.result is not None
    v3 = v3_outcome.result
    assert member_opens == {official.request.csv_name: 1, retained.request.csv_name: 1}
    assert v3.selected_source_events == v2.selected_source_events
    assert v3.selected_lineage == v2.selected_lineage
    assert v3.missing_boundaries == v2.missing_boundaries
    assert tuple(
        (
            lineage.source_snapshot_id,
            lineage.source_snapshot_hash,
            lineage.source_provenance_hash,
            lineage.source_member_key,
            lineage.source_member_hash,
            lineage.archive_member_key,
            lineage.archive_member_hash,
            lineage.request_hash,
            lineage.capture_hash,
        )
        for lineage in v3.selected_lineage
    ) == tuple(
        (
            lineage.source_snapshot_id,
            lineage.source_snapshot_hash,
            lineage.source_provenance_hash,
            lineage.source_member_key,
            lineage.source_member_hash,
            lineage.archive_member_key,
            lineage.archive_member_hash,
            lineage.request_hash,
            lineage.capture_hash,
        )
        for lineage in v2.selected_lineage
    )
    assert tuple(
        (stream.gap_count, stream.missing_id_count, stream.first_gap_hash, stream.last_gap_hash)
        for stream in (v3.intra_day_raw_id_gap_stream, v3.cross_date_raw_id_gap_stream)
    ) == tuple(
        (stream.gap_count, stream.missing_id_count, stream.first_gap_hash, stream.last_gap_hash)
        for stream in (v2.intra_day_raw_id_gap_stream, v2.cross_date_raw_id_gap_stream)
    )
    assert tuple(
        (stream.gap_count, stream.missing_id_count)
        for stream in (v3.intra_day_raw_id_gap_stream, v3.cross_date_raw_id_gap_stream)
    ) == ((1, 3), (0, 0))
    assert v3.aggregate_id_coverage_gaps == v2.aggregate_id_coverage_gaps
    assert (
        v3.aggregate_id_coverage_gaps[0].previous_aggregate_trade_id,
        v3.aggregate_id_coverage_gaps[0].current_aggregate_trade_id,
        v3.aggregate_id_coverage_gaps[0].missing_aggregate_trade_count,
    ) == (600, 700, 99)
    assert tuple(missing.boundary.epoch_nanoseconds for missing in v3.missing_boundaries) == (
        retained_start,
        COVERAGE_START_MS * 1_000_000,
        COVERAGE_END_MS * 1_000_000,
    )
    assert (
        v3.missing_boundaries[1].boundary.epoch_nanoseconds,
        v3.missing_boundaries[1].cutoff.epoch_nanoseconds,
    ) == (COVERAGE_START_MS * 1_000_000, first_retained_time)
    assert len(v3.capture_final_evidence) == 2
    assert v3.capture_final_evidence[0].selected_boundary_indexes == (0,)
    assert v3.capture_final_evidence[0].missing_boundary_indexes == ()
    assert v3.capture_final_evidence[1].selected_boundary_indexes == (3,)
    assert v3.capture_final_evidence[1].missing_boundary_indexes == (1, 2, 4)
    assert tuple(final.source_member_hash for final in v3.capture_final_evidence) == tuple(
        lineage.source_member_hash for lineage in v3.selected_lineage
    )


def test_v3_retained_prefix_and_source_provenance_match_v2() -> None:
    evidence = retained_evidence_for()
    captured = capture_binance_usdm_koru_aggregate_trades_from_retained_rest_v1(
        retained_request_for(evidence),
        evidence.manifest,
        evidence.pages,
        evidence.derived,
        evidence.archive,
        evidence.checksum,
    ).result
    assert captured is not None
    start = RETAINED_DAY_START_MS * 1_000_000
    boundaries = (
        (start, COVERAGE_END_MS * 1_000_000),
        (COVERAGE_START_MS * 1_000_000, COVERAGE_END_MS * 1_000_000),
    )
    v2 = boundary_index.build_binance_usdm_koru_aggregate_trade_boundary_index_v1(
        build_request((captured,), start, start + DAY_NS, boundaries)
    ).result
    v3 = build_binance_usdm_koru_aggregate_trade_boundary_index_v3(
        v3_request((captured,), start, start + DAY_NS, boundaries)
    ).result

    assert v2 is not None
    assert v3 is not None
    assert v3.selected_source_events == v2.selected_source_events
    assert v3.selected_lineage == v2.selected_lineage
    assert v3.missing_boundaries == v2.missing_boundaries
    assert v3.aggregate_id_coverage_gaps == v2.aggregate_id_coverage_gaps
    lineage = v3.selected_lineage[0]
    final = v3.capture_final_evidence[0]
    assert lineage.source_member_hash == final.source_member_hash
    assert lineage.source_snapshot_hash == final.source_snapshot_hash
    assert final.missing_boundary_indexes == (0,)
    assert final.selected_boundary_indexes == (1,)


def test_v3_generated_retained_availability_binding_is_exact_and_reopens(
    tmp_path: Path,
) -> None:
    retained, result = _retained_v3_result()
    view = _raw_view(
        tmp_path,
        (retained,),
        absent=frozenset({(1, _RETAINED_AVAILABILITY_AUTHORITY_MEMBER_KEY)}),
    )

    bindings = boundary_index._raw_member_bindings_v3(result, view)
    generated = bindings[0]["source_members"]
    generated = next(
        item for item in generated if item["source_member_key"] == _RETAINED_AVAILABILITY_AUTHORITY_MEMBER_KEY
    )
    authority = retained.request.authority
    assert authority is not None
    availability = authority.availability_authority
    assert generated == {
        "binding_kind": "koru_retained_availability_authority_v1",
        "source_member_key": _RETAINED_AVAILABILITY_AUTHORITY_MEMBER_KEY,
        "source_member_hash": availability.authority_digest,
        "source_member_byte_count": len(
            boundary_index._availability_authority_bytes()
        ),
        "source_member_mode": "0644",
        "availability_authority_ref": availability.authority_ref,
        "availability_authority_digest": availability.authority_digest,
        "availability_authority": availability.to_canonical_dict(),
    }

    envelope, ref = create_binance_usdm_koru_aggregate_trade_boundary_index_authority_v3(
        result, view, _raw_identity(view)
    )
    opened = open_binance_usdm_koru_aggregate_trade_boundary_index_authority_v3(
        canonical_bytes(envelope), ref, view, _raw_identity(view)
    )
    assert opened.result_digest == result.result_digest

    payload = __import__("json").loads(canonical_bytes(envelope.payload))
    generated_payload = next(
        item
        for item in payload["capture_bindings"][0]["source_members"]
        if item["source_member_key"] == _RETAINED_AVAILABILITY_AUTHORITY_MEMBER_KEY
    )
    generated_payload["availability_authority_digest"] = "sha256:" + "0" * 64
    forged = ArtifactEnvelope.create(
        envelope.artifact_type, envelope.schema_version, payload
    )
    with pytest.raises(ValueError):
        open_binance_usdm_koru_aggregate_trade_boundary_index_authority_v3(
            canonical_bytes(forged), ArtifactRef.from_envelope(forged), view, _raw_identity(view)
        )


def test_v3_rejects_an_unmatched_non_generated_raw_member(tmp_path: Path) -> None:
    retained, result = _retained_v3_result()
    view = _raw_view(
        tmp_path,
        (retained,),
        absent=frozenset({(1, "derived/" + retained.request.archive_name)}),
    )

    with pytest.raises(ValueError, match="raw snapshot must bind each source member exactly once"):
        create_binance_usdm_koru_aggregate_trade_boundary_index_authority_v3(
            result, view, _raw_identity(view)
        )


def test_v3_replay_rejects_capture_final_tamper_without_changing_v2() -> None:
    start = day_start_ns("2026-07-16")
    capture = official_capture(
        "2026-07-16", (row(700, 900, 901, start // 1_000_000 + 1_000),)
    )
    boundaries = ((start, start + DAY_NS),)
    v2_request = build_request((capture,), start, start + DAY_NS, boundaries)
    v2 = boundary_index.build_binance_usdm_koru_aggregate_trade_boundary_index_v1(
        v2_request
    ).result
    assert v2 is not None
    original_v2 = v2.to_canonical_dict()
    outcome = build_binance_usdm_koru_aggregate_trade_boundary_index_v3(
        v3_request((capture,), start, start + DAY_NS, boundaries)
    )
    assert outcome.result is not None
    forged_final = replace(
        outcome.result.capture_final_evidence[0],
        source_member_hash="sha256:" + "0" * 64,
    )
    forged = replace(outcome.result, capture_final_evidence=(forged_final,))

    assert boundary_index._trusted_result_v3(forged) is None
    assert v2.to_canonical_dict() == original_v2


def test_v3_eof_member_hash_and_retained_raw_mismatch_are_source_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evidence = retained_evidence_for()
    captured = capture_binance_usdm_koru_aggregate_trades_from_retained_rest_v1(
        retained_request_for(evidence),
        evidence.manifest,
        evidence.pages,
        evidence.derived,
        evidence.archive,
        evidence.checksum,
    ).result
    assert captured is not None
    start = RETAINED_DAY_START_MS * 1_000_000
    request = v3_request(
        (captured,),
        start,
        start + DAY_NS,
        ((COVERAGE_START_MS * 1_000_000, COVERAGE_END_MS * 1_000_000),),
    )
    authority = captured.request.authority
    assert authority is not None
    original_hash = authority.derived_csv_sha256
    try:
        object.__setattr__(authority, "derived_csv_sha256", "sha256:" + "0" * 64)
        with pytest.raises(boundary_index._V3BoundaryIndexError) as error:
            boundary_index._build_v3(request)
        assert error.value.code is BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV3.SOURCE_INVALID
    finally:
        object.__setattr__(authority, "derived_csv_sha256", original_hash)

    monkeypatch.setattr(boundary_index, "_retained_raw_rows", lambda _capture: iter((("bad",),)))
    outcome = build_binance_usdm_koru_aggregate_trade_boundary_index_v3(request)
    assert outcome.failure is not None
    assert outcome.failure.code is BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV3.SOURCE_INVALID


def test_v3_utf8_remains_source_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    start = day_start_ns("2026-07-16")
    capture = official_capture(
        "2026-07-16", (row(700, 900, 901, start // 1_000_000 + 1_000),)
    )
    invalid_archive = io.BytesIO()
    with ZipFile(invalid_archive, "w") as archive:
        info = ZipInfo(capture.request.csv_name)
        info.compress_type = ZIP_STORED
        archive.writestr(info, b"\xff\n")
    archive_bytes = invalid_archive.getvalue()
    monkeypatch.setattr(boundary_index, "_archive_bytes", lambda *_args: archive_bytes)
    monkeypatch.setattr(
        boundary_index,
        "_snapshot_member",
        lambda *_args: SimpleNamespace(content_hash=boundary_index._sha256(archive_bytes)),
    )

    outcome = build_binance_usdm_koru_aggregate_trade_boundary_index_v3(
        v3_request((capture,), start, start + DAY_NS, ((start, start + DAY_NS),))
    )

    assert outcome.failure is not None
    assert outcome.failure.code is BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV3.SOURCE_INVALID


def test_v3_boundary_and_gap_tamper_keep_v1_failure_classes() -> None:
    start = day_start_ns("2026-07-16")
    capture = official_capture(
        "2026-07-16", (row(700, 900, 901, start // 1_000_000 + 1_000),)
    )
    request = v3_request((capture,), start, start + DAY_NS, ((start, start + DAY_NS),))
    object.__setattr__(request.boundaries[0], "cutoff", UtcInstant(start))
    boundary_outcome = build_binance_usdm_koru_aggregate_trade_boundary_index_v3(request)
    assert boundary_outcome.failure is not None
    assert boundary_outcome.failure.code is BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV3.BOUNDARY_INVALID

    gapped = official_capture(
        "2026-07-16",
        (
            row(700, 900, 901, start // 1_000_000 + 1_000),
            row(702, 902, 903, start // 1_000_000 + 2_000),
        ),
    )
    v2 = boundary_index.build_binance_usdm_koru_aggregate_trade_boundary_index_v1(
        build_request((gapped,), start, start + DAY_NS, ((start, start + DAY_NS),))
    )
    v3 = build_binance_usdm_koru_aggregate_trade_boundary_index_v3(
        v3_request((gapped,), start, start + DAY_NS, ((start, start + DAY_NS),))
    )
    assert v2.failure is not None
    assert v3.failure is not None
    assert v2.failure.code.value == v3.failure.code.value == "data_gap_detected"


def test_v3_malformed_rows_remain_source_invalid() -> None:
    start = day_start_ns("2026-07-16")
    malformed = official_capture(
        "2026-07-16",
        (
            row(700, 900, 901, start // 1_000_000 + 1_000),
            ("701", "quoted,price", "1.250", "902", "903", str(start // 1_000_000 + 2_000), "false"),
        ),
    )
    request = v3_request(
        (malformed,), start, start + DAY_NS, ((start, start + DAY_NS),)
    )

    outcome = build_binance_usdm_koru_aggregate_trade_boundary_index_v3(request)

    assert outcome.result is None
    assert outcome.failure is not None
    assert outcome.failure.code is BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV3.SOURCE_INVALID
