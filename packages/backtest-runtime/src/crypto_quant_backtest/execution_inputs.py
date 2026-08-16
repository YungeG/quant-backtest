from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any

from crypto_quant_domain import (
    ArtifactCatalogError,
    ArtifactDecodeError,
    ArtifactEnvelope,
    ArtifactIntegrityError,
    ArtifactReadResult,
    ArtifactRef,
    ArtifactSchemaRegistration,
    DomainIdKind,
    IdentityNamespace,
    SchemaCatalog,
    UnknownArtifactTypeError,
    UnsupportedSchemaVersionError,
    UtcInstant,
    canonical_bytes,
    canonical_sha256,
)

from .engine import ExecutionCaseIdentityRule, ExecutionCaseSemanticSpec
from .ports import ArtifactEnvelopeReader
from .resolution import (
    ArtifactInstallMode,
    BacktestRequest,
    BuildArtifactManifest,
    BuildArtifactRef,
    BuildArtifactRole,
    BuildProvenance,
    RuntimeLibraryRef,
    SourceTreeState,
)

_ARTIFACT_TYPE = "backtest_execution_input_bundle"
_SCHEMA_VERSION = 1
_TEMPLATE_TYPE = "backtest_initial_financial_state_template"
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


@dataclass(frozen=True, slots=True)
class _ExecutionInputsHydrationFailure:
    code: _ExecutionInputsHydrationFailureCode
    message: str


@dataclass(frozen=True, slots=True)
class _HydratedExecutionInputs:
    build_artifact_manifest: BuildArtifactManifest
    execution_case_semantic_spec: ExecutionCaseSemanticSpec
    timeline_stream_keys: tuple[str, ...]
    target_stream_key: str
    timeline_batch_size: int
    initial_financial_state_template: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class _ExecutionInputsHydrationOutcome:
    result: _HydratedExecutionInputs | None = None
    failure: _ExecutionInputsHydrationFailure | None = None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.failure is None):
            raise ValueError("hydration outcome requires exactly one result or failure")


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
class BacktestExecutionRequest:
    schema_version: int
    request: BacktestRequest
    execution_input_bundle_ref: ArtifactRef

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != _SCHEMA_VERSION:
            raise ValueError("BacktestExecutionRequest schema_version must be 1")
        if type(self.request) is not BacktestRequest:
            raise TypeError("request must be exact BacktestRequest")
        if type(self.execution_input_bundle_ref) is not ArtifactRef:
            raise TypeError("execution_input_bundle_ref must be exact ArtifactRef")
        if (
            self.execution_input_bundle_ref.artifact_type != _ARTIFACT_TYPE
            or self.execution_input_bundle_ref.schema_version != _SCHEMA_VERSION
        ):
            raise ValueError("execution_input_bundle_ref must target backtest_execution_input_bundle@1")

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

    return ExecutionCaseSemanticSpec(
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


_EXECUTION_INPUT_CATALOG = SchemaCatalog(
    (
        ArtifactSchemaRegistration(
            artifact_type="backtest_execution_input_bundle",
            schema_version=1,
            payload_reader=_read_execution_input_payload,
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
    return _EXECUTION_INPUT_CATALOG.write_current(_ARTIFACT_TYPE, payload).envelope


def _failure(
    code: _ExecutionInputsHydrationFailureCode, message: str
) -> _ExecutionInputsHydrationOutcome:
    return _ExecutionInputsHydrationOutcome(
        failure=_ExecutionInputsHydrationFailure(code=code, message=message)
    )


def _hydrate_execution_inputs(
    reader: ArtifactEnvelopeReader,
    request: BacktestExecutionRequest,
) -> _ExecutionInputsHydrationOutcome:
    if type(request) is not BacktestExecutionRequest:
        return _failure(
            _ExecutionInputsHydrationFailureCode.MALFORMED_EXECUTION_REQUEST,
            "request must be exact BacktestExecutionRequest",
        )
    ref = request.execution_input_bundle_ref
    if ref.artifact_type != _ARTIFACT_TYPE or ref.schema_version != _SCHEMA_VERSION:
        return _failure(
            _ExecutionInputsHydrationFailureCode.WRONG_EXECUTION_INPUT_BUNDLE_REF,
            "execution input ref must target backtest_execution_input_bundle@1",
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
    if type(bundle) is not _DecodedExecutionInputBundle:
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
    if bundle.execution_case_semantic_spec.target_stream_digest != public_request.target_stream_digest:
        return _failure(
            _ExecutionInputsHydrationFailureCode.TARGET_BINDING_MISMATCH,
            "bundle target digest does not bind the request",
        )
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
    if bundle.execution_case_semantic_spec.semantic_spec_hash != public_request.execution_case_semantic_hash:
        return _failure(
            _ExecutionInputsHydrationFailureCode.EXECUTION_CASE_SEMANTIC_HASH_MISMATCH,
            "bundle semantic spec does not bind the request",
        )
    return _ExecutionInputsHydrationOutcome(
        result=_HydratedExecutionInputs(
            build_artifact_manifest=bundle.build_artifact_manifest,
            execution_case_semantic_spec=bundle.execution_case_semantic_spec,
            timeline_stream_keys=bundle.timeline_stream_keys,
            target_stream_key=bundle.target_stream_key,
            timeline_batch_size=bundle.timeline_batch_size,
            initial_financial_state_template=bundle.initial_financial_state_template,
        )
    )
