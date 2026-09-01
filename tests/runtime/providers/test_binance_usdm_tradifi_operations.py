from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from crypto_quant_backtest import (
    BacktestCanonicalPublicationRef,
    BacktestEvidenceError,
    BacktestEvidenceRepository,
    BacktestMetricProfile,
    BinanceUsdmTradifiBacktestOperations,
    PreparedBacktestExecution,
    PreparedTradifiTrial,
    VerifiedCanonicalJournalEntryEvidenceV1,
    VerifiedCanonicalJournalEvidenceV1,
    VerifiedResearchCompletedPublicationV1,
    prepare_binance_usdm_tradifi_bar_backtest,
)
from crypto_quant_bundle_builder import (
    LocalMarketBundleRepository,
    LocalMarketBundleRepositoryConfig,
)
from crypto_quant_domain import (
    ArtifactEnvelope,
    ArtifactNotFoundError,
    ArtifactReadResult,
    ArtifactRef,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_market_data import LocalMarketBundleReader

from tests.runtime.providers import test_binance_usdm_tradifi_preparation_v2 as fixture


class _Store:
    def __init__(self, bundle) -> None:
        self.values: dict[ArtifactRef, ArtifactReadResult] = {}
        self.puts: list[ArtifactRef] = []
        for envelope in (*bundle.target_result.artifacts, *bundle.authority_artifacts):
            self.put(envelope=envelope)
        self.puts.clear()

    def put(self, *, envelope: ArtifactEnvelope) -> ArtifactRef:
        ref = ArtifactRef.from_envelope(envelope)
        source = canonical_bytes(envelope)
        self.values[ref] = ArtifactReadResult(
            envelope=envelope,
            artifact=object(),
            source_bytes=source,
            source_hash=canonical_sha256(envelope),
        )
        self.puts.append(ref)
        return ref

    def read(self, *, ref: ArtifactRef) -> ArtifactReadResult:
        try:
            return self.values[ref]
        except KeyError as error:
            raise ArtifactNotFoundError(ref.content_hash) from error


def _local_reader(root: Path, bundle) -> LocalMarketBundleReader:
    published = LocalMarketBundleRepository(
        config=LocalMarketBundleRepositoryConfig(root=root)
    ).publish_market_bundle_v1(
        manifest=bundle.reader.manifest,
        stream_payloads={
            key: canonical_bytes(events)
            for key, events in bundle.reader.streams.items()
        },
        retention_policy_ref="retention.tradifi-operations-test.v1",
    )
    assert published.result is not None
    return LocalMarketBundleReader.open(
        repository_root=root.resolve(), bundle_ref=published.result.bundle_ref
    )


def _plain(value: object) -> dict[str, object]:
    decoded = json.loads(canonical_bytes(value))
    assert type(decoded) is dict
    return decoded


def test_formal_prepare_publishes_runs_and_repository_loads_completion(
    tmp_path: Path,
) -> None:
    bundle = fixture._nonempty_bundle()
    store = _Store(bundle)
    reader = _local_reader(tmp_path / "market", bundle)
    intent = replace(fixture._intent(bundle), experiment_id="formal-smoke")

    prepared = prepare_binance_usdm_tradifi_bar_backtest(
        request_intent=intent,
        provider_inputs=fixture.BinanceUsdmTradifiProviderInputs(
            fixture.build_manifest(), fixture._EQUITY
        ),
        artifact_reader=store,
        artifact_publisher=store,
        market_reader=reader,
        publication_root=tmp_path / "publication",
    )

    assert type(prepared) is PreparedBacktestExecution
    assert [(ref.artifact_type, ref.schema_version) for ref in store.puts] == [
        ("backtest_request", 1),
        ("backtest_execution_input_bundle", 8),
    ]
    assert store.read(ref=prepared.request_ref.to_artifact_ref()).source_bytes
    assert store.read(
        ref=prepared.execution_request.execution_input_bundle_ref
    ).source_bytes

    publication_ref = prepared.runtime.run(prepared.execution_request)

    assert type(publication_ref) is BacktestCanonicalPublicationRef
    repository = BacktestEvidenceRepository(store)
    with pytest.raises(BacktestEvidenceError, match="accounting_journal_entry"):
        repository.load_completed(publication_ref)
    completed = repository.load_completed_research_v1(publication_ref)
    assert type(completed) is VerifiedResearchCompletedPublicationV1
    assert completed.semantic_run_id == prepared.semantic_run_id
    assert completed.execution_summary.fills

    journal = completed.execution_summary.final_journal
    assert type(journal) is VerifiedCanonicalJournalEvidenceV1
    assert not any(name.startswith("replay") for name in dir(journal))
    payloads = [json.loads(entry.canonical_payload) for entry in journal.entries]
    assert {payload["type"] for payload in payloads} >= {
        "linear_derivative_journal_entry",
        "linear_funding_journal_entry",
    }

    derivative = next(
        payload
        for payload in payloads
        if payload["type"] == "linear_derivative_journal_entry"
    )
    funding = next(
        payload
        for payload in payloads
        if payload["type"] == "linear_funding_journal_entry"
    )
    base = VerifiedCanonicalJournalEntryEvidenceV1.from_canonical_payload(
        derivative["journal_entry"]
    )
    assert base.journal_entry.entry_type.value == "fill_booked"
    tampered = json.loads(json.dumps(derivative["journal_entry"]))
    tampered["schema_version"] = 1
    with pytest.raises(ValueError, match="fields"):
        VerifiedCanonicalJournalEntryEvidenceV1.from_canonical_payload(tampered)
    tampered = json.loads(json.dumps(derivative))
    tampered["request_hash"] = "sha256:" + "0" * 64
    with pytest.raises(ValueError, match="request_hash"):
        VerifiedCanonicalJournalEntryEvidenceV1.from_canonical_payload(tampered)
    tampered = json.loads(json.dumps(derivative))
    tampered["schema_version"] = 2
    with pytest.raises(ValueError, match="schema version"):
        VerifiedCanonicalJournalEntryEvidenceV1.from_canonical_payload(tampered)
    tampered = json.loads(json.dumps(funding))
    tampered["schema_version"] = 1
    with pytest.raises(ValueError, match="schema version"):
        VerifiedCanonicalJournalEntryEvidenceV1.from_canonical_payload(tampered)
    tampered = json.loads(json.dumps(derivative))
    tampered["unknown"] = True
    with pytest.raises(ValueError, match="fields"):
        VerifiedCanonicalJournalEntryEvidenceV1.from_canonical_payload(tampered)
    tampered = json.loads(json.dumps(derivative))
    tampered["journal_entry"]["entry_type"] = "funding_applied"
    with pytest.raises(ValueError, match="wrong base entry type"):
        VerifiedCanonicalJournalEntryEvidenceV1.from_canonical_payload(tampered)
    tampered = json.loads(json.dumps(funding))
    tampered["journal_entry"]["entry_type"] = "fill_booked"
    realized = json.loads(json.dumps(funding["payment"]))
    realized["units"] = 1
    tampered["journal_entry"]["realized_pnl"] = [realized]
    with pytest.raises(ValueError, match="wrong base entry type"):
        VerifiedCanonicalJournalEntryEvidenceV1.from_canonical_payload(tampered)
    with pytest.raises(ValueError, match="entry_hash"):
        replace(journal.entries[0], entry_hash="sha256:" + "0" * 64)
    with pytest.raises(ValueError, match="strict stable order"):
        VerifiedCanonicalJournalEvidenceV1(
            tuple(reversed(journal.entries)), journal.journal_hash
        )
    with pytest.raises(ValueError, match="journal_hash"):
        VerifiedCanonicalJournalEvidenceV1(
            journal.entries, "sha256:" + "0" * 64
        )


def test_operations_prepare_run_load_and_analysis_are_exact_and_one_shot(
    tmp_path: Path,
) -> None:
    bundle = fixture._nonempty_bundle()
    store = _Store(bundle)
    reader = _local_reader(tmp_path / "market", bundle)
    template = replace(fixture._intent(bundle), experiment_id=None)
    provider_inputs = fixture.BinanceUsdmTradifiProviderInputs(
        fixture.build_manifest(), fixture._EQUITY
    )
    operations = BinanceUsdmTradifiBacktestOperations(
        intent_templates={"empty": template},
        provider_inputs=provider_inputs,
        artifact_reader=store,
        artifact_publisher=store,
        market_reader=reader,
        publication_root=tmp_path / "publication",
    )

    prepared = operations.prepare({"intent_key": "empty"}, "operations-smoke")

    assert type(prepared) is PreparedTradifiTrial
    assert prepared.backtest_request_ref["type"] == "backtest_request_ref"
    forged = PreparedTradifiTrial(prepared._execution, operations)
    with pytest.raises(TypeError, match="not registered"):
        operations.run_prepared(forged)
    publication_ref = operations.run_prepared(prepared)
    completed = operations.load_completed(publication_ref)
    assert completed["semantic_run_id"].startswith("run_")
    assert completed["result_grade"] == "development"

    metric_ref = ArtifactRef.from_envelope(
        ArtifactEnvelope.create(
            "backtest_metric_profile",
            1,
            BacktestMetricProfile("simple_period_return.fill_count.v1", 1),
        )
    )
    analysis_ref = operations.derive(publication_ref, _plain(metric_ref))
    analysis = operations.load_analysis(analysis_ref)
    assert analysis["source_publication_ref"] == publication_ref
    assert analysis["trade_count"] > 0
    assert analysis["simple_period_return"] is not None

    with pytest.raises(RuntimeError, match="already run"):
        operations.run_prepared(prepared)
    with pytest.raises(ValueError, match="exact-cover"):
        operations.prepare({"intent_key": "empty", "extra": True}, "other")
    with pytest.raises((TypeError, ValueError)):
        operations.load_completed_v3(publication_ref)
    with pytest.raises((TypeError, ValueError)):
        operations.load_analysis_v2(analysis_ref)
