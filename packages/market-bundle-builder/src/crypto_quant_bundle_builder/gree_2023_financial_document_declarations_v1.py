from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from crypto_quant_domain import UtcInstant, canonical_sha256

from .source_snapshots import (
    SourceSnapshot,
    SourceSnapshotFailureCode,
    verify_source_snapshot,
)

_SCHEMA_VERSION = 1
_SNAPSHOT_ID = "sha256:dec0abb1828f8b87256347e72b6ccfe2f84a2ca13f36aa1415c9a53e96a0c7d5"
_CONTENT_TREE_HASH = "sha256:d7e92674dd42a4eeabfde354922cfafa9d50837f2076c1ad88233da8c0456b13"
_PROVENANCE_HASH = "sha256:0fcef32df8c6b41ef0ce55121adc9c392cf483ca71134dc27175f6c9512cab17"
_REPORT_MEMBER = "response/cninfo/annual-report/1219928418.pdf"
_REPORT_HASH = "sha256:32ebc475a2291ce4f1b5c1a9f9da55227e03192f07e75041e976c29d213ec8aa"
_CONFIRMATION_MEMBER = "response/cninfo/publication-confirmation/1220300051.pdf"
_CONFIRMATION_HASH = "sha256:a78a67865a7ea989c4fd8b053fad1aa75f36d22c10d14387800ff16b698dbc60"
_REVIEWER = "platform.a-share-research-orchestrator.v1"
_REVIEWED_AT = UtcInstant(1787649182123754003)
_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_MONEY = re.compile(r"(?:0|[1-9][0-9]*)\.[0-9]{2}\Z")

_PUBLICATION_EXCERPT = (
    "珠海格力电器股份有限公司（以下简称“公司”）已于 2024 年 4 月 30 日在"
    "巨潮资讯网（http://www.cninfo.com.cn）披露了《2023 年年度报告》。"
)


class Gree2023FinancialDeclarationFailureCode(str, Enum):
    INPUT_MISMATCH = "INPUT_MISMATCH"
    SOURCE_SNAPSHOT_IDENTITY_MISMATCH = "SOURCE_SNAPSHOT_IDENTITY_MISMATCH"
    DOCUMENT_IDENTITY_MISMATCH = "DOCUMENT_IDENTITY_MISMATCH"
    REVIEW_TIME_INVALID = "REVIEW_TIME_INVALID"
    DECLARATION_CONTEXT_MISMATCH = "DECLARATION_CONTEXT_MISMATCH"
    DEBT_RECONCILIATION_MISMATCH = "DEBT_RECONCILIATION_MISMATCH"
    DA_RECONCILIATION_MISMATCH = "DA_RECONCILIATION_MISMATCH"
    DECLARATION_RECONSTRUCTION_MISMATCH = "DECLARATION_RECONSTRUCTION_MISMATCH"


FailureCode = Gree2023FinancialDeclarationFailureCode | SourceSnapshotFailureCode


def _hash(name: str, value: object) -> str:
    if type(value) is not str or _HASH.fullmatch(value) is None:
        raise ValueError(f"{name} must be canonical sha256")
    return value


def _money(name: str, value: object) -> str:
    if type(value) is not str or _MONEY.fullmatch(value) is None:
        raise ValueError(f"{name} must be canonical scale-2 money text")
    return value


def _exact_false(*values: object) -> None:
    if any(type(value) is not bool or value for value in values):
        raise TypeError("qualification flags must be exact false")


@dataclass(frozen=True, slots=True)
class Gree2023FinancialDeclarationFailure:
    code: FailureCode

    def __post_init__(self) -> None:
        if type(self.code) not in (
            Gree2023FinancialDeclarationFailureCode,
            SourceSnapshotFailureCode,
        ):
            raise TypeError("code must be exact declaration or SourceSnapshot failure")

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self._body())

    def _body(self) -> dict[str, object]:
        return {
            "type": "gree_2023_financial_declaration_failure",
            "schema_version": _SCHEMA_VERSION,
            "code": self.code.value,
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "failure_hash": self.failure_hash}


@dataclass(frozen=True, slots=True)
class Gree2023FinancialDocumentDeclarationsV1:
    source_snapshot_id: str
    content_tree_hash: str
    provenance_hash: str
    reviewer_identity: str
    reviewed_at: UtcInstant
    confirmed_disclosure_date: str
    accounting_currency: str
    accounting_unit: str
    bank_borrowings_and_other: str
    bonds_payable: str
    lease_liabilities_including_current: str
    non_debt_dividends_payable: str
    official_table_total: str
    ending_interest_bearing_debt: str
    combined_depreciation_amount: str
    intangible_amortization_amount: str
    separate_use_right_addition: str
    separate_long_term_deferred_addition: str
    ending_depreciation_and_amortization: str
    source_bounded: bool
    revision_closure_complete: bool
    decision_grade_eligible: bool
    deployment_authorized: bool
    declaration_hash: str

    def __post_init__(self) -> None:
        if (
            self.source_snapshot_id != _SNAPSHOT_ID
            or self.content_tree_hash != _CONTENT_TREE_HASH
            or self.provenance_hash != _PROVENANCE_HASH
            or type(self.reviewer_identity) is not str
            or self.reviewer_identity != _REVIEWER
            or type(self.reviewed_at) is not UtcInstant
            or type(self.confirmed_disclosure_date) is not str
            or self.confirmed_disclosure_date != "20240430"
            or type(self.accounting_currency) is not str
            or self.accounting_currency != "CNY"
            or type(self.accounting_unit) is not str
            or self.accounting_unit != "yuan"
        ):
            raise ValueError("declaration context mismatch")
        if self.reviewed_at != _REVIEWED_AT:
            raise ValueError("review time invalid")
        for name in ("source_snapshot_id", "content_tree_hash", "provenance_hash"):
            _hash(name, getattr(self, name))
        money_fields = (
            "bank_borrowings_and_other",
            "bonds_payable",
            "lease_liabilities_including_current",
            "non_debt_dividends_payable",
            "official_table_total",
            "ending_interest_bearing_debt",
            "combined_depreciation_amount",
            "intangible_amortization_amount",
            "separate_use_right_addition",
            "separate_long_term_deferred_addition",
            "ending_depreciation_and_amortization",
        )
        values = {name: Decimal(_money(name, getattr(self, name))) for name in money_fields}
        expected_money = {
            "bank_borrowings_and_other": "87676167515.47",
            "bonds_payable": "0.00",
            "lease_liabilities_including_current": "856833971.52",
            "non_debt_dividends_payable": "5572388.92",
            "official_table_total": "88538573875.91",
            "ending_interest_bearing_debt": "88533001486.99",
            "combined_depreciation_amount": "4808144624.82",
            "intangible_amortization_amount": "475186591.56",
            "separate_use_right_addition": "0.00",
            "separate_long_term_deferred_addition": "0.00",
            "ending_depreciation_and_amortization": "5283331216.38",
        }
        if (
            values["bank_borrowings_and_other"]
            + values["bonds_payable"]
            + values["lease_liabilities_including_current"]
            + values["non_debt_dividends_payable"]
            != values["official_table_total"]
            or values["bank_borrowings_and_other"]
            + values["bonds_payable"]
            + values["lease_liabilities_including_current"]
            != values["ending_interest_bearing_debt"]
        ):
            raise ValueError("debt reconciliation mismatch")
        if (
            values["combined_depreciation_amount"]
            + values["intangible_amortization_amount"]
            + values["separate_use_right_addition"]
            + values["separate_long_term_deferred_addition"]
            != values["ending_depreciation_and_amortization"]
        ):
            raise ValueError("D&A reconciliation mismatch")
        if any(getattr(self, name) != expected for name, expected in expected_money.items()):
            raise ValueError("declaration exact value mismatch")
        if type(self.source_bounded) is not bool or not self.source_bounded:
            raise TypeError("source_bounded must be exact true")
        _exact_false(
            self.revision_closure_complete,
            self.decision_grade_eligible,
            self.deployment_authorized,
        )
        expected_hash = canonical_sha256(self._body())
        if type(self.declaration_hash) is not str:
            raise TypeError("declaration_hash must be exact str")
        if self.declaration_hash == "":
            object.__setattr__(self, "declaration_hash", expected_hash)
        else:
            _hash("declaration_hash", self.declaration_hash)
            if self.declaration_hash != expected_hash:
                raise ValueError("declaration hash mismatch")

    def _body(self) -> dict[str, object]:
        return {
            "type": "gree_2023_financial_document_declarations",
            "schema_version": _SCHEMA_VERSION,
            "source_snapshot_id": self.source_snapshot_id,
            "content_tree_hash": self.content_tree_hash,
            "provenance_hash": self.provenance_hash,
            "issuer_name": "珠海格力电器股份有限公司",
            "provider_security_code": "000651.SZ",
            "instrument_candidate": "xshe:000651",
            "report_period": "20231231",
            "reviewer_identity": self.reviewer_identity,
            "reviewed_at": self.reviewed_at,
            "publication_confirmation": {
                "source_member_key": _CONFIRMATION_MEMBER,
                "source_document_hash": _CONFIRMATION_HASH,
                "page": 1,
                "report_title": "2023 年年度报告",
                "confirmed_disclosure_date": self.confirmed_disclosure_date,
                "reviewed_excerpt": _PUBLICATION_EXCERPT,
            },
            "statement_unit": {
                "source_member_key": _REPORT_MEMBER,
                "source_document_hash": _REPORT_HASH,
                "balance_pages": [113, 114],
                "income_pages": [115],
                "cashflow_pages": [116],
                "accounting_currency": self.accounting_currency,
                "accounting_unit": self.accounting_unit,
                "unit_text": "单位：人民币元",
            },
            "financing_liability": {
                "source_member_key": _REPORT_MEMBER,
                "source_document_hash": _REPORT_HASH,
                "report_page": 210,
                "bank_borrowings_and_other": self.bank_borrowings_and_other,
                "bonds_payable": self.bonds_payable,
                "lease_liabilities_including_current": self.lease_liabilities_including_current,
                "non_debt_dividends_payable": self.non_debt_dividends_payable,
                "official_table_total": self.official_table_total,
                "ending_interest_bearing_debt": self.ending_interest_bearing_debt,
            },
            "depreciation_and_amortization": {
                "source_member_key": _REPORT_MEMBER,
                "source_document_hash": _REPORT_HASH,
                "report_page": 210,
                "combined_depreciation_field": "depr_fa_coga_dpba",
                "combined_depreciation_amount": self.combined_depreciation_amount,
                "combined_depreciation_includes": [
                    "fixed_assets",
                    "investment_property",
                    "right_of_use_assets",
                ],
                "intangible_amortization_field": "amort_intang_assets",
                "intangible_amortization_amount": self.intangible_amortization_amount,
                "separate_use_right_addition": self.separate_use_right_addition,
                "separate_long_term_deferred_addition": self.separate_long_term_deferred_addition,
                "ending_depreciation_and_amortization": self.ending_depreciation_and_amortization,
            },
            "source_bounded": self.source_bounded,
            "revision_closure_complete": self.revision_closure_complete,
            "decision_grade_eligible": self.decision_grade_eligible,
            "deployment_authorized": self.deployment_authorized,
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "declaration_hash": self.declaration_hash}


@dataclass(frozen=True, slots=True)
class Gree2023FinancialDeclarationOutcome:
    declaration: Gree2023FinancialDocumentDeclarationsV1 | None
    failure: Gree2023FinancialDeclarationFailure | None

    def __post_init__(self) -> None:
        if (self.declaration is None) == (self.failure is None):
            raise ValueError("outcome must contain exactly one declaration or failure")
        if self.declaration is not None and type(self.declaration) is not Gree2023FinancialDocumentDeclarationsV1:
            raise TypeError("declaration must be exact declaration value")
        if self.failure is not None and type(self.failure) is not Gree2023FinancialDeclarationFailure:
            raise TypeError("failure must be exact declaration failure")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "gree_2023_financial_declaration_outcome",
            "schema_version": _SCHEMA_VERSION,
            "declaration": self.declaration.to_canonical_dict() if self.declaration else None,
            "failure": self.failure.to_canonical_dict() if self.failure else None,
        }


def _failed(code: FailureCode) -> Gree2023FinancialDeclarationOutcome:
    return Gree2023FinancialDeclarationOutcome(
        None, Gree2023FinancialDeclarationFailure(code)
    )


def _value_failure_code(message: str) -> Gree2023FinancialDeclarationFailureCode:
    if "context" in message or "exact value" in message:
        return Gree2023FinancialDeclarationFailureCode.DECLARATION_CONTEXT_MISMATCH
    if "debt reconciliation" in message:
        return Gree2023FinancialDeclarationFailureCode.DEBT_RECONCILIATION_MISMATCH
    if "D&A reconciliation" in message:
        return Gree2023FinancialDeclarationFailureCode.DA_RECONCILIATION_MISMATCH
    if "review time" in message:
        return Gree2023FinancialDeclarationFailureCode.REVIEW_TIME_INVALID
    return Gree2023FinancialDeclarationFailureCode.DECLARATION_RECONSTRUCTION_MISMATCH


def _type_failure_code(message: str) -> Gree2023FinancialDeclarationFailureCode:
    if "qualification" in message or "source_bounded" in message:
        return Gree2023FinancialDeclarationFailureCode.DECLARATION_CONTEXT_MISMATCH
    return Gree2023FinancialDeclarationFailureCode.DECLARATION_RECONSTRUCTION_MISMATCH


def _declaration(reviewed_at: UtcInstant) -> Gree2023FinancialDocumentDeclarationsV1:
    values = {
        "source_snapshot_id": _SNAPSHOT_ID,
        "content_tree_hash": _CONTENT_TREE_HASH,
        "provenance_hash": _PROVENANCE_HASH,
        "reviewer_identity": _REVIEWER,
        "reviewed_at": reviewed_at,
        "confirmed_disclosure_date": "20240430",
        "accounting_currency": "CNY",
        "accounting_unit": "yuan",
        "bank_borrowings_and_other": "87676167515.47",
        "bonds_payable": "0.00",
        "lease_liabilities_including_current": "856833971.52",
        "non_debt_dividends_payable": "5572388.92",
        "official_table_total": "88538573875.91",
        "ending_interest_bearing_debt": "88533001486.99",
        "combined_depreciation_amount": "4808144624.82",
        "intangible_amortization_amount": "475186591.56",
        "separate_use_right_addition": "0.00",
        "separate_long_term_deferred_addition": "0.00",
        "ending_depreciation_and_amortization": "5283331216.38",
        "source_bounded": True,
        "revision_closure_complete": False,
        "decision_grade_eligible": False,
        "deployment_authorized": False,
    }
    return Gree2023FinancialDocumentDeclarationsV1(
        **values, declaration_hash=""
    )


def declare_gree_2023_financial_documents_v1(
    source_snapshot: SourceSnapshot,
    *,
    reviewed_at: UtcInstant,
) -> Gree2023FinancialDeclarationOutcome:
    if type(source_snapshot) is not SourceSnapshot or type(reviewed_at) is not UtcInstant:
        return _failed(Gree2023FinancialDeclarationFailureCode.INPUT_MISMATCH)
    verified = verify_source_snapshot(source_snapshot)
    if verified.failure is not None:
        return _failed(verified.failure.code)
    if (
        source_snapshot.snapshot_id != _SNAPSHOT_ID
        or source_snapshot.content_tree_hash != _CONTENT_TREE_HASH
        or source_snapshot.provenance_hash != _PROVENANCE_HASH
    ):
        return _failed(
            Gree2023FinancialDeclarationFailureCode.SOURCE_SNAPSHOT_IDENTITY_MISMATCH
        )
    members = {member.member_key: member for member in source_snapshot.members}
    if (
        _REPORT_MEMBER not in members
        or _CONFIRMATION_MEMBER not in members
        or members[_REPORT_MEMBER].content_hash != _REPORT_HASH
        or members[_CONFIRMATION_MEMBER].content_hash != _CONFIRMATION_HASH
    ):
        return _failed(Gree2023FinancialDeclarationFailureCode.DOCUMENT_IDENTITY_MISMATCH)
    if (
        reviewed_at != _REVIEWED_AT
        or reviewed_at.epoch_nanoseconds
        < max(member.acquired_at_epoch_nanoseconds for member in source_snapshot.members)
    ):
        return _failed(Gree2023FinancialDeclarationFailureCode.REVIEW_TIME_INVALID)
    try:
        value = _declaration(reviewed_at)
    except ValueError as error:
        return _failed(_value_failure_code(str(error)))
    except TypeError as error:
        return _failed(_type_failure_code(str(error)))
    return Gree2023FinancialDeclarationOutcome(value, None)
