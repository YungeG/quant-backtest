from __future__ import annotations

from pathlib import Path

from crypto_quant_backtest import (
    AttemptIdentity,
    AuditableBacktestRunner,
    DeterministicBarEngine,
    InputOrigin,
)
from tests.runtime.profiles.binance_usdm._fixtures import composition_request
from tests.support.binance_usdm import (
    BinanceUsdmDevelopmentFinancialDispatcher,
    build_binance_usdm_execution_case,
    build_binance_usdm_resolved_request,
)


def test_binance_usdm_runner_preserves_development_only_repeatability(
    tmp_path: Path,
) -> None:
    request = composition_request()
    resolved = build_binance_usdm_resolved_request(request)
    case = build_binance_usdm_execution_case(request, resolved_request=resolved)
    first = AttemptIdentity.first(resolved.semantic_run_id)
    second = AttemptIdentity.retry(first, next_ordinal=2)
    records = tuple(
        AuditableBacktestRunner(
            engine=DeterministicBarEngine(
                BinanceUsdmDevelopmentFinancialDispatcher(request)
            ),
            publication_root=tmp_path / f"attempt-{index}",
        ).execute(
            resolved_request=resolved,
            execution_case=case,
            attempt=attempt,
            input_origin=InputOrigin.PRECOMPUTED_TARGET_STREAM,
        )
        for index, attempt in enumerate((first, second), start=1)
    )

    ready = tuple(record.ready_to_finalize for record in records)
    if any(value is None for value in ready):
        raise AssertionError("Binance USD-M Runner did not reach ready-to-finalize")
    result_hashes = tuple(
        value.engine_result.result_hash for value in ready if value is not None
    )
    assert len(result_hashes) == 2
    assert len(set(result_hashes)) == 1
    assert not resolved.environment.deployment_authorized
