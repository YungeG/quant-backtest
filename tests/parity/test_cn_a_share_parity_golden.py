from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tools.parity.cn_a_share import run_plan


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/parity/fixtures/cn-a-share-g08h-v1"
CONTRACT = ROOT / "tests/parity/contracts/cn-a-share-g08h-legacy-to-g08h-v1.json"
_STATIC_SHA256 = {
    "plan.json": "7600c6416d18e35fe5f9cb3174a6fe9768d752fd740440fba2430f4ef293d1b8",
    "legacy.expected.json": "e6b267b42f5983187a0807c3514beae80e0676ea2987dd4dea2c6c816f680b2a",
    "g08h.actual.json": "6a565b912671b88fe0c9ab70b24705aa5259fdb99fd644d19bac7ac3178a7174",
    "report.expected.json": "d12734232e96a78f8397a795b9151f3c2c597df338fd45d44eeeaf20990e08da",
    "contract": "6d310d9ce7bcf3e5eb1b88704c7030d63a42aa5d2faa67c18324ebd4ca8b423b",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_g08h_parity_report_matches_static_golden() -> None:
    try:
        expected = json.loads(
            (FIXTURES / "report.expected.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError("invalid G08H parity report fixture") from error
    assert run_plan(ROOT, FIXTURES / "plan.json") == expected


def test_g08h_parity_fixture_bytes_are_frozen() -> None:
    for name in ("plan.json", "legacy.expected.json", "g08h.actual.json", "report.expected.json"):
        assert _sha256(FIXTURES / name) == _STATIC_SHA256[name]
    assert _sha256(CONTRACT) == _STATIC_SHA256["contract"]
