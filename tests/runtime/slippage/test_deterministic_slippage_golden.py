from __future__ import annotations

import json
from pathlib import Path

from crypto_quant_domain import OrderSide, canonical_bytes
from tests.runtime.slippage._fixtures import model, request, zero_model


ROOT = Path(__file__).resolve().parents[3]
GOLDEN = ROOT / "tests/fixtures/runtime/deterministic-bps-slippage-v1.json"


def test_deterministic_slippage_matches_canonical_golden() -> None:
    deterministic = model()
    actual = json.loads(
        canonical_bytes(
            {
                "fixture_id": "deterministic-bps-slippage-v1",
                "buy": deterministic.decide_slippage(request(OrderSide.BUY)),
                "sell": deterministic.decide_slippage(request(OrderSide.SELL)),
                "out_of_envelope": deterministic.decide_slippage(
                    request(OrderSide.BUY, state_key="halted")
                ),
                "explicit_zero_development": zero_model().decide_slippage(
                    request(OrderSide.BUY)
                ),
            }
        )
    )
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert actual == expected
