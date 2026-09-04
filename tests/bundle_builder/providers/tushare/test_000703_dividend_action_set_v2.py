from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import pytest
from crypto_quant_domain import InstrumentId, Money, Scale, VenueId
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


def test_constructor_rejects_forged_action_set() -> None:
    receipt_bytes, raw = _inputs()
    action_set = map_tushare_000703_dividend_action_set_v2(
        receipt_bytes, raw, INSTRUMENT
    )
    with pytest.raises(ValueError, match="action set identity mismatch"):
        replace(action_set, source_response_sha256="sha256:" + "0" * 64)
