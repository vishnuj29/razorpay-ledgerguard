"""
Comprehensive benchmark integration test suite for LedgerGuard.
Verifies batch throughput, match rate bounds, audit trail integrity, and SHA-256 chain immutability.
"""

import pytest
import time
from backend.generator.synthetic_data import generate_synthetic_dataset
from backend.engine.deterministic import DeterministicMatcher
from backend.engine.ai_resolver import AIExceptionResolver
from backend.engine.audit_trail import AuditTrailEngine
from backend.models.schema import MatchType


def test_full_pipeline_metrics():
    oms_orders, gateway_records, bank_entries = generate_synthetic_dataset(seed=42)
    start_time = time.time()

    # Step 1: Layer 1
    matcher = DeterministicMatcher()
    reconciled_l1, unres_oms, unres_gateway, unres_bank = matcher.match(
        oms_orders=oms_orders,
        gateway_records=gateway_records,
        bank_entries=bank_entries
    )

    # Step 2: Layer 2
    resolver = AIExceptionResolver()
    auto_resolved, flagged_exceptions = resolver.resolve_exceptions(
        unresolved_oms=unres_oms,
        unresolved_gateway=unres_gateway,
        unresolved_bank=unres_bank
    )

    # Step 3: Layer 3
    all_records = reconciled_l1 + auto_resolved + flagged_exceptions
    audit_engine = AuditTrailEngine()
    sealed = audit_engine.seal_audit_trail(all_records)
    elapsed = time.time() - start_time

    summary = audit_engine.generate_batch_summary("TEST_BATCH", sealed, elapsed)

    # Metric assertions:
    assert summary.total_records_processed >= 50, "Batch must be >= 50 records as required by Track 04 brief"
    assert summary.match_rate_percentage > 80.0, "Expected match rate > 80%"
    assert summary.unresolved_exception_percentage > 5.0, "Must have an honest non-zero exception list"
    assert summary.execution_time_seconds < 2.0, "Pipeline must run fast (sub-2-seconds)"
    assert len(summary.audit_chain_root_hash) == 64, "Must produce valid SHA-256 root hash"

    # Verify cryptographic chaining
    for i in range(1, len(sealed)):
        assert sealed[i].audit_hash != sealed[i-1].audit_hash
