from __future__ import annotations

import json
from pathlib import Path

from crypto_quant_backtest import FullFillBuilder, FullFillResult
from crypto_quant_domain import canonical_bytes, canonical_sha256
from tests.runtime.execution._fixtures import (
    candidate,
    fill_id,
    model,
    request,
    slippage_model,
    slippage_request,
)


ROOT = Path(__file__).resolve().parents[3]
GOLDEN = ROOT / "tests/fixtures/runtime/next-eligible-bar-open-v1.json"


def test_next_eligible_bar_open_matches_canonical_golden() -> None:
    execution = model()
    eligible = execution.simulate_execution(request(bar_candidate=candidate()))
    assert eligible.result is not None
    slippage = slippage_model(eligible.result).decide_slippage(
        slippage_request(eligible.result)
    )
    full_fill = FullFillBuilder().build(
        decision=eligible.result,
        slippage_outcome=slippage,
        fill_id=fill_id(),
    )
    gap = execution.simulate_execution(
        request(bar_candidate=candidate(kind="gap_placeholder"))
    )
    forward = execution.simulate_execution(
        request(bar_candidate=candidate(kind="forward_filled"))
    )
    blocked = execution.simulate_execution(
        request(
            bar_candidate=candidate(
                liquidity_approved=False,
                reason_code="liquidity_blocked_at_limit",
            ),
            eligibility_window_exhausted=True,
        )
    )
    expired = execution.simulate_execution(
        request(bar_candidate=None, eligibility_window_exhausted=True)
    )
    assert isinstance(full_fill, FullFillResult)
    assert gap.result is not None
    assert gap.result.ineligibility_reason is not None
    assert forward.result is not None
    assert forward.result.ineligibility_reason is not None
    assert blocked.result is not None
    assert blocked.result.ineligibility_reason is not None
    assert expired.result is not None
    assert expired.result.ineligibility_reason is not None
    actual = json.loads(
        canonical_bytes(
            {
                "fixture_id": "next-eligible-bar-open-v1",
                "component_spec_hash": canonical_sha256(execution.spec()),
                "eligible": {
                    "input_hash": eligible.input_hash,
                    "decision_id": eligible.result.decision_id,
                    "decision_hash": canonical_sha256(eligible.result),
                    "reference_price": eligible.result.reference_price,
                    "fill_quantity": eligible.result.fill_quantity,
                },
                "full_fill": {
                    "result_hash": full_fill.result_hash,
                    "fill": full_fill.fill,
                },
                "gap_placeholder": {
                    "decision_id": gap.result.decision_id,
                    "action": gap.result.action.value,
                    "reason": gap.result.ineligibility_reason.value,
                },
                "forward_filled": {
                    "decision_id": forward.result.decision_id,
                    "action": forward.result.action.value,
                    "reason": forward.result.ineligibility_reason.value,
                },
                "liquidity_blocked": {
                    "decision_id": blocked.result.decision_id,
                    "action": blocked.result.action.value,
                    "reason": blocked.result.ineligibility_reason.value,
                },
                "no_bar_expired": {
                    "decision_id": expired.result.decision_id,
                    "action": expired.result.action.value,
                    "reason": expired.result.ineligibility_reason.value,
                },
            }
        )
    )
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert actual == expected
