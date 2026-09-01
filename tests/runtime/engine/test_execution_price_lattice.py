from crypto_quant_backtest.engine import _execution_price_on_lattice
from crypto_quant_domain import Price, Scale


def test_raw_execution_reference_is_canonicalized_before_slippage() -> None:
    raw = Price(1_828_000_000, Scale(8), "binance_usdm:koru", "USDT")

    normalized = _execution_price_on_lattice(raw, Scale(2), 1)

    assert normalized == Price(1_828, Scale(2), "binance_usdm:koru", "USDT")
    assert (
        _execution_price_on_lattice(
            Price(1_828_100_000, Scale(8), "binance_usdm:koru", "USDT"),
            Scale(2),
            1,
        )
        is None
    )
