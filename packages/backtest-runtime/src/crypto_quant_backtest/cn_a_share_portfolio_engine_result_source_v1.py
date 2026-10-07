"""Independent DEVELOPMENT Engine result source rehydration; not formal PnL evidence."""
from __future__ import annotations

from collections.abc import Mapping

from crypto_quant_domain import (
    AccountingEntryType, FeeAssessment, FeeBasisType, Money, canonical_bytes,
)
from crypto_quant_trading import GenericLedger, LedgerSchema

from .cn_a_share_portfolio_engine_case_v1 import CnASharePortfolioEngineDevelopmentResultV1
from .cn_a_share_portfolio_financial_development_v1 import CnASharePortfolioFinancialBatchDevelopmentV1
from .cn_a_share_portfolio_settlement_development_v1 import (
    CnASharePortfolioSettlementDevelopmentV1,
    read_cn_a_share_portfolio_settlement_book_source_v1,
)
from .execution_inputs import (
    _read_domain_id, _read_fill, _read_journal, _read_money, _read_utc,
)
from .target_repository import _artifact_ref


def _fields(value: object, expected: set[str], role: str) -> Mapping:
    if not isinstance(value, Mapping) or set(value) != expected:
        raise ValueError(f"portfolio Engine {role} source has wrong fields")
    return value


def _sequence(value: object, role: str) -> tuple:
    if not isinstance(value, (tuple, list)):
        raise ValueError(f"portfolio Engine {role} must be a source sequence")
    return tuple(value)


def _fee(value: object) -> FeeAssessment:
    data = _fields(value, {"type", "fee_assessment_id", "basis_type", "basis_ids",
                          "market_fee_rule_id", "account_fee_schedule_id", "tax_rule_id",
                          "amount", "assessment_time"}, "fee")
    if data["type"] != "fee_assessment":
        raise ValueError("portfolio Engine fee source tag mismatch")
    basis = FeeBasisType(data["basis_type"])
    if basis not in (FeeBasisType.FILL, FeeBasisType.ORDER):
        raise ValueError("portfolio Engine session fee requires separate source decoder")
    result = FeeAssessment(
        _read_domain_id(data["fee_assessment_id"]), basis,
        tuple(_read_domain_id(item) for item in _sequence(data["basis_ids"], "fee basis")),
        data["market_fee_rule_id"], data["account_fee_schedule_id"], data["tax_rule_id"],
        _read_money(data["amount"]), _read_utc(data["assessment_time"]),
    )
    if canonical_bytes(data) != canonical_bytes(result):
        raise ValueError("portfolio Engine fee source reconstruction mismatch")
    return result


def _financial_source_facts(data: Mapping, ledger_schema: LedgerSchema):
    """Reproject actual Fill/Fee/Journal source once for V1 and V3 readers."""
    ledger_source = _fields(data["ledger_state"], {"type", "schema_hash", "cursor", "cash_balances",
                        "position_balances", "realized_pnl", "fees", "financing"}, "Ledger")
    if type(ledger_schema) is not LedgerSchema or ledger_source["schema_hash"] != ledger_schema.schema_hash:
        raise ValueError("portfolio Engine source LedgerSchema hash mismatch")
    journal = _read_journal(data["journal"])
    ledger = GenericLedger(ledger_schema).project(journal)
    if canonical_bytes(ledger) != canonical_bytes(data["ledger_state"]):
        raise ValueError("portfolio Engine Ledger source mismatch")
    fills = tuple(_read_fill(item) for item in _sequence(data["fills"], "Fills"))
    fees = tuple(_fee(item) for item in _sequence(data["fee_assessments"], "fees"))
    fee_ids = {fee.fee_assessment_id.value for fee in fees}
    if len(fee_ids) != len(fees):
        raise ValueError("portfolio Engine duplicate FeeAssessment identity")
    charged = tuple(entry for entry in journal.entries if entry.entry_type is AccountingEntryType.FEE_CHARGED
                    and any(fid in entry.source_ids for fid in fee_ids))
    if len(charged) != len(fees):
        raise ValueError("portfolio Engine fee entries missing from native Journal")
    for fee in fees:
        matching = tuple(entry for entry in charged if fee.fee_assessment_id.value in entry.source_ids)
        if (len(matching) != 1 or fee.amount.currency != "CNY" or fee.amount.scale.places != 2
                or sum(value.units for value in matching[0].fees) != fee.amount.units
                or any(basis.value not in matching[0].source_ids for basis in fee.basis_ids)
                or any(rule is not None and rule not in matching[0].source_ids for rule in (
                    fee.market_fee_rule_id, fee.account_fee_schedule_id, fee.tax_rule_id))
                or not any(isinstance(change.value, Money) and change.value.units == -fee.amount.units
                           for change in matching[0].balance_changes)):
            raise ValueError("portfolio Engine fee assessments do not match native Journal cash charges")
    return journal, ledger, fills, fees


def _batch(value: object, ledger_schema: LedgerSchema) -> CnASharePortfolioFinancialBatchDevelopmentV1:
    data = _fields(value, {"type", "schema_version", "prior_journal_hash", "journal",
                           "ledger_state", "fills", "fee_assessments", "blocked",
                           "synthetic_development_only", "trade_authorized"}, "batch")
    if (data["type"] != "cn_a_share_portfolio_financial_batch_development"
            or type(data["schema_version"]) is not int or data["schema_version"] != 1
            or data["synthetic_development_only"] is not True or data["trade_authorized"] is not False
            or _sequence(data["blocked"], "blocked orders")):
        raise ValueError("portfolio Engine owner publishes only fully filled synthetic development batch")
    journal, ledger, fills, fees = _financial_source_facts(data, ledger_schema)
    result = CnASharePortfolioFinancialBatchDevelopmentV1(
        data["prior_journal_hash"], journal, ledger, fills, fees)
    if canonical_bytes(data) != canonical_bytes(result):
        raise ValueError("portfolio Engine batch source reconstruction mismatch")
    return result


def _settlement(value: object) -> CnASharePortfolioSettlementDevelopmentV1:
    data = _fields(value, {"type", "schema_version", "financial_batch_hash", "calendar_hashes",
                           "book", "synthetic_development_only", "trade_authorized"}, "settlement")
    if (data["type"] != "cn_a_share_portfolio_settlement_development"
            or type(data["schema_version"]) is not int or data["schema_version"] != 1
            or data["synthetic_development_only"] is not True or data["trade_authorized"] is not False):
        raise ValueError("portfolio Engine settlement grade mismatch")
    calendars = _sequence(data["calendar_hashes"], "calendar hashes")
    if len(calendars) != 2:
        raise ValueError("portfolio Engine settlement needs both venue calendars")
    result = CnASharePortfolioSettlementDevelopmentV1(
        data["financial_batch_hash"], (calendars[0], calendars[1]),
        read_cn_a_share_portfolio_settlement_book_source_v1(data["book"]))
    if canonical_bytes(data) != canonical_bytes(result):
        raise ValueError("portfolio Engine settlement source reconstruction mismatch")
    return result


def read_cn_a_share_portfolio_engine_development_result_source_v1(
    source: object, *, ledger_schema: LedgerSchema,
) -> CnASharePortfolioEngineDevelopmentResultV1:
    """Rebuild native Fill/Fee/Journal/Book from bytes; never return blocked as zero."""
    data = _fields(source, {"type", "schema_version", "case_hash", "source_ref", "first_batch",
                            "first_settlement", "matured_first_settlement", "second_batch",
                            "second_settlement", "synthetic_development_only", "trade_authorized"}, "result")
    if (data["type"] != "cn_a_share_portfolio_engine_development_result"
            or type(data["schema_version"]) is not int or data["schema_version"] != 1
            or data["synthetic_development_only"] is not True or data["trade_authorized"] is not False):
        raise ValueError("portfolio Engine result source cannot elevate development grade")
    result = CnASharePortfolioEngineDevelopmentResultV1(
        data["case_hash"], _artifact_ref(data["source_ref"]),
        _batch(data["first_batch"], ledger_schema), _settlement(data["first_settlement"]),
        _settlement(data["matured_first_settlement"]),
        _batch(data["second_batch"], ledger_schema), _settlement(data["second_settlement"]),
    )
    if canonical_bytes(data) != canonical_bytes(result):
        raise ValueError("portfolio Engine result source reconstruction mismatch")
    return result
