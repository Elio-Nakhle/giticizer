from __future__ import annotations

import csv
import io
import json
from typing import Any


def to_csv(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return ""
    headers = list(rows[0].keys())
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=headers)
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def to_json(rows: list[dict[str, Any]]) -> str:
    return json.dumps(rows, indent=2)
