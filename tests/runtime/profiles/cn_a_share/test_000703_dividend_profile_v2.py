from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest
from crypto_quant_bundle_builder.tushare_000703_dividend_action_set_v2 import (
    map_tushare_000703_dividend_action_set_v2,
)
from crypto_quant_domain import InstrumentId, UtcInstant, VenueId, canonical_bytes, canonical_sha256
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
        source_receipt_bytes=(EVIDENCE / "acquisition-receipt.json").read_bytes(),
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
    receipt = (EVIDENCE / "acquisition-receipt.json").read_bytes()
    assert profile.source_acquired_at == UtcInstant(json.loads(receipt)["acquired_at_epoch_nanoseconds"])
    assert profile.source_receipt_sha256 == "sha256:" + hashlib.sha256(receipt).hexdigest()
    assert profile.source_receipt_sha256 in profile.source_manifest


def test_rehashed_profile_cannot_backdate_the_same_source_action_set() -> None:
    profile = compose_tushare_000703_dividend_profile_v2(
        _action_set_payload(), "account:000703-development",
        source_receipt_bytes=(EVIDENCE / "acquisition-receipt.json").read_bytes(),
    )
    body = profile.to_canonical_dict()
    body.pop("profile_hash")
    body["source_acquired_at"] = UtcInstant(0)
    with pytest.raises(ValueError, match="receipt"):
        replace(profile, source_acquired_at=UtcInstant(0), profile_hash=canonical_sha256(body))


def test_profile_rejects_rehashed_acquisition_time_against_the_same_receipt() -> None:
    payload = _action_set_payload()
    payload["source_acquired_at"] = UtcInstant(0).to_canonical_dict()
    payload.pop("action_set_hash")
    payload["action_set_hash"] = canonical_sha256(payload)
    with pytest.raises(ValueError, match="receipt"):
        compose_tushare_000703_dividend_profile_v2(
            payload, "account:000703-development",
            source_receipt_bytes=(EVIDENCE / "acquisition-receipt.json").read_bytes(),
        )


@pytest.mark.parametrize("field_name", ("source_acquired_at", "source_receipt_sha256"))
def test_profile_requires_hash_bound_source_provenance(field_name: str) -> None:
    payload = _action_set_payload()
    payload.pop(field_name)
    with pytest.raises(ValueError, match="canonical shape"):
        compose_tushare_000703_dividend_profile_v2(
            payload, "account:000703-development",
            source_receipt_bytes=(EVIDENCE / "acquisition-receipt.json").read_bytes(),
        )


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
            source_receipt_bytes=(EVIDENCE / "acquisition-receipt.json").read_bytes(),
        )
