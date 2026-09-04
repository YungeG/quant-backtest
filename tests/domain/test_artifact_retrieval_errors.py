from crypto_quant_domain import (
    ArtifactNotFoundError,
    ArtifactRetentionUnavailableError,
)


def test_artifact_retrieval_errors_are_public_domain_errors() -> None:
    assert issubclass(ArtifactNotFoundError, ValueError)
    assert issubclass(ArtifactRetentionUnavailableError, ValueError)
