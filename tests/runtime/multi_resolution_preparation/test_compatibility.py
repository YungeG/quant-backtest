from __future__ import annotations

import inspect

from crypto_quant_backtest import materialize_execution_input_bundle, materialize_execution_input_bundle_v2


def test_legacy_execution_input_materializers_remain_unchanged() -> None:
    assert str(inspect.signature(materialize_execution_input_bundle)) == "(execution_case: 'ResolvedExecutionCase') -> 'BacktestExecutionInputBundle'"
    assert str(inspect.signature(materialize_execution_input_bundle_v2)) == "(*, resolved_request: 'ResolvedBacktestRequest', execution_case: 'ResolvedExecutionCase') -> 'BacktestExecutionInputBundleV2'"
