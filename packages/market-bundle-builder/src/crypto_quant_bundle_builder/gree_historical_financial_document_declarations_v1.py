from __future__ import annotations

import re
from dataclasses import dataclass, fields
from decimal import Decimal
from enum import Enum

from crypto_quant_domain import UtcInstant, canonical_sha256

from .source_snapshots import (
    SourceSnapshot,
    SourceSnapshotFailureCode,
    SourceSnapshotMember,
    SourceSnapshotProvenance,
    verify_source_snapshot,
)

_SCHEMA_VERSION = 1
_SNAPSHOT_ID = "sha256:aee2ea78f3d51185110bc927836ce77ed51f590a9c7b4c26ee7ecd951cbf8d4b"
_CONTENT_TREE_HASH = "sha256:d5375befd81c5fb1ab2832a48bb7c3d0b4fc7dcf9b4ea64700f837dc624ce3d9"
_PROVENANCE_HASH = "sha256:5495fbee8d8668e324be8263f49f9f556ea6a4324b5f530c13a2176f148ad2e5"
_METADATA_MEMBER = "response/cninfo/announcement-query/000651.SZ-2019-2023-annual-reports-v3.json"
_METADATA_HASH = "sha256:3292c3b1bd89f01cb41e09401ad306b6ec8e769cac402317817fe395ff0e918e"
_REVIEWER = "platform.a-share-research-orchestrator.v1"
_REVIEWED_AT = UtcInstant(1787668131165592196)
_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_MONEY = re.compile(r"(?:0|[1-9][0-9]*)\.[0-9]{2}\Z")
_SUCCESS_PERIODS = ("20181231", "20191231", "20201231", "20221231")
_SUPPORTED_PERIODS = ("20181231", "20191231", "20201231", "20211231", "20221231")

_DOCUMENT_FACTS = (
    ("20181231", "response/cninfo/annual-report/1206125365.pdf", "sha256:b147eb6b8a4aaf093f3b83550c70e8526415b5b54fe24e4258ce7bfd11d5406a"),
    ("20191231", "response/cninfo/annual-report/1207685438.pdf", "sha256:1b4869caab122969b322738df69955d788c8dc19b4c6d57188619177e922e708"),
    ("20201231", "response/cninfo/annual-report/1209855305.pdf", "sha256:0d3c39090adf97fede39149a731a5636bd0eca2002606fb942ca70121dba9072"),
    ("20211231", "response/cninfo/annual-report/1213262535.pdf", "sha256:96065ec44285bce7a9c0cbee25dfeb2368ec4552d72f06ebf3ecab35136e2444"),
    ("20221231", "response/cninfo/annual-report/1216702261.pdf", "sha256:7cfc80c2badbf4cd74c5adc080d5072b02cd6c700b04fa7ca0ac44cb8b8fe987"),
)
_PUBLICATION_FACTS = (
    ("20181231", "1206125365", 1556467200000, "20190429", "finalpage/2019-04-29/1206125365.PDF"),
    ("20191231", "1207685438", 1588176000000, "20200430", "finalpage/2020-04-30/1207685438.PDF"),
    ("20201231", "1209855305", 1619625600000, "20210429", "finalpage/2021-04-29/1209855305.PDF"),
    ("20211231", "1213262535", 1651248000000, "20220430", "finalpage/2022-04-30/1213262535.PDF"),
    ("20221231", "1216702261", 1682697600000, "20230429", "finalpage/2023-04-29/1216702261.PDF"),
)
_STATEMENT_FACTS = (
    ("20181231", (85, 86), (85, 86), (89,), (89,), (91,), (91,), ((85, 85, "单位：人民币元"),)),
    ("20191231", (82, 83), (83, 84), (86, 87), (87, 88), (89, 90), (90, 91), ((82, 83, "单位：元"), (5, 6, "单位：人民币元"), (97, 98, "本公司以人民币为记账本位币"))),
    ("20201231", (94, 95), (95, 96), (98,), (99,), (100,), (101,), ((137, 138, "如无特殊说明，金额单位为人民币元"),)),
    ("20221231", (117, 118), (117, 118), (119,), (119,), (120,), (120,), ((151, 152, "如无特殊说明，金额单位为人民币元"),)),
)
_FINANCING_FACTS = (
    ("20181231", 182, 182, "COMPONENT_ARITHMETIC", (("短期借款", "22067750002.70"), ("吸收存款及同业存放", "315879779.13")), "22383629781.83", "PRE_ADOPTION_NOT_RECOGNIZED", "0.00", "0.00", "0.00", "707913.60", "22383629781.83"),
    ("20191231", 189, 190, "PRINTED_TOTAL", (("短期借款", "15944176463.01"), ("吸收存款及同业存放", "352512311.72"), ("拆入资金", "1000446666.67"), ("长期借款", "46885882.86")), "17344021324.26", "PRE_ADOPTION_NOT_RECOGNIZED", "0.00", "0.00", "0.00", "707913.60", "17344021324.26"),
    ("20201231", 195, 196, "PRINTED_TOTAL", (("短期借款", "20304384742.34"), ("吸收存款及同业存放", "261006708.24"), ("拆入资金", "300020250.00"), ("长期借款", "1860713816.09"), ("卖出回购金融资产款项", "475033835.62")), "23201159352.29", "PRE_ADOPTION_NOT_RECOGNIZED", "0.00", "0.00", "0.00", "6986645.96", "23201159352.29"),
    ("20221231", 212, 212, "PRINTED_TOTAL", (("短期借款", "52895851287.92"), ("吸收存款及同业存放", "219111069.61"), ("其他应付款", "1621102937.08"), ("一年内到期的非流动负债", "188387613.61"), ("长期借款", "30784241211.21"), ("长期应付款", "104644415.20")), "85813338534.63", "POST_ADOPTION_FULL_LIABILITY", "213791544.62", "0.00", "0.00", "5620664762.67", "86027130079.25"),
)
_DEPRECIATION_FACTS = (
    ("20181231", (165,), (165,), "2859799547.55", ("fixed_assets", "investment_property"), "249550269.72", "0.00", "979454.55", "3110329271.82"),
    ("20191231", (169,), (170,), "2977103353.04", ("fixed_assets", "investment_property"), "215796437.95", "0.00", "1519448.66", "3194419239.65"),
    ("20201231", (175,), (176,), "3377378887.04", ("fixed_assets", "investment_property"), "211327446.74", "0.00", "0.00", "3588706333.78"),
    ("20221231", (194, 195, 177), (194, 195, 177), "4597938791.84", ("fixed_assets", "investment_property", "right_of_use_assets"), "372007224.51", "0.00", "27739400.53", "4997685416.88"),
)


class GreeHistoricalFinancialDeclarationFailureCode(str, Enum):
    INPUT_MISMATCH = "INPUT_MISMATCH"
    SOURCE_SNAPSHOT_IDENTITY_MISMATCH = "SOURCE_SNAPSHOT_IDENTITY_MISMATCH"
    PERIOD_UNSUPPORTED = "PERIOD_UNSUPPORTED"
    DOCUMENT_IDENTITY_MISMATCH = "DOCUMENT_IDENTITY_MISMATCH"
    REVIEW_TIME_INVALID = "REVIEW_TIME_INVALID"
    DEBT_SCOPE_INCOMPLETE = "DEBT_SCOPE_INCOMPLETE"
    DECLARATION_RECONSTRUCTION_MISMATCH = "DECLARATION_RECONSTRUCTION_MISMATCH"


FailureCode = GreeHistoricalFinancialDeclarationFailureCode | SourceSnapshotFailureCode


def _hash(name: str, value: object) -> str:
    if type(value) is not str or _HASH.fullmatch(value) is None:
        raise ValueError(f"{name} must be canonical sha256")
    return value


def _money(name: str, value: object) -> str:
    if type(value) is not str or _MONEY.fullmatch(value) is None:
        raise ValueError(f"{name} must be canonical scale-2 money text")
    return value


def _document(period: str) -> tuple[str, str]:
    for candidate, member, content_hash in _DOCUMENT_FACTS:
        if candidate == period:
            return member, content_hash
    raise ValueError("period has no document facts")


def _publication_body(period: str) -> dict[str, object]:
    for candidate, announcement_id, milliseconds, publication_date, adjunct_url in _PUBLICATION_FACTS:
        if candidate == period:
            return {
                "source_member_key": _METADATA_MEMBER,
                "source_content_hash": _METADATA_HASH,
                "announcement_id": announcement_id,
                "announcement_time_epoch_milliseconds": milliseconds,
                "publication_date": publication_date,
                "adjunct_url": adjunct_url,
                "precision": "DATE_ONLY",
            }
    raise ValueError("period has no publication facts")


def _statement_unit_body(period: str) -> dict[str, object]:
    member, content_hash = _document(period)
    for candidate, balance_report, balance_pdf, income_report, income_pdf, cash_report, cash_pdf, evidence in _STATEMENT_FACTS:
        if candidate == period:
            return {
                "source_member_key": member,
                "source_document_hash": content_hash,
                "balance_report_pages": list(balance_report),
                "balance_pdf_pages": list(balance_pdf),
                "income_report_pages": list(income_report),
                "income_pdf_pages": list(income_pdf),
                "cashflow_report_pages": list(cash_report),
                "cashflow_pdf_pages": list(cash_pdf),
                "accounting_currency": "CNY",
                "accounting_unit": "yuan",
                "unit_evidence": [
                    {"report_page": report_page, "pdf_page": pdf_page, "text": text}
                    for report_page, pdf_page, text in evidence
                ],
            }
    raise ValueError("period has no statement-unit facts")


def _financing_body(period: str) -> dict[str, object]:
    member, content_hash = _document(period)
    for facts in _FINANCING_FACTS:
        if facts[0] == period:
            (_, report_page, pdf_page, total_kind, components, official_total, lease_scope, lease, short_bonds, long_bonds, dividends, ending_debt) = facts
            return {
                "source_member_key": member,
                "source_document_hash": content_hash,
                "report_page": report_page,
                "pdf_page": pdf_page,
                "official_total_kind": total_kind,
                "official_components": [{"label": label, "amount": amount} for label, amount in components],
                "official_interest_bearing_total": official_total,
                "lease_scope": lease_scope,
                "lease_liabilities_including_current": lease,
                "short_bonds_payable": short_bonds,
                "long_bonds_payable": long_bonds,
                "non_debt_dividends_payable": dividends,
                "ending_interest_bearing_debt": ending_debt,
            }
    raise ValueError("period has no financing facts")


def _depreciation_body(period: str) -> dict[str, object]:
    member, content_hash = _document(period)
    for facts in _DEPRECIATION_FACTS:
        if facts[0] == period:
            (_, report_pages, pdf_pages, combined, includes, intangible, use_right, deferred, ending) = facts
            return {
                "source_member_key": member,
                "source_document_hash": content_hash,
                "report_pages": list(report_pages),
                "pdf_pages": list(pdf_pages),
                "combined_depreciation_field": "depr_fa_coga_dpba",
                "combined_depreciation_amount": combined,
                "combined_depreciation_includes": list(includes),
                "intangible_amortization_field": "amort_intang_assets",
                "intangible_amortization_amount": intangible,
                "separate_use_right_addition": use_right,
                "separate_long_term_deferred_addition": deferred,
                "ending_depreciation_and_amortization": ending,
            }
    raise ValueError("period has no depreciation facts")


def _reconstruct_instant(value: object) -> UtcInstant:
    if type(value) is not UtcInstant:
        raise TypeError("reviewed_at must be exact UtcInstant")
    try:
        nanoseconds = value.epoch_nanoseconds
    except AttributeError as error:
        raise TypeError("reviewed_at must be reconstructable UtcInstant") from error
    if type(nanoseconds) is not int:
        raise TypeError("reviewed_at nanoseconds must be exact int")
    reconstructed = UtcInstant(nanoseconds)
    if reconstructed != value:
        raise ValueError("reviewed_at reconstruction mismatch")
    return reconstructed


@dataclass(frozen=True, slots=True)
class GreeHistoricalDebtScopeConflictV1:
    source_snapshot_id: str
    report_period: str
    source_member_key: str
    source_document_hash: str
    official_table_report_page: int
    official_table_pdf_page: int
    official_interest_bearing_total: str
    short_bonds_payable: str
    short_bonds_already_in_official_total: bool
    lease_liabilities_including_current: str
    omitted_financing_report_page: int
    omitted_financing_pdf_page: int
    omitted_financing_label: str
    omitted_financing_amount: str
    narrow_candidate: str
    broad_candidate: str
    source_bounded: bool
    revision_closure_complete: bool
    decision_grade_eligible: bool
    deployment_authorized: bool
    conflict_hash: str

    def __post_init__(self) -> None:
        expected = {
            "source_snapshot_id": _SNAPSHOT_ID,
            "report_period": "20211231",
            "source_member_key": _DOCUMENT_FACTS[3][1],
            "source_document_hash": _DOCUMENT_FACTS[3][2],
            "official_table_report_page": 222,
            "official_table_pdf_page": 223,
            "official_interest_bearing_total": "43546910016.46",
            "short_bonds_payable": "4048840948.73",
            "short_bonds_already_in_official_total": True,
            "lease_liabilities_including_current": "14785264.79",
            "omitted_financing_report_page": 187,
            "omitted_financing_pdf_page": 188,
            "omitted_financing_label": "企业借款及利息",
            "omitted_financing_amount": "2731680114.20",
            "narrow_candidate": "43561695281.25",
            "broad_candidate": "46293375395.45",
            "source_bounded": True,
            "revision_closure_complete": False,
            "decision_grade_eligible": False,
            "deployment_authorized": False,
        }
        if any(type(getattr(self, name)) is not type(value) or getattr(self, name) != value for name, value in expected.items()):
            raise ValueError("debt scope conflict exact value mismatch")
        for name in ("source_snapshot_id", "source_document_hash"):
            _hash(name, getattr(self, name))
        for name in ("official_interest_bearing_total", "short_bonds_payable", "lease_liabilities_including_current", "omitted_financing_amount", "narrow_candidate", "broad_candidate"):
            _money(name, getattr(self, name))
        if Decimal(self.official_interest_bearing_total) + Decimal(self.lease_liabilities_including_current) != Decimal(self.narrow_candidate):
            raise ValueError("narrow debt candidate mismatch")
        if Decimal(self.narrow_candidate) + Decimal(self.omitted_financing_amount) != Decimal(self.broad_candidate):
            raise ValueError("broad debt candidate mismatch")
        expected_hash = canonical_sha256(self._body())
        if type(self.conflict_hash) is not str:
            raise TypeError("conflict_hash must be exact str")
        if self.conflict_hash == "":
            object.__setattr__(self, "conflict_hash", expected_hash)
        elif _hash("conflict_hash", self.conflict_hash) != expected_hash:
            raise ValueError("conflict hash mismatch")

    def _body(self) -> dict[str, object]:
        return {
            "type": "gree_2021_debt_scope_conflict",
            "schema_version": _SCHEMA_VERSION,
            **{field.name: getattr(self, field.name) for field in fields(self) if field.name != "conflict_hash"},
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "conflict_hash": self.conflict_hash}


@dataclass(frozen=True, slots=True)
class GreeHistoricalFinancialDeclarationFailure:
    code: FailureCode
    report_period: str | None
    debt_scope_conflict: GreeHistoricalDebtScopeConflictV1 | None

    def __post_init__(self) -> None:
        if type(self.code) not in (GreeHistoricalFinancialDeclarationFailureCode, SourceSnapshotFailureCode):
            raise TypeError("code must be exact declaration or SourceSnapshot failure")
        if self.report_period is not None and type(self.report_period) is not str:
            raise TypeError("report_period must be exact str or None")
        if self.code is GreeHistoricalFinancialDeclarationFailureCode.DEBT_SCOPE_INCOMPLETE:
            if type(self.debt_scope_conflict) is not GreeHistoricalDebtScopeConflictV1:
                raise TypeError("debt conflict required")
            conflict = GreeHistoricalDebtScopeConflictV1(**{field.name: getattr(self.debt_scope_conflict, field.name) for field in fields(GreeHistoricalDebtScopeConflictV1)})
            object.__setattr__(self, "debt_scope_conflict", conflict)
            if self.report_period != "20211231":
                raise ValueError("debt conflict period mismatch")
        elif self.debt_scope_conflict is not None:
            raise ValueError("only debt scope failure may contain conflict")

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self._body())

    def _body(self) -> dict[str, object]:
        return {
            "type": "gree_historical_financial_declaration_failure",
            "schema_version": _SCHEMA_VERSION,
            "code": self.code.value,
            "report_period": self.report_period,
            "debt_scope_conflict": None if self.debt_scope_conflict is None else self.debt_scope_conflict.to_canonical_dict(),
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "failure_hash": self.failure_hash}


@dataclass(frozen=True, slots=True)
class GreeHistoricalFinancialPeriodDocumentDeclarationsV1:
    source_snapshot_id: str
    content_tree_hash: str
    provenance_hash: str
    report_period: str
    reviewer_identity: str
    reviewed_at: UtcInstant
    confirmed_disclosure_date: str
    accounting_currency: str
    accounting_unit: str
    official_total_kind: str
    official_interest_bearing_total: str
    lease_scope: str
    lease_liabilities_including_current: str
    short_bonds_payable: str
    long_bonds_payable: str
    non_debt_dividends_payable: str
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
        reviewed_at = _reconstruct_instant(self.reviewed_at)
        object.__setattr__(self, "reviewed_at", reviewed_at)
        if type(self.report_period) is not str or self.report_period not in _SUCCESS_PERIODS:
            raise ValueError("declaration period mismatch")
        publication = _publication_body(self.report_period)
        statement = _statement_unit_body(self.report_period)
        financing = _financing_body(self.report_period)
        depreciation = _depreciation_body(self.report_period)
        expected = {
            "source_snapshot_id": _SNAPSHOT_ID,
            "content_tree_hash": _CONTENT_TREE_HASH,
            "provenance_hash": _PROVENANCE_HASH,
            "reviewer_identity": _REVIEWER,
            "reviewed_at": _REVIEWED_AT,
            "confirmed_disclosure_date": publication["publication_date"],
            "accounting_currency": statement["accounting_currency"],
            "accounting_unit": statement["accounting_unit"],
            "official_total_kind": financing["official_total_kind"],
            "official_interest_bearing_total": financing["official_interest_bearing_total"],
            "lease_scope": financing["lease_scope"],
            "lease_liabilities_including_current": financing["lease_liabilities_including_current"],
            "short_bonds_payable": financing["short_bonds_payable"],
            "long_bonds_payable": financing["long_bonds_payable"],
            "non_debt_dividends_payable": financing["non_debt_dividends_payable"],
            "ending_interest_bearing_debt": financing["ending_interest_bearing_debt"],
            "combined_depreciation_amount": depreciation["combined_depreciation_amount"],
            "intangible_amortization_amount": depreciation["intangible_amortization_amount"],
            "separate_use_right_addition": depreciation["separate_use_right_addition"],
            "separate_long_term_deferred_addition": depreciation["separate_long_term_deferred_addition"],
            "ending_depreciation_and_amortization": depreciation["ending_depreciation_and_amortization"],
            "source_bounded": True,
            "revision_closure_complete": False,
            "decision_grade_eligible": False,
            "deployment_authorized": False,
        }
        if any(type(getattr(self, name)) is not type(value) or getattr(self, name) != value for name, value in expected.items()):
            raise ValueError("declaration exact value mismatch")
        for name in ("source_snapshot_id", "content_tree_hash", "provenance_hash"):
            _hash(name, getattr(self, name))
        money_names = (
            "official_interest_bearing_total", "lease_liabilities_including_current", "short_bonds_payable", "long_bonds_payable", "non_debt_dividends_payable", "ending_interest_bearing_debt", "combined_depreciation_amount", "intangible_amortization_amount", "separate_use_right_addition", "separate_long_term_deferred_addition", "ending_depreciation_and_amortization"
        )
        money = {name: Decimal(_money(name, getattr(self, name))) for name in money_names}
        components = sum((Decimal(component["amount"]) for component in financing["official_components"]), Decimal("0.00"))
        if components != money["official_interest_bearing_total"] or money["official_interest_bearing_total"] + money["lease_liabilities_including_current"] != money["ending_interest_bearing_debt"]:
            raise ValueError("debt reconciliation mismatch")
        if money["combined_depreciation_amount"] + money["intangible_amortization_amount"] + money["separate_use_right_addition"] + money["separate_long_term_deferred_addition"] != money["ending_depreciation_and_amortization"]:
            raise ValueError("D&A reconciliation mismatch")
        expected_hash = canonical_sha256(self._body())
        if type(self.declaration_hash) is not str:
            raise TypeError("declaration_hash must be exact str")
        if self.declaration_hash == "":
            object.__setattr__(self, "declaration_hash", expected_hash)
        elif _hash("declaration_hash", self.declaration_hash) != expected_hash:
            raise ValueError("declaration hash mismatch")

    def _body(self) -> dict[str, object]:
        return {
            "type": "gree_historical_financial_period_document_declarations",
            "schema_version": _SCHEMA_VERSION,
            "source_snapshot_id": self.source_snapshot_id,
            "content_tree_hash": self.content_tree_hash,
            "provenance_hash": self.provenance_hash,
            "issuer_name": "珠海格力电器股份有限公司",
            "provider_security_code": "000651.SZ",
            "instrument_candidate": "xshe:000651",
            "report_period": self.report_period,
            "reviewer_identity": self.reviewer_identity,
            "reviewed_at": self.reviewed_at,
            "publication_evidence": _publication_body(self.report_period),
            "statement_unit": _statement_unit_body(self.report_period),
            "financing_liability": _financing_body(self.report_period),
            "depreciation_and_amortization": _depreciation_body(self.report_period),
            "source_bounded": self.source_bounded,
            "revision_closure_complete": self.revision_closure_complete,
            "decision_grade_eligible": self.decision_grade_eligible,
            "deployment_authorized": self.deployment_authorized,
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "declaration_hash": self.declaration_hash}


@dataclass(frozen=True, slots=True)
class GreeHistoricalFinancialDeclarationOutcome:
    declaration: GreeHistoricalFinancialPeriodDocumentDeclarationsV1 | None
    failure: GreeHistoricalFinancialDeclarationFailure | None

    def __post_init__(self) -> None:
        if (self.declaration is None) == (self.failure is None):
            raise ValueError("outcome must contain exactly one declaration or failure")
        if self.declaration is not None:
            if type(self.declaration) is not GreeHistoricalFinancialPeriodDocumentDeclarationsV1:
                raise TypeError("declaration must be exact declaration value")
            reconstructed = GreeHistoricalFinancialPeriodDocumentDeclarationsV1(**{field.name: getattr(self.declaration, field.name) for field in fields(GreeHistoricalFinancialPeriodDocumentDeclarationsV1)})
            object.__setattr__(self, "declaration", reconstructed)
        if self.failure is not None:
            if type(self.failure) is not GreeHistoricalFinancialDeclarationFailure:
                raise TypeError("failure must be exact declaration failure")
            reconstructed_failure = GreeHistoricalFinancialDeclarationFailure(**{field.name: getattr(self.failure, field.name) for field in fields(GreeHistoricalFinancialDeclarationFailure)})
            object.__setattr__(self, "failure", reconstructed_failure)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "gree_historical_financial_declaration_outcome",
            "schema_version": _SCHEMA_VERSION,
            "declaration": None if self.declaration is None else self.declaration.to_canonical_dict(),
            "failure": None if self.failure is None else self.failure.to_canonical_dict(),
        }


def _failed(code: FailureCode, report_period: str | None, conflict: GreeHistoricalDebtScopeConflictV1 | None = None) -> GreeHistoricalFinancialDeclarationOutcome:
    return GreeHistoricalFinancialDeclarationOutcome(None, GreeHistoricalFinancialDeclarationFailure(code, report_period, conflict))


def _conflict() -> GreeHistoricalDebtScopeConflictV1:
    return GreeHistoricalDebtScopeConflictV1(
        source_snapshot_id=_SNAPSHOT_ID,
        report_period="20211231",
        source_member_key=_DOCUMENT_FACTS[3][1],
        source_document_hash=_DOCUMENT_FACTS[3][2],
        official_table_report_page=222,
        official_table_pdf_page=223,
        official_interest_bearing_total="43546910016.46",
        short_bonds_payable="4048840948.73",
        short_bonds_already_in_official_total=True,
        lease_liabilities_including_current="14785264.79",
        omitted_financing_report_page=187,
        omitted_financing_pdf_page=188,
        omitted_financing_label="企业借款及利息",
        omitted_financing_amount="2731680114.20",
        narrow_candidate="43561695281.25",
        broad_candidate="46293375395.45",
        source_bounded=True,
        revision_closure_complete=False,
        decision_grade_eligible=False,
        deployment_authorized=False,
        conflict_hash="",
    )


def _declaration(period: str, reviewed_at: UtcInstant) -> GreeHistoricalFinancialPeriodDocumentDeclarationsV1:
    publication = _publication_body(period)
    statement = _statement_unit_body(period)
    financing = _financing_body(period)
    depreciation = _depreciation_body(period)
    return GreeHistoricalFinancialPeriodDocumentDeclarationsV1(
        source_snapshot_id=_SNAPSHOT_ID,
        content_tree_hash=_CONTENT_TREE_HASH,
        provenance_hash=_PROVENANCE_HASH,
        report_period=period,
        reviewer_identity=_REVIEWER,
        reviewed_at=reviewed_at,
        confirmed_disclosure_date=publication["publication_date"],
        accounting_currency=statement["accounting_currency"],
        accounting_unit=statement["accounting_unit"],
        official_total_kind=financing["official_total_kind"],
        official_interest_bearing_total=financing["official_interest_bearing_total"],
        lease_scope=financing["lease_scope"],
        lease_liabilities_including_current=financing["lease_liabilities_including_current"],
        short_bonds_payable=financing["short_bonds_payable"],
        long_bonds_payable=financing["long_bonds_payable"],
        non_debt_dividends_payable=financing["non_debt_dividends_payable"],
        ending_interest_bearing_debt=financing["ending_interest_bearing_debt"],
        combined_depreciation_amount=depreciation["combined_depreciation_amount"],
        intangible_amortization_amount=depreciation["intangible_amortization_amount"],
        separate_use_right_addition=depreciation["separate_use_right_addition"],
        separate_long_term_deferred_addition=depreciation["separate_long_term_deferred_addition"],
        ending_depreciation_and_amortization=depreciation["ending_depreciation_and_amortization"],
        source_bounded=True,
        revision_closure_complete=False,
        decision_grade_eligible=False,
        deployment_authorized=False,
        declaration_hash="",
    )


def _reconstruct_snapshot(value: object) -> SourceSnapshot:
    if type(value) is not SourceSnapshot:
        raise TypeError("source_snapshot must be exact SourceSnapshot")
    try:
        members = tuple(
            SourceSnapshotMember(
                **{field.name: getattr(member, field.name) for field in fields(SourceSnapshotMember)}
            )
            for member in value.members
        )
        provenance = SourceSnapshotProvenance(
            **{
                field.name: getattr(value.provenance, field.name)
                for field in fields(SourceSnapshotProvenance)
            }
        )
        reconstructed = SourceSnapshot(
            snapshot_id=value.snapshot_id,
            archive_bytes=value.archive_bytes,
            content_tree_hash=value.content_tree_hash,
            members=members,
            provenance=provenance,
            provenance_hash=value.provenance_hash,
            decision_grade_eligible=value.decision_grade_eligible,
            deployment_authorized=value.deployment_authorized,
        )
    except (AttributeError, TypeError, ValueError) as error:
        raise TypeError("source_snapshot reconstruction mismatch") from error
    if (
        reconstructed.archive_bytes != value.archive_bytes
        or reconstructed.to_canonical_dict() != value.to_canonical_dict()
    ):
        raise ValueError("source_snapshot reconstruction mismatch")
    return reconstructed


def declare_gree_historical_financial_period_v1(
    source_snapshot: SourceSnapshot,
    report_period: str,
    *,
    reviewed_at: UtcInstant,
) -> GreeHistoricalFinancialDeclarationOutcome:
    if type(report_period) is not str:
        return _failed(
            GreeHistoricalFinancialDeclarationFailureCode.INPUT_MISMATCH, None
        )
    period = report_period
    try:
        snapshot = _reconstruct_snapshot(source_snapshot)
        instant = _reconstruct_instant(reviewed_at)
    except (TypeError, ValueError):
        return _failed(GreeHistoricalFinancialDeclarationFailureCode.INPUT_MISMATCH, period)
    verified = verify_source_snapshot(snapshot)
    if verified.failure is not None:
        return _failed(verified.failure.code, period)
    if snapshot.snapshot_id != _SNAPSHOT_ID or snapshot.content_tree_hash != _CONTENT_TREE_HASH or snapshot.provenance_hash != _PROVENANCE_HASH:
        return _failed(GreeHistoricalFinancialDeclarationFailureCode.SOURCE_SNAPSHOT_IDENTITY_MISMATCH, period)
    if report_period not in _SUPPORTED_PERIODS:
        return _failed(GreeHistoricalFinancialDeclarationFailureCode.PERIOD_UNSUPPORTED, report_period)
    members = {member.member_key: member for member in snapshot.members}
    report_member, report_hash = _document(report_period)
    if _METADATA_MEMBER not in members or members[_METADATA_MEMBER].content_hash != _METADATA_HASH or report_member not in members or members[report_member].content_hash != report_hash:
        return _failed(GreeHistoricalFinancialDeclarationFailureCode.DOCUMENT_IDENTITY_MISMATCH, report_period)
    if instant != _REVIEWED_AT or instant.epoch_nanoseconds < max(member.acquired_at_epoch_nanoseconds for member in snapshot.members):
        return _failed(GreeHistoricalFinancialDeclarationFailureCode.REVIEW_TIME_INVALID, report_period)
    try:
        if report_period == "20211231":
            return _failed(GreeHistoricalFinancialDeclarationFailureCode.DEBT_SCOPE_INCOMPLETE, report_period, _conflict())
        declaration = _declaration(report_period, instant)
        return GreeHistoricalFinancialDeclarationOutcome(declaration, None)
    except (AttributeError, TypeError, ValueError):
        return _failed(GreeHistoricalFinancialDeclarationFailureCode.DECLARATION_RECONSTRUCTION_MISMATCH, report_period)
