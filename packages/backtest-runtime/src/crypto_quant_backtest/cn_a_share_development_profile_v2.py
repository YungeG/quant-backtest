"""Additive public V2 composition for the finite 000703 development route."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from zoneinfo import ZoneInfo

from crypto_quant_domain import (
    CurrencyId,
    FeeBasisType,
    InstrumentId,
    InstrumentType,
    Money,
    QuantizationPolicy,
    Rate,
    RoundingPolicy,
    Scale,
    SimulationInstant,
    UtcInstant,
    canonical_sha256,
)
from crypto_quant_market_data import (
    MarketBundleCapability,
    MarketBundleManifest,
)
from crypto_quant_trading import AccountFeeScheduleRef
from crypto_quant_trading.profiles.cn_a_share import (
    CnAShareBoard,
    CnAShareExecutionAccessRoute,
    CnAShareFeeProductClass,
    CnAShareFrozenCalendar,
    CnAShareListingPhase,
    CnAShareMarketFeeRuleBookV2,
    CnAShareOrderRuleBook,
    CnAShareRiskClass,
    CnAShareStampDutyRuleBookV2,
)
from .cn_a_share_dividend_profile_v2 import CnAShareDividendProfileV2
from .cn_a_share_profile import (
    CnAShareAccountScopeDeclaration,
    CnAShareInstrumentScopeDeclaration,
    CnAShareProfileCompositionFailureCode,
)
from .timeline import TimelineWindow


_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_SHANGHAI = ZoneInfo("Asia/Shanghai")
_CLOSE_CAPABILITY = MarketBundleCapability("bar_close", 1)
_CNY = CurrencyId("CNY")
_CENT = Scale(2)
_COMMISSION_RATES = {"3bps": 3, "5bps": 5, "8bps": 8}
_COMMISSION_AUTHORITY_SNAPSHOT = (
    "sha256:87ef8b1b555e654c8f253c0a221b35ed566b0e9a7a9c010119f7e28f5a3d549b"
)
_COMMISSION_COVERAGE_START = UtcInstant(1_704_124_800_000_000_000)
_COMMISSION_COVERAGE_END = UtcInstant(1_706_716_800_000_000_000)
_COMMISSION_QUANTIZATION = QuantizationPolicy(
    "cn-a-share-january-2024-commission.cny-cent.half-up.v1",
    _CENT,
    RoundingPolicy.HALF_UP,
)
_LIMITATIONS = (
    "development_profile",
    "finite_tushare_000703_authority_only",
    "tushare_dividend_actions_are_development_convention_only",
    "broker_chinaclear_tax_and_legal_parity_unproven",
    "no_live_or_deployment_authority",
)


def _hash(name: str, value: object) -> str:
    if type(value) is not str or _HASH.fullmatch(value) is None:
        raise ValueError(f"{name} must be canonical sha256")
    return value


def _utc_covered(
    intervals: tuple[tuple[UtcInstant, UtcInstant], ...],
    window: TimelineWindow,
) -> bool:
    cursor = window.data_start
    for start, end in sorted(intervals):
        if end <= cursor:
            continue
        if start > cursor:
            return False
        cursor = max(cursor, end)
        if cursor >= window.end_exclusive:
            return True
    return False


def _date_covered(
    intervals: tuple[tuple[object, object], ...],
    window: TimelineWindow,
) -> bool:
    start = datetime.fromtimestamp(
        window.data_start.epoch_nanoseconds // 1_000_000_000,
        _SHANGHAI,
    ).date()
    end = datetime.fromtimestamp(
        (window.end_exclusive.epoch_nanoseconds - 1) // 1_000_000_000,
        _SHANGHAI,
    ).date()
    cursor = start
    for interval_start, interval_end in sorted(intervals):
        if interval_end <= cursor:
            continue
        if interval_start > cursor:
            return False
        cursor = max(cursor, interval_end)
        if cursor > end:
            return True
    return False


@dataclass(frozen=True, slots=True)
class CnAShareDevelopmentSourceManifestV2:
    source_hashes: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self.source_hashes) is not tuple:
            raise TypeError("source_hashes must be tuple")
        values = tuple(_hash("source_hash", value) for value in self.source_hashes)
        if not values or values != tuple(sorted(set(values))):
            raise ValueError("source_hashes must be nonempty canonical unique tuple")
        object.__setattr__(self, "source_hashes", values)

    @property
    def manifest_hash(self) -> str:
        return canonical_sha256(
            {
                "type": "cn_a_share_development_source_manifest_v2",
                "schema_version": 2,
                "source_hashes": self.source_hashes,
            }
        )

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_development_source_manifest_v2",
            "schema_version": 2,
            "source_hashes": self.source_hashes,
            "manifest_hash": self.manifest_hash,
        }


def _commission_schedule_ref(
    scenario_key: str, commission_rate: Rate
) -> AccountFeeScheduleRef:
    return AccountFeeScheduleRef(
        "development.cn-a-share.cash.domestic.ordinary-a-share.2024-01."
        f"commission.{scenario_key}",
        1,
        canonical_sha256(
            {
                "type": "cn_a_share_january_2024_development_commission_schedule",
                "schema_version": 1,
                "scenario_key": scenario_key,
                "commission_rate": commission_rate,
                "authority_snapshot_sha256": _COMMISSION_AUTHORITY_SNAPSHOT,
                "coverage_from": _COMMISSION_COVERAGE_START,
                "coverage_to_exclusive": _COMMISSION_COVERAGE_END,
                "minimum_amount": Money(500, _CENT, "CNY"),
                "quantization": _COMMISSION_QUANTIZATION,
                "basis_type": FeeBasisType.ORDER.value,
                "one_full_fill_only": True,
                "development_only": True,
                "access_route": CnAShareExecutionAccessRoute.DOMESTIC.value,
                "fee_product_class": CnAShareFeeProductClass.ORDINARY_A_SHARE.value,
            }
        ),
    )


@dataclass(frozen=True, slots=True)
class CnAShareDevelopmentCommissionScenarioV2:
    scenario_key: str
    commission_rate: Rate
    account_fee_schedule_ref: AccountFeeScheduleRef
    development_only: bool

    def __post_init__(self) -> None:
        if self.scenario_key not in {"3bps", "5bps", "8bps"}:
            raise ValueError("scenario_key must be one of 3bps, 5bps, or 8bps")
        if (
            type(self.commission_rate) is not Rate
            or self.commission_rate.basis != "fee_fraction"
            or self.commission_rate.scale != Scale(4)
            or self.commission_rate.units != _COMMISSION_RATES.get(self.scenario_key)
        ):
            raise ValueError("commission_rate must be a 3, 5, or 8 bps fee_fraction")
        if type(self.account_fee_schedule_ref) is not AccountFeeScheduleRef:
            raise TypeError("account_fee_schedule_ref must be exact AccountFeeScheduleRef")
        if self.account_fee_schedule_ref != _commission_schedule_ref(
            self.scenario_key, self.commission_rate
        ):
            raise ValueError("account_fee_schedule_ref must bind scenario key and rate")
        if type(self.development_only) is not bool or not self.development_only:
            raise ValueError("commission scenario must be development-only")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_development_commission_scenario_v2",
            "schema_version": 2,
            "scenario_key": self.scenario_key,
            "commission_rate": self.commission_rate,
            "account_fee_schedule_ref": self.account_fee_schedule_ref,
            "development_only": self.development_only,
        }


@dataclass(frozen=True, slots=True)
class CnAShareDevelopmentMinuteAuthorityV2:
    instrument_id: InstrumentId
    manifest: MarketBundleManifest
    source_receipt_hash: str
    available_at: SimulationInstant
    development_only: bool
    decision_grade_eligible: bool
    live_eligible: bool
    deployment_authorized: bool

    def __post_init__(self) -> None:
        if type(self.instrument_id) is not InstrumentId:
            raise TypeError("instrument_id must be exact InstrumentId")
        if type(self.manifest) is not MarketBundleManifest:
            raise TypeError("manifest must be exact MarketBundleManifest")
        _hash("source_receipt_hash", self.source_receipt_hash)
        if type(self.available_at) is not SimulationInstant:
            raise TypeError("available_at must be exact SimulationInstant")
        if _CLOSE_CAPABILITY not in self.manifest.capabilities:
            raise ValueError("minute authority must declare bar_close capability")
        if (
            type(self.development_only) is not bool
            or type(self.decision_grade_eligible) is not bool
            or type(self.live_eligible) is not bool
            or type(self.deployment_authorized) is not bool
            or not self.development_only
            or self.decision_grade_eligible
            or self.live_eligible
            or self.deployment_authorized
        ):
            raise ValueError("minute authority must retain development qualification")

    def _body(self) -> dict[str, object]:
        return {
            "instrument_id": self.instrument_id,
            "manifest": self.manifest,
            "source_receipt_hash": self.source_receipt_hash,
            "available_at": self.available_at,
            "development_only": self.development_only,
            "decision_grade_eligible": self.decision_grade_eligible,
            "live_eligible": self.live_eligible,
            "deployment_authorized": self.deployment_authorized,
        }

    @property
    def authority_hash(self) -> str:
        return canonical_sha256(
            {
                "type": "cn_a_share_development_minute_authority_v2",
                "schema_version": 2,
                **self._body(),
            }
        )

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_development_minute_authority_v2",
            "schema_version": 2,
            **self._body(),
            "authority_hash": self.authority_hash,
        }


@dataclass(frozen=True, slots=True)
class CnAShareProfileCompositionRequestV2:
    source_manifest: CnAShareDevelopmentSourceManifestV2
    instrument_scope: CnAShareInstrumentScopeDeclaration
    account_scope: CnAShareAccountScopeDeclaration
    calendar: CnAShareFrozenCalendar
    order_rule_book: CnAShareOrderRuleBook
    market_fee_rule_book: CnAShareMarketFeeRuleBookV2
    stamp_duty_rule_book: CnAShareStampDutyRuleBookV2
    commission_scenario: CnAShareDevelopmentCommissionScenarioV2
    minute_authorities: tuple[CnAShareDevelopmentMinuteAuthorityV2, ...]
    dividend_profile: CnAShareDividendProfileV2
    timeline_window: TimelineWindow
    composed_at: SimulationInstant

    def __post_init__(self) -> None:
        if type(self.source_manifest) is not CnAShareDevelopmentSourceManifestV2:
            raise TypeError("source_manifest must be exact V2 source manifest")
        for name, value_type in (
            ("instrument_scope", CnAShareInstrumentScopeDeclaration),
            ("account_scope", CnAShareAccountScopeDeclaration),
            ("calendar", CnAShareFrozenCalendar),
            ("order_rule_book", CnAShareOrderRuleBook),
            ("market_fee_rule_book", CnAShareMarketFeeRuleBookV2),
            ("stamp_duty_rule_book", CnAShareStampDutyRuleBookV2),
            ("commission_scenario", CnAShareDevelopmentCommissionScenarioV2),
            ("dividend_profile", CnAShareDividendProfileV2),
            ("timeline_window", TimelineWindow),
            ("composed_at", SimulationInstant),
        ):
            if type(getattr(self, name)) is not value_type:
                raise TypeError(f"{name} must be exact {value_type.__name__}")
        if (
            type(self.minute_authorities) is not tuple
            or not self.minute_authorities
            or not all(
                type(value) is CnAShareDevelopmentMinuteAuthorityV2
                for value in self.minute_authorities
            )
        ):
            raise TypeError("minute_authorities must be a nonempty exact V2 tuple")
        ordered = tuple(
            sorted(
                self.minute_authorities,
                key=lambda value: (
                    value.manifest.coverage_start,
                    value.manifest.coverage_end_exclusive,
                    value.authority_hash,
                ),
            )
        )
        if len({value.authority_hash for value in ordered}) != len(ordered):
            raise ValueError("minute_authorities must have unique identities")
        object.__setattr__(self, "minute_authorities", ordered)
        expected = _source_hashes(self)
        if self.source_manifest.source_hashes != expected:
            raise ValueError("source_manifest does not exact-cover V2 authorities")
        manifest_hash = self.source_manifest.manifest_hash
        if (
            self.instrument_scope.source_manifest_hash != manifest_hash
            or self.account_scope.source_manifest_hash != manifest_hash
        ):
            raise ValueError("scope declarations must bind the V2 source manifest")

    @property
    def request_hash(self) -> str:
        return canonical_sha256(
            {
                "type": "cn_a_share_profile_composition_request_v2",
                "schema_version": 2,
                **self._body(),
            }
        )

    def _body(self) -> dict[str, object]:
        return {
            "source_manifest": self.source_manifest,
            "instrument_scope": self.instrument_scope,
            "account_scope": self.account_scope,
            "calendar": self.calendar,
            "order_rule_book": self.order_rule_book,
            "market_fee_rule_book": self.market_fee_rule_book,
            "stamp_duty_rule_book": self.stamp_duty_rule_book,
            "commission_scenario": self.commission_scenario,
            "minute_authorities": self.minute_authorities,
            "dividend_profile": self.dividend_profile,
            "timeline_window": self.timeline_window,
            "composed_at": self.composed_at,
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_profile_composition_request_v2",
            "schema_version": 2,
            **self._body(),
            "request_hash": self.request_hash,
        }


def build_cn_a_share_development_source_manifest_v2(
    *,
    instrument_source_snapshot_hash: str,
    instrument_rule_context_source_hash: str,
    account_source_snapshot_hash: str,
    calendar: CnAShareFrozenCalendar,
    order_rule_book: CnAShareOrderRuleBook,
    market_fee_rule_book: CnAShareMarketFeeRuleBookV2,
    stamp_duty_rule_book: CnAShareStampDutyRuleBookV2,
    commission_scenario: CnAShareDevelopmentCommissionScenarioV2,
    minute_authorities: tuple[CnAShareDevelopmentMinuteAuthorityV2, ...],
    dividend_profile: CnAShareDividendProfileV2,
) -> CnAShareDevelopmentSourceManifestV2:
    for name, value, value_type in (
        ("calendar", calendar, CnAShareFrozenCalendar),
        ("order_rule_book", order_rule_book, CnAShareOrderRuleBook),
        ("market_fee_rule_book", market_fee_rule_book, CnAShareMarketFeeRuleBookV2),
        ("stamp_duty_rule_book", stamp_duty_rule_book, CnAShareStampDutyRuleBookV2),
        ("commission_scenario", commission_scenario, CnAShareDevelopmentCommissionScenarioV2),
        ("dividend_profile", dividend_profile, CnAShareDividendProfileV2),
    ):
        if type(value) is not value_type:
            raise TypeError(f"{name} must be exact {value_type.__name__}")
    if (
        type(minute_authorities) is not tuple
        or not minute_authorities
        or not all(
            type(value) is CnAShareDevelopmentMinuteAuthorityV2
            for value in minute_authorities
        )
    ):
        raise TypeError("minute_authorities must be a nonempty exact V2 tuple")
    return CnAShareDevelopmentSourceManifestV2(
        tuple(
            sorted(
                {
                    _hash("instrument_source_snapshot_hash", instrument_source_snapshot_hash),
                    _hash("instrument_rule_context_source_hash", instrument_rule_context_source_hash),
                    _hash("account_source_snapshot_hash", account_source_snapshot_hash),
                    canonical_sha256(calendar),
                    canonical_sha256(order_rule_book),
                    canonical_sha256(market_fee_rule_book),
                    canonical_sha256(stamp_duty_rule_book),
                    canonical_sha256(commission_scenario),
                    *(value.authority_hash for value in minute_authorities),
                    dividend_profile.profile_hash,
                    *dividend_profile.source_manifest,
                }
            )
        )
    )


def _source_hashes(request: CnAShareProfileCompositionRequestV2) -> tuple[str, ...]:
    return build_cn_a_share_development_source_manifest_v2(
        instrument_source_snapshot_hash=request.instrument_scope.source_snapshot_hash,
        instrument_rule_context_source_hash=request.instrument_scope.rule_context.source_hash,
        account_source_snapshot_hash=request.account_scope.source_snapshot_hash,
        calendar=request.calendar,
        order_rule_book=request.order_rule_book,
        market_fee_rule_book=request.market_fee_rule_book,
        stamp_duty_rule_book=request.stamp_duty_rule_book,
        commission_scenario=request.commission_scenario,
        minute_authorities=request.minute_authorities,
        dividend_profile=request.dividend_profile,
    ).source_hashes


def _first_failure(
    request: CnAShareProfileCompositionRequestV2,
) -> CnAShareProfileCompositionFailureCode | None:
    instrument = request.instrument_scope
    account = request.account_scope
    profile = request.dividend_profile
    window = request.timeline_window
    if (
        instrument.instrument.instrument_id != profile.instrument_id
        or instrument.instrument.instrument_id
        != InstrumentId(profile.instrument_id.venue, "000703")
        or instrument.instrument.instrument_type is not InstrumentType.EQUITY
        or instrument.instrument.quote_currency != _CNY
        or instrument.instrument.settlement_currency != _CNY
        or instrument.rule_context.board is not CnAShareBoard.MAIN
        or instrument.rule_context.risk_class is not CnAShareRiskClass.STANDARD
        or instrument.rule_context.listing_phase is not CnAShareListingPhase.SEASONED
        or account.account_id != profile.simulated_register_policy.account_id
        or account.venue_id != profile.instrument_id.venue
        or request.calendar.venue_id != profile.instrument_id.venue
        or any(
            value.instrument_id != profile.instrument_id
            for value in request.minute_authorities
        )
        or any(
            band.venue_id != profile.instrument_id.venue
            for band in request.order_rule_book.bands
        )
        or request.market_fee_rule_book.access_route
        is not CnAShareExecutionAccessRoute.DOMESTIC
        or request.market_fee_rule_book.fee_product_class
        is not CnAShareFeeProductClass.ORDINARY_A_SHARE
        or request.stamp_duty_rule_book.access_route
        is not CnAShareExecutionAccessRoute.DOMESTIC
        or request.stamp_duty_rule_book.fee_product_class
        is not CnAShareFeeProductClass.ORDINARY_A_SHARE
    ):
        return CnAShareProfileCompositionFailureCode.AUTHORITY_CONTEXT_MISMATCH
    if (
        not instrument.is_ordinary_domestic_a_share
        or not instrument.is_standard_cash_auction
        or instrument.is_b_or_h_share
        or instrument.is_fund_or_bond
        or instrument.is_stock_connect
        or instrument.has_lending_or_repo
        or instrument.has_pledge_or_freeze
        or instrument.is_restricted_or_pre_ipo
        or instrument.has_differential_distribution
        or instrument.has_issuer_self_distribution
    ):
        return CnAShareProfileCompositionFailureCode.INSTRUMENT_SCOPE_MISMATCH
    if (
        not account.is_cash_account
        or not account.is_domestic_access
        or account.has_margin_or_short_permission
        or account.has_stock_connect_permission
        or account.authorizes_available_margin_use
    ):
        return CnAShareProfileCompositionFailureCode.ACCOUNT_SCOPE_MISMATCH
    if (
        not _utc_covered(
            ((instrument.coverage_from, instrument.coverage_to_exclusive),),
            window,
        )
        or not _utc_covered(
            ((account.coverage_from, account.coverage_to_exclusive),),
            window,
        )
        or not _date_covered(
            ((request.calendar.coverage_start, request.calendar.coverage_end_exclusive),),
            window,
        )
        or not _date_covered(
            tuple(
                (value.effective_from, value.effective_to_exclusive)
                for value in request.order_rule_book.bands
            ),
            window,
        )
        or not _utc_covered(
            tuple(
                (value.effective_from, value.effective_to_exclusive)
                for value in request.market_fee_rule_book.bands
            ),
            window,
        )
        or not _utc_covered(
            tuple(
                (value.effective_from, value.effective_to_exclusive)
                for value in request.stamp_duty_rule_book.bands
            ),
            window,
        )
        or not _utc_covered(
            tuple(
                (value.manifest.coverage_start, value.manifest.coverage_end_exclusive)
                for value in request.minute_authorities
            ),
            window,
        )
        or not _date_covered(
            ((
                datetime.strptime(profile.coverage_start_date, "%Y%m%d").date(),
                datetime.strptime(profile.coverage_end_date_exclusive, "%Y%m%d").date(),
            ),),
            window,
        )
    ):
        return CnAShareProfileCompositionFailureCode.TIMELINE_COVERAGE_MISMATCH
    if (
        instrument.available_at > request.composed_at
        or account.available_at > request.composed_at
        or any(value.available_at > request.composed_at for value in request.minute_authorities)
    ):
        return CnAShareProfileCompositionFailureCode.EVIDENCE_NOT_AVAILABLE
    return None


@dataclass(frozen=True, slots=True)
class CnAShareResolvedProfileV2:
    request: CnAShareProfileCompositionRequestV2
    source_manifest_hash: str
    limitations: tuple[str, ...]
    development_only: bool
    decision_grade_eligible: bool
    live_eligible: bool
    deployment_authorized: bool

    def __post_init__(self) -> None:
        if type(self.request) is not CnAShareProfileCompositionRequestV2:
            raise TypeError("request must be exact V2 composition request")
        if (
            self.source_manifest_hash != self.request.source_manifest.manifest_hash
            or self.limitations != _LIMITATIONS
            or not self.development_only
            or self.decision_grade_eligible
            or self.live_eligible
            or self.deployment_authorized
            or _first_failure(self.request) is not None
        ):
            raise ValueError("resolved V2 profile does not match composition authority")

    @property
    def profile_hash(self) -> str:
        return canonical_sha256(
            {
                "type": "cn_a_share_resolved_profile_v2",
                "schema_version": 2,
                "request": self.request,
                "source_manifest_hash": self.source_manifest_hash,
                "limitations": self.limitations,
                "development_only": self.development_only,
                "decision_grade_eligible": self.decision_grade_eligible,
                "live_eligible": self.live_eligible,
                "deployment_authorized": self.deployment_authorized,
            }
        )

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_resolved_profile_v2",
            "schema_version": 2,
            "request": self.request,
            "source_manifest_hash": self.source_manifest_hash,
            "limitations": self.limitations,
            "development_only": self.development_only,
            "decision_grade_eligible": self.decision_grade_eligible,
            "live_eligible": self.live_eligible,
            "deployment_authorized": self.deployment_authorized,
            "profile_hash": self.profile_hash,
        }


@dataclass(frozen=True, slots=True)
class CnAShareProfileCompositionFailureV2:
    request: CnAShareProfileCompositionRequestV2
    code: CnAShareProfileCompositionFailureCode

    def __post_init__(self) -> None:
        if (
            type(self.request) is not CnAShareProfileCompositionRequestV2
            or type(self.code) is not CnAShareProfileCompositionFailureCode
            or self.code is not _first_failure(self.request)
        ):
            raise ValueError("failure must match the first V2 composition failure")

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(
            {
                "type": "cn_a_share_profile_composition_failure_v2",
                "schema_version": 2,
                "request": self.request,
                "code": self.code.value,
            }
        )

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_profile_composition_failure_v2",
            "schema_version": 2,
            "request": self.request,
            "code": self.code.value,
            "failure_hash": self.failure_hash,
        }


@dataclass(frozen=True, slots=True)
class CnAShareProfileCompositionOutcomeV2:
    request_hash: str
    result: CnAShareResolvedProfileV2 | None
    failure: CnAShareProfileCompositionFailureV2 | None

    def __post_init__(self) -> None:
        _hash("request_hash", self.request_hash)
        if (self.result is None) == (self.failure is None):
            raise ValueError("outcome must contain exactly one result or failure")
        authority = self.result if self.result is not None else self.failure
        if (
            authority is None
            or authority.request.request_hash != self.request_hash
            or (self.result is not None) != (_first_failure(authority.request) is None)
        ):
            raise ValueError("outcome does not match V2 composition authority")

    @property
    def outcome_hash(self) -> str:
        return canonical_sha256(
            {
                "type": "cn_a_share_profile_composition_outcome_v2",
                "schema_version": 2,
                "request_hash": self.request_hash,
                "result": self.result,
                "failure": self.failure,
            }
        )

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_profile_composition_outcome_v2",
            "schema_version": 2,
            "request_hash": self.request_hash,
            "result": self.result,
            "failure": self.failure,
            "outcome_hash": self.outcome_hash,
        }


class CnAShareProfileComposerV2:
    def compose(
        self, request: CnAShareProfileCompositionRequestV2, /
    ) -> CnAShareProfileCompositionOutcomeV2:
        if type(request) is not CnAShareProfileCompositionRequestV2:
            raise TypeError("request must be exact V2 composition request")
        code = _first_failure(request)
        if code is not None:
            return CnAShareProfileCompositionOutcomeV2(
                request.request_hash,
                None,
                CnAShareProfileCompositionFailureV2(request, code),
            )
        return CnAShareProfileCompositionOutcomeV2(
            request.request_hash,
            CnAShareResolvedProfileV2(
                request,
                request.source_manifest.manifest_hash,
                _LIMITATIONS,
                True,
                False,
                False,
                False,
            ),
            None,
        )


__all__ = (
    "CnAShareDevelopmentCommissionScenarioV2",
    "CnAShareDevelopmentMinuteAuthorityV2",
    "CnAShareDevelopmentSourceManifestV2",
    "CnAShareProfileComposerV2",
    "CnAShareProfileCompositionFailureV2",
    "CnAShareProfileCompositionOutcomeV2",
    "CnAShareProfileCompositionRequestV2",
    "CnAShareResolvedProfileV2",
    "build_cn_a_share_development_source_manifest_v2",
)
