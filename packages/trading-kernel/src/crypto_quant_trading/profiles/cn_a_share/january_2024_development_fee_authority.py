"""Finite January-2024 development fee authority and commission scenarios."""

from __future__ import annotations

from dataclasses import dataclass

from crypto_quant_domain import (
    CurrencyId,
    DomainId,
    FeeBasisType,
    Money,
    OrderStatus,
    QuantizationPolicy,
    Rate,
    RoundingPolicy,
    Scale,
    UtcInstant,
    VenueId,
    canonical_sha256,
)
from crypto_quant_trading.fee_reservations import AccountFeeScheduleRef
from crypto_quant_trading.fees import (
    FeeAssessmentBasisEvidence,
    FeeAssessmentEngine,
    FinalFeeApplicability,
    FinalFeeAssessmentOutcome,
    FinalFeeCalculationBasis,
    FinalFeeChargeRule,
    FinalFeeMinimum,
    FinalFeeRuleSet,
    FinalFeeRuleSource,
)
from crypto_quant_trading.orders import OrderEventStream
from crypto_quant_trading.ports import ProfileComponentRef

from .commission_tax import CnAShareFeeRuleSourceRef
from .commission_tax_v2 import (
    CnAShareExecutionAccessRoute,
    CnAShareFeeProductClass,
    CnAShareMarketFeeBandV2,
    CnAShareMarketFeeRuleBookV2,
    CnAShareStampDutyBandV2,
    CnAShareStampDutyRuleBookV2,
)


JANUARY_2024_AUTHORITY_SNAPSHOT_SHA256 = (
    "sha256:87ef8b1b555e654c8f253c0a221b35ed566b0e9a7a9c010119f7e28f5a3d549b"
)
_START = UtcInstant(1_704_124_800_000_000_000)
_END = UtcInstant(1_706_716_800_000_000_000)
_CNY = CurrencyId("CNY")
_CENT = Scale(2)
_ZERO = Rate(0, Scale(0), "fee_fraction")
_QUANTIZATION = QuantizationPolicy(
    "cn-a-share-january-2024-commission.cny-cent.half-up.v1",
    _CENT,
    RoundingPolicy.HALF_UP,
)


def _source(source_key: str, source_hash: str) -> CnAShareFeeRuleSourceRef:
    return CnAShareFeeRuleSourceRef(source_key, source_hash)


def _schedule_key(scenario_key: str) -> str:
    return (
        "development.cn-a-share.cash.domestic.ordinary-a-share.2024-01."
        f"commission.{scenario_key}"
    )


def _schedule_payload(scenario_key: str, rate: Rate) -> dict[str, object]:
    return {
        "type": "cn_a_share_january_2024_development_commission_schedule",
        "schema_version": 1,
        "scenario_key": scenario_key,
        "commission_rate": rate,
        "minimum_amount": Money(500, _CENT, "CNY"),
        "quantization": _QUANTIZATION,
        "basis_type": FeeBasisType.ORDER.value,
        "one_full_fill_only": True,
        "access_route": CnAShareExecutionAccessRoute.DOMESTIC.value,
        "fee_product_class": CnAShareFeeProductClass.ORDINARY_A_SHARE.value,
        "authority_snapshot_sha256": JANUARY_2024_AUTHORITY_SNAPSHOT_SHA256,
        "coverage_from": _START,
        "coverage_to_exclusive": _END,
        "development_only": True,
    }


@dataclass(frozen=True, slots=True)
class CnAShareJanuary2024CommissionScenario:
    scenario_key: str
    commission_rate: Rate
    account_fee_schedule_ref: AccountFeeScheduleRef
    development_only: bool

    def __post_init__(self) -> None:
        if self.scenario_key not in {"3bps", "5bps", "8bps"}:
            raise ValueError("scenario_key must be one of 3bps, 5bps, or 8bps")
        if (
            type(self.commission_rate) is not Rate
            or self.commission_rate.basis != "fee_fraction"
            or self.commission_rate.scale != Scale(4)
            or self.commission_rate.units not in {3, 5, 8}
        ):
            raise ValueError("commission_rate must be a 3, 5, or 8 bps fee_fraction")
        if type(self.development_only) is not bool or not self.development_only:
            raise ValueError("commission scenarios must be development-only")
        expected = AccountFeeScheduleRef(
            _schedule_key(self.scenario_key),
            1,
            canonical_sha256(_schedule_payload(self.scenario_key, self.commission_rate)),
        )
        if self.account_fee_schedule_ref != expected:
            raise ValueError("account fee schedule identity mismatch")

    def final_order_rule_set(
        self,
        market_fee_policy_ref: ProfileComponentRef,
        tax_policy_ref: ProfileComponentRef,
        /,
    ) -> FinalFeeRuleSet:
        account_rule_id = "cn-a-share-january-2024-commission:" + canonical_sha256(
            {
                "scenario": self,
                "purpose": "final_order",
                "basis": FeeBasisType.ORDER.value,
            }
        )
        minimum_id = "cn-a-share-january-2024-commission-minimum:" + canonical_sha256(
            {
                "scenario": self,
                "charge_rule_id": account_rule_id,
                "purpose": "final_order",
            }
        )
        return FinalFeeRuleSet.create(
            market_fee_policy_ref=market_fee_policy_ref,
            tax_policy_ref=tax_policy_ref,
            account_fee_schedule_ref=self.account_fee_schedule_ref,
            assessment_currency=_CNY,
            assessment_scale=_CENT,
            charge_rules=(
                FinalFeeChargeRule(
                    FinalFeeRuleSource.MARKET_FEE,
                    "cn-a-share-january-2024-market-fee-not-applicable",
                    FeeBasisType.ORDER,
                    FinalFeeCalculationBasis.NOTIONAL_RATE,
                    FinalFeeApplicability.NOT_APPLICABLE,
                    _ZERO,
                    None,
                    _QUANTIZATION,
                ),
                FinalFeeChargeRule(
                    FinalFeeRuleSource.TAX,
                    "cn-a-share-january-2024-stamp-duty-not-applicable",
                    FeeBasisType.ORDER,
                    FinalFeeCalculationBasis.NOTIONAL_RATE,
                    FinalFeeApplicability.NOT_APPLICABLE,
                    _ZERO,
                    None,
                    _QUANTIZATION,
                ),
                FinalFeeChargeRule(
                    FinalFeeRuleSource.ACCOUNT_SCHEDULE,
                    account_rule_id,
                    FeeBasisType.ORDER,
                    FinalFeeCalculationBasis.NOTIONAL_RATE,
                    FinalFeeApplicability.ALWAYS,
                    self.commission_rate,
                    None,
                    _QUANTIZATION,
                ),
            ),
            minimums=(
                FinalFeeMinimum(
                    FinalFeeRuleSource.ACCOUNT_SCHEDULE,
                    minimum_id,
                    FeeBasisType.ORDER,
                    (account_rule_id,),
                    Money(500, _CENT, "CNY"),
                ),
            ),
        )

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_january_2024_commission_scenario",
            "schema_version": 1,
            "scenario_key": self.scenario_key,
            "commission_rate": self.commission_rate,
            "account_fee_schedule_ref": self.account_fee_schedule_ref,
            "development_only": self.development_only,
        }


def january_2024_fee_rule_books() -> tuple[
    CnAShareMarketFeeRuleBookV2, CnAShareStampDutyRuleBookV2
]:
    market = CnAShareMarketFeeRuleBookV2(
        "equity.cn-a-share.cash.market-fees.domestic.ordinary-a-share.2024-01",
        2,
        CnAShareExecutionAccessRoute.DOMESTIC,
        CnAShareFeeProductClass.ORDINARY_A_SHARE,
        (
            CnAShareMarketFeeBandV2(
                VenueId("xshe"),
                _START,
                _END,
                True,
                Rate(341, Scale(7), "fee_fraction"),
                (
                    _source(
                        "szse-handling-fee-2023-08-18",
                        "sha256:6645a32b6ab297741f22e6b8e959342bb4c9312757d0f1d99de37a0a410d12ba",
                    ),
                ),
                True,
                Rate(2, Scale(5), "fee_fraction"),
                (
                    _source(
                        "ndrc-mof-2018-917",
                        "sha256:4c8c8426c7cc797a99a86f8d8bea21fef8f1a944d1ef14857286c9784085b3c8",
                    ),
                    _source(
                        "szse-fee-document-2025-12-json",
                        "sha256:e64eb8ad2692722a9ba8dbf633fea63c94ccba12aac14826211df72a3cdce3e0",
                    ),
                    _source(
                        "szse-fee-selector",
                        "sha256:34ce00d7302d79f7779c1774ba75db6775caf3d1772c5d60fe85eeeb0a1f0400",
                    ),
                ),
                True,
                Rate(1, Scale(5), "fee_fraction"),
                (
                    _source(
                        "chinaclear-transfer-fee-2022-04-28",
                        "sha256:68763b8fe13f7fb90f378b077033b692aafc4eca851c78c18a306b001d591a60",
                    ),
                ),
                False,
                _ZERO,
                (
                    _source(
                        "chinaclear-stock-connect-detail",
                        "sha256:306141bd99aeddc9ae720be8fb08941deb945640511e02c28eb9c7a47be6575f",
                    ),
                ),
            ),
        ),
    )
    stamp = CnAShareStampDutyRuleBookV2(
        "equity.cn-a-share.cash.stamp-duty.domestic.ordinary-a-share.2024-01",
        2,
        CnAShareExecutionAccessRoute.DOMESTIC,
        CnAShareFeeProductClass.ORDINARY_A_SHARE,
        (
            CnAShareStampDutyBandV2(
                VenueId("xshe"),
                _START,
                _END,
                True,
                Rate(5, Scale(4), "fee_fraction"),
                (
                    _source(
                        "mof-sta-stamp-duty-2023-39",
                        "sha256:bdad8369ee854d205de9a1e355beecc4fa7841f7293e332997e6cadd2b923c35",
                    ),
                    _source(
                        "sta-stamp-tax-law",
                        "sha256:b9c03f76774935b5bc40c46b88d69de5391128269d84cf9ee08df812de44f699",
                    ),
                    _source(
                        "sta-stamp-tax-rate-table",
                        "sha256:60ef5ae1dfb9631d84ee09247748ca292a4c81cb995a47aa0fab89206ee5aa64",
                    ),
                ),
            ),
        ),
    )
    return market, stamp


def january_2024_commission_scenarios() -> tuple[
    CnAShareJanuary2024CommissionScenario, ...
]:
    return tuple(
        CnAShareJanuary2024CommissionScenario(
            scenario_key,
            rate,
            AccountFeeScheduleRef(
                _schedule_key(scenario_key),
                1,
                canonical_sha256(_schedule_payload(scenario_key, rate)),
            ),
            True,
        )
        for scenario_key, rate in (
            ("3bps", Rate(3, Scale(4), "fee_fraction")),
            ("5bps", Rate(5, Scale(4), "fee_fraction")),
            ("8bps", Rate(8, Scale(4), "fee_fraction")),
        )
    )


def assess_january_2024_commission(
    scenario: CnAShareJanuary2024CommissionScenario,
    stream: OrderEventStream,
    market_fee_policy_ref: ProfileComponentRef,
    tax_policy_ref: ProfileComponentRef,
    fee_assessment_id: DomainId,
    assessment_time: UtcInstant,
    /,
) -> FinalFeeAssessmentOutcome:
    if type(scenario) is not CnAShareJanuary2024CommissionScenario:
        raise TypeError("scenario must be concrete CnAShareJanuary2024CommissionScenario")
    if type(stream) is not OrderEventStream:
        raise TypeError("stream must be concrete OrderEventStream")
    fills = tuple(record.fill for record in stream.records if record.fill is not None)
    state = stream.state
    if state is None or not (_START <= state.updated_at.instant < _END):
        raise ValueError("development commission scenario is outside January authority")
    if fills and (
        state.status is not OrderStatus.FILLED
        or len(fills) != 1
        or fills[0].order_id != stream.order.order_id
        or fills[0].quantity != state.ordered_quantity
        or state.cumulative_filled_quantity != state.ordered_quantity
    ):
        raise ValueError("development commission scenario requires one full fill")
    return FeeAssessmentEngine().assess(
        basis=FeeAssessmentBasisEvidence.for_order(stream),
        rule_set=scenario.final_order_rule_set(market_fee_policy_ref, tax_policy_ref),
        fee_assessment_id=fee_assessment_id,
        assessment_time=assessment_time,
    )
