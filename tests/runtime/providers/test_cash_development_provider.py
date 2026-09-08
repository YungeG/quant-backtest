from __future__ import annotations

from dataclasses import fields, is_dataclass, replace
from inspect import Parameter, signature
from pathlib import Path
import subprocess
import sys

import pytest

import crypto_quant_backtest as backtest
from crypto_quant_domain import (
    ArtifactEnvelope,
    ArtifactReadResult,
    ArtifactRef,
    CurrencyId,
    ExecutionStyle,
    InstrumentCatalog,
    InstrumentDefinition,
    InstrumentId,
    InstrumentType,
    Money,
    PositionEffect,
    Price,
    PricePurpose,
    Scale,
    SourceSequence,
    StrategySleeveId,
    TimelinePhase,
    TimeInForce,
    UtcInstant,
    VenueId,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_market_data import InMemoryMarketBundleReader, MarketEvent
from crypto_quant_trading import (
    MarkObservation,
    OrderCapabilityKey,
    OrderCapabilitySet,
    OrderStyleCapability,
    PriceConstraintShape,
    QuantityLattice,
)

_VENUE = VenueId("synthetic")
_USD = CurrencyId("USD")
_INSTRUMENT = InstrumentId(_VENUE, "cash:btc-usd")
_TARGET_TIME = UtcInstant(100)
_BAR_TIME = UtcInstant(200)


def catalog() -> InstrumentCatalog:
    base = CurrencyId("BTC")
    return InstrumentCatalog(
        currencies=(base, _USD),
        instruments=(
            InstrumentDefinition(
                _INSTRUMENT,
                InstrumentType.SPOT,
                base,
                _USD,
                _USD,
            ),
        ),
        symbol_timelines=(),
    )


def target_event() -> MarketEvent:
    return MarketEvent(
        event_id="cash-development-target-100",
        stream_key="targets",
        event_type=backtest.TARGET_STREAM_EVENT_TYPE,
        capability=backtest.TARGET_STREAM_CAPABILITY,
        instrument_id=None,
        event_time=_TARGET_TIME,
        available_time=_TARGET_TIME,
        phase=TimelinePhase(30, "strategy_decision"),
        source_sequence=SourceSequence(1),
        revision_id="rev-1",
        supersedes_revision_id=None,
        source_key="cash-development.targets.v1",
        source_hash="sha256:" + "1" * 64,
        payload={
            "schema_version": 1,
            "candidate": {
                "schema_version": 1,
                "strategy_id": "trend-v1",
                "sleeve_id": "trend.primary",
                "decision_time": 100,
                "observed_through": 99,
                "effective_time": 100,
                "expires_at": 250,
                "targets": [
                    {
                        "instrument_id": {
                            "venue": _VENUE.value,
                            "stable_key": _INSTRUMENT.stable_key,
                        },
                        "value": "0.5",
                    }
                ],
                "confidence": "1",
                "reason": "public cash-development smoke",
                "evidence": {"model_revision": "sha256:cash-development-v1"},
            },
        },
    )


def bar_event() -> MarketEvent:
    return MarketEvent(
        event_id="cash-development-bar-200",
        stream_key="bars.open",
        event_type=backtest.BAR_OPEN_EVENT_TYPE,
        capability=backtest.BAR_OPEN_CAPABILITY,
        instrument_id=_INSTRUMENT,
        event_time=_BAR_TIME,
        available_time=_BAR_TIME,
        phase=TimelinePhase(60, "bar_open"),
        source_sequence=SourceSequence(2),
        revision_id="rev-1",
        supersedes_revision_id=None,
        source_key="cash-development.bar-open.v1",
        source_hash="sha256:" + "2" * 64,
        payload={
            "schema_version": 1,
            "bar_kind": "real",
            "open_price": {
                "units": 10_000,
                "scale": 2,
                "quote_currency": "USD",
            },
        },
    )


def quantity_lattice() -> QuantityLattice:
    return QuantityLattice.create(
        instrument_id=_INSTRUMENT,
        lattice_key="cash-development.lattice.v1",
        lattice_version=1,
        atomic_scale=Scale(3),
        step_units=1,
        buy_lot_units=1,
        sell_lot_units=1,
        min_quantity_units=1,
        min_notional=Money(100, Scale(2), "USD"),
        odd_lot_close_permitted=False,
    )


def capability_set() -> OrderCapabilitySet:
    return OrderCapabilitySet.create(
        capability_set_key="cash-development.capabilities.v1",
        capability_set_version=1,
        style_capabilities=(
            OrderStyleCapability(
                ExecutionStyle.MARKET,
                (PriceConstraintShape.NONE,),
                (TimeInForce.DAY,),
            ),
        ),
        supports_reduce_only=True,
        supported_position_effects=(
            PositionEffect.AUTO,
            PositionEffect.OPEN,
            PositionEffect.CLOSE,
        ),
        declared_capability_keys=tuple(value.value for value in OrderCapabilityKey),
    )


def build_manifest() -> backtest.BuildArtifactManifest:
    roles = (
        (backtest.BuildArtifactRole.DECISION_SOURCE, "precomputed-target-source", "1"),
        (backtest.BuildArtifactRole.TRADING_DOMAIN, "crypto-quant-domain", "2"),
        (backtest.BuildArtifactRole.TRADING_KERNEL, "crypto-quant-trading", "3"),
        (
            backtest.BuildArtifactRole.MARKET_DATA_CONTRACTS,
            "crypto-quant-market-data",
            "4",
        ),
        (backtest.BuildArtifactRole.BACKTEST_RUNTIME, "crypto-quant-backtest", "5"),
    )
    return backtest.BuildArtifactManifest(
        schema_version=1,
        build_key="cash-development.public-build.v1",
        artifacts=tuple(
            backtest.BuildArtifactRef(
                role=role,
                artifact_key=key,
                artifact_version="0.1.0",
                install_mode=backtest.ArtifactInstallMode.WHEEL,
                source_tree_state=backtest.SourceTreeState.CLEAN,
                content_hash="sha256:" + digit * 64,
                source_snapshot_hash=None,
            )
            for role, key, digit in roles
        ),
        dependency_lock_hash="sha256:" + "6" * 64,
        runtime_libraries=(
            backtest.RuntimeLibraryRef(
                library_key="python",
                version="3.13.5",
                content_hash="sha256:" + "7" * 64,
            ),
        ),
        container_image_digest=None,
        provenance=backtest.BuildProvenance(
            git_commit="0e481d4f9e06f073446749149756f38ea0054739",
            hostname="public-builder",
            source_root="/workspace/backtest",
            built_at=UtcInstant(1_000),
        ),
    )


class _Cas:
    def __init__(self, wrong_ref: ArtifactRef | None = None) -> None:
        self.by_ref: dict[ArtifactRef, ArtifactEnvelope] = {}
        self.wrong_ref = wrong_ref

    def put(self, *, envelope: ArtifactEnvelope) -> ArtifactRef:
        ref = ArtifactRef.from_envelope(envelope)
        self.by_ref[ref] = envelope
        return self.wrong_ref or ref

    def read(self, *, ref: ArtifactRef) -> ArtifactReadResult:
        envelope = self.by_ref[ref]
        source = canonical_bytes(envelope)
        return ArtifactReadResult(envelope, None, source, canonical_sha256(envelope))


class _DroppingCas(_Cas):
    def put(self, *, envelope: ArtifactEnvelope) -> ArtifactRef:
        return ArtifactRef.from_envelope(envelope)


class _SubstitutionCas(_Cas):
    def read(self, *, ref: ArtifactRef) -> ArtifactReadResult:
        substitute = ArtifactEnvelope.create(
            "backtest_request",
            1,
            {"type": "substituted_readback", "schema_version": 1},
        )
        source = canonical_bytes(substitute)
        return ArtifactReadResult(
            substitute,
            None,
            source,
            canonical_sha256(substitute),
        )


def _reader(target: MarketEvent | None = None) -> InMemoryMarketBundleReader:
    target = target or target_event()
    original = bar_event()
    bar = replace(
        original,
        payload={
            "schema_version": 1,
            "bar_kind": "real",
            "open_price": {
                "units": 10_000,
                "scale": 2,
                "quote_currency": "USD",
            },
        },
    )
    return InMemoryMarketBundleReader.build(
        bundle_key="cash-development-public-seam-v1",
        schema_version=1,
        coverage_start=UtcInstant(0),
        coverage_end_exclusive=UtcInstant(400),
        instrument_catalog_hash=canonical_sha256(catalog()),
        capabilities=(target.capability, bar.capability),
        streams={"targets": (target,), "bars.open": (bar,)},
    )


def _intent() -> backtest.CashDevelopmentRequestIntent:
    return backtest.CashDevelopmentRequestIntent(
        schema_version=1,
        experiment_id="platform:trial:cash-development-1",
        timeline_window=backtest.TimelineWindow(
            UtcInstant(0), UtcInstant(90), UtcInstant(300)
        ),
        execution_account_id="account:primary",
        reporting_currency=CurrencyId("USD"),
        master_random_seed=7,
    )


def _mark(units: int, at: int, source: str) -> MarkObservation:
    instrument = catalog().instruments[0].instrument_id
    return MarkObservation(
        instrument_id=instrument,
        quote_currency_id=CurrencyId("USD"),
        price_purpose=PricePurpose.VALUATION,
        price=Price(units, Scale(2), str(instrument), "USD"),
        observed_at=UtcInstant(at),
        available_at=UtcInstant(at),
        stream_id=f"marks.{source}",
        source_event_id=f"cash-development-{source}",
        revision_id="rev-1",
    )


def _inputs(manifest=None) -> backtest.CashDevelopmentProviderInputs:
    return backtest.CashDevelopmentProviderInputs(
        schema_version=1,
        build_artifact_manifest=manifest or build_manifest(),
        instrument_catalog=catalog(),
        strategy_id="trend-v1",
        sleeve_id=StrategySleeveId("trend.primary"),
        initial_cash=Money(100_000, Scale(2), "USD"),
        quantity_lattice=quantity_lattice(),
        decision_mark=_mark(10_000, 100, "decision"),
        final_mark=_mark(8_000, 299, "final"),
        order_capabilities=capability_set(),
    )


def _prepared(tmp_path: Path, *, cas: _Cas | None = None):
    reader = _reader()
    store = cas or _Cas()
    prepared = backtest.prepare_cash_development_backtest(
        request_intent=_intent(),
        provider_inputs=_inputs(),
        artifact_reader=store,
        artifact_publisher=store,
        market_reader=reader,
        publication_root=tmp_path,
    )
    return prepared, store


def test_cash_development_public_contract_is_additive_and_hides_resolved_types() -> None:
    names = (
        "CashDevelopmentRequestIntent",
        "BacktestRequestRef",
        "CashDevelopmentProviderInputs",
        "PreparedBacktestExecution",
        "prepare_cash_development_backtest",
    )
    for name in names:
        assert name in backtest.__all__, f"BT-GAP-09 RED: missing public {name}"

    intent = backtest.CashDevelopmentRequestIntent
    provider_inputs = backtest.CashDevelopmentProviderInputs
    request_ref = backtest.BacktestRequestRef
    prepared = backtest.PreparedBacktestExecution
    prepare = backtest.prepare_cash_development_backtest

    assert all(is_dataclass(value) for value in (intent, provider_inputs, request_ref, prepared))
    assert tuple(value.name for value in fields(intent)) == (
        "schema_version", "experiment_id", "timeline_window", "execution_account_id",
        "reporting_currency", "master_random_seed",
    )
    assert tuple(value.name for value in fields(provider_inputs)) == (
        "schema_version", "build_artifact_manifest", "instrument_catalog", "strategy_id",
        "sleeve_id", "initial_cash", "quantity_lattice", "decision_mark", "final_mark",
        "order_capabilities",
    )
    assert tuple(value.name for value in fields(request_ref)) == ("artifact_ref",)
    assert tuple(value.name for value in fields(prepared)) == (
        "request_ref", "semantic_run_id", "execution_request", "runtime",
    )
    prepare_parameters = tuple(signature(prepare).parameters.values())
    assert tuple(value.name for value in prepare_parameters) == (
        "request_intent", "provider_inputs", "artifact_reader", "artifact_publisher",
        "market_reader", "publication_root",
    )
    assert all(value.kind is Parameter.KEYWORD_ONLY for value in prepare_parameters)
    assert tuple(signature(backtest.BacktestRuntime.run_with_cancellation).parameters) == (
        "self", "request", "cancellation",
    )
    assert tuple(signature(backtest.BacktestRuntime.run).parameters) == ("self", "request")


def test_public_root_symbols_import_in_isolated_interpreter(tmp_path: Path) -> None:
    command = (
        "from crypto_quant_backtest import "
        "BacktestRequestRef, CashDevelopmentProviderInputs, "
        "CashDevelopmentRequestIntent, PreparedBacktestExecution, "
        "prepare_cash_development_backtest"
    )

    completed = subprocess.run(
        [sys.executable, "-I", "-c", command],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


def test_preparation_persists_exact_request_and_derives_executable_v2(tmp_path: Path) -> None:
    prepared, store = _prepared(tmp_path)

    request_envelope = store.by_ref[prepared.request_ref.artifact_ref]
    assert request_envelope.artifact_type == "backtest_request"
    assert request_envelope.schema_version == 1
    assert canonical_bytes(request_envelope.payload) == canonical_bytes(
        prepared.execution_request.request
    )
    assert prepared.execution_request.schema_version == 2
    assert prepared.semantic_run_id.startswith("run_")
    assert prepared.execution_request.request.experiment_id == _intent().experiment_id
    assert prepared.execution_request.request.execution_case_semantic_hash.startswith("sha256:")
    assert prepared.execution_request.request.target_stream_digest.startswith("sha256:")


def test_provider_deterministically_extends_base_build_manifest(tmp_path: Path) -> None:
    first, first_store = _prepared(tmp_path / "first")
    second, second_store = _prepared(tmp_path / "second")
    first_payload = first_store.by_ref[
        first.execution_request.execution_input_bundle_ref
    ].payload["build_artifact_manifest"]
    second_payload = second_store.by_ref[
        second.execution_request.execution_input_bundle_ref
    ].payload["build_artifact_manifest"]
    first_artifacts = first_payload["identity"]["artifacts"]
    provider_prefix = "cash.precomputed_target.development.v1."
    provider_artifacts = tuple(
        value
        for value in first_artifacts
        if value["role"] == "profile_component"
        and value["artifact_key"].startswith(provider_prefix)
    )

    assert first_payload == second_payload
    assert first.execution_request.request.build_artifact_manifest_hash == (
        first_payload["manifest_hash"]
    )
    assert first.execution_request.request.build_artifact_manifest_hash != (
        _inputs().build_artifact_manifest.manifest_hash
    )
    assert tuple(value["artifact_key"] for value in provider_artifacts) == (
        f"{provider_prefix}account",
        f"{provider_prefix}market",
        f"{provider_prefix}simulation",
    )
    assert all(
        value["artifact_version"] == "1"
        and value["install_mode"] == "wheel"
        and value["source_tree_state"] == "clean"
        and value["source_snapshot_hash"] is None
        and value["content_hash"].startswith("sha256:")
        for value in provider_artifacts
    )
    base_artifacts = tuple(
        value.to_canonical_dict()
        for value in _inputs().build_artifact_manifest.artifacts
    )
    assert all(value in first_artifacts for value in base_artifacts)
    assert canonical_bytes(first_payload["provenance"]) == canonical_bytes(
        _inputs().build_artifact_manifest.provenance
    )


@pytest.mark.parametrize(
    "role",
    (
        backtest.BuildArtifactRole.PROFILE_COMPONENT,
        backtest.BuildArtifactRole.DECISION_SOURCE,
    ),
)
def test_conflicting_provider_profile_artifact_fails_before_publication(
    tmp_path: Path,
    role: backtest.BuildArtifactRole,
) -> None:
    inputs = _inputs()
    conflict = backtest.BuildArtifactRef(
        role=role,
        artifact_key="cash.precomputed_target.development.v1.market",
        artifact_version="1",
        install_mode=backtest.ArtifactInstallMode.WHEEL,
        source_tree_state=backtest.SourceTreeState.CLEAN,
        content_hash="sha256:" + "0" * 64,
        source_snapshot_hash=None,
    )
    conflicting_manifest = replace(
        inputs.build_artifact_manifest,
        artifacts=inputs.build_artifact_manifest.artifacts + (conflict,),
    )
    reader = _reader()
    store = _Cas()

    with pytest.raises(ValueError, match="conflicts with provider profile keys"):
        backtest.prepare_cash_development_backtest(
            request_intent=_intent(),
            provider_inputs=replace(
                inputs,
                build_artifact_manifest=conflicting_manifest,
            ),
            artifact_reader=store,
            artifact_publisher=store,
            market_reader=reader,
            publication_root=tmp_path,
        )

    assert store.by_ref == {}
    assert not (tmp_path / "runs").exists()


@pytest.mark.parametrize("store", (_DroppingCas(), _SubstitutionCas()))
def test_preparation_readback_failure_returns_no_authority_or_attempt(
    tmp_path: Path,
    store: _Cas,
) -> None:
    with pytest.raises(
        ValueError,
        match="published artifact readback",
    ):
        backtest.prepare_cash_development_backtest(
            request_intent=_intent(),
            provider_inputs=_inputs(),
            artifact_reader=store,
            artifact_publisher=store,
            market_reader=_reader(),
            publication_root=tmp_path,
        )

    assert not (tmp_path / "runs").exists()


def test_completed_run_is_replay_stable_and_has_one_fill_with_adverse_return(tmp_path: Path) -> None:
    prepared, store = _prepared(tmp_path)

    first = prepared.runtime.run(prepared.execution_request)
    second = prepared.runtime.run(prepared.execution_request)

    assert type(first) is backtest.BacktestCanonicalPublicationRef
    assert second == first
    verified = backtest.BacktestEvidenceRepository(reader=store).load_completed(first)
    summary = verified.execution_summary
    assert verified.semantic_run_id == prepared.semantic_run_id
    assert len(summary.fills) == 1
    assert summary.final_journal.entry_count == 2
    assert summary.final_portfolio_snapshot.equity == Money(90_000, Scale(2), "USD")
    assert summary.final_portfolio_snapshot.fees == Money(0, Scale(2), "USD")

    profile = backtest.BacktestMetricProfile(
        "simple_period_return.fill_count.v1",
        1,
    )
    profile_envelope = ArtifactEnvelope.create(
        "backtest_metric_profile",
        1,
        profile,
    )
    profile_ref = store.put(envelope=profile_envelope)
    analysis_runtime = backtest.BacktestAnalysisRuntime(store)
    first_analysis = analysis_runtime.derive(verified, profile_ref)
    second_analysis = analysis_runtime.derive(verified, profile_ref)
    loaded_analysis = backtest.BacktestEvidenceRepository(
        reader=store
    ).load_analysis(first_analysis)

    assert second_analysis == first_analysis
    assert loaded_analysis.simple_period_return == "-0.1"
    assert loaded_analysis.trade_count == 1
    assert loaded_analysis.result_grade.value == "development"
    assert loaded_analysis.metric_profile_ref == profile_ref
    assert loaded_analysis.source_publication_ref == first
    assert loaded_analysis.source_execution_result_hash == (
        verified.source_execution_result_hash
    )


def test_missing_market_capability_is_real_blocked(tmp_path: Path) -> None:
    reader = _reader()
    provider_inputs = _inputs()
    original = provider_inputs.order_capabilities
    no_market = OrderCapabilitySet.create(
        capability_set_key=original.capability_set_key,
        capability_set_version=original.capability_set_version,
        style_capabilities=(),
        supports_reduce_only=original.supports_reduce_only,
        supported_position_effects=original.supported_position_effects,
        declared_capability_keys=original.declared_capability_keys,
    )
    store = _Cas()
    prepared = backtest.prepare_cash_development_backtest(
        request_intent=_intent(),
        provider_inputs=replace(provider_inputs, order_capabilities=no_market),
        artifact_reader=store,
        artifact_publisher=store,
        market_reader=reader,
        publication_root=tmp_path,
    )

    ref = prepared.runtime.run(prepared.execution_request)
    repeated = prepared.runtime.run(prepared.execution_request)
    cancellation_after_terminal = prepared.runtime.run_with_cancellation(
        prepared.execution_request,
        backtest.EngineCancellationRequest(
            cancel_before_event_id=target_event().event_id,
            reason_code="ignored_after_terminal",
        ),
    )

    assert type(ref) is ArtifactRef
    assert repeated == ref
    assert cancellation_after_terminal == ref
    terminal = backtest.BacktestEvidenceRepository(reader=store).load_terminal(ref)
    assert terminal.status.value == "BLOCKED"


def test_cancellation_is_durable_and_run_signature_remains_unchanged(tmp_path: Path) -> None:
    prepared, store = _prepared(tmp_path)
    cancel = backtest.EngineCancellationRequest(
        cancel_before_event_id=target_event().event_id,
        reason_code="platform_cancelled",
    )

    ref = prepared.runtime.run_with_cancellation(prepared.execution_request, cancel)
    repeated = prepared.runtime.run_with_cancellation(
        prepared.execution_request,
        cancel,
    )
    ordinary_after_terminal = prepared.runtime.run(prepared.execution_request)

    assert type(ref) is ArtifactRef
    assert repeated == ref
    assert ordinary_after_terminal == ref
    terminal = backtest.BacktestEvidenceRepository(reader=store).load_terminal(ref)
    assert terminal.status.value == "CANCELLED"


def test_cancellation_after_completed_cache_fails_closed(tmp_path: Path) -> None:
    prepared, _ = _prepared(tmp_path)
    completed = prepared.runtime.run(prepared.execution_request)
    assert type(completed) is backtest.BacktestCanonicalPublicationRef

    with pytest.raises(RuntimeError, match="completed semantic run cannot be cancelled"):
        prepared.runtime.run_with_cancellation(
            prepared.execution_request,
            backtest.EngineCancellationRequest(
                cancel_before_event_id=target_event().event_id,
                reason_code="too_late",
            ),
        )


def test_terminal_replay_rejects_cross_run_manifest_substitution(tmp_path: Path) -> None:
    store = _Cas()
    reader = _reader()
    first = backtest.prepare_cash_development_backtest(
        request_intent=_intent(),
        provider_inputs=_inputs(),
        artifact_reader=store,
        artifact_publisher=store,
        market_reader=reader,
        publication_root=tmp_path,
    )
    second = backtest.prepare_cash_development_backtest(
        request_intent=replace(_intent(), experiment_id="platform:trial:cash-development-2"),
        provider_inputs=_inputs(),
        artifact_reader=store,
        artifact_publisher=store,
        market_reader=reader,
        publication_root=tmp_path,
    )
    cancel = backtest.EngineCancellationRequest(
        cancel_before_event_id=target_event().event_id,
        reason_code="platform_cancelled",
    )
    first.runtime.run_with_cancellation(first.execution_request, cancel)
    second.runtime.run_with_cancellation(second.execution_request, cancel)

    first_attempt = backtest.AttemptIdentity.first(first.semantic_run_id)
    second_attempt = backtest.AttemptIdentity.first(second.semantic_run_id)
    first_manifest = (
        tmp_path
        / "runs"
        / first.semantic_run_id
        / "attempts"
        / first_attempt.attempt_id
        / "evidence-manifest.json"
    )
    second_manifest = (
        tmp_path
        / "runs"
        / second.semantic_run_id
        / "attempts"
        / second_attempt.attempt_id
        / "evidence-manifest.json"
    )
    first_manifest.chmod(0o600)
    first_manifest.write_bytes(second_manifest.read_bytes())

    with pytest.raises(RuntimeError, match="terminal Attempt identity mismatch"):
        first.runtime.run(first.execution_request)


def test_negative_target_is_rejected_before_publication_or_attempt(tmp_path: Path) -> None:
    event = target_event()
    candidate = dict(event.payload["candidate"])
    target = dict(candidate["targets"][0])
    target["value"] = "-0.5"
    candidate["targets"] = (target,)
    reader = _reader(
        replace(event, payload={"schema_version": 1, "candidate": candidate})
    )
    store = _Cas()

    with pytest.raises(ValueError, match="one positive long order"):
        backtest.prepare_cash_development_backtest(
            request_intent=_intent(),
            provider_inputs=_inputs(),
            artifact_reader=store,
            artifact_publisher=store,
            market_reader=reader,
            publication_root=tmp_path,
        )

    assert store.by_ref == {}
    assert not (tmp_path / "runs").exists()


def test_preparation_ref_mismatch_returns_no_authority_or_attempt(tmp_path: Path) -> None:
    wrong = ArtifactRef("backtest_request", 1, "sha256:" + "0" * 64)
    store = _Cas(wrong)
    reader = _reader()

    with pytest.raises(ValueError, match="returned ref does not bind envelope"):
        backtest.prepare_cash_development_backtest(
            request_intent=_intent(),
            provider_inputs=_inputs(),
            artifact_reader=store,
            artifact_publisher=store,
            market_reader=reader,
            publication_root=tmp_path,
        )

    assert not (tmp_path / "runs").exists()
