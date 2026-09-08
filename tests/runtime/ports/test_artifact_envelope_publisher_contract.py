from __future__ import annotations

from inspect import Parameter, Signature, _empty, signature
from typing import get_type_hints

import crypto_quant_backtest
from crypto_quant_backtest import ArtifactEnvelopePublisher
from crypto_quant_domain import ArtifactEnvelope, ArtifactRef


def test_artifact_envelope_publisher_is_a_root_exported_structural_protocol() -> None:
    assert ArtifactEnvelopePublisher is crypto_quant_backtest.ArtifactEnvelopePublisher
    assert "ArtifactEnvelopePublisher" in crypto_quant_backtest.__all__
    assert len(set(crypto_quant_backtest.__all__)) == len(crypto_quant_backtest.__all__)
    assert getattr(ArtifactEnvelopePublisher, "_is_protocol", False)
    assert not getattr(ArtifactEnvelopePublisher, "_is_runtime_protocol", False)

    public_members = {
        name
        for name in vars(ArtifactEnvelopePublisher).keys()
        if not name.startswith("_")
    }
    assert public_members == {"put"}


def test_artifact_envelope_publisher_signature_is_exact() -> None:
    put_signature: Signature = signature(ArtifactEnvelopePublisher.put)
    params = tuple(put_signature.parameters.values())

    assert len(params) == 2
    assert tuple(param.name for param in params) == ("self", "envelope")
    self_param, envelope_param = params

    assert self_param.kind == Parameter.POSITIONAL_OR_KEYWORD
    assert self_param.default is _empty
    assert self_param.annotation is _empty

    assert envelope_param.kind == Parameter.KEYWORD_ONLY
    assert envelope_param.default is _empty
    assert envelope_param.annotation == "ArtifactEnvelope"

    hints = get_type_hints(ArtifactEnvelopePublisher.put)
    assert hints.get("envelope") is ArtifactEnvelope
    assert hints.get("return") is ArtifactRef

    kinds = {param.kind for param in params}
    assert Parameter.VAR_POSITIONAL not in kinds
    assert Parameter.VAR_KEYWORD not in kinds
