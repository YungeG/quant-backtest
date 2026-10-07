"""One atomic local owner pointer for a synthetic transfer; never trade authority."""
from __future__ import annotations

import json
from pathlib import Path

from crypto_quant_domain import ArtifactRef, canonical_bytes, canonical_sha256
from crypto_quant_trading import LedgerSchema

from ._publication import RunPublicationLock, canonical_hash, canonical_text, fsync_directory, write_file
from .artifact_envelope_reader import ArtifactEnvelopeReader
from .cn_a_share_portfolio_funding_development_v1 import (
    SyntheticCrossVenueFundingCandidateV1, read_retained_synthetic_cross_venue_funding_candidate_v1,
)

_FILE = "synthetic-cn-funding-owner-v1.json"


def _scope(root: Path, account: str) -> tuple[Path, str]:
    if not isinstance(root, Path):
        raise TypeError("publication_root must be Path")
    canonical_text("account_id", account)
    return root / "synthetic-cn-funding-owners", "run_" + canonical_sha256(
        {"type": "synthetic_funding_owner", "account_id": account})[7:]


def _body(candidate: SyntheticCrossVenueFundingCandidateV1, ref: ArtifactRef) -> dict[str, object]:
    return {"type": "synthetic_cn_funding_owner_record", "schema_version": 1,
            "account_id": candidate.journal.entries[-2].account_id,
            "prior_journal_hash": candidate.prior_journal_hash,
            "journal_hash": candidate.journal.journal_hash,
            "transfer_identity": candidate.transfer_identity, "candidate_ref": ref,
            "trade_authorized": False}


def read_synthetic_cn_funding_owner_v1(
    *, publication_root: Path, account_id: str, expected_record_hash: str,
    ledger_schema: LedgerSchema, reader: ArtifactEnvelopeReader,
) -> SyntheticCrossVenueFundingCandidateV1:
    root, run_id = _scope(publication_root, account_id)
    canonical_hash("expected_record_hash", expected_record_hash)
    path = root / "runs" / run_id / _FILE
    if path.is_symlink():
        raise ValueError("funding owner pointer cannot be symlink")
    source = path.read_bytes()
    try:
        data = json.loads(source)
    except (ValueError, UnicodeDecodeError) as error:
        raise ValueError("funding owner pointer is not canonical JSON") from error
    if source != canonical_bytes(data) or canonical_sha256(data) != expected_record_hash:
        raise ValueError("funding owner pointer hash mismatch")
    if (type(data) is not dict or type(data.get("candidate_ref")) is not dict
            or set(data["candidate_ref"]) != {"type", "artifact_type", "schema_version", "content_hash"}
            or data["candidate_ref"]["type"] != "artifact_ref"):
        raise ValueError("funding owner ref schema mismatch")
    raw = data["candidate_ref"]
    ref = ArtifactRef(raw["artifact_type"], raw["schema_version"], raw["content_hash"])
    candidate = read_retained_synthetic_cross_venue_funding_candidate_v1(
        ref, ledger_schema=ledger_schema, reader=reader)
    if (candidate.journal.entries[-2].account_id != account_id
            or source != canonical_bytes(_body(candidate, ref))):
        raise ValueError("funding owner pointer disagrees with retained pair")
    return candidate


def publish_synthetic_cn_funding_owner_v1(
    candidate: SyntheticCrossVenueFundingCandidateV1, ref: ArtifactRef, *,
    publication_root: Path, ledger_schema: LedgerSchema, reader: ArtifactEnvelopeReader,
) -> tuple[Path, str]:
    if type(candidate) is not SyntheticCrossVenueFundingCandidateV1 or type(ref) is not ArtifactRef:
        raise TypeError("synthetic funding publication requires exact candidate and ref")
    if read_retained_synthetic_cross_venue_funding_candidate_v1(
        ref, ledger_schema=ledger_schema, reader=reader) != candidate:
        raise ValueError("funding candidate differs from retained pair")
    account = candidate.journal.entries[-2].account_id
    root, run_id = _scope(publication_root, account)
    record_body = _body(candidate, ref)
    record = canonical_bytes(record_body)
    record_hash = canonical_sha256(record_body)
    with RunPublicationLock(root=root, semantic_run_id=run_id) as lock:
        path = lock.run_directory / _FILE
        if path.is_symlink():
            raise ValueError("funding owner pointer cannot be symlink")
        if path.exists():
            if path.read_bytes() != record:
                raise ValueError("different funding pair already committed for account")
        else:
            write_file(path, record)
            fsync_directory(lock.run_directory)
        if read_synthetic_cn_funding_owner_v1(
            publication_root=publication_root, account_id=account,
            expected_record_hash=record_hash, ledger_schema=ledger_schema, reader=reader) != candidate:
            raise ValueError("funding owner readback mismatch")
        return path, record_hash
