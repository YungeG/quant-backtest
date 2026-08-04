"""Framework-independent trading domain contracts."""

from .canonical import (
    CanonicalEnvelope,
    CanonicalSchema,
    CanonicalizationError,
    canonical_bytes,
    canonical_sha256,
)
from .identity import (
    DomainId,
    DomainIdKind,
    IdentityManifest,
    IdentityNamespace,
    derive_domain_id,
)
from .instruments import (
    CurrencyId,
    InstrumentCatalog,
    InstrumentDefinition,
    InstrumentId,
    InstrumentType,
    SymbolInterval,
    SymbolTimeline,
    VenueId,
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
    "CanonicalEnvelope",
    "CanonicalSchema",
    "CanonicalizationError",
    "DomainId",
    "DomainIdKind",
    "CurrencyId",
    "ExposureFraction",
    "InstrumentCatalog",
    "InstrumentDefinition",
    "InstrumentId",
    "InstrumentType",
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
    "SymbolInterval",
    "SymbolTimeline",
    "VenueId",
    "canonical_bytes",
    "canonical_sha256",
    "derive_domain_id",
    "resolve_local_datetime",
]
