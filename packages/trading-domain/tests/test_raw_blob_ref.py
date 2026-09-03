from __future__ import annotations

import pytest
from crypto_quant_domain import RawBlobRef


def test_raw_blob_ref_is_canonical_and_strict() -> None:
    ref = RawBlobRef.from_bytes(b"raw")

    assert ref.to_canonical_dict() == {
        "type": "raw_blob_ref",
        "content_hash": (
            "sha256:d7439bee24773bcbfa2d0a97947ee36227b10d1022b1a55847e928965bb6bfde"
        ),
        "byte_count": 3,
    }
    assert RawBlobRef.from_canonical_dict(ref.to_canonical_dict()) == ref
    with pytest.raises(ValueError, match="exactly"):
        RawBlobRef.from_canonical_dict({"content_hash": ref.content_hash})
    with pytest.raises(ValueError, match="nonnegative"):
        RawBlobRef(ref.content_hash, -1)
