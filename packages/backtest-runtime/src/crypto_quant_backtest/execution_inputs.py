from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any

import crypto_quant_domain as domain
import crypto_quant_trading as trading
from crypto_quant_domain import (
    ArtifactCatalogError,
    ArtifactDecodeError,
    ArtifactEnvelope,
    ArtifactIntegrityError,
    ArtifactReadResult,
    ArtifactRef,
    ArtifactSchemaRegistration,
    CanonicalSchema,
    CurrencyId,
    DomainIdKind,
    IdentityNamespace,
    Scale,
    SchemaCatalog,
    TimeInForce,
    UnknownArtifactTypeError,
    UnsupportedSchemaVersionError,
    UtcInstant,
    VenueId,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_market_data import (
    InMemoryMarketBundleReader,
    InputValidationFailure,
    MarketBundleCapability,
    MarketBundleReader,
    MarketBundleRef,
)
from crypto_quant_trading import (
    LinearFundingApplicationIdentity,  # pyright: ignore[reportPrivateImportUsage]
    LinearFundingApplicationKey,  # pyright: ignore[reportPrivateImportUsage]
    SettlementBook,
)

from .composition import (
    ExecutionCaseComposer,
    _compose_execution_case,
    _compose_execution_case_from_authority,
    _execution_case_semantic_spec_v3,
    _ExecutionCasePlan,
    _HydratedExecutionCaseInputs,
)
from .decision_schedule import (
    DecisionSchedule,
    DecisionScheduleEntry,
    LookbackRequirement,
)
from .engine import (
    ExecutionCaseIdentityRule,
    ExecutionCaseSemanticSpec,
    OrderEventPlan,
    PositionLotBook,
    ResolvedBarExecution,
    ResolvedDecisionCycle,
    ResolvedExecutionCase,
    ResolvedFinancialState,
    ResolvedOrderAdmission,
    ResolvedPreTradePlan,
    SnapshotProjectionPlan,
)
from .execution import (
    BarLiquidityEvidence,
    NextBarOpenApplicability,
    NextEligibleBarOpenModel,
    NoEligibleBarAction,
)
from .financial_dispatch import (
    CashFillAccountingPlan,
    FeeAccountingDispatchPlan,
    FillAccountingDispatchPlan,
    FinancialDispatcherSpec,
    FinancialDispatchPlan,
    LinearDerivativeFillAccountingPlan,
    LinearFundingAccountEventPlan,
    LinearMarginLiquidationAuditPlan,
    ScheduledAccountEvent,
)
from .multi_resolution_market_data import (
    ExecutionDataBinding,
    MultiResolutionMarketDataBindings,
    SignalBarBinding,
    ValuationDataBinding,
    _clock,
    _record_observation,
)
from .multi_resolution_preparation import (
    MarketDataCaseAuthority,
    MarketDataPreparationOutcome,
    MultiResolutionMarketDataPreparation,
    PreparedMultiResolutionMarketData,
    SignalObservationLineageBinding,
    _bundle_ref as _rebuild_market_bundle_ref_v3,
    _event as _rebuild_market_event_v3,
    _manifest as _rebuild_market_bundle_manifest_v3,
    _prepare_multi_resolution_market_data_from_retained_v1,
)
from .observation_windows import BarDefinitionRef
from .observations import ObservationPurposeRef, ObservationQuery
from .performance_observations import (
    BoundedPerformanceRecorder,
    PerformanceOperation,
    PerformanceOutcome,
)
from .ports import (
    ArtifactEnvelopeReader,
    SimulationCapabilityRequirement,
    SimulationComponentRef,
    SimulationPortContract,
    SimulationPortSpec,
    SimulationPortType,
)
from .resolution import (
    ArtifactInstallMode,
    BacktestRequest,
    BuildArtifactManifest,
    BuildArtifactRef,
    BuildArtifactRole,
    BuildProvenance,
    NormalizedBacktestRequest,
    RequestedResultGrade,
    ResolvedBacktestEnvironment,
    ResolvedBacktestRequest,
    RuntimeLibraryRef,
    SourceTreeState,
    StrategyFamily,
)
from .run_end import (
    MarkToMarketCloseoutPolicy,
    RunEndCloseoutMode,
    _RunEndCloseoutApplicability,
)
from .slippage import (
    DeterministicBpsSlippageModel,
    SlippageApplicabilityEnvelope,
    SlippageCalibrationRef,
    SlippageLimitation,
    SlippageMarketState,
)
from .target_stream import (
    PrecomputedTargetStream,
    TargetStreamDecisionSchedule,
    TargetStreamScheduleEntry,
)
from .timeline import TimelineSegment, TimelineWindow

_ARTIFACT_TYPE = "backtest_execution_input_bundle"
_SCHEMA_VERSION = 1
_V2_SCHEMA_VERSION = 2
_V3_SCHEMA_VERSION = 3
_TEMPLATE_TYPE = "backtest_initial_financial_state_template"
_V1_SCHEMA = CanonicalSchema(_ARTIFACT_TYPE, _SCHEMA_VERSION)
_V2_SCHEMA = CanonicalSchema(_ARTIFACT_TYPE, _V2_SCHEMA_VERSION)
_V3_SCHEMA = CanonicalSchema(_ARTIFACT_TYPE, _V3_SCHEMA_VERSION)
_PAYLOAD_FIELDS = frozenset(
    {
        "type",
        "schema_version",
        "request_hash",
        "build_artifact_manifest",
        "execution_case_semantic_spec",
        "timeline_stream_keys",
        "target_stream_key",
        "timeline_batch_size",
        "initial_financial_state_template",
    }
)
_V2_PAYLOAD_FIELDS = frozenset(
    {
        "type",
        "schema_version",
        "request_hash",
        "semantic_run_id",
        "build_artifact_manifest",
        "execution_case_semantic_spec",
        "timeline_stream_keys",
        "target_stream_key",
        "timeline_batch_size",
        "execution_case_plan",
    }
)
_V3_PAYLOAD_FIELDS = _V2_PAYLOAD_FIELDS | {"market_data_preparation"}
_PLAN_FIELDS = frozenset(
    {
        "type",
        "schema_version",
        "decision_cycles",
        "bar_executions",
        "financial_state",
        "financial_dispatch_plan",
        "execution_model_spec",
        "snapshot_plan",
        "closeout_policy_spec",
    }
)
_TEMPLATE_FIELDS = frozenset(
    {
        "type",
        "schema_version",
        "journal_entry_templates",
        "ledger_schema",
        "initial_snapshot_template",
        "lot_books",
        "order_streams",
        "order_admissions",
        "reservation_schedules",
        "settlement_state",
        "settlement_rules",
    }
)
_FORBIDDEN_TEMPLATE_KEYS = frozenset(
    {"journal_entry_id", "journal_state_hash", "settlement_book_hash"}
)


class _ExecutionInputsHydrationFailureCode(str, Enum):
    MALFORMED_EXECUTION_REQUEST = "malformed_execution_request"
    WRONG_EXECUTION_INPUT_BUNDLE_REF = "wrong_execution_input_bundle_ref"
    EXECUTION_INPUT_UNAVAILABLE = "execution_input_unavailable"
    EXECUTION_INPUT_TAMPERED = "execution_input_tampered"
    EXECUTION_INPUT_DECODE_FAILED = "execution_input_decode_failed"
    REQUEST_BINDING_MISMATCH = "request_binding_mismatch"
    BUILD_BINDING_MISMATCH = "build_binding_mismatch"
    TARGET_BINDING_MISMATCH = "target_binding_mismatch"
    INITIAL_STATE_BINDING_MISMATCH = "initial_state_binding_mismatch"
    EXECUTION_CASE_SEMANTIC_HASH_MISMATCH = (
        "execution_case_semantic_hash_mismatch"
    )


class _ExecutionInputsHydrationFailureCodeV3(str, Enum):
    MALFORMED_EXECUTION_REQUEST = "malformed_execution_request"
    WRONG_EXECUTION_INPUT_BUNDLE_REF = "wrong_execution_input_bundle_ref"
    EXECUTION_INPUT_UNAVAILABLE = "execution_input_unavailable"
    EXECUTION_INPUT_TAMPERED = "execution_input_tampered"
    EXECUTION_INPUT_DECODE_FAILED = "execution_input_decode_failed"
    REQUEST_BINDING_MISMATCH = "request_binding_mismatch"
    BUILD_BINDING_MISMATCH = "build_binding_mismatch"
    TARGET_BINDING_MISMATCH = "target_binding_mismatch"
    PREPARED_MARKET_DATA_BINDING_MISMATCH = (
        "prepared_market_data_binding_mismatch"
    )
    PREPARED_MARKET_DATA_REPLAY_MISMATCH = "prepared_market_data_replay_mismatch"
    EXECUTION_CASE_SEMANTIC_HASH_MISMATCH = (
        "execution_case_semantic_hash_mismatch"
    )


@dataclass(frozen=True, slots=True)
class _ExecutionInputsHydrationFailureV3:
    code: _ExecutionInputsHydrationFailureCodeV3
    role_position: int | None = None
    schedule_entry_position: int | None = None
    requirement_position: int | None = None
    event_position: int | None = None

    def __post_init__(self) -> None:
        if type(self.code) is not _ExecutionInputsHydrationFailureCodeV3:
            raise TypeError("code must be exact v3 hydration failure code")
        for name in (
            "role_position",
            "schedule_entry_position",
            "requirement_position",
            "event_position",
        ):
            value = getattr(self, name)
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError(f"{name} must be a non-negative exact integer or None")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "execution_inputs_hydration_failure_v3",
            "schema_version": 3,
            "code": self.code.value,
            "role_position": self.role_position,
            "schedule_entry_position": self.schedule_entry_position,
            "requirement_position": self.requirement_position,
            "event_position": self.event_position,
        }


@dataclass(frozen=True, slots=True)
class _ExecutionInputsHydrationFailure:
    code: _ExecutionInputsHydrationFailureCode
    message: str


@dataclass(frozen=True, slots=True)
class _HydratedExecutionInputs:
    build_artifact_manifest: BuildArtifactManifest
    execution_case_semantic_spec: ExecutionCaseSemanticSpec
    timeline_stream_keys: tuple[str, ...]
    target_stream: PrecomputedTargetStream
    timeline_batch_size: int
    initial_financial_state_template: Mapping[str, Any] | None = None
    execution_case_plan: _ExecutionCasePlan | None = None
    execution_case: ResolvedExecutionCase | None = None


@dataclass(frozen=True, slots=True)
class _ExecutionInputsHydrationOutcome:
    result: _HydratedExecutionInputs | None = None
    failure: _ExecutionInputsHydrationFailure | None = None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.failure is None):
            raise ValueError("hydration outcome requires exactly one result or failure")


@dataclass(frozen=True, slots=True)
class _HydratedExecutionInputsV3:
    build_artifact_manifest: BuildArtifactManifest
    execution_case_semantic_spec: ExecutionCaseSemanticSpec
    timeline_stream_keys: tuple[str, ...]
    target_stream: PrecomputedTargetStream
    timeline_batch_size: int
    execution_case_plan: _ExecutionCasePlan
    market_data_preparation: MultiResolutionMarketDataPreparation

    def __post_init__(self) -> None:
        if type(self.build_artifact_manifest) is not BuildArtifactManifest:
            raise TypeError("build_artifact_manifest must be exact BuildArtifactManifest")
        if type(self.execution_case_semantic_spec) is not ExecutionCaseSemanticSpec:
            raise TypeError("execution_case_semantic_spec must be exact ExecutionCaseSemanticSpec")
        if type(self.execution_case_plan) is not _ExecutionCasePlan:
            raise TypeError("execution_case_plan must be exact _ExecutionCasePlan")
        if type(self.market_data_preparation) is not MultiResolutionMarketDataPreparation:
            raise TypeError("market_data_preparation must be exact MultiResolutionMarketDataPreparation")


@dataclass(frozen=True, slots=True)
class _ExecutionInputsHydrationOutcomeV3:
    result: _HydratedExecutionInputsV3 | None = None
    failure: _ExecutionInputsHydrationFailureV3 | None = None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.failure is None):
            raise ValueError("v3 hydration outcome requires exactly one result or failure")
        if self.result is not None and type(self.result) is not _HydratedExecutionInputsV3:
            raise TypeError("result must be exact _HydratedExecutionInputsV3 or None")
        if self.failure is not None and type(self.failure) is not _ExecutionInputsHydrationFailureV3:
            raise TypeError("failure must be exact _ExecutionInputsHydrationFailureV3 or None")


@dataclass(frozen=True, slots=True)
class _DecodedExecutionInputBundle:
    request_hash: str
    build_artifact_manifest: BuildArtifactManifest
    execution_case_semantic_spec: ExecutionCaseSemanticSpec
    timeline_stream_keys: tuple[str, ...]
    target_stream_key: str
    timeline_batch_size: int
    initial_financial_state_template: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class _DecodedExecutionInputBundleV2:
    request_hash: str
    semantic_run_id: str
    build_artifact_manifest: BuildArtifactManifest
    execution_case_semantic_spec: ExecutionCaseSemanticSpec
    timeline_stream_keys: tuple[str, ...]
    target_stream_key: str
    timeline_batch_size: int
    execution_case_plan: _ExecutionCasePlan


@dataclass(frozen=True, slots=True)
class _DecodedExecutionInputBundleV3:
    request_hash: str
    semantic_run_id: str
    build_artifact_manifest: BuildArtifactManifest
    execution_case_semantic_spec: ExecutionCaseSemanticSpec
    timeline_stream_keys: tuple[str, ...]
    target_stream_key: str
    timeline_batch_size: int
    execution_case_plan: _ExecutionCasePlan
    market_data_preparation: MultiResolutionMarketDataPreparation


@dataclass(frozen=True, slots=True)
class BacktestExecutionRequest:
    schema_version: int
    request: BacktestRequest
    execution_input_bundle_ref: ArtifactRef

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version not in (
            _SCHEMA_VERSION,
            _V2_SCHEMA_VERSION,
            _V3_SCHEMA_VERSION,
        ):
            raise ValueError("BacktestExecutionRequest schema_version must be 1, 2, or 3")
        if type(self.request) is not BacktestRequest:
            raise TypeError("request must be exact BacktestRequest")
        if type(self.execution_input_bundle_ref) is not ArtifactRef:
            raise TypeError("execution_input_bundle_ref must be exact ArtifactRef")
        if (
            self.execution_input_bundle_ref.artifact_type != _ARTIFACT_TYPE
            or self.execution_input_bundle_ref.schema_version != self.schema_version
        ):
            raise ValueError(
                "execution_input_bundle_ref must target "
                f"backtest_execution_input_bundle@{self.schema_version}"
            )

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "backtest_execution_request",
            "schema_version": self.schema_version,
            "request": self.request,
            "execution_input_bundle_ref": self.execution_input_bundle_ref,
        }


def _mapping(name: str, value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    if not all(type(key) is str for key in value):
        raise TypeError(f"{name} keys must be strings")
    return value


def _exact_fields(name: str, value: Mapping[str, Any], fields: frozenset[str]) -> None:
    if set(value) != fields:
        raise ValueError(f"{name} must contain exactly {', '.join(sorted(fields))}")


def _text(name: str, value: object) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(f"{name} must be canonical non-empty text")
    return value


def _positive_int(name: str, value: object) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _utc_instant(name: str, value: object) -> UtcInstant:
    data = _mapping(name, value)
    _exact_fields(name, data, frozenset({"type", "epoch_nanoseconds"}))
    if data["type"] != "utc_instant" or type(data["epoch_nanoseconds"]) is not int:
        raise ValueError(f"{name} must be canonical UtcInstant")
    return UtcInstant(data["epoch_nanoseconds"])


def _contains_key(value: object, keys: frozenset[str]) -> bool:
    if isinstance(value, Mapping):
        return any(key in keys or _contains_key(child, keys) for key, child in value.items())
    if isinstance(value, (list, tuple)):
        return any(_contains_key(child, keys) for child in value)
    return False


def _stream_keys(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise TypeError("timeline_stream_keys must be a list or tuple")
    keys = tuple(_text("timeline_stream_key", item) for item in value)
    if not keys or keys != tuple(sorted(keys)) or len(set(keys)) != len(keys):
        raise ValueError("timeline_stream_keys must be nonempty, sorted, and unique")
    return keys


def _initial_journal_bindings(
    template: Mapping[str, Any], spec: ExecutionCaseSemanticSpec
) -> tuple[str, ...]:
    entries = template["journal_entry_templates"]
    if not isinstance(entries, (list, tuple)):
        raise TypeError("journal_entry_templates must be a list or tuple")
    bindings: list[str] = []
    base_fields = frozenset(
        {
            "identity_binding_key",
            "type",
            "entry_type",
            "account_id",
            "venue_id",
            "effective_time",
            "recorded_at",
            "source_ids",
            "balance_changes",
            "realized_pnl",
            "fees",
            "financing",
        }
    )
    lot_fields = base_fields | {"schema_version", "position_lot_changes"}
    for entry_value in entries:
        entry = _mapping("journal_entry_template", entry_value)
        expected_fields = lot_fields if "position_lot_changes" in entry else base_fields
        _exact_fields("journal_entry_template", entry, expected_fields)
        if entry.get("type") != "accounting_journal_entry":
            raise ValueError("initial journal entries must be base AccountingJournalEntry payloads")
        if "position_lot_changes" in entry and entry.get("schema_version") != 2:
            raise ValueError("position-lot journal templates must use schema_version 2")
        for field_name in (
            "source_ids",
            "balance_changes",
            "realized_pnl",
            "fees",
            "financing",
            "position_lot_changes",
        ):
            if field_name in entry and not isinstance(entry[field_name], (list, tuple)):
                raise TypeError(f"{field_name} must be a list or tuple")
        binding = _text("identity_binding_key", entry.get("identity_binding_key"))
        bindings.append(binding)
    if len(set(bindings)) != len(bindings):
        raise ValueError("initial journal identity_binding_key values must be unique")

    expected = tuple(
        sorted(
            rule.binding_key
            for rule in spec.identity_plan
            if rule.domain_kind is DomainIdKind.JOURNAL
            and rule.binding_key.startswith("journal.initial.")
        )
    )
    actual = tuple(sorted(bindings))
    if actual != expected:
        raise ValueError("initial journal entries must exact-cover journal.initial identity_plan bindings")
    return actual


def _validate_initial_template(
    value: object,
    spec: ExecutionCaseSemanticSpec,
    request: BacktestRequest | None = None,
) -> Mapping[str, Any]:
    template = _mapping("initial_financial_state_template", value)
    _exact_fields("initial_financial_state_template", template, _TEMPLATE_FIELDS)
    if template["type"] != _TEMPLATE_TYPE or template["schema_version"] != _SCHEMA_VERSION:
        raise ValueError("initial financial state template must be backtest_initial_financial_state_template@1")
    if _contains_key(template, _FORBIDDEN_TEMPLATE_KEYS):
        raise ValueError("initial financial state template contains a derived identity or hash")

    snapshot = _mapping("initial_snapshot_template", template["initial_snapshot_template"])
    if snapshot.get("type") != "portfolio_snapshot":
        raise ValueError("initial_snapshot_template must be a PortfolioSnapshot payload")
    typed_mappings = (
        ("ledger_schema", "ledger_schema"),
        ("settlement_state", "settlement_book_state"),
        ("settlement_rules", "market_settlement_rules"),
    )
    for field_name, type_name in typed_mappings:
        child = _mapping(field_name, template[field_name])
        if child.get("type") != type_name:
            raise ValueError(f"{field_name} must use type {type_name}")
    typed_sequences = (
        ("lot_books", "position_lot_book"),
        ("order_streams", "order_event_stream"),
        ("order_admissions", "resolved_order_admission"),
        ("reservation_schedules", "order_reservation_schedule"),
    )
    for field_name, type_name in typed_sequences:
        values = template[field_name]
        if not isinstance(values, (list, tuple)):
            raise TypeError(f"{field_name} must be a list or tuple")
        for child_value in values:
            child = _mapping(field_name, child_value)
            if child.get("type") != type_name:
                raise ValueError(f"{field_name} entries must use type {type_name}")
    _initial_journal_bindings(template, spec)

    if request is not None:
        account_ids: set[str] = set()

        def collect_accounts(item: object) -> None:
            if isinstance(item, Mapping):
                if "account_id" in item:
                    account_ids.add(_text("account_id", item["account_id"]))
                for child in item.values():
                    collect_accounts(child)
            elif isinstance(item, (list, tuple)):
                for child in item:
                    collect_accounts(child)

        collect_accounts(template)
        if account_ids != {request.execution_account_id}:
            raise ValueError("initial financial state account IDs must bind the request account")
        reporting = _mapping("reporting_currency", snapshot.get("reporting_currency"))
        if reporting.get("type") != "currency_id" or reporting.get("value") != request.reporting_currency.value:
            raise ValueError("initial snapshot reporting currency must bind the request")
    return template


def _read_build_manifest(value: object) -> BuildArtifactManifest:
    manifest_value = _mapping("build_artifact_manifest", value)
    _exact_fields(
        "build_artifact_manifest",
        manifest_value,
        frozenset({"type", "identity", "provenance", "manifest_hash"}),
    )
    if manifest_value["type"] != "build_artifact_manifest":
        raise ValueError("invalid BuildArtifactManifest type")

    identity = _mapping("build_artifact_manifest.identity", manifest_value["identity"])
    _exact_fields(
        "build_artifact_manifest.identity",
        identity,
        frozenset(
            {
                "type",
                "schema_version",
                "build_key",
                "artifacts",
                "dependency_lock_hash",
                "runtime_libraries",
                "container_image_digest",
            }
        ),
    )
    if identity["type"] != "build_artifact_manifest_identity":
        raise ValueError("invalid build manifest identity type")

    artifacts_value = identity["artifacts"]
    if not isinstance(artifacts_value, (list, tuple)):
        raise TypeError("build artifacts must be a list or tuple")
    artifacts: list[BuildArtifactRef] = []
    artifact_fields = frozenset(
        {
            "type",
            "role",
            "artifact_key",
            "artifact_version",
            "install_mode",
            "source_tree_state",
            "content_hash",
            "source_snapshot_hash",
        }
    )
    for item in artifacts_value:
        data = _mapping("build_artifact_ref", item)
        _exact_fields("build_artifact_ref", data, artifact_fields)
        if data["type"] != "build_artifact_ref":
            raise ValueError("invalid BuildArtifactRef type")
        artifacts.append(
            BuildArtifactRef(
                role=BuildArtifactRole(data["role"]),
                artifact_key=data["artifact_key"],
                artifact_version=data["artifact_version"],
                install_mode=ArtifactInstallMode(data["install_mode"]),
                source_tree_state=SourceTreeState(data["source_tree_state"]),
                content_hash=data["content_hash"],
                source_snapshot_hash=data["source_snapshot_hash"],
            )
        )

    libraries_value = identity["runtime_libraries"]
    if not isinstance(libraries_value, (list, tuple)):
        raise TypeError("runtime_libraries must be a list or tuple")
    libraries: list[RuntimeLibraryRef] = []
    for item in libraries_value:
        data = _mapping("runtime_library_ref", item)
        _exact_fields(
            "runtime_library_ref",
            data,
            frozenset({"type", "library_key", "version", "content_hash"}),
        )
        if data["type"] != "runtime_library_ref":
            raise ValueError("invalid RuntimeLibraryRef type")
        libraries.append(
            RuntimeLibraryRef(data["library_key"], data["version"], data["content_hash"])
        )

    provenance_value = _mapping("build_provenance", manifest_value["provenance"])
    _exact_fields(
        "build_provenance",
        provenance_value,
        frozenset({"type", "git_commit", "hostname", "source_root", "built_at"}),
    )
    if provenance_value["type"] != "build_provenance":
        raise ValueError("invalid BuildProvenance type")
    provenance = BuildProvenance(
        git_commit=provenance_value["git_commit"],
        hostname=provenance_value["hostname"],
        source_root=provenance_value["source_root"],
        built_at=_utc_instant("build_provenance.built_at", provenance_value["built_at"]),
    )

    manifest = BuildArtifactManifest(
        schema_version=identity["schema_version"],
        build_key=identity["build_key"],
        artifacts=tuple(artifacts),
        dependency_lock_hash=identity["dependency_lock_hash"],
        runtime_libraries=tuple(libraries),
        container_image_digest=identity["container_image_digest"],
        provenance=provenance,
    )
    if manifest_value["manifest_hash"] != manifest.manifest_hash:
        raise ValueError("BuildArtifactManifest manifest_hash mismatch")
    if canonical_bytes(manifest_value) != canonical_bytes(manifest):
        raise ValueError("BuildArtifactManifest did not reconstruct exactly")
    return manifest


def _read_semantic_spec(value: object) -> ExecutionCaseSemanticSpec:
    data = _mapping("execution_case_semantic_spec", value)
    fields = frozenset(
        {
            "type",
            "schema_version",
            "spec_key",
            "spec_version",
            "case_key",
            "case_version",
            "identity_namespace",
            "identity_plan",
            "timeline_semantic_hash",
            "target_stream_digest",
            "decision_inputs_hash",
            "execution_inputs_hash",
            "financial_inputs_hash",
            "snapshot_inputs_hash",
            "run_end_inputs_hash",
        }
    )
    _exact_fields("execution_case_semantic_spec", data, fields)
    if data["type"] != "execution_case_semantic_spec":
        raise ValueError("invalid ExecutionCaseSemanticSpec type")

    namespace_value = _mapping("identity_namespace", data["identity_namespace"])
    _exact_fields(
        "identity_namespace",
        namespace_value,
        frozenset({"value", "version", "algorithm"}),
    )
    namespace = IdentityNamespace(
        namespace_value["value"], namespace_value["version"], namespace_value["algorithm"]
    )

    plan_value = data["identity_plan"]
    if not isinstance(plan_value, (list, tuple)):
        raise TypeError("identity_plan must be a list or tuple")
    plan: list[ExecutionCaseIdentityRule] = []
    for item in plan_value:
        rule = _mapping("identity_rule", item)
        _exact_fields(
            "identity_rule",
            rule,
            frozenset(
                {"binding_key", "identity_type", "domain_kind", "semantic_key", "ordinal"}
            ),
        )
        domain_kind = (
            DomainIdKind(rule["domain_kind"])
            if rule["domain_kind"] is not None
            else None
        )
        expected_identity_type = "domain_id" if domain_kind is not None else "event_id"
        if rule["identity_type"] != expected_identity_type:
            raise ValueError("identity_type does not match domain_kind")
        plan.append(
            ExecutionCaseIdentityRule(
                binding_key=rule["binding_key"],
                semantic_key=rule["semantic_key"],
                ordinal=rule["ordinal"],
                domain_kind=domain_kind,
            )
        )

    spec = ExecutionCaseSemanticSpec(
        schema_version=data["schema_version"],
        spec_key=data["spec_key"],
        spec_version=data["spec_version"],
        case_key=data["case_key"],
        case_version=data["case_version"],
        identity_namespace=namespace,
        identity_plan=tuple(plan),
        timeline_semantic_hash=data["timeline_semantic_hash"],
        target_stream_digest=data["target_stream_digest"],
        decision_inputs_hash=data["decision_inputs_hash"],
        execution_inputs_hash=data["execution_inputs_hash"],
        financial_inputs_hash=data["financial_inputs_hash"],
        snapshot_inputs_hash=data["snapshot_inputs_hash"],
        run_end_inputs_hash=data["run_end_inputs_hash"],
    )
    if canonical_bytes(data) != canonical_bytes(spec):
        raise ValueError("ExecutionCaseSemanticSpec did not reconstruct exactly")
    return spec


def _tagged(name: str, value: object, expected_type: str) -> Mapping[str, Any]:
    data = _mapping(name, value)
    if data.get("type") != expected_type:
        raise ValueError(f"{name} must use type {expected_type}")
    return data


def _sequence(
    name: str, value: object, reader: Callable[[object], Any]
) -> tuple[Any, ...]:
    if not isinstance(value, (list, tuple)):
        raise TypeError(f"{name} must be a list or tuple")
    return tuple(reader(item) for item in value)


def _empty_sequence(name: str, value: object) -> tuple[()]:
    values = _sequence(name, value, lambda item: item)
    if values:
        raise ValueError(f"{name} is unsupported in execution case plan v1")
    return ()


def _optional(value: object, reader: Callable[[object], Any]) -> Any:
    return None if value is None else reader(value)


def _read_currency(value: object) -> CurrencyId:
    data = _tagged("currency_id", value, "currency_id")
    return CurrencyId(data["value"])


def _read_venue(value: object) -> VenueId:
    if type(value) is str:
        return VenueId(value)
    data = _tagged("venue_id", value, "venue_id")
    return VenueId(data["value"])


def _read_instrument_id(value: object) -> domain.InstrumentId:
    data = _tagged("instrument_id", value, "instrument_id")
    return domain.InstrumentId(_read_venue(data["venue"]), data["stable_key"])


def _read_utc(value: object) -> UtcInstant:
    return _utc_instant("utc_instant", value)


def _read_source_sequence(value: object) -> domain.SourceSequence:
    data = _tagged("source_sequence", value, "source_sequence")
    return domain.SourceSequence(data["value"])


def _read_timeline_phase(value: object) -> domain.TimelinePhase:
    data = _tagged("timeline_phase", value, "timeline_phase")
    return domain.TimelinePhase(data["rank"], data["code"])


def _read_simulation_instant(value: object) -> domain.SimulationInstant:
    data = _tagged("simulation_instant", value, "simulation_instant")
    return domain.SimulationInstant(
        _read_utc(data["instant"]),
        _read_timeline_phase(data["phase"]),
        _read_source_sequence(data["source_sequence"]),
    )


def _read_money(value: object) -> domain.Money:
    data = _tagged("money", value, "money")
    return domain.Money(data["units"], Scale(data["scale"]), data["currency"])


def _read_price(value: object) -> domain.Price:
    data = _tagged("price", value, "price")
    return domain.Price(
        data["units"],
        Scale(data["scale"]),
        data["instrument_id"],
        data["quote_currency"],
    )


def _read_quantity(value: object) -> domain.Quantity:
    data = _tagged("quantity", value, "quantity")
    return domain.Quantity(
        data["units"], Scale(data["scale"]), data["instrument_id"]
    )


def _read_rate(value: object) -> domain.Rate:
    data = _tagged("rate", value, "rate")
    return domain.Rate(
        data["units"], Scale(data["scale"]), data.get("basis", "fraction")
    )


def _read_quantization(value: object) -> domain.QuantizationPolicy:
    data = _tagged("quantization_policy", value, "quantization_policy")
    return domain.QuantizationPolicy(
        data["version"],
        Scale(data["target_scale"]),
        domain.RoundingPolicy(data["rounding"]),
    )


def _read_domain_id(value: object) -> domain.DomainId:
    data = _tagged("domain_id", value, "domain_id")
    return domain.DomainId(domain.DomainIdKind(data["kind"]), data["value"])


def _read_cash_key(value: object) -> domain.CashBalanceKey:
    data = _tagged("cash_balance_key", value, "cash_balance_key")
    return domain.CashBalanceKey(
        data["account_id"],
        _read_venue(data["venue_id"]),
        _read_currency(data["currency_id"]),
    )


def _read_position_key(value: object) -> domain.PositionBalanceKey:
    data = _tagged("position_balance_key", value, "position_balance_key")
    return domain.PositionBalanceKey(
        data["account_id"],
        _read_venue(data["venue_id"]),
        _read_instrument_id(data["instrument_id"]),
    )


def _read_balance_key(
    value: object,
) -> domain.CashBalanceKey | domain.PositionBalanceKey:
    data = _mapping("balance_key", value)
    if data.get("type") == "cash_balance_key":
        return _read_cash_key(data)
    if data.get("type") == "position_balance_key":
        return _read_position_key(data)
    raise ValueError("balance_key must be cash_balance_key or position_balance_key")


def _read_profile_component_ref(value: object) -> trading.ProfileComponentRef:
    data = _tagged("profile_component_ref", value, "profile_component_ref")
    return trading.ProfileComponentRef(
        trading.ProfilePortType(data["port_type"]),
        data["component_key"],
        data["component_version"],
        data["component_digest"],
    )


def _read_simulation_component_ref(value: object) -> SimulationComponentRef:
    data = _tagged("simulation_component_ref", value, "simulation_component_ref")
    return SimulationComponentRef(
        SimulationPortType(data["port_type"]),
        data["component_key"],
        data["component_version"],
        data["component_digest"],
    )


def _read_quantity_lattice(value: object) -> trading.QuantityLattice:
    data = _tagged("quantity_lattice", value, "quantity_lattice")
    return trading.QuantityLattice(
        _read_instrument_id(data["instrument_id"]),
        data["lattice_key"],
        data["lattice_version"],
        Scale(data["atomic_scale"]),
        data["step_units"],
        data["buy_lot_units"],
        data["sell_lot_units"],
        data["min_quantity_units"],
        _read_money(data["min_notional"]),
        data["odd_lot_close_permitted"],
        data["config_hash"],
        data.get("whole_sell_residual_permitted", False),
    )


def _read_resolved_mark(value: object) -> trading.ResolvedMark:
    data = _tagged("resolved_mark", value, "resolved_mark")
    return trading.ResolvedMark(
        _read_instrument_id(data["instrument_id"]),
        _read_currency(data["quote_currency_id"]),
        domain.PricePurpose(data["price_purpose"]),
        _read_price(data["price"]),
        _read_utc(data["observed_at"]),
        _read_utc(data["available_at"]),
        _read_utc(data["resolved_at"]),
        data["age_nanoseconds"],
        data["stream_id"],
        data["source_event_id"],
        data["revision_id"],
        data["stale_policy_key"],
        data["stale_policy_version"],
        data["stale_policy_hash"],
    )


def _read_sizing_input(value: object) -> trading.InstrumentSizingInput:
    data = _tagged("instrument_sizing_input", value, "instrument_sizing_input")
    return trading.InstrumentSizingInput(
        _read_instrument_id(data["instrument_id"]),
        _read_resolved_mark(data["mark"]),
        _read_quantity(data["current_quantity"]),
        _read_quantity_lattice(data["lattice"]),
    )


def _read_validation_catalog(
    value: Mapping[str, Any],
    sizing_inputs: tuple[trading.InstrumentSizingInput, ...],
) -> domain.InstrumentCatalog:
    universe = _sequence("validation universe", value["universe"], _read_instrument_id)
    definitions: list[domain.InstrumentDefinition] = []
    currencies: set[CurrencyId] = set()
    for instrument_id in universe:
        sizing_input = next(
            (
                item
                for item in sizing_inputs
                if item.instrument_id == instrument_id
            ),
            None,
        )
        if sizing_input is None:
            raise ValueError("validation universe must exact-cover sizing inputs")
        parts = instrument_id.stable_key.split(":", 1)
        symbols = parts[1].split("-", 1) if len(parts) == 2 else []
        if parts[0] != "cash" or len(symbols) != 2:
            raise ValueError("execution case plan v1 supports exact cash instrument catalogs")
        base = CurrencyId(symbols[0].upper())
        quote = sizing_input.mark.quote_currency_id
        if symbols[1].upper() != quote.value:
            raise ValueError("instrument catalog quote currency mismatch")
        currencies.update((base, quote))
        definitions.append(
            domain.InstrumentDefinition(
                instrument_id,
                domain.InstrumentType.SPOT,
                base,
                quote,
                quote,
            )
        )
    catalog = domain.InstrumentCatalog(
        tuple(sorted(currencies, key=lambda item: item.value)),
        tuple(definitions),
        (),
    )
    if canonical_sha256(catalog) != value["instrument_catalog_hash"]:
        raise ValueError("validation instrument catalog hash mismatch")
    return catalog


def _read_schedule_entry(
    value: object,
    sizing_inputs: tuple[trading.InstrumentSizingInput, ...],
) -> TargetStreamScheduleEntry:
    data = _tagged(
        "target_stream_schedule_entry", value, "target_stream_schedule_entry"
    )
    expectation_value = _tagged(
        "decision_batch_expectation",
        data["expectation"],
        "decision_batch_expectation",
    )
    expectation = trading.DecisionBatchExpectation(
        expectation_value["strategy_id"],
        domain.StrategySleeveId(expectation_value["sleeve_id"]["value"]),
    )
    context_value = _mapping("validation_context", data["validation_context"])
    context = trading.StrategyOutputValidationContext(
        context_value["expected_strategy_id"],
        domain.StrategySleeveId(context_value["expected_sleeve_id"]["value"]),
        _read_utc(context_value["decision_time"]),
        _read_validation_catalog(context_value, sizing_inputs),
        _sequence("validation universe", context_value["universe"], _read_instrument_id),
    )
    return TargetStreamScheduleEntry(data["event_id"], expectation, context)


def _read_schedule(
    value: object,
    sizing_inputs: tuple[trading.InstrumentSizingInput, ...],
) -> TargetStreamDecisionSchedule:
    data = _tagged(
        "target_stream_decision_schedule",
        value,
        "target_stream_decision_schedule",
    )
    entries = _sequence(
        "target stream schedule entries",
        data["entries"],
        lambda item: _read_schedule_entry(item, sizing_inputs),
    )
    return TargetStreamDecisionSchedule(
        _read_utc(data["decision_time"]),
        TimelineSegment(data["segment"]),
        entries,
    )


def _read_capital_policy_ref(value: object) -> trading.CapitalAllocationPolicyRef:
    data = _tagged(
        "capital_allocation_policy_ref", value, "capital_allocation_policy_ref"
    )
    return trading.CapitalAllocationPolicyRef(
        data["policy_key"], data["policy_version"], data["config_hash"]
    )


def _read_allocation(value: object) -> trading.StrategyAllocation:
    data = _tagged("strategy_allocation", value, "strategy_allocation")
    return trading.StrategyAllocation(
        data["strategy_id"],
        domain.StrategySleeveId(data["sleeve_id"]["value"]),
        _read_utc(data["valuation_time"]),
        _read_currency(data["valuation_currency"]),
        _read_money(data["allocation_nav"]),
        _read_capital_policy_ref(data["policy_ref"]),
        data["source_portfolio_snapshot_hash"],
    )


def _read_portfolio_risk_limit(value: object) -> trading.PortfolioRiskLimit:
    data = _tagged("portfolio_risk_limit", value, "portfolio_risk_limit")
    return trading.PortfolioRiskLimit(
        data["limit_id"],
        trading.PortfolioRiskScope(data["scope"]),
        _read_money(data["maximum"]),
        trading.PortfolioRiskAction(data["breach_action"]),
        _optional(data["instrument_id"], _read_instrument_id),
    )


def _read_portfolio_risk_policy(value: object) -> trading.PortfolioRiskPolicy:
    data = _tagged("portfolio_risk_policy", value, "portfolio_risk_policy")
    ref_value = _tagged(
        "portfolio_risk_policy_ref",
        data["policy_ref"],
        "portfolio_risk_policy_ref",
    )
    return trading.PortfolioRiskPolicy(
        trading.PortfolioRiskPolicyRef(
            ref_value["policy_key"],
            ref_value["policy_version"],
            ref_value["config_hash"],
        ),
        _read_currency(data["valuation_currency"]),
        Scale(data["notional_scale"]),
        _sequence("portfolio risk limits", data["limits"], _read_portfolio_risk_limit),
    )


def _read_sizing_policy(value: object) -> trading.PositionSizingPolicy:
    data = _tagged("position_sizing_policy", value, "position_sizing_policy")
    return trading.PositionSizingPolicy(
        data["policy_key"],
        data["policy_version"],
        domain.PricePurpose(data["price_purpose"]),
        domain.RoundingPolicy(data["rounding"]),
        trading.ResidualPositionPolicy(data["residual_policy"]),
        data["config_hash"],
    )


def _read_target_validity(value: object) -> trading.TargetValidity:
    data = _tagged("target_validity", value, "target_validity")
    return trading.TargetValidity(
        data["normalized_target_id"],
        data["normalized_target_hash"],
        _read_utc(data["valid_from"]),
        _optional(data["valid_until"], _read_utc),
    )


def _read_rebalance_policy(value: object) -> trading.RebalancePolicy:
    data = _tagged("rebalance_policy", value, "rebalance_policy")
    return trading.RebalancePolicy(
        data["policy_key"],
        data["policy_version"],
        domain.ExecutionStyle(data["execution_style"]),
        TimeInForce(data["time_in_force"]),
        data["urgency"],
        data["plan_valid_for_nanoseconds"],
        data["config_hash"],
    )


def _read_order(value: object) -> domain.Order:
    data = _tagged("order", value, "order")
    intent_value = _tagged("order_intent", data["intent"], "order_intent")
    intent = domain.OrderIntent(
        _read_instrument_id(intent_value["instrument_id"]),
        domain.OrderSide(intent_value["side"]),
        _read_quantity(intent_value["quantity"]),
        domain.ExecutionStyle(intent_value["execution_style"]),
        None,
        TimeInForce(intent_value["time_in_force"]),
        intent_value["reduce_only"],
        domain.PositionEffect(intent_value["position_effect"]),
        intent_value["urgency"],
        intent_value["reason"],
        intent_value["parent_id"],
    )
    if intent_value["price_constraint"] is not None:
        raise ValueError("execution case plan v1 requires no price constraint")
    return domain.Order(
        _read_domain_id(data["order_id"]),
        data["account_id"],
        intent,
        _read_simulation_instant(data["created_at"]),
    )


def _read_fill(value: object) -> domain.Fill:
    data = _tagged("fill", value, "fill")
    return domain.Fill(
        _read_domain_id(data["fill_id"]),
        _read_domain_id(data["order_id"]),
        data["account_id"],
        _read_venue(data["venue_id"]),
        _read_instrument_id(data["instrument_id"]),
        domain.OrderSide(data["side"]),
        _read_quantity(data["quantity"]),
        _read_price(data["reference_price"]),
        domain.PricePurpose(data["reference_price_purpose"]),
        _read_price(data["price"]),
        _read_money(data["slippage_amount"]),
        data["slippage_decision_id"],
        data["slippage_model_key"],
        data["slippage_calibration_id"],
        data["liquidity"],
        _read_utc(data["execution_time"]),
    )


def _read_order_event(value: object) -> domain.OrderEvent:
    data = _tagged("order_event", value, "order_event")
    return domain.OrderEvent(
        data["event_id"],
        _read_domain_id(data["order_id"]),
        data["causation_id"],
        domain.OrderEventType(data["event_type"]),
        _read_simulation_instant(data["occurred_at"]),
        _optional(data["fill_id"], _read_domain_id),
        data["evidence_id"],
        data["reason_code"],
    )


def _read_order_event_record(value: object) -> trading.OrderEventRecord:
    data = _tagged("order_event_record", value, "order_event_record")
    return trading.OrderEventRecord(
        _read_order_event(data["event"]),
        _optional(data["fill"], _read_fill),
    )


def _read_order_event_stream(value: object) -> trading.OrderEventStream:
    data = _tagged("order_event_stream", value, "order_event_stream")
    stream = trading.OrderEventStream.from_records(
        _read_order(data["order"]),
        _sequence("order event records", data["records"], _read_order_event_record),
    )
    if stream.stream_hash != data["stream_hash"]:
        raise ValueError("order event stream hash mismatch")
    if stream.state_hash != data["state_hash"]:
        raise ValueError("order event state hash mismatch")
    return stream


def _read_order_capability(value: object) -> trading.OrderStyleCapability:
    data = _tagged("order_style_capability", value, "order_style_capability")
    return trading.OrderStyleCapability(
        domain.ExecutionStyle(data["execution_style"]),
        tuple(trading.PriceConstraintShape(item) for item in data["price_constraint_shapes"]),
        tuple(TimeInForce(item) for item in data["time_in_forces"]),
    )


def _read_capability_set(value: object) -> trading.OrderCapabilitySet:
    data = _tagged("order_capability_set", value, "order_capability_set")
    return trading.OrderCapabilitySet(
        data["capability_set_key"],
        data["capability_set_version"],
        _sequence("style capabilities", data["style_capabilities"], _read_order_capability),
        data["supports_reduce_only"],
        tuple(domain.PositionEffect(item) for item in data["supported_position_effects"]),
        tuple(data["declared_capability_keys"]),
        data["config_hash"],
    )


def _read_translation_mapping(value: object) -> trading.OrderTranslationMapping:
    data = _tagged("order_translation_mapping", value, "order_translation_mapping")
    rules = _sequence(
        "translation field rules",
        data["field_rules"],
        lambda item: trading.OrderTranslationFieldRule(
            _tagged(
                "order_translation_field_rule",
                item,
                "order_translation_field_rule",
            )["canonical_field"],
            _tagged(
                "order_translation_field_rule",
                item,
                "order_translation_field_rule",
            )["target_field"],
        ),
    )
    return trading.OrderTranslationMapping(
        data["translator_key"],
        data["translator_version"],
        data["target_profile_id"],
        rules,
        data["config_hash"],
    )


def _read_order_rule_snapshot(value: object) -> trading.OrderRuleSnapshot:
    data = _tagged("order_rule_snapshot", value, "order_rule_snapshot")
    supplemental = _sequence(
        "supplemental order rule decisions",
        data["supplemental_decisions"],
        lambda item: trading.SupplementalOrderRuleDecision(
            _tagged(
                "supplemental_order_rule_decision",
                item,
                "supplemental_order_rule_decision",
            )["rule_key"],
            _tagged(
                "supplemental_order_rule_decision",
                item,
                "supplemental_order_rule_decision",
            )["approved"],
            _tagged(
                "supplemental_order_rule_decision",
                item,
                "supplemental_order_rule_decision",
            )["reason_code"],
        ),
    )
    return trading.OrderRuleSnapshot(
        _read_profile_component_ref(data["component_ref"]),
        _read_instrument_id(data["instrument_id"]),
        domain.SessionId(data["session_id"]["calendar_id"], data["session_id"]["value"]),
        trading.MarketSessionState(data["session_state"]),
        _read_quantity_lattice(data["quantity_lattice"]),
        Scale(data["price_scale"]),
        data["price_tick_units"],
        _optional(data["lower_price_limit"], _read_price),
        _optional(data["upper_price_limit"], _read_price),
        tuple(domain.OrderSide(item) for item in data["permitted_sides"]),
        tuple(domain.PositionEffect(item) for item in data["permitted_position_effects"]),
        data["reduce_only_required"],
        domain.RoundingPolicy(data["notional_rounding"]),
        supplemental,
        data["config_hash"],
        data.get("max_limit_order_quantity_units"),
        data.get("max_market_order_quantity_units"),
        _optional(data.get("market_quantity_lattice"), _read_quantity_lattice),
    )


def _read_order_rule_timeline(value: object) -> trading.OrderRuleTimeline:
    data = _tagged("order_rule_timeline", value, "order_rule_timeline")
    intervals = _sequence(
        "order rule intervals",
        data["intervals"],
        lambda item: trading.OrderRuleInterval(
            _tagged("order_rule_interval", item, "order_rule_interval")["interval_id"],
            _read_utc(_tagged("order_rule_interval", item, "order_rule_interval")["effective_from"]),
            _optional(
                _tagged("order_rule_interval", item, "order_rule_interval")["effective_to_exclusive"],
                _read_utc,
            ),
            _read_order_rule_snapshot(
                _tagged("order_rule_interval", item, "order_rule_interval")["snapshot"]
            ),
        ),
    )
    return trading.OrderRuleTimeline(
        data["timeline_key"],
        data["timeline_version"],
        _read_instrument_id(data["instrument_id"]),
        intervals,
        data["config_hash"],
    )


def _read_notional_evidence(value: object) -> trading.OrderRuleNotionalEvidence:
    data = _tagged(
        "order_rule_notional_evidence", value, "order_rule_notional_evidence"
    )
    return trading.OrderRuleNotionalEvidence(
        trading.NotionalPriceBasis(data["basis"]),
        _read_price(data["price"]),
        data["source_hash"],
        _optional(data["available_at"], _read_utc),
    )


def _read_account_fee_schedule_ref(value: object) -> trading.AccountFeeScheduleRef:
    data = _tagged(
        "account_fee_schedule_ref", value, "account_fee_schedule_ref"
    )
    return trading.AccountFeeScheduleRef(
        data["schedule_key"], data["schedule_version"], data["schedule_digest"]
    )


def _read_fee_reservation_charge(value: object) -> trading.FeeReservationChargeRule:
    data = _tagged(
        "fee_reservation_charge_rule", value, "fee_reservation_charge_rule"
    )
    return trading.FeeReservationChargeRule(
        trading.FeeReservationRuleSource(data["source"]),
        data["rule_id"],
        trading.FeeReservationBasis(data["basis"]),
        trading.FeeReservationApplicability(data["applicability"]),
        _optional(data["rate"], _read_rate),
        _optional(data["flat_amount"], _read_money),
        _read_quantization(data["quantization"]),
    )


def _read_fee_reservation_minimum(value: object) -> trading.FeeReservationMinimum:
    data = _tagged(
        "fee_reservation_minimum", value, "fee_reservation_minimum"
    )
    return trading.FeeReservationMinimum(
        trading.FeeReservationRuleSource(data["source"]),
        data["minimum_id"],
        tuple(data["charge_rule_ids"]),
        _read_money(data["minimum_amount"]),
    )


def _read_fee_reservation_rules(value: object) -> trading.FeeReservationRuleSet:
    data = _tagged("fee_reservation_rule_set", value, "fee_reservation_rule_set")
    return trading.FeeReservationRuleSet(
        _read_profile_component_ref(data["market_fee_policy_ref"]),
        _read_profile_component_ref(data["tax_policy_ref"]),
        _read_account_fee_schedule_ref(data["account_fee_schedule_ref"]),
        _read_currency(data["reservation_currency"]),
        Scale(data["reservation_scale"]),
        _sequence("fee reservation charges", data["charge_rules"], _read_fee_reservation_charge),
        _sequence("fee reservation minimums", data["minimums"], _read_fee_reservation_minimum),
        data["config_hash"],
    )


def _read_reservation_commitment(value: object) -> trading.ReservationCommitment:
    data = _tagged("reservation_commitment", value, "reservation_commitment")
    return trading.ReservationCommitment(
        _sequence("cash commitment", data["cash"], _read_money),
        _sequence("sellable quantity commitment", data["sellable_quantities"], _read_quantity),
        _sequence("margin commitment", data["margin"], _read_money),
        _sequence("fee reserve commitment", data["fee_reserve"], _read_money),
        data["order_capacity_units"],
        _sequence("exposure commitment", data["exposure_capacity"], _read_money),
    )


def _read_reservation_update(value: object) -> trading.OrderReservationUpdate:
    data = _tagged("order_reservation_update", value, "order_reservation_update")
    return trading.OrderReservationUpdate(
        _read_domain_id(data["order_id"]),
        data["event_id"],
        domain.OrderEventType(data["event_type"]),
        _read_quantity(data["remaining_quantity"]),
        _read_reservation_commitment(data["commitment"]),
        data["source_evidence_hash"],
    )


def _read_reservation_schedule(value: object) -> trading.OrderReservationSchedule:
    data = _tagged(
        "order_reservation_schedule", value, "order_reservation_schedule"
    )
    return trading.OrderReservationSchedule(
        _read_domain_id(data["order_id"]),
        data["source_proposal_hash"],
        _sequence(
            "reservation updates", data["updates"], _read_reservation_update
        ),
    )


def _read_account_risk_policy(value: object) -> trading.AccountRiskPolicy:
    data = _tagged("account_risk_policy", value, "account_risk_policy")
    limits = _sequence(
        "exposure capacity limits",
        data["exposure_capacity_limits"],
        lambda item: trading.ExposureCapacityLimit(
            _read_money(
                _tagged("exposure_capacity_limit", item, "exposure_capacity_limit")["maximum"]
            )
        ),
    )
    return trading.AccountRiskPolicy(
        data["policy_key"],
        data["policy_version"],
        data["config_hash"],
        data["account_id"],
        _read_venue(data["venue_id"]),
        tuple(domain.OrderSide(item) for item in data["allowed_sides"]),
        tuple(domain.PositionEffect(item) for item in data["allowed_position_effects"]),
        tuple(data["allowed_reduce_only_values"]),
        trading.FeeReserveFundingSource(data["fee_reserve_funding_source"]),
        data["order_capacity_limit"],
        limits,
    )


def _read_pretrade_plan(value: object) -> ResolvedPreTradePlan:
    data = _tagged("resolved_pretrade_plan", value, "resolved_pretrade_plan")
    return ResolvedPreTradePlan(
        _read_order_rule_timeline(data["order_rule_timeline"]),
        _read_notional_evidence(data["notional_evidence"]),
        _read_utc(data["market_rule_evaluated_at"]),
        _read_fee_reservation_rules(data["fee_reservation_rule_set"]),
        _read_utc(data["fee_estimated_at"]),
        _read_reservation_commitment(data["resource_commitment"]),
        data["requirement_source_key"],
        data["requirement_source_version"],
        data["requirement_source_hash"],
        _read_account_risk_policy(data["account_risk_policy"]),
        _read_utc(data["pretrade_evaluated_at"]),
    )


def _read_order_event_plan(value: object) -> OrderEventPlan:
    data = _tagged("engine_order_event_plan", value, "engine_order_event_plan")
    return OrderEventPlan(
        domain.OrderEventType(data["event_type"]),
        data["event_id"],
        _read_simulation_instant(data["occurred_at"]),
        data["external_evidence_id"],
    )


def _read_order_admission(value: object) -> ResolvedOrderAdmission:
    data = _tagged("resolved_order_admission", value, "resolved_order_admission")
    return ResolvedOrderAdmission(
        _read_order(data["order"]),
        _read_capability_set(data["capability_set"]),
        _read_translation_mapping(data["translation_mapping"]),
        _read_utc(data["translation_time"]),
        _read_pretrade_plan(data["pretrade_plan"]),
        _sequence("order event plan", data["event_plan"], _read_order_event_plan),
    )


def _read_decision_cycle(value: object) -> ResolvedDecisionCycle:
    data = _tagged("resolved_decision_cycle", value, "resolved_decision_cycle")
    sizing_inputs = _sequence("sizing inputs", data["sizing_inputs"], _read_sizing_input)
    return ResolvedDecisionCycle(
        _read_schedule(data["schedule"], sizing_inputs),
        _sequence("allocations", data["allocations"], _read_allocation),
        Scale(data["target_notional_scale"]),
        _read_portfolio_risk_policy(data["risk_policy"]),
        _read_sizing_policy(data["sizing_policy"]),
        sizing_inputs,
        _read_target_validity(data["target_validity"]),
        _read_rebalance_policy(data["rebalance_policy"]),
        _read_utc(data["planning_at"]),
        _sequence("order admissions", data["admissions"], _read_order_admission),
    )


def _read_final_fee_charge(value: object) -> trading.FinalFeeChargeRule:
    data = _tagged("final_fee_charge_rule", value, "final_fee_charge_rule")
    return trading.FinalFeeChargeRule(
        trading.FinalFeeRuleSource(data["source"]),
        data["rule_id"],
        domain.FeeBasisType(data["basis_type"]),
        trading.FinalFeeCalculationBasis(data["calculation_basis"]),
        trading.FinalFeeApplicability(data["applicability"]),
        _optional(data["rate"], _read_rate),
        _optional(data["flat_amount"], _read_money),
        _read_quantization(data["quantization"]),
    )


def _read_final_fee_minimum(value: object) -> trading.FinalFeeMinimum:
    data = _tagged("final_fee_minimum", value, "final_fee_minimum")
    return trading.FinalFeeMinimum(
        trading.FinalFeeRuleSource(data["source"]),
        data["minimum_id"],
        domain.FeeBasisType(data["basis_type"]),
        tuple(data["charge_rule_ids"]),
        _read_money(data["minimum_amount"]),
    )


def _read_final_fee_rules(value: object) -> trading.FinalFeeRuleSet:
    data = _tagged("final_fee_rule_set", value, "final_fee_rule_set")
    return trading.FinalFeeRuleSet(
        _read_profile_component_ref(data["market_fee_policy_ref"]),
        _read_profile_component_ref(data["tax_policy_ref"]),
        _read_account_fee_schedule_ref(data["account_fee_schedule_ref"]),
        _read_currency(data["assessment_currency"]),
        Scale(data["assessment_scale"]),
        _sequence("final fee charges", data["charge_rules"], _read_final_fee_charge),
        _sequence("final fee minimums", data["minimums"], _read_final_fee_minimum),
        data["config_hash"],
    )


def _read_cost_basis(value: object) -> trading.CostBasisPolicy:
    data = _tagged("cost_basis_policy", value, "cost_basis_policy")
    return trading.CostBasisPolicy(
        data["policy_key"],
        data["policy_version"],
        trading.CostBasisMethod(data["method"]),
        domain.RoundingPolicy(data["fee_allocation_rounding"]),
    )


def _read_instrument_definition(value: object) -> domain.InstrumentDefinition:
    data = _tagged("instrument_definition", value, "instrument_definition")
    return domain.InstrumentDefinition(
        _read_instrument_id(data["instrument_id"]),
        domain.InstrumentType(data["instrument_type"]),
        _optional(data["base_currency"], _read_currency),
        _read_currency(data["quote_currency"]),
        _read_currency(data["settlement_currency"]),
    )


def _read_linear_perpetual_contract(
    value: object,
) -> trading.LinearPerpetualContract:
    data = _tagged(
        "linear_perpetual_contract", value, "linear_perpetual_contract"
    )
    return trading.LinearPerpetualContract(
        _read_instrument_definition(data["instrument"]),
        Scale(data["quantity_scale"]),
        Scale(data["price_scale"]),
        _read_rate(data["contract_multiplier"]),
    )


def _read_ledger_registration(value: object) -> trading.LedgerBalanceRegistration:
    data = _tagged(
        "ledger_balance_registration", value, "ledger_balance_registration"
    )
    return trading.LedgerBalanceRegistration(
        _read_balance_key(data["key"]), Scale(data["scale"])
    )


def _read_linear_fill_plan(value: object) -> LinearDerivativeFillAccountingPlan:
    data = _tagged(
        "linear_derivative_fill_accounting_plan",
        value,
        "synthetic_linear_fill_payload",
    )
    return LinearDerivativeFillAccountingPlan(
        _read_position_key(data["position_key"]),
        _read_linear_perpetual_contract(data["contract"]),
        _read_ledger_registration(data["settlement_cash_registration"]),
        _read_quantization(data["pnl_quantization"]),
    )


def _read_cash_fill_plan(value: object) -> CashFillAccountingPlan:
    data = _tagged("cash_fill_accounting_plan", value, "cash_fill_accounting_plan")
    return CashFillAccountingPlan(
        _read_cash_key(data["cash_key"]),
        _read_position_key(data["position_key"]),
        _read_cost_basis(data["cost_basis_policy"]),
        _read_quantization(data["notional_quantization"]),
        _read_domain_id(data["fill_journal_entry_id"]),
        _read_simulation_instant(data["fill_recorded_at"]),
        _read_final_fee_rules(data["final_fee_rule_set"]),
        _read_domain_id(data["fee_assessment_id"]),
        _read_utc(data["fee_assessment_time"]),
        _read_domain_id(data["fee_journal_entry_id"]),
        _read_simulation_instant(data["fee_recorded_at"]),
    )


def _read_canonical_data(value: object) -> object:
    if isinstance(value, Mapping):
        tag = value.get("type")
        if tag == "cash_balance_key":
            return _read_cash_key(value)
        if tag == "position_balance_key":
            return _read_position_key(value)
        if tag == "cost_basis_policy":
            return _read_cost_basis(value)
        if tag == "quantization_policy":
            return _read_quantization(value)
        return {key: _read_canonical_data(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return tuple(_read_canonical_data(child) for child in value)
    if value is None or type(value) in (str, int, bool):
        return value
    raise TypeError("canonical plan payload contains unsupported value")


@dataclass(frozen=True, slots=True)
class _PersistedCanonicalPayload:
    value: Mapping[str, object]

    def __post_init__(self) -> None:
        if not isinstance(self.value, Mapping):
            raise TypeError("persisted canonical payload must be a mapping")
        canonical_sha256(self.value)

    def to_canonical_dict(self) -> dict[str, object]:
        return dict(self.value)


def _read_persisted_canonical_payload(value: object) -> _PersistedCanonicalPayload:
    decoded = _read_canonical_data(value)
    if not isinstance(decoded, Mapping):
        raise TypeError("persisted canonical payload must decode to a mapping")
    return _PersistedCanonicalPayload(decoded)


def _read_fee_accounting_plan(value: object) -> FeeAccountingDispatchPlan:
    data = _tagged(
        "fee_accounting_dispatch_plan", value, "fee_accounting_dispatch_plan"
    )
    return FeeAccountingDispatchPlan(
        _read_cash_key(data["cash_key"]),
        _read_final_fee_rules(data["final_fee_rule_set"]),
        _read_domain_id(data["fee_assessment_id"]),
        _read_utc(data["fee_assessment_time"]),
        _read_domain_id(data["fee_journal_entry_id"]),
        _read_simulation_instant(data["fee_recorded_at"]),
    )


def _read_fill_accounting_plan(value: object) -> FillAccountingDispatchPlan:
    data = _tagged(
        "fill_accounting_dispatch_plan", value, "fill_accounting_dispatch_plan"
    )
    position_value = _mapping("position_payload", data["position_payload"])
    position_tag = position_value.get("type")
    if position_tag == "cash_fill_accounting_plan":
        position_payload: object = _read_cash_fill_plan(position_value)
    elif position_tag == "synthetic_linear_fill_payload":
        position_payload = _read_linear_fill_plan(position_value)
    else:
        raise ValueError("unsupported position_payload type")
    return FillAccountingDispatchPlan(
        data["source_event_id"],
        _read_domain_id(data["expected_fill_id"]),
        _read_profile_component_ref(data["position_accounting_component"]),
        position_payload,
        _read_persisted_canonical_payload(data["semantic_payload"]),
        _read_domain_id(data["fill_journal_entry_id"]),
        _read_simulation_instant(data["fill_recorded_at"]),
        _read_fee_accounting_plan(data["fee_plan"]),
        tuple(data["expected_artifact_roles"]),
    )


def _read_liquidity_evidence(value: object) -> BarLiquidityEvidence:
    data = _tagged("bar_liquidity_evidence", value, "bar_liquidity_evidence")
    return BarLiquidityEvidence(
        data["evidence_key"],
        data["evidence_version"],
        data["market_event_id"],
        data["market_event_hash"],
        _read_utc(data["evaluated_at"]),
        data["approved"],
        data["reason_code"],
        data["source_hash"],
        data["evidence_id"],
    )


def _read_slippage_model(value: object) -> DeterministicBpsSlippageModel:
    data = _mapping("slippage_model", value)
    calibration = _tagged(
        "slippage_calibration_ref",
        data["calibration_ref"],
        "slippage_calibration_ref",
    )
    envelope = _tagged(
        "slippage_applicability_envelope",
        data["applicability_envelope"],
        "slippage_applicability_envelope",
    )
    return DeterministicBpsSlippageModel(
        _read_simulation_component_ref(data["component_ref"]),
        SlippageCalibrationRef(
            calibration["calibration_key"],
            calibration["calibration_version"],
            calibration["calibration_digest"],
        ),
        SlippageApplicabilityEnvelope(
            envelope["envelope_key"],
            envelope["envelope_version"],
            _read_instrument_id(envelope["instrument_id"]),
            _read_utc(envelope["valid_from"]),
            _read_utc(envelope["valid_to_exclusive"]),
            _read_quantity(envelope["maximum_quantity"]),
            tuple(envelope["allowed_market_state_keys"]),
            envelope["config_hash"],
        ),
        data["basis_points_units"],
        Scale(data["basis_points_scale"]),
        domain.RoundingPolicy(data["rounding"]),
        tuple(SlippageLimitation(item) for item in data["limitations"]),
    )


def _read_bar_execution(value: object) -> ResolvedBarExecution:
    data = _tagged("resolved_bar_execution", value, "resolved_bar_execution")
    market_state = _tagged(
        "slippage_market_state", data["market_state"], "slippage_market_state"
    )
    return ResolvedBarExecution(
        data["event_id"],
        _read_domain_id(data["order_id"]),
        _read_pretrade_plan(data["pretrade_plan"]),
        _read_liquidity_evidence(data["liquidity_evidence"]),
        SlippageMarketState(
            market_state["state_key"],
            _read_utc(market_state["observed_at"]),
            _read_utc(market_state["available_at"]),
            market_state["source_event_id"],
            market_state["revision_id"],
            market_state["evidence_hash"],
        ),
        _read_slippage_model(data["slippage_model"]),
        _read_domain_id(data["fill_id"]),
        data["fill_event_id"],
        _read_simulation_instant(data["fill_event_at"]),
        _read_fill_accounting_plan(data["accounting_plan"]),
    )


def _read_balance_change(value: object) -> domain.BalanceChange:
    data = _tagged("balance_change", value, "balance_change")
    key = _read_balance_key(data["key"])
    amount = (
        _read_money(data["value"])
        if isinstance(key, domain.CashBalanceKey)
        else _read_quantity(data["value"])
    )
    return domain.BalanceChange(key, amount)


def _read_position_lot(value: object) -> domain.PositionLot:
    data = _tagged("position_lot", value, "position_lot")
    return domain.PositionLot(
        data["lot_id"],
        _read_position_key(data["position_key"]),
        data["source_id"],
        _read_quantity(data["quantity"]),
        _optional(data["unit_cost"], _read_price),
        _sequence("allocated fees", data["allocated_fees"], _read_money),
        _read_utc(data["opened_at"]),
        _optional(data.get("total_cost_basis"), _read_money),
    )


def _read_position_lot_change(value: object) -> domain.PositionLotChange:
    data = _tagged("position_lot_change", value, "position_lot_change")
    return domain.PositionLotChange(
        _optional(data["before"], _read_position_lot),
        _optional(data["after"], _read_position_lot),
    )


def _read_journal_entry(value: object) -> domain.AccountingJournalEntry:
    data = _tagged("accounting_journal_entry", value, "accounting_journal_entry")
    return domain.AccountingJournalEntry(
        _read_domain_id(data["journal_entry_id"]),
        domain.AccountingEntryType(data["entry_type"]),
        data["account_id"],
        _read_venue(data["venue_id"]),
        _read_utc(data["effective_time"]),
        _read_simulation_instant(data["recorded_at"]),
        tuple(data["source_ids"]),
        _sequence("balance changes", data["balance_changes"], _read_balance_change),
        _sequence("realized pnl", data["realized_pnl"], _read_money),
        _sequence("fees", data["fees"], _read_money),
        _sequence("financing", data["financing"], _read_money),
        position_lot_changes=_sequence(
            "position lot changes",
            data.get("position_lot_changes", ()),
            _read_position_lot_change,
        ),
    )


def _read_journal(value: object) -> trading.AccountingJournal:
    data = _tagged("accounting_journal", value, "accounting_journal")
    journal = trading.AccountingJournal(
        _sequence("journal entries", data["entries"], _read_journal_entry)
    )
    if journal.journal_hash != data["journal_hash"]:
        raise ValueError("accounting journal hash mismatch")
    return journal


def _read_ledger_schema(value: object) -> trading.LedgerSchema:
    data = _tagged("ledger_schema", value, "ledger_schema")
    return trading.LedgerSchema(
        _sequence(
            "ledger registrations",
            data["registrations"],
            lambda item: trading.LedgerBalanceRegistration(
                _read_balance_key(
                    _tagged(
                        "ledger_balance_registration",
                        item,
                        "ledger_balance_registration",
                    )["key"]
                ),
                Scale(
                    _tagged(
                        "ledger_balance_registration",
                        item,
                        "ledger_balance_registration",
                    )["scale"]
                ),
            ),
        )
    )


def _read_position_balance(value: object) -> domain.PositionBalance:
    data = _tagged("position_balance", value, "position_balance")
    return domain.PositionBalance(
        _read_position_key(data["key"]),
        _read_quantity(data["quantity"]),
        _sequence("position balance lots", data["lots"], _read_position_lot),
    )


def _read_valuation_mark_reference(value: object) -> domain.ValuationMarkReference:
    data = _tagged(
        "valuation_mark_reference", value, "valuation_mark_reference"
    )
    return domain.ValuationMarkReference(
        data["mark_id"],
        _read_instrument_id(data["instrument_id"]),
        domain.PricePurpose(data["price_purpose"]),
        _read_utc(data["observed_at"]),
    )


def _read_portfolio_snapshot(value: object) -> domain.PortfolioSnapshot:
    data = _tagged("portfolio_snapshot", value, "portfolio_snapshot")
    cash = _sequence(
        "cash balances",
        data["cash"],
        lambda item: domain.CashBalance(
            _read_cash_key(_tagged("cash_balance", item, "cash_balance")["key"]),
            _read_money(_tagged("cash_balance", item, "cash_balance")["amount"]),
        ),
    )
    return domain.PortfolioSnapshot(
        data["account_id"],
        _read_utc(data["timestamp"]),
        _read_currency(data["reporting_currency"]),
        cash,
        _sequence("snapshot positions", data["positions"], _read_position_balance),
        _read_money(data["realized_pnl"]),
        _read_money(data["unrealized_pnl"]),
        _read_money(data["fees"]),
        _read_money(data["financing"]),
        _read_money(data["equity"]),
        _sequence(
            "valuation marks",
            data["valuation_marks"],
            _read_valuation_mark_reference,
        ),
        data["journal_state_hash"],
        data["valuation_mark_set_hash"],
        data["valuation_staleness_report_hash"],
        data["currency_valuation_graph_hash"],
        timestamp_instant=_optional(
            data.get("timestamp_instant"), _read_simulation_instant
        ),
    )


def _read_position_lot_book(value: object) -> PositionLotBook:
    data = _tagged("position_lot_book", value, "position_lot_book")
    return PositionLotBook(
        _read_position_key(data["position_key"]),
        _sequence("position lots", data["lots"], _read_position_lot),
    )


def _read_settlement_rules(value: object) -> trading.MarketSettlementRules:
    data = _tagged("market_settlement_rules", value, "market_settlement_rules")
    cash_rules = _sequence(
        "cash availability rules",
        data["cash_rules"],
        lambda item: trading.CashAvailabilityRule(
            _read_cash_key(
                _tagged("cash_availability_rule", item, "cash_availability_rule")["key"]
            ),
            _tagged("cash_availability_rule", item, "cash_availability_rule")["pending_receivable_tradable"],
            _tagged("cash_availability_rule", item, "cash_availability_rule")["pending_receivable_withdrawable"],
            _tagged("cash_availability_rule", item, "cash_availability_rule")["pending_receivable_margin_eligible"],
            tuple(
                trading.CashReservationUse(value)
                for value in _tagged("cash_availability_rule", item, "cash_availability_rule")["tradable_reservation_uses"]
            ),
            tuple(
                trading.CashReservationUse(value)
                for value in _tagged("cash_availability_rule", item, "cash_availability_rule")["withdrawable_reservation_uses"]
            ),
            tuple(
                trading.CashReservationUse(value)
                for value in _tagged("cash_availability_rule", item, "cash_availability_rule")["available_margin_reservation_uses"]
            ),
        ),
    )
    position_rules = _sequence(
        "position availability rules",
        data["position_rules"],
        lambda item: trading.PositionAvailabilityRule(
            _read_position_key(
                _tagged(
                    "position_availability_rule",
                    item,
                    "position_availability_rule",
                )["key"]
            ),
            _tagged(
                "position_availability_rule",
                item,
                "position_availability_rule",
            )["pending_receivable_sellable"],
        ),
    )
    return trading.MarketSettlementRules(
        data["policy_key"],
        data["policy_version"],
        data["account_id"],
        cash_rules,
        position_rules,
        data["config_hash"],
    )


def _read_financial_state(value: object) -> ResolvedFinancialState:
    data = _tagged("resolved_financial_state", value, "resolved_financial_state")
    state = _tagged(
        "settlement_state", data["settlement_state"], "settlement_book_state"
    )
    cursor = _tagged(
        "settlement_book_cursor", state["cursor"], "settlement_book_cursor"
    )
    if (
        state.get("schema_version") != 1
        or cursor["position"] != 0
        or state["pending_obligations"] not in ((), [])
        or state["applied_obligations"] not in ((), [])
    ):
        raise ValueError("initial settlement state must be pristine")
    settlement_book = SettlementBook(state["account_id"], (), ())
    if canonical_bytes(settlement_book.project()) != canonical_bytes(state):
        raise ValueError("settlement state does not reconstruct exactly")
    if settlement_book.book_hash != data["settlement_book_hash"]:
        raise ValueError("settlement book hash mismatch")
    return ResolvedFinancialState(
        _read_journal(data["journal"]),
        _read_ledger_schema(data["ledger_schema"]),
        _read_portfolio_snapshot(data["initial_snapshot"]),
        _sequence("lot books", data["lot_books"], _read_position_lot_book),
        _sequence("order streams", data["order_streams"], _read_order_event_stream),
        _sequence(
            "initial order admissions", data["order_admissions"], _read_order_admission
        ),
        _sequence(
            "reservation schedules",
            data["reservation_schedules"],
            _read_reservation_schedule,
        ),
        settlement_book,
        _read_settlement_rules(data["settlement_rules"]),
    )


def _read_valuation_path(value: object) -> trading.CurrencyValuationPath:
    data = _tagged("currency_valuation_path", value, "currency_valuation_path")
    if not data["is_identity"] or data["edges"] not in ((), []):
        raise ValueError("execution case plan v1 requires identity valuation paths")
    path = trading.CurrencyValuationPath(
        _read_currency(data["source_currency_id"]),
        _read_currency(data["reporting_currency_id"]),
        _read_utc(data["valuation_at"]),
        domain.PricePurpose(data["price_purpose"]),
        (),
    )
    if path.path_hash != data["path_hash"]:
        raise ValueError("currency valuation path hash mismatch")
    return path


def _read_reporting_valuation(value: object) -> trading.ReportingCurrencyValuation:
    data = _tagged(
        "reporting_currency_valuation", value, "reporting_currency_valuation"
    )
    ref = _tagged("portfolio_value_ref", data["value_ref"], "portfolio_value_ref")
    resolution = _tagged(
        "currency_valuation_resolution",
        data["resolution"],
        "currency_valuation_resolution",
    )
    if resolution["policy_request"] is not None or resolution["policy_outcome"] is not None:
        raise ValueError("execution case plan v1 requires direct valuation resolution")
    return trading.ReportingCurrencyValuation(
        trading.PortfolioValueRef(
            trading.PortfolioValueKind(ref["kind"]),
            _read_balance_key(ref["balance_key"]),
        ),
        _read_money(data["native_value"]),
        _read_money(data["reporting_value"]),
        trading.CurrencyValuationResolution(
            _read_valuation_path(resolution["path"])
        ),
        data["currency_valuation_graph_hash"],
        _optional(data["quantization_policy"], _read_quantization),
    )


def _read_snapshot_plan(value: object) -> SnapshotProjectionPlan:
    data = _tagged("snapshot_projection_plan", value, "snapshot_projection_plan")
    return SnapshotProjectionPlan(
        _sequence("resolved marks", data["resolved_marks"], _read_resolved_mark),
        _sequence("reporting valuations", data["valuations"], _read_reporting_valuation),
        _read_currency(data["reporting_currency"]),
        Scale(data["reporting_scale"]),
        _read_utc(data["timestamp"]),
        data["currency_valuation_graph_hash"],
    )


def _read_financial_dispatcher_spec(value: object) -> FinancialDispatcherSpec:
    data = _tagged("financial_dispatcher_spec", value, "financial_dispatcher_spec")
    return FinancialDispatcherSpec(
        data["dispatcher_key"],
        data["dispatcher_version"],
        data["config_hash"],
        _read_profile_component_ref(data["position_accounting_component"]),
        _read_profile_component_ref(data["financing_component"]),
        _read_profile_component_ref(data["margin_component"]),
        _read_simulation_component_ref(data["liquidation_audit_component"]),
        data["snapshot_projection_key"],
        data["snapshot_projection_version"],
    )


def _read_identity_binding(value: object) -> tuple[str, domain.DomainId]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise TypeError("identity binding must be a pair")
    binding_key, identity = value
    if type(binding_key) is not str:
        raise TypeError("identity binding key must be str")
    return binding_key, _read_domain_id(identity)


def _read_identity_namespace(value: object) -> IdentityNamespace:
    data = _mapping("identity_namespace", value)
    return IdentityNamespace(data["value"], data["version"], data["algorithm"])


def _read_funding_slot_id(value: object) -> trading.FundingSlotId:
    data = _tagged("funding_slot_id", value, "funding_slot_id")
    return trading.FundingSlotId(
        _read_instrument_id(data["instrument_id"]),
        _read_utc(data["target_funding_time"]),
        data["value"],
    )


def _read_funding_application_key(
    value: object,
) -> LinearFundingApplicationKey:
    data = _tagged(
        "linear_funding_application_key", value, "linear_funding_application_key"
    )
    return LinearFundingApplicationKey(
        data["account_id"],
        _read_funding_slot_id(data["slot_id"]),
        data["value"],
    )


def _read_funding_application_identity(
    value: object,
) -> LinearFundingApplicationIdentity:
    data = _tagged(
        "linear_funding_application_identity",
        value,
        "linear_funding_application_identity",
    )
    return LinearFundingApplicationIdentity(
        _read_funding_application_key(data["application_key"]),
        _read_identity_namespace(data["identity_namespace"]),
        data["semantic_run_id"],
        _read_domain_id(data["settlement_id"]),
        _read_domain_id(data["journal_entry_id"]),
    )


def _read_scheduled_event_payload(value: object) -> object:
    data = _mapping("scheduled event payload", value)
    tag = data.get("type")
    if tag == "synthetic_funding_dispatch_payload":
        return LinearFundingAccountEventPlan(
            _read_funding_application_identity(data["settlement_identity"]),
            _read_simulation_instant(data["recorded_at"]),
        )
    if tag == "synthetic_margin_audit_payload":
        return LinearMarginLiquidationAuditPlan(
            _read_simulation_instant(data["evaluated_at"]),
            _read_price(data["valuation_price"]),
            _read_price(data["margin_price"]),
            _read_utc(data["interval_start"]),
            _read_utc(data["interval_end_exclusive"]),
            _read_price(data["liquidation_low"]),
            _read_price(data["liquidation_high"]),
            _read_simulation_instant(data["audit_at"]),
            data["role_suffix"],
        )
    return _read_persisted_canonical_payload(data)


def _read_scheduled_account_event(value: object) -> ScheduledAccountEvent:
    data = _tagged("scheduled_account_event", value, "scheduled_account_event")
    bindings = _sequence(
        "identity bindings",
        data["identity_bindings"],
        _read_identity_binding,
    )
    return ScheduledAccountEvent(
        data["event_id"],
        _read_simulation_instant(data["event_at"]),
        data["operation_key"],
        tuple(data["component_keys"]),
        bindings,
        _read_scheduled_event_payload(data["payload"]),
        _read_persisted_canonical_payload(data["semantic_payload"]),
        tuple(data["expected_artifact_roles"]),
    )


def _read_financial_dispatch_plan(value: object) -> FinancialDispatchPlan:
    data = _tagged("financial_dispatch_plan", value, "financial_dispatch_plan")
    return FinancialDispatchPlan(
        _read_financial_dispatcher_spec(data["dispatcher_spec"]),
        _sequence(
            "scheduled account events",
            data["scheduled_account_events"],
            _read_scheduled_account_event,
        ),
        _read_snapshot_plan(data["final_snapshot_payload"]),
        tuple(data["expected_artifact_roles"]),
    )


def _read_next_bar_applicability(value: object) -> NextBarOpenApplicability:
    data = _tagged(
        "next_bar_open_applicability", value, "next_bar_open_applicability"
    )
    return NextBarOpenApplicability(
        _sequence(
            "tif actions",
            data["tif_actions"],
            lambda item: (
                TimeInForce(_mapping("tif_action", item)["time_in_force"]),
                NoEligibleBarAction(_mapping("tif_action", item)["action"]),
            ),
        )
    )


def _read_simulation_port_spec(value: object) -> SimulationPortSpec:
    data = _tagged("simulation_port_spec", value, "simulation_port_spec")
    applicability_value = _mapping("simulation applicability", data["applicability"])
    applicability: SimulationPortContract
    if applicability_value.get("type") == "next_bar_open_applicability":
        applicability = _read_next_bar_applicability(applicability_value)
    elif applicability_value.get("type") == "run_end_closeout_applicability":
        applicability = _RunEndCloseoutApplicability(
            RunEndCloseoutMode(applicability_value["policy_mode"]),
            applicability_value["requires_pre_boundary_completion"],
        )
    else:
        raise ValueError("unsupported simulation applicability")
    return SimulationPortSpec(
        _read_simulation_component_ref(data["component_ref"]),
        _sequence(
            "simulation capability requirements",
            data["required_capabilities"],
            lambda item: SimulationCapabilityRequirement(
                _tagged(
                    "simulation_capability_requirement",
                    item,
                    "simulation_capability_requirement",
                )["capability_key"],
                _tagged(
                    "simulation_capability_requirement",
                    item,
                    "simulation_capability_requirement",
                )["minimum_version"],
            ),
        ),
        applicability,
    )


def _read_execution_case_plan(value: object) -> _ExecutionCasePlan:
    plan = _mapping("execution_case_plan", value)
    _exact_fields("execution_case_plan", plan, _PLAN_FIELDS)
    if plan["type"] != "execution_case_plan" or plan["schema_version"] != 1:
        raise ValueError("execution case plan must be execution_case_plan@1")

    decision_cycles = _sequence(
        "decision_cycles", plan["decision_cycles"], _read_decision_cycle
    )
    bar_executions = _sequence(
        "bar_executions", plan["bar_executions"], _read_bar_execution
    )
    financial_state = _read_financial_state(plan["financial_state"])
    financial_dispatch_plan = _read_financial_dispatch_plan(
        plan["financial_dispatch_plan"]
    )
    execution_spec = _read_simulation_port_spec(plan["execution_model_spec"])
    snapshot_plan = _read_snapshot_plan(plan["snapshot_plan"])
    closeout_spec = _read_simulation_port_spec(plan["closeout_policy_spec"])
    if not isinstance(execution_spec, SimulationPortSpec) or not isinstance(
        execution_spec.applicability, NextBarOpenApplicability
    ):
        raise TypeError("execution_model_spec must describe NextEligibleBarOpenModel")
    execution_model = NextEligibleBarOpenModel.create(
        actions=execution_spec.applicability.tif_actions
    )
    if execution_model.spec() != execution_spec:
        raise ValueError("execution model spec does not match the concrete runtime model")
    closeout_policy = MarkToMarketCloseoutPolicy()
    if closeout_policy.spec() != closeout_spec:
        raise ValueError("closeout policy spec does not match the concrete runtime policy")

    rebuilt = {
        "decision_cycles": decision_cycles,
        "bar_executions": bar_executions,
        "financial_state": financial_state,
        "financial_dispatch_plan": financial_dispatch_plan,
        "execution_model_spec": execution_model.spec(),
        "snapshot_plan": snapshot_plan,
        "closeout_policy_spec": closeout_policy.spec(),
    }
    for name, item in rebuilt.items():
        if canonical_bytes(item) != canonical_bytes(plan[name]):
            raise ValueError(f"execution case plan {name} did not reconstruct exactly")
    return _ExecutionCasePlan(
        decision_cycles=decision_cycles,
        bar_executions=bar_executions,
        financial_state=financial_state,
        financial_dispatch_plan=financial_dispatch_plan,
        execution_model=execution_model,
        snapshot_plan=snapshot_plan,
        closeout_policy=closeout_policy,
    )


def _canonical_reconstruction(name: str, value: object, rebuilt: object) -> Any:
    if canonical_bytes(value) != canonical_bytes(rebuilt):
        raise ValueError(f"{name} did not reconstruct exactly")
    return rebuilt


def _read_market_bundle_capability(value: object) -> MarketBundleCapability:
    data = _tagged("market_bundle_capability", value, "market_bundle_capability")
    return _canonical_reconstruction(
        "market_bundle_capability",
        data,
        MarketBundleCapability(data["key"], data["version"]),
    )


def _read_observation_purpose(value: object) -> ObservationPurposeRef:
    data = _tagged("observation_purpose_ref", value, "observation_purpose_ref")
    return _canonical_reconstruction(
        "observation_purpose_ref",
        data,
        ObservationPurposeRef(data["key"], data["version"]),
    )


def _read_observation_query(value: object) -> ObservationQuery:
    data = _tagged("observation_query", value, "observation_query")
    return _canonical_reconstruction(
        "observation_query",
        data,
        ObservationQuery(
            data["dataset_key"],
            _read_instrument_id(data["instrument_id"]),
            _read_observation_purpose(data["purpose"]),
            _read_market_bundle_capability(data["capability"]),
        ),
    )


def _read_bar_definition_ref(value: object) -> BarDefinitionRef:
    data = _tagged("bar_definition_ref", value, "bar_definition_ref")
    return _canonical_reconstruction(
        "bar_definition_ref",
        data,
        BarDefinitionRef(data["key"], data["version"], data["definition_hash"]),
    )


def _read_timeline_window(value: object) -> TimelineWindow:
    data = _tagged("timeline_window", value, "timeline_window")
    return _canonical_reconstruction(
        "timeline_window",
        data,
        TimelineWindow(
            _read_utc(data["data_start"]),
            _read_utc(data["trading_start"]),
            _read_utc(data["end_exclusive"]),
        ),
    )


def _read_decision_schedule_entry(value: object) -> DecisionScheduleEntry:
    data = _tagged("decision_schedule_entry", value, "decision_schedule_entry")
    return _canonical_reconstruction(
        "decision_schedule_entry",
        data,
        DecisionScheduleEntry(
            _read_simulation_instant(data["decision_instant"]),
            TimelineSegment(data["segment"]),
        ),
    )


def _read_lookback_requirement(value: object) -> LookbackRequirement:
    data = _tagged("lookback_requirement", value, "lookback_requirement")
    return _canonical_reconstruction(
        "lookback_requirement",
        data,
        LookbackRequirement(
            data["requirement_key"],
            _read_observation_query(data["observation_query"]),
            _read_bar_definition_ref(data["bar_definition"]),
            data["minimum_count"],
        ),
    )


def _read_decision_schedule(value: object) -> DecisionSchedule:
    data = _tagged("decision_schedule", value, "decision_schedule")
    return _canonical_reconstruction(
        "decision_schedule",
        data,
        DecisionSchedule(
            data["key"],
            data["version"],
            _read_timeline_window(data["window"]),
            _sequence(
                "decision schedule entries",
                data["entries"],
                _read_decision_schedule_entry,
            ),
            _sequence(
                "lookback requirements",
                data["requirements"],
                _read_lookback_requirement,
            ),
        ),
    )


def _read_signal_binding(value: object) -> SignalBarBinding:
    data = _tagged("signal_bar_binding", value, "signal_bar_binding")
    return _canonical_reconstruction(
        "signal_bar_binding",
        data,
        SignalBarBinding(
            data["requirement_hash"],
            data["stream_key"],
            domain.PricePurpose(data["price_purpose"]),
            data["aggregation_input_hash"],
        ),
    )


def _read_execution_binding(value: object) -> ExecutionDataBinding:
    data = _tagged("execution_data_binding", value, "execution_data_binding")
    return _canonical_reconstruction(
        "execution_data_binding",
        data,
        ExecutionDataBinding(data["profile_binding_key"], data["stream_key"]),
    )


def _read_valuation_binding(value: object) -> ValuationDataBinding:
    data = _tagged("valuation_data_binding", value, "valuation_data_binding")
    return _canonical_reconstruction(
        "valuation_data_binding",
        data,
        ValuationDataBinding(
            _read_instrument_id(data["instrument_id"]), data["stream_key"]
        ),
    )


def _read_market_data_bindings(value: object) -> MultiResolutionMarketDataBindings:
    data = _tagged(
        "multi_resolution_market_data_bindings",
        value,
        "multi_resolution_market_data_bindings",
    )
    return _canonical_reconstruction(
        "multi_resolution_market_data_bindings",
        data,
        MultiResolutionMarketDataBindings(
            _sequence("signal_bindings", data["signal_bindings"], _read_signal_binding),
            _sequence(
                "execution_bindings",
                data["execution_bindings"],
                _read_execution_binding,
            ),
            _sequence(
                "valuation_bindings",
                data["valuation_bindings"],
                _read_valuation_binding,
            ),
        ),
    )


def _read_signal_lineage(value: object) -> SignalObservationLineageBinding:
    data = _tagged(
        "signal_observation_lineage_binding",
        value,
        "signal_observation_lineage_binding",
    )
    return _canonical_reconstruction(
        "signal_observation_lineage_binding",
        data,
        SignalObservationLineageBinding(
            data["requirement_hash"],
            data["event_id"],
            data["event_hash"],
            data["observation_key"],
        ),
    )


def _read_market_data_preparation(
    value: object,
) -> MultiResolutionMarketDataPreparation:
    data = _tagged(
        "multi_resolution_market_data_preparation",
        value,
        "multi_resolution_market_data_preparation",
    )
    return _canonical_reconstruction(
        "multi_resolution_market_data_preparation",
        data,
        MultiResolutionMarketDataPreparation(
            _read_decision_schedule(data["decision_schedule"]),
            _read_market_data_bindings(data["bindings"]),
            _sequence(
                "signal_lineages", data["signal_lineages"], _read_signal_lineage
            ),
        ),
    )


def _read_execution_input_payload(value: object) -> _DecodedExecutionInputBundle:
    payload = _mapping("execution_input_bundle", value)
    _exact_fields("execution_input_bundle", payload, _PAYLOAD_FIELDS)
    if payload["type"] != _ARTIFACT_TYPE or payload["schema_version"] != _SCHEMA_VERSION:
        raise ValueError("execution input payload must be backtest_execution_input_bundle@1")

    manifest = _read_build_manifest(payload["build_artifact_manifest"])
    spec = _read_semantic_spec(payload["execution_case_semantic_spec"])
    stream_keys = _stream_keys(payload["timeline_stream_keys"])
    target_key = _text("target_stream_key", payload["target_stream_key"])
    if target_key not in stream_keys:
        raise ValueError("target_stream_key must be included in timeline_stream_keys")
    batch_size = _positive_int("timeline_batch_size", payload["timeline_batch_size"])
    template = _validate_initial_template(payload["initial_financial_state_template"], spec)
    return _DecodedExecutionInputBundle(
        request_hash=payload["request_hash"],
        build_artifact_manifest=manifest,
        execution_case_semantic_spec=spec,
        timeline_stream_keys=stream_keys,
        target_stream_key=target_key,
        timeline_batch_size=batch_size,
        initial_financial_state_template=template,
    )


def _read_execution_input_payload_v2(value: object) -> _DecodedExecutionInputBundleV2:
    payload = _mapping("execution_input_bundle", value)
    _exact_fields("execution_input_bundle", payload, _V2_PAYLOAD_FIELDS)
    if (
        payload["type"] != _ARTIFACT_TYPE
        or payload["schema_version"] != _V2_SCHEMA_VERSION
    ):
        raise ValueError(
            "execution input payload must be backtest_execution_input_bundle@2"
        )
    stream_keys = _stream_keys(payload["timeline_stream_keys"])
    target_key = _text("target_stream_key", payload["target_stream_key"])
    if target_key not in stream_keys:
        raise ValueError("target_stream_key must be included in timeline_stream_keys")
    return _DecodedExecutionInputBundleV2(
        request_hash=_text("request_hash", payload["request_hash"]),
        semantic_run_id=_text("semantic_run_id", payload["semantic_run_id"]),
        build_artifact_manifest=_read_build_manifest(
            payload["build_artifact_manifest"]
        ),
        execution_case_semantic_spec=_read_semantic_spec(
            payload["execution_case_semantic_spec"]
        ),
        timeline_stream_keys=stream_keys,
        target_stream_key=target_key,
        timeline_batch_size=_positive_int(
            "timeline_batch_size", payload["timeline_batch_size"]
        ),
        execution_case_plan=_read_execution_case_plan(
            payload["execution_case_plan"]
        ),
    )


def _read_execution_input_payload_v3(value: object) -> _DecodedExecutionInputBundleV3:
    payload = _mapping("execution_input_bundle", value)
    _exact_fields("execution_input_bundle", payload, _V3_PAYLOAD_FIELDS)
    if (
        payload["type"] != _ARTIFACT_TYPE
        or payload["schema_version"] != _V3_SCHEMA_VERSION
    ):
        raise ValueError(
            "execution input payload must be backtest_execution_input_bundle@3"
        )
    stream_keys = _stream_keys(payload["timeline_stream_keys"])
    target_key = _text("target_stream_key", payload["target_stream_key"])
    if target_key not in stream_keys:
        raise ValueError("target_stream_key must be included in timeline_stream_keys")
    return _DecodedExecutionInputBundleV3(
        request_hash=_text("request_hash", payload["request_hash"]),
        semantic_run_id=_text("semantic_run_id", payload["semantic_run_id"]),
        build_artifact_manifest=_read_build_manifest(
            payload["build_artifact_manifest"]
        ),
        execution_case_semantic_spec=_read_semantic_spec(
            payload["execution_case_semantic_spec"]
        ),
        timeline_stream_keys=stream_keys,
        target_stream_key=target_key,
        timeline_batch_size=_positive_int(
            "timeline_batch_size", payload["timeline_batch_size"]
        ),
        execution_case_plan=_read_execution_case_plan(payload["execution_case_plan"]),
        market_data_preparation=_read_market_data_preparation(
            payload["market_data_preparation"]
        ),
    )


_EXECUTION_INPUT_CATALOG = SchemaCatalog(
    (
        ArtifactSchemaRegistration(
            artifact_type="backtest_execution_input_bundle",
            schema_version=1,
            payload_reader=_read_execution_input_payload,
        ),
        ArtifactSchemaRegistration(
            artifact_type="backtest_execution_input_bundle",
            schema_version=2,
            payload_reader=_read_execution_input_payload_v2,
        ),
        ArtifactSchemaRegistration(
            artifact_type="backtest_execution_input_bundle",
            schema_version=3,
            payload_reader=_read_execution_input_payload_v3,
        ),
    )
)


def materialize_execution_input_bundle(
    *,
    request: BacktestRequest,
    build_artifact_manifest: BuildArtifactManifest,
    execution_case_semantic_spec: ExecutionCaseSemanticSpec,
    timeline_stream_keys: tuple[str, ...],
    target_stream_key: str,
    timeline_batch_size: int,
    initial_financial_state_template: Mapping[str, Any],
) -> ArtifactEnvelope:
    if type(request) is not BacktestRequest:
        raise TypeError("request must be exact BacktestRequest")
    if type(build_artifact_manifest) is not BuildArtifactManifest:
        raise TypeError("build_artifact_manifest must be exact BuildArtifactManifest")
    if type(execution_case_semantic_spec) is not ExecutionCaseSemanticSpec:
        raise TypeError("execution_case_semantic_spec must be exact ExecutionCaseSemanticSpec")
    if build_artifact_manifest.manifest_hash != request.build_artifact_manifest_hash:
        raise ValueError("build artifact manifest does not bind the request")
    if execution_case_semantic_spec.target_stream_digest != request.target_stream_digest:
        raise ValueError("semantic spec target digest does not bind the request")
    if execution_case_semantic_spec.semantic_spec_hash != request.execution_case_semantic_hash:
        raise ValueError("semantic spec does not bind the request")

    stream_keys = _stream_keys(timeline_stream_keys)
    target_key = _text("target_stream_key", target_stream_key)
    if target_key not in stream_keys:
        raise ValueError("target_stream_key must be included in timeline_stream_keys")
    batch_size = _positive_int("timeline_batch_size", timeline_batch_size)
    template = _validate_initial_template(
        initial_financial_state_template,
        execution_case_semantic_spec,
        request,
    )
    payload = {
        "type": _ARTIFACT_TYPE,
        "schema_version": _SCHEMA_VERSION,
        "request_hash": request.request_hash,
        "build_artifact_manifest": build_artifact_manifest,
        "execution_case_semantic_spec": execution_case_semantic_spec,
        "timeline_stream_keys": stream_keys,
        "target_stream_key": target_key,
        "timeline_batch_size": batch_size,
        "initial_financial_state_template": template,
    }
    return ArtifactEnvelope.create(_V1_SCHEMA.name, _V1_SCHEMA.version, payload)


def materialize_execution_input_bundle_v2(
    *,
    resolved_request: ResolvedBacktestRequest,
    execution_case: ResolvedExecutionCase,
) -> ArtifactEnvelope:
    if type(resolved_request) is not ResolvedBacktestRequest:
        raise TypeError("resolved_request must be exact ResolvedBacktestRequest")
    if type(execution_case) is not ResolvedExecutionCase:
        raise TypeError("execution_case must be exact ResolvedExecutionCase")

    request = resolved_request.request
    spec = execution_case.semantic_spec
    if spec is None or execution_case.identity_manifest is None:
        raise ValueError("execution case must be sealed with semantic and identity authority")
    if (
        execution_case.semantic_spec_hash != request.execution_case_semantic_hash
        or spec.semantic_spec_hash != request.execution_case_semantic_hash
        or execution_case.case_key != spec.case_key
        or execution_case.case_version != spec.case_version
    ):
        raise ValueError("execution case semantic identity does not bind the request")
    if resolved_request.build_artifact_manifest.manifest_hash != (
        request.build_artifact_manifest_hash
    ):
        raise ValueError("resolved build artifact manifest does not bind the request")
    if (
        execution_case.timeline.reader.bundle_ref != request.market_bundle_ref
        or execution_case.timeline.window != request.timeline_window
        or ExecutionCaseComposer.timeline_semantic_hash(execution_case.timeline)
        != spec.timeline_semantic_hash
    ):
        raise ValueError("execution case timeline does not bind the request")
    if (
        execution_case.target_stream.target_stream_digest
        != request.target_stream_digest
        or spec.target_stream_digest != request.target_stream_digest
    ):
        raise ValueError("execution case target stream does not bind the request")
    recomputed_spec = ExecutionCaseComposer.semantic_spec_from_case(
        execution_case,
        spec_key=spec.spec_key,
        spec_version=spec.spec_version,
        identity_namespace=spec.identity_namespace,
        identity_plan=spec.identity_plan,
    )
    if recomputed_spec != spec:
        raise ValueError("execution case inputs do not match the semantic spec")
    if not execution_case.verify_identity_manifest(resolved_request.semantic_run_id):
        raise ValueError("execution case identity manifest is invalid")

    component_refs = {
        value.port_type: value
        for value in resolved_request.environment.simulation.component_manifest
    }
    required_refs = {
        execution_case.execution_model.component_ref.port_type: (
            execution_case.execution_model.component_ref
        ),
        execution_case.closeout_policy.spec().component_ref.port_type: (
            execution_case.closeout_policy.spec().component_ref
        ),
    }
    required_refs.update(
        {
            value.slippage_model.component_ref.port_type: value.slippage_model.component_ref
            for value in execution_case.bar_executions
        }
    )
    if any(component_refs.get(port_type) != ref for port_type, ref in required_refs.items()):
        raise ValueError("execution case component refs do not bind the resolved profile")

    payload = {
        "type": _ARTIFACT_TYPE,
        "schema_version": _V2_SCHEMA_VERSION,
        "request_hash": request.request_hash,
        "semantic_run_id": resolved_request.semantic_run_id,
        "build_artifact_manifest": resolved_request.build_artifact_manifest,
        "execution_case_semantic_spec": spec,
        "timeline_stream_keys": execution_case.timeline.stream_keys,
        "target_stream_key": execution_case.target_stream.stream_key,
        "timeline_batch_size": execution_case.timeline_batch_size,
        "execution_case_plan": {
            "type": "execution_case_plan",
            "schema_version": 1,
            "decision_cycles": execution_case.decision_cycles,
            "bar_executions": execution_case.bar_executions,
            "financial_state": execution_case.financial_state,
            "financial_dispatch_plan": execution_case.financial_dispatch_plan,
            "execution_model_spec": execution_case.execution_model.spec(),
            "snapshot_plan": execution_case.snapshot_plan,
            "closeout_policy_spec": execution_case.closeout_policy.spec(),
        },
    }
    return ArtifactEnvelope.create(_V2_SCHEMA.name, _V2_SCHEMA.version, payload)


def _rebuild_backtest_request_v3(value: object) -> BacktestRequest:
    if type(value) is not BacktestRequest:
        raise TypeError("request must be exact BacktestRequest")
    if type(value.timeline_window) is not TimelineWindow:
        raise TypeError("timeline_window must be exact TimelineWindow")
    if type(value.reporting_currency) is not CurrencyId:
        raise TypeError("reporting_currency must be exact CurrencyId")
    if type(value.market_bundle_ref) is not MarketBundleRef:
        raise TypeError("market_bundle_ref must be exact MarketBundleRef")
    if type(value.strategy_family) is not StrategyFamily:
        raise TypeError("strategy_family must be exact StrategyFamily")
    if type(value.result_grade_requested) is not RequestedResultGrade:
        raise TypeError("result_grade_requested must be exact RequestedResultGrade")
    window = TimelineWindow(
        UtcInstant(value.timeline_window.data_start.epoch_nanoseconds),
        UtcInstant(value.timeline_window.trading_start.epoch_nanoseconds),
        UtcInstant(value.timeline_window.end_exclusive.epoch_nanoseconds),
    )
    return BacktestRequest(
        schema_version=value.schema_version,
        experiment_id=value.experiment_id,
        timeline_window=window,
        market_semantics_profile_key=value.market_semantics_profile_key,
        simulation_profile_key=value.simulation_profile_key,
        execution_account_profile_key=value.execution_account_profile_key,
        execution_account_id=value.execution_account_id,
        reporting_currency=CurrencyId(value.reporting_currency.value),
        market_bundle_ref=MarketBundleRef(
            value.market_bundle_ref.bundle_key,
            value.market_bundle_ref.manifest_hash,
        ),
        target_stream_digest=value.target_stream_digest,
        execution_case_semantic_hash=value.execution_case_semantic_hash,
        master_random_seed=value.master_random_seed,
        build_artifact_manifest_hash=value.build_artifact_manifest_hash,
        strategy_family=value.strategy_family,
        engine_kind=value.engine_kind,
        result_grade_requested=value.result_grade_requested,
    )


def _rebuild_build_manifest_v3(value: object) -> BuildArtifactManifest:
    if type(value) is not BuildArtifactManifest:
        raise TypeError("build_artifact_manifest must be exact BuildArtifactManifest")
    if type(value.artifacts) is not tuple or any(
        type(item) is not BuildArtifactRef for item in value.artifacts
    ):
        raise TypeError("artifacts must contain exact BuildArtifactRef")
    if type(value.runtime_libraries) is not tuple or any(
        type(item) is not RuntimeLibraryRef for item in value.runtime_libraries
    ):
        raise TypeError("runtime_libraries must contain exact RuntimeLibraryRef")
    if type(value.provenance) is not BuildProvenance:
        raise TypeError("provenance must be exact BuildProvenance")
    rebuilt = BuildArtifactManifest(
        schema_version=value.schema_version,
        build_key=value.build_key,
        artifacts=value.artifacts,
        dependency_lock_hash=value.dependency_lock_hash,
        runtime_libraries=value.runtime_libraries,
        container_image_digest=value.container_image_digest,
        provenance=value.provenance,
    )
    if canonical_bytes(rebuilt) != canonical_bytes(value):
        raise ValueError("build_artifact_manifest did not reconstruct exactly")
    return rebuilt


def _rebuild_resolved_request_v3(value: object) -> ResolvedBacktestRequest:
    if type(value) is not ResolvedBacktestRequest:
        raise TypeError("resolved_request must be exact ResolvedBacktestRequest")
    request = _rebuild_backtest_request_v3(value.request)
    if type(value.normalized_request) is not NormalizedBacktestRequest:
        raise TypeError("normalized_request must be exact NormalizedBacktestRequest")
    if type(value.environment) is not ResolvedBacktestEnvironment:
        raise TypeError("environment must be exact ResolvedBacktestEnvironment")
    manifest = _rebuild_build_manifest_v3(value.build_artifact_manifest)
    normalized = NormalizedBacktestRequest.from_request(request)
    if normalized != value.normalized_request:
        raise ValueError("normalized_request did not reconstruct exactly")
    return ResolvedBacktestRequest(
        request=request,
        normalized_request=normalized,
        environment=value.environment,
        build_artifact_manifest=manifest,
        semantic_run_id=value.semantic_run_id,
    )


def _rebuild_semantic_spec_v3(value: object) -> ExecutionCaseSemanticSpec:
    if type(value) is not ExecutionCaseSemanticSpec:
        raise TypeError("execution_case_semantic_spec must be exact ExecutionCaseSemanticSpec")
    rebuilt = ExecutionCaseSemanticSpec(
        schema_version=value.schema_version,
        spec_key=value.spec_key,
        spec_version=value.spec_version,
        case_key=value.case_key,
        case_version=value.case_version,
        identity_namespace=value.identity_namespace,
        identity_plan=value.identity_plan,
        timeline_semantic_hash=value.timeline_semantic_hash,
        target_stream_digest=value.target_stream_digest,
        decision_inputs_hash=value.decision_inputs_hash,
        execution_inputs_hash=value.execution_inputs_hash,
        financial_inputs_hash=value.financial_inputs_hash,
        snapshot_inputs_hash=value.snapshot_inputs_hash,
        run_end_inputs_hash=value.run_end_inputs_hash,
    )
    if canonical_bytes(rebuilt) != canonical_bytes(value):
        raise ValueError("execution_case_semantic_spec did not reconstruct exactly")
    return rebuilt


def _rebuild_execution_case_plan_v3(value: object) -> _ExecutionCasePlan:
    if type(value) is not _ExecutionCasePlan:
        raise TypeError("execution_case_plan must be exact _ExecutionCasePlan")
    return _ExecutionCasePlan(
        decision_cycles=value.decision_cycles,
        bar_executions=value.bar_executions,
        financial_state=value.financial_state,
        financial_dispatch_plan=value.financial_dispatch_plan,
        execution_model=value.execution_model,
        snapshot_plan=value.snapshot_plan,
        closeout_policy=value.closeout_policy,
    )


def _rebuild_hydrated_inputs_v3(value: object) -> _HydratedExecutionCaseInputs:
    if type(value) is not _HydratedExecutionCaseInputs:
        raise TypeError("hydrated_inputs must be exact _HydratedExecutionCaseInputs")
    target_stream = PrecomputedTargetStream(
        value.target_stream.stream_key,
        value.target_stream.events,
    )
    return _HydratedExecutionCaseInputs(
        execution_case_semantic_spec=_rebuild_semantic_spec_v3(
            value.execution_case_semantic_spec
        ),
        timeline_stream_keys=tuple(value.timeline_stream_keys),
        target_stream=target_stream,
        timeline_batch_size=value.timeline_batch_size,
        execution_case_plan=_rebuild_execution_case_plan_v3(
            value.execution_case_plan
        ),
    )


def _validate_exact_canonical_scalars_v3(
    value: object,
    active: set[int] | None = None,
) -> None:
    if value is None:
        return
    if isinstance(value, Enum):
        raise TypeError("canonical Reader authority must not contain Enum leaves")
    if isinstance(value, bool):
        if type(value) is not bool:
            raise TypeError("canonical bool leaves must be exact builtins")
        return
    if isinstance(value, int):
        if type(value) is not int:
            raise TypeError("canonical integer leaves must be exact builtins")
        return
    if isinstance(value, str):
        if type(value) is not str:
            raise TypeError("canonical text leaves must be exact builtins")
        return

    seen = set() if active is None else active
    identity = id(value)
    if identity in seen:
        raise ValueError("canonical authority must not contain cycles")
    seen.add(identity)
    try:
        if isinstance(value, Mapping):
            for key, child in value.items():
                if type(key) is not str:
                    raise TypeError("canonical mapping keys must be exact str")
                _validate_exact_canonical_scalars_v3(child, seen)
            return
        if isinstance(value, (list, tuple)):
            for child in value:
                _validate_exact_canonical_scalars_v3(child, seen)
            return
        to_canonical = getattr(value, "to_canonical_dict", None)
        if not callable(to_canonical):
            raise TypeError("canonical authority contains an unsupported value")
        canonical_value = to_canonical()
        if not isinstance(canonical_value, Mapping):
            raise TypeError("canonical authority must encode as a mapping")
        _validate_exact_canonical_scalars_v3(canonical_value, seen)
    finally:
        seen.remove(identity)


def _rebuild_verified_reader_v3(
    value: object,
) -> InMemoryMarketBundleReader:
    if type(value) is not InMemoryMarketBundleReader:
        raise TypeError("verified_reader must be exact InMemoryMarketBundleReader")
    _validate_exact_canonical_scalars_v3(value.bundle_ref)
    _validate_exact_canonical_scalars_v3(value.manifest)
    _validate_exact_canonical_scalars_v3(value.streams)

    def rebuild_once() -> InMemoryMarketBundleReader:
        bundle_ref = _rebuild_market_bundle_ref_v3(value.bundle_ref)
        manifest = _rebuild_market_bundle_manifest_v3(value.manifest)
        stream_values = value.streams
        if not isinstance(stream_values, Mapping):
            raise TypeError("verified_reader streams must be a mapping")
        streams: dict[str, tuple[Any, ...]] = {}
        for stream_key in sorted(stream_values):
            if type(stream_key) is not str:
                raise TypeError("verified_reader stream keys must be exact str")
            events = stream_values[stream_key]
            if type(events) is not tuple:
                raise TypeError("verified_reader stream Events must be exact tuples")
            streams[stream_key] = tuple(
                _rebuild_market_event_v3(event) for event in events
            )
        rebuilt = InMemoryMarketBundleReader(bundle_ref, manifest, streams)
        _validate_exact_canonical_scalars_v3(rebuilt.bundle_ref)
        _validate_exact_canonical_scalars_v3(rebuilt.manifest)
        _validate_exact_canonical_scalars_v3(rebuilt.streams)
        if (
            canonical_bytes(rebuilt.bundle_ref) != canonical_bytes(value.bundle_ref)
            or canonical_bytes(rebuilt.manifest) != canonical_bytes(value.manifest)
            or canonical_bytes(rebuilt.streams) != canonical_bytes(value.streams)
        ):
            raise ValueError("verified_reader did not reconstruct exactly")
        return rebuilt

    rebuilt = rebuild_once()
    verified_again = rebuild_once()
    if (
        canonical_bytes(rebuilt.bundle_ref)
        != canonical_bytes(verified_again.bundle_ref)
        or canonical_bytes(rebuilt.manifest)
        != canonical_bytes(verified_again.manifest)
        or canonical_bytes(rebuilt.streams)
        != canonical_bytes(verified_again.streams)
    ):
        raise ValueError("verified_reader authority changed during reconstruction")
    return rebuilt


def _rebuild_prepared_market_data_v3(
    value: object,
) -> PreparedMultiResolutionMarketData:
    if type(value) is not PreparedMultiResolutionMarketData:
        raise TypeError(
            "prepared_market_data must be exact PreparedMultiResolutionMarketData"
        )
    preparation = MultiResolutionMarketDataPreparation(
        value.preparation.decision_schedule,
        value.preparation.bindings,
        value.preparation.signal_lineages,
    )
    verified_reader = _rebuild_verified_reader_v3(value.verified_reader)
    return PreparedMultiResolutionMarketData(
        preparation=preparation,
        eligibilities=tuple(value.eligibilities),
        verified_reader=verified_reader,
    )


def _rebuild_execution_request_v3(
    value: object,
) -> tuple[int, ArtifactRef]:
    if type(value) is not BacktestExecutionRequest:
        raise TypeError("request must be exact BacktestExecutionRequest")
    schema_version = value.schema_version
    if type(schema_version) is not int or schema_version not in (
        _SCHEMA_VERSION,
        _V2_SCHEMA_VERSION,
        _V3_SCHEMA_VERSION,
    ):
        raise ValueError("request schema_version is malformed")
    ref = value.execution_input_bundle_ref
    if type(ref) is not ArtifactRef:
        raise TypeError("execution_input_bundle_ref must be exact ArtifactRef")
    rebuilt_ref = ArtifactRef(
        ref.artifact_type,
        ref.schema_version,
        ref.content_hash,
    )
    return schema_version, rebuilt_ref


def _materialize_execution_input_bundle_v3(
    *,
    resolved_request: ResolvedBacktestRequest,
    hydrated_inputs: _HydratedExecutionCaseInputs,
    market_data_preparation: MultiResolutionMarketDataPreparation,
) -> ArtifactEnvelope:
    try:
        resolved = _rebuild_resolved_request_v3(resolved_request)
        inputs = _rebuild_hydrated_inputs_v3(hydrated_inputs)
        if type(market_data_preparation) is not MultiResolutionMarketDataPreparation:
            raise TypeError(
                "market_data_preparation must be exact MultiResolutionMarketDataPreparation"
            )
        preparation = MultiResolutionMarketDataPreparation(
            market_data_preparation.decision_schedule,
            market_data_preparation.bindings,
            market_data_preparation.signal_lineages,
        )
    except Exception:
        raise TypeError("v3 materialization authority is malformed") from None
    request = resolved.request
    spec = inputs.execution_case_semantic_spec
    stream_keys = _stream_keys(inputs.timeline_stream_keys)
    target_key = _text("target_stream_key", inputs.target_stream.stream_key)
    if target_key not in stream_keys:
        raise ValueError("target_stream_key must be included in timeline_stream_keys")
    if resolved.build_artifact_manifest.manifest_hash != (
        request.build_artifact_manifest_hash
    ):
        raise ValueError("resolved build artifact manifest does not bind the request")
    if spec.semantic_spec_hash != request.execution_case_semantic_hash:
        raise ValueError("execution case semantic spec does not bind the request")
    if (
        inputs.target_stream.target_stream_digest
        != request.target_stream_digest
        or spec.target_stream_digest != request.target_stream_digest
    ):
        raise ValueError("target stream does not bind the request")
    expected_spec = _execution_case_semantic_spec_v3(
        base_spec=spec,
        execution_case_plan=inputs.execution_case_plan,
        market_data_preparation=preparation,
    )
    if expected_spec != spec:
        raise ValueError("market data preparation does not bind the semantic spec")

    payload = {
        "type": _ARTIFACT_TYPE,
        "schema_version": _V3_SCHEMA_VERSION,
        "request_hash": request.request_hash,
        "semantic_run_id": resolved.semantic_run_id,
        "build_artifact_manifest": resolved.build_artifact_manifest,
        "execution_case_semantic_spec": spec,
        "timeline_stream_keys": stream_keys,
        "target_stream_key": target_key,
        "timeline_batch_size": inputs.timeline_batch_size,
        "execution_case_plan": {
            "type": "execution_case_plan",
            "schema_version": 1,
            "decision_cycles": inputs.execution_case_plan.decision_cycles,
            "bar_executions": inputs.execution_case_plan.bar_executions,
            "financial_state": inputs.execution_case_plan.financial_state,
            "financial_dispatch_plan": inputs.execution_case_plan.financial_dispatch_plan,
            "execution_model_spec": inputs.execution_case_plan.execution_model.spec(),
            "snapshot_plan": inputs.execution_case_plan.snapshot_plan,
            "closeout_policy_spec": inputs.execution_case_plan.closeout_policy.spec(),
        },
        "market_data_preparation": preparation.to_canonical_dict(),
    }
    return ArtifactEnvelope.create(_V3_SCHEMA.name, _V3_SCHEMA.version, payload)


def _failure_v3(
    code: _ExecutionInputsHydrationFailureCodeV3,
    role_position: int | None = None,
    schedule_entry_position: int | None = None,
    requirement_position: int | None = None,
    event_position: int | None = None,
) -> _ExecutionInputsHydrationOutcomeV3:
    return _ExecutionInputsHydrationOutcomeV3(
        failure=_ExecutionInputsHydrationFailureV3(
            code,
            role_position,
            schedule_entry_position,
            requirement_position,
            event_position,
        )
    )


def _start_v3(recorder: BoundedPerformanceRecorder | None) -> int | None:
    if recorder is None:
        return None
    try:
        return _clock()
    except BaseException:
        return None


def _record_v3(
    recorder: BoundedPerformanceRecorder | None,
    operation: PerformanceOperation,
    outcome: PerformanceOutcome,
    started_at: int | None,
    input_count: int,
    output_count: int,
) -> None:
    if recorder is None or started_at is None:
        return
    try:
        ended_at = _clock()
        if ended_at is not None and ended_at >= started_at:
            _record_observation(
                recorder,
                operation,
                outcome,
                ended_at - started_at,
                input_count,
                output_count,
            )
    except BaseException:
        return


def _binding_count_v3(preparation: MultiResolutionMarketDataPreparation) -> int:
    bindings = preparation.bindings
    return (
        len(bindings.signal_bindings)
        + len(bindings.execution_bindings)
        + len(bindings.valuation_bindings)
    )


def _observation_binding_count_v3(
    preparation: MultiResolutionMarketDataPreparation,
) -> int:
    try:
        return _binding_count_v3(preparation)
    except BaseException:
        return 0


def _binding_mismatch_position(
    embedded: MultiResolutionMarketDataBindings,
    retained: MultiResolutionMarketDataBindings,
) -> tuple[int, int] | None:
    roles = (
        (embedded.signal_bindings, retained.signal_bindings),
        (embedded.execution_bindings, retained.execution_bindings),
        (embedded.valuation_bindings, retained.valuation_bindings),
    )
    for role_position, (left, right) in enumerate(roles):
        for position in range(max(len(left), len(right))):
            if position >= len(left) or position >= len(right) or left[position] != right[position]:
                return role_position, position
    return None


def _preparation_replay_positions(
    embedded: MultiResolutionMarketDataPreparation,
    retained: MultiResolutionMarketDataPreparation,
) -> tuple[int | None, int | None, int | None]:
    for position in range(
        max(
            len(embedded.decision_schedule.entries),
            len(retained.decision_schedule.entries),
        )
    ):
        if (
            position >= len(embedded.decision_schedule.entries)
            or position >= len(retained.decision_schedule.entries)
            or embedded.decision_schedule.entries[position]
            != retained.decision_schedule.entries[position]
        ):
            return position, None, None
    for position in range(
        max(
            len(embedded.decision_schedule.requirements),
            len(retained.decision_schedule.requirements),
        )
    ):
        if (
            position >= len(embedded.decision_schedule.requirements)
            or position >= len(retained.decision_schedule.requirements)
            or embedded.decision_schedule.requirements[position]
            != retained.decision_schedule.requirements[position]
        ):
            return None, position, None
    for position in range(
        max(len(embedded.signal_lineages), len(retained.signal_lineages))
    ):
        if (
            position >= len(embedded.signal_lineages)
            or position >= len(retained.signal_lineages)
            or embedded.signal_lineages[position] != retained.signal_lineages[position]
        ):
            return None, None, position
    return None, None, None


def _read_execution_inputs_v3(
    reader: ArtifactEnvelopeReader,
    request: BacktestExecutionRequest,
    *,
    recorder: BoundedPerformanceRecorder | None = None,
) -> tuple[_DecodedExecutionInputBundleV3 | None, _ExecutionInputsHydrationFailureV3 | None]:
    if recorder is not None and type(recorder) is not BoundedPerformanceRecorder:
        return None, _ExecutionInputsHydrationFailureV3(
            _ExecutionInputsHydrationFailureCodeV3.MALFORMED_EXECUTION_REQUEST
        )
    try:
        request_schema_version, ref = _rebuild_execution_request_v3(request)
    except Exception:
        return None, _ExecutionInputsHydrationFailureV3(
            _ExecutionInputsHydrationFailureCodeV3.MALFORMED_EXECUTION_REQUEST
        )
    if (
        request_schema_version != _V3_SCHEMA_VERSION
        or ref.artifact_type != _ARTIFACT_TYPE
        or ref.schema_version != _V3_SCHEMA_VERSION
    ):
        return None, _ExecutionInputsHydrationFailureV3(
            _ExecutionInputsHydrationFailureCodeV3.WRONG_EXECUTION_INPUT_BUNDLE_REF
        )
    try:
        public_request = _rebuild_backtest_request_v3(request.request)
    except Exception:
        return None, _ExecutionInputsHydrationFailureV3(
            _ExecutionInputsHydrationFailureCodeV3.MALFORMED_EXECUTION_REQUEST
        )
    try:
        source = reader.read(ref=ref)
    except Exception as error:
        return None, _ExecutionInputsHydrationFailureV3(
            _ExecutionInputsHydrationFailureCodeV3.EXECUTION_INPUT_TAMPERED
            if isinstance(error, ArtifactIntegrityError)
            else _ExecutionInputsHydrationFailureCodeV3.EXECUTION_INPUT_UNAVAILABLE
        )
    if type(source) is not ArtifactReadResult:
        return None, _ExecutionInputsHydrationFailureV3(
            _ExecutionInputsHydrationFailureCodeV3.EXECUTION_INPUT_UNAVAILABLE
        )
    try:
        source_valid = (
            source.source_bytes == canonical_bytes(source.envelope)
            and source.source_hash == canonical_sha256(source.envelope)
            and ArtifactRef.from_envelope(source.envelope) == ref
        )
    except Exception:
        source_valid = False
    if not source_valid:
        return None, _ExecutionInputsHydrationFailureV3(
            _ExecutionInputsHydrationFailureCodeV3.EXECUTION_INPUT_TAMPERED
        )

    hydrate_started = _start_v3(recorder)
    try:
        decoded = _EXECUTION_INPUT_CATALOG.read(source.source_bytes)
    except Exception as error:
        _record_v3(
            recorder,
            PerformanceOperation.HYDRATE_INPUTS,
            PerformanceOutcome.FAILED,
            hydrate_started,
            0,
            0,
        )
        return None, _ExecutionInputsHydrationFailureV3(
            _ExecutionInputsHydrationFailureCodeV3.EXECUTION_INPUT_TAMPERED
            if isinstance(
                error,
                (
                    ArtifactIntegrityError,
                    UnknownArtifactTypeError,
                    UnsupportedSchemaVersionError,
                ),
            )
            else _ExecutionInputsHydrationFailureCodeV3.EXECUTION_INPUT_DECODE_FAILED
        )
    bundle = decoded.artifact
    if (
        decoded.envelope != source.envelope
        or type(bundle) is not _DecodedExecutionInputBundleV3
    ):
        _record_v3(
            recorder,
            PerformanceOperation.HYDRATE_INPUTS,
            PerformanceOutcome.FAILED,
            hydrate_started,
            0,
            0,
        )
        return None, _ExecutionInputsHydrationFailureV3(
            _ExecutionInputsHydrationFailureCodeV3.EXECUTION_INPUT_DECODE_FAILED
        )
    binding_count = _observation_binding_count_v3(bundle.market_data_preparation)
    _record_v3(
        recorder,
        PerformanceOperation.HYDRATE_INPUTS,
        PerformanceOutcome.SUCCEEDED,
        hydrate_started,
        binding_count,
        binding_count,
    )
    if bundle.request_hash != public_request.request_hash:
        return None, _ExecutionInputsHydrationFailureV3(
            _ExecutionInputsHydrationFailureCodeV3.REQUEST_BINDING_MISMATCH
        )
    return bundle, None


def _hydrate_execution_inputs_v3_from_decoded(
    bundle: _DecodedExecutionInputBundleV3,
    request: BacktestExecutionRequest,
    *,
    market_reader: MarketBundleReader,
    resolved_request: ResolvedBacktestRequest,
    prepared_market_data: PreparedMultiResolutionMarketData,
    recorder: BoundedPerformanceRecorder | None = None,
) -> _ExecutionInputsHydrationOutcomeV3:
    if recorder is not None and type(recorder) is not BoundedPerformanceRecorder:
        return _failure_v3(
            _ExecutionInputsHydrationFailureCodeV3.MALFORMED_EXECUTION_REQUEST
        )
    try:
        request_schema_version, ref = _rebuild_execution_request_v3(request)
    except Exception:
        return _failure_v3(
            _ExecutionInputsHydrationFailureCodeV3.MALFORMED_EXECUTION_REQUEST
        )
    if (
        request_schema_version != _V3_SCHEMA_VERSION
        or ref.artifact_type != _ARTIFACT_TYPE
        or ref.schema_version != _V3_SCHEMA_VERSION
    ):
        return _failure_v3(
            _ExecutionInputsHydrationFailureCodeV3.WRONG_EXECUTION_INPUT_BUNDLE_REF
        )
    try:
        public_request = _rebuild_backtest_request_v3(request.request)
        resolved = _rebuild_resolved_request_v3(resolved_request)
        if type(bundle) is not _DecodedExecutionInputBundleV3:
            raise TypeError("bundle must be exact decoded v3 execution inputs")
        if type(prepared_market_data) is not PreparedMultiResolutionMarketData:
            raise TypeError(
                "prepared_market_data must be exact PreparedMultiResolutionMarketData"
            )
        if market_reader is not prepared_market_data.verified_reader:
            raise ValueError("market_reader must be the retained verified Reader")
        prepared = prepared_market_data
        verified_reader = prepared.verified_reader
    except Exception:
        return _failure_v3(
            _ExecutionInputsHydrationFailureCodeV3.MALFORMED_EXECUTION_REQUEST
        )

    binding_count = _observation_binding_count_v3(bundle.market_data_preparation)
    if (
        bundle.request_hash != public_request.request_hash
        or resolved.request != public_request
        or bundle.semantic_run_id != resolved.semantic_run_id
    ):
        return _failure_v3(
            _ExecutionInputsHydrationFailureCodeV3.REQUEST_BINDING_MISMATCH
        )
    if (
        bundle.build_artifact_manifest.manifest_hash
        != public_request.build_artifact_manifest_hash
        or bundle.build_artifact_manifest != resolved.build_artifact_manifest
    ):
        return _failure_v3(
            _ExecutionInputsHydrationFailureCodeV3.BUILD_BINDING_MISMATCH
        )
    if verified_reader.bundle_ref != public_request.market_bundle_ref:
        return _failure_v3(
            _ExecutionInputsHydrationFailureCodeV3.TARGET_BINDING_MISMATCH
        )
    try:
        requirement_failure = verified_reader.validate_requirements(
            required_streams=bundle.timeline_stream_keys
        )
        cursor = verified_reader.open_cursor(
            bundle.target_stream_key,
            batch_size=bundle.timeline_batch_size,
        )
        if requirement_failure is not None or isinstance(cursor, InputValidationFailure):
            raise ValueError("target unavailable")
        events: list[Any] = []
        while not cursor.exhausted:
            previous_position = cursor.position
            batch, cursor = verified_reader.read_batch(cursor)
            if not batch or cursor.position != previous_position + len(batch):
                raise ValueError("target cursor did not advance")
            events.extend(batch)
        target_stream = PrecomputedTargetStream(bundle.target_stream_key, tuple(events))
    except Exception:
        return _failure_v3(
            _ExecutionInputsHydrationFailureCodeV3.TARGET_BINDING_MISMATCH
        )
    if (
        target_stream.target_stream_digest != public_request.target_stream_digest
        or bundle.execution_case_semantic_spec.target_stream_digest
        != public_request.target_stream_digest
    ):
        return _failure_v3(
            _ExecutionInputsHydrationFailureCodeV3.TARGET_BINDING_MISMATCH
        )

    replay_started = _start_v3(recorder)
    try:
        retained_preparation = MultiResolutionMarketDataPreparation(
            prepared.preparation.decision_schedule,
            prepared.preparation.bindings,
            prepared.preparation.signal_lineages,
        )
    except Exception:
        _record_v3(
            recorder,
            PerformanceOperation.VERIFY_REPLAY,
            PerformanceOutcome.FAILED,
            replay_started,
            binding_count,
            0,
        )
        return _failure_v3(
            _ExecutionInputsHydrationFailureCodeV3.PREPARED_MARKET_DATA_REPLAY_MISMATCH
        )
    binding_position = _binding_mismatch_position(
        bundle.market_data_preparation.bindings,
        retained_preparation.bindings,
    )
    if binding_position is not None:
        _record_v3(
            recorder,
            PerformanceOperation.VERIFY_REPLAY,
            PerformanceOutcome.FAILED,
            replay_started,
            binding_count,
            0,
        )
        return _failure_v3(
            _ExecutionInputsHydrationFailureCodeV3.PREPARED_MARKET_DATA_BINDING_MISMATCH,
            binding_position[0],
            None,
            binding_position[1],
        )
    if bundle.market_data_preparation != retained_preparation:
        schedule_position, requirement_position, event_position = (
            _preparation_replay_positions(
                bundle.market_data_preparation, retained_preparation
            )
        )
        _record_v3(
            recorder,
            PerformanceOperation.VERIFY_REPLAY,
            PerformanceOutcome.FAILED,
            replay_started,
            binding_count,
            0,
        )
        return _failure_v3(
            _ExecutionInputsHydrationFailureCodeV3.PREPARED_MARKET_DATA_REPLAY_MISMATCH,
            None,
            schedule_position,
            requirement_position,
            event_position,
        )
    expected_spec = _execution_case_semantic_spec_v3(
        base_spec=bundle.execution_case_semantic_spec,
        execution_case_plan=bundle.execution_case_plan,
        market_data_preparation=retained_preparation,
    )
    if expected_spec != bundle.execution_case_semantic_spec:
        _record_v3(
            recorder,
            PerformanceOperation.VERIFY_REPLAY,
            PerformanceOutcome.FAILED,
            replay_started,
            binding_count,
            0,
        )
        return _failure_v3(
            _ExecutionInputsHydrationFailureCodeV3.PREPARED_MARKET_DATA_REPLAY_MISMATCH
        )
    try:
        plan = bundle.execution_case_plan
        authority = MarketDataCaseAuthority(
            decision_cycles=plan.decision_cycles,
            bar_executions=plan.bar_executions,
            execution_model=plan.execution_model,
            snapshot_plan=plan.snapshot_plan,
            target_stream=target_stream,
        )
        replayed_preparation = _prepare_multi_resolution_market_data_from_retained_v1(
            expected_bundle_ref=public_request.market_bundle_ref,
            reader=prepared.verified_reader,
            schedule=bundle.market_data_preparation.decision_schedule,
            signal_binding_candidates=(
                bundle.market_data_preparation.bindings.signal_bindings
            ),
            execution_binding_candidates=(
                bundle.market_data_preparation.bindings.execution_bindings
            ),
            valuation_binding_candidates=(
                bundle.market_data_preparation.bindings.valuation_bindings
            ),
            signal_lineages=bundle.market_data_preparation.signal_lineages,
            case_authority=authority,
            resolved_request=resolved,
            recorder=None,
        )
        expected_preparation = MarketDataPreparationOutcome(prepared, None)
        preparation_replayed_exactly = replayed_preparation == expected_preparation
    except Exception:
        preparation_replayed_exactly = False
    if not preparation_replayed_exactly:
        _record_v3(
            recorder,
            PerformanceOperation.VERIFY_REPLAY,
            PerformanceOutcome.FAILED,
            replay_started,
            binding_count,
            0,
        )
        return _failure_v3(
            _ExecutionInputsHydrationFailureCodeV3.PREPARED_MARKET_DATA_REPLAY_MISMATCH
        )
    if (
        bundle.execution_case_semantic_spec.semantic_spec_hash
        != public_request.execution_case_semantic_hash
    ):
        _record_v3(
            recorder,
            PerformanceOperation.VERIFY_REPLAY,
            PerformanceOutcome.FAILED,
            replay_started,
            binding_count,
            0,
        )
        return _failure_v3(
            _ExecutionInputsHydrationFailureCodeV3.EXECUTION_CASE_SEMANTIC_HASH_MISMATCH
        )
    _record_v3(
        recorder,
        PerformanceOperation.VERIFY_REPLAY,
        PerformanceOutcome.SUCCEEDED,
        replay_started,
        binding_count,
        binding_count,
    )
    return _ExecutionInputsHydrationOutcomeV3(
        result=_HydratedExecutionInputsV3(
            build_artifact_manifest=bundle.build_artifact_manifest,
            execution_case_semantic_spec=bundle.execution_case_semantic_spec,
            timeline_stream_keys=bundle.timeline_stream_keys,
            target_stream=target_stream,
            timeline_batch_size=bundle.timeline_batch_size,
            execution_case_plan=bundle.execution_case_plan,
            market_data_preparation=bundle.market_data_preparation,
        )
    )


def _hydrate_execution_inputs_v3(
    reader: ArtifactEnvelopeReader,
    request: BacktestExecutionRequest,
    *,
    market_reader: MarketBundleReader,
    resolved_request: ResolvedBacktestRequest,
    prepared_market_data: PreparedMultiResolutionMarketData,
    recorder: BoundedPerformanceRecorder | None = None,
) -> _ExecutionInputsHydrationOutcomeV3:
    if recorder is not None and type(recorder) is not BoundedPerformanceRecorder:
        return _failure_v3(
            _ExecutionInputsHydrationFailureCodeV3.MALFORMED_EXECUTION_REQUEST
        )
    try:
        request_schema_version, ref = _rebuild_execution_request_v3(request)
    except Exception:
        return _failure_v3(
            _ExecutionInputsHydrationFailureCodeV3.MALFORMED_EXECUTION_REQUEST
        )
    if (
        request_schema_version != _V3_SCHEMA_VERSION
        or ref.artifact_type != _ARTIFACT_TYPE
        or ref.schema_version != _V3_SCHEMA_VERSION
    ):
        return _failure_v3(
            _ExecutionInputsHydrationFailureCodeV3.WRONG_EXECUTION_INPUT_BUNDLE_REF
        )
    try:
        _rebuild_backtest_request_v3(request.request)
        _rebuild_resolved_request_v3(resolved_request)
        if type(prepared_market_data) is not PreparedMultiResolutionMarketData:
            raise TypeError(
                "prepared_market_data must be exact PreparedMultiResolutionMarketData"
            )
        if market_reader is not prepared_market_data.verified_reader:
            raise ValueError("market_reader must be the retained verified Reader")
        _rebuild_prepared_market_data_v3(prepared_market_data)
    except Exception:
        return _failure_v3(
            _ExecutionInputsHydrationFailureCodeV3.MALFORMED_EXECUTION_REQUEST
        )
    bundle, failure = _read_execution_inputs_v3(reader, request, recorder=recorder)
    if failure is not None:
        return _ExecutionInputsHydrationOutcomeV3(failure=failure)
    if bundle is None:
        return _failure_v3(
            _ExecutionInputsHydrationFailureCodeV3.EXECUTION_INPUT_DECODE_FAILED
        )
    return _hydrate_execution_inputs_v3_from_decoded(
        bundle,
        request,
        market_reader=market_reader,
        resolved_request=resolved_request,
        prepared_market_data=prepared_market_data,
        recorder=recorder,
    )

def _failure(
    code: _ExecutionInputsHydrationFailureCode, message: str
) -> _ExecutionInputsHydrationOutcome:
    return _ExecutionInputsHydrationOutcome(
        failure=_ExecutionInputsHydrationFailure(code=code, message=message)
    )


def _hydrate_execution_inputs(
    reader: ArtifactEnvelopeReader,
    request: BacktestExecutionRequest,
    *,
    market_reader: MarketBundleReader,
    resolved_request: ResolvedBacktestRequest | None = None,
) -> _ExecutionInputsHydrationOutcome:
    if type(request) is not BacktestExecutionRequest:
        return _failure(
            _ExecutionInputsHydrationFailureCode.MALFORMED_EXECUTION_REQUEST,
            "request must be exact BacktestExecutionRequest",
        )
    if resolved_request is not None and type(resolved_request) is not ResolvedBacktestRequest:
        return _failure(
            _ExecutionInputsHydrationFailureCode.MALFORMED_EXECUTION_REQUEST,
            "resolved_request must be exact ResolvedBacktestRequest or None",
        )
    ref = request.execution_input_bundle_ref
    if (
        ref.artifact_type != _ARTIFACT_TYPE
        or ref.schema_version != request.schema_version
    ):
        return _failure(
            _ExecutionInputsHydrationFailureCode.WRONG_EXECUTION_INPUT_BUNDLE_REF,
            "execution input ref must target "
            f"backtest_execution_input_bundle@{request.schema_version}",
        )

    try:
        source = reader.read(ref=ref)
    except ArtifactIntegrityError as error:
        return _failure(
            _ExecutionInputsHydrationFailureCode.EXECUTION_INPUT_TAMPERED,
            str(error),
        )
    except (ArtifactCatalogError, OSError) as error:
        return _failure(
            _ExecutionInputsHydrationFailureCode.EXECUTION_INPUT_UNAVAILABLE,
            str(error),
        )
    except Exception as error:  # provider failures are unavailable at this boundary
        return _failure(
            _ExecutionInputsHydrationFailureCode.EXECUTION_INPUT_UNAVAILABLE,
            str(error),
        )
    if type(source) is not ArtifactReadResult:
        return _failure(
            _ExecutionInputsHydrationFailureCode.EXECUTION_INPUT_UNAVAILABLE,
            "reader returned an invalid result",
        )
    if (
        source.source_bytes != canonical_bytes(source.envelope)
        or source.source_hash != canonical_sha256(source.envelope)
    ):
        return _failure(
            _ExecutionInputsHydrationFailureCode.EXECUTION_INPUT_TAMPERED,
            "reader source bytes or source hash do not match its envelope",
        )
    if ArtifactRef.from_envelope(source.envelope) != ref:
        return _failure(
            _ExecutionInputsHydrationFailureCode.EXECUTION_INPUT_TAMPERED,
            "returned envelope does not match requested ref",
        )

    try:
        decoded = _EXECUTION_INPUT_CATALOG.read(source.source_bytes)
    except (ArtifactIntegrityError, UnknownArtifactTypeError, UnsupportedSchemaVersionError) as error:
        return _failure(
            _ExecutionInputsHydrationFailureCode.EXECUTION_INPUT_TAMPERED,
            str(error),
        )
    except ArtifactDecodeError as error:
        return _failure(
            _ExecutionInputsHydrationFailureCode.EXECUTION_INPUT_DECODE_FAILED,
            str(error),
        )
    if decoded.envelope != source.envelope:
        return _failure(
            _ExecutionInputsHydrationFailureCode.EXECUTION_INPUT_TAMPERED,
            "decoded envelope differs from reader envelope",
        )
    bundle = decoded.artifact
    expected_bundle_type = (
        _DecodedExecutionInputBundle
        if request.schema_version == _SCHEMA_VERSION
        else _DecodedExecutionInputBundleV2
    )
    if type(bundle) is not expected_bundle_type:
        return _failure(
            _ExecutionInputsHydrationFailureCode.EXECUTION_INPUT_DECODE_FAILED,
            "catalog returned an invalid execution input bundle",
        )

    public_request = request.request
    if bundle.request_hash != public_request.request_hash:
        return _failure(
            _ExecutionInputsHydrationFailureCode.REQUEST_BINDING_MISMATCH,
            "bundle request_hash does not bind the request",
        )
    if bundle.build_artifact_manifest.manifest_hash != public_request.build_artifact_manifest_hash:
        return _failure(
            _ExecutionInputsHydrationFailureCode.BUILD_BINDING_MISMATCH,
            "bundle build manifest does not bind the request",
        )
    if market_reader.bundle_ref != public_request.market_bundle_ref:
        return _failure(
            _ExecutionInputsHydrationFailureCode.TARGET_BINDING_MISMATCH,
            "MarketBundleReader does not bind the request MarketBundleRef",
        )
    requirement_failure = market_reader.validate_requirements(
        required_streams=bundle.timeline_stream_keys
    )
    if requirement_failure is not None:
        return _failure(
            _ExecutionInputsHydrationFailureCode.TARGET_BINDING_MISMATCH,
            "MarketBundleReader does not provide the required streams",
        )
    cursor = market_reader.open_cursor(
        bundle.target_stream_key,
        batch_size=bundle.timeline_batch_size,
    )
    if isinstance(cursor, InputValidationFailure):
        return _failure(
            _ExecutionInputsHydrationFailureCode.TARGET_BINDING_MISMATCH,
            "target stream cannot be opened",
        )
    events: list[Any] = []
    try:
        while not cursor.exhausted:
            batch, cursor = market_reader.read_batch(cursor)
            events.extend(batch)
        target_stream = PrecomputedTargetStream(
            bundle.target_stream_key,
            tuple(events),
        )
    except Exception as error:
        return _failure(
            _ExecutionInputsHydrationFailureCode.EXECUTION_INPUT_UNAVAILABLE,
            str(error),
        )
    if (
        target_stream.target_stream_digest != public_request.target_stream_digest
        or bundle.execution_case_semantic_spec.target_stream_digest
        != public_request.target_stream_digest
    ):
        return _failure(
            _ExecutionInputsHydrationFailureCode.TARGET_BINDING_MISMATCH,
            "hydrated target stream does not bind the request",
        )
    if (
        bundle.execution_case_semantic_spec.semantic_spec_hash
        != public_request.execution_case_semantic_hash
    ):
        return _failure(
            _ExecutionInputsHydrationFailureCode.EXECUTION_CASE_SEMANTIC_HASH_MISMATCH,
            "bundle semantic spec does not bind the request",
        )
    if type(bundle) is _DecodedExecutionInputBundle:
        try:
            _validate_initial_template(
                bundle.initial_financial_state_template,
                bundle.execution_case_semantic_spec,
                public_request,
            )
        except (TypeError, ValueError) as error:
            return _failure(
                _ExecutionInputsHydrationFailureCode.INITIAL_STATE_BINDING_MISMATCH,
                str(error),
            )
        return _ExecutionInputsHydrationOutcome(
            result=_HydratedExecutionInputs(
                build_artifact_manifest=bundle.build_artifact_manifest,
                execution_case_semantic_spec=bundle.execution_case_semantic_spec,
                timeline_stream_keys=bundle.timeline_stream_keys,
                target_stream=target_stream,
                timeline_batch_size=bundle.timeline_batch_size,
                initial_financial_state_template=(
                    bundle.initial_financial_state_template
                ),
            )
        )

    if not isinstance(bundle, _DecodedExecutionInputBundleV2):
        return _failure(
            _ExecutionInputsHydrationFailureCode.EXECUTION_INPUT_DECODE_FAILED,
            "bundle reader returned the wrong decoded version",
        )
    composition_inputs = _HydratedExecutionCaseInputs(
        execution_case_semantic_spec=bundle.execution_case_semantic_spec,
        timeline_stream_keys=bundle.timeline_stream_keys,
        target_stream=target_stream,
        timeline_batch_size=bundle.timeline_batch_size,
        execution_case_plan=bundle.execution_case_plan,
    )
    try:
        if resolved_request is None:
            execution_case = _compose_execution_case_from_authority(
                request=public_request,
                semantic_run_id=bundle.semantic_run_id,
                market_reader=market_reader,
                hydrated_inputs=composition_inputs,
            )
        else:
            if (
                resolved_request.request != public_request
                or resolved_request.semantic_run_id != bundle.semantic_run_id
                or resolved_request.build_artifact_manifest
                != bundle.build_artifact_manifest
            ):
                raise ValueError("resolved request does not bind the execution bundle")
            execution_case = _compose_execution_case(
                resolved_request=resolved_request,
                market_reader=market_reader,
                hydrated_inputs=composition_inputs,
            )
    except (TypeError, ValueError) as error:
        return _failure(
            _ExecutionInputsHydrationFailureCode.EXECUTION_CASE_SEMANTIC_HASH_MISMATCH,
            str(error),
        )
    return _ExecutionInputsHydrationOutcome(
        result=_HydratedExecutionInputs(
            build_artifact_manifest=bundle.build_artifact_manifest,
            execution_case_semantic_spec=bundle.execution_case_semantic_spec,
            timeline_stream_keys=bundle.timeline_stream_keys,
            target_stream=target_stream,
            timeline_batch_size=bundle.timeline_batch_size,
            execution_case_plan=bundle.execution_case_plan,
            execution_case=execution_case,
        )
    )
