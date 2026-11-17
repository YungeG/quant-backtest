"""Exact V2 source, definition and plan/case/input9 version closure."""
from dataclasses import fields, replace
import inspect
import json

import pytest
import crypto_quant_domain as d
import crypto_quant_trading as t
from crypto_quant_backtest import CnASharePortfolioEconomicDevelopmentInputsV2 as Inputs
from crypto_quant_backtest.cn_a_share_portfolio_economic_definition_v1 import (
    CnASharePortfolioEconomicDevelopmentInputsV1, _read_economic_definition_v1,
    _read_economic_source_fields_v1,
)
from crypto_quant_backtest.cn_a_share_portfolio_economic_definition_v2 import (
    _read_economic_definition_v2 as read, _read_activation_stale_policy_v2,
)
from crypto_quant_backtest.cn_a_share_portfolio_economic_activation_v2 import (
    _economic_activation_at_v2, _economic_activation_value_v2, _economic_financial_checkpoints_v2,
    _resolve_retained_economic_marks_v2, _retained_economic_decision_v2, _EconomicMarkResolutionFailureV2,
)
from crypto_quant_backtest.cn_a_share_portfolio_economic_native_state_v1 import _EconomicNativeFailureV1
from crypto_quant_backtest.cn_a_share_portfolio_standard_definition_v1 import CnASharePortfolioMarkBatchDevelopmentV1 as Batch
from crypto_quant_backtest.target_stream import PrecomputedTargetStream
from tests.runtime.providers._cn_a_share_portfolio_economic_fixtures_v2 import economic_public_sources_v2


@pytest.fixture(scope="module")
def source():
    return economic_public_sources_v2()[0]


def _kwargs(source):
    return {f.name: getattr(source, f.name) for f in fields(Inputs) if f.init}


def _at(source, rank):
    return d.SimulationInstant(source.initial_marks.at.instant, d.TimelinePhase(rank, "cn_economic_native"), d.SourceSequence(0))


def _reclock(batch, at):
    return Batch(at, tuple(replace(m, resolved_at=at.instant,
        age_nanoseconds=at.instant.epoch_nanoseconds - m.observed_at.epoch_nanoseconds,
        resolved_at_instant=at) for m in batch.marks))


def test_v2_exact_public14_from_sources_and_bounded_sources(source):
    expected = ("scope", "source_target_stream", "initial_journal", "calendars", "execution_policy",
        "opening_terms", "initial_marks", "retained_signal_marks", "daily_marks", "checkpoint_marks",
        "cost_basis_policy", "notional_quantization", "dividend_actions", "activation_stale_policy")
    assert tuple(f.name for f in fields(Inputs) if f.init) == expected
    signature = inspect.signature(Inputs.from_sources)
    assert tuple(signature.parameters) == expected
    assert all(p.kind is inspect.Parameter.KEYWORD_ONLY for p in signature.parameters.values())
    assert all(not f.init for f in fields(Inputs) if f.name.startswith("_") or f.name.endswith("verified") or f.name == "trade_authorized")
    assert len(source.to_canonical_dict()) == 19 and source.to_canonical_dict()["schema_version"] == 2
    assert not hasattr(source, "signal_marks") and not isinstance(source, CnASharePortfolioEconomicDevelopmentInputsV1)
    assert not source.trade_authorized and not source.source_qualification_verified and not source.broker_shared_pool_verified
    assert d.canonical_bytes(Inputs(**_kwargs(source))) == d.canonical_bytes(Inputs.from_sources(**_kwargs(source)))
    class Derived(Inputs):
        pass
    with pytest.raises(TypeError, match="exact public class"):
        Derived.from_sources(**_kwargs(source))
    with pytest.raises(TypeError, match="exact public class"):
        Derived(**_kwargs(source))
    with pytest.raises(TypeError):
        replace(source, trade_authorized=True)


@pytest.mark.parametrize("mutation", ["zero", "two", "active", "available", "hour", "phase", "batch_clock", "batch_count",
    "scope", "calendars", "opening_duplicate", "opening_empty", "daily_duplicate", "capital", "action_start", "actions", "native_type"])
def test_v2_bounded_source_refusals(source, mutation):
    event = source.source_target_stream.events[0]
    change = {}
    if mutation == "zero":
        change["source_target_stream"] = PrecomputedTargetStream("targets", ())
    elif mutation == "two":
        second = replace(event, event_id=event.event_id + ".extra", source_sequence=d.SourceSequence(2))
        change["source_target_stream"] = PrecomputedTargetStream("targets", (event, second))
    elif mutation in ("active", "available", "hour", "phase"):
        if mutation == "active":
            at = source.initial_marks.at.instant
            event = replace(event, event_time=at, available_time=at)
        elif mutation == "available":
            event = replace(event, available_time=d.UtcInstant(event.available_time.epoch_nanoseconds + 1))
        elif mutation == "hour":
            at = d.UtcInstant(event.event_time.epoch_nanoseconds - 3_600_000_000_000)
            event = replace(event, event_time=at, available_time=at)
        else:
            event = replace(event, phase=d.TimelinePhase(30, "economic_target_source"))
        change["source_target_stream"] = PrecomputedTargetStream("targets", (event,))
    elif mutation == "batch_clock":
        at = replace(source.retained_signal_marks[0].at, source_sequence=d.SourceSequence(2))
        change["retained_signal_marks"] = (_reclock(source.retained_signal_marks[0], at),)
    elif mutation == "batch_count":
        change["retained_signal_marks"] = source.retained_signal_marks * 2
    elif mutation == "scope":
        change["retained_signal_marks"] = (replace(source.retained_signal_marks[0], marks=source.retained_signal_marks[0].marks[:1]),)
    elif mutation == "calendars":
        change["calendars"] = source.calendars[::-1]
    elif mutation == "opening_duplicate":
        change["opening_terms"] = source.opening_terms * 2
    elif mutation == "opening_empty":
        change["opening_terms"] = ()
    elif mutation == "daily_duplicate":
        change["daily_marks"] = source.daily_marks * 2
    elif mutation == "capital":
        change["scope"] = replace(source.scope, initial_cash=replace(source.scope.initial_cash, units=1))
    elif mutation == "action_start":
        change["dividend_actions"] = replace(source.dividend_actions, coverage_start=event.event_time)
    elif mutation == "actions":
        from tests.runtime.providers._cn_a_share_portfolio_economic_fixtures_v1 import economic_public_sources_v1
        actions = economic_public_sources_v1()[0].dividend_actions.actions
        change["dividend_actions"] = replace(source.dividend_actions, actions=actions)
    else:
        change["initial_journal"] = object()
    with pytest.raises((ValueError, TypeError)):
        replace(source, **change)
    with pytest.raises((ValueError, TypeError)):
        Inputs.from_sources(**{**_kwargs(source), **change})


def test_v2_source_derived_marks_and_checkpoint_collisions(source):
    clocks = (source.initial_marks.at, _economic_activation_at_v2(source), _at(source, 45))
    derived = tuple(_resolve_retained_economic_marks_v2(source, at) for at in clocks)
    assert d.canonical_bytes(derived[0]) == d.canonical_bytes(source.initial_marks)
    assert len({d.canonical_sha256(b) for b in derived}) == 3
    original = source.retained_signal_marks[0].marks
    for batch in derived:
        for old, mark in zip(original, batch.marks, strict=True):
            assert mark.age_nanoseconds == 9 * 3_600_000_000_000
            assert mark.observed_at == old.observed_at and mark.available_at == old.available_at
            assert mark.available_at_instant == old.available_at_instant
            assert (mark.price, mark.stream_id, mark.source_event_id, mark.revision_id) == (old.price, old.stream_id, old.source_event_id, old.revision_id)
            assert mark.stale_policy_hash == source.activation_stale_policy.policy_hash
    checkpoints = _economic_financial_checkpoints_v2(source)
    assert len(checkpoints) == len(source.checkpoint_marks) + 1
    assert tuple(b.at for b in checkpoints) == tuple(sorted((*[b.at for b in source.checkpoint_marks], clocks[2])))
    assert set(b.at.phase.rank for b in checkpoints) == {45, 49, 55, 67, 97, 200}
    assert all(b.at.instant >= source.initial_marks.at.instant for b in checkpoints)
    assert len(source.checkpoint_marks) == 9


@pytest.mark.parametrize("mutation", ["age_minus_ns", "no_forward_fill", "purpose", "policy_substitution", "initial_source", "initial_policy", "initial_price", "retained_source", "retained_missing"])
def test_v2_native_policy_and_provenance_refusals(source, mutation):
    change = {}
    if mutation in ("age_minus_ns", "no_forward_fill", "purpose", "policy_substitution"):
        policy = source.activation_stale_policy
        args = {"age_minus_ns": {"max_age_nanoseconds": policy.max_age_nanoseconds - 1},
            "no_forward_fill": {"allow_forward_fill": False}, "purpose": {"price_purpose": d.PricePurpose.EXECUTION_REFERENCE},
            "policy_substitution": {"policy_key": policy.policy_key + ".substituted"}}[mutation]
        change["activation_stale_policy"] = replace(policy, **args)
    elif mutation.startswith("initial"):
        mark = source.initial_marks.marks[0]
        args = {"initial_source": {"source_event_id": mark.source_event_id + ".substituted"},
            "initial_policy": {"stale_policy_hash": d.canonical_sha256("substituted")},
            "initial_price": {"price": replace(mark.price, units=mark.price.units + 1)}}[mutation]
        change["initial_marks"] = replace(source.initial_marks, marks=(replace(mark, **args), *source.initial_marks.marks[1:]))
    elif mutation == "retained_source":
        batch = source.retained_signal_marks[0]
        change["retained_signal_marks"] = (replace(batch, marks=(replace(batch.marks[0], revision_id="substituted"), *batch.marks[1:])),)
    else:
        change["retained_signal_marks"] = ()
    with pytest.raises(ValueError) as caught:
        replace(source, **change)
    if mutation in ("age_minus_ns", "no_forward_fill"):
        failure = caught.value
        assert type(failure) is _EconomicMarkResolutionFailureV2
        assert type(failure.failure) is t.MarkResolutionFailure
        assert failure.failure.code is t.MarkResolutionFailureCode.STALE_MARK
        assert failure.requested_at == source.initial_marks.at
        assert failure.failure.stale_policy_hash == change["activation_stale_policy"].policy_hash
        assert d.canonical_sha256(failure.failure) in str(failure)


@pytest.mark.parametrize("clock", ["initial", "activation", "coordinator", "source", "source45", "daily", "prestart", "duplicate"])
@pytest.mark.parametrize("conflicting", [False, True])
def test_v2_rejects_equal_and_conflicting_caller_checkpoint_authority(source, clock, conflicting):
    if clock == "duplicate":
        batch = source.checkpoint_marks[0]
    elif clock == "initial":
        batch = source.initial_marks
    elif clock in ("activation", "coordinator"):
        batch = _resolve_retained_economic_marks_v2(source, _at(source, 30 if clock == "activation" else 45))
    elif clock == "daily":
        batch = source.daily_marks[0]
    else:
        batch = source.retained_signal_marks[0]
        if clock == "source45":
            batch = _reclock(batch, d.SimulationInstant(batch.at.instant, d.TimelinePhase(45, "cn_economic_native"), d.SourceSequence(0)))
        elif clock == "prestart":
            batch = _reclock(batch, replace(batch.at, phase=d.TimelinePhase(44, "other_prestart")))
    if conflicting:
        batch = replace(batch, marks=(replace(batch.marks[0], price=replace(batch.marks[0].price, units=batch.marks[0].price.units + 1)), *batch.marks[1:]))
    checkpoints = tuple(sorted((*source.checkpoint_marks, batch), key=lambda b: b.at))
    with pytest.raises(ValueError):
        replace(source, checkpoint_marks=checkpoints)


@pytest.mark.parametrize("mutation", ["duplicate", "future_utc", "future_fullclock", "wrong_purpose", "age"])
def test_v2_native_mark_batch_rejects_malformed_original_observations(source, mutation):
    batch = source.retained_signal_marks[0]
    mark = batch.marks[0]
    with pytest.raises((TypeError, ValueError)):
        if mutation == "duplicate":
            replace(batch, marks=(mark, *batch.marks))
        elif mutation == "future_utc":
            future = d.UtcInstant(mark.available_at.epoch_nanoseconds + 1)
            replace(batch, marks=(replace(mark, available_at=future), *batch.marks[1:]))
        elif mutation == "future_fullclock":
            at = replace(batch.at, source_sequence=d.SourceSequence(batch.at.source_sequence.value + 1))
            replace(batch, marks=(replace(mark, available_at_instant=at), *batch.marks[1:]))
        elif mutation == "wrong_purpose":
            replace(batch, marks=(replace(mark, price_purpose=d.PricePurpose.EXECUTION_REFERENCE), *batch.marks[1:]))
        else:
            replace(batch, marks=(replace(mark, age_nanoseconds=1), *batch.marks[1:]))


@pytest.mark.parametrize("rank,code,sequence", [(30, "wrong", 0), (30, "cn_economic_native", 1), (45, "wrong", 0), (40, "cn_economic_native", 0)])
def test_v2_mark_resolution_requires_the_whole_consumer_clock(source, rank, code, sequence):
    at = d.SimulationInstant(source.initial_marks.at.instant, d.TimelinePhase(rank, code), d.SourceSequence(sequence))
    with pytest.raises(ValueError, match="exact initial0"):
        _resolve_retained_economic_marks_v2(source, at)


def test_v2_pure_original_collection_activation_value_and_no_financial_calls(source, monkeypatch):
    from crypto_quant_backtest import cn_a_share_portfolio_economic_native_state_v1 as state
    def forbidden(*args, **kwargs):
        pytest.fail("source-only construction must not project or allocate finance")
    monkeypatch.setattr(state, "_economic_projection_at_v1", forbidden)
    monkeypatch.setattr(t.PortfolioAllocator, "allocate", forbidden)
    monkeypatch.setattr(t.PositionSizer, "materialize", forbidden)
    same = Inputs.from_sources(**_kwargs(source))
    result = _retained_economic_decision_v2(same)
    event = source.source_target_stream.events[0]
    source_at = d.SimulationInstant(event.event_time, event.phase, event.source_sequence)
    assert type(result) is t.AtomicDecisionBatchResult
    assert result.batch.decision_instant == source_at and result.state.as_of_instant == source_at
    decision = result.batch.decisions[0]
    assert decision.decision_time == event.event_time
    assert decision.target_snapshot.effective_time == event.event_time
    assert decision.target_snapshot.expires_at is None
    activation = _economic_activation_value_v2(source, event)
    assert len(fields(type(activation))) == 8 and len(activation.to_canonical_dict()) == 10
    assert activation.source_at == source_at and activation.activation_at == _at(source, 30)
    assert activation.source_target_stream_digest == source.source_target_stream.target_stream_digest
    assert activation.source_event_hash == event.event_hash
    assert activation.retained_signal_marks_hash == d.canonical_sha256(source.retained_signal_marks[0])
    assert activation.activation_marks_hash == d.canonical_sha256(_resolve_retained_economic_marks_v2(source, _at(source, 30)))
    with pytest.raises(ValueError, match="exact original"):
        _economic_activation_value_v2(source, replace(event, event_id="not-original"))


@pytest.mark.parametrize("mutation,operation", [("decode", "target_decode"), ("validation", "target_validation"), ("weights", None)])
def test_v2_source_native_rejection_retains_actual_native_cause(source, mutation, operation):
    event = source.source_target_stream.events[0]
    payload = json.loads(d.canonical_bytes(event.payload))
    if mutation == "decode":
        payload["schema_version"] = 999
    elif mutation == "validation":
        payload["candidate"]["targets"][0]["instrument_id"]["stable_key"] = "not-in-scope"
    else:
        payload["candidate"]["targets"][0]["value"] = "0.4"
    event = replace(event, payload=payload)
    with pytest.raises(ValueError) as caught:
        replace(source, source_target_stream=PrecomputedTargetStream("targets", (event,)))
    if operation is not None:
        cause = caught.value.__cause__
        assert type(cause) is _EconomicNativeFailureV1 and cause.operation == operation
        assert cause.evidence is not None and cause.evidence_hash == d.canonical_sha256(cause.evidence)
        assert cause.original_claim == {"event": event}
        assert cause.__cause__ is None
        if operation == "target_validation":
            native = t.StrategyOutputValidator().validate(**cause.native_inputs)
            assert type(cause.evidence) is t.StrategyValidationFailure
            assert d.canonical_bytes(cause.evidence) == d.canonical_bytes(native.failure)
            assert cause.native_inputs["context"].decision_instant == source.retained_signal_marks[0].at
            from crypto_quant_backtest.target_stream import PrecomputedTargetStreamAdapter
            candidate, issues = PrecomputedTargetStreamAdapter()._decode(event)
            assert not issues and candidate == cause.native_inputs["candidate"]
    else:
        assert "equal-weight" in str(caught.value) and caught.value.__cause__ is None


@pytest.mark.parametrize("policy", ["cash", "expires_at_activation", "effective_after_activation"])
def test_v2_source_collection_retains_cash_and_original_effective_expiry_for_later_native_activation(source, policy):
    event = source.source_target_stream.events[0]
    payload = json.loads(d.canonical_bytes(event.payload))
    candidate = payload["candidate"]
    if policy == "cash":
        candidate["targets"] = []
    elif policy == "expires_at_activation":
        candidate["expires_at"] = source.initial_marks.at.instant.epoch_nanoseconds
    else:
        candidate["effective_time"] = source.initial_marks.at.instant.epoch_nanoseconds + 1
    event = replace(event, payload=payload)
    changed = replace(source, source_target_stream=PrecomputedTargetStream("targets", (event,)))
    batch = _retained_economic_decision_v2(changed).batch
    decision = batch.decisions[0]
    assert batch.decision_instant == source.retained_signal_marks[0].at
    assert decision.target_snapshot.effective_time.epoch_nanoseconds == candidate["effective_time"]
    assert (None if decision.target_snapshot.expires_at is None else decision.target_snapshot.expires_at.epoch_nanoseconds) == candidate["expires_at"]
    if policy == "cash":
        assert not decision.target_snapshot.targets


def test_v2_definition3_roundtrip_and_v1_immutability(source):
    assert source.definition().schema_version == 3 and len(source.economic_payload()) == 19
    assert "target_stream_ref" not in source.economic_payload()["scope"]
    assert "source_target_stream" not in source.economic_payload()
    decoded = read(source.definition(), source.scope.target_stream_ref, source.dividend_actions, source.source_target_stream)
    assert type(decoded) is Inputs and d.canonical_bytes(decoded) == d.canonical_bytes(source)
    assert decoded.definition() == source.definition()
    with pytest.raises(TypeError):
        _read_economic_definition_v1(source.definition(), source.scope.target_stream_ref, source.dividend_actions)
    from tests.runtime.providers._cn_a_share_portfolio_economic_fixtures_v1 import economic_definition_source_v1
    old = economic_definition_source_v1()
    with pytest.raises(TypeError):
        read(old.definition(), old.scope.target_stream_ref, old.dividend_actions, source.source_target_stream)
    values = _read_economic_source_fields_v1(json.loads(d.canonical_bytes(old.economic_payload())), old.scope.target_stream_ref, signal_field="signal_marks")
    assert len(values) == 11 and values["signal_marks"] == old.signal_marks
    assert _read_economic_definition_v1(old.definition(), old.scope.target_stream_ref, old.dividend_actions).definition() == old.definition()


@pytest.mark.parametrize("mutation", ["missing", "extra", "schema_bool", "schema1", "flag", "action_hash", "source_hash", "scope_ref", "policy_extra", "policy_bool", "mark_clock", "mark_extra", "envelope2", "envelope4"])
def test_v2_definition_reader_refuses_cross_versions_and_rehashed_substitutions(source, mutation):
    raw = json.loads(d.canonical_bytes(source.economic_payload()))
    version = 3
    if mutation == "missing":
        del raw["checkpoint_marks"]
    elif mutation == "extra":
        raw["activation_at"] = _at(source, 30).to_canonical_dict()
    elif mutation == "schema_bool":
        raw["schema_version"] = True
    elif mutation == "schema1":
        raw["schema_version"] = 1
    elif mutation == "flag":
        raw["trade_authorized"] = 0
    elif mutation in ("action_hash", "source_hash"):
        raw["cash_dividend_action_set_hash" if mutation == "action_hash" else "source_target_stream_digest"] = d.canonical_sha256("substituted")
    elif mutation == "scope_ref":
        raw["scope"]["target_stream_ref"] = source.scope.target_stream_ref.to_canonical_dict()
    elif mutation == "policy_extra":
        raw["activation_stale_policy"]["schema_version"] = 1
    elif mutation == "policy_bool":
        raw["activation_stale_policy"]["policy_version"] = True
    elif mutation == "mark_clock":
        del raw["retained_signal_marks"][0]["marks"][0]["available_at_instant"]
    elif mutation == "mark_extra":
        raw["initial_marks"]["marks"][0]["qualified"] = True
    else:
        version = 2 if mutation == "envelope2" else 4
    envelope = d.ArtifactEnvelope.create("backtest_profile_portfolio_definition", version, raw)
    with pytest.raises((ValueError, TypeError)):
        read(envelope, source.scope.target_stream_ref, source.dividend_actions, source.source_target_stream)


def test_v1_legacy_validation_failure_is_not_silently_repaired(source):
    from crypto_quant_backtest.cn_a_share_portfolio_economic_native_state_v1 import _collect_economic_decision_v1
    from tests.runtime.providers._cn_a_share_portfolio_economic_fixtures_v1 import economic_public_sources_v1
    old, _, _, _, target, _ = economic_public_sources_v1()
    event = target.events[0]
    payload = json.loads(d.canonical_bytes(event.payload))
    payload["candidate"]["targets"][0]["instrument_id"]["stable_key"] = "not-in-scope"
    event = replace(event, payload=payload)
    with pytest.raises(d.CanonicalizationError, match="unsupported canonical type StrategyValidationResult"):
        _collect_economic_decision_v1(inputs=old, event=event, original_claim={"event": event})


def test_v2_collection_rejection_retains_actual_native_failure_and_call(source, monkeypatch):
    # Exercise the normally unreachable collector refusal with a real native
    # validated decision at a foreign clock, not a fabricated failure/result.
    from crypto_quant_backtest.cn_a_share_portfolio_economic_native_state_v1 import _collect_economic_decision_v1
    from crypto_quant_backtest.target_stream import PrecomputedTargetStreamAdapter
    event = source.source_target_stream.events[0]
    at = source.retained_signal_marks[0].at
    later = replace(at, source_sequence=d.SourceSequence(at.source_sequence.value + 1))
    candidate, issues = PrecomputedTargetStreamAdapter()._decode(event)
    assert not issues
    context = t.StrategyOutputValidationContext(expected_strategy_id="cn.native.live",
        expected_sleeve_id=d.StrategySleeveId("pharma"), decision_time=at.instant,
        instrument_catalog=source.scope.instrument_catalog, universe=source.scope.instrument_ids, decision_instant=later)
    validated = t.StrategyOutputValidator().validate(candidate, context)
    assert validated.decision is not None
    monkeypatch.setattr(t.StrategyOutputValidator, "validate", lambda self, candidate, context: validated)
    with pytest.raises(ValueError) as caught:
        Inputs.from_sources(**_kwargs(source))
    cause = caught.value.__cause__
    assert type(cause) is _EconomicNativeFailureV1 and cause.operation == "decision_batch_collection"
    assert type(cause.evidence) is t.DecisionBatchFailure
    native = t.AtomicDecisionBatchCollector().collect(**cause.native_inputs)
    assert native.batch is None and d.canonical_bytes(cause.evidence) == d.canonical_bytes(native.failure)
    assert cause.evidence_hash == d.canonical_sha256(native.failure)
    assert cause.original_claim == {"event": event} and cause.__cause__ is None
    assert cause.native_inputs["decision_time"] == event.event_time
    assert cause.native_inputs["decision_instant"] == at
    assert cause.native_inputs["expected"] == (t.DecisionBatchExpectation("cn.native.live", d.StrategySleeveId("pharma")),)
    assert cause.native_inputs["submissions"] == (t.DecisionBatchSubmission(cause.native_inputs["expected"][0], validated),)
    # The exact old class still hands the noncanonical result to its old wrapper.
    from tests.runtime.providers._cn_a_share_portfolio_economic_fixtures_v1 import economic_definition_source_v1
    old = economic_definition_source_v1()
    with pytest.raises(d.CanonicalizationError, match="unsupported canonical type AtomicDecisionBatchResult"):
        _collect_economic_decision_v1(inputs=old, event=event, original_claim={"event": event})


def test_v2_policy_reader_exact_native_value(source):
    raw = json.loads(d.canonical_bytes(source.activation_stale_policy))
    assert _read_activation_stale_policy_v2(raw) == source.activation_stale_policy
    for key, value in (("max_age_nanoseconds", True), ("allow_forward_fill", 1), ("policy_version", 0)):
        with pytest.raises((ValueError, TypeError)):
            _read_activation_stale_policy_v2({**raw, key: value})


def test_v1_factored_signal_uses_the_original_native_source_clock_and_finance(source, monkeypatch):
    from crypto_quant_backtest.cn_a_share_portfolio_economic_case_v1 import _native_initial_economic_financial_state_v1
    from crypto_quant_backtest.cn_a_share_portfolio_economic_native_state_v1 import (
        _EconomicOpenSourcesV1, _economic_signal_target_v1,
    )
    from tests.runtime.providers._cn_a_share_portfolio_economic_fixtures_v1 import economic_public_sources_v1
    old, _, _, _, target, _ = economic_public_sources_v1()
    old = replace(old, dividend_actions=replace(old.dividend_actions, actions=()))
    initial, dividend_state, _ = _native_initial_economic_financial_state_v1(old)
    native = _EconomicOpenSourcesV1(old, initial.journal, initial.settlement_book, (), (),
        initial.settlement_rules, dividend_state, (), old.signal_marks[0].at)
    signal, projection = _economic_signal_target_v1(sources=native, event=target.events[0])
    assert projection is native.economic_projection
    assert signal.decision_batch.decision_instant == old.signal_marks[0].at
    assert signal.normalized_target.materialized_instant == old.signal_marks[0].at
    assert signal.target_validity.valid_from == old.signal_marks[0].at.instant
    assert {row.instrument_id.stable_key: row.decision.final_quantity.units for row in signal.normalized_target.targets} == {"600000": 4300, "000001": 2200}
    assert initial.journal == old.initial_journal and initial.settlement_book.obligations == ()
    # A genuine empty-account native projection exercises the <=0 guard. The
    # input DTO remains untouched; only the account presented to the consumer is empty.
    import crypto_quant_trading.profiles.cn_a_share.portfolio_economic_v1 as economic
    empty = t.AccountingJournal()
    zero_projection = economic.project_cn_a_share_portfolio_economic_state_v1(
        economic.CnASharePortfolioEconomicProjectionInputsV1(
            empty, old.scope.ledger_schema, initial.settlement_book, (), (), initial.settlement_rules,
            old.scope.instrument_catalog, old.signal_marks[0].marks,
            t.CurrencyValuationGraph(native.at.instant, d.PricePurpose.VALUATION, ()),
            old.notional_quantization, replace(dividend_state, as_of=native.at), native.at)).projection
    assert zero_projection is not None and zero_projection.snapshot.equity.units == 0
    # Isolate the precedence boundary with a typed projection, without changing
    # the frozen historical source or performing any financial execution.
    from types import SimpleNamespace
    zero_source = SimpleNamespace(inputs=old, at=native.at, economic_projection=zero_projection)
    def forbidden(*args, **kwargs):
        pytest.fail("V1 source decode must not precede its equity guard")
    from crypto_quant_backtest.target_stream import PrecomputedTargetStreamAdapter
    monkeypatch.setattr(PrecomputedTargetStreamAdapter, "_decode", forbidden)
    with pytest.raises(_EconomicNativeFailureV1) as caught:
        _economic_signal_target_v1(sources=zero_source, event=target.events[0])
    assert caught.value.operation == "economic_equity_allocation"
    assert caught.value.evidence is zero_projection


def test_v2_plan4_case2_input9_tuple_exact_cover(tmp_path):
    from tests.runtime.providers._cn_a_share_portfolio_economic_fixtures_v2 import economic_prepared_case_v2
    from crypto_quant_backtest.execution_inputs import _read_execution_inputs_v9_from_snapshot, _EXECUTION_INPUT_CATALOG
    from crypto_quant_backtest.profile_portfolio_execution import _economic_profile_prefix_v1
    from crypto_quant_backtest.cn_a_share_portfolio_economic_result_v1 import _request_v1
    prepared, case, inputs, store, market = economic_prepared_case_v2(tmp_path)
    bundle, failure = _read_execution_inputs_v9_from_snapshot(store, prepared.execution_request)
    assert failure is None and bundle.execution_case_plan == case.execution_case_plan
    plan = case.execution_case_plan
    assert set(plan.to_canonical_dict()) == {"type", "schema_version", "definition", "financial_state", "initial_dividend_state", "initial_economic_projection", "source_refs"}
    assert plan.to_canonical_dict()["schema_version"] == 4 and case.to_canonical_dict()["schema_version"] == 2
    envelope = store.read(ref=prepared.execution_request.execution_input_bundle_ref).envelope
    assert envelope.schema_version == 9 and len(envelope.payload) == 10
    assert d.canonical_bytes(bundle.target_stream) == d.canonical_bytes(inputs.source_target_stream)
    assert tuple((role, ref.schema_version) for role, ref in plan.source_refs) == (("cash_dividend_action_set", 1), ("definition", 3), ("target_stream", 1))
    assert all(rule.binding_key.startswith("signal.0.") for rule in case.semantic_spec.identity_plan)
    prefix = "cn.portfolio.shared-cny.economic.development.v2"
    assert _economic_profile_prefix_v1(inputs.definition()) == case.case_key == prefix
    with pytest.raises(ValueError): replace(case, case_key=prefix[:-1] + "1")
    with pytest.raises(ValueError): replace(case, case_version=2)
    with pytest.raises(ValueError): replace(bundle, execution_case_semantic_spec=replace(case.semantic_spec, case_key=prefix[:-1] + "1"))
    refs = tuple((role, replace(ref, schema_version=2) if role == "definition" else ref) for role, ref in plan.source_refs)
    with pytest.raises(ValueError): replace(plan, source_refs=refs)
    for envelope_version, payload_version in ((2, 2), (3, 1), (4, 2), (3, True)):
        payload = dict(inputs.economic_payload(), schema_version=payload_version)
        definition = d.ArtifactEnvelope.create("backtest_profile_portfolio_definition", envelope_version, payload)
        with pytest.raises((TypeError, ValueError)): _economic_profile_prefix_v1(definition)
        with pytest.raises((TypeError, ValueError)): replace(plan, definition=definition)
    request = json.loads(d.canonical_bytes(prepared.execution_request.request))
    for field in ("market_semantics_profile_key", "simulation_profile_key", "execution_account_profile_key"):
        changed = {**request, field: request[field].replace(".v2.", ".v1.")}
        with pytest.raises(d.ArtifactIntegrityError): _request_v1(changed, market)
    raw = json.loads(d.canonical_bytes(envelope.payload))
    raw["execution_case_semantic_spec"]["case_key"] = prefix[:-1] + "1"
    forged = d.ArtifactEnvelope.create(envelope.artifact_type, 9, raw)
    with pytest.raises(ValueError): _EXECUTION_INPUT_CATALOG.read(d.canonical_bytes(forged))


def test_v1_parser_extraction_preserves_signal_before_daily_failure_precedence(source):
    from tests.runtime.providers._cn_a_share_portfolio_economic_fixtures_v1 import economic_definition_source_v1
    old = economic_definition_source_v1()
    raw = json.loads(d.canonical_bytes(old.economic_payload()))
    raw["signal_marks"][0]["type"] = "signal-first"
    raw["daily_marks"][0]["type"] = "daily-later"
    envelope = d.ArtifactEnvelope.create("backtest_profile_portfolio_definition", 2, raw)
    with pytest.raises(ValueError, match="cn_a_share_portfolio_mark_batch_development"):
        _read_economic_definition_v1(envelope, old.scope.target_stream_ref, old.dividend_actions)
    raw["signal_marks"][0]["type"] = "cn_a_share_portfolio_mark_batch_development"
    raw["signal_marks"][0]["marks"][0]["price_purpose"] = "invalid-signal-purpose"
    with pytest.raises(ValueError, match="invalid-signal-purpose"):
        _read_economic_definition_v1(d.ArtifactEnvelope.create("backtest_profile_portfolio_definition", 2, raw),
            old.scope.target_stream_ref, old.dividend_actions)
    with pytest.raises(ValueError, match="unknown economic source signal field"):
        _read_economic_source_fields_v1(raw, old.scope.target_stream_ref, signal_field="other")
