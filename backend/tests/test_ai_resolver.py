"""
Unit tests for Layer 2 AI Exception Resolver.
Verifies anomaly classification, ghost order recovery, MDR fee variance resolution,
and honest exception flagging for chargebacks and orphan bank credits.
"""

import pytest
from backend.generator.synthetic_data import generate_synthetic_dataset
from backend.engine.deterministic import DeterministicMatcher
from backend.engine.ai_resolver import AIExceptionResolver
from backend.models.schema import MatchType, AnomalyCategory


def test_ai_exception_resolution():
    oms_orders, gateway_records, bank_entries = generate_synthetic_dataset(seed=42)
    matcher = DeterministicMatcher()
    reconciled_l1, unres_oms, unres_gateway, unres_bank = matcher.match(
        oms_orders=oms_orders,
        gateway_records=gateway_records,
        bank_entries=bank_entries
    )

    resolver = AIExceptionResolver(confidence_threshold=0.85)
    auto_resolved, flagged_exceptions = resolver.resolve_exceptions(
        unresolved_oms=unres_oms,
        unresolved_gateway=unres_gateway,
        unresolved_bank=unres_bank
    )

    # Verify auto-resolved records
    assert len(auto_resolved) > 0
    for rec in auto_resolved:
        assert rec.is_reconciled is True
        assert rec.confidence_score >= 0.85
        assert rec.journal_entry is not None
        assert rec.match_type == MatchType.AI_RESOLVED
        assert rec.anomaly_category in [
            AnomalyCategory.DROPPED_WEBHOOK_GHOST,
            AnomalyCategory.MDR_FEE_VARIANCE,
            AnomalyCategory.PARTIAL_REFUND_OFFSET,
        ]

    # Verify flagged exceptions (honest exception list)
    assert len(flagged_exceptions) > 0
    for exc in flagged_exceptions:
        assert exc.is_reconciled is False
        assert exc.match_type == MatchType.FLAGGED_EXCEPTION
        assert exc.anomaly_category in [
            AnomalyCategory.CHARGEBACK_HOLD,
            AnomalyCategory.ORPHAN_BANK_CREDIT,
            AnomalyCategory.TIMING_SETTLEMENT_DELAY,
        ]
