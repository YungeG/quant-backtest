from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import ClassVar, cast

from crypto_quant_domain import UtcInstant, canonical_bytes, canonical_sha256


def _text(name: str, value: object) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(f"{name} must be canonical non-empty text")
    canonical_bytes(value)
    return value


def _utc(name: str, value: object) -> UtcInstant:
    if type(value) is not UtcInstant:
        raise TypeError(f"{name} must be UtcInstant")
    return value


def _optional_utc(name: str, value: object) -> UtcInstant | None:
    if value is not None:
        return _utc(name, value)
    return None


def _optional_text(name: str, value: object) -> str | None:
    if value is not None:
        return _text(name, value)
    return None


def _optional_int(name: str, value: object) -> int | None:
    if value is not None and type(value) is not int:
        raise TypeError(f"{name} must be int or None")
    return value


def _mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        raise TypeError("value must be a canonical mapping")
    return cast(Mapping[str, object], value)


def _keys(value: Mapping[str, object], expected: set[str]) -> None:
    if set(value) != expected:
        raise ValueError("canonical mapping keys mismatch")


def _int(value: object) -> int:
    if type(value) is not int:
        raise TypeError("value must be an exact integer")
    return value


def _utc_from_mapping(value: object) -> UtcInstant:
    body = _mapping(value)
    _keys(body, {"type", "epoch_nanoseconds"})
    if body["type"] != "utc_instant":
        raise ValueError("UtcInstant type mismatch")
    return UtcInstant(_int(body["epoch_nanoseconds"]))


@dataclass(frozen=True, slots=True)
class G12BListingMembershipRevisionPayloadV1:
    type: ClassVar[str] = "g12b_listing_membership_revision"
    schema_version: ClassVar[int] = 1

    universe_key: str
    membership_key: str
    listed_at: UtcInstant
    delisted_at: UtcInstant | None
    member_from: UtcInstant
    member_until: UtcInstant | None

    def __post_init__(self) -> None:
        if type(self) is not G12BListingMembershipRevisionPayloadV1:
            raise TypeError("payload must be exact concrete type")
        _text("universe_key", self.universe_key)
        _text("membership_key", self.membership_key)
        _utc("listed_at", self.listed_at)
        _optional_utc("delisted_at", self.delisted_at)
        _utc("member_from", self.member_from)
        _optional_utc("member_until", self.member_until)

    def _canonical_body(self) -> dict[str, object]:
        return {
            "type": self.type,
            "schema_version": self.schema_version,
            "universe_key": self.universe_key,
            "membership_key": self.membership_key,
            "listed_at": self.listed_at.to_canonical_dict(),
            "delisted_at": (
                None
                if self.delisted_at is None
                else self.delisted_at.to_canonical_dict()
            ),
            "member_from": self.member_from.to_canonical_dict(),
            "member_until": (
                None
                if self.member_until is None
                else self.member_until.to_canonical_dict()
            ),
        }

    @property
    def payload_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._canonical_body(), "payload_hash": self.payload_hash}


class G12BCorporateActionStatusV1(str, Enum):
    FINAL_IMPLEMENTATION = "final_implementation"
    PLAN_ONLY = "plan_only"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class G12BCorporateActionLifecycleRevisionPayloadV1:
    type: ClassVar[str] = "g12b_corporate_action_lifecycle_revision"
    schema_version: ClassVar[int] = 1

    corporate_action_id: str
    status: G12BCorporateActionStatusV1
    calendar_id: str
    record_date: str | None
    ex_date: str | None
    payment_date: str | None
    listing_date: str | None
    cash_per_share_units: int | None
    cash_per_share_scale: int | None
    cash_currency: str | None
    bonus_rate_units: int | None
    bonus_rate_scale: int | None
    bonus_rate_basis: str | None
    capitalization_rate_units: int | None
    capitalization_rate_scale: int | None
    capitalization_rate_basis: str | None

    def __post_init__(self) -> None:
        if type(self) is not G12BCorporateActionLifecycleRevisionPayloadV1:
            raise TypeError("payload must be exact concrete type")
        _text("corporate_action_id", self.corporate_action_id)
        if type(self.status) is not G12BCorporateActionStatusV1:
            raise TypeError("status must be G12BCorporateActionStatusV1")
        _text("calendar_id", self.calendar_id)
        for name in ("record_date", "ex_date", "payment_date", "listing_date"):
            _optional_text(name, getattr(self, name))
        for name in (
            "cash_per_share_units",
            "cash_per_share_scale",
            "bonus_rate_units",
            "bonus_rate_scale",
            "capitalization_rate_units",
            "capitalization_rate_scale",
        ):
            _optional_int(name, getattr(self, name))
        for name in (
            "cash_currency",
            "bonus_rate_basis",
            "capitalization_rate_basis",
        ):
            _optional_text(name, getattr(self, name))

    def _canonical_body(self) -> dict[str, object]:
        return {
            "type": self.type,
            "schema_version": self.schema_version,
            "corporate_action_id": self.corporate_action_id,
            "status": self.status.value,
            "calendar_id": self.calendar_id,
            "record_date": self.record_date,
            "ex_date": self.ex_date,
            "payment_date": self.payment_date,
            "listing_date": self.listing_date,
            "cash_per_share_units": self.cash_per_share_units,
            "cash_per_share_scale": self.cash_per_share_scale,
            "cash_currency": self.cash_currency,
            "bonus_rate_units": self.bonus_rate_units,
            "bonus_rate_scale": self.bonus_rate_scale,
            "bonus_rate_basis": self.bonus_rate_basis,
            "capitalization_rate_units": self.capitalization_rate_units,
            "capitalization_rate_scale": self.capitalization_rate_scale,
            "capitalization_rate_basis": self.capitalization_rate_basis,
        }

    @property
    def payload_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._canonical_body(), "payload_hash": self.payload_hash}


def _reconstruct_listing_membership_revision_payload_v1(
    value: object,
) -> G12BListingMembershipRevisionPayloadV1:
    body = _mapping(value)
    _keys(
        body,
        {
            "type",
            "schema_version",
            "universe_key",
            "membership_key",
            "listed_at",
            "delisted_at",
            "member_from",
            "member_until",
            "payload_hash",
        },
    )
    if (
        body["type"] != G12BListingMembershipRevisionPayloadV1.type
        or body["schema_version"] != 1
    ):
        raise ValueError("listing payload identity mismatch")
    payload = G12BListingMembershipRevisionPayloadV1(
        universe_key=_text("universe_key", body["universe_key"]),
        membership_key=_text("membership_key", body["membership_key"]),
        listed_at=_utc_from_mapping(body["listed_at"]),
        delisted_at=(
            None
            if body["delisted_at"] is None
            else _utc_from_mapping(body["delisted_at"])
        ),
        member_from=_utc_from_mapping(body["member_from"]),
        member_until=(
            None
            if body["member_until"] is None
            else _utc_from_mapping(body["member_until"])
        ),
    )
    if (
        body["payload_hash"] != payload.payload_hash
        or dict(body) != payload.to_canonical_dict()
    ):
        raise ValueError("listing payload canonical reconstruction mismatch")
    return payload


def _reconstruct_corporate_action_lifecycle_revision_payload_v1(
    value: object,
) -> G12BCorporateActionLifecycleRevisionPayloadV1:
    body = _mapping(value)
    field_names = (
        "corporate_action_id",
        "status",
        "calendar_id",
        "record_date",
        "ex_date",
        "payment_date",
        "listing_date",
        "cash_per_share_units",
        "cash_per_share_scale",
        "cash_currency",
        "bonus_rate_units",
        "bonus_rate_scale",
        "bonus_rate_basis",
        "capitalization_rate_units",
        "capitalization_rate_scale",
        "capitalization_rate_basis",
    )
    _keys(body, {"type", "schema_version", *field_names, "payload_hash"})
    if (
        body["type"] != G12BCorporateActionLifecycleRevisionPayloadV1.type
        or body["schema_version"] != 1
    ):
        raise ValueError("action payload identity mismatch")
    payload = G12BCorporateActionLifecycleRevisionPayloadV1(
        corporate_action_id=_text("corporate_action_id", body["corporate_action_id"]),
        status=G12BCorporateActionStatusV1(_text("status", body["status"])),
        calendar_id=_text("calendar_id", body["calendar_id"]),
        record_date=_optional_text("record_date", body["record_date"]),
        ex_date=_optional_text("ex_date", body["ex_date"]),
        payment_date=_optional_text("payment_date", body["payment_date"]),
        listing_date=_optional_text("listing_date", body["listing_date"]),
        cash_per_share_units=_optional_int(
            "cash_per_share_units", body["cash_per_share_units"]
        ),
        cash_per_share_scale=_optional_int(
            "cash_per_share_scale", body["cash_per_share_scale"]
        ),
        cash_currency=_optional_text("cash_currency", body["cash_currency"]),
        bonus_rate_units=_optional_int("bonus_rate_units", body["bonus_rate_units"]),
        bonus_rate_scale=_optional_int("bonus_rate_scale", body["bonus_rate_scale"]),
        bonus_rate_basis=_optional_text("bonus_rate_basis", body["bonus_rate_basis"]),
        capitalization_rate_units=_optional_int(
            "capitalization_rate_units", body["capitalization_rate_units"]
        ),
        capitalization_rate_scale=_optional_int(
            "capitalization_rate_scale", body["capitalization_rate_scale"]
        ),
        capitalization_rate_basis=_optional_text(
            "capitalization_rate_basis", body["capitalization_rate_basis"]
        ),
    )
    if (
        body["payload_hash"] != payload.payload_hash
        or dict(body) != payload.to_canonical_dict()
    ):
        raise ValueError("action payload canonical reconstruction mismatch")
    return payload
