"""Module 4 Classification wrapper.

The stable implementation lives in src.engine; this file exposes the homework
module boundary used by the starter notebook.
"""

from __future__ import annotations

from .engine import (
    EVENT_CONTRACT_UPI_SCHEMA,
    EVENT_ECONOMIC_FUNCTION_TESTS,
    cftc_event_contract_findings,
    classification_conclusion,
    event_contract_analysis,
    event_economic_function_test,
    event_source_facts,
    event_supervisory_flags,
    mas_event_contract_findings,
)


__all__ = [
    "EVENT_CONTRACT_UPI_SCHEMA",
    "EVENT_ECONOMIC_FUNCTION_TESTS",
    "cftc_event_contract_findings",
    "classification_conclusion",
    "event_contract_analysis",
    "event_economic_function_test",
    "event_source_facts",
    "event_supervisory_flags",
    "mas_event_contract_findings",
]
