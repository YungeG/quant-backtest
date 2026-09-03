from __future__ import annotations

from dataclasses import fields, replace
from pathlib import Path

import pytest
from crypto_quant_bundle_builder import (
    KoruTradifiEconomicsBundleFailureCodeV3,
    KoruTradifiEconomicsBundleRequestV3,
    KoruTradifiEconomicsTermsV3,
    KoruTradifiSourceProjectionContentIdentityV2,
    publish_koru_tradifi_economics_bundle_v3,
)
from crypto_quant_domain import (
    ArtifactEnvelope,
    ArtifactReadResult,
    ArtifactRef,
    UtcInstant,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_market_data import MarketStreamManifest

from tests.bundle_builder.providers.binance_usdm import (
    test_koru_tradifi_execution_bundle_v1 as v1_fixture,
)
from tests.bundle_builder.providers.binance_usdm import (
    test_koru_tradifi_execution_bundle_v2 as v2_fixture,
)


class _MemoryArtifactStore:
    def __init__(self) -> None:
        self.values: dict[ArtifactRef, ArtifactReadResult] = {}
        self.tamper_readback = False

    def put(self, *, envelope: ArtifactEnvelope) -> ArtifactRef:
        ref = ArtifactRef.from_envelope(envelope)
        self.values[ref] = ArtifactReadResult(
            envelope, object(), canonical_bytes(envelope), canonical_sha256(envelope)
        )
        return ref

    def read(self, *, ref: ArtifactRef) -> ArtifactReadResult:
        value = self.values[ref]
        if self.tamper_readback:
            return ArtifactReadResult(value.envelope, value.artifact, b"tampered", value.source_hash)
        return value


def _source():
    """A real V2 replay result, not an object.__new__ fixture."""
    return v2_fixture._source()


def _request(tmp_path: Path, *, source=None, terms=None, store=None):
    source = _source() if source is None else source
    terms = (
        KoruTradifiEconomicsTermsV3.from_source_projection(source, execution_account_id="account-1")
        if terms is None
        else terms
    )
    return KoruTradifiEconomicsBundleRequestV3(
        source_projection=source,
        source_projection_content_identity=KoruTradifiSourceProjectionContentIdentityV2(
            source.fragment_digest, source.request.request_hash
        ),
        terms=terms,
        artifact_store=_MemoryArtifactStore() if store is None else store,
        repository_root=tmp_path,
    )


def _published(tmp_path: Path):
    outcome = publish_koru_tradifi_economics_bundle_v3(_request(tmp_path))
    assert outcome.failure is None and outcome.result is not None
    return outcome.result


def _forged(source, *, holdout: bool):
    """Bypass dataclass construction but retain self-consistent local hashes."""
    forged = object.__new__(type(source))
    for item in fields(source):
        if item.name != "fragment_digest":
            object.__setattr__(forged, item.name, getattr(source, item.name))
    if holdout:
        request = replace(
            source.request,
            timeline_window_end_exclusive=UtcInstant(
                source.request.timeline_window_end_exclusive.epoch_nanoseconds + 1
            ),
        )
        object.__setattr__(forged, "request", request)
    else:
        events = source.source_events[:-1]
        grouped = {
            manifest.stream_key: tuple(
                event for event in (*events, *source.projection_events) if event.stream_key == manifest.stream_key
            )
            for manifest in source.stream_manifests
        }
        object.__setattr__(forged, "source_events", events)
        object.__setattr__(
            forged,
            "stream_manifests",
            tuple(MarketStreamManifest.from_events(key, events) for key, events in sorted(grouped.items())),
        )
    object.__setattr__(forged, "fragment_digest", canonical_sha256(forged._body()))
    return forged


def test_publishes_reopens_target_free_economics_bundle_and_artifacts(tmp_path: Path) -> None:
    result = _published(tmp_path)
    source = result.request.source_projection
    expected = {
        *(value.stream_key for value in source.stream_manifests),
        "binance_usdm.tradifi.economics_authority.koruusdt.v3",
        "binance_usdm.tradifi.price_purpose.authority.koruusdt.v3",
        "binance_usdm.tradifi.account.authority.koruusdt.v3",
    }

    assert {value.stream_key for value in result.manifest.streams} == expected
    assert result.reader.bundle_ref == result.bundle_ref
    assert result.authority_refs == tuple(ArtifactRef.from_envelope(value) for value in result.authority_artifacts)
    assert {value.artifact_type for value in result.authority_artifacts} == {
        "binance_usdm_koru_source_profile_authority",
        "xkrx_regular_session_calendar",
        "arcx_koru_core_session_calendar",
        "binance_usdm_tradifi_post_adjustment_unit_regime",
    }
    wire = result.economics_authority_event.payload
    assert wire["source_projection_content_identity"]["source_fragment_digest"] == source.fragment_digest
    assert wire["full_scope"]["end_exclusive"] == source.request.timeline_window_end_exclusive.to_canonical_dict()
    assert wire["authority_digest"] == result.authority_digest
    assert "repository_root" not in result.request.to_canonical_dict()
    assert all(".target." not in value.stream_key for value in result.manifest.streams)


def test_canonical_replay_and_operational_root_do_not_change_identity(tmp_path: Path) -> None:
    first = _published(tmp_path / "one")
    second = _published(tmp_path / "two")

    assert canonical_bytes(first) == canonical_bytes(second)
    assert first.authority_digest == second.authority_digest
    assert first.bundle_ref == second.bundle_ref


@pytest.mark.parametrize("holdout", (False, True))
def test_forged_partial_or_holdout_source_is_rejected_by_trusted_replay(tmp_path: Path, holdout: bool) -> None:
    source = _source()
    forged = _forged(source, holdout=holdout)
    outcome = publish_koru_tradifi_economics_bundle_v3(
        _request(tmp_path, source=forged, terms=KoruTradifiEconomicsTermsV3.from_source_projection(source, execution_account_id="account-1"))
    )

    assert outcome.result is None
    assert outcome.failure is not None
    assert outcome.failure.code is KoruTradifiEconomicsBundleFailureCodeV3.SOURCE_PROJECTION_INVALID


def test_terms_reject_strategy_target_unknown_and_fake_coverage_keys() -> None:
    terms = KoruTradifiEconomicsTermsV3.from_source_projection(_source(), execution_account_id="account-1")
    for key in ("strategy_definition_ref", "target_stream_key", "unknown"):
        account = dict(terms.account_authority)
        account[key] = {"forbidden": True}
        with pytest.raises(ValueError, match="account_authority"):
            replace(terms, account_authority=account)
    coverage = dict(terms.price_purpose_authority[0])
    coverage["coverage"] = {"stream_id": "forged"}
    with pytest.raises(ValueError, match="price_purpose_authority"):
        replace(terms, price_purpose_authority=(coverage, *terms.price_purpose_authority[1:]))


def test_fake_term_stream_event_and_ref_cover_fail_closed(tmp_path: Path) -> None:
    source = _source()
    terms = KoruTradifiEconomicsTermsV3.from_source_projection(source, execution_account_id="account-1")
    fake_price = dict(terms.price_purpose_authority[0])
    fake_price["stream_manifest"] = next(
        value for value in source.stream_manifests if value.stream_key.endswith("funding_history.publications.koruusdt.v1")
    )
    fake_event = dict(terms.source_event_bindings[0])
    fake_event["event_hash"] = "sha256:" + "0" * 64
    for bad_terms in (
        replace(terms, price_purpose_authority=(fake_price, *terms.price_purpose_authority[1:])),
        replace(terms, source_event_bindings=(fake_event, *terms.source_event_bindings[1:])),
        replace(terms, xkrx_calendar_ref=source.arcx_calendar_ref),
    ):
        outcome = publish_koru_tradifi_economics_bundle_v3(_request(tmp_path / str(id(bad_terms)), source=source, terms=bad_terms))
        assert outcome.result is None
        assert outcome.failure is not None
        assert outcome.failure.code is KoruTradifiEconomicsBundleFailureCodeV3.TERMS_INVALID


def test_legacy_v1_v2_sentinels_remain_available() -> None:
    assert v1_fixture._empty_result().manifest.schema_version == 1
    assert v2_fixture._build().manifest.schema_version == 2


def test_artifact_readback_tamper_fails_closed(tmp_path: Path) -> None:
    store = _MemoryArtifactStore()
    store.tamper_readback = True
    outcome = publish_koru_tradifi_economics_bundle_v3(_request(tmp_path, store=store))

    assert outcome.result is None
    assert outcome.failure is not None
    assert outcome.failure.code is KoruTradifiEconomicsBundleFailureCodeV3.ARTIFACT_PUBLICATION_FAILED


def test_public_module_has_no_target_runtime_or_network_dependency() -> None:
    import crypto_quant_bundle_builder.koru_tradifi_economics_bundle_v3 as module

    source = Path(module.__file__).read_text()
    assert "crypto_quant_backtest" not in source
    assert "binance_usdm_koru_directional_target_compiler" not in source
    assert not any(value in source for value in ("urllib", "requests", "http.client", "socket"))
