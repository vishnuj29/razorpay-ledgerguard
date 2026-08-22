"""
FastAPI Server & REST API for LedgerGuard.
Serves reconciliation engine, exception manager, and interactive web dashboard.
"""

import os
import time
import io
import csv
from typing import List, Optional, Dict, Any, Tuple
from fastapi import FastAPI, Query, HTTPException, Response
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.generator.synthetic_data import generate_synthetic_dataset
from backend.engine.deterministic import DeterministicMatcher
from backend.engine.ai_resolver import AIExceptionResolver
from backend.engine.audit_trail import AuditTrailEngine
from backend.models.schema import (
    OMSOrder,
    GatewaySettlementRecord,
    BankStatementEntry,
    ReconciliationRecord,
    BatchSummary,
    MatchType,
    AnomalyCategory,
)

app = FastAPI(
    title="LedgerGuard API",
    description="3-Way Autonomous Financial Reconciliation & Exception Resolver API",
    version="1.0.0"
)

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)

@app.get("/v1/models", include_in_schema=False)
@app.get("/models", include_in_schema=False)
def dummy_models():
    return {"object": "list", "data": []}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global in-memory state for fast interactive demo
STATE = {
    "oms_orders": [],
    "gateway_records": [],
    "bank_entries": [],
    "reconciliation_records": [],
    "batch_summary": None,
    "last_run_time": None
}


def run_pipeline(seed: int = 42) -> Tuple[List[ReconciliationRecord], BatchSummary]:
    oms, gateway, bank = generate_synthetic_dataset(seed=seed)
    STATE["oms_orders"] = oms
    STATE["gateway_records"] = gateway
    STATE["bank_entries"] = bank

    start_time = time.time()
    
    # Layer 1
    matcher = DeterministicMatcher(mdr_rate=0.02, gst_rate=0.18)
    reconciled_l1, unres_oms, unres_gateway, unres_bank = matcher.match(oms, gateway, bank)

    # Layer 2
    resolver = AIExceptionResolver(confidence_threshold=0.85)
    auto_resolved, flagged_exceptions = resolver.resolve_exceptions(unres_oms, unres_gateway, unres_bank)

    # Layer 3
    all_records = reconciled_l1 + auto_resolved + flagged_exceptions
    audit_engine = AuditTrailEngine()
    sealed = audit_engine.seal_audit_trail(all_records)
    elapsed = time.time() - start_time

    summary = audit_engine.generate_batch_summary("BATCH_DEMO_2026", sealed, elapsed)
    
    STATE["reconciliation_records"] = sealed
    STATE["batch_summary"] = summary
    STATE["last_run_time"] = time.strftime("%Y-%m-%d %H:%M:%S")

    return sealed, summary


# Initialize state with default dataset
run_pipeline(seed=42)


@app.get("/api/summary", response_model=BatchSummary)
def get_summary():
    if not STATE["batch_summary"]:
        run_pipeline(seed=42)
    return STATE["batch_summary"]


@app.post("/api/run-reconciliation")
def trigger_reconciliation(seed: int = Query(42, description="Random seed for synthetic batch")):
    sealed, summary = run_pipeline(seed=seed)
    return {
        "status": "success",
        "summary": summary,
        "records_count": len(sealed)
    }


@app.get("/api/records")
def get_records(
    match_type: Optional[str] = None,
    anomaly_category: Optional[str] = None,
    requires_human_review: Optional[bool] = None,
    search: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
):
    records = STATE["reconciliation_records"]
    
    if match_type:
        records = [r for r in records if r.match_type.value == match_type]
    if anomaly_category:
        records = [r for r in records if r.anomaly_category.value == anomaly_category]
    if requires_human_review is not None:
        records = [r for r in records if r.requires_human_review == requires_human_review]
    if search:
        search_lower = search.lower()
        records = [
            r for r in records
            if (r.order_id and search_lower in r.order_id.lower())
            or (r.payment_id and search_lower in r.payment_id.lower())
            or (r.utr and search_lower in r.utr.lower())
            or (r.recon_id and search_lower in r.recon_id.lower())
        ]

    return {
        "total": len(records),
        "limit": limit,
        "offset": offset,
        "records": records[offset:offset + limit]
    }


@app.get("/api/exceptions")
def get_exceptions():
    exceptions = [r for r in STATE["reconciliation_records"] if r.match_type == MatchType.FLAGGED_EXCEPTION]
    return {
        "count": len(exceptions),
        "exceptions": exceptions
    }


class ManualResolveRequest(BaseModel):
    recon_id: str
    action: str  # "APPROVE_JOURNAL", "DISMISS", "OVERRIDE"
    notes: str


@app.post("/api/resolve-manual")
def manual_resolve(req: ManualResolveRequest):
    for rec in STATE["reconciliation_records"]:
        if rec.recon_id == req.recon_id:
            rec.requires_human_review = False
            rec.is_reconciled = True
            rec.ai_reasoning = f"[MANUAL SIGN-OFF] Action: {req.action}. Notes: {req.notes}. Previous: {rec.ai_reasoning}"
            return {"status": "success", "updated_record": rec}
    raise HTTPException(status_code=404, detail="Record not found")


@app.get("/api/export-csv")
def export_csv():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Recon_ID", "Order_ID", "Payment_ID", "UTR", "Gross_Amount",
        "Fee_MDR", "Tax_GST", "Net_Settled", "Bank_Credited", "Variance",
        "Match_Type", "Category", "Confidence", "Reconciled", "Human_Review", "Audit_Hash"
    ])
    
    for r in STATE["reconciliation_records"]:
        writer.writerow([
            r.recon_id, r.order_id or "", r.payment_id or "", r.utr or "",
            r.gross_amount, r.fee_deducted, r.tax_deducted, r.net_settled,
            r.bank_credited, r.variance, r.match_type.value, r.anomaly_category.value,
            r.confidence_score, r.is_reconciled, r.requires_human_review, r.audit_hash
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=ledgerguard_reconciliation_report.csv"}
    )


def find_frontend_file(filename: str) -> Optional[str]:
    candidates = [
        os.path.join(os.path.dirname(__file__), "..", "frontend", filename),
        os.path.join(os.getcwd(), "frontend", filename),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", filename),
        os.path.join("/var/task/frontend", filename),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


@app.get("/", response_class=HTMLResponse)
def index():
    path = find_frontend_file("index.html")
    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>LedgerGuard API Online</h1>"


@app.get("/static/style.css")
def get_css():
    path = find_frontend_file("style.css")
    if path and os.path.exists(path):
        return FileResponse(path, media_type="text/css")
    return Response(content="", media_type="text/css")


@app.get("/static/app.js")
def get_js():
    path = find_frontend_file("app.js")
    if path and os.path.exists(path):
        return FileResponse(path, media_type="application/javascript")
    return Response(content="", media_type="application/javascript")


# Mount static if directory exists
try:
    frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
    if os.path.exists(frontend_dir):
        app.mount("/static", StaticFiles(directory=frontend_dir), name="static")
except Exception:
    pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app:app", host="0.0.0.0", port=8000, reload=True)

