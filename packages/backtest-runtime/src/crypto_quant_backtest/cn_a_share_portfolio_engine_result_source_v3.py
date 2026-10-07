"""Source-only paired N-stock EngineResult V3 DEVELOPMENT replay, not a formal NAV.

Rebuild A hold/B cash native Journal/Fee/Settlement and working SELL GTC
from bytes. A gap keeps inventory and is never decoded as a zero Fill.
"""
from __future__ import annotations

from crypto_quant_domain import OrderSide, TimeInForce, canonical_bytes
from crypto_quant_trading import LedgerSchema

from .cn_a_share_portfolio_engine_case_v3 import CnASharePortfolioEngineDevelopmentResultV3
from .cn_a_share_portfolio_engine_result_source_v1 import (
    _fields, _financial_source_facts, _sequence, _settlement,
)
from .cn_a_share_portfolio_financial_development_v1 import (
    CnASharePortfolioFinancialBatchDevelopmentV2, CnASharePortfolioNoFillDevelopmentV1,
)
from .cn_a_share_portfolio_next_open_development_v1 import CnASharePortfolioNextOpenDevelopmentOutcomeV1
from .execution import NoEligibleBarAction
from .execution_inputs import _read_instrument_id, _read_order_event_stream
from .target_repository import _artifact_ref


def _blocked(value: object) -> CnASharePortfolioNoFillDevelopmentV1:
    data = _fields(value, {"type", "schema_version", "stream", "outcome"}, "blocked Order")
    if data["type"] != "cn_a_share_portfolio_no_fill_development" or data["schema_version"] != 1:
        raise ValueError("portfolio Engine V3 blocked Order version mismatch")
    stream = _read_order_event_stream(data["stream"])
    raw = _fields(data["outcome"], {"type", "schema_version", "plan_hash", "order_stream_hash",
                   "observation_hash", "risk_approval_hash", "action", "reason", "fill",
                   "synthetic_development_only", "trade_authorized"}, "blocked outcome")
    if (raw["type"] != "cn_a_share_portfolio_next_open_development_outcome"
            or raw["schema_version"] != 1 or raw["synthetic_development_only"] is not True
            or raw["trade_authorized"] is not False or raw["fill"] is not None
            or stream.order.intent.side is not OrderSide.SELL
            or stream.order.intent.time_in_force is not TimeInForce.GTC):
        raise ValueError("portfolio Engine V3 blocked SELL GTC grade/side mismatch")
    outcome = CnASharePortfolioNextOpenDevelopmentOutcomeV1(
        raw["plan_hash"], raw["order_stream_hash"], raw["observation_hash"],
        raw["risk_approval_hash"], NoEligibleBarAction(raw["action"]), raw["reason"], None)
    if outcome.action is not NoEligibleBarAction.KEEP_ACTIVE:
        raise ValueError("portfolio Engine V3 gap SELL GTC must stay working")
    result = CnASharePortfolioNoFillDevelopmentV1(stream, outcome)
    if canonical_bytes(data) != canonical_bytes(result):
        raise ValueError("portfolio Engine V3 blocked Order source reconstruction mismatch")
    return result

def _batch_v2(value: object, ledger_schema: LedgerSchema) -> CnASharePortfolioFinancialBatchDevelopmentV2:
    data = _fields(value, {"type", "schema_version", "universe", "prior_journal_hash",
                           "journal", "ledger_state", "fills", "fee_assessments", "blocked",
                           "synthetic_development_only", "trade_authorized"}, "variable-N batch")
    if (data["type"] != "cn_a_share_portfolio_financial_batch_development"
            or type(data["schema_version"]) is not int or data["schema_version"] != 2
            or data["synthetic_development_only"] is not True or data["trade_authorized"] is not False):
        raise ValueError("portfolio Engine V3 result cannot elevate grade")
    blocked = tuple(_blocked(item) for item in _sequence(data["blocked"], "working blocked orders"))
    universe = tuple(_read_instrument_id(item) for item in _sequence(data["universe"], "stock universe"))
    journal, ledger, fills, fees = _financial_source_facts(data, ledger_schema)
    result = CnASharePortfolioFinancialBatchDevelopmentV2(
        universe, data["prior_journal_hash"], journal, ledger, fills, fees, blocked)
    if canonical_bytes(data) != canonical_bytes(result):
        raise ValueError("portfolio Engine V3 BatchV2 source reconstruction mismatch")
    return result


def read_cn_a_share_portfolio_engine_development_result_source_v3(
    source: object, *, ledger_schema: LedgerSchema,
) -> CnASharePortfolioEngineDevelopmentResultV3:
    """Only whole native source; no typed caller Result or source-unknown NAV."""
    if type(ledger_schema) is not LedgerSchema:
        raise TypeError("portfolio V3 source needs a frozen V8 LedgerSchema")
    data = _fields(source, {"type", "schema_version", "case_hash", "source_ref", "account_arm",
                            "first_batch", "first_settlement", "matured_first_settlement",
                            "second_batch", "second_settlement", "synthetic_development_only",
                            "trade_authorized"}, "paired result")
    if (data["type"] != "cn_a_share_portfolio_engine_development_result"
            or type(data["schema_version"]) is not int or data["schema_version"] != 3
            or data["synthetic_development_only"] is not True or data["trade_authorized"] is not False):
        raise ValueError("portfolio Engine V3 result cannot elevate development grade")
    ref = _artifact_ref(data["source_ref"])
    if ref.artifact_type != "backtest_execution_input_bundle" or ref.schema_version != 8:
        raise ValueError("portfolio Engine V3 result source ref must be V8")
    first = _batch_v2(data["first_batch"], ledger_schema)
    second = None if data["second_batch"] is None else _batch_v2(data["second_batch"], ledger_schema)
    first_book = _settlement(data["first_settlement"])
    matured = _settlement(data["matured_first_settlement"])
    second_book = None if data["second_settlement"] is None else _settlement(data["second_settlement"])
    result = CnASharePortfolioEngineDevelopmentResultV3(
        data["case_hash"], ref, data["account_arm"], first, first_book, matured,
        second, second_book)
    if canonical_bytes(data) != canonical_bytes(result):
        raise ValueError("portfolio Engine V3 paired Result source reconstruction mismatch")
    return result
