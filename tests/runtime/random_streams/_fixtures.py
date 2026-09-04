from __future__ import annotations

from crypto_quant_backtest import NamedRandomStream
from crypto_quant_domain import StrategySleeveId


STRATEGY_ID = StrategySleeveId("portfolio.momentum")


def stream(
    *,
    master_random_seed: int = 42,
    strategy_id: StrategySleeveId = STRATEGY_ID,
    stream_key: str = "signal-selection",
    counter: int = 0,
) -> NamedRandomStream:
    return NamedRandomStream(
        master_random_seed=master_random_seed,
        strategy_id=strategy_id,
        stream_key=stream_key,
        algorithm="sha256-counter",
        algorithm_version=1,
        counter=counter,
    )
