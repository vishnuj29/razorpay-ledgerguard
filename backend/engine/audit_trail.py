"""
Layer 3: Cryptographic Audit Trail & Batch Summary Aggregator for LedgerGuard.
Generates tamper-evident SHA-256 hash chains for all reconciliation events and computes benchmark metrics.
"""

import hashlib
import json
import time
from typing import List, Dict
from datetime import datetime

from backend.models.schema import (
    ReconciliationRecord,
    BatchSummary,
    MatchType,
    AnomalyCategory,
)


class AuditTrailEngine:
    def __init__(self):
        self.current_chain_hash = "GENESIS_BLOCK_LEDGERGUARD_2026"

    def compute_record_hash(self, record: ReconciliationRecord, previous_hash: str) -> str:
        """
        Creates a deterministic SHA-256 hash over the reconciliation record fields and previous block hash.
        """
        payload = {
            "prev_hash": previous_hash,
            "recon_id": record.recon_id,
            "order_id": record.order_id,
            "payment_id": record.payment_id,
            "utr": record.utr,
            "gross_amount": record.gross_amount,
            "net_settled": record.net_settled,
            "bank_credited": record.bank_credited,
            "match_type": record.match_type.value,
            "anomaly_category": record.anomaly_category.value,
            "confidence_score": record.confidence_score,
            "is_reconciled": record.is_reconciled,
            "journal_entry": record.journal_entry.model_dump() if record.journal_entry and hasattr(record.journal_entry, "model_dump") else (record.journal_entry.dict() if record.journal_entry else None)
        }
        encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def seal_audit_trail(self, records: List[ReconciliationRecord]) -> List[ReconciliationRecord]:
        """
        Chains all records in sequence with SHA-256 proofs.
        """
        running_hash = self.current_chain_hash
        for rec in records:
            rec.audit_hash = self.compute_record_hash(rec, running_hash)
            running_hash = rec.audit_hash
        self.current_chain_hash = running_hash
        return records

    def generate_batch_summary(
        self,
        batch_id: str,
        records: List[ReconciliationRecord],
        execution_time_seconds: float
    ) -> BatchSummary:
        total_records = len(records)
        if total_records == 0:
            return BatchSummary(
                batch_id=batch_id,
                total_records_processed=0,
                total_oms_amount=0.0,
                total_gateway_net_amount=0.0,
                total_bank_credited_amount=0.0,
                total_discrepancy_amount=0.0,
                exact_match_count=0,
                batch_match_count=0,
                ai_resolved_count=0,
                flagged_exception_count=0,
                match_rate_percentage=0.0,
                unresolved_exception_percentage=0.0,
                execution_time_seconds=execution_time_seconds,
                discrepancy_breakdown={},
                audit_chain_root_hash=self.current_chain_hash
            )

        exact_count = sum(1 for r in records if r.match_type == MatchType.EXACT_1_TO_1)
        batch_count = sum(1 for r in records if r.match_type == MatchType.BATCH_1_TO_N)
        ai_count = sum(1 for r in records if r.match_type == MatchType.AI_RESOLVED)
        exception_count = sum(1 for r in records if r.match_type == MatchType.FLAGGED_EXCEPTION)

        reconciled_count = sum(1 for r in records if r.is_reconciled)
        match_rate = round((reconciled_count / total_records) * 100, 2)
        exception_rate = round((exception_count / total_records) * 100, 2)

        total_gross = round(sum(r.gross_amount for r in records), 2)
        total_net = round(sum(r.net_settled for r in records), 2)
        total_bank = round(sum(r.bank_credited for r in records), 2)
        total_variance = round(sum(r.variance for r in records), 2)

        # Break down by anomaly category
        breakdown: Dict[str, int] = {}
        for r in records:
            cat_name = r.anomaly_category.value
            breakdown[cat_name] = breakdown.get(cat_name, 0) + 1

        return BatchSummary(
            batch_id=batch_id,
            total_records_processed=total_records,
            total_oms_amount=total_gross,
            total_gateway_net_amount=total_net,
            total_bank_credited_amount=total_bank,
            total_discrepancy_amount=total_variance,
            exact_match_count=exact_count,
            batch_match_count=batch_count,
            ai_resolved_count=ai_count,
            flagged_exception_count=exception_count,
            match_rate_percentage=match_rate,
            unresolved_exception_percentage=exception_rate,
            execution_time_seconds=round(execution_time_seconds, 4),
            discrepancy_breakdown=breakdown,
            audit_chain_root_hash=self.current_chain_hash
        )
