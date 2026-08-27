from __future__ import annotations

import argparse
import json
import os
import shutil
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Literal

from crypto_quant_bundle_builder import (
    RawSourceMember,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
    verify_source_snapshot,
)
from crypto_quant_domain import (
    InstrumentId,
    UtcInstant,
    VenueId,
    canonical_bytes,
    canonical_sha256,
)

import crypto_quant_bundle_builder.official_annual_report_nonfiling_v1 as nonfiling

from . import _common
from ._common import AcquisitionError
from .cn_a_share_official_s2_remediation_source_bounded_v1 import _require_safe_output

PARENT_SNAPSHOT_ID = "sha256:8195e9d9e99949802c829f218929bdbf740b336152d83ad789a060e0355d116e"
SUPPLEMENT_SNAPSHOT_ID = "sha256:052b42ca292a9708cf71586d65a965a12568d55e5629712f22966ab1b1cc9afe"
BOUNDARY_LINEAGE_SNAPSHOT_ID = "sha256:efceeae9bf6a8770d032e510bd2a13e691fe6e220ccebf103531e03dae98c295"
PARENT_RAW_MEMBER_COUNT = 22
PARENT_RAW_BYTES = 6_858_620
SUPPLEMENT_RAW_MEMBER_COUNT = 6
SUPPLEMENT_RAW_BYTES = 480_389
BOUNDARY_LINEAGE_RAW_MEMBER_COUNT = 4
BOUNDARY_LINEAGE_RAW_BYTES = 172_606
HISTORICAL_CALENDAR_AUTHORITY_ID = "sha256:22585fa4c2070d87544f0ba977be757770aeeaad5bead30188317c1794680ee8"
_CALENDAR_MEMBER_KEYS = (
    "response/tushare/trade_cal/sse-20260430-20260510-v1.json",
    "response/tushare/trade_cal/szse-20260430-20260510-v1.json",
)
_LINEAGE_MEMBER_KEY = "response/official/601028/d906b07f748045d4aef1718916182a99.pdf"
_LINEAGE_METADATA_FACT = {
    "seccode": "400267",
    "secname": "R玉龙1",
    "published_at": "2025-07-31T00:00:00.000+00:00",
    "title": "[临时公告]R玉龙1:2025-016 公司全称变更公告",
    "metadata_pdf_url": "http://dataclouds.cninfo.com.cn/sjother/neeqs/2025/20250731/d906b07f748045d4aef1718916182a99.pdf",
    "retained_pdf_url": "https://dataclouds.cninfo.com.cn/sjother/neeqs/2025/20250731/d906b07f748045d4aef1718916182a99.pdf",
}
_LIMITATIONS = (
    "ISSUER_LOCAL_UNRESOLVED_ONLY",
    "NO_FORCED_EXIT_OR_SLOT_RELEASE",
    "NO_NUMERIC_FINANCIAL_VALUES",
    "NO_THRESHOLD_FAILURE",
    "NO_UNRELATED_ISSUER_BLOCK",
    "SOURCE_BOUNDED_DEVELOPMENT_ONLY",
)


@dataclass(frozen=True, slots=True)
class DocumentSpec:
    root: Literal["parent", "supplement"]
    member_key: str
    source_url: str
    published_date: date
    published_at_epoch_nanoseconds: int
    evidence_kind: nonfiling.NonFilingEvidenceKind
    authority: nonfiling.NonFilingAuthority
    reviewed_pages: tuple[int, ...]
    reviewed_excerpt: str
    source_visibility_at_epoch_nanoseconds: int | None


@dataclass(frozen=True, slots=True)
class DeclarationSpec:
    provider_code: str
    fiscal_period_end_date: date
    statutory_deadline_date: date
    deadline_boundary_at_epoch_nanoseconds: int
    active_interval_end_epoch_nanoseconds: int
    terminal_confirmation_fact_date: date
    initial: DocumentSpec
    terminal: DocumentSpec


_DECLARATIONS = (
    DeclarationSpec(
        "000693.SZ", date(2018, 12, 31), date(2019, 4, 30), 1557106200000000000,
        1588728600000000000, date(2019, 5, 17),
        DocumentSpec(
            "parent", "response/official/000693/1206163240.pdf",
            "https://static.cninfo.com.cn/finalpage/2019-04-30/1206163240.PDF",
            date(2019, 4, 29), 1556553600000000000,
            nonfiling.NonFilingEvidenceKind.PREDEADLINE_DEFINITIVE_INABILITY,
            nonfiling.NonFilingAuthority.ISSUER, (1, 2),
            "无法在法定期限内（即 2019 年 4 月 30 日内）披露 2018 年年度报告",
            1556553600000000000,
        ),
        DocumentSpec(
            "parent", "response/official/000693/1206283352.pdf",
            "https://static.cninfo.com.cn/finalpage/2019-05-18/1206283352.PDF",
            date(2019, 5, 17), 1558108800000000000,
            nonfiling.NonFilingEvidenceKind.TERMINAL_NONFILING_CONFIRMATION,
            nonfiling.NonFilingAuthority.SZSE, (2,),
            "公司未能在法定期限内（即 2019 年 4 月 30 日前）披露暂停上市后的首个年度报告（即 2018 年年度报告）",
            1558108800000000000,
        ),
    ),
    DeclarationSpec(
        "600090.SH", date(2021, 12, 31), date(2022, 4, 30), 1651714200000000000,
        1683163800000000000, date(2022, 9, 20),
        DocumentSpec(
            "parent", "response/official/600090/a38770503b904cf88f85ebe52a75ad36.pdf",
            "https://www.sse.com.cn/disclosure/credibility/supervision/inquiries/enquiry/c/10111560/files/a38770503b904cf88f85ebe52a75ad36.pdf",
            date(2022, 4, 30), 1651302366000000000,
            nonfiling.NonFilingEvidenceKind.POST_DEADLINE_NONFILING_CONFIRMATION,
            nonfiling.NonFilingAuthority.SSE, (1, 5),
            "截至 2022 年 4 月 30 日，你公司未在法定期限内披露经审计的 2021 年年度报告",
            1651714200000000000,
        ),
        DocumentSpec(
            "parent", "response/official/600090/16e8ccc4577d410891dfba7e2a691af0.pdf",
            "https://www.sse.com.cn/disclosure/credibility/supervision/measures/focus/c/10107770/files/16e8ccc4577d410891dfba7e2a691af0.pdf",
            date(2022, 9, 20), 1663659329000000000,
            nonfiling.NonFilingEvidenceKind.TERMINAL_NONFILING_CONFIRMATION,
            nonfiling.NonFilingAuthority.SSE, (1,),
            "因公司未按规定在法定期限内披露定期报告，公司股票于 2022 年 7 月 7 日终止上市暨摘牌",
            None,
        ),
    ),
    DeclarationSpec(
        "600146.SH", date(2021, 12, 31), date(2022, 4, 30), 1651714200000000000,
        1683163800000000000, date(2022, 10, 20),
        DocumentSpec(
            "parent", "response/official/600146/514dd89bf3c24c4a95afb42c4aa7cfba.pdf",
            "https://www.sse.com.cn/disclosure/credibility/supervision/inquiries/enquiry/c/10111562/files/514dd89bf3c24c4a95afb42c4aa7cfba.pdf",
            date(2022, 4, 29), 1651242536000000000,
            nonfiling.NonFilingEvidenceKind.PREDEADLINE_DEFINITIVE_INABILITY,
            nonfiling.NonFilingAuthority.SSE, (1, 3),
            "我所无法在 2022 年 4 月 30 日前履行完审计程序、无法出具审计报告",
            1651714200000000000,
        ),
        DocumentSpec(
            "parent", "response/official/600146/8f60b5e2db23462e84d9ef368cb683ac.pdf",
            "https://www.sse.com.cn/disclosure/credibility/supervision/measures/focus/c/10107748/files/8f60b5e2db23462e84d9ef368cb683ac.pdf",
            date(2022, 10, 20), 1666235402000000000,
            nonfiling.NonFilingEvidenceKind.TERMINAL_NONFILING_CONFIRMATION,
            nonfiling.NonFilingAuthority.SSE, (1,),
            "公司在股票终止上市前，未披露 2021 年年度报告和 2022 年第一季度报告",
            None,
        ),
    ),
    DeclarationSpec(
        "000038.SZ", date(2022, 12, 31), date(2023, 4, 30), 1683163800000000000,
        1714959000000000000, date(2023, 6, 9),
        DocumentSpec(
            "supplement", "response/official/000038/1216706117.pdf",
            "https://static.cninfo.com.cn/finalpage/2023-04-29/1216706117.PDF",
            date(2023, 4, 28), 1682701857000000000,
            nonfiling.NonFilingEvidenceKind.PREDEADLINE_DEFINITIVE_INABILITY,
            nonfiling.NonFilingAuthority.ISSUER, (1, 2),
            "因无法在法定期限内（2023 年 4 月 30 日）披露 2022 年度报告及 2023 年第一季度报告",
            1682701857000000000,
        ),
        DocumentSpec(
            "parent", "response/official/000038/1217029890.pdf",
            "https://static.cninfo.com.cn/finalpage/2023-06-10/1217029890.PDF",
            date(2023, 6, 9), 1686326400000000000,
            nonfiling.NonFilingEvidenceKind.TERMINAL_NONFILING_CONFIRMATION,
            nonfiling.NonFilingAuthority.SZSE, (2,),
            "截至 2023 年 4 月 30 日，你公司未在法定期限内披露过半数董事保证真实、准确、完整的 2022 年年度报告",
            1686326400000000000,
        ),
    ),
    DeclarationSpec(
        "000976.SZ", date(2023, 12, 31), date(2024, 4, 30), 1714959000000000000,
        1746495000000000000, date(2024, 8, 23),
        DocumentSpec(
            "supplement", "response/official/000976/1219960138.pdf",
            "https://static.cninfo.com.cn/finalpage/2024-04-30/1219960138.PDF",
            date(2024, 4, 30), 1714474662000000000,
            nonfiling.NonFilingEvidenceKind.PREDEADLINE_DEFINITIVE_INABILITY,
            nonfiling.NonFilingAuthority.ISSUER, (1, 2),
            "无法在法定期限内披露 2023 年年度报告",
            1714474662000000000,
        ),
        DocumentSpec(
            "parent", "response/official/000976/1220964685.pdf",
            "https://static.cninfo.com.cn/finalpage/2024-08-24/1220964685.PDF",
            date(2024, 8, 23), 1724428800000000000,
            nonfiling.NonFilingEvidenceKind.TERMINAL_NONFILING_CONFIRMATION,
            nonfiling.NonFilingAuthority.ISSUER, (1, 2),
            "公司未在法定期限内（2024 年 4 月 30 日）披露 2023 年年度报告及 2024 年第一季度报告",
            1724428800000000000,
        ),
    ),
    DeclarationSpec(
        "000622.SZ", date(2024, 12, 31), date(2025, 4, 30), 1746495000000000000,
        1778031000000000000, date(2025, 6, 18),
        DocumentSpec(
            "parent", "response/official/000622/1223449834.pdf",
            "https://static.cninfo.com.cn/finalpage/2025-05-06/1223449834.pdf",
            date(2025, 5, 5), 1746460800000000000,
            nonfiling.NonFilingEvidenceKind.POST_DEADLINE_NONFILING_CONFIRMATION,
            nonfiling.NonFilingAuthority.ISSUER, (1, 2),
            "公司因无法在法定期限内披露 2024 年年度报告",
            1746460800000000000,
        ),
        DocumentSpec(
            "parent", "response/official/000622/1223910946.pdf",
            "https://static.cninfo.com.cn/finalpage/2025-06-19/1223910946.PDF",
            date(2025, 6, 18), 1750262400000000000,
            nonfiling.NonFilingEvidenceKind.TERMINAL_NONFILING_CONFIRMATION,
            nonfiling.NonFilingAuthority.SZSE, (2,),
            "截至 2025 年 4 月 30 日，你公司未在法定期限内披露过半数董事保证真实、准确、完整的 2024 年年度报告",
            1750262400000000000,
        ),
    ),
    DeclarationSpec(
        "601028.SH", date(2024, 12, 31), date(2025, 4, 30), 1746495000000000000,
        1778031000000000000, date(2026, 4, 29),
        DocumentSpec(
            "parent", "response/official/601028/1223364517.pdf",
            "https://static.cninfo.com.cn/finalpage/2025-04-29/1223364517.PDF",
            date(2025, 4, 28), 1745856000000000000,
            nonfiling.NonFilingEvidenceKind.PREDEADLINE_DEFINITIVE_INABILITY,
            nonfiling.NonFilingAuthority.ISSUER, (1,),
            "因此无法在法定期限内披露 2024 年年度报告及 2025 年第一季度报告",
            1745856000000000000,
        ),
        DocumentSpec(
            "supplement", "response/official/601028/5e69266176024a6dae6eb9392c5e22b5.pdf",
            "https://dataclouds.cninfo.com.cn/sjother2/neeqs/2026/20260429/5e69266176024a6dae6eb9392c5e22b5.pdf",
            date(2026, 4, 29), 1777420800000000000,
            nonfiling.NonFilingEvidenceKind.TERMINAL_NONFILING_CONFIRMATION,
            nonfiling.NonFilingAuthority.NEEQ_SPONSOR, (1,),
            "公司亦未披露 2024 年年度报告、2025 年半年度报告",
            1777420800000000000,
        ),
    ),
)


def _json_value(value: object) -> object:
    if hasattr(value, "to_canonical_dict"):
        return _json_value(value.to_canonical_dict())
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    return value


def _json_bytes(value: object) -> bytes:
    return canonical_bytes(_json_value(value))


def _load_root(
    root: Path,
    expected_snapshot_id: str,
    expected_member_count: int,
    expected_raw_bytes: int,
) -> tuple[dict[str, object], dict[str, dict[str, object]], dict[str, object]]:
    snapshot_path = root / "source-snapshot.json"
    receipt_path = root / "acquisition-receipt.json"
    if (
        root.is_symlink()
        or root.resolve() != root.absolute()
        or not root.is_dir()
        or any(path.is_symlink() or not path.is_file() or path.stat().st_size > (1 << 20) for path in (snapshot_path, receipt_path))
    ):
        raise AcquisitionError("input source root is unreadable")
    try:
        snapshot = json.loads(snapshot_path.read_bytes())
        receipt = json.loads(receipt_path.read_bytes())
        provenance = SourceSnapshotProvenance(**snapshot["provenance"])
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise AcquisitionError("input source root is unreadable") from error
    values = snapshot.get("members")
    if (
        snapshot.get("snapshot_id") != expected_snapshot_id
        or receipt.get("snapshot") != snapshot
        or type(values) is not list
        or len(values) != expected_member_count
        or sum(value.get("byte_count", -1) for value in values if type(value) is dict)
        != expected_raw_bytes
        or root.is_symlink()
        or root.resolve() != root.absolute()
    ):
        raise AcquisitionError("input source snapshot identity mismatch")
    raw_members = []
    members: dict[str, dict[str, object]] = {}
    try:
        for value in values:
            member_key = value["member_key"]
            relative = PurePosixPath(member_key)
            if (
                type(member_key) is not str
                or not member_key
                or "\\" in member_key
                or relative.is_absolute()
                or ".." in relative.parts
                or relative.as_posix() != member_key
                or member_key in members
                or value.get("compression") is not None
            ):
                raise ValueError("member mismatch")
            path = root.joinpath(*relative.parts)
            if (
                path.is_symlink()
                or any(parent.is_symlink() for parent in path.parents if parent != root.parent)
                or not path.is_file()
                or path.stat().st_size != value["byte_count"]
                or path.stat().st_size > expected_raw_bytes
            ):
                raise ValueError("member path mismatch")
            source = path.read_bytes()
            raw_members.append(
                RawSourceMember(
                    member_key,
                    source,
                    value["mode"],
                    value["acquired_at_epoch_nanoseconds"],
                    None,
                )
            )
            members[member_key] = value
    except (KeyError, OSError, TypeError, ValueError) as error:
        raise AcquisitionError("input source member identity mismatch") from error
    rebuilt = freeze_source_snapshot(members=tuple(raw_members), provenance=provenance)
    if (
        rebuilt.snapshot is None
        or verify_source_snapshot(rebuilt.snapshot).snapshot is None
        or rebuilt.snapshot.to_canonical_dict() != snapshot
    ):
        raise AcquisitionError("input source snapshot reconstruction mismatch")
    return snapshot, members, receipt


def _review_boundary_lineage(
    root: Path,
    members: dict[str, dict[str, object]],
    receipt: dict[str, object],
) -> dict[str, object]:
    if receipt.get("selected_neeq_fact") != _LINEAGE_METADATA_FACT:
        raise AcquisitionError("issuer lineage metadata mismatch")
    for member_key, exchange in zip(_CALENDAR_MEMBER_KEYS, ("SSE", "SZSE"), strict=True):
        try:
            payload = json.loads((root / member_key).read_bytes())
            rows = payload["data"]["items"]
        except (KeyError, OSError, TypeError, json.JSONDecodeError) as error:
            raise AcquisitionError("2026 calendar boundary mismatch") from error
        expected = {
            "20260430": (1, "20260429"),
            "20260501": (0, "20260430"),
            "20260502": (0, "20260430"),
            "20260503": (0, "20260430"),
            "20260504": (0, "20260430"),
            "20260505": (0, "20260430"),
            "20260506": (1, "20260430"),
            "20260507": (1, "20260506"),
            "20260508": (1, "20260507"),
            "20260509": (0, "20260508"),
            "20260510": (0, "20260508"),
        }
        if (
            type(rows) is not list
            or len(rows) != len(expected)
            or any(
                type(row) is not list
                or len(row) != 4
                or type(row[0]) is not str
                or type(row[1]) is not str
                or type(row[2]) is not int
                or isinstance(row[2], bool)
                or type(row[3]) is not str
                for row in rows
            )
            or {row[1]: (row[2], row[3]) for row in rows} != expected
            or any(row[0] != exchange for row in rows)
        ):
            raise AcquisitionError("2026 calendar boundary mismatch")
    lineage = members.get(_LINEAGE_MEMBER_KEY)
    if lineage is None:
        raise AcquisitionError("issuer lineage source mismatch")
    return {
        "calendar_source_snapshot_id": BOUNDARY_LINEAGE_SNAPSHOT_ID,
        "next_annual_s2_boundary_at": UtcInstant(1778031000000000000),
        "issuer_lineage_source_snapshot_id": BOUNDARY_LINEAGE_SNAPSHOT_ID,
        "issuer_lineage_member_key": _LINEAGE_MEMBER_KEY,
        "reviewed_pages": (1,),
        "reviewed_excerpt": (
            "变更前公司全称为“山东玉龙黄金股份有限公司”，变更后全称为"
            "“山东鑫升矿业股份有限公司”，证券代码保持不变"
        ),
        "issuer_lineage_assertion": (
            "601028/山东玉龙黄金股份有限公司 transferred to 400267/R玉龙1 and "
            "then changed its full name to 山东鑫升矿业股份有限公司 without changing code."
        ),
    }


def _atomic_publish(output: Path, published: dict[str, bytes]) -> None:
    staging = output.parent / f".{output.name}.staging-nonfiling-v1"
    try:
        _require_safe_output(output)
        output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        _require_safe_output(output)
        _require_safe_output(staging)
        staging.mkdir(mode=0o700)
        for relative, source in published.items():
            path = staging / relative
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                os.fchmod(descriptor, 0o600)
                with os.fdopen(descriptor, "wb") as handle:
                    descriptor = -1
                    handle.write(source)
                    handle.flush()
                    os.fsync(handle.fileno())
            finally:
                if descriptor >= 0:
                    os.close(descriptor)
        if any((staging / relative).read_bytes() != source for relative, source in published.items()):
            raise OSError("staged readback mismatch")
        directory = os.open(staging, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        _require_safe_output(output)
        os.rename(staging, output)
        parent = os.open(output.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(parent)
        finally:
            os.close(parent)
    except BaseException as error:
        shutil.rmtree(staging, ignore_errors=True)
        if isinstance(error, AcquisitionError):
            raise
        raise AcquisitionError("declaration publication failed") from None


def _availability(
    member_key: str,
    source_visibility_ns: int,
    boundary_ns: int,
    source_availability_id: str,
    calendar_authority_id: str,
) -> nonfiling.OfficialNonFilingAvailabilityV1:
    body = {
        "type": "official_nonfiling_availability",
        "schema_version": 1,
        "document_member_key": member_key,
        "source_visibility_at": UtcInstant(source_visibility_ns),
        "deadline_boundary_at": UtcInstant(boundary_ns),
        "available_at": UtcInstant(max(source_visibility_ns, boundary_ns)),
        "calendar_authority_id": calendar_authority_id,
        "source_availability_id": source_availability_id,
    }
    return nonfiling.OfficialNonFilingAvailabilityV1(**body, availability_id=canonical_sha256(body))


def _instrument(provider_code: str) -> InstrumentId:
    code, suffix = provider_code.split(".")
    return InstrumentId(VenueId({"SZ": "xshe", "SH": "xshg"}[suffix]), code)


def build_official_nonfiling_declarations_v1(
    *,
    parent_root: Path,
    supplement_root: Path,
    boundary_lineage_root: Path,
    output_dir: Path,
) -> dict[str, object]:
    output = _require_safe_output(output_dir)
    roots = {"parent": parent_root, "supplement": supplement_root}
    loaded = {
        "parent": _load_root(
            parent_root,
            PARENT_SNAPSHOT_ID,
            PARENT_RAW_MEMBER_COUNT,
            PARENT_RAW_BYTES,
        ),
        "supplement": _load_root(
            supplement_root,
            SUPPLEMENT_SNAPSHOT_ID,
            SUPPLEMENT_RAW_MEMBER_COUNT,
            SUPPLEMENT_RAW_BYTES,
        ),
        "boundary_lineage": _load_root(
            boundary_lineage_root,
            BOUNDARY_LINEAGE_SNAPSHOT_ID,
            BOUNDARY_LINEAGE_RAW_MEMBER_COUNT,
            BOUNDARY_LINEAGE_RAW_BYTES,
        ),
    }
    _boundary_snapshot, boundary_members, boundary_receipt = loaded["boundary_lineage"]
    boundary_lineage_review = _review_boundary_lineage(
        boundary_lineage_root,
        boundary_members,
        boundary_receipt,
    )
    published: dict[str, bytes] = {}
    declaration_rows: list[dict[str, object]] = []
    covered_keys: list[tuple[str, dict[str, object], str]] = []

    for spec in _DECLARATIONS:
        documents = (spec.initial, spec.terminal)
        raw_members: list[RawSourceMember] = []
        selected: dict[str, tuple[bytes, dict[str, object], str]] = {}
        for document in documents:
            snapshot, members, _receipt = loaded[document.root]
            member = members.get(document.member_key)
            try:
                source = (roots[document.root] / document.member_key).read_bytes()
            except OSError as error:
                raise AcquisitionError("required source member is unreadable") from error
            if member is None or member.get("byte_count") != len(source) or member.get("content_hash") != _common.sha256(source):
                raise AcquisitionError("required source member binding mismatch")
            acquired_at = member.get("acquired_at_epoch_nanoseconds")
            if type(acquired_at) is not int:
                raise AcquisitionError("required source acquisition instant mismatch")
            raw_members.append(RawSourceMember(document.member_key, source, "0644", acquired_at, None))
            selected[document.member_key] = (source, member, snapshot["snapshot_id"])
            published[document.member_key] = source

        snapshot_outcome = freeze_source_snapshot(
            members=tuple(raw_members),
            provenance=SourceSnapshotProvenance(
                vendor_key="official.cninfo.sse.neeq",
                source_key=f"quality-bband.nonfiling.{spec.provider_code.lower()}.{spec.fiscal_period_end_date.isoformat()}",
                license_ref="public.official.disclosure",
                retention_policy_ref="immutable.reviewed.two-member.snapshot",
            ),
        )
        source_snapshot = snapshot_outcome.snapshot
        if source_snapshot is None or verify_source_snapshot(source_snapshot).snapshot is None:
            raise AcquisitionError("declaration source snapshot failed verification")
        members = {value.member_key: value for value in source_snapshot.members}
        reviewed_at = max(value.acquired_at_epoch_nanoseconds for value in source_snapshot.members) + 1

        refs = []
        for index, document in enumerate(documents):
            member = members[document.member_key]
            refs.append(
                nonfiling.ReviewedNonFilingDocumentV1(
                    type="reviewed_nonfiling_document",
                    schema_version=1,
                    role=(
                        nonfiling.NonFilingDocumentRole.INITIAL_NONFILING_PROOF
                        if index == 0
                        else nonfiling.NonFilingDocumentRole.TERMINAL_CONFIRMATION
                    ),
                    evidence_kind=document.evidence_kind,
                    authority=document.authority,
                    member_key=document.member_key,
                    source_url=document.source_url,
                    published_date=document.published_date,
                    publication_precision="EXACT_INSTANT",
                    published_at_epoch_nanoseconds=document.published_at_epoch_nanoseconds,
                    content_hash=member.content_hash,
                    byte_count=member.byte_count,
                    reviewed_pages=document.reviewed_pages,
                    reviewed_excerpt=document.reviewed_excerpt,
                    issuer_assertion=f"{spec.provider_code} required annual report was not filed by the statutory deadline.",
                    period_assertion=f"Annual period ended {spec.fiscal_period_end_date.isoformat()}.",
                    supersedes_member_key=None if index == 0 else spec.initial.member_key,
                    reviewer_key="quality-bband-eight-issuer-official-authority-audit-v1",
                    reviewed_at_epoch_nanoseconds=reviewed_at,
                )
            )

        initial_source_id = selected[spec.initial.member_key][2]
        terminal_source_id = selected[spec.terminal.member_key][2]
        terminal_member = members[spec.terminal.member_key]
        calendar_authority_id = HISTORICAL_CALENDAR_AUTHORITY_ID
        initial_availability = _availability(
            spec.initial.member_key,
            spec.initial.source_visibility_at_epoch_nanoseconds
            or members[spec.initial.member_key].acquired_at_epoch_nanoseconds,
            spec.deadline_boundary_at_epoch_nanoseconds,
            initial_source_id,
            calendar_authority_id,
        )
        terminal_availability = _availability(
            spec.terminal.member_key,
            spec.terminal.source_visibility_at_epoch_nanoseconds
            or terminal_member.acquired_at_epoch_nanoseconds,
            spec.deadline_boundary_at_epoch_nanoseconds,
            terminal_source_id,
            calendar_authority_id,
        )
        outcome = nonfiling.declare_official_annual_report_nonfiling_v1(
            nonfiling.OfficialAnnualReportNonFilingRequestV1(
                type="official_annual_report_nonfiling_request",
                schema_version=1,
                instrument_id=_instrument(spec.provider_code),
                provider_code=spec.provider_code,
                fiscal_period_end_date=spec.fiscal_period_end_date,
                statutory_deadline_date=spec.statutory_deadline_date,
                source_snapshot=source_snapshot,
                source_documents=(refs[0], refs[1]),
                initial_availability=initial_availability,
                terminal_availability=terminal_availability,
                active_interval_end=UtcInstant(spec.active_interval_end_epoch_nanoseconds),
                terminal_confirmation_fact_date=spec.terminal_confirmation_fact_date,
                limitations=_LIMITATIONS,
            )
        )
        if outcome.declaration is None or outcome.failure is not None:
            failure = outcome.failure.value if outcome.failure is not None else "UNKNOWN"
            raise AcquisitionError(f"declaration construction failed: {spec.provider_code}: {failure}")

        period = spec.fiscal_period_end_date.strftime("%Y%m%d")
        stem = f"{spec.provider_code}-{period}"
        declaration_path = f"declarations/{stem}.json"
        snapshot_path = f"source-snapshots/{stem}.json"
        published[declaration_path] = _json_bytes(outcome.declaration.to_canonical_dict())
        published[snapshot_path] = _json_bytes(source_snapshot.to_canonical_dict())
        declaration_rows.append(
            {
                "provider_code": spec.provider_code,
                "fiscal_period_end_date": spec.fiscal_period_end_date.isoformat(),
                "declaration_id": outcome.declaration.declaration_id,
                "declaration_path": declaration_path,
                "source_snapshot_path": snapshot_path,
                "source_snapshot_id": source_snapshot.snapshot_id,
                "source_content_tree_hash": source_snapshot.content_tree_hash,
                "source_provenance_hash": source_snapshot.provenance_hash,
                "issuer_lineage_review_ref": (
                    BOUNDARY_LINEAGE_SNAPSHOT_ID
                    if spec.provider_code == "601028.SH"
                    else None
                ),
            }
        )
        instrument_key = _instrument(spec.provider_code).to_canonical_dict()
        covered_keys.extend(
            (api_name, instrument_key, period)
            for api_name in ("income_vip", "balancesheet_vip", "cashflow_vip")
        )

    body: dict[str, object] = {
        "type": "official_annual_report_nonfiling_declaration_publication",
        "schema_version": 1,
        "input_source_snapshot_ids": {
            "parent": PARENT_SNAPSHOT_ID,
            "supplement": SUPPLEMENT_SNAPSHOT_ID,
            "historical_calendar": HISTORICAL_CALENDAR_AUTHORITY_ID,
            "boundary_lineage": BOUNDARY_LINEAGE_SNAPSHOT_ID,
        },
        "boundary_lineage_review": boundary_lineage_review,
        "declarations": declaration_rows,
        "covered_member_keys": sorted(
            covered_keys,
            key=lambda value: (
                value[0],
                value[1]["venue"],
                value[1]["stable_key"],
                value[2],
            ),
        ),
        "declaration_count": len(declaration_rows),
        "covered_member_count": len(covered_keys),
        "official_evidence_reviewed": True,
        "calendar_boundary_reviewed": True,
        "issuer_lineage_reviewed": True,
        "nonfiling_declarations_constructed": True,
        "source_bounded_financial_availability_qualified": True,
        "formal_s1_qualified": False,
        "s2b_exact_cover_complete": False,
        "decision_grade_eligible": False,
        "strategy_target_authorized": False,
        "deployment_authorized": False,
        "limitations": list(_LIMITATIONS),
    }
    receipt = {**body, "publication_id": canonical_sha256(body)}
    published["declaration-receipt.json"] = _json_bytes(receipt)
    if len(declaration_rows) != 7 or len(covered_keys) != 21 or len(published) != 29:
        raise AcquisitionError("declaration publication exact cover mismatch")
    _atomic_publish(output, published)
    return receipt


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-root", type=Path, required=True)
    parser.add_argument("--supplement-root", type=Path, required=True)
    parser.add_argument("--boundary-lineage-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        receipt = build_official_nonfiling_declarations_v1(
            parent_root=args.parent_root,
            supplement_root=args.supplement_root,
            boundary_lineage_root=args.boundary_lineage_root,
            output_dir=args.output_dir,
        )
    except AcquisitionError as error:
        raise SystemExit(f"declaration publication failed: {error}") from None
    print(json.dumps(_json_value(receipt), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
