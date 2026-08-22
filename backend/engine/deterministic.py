"""
Layer 1: Deterministic Financial Matching & Mathematical Verification Engine.
NO LLMs ARE USED IN THIS LAYER.
Performs exact matching, fee schedule verification (MDR + GST), and 1-to-N batch aggregation.
"""

from typing import List, Dict, Tuple, Optional, Set
from backend.models.schema import (
    OMSOrder,
    OMSOrderStatus,
    GatewaySettlementRecord,
    GatewayPaymentStatus,
    GatewayDisputeStatus,
    BankStatementEntry,
    ReconciliationRecord,
    MatchType,
    AnomalyCategory,
    JournalEntry,
)


class DeterministicMatcher:
    def __init__(self, mdr_rate: float = 0.02, gst_rate: float = 0.18, tolerance: float = 0.02):
        self.mdr_rate = mdr_rate
        self.gst_rate = gst_rate
        self.tolerance = tolerance

    def verify_fee_math(self, gross: float, fee_mdr: float, tax_gst: float, net_amount: float) -> bool:
        """
        Verify that Gross - MDR - GST == Net within tolerance (paise rounding).
        """
        computed_net = round(gross - fee_mdr - tax_gst, 2)
        return abs(computed_net - net_amount) <= self.tolerance

    def match(
        self,
        oms_orders: List[OMSOrder],
        gateway_records: List[GatewaySettlementRecord],
        bank_entries: List[BankStatementEntry],
    ) -> Tuple[List[ReconciliationRecord], List[OMSOrder], List[GatewaySettlementRecord], List[BankStatementEntry]]:
        reconciled: List[ReconciliationRecord] = []

        # Indexing for rapid deterministic lookup
        oms_by_id: Dict[str, OMSOrder] = {o.order_id: o for o in oms_orders}
        gateway_by_order: Dict[str, GatewaySettlementRecord] = {g.order_id: g for g in gateway_records}
        gateway_by_pay: Dict[str, GatewaySettlementRecord] = {g.payment_id: g for g in gateway_records}
        
        # Bank entries indexed by UTR (if present)
        bank_by_utr: Dict[str, BankStatementEntry] = {}
        for b in bank_entries:
            if b.utr and b.utr.strip():
                bank_by_utr[b.utr.strip()] = b

        used_oms_ids: Set[str] = set()
        used_pay_ids: Set[str] = set()
        used_bank_ids: Set[str] = set()

        # -------------------------------------------------------------
        # STEP 1: 1-to-N Batch Settlements Match
        # Group gateway records by batch settlement_id or batch UTR
        # -------------------------------------------------------------
        batches: Dict[str, List[GatewaySettlementRecord]] = {}
        for g in gateway_records:
            if g.settlement_id and g.settlement_id.startswith("setl_batch_") and g.utr:
                batches.setdefault(g.utr, []).append(g)

        for batch_utr, g_list in batches.items():
            if batch_utr in bank_by_utr:
                bank_entry = bank_by_utr[batch_utr]
                sum_gateway_net = round(sum(g.net_amount for g in g_list), 2)
                
                # Check if bank credit equals sum of batch
                if abs(bank_entry.credit - sum_gateway_net) <= self.tolerance:
                    used_bank_ids.add(bank_entry.entry_id)
                    
                    for g in g_list:
                        used_pay_ids.add(g.payment_id)
                        oms_ord = oms_by_id.get(g.order_id)
                        if oms_ord:
                            used_oms_ids.add(oms_ord.order_id)

                        reconciled.append(ReconciliationRecord(
                            recon_id=f"rec_batch_{g.payment_id}",
                            order_id=g.order_id,
                            payment_id=g.payment_id,
                            settlement_id=g.settlement_id,
                            bank_entry_id=bank_entry.entry_id,
                            utr=batch_utr,
                            gross_amount=g.gross_amount,
                            fee_deducted=g.fee_mdr,
                            tax_deducted=g.tax_gst,
                            net_settled=g.net_amount,
                            bank_credited=g.net_amount, # Allocated share of batch credit
                            variance=0.0,
                            match_type=MatchType.BATCH_1_TO_N,
                            anomaly_category=AnomalyCategory.CLEAN_MATCH,
                            confidence_score=1.0,
                            ai_reasoning=f"Matched deterministically as part of 1:N batch settlement ({len(g_list)} items, total ₹{sum_gateway_net:.2f}) with UTR {batch_utr}.",
                            journal_entry=JournalEntry(
                                debit_account="1010 - Bank Account (Nodal)",
                                credit_account="1200 - Accounts Receivable / Razorpay Clearing",
                                amount=g.net_amount,
                                narration=f"Settlement batch receipt for {g.order_id}"
                            ),
                            is_reconciled=True,
                            requires_human_review=False
                        ))

        # -------------------------------------------------------------
        # STEP 2: Exact 1:1 Match (OMS <-> Gateway <-> Bank via UTR & Amount)
        # -------------------------------------------------------------
        for g in gateway_records:
            if g.payment_id in used_pay_ids:
                continue

            oms_ord = oms_by_id.get(g.order_id)
            if not oms_ord or oms_ord.status != OMSOrderStatus.PAID:
                # Potential ghost order, refund, or status mismatch - pass to Layer 2
                continue

            # Check mathematical validity of fee & gross
            fee_valid = self.verify_fee_math(g.gross_amount, g.fee_mdr, g.tax_gst, g.net_amount)
            # Check expected MDR rate
            expected_fee = round(g.gross_amount * self.mdr_rate, 2)
            is_standard_mdr = abs(expected_fee - g.fee_mdr) <= self.tolerance

            if not fee_valid or not is_standard_mdr:
                # Fee variance - pass to Layer 2
                continue

            # Check if UTR exists in bank statements
            if g.utr and g.utr in bank_by_utr:
                bank_entry = bank_by_utr[g.utr]
                if bank_entry.entry_id not in used_bank_ids:
                    # Check exact credit match
                    if abs(bank_entry.credit - g.net_amount) <= self.tolerance and abs(oms_ord.amount - g.gross_amount) <= self.tolerance:
                        used_oms_ids.add(oms_ord.order_id)
                        used_pay_ids.add(g.payment_id)
                        used_bank_ids.add(bank_entry.entry_id)

                        reconciled.append(ReconciliationRecord(
                            recon_id=f"rec_exact_{g.payment_id}",
                            order_id=g.order_id,
                            payment_id=g.payment_id,
                            settlement_id=g.settlement_id,
                            bank_entry_id=bank_entry.entry_id,
                            utr=g.utr,
                            gross_amount=g.gross_amount,
                            fee_deducted=g.fee_mdr,
                            tax_deducted=g.tax_gst,
                            net_settled=g.net_amount,
                            bank_credited=bank_entry.credit,
                            variance=0.0,
                            match_type=MatchType.EXACT_1_TO_1,
                            anomaly_category=AnomalyCategory.CLEAN_MATCH,
                            confidence_score=1.0,
                            ai_reasoning="Exact 1:1:1 3-way match verified deterministically across OMS, Gateway, and Bank with exact fee schedule.",
                            journal_entry=JournalEntry(
                                debit_account="1010 - Bank Account (Nodal)",
                                credit_account="1200 - Accounts Receivable / Razorpay Clearing",
                                amount=g.net_amount,
                                narration=f"Exact settlement receipt for {g.order_id} via UTR {g.utr}"
                            ),
                            is_reconciled=True,
                            requires_human_review=False
                        ))

        # -------------------------------------------------------------
        # Collect Remaining Unresolved Records for AI Exception Layer
        # -------------------------------------------------------------
        unresolved_oms = [o for o in oms_orders if o.order_id not in used_oms_ids]
        unresolved_gateway = [g for g in gateway_records if g.payment_id not in used_pay_ids]
        unresolved_bank = [b for b in bank_entries if b.entry_id not in used_bank_ids]

        return reconciled, unresolved_oms, unresolved_gateway, unresolved_bank
