from __future__ import annotations

from dataclasses import dataclass, replace
import json
from pathlib import Path

import crypto_quant_backtest as backtest
import pytest
from crypto_quant_domain import AccountingEntryType, ArtifactEnvelope, ArtifactRef, DomainId, DomainIdKind, FeeBasisType, IdentityNamespace, Money, Scale, UtcInstant, canonical_bytes
from crypto_quant_trading import FinalFeeApplicability, FinalFeeRuleSet, PortfolioValueKind
from tests.kernel.accounting._fixtures import COST_BASIS_POLICY_V2
from tests.kernel.fees._fixtures import order_minimum
from tests.runtime.engine import _fixtures as engine_fixture
from tests.runtime.providers.test_cash_development_provider import _Cas
from tests.runtime.resolution._fixtures import build_manifest, profile_registry, request


def _with_order_fee(case, *, order_basis=True, minimum=False):
    bar = case.bar_executions[0]
    accounting = bar.accounting_plan
    fee = accounting.fee_plan
    if minimum:
        rules = fee.final_fee_rule_set
        fee = replace(fee, final_fee_rule_set=FinalFeeRuleSet.create(
            market_fee_policy_ref=rules.market_fee_policy_ref,
            tax_policy_ref=rules.tax_policy_ref,
            account_fee_schedule_ref=rules.account_fee_schedule_ref,
            assessment_currency=rules.assessment_currency,
            assessment_scale=rules.assessment_scale,
            charge_rules=rules.charge_rules,
            minimums=(order_minimum(),),
        ))
    if order_basis:
        fee = backtest.FullFillOrderFeeAccountingPlan(
            fee.cash_key, fee.final_fee_rule_set, fee.fee_assessment_id,
            fee.fee_assessment_time, fee.fee_journal_entry_id, fee.fee_recorded_at,
        )
    accounting = replace(
        accounting,
        fee_plan=fee,
        position_payload=replace(accounting.position_payload, cost_basis_policy=COST_BASIS_POLICY_V2, final_fee_rule_set=fee.final_fee_rule_set),
        semantic_payload=replace(accounting.semantic_payload, cost_basis_policy=COST_BASIS_POLICY_V2),
    )
    snapshot = case.snapshot_plan
    if minimum:
        amounts = {PortfolioValueKind.CASH: 46_945, PortfolioValueKind.FEES: 500}
        snapshot = replace(snapshot, valuations=tuple(
            replace(value, native_value=Money(amounts[value.value_ref.kind], Scale(2), "USD"), reporting_value=Money(amounts[value.value_ref.kind], Scale(2), "USD"))
            if value.value_ref.kind in amounts else value
            for value in snapshot.valuations
        ))
    return replace(
        case, bar_executions=(replace(bar, accounting_plan=accounting),),
        snapshot_plan=snapshot,
        financial_dispatch_plan=replace(case.financial_dispatch_plan, final_snapshot_payload=snapshot),
    )


@dataclass(frozen=True)
class _OrderCaseBuilder(engine_fixture.SyntheticExecutionCaseBuilder):
    minimum: bool = False
    def semantic_spec(self):
        return backtest.ExecutionCaseComposer.semantic_spec_from_case(
            _with_order_fee(engine_fixture.execution_case(), minimum=self.minimum),
            spec_key="full-fill-order-fee.test.v1", spec_version=1,
            identity_namespace=IdentityNamespace("backtest", "1"),
            identity_plan=self.identity_plan(),
        )

    def build(self, identities, semantic_spec_hash):
        return _with_order_fee(super().build(identities, semantic_spec_hash), minimum=self.minimum)


def _prepared(tmp_path: Path, *, minimum=False, builder=None):
    builder = _OrderCaseBuilder(minimum=minimum) if builder is None else builder
    spec = builder.semantic_spec()
    manifest = build_manifest()
    reader = engine_fixture.reader()
    public_request = replace(
        request(manifest, bundle=reader.manifest),
        execution_case_semantic_hash=spec.semantic_spec_hash,
        target_stream_digest=spec.target_stream_digest,
    )
    resolution = backtest.ProfileResolver().resolve(
        request=public_request, registry=profile_registry(),
        market_bundle_manifest=reader.manifest, build_artifact_manifest=manifest,
    )
    assert resolution.resolved is not None
    case = backtest.ExecutionCaseComposer().compose(resolved_request=resolution.resolved, builder=builder)
    bundle = backtest.materialize_execution_input_bundle_v2(resolved_request=resolution.resolved, execution_case=case)
    store = _Cas()
    ref = store.put(envelope=bundle)
    runtime = backtest.BacktestRuntime(
        registry=profile_registry(), artifact_reader=store, artifact_publisher=store,
        market_reader=reader, publication_root=tmp_path,
    )
    return runtime, backtest.BacktestExecutionRequest(2, public_request, ref), store


def _combined_case(case, fill_fee_id, fill_fee_journal_id, *, zero_fill_fee=False):
    case = _with_order_fee(case, minimum=True)
    bar = case.bar_executions[0]
    accounting = bar.accounting_plan
    order_fee = accounting.fee_plan
    fill_rules = order_fee.final_fee_rule_set
    if zero_fill_fee:
        fill_rules = FinalFeeRuleSet.create(
            market_fee_policy_ref=fill_rules.market_fee_policy_ref,
            tax_policy_ref=fill_rules.tax_policy_ref,
            account_fee_schedule_ref=fill_rules.account_fee_schedule_ref,
            assessment_currency=fill_rules.assessment_currency,
            assessment_scale=fill_rules.assessment_scale,
            charge_rules=tuple(
                replace(rule, applicability=FinalFeeApplicability.NOT_APPLICABLE)
                if rule.basis_type is FeeBasisType.FILL else rule
                for rule in fill_rules.charge_rules
            ),
            minimums=fill_rules.minimums,
        )
    fill_fee = backtest.FeeAccountingDispatchPlan(
        order_fee.cash_key, fill_rules, fill_fee_id,
        order_fee.fee_assessment_time, fill_fee_journal_id, order_fee.fee_recorded_at,
    )
    order_fee = replace(
        order_fee, fill_fee_plan=fill_fee,
        fee_assessment_time=UtcInstant(213),
        fee_recorded_at=replace(order_fee.fee_recorded_at, instant=UtcInstant(214)),
    )
    accounting = replace(
        accounting, fee_plan=order_fee,
        position_payload=replace(
            accounting.position_payload,
            fee_assessment_time=order_fee.fee_assessment_time,
            fee_recorded_at=order_fee.fee_recorded_at,
        ),
    )
    amounts = {PortfolioValueKind.CASH: 46_945 if zero_fill_fee else 46_892, PortfolioValueKind.FEES: 500 if zero_fill_fee else 553}
    snapshot = replace(case.snapshot_plan, valuations=tuple(
        replace(value, native_value=Money(amounts[value.value_ref.kind], Scale(2), "USD"), reporting_value=Money(amounts[value.value_ref.kind], Scale(2), "USD"))
        if value.value_ref.kind in amounts else value
        for value in case.snapshot_plan.valuations
    ))
    return replace(
        case, bar_executions=(replace(bar, accounting_plan=accounting),),
        snapshot_plan=snapshot,
        financial_dispatch_plan=replace(case.financial_dispatch_plan, final_snapshot_payload=snapshot),
    )


def _combined_template(*, zero_fill_fee=False):
    return _combined_case(
        engine_fixture.execution_case(),
        DomainId(DomainIdKind.FEE, DomainIdKind.FEE.prefix + "_" + "e" * 64),
        DomainId(DomainIdKind.JOURNAL, DomainIdKind.JOURNAL.prefix + "_" + "f" * 64),
        zero_fill_fee=zero_fill_fee,
    )


@dataclass(frozen=True)
class _CombinedCaseBuilder(engine_fixture.SyntheticExecutionCaseBuilder):
    zero_fill_fee: bool = False

    def identity_plan(self):
        return super().identity_plan() + (
            backtest.ExecutionCaseIdentityRule("fee.fill.0", "combined-fees.fill-fee", 0, DomainIdKind.FEE),
            backtest.ExecutionCaseIdentityRule("journal.fee.fill.0", "combined-fees.fill-fee-journal", 0, DomainIdKind.JOURNAL),
        )

    def semantic_spec(self):
        return backtest.ExecutionCaseComposer.semantic_spec_from_case(
            _combined_template(zero_fill_fee=self.zero_fill_fee), spec_key="combined-fill-order-fees.test.v1", spec_version=1,
            identity_namespace=IdentityNamespace("backtest", "1"),
            identity_plan=self.identity_plan(),
        )

    def build(self, identities, semantic_spec_hash):
        return _combined_case(
            super().build(identities, semantic_spec_hash),
            identities.domain_id("fee.fill.0"), identities.domain_id("journal.fee.fill.0"),
            zero_fill_fee=self.zero_fill_fee,
        )


def _engine_result(store, publication):
    manifest = store.read(ref=publication.artifact_ref).envelope.payload
    attempt_entry = next(entry for entry in manifest["artifacts"] if entry["artifact_type"] == "canonical_attempt_ref")
    attempt = store.read(ref=ArtifactRef("canonical_attempt_ref", 1, attempt_entry["content_hash"])).envelope.payload
    return store.read(ref=ArtifactRef("engine_execution_result", 1, attempt["engine_result_artifact_content_hash"])).envelope.payload


@pytest.mark.parametrize("minimum, expected_units", [(False, 53), (True, 500)])
def test_public_runtime_reconstructs_and_posts_an_order_fee_with_replay_stable_evidence(tmp_path, minimum, expected_units):
    runtime, execution_request, store = _prepared(tmp_path, minimum=minimum)
    publication = runtime.run(execution_request)
    assert type(publication) is backtest.BacktestCanonicalPublicationRef
    assert runtime.run(execution_request) == publication
    verified = backtest.BacktestEvidenceRepository(reader=store).load_completed(publication)
    summary = verified.execution_summary
    assert len(summary.fills) == 1
    engine_result = _engine_result(store, publication)
    assert len(engine_result["fee_assessments"]) == 1
    fee = engine_result["fee_assessments"][0]
    assert fee["basis_type"] == "order"
    assert canonical_bytes(fee["basis_ids"]) == canonical_bytes((summary.fills[0].order_id,))
    assert canonical_bytes(fee["amount"]) == canonical_bytes(Money(expected_units, Scale(2), "USD"))
    assert summary.final_portfolio_snapshot.fees == Money(expected_units, Scale(2), "USD")
    assert summary.final_portfolio_snapshot.equity == Money(101_945 if minimum else 102_392, Scale(2), "USD")
    fee_entry = summary.final_journal.entries[-1]
    assert str(summary.fills[0].order_id) in fee_entry.source_ids
    assert str(summary.fills[0].fill_id) in fee_entry.source_ids
    assert fee_entry.position_lot_changes


@pytest.mark.parametrize("zero_fill_fee", [False, True])
def test_public_runtime_keeps_both_fill_fee_and_order_minimum_with_distinct_evidence(tmp_path, zero_fill_fee):
    runtime, execution_request, store = _prepared(tmp_path, builder=_CombinedCaseBuilder(zero_fill_fee=zero_fill_fee))
    publication = runtime.run(execution_request)
    assert type(publication) is backtest.BacktestCanonicalPublicationRef
    assert runtime.run(execution_request) == publication
    verified = backtest.BacktestEvidenceRepository(reader=store).load_completed(publication)
    summary = verified.execution_summary
    assessments = _engine_result(store, publication)["fee_assessments"]
    assert len(assessments) == 2
    by_basis = {value["basis_type"]: value for value in assessments}
    assert set(by_basis) == {"fill", "order"}
    assert canonical_bytes(by_basis["fill"]["amount"]) == canonical_bytes(Money(0 if zero_fill_fee else 53, Scale(2), "USD"))
    assert canonical_bytes(by_basis["order"]["amount"]) == canonical_bytes(Money(500, Scale(2), "USD"))
    assert canonical_bytes(by_basis["fill"]["basis_ids"]) == canonical_bytes((summary.fills[0].fill_id,))
    assert canonical_bytes(by_basis["order"]["basis_ids"]) == canonical_bytes((summary.fills[0].order_id,))
    assert by_basis["fill"]["fee_assessment_id"] != by_basis["order"]["fee_assessment_id"]
    total = Money(500 if zero_fill_fee else 553, Scale(2), "USD")
    assert summary.final_portfolio_snapshot.fees == total
    assert summary.final_portfolio_snapshot.equity == Money(101_945 if zero_fill_fee else 101_892, Scale(2), "USD")
    charges = [entry for entry in summary.final_journal.entries if entry.entry_type is AccountingEntryType.FEE_CHARGED]
    assert len(charges) == (1 if zero_fill_fee else 2)
    order_charge = charges[-1]
    if not zero_fill_fee:
        fill_charge = charges[0]
        assert fill_charge.journal_entry_id != order_charge.journal_entry_id
        assert fill_charge.recorded_at < order_charge.recorded_at
        assert fill_charge.fees == (Money(53, Scale(2), "USD"),)
    assert order_charge.fees == (Money(500, Scale(2), "USD"),)
    after = order_charge.position_lot_changes[0].after
    assert after is not None
    assert after.allocated_fees == (total,)


@pytest.mark.parametrize("violation", [
    "assessment_identity", "journal_identity", "cash_context", "nested_order",
    "after_order", "at_order_assessment", "after_assessment_same_utc", "before_position", "position_journal_identity",
])
def test_combined_fee_plan_rejects_ambiguous_identity_context_or_clock(violation):
    accounting = _combined_template().bar_executions[0].accounting_plan
    fee = accounting.fee_plan
    prior = fee.fill_fee_plan
    with pytest.raises((ValueError, TypeError)):
        if violation == "assessment_identity":
            prior = replace(prior, fee_assessment_id=fee.fee_assessment_id)
        elif violation == "journal_identity":
            prior = replace(prior, fee_journal_entry_id=fee.fee_journal_entry_id)
        elif violation == "cash_context":
            prior = replace(prior, cash_key=replace(prior.cash_key, account_id="other-account"))
        elif violation == "nested_order":
            prior = replace(fee, fill_fee_plan=None)
        elif violation == "after_order":
            prior = replace(prior, fee_recorded_at=fee.fee_recorded_at)
        elif violation == "at_order_assessment":
            prior = replace(prior, fee_recorded_at=fee.assessment_at)
        elif violation == "after_assessment_same_utc":
            prior = replace(prior, fee_recorded_at=replace(fee.fee_recorded_at, instant=fee.fee_assessment_time))
        elif violation == "before_position":
            prior = replace(prior, fee_assessment_time=accounting.fill_recorded_at.instant, fee_recorded_at=accounting.fill_recorded_at)
        else:
            prior = replace(prior, fee_journal_entry_id=accounting.fill_journal_entry_id)
        replace(accounting, fee_plan=replace(fee, fill_fee_plan=prior))


@pytest.mark.parametrize("tamper", ["fee_identity", "journal_identity", "remove", "metadata", "scope"])
def test_combined_fee_authority_tampering_fails_before_publication(tmp_path, tamper):
    runtime, execution_request, store = _prepared(tmp_path, builder=_CombinedCaseBuilder())
    original = store.read(ref=execution_request.execution_input_bundle_ref).envelope
    payload = json.loads(canonical_bytes(original.payload))
    fee = payload["execution_case_plan"]["bar_executions"][0]["accounting_plan"]["fee_plan"]
    prior = fee["fill_fee_plan"]
    if tamper == "fee_identity":
        prior["fee_assessment_id"]["value"] = DomainIdKind.FEE.prefix + "_" + "a" * 64
    elif tamper == "journal_identity":
        prior["fee_journal_entry_id"]["value"] = DomainIdKind.JOURNAL.prefix + "_" + "a" * 64
    elif tamper == "remove":
        del fee["fill_fee_plan"]
    elif tamper == "metadata":
        prior["fee_assessment_time"] = json.loads(canonical_bytes(UtcInstant(210)))
    else:
        prior["type"] = "full_fill_order_fee_accounting_plan"
    forged = replace(execution_request, execution_input_bundle_ref=store.put(envelope=ArtifactEnvelope.create(original.artifact_type, original.schema_version, payload)))
    with pytest.raises(RuntimeError, match="execution input hydration failed"):
        runtime.run(forged)
    assert not (tmp_path / "runs").exists()


def test_order_basis_changes_semantic_identity_even_when_rules_and_amount_are_equal():
    def spec(order_basis):
        return backtest.ExecutionCaseComposer.semantic_spec_from_case(
            _with_order_fee(engine_fixture.execution_case(), order_basis=order_basis),
            spec_key="full-fill-order-fee.test.v1", spec_version=1,
            identity_namespace=IdentityNamespace("backtest", "1"),
            identity_plan=engine_fixture.SyntheticExecutionCaseBuilder().identity_plan(),
        )
    assert spec(True).semantic_spec_hash != spec(False).semantic_spec_hash


@pytest.mark.parametrize("tag", ["fee_accounting_dispatch_plan", "unknown_fee_plan"])
def test_fee_scope_substitution_fails_before_an_attempt_or_publication(tmp_path, tag):
    runtime, execution_request, store = _prepared(tmp_path)
    original = store.read(ref=execution_request.execution_input_bundle_ref).envelope
    payload = json.loads(canonical_bytes(original.payload))
    payload["execution_case_plan"]["bar_executions"][0]["accounting_plan"]["fee_plan"]["type"] = tag
    substituted = ArtifactEnvelope.create(original.artifact_type, original.schema_version, payload)
    forged = replace(execution_request, execution_input_bundle_ref=store.put(envelope=substituted))
    with pytest.raises(RuntimeError, match="execution input hydration failed"):
        runtime.run(forged)
    assert not (tmp_path / "runs").exists()
