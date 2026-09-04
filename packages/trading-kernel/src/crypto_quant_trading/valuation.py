"""Deterministic point-in-time reporting-currency path resolution."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Any

from crypto_quant_domain import (
    CurrencyId,
    PricePurpose,
    ProfileComponentFailure,
    UtcInstant,
    canonical_sha256,
)

from .marks import ResolvedMark
from .ports import (
    CurrencyValuationPolicy,
    ProfileComponentRef,
    ProfilePortOutcome,
    ProfilePortType,
)


_SHA256_PATTERN = re.compile(r"sha256:[0-9a-f]{64}\Z")


def _require_hash(name: str, value: str) -> None:
    if type(value) is not str or _SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{name} must be a canonical sha256 identity")


def _validate_graph_context(
    valuation_at: UtcInstant,
    price_purpose: PricePurpose,
) -> None:
    if not isinstance(valuation_at, UtcInstant):
        raise TypeError("valuation_at must be UtcInstant")
    if not isinstance(price_purpose, PricePurpose):
        raise TypeError("price_purpose must be PricePurpose")


def _validate_currency_context(
    source_currency_id: CurrencyId,
    reporting_currency_id: CurrencyId,
    valuation_at: UtcInstant,
    price_purpose: PricePurpose,
) -> None:
    if not isinstance(source_currency_id, CurrencyId):
        raise TypeError("source_currency_id must be CurrencyId")
    if not isinstance(reporting_currency_id, CurrencyId):
        raise TypeError("reporting_currency_id must be CurrencyId")
    _validate_graph_context(valuation_at, price_purpose)


@dataclass(frozen=True, slots=True)
class CurrencyValuationEdge:
    """One supplied directed currency relation backed by a resolved mark."""

    source_currency_id: CurrencyId
    resolved_mark: ResolvedMark

    def __post_init__(self) -> None:
        if not isinstance(self.source_currency_id, CurrencyId):
            raise TypeError("source_currency_id must be CurrencyId")
        if not isinstance(self.resolved_mark, ResolvedMark):
            raise TypeError("resolved_mark must be ResolvedMark")
        if self.source_currency_id == self.target_currency_id:
            raise ValueError("valuation edge must connect different currencies")
        if self.resolved_mark.price.units <= 0:
            raise ValueError("valuation edge price must be positive")

    @property
    def target_currency_id(self) -> CurrencyId:
        return self.resolved_mark.quote_currency_id

    @property
    def price_purpose(self) -> PricePurpose:
        return self.resolved_mark.price_purpose

    @property
    def valuation_at(self) -> UtcInstant:
        return self.resolved_mark.resolved_at

    @property
    def edge_id(self) -> str:
        return canonical_sha256(self._canonical_body())

    def _canonical_body(self) -> dict[str, object]:
        return {
            "source_currency_id": self.source_currency_id,
            "target_currency_id": self.target_currency_id,
            "resolved_mark": self.resolved_mark,
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "currency_valuation_edge",
            "edge_id": self.edge_id,
            **self._canonical_body(),
        }


@dataclass(frozen=True, slots=True)
class CurrencyValuationPath:
    """An explicit simple directed path, including the zero-edge identity path."""

    source_currency_id: CurrencyId
    reporting_currency_id: CurrencyId
    valuation_at: UtcInstant
    price_purpose: PricePurpose
    edges: tuple[CurrencyValuationEdge, ...]

    def __post_init__(self) -> None:
        _validate_currency_context(
            self.source_currency_id,
            self.reporting_currency_id,
            self.valuation_at,
            self.price_purpose,
        )
        if type(self.edges) is not tuple or not all(
            isinstance(edge, CurrencyValuationEdge) for edge in self.edges
        ):
            raise TypeError("edges must be a tuple of CurrencyValuationEdge")

        if not self.edges:
            if self.source_currency_id != self.reporting_currency_id:
                raise ValueError("only an identity path may have zero edges")
            return
        if self.source_currency_id == self.reporting_currency_id:
            raise ValueError("identity path must have zero edges")
        if self.edges[0].source_currency_id != self.source_currency_id:
            raise ValueError("path first edge must start at source currency")
        if self.edges[-1].target_currency_id != self.reporting_currency_id:
            raise ValueError("path last edge must end at reporting currency")

        visited = {self.source_currency_id}
        expected_source = self.source_currency_id
        for edge in self.edges:
            if edge.source_currency_id != expected_source:
                raise ValueError("valuation path edges must be contiguous")
            if edge.valuation_at != self.valuation_at:
                raise ValueError("valuation path edges must share valuation_at")
            if edge.price_purpose is not self.price_purpose:
                raise ValueError("valuation path edges must share price_purpose")
            if edge.target_currency_id in visited:
                raise ValueError("valuation path cannot repeat a currency")
            visited.add(edge.target_currency_id)
            expected_source = edge.target_currency_id

    @property
    def is_identity(self) -> bool:
        return not self.edges

    @property
    def path_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def _canonical_body(self) -> dict[str, object]:
        return {
            "source_currency_id": self.source_currency_id,
            "reporting_currency_id": self.reporting_currency_id,
            "valuation_at": self.valuation_at,
            "price_purpose": self.price_purpose.value,
            "edges": self.edges,
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "currency_valuation_path",
            "path_hash": self.path_hash,
            "is_identity": self.is_identity,
            **self._canonical_body(),
        }


@dataclass(frozen=True, slots=True)
class CurrencyValuationPathRequest:
    """Canonical multi-path request supplied to CurrencyValuationPolicy."""

    graph_hash: str
    source_currency_id: CurrencyId
    reporting_currency_id: CurrencyId
    valuation_at: UtcInstant
    price_purpose: PricePurpose
    candidate_paths: tuple[CurrencyValuationPath, ...]

    def __post_init__(self) -> None:
        _require_hash("graph_hash", self.graph_hash)
        _validate_currency_context(
            self.source_currency_id,
            self.reporting_currency_id,
            self.valuation_at,
            self.price_purpose,
        )
        if type(self.candidate_paths) is not tuple or not self.candidate_paths:
            raise ValueError("candidate_paths must be a non-empty tuple")
        if not all(
            isinstance(path, CurrencyValuationPath) for path in self.candidate_paths
        ):
            raise TypeError("candidate_paths must contain CurrencyValuationPath")
        ordered = tuple(sorted(self.candidate_paths, key=lambda path: path.path_hash))
        if len({path.path_hash for path in ordered}) != len(ordered):
            raise ValueError("candidate_paths cannot contain duplicates")
        for path in ordered:
            if (
                path.source_currency_id != self.source_currency_id
                or path.reporting_currency_id != self.reporting_currency_id
                or path.valuation_at != self.valuation_at
                or path.price_purpose is not self.price_purpose
            ):
                raise ValueError("candidate path does not match request")
        object.__setattr__(self, "candidate_paths", ordered)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "currency_valuation_path_request",
            "graph_hash": self.graph_hash,
            "source_currency_id": self.source_currency_id,
            "reporting_currency_id": self.reporting_currency_id,
            "valuation_at": self.valuation_at,
            "price_purpose": self.price_purpose.value,
            "candidate_paths": self.candidate_paths,
        }


@dataclass(frozen=True, slots=True)
class CurrencyValuationPathSelection:
    """A policy's exact choice from the candidate path set."""

    selected_path_hash: str

    def __post_init__(self) -> None:
        _require_hash("selected_path_hash", self.selected_path_hash)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "currency_valuation_path_selection",
            "selected_path_hash": self.selected_path_hash,
        }


@dataclass(frozen=True, slots=True)
class CurrencyValuationResolution:
    """The one path selected for a point-in-time currency relation."""

    path: CurrencyValuationPath
    policy_request: CurrencyValuationPathRequest | None = None
    policy_outcome: ProfilePortOutcome[
        CurrencyValuationPathSelection, ProfileComponentFailure
    ] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.path, CurrencyValuationPath):
            raise TypeError("path must be CurrencyValuationPath")
        if (self.policy_request is None) != (self.policy_outcome is None):
            raise ValueError("policy request and outcome must be present together")
        if self.policy_request is None:
            return
        if not isinstance(self.policy_request, CurrencyValuationPathRequest):
            raise TypeError("policy_request must be CurrencyValuationPathRequest")
        if not isinstance(self.policy_outcome, ProfilePortOutcome):
            raise TypeError("policy_outcome must be ProfilePortOutcome")
        if self.path.path_hash not in {
            candidate.path_hash for candidate in self.policy_request.candidate_paths
        }:
            raise ValueError("resolved path must belong to policy request")
        if (
            self.policy_outcome.component_ref.port_type
            is not ProfilePortType.CURRENCY_VALUATION_POLICY
        ):
            raise ValueError("policy_outcome must come from CurrencyValuationPolicy")
        if self.policy_outcome.input_hash != canonical_sha256(self.policy_request):
            raise ValueError("policy_outcome input hash must match policy_request")
        if not isinstance(
            self.policy_outcome.result, CurrencyValuationPathSelection
        ) or self.policy_outcome.failure is not None:
            raise ValueError("resolution policy_outcome must contain a selection")
        if self.policy_outcome.result.selected_path_hash != self.path.path_hash:
            raise ValueError("policy selection must match resolved path")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "currency_valuation_resolution",
            "path": self.path,
            "policy_request": self.policy_request,
            "policy_outcome": self.policy_outcome,
        }


class CurrencyValuationFailureCode(str, Enum):
    MISSING_PATH = "missing_path"
    NON_UNIQUE_PATH = "non_unique_path"
    POLICY_REJECTED = "policy_rejected"
    INVALID_POLICY_OUTCOME = "invalid_policy_outcome"


@dataclass(frozen=True, slots=True)
class CurrencyValuationFailure:
    """Structured fail-closed path-resolution evidence."""

    code: CurrencyValuationFailureCode
    graph_hash: str
    source_currency_id: CurrencyId
    reporting_currency_id: CurrencyId
    valuation_at: UtcInstant
    price_purpose: PricePurpose
    candidate_path_hashes: tuple[str, ...]
    policy_request: CurrencyValuationPathRequest | None = None
    policy_outcome: ProfilePortOutcome[Any, Any] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.code, CurrencyValuationFailureCode):
            raise TypeError("code must be CurrencyValuationFailureCode")
        _require_hash("graph_hash", self.graph_hash)
        _validate_currency_context(
            self.source_currency_id,
            self.reporting_currency_id,
            self.valuation_at,
            self.price_purpose,
        )
        if type(self.candidate_path_hashes) is not tuple:
            raise TypeError("candidate_path_hashes must be a tuple")
        for value in self.candidate_path_hashes:
            _require_hash("candidate path hash", value)
        ordered = tuple(sorted(self.candidate_path_hashes))
        if len(set(ordered)) != len(ordered):
            raise ValueError("candidate_path_hashes cannot contain duplicates")
        object.__setattr__(self, "candidate_path_hashes", ordered)
        if self.policy_request is not None and not isinstance(
            self.policy_request, CurrencyValuationPathRequest
        ):
            raise TypeError("policy_request must be CurrencyValuationPathRequest or None")
        if self.policy_outcome is not None and not isinstance(
            self.policy_outcome, ProfilePortOutcome
        ):
            raise TypeError("policy_outcome must be ProfilePortOutcome or None")
        if self.code in (
            CurrencyValuationFailureCode.POLICY_REJECTED,
            CurrencyValuationFailureCode.INVALID_POLICY_OUTCOME,
        ) and self.policy_request is None:
            raise ValueError("policy failure requires policy_request")
        if self.code is CurrencyValuationFailureCode.POLICY_REJECTED:
            if self.policy_outcome is None or not isinstance(
                self.policy_outcome.failure, ProfileComponentFailure
            ):
                raise ValueError("policy_rejected requires a typed policy failure")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "currency_valuation_failure",
            "code": self.code.value,
            "graph_hash": self.graph_hash,
            "source_currency_id": self.source_currency_id,
            "reporting_currency_id": self.reporting_currency_id,
            "valuation_at": self.valuation_at,
            "price_purpose": self.price_purpose.value,
            "candidate_path_hashes": self.candidate_path_hashes,
            "policy_request": self.policy_request,
            "policy_outcome": self.policy_outcome,
        }


@dataclass(frozen=True, slots=True)
class CurrencyValuationOutcome:
    """Exactly one successful resolution or structured failure."""

    resolution: CurrencyValuationResolution | None
    failure: CurrencyValuationFailure | None

    def __post_init__(self) -> None:
        if (self.resolution is None) == (self.failure is None):
            raise ValueError(
                "CurrencyValuationOutcome requires exactly one resolution or failure"
            )
        if self.resolution is not None and not isinstance(
            self.resolution, CurrencyValuationResolution
        ):
            raise TypeError("resolution must be CurrencyValuationResolution")
        if self.failure is not None and not isinstance(
            self.failure, CurrencyValuationFailure
        ):
            raise TypeError("failure must be CurrencyValuationFailure")

    def to_canonical_dict(self) -> dict[str, object]:
        if self.resolution is not None:
            return {
                "type": "currency_valuation_outcome",
                "status": "resolved",
                "resolution": self.resolution,
            }
        return {
            "type": "currency_valuation_outcome",
            "status": "failed",
            "failure": self.failure,
        }


@dataclass(frozen=True, slots=True)
class CurrencyValuationGraph:
    """Immutable graph of supplied point-in-time currency valuation edges."""

    valuation_at: UtcInstant
    price_purpose: PricePurpose
    edges: tuple[CurrencyValuationEdge, ...]

    def __post_init__(self) -> None:
        _validate_graph_context(self.valuation_at, self.price_purpose)
        if type(self.edges) is not tuple or not all(
            isinstance(edge, CurrencyValuationEdge) for edge in self.edges
        ):
            raise TypeError("edges must be a tuple of CurrencyValuationEdge")
        ordered = tuple(sorted(self.edges, key=lambda edge: edge.edge_id))
        if len({edge.edge_id for edge in ordered}) != len(ordered):
            raise ValueError("currency valuation graph cannot contain duplicate edges")
        for edge in ordered:
            if edge.valuation_at != self.valuation_at:
                raise ValueError("all valuation edges must match graph valuation_at")
            if edge.price_purpose is not self.price_purpose:
                raise ValueError("all valuation edges must match graph price_purpose")
        object.__setattr__(self, "edges", ordered)

    @property
    def graph_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "currency_valuation_graph",
            "valuation_at": self.valuation_at,
            "price_purpose": self.price_purpose.value,
            "edges": self.edges,
        }

    def paths(
        self,
        source_currency_id: CurrencyId,
        reporting_currency_id: CurrencyId,
    ) -> tuple[CurrencyValuationPath, ...]:
        if not isinstance(source_currency_id, CurrencyId):
            raise TypeError("source_currency_id must be CurrencyId")
        if not isinstance(reporting_currency_id, CurrencyId):
            raise TypeError("reporting_currency_id must be CurrencyId")
        if source_currency_id == reporting_currency_id:
            return (
                CurrencyValuationPath(
                    source_currency_id=source_currency_id,
                    reporting_currency_id=reporting_currency_id,
                    valuation_at=self.valuation_at,
                    price_purpose=self.price_purpose,
                    edges=(),
                ),
            )

        adjacency: dict[CurrencyId, tuple[CurrencyValuationEdge, ...]] = {}
        for edge in self.edges:
            adjacency[edge.source_currency_id] = tuple(
                sorted(
                    (*adjacency.get(edge.source_currency_id, ()), edge),
                    key=lambda value: value.edge_id,
                )
            )

        found: list[CurrencyValuationPath] = []

        def visit(
            current: CurrencyId,
            visited: frozenset[CurrencyId],
            path_edges: tuple[CurrencyValuationEdge, ...],
        ) -> None:
            for candidate in adjacency.get(current, ()):
                target = candidate.target_currency_id
                if target in visited:
                    continue
                next_edges = (*path_edges, candidate)
                if target == reporting_currency_id:
                    found.append(
                        CurrencyValuationPath(
                            source_currency_id=source_currency_id,
                            reporting_currency_id=reporting_currency_id,
                            valuation_at=self.valuation_at,
                            price_purpose=self.price_purpose,
                            edges=next_edges,
                        )
                    )
                    continue
                visit(target, visited | {target}, next_edges)

        visit(source_currency_id, frozenset({source_currency_id}), ())
        return tuple(sorted(found, key=lambda path: path.path_hash))

    def resolve(
        self,
        source_currency_id: CurrencyId,
        reporting_currency_id: CurrencyId,
        *,
        policy: CurrencyValuationPolicy[
            CurrencyValuationPathRequest,
            CurrencyValuationPathSelection,
            ProfileComponentFailure,
        ]
        | None = None,
    ) -> CurrencyValuationOutcome:
        candidate_paths = self.paths(source_currency_id, reporting_currency_id)
        if not candidate_paths:
            return self._failure(
                CurrencyValuationFailureCode.MISSING_PATH,
                source_currency_id,
                reporting_currency_id,
                candidate_paths,
            )
        if len(candidate_paths) == 1:
            return CurrencyValuationOutcome(
                resolution=CurrencyValuationResolution(candidate_paths[0]),
                failure=None,
            )
        if policy is None:
            return self._failure(
                CurrencyValuationFailureCode.NON_UNIQUE_PATH,
                source_currency_id,
                reporting_currency_id,
                candidate_paths,
            )

        request = CurrencyValuationPathRequest(
            graph_hash=self.graph_hash,
            source_currency_id=source_currency_id,
            reporting_currency_id=reporting_currency_id,
            valuation_at=self.valuation_at,
            price_purpose=self.price_purpose,
            candidate_paths=candidate_paths,
        )
        component_ref = getattr(policy, "component_ref", None)
        if (
            not isinstance(component_ref, ProfileComponentRef)
            or component_ref.port_type
            is not ProfilePortType.CURRENCY_VALUATION_POLICY
        ):
            return self._failure(
                CurrencyValuationFailureCode.INVALID_POLICY_OUTCOME,
                source_currency_id,
                reporting_currency_id,
                candidate_paths,
                policy_request=request,
            )

        policy_outcome = policy.select_valuation_path(request)
        if not isinstance(policy_outcome, ProfilePortOutcome):
            return self._failure(
                CurrencyValuationFailureCode.INVALID_POLICY_OUTCOME,
                source_currency_id,
                reporting_currency_id,
                candidate_paths,
                policy_request=request,
            )
        if (
            policy_outcome.component_ref != component_ref
            or policy_outcome.input_hash != canonical_sha256(request)
        ):
            return self._failure(
                CurrencyValuationFailureCode.INVALID_POLICY_OUTCOME,
                source_currency_id,
                reporting_currency_id,
                candidate_paths,
                policy_request=request,
                policy_outcome=policy_outcome,
            )
        if policy_outcome.failure is not None:
            if not isinstance(policy_outcome.failure, ProfileComponentFailure):
                return self._failure(
                    CurrencyValuationFailureCode.INVALID_POLICY_OUTCOME,
                    source_currency_id,
                    reporting_currency_id,
                    candidate_paths,
                    policy_request=request,
                    policy_outcome=policy_outcome,
                )
            return self._failure(
                CurrencyValuationFailureCode.POLICY_REJECTED,
                source_currency_id,
                reporting_currency_id,
                candidate_paths,
                policy_request=request,
                policy_outcome=policy_outcome,
            )
        if not isinstance(policy_outcome.result, CurrencyValuationPathSelection):
            return self._failure(
                CurrencyValuationFailureCode.INVALID_POLICY_OUTCOME,
                source_currency_id,
                reporting_currency_id,
                candidate_paths,
                policy_request=request,
                policy_outcome=policy_outcome,
            )
        selected = {
            path.path_hash: path for path in candidate_paths
        }.get(policy_outcome.result.selected_path_hash)
        if selected is None:
            return self._failure(
                CurrencyValuationFailureCode.INVALID_POLICY_OUTCOME,
                source_currency_id,
                reporting_currency_id,
                candidate_paths,
                policy_request=request,
                policy_outcome=policy_outcome,
            )
        return CurrencyValuationOutcome(
            resolution=CurrencyValuationResolution(
                selected,
                policy_request=request,
                policy_outcome=policy_outcome,
            ),
            failure=None,
        )

    def _failure(
        self,
        code: CurrencyValuationFailureCode,
        source_currency_id: CurrencyId,
        reporting_currency_id: CurrencyId,
        candidate_paths: tuple[CurrencyValuationPath, ...],
        *,
        policy_request: CurrencyValuationPathRequest | None = None,
        policy_outcome: ProfilePortOutcome[Any, Any] | None = None,
    ) -> CurrencyValuationOutcome:
        return CurrencyValuationOutcome(
            resolution=None,
            failure=CurrencyValuationFailure(
                code=code,
                graph_hash=self.graph_hash,
                source_currency_id=source_currency_id,
                reporting_currency_id=reporting_currency_id,
                valuation_at=self.valuation_at,
                price_purpose=self.price_purpose,
                candidate_path_hashes=tuple(
                    path.path_hash for path in candidate_paths
                ),
                policy_request=policy_request,
                policy_outcome=policy_outcome,
            ),
        )
