"""LEI utility wrapper.

The stable implementation lives in src.engine; this file exposes the homework
module boundary used by the starter notebook.
"""

from __future__ import annotations

from ..engine import lei_check_digits_valid, lei_to_number


__all__ = [
    "lei_check_digits_valid",
    "lei_to_number",
]
