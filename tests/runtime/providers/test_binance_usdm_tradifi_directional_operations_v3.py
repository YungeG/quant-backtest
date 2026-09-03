from __future__ import annotations

import ast
from pathlib import Path

import pytest
from crypto_quant_backtest import (
    BinanceUsdmTradifiDirectionalBacktestOperationsV3,
    BinanceUsdmTradifiProviderInputs,
    PreparedTradifiTrial,
)
from crypto_quant_market_data import (
    EventCursor,
    InMemoryMarketBundleReader,
    LocalMarketBundleReader,
)

from tests.runtime.providers import (
    test_binance_usdm_tradifi_directional_preparation_v3 as directional_fixture,
)
from tests.runtime.providers import (
    test_binance_usdm_tradifi_operations as v1_operations_fixture,
)
from tests.runtime.providers.test_binance_usdm_tradifi_preparation_v2 import _EQUITY
from tests.runtime.resolution._fixtures import build_manifest

_KEYS = ("basilisk", "cobalt", "fennel", "zircon")
_ROOT = Path(__file__).resolve().parents[3]


def _reader_bindings(tmp_path: Path, keys: tuple[str, ...] = _KEYS):
    readers = {}
    artifacts = None
    for key in keys:
        _, overlay, artifacts = directional_fixture._overlay(tmp_path / key, target_key=f"v3.{key}")
        readers[key] = overlay.reader
    assert artifacts is not None
    return readers, artifacts


def _operations(tmp_path: Path, keys: tuple[str, ...] = _KEYS):
    readers, artifacts = _reader_bindings(tmp_path, keys)
    operations = BinanceUsdmTradifiDirectionalBacktestOperationsV3(
        intent_readers=readers,
        provider_inputs=BinanceUsdmTradifiProviderInputs(build_manifest(), _EQUITY),
        artifact_reader=artifacts,
        artifact_publisher=artifacts,
        publication_root=tmp_path / "publication",
    )
    return operations, readers, artifacts


def _direct_reader(reader: LocalMarketBundleReader) -> LocalMarketBundleReader:
    streams = {}
    for stream in reader.manifest.streams:
        cursor = reader.open_cursor(stream.stream_key, batch_size=64)
        assert type(cursor) is EventCursor
        events = []
        while not cursor.exhausted:
            batch, cursor = reader.read_batch(cursor)
            events.extend(batch)
        streams[stream.stream_key] = tuple(events)
    return LocalMarketBundleReader(
        InMemoryMarketBundleReader(
            bundle_ref=reader.bundle_ref,
            manifest=reader.manifest,
            streams=streams,
        )
    )


def test_v3_operations_bind_each_caller_key_to_its_published_reader(
    tmp_path: Path,
) -> None:
    operations, _, _ = _operations(tmp_path)

    prepared = {
        key: operations.prepare({"intent_key": key}, f"reserved:{key}")
        for key in _KEYS
    }

    assert all(type(trial) is PreparedTradifiTrial for trial in prepared.values())
    assert {
        trial._execution.execution_request.request.experiment_id
        for trial in prepared.values()
    } == {f"reserved:{key}" for key in _KEYS}
    assert len(
        {
            trial._execution.execution_request.request.target_stream_digest
            for trial in prepared.values()
        }
    ) == len(_KEYS)


def test_v3_operations_accept_exact_repository_open_readers_and_reject_direct_ones(
    tmp_path: Path,
) -> None:
    readers, artifacts = _reader_bindings(tmp_path, (_KEYS[0],))
    reader = readers[_KEYS[0]]
    direct = _direct_reader(reader)
    inputs = BinanceUsdmTradifiProviderInputs(build_manifest(), _EQUITY)

    assert direct.bundle_ref == reader.bundle_ref
    assert direct.manifest == reader.manifest
    assert isinstance(
        BinanceUsdmTradifiDirectionalBacktestOperationsV3(
            intent_readers={_KEYS[0]: reader},
            provider_inputs=inputs,
            artifact_reader=artifacts,
            artifact_publisher=artifacts,
            publication_root=tmp_path / "repository-open",
        ),
        BinanceUsdmTradifiDirectionalBacktestOperationsV3,
    )
    direct_operations = BinanceUsdmTradifiDirectionalBacktestOperationsV3(
        intent_readers={_KEYS[0]: direct},
        provider_inputs=inputs,
        artifact_reader=artifacts,
        artifact_publisher=artifacts,
        publication_root=tmp_path / "direct",
    )
    with pytest.raises(ValueError, match="repository-open"):
        direct_operations.prepare({"intent_key": _KEYS[0]}, "direct-reader")


def test_v3_operations_reject_cross_key_malformed_and_v1_reader_bindings(
    tmp_path: Path,
) -> None:
    operations, readers, artifacts = _operations(tmp_path, (_KEYS[0],))
    with pytest.raises(KeyError, match="unknown intent_key"):
        operations.prepare({"intent_key": "unknown"}, "reserved:unknown")
    with pytest.raises((TypeError, ValueError)):
        operations.prepare({"intent_key": " basilisk"}, "reserved:bad")
    unvalidated_operations = BinanceUsdmTradifiDirectionalBacktestOperationsV3(
        intent_readers={"bad": object()},  # type: ignore[dict-item]
        provider_inputs=BinanceUsdmTradifiProviderInputs(build_manifest(), _EQUITY),
        artifact_reader=artifacts,
        artifact_publisher=artifacts,
        publication_root=tmp_path / "bad-reader",
    )
    with pytest.raises(ValueError, match="repository-open"):
        unvalidated_operations.prepare({"intent_key": "bad"}, "bad-reader")

    v1_reader = v1_operations_fixture._local_reader(
        tmp_path / "v1-market", v1_operations_fixture.fixture._nonempty_bundle()
    )
    v1_operations = BinanceUsdmTradifiDirectionalBacktestOperationsV3(
        intent_readers={"v1": v1_reader},
        provider_inputs=BinanceUsdmTradifiProviderInputs(build_manifest(), _EQUITY),
        artifact_reader=artifacts,
        artifact_publisher=artifacts,
        publication_root=tmp_path / "v1-publication",
    )
    with pytest.raises(RuntimeError, match="preparation_authority_invalid"):
        v1_operations.prepare({"intent_key": "v1"}, "v1-reader")

    assert set(readers) == {_KEYS[0]}


def test_v3_operations_run_registered_handle_once_and_keep_ownership(
    tmp_path: Path,
) -> None:
    operations, readers, artifacts = _operations(tmp_path, (_KEYS[0],))
    prepared = operations.prepare({"intent_key": _KEYS[0]}, "reserved:one-shot")
    other = BinanceUsdmTradifiDirectionalBacktestOperationsV3(
        intent_readers={_KEYS[0]: readers[_KEYS[0]]},
        provider_inputs=BinanceUsdmTradifiProviderInputs(build_manifest(), _EQUITY),
        artifact_reader=artifacts,
        artifact_publisher=artifacts,
        publication_root=tmp_path / "other-publication",
    )

    with pytest.raises(TypeError, match="owned"):
        other.run_prepared(prepared)
    publication = operations.run_prepared(prepared)
    attempts = tuple((tmp_path / "publication").rglob("attempt-execution-record.json"))
    with pytest.raises(RuntimeError, match="already run"):
        operations.run_prepared(prepared)

    assert publication["type"] == "backtest_canonical_publication_ref"
    assert attempts
    assert tuple((tmp_path / "publication").rglob("attempt-execution-record.json")) == attempts


def test_v3_operations_and_directional_request_are_public_without_builder_imports() -> None:
    from crypto_quant_backtest import BinanceUsdmTradifiDirectionalRequestIntentV3

    assert BinanceUsdmTradifiDirectionalBacktestOperationsV3.__name__.endswith("V3")
    assert BinanceUsdmTradifiDirectionalRequestIntentV3.__name__.endswith("V3")
    for name in (
        "binance_usdm_tradifi_operations.py",
        "binance_usdm_tradifi_directional_preparation.py",
    ):
        tree = ast.parse(
            (_ROOT / "packages/backtest-runtime/src/crypto_quant_backtest" / name).read_text(),
            filename=name,
        )
        imported = {
            module
            for node in ast.walk(tree)
            for module in (
                [alias.name for alias in node.names]
                if isinstance(node, ast.Import)
                else [node.module]
                if isinstance(node, ast.ImportFrom) and node.module is not None
                else []
            )
        }
        assert not any(
            module.startswith(("crypto_quant_bundle_builder", "crypto_quant_research"))
            for module in imported
        )
