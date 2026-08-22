"""
Synthetic Data Generator for LedgerGuard.
Generates 120+ realistic records across 3 sources (OMS Orders, Gateway Settlements, Bank Statement)
simulating real-world Indian fintech failure modes, batch settlements, and fee structures.
"""

import json
import csv
import random
import os
from datetime import datetime, timedelta
from typing import Tuple, List, Dict, Any

from backend.models.schema import (
    OMSOrder,
    OMSOrderStatus,
    GatewaySettlementRecord,
    GatewayPaymentStatus,
    GatewayDisputeStatus,
    BankStatementEntry,
)


def generate_synthetic_dataset(
    seed: int = 42,
    output_dir: str = "data"
) -> Tuple[List[OMSOrder], List[GatewaySettlementRecord], List[BankStatementEntry]]:
    random.seed(seed)
    os.makedirs(output_dir, exist_ok=True)

    base_time = datetime(2026, 8, 1, 10, 0, 0)
    
    oms_orders: List[OMSOrder] = []
    gateway_records: List[GatewaySettlementRecord] = []
    bank_entries: List[BankStatementEntry] = []

    order_counter = 1000
    payment_counter = 50000
    bank_entry_counter = 100

    # -------------------------------------------------------------
    # 1. CLEAN EXACT 1:1 MATCHES (60 records)
    # -------------------------------------------------------------
    for i in range(60):
        order_counter += 1
        payment_counter += 1
        bank_entry_counter += 1

        order_id = f"ord_live_{order_counter}"
        pay_id = f"pay_{payment_counter}"
        bank_id = f"bnk_{bank_entry_counter}"
        utr = f"RZP{random.randint(100000000000, 999999999999)}"
        
        amount = round(random.choice([499.0, 999.0, 1499.0, 2499.0, 4999.0, 7500.0, 12000.0]), 2)
        tx_time = base_time + timedelta(hours=i*2, minutes=random.randint(5, 45))
        
        # Standard Razorpay 2% MDR + 18% GST on MDR
        mdr_rate = 0.02
        fee_mdr = round(amount * mdr_rate, 2)
        tax_gst = round(fee_mdr * 0.18, 2)
        net_amount = round(amount - fee_mdr - tax_gst, 2)

        # OMS
        oms_orders.append(OMSOrder(
            order_id=order_id,
            amount=amount,
            currency="INR",
            customer_id=f"cust_{random.randint(100, 999)}",
            status=OMSOrderStatus.PAID,
            timestamp=tx_time.isoformat(),
            description=f"Standard Checkout Item #{order_counter}"
        ))

        # Gateway
        gateway_records.append(GatewaySettlementRecord(
            payment_id=pay_id,
            order_id=order_id,
            gross_amount=amount,
            fee_mdr=fee_mdr,
            tax_gst=tax_gst,
            net_amount=net_amount,
            status=GatewayPaymentStatus.CAPTURED,
            settlement_id=f"setl_single_{order_counter}",
            utr=utr,
            method=random.choice(["upi", "card", "netbanking"]),
            dispute_status=GatewayDisputeStatus.NONE,
            timestamp=(tx_time + timedelta(seconds=20)).isoformat()
        ))

        # Bank Statement
        bank_time = tx_time + timedelta(days=1, hours=4)
        bank_entries.append(BankStatementEntry(
            entry_id=bank_id,
            date=bank_time.strftime("%Y-%m-%d"),
            utr=utr,
            narration=f"NEFT-RAZORPAY PAYMENT SOLUTIONS INDIA-{utr}-NODAL",
            credit=net_amount,
            debit=0.0,
            balance=1500000.0 + (i * 1000),
            channel="NEFT"
        ))

    # -------------------------------------------------------------
    # 2. 1:N BATCH SETTLEMENTS (30 records grouped into 3 bank lump sums)
    # -------------------------------------------------------------
    for batch_idx in range(1, 4):
        batch_id = f"setl_batch_{batch_idx:02d}"
        batch_utr = f"RZPBAT{batch_idx:02d}{random.randint(10000000, 99999999)}"
        batch_net_total = 0.0
        batch_time = base_time + timedelta(days=5 + batch_idx)

        for _ in range(10):
            order_counter += 1
            payment_counter += 1
            order_id = f"ord_live_{order_counter}"
            pay_id = f"pay_{payment_counter}"
            amount = round(random.choice([350.0, 799.0, 1250.0, 2100.0, 3400.0]), 2)
            tx_time = batch_time - timedelta(hours=random.randint(2, 18))

            mdr_rate = 0.02
            fee_mdr = round(amount * mdr_rate, 2)
            tax_gst = round(fee_mdr * 0.18, 2)
            net_amount = round(amount - fee_mdr - tax_gst, 2)
            batch_net_total += net_amount

            oms_orders.append(OMSOrder(
                order_id=order_id,
                amount=amount,
                currency="INR",
                customer_id=f"cust_{random.randint(100, 999)}",
                status=OMSOrderStatus.PAID,
                timestamp=tx_time.isoformat(),
                description=f"Batch Order #{order_counter}"
            ))

            gateway_records.append(GatewaySettlementRecord(
                payment_id=pay_id,
                order_id=order_id,
                gross_amount=amount,
                fee_mdr=fee_mdr,
                tax_gst=tax_gst,
                net_amount=net_amount,
                status=GatewayPaymentStatus.CAPTURED,
                settlement_id=batch_id,
                utr=batch_utr,
                method="upi",
                dispute_status=GatewayDisputeStatus.NONE,
                timestamp=tx_time.isoformat()
            ))

        bank_entry_counter += 1
        bank_entries.append(BankStatementEntry(
            entry_id=f"bnk_{bank_entry_counter}",
            date=batch_time.strftime("%Y-%m-%d"),
            utr=batch_utr,
            narration=f"NEFT-RAZORPAY SETTLEMENT BATCH-{batch_utr}-CMS POOL",
            credit=round(batch_net_total, 2),
            debit=0.0,
            balance=2500000.0,
            channel="NEFT"
        ))

    # -------------------------------------------------------------
    # 3. DROPPED WEBHOOK GHOST TRANSACTIONS (6 records)
    # Merchant OMS shows CREATED (webhook lost), but Gateway captured & Bank credited!
    # -------------------------------------------------------------
    for i in range(6):
        order_counter += 1
        payment_counter += 1
        bank_entry_counter += 1

        order_id = f"ord_ghost_{order_counter}"
        pay_id = f"pay_{payment_counter}"
        bank_id = f"bnk_{bank_entry_counter}"
        utr = f"RZPGHST{random.randint(1000000000, 9999999999)}"
        amount = round(random.choice([1999.0, 3299.0, 4899.0]), 2)
        tx_time = base_time + timedelta(days=9, hours=i*3)

        fee_mdr = round(amount * 0.02, 2)
        tax_gst = round(fee_mdr * 0.18, 2)
        net_amount = round(amount - fee_mdr - tax_gst, 2)

        # OMS still in CREATED (webhook dropped)
        oms_orders.append(OMSOrder(
            order_id=order_id,
            amount=amount,
            currency="INR",
            customer_id=f"cust_ghost_{i}",
            status=OMSOrderStatus.CREATED,  # <--- Webhook dropped!
            timestamp=tx_time.isoformat(),
            description=f"Webhook Dropped Order #{order_counter}"
        ))

        gateway_records.append(GatewaySettlementRecord(
            payment_id=pay_id,
            order_id=order_id,
            gross_amount=amount,
            fee_mdr=fee_mdr,
            tax_gst=tax_gst,
            net_amount=net_amount,
            status=GatewayPaymentStatus.CAPTURED,
            settlement_id=f"setl_ghst_{order_counter}",
            utr=utr,
            method="card",
            dispute_status=GatewayDisputeStatus.NONE,
            timestamp=tx_time.isoformat()
        ))

        bank_entries.append(BankStatementEntry(
            entry_id=bank_id,
            date=(tx_time + timedelta(days=1)).strftime("%Y-%m-%d"),
            utr=utr,
            narration=f"NEFT-RAZORPAY-{utr}-MERCHANT-AUTO-PAY",
            credit=net_amount,
            debit=0.0,
            balance=3100000.0,
            channel="NEFT"
        ))

    # -------------------------------------------------------------
    # 4. MDR & GST FEE VARIANCE / SPECIAL COMMERCIALS (8 records)
    # International card 3% MDR instead of standard 2%
    # -------------------------------------------------------------
    for i in range(8):
        order_counter += 1
        payment_counter += 1
        bank_entry_counter += 1

        order_id = f"ord_feevar_{order_counter}"
        pay_id = f"pay_{payment_counter}"
        bank_id = f"bnk_{bank_entry_counter}"
        utr = f"RZPFEE{random.randint(1000000000, 9999999999)}"
        amount = round(random.choice([5000.0, 8500.0, 15000.0]), 2)
        tx_time = base_time + timedelta(days=11, hours=i*2)

        # Gateway charged 3% international MDR
        fee_mdr = round(amount * 0.03, 2)
        tax_gst = round(fee_mdr * 0.18, 2)
        net_amount = round(amount - fee_mdr - tax_gst, 2)

        oms_orders.append(OMSOrder(
            order_id=order_id,
            amount=amount,
            currency="INR",
            customer_id=f"cust_intl_{i}",
            status=OMSOrderStatus.PAID,
            timestamp=tx_time.isoformat(),
            description=f"International Card Order #{order_counter}",
            metadata={"expected_mdr_rate": 0.02} # Merchant expected 2%
        ))

        gateway_records.append(GatewaySettlementRecord(
            payment_id=pay_id,
            order_id=order_id,
            gross_amount=amount,
            fee_mdr=fee_mdr,
            tax_gst=tax_gst,
            net_amount=net_amount,
            status=GatewayPaymentStatus.CAPTURED,
            settlement_id=f"setl_fee_{order_counter}",
            utr=utr,
            method="card",
            dispute_status=GatewayDisputeStatus.NONE,
            timestamp=tx_time.isoformat()
        ))

        bank_entries.append(BankStatementEntry(
            entry_id=bank_id,
            date=(tx_time + timedelta(days=1)).strftime("%Y-%m-%d"),
            utr=utr,
            narration=f"NEFT-RAZORPAY INDIA-{utr}-INTL SETTLEMENT",
            credit=net_amount,
            debit=0.0,
            balance=3400000.0,
            channel="NEFT"
        ))

    # -------------------------------------------------------------
    # 5. PARTIAL REFUNDS (6 records)
    # Order ₹4,000, refund of ₹1,000. Net settled = (₹4,000 - ₹1,000) - fees.
    # -------------------------------------------------------------
    for i in range(6):
        order_counter += 1
        payment_counter += 1
        bank_entry_counter += 1

        order_id = f"ord_ref_{order_counter}"
        pay_id = f"pay_{payment_counter}"
        bank_id = f"bnk_{bank_entry_counter}"
        utr = f"RZPREF{random.randint(1000000000, 9999999999)}"
        gross_amount = 4000.0
        refund_amount = 1000.0
        tx_time = base_time + timedelta(days=13, hours=i*2)

        # Fee charged on original gross or adjusted
        fee_mdr = round(gross_amount * 0.02, 2)
        tax_gst = round(fee_mdr * 0.18, 2)
        net_amount = round(gross_amount - refund_amount - fee_mdr - tax_gst, 2)

        oms_orders.append(OMSOrder(
            order_id=order_id,
            amount=gross_amount,
            currency="INR",
            customer_id=f"cust_ref_{i}",
            status=OMSOrderStatus.PARTIALLY_REFUNDED,
            timestamp=tx_time.isoformat(),
            description=f"Partially Refunded Order #{order_counter}",
            metadata={"refund_issued": refund_amount}
        ))

        gateway_records.append(GatewaySettlementRecord(
            payment_id=pay_id,
            order_id=order_id,
            gross_amount=gross_amount,
            fee_mdr=fee_mdr,
            tax_gst=tax_gst,
            net_amount=net_amount,
            status=GatewayPaymentStatus.PARTIALLY_REFUNDED,
            settlement_id=f"setl_ref_{order_counter}",
            utr=utr,
            method="upi",
            dispute_status=GatewayDisputeStatus.NONE,
            timestamp=tx_time.isoformat()
        ))

        bank_entries.append(BankStatementEntry(
            entry_id=bank_id,
            date=(tx_time + timedelta(days=1)).strftime("%Y-%m-%d"),
            utr=utr,
            narration=f"NEFT-RAZORPAY-{utr}-ADJUSTED REFUND NET",
            credit=net_amount,
            debit=0.0,
            balance=3600000.0,
            channel="NEFT"
        ))

    # -------------------------------------------------------------
    # 6. CHARGEBACK DISPUTE HOLDS (5 records)
    # Payment captured, but Gateway withheld bank settlement due to chargeback
    # -------------------------------------------------------------
    for i in range(5):
        order_counter += 1
        payment_counter += 1

        order_id = f"ord_chbk_{order_counter}"
        pay_id = f"pay_{payment_counter}"
        amount = round(random.choice([6000.0, 9500.0, 14000.0]), 2)
        tx_time = base_time + timedelta(days=15, hours=i*3)

        fee_mdr = round(amount * 0.02, 2)
        tax_gst = round(fee_mdr * 0.18, 2)
        net_amount = round(amount - fee_mdr - tax_gst, 2)

        oms_orders.append(OMSOrder(
            order_id=order_id,
            amount=amount,
            currency="INR",
            customer_id=f"cust_chbk_{i}",
            status=OMSOrderStatus.PAID,
            timestamp=tx_time.isoformat(),
            description=f"Disputed Chargeback Order #{order_counter}"
        ))

        gateway_records.append(GatewaySettlementRecord(
            payment_id=pay_id,
            order_id=order_id,
            gross_amount=amount,
            fee_mdr=fee_mdr,
            tax_gst=tax_gst,
            net_amount=net_amount,
            status=GatewayPaymentStatus.CAPTURED,
            settlement_id=None,  # Not settled!
            utr=None,
            method="card",
            dispute_status=GatewayDisputeStatus.CHARGEBACK_HOLD,
            timestamp=tx_time.isoformat()
        ))
        # No Bank Entry for this because settlement was withheld!

    # -------------------------------------------------------------
    # 7. ORPHAN BANK CREDITS (4 records)
    # Direct offline RTGS/IMPS to merchant bank account without gateway/OMS record
    # -------------------------------------------------------------
    for i in range(4):
        bank_entry_counter += 1
        bank_id = f"bnk_{bank_entry_counter}"
        orphan_utr = f"AXISN{random.randint(1000000000, 9999999999)}"
        amount = round(random.choice([25000.0, 45000.0, 80000.0, 120000.0]), 2)
        tx_time = base_time + timedelta(days=17, hours=i*4)

        bank_entries.append(BankStatementEntry(
            entry_id=bank_id,
            date=tx_time.strftime("%Y-%m-%d"),
            utr=orphan_utr,
            narration=f"IMPS/{orphan_utr}/B2B_DIRECT_VENDOR_PAYMENT_XYZ_LTD",
            credit=amount,
            debit=0.0,
            balance=4200000.0,
            channel="IMPS"
        ))

    # -------------------------------------------------------------
    # 8. TIMING / T+2 SETTLEMENT CUTOFF DELAYS (5 records)
    # Captured in Gateway on Sunday night, will settle in next month batch
    # -------------------------------------------------------------
    for i in range(5):
        order_counter += 1
        payment_counter += 1

        order_id = f"ord_timing_{order_counter}"
        pay_id = f"pay_{payment_counter}"
        amount = round(random.choice([1200.0, 2800.0, 3900.0]), 2)
        tx_time = base_time + timedelta(days=20, hours=23, minutes=45 + i)

        fee_mdr = round(amount * 0.02, 2)
        tax_gst = round(fee_mdr * 0.18, 2)
        net_amount = round(amount - fee_mdr - tax_gst, 2)

        oms_orders.append(OMSOrder(
            order_id=order_id,
            amount=amount,
            currency="INR",
            customer_id=f"cust_time_{i}",
            status=OMSOrderStatus.PAID,
            timestamp=tx_time.isoformat(),
            description=f"Cutoff Timing Order #{order_counter}"
        ))

        gateway_records.append(GatewaySettlementRecord(
            payment_id=pay_id,
            order_id=order_id,
            gross_amount=amount,
            fee_mdr=fee_mdr,
            tax_gst=tax_gst,
            net_amount=net_amount,
            status=GatewayPaymentStatus.CAPTURED,
            settlement_id=f"setl_next_cycle_{order_counter}",
            utr=None, # Settlement in flight
            method="upi",
            dispute_status=GatewayDisputeStatus.NONE,
            timestamp=tx_time.isoformat()
        ))

    # Write files to disk (gracefully skip in read-only serverless environments like Vercel)
    try:
        with open(os.path.join(output_dir, "oms_orders.json"), "w", encoding="utf-8") as f:
            json.dump([o.model_dump() if hasattr(o, "model_dump") else o.dict() for o in oms_orders], f, indent=2)

        with open(os.path.join(output_dir, "gateway_settlements.json"), "w", encoding="utf-8") as f:
            json.dump([g.model_dump() if hasattr(g, "model_dump") else g.dict() for g in gateway_records], f, indent=2)

        with open(os.path.join(output_dir, "bank_statement.csv"), "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["entry_id", "date", "utr", "narration", "credit", "debit", "balance", "channel"])
            for b in bank_entries:
                writer.writerow([b.entry_id, b.date, b.utr or "", b.narration, b.credit, b.debit, b.balance, b.channel])
    except Exception:
        pass

    return oms_orders, gateway_records, bank_entries


if __name__ == "__main__":
    generate_synthetic_dataset()

