"""Composition-root request normalization and profile resolution."""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
from enum import Enum
import re
from typing import Protocol, TypeVar, cast, runtime_checkable
import unicodedata

from crypto_quant_domain import CurrencyId, UtcInstant, canonical_sha256
from crypto_quant_market_data import (
    MarketBundleCapability,
    MarketBundleManifest,
    MarketBundleRef,
)
from crypto_quant_trading import ProfileComponentRef, ProfilePortType

from .ports import SimulationComponentRef, SimulationPortType
from .timeline import TimelineWindow


_HASH_PATTERN = re.compile(r"sha256:[0-9a-f]{64}")
_SEMANTIC_RUN_PATTERN = re.compile(r"run_[0-9a-f]{64}")


def _text(name: str, value: object) -> str:
    if type(value) is not str:
        raise TypeError(f"{name} must be str")
    if (
        not value
        or value.strip() != value
        or unicodedata.normalize("NFC", value) != value
    ):
        raise ValueError(f"{name} must be nonempty canonical text")
    return value


def _hash(name: str, value: object) -> str:
    if type(value) is not str:
        raise TypeError(f"{name} must be str")
    if _HASH_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{name} must be canonical sha256 identity")
    return value


def _optional_hash(name: str, value: object) -> str | None:
    if value is None:
        return None
    return _hash(name, value)


def _canonical_strings(name: str, values: tuple[str, ...]) -> tuple[str, ...]:
    if type(values) is not tuple:
        raise TypeError(f"{name} must be tuple")
    checked = tuple(_text(name, value) for value in values)
    if len(set(checked)) != len(checked):
        raise ValueError(f"{name} must be unique")
    return tuple(sorted(checked))


class RequestedResultGrade(str, Enum):
    DEVELOPMENT = "development"
    DECISION_GRADE = "decision_grade"


class StrategyFamily(str, Enum):
    PRECOMPUTED_TARGET = "precomputed_target"
    PORTFOLIO_STRATEGY = "portfolio_strategy"
    LIQUIDITY_STRATEGY = "liquidity_strategy"


class BuildArtifactRole(str, Enum):
    DECISION_SOURCE = "decision_source"
    TRADING_DOMAIN = "trading_domain"
    TRADING_KERNEL = "trading_kernel"
    MARKET_DATA_CONTRACTS = "market_data_contracts"
    BACKTEST_RUNTIME = "backtest_runtime"
    PROFILE_COMPONENT = "profile_component"


class ArtifactInstallMode(str, Enum):
    WHEEL = "wheel"
    CONTAINER = "container"
    EDITABLE = "editable"


class SourceTreeState(str, Enum):
    CLEAN = "clean"
    DIRTY = "dirty"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class BuildArtifactRef:
    role: BuildArtifactRole
    artifact_key: str
    artifact_version: str
    install_mode: ArtifactInstallMode
    source_tree_state: SourceTreeState
    content_hash: str | None
    source_snapshot_hash: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.role, BuildArtifactRole):
            raise TypeError("role must be BuildArtifactRole")
        _text("artifact_key", self.artifact_key)
        _text("artifact_version", self.artifact_version)
        if not isinstance(self.install_mode, ArtifactInstallMode):
            raise TypeError("install_mode must be ArtifactInstallMode")
        if not isinstance(self.source_tree_state, SourceTreeState):
            raise TypeError("source_tree_state must be SourceTreeState")
        _optional_hash("content_hash", self.content_hash)
        _optional_hash("source_snapshot_hash", self.source_snapshot_hash)

    @property
    def has_immutable_identity(self) -> bool:
        return self.content_hash is not None or self.source_snapshot_hash is not None

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "build_artifact_ref",
            "role": self.role.value,
            "artifact_key": self.artifact_key,
            "artifact_version": self.artifact_version,
            "install_mode": self.install_mode.value,
            "source_tree_state": self.source_tree_state.value,
            "content_hash": self.content_hash,
            "source_snapshot_hash": self.source_snapshot_hash,
        }


@dataclass(frozen=True, slots=True)
class RuntimeLibraryRef:
    library_key: str
    version: str
    content_hash: str

    def __post_init__(self) -> None:
        _text("library_key", self.library_key)
        _text("runtime library version", self.version)
        _hash("runtime library content_hash", self.content_hash)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "runtime_library_ref",
            "library_key": self.library_key,
            "version": self.version,
            "content_hash": self.content_hash,
        }


@dataclass(frozen=True, slots=True)
class BuildProvenance:
    """Operational provenance deliberately excluded from build identity."""

    git_commit: str
    hostname: str
    source_root: str
    built_at: UtcInstant

    def __post_init__(self) -> None:
        _text("git_commit", self.git_commit)
        _text("hostname", self.hostname)
        _text("source_root", self.source_root)
        if not isinstance(self.built_at, UtcInstant):
            raise TypeError("built_at must be UtcInstant")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "build_provenance",
            "git_commit": self.git_commit,
            "hostname": self.hostname,
            "source_root": self.source_root,
            "built_at": self.built_at,
        }


_REQUIRED_ARTIFACT_ROLES = frozenset(
    {
        BuildArtifactRole.DECISION_SOURCE,
        BuildArtifactRole.TRADING_DOMAIN,
        BuildArtifactRole.TRADING_KERNEL,
        BuildArtifactRole.MARKET_DATA_CONTRACTS,
        BuildArtifactRole.BACKTEST_RUNTIME,
        BuildArtifactRole.PROFILE_COMPONENT,
    }
)


@dataclass(frozen=True, slots=True)
class BuildArtifactManifest:
    schema_version: int
    build_key: str
    artifacts: tuple[BuildArtifactRef, ...]
    dependency_lock_hash: str
    runtime_libraries: tuple[RuntimeLibraryRef, ...]
    container_image_digest: str | None
    provenance: BuildProvenance

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("BuildArtifactManifest schema_version must be 1")
        _text("build_key", self.build_key)
        if type(self.artifacts) is not tuple or not all(
            isinstance(value, BuildArtifactRef) for value in self.artifacts
        ):
            raise TypeError("artifacts must contain BuildArtifactRef")
        ordered_artifacts = tuple(
            sorted(
                self.artifacts,
                key=lambda value: (
                    value.role.value,
                    value.artifact_key,
                    value.artifact_version,
                ),
            )
        )
        artifact_keys = tuple(
            (value.role, value.artifact_key) for value in ordered_artifacts
        )
        if len(set(artifact_keys)) != len(artifact_keys):
            raise ValueError("build artifact role/key pairs must be unique")
        object.__setattr__(self, "artifacts", ordered_artifacts)
        _hash("dependency_lock_hash", self.dependency_lock_hash)
        if type(self.runtime_libraries) is not tuple or not all(
            isinstance(value, RuntimeLibraryRef) for value in self.runtime_libraries
        ):
            raise TypeError("runtime_libraries must contain RuntimeLibraryRef")
        ordered_libraries = tuple(
            sorted(self.runtime_libraries, key=lambda value: value.library_key)
        )
        if len({value.library_key for value in ordered_libraries}) != len(
            ordered_libraries
        ):
            raise ValueError("runtime library keys must be unique")
        if not ordered_libraries:
            raise ValueError("at least one runtime library is required")
        object.__setattr__(self, "runtime_libraries", ordered_libraries)
        _optional_hash("container_image_digest", self.container_image_digest)
        if not isinstance(self.provenance, BuildProvenance):
            raise TypeError("provenance must be BuildProvenance")

    @property
    def present_roles(self) -> frozenset[BuildArtifactRole]:
        return frozenset(value.role for value in self.artifacts)

    @property
    def has_required_roles(self) -> bool:
        return _REQUIRED_ARTIFACT_ROLES <= self.present_roles

    @property
    def decision_grade_eligible(self) -> bool:
        return (
            self.has_required_roles
            and all(value.has_immutable_identity for value in self.artifacts)
            and all(
                value.install_mode is not ArtifactInstallMode.EDITABLE
                for value in self.artifacts
            )
        )

    @property
    def limitations(self) -> tuple[str, ...]:
        values: set[str] = set()
        for artifact in self.artifacts:
            if artifact.install_mode is ArtifactInstallMode.EDITABLE:
                values.add(f"editable_build_artifact:{artifact.artifact_key}")
            if not artifact.has_immutable_identity:
                values.add(f"unidentified_build_artifact:{artifact.artifact_key}")
            if (
                artifact.source_tree_state is SourceTreeState.DIRTY
                and not artifact.has_immutable_identity
            ):
                values.add(f"dirty_unidentified_source:{artifact.artifact_key}")
        if not self.has_required_roles:
            values.add("incomplete_build_artifact_roles")
        return tuple(sorted(values))

    def profile_artifact(self, profile_key: str) -> BuildArtifactRef | None:
        matches = tuple(
            value
            for value in self.artifacts
            if value.role is BuildArtifactRole.PROFILE_COMPONENT
            and value.artifact_key == profile_key
        )
        return matches[0] if matches else None

    def identity_dict(self) -> dict[str, object]:
        return {
            "type": "build_artifact_manifest_identity",
            "schema_version": self.schema_version,
            "build_key": self.build_key,
            "artifacts": self.artifacts,
            "dependency_lock_hash": self.dependency_lock_hash,
            "runtime_libraries": self.runtime_libraries,
            "container_image_digest": self.container_image_digest,
        }

    @property
    def manifest_hash(self) -> str:
        return canonical_sha256(self.identity_dict())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "build_artifact_manifest",
            "identity": self.identity_dict(),
            "manifest_hash": self.manifest_hash,
            "provenance": self.provenance,
        }


@runtime_checkable
class _MarketSemanticsImplementation(Protocol):
    @property
    @abstractmethod
    def profile_digest(self) -> str:
        raise TypeError("market profile implementation has no default digest")

    @property
    @abstractmethod
    def component_manifest(self) -> tuple[ProfileComponentRef, ...]:
        raise TypeError("market profile implementation has no default manifest")

    @abstractmethod
    def to_canonical_dict(self) -> dict[str, object]:
        raise TypeError("market profile implementation has no default encoding")


@runtime_checkable
class _SimulationImplementation(Protocol):
    @property
    @abstractmethod
    def profile_digest(self) -> str:
        raise TypeError("simulation profile implementation has no default digest")

    @property
    @abstractmethod
    def component_manifest(self) -> tuple[SimulationComponentRef, ...]:
        raise TypeError("simulation profile implementation has no default manifest")

    @abstractmethod
    def to_canonical_dict(self) -> dict[str, object]:
        raise TypeError("simulation profile implementation has no default encoding")


@runtime_checkable
class _ExecutionAccountImplementation(Protocol):
    @property
    @abstractmethod
    def profile_digest(self) -> str:
        raise TypeError("account profile implementation has no default digest")

    @abstractmethod
    def to_canonical_dict(self) -> dict[str, object]:
        raise TypeError("account profile implementation has no default encoding")


def _profile_fields(
    *,
    profile_key: str,
    profile_version: int,
    profile_digest: str,
    grade: RequestedResultGrade,
    limitations: tuple[str, ...],
    decision_grade_eligible: bool,
) -> tuple[str, ...]:
    _text("profile_key", profile_key)
    if type(profile_version) is not int or profile_version <= 0:
        raise ValueError("profile_version must be positive integer")
    _hash("profile_digest", profile_digest)
    if not isinstance(grade, RequestedResultGrade):
        raise TypeError("grade must be RequestedResultGrade")
    normalized_limitations = _canonical_strings("limitations", limitations)
    if type(decision_grade_eligible) is not bool:
        raise TypeError("decision_grade_eligible must be bool")
    if grade is RequestedResultGrade.DEVELOPMENT and decision_grade_eligible:
        raise ValueError("development profile cannot be decision-grade eligible")
    return normalized_limitations


class _RegistrationHeader(Protocol):
    @property
    def profile_key(self) -> str:
        raise TypeError("registration has no default profile key")

    @property
    def profile_version(self) -> int:
        raise TypeError("registration has no default profile version")

    @property
    def profile_digest(self) -> str:
        raise TypeError("registration has no default profile digest")

    @property
    def grade(self) -> RequestedResultGrade:
        raise TypeError("registration has no default grade")

    @property
    def limitations(self) -> tuple[str, ...]:
        raise TypeError("registration has no default limitations")

    @property
    def decision_grade_eligible(self) -> bool:
        raise TypeError("registration has no default grade eligibility")


def _validate_registration_header(
    registration: _RegistrationHeader,
    implementation: object,
    expected_type: type[object],
    label: str,
) -> tuple[str, ...]:
    normalized = _profile_fields(
        profile_key=registration.profile_key,
        profile_version=registration.profile_version,
        profile_digest=registration.profile_digest,
        grade=registration.grade,
        limitations=registration.limitations,
        decision_grade_eligible=registration.decision_grade_eligible,
    )
    if not isinstance(implementation, expected_type):
        raise TypeError(f"implementation must satisfy {label} profile contract")
    implementation_digest = getattr(implementation, "profile_digest")
    if implementation_digest != registration.profile_digest:
        raise ValueError(f"{label} implementation profile digest mismatch")
    return normalized


def _required_capabilities(
    values: tuple[MarketBundleCapability, ...],
) -> tuple[MarketBundleCapability, ...]:
    if type(values) is not tuple or not all(
        isinstance(value, MarketBundleCapability) for value in values
    ):
        raise TypeError("required_bundle_capabilities must contain MarketBundleCapability")
    ordered = tuple(sorted(values, key=lambda value: (value.key, value.version)))
    if len({value.key for value in ordered}) != len(ordered):
        raise ValueError("required bundle capability keys must be unique")
    return ordered


@dataclass(frozen=True, slots=True)
class MarketSemanticsProfileRegistration:
    profile_key: str
    profile_version: int
    profile_digest: str
    implementation: _MarketSemanticsImplementation
    venue_id: str
    required_bundle_capabilities: tuple[MarketBundleCapability, ...]
    component_manifest: tuple[ProfileComponentRef, ...]
    grade: RequestedResultGrade
    limitations: tuple[str, ...]
    decision_grade_eligible: bool

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "limitations",
            _validate_registration_header(
                self, self.implementation, _MarketSemanticsImplementation, "market"
            ),
        )
        _text("venue_id", self.venue_id)
        object.__setattr__(
            self,
            "required_bundle_capabilities",
            _required_capabilities(self.required_bundle_capabilities),
        )
        if type(self.component_manifest) is not tuple or not all(
            isinstance(value, ProfileComponentRef) for value in self.component_manifest
        ):
            raise TypeError("component_manifest must contain ProfileComponentRef")
        ordered = tuple(
            sorted(self.component_manifest, key=lambda value: value.port_type.value)
        )
        if {value.port_type for value in ordered} != set(ProfilePortType):
            raise ValueError("market profile must exact-cover all ProfilePortType values")
        if tuple(self.implementation.component_manifest) != ordered:
            raise ValueError("market implementation component manifest mismatch")
        object.__setattr__(self, "component_manifest", ordered)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "market_semantics_profile_registration",
            "profile_key": self.profile_key,
            "profile_version": self.profile_version,
            "profile_digest": self.profile_digest,
            "venue_id": self.venue_id,
            "required_bundle_capabilities": self.required_bundle_capabilities,
            "component_manifest": self.component_manifest,
            "grade": self.grade.value,
            "limitations": self.limitations,
            "decision_grade_eligible": self.decision_grade_eligible,
        }


@dataclass(frozen=True, slots=True)
class SimulationProfileRegistration:
    profile_key: str
    profile_version: int
    profile_digest: str
    implementation: _SimulationImplementation
    engine_kind: str
    supported_strategy_families: tuple[StrategyFamily, ...]
    required_bundle_capabilities: tuple[MarketBundleCapability, ...]
    component_manifest: tuple[SimulationComponentRef, ...]
    grade: RequestedResultGrade
    limitations: tuple[str, ...]
    decision_grade_eligible: bool

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "limitations",
            _validate_registration_header(
                self, self.implementation, _SimulationImplementation, "simulation"
            ),
        )
        _text("engine_kind", self.engine_kind)
        if type(self.supported_strategy_families) is not tuple or not all(
            isinstance(value, StrategyFamily)
            for value in self.supported_strategy_families
        ):
            raise TypeError("supported_strategy_families must contain StrategyFamily")
        families = tuple(
            sorted(set(self.supported_strategy_families), key=lambda value: value.value)
        )
        if not families or len(families) != len(self.supported_strategy_families):
            raise ValueError("supported_strategy_families must be nonempty and unique")
        object.__setattr__(self, "supported_strategy_families", families)
        object.__setattr__(
            self,
            "required_bundle_capabilities",
            _required_capabilities(self.required_bundle_capabilities),
        )
        if type(self.component_manifest) is not tuple or not all(
            isinstance(value, SimulationComponentRef) for value in self.component_manifest
        ):
            raise TypeError("component_manifest must contain SimulationComponentRef")
        ordered = tuple(
            sorted(self.component_manifest, key=lambda value: value.port_type.value)
        )
        if {value.port_type for value in ordered} != set(SimulationPortType):
            raise ValueError(
                "simulation profile must exact-cover all SimulationPortType values"
            )
        if tuple(self.implementation.component_manifest) != ordered:
            raise ValueError("simulation implementation component manifest mismatch")
        object.__setattr__(self, "component_manifest", ordered)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "simulation_profile_registration",
            "profile_key": self.profile_key,
            "profile_version": self.profile_version,
            "profile_digest": self.profile_digest,
            "engine_kind": self.engine_kind,
            "supported_strategy_families": tuple(
                value.value for value in self.supported_strategy_families
            ),
            "required_bundle_capabilities": self.required_bundle_capabilities,
            "component_manifest": self.component_manifest,
            "grade": self.grade.value,
            "limitations": self.limitations,
            "decision_grade_eligible": self.decision_grade_eligible,
        }


@dataclass(frozen=True, slots=True)
class ExecutionAccountProfileRegistration:
    profile_key: str
    profile_version: int
    profile_digest: str
    implementation: _ExecutionAccountImplementation
    account_id: str
    venue_id: str
    account_type: str
    margin_mode: str
    supported_reporting_currencies: tuple[CurrencyId, ...]
    grade: RequestedResultGrade
    limitations: tuple[str, ...]
    decision_grade_eligible: bool

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "limitations",
            _validate_registration_header(
                self,
                self.implementation,
                _ExecutionAccountImplementation,
                "execution account",
            ),
        )
        for name in ("account_id", "venue_id", "account_type", "margin_mode"):
            _text(name, getattr(self, name))
        if type(self.supported_reporting_currencies) is not tuple or not all(
            isinstance(value, CurrencyId)
            for value in self.supported_reporting_currencies
        ):
            raise TypeError("supported_reporting_currencies must contain CurrencyId")
        currencies = tuple(
            sorted(self.supported_reporting_currencies, key=lambda value: value.value)
        )
        if not currencies or len({value.value for value in currencies}) != len(currencies):
            raise ValueError("supported_reporting_currencies must be nonempty and unique")
        object.__setattr__(self, "supported_reporting_currencies", currencies)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "execution_account_profile_registration",
            "profile_key": self.profile_key,
            "profile_version": self.profile_version,
            "profile_digest": self.profile_digest,
            "account_id": self.account_id,
            "venue_id": self.venue_id,
            "account_type": self.account_type,
            "margin_mode": self.margin_mode,
            "supported_reporting_currencies": self.supported_reporting_currencies,
            "grade": self.grade.value,
            "limitations": self.limitations,
            "decision_grade_eligible": self.decision_grade_eligible,
        }


class _ProfileRegistration(Protocol):
    @property
    def profile_key(self) -> str:
        raise TypeError("profile registration has no default key")


_RegistrationT = TypeVar("_RegistrationT", bound=_ProfileRegistration)


@dataclass(frozen=True, slots=True)
class BacktestProfileRegistry:
    market_semantics_profiles: tuple[MarketSemanticsProfileRegistration, ...] = ()
    simulation_profiles: tuple[SimulationProfileRegistration, ...] = ()
    execution_account_profiles: tuple[ExecutionAccountProfileRegistration, ...] = ()

    def __post_init__(self) -> None:
        market = self._ordered(
            "market_semantics_profiles",
            self.market_semantics_profiles,
            MarketSemanticsProfileRegistration,
            "duplicate market semantics profile key",
        )
        simulation = self._ordered(
            "simulation_profiles",
            self.simulation_profiles,
            SimulationProfileRegistration,
            "duplicate simulation profile key",
        )
        accounts = self._ordered(
            "execution_account_profiles",
            self.execution_account_profiles,
            ExecutionAccountProfileRegistration,
            "duplicate execution account profile key",
        )
        object.__setattr__(self, "market_semantics_profiles", market)
        object.__setattr__(self, "simulation_profiles", simulation)
        object.__setattr__(self, "execution_account_profiles", accounts)

    @staticmethod
    def _ordered(
        name: str,
        values: tuple[_RegistrationT, ...],
        expected_type: type[object],
        duplicate_message: str,
    ) -> tuple[_RegistrationT, ...]:
        if type(values) is not tuple or not all(
            isinstance(value, expected_type) for value in values
        ):
            raise TypeError(f"{name} contains invalid registration")
        ordered = tuple(sorted(values, key=lambda value: value.profile_key))
        if len({value.profile_key for value in ordered}) != len(ordered):
            raise ValueError(duplicate_message)
        return ordered

    def market_semantics(
        self, profile_key: str
    ) -> MarketSemanticsProfileRegistration | None:
        return next(
            (
                value
                for value in self.market_semantics_profiles
                if value.profile_key == profile_key
            ),
            None,
        )

    def simulation(self, profile_key: str) -> SimulationProfileRegistration | None:
        return next(
            (value for value in self.simulation_profiles if value.profile_key == profile_key),
            None,
        )

    def execution_account(
        self, profile_key: str
    ) -> ExecutionAccountProfileRegistration | None:
        return next(
            (
                value
                for value in self.execution_account_profiles
                if value.profile_key == profile_key
            ),
            None,
        )

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "backtest_profile_registry",
            "market_semantics_profiles": self.market_semantics_profiles,
            "simulation_profiles": self.simulation_profiles,
            "execution_account_profiles": self.execution_account_profiles,
        }


@dataclass(frozen=True, slots=True)
class BacktestRequest:
    schema_version: int
    experiment_id: str | None
    timeline_window: TimelineWindow
    market_semantics_profile_key: str
    simulation_profile_key: str
    execution_account_profile_key: str
    execution_account_id: str
    reporting_currency: CurrencyId
    market_bundle_ref: MarketBundleRef
    target_stream_digest: str
    execution_case_semantic_hash: str
    master_random_seed: int
    build_artifact_manifest_hash: str
    strategy_family: StrategyFamily
    engine_kind: str
    result_grade_requested: RequestedResultGrade

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("BacktestRequest schema_version must be 1")
        if self.experiment_id is not None:
            _text("experiment_id", self.experiment_id)
        if not isinstance(self.timeline_window, TimelineWindow):
            raise TypeError("timeline_window must be TimelineWindow")
        for name in (
            "market_semantics_profile_key",
            "simulation_profile_key",
            "execution_account_profile_key",
            "execution_account_id",
            "engine_kind",
        ):
            _text(name, getattr(self, name))
        if not isinstance(self.reporting_currency, CurrencyId):
            raise TypeError("reporting_currency must be CurrencyId")
        if not isinstance(self.market_bundle_ref, MarketBundleRef):
            raise TypeError("market_bundle_ref must be MarketBundleRef")
        _hash("target_stream_digest", self.target_stream_digest)
        _hash("execution_case_semantic_hash", self.execution_case_semantic_hash)
        if type(self.master_random_seed) is not int or self.master_random_seed < 0:
            raise ValueError("master_random_seed must be nonnegative integer")
        _hash("build_artifact_manifest_hash", self.build_artifact_manifest_hash)
        if not isinstance(self.strategy_family, StrategyFamily):
            raise TypeError("strategy_family must be StrategyFamily")
        if not isinstance(self.result_grade_requested, RequestedResultGrade):
            raise TypeError("result_grade_requested must be RequestedResultGrade")

    @property
    def request_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "backtest_request",
            "schema_version": self.schema_version,
            "experiment_id": self.experiment_id,
            "timeline_window": self.timeline_window,
            "market_semantics_profile_key": self.market_semantics_profile_key,
            "simulation_profile_key": self.simulation_profile_key,
            "execution_account_profile_key": self.execution_account_profile_key,
            "execution_account_id": self.execution_account_id,
            "reporting_currency": self.reporting_currency,
            "market_bundle_ref": self.market_bundle_ref,
            "target_stream_digest": self.target_stream_digest,
            "execution_case_semantic_hash": self.execution_case_semantic_hash,
            "master_random_seed": self.master_random_seed,
            "build_artifact_manifest_hash": self.build_artifact_manifest_hash,
            "strategy_family": self.strategy_family.value,
            "engine_kind": self.engine_kind,
            "result_grade_requested": self.result_grade_requested.value,
        }


@dataclass(frozen=True, slots=True)
class NormalizedBacktestRequest:
    request: BacktestRequest
    request_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.request, BacktestRequest):
            raise TypeError("request must be BacktestRequest")
        _hash("request_hash", self.request_hash)
        if self.request_hash != self.request.request_hash:
            raise ValueError("normalized request hash mismatch")

    @classmethod
    def from_request(cls, request: BacktestRequest) -> NormalizedBacktestRequest:
        return cls(request=request, request_hash=request.request_hash)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "normalized_backtest_request",
            "request": self.request,
            "request_hash": self.request_hash,
        }


class EnvironmentCompatibilityCheckCode(str, Enum):
    MARKET_BUNDLE_IDENTITY = "market_bundle_identity"
    MARKET_BUNDLE_COVERAGE = "market_bundle_coverage"
    MARKET_BUNDLE_CAPABILITIES = "market_bundle_capabilities"
    PROFILE_COMPONENT_COVERAGE = "profile_component_coverage"
    PROFILE_BUILD_IDENTITY = "profile_build_identity"
    VENUE_ACCOUNT_CONTEXT = "venue_account_context"
    SIMULATION_CONTEXT = "simulation_context"
    REPORTING_CURRENCY = "reporting_currency"
    PROFILE_GRADE = "profile_grade"
    BUILD_ARTIFACT_IDENTITY = "build_artifact_identity"


@dataclass(frozen=True, slots=True)
class EnvironmentCompatibilityCheck:
    code: EnvironmentCompatibilityCheckCode
    passed: bool
    subjects: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.code, EnvironmentCompatibilityCheckCode):
            raise TypeError("code must be EnvironmentCompatibilityCheckCode")
        if type(self.passed) is not bool:
            raise TypeError("passed must be bool")
        object.__setattr__(self, "subjects", _canonical_strings("subjects", self.subjects))

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "environment_compatibility_check",
            "code": self.code.value,
            "passed": self.passed,
            "subjects": self.subjects,
        }


@dataclass(frozen=True, slots=True)
class EnvironmentCompatibilityReport:
    request_hash: str
    market_bundle_manifest_hash: str
    profile_digests: tuple[str, ...]
    checks: tuple[EnvironmentCompatibilityCheck, ...]
    allowed_grade: RequestedResultGrade
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        _hash("request_hash", self.request_hash)
        _hash("market_bundle_manifest_hash", self.market_bundle_manifest_hash)
        if type(self.profile_digests) is not tuple:
            raise TypeError("profile_digests must be tuple")
        digests = tuple(sorted(_hash("profile_digest", value) for value in self.profile_digests))
        if len(set(digests)) != len(digests):
            raise ValueError("profile_digests must be unique")
        object.__setattr__(self, "profile_digests", digests)
        if type(self.checks) is not tuple or not all(
            isinstance(value, EnvironmentCompatibilityCheck) for value in self.checks
        ):
            raise TypeError("checks must contain EnvironmentCompatibilityCheck")
        checks = tuple(sorted(self.checks, key=lambda value: value.code.value))
        if len({value.code for value in checks}) != len(checks):
            raise ValueError("compatibility check codes must be unique")
        object.__setattr__(self, "checks", checks)
        if not isinstance(self.allowed_grade, RequestedResultGrade):
            raise TypeError("allowed_grade must be RequestedResultGrade")
        object.__setattr__(
            self, "limitations", _canonical_strings("limitations", self.limitations)
        )

    @property
    def compatible(self) -> bool:
        return all(value.passed for value in self.checks)

    @property
    def failed_codes(self) -> tuple[EnvironmentCompatibilityCheckCode, ...]:
        return tuple(value.code for value in self.checks if not value.passed)

    @property
    def report_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "environment_compatibility_report",
            "request_hash": self.request_hash,
            "market_bundle_manifest_hash": self.market_bundle_manifest_hash,
            "profile_digests": self.profile_digests,
            "checks": self.checks,
            "compatible": self.compatible,
            "failed_codes": tuple(value.value for value in self.failed_codes),
            "allowed_grade": self.allowed_grade.value,
            "limitations": self.limitations,
        }


@dataclass(frozen=True, slots=True)
class ResolvedBacktestEnvironment:
    market_semantics: MarketSemanticsProfileRegistration
    simulation: SimulationProfileRegistration
    execution_account: ExecutionAccountProfileRegistration
    market_bundle_ref: MarketBundleRef
    compatibility_report: EnvironmentCompatibilityReport
    limitations: tuple[str, ...]
    deployment_authorized: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.market_semantics, MarketSemanticsProfileRegistration):
            raise TypeError("market_semantics must be registered profile")
        if not isinstance(self.simulation, SimulationProfileRegistration):
            raise TypeError("simulation must be registered profile")
        if not isinstance(self.execution_account, ExecutionAccountProfileRegistration):
            raise TypeError("execution_account must be registered profile")
        if not isinstance(self.market_bundle_ref, MarketBundleRef):
            raise TypeError("market_bundle_ref must be MarketBundleRef")
        if not isinstance(self.compatibility_report, EnvironmentCompatibilityReport):
            raise TypeError("compatibility_report must be EnvironmentCompatibilityReport")
        if not self.compatibility_report.compatible:
            raise ValueError("resolved environment requires compatible report")
        normalized = _canonical_strings("limitations", self.limitations)
        if normalized != self.compatibility_report.limitations:
            raise ValueError("environment limitations must match compatibility report")
        object.__setattr__(self, "limitations", normalized)
        if type(self.deployment_authorized) is not bool:
            raise TypeError("deployment_authorized must be bool")
        if self.deployment_authorized:
            raise ValueError("backtest environment never authorizes deployment")

    @property
    def environment_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "resolved_backtest_environment",
            "market_semantics": self.market_semantics,
            "simulation": self.simulation,
            "execution_account": self.execution_account,
            "market_bundle_ref": self.market_bundle_ref,
            "compatibility_report": self.compatibility_report,
            "limitations": self.limitations,
            "deployment_authorized": self.deployment_authorized,
        }


class BacktestResolutionFailureCode(str, Enum):
    PROFILE_NOT_FOUND = "profile_not_found"
    INCOMPATIBLE_ENVIRONMENT = "incompatible_environment"


@dataclass(frozen=True, slots=True)
class BacktestResolutionFailure:
    code: BacktestResolutionFailureCode
    request_hash: str
    subjects: tuple[str, ...]
    compatibility_report: EnvironmentCompatibilityReport | None

    def __post_init__(self) -> None:
        if not isinstance(self.code, BacktestResolutionFailureCode):
            raise TypeError("code must be BacktestResolutionFailureCode")
        _hash("request_hash", self.request_hash)
        object.__setattr__(self, "subjects", _canonical_strings("subjects", self.subjects))
        if self.compatibility_report is not None and not isinstance(
            self.compatibility_report, EnvironmentCompatibilityReport
        ):
            raise TypeError("compatibility_report must be EnvironmentCompatibilityReport")
        if (
            self.code is BacktestResolutionFailureCode.INCOMPATIBLE_ENVIRONMENT
            and (
                self.compatibility_report is None
                or self.compatibility_report.compatible
            )
        ):
            raise ValueError("incompatible failure requires failed compatibility report")

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "backtest_resolution_failure",
            "code": self.code.value,
            "request_hash": self.request_hash,
            "subjects": self.subjects,
            "compatibility_report": self.compatibility_report,
        }


def _semantic_run_id(
    normalized: NormalizedBacktestRequest,
    environment: ResolvedBacktestEnvironment,
    manifest_hash: str,
) -> str:
    identity = canonical_sha256(
        {
            "type": "semantic_run_identity",
            "schema_version": 1,
            "normalized_request": normalized,
            "market_bundle_ref": environment.market_bundle_ref,
            "market_semantics_profile_digest": environment.market_semantics.profile_digest,
            "simulation_profile_digest": environment.simulation.profile_digest,
            "execution_account_profile_digest": environment.execution_account.profile_digest,
            "build_artifact_manifest_hash": manifest_hash,
            "target_stream_digest": normalized.request.target_stream_digest,
        }
    )
    return f"run_{identity.removeprefix('sha256:')}"


@dataclass(frozen=True, slots=True)
class ResolvedBacktestRequest:
    request: BacktestRequest
    normalized_request: NormalizedBacktestRequest
    environment: ResolvedBacktestEnvironment
    build_artifact_manifest: BuildArtifactManifest
    semantic_run_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.request, BacktestRequest):
            raise TypeError("request must be BacktestRequest")
        if not isinstance(self.normalized_request, NormalizedBacktestRequest):
            raise TypeError("normalized_request must be NormalizedBacktestRequest")
        if self.normalized_request.request != self.request:
            raise ValueError("normalized request does not wrap request")
        if not isinstance(self.environment, ResolvedBacktestEnvironment):
            raise TypeError("environment must be ResolvedBacktestEnvironment")
        if not isinstance(self.build_artifact_manifest, BuildArtifactManifest):
            raise TypeError("build_artifact_manifest must be BuildArtifactManifest")
        if _SEMANTIC_RUN_PATTERN.fullmatch(self.semantic_run_id) is None:
            raise ValueError("semantic_run_id must use run_sha256 schema")
        expected = _semantic_run_id(
            self.normalized_request,
            self.environment,
            self.build_artifact_manifest.manifest_hash,
        )
        if self.semantic_run_id != expected:
            raise ValueError("semantic_run_id does not match resolved identities")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "resolved_backtest_request",
            "request": self.request,
            "normalized_request": self.normalized_request,
            "environment": self.environment,
            "build_artifact_manifest_hash": self.build_artifact_manifest.manifest_hash,
            "semantic_run_id": self.semantic_run_id,
        }


@dataclass(frozen=True, slots=True)
class BacktestResolutionOutcome:
    resolved: ResolvedBacktestRequest | None
    failure: BacktestResolutionFailure | None

    def __post_init__(self) -> None:
        if (self.resolved is None) == (self.failure is None):
            raise ValueError("resolution outcome requires exactly one branch")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "backtest_resolution_outcome",
            "resolved": self.resolved,
            "failure": self.failure,
        }


class ProfileResolver:
    """Pure composition root; it validates identities and never executes a model."""

    def resolve(
        self,
        *,
        request: BacktestRequest,
        registry: BacktestProfileRegistry,
        market_bundle_manifest: MarketBundleManifest,
        build_artifact_manifest: BuildArtifactManifest,
    ) -> BacktestResolutionOutcome:
        if not isinstance(request, BacktestRequest):
            raise TypeError("request must be BacktestRequest")
        if not isinstance(registry, BacktestProfileRegistry):
            raise TypeError("registry must be BacktestProfileRegistry")
        if not isinstance(market_bundle_manifest, MarketBundleManifest):
            raise TypeError("market_bundle_manifest must be MarketBundleManifest")
        if not isinstance(build_artifact_manifest, BuildArtifactManifest):
            raise TypeError("build_artifact_manifest must be BuildArtifactManifest")

        normalized = NormalizedBacktestRequest.from_request(request)
        market = registry.market_semantics(request.market_semantics_profile_key)
        simulation = registry.simulation(request.simulation_profile_key)
        account = registry.execution_account(request.execution_account_profile_key)
        missing = tuple(
            key
            for key, value in (
                (request.market_semantics_profile_key, market),
                (request.simulation_profile_key, simulation),
                (request.execution_account_profile_key, account),
            )
            if value is None
        )
        if missing:
            return BacktestResolutionOutcome(
                resolved=None,
                failure=BacktestResolutionFailure(
                    code=BacktestResolutionFailureCode.PROFILE_NOT_FOUND,
                    request_hash=normalized.request_hash,
                    subjects=missing,
                    compatibility_report=None,
                ),
            )
        resolved_market = cast(MarketSemanticsProfileRegistration, market)
        resolved_simulation = cast(SimulationProfileRegistration, simulation)
        resolved_account = cast(ExecutionAccountProfileRegistration, account)

        report = self._compatibility_report(
            normalized,
            resolved_market,
            resolved_simulation,
            resolved_account,
            market_bundle_manifest,
            build_artifact_manifest,
        )
        if not report.compatible:
            subjects = tuple(
                subject
                for check in report.checks
                if not check.passed
                for subject in check.subjects
            )
            return BacktestResolutionOutcome(
                resolved=None,
                failure=BacktestResolutionFailure(
                    code=BacktestResolutionFailureCode.INCOMPATIBLE_ENVIRONMENT,
                    request_hash=normalized.request_hash,
                    subjects=tuple(sorted(set(subjects))),
                    compatibility_report=report,
                ),
            )

        environment = ResolvedBacktestEnvironment(
            market_semantics=resolved_market,
            simulation=resolved_simulation,
            execution_account=resolved_account,
            market_bundle_ref=request.market_bundle_ref,
            compatibility_report=report,
            limitations=report.limitations,
            deployment_authorized=False,
        )
        semantic_run_id = _semantic_run_id(
            normalized, environment, build_artifact_manifest.manifest_hash
        )
        return BacktestResolutionOutcome(
            resolved=ResolvedBacktestRequest(
                request=request,
                normalized_request=normalized,
                environment=environment,
                build_artifact_manifest=build_artifact_manifest,
                semantic_run_id=semantic_run_id,
            ),
            failure=None,
        )

    @staticmethod
    def _compatibility_report(
        normalized: NormalizedBacktestRequest,
        market: MarketSemanticsProfileRegistration,
        simulation: SimulationProfileRegistration,
        account: ExecutionAccountProfileRegistration,
        bundle: MarketBundleManifest,
        build: BuildArtifactManifest,
    ) -> EnvironmentCompatibilityReport:
        request = normalized.request
        actual_bundle_ref = MarketBundleRef.from_manifest(bundle)
        identity_ok = request.market_bundle_ref == actual_bundle_ref
        identity_subjects = () if identity_ok else (
            request.market_bundle_ref.manifest_hash,
            actual_bundle_ref.manifest_hash,
        )

        coverage_ok = (
            request.timeline_window.data_start.epoch_nanoseconds
            >= bundle.coverage_start.epoch_nanoseconds
            and request.timeline_window.end_exclusive.epoch_nanoseconds
            <= bundle.coverage_end_exclusive.epoch_nanoseconds
        )
        coverage_subjects = () if coverage_ok else (
            f"request:{request.timeline_window.data_start.epoch_nanoseconds}:{request.timeline_window.end_exclusive.epoch_nanoseconds}",
            f"bundle:{bundle.coverage_start.epoch_nanoseconds}:{bundle.coverage_end_exclusive.epoch_nanoseconds}",
        )

        required_capabilities = list(market.required_bundle_capabilities)
        required_capabilities.extend(simulation.required_bundle_capabilities)
        if request.strategy_family is StrategyFamily.PRECOMPUTED_TARGET:
            required_capabilities.append(
                MarketBundleCapability("precomputed_target_stream", 1)
            )
        required_versions: dict[str, int] = {}
        for capability in required_capabilities:
            required_versions[capability.key] = max(
                required_versions.get(capability.key, 0), capability.version
            )
        available_versions = {value.key: value.version for value in bundle.capabilities}
        missing_capabilities = tuple(
            f"{key}@{version}"
            for key, version in sorted(required_versions.items())
            if available_versions.get(key, 0) < version
        )

        profile_components_ok = (
            {value.port_type for value in market.component_manifest}
            == set(ProfilePortType)
            and {value.port_type for value in simulation.component_manifest}
            == set(SimulationPortType)
        )
        component_subjects = () if profile_components_ok else (
            market.profile_key,
            simulation.profile_key,
        )

        profile_build_mismatches: list[str] = []
        for registration in (market, simulation, account):
            artifact = build.profile_artifact(registration.profile_key)
            if artifact is None or artifact.content_hash != registration.profile_digest:
                profile_build_mismatches.append(registration.profile_key)

        venue_ok = (
            market.venue_id == account.venue_id
            and request.execution_account_id == account.account_id
        )
        venue_subjects = () if venue_ok else (
            market.venue_id,
            account.venue_id,
            request.execution_account_id,
            account.account_id,
        )

        simulation_ok = (
            request.engine_kind == simulation.engine_kind
            and request.strategy_family in simulation.supported_strategy_families
        )
        simulation_subjects = () if simulation_ok else (
            request.engine_kind,
            simulation.engine_kind,
            request.strategy_family.value,
        )

        currency_ok = request.reporting_currency in account.supported_reporting_currencies
        currency_subjects = () if currency_ok else (
            request.reporting_currency.value,
            account.profile_key,
        )

        profiles_decision_grade = all(
            value.grade is RequestedResultGrade.DECISION_GRADE
            and value.decision_grade_eligible
            for value in (market, simulation, account)
        )
        grade_ok = (
            request.result_grade_requested is RequestedResultGrade.DEVELOPMENT
            or profiles_decision_grade
        )
        grade_subjects = () if grade_ok else tuple(
            value.profile_key
            for value in (market, simulation, account)
            if not value.decision_grade_eligible
        )

        build_reference_ok = (
            request.build_artifact_manifest_hash == build.manifest_hash
        )
        build_ok = build_reference_ok and build.has_required_roles and (
            request.result_grade_requested is RequestedResultGrade.DEVELOPMENT
            or build.decision_grade_eligible
        )
        build_subject_values = [
            value.artifact_key
            for value in build.artifacts
            if (
                value.install_mode is ArtifactInstallMode.EDITABLE
                or not value.has_immutable_identity
            )
        ]
        if not build_reference_ok:
            build_subject_values.extend(
                (request.build_artifact_manifest_hash, build.manifest_hash)
            )
        build_subjects = (
            () if build_ok else tuple(build_subject_values) or (build.build_key,)
        )

        limitations: set[str] = set(build.limitations)
        for value in (market, simulation, account):
            limitations.update(value.limitations)
            if value.grade is RequestedResultGrade.DEVELOPMENT:
                limitations.add("development_profile")
        allowed_grade = (
            RequestedResultGrade.DECISION_GRADE
            if profiles_decision_grade and build.decision_grade_eligible
            else RequestedResultGrade.DEVELOPMENT
        )
        checks = (
            EnvironmentCompatibilityCheck(
                EnvironmentCompatibilityCheckCode.MARKET_BUNDLE_IDENTITY,
                identity_ok,
                tuple(sorted(set(identity_subjects))),
            ),
            EnvironmentCompatibilityCheck(
                EnvironmentCompatibilityCheckCode.MARKET_BUNDLE_COVERAGE,
                coverage_ok,
                coverage_subjects,
            ),
            EnvironmentCompatibilityCheck(
                EnvironmentCompatibilityCheckCode.MARKET_BUNDLE_CAPABILITIES,
                not missing_capabilities,
                missing_capabilities,
            ),
            EnvironmentCompatibilityCheck(
                EnvironmentCompatibilityCheckCode.PROFILE_COMPONENT_COVERAGE,
                profile_components_ok,
                component_subjects,
            ),
            EnvironmentCompatibilityCheck(
                EnvironmentCompatibilityCheckCode.PROFILE_BUILD_IDENTITY,
                not profile_build_mismatches,
                tuple(profile_build_mismatches),
            ),
            EnvironmentCompatibilityCheck(
                EnvironmentCompatibilityCheckCode.VENUE_ACCOUNT_CONTEXT,
                venue_ok,
                tuple(sorted(set(venue_subjects))),
            ),
            EnvironmentCompatibilityCheck(
                EnvironmentCompatibilityCheckCode.SIMULATION_CONTEXT,
                simulation_ok,
                tuple(sorted(set(simulation_subjects))),
            ),
            EnvironmentCompatibilityCheck(
                EnvironmentCompatibilityCheckCode.REPORTING_CURRENCY,
                currency_ok,
                currency_subjects,
            ),
            EnvironmentCompatibilityCheck(
                EnvironmentCompatibilityCheckCode.PROFILE_GRADE,
                grade_ok,
                tuple(sorted(set(grade_subjects))),
            ),
            EnvironmentCompatibilityCheck(
                EnvironmentCompatibilityCheckCode.BUILD_ARTIFACT_IDENTITY,
                build_ok,
                tuple(sorted(set(build_subjects))),
            ),
        )
        return EnvironmentCompatibilityReport(
            request_hash=normalized.request_hash,
            market_bundle_manifest_hash=actual_bundle_ref.manifest_hash,
            profile_digests=(
                market.profile_digest,
                simulation.profile_digest,
                account.profile_digest,
            ),
            checks=checks,
            allowed_grade=allowed_grade,
            limitations=tuple(sorted(limitations)),
        )
