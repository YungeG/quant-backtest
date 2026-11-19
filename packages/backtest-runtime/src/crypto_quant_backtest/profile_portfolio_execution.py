"""Private profile-owned portfolio carrier; no market logic or publication I/O.

The definition exists before the request. Producer/transport references belong
in input8, never in the target digest or a recursive request-hash preimage.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from crypto_quant_domain import (
    ArtifactEnvelope, ArtifactRef, DomainId, IdentityNamespace,
    canonical_sha256,
)
from crypto_quant_market_data import InputValidationFailure

from .artifact_envelope_reader import ArtifactEnvelopeReader
from .engine import (
    EngineCancellationRequest, EngineExecutionOutcome, EngineExecutionResult, EngineFailure,
    ExecutionCase, ExecutionCaseIdentityFactory, ExecutionCaseIdentityManifest,
    ExecutionCaseIdentityRule, ExecutionCaseSemanticSpec, ResolvedFinancialState,
)
from .target_stream import PrecomputedTargetStream
from .timeline import DeterministicTimelineV2

from crypto_quant_trading.profiles.cn_a_share.portfolio_economic_v1 import (
    CnAShareCashDividendStateV1, CnASharePortfolioEconomicProjectionV1,
)

_DEFINITION_TYPE = "backtest_profile_portfolio_definition"
_ECONOMIC_EXCLUSIVE_SETTLEMENT_SPEC_VERSION = 2


@dataclass(frozen=True, slots=True)
class _ProfilePortfolioExecutionPlanV1:
    definition: ArtifactEnvelope
    financial_state: ResolvedFinancialState
    source_refs: tuple[tuple[str, ArtifactRef], ...] = ()

    def __post_init__(self) -> None:
        if (type(self.definition) is not ArtifactEnvelope
                or self.definition.artifact_type != _DEFINITION_TYPE
                or self.definition.schema_version != 1):
            raise TypeError("portfolio plan requires an exact profile definition@1")
        if type(self.financial_state) is not ResolvedFinancialState:
            raise TypeError("portfolio plan requires exact native financial state")
        refs = self.source_refs
        if (type(refs) is not tuple or any(type(v) is not tuple or len(v) != 2
                or type(v[0]) is not str or not v[0] or v[0] != v[0].strip()
                or type(v[1]) is not ArtifactRef for v in refs)
                or len({v[0] for v in refs}) != len(refs)
                or tuple(sorted(refs, key=lambda v: v[0])) != refs):
            raise ValueError("portfolio source references must have sorted unique roles")

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "execution_case_plan", "schema_version": 3,
                "definition": self.definition,
                "financial_state": self.financial_state, "source_refs": self.source_refs}


def _profile_portfolio_semantic_spec_from_case(
    case: _ResolvedProfilePortfolioCaseV1, *, spec_key: str, spec_version: int,
    identity_namespace: IdentityNamespace,
    identity_plan: tuple[ExecutionCaseIdentityRule, ...],
) -> ExecutionCaseSemanticSpec:
    timeline = case.timeline
    timeline_hash = canonical_sha256({
        "type": "execution_case_timeline_semantics_v2",
        "timeline_id": timeline.timeline_id,
        "market_bundle_ref": timeline.reader.bundle_ref,
        "market_stream_keys": timeline.stream_keys,
        "target_stream_digest": timeline.target_stream_digest,
        "window": timeline.window,
    })
    # Domain separation binds the whole frozen economic definition, not a
    # provider-selected subset, caller boolean, future quantity or future fill.
    definition = case.execution_case_plan.definition
    return ExecutionCaseSemanticSpec(
        1, spec_key, spec_version, case.case_key, case.case_version,
        identity_namespace, identity_plan, timeline_hash,
        case.target_stream.target_stream_digest,
        canonical_sha256({"role": "portfolio_decisions", "definition": definition}),
        canonical_sha256({"role": "portfolio_execution", "definition": definition}),
        canonical_sha256(case.financial_state),
        canonical_sha256({"role": "portfolio_snapshots", "definition": definition}),
        canonical_sha256({"role": "portfolio_run_end", "definition": definition}),
    )


@dataclass(frozen=True, slots=True)
class _ResolvedProfilePortfolioCaseV1:
    case_key: str
    case_version: int
    timeline: DeterministicTimelineV2
    target_stream: PrecomputedTargetStream
    timeline_batch_size: int
    execution_case_plan: _ProfilePortfolioExecutionPlanV1
    semantic_spec_hash: str
    identity_manifest: ExecutionCaseIdentityManifest | None = None
    semantic_spec: ExecutionCaseSemanticSpec | None = None

    def __post_init__(self) -> None:
        if (type(self.case_key) is not str or not self.case_key
                or self.case_key != self.case_key.strip()
                or type(self.case_version) is not int or self.case_version < 1):
            raise ValueError("profile portfolio case needs canonical key/version")
        if type(self.timeline) is not DeterministicTimelineV2:
            raise TypeError("profile portfolio requires an embedded-target timeline")
        if type(self.target_stream) is not PrecomputedTargetStream:
            raise TypeError("profile portfolio requires exact target stream")
        if self.timeline.target_stream_digest != self.target_stream.target_stream_digest:
            raise ValueError("profile portfolio timeline/target mismatch")
        if type(self.timeline_batch_size) is not int or self.timeline_batch_size < 1:
            raise ValueError("profile portfolio batch size must be positive")
        if type(self.execution_case_plan) is not _ProfilePortfolioExecutionPlanV1:
            raise TypeError("profile portfolio requires exact plan3")
        value = self.semantic_spec_hash
        if (type(value) is not str or len(value) != 71 or not value.startswith("sha256:")
                or any(c not in "0123456789abcdef" for c in value[7:])):
            raise ValueError("profile portfolio semantic hash must be canonical sha256")
        if self.semantic_spec is not None:
            if (type(self.semantic_spec) is not ExecutionCaseSemanticSpec
                    or self.semantic_spec.semantic_spec_hash != value
                    or self.semantic_spec.case_key != self.case_key
                    or self.semantic_spec.case_version != self.case_version):
                raise ValueError("profile portfolio semantic seal mismatch")
        if self.identity_manifest is not None and type(self.identity_manifest) is not ExecutionCaseIdentityManifest:
            raise TypeError("profile portfolio requires an exact identity manifest")

    @property
    def financial_state(self) -> ResolvedFinancialState:
        return self.execution_case_plan.financial_state

    @property
    def case_hash(self) -> str:
        return canonical_sha256(self)

    def verify_identity_manifest(self, semantic_run_id: str) -> bool:
        spec, manifest = self.semantic_spec, self.identity_manifest
        if spec is None or manifest is None or manifest.semantic_run_id != semantic_run_id:
            return False
        try:
            factory = ExecutionCaseIdentityFactory(semantic_run_id=semantic_run_id,
                namespace=spec.identity_namespace, identity_plan=spec.identity_plan)
            for rule in spec.identity_plan:
                if rule.domain_kind is None:
                    factory.event_id(rule.binding_key)
                else:
                    factory.domain_id(rule.binding_key)
            return factory.manifest() == manifest
        except (TypeError, ValueError):
            return False

    def domain_id(self, binding_key: str) -> DomainId:
        manifest = self.identity_manifest
        if manifest is None:
            raise ValueError("profile portfolio identity manifest is missing")
        binding = next((v for v in manifest.bindings if v.binding_key == binding_key), None)
        if binding is None or binding.domain_kind is None:
            raise ValueError("profile portfolio domain identity slot is missing")
        return DomainId(binding.domain_kind, binding.value)

    def event_id(self, binding_key: str) -> str:
        manifest = self.identity_manifest
        if manifest is None:
            raise ValueError("profile portfolio identity manifest is missing")
        binding = next((v for v in manifest.bindings if v.binding_key == binding_key), None)
        if binding is None or binding.domain_kind is not None:
            raise ValueError("profile portfolio event identity slot is missing")
        return binding.value

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "resolved_profile_portfolio_execution_case", "schema_version": 1,
            "case_key": self.case_key, "case_version": self.case_version,
            "timeline_id": self.timeline.timeline_id,
            "market_bundle_ref": self.timeline.reader.bundle_ref,
            "timeline_stream_keys": self.timeline.stream_keys,
            "timeline_window": self.timeline.window,
            "target_stream_digest": self.target_stream.target_stream_digest,
            "timeline_batch_size": self.timeline_batch_size,
            # Source/producer refs bind transport bytes and are cold-verified by
            # the profile against this definition, not added to economic identity.
            "execution_case_plan": {"type": "execution_case_plan", "schema_version": 3,
                "definition": self.execution_case_plan.definition,
                "financial_state": self.financial_state},
            "semantic_spec_hash": self.semantic_spec_hash,
            "identity_manifest": self.identity_manifest,
            "semantic_spec": self.semantic_spec}


def _economic_profile_prefix_v1(definition: ArtifactEnvelope) -> str:
    if (type(definition) is not ArtifactEnvelope or definition.artifact_type != _DEFINITION_TYPE
            or type(definition.schema_version) is not int or definition.schema_version not in (2, 3)):
        raise TypeError("economic plan requires exact definition@2")
    payload = definition.payload
    from collections.abc import Mapping
    if (not isinstance(payload, Mapping) or payload.get("type") != "cn_a_share_portfolio_economic_development_definition"
            or type(payload.get("schema_version")) is not int
            or payload["schema_version"] != definition.schema_version - 1):
        raise ValueError("economic definition/profile version tuple mismatch")
    return ("cn.portfolio.shared-cny.economic.development.v1" if definition.schema_version == 2
        else "cn.portfolio.shared-cny.economic.development.v2")


@dataclass(frozen=True, slots=True)
class _ProfilePortfolioExecutionPlanV2:
    definition: ArtifactEnvelope
    financial_state: ResolvedFinancialState
    initial_dividend_state: CnAShareCashDividendStateV1
    initial_economic_projection: CnASharePortfolioEconomicProjectionV1
    source_refs: tuple[tuple[str, ArtifactRef], ...]

    def __post_init__(self) -> None:
        _economic_profile_prefix_v1(self.definition)
        if type(self.financial_state) is not ResolvedFinancialState:
            raise TypeError("economic plan requires exact native financial state")
        if (type(self.initial_dividend_state) is not CnAShareCashDividendStateV1
                or type(self.initial_economic_projection) is not CnASharePortfolioEconomicProjectionV1):
            raise TypeError("economic plan requires exact initial economic values")
        state, projection = self.initial_dividend_state, self.initial_economic_projection
        if (state.claims or state.as_of != projection.as_of or state.account_id != projection.account_id
                or projection.dividend_state_hash != canonical_sha256(state)
                or projection.base_snapshot != projection.snapshot
                or self.financial_state.initial_snapshot != projection.base_snapshot):
            raise ValueError("economic initial native/state/projection binding mismatch")
        refs = self.source_refs
        if (type(refs) is not tuple or any(type(row) is not tuple or len(row) != 2
                or type(row[0]) is not str or type(row[1]) is not ArtifactRef for row in refs)):
            raise TypeError("economic source refs must be exact role/ref tuples")
        expected = (("cash_dividend_action_set", "cn_a_share_cash_dividend_action_set", 1),
            ("definition", _DEFINITION_TYPE, self.definition.schema_version), ("target_stream", "backtest_target_stream", 1))
        if tuple((role, ref.artifact_type, ref.schema_version) for role, ref in refs) != expected:
            raise ValueError("economic source refs require exact sorted three roles")
        if refs[1][1] != ArtifactRef.from_envelope(self.definition):
            raise ValueError("economic definition ref does not bind envelope")

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "execution_case_plan", "schema_version": 4,
            "definition": self.definition, "financial_state": self.financial_state,
            "initial_dividend_state": self.initial_dividend_state,
            "initial_economic_projection": self.initial_economic_projection, "source_refs": self.source_refs}


@dataclass(frozen=True, slots=True)
class _ResolvedProfilePortfolioCaseV2:
    case_key: str
    case_version: int
    timeline: DeterministicTimelineV2
    target_stream: PrecomputedTargetStream
    timeline_batch_size: int
    execution_case_plan: _ProfilePortfolioExecutionPlanV2
    semantic_spec_hash: str
    identity_manifest: ExecutionCaseIdentityManifest | None = None
    semantic_spec: ExecutionCaseSemanticSpec | None = None

    def __post_init__(self) -> None:
        if (type(self.case_key) is not str or not self.case_key
                or self.case_key != self.case_key.strip()
                or type(self.case_version) is not int or self.case_version < 1):
            raise ValueError("profile portfolio case needs canonical key/version")
        if self.case_key not in ("cn.portfolio.shared-cny.economic.development.v1", "cn.portfolio.shared-cny.economic.development.v2") or self.case_version != 1:
            raise ValueError("economic case key/version mismatch")
        if self.timeline_batch_size != 64:
            raise ValueError("economic case batch size must be64")
        if type(self.timeline) is not DeterministicTimelineV2:
            raise TypeError("profile portfolio requires an embedded-target timeline")
        if type(self.target_stream) is not PrecomputedTargetStream:
            raise TypeError("profile portfolio requires exact target stream")
        if self.timeline.target_stream_digest != self.target_stream.target_stream_digest:
            raise ValueError("profile portfolio timeline/target mismatch")
        if type(self.timeline_batch_size) is not int or self.timeline_batch_size < 1:
            raise ValueError("profile portfolio batch size must be positive")
        if type(self.execution_case_plan) is not _ProfilePortfolioExecutionPlanV2:
            raise TypeError("profile portfolio requires exact plan4")
        if self.case_key != _economic_profile_prefix_v1(self.execution_case_plan.definition):
            raise ValueError("economic case key/version mismatch")
        value = self.semantic_spec_hash
        if (type(value) is not str or len(value) != 71 or not value.startswith("sha256:")
                or any(c not in "0123456789abcdef" for c in value[7:])):
            raise ValueError("profile portfolio semantic hash must be canonical sha256")
        if self.semantic_spec is not None:
            if (type(self.semantic_spec) is not ExecutionCaseSemanticSpec
                    or self.semantic_spec.semantic_spec_hash != value
                    or self.semantic_spec.case_key != self.case_key
                    or self.semantic_spec.case_version != self.case_version):
                raise ValueError("profile portfolio semantic seal mismatch")
        if self.identity_manifest is not None and type(self.identity_manifest) is not ExecutionCaseIdentityManifest:
            raise TypeError("profile portfolio requires an exact identity manifest")

    @property
    def financial_state(self) -> ResolvedFinancialState:
        return self.execution_case_plan.financial_state

    @property
    def case_hash(self) -> str:
        return canonical_sha256(self)

    def verify_identity_manifest(self, semantic_run_id: str) -> bool:
        spec, manifest = self.semantic_spec, self.identity_manifest
        if spec is None or manifest is None or manifest.semantic_run_id != semantic_run_id:
            return False
        try:
            factory = ExecutionCaseIdentityFactory(semantic_run_id=semantic_run_id,
                namespace=spec.identity_namespace, identity_plan=spec.identity_plan)
            for rule in spec.identity_plan:
                if rule.domain_kind is None:
                    factory.event_id(rule.binding_key)
                else:
                    factory.domain_id(rule.binding_key)
            return factory.manifest() == manifest
        except (TypeError, ValueError):
            return False

    def domain_id(self, binding_key: str) -> DomainId:
        manifest = self.identity_manifest
        if manifest is None:
            raise ValueError("profile portfolio identity manifest is missing")
        binding = next((v for v in manifest.bindings if v.binding_key == binding_key), None)
        if binding is None or binding.domain_kind is None:
            raise ValueError("profile portfolio domain identity slot is missing")
        return DomainId(binding.domain_kind, binding.value)

    def event_id(self, binding_key: str) -> str:
        manifest = self.identity_manifest
        if manifest is None:
            raise ValueError("profile portfolio identity manifest is missing")
        binding = next((v for v in manifest.bindings if v.binding_key == binding_key), None)
        if binding is None or binding.domain_kind is not None:
            raise ValueError("profile portfolio event identity slot is missing")
        return binding.value

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "resolved_profile_portfolio_execution_case", "schema_version": 2,
            "case_key": self.case_key, "case_version": self.case_version,
            "timeline_id": self.timeline.timeline_id,
            "market_bundle_ref": self.timeline.reader.bundle_ref,
            "timeline_stream_keys": self.timeline.stream_keys,
            "timeline_window": self.timeline.window,
            "target_stream_digest": self.target_stream.target_stream_digest,
            "timeline_batch_size": self.timeline_batch_size,
            # Source/producer refs bind transport bytes and are cold-verified by
            # the profile against this definition, not added to economic identity.
            "execution_case_plan": {"type": "execution_case_plan", "schema_version": 4,
                "definition": self.execution_case_plan.definition,
                "financial_state": self.financial_state,
                "initial_dividend_state": self.execution_case_plan.initial_dividend_state,
                "initial_economic_projection": self.execution_case_plan.initial_economic_projection},
            "semantic_spec_hash": self.semantic_spec_hash,
            "identity_manifest": self.identity_manifest,
            "semantic_spec": self.semantic_spec}


def _profile_portfolio_economic_semantic_spec_from_case_v1(
    case: _ResolvedProfilePortfolioCaseV2, *, spec_key: str, spec_version: int,
    identity_namespace: IdentityNamespace,
    identity_plan: tuple[ExecutionCaseIdentityRule, ...],
) -> ExecutionCaseSemanticSpec:
    if type(spec_version) is not int or spec_version not in (1, 2):
        raise ValueError("unsupported economic execution spec version for definition")
    timeline = case.timeline
    timeline_hash = canonical_sha256({
        "type": "execution_case_timeline_semantics_v2",
        "timeline_id": timeline.timeline_id,
        "market_bundle_ref": timeline.reader.bundle_ref,
        "market_stream_keys": timeline.stream_keys,
        "target_stream_digest": timeline.target_stream_digest,
        "window": timeline.window,
    })
    # Domain separation binds the whole frozen economic definition, not a
    # provider-selected subset, caller boolean, future quantity or future fill.
    definition = case.execution_case_plan.definition
    return ExecutionCaseSemanticSpec(
        1, spec_key, spec_version, case.case_key, case.case_version,
        identity_namespace, identity_plan, timeline_hash,
        case.target_stream.target_stream_digest,
        canonical_sha256({"role": "portfolio_decisions", "definition": definition}),
        canonical_sha256({"role": "portfolio_execution", "definition": definition}),
        canonical_sha256({"type": "cn_a_share_portfolio_economic_initial_state", "schema_version": 1,
            "financial_state": case.financial_state,
            "dividend_state": case.execution_case_plan.initial_dividend_state,
            "economic_projection": case.execution_case_plan.initial_economic_projection}),
        canonical_sha256({"role": "portfolio_snapshots", "definition": definition}),
        canonical_sha256({"role": "portfolio_run_end", "definition": definition}),
    )


_RuntimeExecutionCase = ExecutionCase | _ResolvedProfilePortfolioCaseV1 | _ResolvedProfilePortfolioCaseV2


@runtime_checkable
class _ProfilePortfolioEngine(Protocol):
    def run(self, case: _RuntimeExecutionCase | InputValidationFailure, *,
            cancellation: EngineCancellationRequest | None = None) -> EngineExecutionOutcome: ...

    def verify_result(self, case: _ResolvedProfilePortfolioCaseV1,
                      result: EngineExecutionResult) -> None: ...

    def verify_cached(self, case: _ResolvedProfilePortfolioCaseV1,
                      publication_ref: ArtifactRef) -> None: ...


@runtime_checkable
class _PortfolioExecutionProvider(Protocol):
    @property
    def profile_digest(self) -> str: ...

    def build_portfolio_engine(self, *, case: _ResolvedProfilePortfolioCaseV1,
                               artifact_reader: ArtifactEnvelopeReader) -> _ProfilePortfolioEngine: ...


@runtime_checkable
class _EconomicPortfolioEngine(_ProfilePortfolioEngine, Protocol):
    def verify_failure(self, case: _ResolvedProfilePortfolioCaseV2, failure: EngineFailure) -> None: ...
