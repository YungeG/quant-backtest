from __future__ import annotations

from typing import Protocol

from crypto_quant_domain import ArtifactEnvelope, ArtifactRef


class ArtifactEnvelopePublisher(Protocol):
    def put(self, *, envelope: ArtifactEnvelope) -> ArtifactRef: ...
