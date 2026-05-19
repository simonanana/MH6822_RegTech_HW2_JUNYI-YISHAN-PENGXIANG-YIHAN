"""Shared model aliases for the homework architecture.

The stable implementation lives in src.engine; this file exposes lightweight
typing names used by the starter-notebook-style module boundaries.
"""

from __future__ import annotations

from typing import Any, TypeAlias

from .engine import CONVENTIONAL_ASSET_CLASSES, EVENT_ASSET_CLASS


Trade: TypeAlias = dict[str, Any]
Finding: TypeAlias = dict[str, str]
ParseResult: TypeAlias = dict[str, Any]
UPIResult: TypeAlias = dict[str, Any]
AnalyzedTrade: TypeAlias = dict[str, Any]
ComplianceReport: TypeAlias = dict[str, Any]


__all__ = [
    "AnalyzedTrade",
    "ComplianceReport",
    "CONVENTIONAL_ASSET_CLASSES",
    "EVENT_ASSET_CLASS",
    "Finding",
    "ParseResult",
    "Trade",
    "UPIResult",
]
