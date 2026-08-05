from __future__ import annotations

from dataclasses import replace
import json
import re

import pytest

from crypto_quant_backtest import (
    AttemptIdentity,
    BacktestRunOutcome,
    DeterministicBarEngine,
    ExecutionCaseComposer,
    ExecutionCaseIdentityRule,
    InputOrigin,
    ProfileResolver,
)
from crypto_quant_domain import canonical_bytes, canonical_sha256
from tests.runtime.engine._fixtures import (
    SyntheticExecutionCaseBuilder,
    execution_case as legacy_execution_case,
    reader,
)
from tests.runtime.resolution._fixtures import (
    build_manifest,
    profile_registry,
    request,
)
from tests.runtime.runner._fixtures import RecordingEngine, auditable_runner


_DOMAIN_OR_EVENT_ID = re.compile(r"^(ord|fil|fee|jnl|evt)_[0-9a-f]{64}$")
_HASH = re.compile(r"sha256:[0-9a-f]{64}")


def _scrub_identity(value):
    if isinstance(value, dict):
        return {
            key: (
                "<event_id>"
                if key in {"event_id", "causation_id", "correlation_id"}
                else _scrub_identity(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_scrub_identity(item) for item in value]
    if isinstance(value, str):
        match = _DOMAIN_OR_EVENT_ID.fullmatch(value)
        if match is not None:
            return f"<{match.group(1)}_id>"
        if _HASH.search(value) is not None:
            return _HASH.sub("<hash>", value)
    return value


def resolved_for(builder: SyntheticExecutionCaseBuilder):
    spec = builder.semantic_spec()
    manifest = build_manifest()
    bundle = reader(include_warmup=builder.include_warmup).manifest
    requested = replace(
        request(manifest, bundle=bundle),
        execution_case_semantic_hash=spec.semantic_spec_hash,
        target_stream_digest=spec.target_stream_digest,
    )
    outcome = ProfileResolver().resolve(
        request=requested,
        registry=profile_registry(),
        market_bundle_manifest=bundle,
        build_artifact_manifest=manifest,
    )
    assert outcome.resolved is not None
    case = ExecutionCaseComposer().compose(
        resolved_request=outcome.resolved,
        builder=builder,
    )
    return outcome.resolved, case


def test_semantic_run_uses_id_free_case_spec_not_final_case_hash() -> None:
    builder = SyntheticExecutionCaseBuilder()
    spec = builder.semantic_spec()
    resolved, case = resolved_for(builder)
    encoded = canonical_bytes(spec)

    assert resolved.request.execution_case_semantic_hash == spec.semantic_spec_hash
    assert case.semantic_spec_hash == spec.semantic_spec_hash
    assert case.case_hash != spec.semantic_spec_hash
    assert case.identity_manifest is not None
    assert case.verify_identity_manifest(resolved.semantic_run_id)
    assert re.search(rb'"(ord|fil|fee|jnl|evt)_[0-9a-f]{64}"', encoded) is None


def test_semantic_spec_rejects_noncanonical_identity_text() -> None:
    with pytest.raises(ValueError, match="spec_key"):
        replace(
            SyntheticExecutionCaseBuilder().semantic_spec(),
            spec_key="cafe\u0301",
        )


def test_semantic_input_change_changes_semantic_run_and_final_case() -> None:
    first, first_case = resolved_for(SyntheticExecutionCaseBuilder())
    changed, changed_case = resolved_for(
        SyntheticExecutionCaseBuilder(reject_capability=True)
    )

    assert first.semantic_run_id != changed.semantic_run_id
    assert first_case.semantic_spec_hash != changed_case.semantic_spec_hash
    assert first_case.case_hash != changed_case.case_hash


def test_runner_validates_manifest_and_spec_instead_of_final_case_preimage() -> None:
    resolved, case = resolved_for(SyntheticExecutionCaseBuilder())
    record = auditable_runner().execute(
        resolved_request=resolved,
        execution_case=case,
        attempt=AttemptIdentity.first(resolved.semantic_run_id),
        input_origin=InputOrigin.PRECOMPUTED_TARGET_STREAM,
    )

    assert record.ready_to_finalize is not None
    assert record.terminal_outcome is None
    assert record.ready_to_finalize.engine_result.case_hash == case.case_hash


def test_cross_run_relabel_is_rejected_before_engine() -> None:
    first_resolved, first_case = resolved_for(SyntheticExecutionCaseBuilder())
    changed_resolved, changed_case = resolved_for(
        SyntheticExecutionCaseBuilder(reject_capability=True)
    )
    relabelled = replace(
        first_case,
        semantic_spec_hash=changed_case.semantic_spec_hash,
        semantic_spec=changed_case.semantic_spec,
    )
    expected_outcome = DeterministicBarEngine().run(changed_case)
    recording = RecordingEngine(outcome=expected_outcome)

    record = auditable_runner(recording).execute(
        resolved_request=changed_resolved,
        execution_case=relabelled,
        attempt=AttemptIdentity.first(changed_resolved.semantic_run_id),
        input_origin=InputOrigin.PRECOMPUTED_TARGET_STREAM,
    )

    assert record.failed_report is not None
    assert record.terminal_outcome is BacktestRunOutcome.FAILED
    assert record.failed_report.issue.code == "execution_case_semantic_spec_mismatch"
    assert recording.calls == []
    assert first_resolved.semantic_run_id != changed_resolved.semantic_run_id


def test_composer_rejects_wrong_target_digest() -> None:
    base = SyntheticExecutionCaseBuilder()

    class WrongTargetBuilder:
        def semantic_spec(self):
            return replace(
                base.semantic_spec(),
                target_stream_digest=canonical_sha256({"target": "wrong"}),
            )

        def build(self, identities, semantic_spec_hash):
            return base.build(identities, semantic_spec_hash)

    spec = WrongTargetBuilder().semantic_spec()
    manifest = build_manifest()
    bundle = reader().manifest
    requested = replace(
        request(manifest, bundle=bundle),
        execution_case_semantic_hash=spec.semantic_spec_hash,
        target_stream_digest=spec.target_stream_digest,
    )
    outcome = ProfileResolver().resolve(
        request=requested,
        registry=profile_registry(),
        market_bundle_manifest=bundle,
        build_artifact_manifest=manifest,
    )
    assert outcome.resolved is not None

    with pytest.raises(ValueError, match="inputs do not match semantic spec"):
        ExecutionCaseComposer().compose(
            resolved_request=outcome.resolved,
            builder=WrongTargetBuilder(),
        )


def test_composer_rejects_execution_policy_substitution() -> None:
    base = SyntheticExecutionCaseBuilder()
    changed = SyntheticExecutionCaseBuilder(reject_capability=True)
    spec = base.semantic_spec()
    resolved, _ = resolved_for(base)

    class SubstitutedBuilder:
        def semantic_spec(self):
            return spec

        def build(self, identities, semantic_spec_hash):
            return changed.build(identities, semantic_spec_hash)

    with pytest.raises(ValueError, match="inputs do not match semantic spec"):
        ExecutionCaseComposer().compose(
            resolved_request=resolved,
            builder=SubstitutedBuilder(),
        )


def test_runner_rejects_missing_manifest_before_engine() -> None:
    resolved, case = resolved_for(SyntheticExecutionCaseBuilder())
    stripped = replace(case, identity_manifest=None)
    expected_outcome = DeterministicBarEngine().run(case)
    recording = RecordingEngine(outcome=expected_outcome)

    record = auditable_runner(recording).execute(
        resolved_request=resolved,
        execution_case=stripped,
        attempt=AttemptIdentity.first(resolved.semantic_run_id),
        input_origin=InputOrigin.PRECOMPUTED_TARGET_STREAM,
    )

    assert record.failed_report is not None
    assert record.failed_report.issue.code == "execution_case_identity_manifest_missing"
    assert recording.calls == []


def test_composer_rejects_request_semantic_hash_mismatch() -> None:
    resolved, _ = resolved_for(SyntheticExecutionCaseBuilder())
    changed = SyntheticExecutionCaseBuilder(reject_capability=True)

    with pytest.raises(ValueError, match="Request does not bind"):
        ExecutionCaseComposer().compose(
            resolved_request=resolved,
            builder=changed,
        )


def test_composer_rejects_builder_supplied_manifest() -> None:
    base = SyntheticExecutionCaseBuilder()
    resolved, _ = resolved_for(base)

    class ManifestBuilder:
        def semantic_spec(self):
            return base.semantic_spec()

        def build(self, identities, semantic_spec_hash):
            case = base.build(identities, semantic_spec_hash)
            return replace(case, identity_manifest=identities.manifest())

    with pytest.raises(ValueError, match="must not supply"):
        ExecutionCaseComposer().compose(
            resolved_request=resolved,
            builder=ManifestBuilder(),
        )


def test_composer_rejects_stateful_semantic_spec() -> None:
    base = SyntheticExecutionCaseBuilder()
    resolved, _ = resolved_for(base)

    class StatefulBuilder:
        calls = 0

        def semantic_spec(self):
            self.calls += 1
            spec = base.semantic_spec()
            if self.calls == 1:
                return spec
            return replace(spec, spec_version=spec.spec_version + 1)

        def build(self, identities, semantic_spec_hash):
            return base.build(identities, semantic_spec_hash)

    with pytest.raises(ValueError, match="changed during composition"):
        ExecutionCaseComposer().compose(
            resolved_request=resolved,
            builder=StatefulBuilder(),
        )


def test_composer_rejects_identity_plan_without_exact_coverage() -> None:
    base = SyntheticExecutionCaseBuilder()
    base_spec = base.semantic_spec()
    extra_rule = ExecutionCaseIdentityRule(
        binding_key="order-event.unused",
        semantic_key="engine.cash.order-event.unused",
        ordinal=0,
    )
    changed_spec = replace(
        base_spec,
        identity_plan=(*base_spec.identity_plan, extra_rule),
    )
    manifest = build_manifest()
    bundle = reader().manifest
    requested = replace(
        request(manifest, bundle=bundle),
        execution_case_semantic_hash=changed_spec.semantic_spec_hash,
        target_stream_digest=changed_spec.target_stream_digest,
    )
    outcome = ProfileResolver().resolve(
        request=requested,
        registry=profile_registry(),
        market_bundle_manifest=bundle,
        build_artifact_manifest=manifest,
    )
    assert outcome.resolved is not None

    class ExtraIdentityBuilder:
        def semantic_spec(self):
            return changed_spec

        def build(self, identities, semantic_spec_hash):
            return base.build(identities, semantic_spec_hash)

    with pytest.raises(ValueError, match="not exact-covered"):
        ExecutionCaseComposer().compose(
            resolved_request=outcome.resolved,
            builder=ExtraIdentityBuilder(),
        )


def test_runner_rejects_identity_role_swap_before_engine() -> None:
    resolved, case = resolved_for(SyntheticExecutionCaseBuilder())
    execution = case.bar_executions[0]
    accounting = execution.accounting_plan
    swapped_accounting = replace(
        accounting,
        fill_journal_entry_id=accounting.fee_journal_entry_id,
        fee_journal_entry_id=accounting.fill_journal_entry_id,
    )
    swapped_execution = replace(execution, accounting_plan=swapped_accounting)
    swapped = replace(case, bar_executions=(swapped_execution,))
    recording = RecordingEngine(outcome=DeterministicBarEngine().run(case))

    record = auditable_runner(recording).execute(
        resolved_request=resolved,
        execution_case=swapped,
        attempt=AttemptIdentity.first(resolved.semantic_run_id),
        input_origin=InputOrigin.PRECOMPUTED_TARGET_STREAM,
    )

    assert record.failed_report is not None
    assert record.failed_report.issue.code == "execution_case_identity_manifest_mismatch"
    assert recording.calls == []


def test_independent_recomposition_and_attempts_preserve_ids() -> None:
    builder = SyntheticExecutionCaseBuilder()
    first_resolved, first_case = resolved_for(builder)
    second_resolved, second_case = resolved_for(builder)
    assert first_case is not second_case
    assert first_resolved.semantic_run_id == second_resolved.semantic_run_id
    assert first_case.case_hash == second_case.case_hash
    assert first_case.identity_manifest == second_case.identity_manifest
    assert replace(
        first_case,
        semantic_spec_hash=canonical_sha256({"semantic_spec": "changed"}),
        semantic_spec=None,
    ).case_hash != first_case.case_hash

    runner = auditable_runner()
    first = runner.execute(
        resolved_request=first_resolved,
        execution_case=first_case,
        attempt=AttemptIdentity.first(first_resolved.semantic_run_id),
        input_origin=InputOrigin.PRECOMPUTED_TARGET_STREAM,
    )
    second = runner.retry_from_start(
        previous=first,
        resolved_request=second_resolved,
        execution_case=second_case,
        next_attempt_ordinal=2,
        input_origin=InputOrigin.PRECOMPUTED_TARGET_STREAM,
    )
    assert first.ready_to_finalize is not None
    assert second.ready_to_finalize is not None
    assert first.attempt != second.attempt
    assert (
        first.ready_to_finalize.engine_result.fills[0].fill_id
        == second.ready_to_finalize.engine_result.fills[0].fill_id
    )


def test_derived_identity_changes_no_economic_values() -> None:
    _, derived_case = resolved_for(SyntheticExecutionCaseBuilder())
    legacy = DeterministicBarEngine().run(legacy_execution_case()).result
    derived = DeterministicBarEngine().run(derived_case).result
    assert legacy is not None
    assert derived is not None

    assert derived.fills[0].quantity == legacy.fills[0].quantity
    assert derived.fills[0].price == legacy.fills[0].price
    assert derived.fee_assessments[0].amount == legacy.fee_assessments[0].amount
    assert derived.final_ledger_state.cash_balances == legacy.final_ledger_state.cash_balances
    assert derived.final_ledger_state.position_balances == legacy.final_ledger_state.position_balances
    assert derived.final_portfolio_snapshot.equity == legacy.final_portfolio_snapshot.equity
    assert _scrub_identity(json.loads(canonical_bytes(derived))) == _scrub_identity(
        json.loads(canonical_bytes(legacy))
    )


def test_identity_plan_changes_semantic_identity() -> None:
    spec = SyntheticExecutionCaseBuilder().semantic_spec()
    fill_rule = next(
        rule for rule in spec.identity_plan if rule.binding_key == "journal.fill.0"
    )
    fee_rule = next(
        rule for rule in spec.identity_plan if rule.binding_key == "journal.fee.0"
    )
    changed_plan = tuple(
        replace(rule, semantic_key=fee_rule.semantic_key)
        if rule == fill_rule
        else replace(rule, semantic_key=fill_rule.semantic_key)
        if rule == fee_rule
        else rule
        for rule in spec.identity_plan
    )

    assert replace(spec, identity_plan=changed_plan).semantic_spec_hash != spec.semantic_spec_hash


def test_duplicate_domain_identity_coordinates_are_rejected() -> None:
    spec = SyntheticExecutionCaseBuilder().semantic_spec()
    order_rule = next(
        rule for rule in spec.identity_plan if rule.binding_key == "order.0.0"
    )
    duplicate = ExecutionCaseIdentityRule(
        binding_key="order.duplicate",
        semantic_key=order_rule.semantic_key,
        ordinal=order_rule.ordinal,
        domain_kind=order_rule.domain_kind,
    )

    with pytest.raises(ValueError, match="coordinates must be unique"):
        replace(spec, identity_plan=(*spec.identity_plan, duplicate))


def test_runner_rejects_slippage_parameter_substitution_before_engine() -> None:
    resolved, case = resolved_for(SyntheticExecutionCaseBuilder())
    execution = case.bar_executions[0]
    changed_execution = replace(
        execution,
        slippage_model=replace(
            execution.slippage_model,
            basis_points_units=execution.slippage_model.basis_points_units + 1,
        ),
    )
    changed = replace(case, bar_executions=(changed_execution,))
    recording = RecordingEngine(outcome=DeterministicBarEngine().run(case))

    record = auditable_runner(recording).execute(
        resolved_request=resolved,
        execution_case=changed,
        attempt=AttemptIdentity.first(resolved.semantic_run_id),
        input_origin=InputOrigin.PRECOMPUTED_TARGET_STREAM,
    )

    assert record.failed_report is not None
    assert record.failed_report.issue.code == "execution_case_semantic_spec_mismatch"
    assert recording.calls == []


def test_runner_rejects_order_parent_substitution_before_engine() -> None:
    resolved, case = resolved_for(SyntheticExecutionCaseBuilder())
    cycle = case.decision_cycles[0]
    admission = cycle.admissions[0]
    changed_admission = replace(
        admission,
        order=replace(
            admission.order,
            intent=replace(
                admission.order.intent,
                parent_id=case.financial_state.journal.entries[0].journal_entry_id.value,
            ),
        ),
    )
    changed = replace(
        case,
        decision_cycles=(replace(cycle, admissions=(changed_admission,)),),
    )
    recording = RecordingEngine(outcome=DeterministicBarEngine().run(case))

    record = auditable_runner(recording).execute(
        resolved_request=resolved,
        execution_case=changed,
        attempt=AttemptIdentity.first(resolved.semantic_run_id),
        input_origin=InputOrigin.PRECOMPUTED_TARGET_STREAM,
    )

    assert record.failed_report is not None
    assert record.failed_report.issue.code == "execution_case_semantic_spec_mismatch"
    assert recording.calls == []
