from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from crypto_quant_domain import (
    DomainId,
    DomainIdKind,
    FeeBasisType,
    OrderStatus,
    PortfolioSnapshot,
    PositionBalance,
    Quantity,
    SessionId,
    UtcInstant,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_trading import (
    AccountSettlementObligation,
    FeeAssessmentBasisEvidence,
    OrderEventStream,
    ReservationCommitment,
    ResourceReservationState,
    SettlementBookState,
)

from .ports import (
    CloseoutPolicy,
    SimulationComponentRef,
    SimulationPortOutcome,
    SimulationPortSpec,
    SimulationPortType,
)
from .timeline import TimelineCursor, TimelineWindow


_SHA256_PATTERN = re.compile(r"sha256:[0-9a-f]{64}")
_TERMINAL_ORDER_STATUSES = frozenset(
    {
        OrderStatus.FILLED,
        OrderStatus.CANCELLED,
        OrderStatus.EXPIRED,
        OrderStatus.REJECTED,
    }
)
_MARK_TO_MARKET_COMPONENT = SimulationComponentRef(
    SimulationPortType.CLOSEOUT_POLICY,
    "mark_to_market.v1",
    1,
    canonical_sha256(
        {
            "type": "mark_to_market_closeout_policy_config",
            "schema_version": 1,
            "preserve_positions": True,
            "implicit_fill": False,
        }
    ),
)


def _canonical_text(name: str, value: object) -> str:
    if type(value) is not str:
        raise TypeError(f"{name} must be str")
    if not value or value != value.strip():
        raise ValueError(f"{name} must be nonempty without surrounding whitespace")
    if unicodedata.normalize("NFC", value) != value:
        raise ValueError(f"{name} must be canonical NFC text")
    return value


def _require_hash(name: str, value: object) -> str:
    if type(value) is not str or _SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{name} must be a canonical sha256 identity")
    return value


def _sorted_hashes(name: str, values: tuple[str, ...]) -> tuple[str, ...]:
    if type(values) is not tuple:
        raise TypeError(f"{name} must be tuple")
    ordered = tuple(sorted(_require_hash(name, value) for value in values))
    if len(ordered) != len(set(ordered)):
        raise ValueError(f"{name} must be unique")
    return ordered


def _basis_id_text(value: DomainId | SessionId) -> str:
    if isinstance(value, DomainId):
        return value.value
    if isinstance(value, SessionId):
        return f"{value.calendar_id}:{value.value}"
    raise TypeError("fee basis identity must be DomainId or SessionId")


class RunEndCloseoutMode(str, Enum):
    MARK_TO_MARKET = "mark_to_market"
    LIQUIDATE_BEFORE_END = "liquidate_before_end"


class RunEndCloseoutStatus(str, Enum):
    POSITIONS_PRESERVED = "positions_preserved"
    LIQUIDATION_COMPLETED = "liquidation_completed"
    LIQUIDATION_INCOMPLETE = "liquidation_incomplete"


class EngineTerminationCode(str, Enum):
    TIMELINE_INCOMPLETE = "timeline_incomplete"
    BOUNDARY_VIOLATION = "boundary_violation"
    EVIDENCE_MISMATCH = "evidence_mismatch"
    CLOSEOUT_OUTCOME_MISMATCH = "closeout_outcome_mismatch"
    CLOSEOUT_POLICY_FAILURE = "closeout_policy_failure"
    LIQUIDATION_INCOMPLETE = "liquidation_incomplete"


@dataclass(frozen=True, slots=True)
class PendingFeeAssessmentRef:
    basis_type: FeeBasisType
    basis_ids: tuple[str, ...]
    basis_hash: str
    closed_at: UtcInstant

    def __post_init__(self) -> None:
        if not isinstance(self.basis_type, FeeBasisType):
            raise TypeError("basis_type must be FeeBasisType")
        if type(self.basis_ids) is not tuple or not self.basis_ids:
            raise TypeError("basis_ids must be nonempty tuple")
        basis_ids = tuple(sorted(_canonical_text("basis_id", value) for value in self.basis_ids))
        if len(basis_ids) != len(set(basis_ids)):
            raise ValueError("basis_ids must be unique")
        object.__setattr__(self, "basis_ids", basis_ids)
        _require_hash("basis_hash", self.basis_hash)
        if not isinstance(self.closed_at, UtcInstant):
            raise TypeError("closed_at must be UtcInstant")

    @classmethod
    def from_basis(cls, basis: FeeAssessmentBasisEvidence) -> PendingFeeAssessmentRef:
        if not isinstance(basis, FeeAssessmentBasisEvidence):
            raise TypeError("basis must be FeeAssessmentBasisEvidence")
        return cls(
            basis_type=basis.basis_type,
            basis_ids=tuple(_basis_id_text(value) for value in basis.basis_ids),
            basis_hash=basis.basis_hash,
            closed_at=basis.closed_at,
        )

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "pending_fee_assessment_ref",
            "schema_version": 1,
            "basis_type": self.basis_type.value,
            "basis_ids": self.basis_ids,
            "basis_hash": self.basis_hash,
            "closed_at": self.closed_at,
        }


@dataclass(frozen=True, slots=True)
class RunEndEvidence:
    timeline_window: TimelineWindow
    timeline_cursor: TimelineCursor
    final_snapshot: PortfolioSnapshot
    order_streams: tuple[OrderEventStream, ...]
    reservation_state: ResourceReservationState
    settlement_state: SettlementBookState
    pending_fee_assessments: tuple[FeeAssessmentBasisEvidence, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.timeline_window, TimelineWindow):
            raise TypeError("timeline_window must be TimelineWindow")
        if not isinstance(self.timeline_cursor, TimelineCursor):
            raise TypeError("timeline_cursor must be TimelineCursor")
        if not isinstance(self.final_snapshot, PortfolioSnapshot):
            raise TypeError("final_snapshot must be PortfolioSnapshot")
        if type(self.order_streams) is not tuple or not all(
            isinstance(value, OrderEventStream) for value in self.order_streams
        ):
            raise TypeError("order_streams must contain OrderEventStream")
        streams = tuple(
            sorted(self.order_streams, key=lambda value: value.order.order_id.value)
        )
        order_ids = tuple(value.order.order_id.value for value in streams)
        if len(order_ids) != len(set(order_ids)):
            raise ValueError("duplicate Order stream identity")
        object.__setattr__(self, "order_streams", streams)
        if not isinstance(self.reservation_state, ResourceReservationState):
            raise TypeError("reservation_state must be ResourceReservationState")
        if not isinstance(self.settlement_state, SettlementBookState):
            raise TypeError("settlement_state must be SettlementBookState")
        if type(self.pending_fee_assessments) is not tuple or not all(
            isinstance(value, FeeAssessmentBasisEvidence)
            for value in self.pending_fee_assessments
        ):
            raise TypeError(
                "pending_fee_assessments must contain FeeAssessmentBasisEvidence"
            )
        fees = tuple(
            sorted(self.pending_fee_assessments, key=lambda value: value.basis_hash)
        )
        fee_hashes = tuple(value.basis_hash for value in fees)
        if len(fee_hashes) != len(set(fee_hashes)):
            raise ValueError("duplicate pending Fee basis evidence")
        fee_identities = tuple(
            (
                value.basis_type,
                tuple(_basis_id_text(identity) for identity in value.basis_ids),
            )
            for value in fees
        )
        if len(fee_identities) != len(set(fee_identities)):
            raise ValueError("conflicting pending Fee basis identity")
        object.__setattr__(self, "pending_fee_assessments", fees)
        account_id = self.final_snapshot.account_id
        if self.reservation_state.account_id != account_id:
            raise ValueError("Reservation account does not match Final Snapshot")
        if self.settlement_state.account_id != account_id:
            raise ValueError("Settlement account does not match Final Snapshot")
        if any(value.order.account_id != account_id for value in streams):
            raise ValueError("Order account does not match Final Snapshot")
        if any(value.account_id != account_id for value in fees):
            raise ValueError("Fee basis account does not match Final Snapshot")

    @property
    def evidence_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "run_end_evidence",
            "schema_version": 1,
            "timeline_window": self.timeline_window,
            "timeline_cursor": self.timeline_cursor,
            "final_snapshot": self.final_snapshot,
            "order_streams": self.order_streams,
            "reservation_state": self.reservation_state,
            "settlement_state": self.settlement_state,
            "pending_fee_assessments": self.pending_fee_assessments,
        }


@dataclass(frozen=True, slots=True)
class RunEndCloseoutRequest:
    account_id: str
    trading_end_exclusive: UtcInstant
    run_end_evidence_hash: str
    final_snapshot_hash: str
    open_position_hashes: tuple[str, ...]
    working_order_stream_hashes: tuple[str, ...]
    pending_settlement_ids: tuple[str, ...]
    pending_fee_basis_hashes: tuple[str, ...]

    def __post_init__(self) -> None:
        _canonical_text("account_id", self.account_id)
        if not isinstance(self.trading_end_exclusive, UtcInstant):
            raise TypeError("trading_end_exclusive must be UtcInstant")
        _require_hash("run_end_evidence_hash", self.run_end_evidence_hash)
        _require_hash("final_snapshot_hash", self.final_snapshot_hash)
        object.__setattr__(
            self,
            "open_position_hashes",
            _sorted_hashes("open_position_hashes", self.open_position_hashes),
        )
        object.__setattr__(
            self,
            "working_order_stream_hashes",
            _sorted_hashes(
                "working_order_stream_hashes", self.working_order_stream_hashes
            ),
        )
        if type(self.pending_settlement_ids) is not tuple:
            raise TypeError("pending_settlement_ids must be tuple")
        settlement_ids = tuple(
            sorted(
                _canonical_text("pending_settlement_id", value)
                for value in self.pending_settlement_ids
            )
        )
        if len(settlement_ids) != len(set(settlement_ids)):
            raise ValueError("pending_settlement_ids must be unique")
        object.__setattr__(self, "pending_settlement_ids", settlement_ids)
        object.__setattr__(
            self,
            "pending_fee_basis_hashes",
            _sorted_hashes(
                "pending_fee_basis_hashes", self.pending_fee_basis_hashes
            ),
        )

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "run_end_closeout_request",
            "schema_version": 1,
            "account_id": self.account_id,
            "trading_end_exclusive": self.trading_end_exclusive,
            "run_end_evidence_hash": self.run_end_evidence_hash,
            "final_snapshot_hash": self.final_snapshot_hash,
            "open_position_hashes": self.open_position_hashes,
            "working_order_stream_hashes": self.working_order_stream_hashes,
            "pending_settlement_ids": self.pending_settlement_ids,
            "pending_fee_basis_hashes": self.pending_fee_basis_hashes,
        }


@dataclass(frozen=True, slots=True)
class RunEndCloseoutDecision:
    mode: RunEndCloseoutMode
    status: RunEndCloseoutStatus
    completed_at: UtcInstant
    completion_evidence_hashes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.mode, RunEndCloseoutMode):
            raise TypeError("mode must be RunEndCloseoutMode")
        if not isinstance(self.status, RunEndCloseoutStatus):
            raise TypeError("status must be RunEndCloseoutStatus")
        if not isinstance(self.completed_at, UtcInstant):
            raise TypeError("completed_at must be UtcInstant")
        object.__setattr__(
            self,
            "completion_evidence_hashes",
            _sorted_hashes(
                "completion_evidence_hashes", self.completion_evidence_hashes
            ),
        )
        if self.mode is RunEndCloseoutMode.MARK_TO_MARKET:
            if self.status is not RunEndCloseoutStatus.POSITIONS_PRESERVED:
                raise ValueError("mark-to-market must preserve positions")
            if self.completion_evidence_hashes:
                raise ValueError("mark-to-market cannot carry liquidation evidence")
        elif self.status is RunEndCloseoutStatus.POSITIONS_PRESERVED:
            raise ValueError("liquidation cannot report positions_preserved")
        if (
            self.status is RunEndCloseoutStatus.LIQUIDATION_COMPLETED
            and not self.completion_evidence_hashes
        ):
            raise ValueError("completed liquidation requires full-chain evidence")
        if (
            self.status is RunEndCloseoutStatus.LIQUIDATION_INCOMPLETE
            and self.completion_evidence_hashes
        ):
            raise ValueError("incomplete liquidation cannot claim completion evidence")

    @property
    def decision_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "run_end_closeout_decision",
            "schema_version": 1,
            "mode": self.mode.value,
            "status": self.status.value,
            "completed_at": self.completed_at,
            "completion_evidence_hashes": self.completion_evidence_hashes,
        }


@dataclass(frozen=True, slots=True)
class RunEndCloseoutFailure:
    reason_code: str
    subject_key: str

    def __post_init__(self) -> None:
        _canonical_text("reason_code", self.reason_code)
        _canonical_text("subject_key", self.subject_key)

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "run_end_closeout_failure",
            "schema_version": 1,
            "reason_code": self.reason_code,
            "subject_key": self.subject_key,
        }


@dataclass(frozen=True, slots=True)
class _RunEndCloseoutApplicability:
    policy_mode: RunEndCloseoutMode
    requires_pre_boundary_completion: bool

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "run_end_closeout_applicability",
            "schema_version": 1,
            "policy_mode": self.policy_mode.value,
            "requires_pre_boundary_completion": self.requires_pre_boundary_completion,
        }


@dataclass(frozen=True, slots=True)
class MarkToMarketCloseoutPolicy:
    component_ref: SimulationComponentRef = field(
        init=False, default=_MARK_TO_MARKET_COMPONENT
    )

    def spec(self) -> SimulationPortSpec:
        return SimulationPortSpec(
            component_ref=self.component_ref,
            required_capabilities=(),
            applicability=_RunEndCloseoutApplicability(
                RunEndCloseoutMode.MARK_TO_MARKET,
                requires_pre_boundary_completion=False,
            ),
        )

    def resolve_closeout(
        self, request: RunEndCloseoutRequest, /
    ) -> SimulationPortOutcome[RunEndCloseoutDecision, RunEndCloseoutFailure]:
        if not isinstance(request, RunEndCloseoutRequest):
            raise TypeError("request must be RunEndCloseoutRequest")
        return SimulationPortOutcome.for_result(
            self.component_ref,
            request,
            RunEndCloseoutDecision(
                mode=RunEndCloseoutMode.MARK_TO_MARKET,
                status=RunEndCloseoutStatus.POSITIONS_PRESERVED,
                completed_at=request.trading_end_exclusive,
            ),
        )


@dataclass(frozen=True, slots=True)
class OrderTerminatedByRunEnd:
    order_id: DomainId
    stream_hash: str
    state_hash: str
    prior_status: OrderStatus
    remaining_quantity: Quantity
    terminated_at: UtcInstant

    def __post_init__(self) -> None:
        if not isinstance(self.order_id, DomainId):
            raise TypeError("order_id must be DomainId")
        if self.order_id.kind is not DomainIdKind.ORDER:
            raise ValueError("order_id must use ORDER kind")
        _require_hash("stream_hash", self.stream_hash)
        _require_hash("state_hash", self.state_hash)
        if not isinstance(self.prior_status, OrderStatus):
            raise TypeError("prior_status must be OrderStatus")
        if self.prior_status in _TERMINAL_ORDER_STATUSES:
            raise ValueError("terminal Order cannot be terminated by Run End")
        if not isinstance(self.remaining_quantity, Quantity):
            raise TypeError("remaining_quantity must be Quantity")
        if self.remaining_quantity.units <= 0:
            raise ValueError("Run End termination requires positive remaining Quantity")
        if not isinstance(self.terminated_at, UtcInstant):
            raise TypeError("terminated_at must be UtcInstant")

    @property
    def termination_id(self) -> str:
        return canonical_sha256(self._payload())

    def _payload(self) -> dict[str, object]:
        return {
            "type": "order_terminated_by_run_end_payload",
            "schema_version": 1,
            "order_id": self.order_id,
            "stream_hash": self.stream_hash,
            "state_hash": self.state_hash,
            "prior_status": self.prior_status.value,
            "remaining_quantity": self.remaining_quantity,
            "terminated_at": self.terminated_at,
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "order_terminated_by_run_end",
            "schema_version": 1,
            "termination_id": self.termination_id,
            **{key: value for key, value in self._payload().items() if key not in {"type", "schema_version"}},
        }


@dataclass(frozen=True, slots=True)
class RunEndReservationRelease:
    order_id: DomainId
    reservation_hash: str
    commitment: ReservationCommitment
    released_at: UtcInstant

    def __post_init__(self) -> None:
        if not isinstance(self.order_id, DomainId):
            raise TypeError("order_id must be DomainId")
        if self.order_id.kind is not DomainIdKind.ORDER:
            raise ValueError("order_id must use ORDER kind")
        _require_hash("reservation_hash", self.reservation_hash)
        if not isinstance(self.commitment, ReservationCommitment):
            raise TypeError("commitment must be ReservationCommitment")
        if self.commitment.is_empty:
            raise ValueError("released Reservation cannot be empty")
        if not isinstance(self.released_at, UtcInstant):
            raise TypeError("released_at must be UtcInstant")

    @property
    def release_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "run_end_reservation_release",
            "schema_version": 1,
            "order_id": self.order_id,
            "reservation_hash": self.reservation_hash,
            "commitment": self.commitment,
            "released_at": self.released_at,
        }


@dataclass(frozen=True, slots=True)
class EngineTermination:
    code: EngineTerminationCode
    trading_end_exclusive: UtcInstant
    run_end_evidence_hash: str
    subject_keys: tuple[str, ...]
    detail_hashes: tuple[str, ...] = ()
    closeout_outcome_hash: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.code, EngineTerminationCode):
            raise TypeError("code must be EngineTerminationCode")
        if not isinstance(self.trading_end_exclusive, UtcInstant):
            raise TypeError("trading_end_exclusive must be UtcInstant")
        _require_hash("run_end_evidence_hash", self.run_end_evidence_hash)
        if type(self.subject_keys) is not tuple or not self.subject_keys:
            raise TypeError("subject_keys must be nonempty tuple")
        subjects = tuple(sorted(_canonical_text("subject_key", value) for value in self.subject_keys))
        if len(subjects) != len(set(subjects)):
            raise ValueError("subject_keys must be unique")
        object.__setattr__(self, "subject_keys", subjects)
        object.__setattr__(
            self, "detail_hashes", _sorted_hashes("detail_hashes", self.detail_hashes)
        )
        if self.closeout_outcome_hash is not None:
            _require_hash("closeout_outcome_hash", self.closeout_outcome_hash)

    @property
    def termination_id(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "engine_termination",
            "schema_version": 1,
            "code": self.code.value,
            "trading_end_exclusive": self.trading_end_exclusive,
            "run_end_evidence_hash": self.run_end_evidence_hash,
            "subject_keys": self.subject_keys,
            "detail_hashes": self.detail_hashes,
            "closeout_outcome_hash": self.closeout_outcome_hash,
        }


@dataclass(frozen=True, slots=True)
class RunEndReport:
    account_id: str
    trading_end_exclusive: UtcInstant
    run_end_evidence_hash: str
    timeline_cursor_hash: str
    final_snapshot_hash: str
    journal_state_hash: str
    reservation_state_hash: str
    settlement_state_hash: str
    terminated_orders: tuple[OrderTerminatedByRunEnd, ...]
    released_reservations: tuple[RunEndReservationRelease, ...]
    open_positions: tuple[PositionBalance, ...]
    pending_settlements: tuple[AccountSettlementObligation, ...]
    pending_fee_assessments: tuple[PendingFeeAssessmentRef, ...]
    last_valuation_mark_ids: tuple[str, ...]
    closeout_component_ref: SimulationComponentRef
    closeout_outcome_hash: str
    closeout_mode: RunEndCloseoutMode
    closeout_status: RunEndCloseoutStatus

    def __post_init__(self) -> None:
        _canonical_text("account_id", self.account_id)
        if not isinstance(self.trading_end_exclusive, UtcInstant):
            raise TypeError("trading_end_exclusive must be UtcInstant")
        for name, value in (
            ("run_end_evidence_hash", self.run_end_evidence_hash),
            ("timeline_cursor_hash", self.timeline_cursor_hash),
            ("final_snapshot_hash", self.final_snapshot_hash),
            ("journal_state_hash", self.journal_state_hash),
            ("reservation_state_hash", self.reservation_state_hash),
            ("settlement_state_hash", self.settlement_state_hash),
            ("closeout_outcome_hash", self.closeout_outcome_hash),
        ):
            _require_hash(name, value)
        if type(self.terminated_orders) is not tuple or not all(
            isinstance(value, OrderTerminatedByRunEnd)
            for value in self.terminated_orders
        ):
            raise TypeError("terminated_orders must contain termination evidence")
        ordered_terminations = tuple(
            sorted(self.terminated_orders, key=lambda value: value.order_id.value)
        )
        termination_ids = tuple(
            value.order_id.value for value in self.terminated_orders
        )
        if ordered_terminations != self.terminated_orders:
            raise ValueError("terminated_orders must use canonical order")
        if len(termination_ids) != len(set(termination_ids)):
            raise ValueError("terminated_orders must have unique Order identities")
        if type(self.released_reservations) is not tuple or not all(
            isinstance(value, RunEndReservationRelease)
            for value in self.released_reservations
        ):
            raise TypeError("released_reservations must contain release evidence")
        ordered_releases = tuple(
            sorted(self.released_reservations, key=lambda value: value.order_id.value)
        )
        release_ids = tuple(
            value.order_id.value for value in self.released_reservations
        )
        if ordered_releases != self.released_reservations:
            raise ValueError("released_reservations must use canonical order")
        if len(release_ids) != len(set(release_ids)):
            raise ValueError("released_reservations must have unique Order identities")
        if not set(release_ids).issubset(termination_ids):
            raise ValueError("released Reservation lacks Run End termination")
        if type(self.open_positions) is not tuple or not all(
            isinstance(value, PositionBalance) for value in self.open_positions
        ):
            raise TypeError("open_positions must contain PositionBalance")
        if tuple(sorted(self.open_positions, key=canonical_bytes)) != self.open_positions:
            raise ValueError("open_positions must use canonical order")
        if any(value.key.account_id != self.account_id for value in self.open_positions):
            raise ValueError("open Position account mismatch")
        if type(self.pending_settlements) is not tuple or not all(
            isinstance(value, AccountSettlementObligation)
            for value in self.pending_settlements
        ):
            raise TypeError("pending_settlements must contain obligations")
        settlement_ids = tuple(
            value.obligation.settlement_obligation_id.value
            for value in self.pending_settlements
        )
        if tuple(sorted(settlement_ids)) != settlement_ids:
            raise ValueError("pending_settlements must use canonical order")
        if len(settlement_ids) != len(set(settlement_ids)):
            raise ValueError("pending_settlements must be unique")
        if any(
            value.account_id != self.account_id for value in self.pending_settlements
        ):
            raise ValueError("pending Settlement account mismatch")
        if any(
            value.terminated_at != self.trading_end_exclusive
            for value in self.terminated_orders
        ):
            raise ValueError("Order termination must occur at Run End boundary")
        if any(
            value.released_at != self.trading_end_exclusive
            for value in self.released_reservations
        ):
            raise ValueError("Reservation release must occur at Run End boundary")
        if type(self.pending_fee_assessments) is not tuple or not all(
            isinstance(value, PendingFeeAssessmentRef)
            for value in self.pending_fee_assessments
        ):
            raise TypeError("pending_fee_assessments must contain references")
        if (
            tuple(
                sorted(
                    self.pending_fee_assessments,
                    key=lambda value: value.basis_hash,
                )
            )
            != self.pending_fee_assessments
        ):
            raise ValueError("pending_fee_assessments must use canonical order")
        if type(self.last_valuation_mark_ids) is not tuple:
            raise TypeError("last_valuation_mark_ids must be tuple")
        marks = tuple(
            sorted(
                _canonical_text("valuation_mark_id", value)
                for value in self.last_valuation_mark_ids
            )
        )
        if len(marks) != len(set(marks)):
            raise ValueError("last_valuation_mark_ids must be unique")
        object.__setattr__(self, "last_valuation_mark_ids", marks)
        if not isinstance(self.closeout_component_ref, SimulationComponentRef):
            raise TypeError("closeout_component_ref must be SimulationComponentRef")
        if self.closeout_component_ref.port_type is not SimulationPortType.CLOSEOUT_POLICY:
            raise ValueError("closeout component must be CLOSEOUT_POLICY")
        if not isinstance(self.closeout_mode, RunEndCloseoutMode):
            raise TypeError("closeout_mode must be RunEndCloseoutMode")
        if not isinstance(self.closeout_status, RunEndCloseoutStatus):
            raise TypeError("closeout_status must be RunEndCloseoutStatus")
        if (
            self.closeout_mode is RunEndCloseoutMode.MARK_TO_MARKET
            and self.closeout_status is not RunEndCloseoutStatus.POSITIONS_PRESERVED
        ):
            raise ValueError("mark-to-market Report must preserve positions")
        if (
            self.closeout_mode is RunEndCloseoutMode.LIQUIDATE_BEFORE_END
            and self.closeout_status is not RunEndCloseoutStatus.LIQUIDATION_COMPLETED
        ):
            raise ValueError("liquidation Report must be completed")

    @property
    def report_id(self) -> str:
        return canonical_sha256(self._payload())

    @property
    def report_hash(self) -> str:
        return canonical_sha256(self)

    def _payload(self) -> dict[str, object]:
        return {
            "type": "run_end_report_payload",
            "schema_version": 1,
            "account_id": self.account_id,
            "trading_end_exclusive": self.trading_end_exclusive,
            "run_end_evidence_hash": self.run_end_evidence_hash,
            "timeline_cursor_hash": self.timeline_cursor_hash,
            "final_snapshot_hash": self.final_snapshot_hash,
            "journal_state_hash": self.journal_state_hash,
            "reservation_state_hash": self.reservation_state_hash,
            "settlement_state_hash": self.settlement_state_hash,
            "terminated_orders": self.terminated_orders,
            "released_reservations": self.released_reservations,
            "open_positions": self.open_positions,
            "pending_settlements": self.pending_settlements,
            "pending_fee_assessments": self.pending_fee_assessments,
            "last_valuation_mark_ids": self.last_valuation_mark_ids,
            "closeout_component_ref": self.closeout_component_ref,
            "closeout_outcome_hash": self.closeout_outcome_hash,
            "closeout_mode": self.closeout_mode.value,
            "closeout_status": self.closeout_status.value,
        }

    def to_canonical_dict(self) -> dict[str, object]:
        payload = self._payload()
        return {
            "type": "run_end_report",
            "schema_version": 1,
            "report_id": self.report_id,
            **{key: value for key, value in payload.items() if key not in {"type", "schema_version"}},
        }


@dataclass(frozen=True, slots=True)
class RunEndOutcome:
    run_end_evidence_hash: str
    report: RunEndReport | None = None
    termination: EngineTermination | None = None

    def __post_init__(self) -> None:
        _require_hash("run_end_evidence_hash", self.run_end_evidence_hash)
        if (self.report is None) == (self.termination is None):
            raise ValueError("RunEndOutcome requires exactly one report or termination")
        if self.report is not None:
            if not isinstance(self.report, RunEndReport):
                raise TypeError("report must be RunEndReport")
            if self.report.run_end_evidence_hash != self.run_end_evidence_hash:
                raise ValueError("Report evidence hash mismatch")
        if self.termination is not None:
            if not isinstance(self.termination, EngineTermination):
                raise TypeError("termination must be EngineTermination")
            if self.termination.run_end_evidence_hash != self.run_end_evidence_hash:
                raise ValueError("Termination evidence hash mismatch")

    @property
    def outcome_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "run_end_outcome",
            "schema_version": 1,
            "run_end_evidence_hash": self.run_end_evidence_hash,
            "report": self.report,
            "termination": self.termination,
        }


class RunEndCoordinator:
    def coordinate(
        self,
        evidence: RunEndEvidence,
        closeout_policy: CloseoutPolicy[
            RunEndCloseoutRequest,
            RunEndCloseoutDecision,
            RunEndCloseoutFailure,
        ],
    ) -> RunEndOutcome:
        if not isinstance(evidence, RunEndEvidence):
            raise TypeError("evidence must be RunEndEvidence")
        boundary_failure = self._validate_boundary(evidence)
        if boundary_failure is not None:
            return boundary_failure

        states = []
        for stream in evidence.order_streams:
            state = stream.state
            if state is None:
                return self._terminate(
                    evidence,
                    EngineTerminationCode.EVIDENCE_MISMATCH,
                    (stream.order.order_id.value,),
                    (stream.stream_hash,),
                )
            states.append((stream, state))
        working = tuple(
            (stream, state)
            for stream, state in states
            if state.status not in _TERMINAL_ORDER_STATUSES
        )
        reservation_by_order = {
            value.order_id.value: value
            for value in evidence.reservation_state.active_reservations
        }
        stream_by_order = {
            stream.order.order_id.value: stream for stream in evidence.order_streams
        }
        cursor_by_order = {
            value.order_id.value: value for value in evidence.reservation_state.cursors
        }
        unknown_cursors = tuple(sorted(set(cursor_by_order) - set(stream_by_order)))
        if unknown_cursors:
            return self._terminate(
                evidence,
                EngineTerminationCode.EVIDENCE_MISMATCH,
                unknown_cursors,
                tuple(cursor_by_order[key].stream_hash for key in unknown_cursors),
            )
        for order_id, cursor in cursor_by_order.items():
            stream = stream_by_order[order_id]
            if (
                cursor.event_count != stream.event_count
                or cursor.stream_hash != stream.stream_hash
            ):
                return self._terminate(
                    evidence,
                    EngineTerminationCode.EVIDENCE_MISMATCH,
                    (order_id,),
                    (cursor.stream_hash, stream.stream_hash),
                )
        working_ids = {stream.order.order_id.value for stream, _ in working}
        unknown_reservations = tuple(sorted(set(reservation_by_order) - working_ids))
        if unknown_reservations:
            return self._terminate(
                evidence,
                EngineTerminationCode.EVIDENCE_MISMATCH,
                unknown_reservations,
                tuple(
                    reservation_by_order[key].reservation_hash
                    for key in unknown_reservations
                ),
            )
        for stream, state in working:
            active = reservation_by_order.get(stream.order.order_id.value)
            if active is not None and (
                active.remaining_quantity != state.remaining_quantity
                or active.account_id != stream.order.account_id
            ):
                return self._terminate(
                    evidence,
                    EngineTerminationCode.EVIDENCE_MISMATCH,
                    (stream.order.order_id.value,),
                    (active.reservation_hash, stream.state_hash),
                )

        terminations = tuple(
            OrderTerminatedByRunEnd(
                order_id=stream.order.order_id,
                stream_hash=stream.stream_hash,
                state_hash=stream.state_hash,
                prior_status=state.status,
                remaining_quantity=state.remaining_quantity,
                terminated_at=evidence.timeline_window.end_exclusive,
            )
            for stream, state in working
        )
        releases = tuple(
            RunEndReservationRelease(
                order_id=active.order_id,
                reservation_hash=active.reservation_hash,
                commitment=active.commitment,
                released_at=evidence.timeline_window.end_exclusive,
            )
            for active in sorted(
                evidence.reservation_state.active_reservations,
                key=lambda value: value.order_id.value,
            )
        )
        pending_fee_refs = tuple(
            PendingFeeAssessmentRef.from_basis(value)
            for value in evidence.pending_fee_assessments
        )
        request = RunEndCloseoutRequest(
            account_id=evidence.final_snapshot.account_id,
            trading_end_exclusive=evidence.timeline_window.end_exclusive,
            run_end_evidence_hash=evidence.evidence_hash,
            final_snapshot_hash=canonical_sha256(evidence.final_snapshot),
            open_position_hashes=tuple(
                canonical_sha256(value) for value in evidence.final_snapshot.positions
            ),
            working_order_stream_hashes=tuple(
                stream.stream_hash for stream, _ in working
            ),
            pending_settlement_ids=tuple(
                value.obligation.settlement_obligation_id.value
                for value in evidence.settlement_state.pending_obligations
            ),
            pending_fee_basis_hashes=tuple(
                value.basis_hash for value in pending_fee_refs
            ),
        )
        spec = closeout_policy.spec()
        if (
            not isinstance(spec, SimulationPortSpec)
            or spec.component_ref.port_type is not SimulationPortType.CLOSEOUT_POLICY
        ):
            return self._terminate(
                evidence,
                EngineTerminationCode.CLOSEOUT_OUTCOME_MISMATCH,
                ("closeout_policy_spec",),
            )
        outcome = closeout_policy.resolve_closeout(request)
        if not isinstance(outcome, SimulationPortOutcome):
            return self._terminate(
                evidence,
                EngineTerminationCode.CLOSEOUT_OUTCOME_MISMATCH,
                ("closeout_policy_outcome",),
            )
        outcome_hash = canonical_sha256(outcome)
        if (
            outcome.component_ref != spec.component_ref
            or outcome.input_hash != canonical_sha256(request)
        ):
            return self._terminate(
                evidence,
                EngineTerminationCode.CLOSEOUT_OUTCOME_MISMATCH,
                (spec.component_ref.component_key,),
                (outcome_hash,),
                outcome_hash,
            )
        if outcome.failure is not None:
            if not isinstance(outcome.failure, RunEndCloseoutFailure):
                return self._terminate(
                    evidence,
                    EngineTerminationCode.CLOSEOUT_OUTCOME_MISMATCH,
                    (spec.component_ref.component_key,),
                    (outcome_hash,),
                    outcome_hash,
                )
            return self._terminate(
                evidence,
                EngineTerminationCode.CLOSEOUT_POLICY_FAILURE,
                (outcome.failure.subject_key,),
                (outcome.failure.failure_hash,),
                outcome_hash,
            )
        decision = outcome.result
        if not isinstance(decision, RunEndCloseoutDecision):
            return self._terminate(
                evidence,
                EngineTerminationCode.CLOSEOUT_OUTCOME_MISMATCH,
                (spec.component_ref.component_key,),
                (outcome_hash,),
                outcome_hash,
            )
        if decision.completed_at != evidence.timeline_window.end_exclusive:
            return self._terminate(
                evidence,
                EngineTerminationCode.CLOSEOUT_OUTCOME_MISMATCH,
                (spec.component_ref.component_key,),
                (decision.decision_hash,),
                outcome_hash,
            )
        if decision.mode is RunEndCloseoutMode.LIQUIDATE_BEFORE_END:
            incomplete_subjects = []
            if evidence.final_snapshot.positions:
                incomplete_subjects.append("open_positions")
            if working:
                incomplete_subjects.append("working_orders")
            if evidence.reservation_state.active_reservations:
                incomplete_subjects.append("active_reservations")
            if evidence.pending_fee_assessments:
                incomplete_subjects.append("pending_fee_assessments")
            if decision.status is not RunEndCloseoutStatus.LIQUIDATION_COMPLETED:
                incomplete_subjects.append("closeout_status")
            if incomplete_subjects:
                return self._terminate(
                    evidence,
                    EngineTerminationCode.LIQUIDATION_INCOMPLETE,
                    tuple(incomplete_subjects),
                    (decision.decision_hash,),
                    outcome_hash,
                )
        elif decision.status is not RunEndCloseoutStatus.POSITIONS_PRESERVED:
            return self._terminate(
                evidence,
                EngineTerminationCode.CLOSEOUT_OUTCOME_MISMATCH,
                ("mark_to_market_status",),
                (decision.decision_hash,),
                outcome_hash,
            )

        report = RunEndReport(
            account_id=evidence.final_snapshot.account_id,
            trading_end_exclusive=evidence.timeline_window.end_exclusive,
            run_end_evidence_hash=evidence.evidence_hash,
            timeline_cursor_hash=evidence.timeline_cursor.cursor_hash,
            final_snapshot_hash=canonical_sha256(evidence.final_snapshot),
            journal_state_hash=evidence.final_snapshot.journal_state_hash,
            reservation_state_hash=evidence.reservation_state.state_hash,
            settlement_state_hash=evidence.settlement_state.state_hash,
            terminated_orders=terminations,
            released_reservations=releases,
            open_positions=tuple(
                sorted(evidence.final_snapshot.positions, key=canonical_bytes)
            ),
            pending_settlements=evidence.settlement_state.pending_obligations,
            pending_fee_assessments=pending_fee_refs,
            last_valuation_mark_ids=tuple(
                value.mark_id for value in evidence.final_snapshot.valuation_marks
            ),
            closeout_component_ref=outcome.component_ref,
            closeout_outcome_hash=outcome_hash,
            closeout_mode=decision.mode,
            closeout_status=decision.status,
        )
        return RunEndOutcome(evidence.evidence_hash, report=report)

    def _validate_boundary(self, evidence: RunEndEvidence) -> RunEndOutcome | None:
        window = evidence.timeline_window
        cursor = evidence.timeline_cursor
        if not cursor.window_complete:
            return self._terminate(
                evidence,
                EngineTerminationCode.TIMELINE_INCOMPLETE,
                (cursor.timeline_id,),
                (cursor.cursor_hash,),
            )
        if cursor.window_hash != window.window_hash:
            return self._terminate(
                evidence,
                EngineTerminationCode.EVIDENCE_MISMATCH,
                ("timeline_window",),
                (cursor.window_hash, window.window_hash),
            )
        boundary = window.end_exclusive
        if evidence.final_snapshot.timestamp != boundary:
            return self._terminate(
                evidence,
                EngineTerminationCode.EVIDENCE_MISMATCH,
                ("final_snapshot_timestamp",),
                (canonical_sha256(evidence.final_snapshot),),
            )
        if any(value.observed_at >= boundary for value in evidence.final_snapshot.valuation_marks):
            return self._terminate(
                evidence,
                EngineTerminationCode.BOUNDARY_VIOLATION,
                tuple(value.mark_id for value in evidence.final_snapshot.valuation_marks if value.observed_at >= boundary),
            )
        for stream in evidence.order_streams:
            if stream.order.created_at.instant >= boundary or any(
                record.event.occurred_at.instant >= boundary for record in stream.records
            ):
                return self._terminate(
                    evidence,
                    EngineTerminationCode.BOUNDARY_VIOLATION,
                    (stream.order.order_id.value,),
                    (stream.stream_hash,),
                )
        future_settlements = tuple(
            value.obligation.settlement_obligation_id.value
            for value in (
                evidence.settlement_state.pending_obligations
                + evidence.settlement_state.applied_obligations
            )
            if value.obligation.trade_time >= boundary
            or (
                value in evidence.settlement_state.applied_obligations
                and value.obligation.settlement_time >= boundary
            )
        )
        if future_settlements:
            return self._terminate(
                evidence,
                EngineTerminationCode.BOUNDARY_VIOLATION,
                future_settlements,
            )
        future_fees = tuple(
            value.basis_hash
            for value in evidence.pending_fee_assessments
            if value.closed_at > boundary
        )
        if future_fees:
            return self._terminate(
                evidence,
                EngineTerminationCode.BOUNDARY_VIOLATION,
                future_fees,
            )
        return None

    @staticmethod
    def _terminate(
        evidence: RunEndEvidence,
        code: EngineTerminationCode,
        subject_keys: tuple[str, ...],
        detail_hashes: tuple[str, ...] = (),
        closeout_outcome_hash: str | None = None,
    ) -> RunEndOutcome:
        return RunEndOutcome(
            evidence.evidence_hash,
            termination=EngineTermination(
                code=code,
                trading_end_exclusive=evidence.timeline_window.end_exclusive,
                run_end_evidence_hash=evidence.evidence_hash,
                subject_keys=subject_keys,
                detail_hashes=detail_hashes,
                closeout_outcome_hash=closeout_outcome_hash,
            ),
        )
