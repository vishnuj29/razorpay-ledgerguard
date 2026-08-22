"""
Unit tests for Layer 1 Deterministic Matcher.
Verifies mathematical fee verification, 1:1 exact matching, and 1:N batch knapsack grouping.
"""

import pytest
from backend.generator.synthetic_data import generate_synthetic_dataset
from backend.engine.deterministic import DeterministicMatcher
from backend.models.schema import MatchType, AnomalyCategory


def test_fee_math_verification():
    matcher = DeterministicMatcher(mdr_rate=0.02, gst_rate=0.18)
    gross = 1000.0
    fee_mdr = 20.0
    tax_gst = 3.60
    net = 976.40
    assert matcher.verify_fee_math(gross, fee_mdr, tax_gst, net) is True


def test_fee_math_invalid():
    matcher = DeterministicMatcher(mdr_rate=0.02, gst_rate=0.18)
    gross = 1000.0
    fee_mdr = 20.0
    tax_gst = 3.60
    net = 900.00  # Incorrect net
    assert matcher.verify_fee_math(gross, fee_mdr, tax_gst, net) is False


def test_deterministic_matching_accuracy():
    oms_orders, gateway_records, bank_entries = generate_synthetic_dataset(seed=42)
    matcher = DeterministicMatcher(mdr_rate=0.02, gst_rate=0.18)
    
    reconciled, unres_oms, unres_gateway, unres_bank = matcher.match(
        oms_orders=oms_orders,
        gateway_records=gateway_records,
        bank_entries=bank_entries
    )

    # All reconciled records in Layer 1 must have 100% confidence
    assert len(reconciled) > 0
    for rec in reconciled:
        assert rec.confidence_score == 1.0
        assert rec.is_reconciled is True
        assert rec.variance == 0.0
        assert rec.match_type in [MatchType.EXACT_1_TO_1, MatchType.BATCH_1_TO_N]

    # Verify that batch settlements were grouped correctly
    batch_records = [r for r in reconciled if r.match_type == MatchType.BATCH_1_TO_N]
    assert len(batch_records) == 30  # 3 batches of 10
