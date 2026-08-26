from __future__ import annotations

import ast
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = "33f7320bd3f1e81c6a985f2fdeea39aedb7bc01e"
MODULE = (
    ROOT
    / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/pan_hai_2014_official_balance_backfill_v1.py"
)
ALLOWED = {
    "packages/market-bundle-builder/src/crypto_quant_bundle_builder/pan_hai_2014_official_balance_backfill_v1.py",
    "tests/bundle_builder/providers/tushare/test_pan_hai_2014_official_balance_backfill_v1.py",
    "tests/architecture/test_pan_hai_2014_official_balance_backfill_v1_boundary.py",
}
REQUIRED_SYMBOLS = {
    "BalanceFieldApplicability",
    "PanHai2014BalanceFieldReviewV1",
    "PanHai2014ReviewedBalanceEvidenceV1",
    "PanHai2014BalanceAvailabilityV1",
    "PanHai2014OfficialBalanceBackfillRequestV1",
    "PanHai2014OfficialBalanceBackfillV1",
    "PanHai2014OfficialBalanceBackfillFailure",
    "PanHai2014OfficialBalanceBackfillOutcome",
    "build_pan_hai_2014_official_balance_backfill_v1",
}
FIELD_REVIEW_FIELDS = (
    "type",
    "schema_version",
    "field_key",
    "source_label",
    "pdf_page",
    "applicability",
    "value_decimal_text",
)
EVIDENCE_FIELDS = (
    "type",
    "schema_version",
    "reviewer_key",
    "reviewed_at_epoch_nanoseconds",
    "pdf_member_key",
    "metadata_member_key",
    "statement_pages",
    "audit_page",
    "statement_title",
    "issuer_name",
    "provider_code",
    "fiscal_period_end_date",
    "publication_date",
    "currency",
    "unit_text",
    "unit_multiplier",
    "consolidation",
    "company_layout",
    "audit_opinion",
    "audit_report_date",
    "audit_report_number",
    "field_reviews",
    "limitations",
)
AVAILABILITY_FIELDS = (
    "type",
    "schema_version",
    "availability_id",
    "pdf_member_key",
    "source_publication_date",
    "source_visibility_at",
    "publication_boundary_at",
    "available_at",
    "calendar_authority_id",
    "source_availability_id",
)
REQUEST_FIELDS = (
    "type",
    "schema_version",
    "source_snapshot",
    "reviewed_evidence",
    "availability",
)
BACKFILL_FIELDS = (
    "type",
    "schema_version",
    "backfill_id",
    "instrument_id",
    "provider_code",
    "api_name",
    "period",
    "statement_kind",
    "source_snapshot_id",
    "source_content_tree_hash",
    "source_provenance_hash",
    "reviewed_evidence",
    "availability",
    "field_reviews",
    "covered_member_key",
    "financial_payload_complete",
    "financial_scope_qualified",
    "scope_reason",
    "limitations",
)
OUTCOME_FIELDS = ("backfill", "failure")


def _imports(tree: ast.AST) -> set[str]:
    return {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }


def _fields(tree: ast.Module, class_name: str) -> tuple[str, ...]:
    declaration = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    return tuple(
        node.target.id
        for node in declaration.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    )


def test_packet_is_pure_builder_only_without_public_export_or_target_authority() -> None:
    source = MODULE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = _imports(tree)
    assert REQUIRED_SYMBOLS <= {
        node.name
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef))
    }
    assert not any(
        name.startswith(
            (
                "crypto_quant_backtest",
                "crypto_quant_market_data",
                "crypto_quant_trading",
            )
        )
        for name in imported
    )
    assert not any(
        name.startswith(
            (
                "os",
                "pathlib",
                "requests",
                "urllib",
                "http",
                "socket",
                "subprocess",
                "time",
                "pypdf",
                "pdfplumber",
            )
        )
        for name in imported
    )
    for forbidden in (
        "Path(",
        "open(",
        "datetime.now",
        "date.today",
        "time.time",
        "member_bytes(",
        "freeze_source_snapshot",
        "MarketBundle",
        "BacktestRuntime",
        ".publish(",
        "1428370200000000000",
        "report_type",
        "comp_type",
        "update_flag",
    ):
        assert forbidden not in source
    assert "verify_source_snapshot" in source
    assert "canonical_sha256" in source
    assert "InstrumentId" in source
    assert "VenueId" in source
    assert "UtcInstant" in source

    public_root = (
        ROOT / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/__init__.py"
    ).read_text(encoding="utf-8")
    assert "pan_hai_2014_official_balance_backfill_v1" not in public_root
    assert "PanHai2014OfficialBalanceBackfill" not in public_root


def test_packet_schemas_signature_failure_enum_and_scope_are_exact() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    assert _fields(tree, "PanHai2014BalanceFieldReviewV1") == FIELD_REVIEW_FIELDS
    assert _fields(tree, "PanHai2014ReviewedBalanceEvidenceV1") == EVIDENCE_FIELDS
    assert _fields(tree, "PanHai2014BalanceAvailabilityV1") == AVAILABILITY_FIELDS
    assert _fields(tree, "PanHai2014OfficialBalanceBackfillRequestV1") == REQUEST_FIELDS
    assert _fields(tree, "PanHai2014OfficialBalanceBackfillV1") == BACKFILL_FIELDS
    assert _fields(tree, "PanHai2014OfficialBalanceBackfillOutcome") == OUTCOME_FIELDS

    operation = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "build_pan_hai_2014_official_balance_backfill_v1"
    )
    assert [argument.arg for argument in operation.args.args] == ["request"]
    assert operation.args.kwonlyargs == []

    failure = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "PanHai2014OfficialBalanceBackfillFailure"
    )
    values = tuple(
        ast.literal_eval(node.value)
        for node in failure.body
        if isinstance(node, ast.Assign)
    )
    assert values == (
        "INPUT_TYPE_MISMATCH",
        "CATALOG_IDENTITY_MISMATCH",
        "SOURCE_MEMBER_CONFLICT",
        "FINANCIAL_REVISION_MISMATCH",
        "FINANCIAL_PAYLOAD_INCOMPLETE",
        "PUBLICATION_INTEGRITY_FAILURE",
    )

    source = MODULE.read_text(encoding="utf-8")
    assert '("balancesheet_vip", "xshe:000046", "20141231")' in source
    assert '"MIXED_REAL_ESTATE_SECURITIES_CONSOLIDATION"' in source
    assert '"STATEMENT_SCOPE_UNSUPPORTED"' in source
    assert source.count('"financial_payload_complete": self.financial_payload_complete') == 1
    assert source.count('"financial_scope_qualified": self.financial_scope_qualified') == 1


def test_candidate_write_set_is_exact_and_base_is_unchanged_elsewhere() -> None:
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", BASE, "HEAD"],
        cwd=ROOT,
        check=True,
    )
    changed = {
        line[3:]
        for line in subprocess.check_output(
            ["git", "status", "--short", "--untracked-files=all"],
            cwd=ROOT,
            text=True,
        ).splitlines()
    }
    committed = set(
        subprocess.check_output(
            ["git", "diff", "--name-only", f"{BASE}..HEAD"],
            cwd=ROOT,
            text=True,
        ).splitlines()
    )
    assert changed <= ALLOWED
    assert committed <= ALLOWED
    assert changed | committed == ALLOWED
