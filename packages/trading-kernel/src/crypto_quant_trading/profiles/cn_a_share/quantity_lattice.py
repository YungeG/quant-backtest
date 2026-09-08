"""Mainland China cash-equity quantity lattice semantics."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import unicodedata

from crypto_quant_domain import (
    CurrencyId,
    InstrumentDefinition,
    InstrumentId,
    InstrumentType,
    Money,
    Scale,
    VenueId,
    canonical_sha256,
)
from crypto_quant_trading.ports import (
    ProfileComponentRef,
    ProfilePortOutcome,
    ProfilePortType,
)
from crypto_quant_trading.sizing import QuantityLattice


_COMPONENT_KEY = "equity.cn_a_share.cash.quantity-lattice.v1"
_ALGORITHM_KEY = "cn-a-share-cash-position-relative-lattice-v1"
_APPLICABILITY_KEY = "ordinary-rmb-a-share-cny-cash-v1"
_CNY = CurrencyId("CNY")
_SUPPORTED_VENUES = frozenset(("xshg", "xshe"))


class CnAShareQuantityLatticeFailureCode(Enum):
    UNSUPPORTED_VENUE = "unsupported_venue"
    UNSUPPORTED_INSTRUMENT = "unsupported_instrument"
    UNSUPPORTED_CURRENCY = "unsupported_currency"


def _canonical_text(name: str, value: object) -> str:
    if type(value) is not str:
        raise TypeError(f"{name} must be str")
    if (
        not value
        or value.strip() != value
        or unicodedata.normalize("NFC", value) != value
    ):
        raise ValueError(f"{name} must be nonempty canonical text")
    return value


def _lattice_policy_payload() -> dict[str, object]:
    return {
        "atomic_scale": 0,
        "step_units": 1,
        "buy_lot_units": 100,
        "sell_lot_units": 100,
        "min_quantity_units": 0,
        "min_notional_units": 0,
        "odd_lot_close_permitted": True,
        "whole_sell_residual_permitted": True,
    }


@dataclass(frozen=True, slots=True)
class CnAShareQuantityLatticeQuery:
    instrument: InstrumentDefinition

    def __post_init__(self) -> None:
        if not isinstance(self.instrument, InstrumentDefinition):
            raise TypeError("instrument must be InstrumentDefinition")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_quantity_lattice_query",
            "schema_version": 1,
            "instrument": self.instrument,
        }


@dataclass(frozen=True, slots=True)
class CnAShareQuantityLatticeResolution:
    venue_id: VenueId
    instrument_id: InstrumentId
    quantity_lattice: QuantityLattice

    def __post_init__(self) -> None:
        if not isinstance(self.venue_id, VenueId):
            raise TypeError("venue_id must be VenueId")
        if not isinstance(self.instrument_id, InstrumentId):
            raise TypeError("instrument_id must be InstrumentId")
        if not isinstance(self.quantity_lattice, QuantityLattice):
            raise TypeError("quantity_lattice must be QuantityLattice")
        if self.instrument_id.venue != self.venue_id:
            raise ValueError("instrument venue does not match resolution venue")
        if self.quantity_lattice.instrument_id != self.instrument_id:
            raise ValueError("quantity lattice instrument does not match resolution")
        lattice = self.quantity_lattice
        if (
            lattice.lattice_key != _COMPONENT_KEY
            or lattice.lattice_version != 1
            or lattice.atomic_scale != Scale(0)
            or lattice.step_units != 1
            or lattice.buy_lot_units != 100
            or lattice.sell_lot_units != 100
            or lattice.min_quantity_units != 0
            or lattice.min_notional.units != 0
            or lattice.min_notional.currency != str(_CNY)
            or not lattice.odd_lot_close_permitted
            or not lattice.whole_sell_residual_permitted
        ):
            raise ValueError("quantity lattice does not match A-share cash template")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_quantity_lattice_resolution",
            "schema_version": 1,
            "venue_id": self.venue_id,
            "instrument_id": self.instrument_id,
            "quantity_lattice": self.quantity_lattice,
        }


@dataclass(frozen=True, slots=True)
class CnAShareQuantityLatticeFailure:
    code: CnAShareQuantityLatticeFailureCode
    venue_id: VenueId
    instrument_id: InstrumentId
    subject_key: str

    def __post_init__(self) -> None:
        if not isinstance(self.code, CnAShareQuantityLatticeFailureCode):
            raise TypeError("code must be CnAShareQuantityLatticeFailureCode")
        if not isinstance(self.venue_id, VenueId):
            raise TypeError("venue_id must be VenueId")
        if not isinstance(self.instrument_id, InstrumentId):
            raise TypeError("instrument_id must be InstrumentId")
        _canonical_text("subject_key", self.subject_key)
        if self.instrument_id.venue != self.venue_id:
            raise ValueError("failure venue does not match Instrument")
        expected_subject = (
            f"venue:{self.venue_id.value}"
            if self.code is CnAShareQuantityLatticeFailureCode.UNSUPPORTED_VENUE
            else f"instrument:{self.instrument_id}"
        )
        if self.subject_key != expected_subject:
            raise ValueError("failure subject_key does not match failure code")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_quantity_lattice_failure",
            "schema_version": 1,
            "code": self.code.value,
            "venue_id": self.venue_id,
            "instrument_id": self.instrument_id,
            "subject_key": self.subject_key,
        }


@dataclass(frozen=True, slots=True)
class CnAShareCashQuantityLatticeModel:
    venue_id: VenueId
    notional_scale: Scale

    def __post_init__(self) -> None:
        if not isinstance(self.venue_id, VenueId):
            raise TypeError("venue_id must be VenueId")
        if self.venue_id.value not in _SUPPORTED_VENUES:
            raise ValueError("unsupported venue")
        if not isinstance(self.notional_scale, Scale):
            raise TypeError("notional_scale must be Scale")

    @property
    def component_ref(self) -> ProfileComponentRef:
        digest = canonical_sha256(
            {
                "type": "cn_a_share_cash_quantity_lattice_component",
                "schema_version": 1,
                "component_key": _COMPONENT_KEY,
                "component_version": 1,
                "algorithm_key": _ALGORITHM_KEY,
                "venue_id": self.venue_id,
                "applicability_key": _APPLICABILITY_KEY,
                "notional_scale": self.notional_scale.places,
                "lattice_policy": _lattice_policy_payload(),
            }
        )
        return ProfileComponentRef(
            port_type=ProfilePortType.INSTRUMENT_MODEL,
            component_key=_COMPONENT_KEY,
            component_version=1,
            component_digest=digest,
        )

    def resolve_instrument(
        self,
        request: CnAShareQuantityLatticeQuery,
        /,
    ) -> ProfilePortOutcome[
        CnAShareQuantityLatticeResolution,
        CnAShareQuantityLatticeFailure,
    ]:
        if not isinstance(request, CnAShareQuantityLatticeQuery):
            raise TypeError("request must be CnAShareQuantityLatticeQuery")
        instrument = request.instrument
        if instrument.instrument_id.venue != self.venue_id:
            return self._failure(
                request,
                CnAShareQuantityLatticeFailureCode.UNSUPPORTED_VENUE,
                f"venue:{instrument.instrument_id.venue.value}",
            )
        if instrument.instrument_type is not InstrumentType.EQUITY:
            return self._failure(
                request,
                CnAShareQuantityLatticeFailureCode.UNSUPPORTED_INSTRUMENT,
                f"instrument:{instrument.instrument_id}",
            )
        if (
            instrument.quote_currency != _CNY
            or instrument.settlement_currency != _CNY
        ):
            return self._failure(
                request,
                CnAShareQuantityLatticeFailureCode.UNSUPPORTED_CURRENCY,
                f"instrument:{instrument.instrument_id}",
            )
        lattice = QuantityLattice.create(
            instrument_id=instrument.instrument_id,
            lattice_key=_COMPONENT_KEY,
            lattice_version=1,
            atomic_scale=Scale(0),
            step_units=1,
            buy_lot_units=100,
            sell_lot_units=100,
            min_quantity_units=0,
            min_notional=Money(0, self.notional_scale, str(_CNY)),
            odd_lot_close_permitted=True,
            whole_sell_residual_permitted=True,
        )
        return ProfilePortOutcome.for_result(
            self.component_ref,
            request,
            CnAShareQuantityLatticeResolution(
                venue_id=self.venue_id,
                instrument_id=instrument.instrument_id,
                quantity_lattice=lattice,
            ),
        )

    def _failure(
        self,
        request: CnAShareQuantityLatticeQuery,
        code: CnAShareQuantityLatticeFailureCode,
        subject_key: str,
    ) -> ProfilePortOutcome[
        CnAShareQuantityLatticeResolution,
        CnAShareQuantityLatticeFailure,
    ]:
        instrument = request.instrument
        return ProfilePortOutcome.for_failure(
            self.component_ref,
            request,
            CnAShareQuantityLatticeFailure(
                code=code,
                venue_id=instrument.instrument_id.venue,
                instrument_id=instrument.instrument_id,
                subject_key=subject_key,
            ),
        )
