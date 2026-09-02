from __future__ import annotations

import json

import pytest
from crypto_quant_backtest.execution_inputs import _read_journal_entry
from crypto_quant_domain import AccountingJournalEntry, canonical_bytes
from crypto_quant_trading import (
    LinearDerivativeJournalEntry,
    LinearFundingJournalEntryV2,
)

from tests.runtime.providers import (
    test_binance_usdm_tradifi_directional_preparation_v3 as fixture,
)


@pytest.fixture(scope="module")
def journal_payloads(tmp_path_factory: pytest.TempPathFactory) -> dict[str, dict[str, object]]:
    tmp_path = tmp_path_factory.mktemp("journal-entry-parser")
    _, _, artifacts, prepared = fixture._prepare(
        tmp_path, source=fixture._sealed_nonzero_source()
    )
    prepared.runtime.run(prepared.execution_request)
    engine = next(
        json.loads(value.source_bytes)["payload"]
        for value in artifacts.values.values()
        if json.loads(value.source_bytes).get("artifact_type")
        == "engine_execution_result"
    )
    entries = engine["final_journal"]["entries"]
    derivative = next(
        entry for entry in entries if entry["type"] == "linear_derivative_journal_entry"
    )
    funding = next(
        entry for entry in entries if entry["type"] == "linear_funding_journal_entry"
    )
    return {
        "base": derivative["journal_entry"],
        "derivative": derivative,
        "funding": funding,
    }


@pytest.mark.parametrize(
    ("entry_kind", "entry_type"),
    (
        ("base", AccountingJournalEntry),
        ("derivative", LinearDerivativeJournalEntry),
        ("funding", LinearFundingJournalEntryV2),
    ),
)
def test_journal_parser_accepts_only_existing_canonical_entry_variants(
    journal_payloads: dict[str, dict[str, object]],
    entry_kind: str,
    entry_type: type[AccountingJournalEntry],
) -> None:
    payload = journal_payloads[entry_kind]
    entry = _read_journal_entry(payload)

    assert type(entry) is entry_type
    assert canonical_bytes(entry) == canonical_bytes(payload)


def test_journal_parser_rejects_unknown_and_malformed_entry_variants(
    journal_payloads: dict[str, dict[str, object]],
) -> None:
    payloads = journal_payloads
    unknown = dict(payloads["base"])
    unknown["type"] = "unrecognized_journal_entry"
    malformed_base = dict(payloads["base"])
    malformed_base["unexpected"] = True
    malformed = dict(payloads["funding"])
    malformed["schema_version"] = 1

    with pytest.raises(ValueError, match="unsupported accounting journal entry type"):
        _read_journal_entry(unknown)
    with pytest.raises(ValueError, match="must contain exactly"):
        _read_journal_entry(malformed_base)
    with pytest.raises(ValueError, match="schema_version 2"):
        _read_journal_entry(malformed)
