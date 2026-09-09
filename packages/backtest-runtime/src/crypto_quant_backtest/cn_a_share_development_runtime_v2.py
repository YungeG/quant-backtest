"""Profile-owned cash accounting and settlement for the finite CN V2 route."""
from __future__ import annotations

from dataclasses import replace

from crypto_quant_domain import CurrencyId, FeeBasisType, Fill, OrderSide, Rate, Scale, canonical_sha256
from crypto_quant_trading import (
    FeeReservationApplicability, FeeReservationBasis, FeeReservationChargeRule,
    FeeReservationMinimum, FeeReservationRuleSet, FeeReservationRuleSource,
    FinalFeeApplicability, FinalFeeCalculationBasis, FinalFeeChargeRule,
    FinalFeeRuleSet, FinalFeeRuleSource, ProfileComponentRef, SettlementEvent, SettlementEventType,
)
from crypto_quant_trading.profiles.cn_a_share import (
    CnAShareBarCloseReceipt, CnAShareBarCloseSettlementQuery,
    CnAShareCashFeeRuleQueryV2, CnAShareCashMarketFeePolicyV2,
    CnAShareCashSettlementModel, CnAShareCashStampDutyTaxPolicyV2,
    CnAShareExecutionAccessRoute, CnAShareFeeExecutionAuthorityV2,
    CnAShareFeeExecutionBindingFailureV2, CnAShareFeeExecutionScopeV2,
    CnAShareFeeExecutionSelectionV2, CnAShareFeeProductClass, CnAShareFeeQueryConstructionFailureV2,
    CnAShareFeeReservationBufferV2, CnAShareFeeTradeMechanism,
    CnAShareJanuary2024CommissionScenario, CnAShareSettlementQuery, bind_cn_a_share_fee_execution_v2,
    create_cn_a_share_fee_execution_authority_v2,
)

from .cn_a_share_development_profile_v2 import CnAShareResolvedProfileV2
from .cn_a_share_dividend_runtime_v2 import (
    CnAShareDividendFinancialDispatcherV2,
    build_tushare_000703_dividend_scheduled_events_v2,
)
from .execution import BarCloseKind, BarCloseObservation
from .financial_dispatch import (
    DefaultCashFinancialDispatcher,
    FillAccountingDispatchPlan,
    FinancialDispatchArtifact,
    FinancialDispatchFailure,
    FinancialDispatchFailureCode,
    FinancialDispatchOutcome,
    FinancialStateView,
    LedgerCashSnapshotProjectionPlan,
    ProfileFeeRuleQuery,
    ProfileFeeRuleResolution,
    ScheduledAccountEvent,
    SettlementApplicationPlan,
    SettlementFillAccountingDispatchPlan,
    SettlementFinancialDispatchResult,
)


class CnAShareDevelopmentFinancialDispatcherV2(DefaultCashFinancialDispatcher):
    """Reuse cash hooks; only the profile's existing model resolves settlement."""

    def __init__(self, profile: CnAShareResolvedProfileV2, *, closed_bar_execution: bool = False) -> None:
        if type(profile) is not CnAShareResolvedProfileV2:
            raise TypeError("profile must be exact CnAShareResolvedProfileV2")
        if type(closed_bar_execution) is not bool:
            raise TypeError("closed_bar_execution must be bool")
        super().__init__()
        self._profile = profile
        self._closed_bar_execution = closed_bar_execution
        events = tuple(event for authority in profile.request.minute_authorities for event in authority.events)
        self._close_events = {event.event_id: event for event in events} if closed_bar_execution else {}
        if closed_bar_execution and len(self._close_events) != len(events):
            raise ValueError("closed profile events must have unique source identities")
        self._settlement_model = CnAShareCashSettlementModel(profile.request.calendar)
        self._dividend = CnAShareDividendFinancialDispatcherV2(profile.request.dividend_profile)
        request = profile.request
        instrument = request.instrument_scope.instrument
        cny, cent = CurrencyId("CNY"), Scale(2)
        scope = CnAShareFeeExecutionScopeV2(request.account_scope.account_id, instrument.instrument_id.venue,
            instrument, instrument.instrument_id, instrument.instrument_type, cny, cny,
            CnAShareFeeTradeMechanism.AUCTION, request.timeline_window.trading_start, request.timeline_window.end_exclusive,
            (OrderSide.BUY, OrderSide.SELL), CnAShareExecutionAccessRoute.DOMESTIC, CnAShareFeeProductClass.ORDINARY_A_SHARE)
        selection = CnAShareFeeExecutionSelectionV2.create(selection_key="cn-a-share.development.profile-fees.v2",
            selection_version=2, market_fee_rule_book=request.market_fee_rule_book,
            stamp_duty_rule_book=request.stamp_duty_rule_book)
        authority = create_cn_a_share_fee_execution_authority_v2(scope, selection)
        if type(authority) is not CnAShareFeeExecutionAuthorityV2:
            raise ValueError("resolved profile fee authority mismatch")
        self._fee_authority = authority
        self._market_fees = CnAShareCashMarketFeePolicyV2(authority, authority.authority_hash, cent)
        self._taxes = CnAShareCashStampDutyTaxPolicyV2(authority, authority.authority_hash, cent)
        scenario = request.commission_scenario
        self._commission = CnAShareJanuary2024CommissionScenario(scenario.scenario_key,
            scenario.commission_rate, scenario.account_fee_schedule_ref, scenario.development_only)
        base = self.spec
        self._spec = replace(base, dispatcher_key="equity.cn_a_share.development-financial-dispatch.v2",
            dispatcher_version=2, config_hash=canonical_sha256({
                "type": "cn_a_share_development_financial_dispatcher", "schema_version": 2,
                "profile_hash": profile.profile_hash, "base_spec": base,
                "settlement_component": self._settlement_model.component_ref,
                "dividend_dispatcher_spec": self._dividend.spec,
                "fee_authority_hash": authority.authority_hash,
                "fee_binding_policy": "actual_order_reservation_actual_single_fill_and_order.v1",
                "lifecycle_policy": "record_actual_fill_apply_delivery_then_actual_boundary_due.v1",
            }))
        if closed_bar_execution:
            self._spec = replace(self._spec, config_hash=canonical_sha256({
                "type": "cn_a_share_closed_bar_financial_dispatcher", "schema_version": 1,
                "base_spec": self._spec, "settlement_component": self._settlement_model.closed_bar_component_ref,
                "source_policy": "actual_profile_event_exact_close_receipt_no_retiming"}))
        window = profile.request.timeline_window
        self._scheduled_events = tuple(event for event in build_tushare_000703_dividend_scheduled_events_v2(
            profile.request.dividend_profile) if window.data_start <= event.event_at.instant < window.end_exclusive)

    @property
    def fee_policy_components(self) -> tuple[ProfileComponentRef, ProfileComponentRef]:
        """Actual policy identities for the owning public profile registration."""
        return self._market_fees.component_ref, self._taxes.component_ref

    @property
    def scheduled_account_events(self) -> tuple[ScheduledAccountEvent, ...]:
        return self._scheduled_events

    def bar_close_receipt(self, source_event_id: str) -> CnAShareBarCloseReceipt:
        """Project only the exact event retained by this closed profile instance."""
        event = self._close_events.get(source_event_id)
        if event is None:
            raise ValueError("closed receipt source is absent from the resolved profile")
        observation = BarCloseObservation.from_event(event)
        if observation.kind is not BarCloseKind.REAL or observation.close_price is None or event.instrument_id is None:
            raise ValueError("closed receipt requires an actual priced bar")
        return CnAShareBarCloseReceipt(event.instrument_id, observation.close_price,
            observation.interval_start, observation.interval_end_exclusive, event.timeline_instant,
            event.event_id, event.event_hash)

    def _failure(self, source_event_id: str, input_hash: str, code: FinancialDispatchFailureCode,
                 *subjects: str) -> FinancialDispatchOutcome:
        return FinancialDispatchOutcome(self.spec, input_hash, failure=FinancialDispatchFailure(
            self.spec, source_event_id, input_hash, code, tuple(subjects)))

    def resolve_fee_rules(self, query: ProfileFeeRuleQuery, /) -> ProfileFeeRuleResolution:
        """Bind only actual Engine values; delegate every statutory rule to V2."""
        if type(query) is not ProfileFeeRuleQuery:
            raise TypeError("query must be exact ProfileFeeRuleQuery")
        scope = self._fee_authority.scope
        if (query.binding.dispatcher_spec_hash != self.spec.spec_hash
                or query.binding.assessment_currency != CurrencyId("CNY")
                or query.binding.assessment_scale != Scale(2)
                or not scope.coverage_from <= query.evaluated_at.instant < scope.coverage_to_exclusive
                or (query.fill is not None and query.fill.quantity != query.order.intent.quantity)):
            return ProfileFeeRuleResolution(query, None, (query,), "cn_a_share_fee_scope_mismatch")
        binding = bind_cn_a_share_fee_execution_v2(self._fee_authority, query.order)
        if isinstance(binding, CnAShareFeeExecutionBindingFailureV2):
            return ProfileFeeRuleResolution(query, None, (binding,), binding.code.value)
        kernel_query = (CnAShareCashFeeRuleQueryV2.for_reservation(self._fee_authority, binding)
            if query.basis_type is None else CnAShareCashFeeRuleQueryV2.for_final_fill(self._fee_authority, binding, query.fill))
        if isinstance(kernel_query, CnAShareFeeQueryConstructionFailureV2):
            return ProfileFeeRuleResolution(query, None, (kernel_query,), kernel_query.code.value)
        market = self._market_fees.assess_fees(kernel_query)
        tax = self._taxes.assess_taxes(kernel_query)
        evidence: tuple[object, ...] = (market, tax, self._commission)
        if market.result is None or tax.result is None:
            failure = market.failure or tax.failure
            if failure is None:
                raise ValueError("kernel fee outcome has no branch")
            return ProfileFeeRuleResolution(query, None, evidence, failure.code.value)
        order_rules = self._commission.final_order_rule_set(self._market_fees.component_ref, self._taxes.component_ref)
        account_rule = next(rule for rule in order_rules.charge_rules if rule.source is FinalFeeRuleSource.ACCOUNT_SCHEDULE)
        if query.basis_type is None:
            buffer = CnAShareFeeReservationBufferV2.create(market_resolution=market.result,
                tax_resolution=tax.result, maximum_fill_count=1)
            evidence = (*evidence, buffer)
            rule_id = "cn-a-share-commission-reservation:" + canonical_sha256({"scenario": self._commission, "basis": "order_notional"})
            account = FeeReservationChargeRule(FeeReservationRuleSource.ACCOUNT_SCHEDULE, rule_id,
                FeeReservationBasis.ORDER_NOTIONAL, FeeReservationApplicability.APPLIES,
                account_rule.rate, None, account_rule.quantization)
            minimum = order_rules.minimums[0]
            rules = FeeReservationRuleSet.create(market_fee_policy_ref=order_rules.market_fee_policy_ref,
                tax_policy_ref=order_rules.tax_policy_ref, account_fee_schedule_ref=order_rules.account_fee_schedule_ref,
                reservation_currency=order_rules.assessment_currency, reservation_scale=order_rules.assessment_scale,
                charge_rules=(*market.result.reservation_charge_rules, tax.result.reservation_charge_rule,
                    buffer.market_charge_rule, buffer.tax_charge_rule, account),
                minimums=(FeeReservationMinimum(FeeReservationRuleSource.ACCOUNT_SCHEDULE,
                    "cn-a-share-commission-reservation-minimum:" + canonical_sha256(minimum), (rule_id,), minimum.minimum_amount),))
        elif query.basis_type is FeeBasisType.FILL:
            account = FinalFeeChargeRule(FinalFeeRuleSource.ACCOUNT_SCHEDULE,
                "cn-a-share-commission-not-on-fill:" + canonical_sha256(self._commission), FeeBasisType.FILL,
                FinalFeeCalculationBasis.NOTIONAL_RATE, FinalFeeApplicability.NOT_APPLICABLE,
                Rate(0, Scale(0), "fee_fraction"), None, account_rule.quantization)
            rules = FinalFeeRuleSet.create(market_fee_policy_ref=order_rules.market_fee_policy_ref,
                tax_policy_ref=order_rules.tax_policy_ref, account_fee_schedule_ref=order_rules.account_fee_schedule_ref,
                assessment_currency=order_rules.assessment_currency, assessment_scale=order_rules.assessment_scale,
                charge_rules=(*market.result.final_fill_charge_rules, tax.result.final_fill_charge_rule, account), minimums=())
        else:
            rules = FinalFeeRuleSet.create(market_fee_policy_ref=order_rules.market_fee_policy_ref,
                tax_policy_ref=order_rules.tax_policy_ref, account_fee_schedule_ref=order_rules.account_fee_schedule_ref,
                assessment_currency=order_rules.assessment_currency, assessment_scale=order_rules.assessment_scale,
                charge_rules=(*market.result.final_order_not_applicable_rules,
                    tax.result.final_order_not_applicable_rule, account_rule), minimums=order_rules.minimums)
        return ProfileFeeRuleResolution(query, rules, evidence)

    def book_fill(self, plan: FillAccountingDispatchPlan, fill: Fill,
                  state_view: FinancialStateView, /) -> FinancialDispatchOutcome:
        request = self._profile.request
        input_hash = canonical_sha256({"operation": "cn_a_share_settlement_book_fill_v2", "plan": plan,
            "fill": fill, "profile_hash": self._profile.profile_hash, "journal_hash": state_view.journal.journal_hash,
            "settlement_book_hash": state_view.settlement_book.book_hash if state_view.settlement_book else None})
        if (type(plan) is not SettlementFillAccountingDispatchPlan
                or fill.instrument_id != request.instrument_scope.instrument.instrument_id
                or fill.account_id != request.account_scope.account_id
                or not request.timeline_window.trading_start <= fill.execution_time < request.timeline_window.end_exclusive
                or state_view.settlement_book is None
                or state_view.settlement_book.account_id != fill.account_id
                or set(plan.expected_artifact_roles) != {f"position_accounting.{plan.source_event_id}",
                    f"settlement.{plan.source_event_id}", f"settlement_resolution.{plan.source_event_id}"}):
            return self._failure(plan.source_event_id, input_hash, FinancialDispatchFailureCode.FILL_PLAN_MISMATCH,
                "cn_a_share_settlement_scope")
        outcome = super().book_fill(plan, fill, state_view)
        if outcome.result is None:
            return outcome
        base = outcome.result
        if self._closed_bar_execution:
            try:
                query = CnAShareBarCloseSettlementQuery(fill, request.instrument_scope.instrument, base.journal_entries[0],
                    plan.settlement_slots[0].obligation_id, plan.settlement_slots[1].obligation_id,
                    bar_close_receipt=self.bar_close_receipt(plan.source_event_id))
            except (TypeError, ValueError):
                return self._failure(plan.source_event_id, input_hash, FinancialDispatchFailureCode.FILL_PLAN_MISMATCH,
                    "cn_a_share_closed_receipt_mismatch")
        else:
            query = CnAShareSettlementQuery(fill, request.instrument_scope.instrument, base.journal_entries[0],
                plan.settlement_slots[0].obligation_id, plan.settlement_slots[1].obligation_id)
        resolved = self._settlement_model.resolve_settlement(query)
        if resolved.result is None:
            failure = resolved.failure
            if failure is None:  # the kernel port requires exactly one branch
                raise ValueError("settlement outcome has no branch")
            return self._failure(plan.source_event_id, input_hash, FinancialDispatchFailureCode.PROFILE_COMPONENT_FAILURE,
                failure.code.value, failure.subject_key, canonical_sha256(resolved))
        resolution = resolved.result
        book = state_view.settlement_book
        source_hash = canonical_sha256(fill)
        events = []
        for slot, obligation in zip(plan.settlement_slots, resolution.obligations, strict=True):
            events.append(SettlementEvent(slot.recorded_event_id, slot.obligation_id, SettlementEventType.OBLIGATION_RECORDED,
                plan.settlement_recorded_at, fill.fill_id.value, source_hash))
            if obligation.obligation.settlement_time <= plan.fill_recorded_at.instant:
                events.append(SettlementEvent(slot.applied_event_id, slot.obligation_id, SettlementEventType.SETTLEMENT_APPLIED,
                    plan.fill_recorded_at, slot.recorded_event_id, source_hash))
        after = book.append(obligations=resolution.obligations, events=tuple(events))
        component = resolved.component_ref
        artifact = FinancialDispatchArtifact(f"settlement_resolution.{plan.source_event_id}", plan.source_event_id,
            plan.fill_recorded_at, component.component_key, component.component_version, component.component_digest,
            canonical_sha256(query), canonical_sha256(resolved), resolved)
        result = SettlementFinancialDispatchResult(self.spec, base.source_event_id, base.journal_entries,
            base.position_lot_books, (*base.artifacts, artifact), settlement_obligations=resolution.obligations,
            settlement_events=tuple(events), prior_settlement_book_hash=book.book_hash, settlement_book_hash=after.book_hash)
        return FinancialDispatchOutcome(self.spec, input_hash, result=result)

    def dispatch_scheduled_event(self, event: ScheduledAccountEvent, state_view: FinancialStateView,
                                 /) -> FinancialDispatchOutcome:
        if type(event.payload) in (SettlementApplicationPlan, LedgerCashSnapshotProjectionPlan):
            return super().dispatch_scheduled_event(event, state_view)
        if event not in self._scheduled_events:
            return self._failure(event.event_id, canonical_sha256(event), FinancialDispatchFailureCode.EVENT_PLAN_MISMATCH,
                "cn_a_share_scheduled_event_scope")
        outcome = self._dividend.dispatch_scheduled_event(event, state_view)
        # Keep subtype fields when rebinding; the base result is not a lossy DTO adapter.
        return replace(outcome, dispatcher_spec=self.spec,
            result=replace(outcome.result, dispatcher_spec=self.spec) if outcome.result is not None else None,
            failure=replace(outcome.failure, dispatcher_spec=self.spec) if outcome.failure is not None else None)


__all__ = ["CnAShareDevelopmentFinancialDispatcherV2"]
