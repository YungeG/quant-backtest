from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time
from enum import Enum
from typing import ClassVar
from zoneinfo import ZoneInfo

from crypto_quant_domain import canonical_bytes, canonical_sha256

_DIMENSIONS = (
    "calendar",
    "order_rules",
    "market_fees",
    "stamp_duty",
    "corporate_action_entitlements",
)
_QUALIFICATION = (
    ("official_successor_closure_complete", False),
    ("provider_authority_qualified", False),
    ("provider_completeness_qualified", False),
    ("rule_coverage_qualified", False),
    ("decision_grade_eligible", False),
    ("live_eligible", False),
    ("deployment_authorized", False),
    ("development_projection_authorized", True),
)
_TARGET_FROM = 1_783_267_200_000_000_000
_TARGET_TO_EXCLUSIVE = 1_785_427_200_000_000_000
_EVIDENCE_AVAILABLE_AT = 1_787_218_900_204_605_000
_SNAPSHOT_HASH = (
    "sha256:747e5c88fd2810ca05841cc6bb3c9534fbfc203ccad3e0903dd3f14e25a8a5c8"
)
_SNAPSHOT_KEY = (
    "equity.cn_a_share.current-selected-development.xshe.domestic."
    "ordinary-a-share.2026-07.v1"
)
_DECLARATION_HASH = (
    "sha256:4b21421bbe112d47a63ff03578dcb2215946e394d9971ab39a65c381d3d697d1"
)
_REPORT_HASH = (
    "sha256:5cbcc37871999b334709d1823f1c40ce6cdf73480f410f821cf4ebd38ceec9bb"
)
_DECLARATION_KEYS = {
    "authorities",
    "declaration_key",
    "declaration_version",
    "publication",
    "qualification",
    "schema_version",
    "snapshot",
    "snapshot_hash",
    "target_coverage",
    "type",
}
_PUBLICATION = {
    "bundle_key": (
        "cn-a-share-current-selected-development-rule-authorities-20260706-20260731-v2"
    ),
    "publication_key": (
        "cn-a-share-current-selected-development-rule-authorities-20260706-20260731-v2"
    ),
    "retention_policy_ref": (
        "retention.g12h-cn-a-share-current-selected-development-rule-authorities-v2"
    ),
}
_SHANGHAI = ZoneInfo("Asia/Shanghai")
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


class CnAShareCurrentSelectedRuleCoverageFailureCode(str, Enum):
    INVALID_INPUT = "invalid_input"
    BUNDLE_DECLARATION_MISMATCH = "bundle_declaration_mismatch"
    MISSING_REQUIRED_DIMENSION = "missing_required_dimension"
    COVERAGE_GAP = "coverage_gap"
    COVERAGE_OVERLAP = "coverage_overlap"
    SOURCE_IDENTITY_MISMATCH = "source_identity_mismatch"


@dataclass(frozen=True, slots=True)
class CnAShareCurrentSelectedRuleCoverageFailure:
    schema_version: ClassVar[int] = 1

    code: CnAShareCurrentSelectedRuleCoverageFailureCode
    dimension: str | None

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        if type(self) is not CnAShareCurrentSelectedRuleCoverageFailure:
            raise TypeError("failure must be exact concrete type")
        if type(self.code) is not CnAShareCurrentSelectedRuleCoverageFailureCode:
            raise TypeError("code must be exact failure code")
        dimension_required = self.code in {
            CnAShareCurrentSelectedRuleCoverageFailureCode.MISSING_REQUIRED_DIMENSION,
            CnAShareCurrentSelectedRuleCoverageFailureCode.COVERAGE_GAP,
            CnAShareCurrentSelectedRuleCoverageFailureCode.COVERAGE_OVERLAP,
            CnAShareCurrentSelectedRuleCoverageFailureCode.SOURCE_IDENTITY_MISMATCH,
        }
        if dimension_required:
            if type(self.dimension) is not str or self.dimension not in _DIMENSIONS:
                raise ValueError("dimension must be a required dimension")
        elif self.dimension is not None:
            raise ValueError("dimension must be absent for declaration-level failure")

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self.to_canonical_dict())

    def to_canonical_dict(self) -> dict[str, object]:
        self._validate()
        return {
            "type": "cn_a_share_current_selected_rule_coverage_failure",
            "schema_version": self.schema_version,
            "code": self.code.value,
            "dimension": self.dimension,
        }


@dataclass(frozen=True, slots=True)
class CnAShareCurrentSelectedRuleCoverageReport:
    schema_version: ClassVar[int] = 1

    declaration_hash: str
    snapshot_hash: str
    snapshot_key: str
    snapshot_version: int
    target_from: int
    target_to_exclusive: int
    board_ids: tuple[str, ...]
    dimension_interval_evidence: tuple[
        tuple[str, str, str, tuple[tuple[int, int], ...]], ...
    ]
    qualification: tuple[tuple[str, bool], ...]
    finite_development_interval_coverage_complete: bool = field(
        default=True, init=False
    )

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        if type(self) is not CnAShareCurrentSelectedRuleCoverageReport:
            raise TypeError("report must be exact concrete type")
        for name, value in (
            ("declaration_hash", self.declaration_hash),
            ("snapshot_hash", self.snapshot_hash),
        ):
            if not _is_hash(value):
                raise ValueError(f"{name} must be canonical sha256")
        if self.declaration_hash != _DECLARATION_HASH:
            raise ValueError("declaration hash must be canonical current-selected declaration")
        if self.report_hash != _REPORT_HASH:
            raise ValueError("report hash must be canonical current-selected report")
        if self.snapshot_hash != _SNAPSHOT_HASH:
            raise ValueError("snapshot hash must bind the current-selected snapshot")
        if self.snapshot_key != _SNAPSHOT_KEY or self.snapshot_version != 1:
            raise ValueError("snapshot identity mismatch")
        if (self.target_from, self.target_to_exclusive) != (
            _TARGET_FROM,
            _TARGET_TO_EXCLUSIVE,
        ):
            raise ValueError("target interval mismatch")
        if self.board_ids != ("main",):
            raise ValueError("target boards mismatch")
        if (
            type(self.dimension_interval_evidence) is not tuple
            or tuple(value[0] for value in self.dimension_interval_evidence)
            != _DIMENSIONS
        ):
            raise ValueError("dimension evidence must use required order")
        for evidence in self.dimension_interval_evidence:
            if type(evidence) is not tuple or len(evidence) != 4:
                raise TypeError("dimension evidence must be exact tuples")
            dimension, authority_hash, body_hash, intervals = evidence
            if dimension not in _DIMENSIONS:
                raise ValueError("unknown dimension evidence")
            if not _is_hash(authority_hash) or not _is_hash(body_hash):
                raise ValueError("dimension evidence hashes must be canonical")
            if type(intervals) is not tuple or not intervals:
                raise ValueError("dimension evidence intervals cannot be empty")
            previous = _TARGET_FROM
            for interval in intervals:
                if type(interval) is not tuple or len(interval) != 2:
                    raise TypeError("coverage intervals must be exact tuples")
                start, end = interval
                if type(start) is not int or type(end) is not int or start != previous:
                    raise ValueError("coverage intervals must be contiguous")
                if end <= start or end > _TARGET_TO_EXCLUSIVE:
                    raise ValueError("coverage interval bounds are invalid")
                previous = end
            if previous != _TARGET_TO_EXCLUSIVE:
                raise ValueError("coverage intervals must complete the target")
        if self.qualification != _QUALIFICATION:
            raise ValueError("qualification must remain development-only")
        if (
            type(self.finite_development_interval_coverage_complete) is not bool
            or not self.finite_development_interval_coverage_complete
        ):
            raise ValueError("finite development interval coverage must be complete")

    def _canonical_body(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_current_selected_rule_coverage_report",
            "schema_version": self.schema_version,
            "coverage_semantics": "finite_development_interval",
            "finite_development_interval_coverage_complete": (
                self.finite_development_interval_coverage_complete
            ),
            "declaration_hash": self.declaration_hash,
            "snapshot_hash": self.snapshot_hash,
            "snapshot_key": self.snapshot_key,
            "snapshot_version": self.snapshot_version,
            "target_scope": _target_scope(),
            "target_from": self.target_from,
            "target_to_exclusive": self.target_to_exclusive,
            "dimension_interval_evidence": [
                {
                    "dimension": dimension,
                    "authority_hash": authority_hash,
                    "canonical_body_hash": body_hash,
                    "intervals": [
                        {
                            "start_epoch_nanoseconds": start,
                            "end_exclusive_epoch_nanoseconds": end,
                        }
                        for start, end in intervals
                    ],
                }
                for dimension, authority_hash, body_hash, intervals in (
                    self.dimension_interval_evidence
                )
            ],
            "qualification": dict(self.qualification),
        }

    @property
    def report_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, object]:
        self._validate()
        return {**self._canonical_body(), "report_hash": self.report_hash}


def _failure(
    code: CnAShareCurrentSelectedRuleCoverageFailureCode,
    dimension: str | None = None,
) -> CnAShareCurrentSelectedRuleCoverageFailure:
    return CnAShareCurrentSelectedRuleCoverageFailure(code, dimension)


def _target_scope() -> dict[str, object]:
    return {
        "access_route": "DOMESTIC",
        "basis": "trade_notional",
        "board_ids": ["main"],
        "fee_product_class": "ORDINARY_A_SHARE",
        "instrument_type": "EQUITY",
        "quote_currency": "CNY",
        "settlement_currency": "CNY",
        "trade_mechanism": "AUCTION",
        "venue": "XSHE",
    }


def _is_hash(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 71
        and value.startswith("sha256:")
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def _require_exact_json(value: object) -> None:
    if value is None or type(value) is bool or type(value) is int or type(value) is str:
        return
    if type(value) is list:
        for item in value:
            _require_exact_json(item)
        return
    if type(value) is dict:
        if any(type(key) is not str for key in value):
            raise TypeError("JSON object keys must be exact strings")
        for item in value.values():
            _require_exact_json(item)
        return
    raise TypeError("declaration must contain exact JSON values")


def _dict(value: object) -> dict[str, object]:
    if type(value) is not dict:
        raise TypeError("value must be an exact JSON object")
    return value


def _list(value: object) -> list[object]:
    if type(value) is not list:
        raise TypeError("value must be an exact JSON array")
    return value


def _int(value: object) -> int:
    if type(value) is not int:
        raise TypeError("value must be an exact integer")
    return value


def _text(value: object) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise TypeError("value must be canonical non-empty text")
    return value


def _local_midnight_ns(value: object) -> int:
    local_date = date.fromisoformat(_text(value))
    instant = datetime.combine(local_date, time.min, _SHANGHAI).astimezone(UTC)
    delta = instant - _EPOCH
    return (
        delta.days * 86_400 + delta.seconds
    ) * 1_000_000_000 + delta.microseconds * 1_000


def _venue(value: object) -> str:
    venue = _dict(value)
    if set(venue) != {"type", "value"} or venue["type"] != "venue_id":
        raise ValueError("venue_id identity mismatch")
    return _text(venue["value"])


def _utc_ns(value: object) -> int:
    instant = _dict(value)
    if (
        set(instant) != {"epoch_nanoseconds", "type"}
        or instant["type"] != "utc_instant"
    ):
        raise ValueError("UTC instant identity mismatch")
    return _int(instant["epoch_nanoseconds"])


def _calendar_intervals(body: dict[str, object]) -> tuple[tuple[int, int], ...]:
    return (
        (
            _local_midnight_ns(body["coverage_start"]),
            _local_midnight_ns(body["coverage_end_exclusive"]),
        ),
    )


def _order_rule_intervals(body: dict[str, object]) -> tuple[tuple[int, int], ...]:
    intervals = []
    for value in _list(body["bands"]):
        band = _dict(value)
        if _venue(band["venue_id"]) == "xshe" and _text(band["board"]) in ("main",):
            intervals.append(
                (
                    _local_midnight_ns(band["effective_from"]),
                    _local_midnight_ns(band["effective_to_exclusive"]),
                )
            )
    return tuple(intervals)


def _utc_band_intervals(
    body: dict[str, object], start_key: str, end_key: str
) -> tuple[tuple[int, int], ...]:
    intervals = []
    for value in _list(body["bands"]):
        band = _dict(value)
        if _venue(band["venue_id"]) == "xshe":
            intervals.append((_utc_ns(band[start_key]), _utc_ns(band[end_key])))
    return tuple(intervals)


def _body_identity_matches(dimension: str, body: dict[str, object]) -> bool:
    if dimension == "calendar":
        return (
            body.get("type") == "cn_a_share_frozen_calendar"
            and body.get("schema_version") == 1
            and body.get("calendar_id") == "CN.XSHE"
            and body.get("timezone_name") == "Asia/Shanghai"
            and _venue(body.get("venue_id")) == "xshe"
        )
    if dimension == "order_rules":
        return (
            body.get("type") == "cn_a_share_order_rule_book"
            and body.get("schema_version") == 1
            and body.get("rule_book_key")
            == "equity.cn_a_share.cash.order-rules.development.v1"
            and body.get("rule_book_version") == 1
        )
    if dimension == "market_fees":
        return (
            body.get("type") == "cn_a_share_market_fee_rule_book_v2"
            and body.get("schema_version") == 1
            and body.get("rule_book_key")
            == (
                "equity.cn_a_share.cash.market-fees.domestic.ordinary-a-share."
                "current-selected-development.v2"
            )
            and body.get("rule_book_version") == 2
            and body.get("access_route") == "domestic"
            and body.get("fee_product_class") == "ordinary_a_share"
        )
    if dimension == "stamp_duty":
        return (
            body.get("type") == "cn_a_share_stamp_duty_rule_book_v2"
            and body.get("schema_version") == 1
            and body.get("rule_book_key")
            == (
                "equity.cn_a_share.cash.stamp-duty.domestic.ordinary-a-share."
                "current-selected-development.v2"
            )
            and body.get("rule_book_version") == 2
            and body.get("access_route") == "domestic"
            and body.get("fee_product_class") == "ordinary_a_share"
        )
    return (
        body.get("type") == "cn_a_share_corporate_action_entitlement_rule_book"
        and body.get("schema_version") == 1
    )


def _authority_hash(dimension: str, body: dict[str, object]) -> str:
    if dimension != "calendar":
        return canonical_sha256(body)
    days = sorted(
        _list(body["days"]), key=lambda value: _text(_dict(value)["local_date"])
    )
    return canonical_sha256(
        {
            "type": "cn_a_share_frozen_calendar",
            "schema_version": 1,
            "venue_id": body["venue_id"],
            "calendar_id": body["calendar_id"],
            "timezone_name": body["timezone_name"],
            "coverage_start": body["coverage_start"],
            "coverage_end_exclusive": body["coverage_end_exclusive"],
            "canonical_sorted_days": days,
        }
    )


def _coverage_state(
    intervals: tuple[tuple[int, int], ...],
) -> tuple[bool, bool, tuple[tuple[int, int], ...]]:
    if any(
        type(start) is not int or type(end) is not int or end <= start
        for start, end in intervals
    ):
        raise ValueError("authority interval must be non-empty")
    clipped = tuple(
        sorted(
            (
                (max(start, _TARGET_FROM), min(end, _TARGET_TO_EXCLUSIVE))
                for start, end in intervals
                if start < _TARGET_TO_EXCLUSIVE and end > _TARGET_FROM
            ),
            key=lambda value: (value[0], value[1]),
        )
    )
    cursor = _TARGET_FROM
    gap = not clipped
    overlap = False
    for start, end in clipped:
        if start > cursor:
            gap = True
        elif start < cursor:
            overlap = True
        cursor = max(cursor, end)
    if cursor < _TARGET_TO_EXCLUSIVE:
        gap = True
    return gap, overlap, clipped


def _declaration_matches(rebuilt: dict[str, object]) -> bool:
    if set(rebuilt) != _DECLARATION_KEYS:
        return False
    snapshot = _dict(rebuilt["snapshot"])
    target = _dict(rebuilt["target_coverage"])
    qualification = _dict(rebuilt["qualification"])
    return (
        rebuilt.get("type")
        == "cn_a_share_current_selected_development_rule_publication_declaration_v2"
        and rebuilt.get("schema_version") == 2
        and rebuilt.get("declaration_key")
        == (
            "equity.cn_a_share.current-selected-development.rule-authorities."
            "xshe.domestic.ordinary-a-share.2026-07.v2"
        )
        and rebuilt.get("declaration_version") == 2
        and rebuilt.get("publication") == _PUBLICATION
        and rebuilt.get("snapshot_hash") == _SNAPSHOT_HASH
        and canonical_sha256(snapshot) == _SNAPSHOT_HASH
        and snapshot.get("snapshot_key") == _SNAPSHOT_KEY
        and snapshot.get("snapshot_version") == 1
        and snapshot.get("target_scope") == _target_scope()
        and snapshot.get("target_from") == _TARGET_FROM
        and snapshot.get("target_to_exclusive") == _TARGET_TO_EXCLUSIVE
        and snapshot.get("development_evidence_available_at") == _EVIDENCE_AVAILABLE_AT
        and snapshot.get("qualification") == dict(_QUALIFICATION)
        and qualification == dict(_QUALIFICATION)
        and target
        == {
            "development_evidence_available_at_epoch_nanoseconds": (
                _EVIDENCE_AVAILABLE_AT
            ),
            "end_exclusive_epoch_nanoseconds": _TARGET_TO_EXCLUSIVE,
            "start_epoch_nanoseconds": _TARGET_FROM,
        }
        and not _contains_key(rebuilt, "official_record_as_of")
    )


def _contains_key(value: object, key: str) -> bool:
    if type(value) is dict:
        return key in value or any(_contains_key(item, key) for item in value.values())
    if type(value) is list:
        return any(_contains_key(item, key) for item in value)
    return False


def analyze_cn_a_share_current_selected_rule_coverage_v1(
    declaration: Mapping[str, object],
    /,
) -> (
    CnAShareCurrentSelectedRuleCoverageReport
    | CnAShareCurrentSelectedRuleCoverageFailure
):
    try:
        if type(declaration) is not dict:
            raise TypeError("declaration must be exact dict")
        _require_exact_json(declaration)
        rebuilt = json.loads(canonical_bytes(declaration))
        if type(rebuilt) is not dict or rebuilt != declaration:
            raise ValueError("declaration must canonical-rebuild exactly")
        authorities = _dict(rebuilt["authorities"])
        present = tuple(
            dimension for dimension in _DIMENSIONS if dimension in authorities
        )
        parsed: dict[
            str,
            tuple[
                str,
                str,
                tuple[tuple[int, int], ...],
                bool,
                bool,
            ],
        ] = {}
        for dimension in present:
            entry = _dict(authorities[dimension])
            if set(entry) != {"authority_hash", "body", "canonical_body_hash"}:
                raise ValueError("authority entry shape mismatch")
            authority_hash = _text(entry["authority_hash"])
            body_hash = _text(entry["canonical_body_hash"])
            if not _is_hash(authority_hash) or not _is_hash(body_hash):
                raise ValueError("authority hashes must be canonical")
            body = _dict(entry["body"])
            identity_matches = _body_identity_matches(dimension, body)
            if dimension == "calendar":
                intervals = _calendar_intervals(body)
            elif dimension == "order_rules":
                intervals = _order_rule_intervals(body)
            elif dimension in {"market_fees", "stamp_duty"}:
                intervals = _utc_band_intervals(
                    body, "effective_from", "effective_to_exclusive"
                )
            else:
                intervals = _utc_band_intervals(
                    body, "effective_start", "effective_end"
                )
            _coverage_state(intervals)
            parsed[dimension] = (
                authority_hash,
                body_hash,
                intervals,
                identity_matches,
                body_hash == canonical_sha256(body)
                and authority_hash == _authority_hash(dimension, body),
            )
    except (KeyError, TypeError, ValueError, OverflowError, RecursionError):
        return _failure(CnAShareCurrentSelectedRuleCoverageFailureCode.INVALID_INPUT)

    try:
        declaration_matches = _declaration_matches(rebuilt)
    except (KeyError, TypeError, ValueError):
        return _failure(CnAShareCurrentSelectedRuleCoverageFailureCode.INVALID_INPUT)
    declaration_mismatch = (
        not declaration_matches
        or any(not parsed[dimension][3] for dimension in present)
        or any(dimension not in _DIMENSIONS for dimension in authorities)
    )

    missing = next(
        (dimension for dimension in _DIMENSIONS if dimension not in authorities), None
    )
    if declaration_mismatch:
        return _failure(
            CnAShareCurrentSelectedRuleCoverageFailureCode.BUNDLE_DECLARATION_MISMATCH
        )
    if missing is not None:
        return _failure(
            CnAShareCurrentSelectedRuleCoverageFailureCode.MISSING_REQUIRED_DIMENSION,
            missing,
        )

    states: dict[str, tuple[bool, bool, tuple[tuple[int, int], ...]]] = {}
    try:
        states = {
            dimension: _coverage_state(parsed[dimension][2])
            for dimension in _DIMENSIONS
        }
    except (TypeError, ValueError):
        return _failure(CnAShareCurrentSelectedRuleCoverageFailureCode.INVALID_INPUT)
    gap = next((dimension for dimension in _DIMENSIONS if states[dimension][0]), None)
    if gap is not None:
        return _failure(
            CnAShareCurrentSelectedRuleCoverageFailureCode.COVERAGE_GAP, gap
        )
    overlap = next(
        (dimension for dimension in _DIMENSIONS if states[dimension][1]), None
    )
    if overlap is not None:
        return _failure(
            CnAShareCurrentSelectedRuleCoverageFailureCode.COVERAGE_OVERLAP,
            overlap,
        )
    source_mismatch = next(
        (dimension for dimension in _DIMENSIONS if not parsed[dimension][4]), None
    )
    if source_mismatch is not None:
        return _failure(
            CnAShareCurrentSelectedRuleCoverageFailureCode.SOURCE_IDENTITY_MISMATCH,
            source_mismatch,
        )

    declaration_hash = canonical_sha256(rebuilt)
    # ponytail: success identity gate keeps frozen declaration pin after coverage/identity checks
    if declaration_hash != _DECLARATION_HASH:
        return _failure(
            CnAShareCurrentSelectedRuleCoverageFailureCode.BUNDLE_DECLARATION_MISMATCH
        )

    return CnAShareCurrentSelectedRuleCoverageReport(
        declaration_hash=declaration_hash,
        snapshot_hash=_SNAPSHOT_HASH,
        snapshot_key=_SNAPSHOT_KEY,
        snapshot_version=1,
        target_from=_TARGET_FROM,
        target_to_exclusive=_TARGET_TO_EXCLUSIVE,
        board_ids=("main",),
        dimension_interval_evidence=tuple(
            (
                dimension,
                parsed[dimension][0],
                parsed[dimension][1],
                states[dimension][2],
            )
            for dimension in _DIMENSIONS
        ),
        qualification=_QUALIFICATION,
    )
