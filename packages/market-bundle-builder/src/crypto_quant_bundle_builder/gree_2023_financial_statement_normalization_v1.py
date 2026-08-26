from __future__ import annotations

import json
import re
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import cast

from crypto_quant_domain import UtcInstant, canonical_sha256

from .gree_2023_financial_document_declarations_v1 import (
    Gree2023FinancialDocumentDeclarationsV1,
)
from .source_snapshots import (
    SourceSnapshot,
    SourceSnapshotFailureCode,
    verify_source_snapshot,
)

_SCHEMA_VERSION = 1
_SNAPSHOT_ID = "sha256:dec0abb1828f8b87256347e72b6ccfe2f84a2ca13f36aa1415c9a53e96a0c7d5"
_CONTENT_TREE_HASH = "sha256:d7e92674dd42a4eeabfde354922cfafa9d50837f2076c1ad88233da8c0456b13"
_PROVENANCE_HASH = "sha256:0fcef32df8c6b41ef0ce55121adc9c392cf483ca71134dc27175f6c9512cab17"
_DECLARATION_HASH = "sha256:59e09eb542a6e2ec480a7b8ed322d9ae9106416460f0999216fd5564f7278007"
_REPORT_HASH = "sha256:32ebc475a2291ce4f1b5c1a9f9da55227e03192f07e75041e976c29d213ec8aa"
_CONFIRMATION_HASH = "sha256:a78a67865a7ea989c4fd8b053fad1aa75f36d22c10d14387800ff16b698dbc60"
_EXPECTED_AVAILABLE_AT_NS = 1_714_959_000_000_000_000
_AVAILABLE_AT = UtcInstant(_EXPECTED_AVAILABLE_AT_NS)
_INSTRUMENT = "xshe:000651"
_PERIOD = "20231231"
_ANNOUNCEMENT_DATE = "20240430"
_PRESENTATION_BASIS = "CURRENT_CONSOLIDATED"
_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_DECIMAL = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?\Z")

_INCOME_MEMBER = "response/tushare/income/000651.SZ-20231231-20240430-v2.json"
_BALANCE_MEMBER = "response/tushare/balancesheet/000651.SZ-20231231-20240430-v2.json"
_CASHFLOW_MEMBER = "response/tushare/cashflow/000651.SZ-20231231-20240430-v2.json"

_INCOME_FIELDS = (
    "ts_code",
    "ann_date",
    "f_ann_date",
    "end_date",
    "report_type",
    "comp_type",
    "revenue",
    "operate_profit",
    "total_profit",
    "income_tax",
    "n_income",
    "n_income_attr_p",
    "minority_gain",
    "fin_exp_int_exp",
    "ebit",
    "ebitda",
    "update_flag",
)
_BALANCE_FIELDS = (
    "ts_code",
    "ann_date",
    "f_ann_date",
    "end_date",
    "report_type",
    "comp_type",
    "money_cap",
    "total_assets",
    "total_liab",
    "total_hldr_eqy_inc_min_int",
    "total_hldr_eqy_exc_min_int",
    "minority_int",
    "total_liab_hldr_eqy",
    "st_borr",
    "non_cur_liab_due_1y",
    "lt_borr",
    "bond_payable",
    "st_bonds_payable",
    "lease_liab",
    "update_flag",
)
_CASHFLOW_FIELDS = (
    "ts_code",
    "ann_date",
    "f_ann_date",
    "end_date",
    "report_type",
    "comp_type",
    "n_cashflow_act",
    "c_pay_acq_const_fiolta",
    "depr_fa_coga_dpba",
    "use_right_asset_dep",
    "amort_intang_assets",
    "lt_amort_deferred_exp",
    "c_cash_equ_end_period",
    "free_cashflow",
    "update_flag",
)

# These hashes bind canonical rows after JSON numeric tokens have been converted
# directly to strings. They intentionally differ from hashes produced via float.
_REAL_ROW_HASHES = {
    "INCOME": (
        "sha256:7650431917f2c6d302075cb08265e2c0993681bff2e964f793d179476792e4a0",
    ),
    "BALANCE": (
        "sha256:42558caf71776422ea55d8c54f5cbe20c5a5869c6a72e44b37d7d8662adb37e3",
        "sha256:f891a94138f37fb1dad697354f9278a45e779a2b8c700ffafa0ea34090a00688",
    ),
    "CASH_FLOW": (
        "sha256:7765c5315c9e65a9799af793050520dc2a7f21dd4dc9e410820b0b326ccbeba7",
    ),
}
_MEMBER_HASHES = {
    "INCOME": "sha256:fcde549fe51112d8721810476483c88cb2b509fbcf0e8483ddd87c435edf1d35",
    "BALANCE": "sha256:59e6d57ea45aa0649c402327e67b7098618f71c636ff0f5be670030552e4960d",
    "CASH_FLOW": "sha256:94b9483fd4dd37c9f83c0d5d0174473497ac5641f915490e452bacdb379a5e60",
}
_EXPECTED_LINE_ITEMS: dict[str, tuple[LineItem, ...]] = {
    "INCOME": (
        ("revenue", "203979266387.09"),
        ("operate_profit", "32864780357.76"),
        ("total_profit", "32815703838.19"),
        ("income_tax", "5096680924.6"),
        ("n_income", "27719022913.59"),
        ("n_income_attr_p", "29017387604.18"),
        ("minority_gain", "-1298364690.59"),
        ("fin_exp_int_exp", "2962205439.75"),
        ("ebit", "28716608257.66"),
        ("ebitda", "33999939474.04"),
    ),
    "BALANCE": (
        ("money_cap", "124104987289.62"),
        ("total_assets", "368053902576.37"),
        ("total_liab", "247407749159.93"),
        ("total_hldr_eqy_inc_min_int", "120646153416.44"),
        ("total_hldr_eqy_exc_min_int", "116793716103.39"),
        ("minority_int", "3852437313.05"),
        ("total_liab_hldr_eqy", "368053902576.37"),
        ("st_borr", "26443476388.52"),
        ("non_cur_liab_due_1y", "20605521073.03"),
        ("lt_borr", "39035742535.09"),
        ("bond_payable", "0.00"),
        ("st_bonds_payable", "0.00"),
        ("lease_liab", "767007951.92"),
    ),
    "CASH_FLOW": (
        ("n_cashflow_act", "56398426354.17"),
        ("c_pay_acq_const_fiolta", "5425734302.92"),
        ("depr_fa_coga_dpba", "4808144624.82"),
        ("use_right_asset_dep", None),
        ("amort_intang_assets", "475186591.56"),
        ("lt_amort_deferred_exp", None),
        ("c_cash_equ_end_period", "30914196186.41"),
        ("free_cashflow", "14242168298.2958"),
    ),
}
_EXPECTED_UPDATE_FLAGS = {
    "INCOME": ("1",),
    "BALANCE": ("0", "1"),
    "CASH_FLOW": ("1",),
}
_EXPECTED_NULL_FIELDS = {
    "INCOME": (),
    "BALANCE": ("bond_payable", "st_bonds_payable"),
    "CASH_FLOW": ("use_right_asset_dep", "lt_amort_deferred_exp"),
}


class Gree2023FinancialStatementKind(str, Enum):
    INCOME = "INCOME"
    BALANCE = "BALANCE"
    CASH_FLOW = "CASH_FLOW"


class Gree2023FinancialNormalizationFailureCode(str, Enum):
    INPUT_MISMATCH = "INPUT_MISMATCH"
    SOURCE_IDENTITY_MISMATCH = "SOURCE_IDENTITY_MISMATCH"
    DECLARATION_MISMATCH = "DECLARATION_MISMATCH"
    SOURCE_RESPONSE_INVALID = "SOURCE_RESPONSE_INVALID"
    SOURCE_ROW_SET_MISMATCH = "SOURCE_ROW_SET_MISMATCH"
    STATEMENT_CONTEXT_MISMATCH = "STATEMENT_CONTEXT_MISMATCH"
    BALANCE_PRESENTATION_CONFLICT = "BALANCE_PRESENTATION_CONFLICT"
    REQUIRED_LINE_ITEM_MISSING = "REQUIRED_LINE_ITEM_MISSING"
    DECLARATION_SUBSTITUTION_MISMATCH = "DECLARATION_SUBSTITUTION_MISMATCH"
    AVAILABILITY_MISMATCH = "AVAILABILITY_MISMATCH"
    RESULT_RECONSTRUCTION_MISMATCH = "RESULT_RECONSTRUCTION_MISMATCH"


FailureCode = Gree2023FinancialNormalizationFailureCode | SourceSnapshotFailureCode
LineItem = tuple[str, str | None]


@dataclass(frozen=True, slots=True)
class Gree2023FinancialNormalizationFailure:
    code: FailureCode

    def __post_init__(self) -> None:
        if type(self.code) not in (
            Gree2023FinancialNormalizationFailureCode,
            SourceSnapshotFailureCode,
        ):
            raise TypeError("code must be exact normalization or SourceSnapshot failure")

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self._body())

    def _body(self) -> dict[str, object]:
        return {
            "type": "gree_2023_financial_normalization_failure",
            "schema_version": _SCHEMA_VERSION,
            "code": self.code.value,
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "failure_hash": self.failure_hash}


def _line_item_dict(values: tuple[LineItem, ...]) -> dict[str, str | None]:
    return dict(values)


def _hash(name: str, value: object) -> str:
    if type(value) is not str or _HASH.fullmatch(value) is None:
        raise ValueError(f"{name} must be canonical sha256")
    return value


def _exact_false(*values: object) -> None:
    if any(type(value) is not bool or value for value in values):
        raise TypeError("qualification flags must be exact false")


def _statement_spec(
    kind: Gree2023FinancialStatementKind,
) -> tuple[str, tuple[str, ...], tuple[str, ...], str]:
    if kind is Gree2023FinancialStatementKind.INCOME:
        return _INCOME_MEMBER, _INCOME_FIELDS, _REAL_ROW_HASHES["INCOME"], _MEMBER_HASHES["INCOME"]
    if kind is Gree2023FinancialStatementKind.BALANCE:
        return _BALANCE_MEMBER, _BALANCE_FIELDS, _REAL_ROW_HASHES["BALANCE"], _MEMBER_HASHES["BALANCE"]
    return _CASHFLOW_MEMBER, _CASHFLOW_FIELDS, _REAL_ROW_HASHES["CASH_FLOW"], _MEMBER_HASHES["CASH_FLOW"]


def _economic_key(kind: Gree2023FinancialStatementKind) -> str:
    return canonical_sha256(
        {
            "instrument_id": _INSTRUMENT,
            "statement_kind": kind.value,
            "report_period_end": _PERIOD,
            "period_kind": "ANNUAL",
            "consolidation_scope": "CONSOLIDATED",
            "accounting_currency": "CNY",
            "accounting_unit": "yuan",
        }
    )


def _lineage_key(kind: Gree2023FinancialStatementKind) -> str:
    return canonical_sha256(
        {
            "instrument_id": _INSTRUMENT,
            "statement_kind": kind.value,
            "report_period_end": _PERIOD,
            "period_kind": "ANNUAL",
            "consolidation_scope": "CONSOLIDATED",
            "accounting_currency": "CNY",
            "accounting_unit": "yuan",
            "presentation_basis": _PRESENTATION_BASIS,
        }
    )


@dataclass(frozen=True, slots=True)
class Gree2023FinancialStatementObservationRevisionV1:
    schema_version: int
    statement_kind: Gree2023FinancialStatementKind
    economic_statement_key: str
    observation_lineage_key: str
    instrument_id: str
    report_period_end: str
    period_kind: str
    consolidation_scope: str
    accounting_currency: str
    accounting_unit: str
    presentation_basis: str
    announcement_date: str
    actual_announcement_date: str
    available_at_utc: UtcInstant
    source_snapshot_id: str
    source_content_tree_hash: str
    source_provenance_hash: str
    source_member_key: str
    source_member_content_hash: str
    source_row_hashes: tuple[str, ...]
    provider_update_flags: tuple[str, ...]
    official_document_hash: str
    publication_confirmation_hash: str
    declaration_hash: str
    raw_null_fields: tuple[str, ...]
    line_items: tuple[LineItem, ...]
    line_items_hash: str
    provider_revision_id: None
    supersedes_revision_id: None
    source_bounded: bool
    revision_closure_complete: bool
    decision_grade_eligible: bool
    deployment_authorized: bool
    revision_id: str

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != _SCHEMA_VERSION:
            raise ValueError("schema_version mismatch")
        if type(self.statement_kind) is not Gree2023FinancialStatementKind:
            raise TypeError("statement_kind must be exact statement kind")
        member, fields, row_hashes, member_hash = _statement_spec(self.statement_kind)
        literals = (
            (self.instrument_id, _INSTRUMENT),
            (self.report_period_end, _PERIOD),
            (self.period_kind, "ANNUAL"),
            (self.consolidation_scope, "CONSOLIDATED"),
            (self.accounting_currency, "CNY"),
            (self.accounting_unit, "yuan"),
            (self.presentation_basis, _PRESENTATION_BASIS),
            (self.announcement_date, _ANNOUNCEMENT_DATE),
            (self.actual_announcement_date, _ANNOUNCEMENT_DATE),
            (self.source_snapshot_id, _SNAPSHOT_ID),
            (self.source_content_tree_hash, _CONTENT_TREE_HASH),
            (self.source_provenance_hash, _PROVENANCE_HASH),
            (self.source_member_key, member),
            (self.source_member_content_hash, member_hash),
            (self.official_document_hash, _REPORT_HASH),
            (self.publication_confirmation_hash, _CONFIRMATION_HASH),
            (self.declaration_hash, _DECLARATION_HASH),
        )
        if any(type(value) is not str or value != expected for value, expected in literals):
            raise ValueError("revision context mismatch")
        for name in (
            "economic_statement_key",
            "observation_lineage_key",
            "source_snapshot_id",
            "source_content_tree_hash",
            "source_provenance_hash",
            "source_member_content_hash",
            "official_document_hash",
            "publication_confirmation_hash",
            "declaration_hash",
            "line_items_hash",
        ):
            _hash(name, getattr(self, name))
        if self.economic_statement_key != _economic_key(self.statement_kind):
            raise ValueError("economic statement key mismatch")
        if self.observation_lineage_key != _lineage_key(self.statement_kind):
            raise ValueError("observation lineage key mismatch")
        if type(self.available_at_utc) is not UtcInstant or self.available_at_utc != UtcInstant(
            _EXPECTED_AVAILABLE_AT_NS
        ):
            raise ValueError("available_at_utc mismatch")
        if (
            type(self.source_row_hashes) is not tuple
            or self.source_row_hashes != row_hashes
            or any(_HASH.fullmatch(value) is None for value in self.source_row_hashes)
            or type(self.provider_update_flags) is not tuple
            or self.provider_update_flags != _EXPECTED_UPDATE_FLAGS[self.statement_kind.value]
            or any(type(value) is not str for value in self.provider_update_flags)
        ):
            raise ValueError("source row evidence mismatch")
        item_fields = fields[6:-1]
        if (
            type(self.raw_null_fields) is not tuple
            or any(type(value) is not str for value in self.raw_null_fields)
            or type(self.line_items) is not tuple
            or any(
                type(item) is not tuple
                or len(item) != 2
                or type(item[0]) is not str
                or (item[1] is not None and (type(item[1]) is not str or _DECIMAL.fullmatch(item[1]) is None))
                for item in self.line_items
            )
            or tuple(name for name, _ in self.line_items) != item_fields
        ):
            raise ValueError("line item shape mismatch")
        line_items = _line_item_dict(self.line_items)
        resolved_nulls = tuple(name for name in item_fields if line_items[name] is None)
        if self.raw_null_fields != _EXPECTED_NULL_FIELDS[self.statement_kind.value]:
            raise ValueError("raw null evidence mismatch")
        if self.line_items != _EXPECTED_LINE_ITEMS[self.statement_kind.value]:
            raise ValueError("line item exact value mismatch")
        if self.statement_kind is Gree2023FinancialStatementKind.BALANCE:
            if (
                self.raw_null_fields != ("bond_payable", "st_bonds_payable")
                or resolved_nulls
                or line_items["bond_payable"] != "0.00"
                or line_items["st_bonds_payable"] != "0.00"
            ):
                raise ValueError("balance declaration substitution mismatch")
        elif resolved_nulls != self.raw_null_fields:
            raise ValueError("raw null evidence mismatch")
        if self.statement_kind is Gree2023FinancialStatementKind.CASH_FLOW:
            if self.raw_null_fields != ("use_right_asset_dep", "lt_amort_deferred_exp"):
                raise ValueError("cash-flow raw null evidence mismatch")
        if self.line_items_hash != canonical_sha256(line_items):
            raise ValueError("line_items_hash mismatch")
        if self.provider_revision_id is not None or self.supersedes_revision_id is not None:
            raise ValueError("provider/supersedes revision identities must be null")
        if type(self.source_bounded) is not bool or not self.source_bounded:
            raise TypeError("source_bounded must be exact true")
        _exact_false(
            self.revision_closure_complete,
            self.decision_grade_eligible,
            self.deployment_authorized,
        )
        expected_revision_id = canonical_sha256(self._body())
        if type(self.revision_id) is not str:
            raise TypeError("revision_id must be exact str")
        if self.revision_id == "":
            object.__setattr__(self, "revision_id", expected_revision_id)
        else:
            _hash("revision_id", self.revision_id)
            if self.revision_id != expected_revision_id:
                raise ValueError("revision_id mismatch")

    def _body(self) -> dict[str, object]:
        return {
            "type": "gree_2023_financial_statement_observation_revision",
            "schema_version": self.schema_version,
            "statement_kind": self.statement_kind.value,
            "economic_statement_key": self.economic_statement_key,
            "observation_lineage_key": self.observation_lineage_key,
            "instrument_id": self.instrument_id,
            "report_period_end": self.report_period_end,
            "period_kind": self.period_kind,
            "consolidation_scope": self.consolidation_scope,
            "accounting_currency": self.accounting_currency,
            "accounting_unit": self.accounting_unit,
            "presentation_basis": self.presentation_basis,
            "announcement_date": self.announcement_date,
            "actual_announcement_date": self.actual_announcement_date,
            "available_at_utc": self.available_at_utc,
            "source_snapshot_id": self.source_snapshot_id,
            "source_content_tree_hash": self.source_content_tree_hash,
            "source_provenance_hash": self.source_provenance_hash,
            "source_member_key": self.source_member_key,
            "source_member_content_hash": self.source_member_content_hash,
            "source_row_hashes": self.source_row_hashes,
            "provider_update_flags": self.provider_update_flags,
            "official_document_hash": self.official_document_hash,
            "publication_confirmation_hash": self.publication_confirmation_hash,
            "declaration_hash": self.declaration_hash,
            "raw_null_fields": self.raw_null_fields,
            "line_items": _line_item_dict(self.line_items),
            "line_items_hash": self.line_items_hash,
            "provider_revision_id": self.provider_revision_id,
            "supersedes_revision_id": self.supersedes_revision_id,
            "source_bounded": self.source_bounded,
            "revision_closure_complete": self.revision_closure_complete,
            "decision_grade_eligible": self.decision_grade_eligible,
            "deployment_authorized": self.deployment_authorized,
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "revision_id": self.revision_id}


@dataclass(frozen=True, slots=True)
class Gree2023FinancialStatementObservationSetV1:
    schema_version: int
    source_snapshot_id: str
    declaration_hash: str
    available_at_utc: UtcInstant
    revisions: tuple[Gree2023FinancialStatementObservationRevisionV1, ...]
    ending_interest_bearing_debt: str
    ending_depreciation_and_amortization: str
    source_bounded: bool
    revision_closure_complete: bool
    decision_grade_eligible: bool
    deployment_authorized: bool
    observation_set_hash: str

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != _SCHEMA_VERSION:
            raise ValueError("schema_version mismatch")
        if self.source_snapshot_id != _SNAPSHOT_ID or self.declaration_hash != _DECLARATION_HASH:
            raise ValueError("observation set source binding mismatch")
        _hash("source_snapshot_id", self.source_snapshot_id)
        _hash("declaration_hash", self.declaration_hash)
        if type(self.available_at_utc) is not UtcInstant or self.available_at_utc != UtcInstant(
            _EXPECTED_AVAILABLE_AT_NS
        ):
            raise ValueError("observation set availability mismatch")
        if type(self.revisions) is not tuple or len(self.revisions) != 3:
            raise TypeError("revisions must be exact three-revision tuple")
        trusted = tuple(_reconstruct_revision(value) for value in self.revisions)
        if any(value is None for value in trusted):
            raise ValueError("nested revision reconstruction mismatch")
        rebuilt = cast(tuple[Gree2023FinancialStatementObservationRevisionV1, ...], trusted)
        if tuple(value.statement_kind for value in rebuilt) != tuple(Gree2023FinancialStatementKind):
            raise ValueError("revision statement order mismatch")
        if any(
            value.source_snapshot_id != self.source_snapshot_id
            or value.declaration_hash != self.declaration_hash
            or value.available_at_utc != self.available_at_utc
            for value in rebuilt
        ):
            raise ValueError("nested revision source binding mismatch")
        object.__setattr__(self, "revisions", rebuilt)
        for name in ("ending_interest_bearing_debt", "ending_depreciation_and_amortization"):
            value = getattr(self, name)
            if type(value) is not str or _DECIMAL.fullmatch(value) is None:
                raise ValueError(f"{name} must be canonical decimal text")
        if self.ending_depreciation_and_amortization != "5283331216.38":
            raise ValueError("D&A supplement mismatch")
        if self.ending_interest_bearing_debt != "88533001486.99":
            raise ValueError("debt supplement mismatch")
        if type(self.source_bounded) is not bool or not self.source_bounded:
            raise TypeError("source_bounded must be exact true")
        _exact_false(
            self.revision_closure_complete,
            self.decision_grade_eligible,
            self.deployment_authorized,
        )
        expected_hash = canonical_sha256(self._body())
        if type(self.observation_set_hash) is not str:
            raise TypeError("observation_set_hash must be exact str")
        if self.observation_set_hash == "":
            object.__setattr__(self, "observation_set_hash", expected_hash)
        else:
            _hash("observation_set_hash", self.observation_set_hash)
            if self.observation_set_hash != expected_hash:
                raise ValueError("observation_set_hash mismatch")

    def _body(self) -> dict[str, object]:
        return {
            "type": "gree_2023_financial_statement_observation_set",
            "schema_version": self.schema_version,
            "source_snapshot_id": self.source_snapshot_id,
            "declaration_hash": self.declaration_hash,
            "available_at_utc": self.available_at_utc,
            "revisions": tuple(value.to_canonical_dict() for value in self.revisions),
            "ending_interest_bearing_debt": self.ending_interest_bearing_debt,
            "ending_depreciation_and_amortization": self.ending_depreciation_and_amortization,
            "source_bounded": self.source_bounded,
            "revision_closure_complete": self.revision_closure_complete,
            "decision_grade_eligible": self.decision_grade_eligible,
            "deployment_authorized": self.deployment_authorized,
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "observation_set_hash": self.observation_set_hash}


@dataclass(frozen=True, slots=True)
class Gree2023FinancialNormalizationOutcome:
    observation_set: Gree2023FinancialStatementObservationSetV1 | None
    failure: Gree2023FinancialNormalizationFailure | None

    def __post_init__(self) -> None:
        if (self.observation_set is None) == (self.failure is None):
            raise ValueError("outcome must contain exactly one observation set or failure")
        if self.observation_set is not None:
            trusted = _reconstruct_set(self.observation_set)
            if trusted is None:
                raise ValueError("outcome observation set reconstruction mismatch")
            object.__setattr__(self, "observation_set", trusted)
        if self.failure is not None and type(self.failure) is not Gree2023FinancialNormalizationFailure:
            raise TypeError("failure must be exact normalization failure")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "gree_2023_financial_normalization_outcome",
            "schema_version": _SCHEMA_VERSION,
            "observation_set": self.observation_set.to_canonical_dict() if self.observation_set else None,
            "failure": self.failure.to_canonical_dict() if self.failure else None,
        }


@dataclass(frozen=True, slots=True)
class _DecimalToken:
    lexeme: str

    def __post_init__(self) -> None:
        if type(self.lexeme) is not str:
            raise TypeError("JSON numeric token must be exact str")


@dataclass(frozen=True, slots=True)
class _ParsedStatement:
    kind: Gree2023FinancialStatementKind
    fields: tuple[str, ...]
    rows: tuple[tuple[str | None, ...], ...]


def _failed(code: FailureCode) -> Gree2023FinancialNormalizationOutcome:
    return Gree2023FinancialNormalizationOutcome(
        None, Gree2023FinancialNormalizationFailure(code)
    )


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, child in pairs:
        if key in value:
            raise ValueError("duplicate JSON object key")
        value[key] = child
    return value


def _reject_constant(_: str) -> object:
    raise ValueError("non-finite JSON constant")


def _parse_statement(
    source: bytes, kind: Gree2023FinancialStatementKind
) -> _ParsedStatement:
    try:
        parsed = json.loads(
            source.decode("utf-8"),
            parse_int=_DecimalToken,
            parse_float=_DecimalToken,
            parse_constant=_reject_constant,
            object_pairs_hook=_unique_object,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        raise ValueError("response JSON invalid") from None
    _, expected_fields, _, _ = _statement_spec(kind)
    if type(parsed) is not dict or set(parsed) != {"request_id", "code", "data", "msg", "detail"}:
        raise ValueError("response envelope mismatch")
    data = parsed["data"]
    if (
        type(parsed["request_id"]) is not str
        or not parsed["request_id"]
        or parsed["request_id"] != parsed["request_id"].strip()
        or type(parsed["code"]) is not _DecimalToken
        or parsed["code"].lexeme != "0"
        or parsed["msg"] != ""
        or type(parsed["detail"]) is not str
        or type(data) is not dict
        or set(data) != {"fields", "items", "has_more", "count"}
        or type(data["fields"]) is not list
        or tuple(data["fields"]) != expected_fields
        or any(type(value) is not str for value in data["fields"])
        or type(data["items"]) is not list
        or type(data["has_more"]) is not bool
        or data["has_more"]
        or type(data["count"]) is not _DecimalToken
        or data["count"].lexeme != "0"
    ):
        raise ValueError("response schema mismatch")
    rows: list[tuple[str | None, ...]] = []
    for row in data["items"]:
        if type(row) is not list or len(row) != len(expected_fields):
            raise ValueError("response row shape mismatch")
        values: list[str | None] = []
        for index, value in enumerate(row):
            is_context = index < 6 or index == len(expected_fields) - 1
            if is_context:
                if type(value) is not str:
                    raise ValueError("response context primitive mismatch")
                values.append(value)
            elif type(value) is _DecimalToken:
                values.append(value.lexeme)
            elif value is None:
                values.append(None)
            else:
                raise ValueError("response line-item primitive mismatch")
        rows.append(tuple(values))
    return _ParsedStatement(kind, expected_fields, tuple(rows))


def _reconstruct_declaration(value: object) -> Gree2023FinancialDocumentDeclarationsV1 | None:
    if type(value) is not Gree2023FinancialDocumentDeclarationsV1:
        return None
    try:
        rebuilt = Gree2023FinancialDocumentDeclarationsV1(
            source_snapshot_id=value.source_snapshot_id,
            content_tree_hash=value.content_tree_hash,
            provenance_hash=value.provenance_hash,
            reviewer_identity=value.reviewer_identity,
            reviewed_at=value.reviewed_at,
            confirmed_disclosure_date=value.confirmed_disclosure_date,
            accounting_currency=value.accounting_currency,
            accounting_unit=value.accounting_unit,
            bank_borrowings_and_other=value.bank_borrowings_and_other,
            bonds_payable=value.bonds_payable,
            lease_liabilities_including_current=value.lease_liabilities_including_current,
            non_debt_dividends_payable=value.non_debt_dividends_payable,
            official_table_total=value.official_table_total,
            ending_interest_bearing_debt=value.ending_interest_bearing_debt,
            combined_depreciation_amount=value.combined_depreciation_amount,
            intangible_amortization_amount=value.intangible_amortization_amount,
            separate_use_right_addition=value.separate_use_right_addition,
            separate_long_term_deferred_addition=value.separate_long_term_deferred_addition,
            ending_depreciation_and_amortization=value.ending_depreciation_and_amortization,
            source_bounded=value.source_bounded,
            revision_closure_complete=value.revision_closure_complete,
            decision_grade_eligible=value.decision_grade_eligible,
            deployment_authorized=value.deployment_authorized,
            declaration_hash=value.declaration_hash,
        )
        return rebuilt if rebuilt.to_canonical_dict() == value.to_canonical_dict() else None
    except (AttributeError, TypeError, ValueError):
        return None


def _reconstruct_revision(
    value: object,
) -> Gree2023FinancialStatementObservationRevisionV1 | None:
    if type(value) is not Gree2023FinancialStatementObservationRevisionV1:
        return None
    try:
        rebuilt = Gree2023FinancialStatementObservationRevisionV1(
            **{
                name: getattr(value, name)
                for name in Gree2023FinancialStatementObservationRevisionV1.__dataclass_fields__
            }
        )
        return rebuilt if rebuilt.to_canonical_dict() == value.to_canonical_dict() else None
    except (AttributeError, TypeError, ValueError):
        return None


def _reconstruct_set(value: object) -> Gree2023FinancialStatementObservationSetV1 | None:
    if type(value) is not Gree2023FinancialStatementObservationSetV1:
        return None
    try:
        rebuilt = Gree2023FinancialStatementObservationSetV1(
            **{
                name: getattr(value, name)
                for name in Gree2023FinancialStatementObservationSetV1.__dataclass_fields__
            }
        )
        return rebuilt if rebuilt.to_canonical_dict() == value.to_canonical_dict() else None
    except (AttributeError, TypeError, ValueError):
        return None


def _source_rows_match(parsed: _ParsedStatement) -> bool:
    expected = _statement_spec(parsed.kind)[2]
    hashes = tuple(sorted(canonical_sha256(row) for row in parsed.rows))
    return len(parsed.rows) == len(expected) and hashes == expected


def _context_matches(parsed: _ParsedStatement) -> bool:
    expected = ("000651.SZ", _ANNOUNCEMENT_DATE, _ANNOUNCEMENT_DATE, _PERIOD, "1", "1")
    return all(row[:6] == expected and row[-1] in {"0", "1"} for row in parsed.rows)


def _resolved_line_items(
    parsed: _ParsedStatement,
    declaration: Gree2023FinancialDocumentDeclarationsV1,
) -> tuple[tuple[LineItem, ...], tuple[str, ...], tuple[tuple[str, str], ...]]:
    evidence = tuple(
        sorted(
            (
                canonical_sha256(row),
                cast(str, row[-1]),
            )
            for row in parsed.rows
        )
    )
    row = parsed.rows[0]
    names = parsed.fields[6:-1]
    raw_values = dict(zip(names, row[6:-1], strict=True))
    raw_nulls = tuple(name for name in names if raw_values[name] is None)
    resolved = dict(raw_values)
    if parsed.kind is Gree2023FinancialStatementKind.BALANCE:
        resolved["bond_payable"] = declaration.bonds_payable
        resolved["st_bonds_payable"] = declaration.bonds_payable
    return tuple((name, resolved[name]) for name in names), raw_nulls, evidence


def _build_revision(
    parsed: _ParsedStatement,
    declaration: Gree2023FinancialDocumentDeclarationsV1,
) -> Gree2023FinancialStatementObservationRevisionV1:
    line_items, raw_nulls, evidence = _resolved_line_items(parsed, declaration)
    member, _, _, member_hash = _statement_spec(parsed.kind)
    return Gree2023FinancialStatementObservationRevisionV1(
        schema_version=_SCHEMA_VERSION,
        statement_kind=parsed.kind,
        economic_statement_key=_economic_key(parsed.kind),
        observation_lineage_key=_lineage_key(parsed.kind),
        instrument_id=_INSTRUMENT,
        report_period_end=_PERIOD,
        period_kind="ANNUAL",
        consolidation_scope="CONSOLIDATED",
        accounting_currency=declaration.accounting_currency,
        accounting_unit=declaration.accounting_unit,
        presentation_basis=_PRESENTATION_BASIS,
        announcement_date=_ANNOUNCEMENT_DATE,
        actual_announcement_date=_ANNOUNCEMENT_DATE,
        available_at_utc=_AVAILABLE_AT,
        source_snapshot_id=_SNAPSHOT_ID,
        source_content_tree_hash=_CONTENT_TREE_HASH,
        source_provenance_hash=_PROVENANCE_HASH,
        source_member_key=member,
        source_member_content_hash=member_hash,
        source_row_hashes=tuple(value[0] for value in evidence),
        provider_update_flags=tuple(value[1] for value in evidence),
        official_document_hash=_REPORT_HASH,
        publication_confirmation_hash=_CONFIRMATION_HASH,
        declaration_hash=declaration.declaration_hash,
        raw_null_fields=raw_nulls,
        line_items=line_items,
        line_items_hash=canonical_sha256(_line_item_dict(line_items)),
        provider_revision_id=None,
        supersedes_revision_id=None,
        source_bounded=True,
        revision_closure_complete=False,
        decision_grade_eligible=False,
        deployment_authorized=False,
        revision_id="",
    )


def _build_set(
    parsed: tuple[_ParsedStatement, ...],
    declaration: Gree2023FinancialDocumentDeclarationsV1,
) -> Gree2023FinancialStatementObservationSetV1:
    revisions = tuple(_build_revision(value, declaration) for value in parsed)
    return Gree2023FinancialStatementObservationSetV1(
        schema_version=_SCHEMA_VERSION,
        source_snapshot_id=_SNAPSHOT_ID,
        declaration_hash=declaration.declaration_hash,
        available_at_utc=_AVAILABLE_AT,
        revisions=revisions,
        ending_interest_bearing_debt=declaration.ending_interest_bearing_debt,
        ending_depreciation_and_amortization=declaration.ending_depreciation_and_amortization,
        source_bounded=True,
        revision_closure_complete=False,
        decision_grade_eligible=False,
        deployment_authorized=False,
        observation_set_hash="",
    )


def normalize_gree_2023_financial_statements_v1(
    source_snapshot: SourceSnapshot,
    declarations: Gree2023FinancialDocumentDeclarationsV1,
) -> Gree2023FinancialNormalizationOutcome:
    if type(source_snapshot) is not SourceSnapshot or type(declarations) is not Gree2023FinancialDocumentDeclarationsV1:
        return _failed(Gree2023FinancialNormalizationFailureCode.INPUT_MISMATCH)

    try:
        verified = verify_source_snapshot(source_snapshot)
    except (AttributeError, TypeError, ValueError):
        return _failed(Gree2023FinancialNormalizationFailureCode.SOURCE_IDENTITY_MISMATCH)
    if verified.failure is not None:
        return _failed(verified.failure.code)
    if (
        source_snapshot.snapshot_id != _SNAPSHOT_ID
        or source_snapshot.content_tree_hash != _CONTENT_TREE_HASH
        or source_snapshot.provenance_hash != _PROVENANCE_HASH
    ):
        return _failed(Gree2023FinancialNormalizationFailureCode.SOURCE_IDENTITY_MISMATCH)

    declaration = _reconstruct_declaration(declarations)
    if (
        declaration is None
        or declaration.declaration_hash != _DECLARATION_HASH
        or declaration.source_snapshot_id != source_snapshot.snapshot_id
        or declaration.content_tree_hash != source_snapshot.content_tree_hash
        or declaration.provenance_hash != source_snapshot.provenance_hash
    ):
        return _failed(Gree2023FinancialNormalizationFailureCode.DECLARATION_MISMATCH)

    members = {member.member_key: member for member in source_snapshot.members}
    parsed_values: list[_ParsedStatement] = []
    for kind in Gree2023FinancialStatementKind:
        member_key, _, _, member_hash = _statement_spec(kind)
        member = members.get(member_key)
        if member is None or member.content_hash != member_hash:
            return _failed(Gree2023FinancialNormalizationFailureCode.SOURCE_RESPONSE_INVALID)
        try:
            parsed_values.append(_parse_statement(source_snapshot.member_bytes(member_key), kind))
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, TypeError, ValueError):
            return _failed(Gree2023FinancialNormalizationFailureCode.SOURCE_RESPONSE_INVALID)
    parsed = tuple(parsed_values)

    if any(not _source_rows_match(value) for value in parsed):
        return _failed(Gree2023FinancialNormalizationFailureCode.SOURCE_ROW_SET_MISMATCH)
    if any(not _context_matches(value) for value in parsed):
        return _failed(Gree2023FinancialNormalizationFailureCode.STATEMENT_CONTEXT_MISMATCH)

    balance = parsed[1]
    update_index = balance.fields.index("update_flag")
    economic_rows = {
        row[:update_index] + row[update_index + 1 :] for row in balance.rows
    }
    if len(economic_rows) != 1:
        return _failed(Gree2023FinancialNormalizationFailureCode.BALANCE_PRESENTATION_CONFLICT)

    required = {
        Gree2023FinancialStatementKind.INCOME: _INCOME_FIELDS[6:-1],
        Gree2023FinancialStatementKind.BALANCE: tuple(
            name for name in _BALANCE_FIELDS[6:-1] if name not in {"bond_payable", "st_bonds_payable"}
        ),
        Gree2023FinancialStatementKind.CASH_FLOW: tuple(
            name for name in _CASHFLOW_FIELDS[6:-1] if name not in {"use_right_asset_dep", "lt_amort_deferred_exp"}
        ),
    }
    for value in parsed:
        positions = {name: index for index, name in enumerate(value.fields)}
        if any(value.rows[0][positions[name]] is None for name in required[value.kind]):
            return _failed(Gree2023FinancialNormalizationFailureCode.REQUIRED_LINE_ITEM_MISSING)

    balance_values = dict(zip(balance.fields, balance.rows[0], strict=True))
    cashflow = parsed[2]
    cashflow_values = dict(zip(cashflow.fields, cashflow.rows[0], strict=True))
    if (
        declaration.declaration_hash != _DECLARATION_HASH
        or declaration.bonds_payable != "0.00"
        or balance_values["bond_payable"] is not None
        or balance_values["st_bonds_payable"] is not None
        or cashflow_values["depr_fa_coga_dpba"] != declaration.combined_depreciation_amount
        or cashflow_values["amort_intang_assets"] != declaration.intangible_amortization_amount
        or declaration.separate_use_right_addition != "0.00"
        or declaration.separate_long_term_deferred_addition != "0.00"
        or Decimal(declaration.combined_depreciation_amount)
        + Decimal(declaration.intangible_amortization_amount)
        != Decimal(declaration.ending_depreciation_and_amortization)
    ):
        return _failed(Gree2023FinancialNormalizationFailureCode.DECLARATION_SUBSTITUTION_MISMATCH)

    if type(_AVAILABLE_AT) is not UtcInstant or _AVAILABLE_AT != UtcInstant(_EXPECTED_AVAILABLE_AT_NS):
        return _failed(Gree2023FinancialNormalizationFailureCode.AVAILABILITY_MISMATCH)

    try:
        observation_set = _build_set(parsed, declaration)
        trusted = _reconstruct_set(observation_set)
        if trusted is None or trusted.to_canonical_dict() != observation_set.to_canonical_dict():
            raise ValueError("result reconstruction mismatch")
    except (AttributeError, TypeError, ValueError):
        return _failed(Gree2023FinancialNormalizationFailureCode.RESULT_RECONSTRUCTION_MISMATCH)
    return Gree2023FinancialNormalizationOutcome(trusted, None)
