from __future__ import annotations

from typing import Protocol

from crypto_quant_domain import ArtifactRef, ArtifactReadResult


class ArtifactEnvelopeReader(Protocol):
    def read(self, *, ref: ArtifactRef) -> ArtifactReadResult: ...
