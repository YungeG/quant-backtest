from __future__ import annotations

import ast
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = "33f7320bd3f1e81c6a985f2fdeea39aedb7bc01e"
MODULE = (
    ROOT
    / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/official_annual_report_nonfiling_v1.py"
)
ALLOWED = {
    "packages/market-bundle-builder/src/crypto_quant_bundle_builder/official_annual_report_nonfiling_v1.py",
    "tests/bundle_builder/providers/tushare/test_official_annual_report_nonfiling_v1.py",
    "tests/architecture/test_official_annual_report_nonfiling_v1_boundary.py",
}
REQUIRED_SYMBOLS = {
    "NonFilingDocumentRole",
    "NonFilingAuthority",
    "ReviewedNonFilingDocumentV1",
    "OfficialNonFilingAvailabilityV1",
    "OfficialAnnualReportNonFilingRequestV1",
    "OfficialAnnualReportNonFilingDeclarationV1",
    "OfficialAnnualReportNonFilingFailure",
    "OfficialAnnualReportNonFilingOutcome",
    "declare_official_annual_report_nonfiling_v1",
}
DOCUMENT_FIELDS = (
    "type", "schema_version", "role", "authority", "member_key",
    "source_url", "published_date", "publication_precision",
    "published_at_epoch_nanoseconds", "content_hash", "byte_count",
    "reviewed_pages", "reviewed_excerpt", "issuer_assertion",
    "period_assertion", "supersedes_member_key", "reviewer_key",
    "reviewed_at_epoch_nanoseconds",
)
AVAILABILITY_FIELDS = (
    "type", "schema_version", "availability_id", "document_member_key",
    "source_visibility_at", "deadline_boundary_at", "available_at",
    "calendar_authority_id", "source_availability_id",
)
REQUEST_FIELDS = (
    "type",
    "schema_version",
    "instrument_id",
    "provider_code",
    "fiscal_period_end_date",
    "statutory_deadline_date",
    "source_snapshot",
    "source_documents",
    "initial_availability",
    "terminal_availability",
    "active_interval_end",
    "terminal_confirmation_fact_date",
    "limitations",
)
DECLARATION_FIELDS = (
    "type", "schema_version", "declaration_id", "instrument_id",
    "provider_code", "fiscal_period_end_date", "statutory_deadline_date",
    "filing_status", "economic_effective_date", "initial_availability",
    "terminal_availability", "available_at", "active_interval_start",
    "active_interval_end", "covered_api_names", "covered_statement_kinds",
    "source_snapshot_id", "source_content_tree_hash", "source_provenance_hash",
    "source_document_refs", "terminal_confirmation",
    "terminal_confirmation_fact_date", "terminal_confirmation_available_at",
    "limitations",
)


def _imports(tree: ast.AST) -> set[str]:
    return {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }


def test_nonfiling_packet_is_pure_builder_only_and_not_publicly_exported() -> None:
    source = MODULE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = _imports(tree)
    assert REQUIRED_SYMBOLS <= {
        node.name
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef))
    }
    assert not any(
        name.startswith(("crypto_quant_backtest", "crypto_quant_market_data", "crypto_quant_trading"))
        for name in imported
    )
    assert not any(
        name.startswith(("os", "pathlib", "requests", "urllib", "http", "socket", "subprocess", "time"))
        for name in imported
    )
    for forbidden in (
        "Path(",
        "open(",
        "datetime.now",
        "date.today",
        "time.time",
        "PDF",
        "pypdf",
        "pdfplumber",
        "MarketBundle",
        ".publish(",
    ):
        assert forbidden not in source
    assert "verify_source_snapshot" in source
    assert "canonical_sha256" in source
    assert "InstrumentId" in source and "VenueId" in source and "UtcInstant" in source

    public_root = (
        ROOT / "packages/market-bundle-builder/src/crypto_quant_bundle_builder/__init__.py"
    ).read_text(encoding="utf-8")
    assert "official_annual_report_nonfiling_v1" not in public_root
    assert "OfficialAnnualReportNonFiling" not in public_root


def test_request_schema_and_builder_signature_are_exact() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))

    def fields(class_name: str) -> tuple[str, ...]:
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

    assert fields("ReviewedNonFilingDocumentV1") == DOCUMENT_FIELDS
    assert fields("OfficialNonFilingAvailabilityV1") == AVAILABILITY_FIELDS
    assert fields("OfficialAnnualReportNonFilingRequestV1") == REQUEST_FIELDS
    assert fields("OfficialAnnualReportNonFilingDeclarationV1") == DECLARATION_FIELDS

    operation = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "declare_official_annual_report_nonfiling_v1"
    )
    assert [argument.arg for argument in operation.args.args] == ["request"]
    assert operation.args.kwonlyargs == []


def test_candidate_write_set_is_exact_and_base_is_unchanged_elsewhere() -> None:
    subprocess.run(["git", "merge-base", "--is-ancestor", BASE, "HEAD"], cwd=ROOT, check=True)
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
