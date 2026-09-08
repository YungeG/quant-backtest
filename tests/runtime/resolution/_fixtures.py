from __future__ import annotations

from dataclasses import dataclass, replace

from crypto_quant_backtest import (
    ArtifactInstallMode,
    BacktestProfileRegistry,
    BacktestRequest,
    BuildArtifactManifest,
    BuildArtifactRef,
    BuildArtifactRole,
    BuildProvenance,
    ExecutionAccountProfileRegistration,
    MarketSemanticsProfileRegistration,
    RequestedResultGrade,
    RuntimeLibraryRef,
    SimulationProfileRegistration,
    SourceTreeState,
    StrategyFamily,
)
from crypto_quant_domain import CurrencyId, UtcInstant, canonical_sha256
from crypto_quant_market_data import MarketBundleCapability, MarketBundleManifest, MarketBundleRef
from crypto_quant_trading import ProfileComponentRef
from tests.runtime.engine._fixtures import SyntheticExecutionCaseBuilder
from tests.support.synthetic_market import (
    SYNTHETIC_PROFILE_KEY,
    SyntheticCashDevelopmentProfile,
    TestProfileRegistry,
    build_synthetic_bundle,
    build_synthetic_execution_case,
    build_synthetic_target_stream,
)


USD = CurrencyId("USD")
BAR_OPEN = MarketBundleCapability("bar_open", 1)
TARGET_STREAM = MarketBundleCapability("precomputed_target_stream", 1)


@dataclass(frozen=True, slots=True)
class MarketProfileVariant:
    component_manifest: tuple[ProfileComponentRef, ...]
    variant: str

    @property
    def profile_digest(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "market_profile_variant",
            "component_manifest": self.component_manifest,
            "variant": self.variant,
        }


def development_profile() -> SyntheticCashDevelopmentProfile:
    lookup = TestProfileRegistry(allow_development_profiles=True).lookup(
        SYNTHETIC_PROFILE_KEY
    )
    assert lookup.profile is not None
    return lookup.profile


def profile_registry(
    *,
    extra_market_capabilities: tuple[MarketBundleCapability, ...] = (),
    market_profile: MarketSemanticsProfileRegistration | None = None,
) -> BacktestProfileRegistry:
    profile = development_profile()
    market = market_profile or MarketSemanticsProfileRegistration(
        profile_key=f"{SYNTHETIC_PROFILE_KEY}.market",
        profile_version=1,
        profile_digest=profile.market_semantics.profile_digest,
        implementation=profile.market_semantics,
        venue_id=profile.execution_account.venue_id,
        required_bundle_capabilities=(BAR_OPEN,) + extra_market_capabilities,
        component_manifest=profile.market_semantics.component_manifest,
        grade=RequestedResultGrade.DEVELOPMENT,
        limitations=("synthetic_market_profile",),
        decision_grade_eligible=False,
    )
    simulation = SimulationProfileRegistration(
        profile_key=f"{SYNTHETIC_PROFILE_KEY}.simulation",
        profile_version=1,
        profile_digest=profile.simulation.profile_digest,
        implementation=profile.simulation,
        engine_kind="bar",
        supported_strategy_families=(StrategyFamily.PRECOMPUTED_TARGET,),
        required_bundle_capabilities=(BAR_OPEN,),
        component_manifest=profile.simulation.component_manifest,
        grade=RequestedResultGrade.DEVELOPMENT,
        limitations=("synthetic_market_profile",),
        decision_grade_eligible=False,
    )
    account = ExecutionAccountProfileRegistration(
        profile_key=f"{SYNTHETIC_PROFILE_KEY}.account",
        profile_version=1,
        profile_digest=profile.execution_account.profile_digest,
        implementation=profile.execution_account,
        account_id=profile.execution_account.account_id,
        venue_id=profile.execution_account.venue_id,
        account_type=profile.execution_account.account_type,
        margin_mode=profile.execution_account.margin_mode,
        supported_reporting_currencies=(USD,),
        grade=RequestedResultGrade.DEVELOPMENT,
        limitations=("synthetic_market_profile",),
        decision_grade_eligible=False,
    )
    return BacktestProfileRegistry(
        market_semantics_profiles=(market,),
        simulation_profiles=(simulation,),
        execution_account_profiles=(account,),
    )


def bundle_manifest() -> MarketBundleManifest:
    return build_synthetic_bundle(development_profile()).manifest


def build_manifest(
    *,
    provenance: BuildProvenance | None = None,
    runtime_mode: ArtifactInstallMode = ArtifactInstallMode.WHEEL,
    runtime_content_hash: str | None = "sha256:" + "55" * 32,
    runtime_source_state: SourceTreeState = SourceTreeState.CLEAN,
    market_profile_digest: str | None = None,
) -> BuildArtifactManifest:
    profile = development_profile()
    profile_digests = {
        f"{SYNTHETIC_PROFILE_KEY}.market": market_profile_digest
        or profile.market_semantics.profile_digest,
        f"{SYNTHETIC_PROFILE_KEY}.simulation": profile.simulation.profile_digest,
        f"{SYNTHETIC_PROFILE_KEY}.account": profile.execution_account.profile_digest,
    }
    artifacts = (
        BuildArtifactRef(
            role=BuildArtifactRole.DECISION_SOURCE,
            artifact_key="precomputed-target-stream-adapter",
            artifact_version="0.1.0",
            install_mode=ArtifactInstallMode.WHEEL,
            source_tree_state=SourceTreeState.CLEAN,
            content_hash="sha256:" + "11" * 32,
            source_snapshot_hash=None,
        ),
        BuildArtifactRef(
            role=BuildArtifactRole.TRADING_DOMAIN,
            artifact_key="crypto-quant-domain",
            artifact_version="0.1.0",
            install_mode=ArtifactInstallMode.WHEEL,
            source_tree_state=SourceTreeState.CLEAN,
            content_hash="sha256:" + "22" * 32,
            source_snapshot_hash=None,
        ),
        BuildArtifactRef(
            role=BuildArtifactRole.TRADING_KERNEL,
            artifact_key="crypto-quant-trading",
            artifact_version="0.1.0",
            install_mode=ArtifactInstallMode.WHEEL,
            source_tree_state=SourceTreeState.CLEAN,
            content_hash="sha256:" + "33" * 32,
            source_snapshot_hash=None,
        ),
        BuildArtifactRef(
            role=BuildArtifactRole.MARKET_DATA_CONTRACTS,
            artifact_key="crypto-quant-market-data",
            artifact_version="0.1.0",
            install_mode=ArtifactInstallMode.WHEEL,
            source_tree_state=SourceTreeState.CLEAN,
            content_hash="sha256:" + "44" * 32,
            source_snapshot_hash=None,
        ),
        BuildArtifactRef(
            role=BuildArtifactRole.BACKTEST_RUNTIME,
            artifact_key="crypto-quant-backtest",
            artifact_version="0.1.0",
            install_mode=runtime_mode,
            source_tree_state=runtime_source_state,
            content_hash=runtime_content_hash,
            source_snapshot_hash=None,
        ),
        *(
            BuildArtifactRef(
                role=BuildArtifactRole.PROFILE_COMPONENT,
                artifact_key=key,
                artifact_version="1",
                install_mode=ArtifactInstallMode.WHEEL,
                source_tree_state=SourceTreeState.CLEAN,
                content_hash=digest,
                source_snapshot_hash=None,
            )
            for key, digest in sorted(profile_digests.items())
        ),
    )
    return BuildArtifactManifest(
        schema_version=1,
        build_key="synthetic.backtest.build.v1",
        artifacts=artifacts,
        dependency_lock_hash="sha256:" + "66" * 32,
        runtime_libraries=(
            RuntimeLibraryRef(
                library_key="python",
                version="3.13.5",
                content_hash="sha256:" + "77" * 32,
            ),
        ),
        container_image_digest=None,
        provenance=provenance
        or BuildProvenance(
            git_commit="0e481d4f9e06f073446749149756f38ea0054739",
            hostname="builder-a",
            source_root="/workspace/backtest",
            built_at=UtcInstant(1_000),
        ),
    )


def request(
    manifest: BuildArtifactManifest | None = None,
    *,
    bundle: MarketBundleManifest | None = None,
    grade: RequestedResultGrade = RequestedResultGrade.DEVELOPMENT,
    target_stream_digest: str | None = None,
) -> BacktestRequest:
    profile = development_profile()
    case = build_synthetic_execution_case(profile, timeline_batch_size=1)
    spec = SyntheticExecutionCaseBuilder().semantic_spec()
    if target_stream_digest is not None:
        spec = replace(spec, target_stream_digest=target_stream_digest)
    selected_build = manifest or build_manifest()
    selected_bundle = bundle or bundle_manifest()
    return BacktestRequest(
        schema_version=1,
        experiment_id="synthetic-cash-resolution",
        timeline_window=case.timeline.window,
        market_semantics_profile_key=f"{SYNTHETIC_PROFILE_KEY}.market",
        simulation_profile_key=f"{SYNTHETIC_PROFILE_KEY}.simulation",
        execution_account_profile_key=f"{SYNTHETIC_PROFILE_KEY}.account",
        execution_account_id=profile.execution_account.account_id,
        reporting_currency=USD,
        market_bundle_ref=MarketBundleRef.from_manifest(selected_bundle),
        target_stream_digest=spec.target_stream_digest,
        execution_case_semantic_hash=spec.semantic_spec_hash,
        master_random_seed=7,
        build_artifact_manifest_hash=selected_build.manifest_hash,
        strategy_family=StrategyFamily.PRECOMPUTED_TARGET,
        engine_kind="bar",
        result_grade_requested=grade,
    )


def market_profile_variant() -> MarketSemanticsProfileRegistration:
    profile = development_profile()
    implementation = MarketProfileVariant(
        component_manifest=profile.market_semantics.component_manifest,
        variant="changed-market-profile-code-and-config",
    )
    return MarketSemanticsProfileRegistration(
        profile_key=f"{SYNTHETIC_PROFILE_KEY}.market",
        profile_version=2,
        profile_digest=implementation.profile_digest,
        implementation=implementation,
        venue_id=profile.execution_account.venue_id,
        required_bundle_capabilities=(BAR_OPEN,),
        component_manifest=profile.market_semantics.component_manifest,
        grade=RequestedResultGrade.DEVELOPMENT,
        limitations=("synthetic_market_profile", "profile_variant"),
        decision_grade_eligible=False,
    )


def bundle_variant() -> MarketBundleManifest:
    original = bundle_manifest()
    return MarketBundleManifest.build(
        bundle_key="fixture.engine.bundle.variant.v1",
        schema_version=original.schema_version,
        coverage_start=original.coverage_start,
        coverage_end_exclusive=original.coverage_end_exclusive,
        instrument_catalog_hash=original.instrument_catalog_hash,
        capabilities=original.capabilities,
        streams=original.streams,
    )


def provenance_variant(manifest: BuildArtifactManifest) -> BuildArtifactManifest:
    return replace(
        manifest,
        provenance=BuildProvenance(
            git_commit="ffffffffffffffffffffffffffffffffffffffff",
            hostname="builder-b",
            source_root="/different/absolute/path",
            built_at=UtcInstant(9_999),
        ),
    )
