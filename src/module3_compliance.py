"""Module 3 Compliance wrapper.

The stable implementation lives in src.engine; this file exposes the homework
module boundary used by the starter notebook.
"""

from __future__ import annotations

from .engine import (
    data_quality_status,
    lei_check_digits_valid,
    margin_findings,
    overall_status,
    regime_findings,
    reporting_scope_status,
    required_field_findings,
    validate_lei_field,
    validate_uti,
)


__all__ = [
    "data_quality_status",
    "lei_check_digits_valid",
    "margin_findings",
    "overall_status",
    "regime_findings",
    "reporting_scope_status",
    "required_field_findings",
    "validate_lei_field",
    "validate_uti",
]
