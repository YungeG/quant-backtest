from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest
from crypto_quant_domain import InstrumentId, Money, Scale, UtcInstant, VenueId
from crypto_quant_bundle_builder.tushare_000703_dividend_action_set_v2 import (
    map_tushare_000703_dividend_action_set_v2,
)


ROOT = Path(__file__).resolve().parents[4]
EVIDENCE = ROOT / "evidence/tushare-000703-dividend-authority-v1"
INSTRUMENT = InstrumentId(VenueId("xshe"), "000703")


def _inputs() -> tuple[bytes, bytes]:
    return (
        (EVIDENCE / "acquisition-receipt.json").read_bytes(),
        (EVIDENCE / "response/dividend.json").read_bytes(),
    )


def test_maps_the_three_selected_cash_actions_in_record_date_order() -> None:
    receipt_bytes, raw = _inputs()
    receipt = json.loads(receipt_bytes)
    action_set = map_tushare_000703_dividend_action_set_v2(
        receipt_bytes, raw, INSTRUMENT
    )
    assert action_set.instrument_id == INSTRUMENT
    assert action_set.tushare_dividend_assumed_correct is True
    assert action_set.zero_row_authoritative is True
    assert [action.record_date for action in action_set.actions] == [
        "20240625",
        "20250619",
        "20260612",
    ]
    assert [action.ex_date for action in action_set.actions] == [
        "20240626",
        "20250620",
        "20260615",
    ]
    assert [action.payment_date for action in action_set.actions] == [
        "20240626",
        "20250620",
        "20260615",
    ]
    assert [action.cash_per_share for action in action_set.actions] == [
        Money(10, Scale(2), "CNY"),
        Money(5, Scale(2), "CNY"),
        Money(5, Scale(2), "CNY"),
    ]
    assert len({action.action_id for action in action_set.actions}) == 3
    assert action_set.source_response_sha256 == receipt["provider_request"][
        "response_sha256"
    ]
    assert action_set.source_acquired_at == UtcInstant(receipt["acquired_at_epoch_nanoseconds"])
    assert action_set.source_receipt_sha256 == "sha256:" + hashlib.sha256(receipt_bytes).hexdigest()


@pytest.mark.parametrize("target", ("selection_hash", "cash_tax", "stock_distribution"))
def test_tampered_or_unsupported_selected_action_fails_closed(target: str) -> None:
    receipt_bytes, raw = _inputs()
    receipt = json.loads(receipt_bytes)
    source = json.loads(raw)
    fields = source["data"]["fields"]
    rows = source["data"]["items"]
    index = receipt["action_selection"]["selected_implementation_rows"][0][
        "row_index"
    ]
    if target == "selection_hash":
        forged = json.loads(json.dumps(receipt))
        forged["action_selection"]["selected_implementation_rows"][0][
            "row_sha256"
        ] = "sha256:" + "0" * 64
        with pytest.raises(ValueError, match="row hash"):
            map_tushare_000703_dividend_action_set_v2(
                json.dumps(
                    forged, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                ).encode()
                + b"\n",
                raw,
                INSTRUMENT,
            )
        return
    if target == "cash_tax":
        rows[index][fields.index("cash_div_tax")] = 0.01
    else:
        rows[index][fields.index("stk_div")] = 0.1
    with pytest.raises(ValueError, match="approved action source"):
        map_tushare_000703_dividend_action_set_v2(
            receipt_bytes,
            json.dumps(source, separators=(",", ":")).encode(),
            INSTRUMENT,
        )


def test_mapper_rejects_backdated_receipt_with_unchanged_snapshot() -> None:
    receipt_bytes, raw = _inputs()
    receipt = json.loads(receipt_bytes)
    receipt["acquired_at_epoch_nanoseconds"] -= 1
    receipt["provider_request"]["response_acquired_at_epoch_nanoseconds"] -= 1
    forged = json.dumps(
        receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode() + b"\n"
    with pytest.raises(ValueError, match="snapshot identity mismatch"):
        map_tushare_000703_dividend_action_set_v2(forged, raw, INSTRUMENT)


def test_constructor_rejects_forged_action_set() -> None:
    receipt_bytes, raw = _inputs()
    action_set = map_tushare_000703_dividend_action_set_v2(
        receipt_bytes, raw, INSTRUMENT
    )
    with pytest.raises(ValueError, match="action set identity mismatch"):
        replace(action_set, source_response_sha256="sha256:" + "0" * 64)
    with pytest.raises(ValueError, match="action set identity mismatch"):
        replace(action_set, source_acquired_at=UtcInstant(0))
    with pytest.raises(ValueError, match="action set identity mismatch"):
        replace(action_set, source_receipt_sha256="sha256:" + "0" * 64)


def _bound_empty_inputs(target: str) -> tuple[bytes, bytes]:
    from crypto_quant_bundle_builder.source_snapshots import (
        RawSourceMember, SourceSnapshotProvenance, freeze_source_snapshot,
    )

    receipt_bytes, original_raw = _inputs()
    receipt, source = json.loads(receipt_bytes), json.loads(original_raw)
    source["data"]["items"] = []
    receipt["action_selection"]["selected_implementation_rows"] = []
    receipt["action_selection"]["out_of_scope_implementation_row_count"] = 0
    receipt["provider_request"]["returned_row_count"] = 0
    mutations = {
        "has_more": (source["data"], "has_more", True),
        "count": (source["data"], "count", 1),
        "bool_count": (source["data"], "count", False),
        "code": (source, "code", 1),
        "bool_code": (source, "code", False),
        "row_count": (receipt["provider_request"], "returned_row_count", 1),
        "bool_row_count": (receipt["provider_request"], "returned_row_count", False),
        "fields": (source["data"], "fields", []),
        "envelope": (source, "request_id", ""),
    }
    if target in mutations:
        container, key, value = mutations[target]
        container[key] = value
    elif target.startswith("missing_"):
        key = target.removeprefix("missing_")
        (source if key == "code" else source["data"]).pop(key)
    raw = json.dumps(source, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    acquired = receipt["acquired_at_epoch_nanoseconds"]
    snapshot = freeze_source_snapshot(
        members=(RawSourceMember("response/dividend.json", raw, "0644", acquired, None),),
        provenance=SourceSnapshotProvenance(
            "tushare.pro",
            "tushare.pro.via.xiaodefa.approved-proxy."
            + receipt["transport_endpoint"].removeprefix("https://")
            + ".000703.sz.dividend.authority.v1",
            "tushare.pro.terms", "backtest.acquisition.candidate",
        ),
    ).snapshot
    assert snapshot is not None
    receipt["snapshot"] = snapshot.to_canonical_dict()
    receipt["provider_request"]["response_sha256"] = "sha256:" + hashlib.sha256(raw).hexdigest()
    receipt["provider_request"]["response_byte_count"] = len(raw)
    return json.dumps(receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode() + b"\n", raw


@pytest.mark.parametrize("target", (
    "has_more", "count", "bool_count", "code", "bool_code", "row_count",
    "bool_row_count", "missing_code", "missing_has_more", "missing_count",
    "fields", "envelope",
))
def test_public_mapper_rejects_consistently_bound_invalid_empty_page(target: str) -> None:
    receipt, raw = _bound_empty_inputs(target)
    with pytest.raises(ValueError):
        map_tushare_000703_dividend_action_set_v2(receipt, raw, INSTRUMENT)


def test_public_mapper_accepts_terminal_empty_page() -> None:
    receipt, raw = _bound_empty_inputs("valid")
    assert map_tushare_000703_dividend_action_set_v2(receipt, raw, INSTRUMENT).actions == ()
