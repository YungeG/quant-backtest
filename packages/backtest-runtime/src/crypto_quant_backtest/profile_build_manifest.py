"""Profile registration build-manifest fan-in."""

from __future__ import annotations

from dataclasses import replace

from .resolution import (
    ArtifactInstallMode,
    BacktestProfileRegistry,
    BuildArtifactManifest,
    BuildArtifactRef,
    BuildArtifactRole,
    SourceTreeState,
)


def _provider_build_manifest(
    base: BuildArtifactManifest,
    registry: BacktestProfileRegistry,
) -> BuildArtifactManifest:
    registrations = (
        *registry.market_semantics_profiles,
        *registry.simulation_profiles,
        *registry.execution_account_profiles,
    )
    provider_refs = tuple(
        BuildArtifactRef(
            role=BuildArtifactRole.PROFILE_COMPONENT,
            artifact_key=value.profile_key,
            artifact_version=str(value.profile_version),
            install_mode=ArtifactInstallMode.WHEEL,
            source_tree_state=SourceTreeState.CLEAN,
            content_hash=value.profile_digest,
            source_snapshot_hash=None,
        )
        for value in registrations
    )
    expected = {(value.role, value.artifact_key): value for value in provider_refs}
    conflicts = tuple(
        sorted(
            key
            for role, key in expected
            for value in base.artifacts
            if (value.role, value.artifact_key) == (role, key)
            and value != expected[(role, key)]
        )
    )
    if conflicts:
        raise ValueError(
            "caller build manifest conflicts with provider profile keys: "
            + ", ".join(conflicts)
        )
    artifacts = (
        tuple(
            value
            for value in base.artifacts
            if (value.role, value.artifact_key) not in expected
        )
        + provider_refs
    )
    return replace(base, artifacts=artifacts)


__all__ = ["_provider_build_manifest"]
