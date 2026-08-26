from __future__ import annotations

import json
import re
from dataclasses import dataclass, fields
from enum import Enum
from typing import cast

from crypto_quant_domain import UtcInstant, canonical_sha256

from .gree_historical_financial_document_declarations_v1 import (
    GreeHistoricalFinancialDeclarationFailure,
    GreeHistoricalFinancialDeclarationFailureCode,
    GreeHistoricalFinancialDeclarationOutcome,
    GreeHistoricalFinancialPeriodDocumentDeclarationsV1,
)
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
_PUBLICATION_METADATA_HASH = "sha256:3292c3b1bd89f01cb41e09401ad306b6ec8e769cac402317817fe395ff0e918e"
_INSTRUMENT = "xshe:000651"
_PRESENTATION_BASIS = "CURRENT_CONSOLIDATED"
_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_DECIMAL = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?\Z")

_INCOME_FIELDS = (
    "ts_code", "ann_date", "f_ann_date", "end_date", "report_type", "comp_type",
    "revenue", "operate_profit", "total_profit", "income_tax", "n_income",
    "n_income_attr_p", "minority_gain", "fin_exp_int_exp", "ebit", "ebitda",
    "update_flag",
)
_BALANCE_FIELDS = (
    "ts_code", "ann_date", "f_ann_date", "end_date", "report_type", "comp_type",
    "money_cap", "total_assets", "total_liab", "total_hldr_eqy_inc_min_int",
    "total_hldr_eqy_exc_min_int", "minority_int", "total_liab_hldr_eqy", "st_borr",
    "non_cur_liab_due_1y", "lt_borr", "bond_payable", "st_bonds_payable",
    "lease_liab", "update_flag",
)
_CASHFLOW_FIELDS = (
    "ts_code", "ann_date", "f_ann_date", "end_date", "report_type", "comp_type",
    "n_cashflow_act", "c_pay_acq_const_fiolta", "depr_fa_coga_dpba",
    "use_right_asset_dep", "amort_intang_assets", "lt_amort_deferred_exp",
    "c_cash_equ_end_period", "free_cashflow", "update_flag",
)


class GreeHistoricalFinancialStatementKind(str, Enum):
    INCOME = "INCOME"
    BALANCE = "BALANCE"
    CASH_FLOW = "CASH_FLOW"


class GreeHistoricalFinancialNormalizationFailureCode(str, Enum):
    INPUT_MISMATCH = "INPUT_MISMATCH"
    DECLARATION_MISMATCH = "DECLARATION_MISMATCH"
    SOURCE_IDENTITY_MISMATCH = "SOURCE_IDENTITY_MISMATCH"
    DEBT_SCOPE_INCOMPLETE = "DEBT_SCOPE_INCOMPLETE"
    SOURCE_RESPONSE_INVALID = "SOURCE_RESPONSE_INVALID"
    SOURCE_ROW_SET_MISMATCH = "SOURCE_ROW_SET_MISMATCH"
    STATEMENT_CONTEXT_MISMATCH = "STATEMENT_CONTEXT_MISMATCH"
    PRESENTATION_CONFLICT = "PRESENTATION_CONFLICT"
    DECLARATION_SUPPLEMENT_MISMATCH = "DECLARATION_SUPPLEMENT_MISMATCH"
    AVAILABILITY_MISMATCH = "AVAILABILITY_MISMATCH"
    RESULT_RECONSTRUCTION_MISMATCH = "RESULT_RECONSTRUCTION_MISMATCH"


FailureCode = GreeHistoricalFinancialNormalizationFailureCode | SourceSnapshotFailureCode
LineItem = tuple[str, str | None]


@dataclass(frozen=True, slots=True)
class _StatementSpec:
    member: str
    member_hash: str
    fields: tuple[str, ...]
    row_evidence: tuple[tuple[str, str], ...]
    line_items: tuple[LineItem, ...]
    raw_null_fields: tuple[str, ...]
    unresolved_fields: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class _PeriodSpec:
    declaration_hash: str
    announcement_date: str
    official_document_hash: str
    available_at_ns: int
    availability_source_hashes: tuple[str, ...]
    ending_debt: str
    ending_da: str
    statements: tuple[tuple[GreeHistoricalFinancialStatementKind, _StatementSpec], ...]


def _statement(member: str, member_hash: str, fields: tuple[str, ...], row_hashes: tuple[str, ...], flags: tuple[str, ...], line_items: tuple[LineItem, ...], raw_null_fields: tuple[str, ...], unresolved_fields: tuple[str, ...] = ()) -> _StatementSpec:
    return _StatementSpec(member, member_hash, fields, tuple(zip(row_hashes, flags, strict=True)), line_items, raw_null_fields, unresolved_fields)


_PERIOD_SPECS = {
    "20181231": _PeriodSpec(
        "sha256:51b1ae41791336ead0487148e721c530ff0de8b5a718d81d4b3d2fe63a55a575", "20190429",
        "sha256:b147eb6b8a4aaf093f3b83550c70e8526415b5b54fe24e4258ce7bfd11d5406a", 1556587800000000000,
        ("sha256:888302b51ee0f22713c20ac9afb08b72ba7d3fb01945c9f181eede1e4385ff4b", "sha256:e7d30c906216ebd7b2f0308c9ee0b609192fb3f9462c12ab938c64ff33be40b3"),
        "22383629781.83", "3110329271.82",
        ((GreeHistoricalFinancialStatementKind.BALANCE, _statement(
            "response/tushare/balancesheet/000651.SZ-20181231-20190429-v3.json", "sha256:d412a0972630ba642aa06f162885cc06ba9d1310b5e40a604169c3cecc8355e1", _BALANCE_FIELDS,
            ("sha256:0c8f5e8a8c6107573be52e29afcf5d03adf544c55a7f705a2d37dc41cdbbadf1", "sha256:436143a5f528e7c61ff71a43486258f5efe6121b5b810b61a9d769188d576456"), ("0", "1"),
            (("money_cap", "113079030368.11"), ("total_assets", "251234157276.81"), ("total_liab", "158519445549.35"), ("total_hldr_eqy_inc_min_int", "92714711727.46"), ("total_hldr_eqy_exc_min_int", "91327095069.1"), ("minority_int", "1387616658.36"), ("total_liab_hldr_eqy", "251234157276.81"), ("st_borr", "22067750002.7"), ("non_cur_liab_due_1y", None), ("lt_borr", None), ("bond_payable", None), ("st_bonds_payable", None), ("lease_liab", None)),
            ("non_cur_liab_due_1y", "lt_borr", "bond_payable", "st_bonds_payable", "lease_liab"))),),
    ),
    "20191231": _PeriodSpec(
        "sha256:0f52ca93b04c25d2135a584d853198ad2655f0cec31cc161867c22010927aa96", "20200430",
        "sha256:1b4869caab122969b322738df69955d788c8dc19b4c6d57188619177e922e708", 1588728600000000000,
        ("sha256:f386cf8cb0f9e3e9c288b231e3a07b190464917c191687026a29b07ab3ef18af", "sha256:348218aab3164083e52057f7313d7d9d7e29f3701b464bc3cc030b600fc23215", "sha256:bc75da295c9857ed8d8fa50f00f3e783307649d548fbc2660bad227a11b0d835"),
        "17344021324.26", "3194419239.65",
        (
            (GreeHistoricalFinancialStatementKind.INCOME, _statement("response/tushare/income/000651.SZ-20191231-20200430-v3.json", "sha256:982a5d65674e8f58f6277bc9c89aa0f894281f49fa5769b84ac67760faafd586", _INCOME_FIELDS, ("sha256:2d74a71e7390fac916705537f15f1cd29aeaa4aed4b9f4724d9ec7a0625c3d12", "sha256:cff83cb7e3ea02f44ad667e1baf2748c0e9d434f74d8096f04116e7fc4410b2e"), ("1", "0"), (("revenue", "198153027540.35"), ("operate_profit", "29605107122.4"), ("total_profit", "29352707228.7"), ("income_tax", "4525463624.73"), ("n_income", "24827243603.97"), ("n_income_attr_p", "24696641368.84"), ("minority_gain", "130602235.13"), ("fin_exp_int_exp", "1598276258.59"), ("ebit", "27947212725.83"), ("ebitda", "31141631965.48")), ())),
            (GreeHistoricalFinancialStatementKind.BALANCE, _statement("response/tushare/balancesheet/000651.SZ-20191231-20200430-v3.json", "sha256:cd4a19de67c30837df4546abbb87f0bfeef97d1c2359a25fce29ee0a6d1631b8", _BALANCE_FIELDS, ("sha256:0eede15c1f9033a38ee0b41ef3a279d3fd24dfb84bff78c91795b684c2fdad54", "sha256:3e82d2ec45dd7e9afc931f7e80c14b39da7cc5026db11705e091eb151b253a2a"), ("1", "0"), (("money_cap", "125400715267.64"), ("total_assets", "282972157415.28"), ("total_liab", "170924500892.2"), ("total_hldr_eqy_inc_min_int", "112047656523.08"), ("total_hldr_eqy_exc_min_int", "110153573282.67"), ("minority_int", "1894083240.41"), ("total_liab_hldr_eqy", "282972157415.28"), ("st_borr", "15944176463.01"), ("non_cur_liab_due_1y", None), ("lt_borr", "46885882.86"), ("bond_payable", None), ("st_bonds_payable", None), ("lease_liab", None)), ("non_cur_liab_due_1y", "bond_payable", "st_bonds_payable", "lease_liab"))),
            (GreeHistoricalFinancialStatementKind.CASH_FLOW, _statement("response/tushare/cashflow/000651.SZ-20191231-20200430-v3.json", "sha256:9d2837a0897cb25e40e428d037ed276ea03b19508159251f510bd21f08b1b305", _CASHFLOW_FIELDS, ("sha256:125f686ad284aaec663439be6369e4ae2ca112d225d109abe3a212368a638a28", "sha256:fedce59f03b3958c7fdb4d01851b2189245cba5ebd2d44ba3cfef1bbd1ee8f3d"), ("1", "0"), (("n_cashflow_act", "27893714093.59"), ("c_pay_acq_const_fiolta", "4713187965.97"), ("depr_fa_coga_dpba", "2977103353.04"), ("use_right_asset_dep", None), ("amort_intang_assets", "215796437.95"), ("lt_amort_deferred_exp", "1519448.66"), ("c_cash_equ_end_period", "26372571821.49"), ("free_cashflow", "38794013433.0428")), ("use_right_asset_dep",))),
        ),
    ),
    "20201231": _PeriodSpec(
        "sha256:14143974d80d622721ecf78e3eae1e3467815366dc9bd90657774bd8473ee099", "20210429",
        "sha256:0d3c39090adf97fede39149a731a5636bd0eca2002606fb942ca70121dba9072", 1619746200000000000,
        ("sha256:348218aab3164083e52057f7313d7d9d7e29f3701b464bc3cc030b600fc23215", "sha256:57cda17f2cdbfba82ddb10cbf595806cc34a498b22b9edc6d50da38dfe232ad7"),
        "23201159352.29", "3588706333.78",
        (
            (GreeHistoricalFinancialStatementKind.INCOME, _statement("response/tushare/income/000651.SZ-20201231-20210429-v3.json", "sha256:c90bf9ceaca99e6246544e7a3d5b9ce18f6010ce5dd46f8fdf19b6670f439f8a", _INCOME_FIELDS, ("sha256:526c9a14945d0ec256f6b521ce2b13ba4a942e60f0a8d9b39f27cd5e77a0b249", "sha256:76d72b36d08d121b5ef12b037c723d4e70c79450804defce13191cf6cddbcde3"), ("0", "1"), (("revenue", "168199204404.53"), ("operate_profit", "26043517837.7"), ("total_profit", "26308937428.79"), ("income_tax", "4029695233.52"), ("n_income", "22279242195.27"), ("n_income_attr_p", "22175108137.32"), ("minority_gain", "104134057.95"), ("fin_exp_int_exp", "1088369394.87"), ("ebit", "23318957276.21"), ("ebitda", "26907663609.99")), ())),
            (GreeHistoricalFinancialStatementKind.BALANCE, _statement("response/tushare/balancesheet/000651.SZ-20201231-20210429-v3.json", "sha256:967469a431b76e6f3af5d2d2af5abe8c726951c7742cb8b2ec7f0804bfd5238c", _BALANCE_FIELDS, ("sha256:3e1c1256838e8e1e03bad1e19fba81134bf1376896a39907e5fe58cb83638adb", "sha256:dccef36e8378b78c76efea167a8354bba0f520403c58ff33de3c43b86e988069"), ("1", "0"), (("money_cap", "136413143859.81"), ("total_assets", "279217923628.27"), ("total_liab", "162337436540.13"), ("total_hldr_eqy_inc_min_int", "116880487088.14"), ("total_hldr_eqy_exc_min_int", "115190211206.76"), ("minority_int", "1690275881.38"), ("total_liab_hldr_eqy", "279217923628.27"), ("st_borr", "20304384742.34"), ("non_cur_liab_due_1y", None), ("lt_borr", "1860713816.09"), ("bond_payable", None), ("st_bonds_payable", None), ("lease_liab", None)), ("non_cur_liab_due_1y", "bond_payable", "st_bonds_payable", "lease_liab"))),
            (GreeHistoricalFinancialStatementKind.CASH_FLOW, _statement("response/tushare/cashflow/000651.SZ-20201231-20210429-v3.json", "sha256:0bad70737efd1091934524b4a8022d24f7dbc4f0935ddb0fde67013223bc7ccb", _CASHFLOW_FIELDS, ("sha256:1b1c7295f057a39d7c8d0ffc18e719381b8857d2526daa9fbb246caa81484037", "sha256:f2441ea67e9231a4b612f9deef05825d71d2c3ff7ce299add0ae26cb35f62e11"), ("1", "0"), (("n_cashflow_act", "19238637309.16"), ("c_pay_acq_const_fiolta", "4528646805.03"), ("depr_fa_coga_dpba", "3377378887.04"), ("use_right_asset_dep", None), ("amort_intang_assets", "211327446.74"), ("lt_amort_deferred_exp", None), ("c_cash_equ_end_period", "24225049638.15"), ("free_cashflow", "14100983784.043")), ("use_right_asset_dep", "lt_amort_deferred_exp"))),
        ),
    ),
    "20221231": _PeriodSpec(
        "sha256:1124c88497385f9233df6c4f8c6ece397379d382a18d27aeacead31b82539aba", "20230429",
        "sha256:7cfc80c2badbf4cd74c5adc080d5072b02cd6c700b04fa7ca0ac44cb8b8fe987", 1683163800000000000,
        ("sha256:a56a1050b2d516ad287ac1aa5edb7b9cde3e1e007a4e3d3917056bba24cedab8", "sha256:58ea091197cc7c95eae9c3a0dab2ae80f45a4d54f26a3755810b8672517cdea9", "sha256:7018114a6e11deb239c2a72e71e49defc6e8841b3e2c093b3bbf809282c67222", "sha256:a5288222974e04cb25c52f1d2c04059217eee552cbce6e4e91fa7a792f07cf83", "sha256:d668beafd3aa475345e9c8f60210c9793de3868ef9da11312f1b1316c5b068d5"),
        "86027130079.25", "4997685416.88",
        (
            (GreeHistoricalFinancialStatementKind.INCOME, _statement("response/tushare/income/000651.SZ-20221231-20230429-v3.json", "sha256:51f6ad53f20172cbeacd10e928d41682f46810c4bec0ba6f954831770c6c3e65", _INCOME_FIELDS, ("sha256:d9b6c258c86cd517d0174a6e2c45ef6c9835310c78735df0d08a728ed6329be4",), ("1",), (("revenue", "188988382706.68"), ("operate_profit", "27284097086.18"), ("total_profit", "27217384842.61"), ("income_tax", "4206040489.5"), ("n_income", "23011344353.11"), ("n_income_attr_p", "24506623782.46"), ("minority_gain", "-1495279429.35"), ("fin_exp_int_exp", "2836743431.08"), ("ebit", "25617870403.76"), ("ebitda", "30587816420.11")), ())),
            (GreeHistoricalFinancialStatementKind.BALANCE, _statement("response/tushare/balancesheet/000651.SZ-20221231-20230429-v3.json", "sha256:9c5f870bbf1601964801223019af51ab281fabb671a83c78b582bb28ea615fe5", _BALANCE_FIELDS, ("sha256:62a2c5212905023399073dd0ea8fecdf92d00e86e59bc2a80ad18308ea2d24fe", "sha256:fb4471d6a17c7184eb39834d04f6606c4c95ef94b7d0b3fbf651b0fab3b606b2"), ("0", "1"), (("money_cap", "157484332251.39"), ("total_assets", "355024758878.82"), ("total_liab", "253148710864.63"), ("total_hldr_eqy_inc_min_int", "101876048014.19"), ("total_hldr_eqy_exc_min_int", "96758734892.25"), ("minority_int", "5117313121.94"), ("total_liab_hldr_eqy", "355024758878.82"), ("st_borr", "52895851287.92"), ("non_cur_liab_due_1y", "255342537.57"), ("lt_borr", "30784241211.21"), ("bond_payable", None), ("st_bonds_payable", None), ("lease_liab", "146836620.66")), ("bond_payable", "st_bonds_payable"))),
            (GreeHistoricalFinancialStatementKind.CASH_FLOW, _statement("response/tushare/cashflow/000651.SZ-20221231-20230429-v3.json", "sha256:c81e36321dc7b64412789deab14f6a43ec465bd7c15f3b937594556ceeac6e54", _CASHFLOW_FIELDS, ("sha256:336f90eb45f8cc80df7da6968751d7ec503e2bea203557ecfc1a0a841d94914b", "sha256:9dc0456482960fa746c74c6e693d5497ecaa01e6a972a2c56f92f98794614438"), ("0", "1"), (("n_cashflow_act", "28668435921.27"), ("c_pay_acq_const_fiolta", "6036136315.75"), ("depr_fa_coga_dpba", "4597938791.84"), ("use_right_asset_dep", None), ("amort_intang_assets", "372007224.51"), ("lt_amort_deferred_exp", None), ("c_cash_equ_end_period", "31754656695.61"), ("free_cashflow", None)), ("use_right_asset_dep", "lt_amort_deferred_exp"), ("free_cashflow",))),
        ),
    ),
}

_EXPECTED_REVISION_IDS = {
    ("20181231", "BALANCE"): "sha256:c3be5c3de8b458180a350e8e0c84ba3618fc23393c51817e1c2fd823f9cf4148",
    ("20191231", "INCOME"): "sha256:176122a6db10c8ee7ec20eb2862632dc19cbdae9d1e1537c0a98708d3ac5b231",
    ("20191231", "BALANCE"): "sha256:c898675a1b7b5db86cf7d4db1cace6fb27045f4214ea351a3ef4974523f0e7b3",
    ("20191231", "CASH_FLOW"): "sha256:22438762ffb7532e9653d354686eae61b3812172e4868825f87691ccc5cd1349",
    ("20201231", "INCOME"): "sha256:35d35b0856b6cecb8d8bb79c21d48058e44fcc51f6a7bd6c9c23a73a26b4a0ca",
    ("20201231", "BALANCE"): "sha256:f883c487f930e3a58706965678bebabbb3fc5f200e2304fc521d3d4ace2ed7b6",
    ("20201231", "CASH_FLOW"): "sha256:7d991e01d78363478e53a95401156a9f035120ae393c96cfcbccd680d80393b1",
    ("20221231", "INCOME"): "sha256:ad1037c494eb4e79f215c4a342d814a5f3478ffcc1042bce61cc570b16ce761f",
    ("20221231", "BALANCE"): "sha256:b3b9a5f5bf4dcdbfdeed4e9a2f53a6bfdc5f72655c7cbe3bdb521364bee5c396",
    ("20221231", "CASH_FLOW"): "sha256:7812b0f8fd492e70a6a4aaa23dff33dbd0a4db9bf347b19e403bc3d55eb0387b",
}
_EXPECTED_SET_HASHES = {
    "20181231": "sha256:20638846aa5eb0c98e30efcae5693114553ef8794a2697783d740ec658d38c68",
    "20191231": "sha256:02bb2571ea9cef06465f0151b747004c34f4baa35b5d59b63e71f65c707fd7d1",
    "20201231": "sha256:2c6110a07d2a7c80745a3cabf35b84b4aeb13f1cd4901d53c24cca619c40f4ce",
    "20221231": "sha256:92d196719be464dc79938db432f442e2d56891effd04adb7e11031f6e31fe736",
}
_DECLARATION_FAILURE_HASH = "sha256:2c5b90d0cbd89ccd584c0a33234d796ec9b039abe683ad897b7a5fe61cac5792"
_EXPECTED_NORMALIZATION_FAILURE_HASH = "sha256:2cedd67871396e99f324623540ac66f1b254d31020d0e81ba075c6b5876bbc82"
_EXPECTED_AVAILABLE_AT_NS = {period: spec.available_at_ns for period, spec in _PERIOD_SPECS.items()}
_AVAILABILITY_SOURCE_HASHES = {period: spec.availability_source_hashes for period, spec in _PERIOD_SPECS.items()}


def _hash(name: str, value: object) -> str:
    if type(value) is not str or _HASH.fullmatch(value) is None:
        raise ValueError(f"{name} must be canonical sha256")
    return value


def _exact_false(*values: object) -> None:
    if any(type(value) is not bool or value for value in values):
        raise TypeError("qualification flags must be exact false")


def _line_item_dict(values: tuple[LineItem, ...]) -> dict[str, str | None]:
    return dict(values)


def _spec(period: str, kind: GreeHistoricalFinancialStatementKind) -> _StatementSpec:
    return dict(_PERIOD_SPECS[period].statements)[kind]


def _economic_key(period: str, kind: GreeHistoricalFinancialStatementKind) -> str:
    return canonical_sha256({"instrument_id": _INSTRUMENT, "statement_kind": kind.value, "report_period_end": period, "period_kind": "ANNUAL", "consolidation_scope": "CONSOLIDATED", "accounting_currency": "CNY", "accounting_unit": "yuan"})


def _lineage_key(period: str, kind: GreeHistoricalFinancialStatementKind) -> str:
    return canonical_sha256({"instrument_id": _INSTRUMENT, "statement_kind": kind.value, "report_period_end": period, "period_kind": "ANNUAL", "consolidation_scope": "CONSOLIDATED", "accounting_currency": "CNY", "accounting_unit": "yuan", "presentation_basis": _PRESENTATION_BASIS})


def _reconstruct_instant(value: object) -> UtcInstant:
    if type(value) is not UtcInstant or type(value.epoch_nanoseconds) is not int:
        raise TypeError("available_at_utc must be exact reconstructable UtcInstant")
    rebuilt = UtcInstant(value.epoch_nanoseconds)
    if rebuilt != value:
        raise ValueError("available_at_utc reconstruction mismatch")
    return rebuilt


@dataclass(frozen=True, slots=True)
class GreeHistoricalFinancialAdvisoryObservationV1:
    source_row_hash: str
    provider_update_flag: str
    value: str

    def __post_init__(self) -> None:
        _hash("source_row_hash", self.source_row_hash)
        if type(self.provider_update_flag) is not str or self.provider_update_flag not in {"0", "1"}:
            raise ValueError("provider_update_flag mismatch")
        if type(self.value) is not str or _DECIMAL.fullmatch(self.value) is None:
            raise ValueError("advisory value must be canonical decimal text")

    def to_canonical_dict(self) -> dict[str, object]:
        return {"source_row_hash": self.source_row_hash, "provider_update_flag": self.provider_update_flag, "value": self.value}


@dataclass(frozen=True, slots=True)
class GreeHistoricalFinancialAdvisoryConflictV1:
    field: str
    observations: tuple[GreeHistoricalFinancialAdvisoryObservationV1, ...]

    def __post_init__(self) -> None:
        if type(self.field) is not str or not self.field:
            raise ValueError("advisory field must be exact non-empty str")
        if type(self.observations) is not tuple or not self.observations:
            raise TypeError("advisory observations must be non-empty tuple")
        if any(type(value) is not GreeHistoricalFinancialAdvisoryObservationV1 for value in self.observations):
            raise TypeError("advisory observation must be exact class")
        rebuilt = tuple(
            GreeHistoricalFinancialAdvisoryObservationV1(
                value.source_row_hash, value.provider_update_flag, value.value
            )
            for value in self.observations
        )
        if tuple(value.source_row_hash for value in rebuilt) != tuple(sorted(value.source_row_hash for value in rebuilt)):
            raise ValueError("advisory observations must use row-hash order")
        object.__setattr__(self, "observations", rebuilt)

    def to_canonical_dict(self) -> dict[str, object]:
        return {"field": self.field, "observations": tuple(value.to_canonical_dict() for value in self.observations)}


@dataclass(frozen=True, slots=True)
class GreeHistoricalFinancialNormalizationFailure:
    schema_version: int
    code: FailureCode
    report_period: str | None
    declaration_failure: GreeHistoricalFinancialDeclarationFailure | None
    failure_hash: str

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != _SCHEMA_VERSION:
            raise ValueError("schema_version mismatch")
        if type(self.code) not in (GreeHistoricalFinancialNormalizationFailureCode, SourceSnapshotFailureCode):
            raise TypeError("code must be exact normalization or SourceSnapshot failure")
        if self.report_period is not None and type(self.report_period) is not str:
            raise TypeError("report_period must be exact str or None")
        if self.code is GreeHistoricalFinancialNormalizationFailureCode.DEBT_SCOPE_INCOMPLETE:
            rebuilt = _reconstruct_declaration_failure(self.declaration_failure)
            if (
                rebuilt is None
                or rebuilt.code is not GreeHistoricalFinancialDeclarationFailureCode.DEBT_SCOPE_INCOMPLETE
                or rebuilt.report_period != "20211231"
                or rebuilt.failure_hash != _DECLARATION_FAILURE_HASH
                or self.report_period != "20211231"
            ):
                raise ValueError("canonical declaration failure required")
            object.__setattr__(self, "declaration_failure", rebuilt)
        elif self.declaration_failure is not None:
            raise ValueError("only debt-scope failure stores declaration failure")
        expected = canonical_sha256(self._body())
        if type(self.failure_hash) is not str:
            raise TypeError("failure_hash must be exact str")
        if not self.failure_hash:
            object.__setattr__(self, "failure_hash", expected)
        elif _hash("failure_hash", self.failure_hash) != expected:
            raise ValueError("failure_hash mismatch")

    def _body(self) -> dict[str, object]:
        return {"type": "gree_historical_financial_normalization_failure", "schema_version": self.schema_version, "code": self.code.value, "report_period": self.report_period, "declaration_failure": None if self.declaration_failure is None else self.declaration_failure.to_canonical_dict()}

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "failure_hash": self.failure_hash}


@dataclass(frozen=True, slots=True)
class GreeHistoricalFinancialStatementObservationRevisionV1:
    schema_version: int
    statement_kind: GreeHistoricalFinancialStatementKind
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
    availability_source_hashes: tuple[str, ...]
    source_snapshot_id: str
    source_content_tree_hash: str
    source_provenance_hash: str
    source_member_key: str
    source_member_content_hash: str
    source_row_evidence: tuple[tuple[str, str], ...]
    official_document_hash: str
    publication_metadata_hash: str
    declaration_hash: str
    raw_null_fields: tuple[str, ...]
    unresolved_fields: tuple[str, ...]
    advisory_conflicts: tuple[GreeHistoricalFinancialAdvisoryConflictV1, ...]
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
        if type(self.statement_kind) is not GreeHistoricalFinancialStatementKind or type(self.report_period_end) is not str or self.report_period_end not in _PERIOD_SPECS:
            raise ValueError("statement period/kind mismatch")
        period = _PERIOD_SPECS[self.report_period_end]
        statement = _spec(self.report_period_end, self.statement_kind)
        expected = ((self.instrument_id, _INSTRUMENT), (self.period_kind, "ANNUAL"), (self.consolidation_scope, "CONSOLIDATED"), (self.accounting_currency, "CNY"), (self.accounting_unit, "yuan"), (self.presentation_basis, _PRESENTATION_BASIS), (self.announcement_date, period.announcement_date), (self.actual_announcement_date, period.announcement_date), (self.source_snapshot_id, _SNAPSHOT_ID), (self.source_content_tree_hash, _CONTENT_TREE_HASH), (self.source_provenance_hash, _PROVENANCE_HASH), (self.source_member_key, statement.member), (self.source_member_content_hash, statement.member_hash), (self.official_document_hash, period.official_document_hash), (self.publication_metadata_hash, _PUBLICATION_METADATA_HASH), (self.declaration_hash, period.declaration_hash))
        if any(type(value) is not str or value != wanted for value, wanted in expected):
            raise ValueError("revision context mismatch")
        _hash("economic_statement_key", self.economic_statement_key)
        _hash("observation_lineage_key", self.observation_lineage_key)
        for name in ("source_snapshot_id", "source_content_tree_hash", "source_provenance_hash", "source_member_content_hash", "official_document_hash", "publication_metadata_hash", "declaration_hash", "line_items_hash"):
            _hash(name, getattr(self, name))
        if self.economic_statement_key != _economic_key(self.report_period_end, self.statement_kind) or self.observation_lineage_key != _lineage_key(self.report_period_end, self.statement_kind):
            raise ValueError("statement key mismatch")
        instant = _reconstruct_instant(self.available_at_utc)
        if instant != UtcInstant(period.available_at_ns):
            raise ValueError("revision availability mismatch")
        object.__setattr__(self, "available_at_utc", instant)
        if type(self.availability_source_hashes) is not tuple or self.availability_source_hashes != period.availability_source_hashes or any(type(value) is not str or _HASH.fullmatch(value) is None for value in self.availability_source_hashes):
            raise ValueError("availability source hashes mismatch")
        if type(self.source_row_evidence) is not tuple or self.source_row_evidence != statement.row_evidence or any(type(value) is not tuple or len(value) != 2 or type(value[0]) is not str or type(value[1]) is not str for value in self.source_row_evidence):
            raise ValueError("source row evidence mismatch")
        if type(self.raw_null_fields) is not tuple or self.raw_null_fields != statement.raw_null_fields or any(type(value) is not str for value in self.raw_null_fields) or type(self.unresolved_fields) is not tuple or self.unresolved_fields != statement.unresolved_fields or any(type(value) is not str for value in self.unresolved_fields):
            raise ValueError("null/unresolved evidence mismatch")
        if type(self.advisory_conflicts) is not tuple:
            raise TypeError("advisory_conflicts must be tuple")
        rebuilt_conflicts = tuple(_reconstruct_advisory_conflict(value) for value in self.advisory_conflicts)
        if any(value is None for value in rebuilt_conflicts):
            raise ValueError("advisory conflict reconstruction mismatch")
        object.__setattr__(self, "advisory_conflicts", cast(tuple[GreeHistoricalFinancialAdvisoryConflictV1, ...], rebuilt_conflicts))
        if self.advisory_conflicts != _expected_advisory_conflicts(self.report_period_end, self.statement_kind):
            raise ValueError("advisory conflict mismatch")
        if type(self.line_items) is not tuple or self.line_items != statement.line_items or any(type(value) is not tuple or len(value) != 2 or type(value[0]) is not str or (value[1] is not None and (type(value[1]) is not str or _DECIMAL.fullmatch(value[1]) is None)) for value in self.line_items):
            raise ValueError("line item exact value mismatch")
        if self.line_items_hash != canonical_sha256(_line_item_dict(self.line_items)):
            raise ValueError("line_items_hash mismatch")
        if self.provider_revision_id is not None or self.supersedes_revision_id is not None:
            raise ValueError("provider/supersedes revision identities must be null")
        if type(self.source_bounded) is not bool or not self.source_bounded:
            raise TypeError("source_bounded must be exact true")
        _exact_false(self.revision_closure_complete, self.decision_grade_eligible, self.deployment_authorized)
        expected_id = canonical_sha256(self._body())
        if type(self.revision_id) is not str:
            raise TypeError("revision_id must be exact str")
        if not self.revision_id:
            object.__setattr__(self, "revision_id", expected_id)
        elif _hash("revision_id", self.revision_id) != expected_id:
            raise ValueError("revision_id mismatch")

    def _body(self) -> dict[str, object]:
        return {
            "type": "gree_historical_financial_statement_observation_revision", "schema_version": self.schema_version,
            "statement_kind": self.statement_kind.value, "economic_statement_key": self.economic_statement_key,
            "observation_lineage_key": self.observation_lineage_key, "instrument_id": self.instrument_id,
            "report_period_end": self.report_period_end, "period_kind": self.period_kind,
            "consolidation_scope": self.consolidation_scope, "accounting_currency": self.accounting_currency,
            "accounting_unit": self.accounting_unit, "presentation_basis": self.presentation_basis,
            "announcement_date": self.announcement_date, "actual_announcement_date": self.actual_announcement_date,
            "available_at_utc": self.available_at_utc, "availability_source_hashes": self.availability_source_hashes,
            "source_snapshot_id": self.source_snapshot_id, "source_content_tree_hash": self.source_content_tree_hash,
            "source_provenance_hash": self.source_provenance_hash, "source_member_key": self.source_member_key,
            "source_member_content_hash": self.source_member_content_hash,
            "source_row_evidence": tuple({"source_row_hash": row_hash, "provider_update_flag": update_flag} for row_hash, update_flag in self.source_row_evidence),
            "official_document_hash": self.official_document_hash, "publication_metadata_hash": self.publication_metadata_hash,
            "declaration_hash": self.declaration_hash, "raw_null_fields": self.raw_null_fields,
            "unresolved_fields": self.unresolved_fields, "advisory_conflicts": tuple(value.to_canonical_dict() for value in self.advisory_conflicts),
            "line_items": _line_item_dict(self.line_items), "line_items_hash": self.line_items_hash,
            "provider_revision_id": self.provider_revision_id, "supersedes_revision_id": self.supersedes_revision_id,
            "source_bounded": self.source_bounded, "revision_closure_complete": self.revision_closure_complete,
            "decision_grade_eligible": self.decision_grade_eligible, "deployment_authorized": self.deployment_authorized,
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "revision_id": self.revision_id}


@dataclass(frozen=True, slots=True)
class GreeHistoricalFinancialPeriodObservationSetV1:
    schema_version: int
    report_period_end: str
    source_snapshot_id: str
    declaration_hash: str
    available_at_utc: UtcInstant
    availability_source_hashes: tuple[str, ...]
    revisions: tuple[GreeHistoricalFinancialStatementObservationRevisionV1, ...]
    ending_interest_bearing_debt: str
    ending_depreciation_and_amortization: str
    source_bounded: bool
    revision_closure_complete: bool
    decision_grade_eligible: bool
    deployment_authorized: bool
    observation_set_hash: str

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != _SCHEMA_VERSION or type(self.report_period_end) is not str or self.report_period_end not in _PERIOD_SPECS:
            raise ValueError("observation set period/schema mismatch")
        period = _PERIOD_SPECS[self.report_period_end]
        _hash("source_snapshot_id", self.source_snapshot_id)
        _hash("declaration_hash", self.declaration_hash)
        if self.source_snapshot_id != _SNAPSHOT_ID or self.declaration_hash != period.declaration_hash:
            raise ValueError("observation set source binding mismatch")
        instant = _reconstruct_instant(self.available_at_utc)
        if instant != UtcInstant(period.available_at_ns) or self.availability_source_hashes != period.availability_source_hashes or type(self.availability_source_hashes) is not tuple or any(type(value) is not str or _HASH.fullmatch(value) is None for value in self.availability_source_hashes):
            raise ValueError("observation set availability mismatch")
        object.__setattr__(self, "available_at_utc", instant)
        if type(self.revisions) is not tuple:
            raise TypeError("revisions must be tuple")
        rebuilt = tuple(_reconstruct_revision(value) for value in self.revisions)
        if any(value is None for value in rebuilt):
            raise ValueError("nested revision reconstruction mismatch")
        trusted = cast(tuple[GreeHistoricalFinancialStatementObservationRevisionV1, ...], rebuilt)
        expected_kinds = tuple(kind for kind, _ in period.statements)
        if tuple(value.statement_kind for value in trusted) != expected_kinds or any(value.report_period_end != self.report_period_end or value.source_snapshot_id != self.source_snapshot_id or value.declaration_hash != self.declaration_hash or value.available_at_utc != instant or value.availability_source_hashes != self.availability_source_hashes for value in trusted):
            raise ValueError("nested revision source/order mismatch")
        object.__setattr__(self, "revisions", trusted)
        if type(self.ending_interest_bearing_debt) is not str or self.ending_interest_bearing_debt != period.ending_debt or type(self.ending_depreciation_and_amortization) is not str or self.ending_depreciation_and_amortization != period.ending_da:
            raise ValueError("declaration supplement mismatch")
        if type(self.source_bounded) is not bool or not self.source_bounded:
            raise TypeError("source_bounded must be exact true")
        _exact_false(self.revision_closure_complete, self.decision_grade_eligible, self.deployment_authorized)
        expected_hash = canonical_sha256(self._body())
        if type(self.observation_set_hash) is not str:
            raise TypeError("observation_set_hash must be exact str")
        if not self.observation_set_hash:
            object.__setattr__(self, "observation_set_hash", expected_hash)
        elif _hash("observation_set_hash", self.observation_set_hash) != expected_hash:
            raise ValueError("observation_set_hash mismatch")

    def _body(self) -> dict[str, object]:
        return {"type": "gree_historical_financial_period_observation_set", "schema_version": self.schema_version, "report_period_end": self.report_period_end, "source_snapshot_id": self.source_snapshot_id, "declaration_hash": self.declaration_hash, "available_at_utc": self.available_at_utc, "availability_source_hashes": self.availability_source_hashes, "revisions": tuple(value.to_canonical_dict() for value in self.revisions), "ending_interest_bearing_debt": self.ending_interest_bearing_debt, "ending_depreciation_and_amortization": self.ending_depreciation_and_amortization, "source_bounded": self.source_bounded, "revision_closure_complete": self.revision_closure_complete, "decision_grade_eligible": self.decision_grade_eligible, "deployment_authorized": self.deployment_authorized}

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "observation_set_hash": self.observation_set_hash}


@dataclass(frozen=True, slots=True)
class GreeHistoricalFinancialNormalizationOutcome:
    observation_set: GreeHistoricalFinancialPeriodObservationSetV1 | None
    failure: GreeHistoricalFinancialNormalizationFailure | None

    def __post_init__(self) -> None:
        if (self.observation_set is None) == (self.failure is None):
            raise ValueError("outcome must contain exactly one observation set or failure")
        if self.observation_set is not None:
            rebuilt = _reconstruct_set(self.observation_set)
            if rebuilt is None:
                raise ValueError("outcome observation set reconstruction mismatch")
            object.__setattr__(self, "observation_set", rebuilt)
        if self.failure is not None:
            rebuilt_failure = _reconstruct_failure(self.failure)
            if rebuilt_failure is None:
                raise ValueError("outcome failure reconstruction mismatch")
            object.__setattr__(self, "failure", rebuilt_failure)

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "gree_historical_financial_normalization_outcome", "schema_version": 1, "observation_set": None if self.observation_set is None else self.observation_set.to_canonical_dict(), "failure": None if self.failure is None else self.failure.to_canonical_dict()}


@dataclass(frozen=True, slots=True)
class _DecimalToken:
    lexeme: str


@dataclass(frozen=True, slots=True)
class _ParsedStatement:
    kind: GreeHistoricalFinancialStatementKind
    fields: tuple[str, ...]
    rows: tuple[tuple[str | None, ...], ...]


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(_: str) -> object:
    raise ValueError("non-finite JSON constant")


def _parse_statement(source: bytes, kind: GreeHistoricalFinancialStatementKind, expected_fields: tuple[str, ...]) -> _ParsedStatement:
    try:
        parsed = json.loads(source.decode("utf-8"), parse_int=_DecimalToken, parse_float=_DecimalToken, parse_constant=_reject_constant, object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        raise ValueError("response JSON invalid") from None
    if type(parsed) is not dict or set(parsed) != {"request_id", "code", "data", "msg", "detail"}:
        raise ValueError("response envelope mismatch")
    data = parsed["data"]
    if type(parsed["request_id"]) is not str or not parsed["request_id"] or parsed["request_id"] != parsed["request_id"].strip() or type(parsed["code"]) is not _DecimalToken or parsed["code"].lexeme != "0" or parsed["msg"] != "" or type(parsed["detail"]) is not str or type(data) is not dict or set(data) != {"fields", "items", "has_more", "count"} or type(data["fields"]) is not list or tuple(data["fields"]) != expected_fields or any(type(value) is not str for value in data["fields"]) or type(data["items"]) is not list or type(data["has_more"]) is not bool or data["has_more"] or type(data["count"]) is not _DecimalToken or data["count"].lexeme != "0":
        raise ValueError("response schema mismatch")
    rows: list[tuple[str | None, ...]] = []
    for row in data["items"]:
        if type(row) is not list or len(row) != len(expected_fields):
            raise ValueError("response row shape mismatch")
        values: list[str | None] = []
        for index, value in enumerate(row):
            if index < 6 or index == len(expected_fields) - 1:
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


def _reconstruct_snapshot(value: object) -> SourceSnapshot:
    if type(value) is not SourceSnapshot:
        raise TypeError("source_snapshot must be exact SourceSnapshot")
    members = tuple(SourceSnapshotMember(**{field.name: getattr(member, field.name) for field in fields(SourceSnapshotMember)}) for member in value.members)
    provenance = SourceSnapshotProvenance(**{field.name: getattr(value.provenance, field.name) for field in fields(SourceSnapshotProvenance)})
    rebuilt = SourceSnapshot(value.snapshot_id, value.archive_bytes, value.content_tree_hash, members, provenance, value.provenance_hash, value.decision_grade_eligible, value.deployment_authorized)
    if rebuilt.archive_bytes != value.archive_bytes or rebuilt.to_canonical_dict() != value.to_canonical_dict():
        raise ValueError("source_snapshot reconstruction mismatch")
    return rebuilt


def _reconstruct_declaration_outcome(value: object) -> GreeHistoricalFinancialDeclarationOutcome | None:
    if type(value) is not GreeHistoricalFinancialDeclarationOutcome:
        return None
    try:
        rebuilt = GreeHistoricalFinancialDeclarationOutcome(value.declaration, value.failure)
        return rebuilt if rebuilt.to_canonical_dict() == value.to_canonical_dict() else None
    except (AttributeError, TypeError, ValueError):
        return None


def _reconstruct_declaration_failure(value: object) -> GreeHistoricalFinancialDeclarationFailure | None:
    if type(value) is not GreeHistoricalFinancialDeclarationFailure:
        return None
    try:
        rebuilt = GreeHistoricalFinancialDeclarationFailure(**{field.name: getattr(value, field.name) for field in fields(GreeHistoricalFinancialDeclarationFailure)})
        return rebuilt if rebuilt.to_canonical_dict() == value.to_canonical_dict() else None
    except (AttributeError, TypeError, ValueError):
        return None


def _reconstruct_advisory_conflict(value: object) -> GreeHistoricalFinancialAdvisoryConflictV1 | None:
    if type(value) is not GreeHistoricalFinancialAdvisoryConflictV1:
        return None
    try:
        rebuilt = GreeHistoricalFinancialAdvisoryConflictV1(value.field, value.observations)
        return rebuilt if rebuilt.to_canonical_dict() == value.to_canonical_dict() else None
    except (AttributeError, TypeError, ValueError):
        return None


def _reconstruct_revision(value: object) -> GreeHistoricalFinancialStatementObservationRevisionV1 | None:
    if type(value) is not GreeHistoricalFinancialStatementObservationRevisionV1:
        return None
    try:
        rebuilt = GreeHistoricalFinancialStatementObservationRevisionV1(**{field.name: getattr(value, field.name) for field in fields(GreeHistoricalFinancialStatementObservationRevisionV1)})
        return rebuilt if rebuilt.to_canonical_dict() == value.to_canonical_dict() else None
    except (AttributeError, TypeError, ValueError):
        return None


def _reconstruct_set(value: object) -> GreeHistoricalFinancialPeriodObservationSetV1 | None:
    if type(value) is not GreeHistoricalFinancialPeriodObservationSetV1:
        return None
    try:
        rebuilt = GreeHistoricalFinancialPeriodObservationSetV1(**{field.name: getattr(value, field.name) for field in fields(GreeHistoricalFinancialPeriodObservationSetV1)})
        return rebuilt if rebuilt.to_canonical_dict() == value.to_canonical_dict() else None
    except (AttributeError, TypeError, ValueError):
        return None


def _reconstruct_failure(value: object) -> GreeHistoricalFinancialNormalizationFailure | None:
    if type(value) is not GreeHistoricalFinancialNormalizationFailure:
        return None
    try:
        rebuilt = GreeHistoricalFinancialNormalizationFailure(**{field.name: getattr(value, field.name) for field in fields(GreeHistoricalFinancialNormalizationFailure)})
        return rebuilt if rebuilt.to_canonical_dict() == value.to_canonical_dict() else None
    except (AttributeError, TypeError, ValueError):
        return None


def _failed(code: FailureCode, period: str | None = None, declaration_failure: GreeHistoricalFinancialDeclarationFailure | None = None) -> GreeHistoricalFinancialNormalizationOutcome:
    return GreeHistoricalFinancialNormalizationOutcome(None, GreeHistoricalFinancialNormalizationFailure(_SCHEMA_VERSION, code, period, declaration_failure, ""))


def _expected_advisory_conflicts(period: str, kind: GreeHistoricalFinancialStatementKind) -> tuple[GreeHistoricalFinancialAdvisoryConflictV1, ...]:
    if period != "20221231" or kind is not GreeHistoricalFinancialStatementKind.CASH_FLOW:
        return ()
    return (GreeHistoricalFinancialAdvisoryConflictV1("free_cashflow", (
        GreeHistoricalFinancialAdvisoryObservationV1("sha256:336f90eb45f8cc80df7da6968751d7ec503e2bea203557ecfc1a0a841d94914b", "0", "27066951494.8798"),
        GreeHistoricalFinancialAdvisoryObservationV1("sha256:9dc0456482960fa746c74c6e693d5497ecaa01e6a972a2c56f92f98794614438", "1", "30735381659.7498"),
    )),)


def _row_evidence(parsed: _ParsedStatement) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((canonical_sha256(row), cast(str, row[-1])) for row in parsed.rows))


def _context_matches(parsed: _ParsedStatement, period: str, announcement_date: str) -> bool:
    expected = ("000651.SZ", announcement_date, announcement_date, period, "1", "1")
    return all(row[:6] == expected and row[-1] in {"0", "1"} for row in parsed.rows)


def _resolve(parsed: _ParsedStatement, period: str) -> tuple[tuple[LineItem, ...], tuple[str, ...], tuple[str, ...], tuple[GreeHistoricalFinancialAdvisoryConflictV1, ...]] | None:
    rows = tuple(sorted(parsed.rows, key=canonical_sha256))
    ignored = {len(parsed.fields) - 1}
    if period == "20221231" and parsed.kind is GreeHistoricalFinancialStatementKind.CASH_FLOW:
        ignored.add(parsed.fields.index("free_cashflow"))
    if len({tuple(value for index, value in enumerate(row) if index not in ignored) for row in rows}) != 1:
        return None
    names = parsed.fields[6:-1]
    values = dict(zip(names, rows[0][6:-1], strict=True))
    raw_nulls = tuple(name for name in names if values[name] is None)
    unresolved: tuple[str, ...] = ()
    conflicts: tuple[GreeHistoricalFinancialAdvisoryConflictV1, ...] = ()
    if period == "20221231" and parsed.kind is GreeHistoricalFinancialStatementKind.CASH_FLOW:
        position = parsed.fields.index("free_cashflow")
        observations = tuple(GreeHistoricalFinancialAdvisoryObservationV1(canonical_sha256(row), cast(str, row[-1]), cast(str, row[position])) for row in rows)
        conflicts = (GreeHistoricalFinancialAdvisoryConflictV1("free_cashflow", observations),)
        unresolved = ("free_cashflow",)
        values["free_cashflow"] = None
    return tuple((name, values[name]) for name in names), raw_nulls, unresolved, conflicts


def _declaration_matches(declaration: GreeHistoricalFinancialPeriodDocumentDeclarationsV1, period: str, snapshot: SourceSnapshot) -> bool:
    spec = _PERIOD_SPECS[period]
    body = declaration.to_canonical_dict()
    publication = body.get("publication_evidence")
    statement = body.get("statement_unit")
    return declaration.declaration_hash == spec.declaration_hash and declaration.report_period == period and declaration.source_snapshot_id == snapshot.snapshot_id and declaration.content_tree_hash == snapshot.content_tree_hash and declaration.provenance_hash == snapshot.provenance_hash and declaration.confirmed_disclosure_date == spec.announcement_date and declaration.accounting_currency == "CNY" and declaration.accounting_unit == "yuan" and declaration.ending_interest_bearing_debt == spec.ending_debt and declaration.ending_depreciation_and_amortization == spec.ending_da and type(publication) is dict and publication.get("source_content_hash") == _PUBLICATION_METADATA_HASH and type(statement) is dict and statement.get("source_document_hash") == spec.official_document_hash


def _build_revision(parsed: _ParsedStatement, period: str, resolved: tuple[tuple[LineItem, ...], tuple[str, ...], tuple[str, ...], tuple[GreeHistoricalFinancialAdvisoryConflictV1, ...]]) -> GreeHistoricalFinancialStatementObservationRevisionV1:
    period_spec = _PERIOD_SPECS[period]
    statement = _spec(period, parsed.kind)
    line_items, raw_nulls, unresolved, conflicts = resolved
    return GreeHistoricalFinancialStatementObservationRevisionV1(
        _SCHEMA_VERSION, parsed.kind, _economic_key(period, parsed.kind), _lineage_key(period, parsed.kind), _INSTRUMENT,
        period, "ANNUAL", "CONSOLIDATED", "CNY", "yuan", _PRESENTATION_BASIS,
        period_spec.announcement_date, period_spec.announcement_date, UtcInstant(period_spec.available_at_ns),
        period_spec.availability_source_hashes, _SNAPSHOT_ID, _CONTENT_TREE_HASH, _PROVENANCE_HASH,
        statement.member, statement.member_hash, _row_evidence(parsed), period_spec.official_document_hash,
        _PUBLICATION_METADATA_HASH, period_spec.declaration_hash, raw_nulls, unresolved, conflicts, line_items,
        canonical_sha256(_line_item_dict(line_items)), None, None, True, False, False, False, "",
    )


def _build_set(parsed: tuple[_ParsedStatement, ...], period: str, resolved: tuple[tuple[tuple[LineItem, ...], tuple[str, ...], tuple[str, ...], tuple[GreeHistoricalFinancialAdvisoryConflictV1, ...]], ...]) -> GreeHistoricalFinancialPeriodObservationSetV1:
    spec = _PERIOD_SPECS[period]
    revisions = tuple(_build_revision(value, period, result) for value, result in zip(parsed, resolved, strict=True))
    return GreeHistoricalFinancialPeriodObservationSetV1(_SCHEMA_VERSION, period, _SNAPSHOT_ID, spec.declaration_hash, UtcInstant(spec.available_at_ns), spec.availability_source_hashes, revisions, spec.ending_debt, spec.ending_da, True, False, False, False, "")


def normalize_gree_historical_financial_period_v1(source_snapshot: SourceSnapshot, declaration_outcome: GreeHistoricalFinancialDeclarationOutcome) -> GreeHistoricalFinancialNormalizationOutcome:
    if type(source_snapshot) is not SourceSnapshot or type(declaration_outcome) is not GreeHistoricalFinancialDeclarationOutcome:
        return _failed(GreeHistoricalFinancialNormalizationFailureCode.INPUT_MISMATCH)
    try:
        snapshot = _reconstruct_snapshot(source_snapshot)
    except (AttributeError, TypeError, ValueError):
        return _failed(GreeHistoricalFinancialNormalizationFailureCode.INPUT_MISMATCH)
    declared = _reconstruct_declaration_outcome(declaration_outcome)
    if declared is None:
        return _failed(GreeHistoricalFinancialNormalizationFailureCode.DECLARATION_MISMATCH)
    period = declared.declaration.report_period if declared.declaration is not None else declared.failure.report_period if declared.failure is not None else None
    verified = verify_source_snapshot(snapshot)
    if verified.failure is not None:
        return _failed(verified.failure.code, period)
    if snapshot.snapshot_id != _SNAPSHOT_ID or snapshot.content_tree_hash != _CONTENT_TREE_HASH or snapshot.provenance_hash != _PROVENANCE_HASH:
        return _failed(GreeHistoricalFinancialNormalizationFailureCode.SOURCE_IDENTITY_MISMATCH, period)
    if declared.failure is not None and declared.failure.code is GreeHistoricalFinancialDeclarationFailureCode.DEBT_SCOPE_INCOMPLETE and declared.failure.report_period == "20211231" and declared.failure.failure_hash == _DECLARATION_FAILURE_HASH:
        outcome = _failed(GreeHistoricalFinancialNormalizationFailureCode.DEBT_SCOPE_INCOMPLETE, "20211231", declared.failure)
        if outcome.failure is None or outcome.failure.failure_hash != _EXPECTED_NORMALIZATION_FAILURE_HASH:
            return _failed(GreeHistoricalFinancialNormalizationFailureCode.RESULT_RECONSTRUCTION_MISMATCH, "20211231")
        return outcome
    if declared.failure is not None or declared.declaration is None or period not in _PERIOD_SPECS:
        return _failed(GreeHistoricalFinancialNormalizationFailureCode.DECLARATION_MISMATCH, period)
    declaration = declared.declaration
    period_spec = _PERIOD_SPECS[period]
    members = {member.member_key: member for member in snapshot.members}
    parsed_values: list[_ParsedStatement] = []
    for kind, statement in period_spec.statements:
        member = members.get(statement.member)
        if member is None:
            return _failed(GreeHistoricalFinancialNormalizationFailureCode.SOURCE_RESPONSE_INVALID, period)
        try:
            parsed_values.append(_parse_statement(snapshot.member_bytes(statement.member), kind, statement.fields))
        except (AttributeError, RecursionError, TypeError, ValueError):
            return _failed(GreeHistoricalFinancialNormalizationFailureCode.SOURCE_RESPONSE_INVALID, period)
    parsed = tuple(parsed_values)
    if any(members[_spec(period, value.kind).member].content_hash != _spec(period, value.kind).member_hash or _row_evidence(value) != _spec(period, value.kind).row_evidence for value in parsed):
        return _failed(GreeHistoricalFinancialNormalizationFailureCode.SOURCE_ROW_SET_MISMATCH, period)
    if any(not _context_matches(value, period, period_spec.announcement_date) for value in parsed):
        return _failed(GreeHistoricalFinancialNormalizationFailureCode.STATEMENT_CONTEXT_MISMATCH, period)
    resolved_values = tuple(_resolve(value, period) for value in parsed)
    if any(value is None for value in resolved_values):
        return _failed(GreeHistoricalFinancialNormalizationFailureCode.PRESENTATION_CONFLICT, period)
    resolved = cast(tuple[tuple[tuple[LineItem, ...], tuple[str, ...], tuple[str, ...], tuple[GreeHistoricalFinancialAdvisoryConflictV1, ...]], ...], resolved_values)
    if any(value[3] != _expected_advisory_conflicts(period, parsed_value.kind) for parsed_value, value in zip(parsed, resolved, strict=True)):
        return _failed(GreeHistoricalFinancialNormalizationFailureCode.PRESENTATION_CONFLICT, period)
    if not _declaration_matches(declaration, period, snapshot):
        return _failed(GreeHistoricalFinancialNormalizationFailureCode.DECLARATION_SUPPLEMENT_MISMATCH, period)
    if type(period_spec.available_at_ns) is not int or period_spec.available_at_ns != _EXPECTED_AVAILABLE_AT_NS[period] or type(period_spec.availability_source_hashes) is not tuple or period_spec.availability_source_hashes != _AVAILABILITY_SOURCE_HASHES[period] or any(type(value) is not str or _HASH.fullmatch(value) is None for value in period_spec.availability_source_hashes):
        return _failed(GreeHistoricalFinancialNormalizationFailureCode.AVAILABILITY_MISMATCH, period)
    try:
        observation_set = _build_set(parsed, period, resolved)
        trusted = _reconstruct_set(observation_set)
        if trusted is None or trusted.to_canonical_dict() != observation_set.to_canonical_dict() or tuple(value.revision_id for value in trusted.revisions) != tuple(_EXPECTED_REVISION_IDS[(period, kind.value)] for kind, _ in period_spec.statements) or trusted.observation_set_hash != _EXPECTED_SET_HASHES[period]:
            raise ValueError("result reconstruction mismatch")
        return GreeHistoricalFinancialNormalizationOutcome(trusted, None)
    except (AttributeError, KeyError, TypeError, ValueError):
        return _failed(GreeHistoricalFinancialNormalizationFailureCode.RESULT_RECONSTRUCTION_MISMATCH, period)
