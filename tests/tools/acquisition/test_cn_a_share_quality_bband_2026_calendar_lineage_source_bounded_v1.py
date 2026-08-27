from __future__ import annotations

import json
import stat
from pathlib import Path
from typing import Any

import pytest
from crypto_quant_bundle_builder import (
    RawSourceMember,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
)
from crypto_quant_domain import canonical_bytes

from tools.acquisition import cn_a_share_quality_bband_2026_calendar_lineage_source_bounded_v1 as subject
from tools.acquisition._common import AcquisitionError, sha256

TOKEN = "t" * 56
ENDPOINT = subject._ALLOWED_ENDPOINTS[0]
PDF = b"%PDF-fixture-lineage"


def calendar_bytes(exchange: str, *, mutate: bool = False) -> bytes:
    rows = [[exchange, day, is_open, previous] for day, is_open, previous in subject._EXPECTED_CALENDAR_DAYS]
    if mutate:
        rows[4][2] = 0
    return json.dumps(
        {
            "request_id": f"fixture-{exchange}",
            "code": 0,
            "msg": "",
            "detail": "",
            "data": {
                "fields": list(subject._CALENDAR_FIELDS),
                "items": rows,
                "has_more": False,
                "count": 0,
            },
        },
        separators=(",", ":"),
    ).encode()


def neeq_bytes(*, duplicate_selected: bool = False) -> bytes:
    selected = {
        "seccode": "400267",
        "secname": "R玉龙1",
        "f001d": "2025-07-31T00:00:00.000+00:00",
        "f002v": "[临时公告]R玉龙1:2025-016 公司全称变更公告",
        "f003v": subject._METADATA_PDF_URL,
        "f004v": "PDF",
        "retainedExtraField": "raw-source",
    }
    rows = [selected]
    rows.extend(
        {
            "seccode": "400267",
            "secname": "R玉龙1",
            "f003v": subject._METADATA_PDF_URL if duplicate_selected and index == 0 else f"http://example.invalid/{index}.pdf",
            "retainedExtraField": "extra",
        }
        for index in range(12)
    )
    return json.dumps(
        {
            "code": 0,
            "errorMessage": None,
            "data": {
                "code": 0,
                "errorMessage": None,
                "data": rows,
                "currentPage": 1,
                "size": 30,
                "total": 13,
            },
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()


class Clock:
    def __init__(self) -> None:
        self.value = 1_800_000_000_000_000_000

    def __call__(self) -> int:
        self.value += 1
        return self.value


class Transport:
    def __init__(self) -> None:
        self.proxy_calls: list[tuple[str, dict[str, object], dict[str, str]]] = []
        self.get_calls: list[tuple[str, subject.HeaderPairs]] = []
        self.calendar_mutation: str | None = None
        self.duplicate_selected = False
        self.final_url: str | None = None
        self.failures = 0

    def proxy_post(self, url: str, body: dict[str, object], headers: dict[str, str]):
        self.proxy_calls.append((url, body, headers))
        exchange = body["params"]["exchange"]  # type: ignore[index]
        return 200, calendar_bytes(str(exchange), mutate=exchange == self.calendar_mutation)

    def get(self, url: str, headers: subject.HeaderPairs):
        self.get_calls.append((url, headers))
        if self.failures:
            self.failures -= 1
            return 503, (), b"retry", url
        if url == subject._NEEQ_URL:
            return 200, (("Content-Type", "application/json"),), neeq_bytes(duplicate_selected=self.duplicate_selected), self.final_url or url
        return 200, (("Content-Type", "application/pdf"),), PDF, self.final_url or url


def acquire(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, transport: Transport | None = None):
    monkeypatch.setattr(subject, "_PDF_BYTE_COUNT", len(PDF))
    monkeypatch.setattr(subject, "_PDF_SHA256", sha256(PDF))
    selected = transport or Transport()
    output = tmp_path / "candidate"
    receipt = subject.acquire_cn_a_share_quality_bband_2026_calendar_lineage_source_bounded_v1(
        token=TOKEN,
        endpoint=ENDPOINT,
        output_dir=output,
        proxy_post=selected.proxy_post,
        get=selected.get,
        sleep=lambda _seconds: None,
        clock=Clock(),
    )
    return receipt, output, selected


def test_success_is_exact_canonical_atomic_source_snapshot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    receipt, output, transport = acquire(tmp_path, monkeypatch)
    files = sorted(path for path in output.rglob("*") if path.is_file())
    assert len(files) == 6
    assert all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in files)
    assert (output / "acquisition-receipt.json").read_bytes() == canonical_bytes(receipt)
    assert (output / "source-snapshot.json").read_bytes() == canonical_bytes(receipt["snapshot"])
    assert [value["logical_index"] for value in receipt["logical_requests"]] == list(range(4))
    assert receipt["neeq_extra_record_count"] == 12
    assert receipt["selected_neeq_fact"]["seccode"] == "400267"
    assert receipt["selected_neeq_fact"]["secname"] == "R玉龙1"
    assert all(receipt[flag] is False for flag in subject._FALSE_FLAGS)
    assert len(transport.proxy_calls) == 2 and len(transport.get_calls) == 2
    encoded = b"".join(path.read_bytes() for path in files)
    assert TOKEN.encode() not in encoded

    snapshot = receipt["snapshot"]
    by_key = {value["member_key"]: value for value in snapshot["members"]}
    rebuilt = freeze_source_snapshot(
        members=tuple(
            RawSourceMember(
                key,
                (output / key).read_bytes(),
                "0644",
                by_key[key]["acquired_at_epoch_nanoseconds"],
                None,
            )
            for key in by_key
        ),
        provenance=SourceSnapshotProvenance(**snapshot["provenance"]),
    )
    assert rebuilt.snapshot is not None
    assert rebuilt.snapshot.to_canonical_dict() == snapshot


def test_request_shapes_calendar_boundary_and_secret_redaction(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    receipt, _output, transport = acquire(tmp_path, monkeypatch)
    assert {call[1]["params"]["exchange"] for call in transport.proxy_calls} == {"SSE", "SZSE"}  # type: ignore[index]
    assert all(call[1]["api_name"] == "trade_cal" for call in transport.proxy_calls)
    assert all(call[1]["fields"] == ",".join(subject._CALENDAR_FIELDS) for call in transport.proxy_calls)
    assert all(call[2]["x-api-key"] == TOKEN for call in transport.proxy_calls)
    for request in receipt["logical_requests"][:2]:
        assert request["returned_row_count"] == 11
        assert all(name.lower() != "x-api-key" for name, _value in request["ordered_headers"])
    assert receipt["selected_neeq_fact"] == {
        "seccode": "400267",
        "secname": "R玉龙1",
        "published_at": "2025-07-31T00:00:00.000+00:00",
        "title": "[临时公告]R玉龙1:2025-016 公司全称变更公告",
        "metadata_pdf_url": subject._METADATA_PDF_URL,
        "retained_pdf_url": subject._PDF_URL,
    }


@pytest.mark.parametrize("failure", ["calendar", "duplicate", "redirect"])
def test_scope_and_redirect_failures_publish_nothing(
    failure: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transport = Transport()
    if failure == "calendar":
        transport.calendar_mutation = "SSE"
    elif failure == "duplicate":
        transport.duplicate_selected = True
    else:
        transport.final_url = "https://example.invalid/redirect"
    monkeypatch.setattr(subject, "_PDF_BYTE_COUNT", len(PDF))
    monkeypatch.setattr(subject, "_PDF_SHA256", sha256(PDF))
    output = tmp_path / "candidate"
    with pytest.raises(AcquisitionError):
        subject.acquire_cn_a_share_quality_bband_2026_calendar_lineage_source_bounded_v1(
            token=TOKEN,
            endpoint=ENDPOINT,
            output_dir=output,
            proxy_post=transport.proxy_post,
            get=transport.get,
            sleep=lambda _seconds: None,
            clock=Clock(),
        )
    assert not output.exists()


def test_calendar_booleans_and_malformed_neeq_records_are_rejected() -> None:
    calendar = json.loads(calendar_bytes("SSE"))
    calendar["data"]["items"][4][2] = True
    with pytest.raises(AcquisitionError, match="exact rows mismatch"):
        subject._validate_calendar(canonical_bytes(calendar), "SSE", TOKEN)

    malformed = json.loads(neeq_bytes())
    malformed["data"]["data"][1] = None
    with pytest.raises(AcquisitionError, match="record mismatch"):
        subject._parse_neeq(canonical_bytes(malformed))

    wrong_format = json.loads(neeq_bytes())
    wrong_format["data"]["data"][0]["f004v"] = "TXT"
    with pytest.raises(AcquisitionError, match="fact mismatch"):
        subject._parse_neeq(canonical_bytes(wrong_format))


def test_retry_then_success_and_publication_failure_cleanup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    transport = Transport()
    transport.failures = 1
    receipt, output, _transport = acquire(tmp_path, monkeypatch, transport)
    assert receipt["logical_requests"][2]["attempts"] == 2
    assert output.exists()

    second = tmp_path / "second"
    monkeypatch.setattr(subject.os, "rename", lambda _source, _target: (_ for _ in ()).throw(OSError("injected")))
    with pytest.raises(AcquisitionError, match="publication failed"):
        subject.acquire_cn_a_share_quality_bband_2026_calendar_lineage_source_bounded_v1(
            token=TOKEN,
            endpoint=ENDPOINT,
            output_dir=second,
            proxy_post=Transport().proxy_post,
            get=Transport().get,
            sleep=lambda _seconds: None,
            clock=Clock(),
        )
    assert not second.exists()
    assert not (second.parent / f".{second.name}.staging-v1").exists()


def test_invalid_token_existing_output_and_pdf_binding_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subject, "_PDF_BYTE_COUNT", len(PDF) + 1)
    monkeypatch.setattr(subject, "_PDF_SHA256", sha256(PDF))
    output = tmp_path / "candidate"
    with pytest.raises(AcquisitionError):
        subject.acquire_cn_a_share_quality_bband_2026_calendar_lineage_source_bounded_v1(
            token=TOKEN,
            endpoint=ENDPOINT,
            output_dir=output,
            proxy_post=Transport().proxy_post,
            get=Transport().get,
            sleep=lambda _seconds: None,
            clock=Clock(),
        )
    assert not output.exists()
    with pytest.raises(AcquisitionError, match="56-character"):
        subject.acquire_cn_a_share_quality_bband_2026_calendar_lineage_source_bounded_v1(
            token="bad",
            endpoint=ENDPOINT,
            output_dir=output,
            proxy_post=Transport().proxy_post,
            get=Transport().get,
            sleep=lambda _seconds: None,
            clock=Clock(),
        )
