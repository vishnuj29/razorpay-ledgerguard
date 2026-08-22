// LedgerGuard Frontend Controller

let allRecords = [];
let batchSummary = null;

// DOM Elements
const metricMatchRate = document.getElementById('metric-match-rate');
const metricMatchSub = document.getElementById('metric-match-sub');
const metricDeterministic = document.getElementById('metric-deterministic-count');
const metricAI = document.getElementById('metric-ai-count');
const metricExceptions = document.getElementById('metric-exceptions-count');
const metricDiscrepancySum = document.getElementById('metric-discrepancy-sum');
const metricThroughput = document.getElementById('metric-throughput');
const metricTime = document.getElementById('metric-time');

const badgeAll = document.getElementById('badge-all');
const badgeAI = document.getElementById('badge-ai');
const badgeExceptions = document.getElementById('badge-exceptions');

const recordsTableBody = document.getElementById('records-table-body');
const aiCardsContainer = document.getElementById('ai-cards-container');
const exceptionCardsContainer = document.getElementById('exception-cards-container');
const auditListContainer = document.getElementById('audit-list-container');
const rootAuditHash = document.getElementById('root-audit-hash');

const searchInput = document.getElementById('search-input');
const filterMatchType = document.getElementById('filter-match-type');
const filterCategory = document.getElementById('filter-category');

const btnReRun = document.getElementById('btn-re-run');
const btnExportCsv = document.getElementById('btn-export-csv');
const btnCopyHash = document.getElementById('btn-copy-hash');

// Tabs
const tabBtns = document.querySelectorAll('.tab-btn');
const tabContents = document.querySelectorAll('.tab-content');

// Drawer
const drawerOverlay = document.getElementById('drawer-overlay');
const recordDrawer = document.getElementById('record-drawer');
const drawerClose = document.getElementById('drawer-close');
const drawerBody = document.getElementById('drawer-body');
const drawerReconId = document.getElementById('drawer-recon-id');

// Fetch Initial Data
async function loadData() {
    try {
        const summaryRes = await fetch('/api/summary');
        batchSummary = await summaryRes.json();

        const recordsRes = await fetch('/api/records?limit=200');
        const recordsData = await recordsRes.json();
        allRecords = recordsData.records;

        renderSummary();
        renderRecordsTable();
        renderAICards();
        renderExceptionCards();
        renderAuditChain();
    } catch (err) {
        console.error("Failed to load LedgerGuard data:", err);
    }
}

// Render Summary Metrics
function renderSummary() {
    if (!batchSummary) return;

    metricMatchRate.innerText = `${batchSummary.match_rate_percentage}%`;
    const recCount = batchSummary.exact_match_count + batchSummary.batch_match_count + batchSummary.ai_resolved_count;
    metricMatchSub.innerText = `${recCount} of ${batchSummary.total_records_processed} records reconciled`;

    metricDeterministic.innerText = batchSummary.exact_match_count + batchSummary.batch_match_count;
    metricAI.innerText = batchSummary.ai_resolved_count;
    metricExceptions.innerText = batchSummary.flagged_exception_count;
    metricDiscrepancySum.innerText = `Rs. ${batchSummary.total_discrepancy_amount.toLocaleString('en-IN', {minimumFractionDigits: 2})} in dispute/hold`;

    const throughput = Math.round(batchSummary.total_records_processed / Math.max(batchSummary.execution_time_seconds, 0.001));
    metricThroughput.innerText = `${throughput} rec/s`;
    metricTime.innerText = `Execution: ${batchSummary.execution_time_seconds}s`;

    badgeAll.innerText = batchSummary.total_records_processed;
    badgeAI.innerText = batchSummary.ai_resolved_count;
    badgeExceptions.innerText = batchSummary.flagged_exception_count;

    rootAuditHash.innerText = batchSummary.audit_chain_root_hash;
}

// Format Currency
function formatINR(val) {
    return `Rs. ${(val || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

// Render Table
function renderRecordsTable() {
    const searchTerm = searchInput.value.toLowerCase().trim();
    const matchTypeFilter = filterMatchType.value;
    const categoryFilter = filterCategory.value;

    const filtered = allRecords.filter(r => {
        if (matchTypeFilter && r.match_type !== matchTypeFilter) return false;
        if (categoryFilter && r.anomaly_category !== categoryFilter) return false;
        if (searchTerm) {
            const matchesId = (r.order_id && r.order_id.toLowerCase().includes(searchTerm)) ||
                              (r.payment_id && r.payment_id.toLowerCase().includes(searchTerm)) ||
                              (r.utr && r.utr.toLowerCase().includes(searchTerm)) ||
                              (r.recon_id && r.recon_id.toLowerCase().includes(searchTerm));
            if (!matchesId) return false;
        }
        return true;
    });

    recordsTableBody.innerHTML = filtered.map(r => {
        let pillClass = 'pill-exact';
        if (r.match_type === 'BATCH_1_TO_N') pillClass = 'pill-batch';
        else if (r.match_type === 'AI_RESOLVED') pillClass = 'pill-ai';
        else if (r.match_type === 'FLAGGED_EXCEPTION') pillClass = 'pill-exception';

        return `
            <tr onclick="openDrawer('${r.recon_id}')">
                <td class="font-mono" style="font-weight: 600; color: var(--accent-blue);">${r.recon_id}</td>
                <td>
                    <div style="font-weight: 600;">${r.order_id || '—'}</div>
                    <div class="font-mono" style="font-size: 11px; color: var(--text-muted);">${r.payment_id || '—'}</div>
                </td>
                <td class="font-mono" style="font-size: 11px;">${r.utr || '—'}</td>
                <td class="font-mono">${formatINR(r.gross_amount)}</td>
                <td class="font-mono" style="color: var(--text-secondary);">${formatINR(r.fee_deducted + r.tax_deducted)}</td>
                <td class="font-mono" style="font-weight: 600; color: var(--accent-green);">${formatINR(r.net_settled)}</td>
                <td class="font-mono" style="color: #93C5FD;">${formatINR(r.bank_credited)}</td>
                <td><span class="pill ${pillClass}">${r.match_type}</span></td>
                <td><span style="font-size: 12px; font-weight: 500;">${r.anomaly_category.replace(/_/g, ' ')}</span></td>
                <td class="font-mono" style="font-weight: 700;">${Math.round(r.confidence_score * 100)}%</td>
                <td>${r.is_reconciled ? '<span style="color: var(--accent-green);">● Reconciled</span>' : '<span style="color: var(--accent-red);">▲ Review</span>'}</td>
            </tr>
        `;
    }).join('');
}

// Render AI Resolution Cards
function renderAICards() {
    const aiRecords = allRecords.filter(r => r.match_type === 'AI_RESOLVED');
    aiCardsContainer.innerHTML = aiRecords.map(r => `
        <div class="recon-card">
            <div class="card-top">
                <div class="card-title">${r.order_id || r.recon_id}</div>
                <span class="pill pill-ai">Confidence: ${Math.round(r.confidence_score * 100)}%</span>
            </div>
            <div style="display: flex; gap: 20px; font-size: 12px;">
                <div><span style="color: var(--text-muted);">Payment ID:</span> <span class="font-mono">${r.payment_id || '—'}</span></div>
                <div><span style="color: var(--text-muted);">Gross:</span> <span class="font-mono">${formatINR(r.gross_amount)}</span></div>
                <div><span style="color: var(--text-muted);">Net Settled:</span> <span class="font-mono" style="color: var(--accent-green);">${formatINR(r.net_settled)}</span></div>
            </div>
            <div class="card-diagnosis">
                <strong>🤖 AI Diagnostic:</strong> ${r.ai_reasoning}
            </div>
            ${r.journal_entry ? `
                <div class="journal-box">
                    <div style="color: #94A3B8; font-weight: 600; margin-bottom: 6px;">COMPLIANT JOURNAL ADJUSTMENT:</div>
                    <div class="journal-row"><span>Dr ${r.journal_entry.debit_account}</span> <span>${formatINR(r.journal_entry.amount)}</span></div>
                    <div class="journal-row" style="padding-left: 14px;"><span>Cr ${r.journal_entry.credit_account}</span> <span>${formatINR(r.journal_entry.amount)}</span></div>
                </div>
            ` : ''}
            <div style="font-size: 11px; color: var(--text-muted); font-family: var(--font-mono); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                SHA-256: ${r.audit_hash}
            </div>
        </div>
    `).join('');
}

// Render Exception Queue Cards
function renderExceptionCards() {
    const exceptions = allRecords.filter(r => r.match_type === 'FLAGGED_EXCEPTION');
    exceptionCardsContainer.innerHTML = exceptions.map(r => `
        <div class="recon-card" style="border-color: rgba(239, 68, 68, 0.3);">
            <div class="card-top">
                <div class="card-title" style="color: #F87171;">⚠️ ${r.anomaly_category.replace(/_/g, ' ')}</div>
                <span class="pill pill-exception">Action Required</span>
            </div>
            <div style="display: flex; gap: 20px; font-size: 12.5px;">
                <div><span style="color: var(--text-muted);">Reference:</span> <span class="font-mono">${r.order_id || r.bank_entry_id || r.payment_id}</span></div>
                <div><span style="color: var(--text-muted);">Discrepancy:</span> <span class="font-mono" style="font-weight: 700; color: #FCA5A5;">${formatINR(r.variance)}</span></div>
            </div>
            <div class="card-diagnosis exception-border">
                <strong>Policy Stop Rule:</strong> ${r.ai_reasoning}
            </div>
            ${r.journal_entry ? `
                <div class="journal-box">
                    <div style="color: #94A3B8; font-weight: 600; margin-bottom: 6px;">PROPOSED PROVISIONING ENTRY:</div>
                    <div class="journal-row"><span>Dr ${r.journal_entry.debit_account}</span> <span>${formatINR(r.journal_entry.amount)}</span></div>
                    <div class="journal-row" style="padding-left: 14px;"><span>Cr ${r.journal_entry.credit_account}</span> <span>${formatINR(r.journal_entry.amount)}</span></div>
                </div>
            ` : ''}
            <div style="display: flex; gap: 10px; margin-top: 6px;">
                <button class="btn btn-secondary" style="flex: 1; font-size: 12px;" onclick="manualSignOff('${r.recon_id}', 'APPROVE_PROVISION')">
                    Approve Provision
                </button>
                <button class="btn btn-primary" style="flex: 1; font-size: 12px; background: #DC2626;" onclick="manualSignOff('${r.recon_id}', 'ESCALATE_DISPUTE_TEAM')">
                    Escalate to Ops
                </button>
            </div>
        </div>
    `).join('');
}

// Render Audit Chain
function renderAuditChain() {
    auditListContainer.innerHTML = allRecords.slice(0, 30).map((r, i) => `
        <div class="audit-item">
            <div>
                <span class="font-mono" style="color: var(--accent-blue); font-weight: 600;">Block #${i + 1}</span> —
                <span style="font-weight: 500;">${r.recon_id} (${r.anomaly_category})</span>
            </div>
            <div class="audit-hash-code">${r.audit_hash}</div>
        </div>
    `).join('');
}

// Open Drawer for detailed line inspection
function openDrawer(reconId) {
    const record = allRecords.find(r => r.recon_id === reconId);
    if (!record) return;

    drawerReconId.innerText = record.recon_id;
    drawerBody.innerHTML = `
        <div>
            <div class="detail-section-title">Reconciliation Overview</div>
            <div class="detail-box">
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                    <div><span style="color: var(--text-muted);">Status:</span> <strong>${record.is_reconciled ? 'Reconciled' : 'Unresolved Exception'}</strong></div>
                    <div><span style="color: var(--text-muted);">Match Type:</span> <strong>${record.match_type}</strong></div>
                    <div><span style="color: var(--text-muted);">Category:</span> <strong>${record.anomaly_category}</strong></div>
                    <div><span style="color: var(--text-muted);">Confidence Score:</span> <strong>${Math.round(record.confidence_score * 100)}%</strong></div>
                </div>
            </div>
        </div>

        <div>
            <div class="detail-section-title">3-Way Multi-Source Match Data</div>
            <div class="detail-box">
                <table style="width: 100%; font-size: 12px;">
                    <tr><td style="color: var(--text-muted); padding: 4px 0;">Merchant Order ID:</td><td class="font-mono">${record.order_id || '—'}</td></tr>
                    <tr><td style="color: var(--text-muted); padding: 4px 0;">Razorpay Payment ID:</td><td class="font-mono">${record.payment_id || '—'}</td></tr>
                    <tr><td style="color: var(--text-muted); padding: 4px 0;">Settlement Batch ID:</td><td class="font-mono">${record.settlement_id || '—'}</td></tr>
                    <tr><td style="color: var(--text-muted); padding: 4px 0;">Bank UTR / Line ID:</td><td class="font-mono">${record.utr || record.bank_entry_id || '—'}</td></tr>
                    <tr><td style="color: var(--text-muted); padding: 4px 0;">Gross Order Amount:</td><td class="font-mono">${formatINR(record.gross_amount)}</td></tr>
                    <tr><td style="color: var(--text-muted); padding: 4px 0;">MDR Gateway Fee:</td><td class="font-mono">${formatINR(record.fee_deducted)}</td></tr>
                    <tr><td style="color: var(--text-muted); padding: 4px 0;">GST (18% on MDR):</td><td class="font-mono">${formatINR(record.tax_deducted)}</td></tr>
                    <tr><td style="color: var(--text-muted); padding: 4px 0;">Net Gateway Payout:</td><td class="font-mono" style="color: var(--accent-green); font-weight: 700;">${formatINR(record.net_settled)}</td></tr>
                    <tr><td style="color: var(--text-muted); padding: 4px 0;">Bank Received Credit:</td><td class="font-mono" style="color: #93C5FD; font-weight: 700;">${formatINR(record.bank_credited)}</td></tr>
                    <tr><td style="color: var(--text-muted); padding: 4px 0;">Variance / Variance Risk:</td><td class="font-mono" style="color: #F87171; font-weight: 700;">${formatINR(record.variance)}</td></tr>
                </table>
            </div>
        </div>

        <div>
            <div class="detail-section-title">Diagnostic Reasoning & Audit Trail</div>
            <div class="detail-box" style="line-height: 1.5;">
                <p style="margin-bottom: 10px;">${record.ai_reasoning || 'Reconciled via Layer 1 deterministic mathematical rule engine.'}</p>
                <div style="font-size: 11px; color: var(--text-muted); font-family: var(--font-mono); word-break: break-all;">
                    SHA-256 HASH: ${record.audit_hash}
                </div>
            </div>
        </div>
    `;

    drawerOverlay.classList.add('open');
    recordDrawer.classList.add('open');
}

function closeDrawer() {
    drawerOverlay.classList.remove('open');
    recordDrawer.classList.remove('open');
}

// Manual sign-off action
async function manualSignOff(reconId, action) {
    try {
        const res = await fetch('/api/resolve-manual', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                recon_id: reconId,
                action: action,
                notes: "Signed off by Finance Ops Controller during batch review."
            })
        });
        if (res.ok) {
            await loadData();
        }
    } catch (e) {
        console.error("Sign-off error:", e);
    }
}

// Event Listeners
tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        tabBtns.forEach(b => b.classList.remove('active'));
        tabContents.forEach(c => c.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById(`tab-${btn.dataset.tab}`).classList.add('active');
    });
});

searchInput.addEventListener('input', renderRecordsTable);
filterMatchType.addEventListener('change', renderRecordsTable);
filterCategory.addEventListener('change', renderRecordsTable);

drawerClose.addEventListener('click', closeDrawer);
drawerOverlay.addEventListener('click', closeDrawer);

btnReRun.addEventListener('click', async () => {
    btnReRun.disabled = true;
    btnReRun.innerHTML = 'Running...';
    const randomSeed = Math.floor(Math.random() * 10000);
    await fetch(`/api/run-reconciliation?seed=${randomSeed}`, { method: 'POST' });
    await loadData();
    btnReRun.disabled = false;
    btnReRun.innerHTML = `
        <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>
        Run Batch Simulation
    `;
});

btnExportCsv.addEventListener('click', () => {
    window.location.href = '/api/export-csv';
});

btnCopyHash.addEventListener('click', () => {
    if (batchSummary && batchSummary.audit_chain_root_hash) {
        navigator.clipboard.writeText(batchSummary.audit_chain_root_hash);
        btnCopyHash.innerText = 'Copied!';
        setTimeout(() => { btnCopyHash.innerText = 'Copy Root Hash'; }, 2000);
    }
});

// Initialize on page load
loadData();
