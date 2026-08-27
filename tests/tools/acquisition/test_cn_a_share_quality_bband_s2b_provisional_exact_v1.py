from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest
from crypto_quant_bundle_builder import (
    RawSourceMember,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
)

import tools.acquisition.cn_a_share_quality_bband_s2b_provisional_exact_v1 as s2b


def _raw(fields: tuple[str, ...], rows: list[list[object]]) -> bytes:
    return json.dumps(
        {
            "request_id": "fixture",
            "code": 0,
            "data": {"fields": list(fields), "items": rows, "has_more": False, "count": 0},
            "msg": None,
            "detail": None,
        },
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def _loaded(members: dict[str, bytes], receipt: dict[str, object] | None = None):
    outcome = freeze_source_snapshot(
        members=tuple(
            RawSourceMember(key, value, "0644", index + 1, None)
            for index, (key, value) in enumerate(sorted(members.items()))
        ),
        provenance=SourceSnapshotProvenance(
            vendor_key="fixture.vendor",
            source_key="fixture.source",
            license_ref="fixture.license",
            retention_policy_ref="fixture.retention",
        ),
    )
    assert outcome.snapshot is not None
    return s2b._LoadedSourceRoot(
        Path("/fixture"),
        outcome.snapshot,
        outcome.snapshot.to_canonical_dict(),
        receipt or {},
        members,
    )


def _s0_row(code: str, *, market: str = "主板") -> list[object]:
    values = {field: None for field in s2b._FIELDS["s0"]}
    values.update(
        ts_code=code,
        symbol=code[:6],
        name="fixture",
        market=market,
        exchange="SZSE" if code.endswith("SZ") else "SSE",
        curr_type="CNY",
        list_status="L",
        list_date="20100101",
    )
    return [values[field] for field in s2b._FIELDS["s0"]]


def _roster_row(code: str, *, industry: object = None, list_date: str = "20100101") -> list[object]:
    values = {
        "trade_date": "20170502",
        "ts_code": code,
        "name": "fixture",
        "industry": industry,
        "list_date": list_date,
    }
    return [values[field] for field in s2b._FIELDS["annual_roster"]]


def _statement_row(api_name: str, code: str, period: str, revision: str) -> list[object]:
    values = {field: None for field in s2b._FIELDS[api_name]}
    values.update(ts_code=code, end_date=period, update_flag=revision)
    return [values[field] for field in s2b._FIELDS[api_name]]


def test_strict_json_rejects_duplicate_keys_and_nonfinite_values() -> None:
    with pytest.raises(ValueError, match="strict JSON"):
        s2b._strict_json(b'{"x":1,"x":2}')
    with pytest.raises(ValueError, match="strict JSON"):
        s2b._strict_json(b'{"x":NaN}')
    with pytest.raises(ValueError, match="strict JSON"):
        s2b._strict_json(b'{"x":1e999}')


def test_canonical_instrument_is_exact_sh_sz_only() -> None:
    assert s2b._canonical_instrument("000001.SZ") == {
        "type": "instrument_id",
        "venue": "xshe",
        "stable_key": "000001",
    }
    assert s2b._canonical_instrument("600000.SH")["venue"] == "xshg"
    for value in ("430001.BJ", "600000.sh", "xshg:600000"):
        with pytest.raises(s2b.QualityBbandS2bProvisionalExactExtractionError) as raised:
            s2b._canonical_instrument(value)
        assert raised.value.code is s2b.QualityBbandS2bProvisionalExactExtractionFailure.CATALOG_IDENTITY_MISMATCH


def test_tiny_expected_set_preserves_screen_pair_key_order_and_false_authority() -> None:
    s0 = _loaded(
        {
            "response/tushare/stock_basic/listed-v1.json": _raw(
                s2b._FIELDS["s0"],
                [_s0_row("600001.SH"), _s0_row("000001.SZ"), _s0_row("300001.SZ", market="创业板")],
            )
        }
    )
    roster = _loaded(
        {
            "response/tushare/bak_basic/20160503-v1.json": _raw(s2b._FIELDS["annual_roster"], []),
            "response/tushare/bak_basic/20170502-v1.json": _raw(
                s2b._FIELDS["annual_roster"],
                [
                    _roster_row("600001.SH", industry=None),
                    _roster_row("000001.SZ", industry="制造业"),
                    _roster_row("300001.SZ"),
                    _roster_row("600002.SH", industry="银行"),
                ],
            ),
        }
    )
    expected, keys, provider_keys = s2b._derive_provisional_expected_set(s0, roster)
    instruments = expected["screens"][0]["instrument_ids"]
    assert [(value["venue"], value["stable_key"]) for value in instruments] == [
        ("xshe", "000001"),
        ("xshg", "600001"),
    ]
    assert expected["expected_pair_count"] == 10
    assert expected["expected_member_count"] == len(keys) == len(provider_keys) == 30
    assert expected["formal_s1_qualified"] is False
    assert expected["derivation"]["null_or_other_roster_industry_policy"] == "RETAIN"


def test_terminal_only_scan_retains_both_child_revisions_and_excludes_parent() -> None:
    api_name = "income_vip"
    fields = s2b._FIELDS[api_name]
    parent = "response/parent.json"
    child_a = "response/child-a.json"
    child_b = "response/child-b.json"
    loaded = _loaded(
        {
            parent: _raw(fields, [_statement_row(api_name, "000001.SZ", "20161231", "P")]),
            child_a: _raw(fields, [_statement_row(api_name, "000001.SZ", "20161231", "0")]),
            child_b: _raw(fields, [_statement_row(api_name, "000001.SZ", "20161231", "1")]),
        },
        {
            "request": {"field_sets": {api_name: list(fields)}},
            "root_trees": [
                {
                    "api_name": api_name,
                    "period": "20161231",
                    "terminal_leaf_member_keys": [child_a, child_b],
                }
            ],
            "provider_requests": [
                {"terminal": False, "returned_row_count": 1},
                {"terminal": True, "returned_row_count": 1},
                {"terminal": True, "returned_row_count": 1},
            ],
        },
    )
    output, keys, details = s2b._extract_terminal_provider_rows(
        loaded, {(api_name, "000001.SZ", "20161231")}
    )
    records = [json.loads(line) for line in output.splitlines()]
    assert len(records) == 2
    assert {record["source_member_key"] for record in records} == {child_a, child_b}
    assert len({record["source_row_id"] for record in records}) == 2
    assert keys == {(api_name, "xshe", "000001", "20161231")}
    accounting = details["accounting"]
    assert accounting["terminal_leaf_page_count"] == 2
    assert accounting["nonterminal_parent_page_count"] == 1
    assert accounting["provider_revision_surplus_row_count"] == 1


def test_bounded_member_read_rejects_escape_nonregular_and_oversize(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    member = root / "member.bin"
    member.write_bytes(b"abc")
    files = {"member.bin"}
    assert s2b._read_root_member(root, "member.bin", files, maximum_bytes=3) == b"abc"
    for key in ("../outside.bin", "/tmp/outside.bin"):
        with pytest.raises(ValueError, match="unsafe source member"):
            s2b._read_root_member(root, key, files, maximum_bytes=3)
    member.write_bytes(b"abcd")
    with pytest.raises(ValueError, match="unsafe source member"):
        s2b._read_root_member(root, "member.bin", files, maximum_bytes=3)
    member.unlink()
    member.mkdir()
    with pytest.raises(ValueError, match="unsafe source member"):
        s2b._read_root_member(root, "member.bin", files, maximum_bytes=3)


def test_load_source_root_uses_exact_bounded_member_reads(tmp_path: Path) -> None:
    member_key = "response/member.json"
    loaded = _loaded({member_key: b"abc"})
    root = tmp_path / "source"
    path = root / member_key
    path.parent.mkdir(parents=True)
    path.write_bytes(b"abc")
    snapshot_raw = s2b._canonical_json(loaded.snapshot_metadata).encode()
    receipt_raw = b"{}"
    (root / "source-snapshot.json").write_bytes(snapshot_raw)
    (root / "acquisition-receipt.json").write_bytes(receipt_raw)
    identity = s2b._FrozenSourceIdentity(
        loaded.snapshot.snapshot_id,
        loaded.snapshot.content_tree_hash,
        loaded.snapshot.provenance_hash,
        s2b._bytes_hash(snapshot_raw),
        s2b._bytes_hash(receipt_raw),
        3,
    )
    assert s2b._load_source_root(root, identity).member_bytes[member_key] == b"abc"
    path.write_bytes(b"abcd")
    with pytest.raises(s2b.QualityBbandS2bProvisionalExactExtractionError) as raised:
        s2b._load_source_root(root, identity)
    assert raised.value.code is s2b.QualityBbandS2bProvisionalExactExtractionFailure.SOURCE_MEMBER_CONFLICT


def test_exact_closure_rejects_overlap_and_missing() -> None:
    key = ("income_vip", "xshe", "000001", "20161231")
    with pytest.raises(s2b.QualityBbandS2bProvisionalExactExtractionError) as overlap:
        s2b._validate_exact_closure({key}, {key}, {key}, set())
    assert overlap.value.code is s2b.QualityBbandS2bProvisionalExactExtractionFailure.BUNDLE_EXACT_COVER_MISMATCH
    with pytest.raises(s2b.QualityBbandS2bProvisionalExactExtractionError) as missing:
        s2b._validate_exact_closure({key}, set(), set(), set())
    assert missing.value.reason == "EXPECTED_MEMBER_MISSING"


def test_nonfiling_source_validation_precedes_official_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _loaded({"fixture.json": b"{}"})
    monkeypatch.setattr(s2b, "_preflight", lambda _roots, _output: None)
    monkeypatch.setattr(s2b, "_load_source_root", lambda _root, _identity: source)
    called = {"official": False}

    def corrupt(_root: Path) -> None:
        raise s2b.QualityBbandS2bProvisionalExactExtractionError(
            s2b.QualityBbandS2bProvisionalExactExtractionFailure.SOURCE_MEMBER_CONFLICT
        )

    def official(_source: object):
        called["official"] = True
        raise AssertionError("official builder must not run")

    monkeypatch.setattr(s2b, "_validate_nonfiling_source_files", corrupt)
    monkeypatch.setattr(s2b, "_build_pan_hai_o", official)
    with pytest.raises(s2b.QualityBbandS2bProvisionalExactExtractionError) as raised:
        s2b.extract_quality_bband_s2b_provisional_exact_v1(
            s0_root=tmp_path / "s0",
            annual_roster_root=tmp_path / "annual",
            s2a_root=tmp_path / "s2a",
            official_remediation_root=tmp_path / "official",
            nonfiling_publication_root=tmp_path / "nonfiling",
            output_dir=tmp_path / "output",
        )
    assert raised.value.code is s2b.QualityBbandS2bProvisionalExactExtractionFailure.SOURCE_MEMBER_CONFLICT
    assert called["official"] is False


def test_atomic_publication_sets_modes_is_no_clobber_and_writes_manifest_last(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "candidate"
    published = {
        "provisional-expected-set.json": b"a",
        "provider-rows.jsonl": b"b",
        "official-coverage.json": b"c",
        "extraction-manifest.json": b"d",
    }
    monkeypatch.setattr(
        s2b,
        "_EXPECTED_OUTPUTS",
        {name: (len(value), s2b._bytes_hash(value)) for name, value in published.items()},
    )
    opened: list[str] = []
    real_open = s2b.os.open

    def recording_open(path: object, flags: int, mode: int = 0o777) -> int:
        if isinstance(path, Path) and path.name in published:
            opened.append(path.name)
        return real_open(path, flags, mode)

    monkeypatch.setattr(s2b.os, "open", recording_open)
    s2b._atomic_publish(output, published)
    assert stat.S_IMODE(output.stat().st_mode) == 0o700
    assert {path.name for path in output.iterdir()} == set(published)
    assert opened == list(published)
    assert all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in output.iterdir())
    with pytest.raises(s2b.QualityBbandS2bProvisionalExactExtractionError) as raised:
        s2b._atomic_publish(output, published)
    assert raised.value.code is s2b.QualityBbandS2bProvisionalExactExtractionFailure.PUBLICATION_INTEGRITY_FAILURE


def test_atomic_publication_race_does_not_replace_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "candidate"
    published = {
        "provisional-expected-set.json": b"a",
        "provider-rows.jsonl": b"b",
        "official-coverage.json": b"c",
        "extraction-manifest.json": b"d",
    }
    monkeypatch.setattr(
        s2b,
        "_EXPECTED_OUTPUTS",
        {name: (len(value), s2b._bytes_hash(value)) for name, value in published.items()},
    )
    real_rename = s2b._rename_noreplace

    def racing_rename(source: Path, target: Path) -> None:
        target.mkdir()
        real_rename(source, target)

    monkeypatch.setattr(s2b, "_rename_noreplace", racing_rename)
    with pytest.raises(s2b.QualityBbandS2bProvisionalExactExtractionError):
        s2b._atomic_publish(output, published)
    assert output.is_dir() and not any(output.iterdir())
    assert not any(path.name.startswith(f".{output.name}.staging-") for path in tmp_path.iterdir())


_REAL_ROOT = Path("/srv/bcache-8t/ygguo/quant/artifacts/a-share-quality-bband")
_REAL_PATHS = {
    "s0_root": _REAL_ROOT / "s0-lightweight-source-snapshots/stock-basic/20260826/v1-candidate-01",
    "annual_roster_root": _REAL_ROOT / "annual-structural-roster-source-snapshots/2016-2025/20260826/v1-candidate-01",
    "s2a_root": _REAL_ROOT / "s2a-vip-financial-source-snapshots/2012-2024/20260826/v1-candidate-02",
    "official_remediation_root": _REAL_ROOT / "official-s2-remediation-source-snapshots/eight-issuer/20260826/v1-candidate-01",
    "nonfiling_publication_root": _REAL_ROOT / "official-annual-nonfiling-declarations/seven-issuer/20260827/v1-candidate-01",
}


@pytest.mark.skipif(
    os.environ.get("QB_S2B_REAL_ARTIFACT_SENTINEL") != "1"
    or not all(path.is_dir() for path in _REAL_PATHS.values()),
    reason="real accepted S2B inputs are unavailable or sentinel is not enabled",
)
def test_real_artifacts_reproduce_four_frozen_outputs(tmp_path: Path) -> None:
    output = tmp_path / "real-extraction"
    manifest = s2b.extract_quality_bband_s2b_provisional_exact_v1(
        **_REAL_PATHS,
        output_dir=output,
    )
    assert manifest["manifest_id"] == s2b._EXPECTED_IDS["manifest"]
    assert manifest["accounting"]["expected_member_count"] == 96537
    assert manifest["accounting"]["provider_member_count"] == 96515
    assert manifest["accounting"]["official_filing_member_count"] == 1
    assert manifest["accounting"]["official_nonfiling_member_count"] == 21
    for name, (byte_count, digest) in s2b._EXPECTED_OUTPUTS.items():
        raw = (output / name).read_bytes()
        assert (len(raw), s2b._bytes_hash(raw)) == (byte_count, digest)
