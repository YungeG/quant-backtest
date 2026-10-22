"""Cold source-preflight replay; test byte storage is NOT a production CAS/owner log."""
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from crypto_quant_backtest import BacktestTargetStreamError
from crypto_quant_backtest.cn_a_share_portfolio_case_inputs_v8 import (
    read_retained_cn_a_share_portfolio_case_input_v8,
    retain_cn_a_share_portfolio_case_input_v8,
)
from crypto_quant_backtest.cn_a_share_portfolio_preparation_inputs_v1 import (
    CnASharePortfolioSourceAdmissionBlockedV1,
    require_cn_a_share_portfolio_source_qualification_v1,
)
from crypto_quant_backtest.cn_a_share_portfolio_source_bundle_draft_v0 import (
    read_cn_a_share_portfolio_source_bundle_draft_v0,
)
from crypto_quant_bundle_builder import LocalMarketBundleRepository, LocalMarketBundleRepositoryConfig
from crypto_quant_domain import (
    ArtifactEnvelope, ArtifactIntegrityError, ArtifactNotFoundError, ArtifactReadResult,
    ArtifactRef, ArtifactSchemaRegistration, SchemaCatalog, canonical_bytes,
)
from crypto_quant_market_data import LocalMarketBundleReader, MarketBundleRef
from tests.runtime.providers.test_cn_a_share_portfolio_source_bundle_draft_v0 import (
    _BUNDLE, _COMPONENT, _CODES, _gate_bundle, _ref,
)


class _DiskArtifacts:
    """Test-only path adapter: native SchemaCatalog validates every fresh byte read."""

    def __init__(self, root: Path) -> None:
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        self.catalog = SchemaCatalog(tuple(ArtifactSchemaRegistration(kind, version, lambda raw: raw)
            for kind, version in ((_BUNDLE, 1), (_COMPONENT, 1), ("backtest_target_stream", 1),
                                  ("backtest_execution_input_bundle", 8))))

    def path(self, ref: ArtifactRef) -> Path:
        return self.root / f"{ref.content_hash.removeprefix('sha256:')}.json"

    def put(self, *, envelope: ArtifactEnvelope) -> ArtifactRef:
        ref = ArtifactRef.from_envelope(envelope)
        path = self.path(ref)
        source = canonical_bytes(envelope)
        if path.exists():
            if path.read_bytes() != source:
                raise ArtifactIntegrityError("test fixture occupied ref bytes differ")
        else:
            with path.open("xb") as stream:
                stream.write(source)
        return ref

    def read(self, *, ref: ArtifactRef) -> ArtifactReadResult:
        try:
            source = self.path(ref).read_bytes()
        except FileNotFoundError as error:
            raise ArtifactNotFoundError(ref.content_hash) from error
        result = self.catalog.read(source)
        if ArtifactRef.from_envelope(result.envelope) != ref:
            raise ArtifactIntegrityError("test fixture ref does not bind retained bytes")
        return result


def _retained(root: Path, codes=(_CODES[0], _CODES[4])) -> tuple[Path, dict[str, Path]]:
    source_ref, inputs, memory, market = _gate_bundle(codes=codes)
    disk = _DiskArtifacts(root / "sources")
    for ref, envelope in memory.values.items():
        assert disk.put(envelope=envelope) == ref
    case_ref = retain_cn_a_share_portfolio_case_input_v8(
        inputs, target_reader=disk, market_reader=market, publisher=disk)
    stored = LocalMarketBundleRepository(config=LocalMarketBundleRepositoryConfig(root=root / "market"))
    result = stored.publish_market_bundle_v1(
        manifest=market.manifest,
        stream_payloads={key: canonical_bytes(events) for key, events in market.streams.items()},
        retention_policy_ref="retention.local-market-bundle-repository-v1")
    assert result.result is not None and result.result.bundle_ref == inputs.market_bundle_ref
    selectors = root / "selectors.json"
    selectors.write_bytes(canonical_bytes({"source_ref": source_ref, "case_ref": case_ref,
                                          "market_ref": inputs.market_bundle_ref}))
    payload = memory.values[source_ref].payload
    stocks = payload["stock_sources"]
    paths = {"source_bundle": disk.path(source_ref), "scope": disk.path(case_ref),
             "target": disk.path(inputs.target_stream_ref.artifact_ref),
             **{role: disk.path(_ref(stocks[-1][role]))
                for role in ("membership", "trade_status", "corporate_action")},
             **{venue["venue_id"] + "_fee": disk.path(_ref(venue["fee"]))
                for venue in payload["venue_fees"]}}
    expected_open_bytes = canonical_bytes(market.streams["bars.open"])
    paths["open_stream"] = next(path for path in (root / "market").rglob("*")
                                if path.is_file() and path.read_bytes() == expected_open_bytes)
    return selectors, paths


def _cold_read(selectors_path: Path) -> dict[str, Any]:
    selectors = json.loads(selectors_path.read_bytes())
    source_ref, case_ref = (_ref(selectors[key]) for key in ("source_ref", "case_ref"))
    raw_market = selectors["market_ref"]
    market_ref = MarketBundleRef(raw_market["bundle_key"], raw_market["manifest_hash"])
    disk = _DiskArtifacts(selectors_path.parent / "sources")
    market = LocalMarketBundleReader.open(
        repository_root=(selectors_path.parent / "market").resolve(), bundle_ref=market_ref)
    # No typed scope, memory store, target object or opening event passed from the producer.
    case = read_retained_cn_a_share_portfolio_case_input_v8(
        case_ref, reader=disk, target_reader=disk, market_reader=market)
    source = read_cn_a_share_portfolio_source_bundle_draft_v0(
        source_ref, inputs=case.scope, reader=disk)
    assert source.synthetic_complete and not source.formal_qualified and not source.trade_authorized
    try:
        require_cn_a_share_portfolio_source_qualification_v1(
            case.scope, market_reader=market, artifact_reader=disk, source_bundle_ref=source_ref)
    except CnASharePortfolioSourceAdmissionBlockedV1 as blocked:
        return {"component_count": source.component_count, "stock_count": len(case.scope.instrument_ids),
                "formal_qualified": source.formal_qualified, "trade_authorized": source.trade_authorized,
                "formal_blockers": list(blocked.reason_codes), "scope_hash": case.scope.input_hash}
    raise AssertionError("cold synthetic source unexpectedly received formal admission")


def _bytes(root: Path) -> dict[str, bytes]:
    return {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def test_cold_two_stock_smoke_reconstructs_scope_target_open_and_eight_source_components(tmp_path):
    selectors, _ = _retained(tmp_path)
    before = _bytes(tmp_path)
    result = _cold_read(selectors)
    assert result["component_count"] == 8 and result["stock_count"] == 2
    assert len(result["formal_blockers"]) == 8
    assert not result["formal_qualified"] and not result["trade_authorized"]
    assert _bytes(tmp_path) == before  # cold replay produces no case/result/owner publication


@pytest.mark.parametrize("count", (2, 10), ids=("two_stock", "ten_stock"))
def test_new_process_reopens_only_raw_selectors_and_stays_formal_blocked(tmp_path, count, record_property):
    codes = (_CODES[0], _CODES[4]) if count == 2 else _CODES
    selectors, _ = _retained(tmp_path, codes)
    before = _bytes(tmp_path)
    root = Path(__file__).resolve().parents[3]
    script = "\n".join((
        "import json, sys, socket",
        "from pathlib import Path",
        "root = Path(sys.argv[1])",
        "packages = ('trading-domain', 'market-data-contracts', 'trading-kernel', 'backtest-runtime', 'market-bundle-builder')",
        "sys.path[:0] = [str(root)] + [str(root / 'packages' / name / 'src') for name in packages]",
        "from tests import conftest",
        "assert getattr(socket.socket.connect, '__network_guard__', False)",
        "from tests.runtime.providers.test_cn_a_share_portfolio_source_cold_reopen import _cold_read",
        "from crypto_quant_backtest import cn_a_share_portfolio_source_bundle_draft_v0 as owner",
        "assert Path(owner.__file__).resolve() == root / 'packages/backtest-runtime/src/crypto_quant_backtest/cn_a_share_portfolio_source_bundle_draft_v0.py'",
        "print(json.dumps(_cold_read(Path(sys.argv[2])), sort_keys=True))",
    ))
    argv = [sys.executable, "-I", "-B", "-c", script, str(root), str(selectors)]
    env = {"PATH": os.defpath, "HOME": str(tmp_path), "TMPDIR": str(tmp_path),
           "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1",
           "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "OPENBLAS_NUM_THREADS": "1",
           "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
    record_property("cold_reopen_request", json.dumps({"argv": argv, "cwd": str(root), "env": env}))
    try:
        child = subprocess.run(argv, cwd=root, env=env, capture_output=True, text=True,
                               timeout=10, check=False)
    except subprocess.TimeoutExpired:
        record_property("cold_reopen_result", json.dumps({"timed_out": True, "exit_code": None}))
        raise
    record_property("cold_reopen_result", json.dumps({"exit_code": int(child.returncode),
                    "stdout": child.stdout, "stderr": child.stderr, "timed_out": False}))
    child.check_returncode()
    result = json.loads(child.stdout)
    assert result["component_count"] == 3 * count + 2 and result["stock_count"] == count
    assert len(result["formal_blockers"]) == 8
    assert not result["formal_qualified"] and not result["trade_authorized"]
    assert _bytes(tmp_path) == before


@pytest.mark.parametrize("role", ("source_bundle", "scope", "target", "membership", "trade_status",
                                   "corporate_action", "xshg_fee", "xshe_fee", "open_stream"))
@pytest.mark.parametrize("failure", ("deleted", "corrupted"))
def test_cold_reopen_after_success_still_rejects_missing_or_corrupt_raw_files(tmp_path, role, failure):
    selectors, paths = _retained(tmp_path)
    assert _cold_read(selectors)["component_count"] == 8  # a prior success never supplies a cache fallback
    affected = paths[role]
    # Deliberate fault injection only in this test root; restore native immutable-bundle modes.
    if failure == "deleted":
        mode = stat.S_IMODE(affected.parent.stat().st_mode)
        affected.parent.chmod(mode | stat.S_IWUSR)
        affected.unlink()
        affected.parent.chmod(mode)
    else:
        mode = stat.S_IMODE(affected.stat().st_mode)
        affected.chmod(mode | stat.S_IWUSR)
        affected.write_bytes(affected.read_bytes() + b"\n")
        affected.chmod(mode)
    before = _bytes(tmp_path)
    with pytest.raises((ValueError, ArtifactNotFoundError, ArtifactIntegrityError, BacktestTargetStreamError)) as rejected:
        _cold_read(selectors)
    assert type(rejected.value) is not CnASharePortfolioSourceAdmissionBlockedV1
    assert _bytes(tmp_path) == before
