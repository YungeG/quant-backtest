"""Exactly two source windows for the existing paired-week DEVELOPMENT slice.

This is a read-only synthetic CAS contract, never formal source qualification.
Each window reuses the V0 reader; unchanged bands may legitimately span both
windows, but the first window manifest may not stand in for a second snapshot.
"""
from __future__ import annotations

from crypto_quant_domain import ArtifactRef, UtcInstant

from .artifact_envelope_reader import ArtifactEnvelopeReader
from .cn_a_share_portfolio_preparation_inputs_v1 import CnASharePortfolioPreparationInputsV1
from .cn_a_share_portfolio_source_bundle_draft_v0 import (
    CnASharePortfolioSourceReadbackDraftV0, _list, _read,
    read_cn_a_share_portfolio_source_bundle_draft_v0,
)
from .target_repository import _artifact_ref, _exact, _instant, _mapping

_PAIR = "backtest_cn_a_share_portfolio_source_pair_draft"
_FIELDS = frozenset({"type", "schema_version", "input_hash", "windows", "synthetic_only", "formal_qualified"})
_WINDOW_FIELDS = frozenset({"decision_at", "execution_at", "bundle_ref"})


def read_cn_a_share_portfolio_source_pair_draft_v0(
    ref: ArtifactRef, *, inputs: CnASharePortfolioPreparationInputsV1,
    reader: ArtifactEnvelopeReader,
) -> tuple[CnASharePortfolioSourceReadbackDraftV0, CnASharePortfolioSourceReadbackDraftV0]:
    """Both separately retained snapshots must cover non-overlapping causal windows."""
    if type(inputs) is not CnASharePortfolioPreparationInputsV1 or not callable(getattr(reader, "read", None)):
        raise TypeError("draft source pair requires portfolio inputs and artifact reader")
    data = _read(ref, reader, _PAIR)
    _exact("draft source pair", data, _FIELDS)
    if (data["type"] != "cn_a_share_portfolio_source_pair_draft"
            or type(data["schema_version"]) is not int or data["schema_version"] != 1
            or data["input_hash"] != inputs.input_hash or data["synthetic_only"] is not True
            or data["formal_qualified"] is not False):
        raise ValueError("draft source pair scope/grade mismatch")
    rows = _list(data["windows"], "source pair windows")
    if len(rows) != 2:
        raise ValueError("draft source pair requires exactly two windows")
    declared: list[tuple[UtcInstant, UtcInstant, ArtifactRef]] = []
    for row in rows:
        window = _mapping("source pair window", row)
        _exact("source pair window", window, _WINDOW_FIELDS)
        declared.append((_instant(window["decision_at"]), _instant(window["execution_at"]),
                         _artifact_ref(window["bundle_ref"])))
    first, second = declared
    if (first[2] == second[2] or not first[0] < first[1] < second[0] < second[1]):
        raise ValueError("draft source pair needs distinct ordered, disjoint window snapshots")
    verified = []
    for decision, execution, bundle_ref in declared:
        source = read_cn_a_share_portfolio_source_bundle_draft_v0(bundle_ref, inputs=inputs, reader=reader)
        if (source.decision_at, source.execution_at) != (decision, execution):
            raise ValueError("draft source pair window does not bind retained snapshot clocks")
        verified.append(source)
    return verified[0], verified[1]
