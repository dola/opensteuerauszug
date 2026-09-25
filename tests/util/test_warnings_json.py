"""Tests for the --warnings-json export."""

import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from typer.testing import CliRunner

from opensteuerauszug.model.critical_warning import CriticalWarning, CriticalWarningCategory
from opensteuerauszug.model.ech0196 import TaxStatement
from opensteuerauszug.model.payment_reconciliation import (
    PaymentReconciliationReport,
    PaymentReconciliationRow,
)
from opensteuerauszug.steuerauszug import app
from opensteuerauszug.util.warnings_json import (
    WARNINGS_JSON_VERSION,
    warnings_document,
    write_warnings_json,
)

runner = CliRunner()
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
IBKR_SAMPLE = PROJECT_ROOT / "tests" / "samples" / "import" / "ibkr" / "vtandchill_2025.xml"
KURSLISTE_DIR = PROJECT_ROOT / "tests" / "samples" / "kursliste"


def _statement() -> TaxStatement:
    return TaxStatement(
        minorVersion=2,
        id="test-warnings-json",
        creationDate=datetime(2025, 3, 1, 10, 0, 0),
        taxPeriod=2024,
        periodFrom=date(2024, 1, 1),
        periodTo=date(2024, 12, 31),
        country="CH",
        canton="ZH",
        totalTaxValue=Decimal("0"),
        totalGrossRevenueA=Decimal("0"),
        totalGrossRevenueB=Decimal("0"),
        totalWithHoldingTaxClaim=Decimal("0"),
    )


def test_critical_warnings_are_serialised():
    statement = _statement()
    statement.critical_warnings.append(
        CriticalWarning(
            category=CriticalWarningCategory.MISSING_KURSLISTE,
            message="Security X was not found in the Kursliste.",
            source="KurslisteTaxValueCalculator",
            identifier="US0000000000",
            payment_date=date(2024, 6, 30),
        )
    )

    document = warnings_document(statement)

    assert document["version"] == WARNINGS_JSON_VERSION
    assert document["critical_warnings"] == [
        {
            "category": "missing_kursliste",
            "message": "Security X was not found in the Kursliste.",
            "source": "KurslisteTaxValueCalculator",
            "identifier": "US0000000000",
            "payment_date": "2024-06-30",
        }
    ]


def test_reconciliation_is_null_when_not_run():
    assert warnings_document(_statement())["reconciliation"] is None


def test_reconciliation_rows_are_serialised(tmp_path: Path):
    statement = _statement()
    statement.payment_reconciliation_report = PaymentReconciliationReport(
        rows=[
            PaymentReconciliationRow(
                country="US",
                security="Example",
                identifier="US0000000000",
                payment_date=date(2024, 12, 31),
                kursliste_dividend_chf=Decimal("1.50"),
                status="mismatch",
            )
        ],
        mismatch_count=1,
    )
    path = tmp_path / "warnings.json"

    write_warnings_json(statement, path)
    document = json.loads(path.read_text(encoding="utf-8"))

    reconciliation = document["reconciliation"]
    assert reconciliation["mismatch_count"] == 1
    assert reconciliation["rows"][0]["status"] == "mismatch"
    assert reconciliation["rows"][0]["payment_date"] == "2024-12-31"
    assert reconciliation["rows"][0]["kursliste_dividend_chf"] == "1.50"


def _process(tmp_path: Path, *extra: str) -> dict:
    output = tmp_path / "warnings.json"
    result = runner.invoke(
        app,
        [
            "process",
            str(IBKR_SAMPLE),
            "--importer",
            "ibkr",
            "--tax-year",
            "2025",
            "--kursliste-dir",
            str(KURSLISTE_DIR),
            "--output",
            str(tmp_path / "out.pdf"),
            "--warnings-json",
            str(output),
            *extra,
        ],
    )
    assert result.exit_code == 0, result.stdout
    return json.loads(output.read_text(encoding="utf-8"))


def test_cli_writes_warnings_json(tmp_path: Path):
    document = _process(tmp_path)

    assert document["version"] == WARNINGS_JSON_VERSION
    assert isinstance(document["critical_warnings"], list)
    assert document["reconciliation"]["match_count"] == len(
        [r for r in document["reconciliation"]["rows"] if r["status"] == "match"]
    )


def test_cli_reconciliation_null_when_disabled(tmp_path: Path):
    document = _process(tmp_path, "--no-payment-reconciliation")

    assert document["reconciliation"] is None
