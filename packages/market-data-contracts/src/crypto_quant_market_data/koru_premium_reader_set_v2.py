"""Shared sealed KORU premium-reader V2 bindings, independent of Builder and Runtime."""

from __future__ import annotations

from dataclasses import dataclass, field

from crypto_quant_domain import ArtifactEnvelope, ArtifactRef, canonical_sha256

from .bundles import MarketBundleReader, MarketBundleRef
from .local_market_bundle_reader import LocalMarketBundleReader

_PREMIUM_IDS = tuple(f"KORU-PRM-{number:02d}" for number in range(1, 5))


def _text(name: str, value: object) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(name)
    return value


def _digest(name: str, value: object) -> str:
    if (
        type(value) is not str
        or len(value) != 71
        or not value.startswith("sha256:")
        or any(character not in "0123456789abcdef" for character in value[7:])
    ):
        raise ValueError(name)
    return value


@dataclass(frozen=True, slots=True)
class KoruPremiumReaderBindingV2:
    """One sealed premium recipe identity and its repository-open OverlayV4 reader."""

    premium_id: str
    premium_key: str
    strategy_definition_envelope: ArtifactEnvelope
    strategy_parameter_set_envelope: ArtifactEnvelope
    strategy_ref: ArtifactRef
    parameter_ref: ArtifactRef
    recipe_digest: str
    compiler_result_ref: ArtifactRef
    compiler_result_digest: str
    scope_ref: ArtifactRef
    scope_digest: str
    source_projection_authority_ref: ArtifactRef
    source_projection_authority_content_hash: str
    source_fragment_digest: str
    target_stream_key: str
    target_stream_digest: str
    overlay_bundle_ref: MarketBundleRef
    overlay_bundle_digest: str
    economics_bundle_ref: MarketBundleRef
    economics_bundle_digest: str
    economics_authority_digest: str
    reader: MarketBundleReader = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        for name in ("premium_id", "premium_key", "target_stream_key"):
            _text(name, getattr(self, name))
        for name in (
            "recipe_digest", "compiler_result_digest", "scope_digest",
            "source_projection_authority_content_hash", "source_fragment_digest",
            "target_stream_digest", "overlay_bundle_digest", "economics_bundle_digest",
            "economics_authority_digest",
        ):
            _digest(name, getattr(self, name))
        if (
            type(self.strategy_definition_envelope) is not ArtifactEnvelope
            or self.strategy_definition_envelope.artifact_type != "strategy_definition"
            or self.strategy_definition_envelope.schema_version != 1
            or type(self.strategy_parameter_set_envelope) is not ArtifactEnvelope
            or self.strategy_parameter_set_envelope.artifact_type != "strategy_parameter_set"
            or self.strategy_parameter_set_envelope.schema_version != 1
            or type(self.strategy_ref) is not ArtifactRef
            or self.strategy_ref != ArtifactRef.from_envelope(self.strategy_definition_envelope)
            or self.strategy_ref.artifact_type != "strategy_definition"
            or self.strategy_ref.schema_version != 1
            or type(self.parameter_ref) is not ArtifactRef
            or self.parameter_ref != ArtifactRef.from_envelope(self.strategy_parameter_set_envelope)
            or self.parameter_ref.artifact_type != "strategy_parameter_set"
            or self.parameter_ref.schema_version != 1
            or type(self.compiler_result_ref) is not ArtifactRef
            or self.compiler_result_ref.artifact_type != "koru_directional_target_compile_result"
            or self.compiler_result_ref.schema_version != 2
            or self.compiler_result_ref.content_hash != self.compiler_result_digest
            or type(self.scope_ref) is not ArtifactRef
            or self.scope_ref.artifact_type != "koru_directional_discovery_scope"
            or self.scope_ref.schema_version != 1
            or self.scope_ref.content_hash != self.scope_digest
            or type(self.source_projection_authority_ref) is not ArtifactRef
            or self.source_projection_authority_ref.artifact_type != "binance_usdm_koru_tradifi_source_projection_authority_v3"
            or self.source_projection_authority_ref.schema_version != 3
            or self.source_projection_authority_ref.content_hash != self.source_projection_authority_content_hash
            or type(self.overlay_bundle_ref) is not MarketBundleRef
            or type(self.economics_bundle_ref) is not MarketBundleRef
            or self.overlay_bundle_digest != self.overlay_bundle_ref.manifest_hash
            or self.economics_bundle_digest != self.economics_bundle_ref.manifest_hash
        ):
            raise ValueError("premium_reader_binding")
        try:
            reader = LocalMarketBundleReader.validate_repository_open_reader_v1(self.reader)
            if (
                reader.bundle_ref != self.overlay_bundle_ref
                or reader.bundle_ref.manifest_hash != self.overlay_bundle_digest
                or MarketBundleRef.from_manifest(reader.manifest) != self.overlay_bundle_ref
            ):
                raise ValueError("reader binding")
        except (AttributeError, TypeError, ValueError):
            raise ValueError("premium_reader_binding") from None

    def to_canonical_dict(self) -> dict[str, object]:
        """Identity deliberately omits the operational reader object."""
        return {
            "type": "koru_premium_reader_binding_v2",
            "premium_id": self.premium_id,
            "premium_key": self.premium_key,
            "strategy_definition_envelope": self.strategy_definition_envelope,
            "strategy_parameter_set_envelope": self.strategy_parameter_set_envelope,
            "strategy_ref": self.strategy_ref,
            "parameter_ref": self.parameter_ref,
            "recipe_digest": self.recipe_digest,
            "compiler_result_ref": self.compiler_result_ref,
            "compiler_result_digest": self.compiler_result_digest,
            "scope_ref": self.scope_ref,
            "scope_digest": self.scope_digest,
            "source_projection_authority_ref": self.source_projection_authority_ref,
            "source_projection_authority_content_hash": self.source_projection_authority_content_hash,
            "source_fragment_digest": self.source_fragment_digest,
            "target_stream_key": self.target_stream_key,
            "target_stream_digest": self.target_stream_digest,
            "overlay_bundle_ref": self.overlay_bundle_ref,
            "overlay_bundle_digest": self.overlay_bundle_digest,
            "economics_bundle_ref": self.economics_bundle_ref,
            "economics_bundle_digest": self.economics_bundle_digest,
            "economics_authority_digest": self.economics_authority_digest,
        }


@dataclass(frozen=True, slots=True)
class KoruPremiumReaderSetV2:
    """The exact ordered PRM-01..04 V2 reader declaration and accessors."""

    bindings: tuple[KoruPremiumReaderBindingV2, ...]
    reader_set_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.bindings) is not tuple or any(type(row) is not KoruPremiumReaderBindingV2 for row in self.bindings):
            raise TypeError("bindings")
        if (
            tuple(row.premium_id for row in self.bindings) != _PREMIUM_IDS
            or tuple(row.premium_key for row in self.bindings) != _PREMIUM_IDS
            or tuple(row.target_stream_key for row in self.bindings) != _PREMIUM_IDS
        ):
            raise ValueError("canonical premium rows")
        if len({row.strategy_ref for row in self.bindings}) != 4 or len({row.parameter_ref for row in self.bindings}) != 4:
            raise ValueError("premium envelope refs")
        shared = (
            "compiler_result_ref", "compiler_result_digest", "scope_ref", "scope_digest",
            "source_projection_authority_ref", "source_projection_authority_content_hash",
            "source_fragment_digest", "economics_bundle_ref", "economics_bundle_digest",
            "economics_authority_digest",
        )
        if any(len({getattr(row, name) for row in self.bindings}) != 1 for name in shared):
            raise ValueError("shared premium authority")
        object.__setattr__(self, "reader_set_digest", canonical_sha256(self.to_canonical_dict()))

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "koru_premium_reader_set_v2", "bindings": self.bindings}

    def reader_for(self, premium_id: str) -> LocalMarketBundleReader:
        """Return only the repository-open reader bound to the sealed row."""
        _text("premium_id", premium_id)
        try:
            binding = next(row for row in self.bindings if row.premium_id == premium_id)
        except StopIteration as error:
            raise KeyError("unknown premium_id") from error
        reader = LocalMarketBundleReader.validate_repository_open_reader_v1(binding.reader)
        if (
            reader.bundle_ref != binding.overlay_bundle_ref
            or reader.bundle_ref.manifest_hash != binding.overlay_bundle_digest
            or MarketBundleRef.from_manifest(reader.manifest) != binding.overlay_bundle_ref
        ):
            raise ValueError("premium reader binding")
        return reader


__all__ = ["KoruPremiumReaderBindingV2", "KoruPremiumReaderSetV2"]
