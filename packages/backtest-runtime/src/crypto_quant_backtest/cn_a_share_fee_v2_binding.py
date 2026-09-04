"""Private Runtime binding for route/product-aware A-share fee v2 identity."""

from __future__ import annotations

import re
from dataclasses import dataclass, fields, replace
from enum import Enum
from typing import cast

from crypto_quant_domain import (
    DomainIdKind,
    Fill,
    IdentityNamespace,
    Order,
    Scale,
    UtcInstant,
    canonical_sha256,
)
from crypto_quant_trading import ProfileComponentRef
from crypto_quant_trading.profiles.cn_a_share import (
    CnAShareCashFeeRuleQueryV2,
    CnAShareCashMarketFeePolicyV2,
    CnAShareCashStampDutyTaxPolicyV2,
    CnAShareDomesticOrdinaryFeeProjectionV2,
    CnAShareExecutionAccessRoute,
    CnAShareFeeExecutionAuthorityV2,
    CnAShareFeeExecutionBindingFailureV2,
    CnAShareFeeExecutionBindingV2,
    CnAShareFeeProductClass,
    CnAShareFeeQueryConstructionFailureV2,
    CnAShareMarketFeeRuleBook,
    CnAShareStampDutyRuleBook,
)
from crypto_quant_trading.profiles.cn_a_share import (
    bind_cn_a_share_fee_execution_v2 as bind_kernel_fee_execution_v2,
)

from .cn_a_share_profile import (
    CnAShareProfileComposer,
    CnAShareResolvedProfile,
)
from .engine import ExecutionCaseIdentityRule, ExecutionCaseSemanticSpec
from .resolution import (
    ArtifactInstallMode,
    BuildArtifactManifest,
    BuildArtifactRef,
    BuildArtifactRole,
    BuildProvenance,
    RuntimeLibraryRef,
    SourceTreeState,
)

_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_SCALE = Scale(2)


def _text(name: str, value: object) -> None:
    if type(value) is not str or not value or value.strip() != value:
        raise ValueError(f"{name} must be canonical non-empty text")


def _hash(name: str, value: object) -> None:
    if type(value) is not str or _HASH.fullmatch(value) is None:
        raise ValueError(f"{name} must be a canonical sha256 identity")


def _enum_member(value: object, enum_type: type[Enum]) -> bool:
    return type(value) is enum_type and any(value is member for member in enum_type)


def _valid_text(value: object) -> bool:
    try:
        _text("text", value)
    except (TypeError, ValueError):
        return False
    return True


def _valid_hash(value: object, *, optional: bool = False) -> bool:
    if optional and value is None:
        return True
    try:
        _hash("hash", value)
    except (TypeError, ValueError):
        return False
    return True


def _reconstructed_component_ref(value: object) -> ProfileComponentRef | None:
    if (
        type(value) is not ProfileComponentRef
        or not _enum_member(value.port_type, type(value.port_type))
        or not _valid_text(value.component_key)
        or type(value.component_version) is not int
        or value.component_version <= 0
        or not _valid_hash(value.component_digest)
    ):
        return None
    try:
        rebuilt = ProfileComponentRef(
            value.port_type,
            value.component_key,
            value.component_version,
            value.component_digest,
        )
    except (TypeError, ValueError, AttributeError):
        return None
    return (
        value
        if rebuilt == value and canonical_sha256(rebuilt) == canonical_sha256(value)
        else None
    )


def _reconstructed_artifact(value: object) -> BuildArtifactRef | None:
    if (
        type(value) is not BuildArtifactRef
        or not _enum_member(value.role, BuildArtifactRole)
        or not _valid_text(value.artifact_key)
        or not _valid_text(value.artifact_version)
        or not _enum_member(value.install_mode, ArtifactInstallMode)
        or not _enum_member(value.source_tree_state, SourceTreeState)
        or not _valid_hash(value.content_hash, optional=True)
        or not _valid_hash(value.source_snapshot_hash, optional=True)
    ):
        return None
    try:
        rebuilt = BuildArtifactRef(
            value.role,
            value.artifact_key,
            value.artifact_version,
            value.install_mode,
            value.source_tree_state,
            value.content_hash,
            value.source_snapshot_hash,
        )
    except (TypeError, ValueError, AttributeError):
        return None
    return (
        value
        if rebuilt == value and canonical_sha256(rebuilt) == canonical_sha256(value)
        else None
    )


def _reconstructed_runtime_library(value: object) -> RuntimeLibraryRef | None:
    if (
        type(value) is not RuntimeLibraryRef
        or not _valid_text(value.library_key)
        or not _valid_text(value.version)
        or not _valid_hash(value.content_hash)
    ):
        return None
    try:
        rebuilt = RuntimeLibraryRef(
            value.library_key, value.version, value.content_hash
        )
    except (TypeError, ValueError, AttributeError):
        return None
    return (
        value
        if rebuilt == value and canonical_sha256(rebuilt) == canonical_sha256(value)
        else None
    )


def _reconstructed_provenance(value: object) -> BuildProvenance | None:
    if (
        type(value) is not BuildProvenance
        or not _valid_text(value.git_commit)
        or not _valid_text(value.hostname)
        or not _valid_text(value.source_root)
        or type(value.built_at) is not UtcInstant
        or type(value.built_at.epoch_nanoseconds) is not int
    ):
        return None
    try:
        rebuilt = BuildProvenance(
            value.git_commit, value.hostname, value.source_root, value.built_at
        )
    except (TypeError, ValueError, AttributeError):
        return None
    return (
        value
        if rebuilt == value and canonical_sha256(rebuilt) == canonical_sha256(value)
        else None
    )


def _reconstructed_authority(
    value: object,
) -> CnAShareFeeExecutionAuthorityV2 | None:
    if type(value) is not CnAShareFeeExecutionAuthorityV2:
        return None
    try:
        rebuilt = CnAShareFeeExecutionAuthorityV2(
            *(getattr(value, field.name) for field in fields(value))
        )
    except (TypeError, ValueError, AttributeError):
        return None
    return (
        value
        if rebuilt == value and rebuilt.authority_hash == value.authority_hash
        else None
    )


def _reconstructed_projection(
    value: object,
) -> CnAShareDomesticOrdinaryFeeProjectionV2 | None:
    if type(value) is not CnAShareDomesticOrdinaryFeeProjectionV2:
        return None
    try:
        rebuilt = CnAShareDomesticOrdinaryFeeProjectionV2(
            *(getattr(value, field.name) for field in fields(value))
        )
    except (TypeError, ValueError, AttributeError):
        return None
    return (
        value
        if rebuilt == value and rebuilt.projection_hash == value.projection_hash
        else None
    )


def _reconstructed_profile(value: object) -> CnAShareResolvedProfile | None:
    if type(value) is not CnAShareResolvedProfile:
        return None
    outcome = CnAShareProfileComposer().compose(value.request)
    rebuilt = outcome.result
    return (
        value
        if type(rebuilt) is CnAShareResolvedProfile
        and rebuilt == value
        and rebuilt.profile_digest == value.profile_digest
        else None
    )


def _reconstructed_build(value: object) -> BuildArtifactManifest | None:
    if (
        type(value) is not BuildArtifactManifest
        or type(value.schema_version) is not int
        or value.schema_version != 1
        or not _valid_text(value.build_key)
        or type(value.artifacts) is not tuple
        or not all(
            _reconstructed_artifact(artifact) is not None
            for artifact in value.artifacts
        )
        or not _valid_hash(value.dependency_lock_hash)
        or type(value.runtime_libraries) is not tuple
        or not all(
            _reconstructed_runtime_library(library) is not None
            for library in value.runtime_libraries
        )
        or not _valid_hash(value.container_image_digest, optional=True)
        or _reconstructed_provenance(value.provenance) is None
    ):
        return None
    try:
        rebuilt = BuildArtifactManifest(
            *(getattr(value, field.name) for field in fields(value))
        )
    except (TypeError, ValueError, AttributeError):
        return None
    return (
        value
        if rebuilt == value and rebuilt.manifest_hash == value.manifest_hash
        else None
    )


def _profile_inputs(profile: CnAShareResolvedProfile) -> dict[str, object]:
    return {
        "type": "cn_a_share_fee_legacy_profile_inputs_v2",
        "schema_version": 1,
        "account_risk_policy": profile.account_risk_policy,
        "market_profile_key": profile.market_registration.profile_key,
        "market_profile_version": profile.market_registration.profile_version,
        "market_component_manifest": profile.market_registration.component_manifest,
        "market_venue_id": profile.market_registration.venue_id,
        "market_required_bundle_capabilities": (
            profile.market_registration.required_bundle_capabilities
        ),
        "simulation_profile_key": profile.simulation_registration.profile_key,
        "simulation_profile_version": profile.simulation_registration.profile_version,
        "simulation_engine_kind": profile.simulation_registration.engine_kind,
        "simulation_strategy_families": (
            profile.simulation_registration.supported_strategy_families
        ),
        "simulation_required_bundle_capabilities": (
            profile.simulation_registration.required_bundle_capabilities
        ),
        "execution_account_profile_key": (
            profile.execution_account_registration.profile_key
        ),
        "execution_account_profile_version": (
            profile.execution_account_registration.profile_version
        ),
        "execution_account_id": profile.execution_account_registration.account_id,
        "execution_account_venue_id": (profile.execution_account_registration.venue_id),
        "execution_account_type": profile.execution_account_registration.account_type,
        "execution_account_margin_mode": (
            profile.execution_account_registration.margin_mode
        ),
        "supported_reporting_currencies": (
            profile.execution_account_registration.supported_reporting_currencies
        ),
    }


def _selected_source_books(
    profile: CnAShareResolvedProfile,
    authority: CnAShareFeeExecutionAuthorityV2,
) -> tuple[CnAShareMarketFeeRuleBook, CnAShareStampDutyRuleBook]:
    request = profile.request
    venue = authority.scope.venue_id
    return (
        CnAShareMarketFeeRuleBook(
            request.market_fee_rule_book.rule_book_key,
            request.market_fee_rule_book.rule_book_version,
            tuple(
                band
                for band in request.market_fee_rule_book.bands
                if band.venue_id == venue
            ),
        ),
        CnAShareStampDutyRuleBook(
            request.stamp_duty_rule_book.rule_book_key,
            request.stamp_duty_rule_book.rule_book_version,
            tuple(
                band
                for band in request.stamp_duty_rule_book.bands
                if band.venue_id == venue
            ),
        ),
    )


@dataclass(frozen=True, slots=True)
class CnAShareFeeProfileBindingV2:
    schema_version: int
    resolved_profile: CnAShareResolvedProfile
    projection: CnAShareDomesticOrdinaryFeeProjectionV2
    legacy_profile_inputs_hash: str
    market_profile_key: str
    market_profile_version: int
    simulation_profile_key: str
    simulation_profile_version: int
    execution_account_profile_key: str
    execution_account_profile_version: int
    account_id: str
    venue_id: str
    instrument_id: str
    access_route: CnAShareExecutionAccessRoute
    fee_product_class: CnAShareFeeProductClass
    authority: CnAShareFeeExecutionAuthorityV2
    authority_hash: str
    scope_hash: str
    selection_hash: str
    market_fee_rule_book_hash: str
    stamp_duty_rule_book_hash: str
    market_fee_component_ref: ProfileComponentRef
    stamp_duty_component_ref: ProfileComponentRef
    compatibility_projection_hash: str

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("profile binding schema_version must be 1")
        profile = _reconstructed_profile(self.resolved_profile)
        projection = _reconstructed_projection(self.projection)
        if profile is None or projection is None:
            raise TypeError("profile binding sources must reconstruct exactly")
        for name in (
            "market_profile_key",
            "simulation_profile_key",
            "execution_account_profile_key",
            "account_id",
            "venue_id",
            "instrument_id",
        ):
            _text(name, getattr(self, name))
        for name in (
            "market_profile_version",
            "simulation_profile_version",
            "execution_account_profile_version",
        ):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be positive")
        for name in (
            "legacy_profile_inputs_hash",
            "authority_hash",
            "scope_hash",
            "selection_hash",
            "market_fee_rule_book_hash",
            "stamp_duty_rule_book_hash",
            "compatibility_projection_hash",
        ):
            _hash(name, getattr(self, name))
        if not _enum_member(
            self.access_route, CnAShareExecutionAccessRoute
        ) or not _enum_member(self.fee_product_class, CnAShareFeeProductClass):
            raise TypeError(
                "profile binding route/product must be declared enum members"
            )
        authority = _reconstructed_authority(self.authority)
        if (
            authority is None
            or _reconstructed_component_ref(self.market_fee_component_ref) is None
            or _reconstructed_component_ref(self.stamp_duty_component_ref) is None
        ):
            raise TypeError(
                "profile binding authority/components must reconstruct exactly"
            )
        instrument_scope = profile.request.instrument_scope
        account_scope = profile.request.account_scope
        if instrument_scope is None or account_scope is None:
            raise ValueError(
                "resolved profile lacks immutable account/instrument scope"
            )
        source_market, source_stamp = _selected_source_books(profile, authority)
        profile_expected = (
            canonical_sha256(_profile_inputs(profile)),
            profile.market_registration.profile_key,
            profile.market_registration.profile_version,
            profile.simulation_registration.profile_key,
            profile.simulation_registration.profile_version,
            profile.execution_account_registration.profile_key,
            profile.execution_account_registration.profile_version,
            account_scope.account_id,
            account_scope.venue_id.value,
            str(instrument_scope.instrument.instrument_id),
            projection.projection_hash,
        )
        profile_actual = (
            self.legacy_profile_inputs_hash,
            self.market_profile_key,
            self.market_profile_version,
            self.simulation_profile_key,
            self.simulation_profile_version,
            self.execution_account_profile_key,
            self.execution_account_profile_version,
            self.account_id,
            self.venue_id,
            self.instrument_id,
            self.compatibility_projection_hash,
        )
        if profile_actual != profile_expected:
            raise ValueError("profile binding does not match resolved profile inputs")
        if (
            authority.scope.account_id != account_scope.account_id
            or authority.scope.venue_id != account_scope.venue_id
            or authority.scope.instrument != instrument_scope.instrument
            or projection.source_market_rule_book != source_market
            or projection.source_stamp_duty_rule_book != source_stamp
            or authority.market_fee_rule_book != projection.market_fee_rule_book
            or authority.stamp_duty_rule_book != projection.stamp_duty_rule_book
        ):
            raise ValueError("profile binding source authority mismatch")
        expected = (
            authority.authority_hash,
            authority.scope_hash,
            authority.selection_hash,
            authority.market_fee_rule_book_hash,
            authority.stamp_duty_rule_book_hash,
            authority.market_fee_component_ref,
            authority.stamp_duty_component_ref,
            authority.scope.account_id,
            authority.scope.venue_id.value,
            str(authority.scope.instrument_id),
            authority.access_route,
            authority.fee_product_class,
        )
        actual = (
            self.authority_hash,
            self.scope_hash,
            self.selection_hash,
            self.market_fee_rule_book_hash,
            self.stamp_duty_rule_book_hash,
            self.market_fee_component_ref,
            self.stamp_duty_component_ref,
            self.account_id,
            self.venue_id,
            self.instrument_id,
            self.access_route,
            self.fee_product_class,
        )
        if actual != expected:
            raise ValueError("profile binding authority identity mismatch")

    @property
    def profile_binding_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_fee_profile_binding_v2",
            **{
                field.name: getattr(self, field.name)
                for field in fields(self)
                if field.name not in {"resolved_profile", "projection"}
            },
        }


@dataclass(frozen=True, slots=True)
class CnAShareFeeBuildBindingV2:
    schema_version: int
    build_artifact_manifest: BuildArtifactManifest
    profile_binding: CnAShareFeeProfileBindingV2
    profile_binding_hash: str
    build_artifact_manifest_hash: str
    profile_artifact_hashes: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("build binding schema_version must be 1")
        manifest = _reconstructed_build(self.build_artifact_manifest)
        if manifest is None:
            raise TypeError("build_artifact_manifest must reconstruct exactly")
        if type(self.profile_binding) is not CnAShareFeeProfileBindingV2:
            raise TypeError("profile_binding must be exact CnAShareFeeProfileBindingV2")
        rebuilt = CnAShareFeeProfileBindingV2(
            *(
                getattr(self.profile_binding, field.name)
                for field in fields(self.profile_binding)
            )
        )
        if rebuilt != self.profile_binding:
            raise ValueError("profile_binding did not reconstruct exactly")
        _hash("profile_binding_hash", self.profile_binding_hash)
        _hash("build_artifact_manifest_hash", self.build_artifact_manifest_hash)
        if (
            self.profile_binding_hash != self.profile_binding.profile_binding_hash
            or self.build_artifact_manifest_hash != manifest.manifest_hash
        ):
            raise ValueError("build binding profile/manifest hash mismatch")
        if type(self.profile_artifact_hashes) is not tuple or not all(
            type(value) is tuple
            and len(value) == 2
            and type(value[0]) is str
            and type(value[1]) is str
            for value in self.profile_artifact_hashes
        ):
            raise TypeError("profile_artifact_hashes must contain exact pairs")
        for key, digest in self.profile_artifact_hashes:
            _text("profile artifact key", key)
            _hash("profile artifact hash", digest)
        if self.profile_artifact_hashes != tuple(sorted(self.profile_artifact_hashes)):
            raise ValueError("profile_artifact_hashes must be canonical-sorted")
        profile = self.profile_binding.resolved_profile
        registrations = (
            profile.market_registration,
            profile.simulation_registration,
            profile.execution_account_registration,
        )
        expected_artifacts: list[tuple[str, str]] = []
        for registration in registrations:
            artifact = _reconstructed_artifact(
                manifest.profile_artifact(registration.profile_key)
            )
            if (
                artifact is None
                or artifact.role is not BuildArtifactRole.PROFILE_COMPONENT
                or artifact.content_hash != registration.profile_digest
            ):
                raise ValueError("build manifest profile artifact identity mismatch")
            expected_artifacts.append(
                (registration.profile_key, canonical_sha256(artifact))
            )
        if self.profile_artifact_hashes != tuple(sorted(expected_artifacts)):
            raise ValueError("profile artifact hashes do not match build manifest")

    @property
    def build_binding_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_fee_build_binding_v2",
            "schema_version": self.schema_version,
            "profile_binding": self.profile_binding,
            "profile_binding_hash": self.profile_binding_hash,
            "build_artifact_manifest_hash": self.build_artifact_manifest_hash,
            "profile_artifact_hashes": self.profile_artifact_hashes,
        }


def bind_cn_a_share_fee_profile_v2(
    *,
    resolved_profile: CnAShareResolvedProfile,
    projection: CnAShareDomesticOrdinaryFeeProjectionV2,
    authority: CnAShareFeeExecutionAuthorityV2,
    access_route: CnAShareExecutionAccessRoute,
    fee_product_class: CnAShareFeeProductClass,
) -> CnAShareFeeProfileBindingV2:
    profile = _reconstructed_profile(resolved_profile)
    projected = _reconstructed_projection(projection)
    selected = _reconstructed_authority(authority)
    if profile is None or projected is None or selected is None:
        raise TypeError("profile, projection, and authority must reconstruct exactly")
    if not _enum_member(access_route, CnAShareExecutionAccessRoute) or not _enum_member(
        fee_product_class, CnAShareFeeProductClass
    ):
        raise TypeError("route/product must be declared enum members")
    if (access_route, fee_product_class) != (
        selected.access_route,
        selected.fee_product_class,
    ):
        raise ValueError("explicit route/product does not match selected authority")
    instrument_scope = profile.request.instrument_scope
    account_scope = profile.request.account_scope
    if instrument_scope is None or account_scope is None:
        raise ValueError("resolved profile lacks immutable account/instrument scope")
    if (
        selected.scope.account_id != account_scope.account_id
        or selected.scope.venue_id != account_scope.venue_id
        or selected.scope.instrument != instrument_scope.instrument
    ):
        raise ValueError("selected authority is outside resolved profile scope")
    source_market, source_stamp = _selected_source_books(profile, selected)
    if (
        projected.source_market_rule_book != source_market
        or projected.source_stamp_duty_rule_book != source_stamp
        or selected.market_fee_rule_book != projected.market_fee_rule_book
        or selected.stamp_duty_rule_book != projected.stamp_duty_rule_book
        or selected.market_fee_component_ref
        != selected.selection.market_fee_component_ref
        or selected.stamp_duty_component_ref
        != selected.selection.stamp_duty_component_ref
    ):
        raise ValueError("selected authority does not bind the profile fee projection")
    return CnAShareFeeProfileBindingV2(
        1,
        profile,
        projected,
        canonical_sha256(_profile_inputs(profile)),
        profile.market_semantics.profile_key,
        profile.market_semantics.profile_version,
        profile.simulation.profile_key,
        profile.simulation.profile_version,
        profile.execution_account.profile_key,
        profile.execution_account.profile_version,
        account_scope.account_id,
        account_scope.venue_id.value,
        str(instrument_scope.instrument.instrument_id),
        access_route,
        fee_product_class,
        selected,
        selected.authority_hash,
        selected.scope_hash,
        selected.selection_hash,
        selected.market_fee_rule_book_hash,
        selected.stamp_duty_rule_book_hash,
        selected.market_fee_component_ref,
        selected.stamp_duty_component_ref,
        projected.projection_hash,
    )


def bind_cn_a_share_fee_build_v2(
    *,
    resolved_profile: CnAShareResolvedProfile,
    profile_binding: CnAShareFeeProfileBindingV2,
    build_artifact_manifest: BuildArtifactManifest,
) -> CnAShareFeeBuildBindingV2:
    profile = _reconstructed_profile(resolved_profile)
    manifest = _reconstructed_build(build_artifact_manifest)
    if profile is None or manifest is None:
        raise TypeError("resolved profile and build manifest must reconstruct exactly")
    if type(profile_binding) is not CnAShareFeeProfileBindingV2:
        raise TypeError("profile_binding must be exact CnAShareFeeProfileBindingV2")
    rebuilt_binding = CnAShareFeeProfileBindingV2(
        *(getattr(profile_binding, field.name) for field in fields(profile_binding))
    )
    if rebuilt_binding != profile_binding:
        raise ValueError("profile_binding did not reconstruct exactly")
    if profile_binding.legacy_profile_inputs_hash != canonical_sha256(
        _profile_inputs(profile)
    ):
        raise ValueError("profile binding does not match resolved profile inputs")
    registrations = (
        profile.market_registration,
        profile.simulation_registration,
        profile.execution_account_registration,
    )
    artifact_hashes: list[tuple[str, str]] = []
    for registration in registrations:
        artifact = manifest.profile_artifact(registration.profile_key)
        if (
            type(artifact) is not BuildArtifactRef
            or artifact.role is not BuildArtifactRole.PROFILE_COMPONENT
            or artifact.content_hash != registration.profile_digest
        ):
            raise ValueError("build manifest profile artifact identity mismatch")
        artifact_hashes.append((registration.profile_key, canonical_sha256(artifact)))
    return CnAShareFeeBuildBindingV2(
        1,
        manifest,
        profile_binding,
        profile_binding.profile_binding_hash,
        manifest.manifest_hash,
        tuple(sorted(artifact_hashes)),
    )


def _reconstructed_kernel_binding(
    value: object,
) -> CnAShareFeeExecutionBindingV2 | None:
    if type(value) is not CnAShareFeeExecutionBindingV2:
        return None
    try:
        rebuilt = CnAShareFeeExecutionBindingV2(
            *(getattr(value, field.name) for field in fields(value))
        )
    except (TypeError, ValueError, AttributeError):
        return None
    return (
        value
        if rebuilt == value and rebuilt.binding_hash == value.binding_hash
        else None
    )


def _reconstructed_namespace(value: object) -> IdentityNamespace | None:
    if (
        type(value) is not IdentityNamespace
        or not _valid_text(value.value)
        or not _valid_text(value.version)
        or not _valid_text(value.algorithm)
    ):
        return None
    try:
        rebuilt = IdentityNamespace(value.value, value.version, value.algorithm)
    except (TypeError, ValueError, AttributeError):
        return None
    return value if rebuilt == value else None


def _reconstructed_identity_rule(
    value: object,
) -> ExecutionCaseIdentityRule | None:
    if (
        type(value) is not ExecutionCaseIdentityRule
        or not _valid_text(value.binding_key)
        or not _valid_text(value.semantic_key)
        or type(value.ordinal) is not int
        or value.ordinal < 0
        or not (
            value.domain_kind is None or _enum_member(value.domain_kind, DomainIdKind)
        )
    ):
        return None
    try:
        rebuilt = ExecutionCaseIdentityRule(
            value.binding_key, value.semantic_key, value.ordinal, value.domain_kind
        )
    except (TypeError, ValueError, AttributeError):
        return None
    return (
        value
        if rebuilt == value and canonical_sha256(rebuilt) == canonical_sha256(value)
        else None
    )


def _reconstructed_semantic_spec(
    value: object,
) -> ExecutionCaseSemanticSpec | None:
    if (
        type(value) is not ExecutionCaseSemanticSpec
        or type(value.schema_version) is not int
        or value.schema_version != 1
        or not _valid_text(value.spec_key)
        or type(value.spec_version) is not int
        or value.spec_version <= 0
        or not _valid_text(value.case_key)
        or type(value.case_version) is not int
        or value.case_version <= 0
        or _reconstructed_namespace(value.identity_namespace) is None
        or type(value.identity_plan) is not tuple
        or not all(
            _reconstructed_identity_rule(rule) is not None
            for rule in value.identity_plan
        )
        or not all(
            _valid_hash(getattr(value, name))
            for name in (
                "timeline_semantic_hash",
                "target_stream_digest",
                "decision_inputs_hash",
                "execution_inputs_hash",
                "financial_inputs_hash",
                "snapshot_inputs_hash",
                "run_end_inputs_hash",
            )
        )
    ):
        return None
    try:
        rebuilt = ExecutionCaseSemanticSpec(
            *(getattr(value, field.name) for field in fields(value))
        )
    except (TypeError, ValueError, AttributeError):
        return None
    return (
        value
        if rebuilt == value and rebuilt.semantic_spec_hash == value.semantic_spec_hash
        else None
    )


@dataclass(frozen=True, slots=True)
class CnAShareFeeRuntimeExecutionV2:
    schema_version: int
    profile_binding: CnAShareFeeProfileBindingV2
    profile_binding_hash: str
    build_binding: CnAShareFeeBuildBindingV2
    build_binding_hash: str
    authority: CnAShareFeeExecutionAuthorityV2
    authority_hash: str
    execution_binding: CnAShareFeeExecutionBindingV2
    order_hash: str

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("runtime fee execution schema_version must be 1")
        if type(self.profile_binding) is not CnAShareFeeProfileBindingV2:
            raise TypeError("profile_binding must be exact CnAShareFeeProfileBindingV2")
        if type(self.build_binding) is not CnAShareFeeBuildBindingV2:
            raise TypeError("build_binding must be exact CnAShareFeeBuildBindingV2")
        rebuilt_profile = CnAShareFeeProfileBindingV2(
            *(
                getattr(self.profile_binding, field.name)
                for field in fields(self.profile_binding)
            )
        )
        rebuilt_build = CnAShareFeeBuildBindingV2(
            *(
                getattr(self.build_binding, field.name)
                for field in fields(self.build_binding)
            )
        )
        authority = _reconstructed_authority(self.authority)
        execution = _reconstructed_kernel_binding(self.execution_binding)
        if authority is None or execution is None:
            raise TypeError(
                "runtime authority/execution binding must reconstruct exactly"
            )
        for name in (
            "profile_binding_hash",
            "build_binding_hash",
            "authority_hash",
            "order_hash",
        ):
            _hash(name, getattr(self, name))
        if (
            rebuilt_profile != self.profile_binding
            or rebuilt_build != self.build_binding
            or self.profile_binding_hash != self.profile_binding.profile_binding_hash
            or self.build_binding.profile_binding != self.profile_binding
            or self.build_binding_hash != self.build_binding.build_binding_hash
            or self.authority != self.profile_binding.authority
            or self.authority_hash != self.profile_binding.authority_hash
            or self.execution_binding.authority != self.authority
            or self.execution_binding.authority_hash != self.authority_hash
            or self.order_hash != self.execution_binding.order_hash
        ):
            raise ValueError("runtime fee execution identity mismatch")

    @property
    def runtime_binding_hash(self) -> str:
        return canonical_sha256(self)

    def _require_authority(
        self, authority: CnAShareFeeExecutionAuthorityV2, /
    ) -> CnAShareFeeExecutionAuthorityV2:
        selected = _reconstructed_authority(authority)
        if (
            selected is None
            or selected != self.authority
            or selected.authority_hash != self.authority_hash
        ):
            raise ValueError("authority is not the execution-selected authority")
        return selected

    def reservation_query(
        self, authority: CnAShareFeeExecutionAuthorityV2, /
    ) -> CnAShareCashFeeRuleQueryV2:
        selected = self._require_authority(authority)
        query = CnAShareCashFeeRuleQueryV2.for_reservation(
            selected, self.execution_binding
        )
        if type(query) is not CnAShareCashFeeRuleQueryV2:
            failure = cast(CnAShareFeeQueryConstructionFailureV2, query)
            raise ValueError(f"fee reservation query failed:{failure.code.value}")
        return query

    def final_fill_query(
        self, authority: CnAShareFeeExecutionAuthorityV2, fill: Fill | None, /
    ) -> CnAShareCashFeeRuleQueryV2:
        selected = self._require_authority(authority)
        query = CnAShareCashFeeRuleQueryV2.for_final_fill(
            selected, self.execution_binding, fill
        )
        if type(query) is not CnAShareCashFeeRuleQueryV2:
            failure = cast(CnAShareFeeQueryConstructionFailureV2, query)
            raise ValueError(f"fee final-fill query failed:{failure.code.value}")
        return query

    def policies(
        self, authority: CnAShareFeeExecutionAuthorityV2, /
    ) -> tuple[CnAShareCashMarketFeePolicyV2, CnAShareCashStampDutyTaxPolicyV2]:
        selected = self._require_authority(authority)
        return (
            CnAShareCashMarketFeePolicyV2(selected, selected.authority_hash, _SCALE),
            CnAShareCashStampDutyTaxPolicyV2(selected, selected.authority_hash, _SCALE),
        )

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_fee_runtime_execution_v2",
            **{field.name: getattr(self, field.name) for field in fields(self)},
        }


def bind_cn_a_share_fee_execution_v2(
    *,
    profile_binding: CnAShareFeeProfileBindingV2,
    build_binding: CnAShareFeeBuildBindingV2,
    authority: CnAShareFeeExecutionAuthorityV2,
    order: Order,
) -> CnAShareFeeRuntimeExecutionV2:
    if type(profile_binding) is not CnAShareFeeProfileBindingV2:
        raise TypeError("profile_binding must be exact CnAShareFeeProfileBindingV2")
    if type(build_binding) is not CnAShareFeeBuildBindingV2:
        raise TypeError("build_binding must be exact CnAShareFeeBuildBindingV2")
    selected = _reconstructed_authority(authority)
    if selected is None:
        raise TypeError("authority must reconstruct exactly")
    if (
        build_binding.profile_binding != profile_binding
        or build_binding.profile_binding_hash != profile_binding.profile_binding_hash
        or selected != profile_binding.authority
        or selected.authority_hash != profile_binding.authority_hash
    ):
        raise ValueError("runtime binding does not use the selected profile authority")
    execution = bind_kernel_fee_execution_v2(selected, order)
    if type(execution) is not CnAShareFeeExecutionBindingV2:
        failure = cast(CnAShareFeeExecutionBindingFailureV2, execution)
        raise ValueError(f"fee execution binding failed:{failure.code.value}")
    return CnAShareFeeRuntimeExecutionV2(
        1,
        profile_binding,
        profile_binding.profile_binding_hash,
        build_binding,
        build_binding.build_binding_hash,
        selected,
        selected.authority_hash,
        execution,
        execution.order_hash,
    )


def bind_cn_a_share_fee_semantic_spec_v2(
    *,
    base_spec: ExecutionCaseSemanticSpec,
    build_binding: CnAShareFeeBuildBindingV2,
) -> ExecutionCaseSemanticSpec:
    spec = _reconstructed_semantic_spec(base_spec)
    if spec is None:
        raise TypeError("base_spec must reconstruct exactly")
    if type(build_binding) is not CnAShareFeeBuildBindingV2:
        raise TypeError("build_binding must be exact CnAShareFeeBuildBindingV2")
    rebuilt = CnAShareFeeBuildBindingV2(
        *(getattr(build_binding, field.name) for field in fields(build_binding))
    )
    if rebuilt != build_binding:
        raise ValueError("build_binding did not reconstruct exactly")
    return replace(
        spec,
        financial_inputs_hash=canonical_sha256(
            {
                "type": "cn_a_share_fee_financial_inputs_binding_v2",
                "schema_version": 1,
                "base_financial_inputs_hash": spec.financial_inputs_hash,
                "fee_build_binding_hash": build_binding.build_binding_hash,
            }
        ),
    )


@dataclass(frozen=True, slots=True)
class CnAShareFeePreparedExecutionV2:
    schema_version: int
    base_spec: ExecutionCaseSemanticSpec
    profile_binding: CnAShareFeeProfileBindingV2
    build_binding: CnAShareFeeBuildBindingV2
    runtime_execution: CnAShareFeeRuntimeExecutionV2
    semantic_spec: ExecutionCaseSemanticSpec

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("prepared fee execution schema_version must be 1")
        base = _reconstructed_semantic_spec(self.base_spec)
        if base is None:
            raise TypeError("prepared base_spec must reconstruct exactly")
        if type(self.profile_binding) is not CnAShareFeeProfileBindingV2:
            raise TypeError("prepared profile_binding must be exact")
        if type(self.build_binding) is not CnAShareFeeBuildBindingV2:
            raise TypeError("prepared build_binding must be exact")
        if type(self.runtime_execution) is not CnAShareFeeRuntimeExecutionV2:
            raise TypeError("prepared runtime_execution must be exact")
        semantic = _reconstructed_semantic_spec(self.semantic_spec)
        if semantic is None:
            raise TypeError("prepared semantic_spec must reconstruct exactly")
        profile = CnAShareFeeProfileBindingV2(
            *(
                getattr(self.profile_binding, field.name)
                for field in fields(self.profile_binding)
            )
        )
        build = CnAShareFeeBuildBindingV2(
            *(
                getattr(self.build_binding, field.name)
                for field in fields(self.build_binding)
            )
        )
        runtime = CnAShareFeeRuntimeExecutionV2(
            *(
                getattr(self.runtime_execution, field.name)
                for field in fields(self.runtime_execution)
            )
        )
        expected_spec = bind_cn_a_share_fee_semantic_spec_v2(
            base_spec=base,
            build_binding=build,
        )
        if (
            profile != self.profile_binding
            or build != self.build_binding
            or runtime != self.runtime_execution
            or build.profile_binding != profile
            or runtime.profile_binding != profile
            or runtime.build_binding != build
            or semantic != expected_spec
            or semantic.semantic_spec_hash != expected_spec.semantic_spec_hash
        ):
            raise ValueError("prepared fee execution identity mismatch")

    @property
    def preparation_hash(self) -> str:
        return canonical_sha256(self)

    def reservation_query(self) -> CnAShareCashFeeRuleQueryV2:
        return self.runtime_execution.reservation_query(
            self.runtime_execution.authority
        )

    def final_fill_query(self, fill: Fill | None, /) -> CnAShareCashFeeRuleQueryV2:
        return self.runtime_execution.final_fill_query(
            self.runtime_execution.authority, fill
        )

    def policies(
        self,
    ) -> tuple[CnAShareCashMarketFeePolicyV2, CnAShareCashStampDutyTaxPolicyV2]:
        return self.runtime_execution.policies(self.runtime_execution.authority)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_fee_prepared_execution_v2",
            "schema_version": self.schema_version,
            "profile_binding": self.profile_binding,
            "build_binding": self.build_binding,
            "runtime_execution": self.runtime_execution,
            "semantic_spec": self.semantic_spec,
        }


def prepare_cn_a_share_fee_execution_v2(
    *,
    resolved_profile: CnAShareResolvedProfile,
    projection: CnAShareDomesticOrdinaryFeeProjectionV2,
    authority: CnAShareFeeExecutionAuthorityV2,
    access_route: CnAShareExecutionAccessRoute,
    fee_product_class: CnAShareFeeProductClass,
    build_artifact_manifest: BuildArtifactManifest,
    base_spec: ExecutionCaseSemanticSpec,
    order: Order,
) -> CnAShareFeePreparedExecutionV2:
    profile_binding = bind_cn_a_share_fee_profile_v2(
        resolved_profile=resolved_profile,
        projection=projection,
        authority=authority,
        access_route=access_route,
        fee_product_class=fee_product_class,
    )
    build_binding = bind_cn_a_share_fee_build_v2(
        resolved_profile=resolved_profile,
        profile_binding=profile_binding,
        build_artifact_manifest=build_artifact_manifest,
    )
    runtime_execution = bind_cn_a_share_fee_execution_v2(
        profile_binding=profile_binding,
        build_binding=build_binding,
        authority=authority,
        order=order,
    )
    semantic_spec = bind_cn_a_share_fee_semantic_spec_v2(
        base_spec=base_spec,
        build_binding=build_binding,
    )
    return CnAShareFeePreparedExecutionV2(
        1,
        base_spec,
        profile_binding,
        build_binding,
        runtime_execution,
        semantic_spec,
    )
