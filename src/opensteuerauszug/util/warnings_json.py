"""Machine-readable export of the problems a run found.

Critical warnings reach the PDF's instructions page and payment reconciliation rows
reach the console, but neither is available to a program that drives
``opensteuerauszug`` and wants to act on them. This writes both as JSON.

The format is versioned. Bump ``WARNINGS_JSON_VERSION`` on any change that removes or
renames a field; adding fields does not require a bump.
"""

import json
from pathlib import Path
from typing import Any, Dict

from ..model.ech0196 import TaxStatement

WARNINGS_JSON_VERSION = 1


def warnings_document(statement: TaxStatement) -> Dict[str, Any]:
    """The statement's critical warnings and reconciliation report, as plain data.

    ``reconciliation`` is ``None`` when the reconciliation phase did not run.
    """
    report = statement.payment_reconciliation_report
    return {
        "version": WARNINGS_JSON_VERSION,
        "critical_warnings": [
            warning.model_dump(mode="json") for warning in statement.critical_warnings
        ],
        "reconciliation": report.model_dump(mode="json") if report is not None else None,
    }


def write_warnings_json(statement: TaxStatement, path: Path) -> None:
    path.write_text(
        json.dumps(warnings_document(statement), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
