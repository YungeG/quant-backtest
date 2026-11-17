"""Fixture interruptions must not leak a global finalizer into later test modules."""
from types import SimpleNamespace

import pytest
from crypto_quant_backtest import BacktestRuntime
from tests.runtime.g12m import test_tushare_fixed_singleton_assessment_v2 as assessment
from tests.runtime.g12m import test_tushare_listing_presence_binding_v1 as listing


@pytest.mark.parametrize("owner,fixture_name", ((assessment, "route_result"), (listing, "base_assessment")),
    ids=("assessment", "listing"))
@pytest.mark.parametrize("failure", ("reader", "run"))
def test_native_fixture_interruption_restores_original_finalizer(tmp_path, monkeypatch, owner, fixture_name, failure):
    class Interrupted(RuntimeError):
        pass
    def interrupt(*args, **kwargs):
        raise Interrupted("synthetic fixture interruption before retained data access")
    def directory(name):
        path = tmp_path / name
        path.mkdir()
        return path
    monkeypatch.setattr(owner, "_reader", interrupt if failure == "reader" else lambda *a, **k: object())
    if failure == "run":
        monkeypatch.setattr(owner, "run_g12m_tushare_fixed_singleton_route_v2", interrupt)
    original = BacktestRuntime._finalize_v3_attempt_locked
    try:
        with pytest.raises(Interrupted):
            getattr(owner, fixture_name).__wrapped__(SimpleNamespace(mktemp=directory))
        assert BacktestRuntime._finalize_v3_attempt_locked is original
    finally:
        # The RED itself must not poison subsequent tests in this process.
        BacktestRuntime._finalize_v3_attempt_locked = original
