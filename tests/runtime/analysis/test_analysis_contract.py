from __future__ import annotations

from hashlib import sha256
from inspect import signature
import json
from pathlib import Path

import pytest

import crypto_quant_backtest
from crypto_quant_backtest import BacktestCanonicalPublicationRef, ResultGrade
from crypto_quant_domain import (
    ArtifactEnvelope,
    ArtifactRef,
    canonical_bytes,
    canonical_sha256,
)

_ROOT = Path(__file__).resolve().parents[3]
_FIXTURE = _ROOT / "tests/fixtures/runtime/bt-gap06-analysis-v1.json"
_PLATFORM_FIXTURE = _ROOT.parent / "tests/contracts/backtest-consumer-port-v1.json"
_FIXTURE_SHA256 = "7764e978cc530d1e518f4c4b4a714627b49b09dc2fe594eacf1633a9d8ba5ef1"


def _load(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        pytest.fail(f"invalid JSON fixture {path}: {error}")
    assert type(value) is dict
    return value


def _artifact_ref(value: object) -> ArtifactRef:
    assert type(value) is dict
    fields = dict(value)
    assert fields.pop("type") == "artifact_ref"
    return ArtifactRef(**fields)


def _publication_ref(value: object) -> BacktestCanonicalPublicationRef:
    assert type(value) is dict
    fields = dict(value)
    assert fields.pop("type") == "backtest_canonical_publication_ref"
    return BacktestCanonicalPublicationRef.from_artifact_ref(
        _artifact_ref(fields["artifact_ref"])
    )


def _public_type(name: str) -> type[object]:
    value = getattr(crypto_quant_backtest, name, None)
    assert isinstance(value, type), f"BT-GAP-06 RED: missing public {name}"
    assert name in crypto_quant_backtest.__all__
    return value


def test_fixture_freezes_stored_payload_loaded_view_and_metric_semantics() -> None:
    fixture = _load(_FIXTURE)
    assert sha256(_FIXTURE.read_bytes()).hexdigest() == _FIXTURE_SHA256
    assert fixture["fixture_id"] == "bt-gap06-analysis-v1"
    assert fixture["schema_version"] == 1

    profile = fixture["metric_profile"]
    assert type(profile) is dict
    profile_payload = profile["payload"]
    assert type(profile_payload) is dict
    assert profile_payload == {
        "type": "backtest_metric_profile",
        "schema_version": 1,
        "profile_key": "simple_period_return.fill_count.v1",
        "profile_version": 1,
        "valuation_schedule": "run_boundary_snapshots",
        "return_method": "simple_period_return",
        "annualization_basis": "not_applicable",
        "risk_free_source": "not_applicable",
        "cash_flow_treatment": "subtract_net_external_cash_flow",
        "drawdown_sampling": "not_applicable",
        "reporting_currency_source": "source_execution_result",
        "benchmark": "not_applicable",
        "trade_count_method": "authoritative_fill_count",
        "decimal_policy": {
            "maximum_fractional_digits": 18,
            "rounding": "half_even",
            "notation": "ordinary",
            "strip_trailing_fractional_zeros": True,
            "normalize_negative_zero": True,
        },
        "missing_metric_encoding": "null",
    }
    assert canonical_sha256(profile_payload) == profile["payload_canonical_sha256"]
    profile_envelope = ArtifactEnvelope(**profile["envelope"])
    assert canonical_bytes(profile_envelope).decode() == profile["expected_canonical_utf8"]
    assert ArtifactRef.from_envelope(profile_envelope) == _artifact_ref(profile["ref"])

    conclusive = fixture["conclusive_analysis"]
    assert type(conclusive) is dict
    stored = conclusive["stored_payload"]
    loaded = conclusive["loaded_view"]
    assert type(stored) is dict and type(loaded) is dict
    assert "analysis_ref" not in stored
    assert set(loaded) == {
        "analysis_ref",
        "metric_profile_ref",
        "source_publication_ref",
        "source_execution_result_hash",
        "simple_period_return",
        "trade_count",
        "result_grade",
    }
    assert {key: value for key, value in stored.items() if key not in {"type", "schema_version"}} == {
        key: value for key, value in loaded.items() if key != "analysis_ref"
    }
    analysis_envelope = ArtifactEnvelope(**conclusive["envelope"])
    assert canonical_bytes(analysis_envelope).decode() == conclusive[
        "expected_canonical_utf8"
    ]
    analysis_ref = conclusive["ref"]
    assert type(analysis_ref) is dict
    assert ArtifactRef.from_envelope(analysis_envelope) == _artifact_ref(
        analysis_ref["artifact_ref"]
    )

    inconclusive = fixture["inconclusive_analysis"]
    assert type(inconclusive) is dict
    inconclusive_payload = inconclusive["stored_payload"]
    assert type(inconclusive_payload) is dict
    assert inconclusive_payload["simple_period_return"] is None
    assert inconclusive_payload["trade_count"] == 0
    assert canonical_sha256(inconclusive_payload) == inconclusive[
        "payload_canonical_sha256"
    ]

    assert fixture["worked_examples"] == [
        {
            "starting_equity": "100",
            "ending_equity": "90",
            "net_external_cash_flow": "0",
            "expected_simple_period_return": "-0.1",
        },
        {
            "starting_equity": "100",
            "ending_equity": "110",
            "net_external_cash_flow": "20",
            "expected_simple_period_return": "-0.1",
        },
        {
            "starting_equity": "2000000000000000000",
            "ending_equity": "2000000000000000001",
            "net_external_cash_flow": "0",
            "expected_simple_period_return": "0",
        },
        {
            "starting_equity": "2000000000000000000",
            "ending_equity": "2000000000000000003",
            "net_external_cash_flow": "0",
            "expected_simple_period_return": "0.000000000000000002",
        },
    ]


def test_fixture_preserves_the_platform_loaded_projection_without_self_reference() -> None:
    fixture = _load(_FIXTURE)
    platform = _load(_PLATFORM_FIXTURE)
    cases = platform["cases"]
    assert type(cases) is list
    adverse = next(value for value in cases if value["case_id"] == "adverse_completed")
    platform_analysis = adverse["analysis"]
    assert type(platform_analysis) is dict
    local_loaded = fixture["conclusive_analysis"]["loaded_view"]
    assert type(local_loaded) is dict
    assert set(platform_analysis) == set(local_loaded)

    projection = fixture["preserved_platform_projection"]
    assert type(projection) is dict
    for key, expected in projection.items():
        assert platform_analysis[key] == expected
        assert local_loaded[key] == expected
    assert platform_analysis["source_publication_ref"] == local_loaded[
        "source_publication_ref"
    ]
    assert platform_analysis["analysis_ref"] == adverse["derive"]["analysis_ref"]
    assert platform_analysis["metric_profile_ref"] == adverse["derive"][
        "metric_profile_ref"
    ]
    for key, artifact_type in (
        ("analysis_ref", "backtest_analysis"),
        ("metric_profile_ref", "backtest_metric_profile"),
    ):
        platform_ref = platform_analysis[key]
        local_ref = local_loaded[key]
        if key == "analysis_ref":
            platform_ref = platform_ref["artifact_ref"]
            local_ref = local_ref["artifact_ref"]
        assert platform_ref["artifact_type"] == local_ref["artifact_type"] == artifact_type
        assert platform_ref["schema_version"] == local_ref["schema_version"] == 1


def test_metric_profile_is_one_exact_public_v1_authority() -> None:
    profile_type = _public_type("BacktestMetricProfile")
    parameters = list(signature(profile_type).parameters)
    assert parameters == ["profile_key", "profile_version"]
    fixture = _load(_FIXTURE)["metric_profile"]
    assert type(fixture) is dict
    payload = fixture["payload"]
    assert type(payload) is dict
    profile = profile_type(payload["profile_key"], payload["profile_version"])
    assert canonical_bytes(profile) == canonical_bytes(payload)

    with pytest.raises((TypeError, ValueError)):
        profile_type("other", 1)
    with pytest.raises((TypeError, ValueError)):
        profile_type(payload["profile_key"], 2)


def test_stored_analysis_is_typed_canonical_and_uses_null_for_inconclusive_return() -> None:
    analysis_type = _public_type("BacktestAnalysis")
    parameters = list(signature(analysis_type).parameters)
    assert parameters == [
        "metric_profile_ref",
        "source_publication_ref",
        "source_execution_result_hash",
        "simple_period_return",
        "trade_count",
        "result_grade",
    ]
    fixture = _load(_FIXTURE)
    for key in ("conclusive_analysis", "inconclusive_analysis"):
        case = fixture[key]
        assert type(case) is dict
        payload = case["stored_payload"]
        assert type(payload) is dict
        analysis = analysis_type(
            _artifact_ref(payload["metric_profile_ref"]),
            _publication_ref(payload["source_publication_ref"]),
            payload["source_execution_result_hash"],
            payload["simple_period_return"],
            payload["trade_count"],
            ResultGrade(payload["result_grade"]),
        )
        assert canonical_bytes(analysis) == canonical_bytes(payload)
        assert not hasattr(analysis, "analysis_ref")

    conclusive = fixture["conclusive_analysis"]["stored_payload"]
    assert type(conclusive) is dict
    valid_args = (
        _artifact_ref(conclusive["metric_profile_ref"]),
        _publication_ref(conclusive["source_publication_ref"]),
        conclusive["source_execution_result_hash"],
    )
    for valid in (None, "0", "0.123456789012345678"):
        analysis_type(*valid_args, valid, 0, ResultGrade.DEVELOPMENT)
    for invalid in (0.1, "1e-1", "-0", "0.10", "0.1234567890123456789"):
        with pytest.raises((TypeError, ValueError)):
            analysis_type(*valid_args, invalid, 1, ResultGrade.DEVELOPMENT)
    for invalid in (True, -1, 1.0, "1"):
        with pytest.raises((TypeError, ValueError)):
            analysis_type(*valid_args, "-0.1", invalid, ResultGrade.DEVELOPMENT)

    forged_metric_ref = valid_args[0]
    object.__setattr__(forged_metric_ref, "content_hash", "not-a-hash")
    with pytest.raises((TypeError, ValueError)):
        analysis_type(
            forged_metric_ref,
            *valid_args[1:],
            "-0.1",
            1,
            ResultGrade.DEVELOPMENT,
        )


def test_verified_loaded_view_attaches_only_the_derived_analysis_ref() -> None:
    ref_type = _public_type("AnalysisArtifactRef")
    view_type = _public_type("VerifiedBacktestAnalysis")
    ref_parameters = list(signature(ref_type).parameters)
    view_parameters = list(signature(view_type).parameters)
    assert ref_parameters == ["artifact_ref"]
    assert view_parameters == ["analysis_ref", "analysis"]

    fixture = _load(_FIXTURE)["conclusive_analysis"]
    assert type(fixture) is dict
    payload = fixture["stored_payload"]
    assert type(payload) is dict
    analysis_type = _public_type("BacktestAnalysis")
    analysis = analysis_type(
        _artifact_ref(payload["metric_profile_ref"]),
        _publication_ref(payload["source_publication_ref"]),
        payload["source_execution_result_hash"],
        payload["simple_period_return"],
        payload["trade_count"],
        ResultGrade(payload["result_grade"]),
    )
    ref_wire = fixture["ref"]
    assert type(ref_wire) is dict
    analysis_ref = ref_type(_artifact_ref(ref_wire["artifact_ref"]))
    loaded = view_type(analysis_ref, analysis)
    assert canonical_bytes(loaded) == canonical_bytes(fixture["loaded_view"])
    assert loaded.analysis_ref is analysis_ref
    for name in (
        "metric_profile_ref",
        "source_publication_ref",
        "source_execution_result_hash",
        "simple_period_return",
        "trade_count",
        "result_grade",
    ):
        assert getattr(loaded, name) == getattr(analysis, name)

    forged_ref = _artifact_ref(ref_wire["artifact_ref"])
    object.__setattr__(forged_ref, "artifact_type", "backtest_metric_profile")
    with pytest.raises((TypeError, ValueError)):
        ref_type(forged_ref)
