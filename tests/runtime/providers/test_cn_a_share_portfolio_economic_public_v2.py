"""Public V2 activation, real native money and source-bound NAV contracts."""
from dataclasses import replace, fields
import json

import pytest
import crypto_quant_domain as d
import crypto_quant_trading as t
import crypto_quant_backtest as bt
from tests.runtime.providers._cn_a_share_portfolio_economic_fixtures_v2 import economic_prepared_case_v2


def _forbidden(*args, **kwargs):
    raise AssertionError("cold/cache must not execute, select, append or publish")


def _cold_guards(monkeypatch, store):
    from crypto_quant_backtest.cn_a_share_portfolio_economic_engine_v1 import _CnASharePortfolioEconomicEngineV1
    import crypto_quant_backtest.cn_a_share_portfolio_economic_opening_v1 as opening
    import crypto_quant_backtest.cn_a_share_portfolio_financial_core_v1 as core
    monkeypatch.setattr(_CnASharePortfolioEconomicEngineV1, "run", _forbidden)
    monkeypatch.setattr(opening, "_economic_opening_v1", _forbidden)
    monkeypatch.setattr(opening, "_book_economic_full_fill_batch_v1", _forbidden)
    monkeypatch.setattr(core, "book_native_cn_portfolio_financial_core_v1", _forbidden)
    monkeypatch.setattr(t.AccountingJournal, "append", _forbidden)
    monkeypatch.setattr(t.AccountingJournal, "append_many", _forbidden)
    monkeypatch.setattr(store, "put", _forbidden)


def _assert_public_replay_v2(prepared, ref, store, root, monkeypatch):
    before = {key: d.canonical_bytes(value) for key, value in store.values.items()}
    files = {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()}
    put, repeated = store.put, []
    def identical_put(*, envelope):
        expected = d.ArtifactRef.from_envelope(envelope)
        assert expected in before
        assert before[expected] == d.canonical_bytes(envelope)
        retained = store.read(ref=expected)
        assert retained.source_bytes == before[expected] == d.canonical_bytes(retained.envelope)
        repeated.append(expected)
        return put(envelope=envelope)
    with monkeypatch.context() as cached:
        _cold_guards(cached, store)
        cached.setattr(store, "put", identical_put)
        assert prepared.runtime.run(prepared.execution_request) == ref
    assert {key: d.canonical_bytes(value) for key, value in store.values.items()} == before
    assert {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()} == files
    return repeated


def test_v2_two_instrument_public_activation_finance(tmp_path, monkeypatch):
    import crypto_quant_backtest.cn_a_share_portfolio_economic_native_state_v1 as state
    from crypto_quant_backtest.cn_a_share_portfolio_economic_engine_v1 import _CnASharePortfolioEconomicEngineV1
    from tests.runtime.providers._cn_a_share_portfolio_economic_fixtures_v2 import economic_public_sources_v2, _prepare_sources_v2
    inputs, _, market, store, _, window = economic_public_sources_v2()
    projected, allocated, sized, outcomes = [], [], [], []
    project, allocate, materialize, run = state._economic_projection_at_v1, t.PortfolioAllocator.allocate, t.PositionSizer.materialize, _CnASharePortfolioEconomicEngineV1.run
    def projection(**kwargs):
        projected.append(kwargs["marks"].at)
        return project(**kwargs)
    def allocation(self, **kwargs):
        allocated.append(kwargs)
        return allocate(self, **kwargs)
    def sizing(self, **kwargs):
        sized.append(kwargs)
        return materialize(self, **kwargs)
    def engine(self, *args, **kwargs):
        result = run(self, *args, **kwargs)
        outcomes.append(result)
        return result
    monkeypatch.setattr(state, "_economic_projection_at_v1", projection)
    monkeypatch.setattr(t.PortfolioAllocator, "allocate", allocation)
    monkeypatch.setattr(t.PositionSizer, "materialize", sizing)
    monkeypatch.setattr(_CnASharePortfolioEconomicEngineV1, "run", engine)
    inputs = replace(inputs)
    prepared, case, inputs, store, market = _prepare_sources_v2(tmp_path, inputs, market, store, window)
    original = d.canonical_bytes(inputs.source_target_stream)
    retained = d.canonical_bytes(inputs.retained_signal_marks)
    assert not outcomes and not allocated and not sized
    ref = prepared.runtime.run(prepared.execution_request)
    assert type(ref) is bt.BacktestCanonicalPublicationRef
    assert len(outcomes) == 2 and all(o.result is not None for o in outcomes)
    result = outcomes[0].result
    fills = {f.instrument_id.stable_key: f for f in result.fills}
    assert set(fills) == {"600000", "000001"}
    for key, quantity, reference, execution in (("600000", 4300, 1137, 1138), ("000001", 2200, 2231, 2233)):
        fill = fills[key]
        assert fill.side is d.OrderSide.BUY and fill.quantity.units == quantity
        assert fill.reference_price.units == reference and fill.price.units == execution
        assert fill.slippage_amount.units > 0
        expected = replace(fill, quantity=d.Quantity(quantity, fill.quantity.scale, str(fill.instrument_id)),
            reference_price=replace(fill.reference_price, units=reference), price=replace(fill.price, units=execution))
        assert expected == fill
    assert all(at >= inputs.initial_marks.at for at in projected)
    assert allocated and sized
    assert all(call["sleeve_state"].as_of_instant.phase.rank == 30 for call in allocated)
    assert all(call["portfolio_snapshot"].timestamp_instant >= inputs.initial_marks.at for call in allocated)
    assert all(call["approved_target"].approved_instant.phase.rank == 30 for call in sized)
    assert all(a.occurred_at >= inputs.initial_marks.at for a in result.financial_artifacts)
    assert all(s.order.created_at >= inputs.initial_marks.at for s in result.order_streams)
    assert all(e.recorded_at >= inputs.initial_marks.at for e in result.final_journal.entries[len(inputs.initial_journal.entries):])
    assert not any(a.role == "economic_dividend_transition" for a in result.financial_artifacts)
    # Native assessors independently derive every complete assessment from fixed
    # expected fill economics and the original source fee rules, not aggregate math.
    steps = [step for a in result.financial_artifacts if a.role == "economic_opening_batch" for step in a.payload.payload["steps"]]
    for fill in fills.values():
        stream = next(s for s in result.order_streams if s.order.order_id == fill.order_id)
        term = next(term for term in inputs.opening_terms if term.instrument_id == fill.instrument_id
            and term.opening_at == fill.execution_time and term.side == fill.side)
        for basis, rules in ((t.FeeAssessmentBasisEvidence.for_fill(fill), term.final_fill_rules),
                (t.FeeAssessmentBasisEvidence.for_order(stream), term.final_order_rules)):
            actual = next(a for a in result.fee_assessments if a.basis_ids == (fill.fill_id if rules is term.final_fill_rules else stream.order.order_id,))
            expected = t.FeeAssessmentEngine().assess(basis=basis, rule_set=rules,
                fee_assessment_id=actual.fee_assessment_id, assessment_time=fill.execution_time)
            assert expected.result is not None and expected.result.assessment == actual
    assert len(result.fee_assessments) == 4 and steps
    assert sum(a.amount.units for a in result.fee_assessments) > 0
    ledger = result.final_ledger_state
    assert {p.key.instrument_id.stable_key: p.quantity.units for p in ledger.position_balances} == {"600000": 4300, "000001": 2200}
    suffix = result.final_journal.entries[len(inputs.initial_journal.entries):]
    booked = sum(-change.value.units for e in suffix if e.entry_type is d.AccountingEntryType.FILL_BOOKED for change in e.balance_changes if type(change.key) is d.CashBalanceKey)
    charged = sum(fee.units for e in suffix for fee in e.fees)
    assert charged == sum(a.amount.units for a in result.fee_assessments) > 0
    assert sum(b.amount.units for b in ledger.cash_balances) == inputs.scope.initial_cash.units - booked - charged
    assert d.canonical_bytes(case.target_stream) == original == d.canonical_bytes(inputs.source_target_stream)
    assert retained == d.canonical_bytes(inputs.retained_signal_marks)
    repository = bt.BacktestEvidenceRepository(reader=store)
    completed = repository.load_completed(ref, economic_market_reader=market)
    assert len(completed.execution_summary.fills) == 2
    nav = bt.CnASharePortfolioEconomicDailyNavAnalysisRuntimeV1(reader=store, publisher=store, market_reader=market)
    profile = nav.publish_metric_profile()
    analysis_ref = nav.derive(publication_ref=ref, metric_profile_ref=profile)
    value = repository.load_cn_a_share_portfolio_economic_daily_nav(analysis_ref, market_reader=market)
    assert value.trade_count == 2 and len(value.points) == 2
    assert tuple(p.trade_date for p in value.points) == ("2023-08-28", "2023-08-29")
    assert value.initial_equity == case.execution_case_plan.initial_economic_projection.snapshot.equity
    assert value.definition_ref.schema_version == 3 and value.execution_input_ref == prepared.execution_request.execution_input_bundle_ref
    assert len([f for f in fields(type(value)) if f.init]) == 13 and len(value.to_canonical_dict()) == 24
    assert all(value.to_canonical_dict()[k] is False for k in ("source_qualification_verified", "validation_eligible", "trade_authorized"))
    assert nav.derive(publication_ref=ref, metric_profile_ref=profile) == analysis_ref
    assert _assert_public_replay_v2(prepared, ref, store, tmp_path, monkeypatch)
    with monkeypatch.context() as cold:
        _cold_guards(cold, store)
        from crypto_quant_backtest.cn_a_share_portfolio_economic_result_v1 import _verify_economic_native_cached_v1
        _verify_economic_native_cached_v1(case=case, reader=store, publication_ref=ref.artifact_ref)
        assert repository.load_completed(ref, economic_market_reader=market) == completed
        assert repository.load_cn_a_share_portfolio_economic_daily_nav(analysis_ref, market_reader=market) == value
    assert len(tuple(tmp_path.glob("runs/*/attempts/*/attempt-execution-record.json"))) == 2


@pytest.fixture(scope="module")
def public_v2_result(tmp_path_factory):
    root = tmp_path_factory.mktemp("public-v2-facts")
    prepared, case, inputs, store, market = economic_prepared_case_v2(root)
    ref = prepared.runtime.run(prepared.execution_request)
    from crypto_quant_backtest.cn_a_share_portfolio_economic_result_v1 import _completed_children_v1
    engine = _completed_children_v1(store, ref)[3]
    return prepared, case, inputs, store, market, ref, engine


def test_v2_native_mixed_clock_invariants(public_v2_result):
    prepared, case, inputs, store, market, ref, engine = public_v2_result
    from crypto_quant_backtest.execution_inputs import _read_simulation_instant
    fact = next(a["payload"]["payload"] for a in engine.payload["financial_artifacts"] if a["role"] == "economic_signal")
    signal = fact["signal"]
    assert _read_simulation_instant(signal["decision_batch"]["decision_instant"]) == inputs.retained_signal_marks[0].at
    activation = fact["activation"]
    at = _read_simulation_instant(activation["activation_at"])
    assert at.phase == d.TimelinePhase(30, "cn_economic_native") and at.source_sequence == d.SourceSequence(0)
    assert fact["cancel_sources"]["at"] == signal["normalized_target"]["materialized_instant"] == activation["activation_at"]
    assert signal["allocation"]["valuation_instant"] == signal["approved_target"]["approved_instant"] == activation["activation_at"]
    assert signal["snapshot"]["timestamp_instant"] == activation["activation_at"]
    assert signal["target_validity"]["valid_from"] == signal["normalized_target"]["materialized_at"]
    assert signal["target_validity"]["valid_until"] is None
    assert signal["target_validity"]["valid_until"] == signal["decision_batch"]["decisions"][0]["target_snapshot"]["expires_at"]
    assert _read_simulation_instant(fact["coordinator_sources"]["at"]).phase.rank == 45
    orders = sorted((s["order"] for s in engine.payload["order_streams"]), key=lambda o: o["created_at"]["source_sequence"]["value"])
    assert tuple(o["created_at"]["source_sequence"]["value"] for o in orders) == (1, 2)
    assert all(_read_simulation_instant(o["created_at"]).phase.rank == 40 for o in orders)
    assert prepared.execution_request.request.target_stream_digest == inputs.source_target_stream.target_stream_digest


def test_v2_shared_native_financial_path(public_v2_result):
    _, _, inputs, _, _, _, engine = public_v2_result
    assert len(engine.payload["fills"]) == 2 and len(engine.payload["fee_assessments"]) == 4
    steps = [step for a in engine.payload["financial_artifacts"] if a["role"] == "economic_opening_batch" for step in a["payload"]["payload"]["steps"]]
    assert len(steps) == 2
    assert all(step["type"] == "cn_a_share_portfolio_economic_financial_step" for step in steps)
    from crypto_quant_backtest.cn_a_share_portfolio_economic_result_v1 import _verify_economic_native_result_v1
    # Full native fee/accounting/T+1 rederivation, not aggregate fill-count evidence.
    _, case, _, store, _, _, _ = public_v2_result
    _verify_economic_native_result_v1(case=case, reader=store, result=engine.payload)


def test_v2_existing_nav_runtime_source_tuple_and_replay(public_v2_result, monkeypatch):
    prepared, case, inputs, store, market, ref, engine = public_v2_result
    nav = bt.CnASharePortfolioEconomicDailyNavAnalysisRuntimeV1(reader=store, publisher=store, market_reader=market)
    profile = nav.publish_metric_profile()
    nav_ref = nav.derive(publication_ref=ref, metric_profile_ref=profile)
    assert nav.derive(publication_ref=ref, metric_profile_ref=profile) == nav_ref
    repository = bt.BacktestEvidenceRepository(reader=store)
    value = repository.load_cn_a_share_portfolio_economic_daily_nav(nav_ref, market_reader=market)
    assert value.initial_equity.units == 10_000_000 and value.trade_count == 2
    assert value.definition_ref == d.ArtifactRef.from_envelope(inputs.definition())
    assert tuple(p.trade_date for p in value.points) == ("2023-08-28", "2023-08-29")
    with monkeypatch.context() as cold:
        _cold_guards(cold, store)
        assert repository.load_cn_a_share_portfolio_economic_daily_nav(nav_ref, market_reader=market) == value


def test_v2_nav_definition_reference_legacy_error_order_and_versions(public_v2_result):
    # These declarations probe constructor compatibility only; synthetic schema-3
    # refs are not evidence of a semantic publication/source tuple.
    _, _, inputs, store, market, ref, _ = public_v2_result
    nav = bt.CnASharePortfolioEconomicDailyNavAnalysisRuntimeV1(reader=store, publisher=store, market_reader=market)
    profile = nav.publish_metric_profile()
    nav_ref = nav.derive(publication_ref=ref, metric_profile_ref=profile)
    value = bt.BacktestEvidenceRepository(reader=store).load_cn_a_share_portfolio_economic_daily_nav(nav_ref, market_reader=market)

    with pytest.raises(TypeError, match="^NAV source requires exact backtest_profile_portfolio_definition@2$") as caught:
        replace(value, definition_ref=None)
    assert str(caught.value) == "NAV source requires exact backtest_profile_portfolio_definition@2"

    with pytest.raises(TypeError, match="^NAV source requires exact backtest_execution_input_bundle@9$") as caught:
        replace(value, execution_input_ref=None, definition_ref=None)
    assert str(caught.value) == "NAV source requires exact backtest_execution_input_bundle@9"

    definition2 = d.ArtifactRef("backtest_profile_portfolio_definition", 2, d.canonical_sha256("declaration-only definition2"))
    definition3 = d.ArtifactRef("backtest_profile_portfolio_definition", 3, d.canonical_sha256("declaration-only definition3"))
    assert replace(value, definition_ref=definition2).definition_ref == definition2
    assert replace(value, definition_ref=definition3).definition_ref == definition3
    for artifact_type, version in (("wrong_definition", 3), ("backtest_profile_portfolio_definition", 4)):
        wrong = d.ArtifactRef(artifact_type, version, d.canonical_sha256((artifact_type, version)))
        with pytest.raises(TypeError, match="^NAV source requires exact backtest_profile_portfolio_definition@2$"):
            replace(value, definition_ref=wrong)


def test_v2_repeated_prepare_and_original_source_refusal(tmp_path, monkeypatch):
    from tests.runtime.providers._cn_a_share_portfolio_economic_fixtures_v2 import economic_public_sources_v2, _prepare_sources_v2, _changed_target_v2
    inputs, _, market, store, _, window = economic_public_sources_v2()
    one = _prepare_sources_v2(tmp_path, inputs, market, store, window)[0]
    two = _prepare_sources_v2(tmp_path, inputs, market, store, window)[0]
    assert d.canonical_bytes(one.execution_request) == d.canonical_bytes(two.execution_request)
    assert one.request_ref == two.request_ref and one.semantic_run_id == two.semantic_run_id
    changed = _changed_target_v2(inputs, store, expires_at=inputs.initial_marks.at.instant.epoch_nanoseconds)
    changed = replace(changed, scope=inputs.scope)
    writes = []
    put = store.put
    def observe(*, envelope):
        writes.append(envelope.artifact_type)
        return put(envelope=envelope)
    with monkeypatch.context() as patch:
        patch.setattr(store, "put", observe)
        with pytest.raises(ValueError, match="retained target differs"):
            _prepare_sources_v2(tmp_path, changed, market, store, window)
    assert not writes and not tuple(tmp_path.glob("runs/*/attempts/*/attempt-execution-record.json"))
    with pytest.raises(ValueError, match="prestart data window"):
        _prepare_sources_v2(tmp_path, inputs, market, store, replace(window, data_start=inputs.initial_marks.at.instant))


@pytest.mark.parametrize("where", ["prepare_target", "prepare_put", "prepare_definition", "prepare_binder", "run", "cache", "cold"])
def test_v2_public_storage_exception_identity(tmp_path, monkeypatch, where):
    from tests.runtime.providers._cn_a_share_portfolio_economic_fixtures_v2 import economic_public_sources_v2, _prepare_sources_v2
    inputs, _, market, store, _, window = economic_public_sources_v2()
    sentinel = OSError("public V2 exact IO object")
    if not where.startswith("prepare"):
        prepared = _prepare_sources_v2(tmp_path, inputs, market, store, window)[0]
        if where in ("cache", "cold"):
            ref = prepared.runtime.run(prepared.execution_request)
    read = store.read
    definition_reads, binding = [], []
    import crypto_quant_backtest.cn_a_share_portfolio_economic_prepare_v2 as prepare_module
    bind = prepare_module._bind_economic_portfolio_sources_v1
    def binding_boundary(*args, **kwargs):
        binding.append(True)
        try:
            return bind(*args, **kwargs)
        finally:
            binding.append(False)
    monkeypatch.setattr(prepare_module, "_bind_economic_portfolio_sources_v1", binding_boundary)
    def broken(*args, **kwargs): raise sentinel
    def selective(*, ref):
        definition = ref.artifact_type == "backtest_profile_portfolio_definition" and ref.schema_version == 3
        in_binding = bool(binding and binding[-1])
        if definition: definition_reads.append((ref, in_binding))
        if ((where == "prepare_target" and ref == inputs.scope.target_stream_ref.to_artifact_ref())
                or (where == "prepare_definition" and definition)
                or (where == "prepare_binder" and definition and in_binding)):
            raise sentinel
        return read(ref=ref)
    monkeypatch.setattr(store, "read", selective if where.startswith("prepare") else broken)
    if where == "prepare_put": monkeypatch.setattr(store, "put", broken)
    if where == "prepare_target":
        with pytest.raises(bt.BacktestTargetStreamError) as caught:
            _prepare_sources_v2(tmp_path, inputs, market, store, window)
        assert caught.value.code is bt.BacktestTargetStreamFailureCode.RETENTION_UNAVAILABLE
        assert caught.value.__cause__ is sentinel
    elif where == "prepare_definition":
        with pytest.raises(ValueError, match="^published artifact readback unavailable$") as caught:
            _prepare_sources_v2(tmp_path, inputs, market, store, window)
        assert type(caught.value) is ValueError and caught.value.__cause__ is sentinel
        assert definition_reads == [(d.ArtifactRef.from_envelope(inputs.definition()), False)]
    else:
        with pytest.raises(OSError) as caught:
            if where.startswith("prepare"): _prepare_sources_v2(tmp_path, inputs, market, store, window)
            elif where == "cold": bt.BacktestEvidenceRepository(reader=store).load_completed(ref, economic_market_reader=market)
            else: prepared.runtime.run(prepared.execution_request)
        assert caught.value is sentinel
    if where == "prepare_binder":
        assert definition_reads == [(d.ArtifactRef.from_envelope(inputs.definition()), False),
            (d.ArtifactRef.from_envelope(inputs.definition()), True)]
        assert binding == [True, False]
    if where.startswith("prepare"):
        assert not tuple(tmp_path.glob("runs/*/attempts/*/attempt-execution-record.json"))


def _assert_candidate_source_provenance(snapshot, manifest):
    """Both pre-commit snapshots and clean committed candidates must be truthful."""
    from pathlib import Path
    assert manifest.provenance.source_root == snapshot["candidate"]
    if snapshot["source_tree_state"] == "UNCOMMITTED":
        assert manifest.provenance.git_commit == "uncommitted-source-snapshot:" + snapshot["snapshot_hash"]
    else:
        import subprocess
        assert snapshot["source_tree_state"] == "CLEAN"
        root = Path(snapshot["candidate"])
        git = ["git", "--no-optional-locks", "-c", "diff.autoRefreshIndex=false", "-C", str(root)]
        actual = subprocess.check_output([*git, "rev-parse", "HEAD"], text=True).strip()
        assert actual == snapshot["base_commit"] == manifest.provenance.git_commit
        assert subprocess.check_output([*git, "status", "--porcelain=v1", "--untracked-files=all"]) == b""


@pytest.mark.parametrize("mutation", ("valid", "commit", "root", "unknown-state"))
def test_v2_legacy_uncommitted_provenance_checks_remain_exact(tmp_path, mutation):
    from types import SimpleNamespace
    snapshot = {"source_tree_state": "UNCOMMITTED", "snapshot_hash": "sha256:" + "a" * 64,
        "candidate": str(tmp_path), "base_commit": "0" * 40}
    provenance = bt.BuildProvenance("uncommitted-source-snapshot:" + snapshot["snapshot_hash"],
        "synthetic", str(tmp_path), d.UtcInstant(1))
    if mutation == "commit":
        provenance = replace(provenance, git_commit="0" * 40)
    elif mutation == "root":
        provenance = replace(provenance, source_root=str(tmp_path / "different"))
    elif mutation == "unknown-state":
        snapshot["source_tree_state"] = "UNRECOGNIZED"
    manifest = SimpleNamespace(provenance=provenance)
    if mutation == "valid":
        _assert_candidate_source_provenance(snapshot, manifest)
    else:
        with pytest.raises(AssertionError):
            _assert_candidate_source_provenance(snapshot, manifest)


@pytest.mark.parametrize("mutation", ("valid", "dirty", "base", "provenance", "root"))
def test_v2_committed_provenance_requires_actual_clean_Git_source(tmp_path, mutation):
    import subprocess
    from types import SimpleNamespace
    root = tmp_path / "clean-source"
    root.mkdir()
    git = ["git", "--no-optional-locks", "-c", "diff.autoRefreshIndex=false", "-C", str(root)]
    subprocess.run([*git, "init", "-q"], check=True)
    source = root / "tracked.txt"
    source.write_text("synthetic source\n")
    subprocess.run([*git, "add", "tracked.txt"], check=True)
    subprocess.run([*git, "-c", "user.name=SDK Test", "-c", "user.email=sdk-test@localhost",
        "commit", "-q", "-m", "synthetic source"], check=True)
    commit = subprocess.check_output([*git, "rev-parse", "HEAD"], text=True).strip()
    snapshot = {"source_tree_state": "CLEAN", "snapshot_hash": "sha256:" + "a" * 64,
        "candidate": str(root), "base_commit": commit}
    provenance = bt.BuildProvenance(commit, "synthetic", str(root), d.UtcInstant(1))
    if mutation == "dirty":
        source.write_text("changed source\n")
    elif mutation == "base":
        snapshot["base_commit"] = "0" * 40
    elif mutation == "provenance":
        provenance = replace(provenance, git_commit="0" * 40)
    elif mutation == "root":
        provenance = replace(provenance, source_root=str(tmp_path / "wrong"))
    manifest = SimpleNamespace(provenance=provenance)
    if mutation == "valid":
        _assert_candidate_source_provenance(snapshot, manifest)
    else:
        with pytest.raises(AssertionError):
            _assert_candidate_source_provenance(snapshot, manifest)


def test_v2_honest_candidate_build_binding(tmp_path, monkeypatch):
    import hashlib
    import importlib
    import importlib.metadata
    import os
    from pathlib import Path
    from crypto_quant_backtest.execution_inputs import _read_build_manifest, _read_execution_inputs_v9_from_snapshot
    path = os.environ.get("V2_CANDIDATE_PROVENANCE")
    assert path, "V2_CANDIDATE_PROVENANCE must identify actual fresh candidate proof; absence is failure"
    proof = json.loads(Path(path).read_text())
    snapshot = json.loads(Path(proof["source_manifest"]).read_text())
    identity = {key: snapshot[key] for key in ("base_commit", "files")}
    compact = json.dumps(identity, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    assert snapshot["snapshot_hash"] == "sha256:" + hashlib.sha256(compact).hexdigest()
    manifest = _read_build_manifest(proof["build_manifest"])
    _assert_candidate_source_provenance(snapshot, manifest)
    root = Path(snapshot["candidate"])
    for row in snapshot["files"]:
        source = root / row["path"]
        assert hashlib.sha256(source.read_bytes()).hexdigest() == row["sha256"], row["path"]
        assert source.stat().st_mode & 0o777 == row["mode"]
    for package in proof["packages"]:
        module = importlib.import_module(package["module"])
        assert str(Path(module.__file__).resolve()) == package["module_file"]
        dist = importlib.metadata.distribution(package["distribution"])
        assert json.loads(dist.read_text("direct_url.json")) == package["direct_url"]
        assert dist.version == package["version"]
    assert len(proof["packages"]) == 5
    prepared, case, inputs, store, market = economic_prepared_case_v2(tmp_path, build_artifact_manifest=manifest)
    bundle, failure = _read_execution_inputs_v9_from_snapshot(store, prepared.execution_request)
    assert failure is None
    assert all(a in bundle.build_artifact_manifest.artifacts for a in manifest.artifacts)
    ref = prepared.runtime.run(prepared.execution_request)
    assert type(ref) is bt.BacktestCanonicalPublicationRef
    _assert_public_replay_v2(prepared, ref, store, tmp_path, monkeypatch)
    with monkeypatch.context() as cold:
        _cold_guards(cold, store)
        assert len(bt.BacktestEvidenceRepository(reader=store).load_completed(ref, economic_market_reader=market).execution_summary.fills) == 2
    runtime = next(a for a in manifest.artifacts if a.role is bt.BuildArtifactRole.BACKTEST_RUNTIME)
    changed = replace(runtime, content_hash=d.canonical_sha256({"different_runtime_snapshot": runtime.content_hash}),
        source_snapshot_hash=d.canonical_sha256({"different_runtime_source": runtime.source_snapshot_hash}))
    other_manifest = replace(manifest, artifacts=tuple(changed if a is runtime else a for a in manifest.artifacts))
    other = economic_prepared_case_v2(tmp_path, build_artifact_manifest=other_manifest)[0]
    assert other.semantic_run_id != prepared.semantic_run_id
