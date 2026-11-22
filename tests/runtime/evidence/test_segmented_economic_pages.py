"""Bounded page transport for the opt-in economic evidence reader."""

from contextlib import contextmanager
from dataclasses import replace
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import MappingProxyType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from crypto_quant_backtest._economic_result_encoding import (
    decode_frozen_economic_paged_fact, encode_economic_paged_fact,
)
from crypto_quant_backtest._referenced_evidence import _ReferencedResultObjects, _ReferencedRunLock, _native_bytes
from crypto_quant_backtest.cn_a_share_portfolio_economic_case_v1 import _BoundEconomicPortfolioSourcesV1
from crypto_quant_backtest.cn_a_share_portfolio_economic_engine_v1 import _CnASharePortfolioEconomicEngineV1
from crypto_quant_backtest.cn_a_share_portfolio_economic_opening_v1 import _retained_opening_term_v1
from crypto_quant_backtest.cn_a_share_portfolio_economic_result_v1 import _artifact_and_bytes

from crypto_quant_backtest._segmented_economic_pages import (
    EconomicPageSeries,
    iter_economic_pages,
    publish_economic_page,
    publish_economic_series,
)
from crypto_quant_domain import (
    ArtifactEnvelope, ArtifactIntegrityError, ArtifactNotFoundError, OrderSide,
    SimulationInstant, SourceSequence, TimelinePhase, UtcInstant, canonical_bytes,
    canonical_sha256,
)
from crypto_quant_backtest.financial_dispatch import FinancialDispatchArtifact
from crypto_quant_foundation import LocalFoundation


class SegmentedEconomicPagesTest(unittest.TestCase):
    def test_native_paged_writer_preserves_financial_envelope_and_trace_commitments(self):
        at = SimulationInstant(UtcInstant(123), TimelinePhase(49, "test_opening"), SourceSequence(2))
        envelope_fields = dict(role="economic_opening_batch", source_event_id="opening.1", occurred_at=at,
            component_key="test.finance", component_digest="sha256:" + "1" * 64, input_hash="sha256:" + "2" * 64)
        payload = {"text": "分红", "at": at, "coordinates": (True, 1, None, {"z": "x", "a": "y"})}
        envelope = ArtifactEnvelope.create("cn_a_share_portfolio_economic_opening_batch", 3, payload)
        original = FinancialDispatchArtifact(**envelope_fields, component_version=1,
            result_hash=canonical_sha256(envelope), payload=envelope)

        row, digest = encode_economic_paged_fact(**envelope_fields, schema_version=3, payload=payload)
        self.assertEqual(canonical_bytes(row), canonical_bytes(original))
        self.assertEqual(digest, original.artifact_hash)
        page = ArtifactEnvelope.create("economic_test_page", 1, {"rows": (row,)})
        decoded, source = _artifact_and_bytes(page.payload["rows"][0], paged_row=True)
        self.assertEqual(decoded, original)
        self.assertEqual(source, canonical_bytes(original))
        strict_fact, strict_source = decode_frozen_economic_paged_fact(page.payload["rows"][0])
        self.assertEqual(strict_source, source)
        self.assertEqual(canonical_bytes(strict_fact.payload), canonical_bytes(envelope))
        self.assertEqual(strict_fact.occurred_at, original.occurred_at)

        frozen = page.payload["rows"][0]
        malformed = (
            {**frozen, "schema_version": True},
            {**frozen, "component_version": False},
            {**frozen, "occurred_at": {**frozen["occurred_at"], "unknown": True}},
            {**frozen, "source_event_id": " padded ", "component_digest": "bad"},
            {**frozen, "result_hash": "sha256:" + "0" * 64},
            {**frozen, "payload": {**frozen["payload"], "content_hash": "sha256:" + "0" * 64}},
        )
        for item in malformed:
            with self.subTest(invalid_row=tuple(item)):
                read_row = ArtifactEnvelope.create("economic_test_page", 1, {"rows": (item,)}).payload["rows"][0]
                with self.assertRaises(ValueError) as original_error:
                    _artifact_and_bytes(read_row, paged_row=True)
                with self.assertRaises(type(original_error.exception)) as strict_error:
                    decode_frozen_economic_paged_fact(read_row)
                self.assertEqual(str(strict_error.exception), str(original_error.exception))

        def legacy_encode(fields, version, body):
            kind = "cn_a_share_portfolio_" + fields["role"]
            payload_envelope = ArtifactEnvelope.create(kind, version, body)
            return FinancialDispatchArtifact(**fields, component_version=1,
                result_hash=canonical_sha256(payload_envelope), payload=payload_envelope)

        cases = (
            ({"component_digest": "bad"}, 0, {"float": 0.5}),
            ({"component_digest": "bad"}, 0, payload),
            ({"role": "bad role"}, 3, payload),
            ({"occurred_at": "bad clock", "component_digest": "bad"}, 3, payload),
            ({"component_digest": "bad", "input_hash": "bad"}, 3, payload),
            ({}, 3, {"overflow": 10**5000}),
        )
        for changes, version, body in cases:
            with self.subTest(changes=changes, version=version, keys=tuple(body)):
                fields = {**envelope_fields, **changes}
                with self.assertRaises(ValueError if "occurred_at" not in changes else TypeError) as legacy_error:
                    legacy_encode(fields, version, body)
                with self.assertRaises(type(legacy_error.exception)) as scoped_error:
                    encode_economic_paged_fact(**fields, schema_version=version, payload=body)
                self.assertEqual(str(scoped_error.exception), str(legacy_error.exception))

    def test_exact_native_page_publisher_matches_regular_envelope_bytes(self):
        series = EconomicPageSeries("run_" + "7" * 64, "sha256:" + "8" * 64, "financial_fact")
        with TemporaryDirectory() as directory:
            root = Path(directory)
            storage = LocalFoundation(root / "candidate")
            reference = LocalFoundation(root / "reference")
            with _ReferencedRunLock(root=root / "native", semantic_run_id=series.semantic_run_id) as lock:
                publisher = _ReferencedResultObjects(lock=lock, reader=storage, publisher=storage)
                for offset, count in ((0, 1), (4096*64-64, 64)):
                    rows = tuple({"symbol": "上海", "nested": ({"lots": [i, True, None]},)} for i in range(count))
                    expected = publish_economic_page(reference, series, offset, rows)
                    actual = publish_economic_page(publisher, series, offset, rows)
                    self.assertEqual(actual, expected)
                    self.assertEqual(publish_economic_page(publisher, series, offset, rows), expected)
                    self.assertEqual(publisher.read(ref=actual.artifact_ref).source_bytes,
                                     reference.read(ref=expected.artifact_ref).source_bytes)

    def test_frozen_financial_fact_keeps_canonical_bytes_and_failure_precedence(self):
        payload = ArtifactEnvelope.create("economic_financial_fact", 1, {"coordinates": (1, 2)})
        at = SimulationInstant(UtcInstant(123), TimelinePhase(49, "test_opening"), SourceSequence(2))
        row = {
            "type": "financial_dispatch_artifact", "schema_version": 1, "role": "test_opening",
            "source_event_id": "opening.1", "occurred_at": at, "component_key": "test.finance",
            "component_version": 1, "component_digest": "sha256:" + "1" * 64,
            "input_hash": "sha256:" + "2" * 64, "result_hash": canonical_sha256(payload), "payload": payload,
        }

        def frozen(value):
            return ArtifactEnvelope.create("test_paged_rows", 1, {"row": value}).payload["row"]

        row = json.loads(canonical_bytes(row))
        canonical = frozen(row)
        self.assertIs(type(canonical), MappingProxyType)
        self.assertEqual(_artifact_and_bytes(canonical, paged_row=True), _artifact_and_bytes(canonical))
        self.assertEqual(_artifact_and_bytes(row, paged_row=True), _artifact_and_bytes(row))

        bad_clock = dict(row["occurred_at"], phase=dict(row["occurred_at"]["phase"], extra=1))
        altered = frozen(dict(row, occurred_at=bad_clock))
        with self.assertRaisesRegex(ArtifactIntegrityError, "financial artifact canonical reconstruction"):
            _artifact_and_bytes(altered, paged_row=True)

        bad_payload = dict(row["payload"], content_hash="sha256:" + "0" * 64)
        altered = frozen(dict(row, occurred_at=bad_clock, payload=bad_payload))
        with self.assertRaisesRegex(ValueError, "content hash does not match artifact body"):
            _artifact_and_bytes(altered, paged_row=True)

    def test_fixed_inputs_require_exact_case_and_reader_identity(self):
        case = Mock(name="case")
        reader = Mock(name="reader")
        bound = _BoundEconomicPortfolioSourcesV1(
            case=case, reader=reader, inputs=Mock(), openings=(),
            journal_entry_ids=(), opening_batches={}, terms_by_side={},
        )
        engine = _CnASharePortfolioEconomicEngineV1(artifact_reader=reader, fixed_sources=bound)
        self.assertIs(engine._referenced_fixed_sources(case, reader), bound)
        with self.assertRaisesRegex(ArtifactIntegrityError, "another Case or reader"):
            engine._referenced_fixed_sources(Mock(name="foreign_case"), reader)
        with self.assertRaisesRegex(ArtifactIntegrityError, "another Case or reader"):
            engine._referenced_fixed_sources(case, Mock(name="foreign_reader"))
        fresh = _CnASharePortfolioEconomicEngineV1(artifact_reader=reader)
        self.assertIsNone(fresh._referenced_fixed_sources(case, reader))

    def test_retained_opening_term_matches_exact_sorted_coordinate(self):
        rows = (
            SimpleNamespace(opening_at=1, instrument_id="a", side=OrderSide.BUY),
            SimpleNamespace(opening_at=1, instrument_id="a", side=OrderSide.SELL),
            SimpleNamespace(opening_at=1, instrument_id="b", side=OrderSide.BUY),
            SimpleNamespace(opening_at=3, instrument_id="a", side=OrderSide.BUY),
        )
        for row in rows:
            self.assertIs(_retained_opening_term_v1(rows, row.opening_at, row.instrument_id, row.side), row)
        for when, instrument, side in (
            (0, "a", OrderSide.BUY), (1, "b", OrderSide.SELL),
            (2, "a", OrderSide.BUY), (4, "a", OrderSide.BUY),
        ):
            self.assertIsNone(_retained_opening_term_v1(rows, when, instrument, side))

    def test_bound_cas_pages_have_exact_cover_and_order(self):
        with TemporaryDirectory() as work:
            store = LocalFoundation(Path(work) / "foundation")
            series = EconomicPageSeries("run_" + "1" * 64, "sha256:" + "2" * 64, "financial_fact")
            a = publish_economic_page(store, series, 0, ({"row": "first"}, {"row": "second"}))
            b = publish_economic_page(store, series, 2, ({"row": "third"},))
            pages = iter_economic_pages(store, series, (a, b), expected_count=3)
            self.assertEqual(canonical_bytes(next(pages)), b'[{"row":"first"},{"row":"second"}]')
            self.assertEqual(canonical_bytes(next(pages)), b'[{"row":"third"}]')
            self.assertIsNone(next(pages, None))
            with self.assertRaisesRegex(ArtifactIntegrityError, "offset"):
                tuple(iter_economic_pages(store, series, (b, a), expected_count=3))
            with self.assertRaisesRegex(ArtifactIntegrityError, "cover"):
                tuple(iter_economic_pages(store, series, (a,), expected_count=3))
            with self.assertRaisesRegex(ArtifactIntegrityError, "duplicate"):
                tuple(iter_economic_pages(store, series, (a, a), expected_count=4))

    def test_wrong_owner_source_or_missing_child_never_yields_page(self):
        with TemporaryDirectory() as work:
            store = LocalFoundation(Path(work) / "foundation")
            series = EconomicPageSeries("run_" + "1" * 64, "sha256:" + "2" * 64, "financial_fact")
            target = publish_economic_page(store, series, 0, ({"row": "original"},))
            altered_owner = replace(series, case_hash="sha256:" + "3" * 64)
            with self.assertRaisesRegex(ArtifactIntegrityError, "owner"):
                next(iter_economic_pages(store, altered_owner, (target,), expected_count=1))
            forged = replace(target, source_hash="sha256:" + "0" * 64)
            with self.assertRaisesRegex(ArtifactIntegrityError, "coordinates"):
                next(iter_economic_pages(store, series, (forged,), expected_count=1))
            missing = LocalFoundation(Path(work) / "other")
            with self.assertRaises(ArtifactNotFoundError):
                next(iter_economic_pages(missing, series, (target,), expected_count=1))

    def test_series_limits_rows_and_bytes_before_publishing(self):
        with TemporaryDirectory() as work:
            store = LocalFoundation(Path(work) / "foundation")
            series = EconomicPageSeries("run_" + "1" * 64, "sha256:" + "2" * 64, "admission")
            entries = publish_economic_series(store, series, ({"row": i} for i in range(65)))
            self.assertEqual(tuple(e.row_count for e in entries), (64, 1))
            self.assertEqual([r["row"] for p in iter_economic_pages(store, series, entries, expected_count=65) for r in p], list(range(65)))

        class NoPut:
            def put(self, **kwargs):
                raise AssertionError("oversized row reached CAS")

        with self.assertRaisesRegex(ValueError, "row outside cap"):
            publish_economic_series(NoPut(), series, ({"row": "x" * (8 * 1024 * 1024)},))


    def test_native_read_bounds_buffer_with_open_file_size(self):
        payload = b'original evidence'
        open_descriptor = os.fdopen

        with TemporaryDirectory() as work:
            path = Path(work) / "artifact.json"
            path.write_bytes(payload)
            path.chmod(0o444)

            for observed_bytes in (payload, payload[:-1], payload + b"x"):
                with self.subTest(observed_bytes=observed_bytes):
                    read = Mock(return_value=observed_bytes)

                    @contextmanager
                    def open_for_test(fd, mode):
                        with open_descriptor(fd, mode) as file:
                            yield Mock(wraps=file, read=read)

                    with patch("os.fdopen", open_for_test):
                        if observed_bytes == payload:
                            self.assertEqual(_native_bytes(path, 512 * 1024 * 1024), payload)
                        else:
                            with self.assertRaisesRegex(ArtifactIntegrityError, "size changed"):
                                _native_bytes(path, 512 * 1024 * 1024)
                        read.assert_called_once_with(len(payload) + 1)

                        read.reset_mock()
                        with self.assertRaisesRegex(ArtifactIntegrityError, "invalid native"):
                            _native_bytes(path, len(payload) - 1)
                        read.assert_not_called()
