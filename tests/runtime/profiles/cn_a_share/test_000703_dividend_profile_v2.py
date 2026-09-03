from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest
from crypto_quant_bundle_builder.tushare_000703_dividend_action_set_v2 import (
    map_tushare_000703_dividend_action_set_v2,
)
from crypto_quant_domain import InstrumentId, VenueId, canonical_bytes
from crypto_quant_backtest.cn_a_share_dividend_profile_v2 import (
    CnAShareDividendProfileV2,
    compose_tushare_000703_dividend_profile_v2,
)


ROOT = Path(__file__).resolve().parents[4]
EVIDENCE = ROOT / "evidence/tushare-000703-dividend-authority-v1"
INSTRUMENT = InstrumentId(VenueId("xshe"), "000703")


def _action_set_payload() -> dict[str, object]:
    action_set = map_tushare_000703_dividend_action_set_v2(
        (EVIDENCE / "acquisition-receipt.json").read_bytes(),
        (EVIDENCE / "response/dividend.json").read_bytes(),
        INSTRUMENT,
    )
    return json.loads(canonical_bytes(action_set))


def test_profile_v2_maps_the_retained_multi_action_set_without_runtime_quantity() -> None:
    profile = compose_tushare_000703_dividend_profile_v2(
        _action_set_payload(),
        "account:000703-development",
    )
    assert type(profile) is CnAShareDividendProfileV2
    assert profile.instrument_id == INSTRUMENT
    assert profile.simulated_register_policy.account_id == "account:000703-development"
    assert profile.simulated_register_policy.record_close_phase == (100, "corporate_action_record")
    assert [action.record_date for action in profile.actions] == [
        "20240625",
        "20250619",
        "20260612",
    ]
    assert [action.cash_per_share.units for action in profile.actions] == [10, 5, 5]
    assert profile.tushare_dividend_assumed_correct is True
    assert profile.zero_row_authoritative is True
    assert profile.development_only is True
    assert profile.decision_grade_eligible is False
    assert profile.live_eligible is False
    assert profile.deployment_authorized is False
    assert profile.source_manifest == tuple(sorted(profile.source_manifest))


@pytest.mark.parametrize("mutation", ("reorder", "outside", "flag"))
def test_profile_v2_rejects_noncanonical_or_out_of_scope_action_payload(
    mutation: str,
) -> None:
    payload = deepcopy(_action_set_payload())
    if mutation == "reorder":
        payload["actions"] = list(reversed(payload["actions"]))
    elif mutation == "outside":
        payload["actions"][0]["record_date"] = "20230101"
    else:
        payload["development_only"] = False
    with pytest.raises(ValueError):
        compose_tushare_000703_dividend_profile_v2(
            payload,
            "account:000703-development",
        )
