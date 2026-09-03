from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from tools.acquisition import cn_a_share_szse_trading_rules_2023_fixed_source_v1 as source
from tools.acquisition._common import AcquisitionError, sha256


def _capture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    content = b"%PDF-1.7\nfixed test attachment\n"
    monkeypatch.setattr(source, "_SHA256", sha256(content))
    request = source.SzseTradingRules2023FixedSourceRequestV1()
    output = tmp_path / "capture"
    receipt = source.acquire_szse_trading_rules_2023_fixed_source_v1(
        request,
        output_dir=output,
        acquired_at_epoch_nanoseconds=7,
        fetch=lambda url: (200, content),
    )
    assert receipt["request"] == request.to_canonical_dict()
    assert source.verify_szse_trading_rules_2023_fixed_source_v1(output) == receipt
    return output


def test_fixed_source_capture_binds_exact_url_pdf_hash_and_immutable_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert source._URL == "https://docs.static.szse.cn/www/lawrules/rule/repeal/rules/W020230217564423808793.pdf"
    assert source._SHA256 == "sha256:7018114a6e11deb239c2a72e71e49defc6e8841b3e2c093b3bbf809282c67222"
    output = _capture(tmp_path, monkeypatch)
    receipt = json.loads((output / "acquisition-receipt.json").read_bytes())
    assert tuple(receipt[key] for key in ("source_bounded", "decision_grade_eligible", "live_eligible", "deployment_authorized")) == (True, False, False, False)
    snapshot = receipt["snapshot"]
    assert type(snapshot) is dict
    members = snapshot["members"]
    assert type(members) is list
    assert members[0]["declared_sha256"] == source._SHA256
    with pytest.raises(FrozenInstanceError):
        source.SzseTradingRules2023FixedSourceRequestV1().source_url = "x"  # type: ignore[misc]


@pytest.mark.parametrize("status,content", [(302, b"%PDF-x"), (200, b"not-a-pdf"), (200, b"%PDF-wrong")])
def test_fixed_source_capture_rejects_redirect_status_or_invalid_attachment_atomically(
    tmp_path: Path, status: int, content: bytes
) -> None:
    output = tmp_path / "capture"
    with pytest.raises(AcquisitionError):
        source.acquire_szse_trading_rules_2023_fixed_source_v1(
            source.SzseTradingRules2023FixedSourceRequestV1(),
            output_dir=output,
            acquired_at_epoch_nanoseconds=7,
            fetch=lambda url: (status, content),
        )
    assert not output.exists()


def test_fixed_source_verification_rejects_raw_or_receipt_substitution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = _capture(tmp_path, monkeypatch)
    (output / "attachment/szse-trading-rules-2023.pdf").write_bytes(b"%PDF-replaced")
    with pytest.raises(AcquisitionError):
        source.verify_szse_trading_rules_2023_fixed_source_v1(output)

    output = _capture(tmp_path / "receipt", monkeypatch)
    receipt_path = output / "acquisition-receipt.json"
    receipt = json.loads(receipt_path.read_bytes())
    receipt["attachment_sha256"] = "sha256:substituted"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(AcquisitionError):
        source.verify_szse_trading_rules_2023_fixed_source_v1(output)
