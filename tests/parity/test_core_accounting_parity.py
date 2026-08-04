from __future__ import annotations

import importlib
import json
import subprocess
import sys
import tarfile
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from types import ModuleType
from typing import Iterator

from crypto_quant_domain import (
    DomainIdKind,
    Money,
    OrderSide,
)
from crypto_quant_trading import (
    AccountingJournal,
    CashInstrumentAccounting,
    GenericLedger,
    LedgerBalanceRegistration,
    LedgerSchema,
)

from tests.kernel.accounting._fixtures import (
    CASH_KEY,
    COST_BASIS_POLICY,
    MONEY_SCALE,
    NOTIONAL_POLICY,
    POSITION_KEY,
    domain_id,
    fee_assessment,
    fill,
    recorded_at,
)


ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / "tests/parity/fixtures/legacy-sources/crypto-quant-core-33ca4055b16fd966d92263248289fcd960a1cb93f52c4d8a0db00030b3e3d0d1.tar.gz"
EXPECTED = ROOT / "tests/parity/fixtures/core-accounting-wp03f-v1.expected.json"
CONTRACT = ROOT / "tests/parity/contracts/core-accounting-wp03f-v1.json"
ACTUAL = ROOT / "build/acceptance/wp-03f-core-accounting-actual.json"
REPORT = ROOT / "build/acceptance/wp-03f-core-accounting-parity.json"
RUNNER = ROOT / "tools/migration/run_parity.py"


@contextmanager
def legacy_accounting_module() -> Iterator[ModuleType]:
    with TemporaryDirectory() as directory:
        package = Path(directory) / "crypto_quant_core"
        package.mkdir()
        (package / "__init__.py").write_text("", encoding="utf-8")
        with tarfile.open(ARCHIVE, "r:gz") as archive:
            for source in ("contracts.py", "accounting.py"):
                member = archive.getmember(f"src/crypto_quant_core/{source}")
                extracted = archive.extractfile(member)
                assert extracted is not None
                (package / source).write_bytes(extracted.read())
        sys.path.insert(0, directory)
        try:
            yield importlib.import_module("crypto_quant_core.accounting")
        finally:
            sys.path.remove(directory)
            for name in tuple(sys.modules):
                if name == "crypto_quant_core" or name.startswith("crypto_quant_core."):
                    del sys.modules[name]


def money_text(value: Money) -> str:
    decimal = Decimal(value.units).scaleb(-value.scale.places)
    return f"{decimal:.{value.scale.places}f}"


def legacy_result() -> dict[str, str]:
    with legacy_accounting_module() as legacy:
        entry = legacy.Fill(
            timestamp_ms=1,
            side="buy",
            price=Decimal("100.00"),
            quantity=Decimal("2.0"),
            fee_quote=Decimal("1.00"),
        )
        exit_fill = legacy.Fill(
            timestamp_ms=2,
            side="sell",
            price=Decimal("110.00"),
            quantity=Decimal("2.0"),
            fee_quote=Decimal("1.50"),
        )
        result = legacy.calculate_closed_trade(entry, exit_fill)
    return {
        "fees": f"{result.fees:.2f}",
        "funding": f"{result.funding:.2f}",
        "gross_price_pnl": f"{result.gross_price_pnl:.2f}",
        "net_pnl": f"{result.net_pnl:.2f}",
    }


def current_result() -> dict[str, str]:
    accounting = CashInstrumentAccounting()
    buy = fill("1", side=OrderSide.BUY, quantity_units=20, price_units=10_000, execution_time=10)
    buy_result = accounting.book_fill(
        fill=buy,
        cash_key=CASH_KEY,
        position_key=POSITION_KEY,
        open_lots=(),
        cost_basis_policy=COST_BASIS_POLICY,
        notional_quantization=NOTIONAL_POLICY,
        journal_entry_id=domain_id(DomainIdKind.JOURNAL, "1"),
        recorded_at=recorded_at(11),
    ).result
    assert buy_result is not None
    buy_fee = accounting.charge_fee(
        assessment=fee_assessment("3", buy, amount_units=100, assessment_time=12),
        related_fill=buy,
        cash_key=CASH_KEY,
        open_lots=buy_result.open_lots,
        cost_basis_policy=COST_BASIS_POLICY,
        journal_entry_id=domain_id(DomainIdKind.JOURNAL, "3"),
        recorded_at=recorded_at(13),
    ).result
    assert buy_fee is not None

    sell = fill("2", side=OrderSide.SELL, quantity_units=20, price_units=11_000, execution_time=20)
    sell_result = accounting.book_fill(
        fill=sell,
        cash_key=CASH_KEY,
        position_key=POSITION_KEY,
        open_lots=buy_fee.open_lots,
        cost_basis_policy=COST_BASIS_POLICY,
        notional_quantization=NOTIONAL_POLICY,
        journal_entry_id=domain_id(DomainIdKind.JOURNAL, "2"),
        recorded_at=recorded_at(21),
    ).result
    assert sell_result is not None
    sell_fee = accounting.charge_fee(
        assessment=fee_assessment("4", sell, amount_units=150, assessment_time=22),
        related_fill=sell,
        cash_key=CASH_KEY,
        open_lots=sell_result.open_lots,
        cost_basis_policy=COST_BASIS_POLICY,
        journal_entry_id=domain_id(DomainIdKind.JOURNAL, "4"),
        recorded_at=recorded_at(23),
    ).result
    assert sell_fee is not None

    journal = AccountingJournal.from_entries(
        (
            buy_result.journal_entry,
            buy_fee.journal_entry,
            sell_result.journal_entry,
            sell_fee.journal_entry,
        )
    )
    ledger = GenericLedger(
        LedgerSchema(
            (
                LedgerBalanceRegistration(CASH_KEY, MONEY_SCALE),
                LedgerBalanceRegistration(POSITION_KEY, buy.quantity.scale),
            )
        )
    ).project(journal)
    gross = ledger.realized_pnl_amount(CASH_KEY)
    fees = ledger.fee_amount(CASH_KEY)
    funding = ledger.financing_amount(CASH_KEY)
    net = gross - fees + funding
    return {
        "fees": money_text(fees),
        "funding": money_text(funding),
        "gross_price_pnl": money_text(gross),
        "net_pnl": money_text(net),
    }


def test_frozen_legacy_behavior_and_current_cash_accounting_have_exact_parity() -> None:
    expected = json.loads(EXPECTED.read_text(encoding="utf-8"))
    assert legacy_result() == expected

    actual = current_result()
    ACTUAL.parent.mkdir(parents=True, exist_ok=True)
    ACTUAL.write_text(json.dumps(actual, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    completed = subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "--root",
            str(ROOT),
            "--contract",
            str(CONTRACT),
            "--expected",
            str(EXPECTED),
            "--actual",
            str(ACTUAL),
            "--migration-mode",
            "copy_with_parity",
            "--report",
            str(REPORT),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    assert report["verdict"] == "MATCH"
    assert report["first_divergence"] is None
