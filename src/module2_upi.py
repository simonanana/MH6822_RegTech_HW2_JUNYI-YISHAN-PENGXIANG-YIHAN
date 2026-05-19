"""Module 2 UPI wrapper.

The stable implementation lives in src.engine; this file exposes the homework
module boundary used by the starter notebook.
"""

from __future__ import annotations

from .engine import (
    codeset_findings,
    load_codeset,
    load_codesets,
    lookup_upi,
    map_product,
    product_template_path,
    upi_findings,
    validate_currency,
    validate_reference_rate,
)


__all__ = [
    "codeset_findings",
    "load_codeset",
    "load_codesets",
    "lookup_upi",
    "map_product",
    "product_template_path",
    "upi_findings",
    "validate_currency",
    "validate_reference_rate",
]
