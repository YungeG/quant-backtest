from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path

import pytest
from crypto_quant_backtest import (
    BinanceUsdmKoruPremiumBacktestOperationsV1,
    BinanceUsdmTradifiProviderInputs,
)
from crypto_quant_bundle_builder import build_koru_premium_reader_set_v1
from crypto_quant_market_data import (
    EventCursor,
    InMemoryMarketBundleReader,
    LocalMarketBundleReader,
)

from tests.bundle_builder.providers.binance_usdm import (
    test_koru_premium_reader_set_v1 as reader_set_fixture,
)
from tests.runtime.providers.test_binance_usdm_tradifi_preparation_v2 import _EQUITY
from tests.runtime.resolution._fixtures import build_manifest

_ROOT = Path(__file__).resolve().parents[3]


def _operations(reader_set, store, publication_root: Path) -> BinanceUsdmKoruPremiumBacktestOperationsV1:
    return BinanceUsdmKoruPremiumBacktestOperationsV1(
        reader_set=reader_set,
        provider_inputs=BinanceUsdmTradifiProviderInputs(build_manifest(), _EQUITY),
        artifact_reader=store,
        artifact_publisher=store,
        publication_root=publication_root,
    )


def _direct_reader(reader: LocalMarketBundleReader) -> LocalMarketBundleReader:
    streams = {}
    for stream in reader.manifest.streams:
        cursor = reader.open_cursor(stream.stream_key, batch_size=64)
        assert type(cursor) is EventCursor
        values = []
        while not cursor.exhausted:
            batch, cursor = reader.read_batch(cursor)
            values.extend(batch)
        streams[stream.stream_key] = tuple(values)
    return LocalMarketBundleReader(InMemoryMarketBundleReader(reader.bundle_ref, reader.manifest, streams))


def test_prm_01_prepares_runs_and_loads_while_prm_02_cannot_be_substituted(tmp_path: Path) -> None:
    request = reader_set_fixture._request(tmp_path)
    built = build_koru_premium_reader_set_v1(request)
    assert built.result is not None
    operations = _operations(
        built.result, request.economics_bundle.request.artifact_store, tmp_path / "publication"
    )

    prepared = operations.prepare({"intent_key": "KORU-PRM-01"}, "reserved:prm-01")
    completed = operations.run_prepared(prepared)
    assert operations.load_completed(completed)["semantic_run_id"]

    swapped = replace(
        built.result.bindings[1], reader=built.result.bindings[0].reader
    )
    replaced = replace(built.result, bindings=(built.result.bindings[0], swapped, *built.result.bindings[2:]))
    blocked = _operations(
        replaced, request.economics_bundle.request.artifact_store, tmp_path / "blocked"
    )
    with pytest.raises(ValueError, match="premium reader binding"):
        blocked.prepare({"intent_key": "KORU-PRM-02"}, "reserved:prm-02")


def test_prm_01_rejects_coherent_prm_02_overlay_substitution(tmp_path: Path) -> None:
    request = reader_set_fixture._request(tmp_path)
    built = build_koru_premium_reader_set_v1(request)
    assert built.result is not None
    prm_01, prm_02, *rest = built.result.bindings
    swapped = replace(
        prm_01,
        reader=prm_02.reader,
        overlay_bundle_ref=prm_02.overlay_bundle_ref,
        overlay_bundle_digest=prm_02.overlay_bundle_digest,
    )
    replaced = replace(built.result, bindings=(swapped, prm_02, *rest))

    with pytest.raises(ValueError, match="premium overlay binding"):
        _operations(
            replaced,
            request.economics_bundle.request.artifact_store,
            tmp_path / "coherent-swap",
        ).prepare({"intent_key": "KORU-PRM-01"}, "reserved:coherent-swap")


def test_premium_operations_reject_non_prm_and_direct_reader_before_preparation(tmp_path: Path) -> None:
    request = reader_set_fixture._request(tmp_path)
    outcome = build_koru_premium_reader_set_v1(request)
    assert outcome.result is not None
    reader_set = outcome.result
    store = request.economics_bundle.request.artifact_store
    with pytest.raises(KeyError, match="unknown intent_key"):
        _operations(reader_set, store, tmp_path / "bad").prepare({"intent_key": "KORU-PRM-99"}, "reserved:bad")

    direct = _direct_reader(reader_set.reader_for("KORU-PRM-01"))
    broken = replace(reader_set, bindings=(replace(reader_set.bindings[0], reader=direct), *reader_set.bindings[1:]))
    with pytest.raises(ValueError, match="repository-open"):
        _operations(broken, store, tmp_path / "direct").prepare({"intent_key": "KORU-PRM-01"}, "reserved:direct")


def test_premium_operations_preserve_v1_v2_v3_imports_without_builder_import() -> None:
    from crypto_quant_backtest import (
        BinanceUsdmKoruPremiumBacktestOperationsV1 as PublicOperations,
    )
    from crypto_quant_backtest import (
        BinanceUsdmTradifiBacktestOperations,
        BinanceUsdmTradifiDirectionalBacktestOperationsV3,
    )
    from crypto_quant_bundle_builder import (
        BinanceUsdmKoruTradifiExecutionBundleResultV2,
    )
    from crypto_quant_market_data import KoruPremiumReaderSetV1

    assert PublicOperations is BinanceUsdmKoruPremiumBacktestOperationsV1
    assert BinanceUsdmTradifiBacktestOperations.__name__.endswith("Operations")
    assert BinanceUsdmTradifiDirectionalBacktestOperationsV3.__name__.endswith("V3")
    assert BinanceUsdmKoruTradifiExecutionBundleResultV2.__name__.endswith("V2")
    assert KoruPremiumReaderSetV1.__module__.startswith("crypto_quant_market_data")
    source = (_ROOT / "packages/backtest-runtime/src/crypto_quant_backtest/binance_usdm_tradifi_operations.py").read_text()
    assert not any(alias.name.startswith("crypto_quant_bundle_builder") for alias in ast.walk(ast.parse(source)) if isinstance(alias, ast.alias))
