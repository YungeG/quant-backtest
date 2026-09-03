from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import pytest
from crypto_quant_bundle_builder.binance_usdm_koru_tradifi_source_projection_v2 import (
    build_binance_usdm_koru_tradifi_source_projection_v2,
    create_binance_usdm_koru_tradifi_source_projection_authority_v1,
    open_binance_usdm_koru_tradifi_source_projection_authority_v1,
    serialize_binance_usdm_koru_tradifi_source_projection_authority_v1,
)
from crypto_quant_domain import ArtifactEnvelope, canonical_bytes

from tests.bundle_builder.providers.binance_usdm import (
    test_koru_tradifi_source_projection_v1 as v1_fixture,
)
from tests.bundle_builder.providers.binance_usdm.test_koru_tradifi_source_projection_v2 import (
    _from_v1_request,
)


def _result():
    trade = v1_fixture.aggregate_fixture.DAY_START_MS + 22 * 60 * 60 * 1000
    outcome = build_binance_usdm_koru_tradifi_source_projection_v2(
        _from_v1_request(v1_fixture._request(((trade, "12.340"),)))
    )
    assert outcome.result is not None
    return outcome.result


def test_authority_round_trip_rebuilds_the_exact_typed_source_projection() -> None:
    result = _result()
    source_bytes = canonical_bytes(result)

    envelope, ref = create_binance_usdm_koru_tradifi_source_projection_authority_v1(
        result
    )
    rebuilt = open_binance_usdm_koru_tradifi_source_projection_authority_v1(
        canonical_bytes(envelope)
    )

    assert type(rebuilt) is type(result)
    assert canonical_bytes(rebuilt) == source_bytes
    assert ref.content_hash == envelope.content_hash
    assert ref.content_hash != result.fragment_digest


def _model_field(node: object, type_name: str, field_name: str) -> dict[str, object]:
    if type(node) is dict:
        if node.get("kind") == "model" and node.get("type", "").endswith(type_name):
            for field in node["fields"]:
                if field[0] == field_name:
                    return field[1]
        for value in node.values():
            try:
                return _model_field(value, type_name, field_name)
            except LookupError:
                pass
    elif type(node) is list:
        for value in node:
            try:
                return _model_field(value, type_name, field_name)
            except LookupError:
                pass
    raise LookupError(f"{type_name}.{field_name}")


def _tampered_bytes(
    envelope: ArtifactEnvelope,
    mutate: Callable[[dict[str, Any]], None],
    *,
    rehash: bool = True,
) -> bytes:
    body: dict[str, Any] = json.loads(canonical_bytes(envelope))
    mutate(body)
    if not rehash:
        return canonical_bytes(body)
    return canonical_bytes(
        ArtifactEnvelope.create(
            body["artifact_type"], body["schema_version"], body["payload"]
        )
    )


def test_authority_rejects_tampered_scope_events_manifests_and_identity() -> None:
    envelope, _ = create_binance_usdm_koru_tradifi_source_projection_authority_v1(
        _result()
    )

    def scope(body: dict[str, Any]) -> None:
        body["payload"]["discovery_scope"]["timeline_window_start"][
            "epoch_nanoseconds"
        ] += 1

    def event(body: dict[str, Any]) -> None:
        _model_field(
            body["payload"]["source_projection"], "MarketEvent", "event_id"
        )["value"] = "tampered-event"

    def manifest(body: dict[str, Any]) -> None:
        _model_field(
            body["payload"]["source_projection"],
            "MarketStreamManifest",
            "content_hash",
        )["value"] = "sha256:" + "0" * 64

    def request(body: dict[str, Any]) -> None:
        _model_field(
            body["payload"]["source_projection"],
            "BinanceUsdmKoruTradifiSourceProjectionRequestV2",
            "instrument_catalog_hash",
        )["value"] = "sha256:" + "0" * 64

    def authority_ref(body: dict[str, Any]) -> None:
        _model_field(
            body["payload"]["source_projection"], "ArtifactRef", "content_hash"
        )["value"] = "sha256:" + "0" * 64

    def fragment_hash(body: dict[str, Any]) -> None:
        body["payload"]["source_fragment_digest"] = "sha256:" + "0" * 64

    def builder_schema(body: dict[str, Any]) -> None:
        body["payload"]["builder"]["source_projection_schema_version"] = 3

    def field_order(body: dict[str, Any]) -> None:
        body["payload"]["source_projection"]["fields"].reverse()

    def artifact_hash(body: dict[str, Any]) -> None:
        body["content_hash"] = "sha256:" + "0" * 64

    for mutate, rehash in (
        (scope, True),
        (event, True),
        (manifest, True),
        (request, True),
        (authority_ref, True),
        (fragment_hash, True),
        (builder_schema, True),
        (field_order, True),
        (artifact_hash, False),
    ):
        with pytest.raises(ValueError):
            open_binance_usdm_koru_tradifi_source_projection_authority_v1(
                _tampered_bytes(envelope, mutate, rehash=rehash)
            )


def test_authority_serialization_does_not_change_source_projection_bytes() -> None:
    result = _result()
    source_bytes = canonical_bytes(result)

    serialized = serialize_binance_usdm_koru_tradifi_source_projection_authority_v1(
        result
    )

    assert canonical_bytes(result) == source_bytes
    assert canonical_bytes(
        open_binance_usdm_koru_tradifi_source_projection_authority_v1(serialized)
    ) == source_bytes
