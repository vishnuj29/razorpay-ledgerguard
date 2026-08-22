"""
Data models and schemas for LedgerGuard 3-Way Reconciliation Engine.
Compatible with Python 3.8+ and Pydantic v2/v1.
"""

from enum import Enum
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime


class OMSOrderStatus(str, Enum):
    PAID = "PAID"
    CREATED = "CREATED"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"
    PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED"


class OMSOrder(BaseModel):
    order_id: str = Field(..., description="Unique merchant order ID, e.g. ord_1001")
    amount: float = Field(..., description="Gross order amount in INR")
    currency: str = Field(default="INR")
    customer_id: str
    status: OMSOrderStatus
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    description: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GatewayPaymentStatus(str, Enum):
    CAPTURED = "captured"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"
    FAILED = "failed"


class GatewayDisputeStatus(str, Enum):
    NONE = "none"
    CHARGEBACK_HOLD = "chargeback_hold"
    REVERSED = "reversed"


class GatewaySettlementRecord(BaseModel):
    payment_id: str = Field(..., description="Razorpay payment ID, e.g. pay_99812")
    order_id: str = Field(..., description="Associated merchant order ID")
    gross_amount: float
    fee_mdr: float = Field(..., description="Merchant Discount Rate fee charged by gateway")
    tax_gst: float = Field(..., description="18% GST on MDR")
    net_amount: float = Field(..., description="Net payout = gross - fee - tax")
    status: GatewayPaymentStatus
    settlement_id: Optional[str] = Field(default=None, description="Batch settlement ID, e.g. setl_batch_01")
    utr: Optional[str] = Field(default=None, description="Unique Transaction Reference for bank payout")
    method: str = Field(default="upi", description="Payment method (upi, card, netbanking)")
    dispute_status: GatewayDisputeStatus = GatewayDisputeStatus.NONE
    timestamp: str


class BankStatementEntry(BaseModel):
    entry_id: str = Field(..., description="Internal line ID in bank statement")
    date: str
    utr: Optional[str] = Field(default=None, description="Extracted or stated UTR from bank")
    narration: str = Field(..., description="Raw bank narration string")
    credit: float = Field(default=0.0)
    debit: float = Field(default=0.0)
    balance: float = Field(default=0.0)
    channel: str = Field(default="NEFT", description="NEFT, RTGS, IMPS, UPI")


class MatchType(str, Enum):
    EXACT_1_TO_1 = "EXACT_1_TO_1"
    BATCH_1_TO_N = "BATCH_1_TO_N"
    AI_RESOLVED = "AI_RESOLVED"
    FLAGGED_EXCEPTION = "FLAGGED_EXCEPTION"


class AnomalyCategory(str, Enum):
    CLEAN_MATCH = "CLEAN_MATCH"
    DROPPED_WEBHOOK_GHOST = "DROPPED_WEBHOOK_GHOST"
    MDR_FEE_VARIANCE = "MDR_FEE_VARIANCE"
    PARTIAL_REFUND_OFFSET = "PARTIAL_REFUND_OFFSET"
    CHARGEBACK_HOLD = "CHARGEBACK_HOLD"
    ORPHAN_BANK_CREDIT = "ORPHAN_BANK_CREDIT"
    TIMING_SETTLEMENT_DELAY = "TIMING_SETTLEMENT_DELAY"
    AMBIGUOUS_NARRATION = "AMBIGUOUS_NARRATION"
    UNMATCHED_OMS_ORDER = "UNMATCHED_OMS_ORDER"


class JournalEntry(BaseModel):
    debit_account: str
    credit_account: str
    amount: float
    narration: str


class ReconciliationRecord(BaseModel):
    recon_id: str
    order_id: Optional[str] = None
    payment_id: Optional[str] = None
    settlement_id: Optional[str] = None
    bank_entry_id: Optional[str] = None
    utr: Optional[str] = None
    gross_amount: float
    fee_deducted: float
    tax_deducted: float
    net_settled: float
    bank_credited: float
    variance: float = 0.0
    match_type: MatchType
    anomaly_category: AnomalyCategory
    confidence_score: float = 1.0
    ai_reasoning: Optional[str] = None
    journal_entry: Optional[JournalEntry] = None
    is_reconciled: bool
    requires_human_review: bool = False
    audit_hash: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class BatchSummary(BaseModel):
    batch_id: str
    total_records_processed: int
    total_oms_amount: float
    total_gateway_net_amount: float
    total_bank_credited_amount: float
    total_discrepancy_amount: float
    exact_match_count: int
    batch_match_count: int
    ai_resolved_count: int
    flagged_exception_count: int
    match_rate_percentage: float
    unresolved_exception_percentage: float
    execution_time_seconds: float
    discrepancy_breakdown: Dict[str, int]
    audit_chain_root_hash: str
