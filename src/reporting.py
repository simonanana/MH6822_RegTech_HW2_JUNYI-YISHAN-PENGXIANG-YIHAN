"""Reporting wrapper.

The stable implementation lives in src.engine; this file exposes the homework
module boundary used by the starter notebook.
"""

from __future__ import annotations

from .engine import (
    summarize,
    write_dashboard,
    write_findings_csv,
    write_json,
    write_outputs,
)


__all__ = [
    "summarize",
    "write_dashboard",
    "write_findings_csv",
    "write_json",
    "write_outputs",
]
