from __future__ import annotations

from inspect import Parameter, Signature, _empty, signature
from typing import get_type_hints

import crypto_quant_backtest
from crypto_quant_backtest import ArtifactEnvelopeReader
from crypto_quant_domain import ArtifactReadResult, ArtifactRef


def test_artifact_envelope_reader_is_a_root_exported_structural_protocol() -> None:
    assert ArtifactEnvelopeReader is crypto_quant_backtest.ArtifactEnvelopeReader
    assert "ArtifactEnvelopeReader" in crypto_quant_backtest.__all__
    assert len(set(crypto_quant_backtest.__all__)) == len(crypto_quant_backtest.__all__)
    assert getattr(ArtifactEnvelopeReader, "_is_protocol", False)
    assert not getattr(ArtifactEnvelopeReader, "_is_runtime_protocol", False)

    public_members = {
        name
        for name in vars(ArtifactEnvelopeReader).keys()
        if not name.startswith("_")
    }
    assert public_members == {"read"}


def test_artifact_envelope_reader_signature_is_exact() -> None:
    read_signature: Signature = signature(ArtifactEnvelopeReader.read)
    params = tuple(read_signature.parameters.values())

    assert len(params) == 2
    assert tuple(param.name for param in params) == ("self", "ref")
    self_param, ref_param = params

    assert self_param.kind == Parameter.POSITIONAL_OR_KEYWORD
    assert self_param.default is _empty
    assert self_param.annotation is _empty

    assert ref_param.kind == Parameter.KEYWORD_ONLY
    assert ref_param.default is _empty
    assert ref_param.annotation == "ArtifactRef"

    hints = get_type_hints(ArtifactEnvelopeReader.read)
    assert hints.get("ref") is ArtifactRef
    assert hints.get("return") is ArtifactReadResult

    kinds = {param.kind for param in params}
    assert Parameter.VAR_POSITIONAL not in kinds
    assert Parameter.VAR_KEYWORD not in kinds
