"""Framework-independent trading domain contracts."""

from .identity import (
    DomainId,
    DomainIdKind,
    IdentityManifest,
    IdentityNamespace,
    derive_domain_id,
)
from .numeric import (
    ExposureFraction,
    Money,
    Price,
    Quantity,
    QuantizationPolicy,
    Rate,
    RoundingPolicy,
    Scale,
)
from .time import (
    LocalTimeDisambiguation,
    SessionId,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    TradingDate,
    UtcInstant,
    resolve_local_datetime,
)

__version__ = "0.1.0"

__all__ = [
    "DomainId",
    "DomainIdKind",
    "ExposureFraction",
    "IdentityManifest",
    "IdentityNamespace",
    "LocalTimeDisambiguation",
    "Money",
    "Price",
    "Quantity",
    "QuantizationPolicy",
    "Rate",
    "RoundingPolicy",
    "Scale",
    "SessionId",
    "SimulationInstant",
    "SourceSequence",
    "TimelinePhase",
    "TradingDate",
    "UtcInstant",
    "derive_domain_id",
    "resolve_local_datetime",
]
