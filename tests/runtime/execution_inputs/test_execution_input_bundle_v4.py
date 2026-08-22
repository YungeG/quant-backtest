from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import crypto_quant_trading as trading
import pytest
from crypto_quant_backtest.composition import (
    _execution_case_semantic_spec_v3,
    _HydratedExecutionCaseInputs,
)
from crypto_quant_backtest.execution_inputs import (
    _EXECUTION_INPUT_CATALOG_V4,
    BacktestExecutionRequest,
    _DecodedExecutionInputBundleV3,
    _ExecutionInputsHydrationFailureCodeV3,
    _hydrate_execution_inputs_v4,
    _materialize_execution_input_bundle_v4,
    _read_execution_input_payload_v4,
    _read_execution_inputs_v4,
)
from crypto_quant_domain import (
    ArtifactEnvelope,
    ArtifactRef,
    CurrencyId,
    InstrumentCatalog,
    InstrumentDefinition,
    InstrumentId,
    InstrumentType,
    SymbolInterval,
    SymbolTimeline,
    UtcInstant,
    VenueId,
    canonical_bytes,
    canonical_sha256,
)

from tests.runtime.execution_inputs.test_multi_resolution_bundle_v3 import (
    _contract,
    _Reader,
    _resolved_for_spec,
)

_FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures/runtime/execution-input-bundle-v4/equity.json"
)


def _equity_contract():
    prepared, resolved, hydrated, _, _ = _contract()
    instrument_id = InstrumentId(VenueId("xshe"), "000001")
    cny = CurrencyId("CNY")
    catalog = InstrumentCatalog(
        (cny,),
        (
            InstrumentDefinition(
                instrument_id,
                InstrumentType.EQUITY,
                None,
                cny,
                cny,
            ),
        ),
        (
            SymbolTimeline(
                instrument_id,
                (
                    SymbolInterval("000001", UtcInstant(0), UtcInstant(1)),
                    SymbolInterval("000001.SZ", UtcInstant(1), None),
                ),
            ),
        ),
    )
    cycles = []
    for cycle in hydrated.execution_case_plan.decision_cycles:
        sizing_inputs = tuple(
            replace(
                sizing_input,
                instrument_id=instrument_id,
                mark=replace(
                    sizing_input.mark,
                    instrument_id=instrument_id,
                    quote_currency_id=cny,
                    price=replace(
                        sizing_input.mark.price,
                        instrument_id=str(instrument_id),
                        quote_currency=str(cny),
                    ),
                ),
                current_quantity=replace(
                    sizing_input.current_quantity,
                    instrument_id=str(instrument_id),
                ),
                lattice=trading.QuantityLattice.create(
                    instrument_id=instrument_id,
                    lattice_key=sizing_input.lattice.lattice_key,
                    lattice_version=sizing_input.lattice.lattice_version,
                    atomic_scale=sizing_input.lattice.atomic_scale,
                    step_units=sizing_input.lattice.step_units,
                    buy_lot_units=sizing_input.lattice.buy_lot_units,
                    sell_lot_units=sizing_input.lattice.sell_lot_units,
                    min_quantity_units=sizing_input.lattice.min_quantity_units,
                    min_notional=replace(
                        sizing_input.lattice.min_notional,
                        currency=str(cny),
                    ),
                    odd_lot_close_permitted=(
                        sizing_input.lattice.odd_lot_close_permitted
                    ),
                    whole_sell_residual_permitted=(
                        sizing_input.lattice.whole_sell_residual_permitted
                    ),
                ),
            )
            for sizing_input in cycle.sizing_inputs
        )
        entries = tuple(
            replace(
                entry,
                validation_context=replace(
                    entry.validation_context,
                    instrument_catalog=catalog,
                    universe=(instrument_id,),
                ),
            )
            for entry in cycle.schedule.entries
        )
        cycles.append(
            replace(
                cycle,
                schedule=replace(cycle.schedule, entries=entries),
                sizing_inputs=sizing_inputs,
            )
        )
    plan = replace(hydrated.execution_case_plan, decision_cycles=tuple(cycles))
    spec = _execution_case_semantic_spec_v3(
        base_spec=hydrated.execution_case_semantic_spec,
        execution_case_plan=plan,
        market_data_preparation=prepared.preparation,
    )
    resolved = _resolved_for_spec(prepared, resolved, spec)
    hydrated = _HydratedExecutionCaseInputs(
        execution_case_semantic_spec=spec,
        timeline_stream_keys=hydrated.timeline_stream_keys,
        target_stream=hydrated.target_stream,
        timeline_batch_size=hydrated.timeline_batch_size,
        execution_case_plan=plan,
    )
    envelope = _materialize_execution_input_bundle_v4(
        resolved_request=resolved,
        hydrated_inputs=hydrated,
        market_data_preparation=prepared.preparation,
    )
    return prepared, resolved, hydrated, catalog, envelope


def _payload(envelope: ArtifactEnvelope) -> dict[str, object]:
    return json.loads(canonical_bytes(envelope).decode())["payload"]


def _empty_binding() -> dict[str, object]:
    catalog = InstrumentCatalog((CurrencyId("USD"),), (), ())
    return {
        "type": "validation_instrument_catalog_binding_v1",
        "schema_version": 1,
        "catalog_hash": canonical_sha256(catalog),
        "catalog": catalog.to_canonical_dict(),
    }


def test_v4_cash_materializes_decodes_and_hydrates_as_v3_common_value() -> None:
    prepared, resolved, hydrated, _, _ = _contract()
    envelope = _materialize_execution_input_bundle_v4(
        resolved_request=resolved,
        hydrated_inputs=hydrated,
        market_data_preparation=prepared.preparation,
    )
    request = BacktestExecutionRequest(
        4,
        resolved.request,
        ArtifactRef.from_envelope(envelope),
    )
    decoded = _EXECUTION_INPUT_CATALOG_V4.read(canonical_bytes(envelope)).artifact
    assert type(decoded) is _DecodedExecutionInputBundleV3
    outcome = _hydrate_execution_inputs_v4(
        _Reader(envelope),
        request,
        market_reader=prepared.verified_reader,
        resolved_request=resolved,
        prepared_market_data=prepared,
    )
    assert outcome.failure is None
    assert outcome.result is not None
    actual = outcome.result.execution_case_plan
    expected = hydrated.execution_case_plan
    for left, right in (
        (actual.decision_cycles, expected.decision_cycles),
        (actual.bar_executions, expected.bar_executions),
        (actual.financial_state, expected.financial_state),
        (actual.financial_dispatch_plan, expected.financial_dispatch_plan),
        (actual.execution_model.spec(), expected.execution_model.spec()),
        (actual.snapshot_plan, expected.snapshot_plan),
        (actual.closeout_policy.spec(), expected.closeout_policy.spec()),
    ):
        assert canonical_bytes(left) == canonical_bytes(right)


def test_v4_equity_catalog_round_trip_locks_nullable_base_and_symbol_timeline() -> None:
    _, _, hydrated, catalog, envelope = _equity_contract()
    fixture = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    assert fixture == json.loads(canonical_bytes(envelope).decode())
    decoded = _EXECUTION_INPUT_CATALOG_V4.read(canonical_bytes(envelope)).artifact
    assert type(decoded) is _DecodedExecutionInputBundleV3
    context = decoded.execution_case_plan.decision_cycles[0].schedule.entries[
        0
    ].validation_context
    assert context.instrument_catalog == catalog
    assert context.instrument_catalog.instruments[0].base_currency is None
    assert context.instrument_catalog.symbol_timelines[0].intervals == (
        SymbolInterval("000001", UtcInstant(0), UtcInstant(1)),
        SymbolInterval("000001.SZ", UtcInstant(1), None),
    )
    actual = decoded.execution_case_plan
    expected = hydrated.execution_case_plan
    for left, right in (
        (actual.decision_cycles, expected.decision_cycles),
        (actual.bar_executions, expected.bar_executions),
        (actual.financial_state, expected.financial_state),
        (actual.financial_dispatch_plan, expected.financial_dispatch_plan),
        (actual.execution_model.spec(), expected.execution_model.spec()),
        (actual.snapshot_plan, expected.snapshot_plan),
        (actual.closeout_policy.spec(), expected.closeout_policy.spec()),
    ):
        assert canonical_bytes(left) == canonical_bytes(right)


@pytest.mark.parametrize(
    "case",
    ("missing", "unused", "duplicate", "unsorted", "hash", "context", "universe"),
)
def test_v4_catalog_table_and_context_mismatches_fail_closed(case: str) -> None:
    _, _, _, _, envelope = _equity_contract()
    payload = _payload(envelope)
    bindings = cast(
        list[dict[str, Any]], payload["validation_instrument_catalogs"]
    )
    plan = cast(dict[str, Any], payload["execution_case_plan"])
    context = cast(
        dict[str, Any],
        plan["decision_cycles"][0]["schedule"]["entries"][0][
            "validation_context"
        ],
    )
    if case == "missing":
        bindings.clear()
    elif case == "unused":
        bindings.append(_empty_binding())
        bindings.sort(key=lambda item: item["catalog_hash"])
    elif case == "duplicate":
        bindings.append(dict(bindings[0]))
    elif case == "unsorted":
        bindings.append(_empty_binding())
        bindings.sort(key=lambda item: item["catalog_hash"], reverse=True)
    elif case == "hash":
        bindings[0]["catalog_hash"] = "0" * 64
    elif case == "context":
        context["instrument_catalog_hash"] = "0" * 64
    else:
        context["universe"] = [
            {
                "type": "instrument_id",
                "venue": "xshe",
                "stable_key": "000002",
            }
        ]
    with pytest.raises((TypeError, ValueError)):
        _read_execution_input_payload_v4(payload)


def test_v4_materializer_rejects_nested_subclass_and_constructor_bypass() -> None:
    _, resolved, hydrated, _, _ = _equity_contract()

    class CurrencyIdSubclass(CurrencyId):
        pass

    catalog = hydrated.execution_case_plan.decision_cycles[0].schedule.entries[
        0
    ].validation_context.instrument_catalog
    subclass_currency = CurrencyIdSubclass("CNY")
    subclassed = InstrumentCatalog(
        (subclass_currency,),
        tuple(
            replace(
                definition,
                quote_currency=subclass_currency,
                settlement_currency=subclass_currency,
            )
            for definition in catalog.instruments
        ),
        catalog.symbol_timelines,
    )
    bypassed = object.__new__(InstrumentCatalog)
    object.__setattr__(bypassed, "currencies", ())
    object.__setattr__(bypassed, "instruments", catalog.instruments)
    object.__setattr__(bypassed, "symbol_timelines", catalog.symbol_timelines)

    for malformed in (subclassed, bypassed):
        entry = hydrated.execution_case_plan.decision_cycles[0].schedule.entries[0]
        changed_entry = replace(
            entry,
            validation_context=replace(
                entry.validation_context,
                instrument_catalog=malformed,
            ),
        )
        cycle = hydrated.execution_case_plan.decision_cycles[0]
        plan = replace(
            hydrated.execution_case_plan,
            decision_cycles=(
                replace(
                    cycle,
                    schedule=replace(cycle.schedule, entries=(changed_entry,)),
                ),
            ),
        )
        with pytest.raises((TypeError, ValueError)):
            _materialize_execution_input_bundle_v4(
                resolved_request=resolved,
                hydrated_inputs=replace(hydrated, execution_case_plan=plan),
                market_data_preparation=_contract()[0].preparation,
            )


def test_v4_wrong_request_or_ref_fails_before_artifact_io() -> None:
    _, resolved, _, _, envelope = _equity_contract()
    valid = BacktestExecutionRequest(
        4,
        resolved.request,
        ArtifactRef.from_envelope(envelope),
    )

    class RequestSubclass(BacktestExecutionRequest):
        pass

    wrong_type = RequestSubclass(
        valid.schema_version,
        valid.request,
        valid.execution_input_bundle_ref,
    )
    wrong_ref = object.__new__(BacktestExecutionRequest)
    object.__setattr__(wrong_ref, "schema_version", 4)
    object.__setattr__(wrong_ref, "request", valid.request)
    object.__setattr__(
        wrong_ref,
        "execution_input_bundle_ref",
        ArtifactRef("wrong", 4, valid.execution_input_bundle_ref.content_hash),
    )
    for malformed in (wrong_type, wrong_ref):
        bundle, failure = _read_execution_inputs_v4(
            _Reader(error=AssertionError("artifact I/O must not occur")),
            malformed,
        )
        assert bundle is None
        assert failure is not None
        assert failure.code in {
            _ExecutionInputsHydrationFailureCodeV3.MALFORMED_EXECUTION_REQUEST,
            _ExecutionInputsHydrationFailureCodeV3.WRONG_EXECUTION_INPUT_BUNDLE_REF,
        }
