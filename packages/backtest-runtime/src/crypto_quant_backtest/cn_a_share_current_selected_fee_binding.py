"""Runtime fan-in for frozen current-selected A-share fee authorities."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, fields, replace
from typing import cast

from crypto_quant_domain import (
    Fill,
    Order,
    OrderSide,
    Rate,
    Scale,
    UtcInstant,
    VenueId,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_market_data import MarketBundleManifest, MarketEvent
from crypto_quant_trading.profiles.cn_a_share import (
    CnAShareCashFeeRuleQueryV2,
    CnAShareCashMarketFeePolicyV2,
    CnAShareCashStampDutyTaxPolicyV2,
    CnAShareExecutionAccessRoute,
    CnAShareFeeExecutionAuthorityV2,
    CnAShareFeeExecutionBindingFailureV2,
    CnAShareFeeExecutionBindingV2,
    CnAShareFeeExecutionScopeV2,
    CnAShareFeeExecutionSelectionV2,
    CnAShareFeeProductClass,
    CnAShareFeeQueryConstructionFailureV2,
    CnAShareFeeRuleSourceRef,
    CnAShareFeeTradeMechanism,
    CnAShareMarketFeeBandV2,
    CnAShareMarketFeeRuleBookV2,
    CnAShareStampDutyBandV2,
    CnAShareStampDutyRuleBookV2,
    create_cn_a_share_fee_execution_authority_v2,
)
from crypto_quant_trading.profiles.cn_a_share import (
    bind_cn_a_share_fee_execution_v2 as bind_kernel_fee_execution_v2,
)
from crypto_quant_trading.profiles.cn_a_share import commission_tax_v2 as kernel_v2

from .cn_a_share_fee_v2_binding import (
    _reconstructed_build,
    _reconstructed_kernel_binding,
    _reconstructed_profile,
    _reconstructed_semantic_spec,
)
from .cn_a_share_profile import CnAShareResolvedProfile
from .engine import ExecutionCaseSemanticSpec
from .resolution import BuildArtifactManifest, BuildArtifactRef, BuildArtifactRole

__all__ = (
    "CnAShareCurrentSelectedFeeBindingV2",
    "CnAShareCurrentSelectedFeePreparedExecutionV2",
    "prepare_cn_a_share_current_selected_fee_execution_v2",
)

_MANIFEST_HASH = (
    "sha256:28fdfafe241c48cd4a12a8b7467ccfafdb1b2b28881e0608d938cbb3b4853989"
)
_MANIFEST_CONTENT_HASH = (
    "sha256:068420713a257cac40c8b3590d4580da5af090a226656bf64fefe4e63bc59182"
)
_DECLARATION_HASH = (
    "sha256:4b21421bbe112d47a63ff03578dcb2215946e394d9971ab39a65c381d3d697d1"
)
_SNAPSHOT_HASH = (
    "sha256:747e5c88fd2810ca05841cc6bb3c9534fbfc203ccad3e0903dd3f14e25a8a5c8"
)
_COVERAGE_HASH = (
    "sha256:5cbcc37871999b334709d1823f1c40ce6cdf73480f410f821cf4ebd38ceec9bb"
)
_MARKET_BOOK_HASH = (
    "sha256:7dc7d6316ff8e7c88435bb7a070adc18fe9f18db6fd79fd19f927d88b6384c40"
)
_STAMP_BOOK_HASH = (
    "sha256:f8ba2eae8d6d4eefb119a864ffc2c170b97ba0eb0537371ab4caf65bb25b01cb"
)
_START = 1_783_267_200_000_000_000
_END = 1_785_427_200_000_000_000
_CAPABILITY = "cn_a_share.current-selected-development-rule-authorities@2"
_SCALE = Scale(2)
_DIMENSIONS = (
    "calendar",
    "order_rules",
    "market_fees",
    "stamp_duty",
    "corporate_action_entitlements",
)
_EVENT_HASHES = (
    "sha256:90afd657c7bc4d94d03bf71d00bc66ecd54d089ea3e184ddc3e6f0bdc78ceb18",
    "sha256:9166dcd93958f0d563d0845c0464361fe4a400e97defe7b43e5095b1f4e8797a",
    "sha256:887f557718a5d4289b8e53342c5d927313e36fb0eac4dd841263fb9bbb597488",
    "sha256:1deb5374c704488ce2ce362712ec7c7fcc0e9eaa67df96e4ebd970e323933d9a",
    "sha256:5ceaa462c1da9cd76065735354c34a69ea60d622b7e718a8fda14b84bdecdf59",
)
_QUALIFICATION = {
    "decision_grade_eligible": False,
    "deployment_authorized": False,
    "development_projection_authorized": True,
    "live_eligible": False,
    "official_successor_closure_complete": False,
    "provider_authority_qualified": False,
    "provider_completeness_qualified": False,
    "rule_coverage_qualified": False,
}
_COVERAGE_FIELDS = {
    "coverage_semantics",
    "declaration_hash",
    "dimension_interval_evidence",
    "finite_development_interval_coverage_complete",
    "qualification",
    "report_hash",
    "schema_version",
    "snapshot_hash",
    "snapshot_key",
    "snapshot_version",
    "target_from",
    "target_scope",
    "target_to_exclusive",
    "type",
}
_SNAPSHOT_KEY = (
    "equity.cn_a_share.current-selected-development.xshe.domestic."
    "ordinary-a-share.2026-07.v1"
)


def _mapping(name: str, value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or not all(type(key) is str for key in value):
        raise TypeError(f"{name} must be a canonical mapping")
    return value


def _source_refs(value: object) -> tuple[CnAShareFeeRuleSourceRef, ...]:
    if not isinstance(value, (tuple, list)):
        raise TypeError("source_refs must be a sequence")
    refs = tuple(
        CnAShareFeeRuleSourceRef(
            cast(str, _mapping("source_ref", item)["source_key"]),
            cast(str, _mapping("source_ref", item)["source_hash"]),
        )
        for item in value
    )
    return tuple(sorted(refs, key=lambda item: (item.source_key, item.source_hash)))


def _instant(value: object) -> UtcInstant:
    return UtcInstant(cast(int, _mapping("instant", value)["epoch_nanoseconds"]))


def _rate(value: object) -> Rate:
    data = _mapping("rate", value)
    return Rate(
        cast(int, data["units"]),
        Scale(cast(int, data["scale"])),
        cast(str, data["basis"]),
    )


def _market_book(body: object) -> CnAShareMarketFeeRuleBookV2:
    data = _mapping("market fee authority", body)
    bands = []
    for value in cast(tuple[object, ...], data["bands"]):
        band = _mapping("market fee band", value)
        bands.append(
            CnAShareMarketFeeBandV2(
                VenueId(cast(Mapping[str, str], band["venue_id"])["value"]),
                _instant(band["effective_from"]),
                _instant(band["effective_to_exclusive"]),
                cast(bool, band["handling_applies"]),
                _rate(band["handling_rate"]),
                _source_refs(band["handling_source_refs"]),
                cast(bool, band["regulatory_applies"]),
                _rate(band["regulatory_rate"]),
                _source_refs(band["regulatory_source_refs"]),
                cast(bool, band["chinaclear_transfer_applies"]),
                _rate(band["chinaclear_transfer_rate"]),
                _source_refs(band["chinaclear_transfer_source_refs"]),
                cast(bool, band["hkscc_transfer_applies"]),
                _rate(band["hkscc_transfer_rate"]),
                _source_refs(band["hkscc_transfer_source_refs"]),
            )
        )
    return CnAShareMarketFeeRuleBookV2(
        cast(str, data["rule_book_key"]),
        cast(int, data["rule_book_version"]),
        CnAShareExecutionAccessRoute(cast(str, data["access_route"])),
        CnAShareFeeProductClass(cast(str, data["fee_product_class"])),
        tuple(bands),
    )


def _stamp_book(body: object) -> CnAShareStampDutyRuleBookV2:
    data = _mapping("stamp duty authority", body)
    bands = []
    for value in cast(tuple[object, ...], data["bands"]):
        band = _mapping("stamp duty band", value)
        bands.append(
            CnAShareStampDutyBandV2(
                VenueId(cast(Mapping[str, str], band["venue_id"])["value"]),
                _instant(band["effective_from"]),
                _instant(band["effective_to_exclusive"]),
                cast(bool, band["applies_to_sell"]),
                _rate(band["rate"]),
                _source_refs(band["source_refs"]),
            )
        )
    return CnAShareStampDutyRuleBookV2(
        cast(str, data["rule_book_key"]),
        cast(int, data["rule_book_version"]),
        CnAShareExecutionAccessRoute(cast(str, data["access_route"])),
        CnAShareFeeProductClass(cast(str, data["fee_product_class"])),
        tuple(bands),
    )


def _events(
    manifest: MarketBundleManifest, events: tuple[MarketEvent, ...]
) -> tuple[CnAShareMarketFeeRuleBookV2, CnAShareStampDutyRuleBookV2, str, str]:
    if type(manifest) is not MarketBundleManifest:
        raise TypeError("market_bundle_manifest must be exact MarketBundleManifest")
    rebuilt_manifest = MarketBundleManifest(
        *(getattr(manifest, field.name) for field in fields(manifest))
    )
    if rebuilt_manifest != manifest or canonical_sha256(manifest) != _MANIFEST_HASH:
        raise ValueError("market bundle manifest identity mismatch")
    if (
        manifest.content_hash != _MANIFEST_CONTENT_HASH
        or manifest.coverage_start != UtcInstant(_START)
        or manifest.coverage_end_exclusive != UtcInstant(_END)
    ):
        raise ValueError("market bundle manifest coverage mismatch")
    if type(events) is not tuple or len(events) != len(_DIMENSIONS):
        raise TypeError("events must be the exact five-event tuple")
    rebuilt_events = []
    for event in events:
        if type(event) is not MarketEvent:
            raise TypeError("events must contain exact MarketEvent values")
        rebuilt_events.append(
            MarketEvent(*(getattr(event, field.name) for field in fields(event)))
        )
    if (
        tuple(rebuilt_events) != events
        or tuple(event.event_hash for event in events) != _EVENT_HASHES
    ):
        raise ValueError("current-selected event identity/order mismatch")
    stream_by_key = {stream.stream_key: stream for stream in manifest.streams}
    declaration_hash = ""
    snapshot_hash = ""
    for index, (dimension, event) in enumerate(zip(_DIMENSIONS, events, strict=True)):
        payload = _mapping("event payload", event.payload)
        target = _mapping("target coverage", payload["target_coverage"])
        if (
            event.capability.identity != _CAPABILITY
            or event.source_sequence.value != index
            or event.stream_key
            != f"cn_a_share.current_selected_development.rule_authority.{dimension}.v2"
            or event.event_type
            != f"cn_a_share_current_selected_development_{dimension}_authority.v2"
            or event.event_time != UtcInstant(_START)
            or event.instrument_id is not None
            or payload["dimension"] != dimension
            or payload["qualification"] != _QUALIFICATION
            or target["start_epoch_nanoseconds"] != _START
            or target["end_exclusive_epoch_nanoseconds"] != _END
        ):
            raise ValueError("current-selected event declaration mismatch")
        if index == 0:
            declaration_hash = cast(str, payload["declaration_hash"])
            snapshot_hash = cast(str, payload["snapshot_hash"])
        elif (payload["declaration_hash"], payload["snapshot_hash"]) != (
            declaration_hash,
            snapshot_hash,
        ):
            raise ValueError(
                "current-selected events do not share declaration/snapshot"
            )
        stream = stream_by_key.get(event.stream_key)
        if (
            stream is None
            or stream.event_count != 1
            or stream.content_hash != canonical_sha256((event,))
        ):
            raise ValueError("manifest stream does not bind its current-selected event")
    if declaration_hash != _DECLARATION_HASH or snapshot_hash != _SNAPSHOT_HASH:
        raise ValueError("current-selected declaration/snapshot identity mismatch")
    market = _market_book(events[2].payload["authority"])
    stamp = _stamp_book(events[3].payload["authority"])
    if (
        market.rule_book_hash != _MARKET_BOOK_HASH
        or stamp.rule_book_hash != _STAMP_BOOK_HASH
    ):
        raise ValueError("hydrated current-selected RuleBook identity mismatch")
    return market, stamp, declaration_hash, snapshot_hash


def _coverage_report(value: object) -> dict[str, object]:
    if type(value) is not dict:
        raise TypeError("coverage report must be an exact dict")
    try:
        rebuilt = json.loads(canonical_bytes(value))
    except (TypeError, ValueError) as error:
        raise ValueError("coverage report must contain canonical JSON values") from error
    if type(rebuilt) is not dict or rebuilt != value or set(rebuilt) != _COVERAGE_FIELDS:
        raise ValueError("coverage report must canonical-rebuild exactly")
    body = dict(rebuilt)
    report_hash = body.pop("report_hash")
    complete = rebuilt["finite_development_interval_coverage_complete"]
    if (
        type(rebuilt["type"]) is not str
        or rebuilt["type"] != "cn_a_share_current_selected_rule_coverage_report"
        or type(rebuilt["schema_version"]) is not int
        or rebuilt["schema_version"] != 1
        or report_hash != _COVERAGE_HASH
        or canonical_sha256(body) != _COVERAGE_HASH
        or rebuilt["declaration_hash"] != _DECLARATION_HASH
        or rebuilt["snapshot_hash"] != _SNAPSHOT_HASH
        or rebuilt["snapshot_key"] != _SNAPSHOT_KEY
        or type(rebuilt["snapshot_version"]) is not int
        or rebuilt["snapshot_version"] != 1
        or type(rebuilt["target_from"]) is not int
        or rebuilt["target_from"] != _START
        or type(rebuilt["target_to_exclusive"]) is not int
        or rebuilt["target_to_exclusive"] != _END
        or rebuilt["qualification"] != _QUALIFICATION
        or type(complete) is not bool
        or not complete
    ):
        raise ValueError("coverage report identity mismatch")
    return cast(dict[str, object], rebuilt)


def _profile_build(
    profile: object, manifest: object
) -> tuple[CnAShareResolvedProfile, BuildArtifactManifest]:
    resolved = _reconstructed_profile(profile)
    build = _reconstructed_build(manifest)
    if resolved is None or build is None:
        raise TypeError("resolved profile and build manifest must reconstruct exactly")
    for registration in (
        resolved.market_registration,
        resolved.simulation_registration,
        resolved.execution_account_registration,
    ):
        artifact = build.profile_artifact(registration.profile_key)
        if (
            type(artifact) is not BuildArtifactRef
            or artifact.role is not BuildArtifactRole.PROFILE_COMPONENT
            or artifact.content_hash != registration.profile_digest
        ):
            raise ValueError("build manifest profile artifact identity mismatch")
    return resolved, build


def _authority(
    profile: CnAShareResolvedProfile,
    market: CnAShareMarketFeeRuleBookV2,
    stamp: CnAShareStampDutyRuleBookV2,
    snapshot_key: str,
    snapshot_version: int,
) -> CnAShareFeeExecutionAuthorityV2:
    account = profile.request.account_scope
    instrument = profile.request.instrument_scope
    if account is None or instrument is None:
        raise ValueError("resolved profile lacks immutable account/instrument scope")
    if account.venue_id != VenueId("xshe"):
        raise ValueError("resolved profile is outside current-selected XSHE scope")
    scope = CnAShareFeeExecutionScopeV2(
        account.account_id,
        account.venue_id,
        instrument.instrument,
        instrument.instrument.instrument_id,
        instrument.instrument.instrument_type,
        instrument.instrument.quote_currency,
        instrument.instrument.settlement_currency,
        CnAShareFeeTradeMechanism.AUCTION,
        UtcInstant(_START),
        UtcInstant(_END),
        (OrderSide.BUY, OrderSide.SELL),
        CnAShareExecutionAccessRoute.DOMESTIC,
        CnAShareFeeProductClass.ORDINARY_A_SHARE,
    )
    selection = CnAShareFeeExecutionSelectionV2(
        snapshot_key,
        snapshot_version,
        CnAShareExecutionAccessRoute.DOMESTIC,
        CnAShareFeeProductClass.ORDINARY_A_SHARE,
        market,
        market.rule_book_hash,
        stamp,
        stamp.rule_book_hash,
        kernel_v2._market_component(market),
        kernel_v2._tax_component(stamp),
    )
    selected = create_cn_a_share_fee_execution_authority_v2(scope, selection)
    if type(selected) is not CnAShareFeeExecutionAuthorityV2:
        raise ValueError("current-selected fee authority construction failed")
    return selected


@dataclass(frozen=True, slots=True)
class CnAShareCurrentSelectedFeeBindingV2:
    schema_version: int
    resolved_profile: CnAShareResolvedProfile
    market_bundle_manifest: MarketBundleManifest
    events: tuple[MarketEvent, ...]
    coverage_report: dict[str, object]
    build_artifact_manifest: BuildArtifactManifest
    market_fee_rule_book: CnAShareMarketFeeRuleBookV2
    stamp_duty_rule_book: CnAShareStampDutyRuleBookV2
    authority: CnAShareFeeExecutionAuthorityV2
    manifest_hash: str
    declaration_hash: str
    snapshot_hash: str
    coverage_report_hash: str
    profile_digest: str
    build_artifact_manifest_hash: str

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("current-selected fee binding schema_version must be 1")
        profile, build = _profile_build(
            self.resolved_profile, self.build_artifact_manifest
        )
        market, stamp, declaration, snapshot = _events(
            self.market_bundle_manifest, self.events
        )
        report = _coverage_report(self.coverage_report)
        first_payload = _mapping("event payload", self.events[0].payload)
        expected_authority = _authority(
            profile,
            market,
            stamp,
            cast(str, first_payload["snapshot_key"]),
            cast(int, first_payload["snapshot_version"]),
        )
        if (
            report != self.coverage_report
            or market != self.market_fee_rule_book
            or stamp != self.stamp_duty_rule_book
            or self.authority != expected_authority
            or self.manifest_hash != _MANIFEST_HASH
            or self.declaration_hash != declaration
            or self.snapshot_hash != snapshot
            or self.coverage_report_hash != _COVERAGE_HASH
            or self.profile_digest != profile.profile_digest
            or self.build_artifact_manifest_hash != build.manifest_hash
        ):
            raise ValueError("current-selected fee binding identity mismatch")

    @property
    def binding_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_current_selected_fee_binding_v2",
            "schema_version": self.schema_version,
            "manifest_hash": self.manifest_hash,
            "event_hashes": tuple(event.event_hash for event in self.events),
            "declaration_hash": self.declaration_hash,
            "snapshot_hash": self.snapshot_hash,
            "coverage_report_hash": self.coverage_report_hash,
            "market_fee_rule_book_hash": self.market_fee_rule_book.rule_book_hash,
            "stamp_duty_rule_book_hash": self.stamp_duty_rule_book.rule_book_hash,
            "authority_hash": self.authority.authority_hash,
            "profile_digest": self.profile_digest,
            "build_artifact_manifest_hash": self.build_artifact_manifest_hash,
        }


@dataclass(frozen=True, slots=True)
class CnAShareCurrentSelectedFeePreparedExecutionV2:
    schema_version: int
    base_spec: ExecutionCaseSemanticSpec
    binding: CnAShareCurrentSelectedFeeBindingV2
    execution_binding: CnAShareFeeExecutionBindingV2
    semantic_spec: ExecutionCaseSemanticSpec

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("prepared current-selected fee schema_version must be 1")
        base = _reconstructed_semantic_spec(self.base_spec)
        if (
            base is None
            or type(self.binding) is not CnAShareCurrentSelectedFeeBindingV2
        ):
            raise TypeError(
                "prepared current-selected sources must reconstruct exactly"
            )
        rebuilt_binding = CnAShareCurrentSelectedFeeBindingV2(
            *(getattr(self.binding, field.name) for field in fields(self.binding))
        )
        execution = _reconstructed_kernel_binding(self.execution_binding)
        semantic = _reconstructed_semantic_spec(self.semantic_spec)
        expected_semantic = _semantic_spec(base, rebuilt_binding)
        if (
            rebuilt_binding != self.binding
            or execution is None
            or execution.authority != rebuilt_binding.authority
            or semantic is None
            or semantic != expected_semantic
        ):
            raise ValueError("prepared current-selected fee identity mismatch")

    @property
    def preparation_hash(self) -> str:
        return canonical_sha256(self)

    def reservation_query(self) -> CnAShareCashFeeRuleQueryV2:
        query = CnAShareCashFeeRuleQueryV2.for_reservation(
            self.binding.authority, self.execution_binding
        )
        if type(query) is not CnAShareCashFeeRuleQueryV2:
            failure = cast(CnAShareFeeQueryConstructionFailureV2, query)
            raise ValueError(f"fee reservation query failed:{failure.code.value}")
        return query

    def final_fill_query(self, fill: Fill | None, /) -> CnAShareCashFeeRuleQueryV2:
        query = CnAShareCashFeeRuleQueryV2.for_final_fill(
            self.binding.authority, self.execution_binding, fill
        )
        if type(query) is not CnAShareCashFeeRuleQueryV2:
            failure = cast(CnAShareFeeQueryConstructionFailureV2, query)
            raise ValueError(f"fee final-fill query failed:{failure.code.value}")
        return query

    def policies(
        self,
    ) -> tuple[CnAShareCashMarketFeePolicyV2, CnAShareCashStampDutyTaxPolicyV2]:
        authority = self.binding.authority
        return (
            CnAShareCashMarketFeePolicyV2(authority, authority.authority_hash, _SCALE),
            CnAShareCashStampDutyTaxPolicyV2(
                authority, authority.authority_hash, _SCALE
            ),
        )

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_current_selected_fee_prepared_execution_v2",
            "schema_version": self.schema_version,
            "binding": self.binding,
            "execution_binding": self.execution_binding,
            "semantic_spec": self.semantic_spec,
        }


def _semantic_spec(
    base_spec: ExecutionCaseSemanticSpec,
    binding: CnAShareCurrentSelectedFeeBindingV2,
) -> ExecutionCaseSemanticSpec:
    return replace(
        base_spec,
        financial_inputs_hash=canonical_sha256(
            {
                "type": "cn_a_share_current_selected_fee_financial_inputs_binding_v2",
                "schema_version": 1,
                "base_financial_inputs_hash": base_spec.financial_inputs_hash,
                "market_bundle_manifest_hash": binding.manifest_hash,
                "declaration_hash": binding.declaration_hash,
                "snapshot_hash": binding.snapshot_hash,
                "coverage_report_hash": binding.coverage_report_hash,
                "authority_hash": binding.authority.authority_hash,
                "market_fee_rule_book_hash": binding.market_fee_rule_book.rule_book_hash,
                "stamp_duty_rule_book_hash": binding.stamp_duty_rule_book.rule_book_hash,
                "resolved_profile_digest": binding.profile_digest,
                "build_artifact_manifest_hash": binding.build_artifact_manifest_hash,
            }
        ),
    )


def prepare_cn_a_share_current_selected_fee_execution_v2(
    *,
    resolved_profile: CnAShareResolvedProfile,
    market_bundle_manifest: MarketBundleManifest,
    events: tuple[MarketEvent, ...],
    coverage_report: object,
    build_artifact_manifest: BuildArtifactManifest,
    base_spec: ExecutionCaseSemanticSpec,
    order: Order,
) -> CnAShareCurrentSelectedFeePreparedExecutionV2:
    profile, build = _profile_build(resolved_profile, build_artifact_manifest)
    market, stamp, declaration, snapshot = _events(market_bundle_manifest, events)
    report = _coverage_report(coverage_report)
    payload = _mapping("event payload", events[0].payload)
    authority = _authority(
        profile,
        market,
        stamp,
        cast(str, payload["snapshot_key"]),
        cast(int, payload["snapshot_version"]),
    )
    binding = CnAShareCurrentSelectedFeeBindingV2(
        1,
        profile,
        market_bundle_manifest,
        events,
        report,
        build,
        market,
        stamp,
        authority,
        _MANIFEST_HASH,
        declaration,
        snapshot,
        _COVERAGE_HASH,
        profile.profile_digest,
        build.manifest_hash,
    )
    execution = bind_kernel_fee_execution_v2(authority, order)
    if type(execution) is not CnAShareFeeExecutionBindingV2:
        failure = cast(CnAShareFeeExecutionBindingFailureV2, execution)
        raise ValueError(f"fee execution binding failed:{failure.code.value}")
    spec = _reconstructed_semantic_spec(base_spec)
    if spec is None:
        raise TypeError("base_spec must reconstruct exactly")
    return CnAShareCurrentSelectedFeePreparedExecutionV2(
        1,
        spec,
        binding,
        execution,
        _semantic_spec(spec, binding),
    )
