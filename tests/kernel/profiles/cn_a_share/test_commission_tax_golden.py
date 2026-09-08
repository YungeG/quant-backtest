from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

from crypto_quant_domain import (
    DomainIdKind,
    OrderSide,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    canonical_bytes,
)
from crypto_quant_trading import (
    FeeAssessmentBasisEvidence,
    FeeAssessmentEngine,
    FeeChargedJournalTranslator,
    FeeReservationEstimator,
    FinalFeeAssessmentResult,
    OrderEventStream,
)
from crypto_quant_trading.profiles.cn_a_share import (
    CnAShareCashMarketFeePolicy,
    CnAShareFeeTradeMechanism,
    CnAShareMarketFeeRuleBook,
)
from tests.kernel.profiles.cn_a_share._commission_tax_fixtures import (
    cash_key,
    domain_id,
    fee_query,
    filled_stream,
    final_fill_rule_set,
    final_order_rule_set,
    local_instant,
    market_rule_approval,
    market_rule_book,
    partial_cancelled_stream,
    policies,
    reservation_buffer,
    reservation_rule_set,
    reservation_states,
    single_fill_stream,
    tax_rule_book,
    unfilled_cancelled_stream,
)


ROOT = Path(__file__).resolve().parents[4]
FIXTURE = ROOT / "tests/fixtures/kernel/profiles/cn_a_share/commission-tax-v1.json"


def _read_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"cannot read canonical JSON: {path.name}") from error
    assert isinstance(value, dict)
    return value


def _reservation(
    side: OrderSide, effective_at: UtcInstant, quantity: int
) -> dict[str, object]:
    outcome = FeeReservationEstimator().estimate(
        market_rule_approval(
            quantity_units=quantity, side=side, effective_at=effective_at
        ),
        reservation_rule_set(side=side, effective_at=effective_at),
        UtcInstant(effective_at.epoch_nanoseconds + 1),
    )
    assert outcome.estimate is not None and outcome.proposal is not None
    return {
        "estimate_id": outcome.estimate.estimate_id,
        "estimate_hash": outcome.estimate.estimate_hash,
        "maximum_fill_count": 2,
        "rule_set_hash": outcome.estimate.rule_set.rule_set_hash,
        "lines": outcome.estimate.lines,
        "total_fee": outcome.estimate.total_fee,
        "proposal_id": outcome.proposal.proposal_id,
        "commitment": outcome.proposal.commitment,
    }


def _assess_stream(
    stream: OrderEventStream, effective_at: UtcInstant
) -> dict[str, object]:
    basis = FeeAssessmentBasisEvidence.for_order(stream)
    reservation_buffer(
        side=basis.order_streams[0].order.intent.side,
        effective_at=effective_at,
    ).require_covers_fills(basis.fills)
    engine = FeeAssessmentEngine()
    fill_results = []
    journal_entries = []
    for index, value in enumerate(basis.fills, start=1):
        outcome = engine.assess(
            basis=FeeAssessmentBasisEvidence.for_fill(value),
            rule_set=final_fill_rule_set(value),
            fee_assessment_id=domain_id(DomainIdKind.FEE, str(index)),
            assessment_time=UtcInstant(value.execution_time.epoch_nanoseconds + 1),
        )
        assert outcome.result is not None
        fill_results.append(outcome.result)
    order = engine.assess(
        basis=basis,
        rule_set=final_order_rule_set(
            side=basis.order_streams[0].order.intent.side,
            effective_at=effective_at,
        ),
        fee_assessment_id=domain_id(DomainIdKind.FEE, "3"),
        assessment_time=UtcInstant(effective_at.epoch_nanoseconds + 10),
    )
    assert order.result is not None
    for index, result in enumerate((*fill_results, order.result), start=4):
        if result.assessment.amount.units <= 0:
            continue
        translated = FeeChargedJournalTranslator().translate(
            result=result,
            cash_key=cash_key(),
            journal_entry_id=domain_id(DomainIdKind.JOURNAL, str(index)),
            recorded_at=SimulationInstant(
                UtcInstant(effective_at.epoch_nanoseconds + 20 + index),
                TimelinePhase(90, "fees"),
                SourceSequence(index),
            ),
        )
        assert translated.result is not None
        journal_entries.append(translated.result.journal_entry)
    def summary(result: FinalFeeAssessmentResult) -> dict[str, object]:
        return {
            "result_hash": result.result_hash,
            "basis_hash": result.basis.basis_hash,
            "rule_set_hash": result.rule_set.rule_set_hash,
            "lines": result.lines,
            "minimum_adjustments": result.minimum_adjustments,
            "assessment": result.assessment,
            "rule_identity_ids": result.rule_identity_ids,
        }

    return {
        "basis_hash": basis.basis_hash,
        "fill_results": tuple(summary(value) for value in fill_results),
        "order_result": summary(order.result),
        "journal_entries": tuple(journal_entries),
        "final_total_units": sum(
            value.assessment.amount.units for value in fill_results
        )
        + order.result.assessment.amount.units,
    }


def build_actual() -> dict[str, object]:
    market, tax = policies()
    old_at = local_instant(25, 10)
    new_at = local_instant(28, 10)
    old_query = fee_query(OrderSide.SELL, old_at)
    new_query = fee_query(OrderSide.SELL, new_at)
    buy_query = fee_query(OrderSide.BUY, new_at)

    old_market = market.assess_fees(old_query)
    new_market = market.assess_fees(new_query)
    old_tax = tax.assess_taxes(old_query)
    new_tax = tax.assess_taxes(new_query)
    buy_tax = tax.assess_taxes(buy_query)
    assert old_market.result is not None and new_market.result is not None
    assert old_tax.result is not None and new_tax.result is not None
    assert buy_tax.result is not None

    gap = market.assess_fees(fee_query(OrderSide.SELL, local_instant(30)))
    block = market.assess_fees(
        fee_query(
            OrderSide.SELL,
            new_at,
            mechanism=CnAShareFeeTradeMechanism.BLOCK,
        )
    )
    base_book = market_rule_book()
    overlap_band = replace(
        next(
            band
            for band in base_book.bands
            if band.venue_id.value == "xshg" and band.effective_from == local_instant(25)
        ),
        effective_from=local_instant(27),
        effective_to_exclusive=local_instant(29),
    )
    overlap = CnAShareCashMarketFeePolicy(
        CnAShareMarketFeeRuleBook(
            "equity.cn_a_share.cash.market-fees.overlap-control.v1",
            1,
            (*base_book.bands, overlap_band),
        )
    ).assess_fees(new_query)
    assert gap.failure is not None and block.failure is not None
    assert overlap.failure is not None

    partial_stream = partial_cancelled_stream(
        quantity_units=1_000,
        side=OrderSide.SELL,
        effective_at=new_at,
    )
    partial_reservation = FeeReservationEstimator().estimate(
        market_rule_approval(
            quantity_units=1_000,
            side=OrderSide.SELL,
            effective_at=new_at,
        ),
        reservation_rule_set(side=OrderSide.SELL, effective_at=new_at),
        UtcInstant(new_at.epoch_nanoseconds + 1),
    )
    assert partial_reservation.proposal is not None
    accepted_state, partial_state, terminal_state = reservation_states(
        partial_reservation.proposal, partial_stream
    )
    partial = _assess_stream(
        partial_stream,
        UtcInstant(new_at.epoch_nanoseconds + 50),
    )
    partial_final_total = partial["final_total_units"]
    assert isinstance(partial_final_total, int)
    partial["reservation_release"] = {
        "accepted_state_hash": accepted_state.state_hash,
        "accepted_totals": accepted_state.totals,
        "partial_state_hash": partial_state.state_hash,
        "partial_totals": partial_state.totals,
        "terminal_state_hash": terminal_state.state_hash,
        "terminal_totals": terminal_state.totals,
        "released_after_final_units": 1_068 - partial_final_total,
    }
    rounding_stream = filled_stream(
        quantity_units=200,
        side=OrderSide.SELL,
        effective_at=new_at,
    )
    rounding = _assess_stream(
        rounding_stream,
        UtcInstant(new_at.epoch_nanoseconds + 30),
    )
    adversarial = _assess_stream(
        filled_stream(
            quantity_units=600,
            side=OrderSide.SELL,
            effective_at=new_at,
            fill_quantities=(200, 400),
        ),
        UtcInstant(new_at.epoch_nanoseconds + 30),
    )
    rounding_fills = FeeAssessmentBasisEvidence.for_order(rounding_stream).fills
    try:
        reservation_buffer(
            side=OrderSide.SELL, effective_at=new_at
        ).require_covers_fills((*rounding_fills, rounding_fills[0]))
    except ValueError as error:
        overflow_failure = str(error)
    else:
        raise AssertionError("fill-count overflow must fail closed")
    unfilled = _assess_stream(
        unfilled_cancelled_stream(side=OrderSide.SELL, effective_at=new_at),
        UtcInstant(new_at.epoch_nanoseconds + 30),
    )
    old_sell_final = _assess_stream(
        single_fill_stream(
            quantity_units=1_000,
            side=OrderSide.SELL,
            effective_at=old_at,
        ),
        UtcInstant(old_at.epoch_nanoseconds + 20),
    )
    new_buy_final = _assess_stream(
        single_fill_stream(
            quantity_units=1_000,
            side=OrderSide.BUY,
            effective_at=new_at,
        ),
        UtcInstant(new_at.epoch_nanoseconds + 20),
    )

    payload = {
        "fixture_id": "cn-a-share-commission-tax-v1",
        "qualification": {
            "allowed_grade": "development",
            "deployment_authorized": False,
            "supported": (
                "standard-domestic-xshg-cny-cash-auction-a-share",
                "standard-domestic-xshe-cny-cash-auction-a-share",
            ),
            "limitations": (
                "synthetic-net-broker-commission-not-provider-parity",
                "block-trade-b-share-fund-stock-connect-margin-not-supported",
                "finite-2023-08-25-through-2023-08-29-coverage",
                "cny-cent-half-up-is-a-development-system-convention",
                "reservation-rounding-bound-requires-maximum-fill-count-2",
            ),
            "official_facts": {
                "old_handling_per_mille": "0.0487",
                "new_handling_per_mille": "0.0341",
                "regulatory_per_mille": "0.02",
                "transfer_per_mille": "0.01",
                "old_sell_stamp_per_mille": "1",
                "new_sell_stamp_per_mille": "0.5",
                "transition_local_date": "2023-08-28",
            },
        },
        "source_evidence": {
            "market_rule_book": market_rule_book(),
            "market_rule_book_hash": market.rule_book.rule_book_hash,
            "tax_rule_book": tax_rule_book(),
            "tax_rule_book_hash": tax.rule_book.rule_book_hash,
        },
        "components": {
            "market": market.component_ref,
            "tax": tax.component_ref,
        },
        "transition": {
            "old_market": old_market.result,
            "new_market": new_market.result,
            "old_tax": old_tax.result,
            "new_tax": new_tax.result,
            "buy_tax": buy_tax.result,
            "xshe_market": market.assess_fees(
                fee_query(OrderSide.SELL, new_at, venue="xshe")
            ).result,
            "xshe_tax": tax.assess_taxes(
                fee_query(OrderSide.SELL, new_at, venue="xshe")
            ).result,
            "resolution_hashes": {
                "old_market": old_market.result.resolution_hash,
                "new_market": new_market.result.resolution_hash,
                "old_tax": old_tax.result.resolution_hash,
                "new_tax": new_tax.result.resolution_hash,
                "buy_tax": buy_tax.result.resolution_hash,
            },
        },
        "failures": {
            "gap": gap.failure,
            "block": block.failure,
            "overlap": overlap.failure,
        },
        "reservation_buffer": {
            "sell": reservation_buffer(
                side=OrderSide.SELL,
                effective_at=new_at,
                maximum_fill_count=2,
            ),
            "buy": reservation_buffer(
                side=OrderSide.BUY,
                effective_at=new_at,
                maximum_fill_count=2,
            ),
            "covers_two_fills": reservation_buffer(
                side=OrderSide.SELL, effective_at=new_at
            ).covers_fill_count(2),
            "rejects_three_fills": not reservation_buffer(
                side=OrderSide.SELL, effective_at=new_at
            ).covers_fill_count(3),
        },
        "reservation_controls": {
            "old_sell_10000": _reservation(OrderSide.SELL, old_at, 1_000),
            "new_sell_10000": _reservation(OrderSide.SELL, new_at, 1_000),
            "new_buy_10000": _reservation(OrderSide.BUY, new_at, 1_000),
            "new_sell_2000": _reservation(OrderSide.SELL, new_at, 200),
            "new_sell_6000_adversarial": _reservation(
                OrderSide.SELL, new_at, 600
            ),
        },
        "final_controls": {
            "partial_cancel": partial,
            "rounding": rounding,
            "adversarial_rounding": adversarial,
            "fill_count_overflow_failure": overflow_failure,
            "unfilled_cancel": unfilled,
            "old_sell_single_fill": old_sell_final,
            "new_buy_single_fill": new_buy_final,
        },
    }
    decoded = json.loads(canonical_bytes(payload))
    assert isinstance(decoded, dict)
    return decoded


def test_commission_tax_matches_static_golden() -> None:
    assert build_actual() == _read_json(FIXTURE)
