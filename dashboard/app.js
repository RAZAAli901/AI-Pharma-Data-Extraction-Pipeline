/**
 * PharmaPipeline — Dashboard Application
 *
 * Loads pipeline report JSON, renders KPI cards, charts, drug asset cards,
 * and a sortable/filterable records table.
 */

// ── State ────────────────────────────────────────────────────────────────

const state = {
    records: [],
    pipelineRuns: [],
    currentSort: { column: null, direction: 'asc' },
    charts: {},
};

// ── Chart Color Palette ──────────────────────────────────────────────────

const COLORS = {
    blue:    { bg: 'rgba(59, 130, 246, 0.6)',  border: '#3b82f6' },
    cyan:    { bg: 'rgba(6, 182, 212, 0.6)',   border: '#06b6d4' },
    violet:  { bg: 'rgba(139, 92, 246, 0.6)',  border: '#8b5cf6' },
    emerald: { bg: 'rgba(16, 185, 129, 0.6)',  border: '#10b981' },
    amber:   { bg: 'rgba(245, 158, 11, 0.6)',  border: '#f59e0b' },
    rose:    { bg: 'rgba(244, 63, 94, 0.6)',   border: '#f43f5e' },
    indigo:  { bg: 'rgba(99, 102, 241, 0.6)',  border: '#6366f1' },
    slate:   { bg: 'rgba(100, 116, 139, 0.6)', border: '#64748b' },
};

const COLOR_LIST = Object.values(COLORS);

const TYPE_STYLES = {
    'Drug Asset':                { css: 'type-drug',        color: COLORS.violet },
    'Clinical Insight':          { css: 'type-clinical',     color: COLORS.cyan },
    'Competitive Intelligence':  { css: 'type-competitive',  color: COLORS.amber },
    'Regulatory Update':         { css: 'type-regulatory',   color: COLORS.emerald },
    'Market Analysis':           { css: 'type-market',       color: COLORS.rose },
    'General Insight':           { css: 'type-general',      color: COLORS.slate },
};


// ── Initialization ───────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    bindEvents();
    initCharts();
    loadDemoDataIfAvailable();
});


function bindEvents() {
    // File load
    document.getElementById('btn-load-json').addEventListener('click', () => {
        document.getElementById('file-input').click();
    });
    document.getElementById('file-input').addEventListener('change', handleFileLoad);

    // Refresh
    document.getElementById('btn-refresh').addEventListener('click', () => {
        if (state.records.length > 0) renderAll();
    });

    // Export
    document.getElementById('btn-export').addEventListener('click', handleExport);

    // Table search
    document.getElementById('table-search').addEventListener('input', filterTable);

    // Type filter
    document.getElementById('type-filter').addEventListener('change', filterTable);

    // Drug search
    document.getElementById('drug-search').addEventListener('input', filterDrugs);

    // Table sorting
    document.querySelectorAll('.data-table th[data-sort]').forEach(th => {
        th.addEventListener('click', () => handleSort(th.dataset.sort));
    });

    // Modal
    document.getElementById('modal-close').addEventListener('click', closeModal);
    document.getElementById('record-modal').addEventListener('click', (e) => {
        if (e.target === e.currentTarget) closeModal();
    });
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeModal();
    });
}


// ── Data Loading ─────────────────────────────────────────────────────────

function handleFileLoad(e) {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (evt) => {
        try {
            const data = JSON.parse(evt.target.result);
            processLoadedData(data);
            updateStatus(`Loaded: ${file.name}`, true);
        } catch (err) {
            updateStatus(`Error: Invalid JSON — ${err.message}`, false);
        }
    };
    reader.readAsText(file);
    e.target.value = ''; // Allow re-loading same file
}


function processLoadedData(data) {
    // Handle both pipeline report format and direct records array
    if (data.file_results) {
        // Pipeline report format
        state.records = [];
        state.pipelineRuns.push(data);

        // Extract records from file results
        if (data.file_results) {
            data.file_results.forEach(fr => {
                if (fr.records) {
                    state.records.push(...fr.records);
                }
            });
        }

        // If no embedded records, check for a top-level "records" key
        if (state.records.length === 0 && data.records) {
            state.records = data.records;
        }
    } else if (Array.isArray(data)) {
        state.records = data;
    } else if (data.records && Array.isArray(data.records)) {
        state.records = data.records;
    }

    renderAll();
}


function loadDemoDataIfAvailable() {
    // Try loading demo data from a local file (for development)
    fetch('demo_data.json')
        .then(res => res.ok ? res.json() : null)
        .then(data => {
            if (data) {
                processLoadedData(data);
                updateStatus('Loaded demo data', true);
            }
        })
        .catch(() => { /* No demo data, that's fine */ });
}


// ── Rendering ────────────────────────────────────────────────────────────

function renderAll() {
    renderKPIs();
    renderCharts();
    renderDrugCards();
    renderTable();
    renderPipelineRuns();
    populateTypeFilter();
    document.getElementById('last-updated').textContent = new Date().toLocaleTimeString();
}


// ── KPIs ─────────────────────────────────────────────────────────────────

function renderKPIs() {
    const records = state.records;
    const lastRun = state.pipelineRuns[state.pipelineRuns.length - 1];

    animateValue('kpi-files-value', lastRun?.files_processed ?? 0);
    animateValue('kpi-records-value', records.length);
    animateValue('kpi-validated-value', lastRun?.total_records_validated ?? records.length);

    // Average confidence
    if (records.length > 0) {
        const avgConf = records.reduce((sum, r) => sum + (r.confidence_score || 0), 0) / records.length;
        document.getElementById('kpi-confidence-value').textContent = (avgConf * 100).toFixed(1) + '%';
    } else {
        document.getElementById('kpi-confidence-value').textContent = '—';
    }
}


function animateValue(elementId, targetValue) {
    const el = document.getElementById(elementId);
    const duration = 600;
    const start = parseInt(el.textContent) || 0;
    const startTime = performance.now();

    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
        const current = Math.round(start + (targetValue - start) * eased);
        el.textContent = current;
        if (progress < 1) requestAnimationFrame(update);
    }

    requestAnimationFrame(update);
}


// ── Charts ───────────────────────────────────────────────────────────────

function initCharts() {
    // Global Chart.js defaults
    Chart.defaults.color = '#94a3b8';
    Chart.defaults.font.family = "'Inter', sans-serif";
    Chart.defaults.font.size = 12;
    Chart.defaults.plugins.legend.labels.boxWidth = 12;
    Chart.defaults.plugins.legend.labels.padding = 16;
}


function renderCharts() {
    renderRecordTypesChart();
    renderTherapyAreasChart();
    renderConfidenceChart();
}


function renderRecordTypesChart() {
    const counts = {};
    state.records.forEach(r => {
        const type = r.record_type || 'Unknown';
        counts[type] = (counts[type] || 0) + 1;
    });

    const labels = Object.keys(counts);
    const data = Object.values(counts);
    const colors = labels.map(l => (TYPE_STYLES[l]?.color || COLORS.slate));

    if (state.charts.recordTypes) state.charts.recordTypes.destroy();

    const ctx = document.getElementById('chart-record-types').getContext('2d');
    state.charts.recordTypes = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels,
            datasets: [{
                data,
                backgroundColor: colors.map(c => c.bg),
                borderColor: colors.map(c => c.border),
                borderWidth: 2,
                hoverOffset: 8,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '65%',
            plugins: {
                legend: { position: 'bottom', labels: { padding: 12 } },
            },
        },
    });
}


function renderTherapyAreasChart() {
    const counts = {};
    state.records.forEach(r => {
        const ta = r.drug_asset?.therapy_area || r.therapy_area || 'Unspecified';
        counts[ta] = (counts[ta] || 0) + 1;
    });

    const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 8);
    const labels = sorted.map(([k]) => k);
    const data = sorted.map(([, v]) => v);

    if (state.charts.therapyAreas) state.charts.therapyAreas.destroy();

    const ctx = document.getElementById('chart-therapy-areas').getContext('2d');
    state.charts.therapyAreas = new Chart(ctx, {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                data,
                backgroundColor: labels.map((_, i) => COLOR_LIST[i % COLOR_LIST.length].bg),
                borderColor: labels.map((_, i) => COLOR_LIST[i % COLOR_LIST.length].border),
                borderWidth: 1,
                borderRadius: 6,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            indexAxis: 'y',
            plugins: { legend: { display: false } },
            scales: {
                x: {
                    grid: { color: 'rgba(255,255,255,0.04)' },
                    ticks: { stepSize: 1 },
                },
                y: {
                    grid: { display: false },
                },
            },
        },
    });
}


function renderConfidenceChart() {
    const buckets = { '90-100%': 0, '70-89%': 0, '50-69%': 0, '<50%': 0 };
    state.records.forEach(r => {
        const c = (r.confidence_score || 0) * 100;
        if (c >= 90) buckets['90-100%']++;
        else if (c >= 70) buckets['70-89%']++;
        else if (c >= 50) buckets['50-69%']++;
        else buckets['<50%']++;
    });

    if (state.charts.confidence) state.charts.confidence.destroy();

    const ctx = document.getElementById('chart-confidence').getContext('2d');
    state.charts.confidence = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: Object.keys(buckets),
            datasets: [{
                data: Object.values(buckets),
                backgroundColor: [
                    COLORS.emerald.bg, COLORS.blue.bg, COLORS.amber.bg, COLORS.rose.bg,
                ],
                borderColor: [
                    COLORS.emerald.border, COLORS.blue.border, COLORS.amber.border, COLORS.rose.border,
                ],
                borderWidth: 1,
                borderRadius: 6,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: {
                    grid: { color: 'rgba(255,255,255,0.04)' },
                    ticks: { stepSize: 1 },
                },
                x: { grid: { display: false } },
            },
        },
    });
}


// ── Drug Asset Cards ─────────────────────────────────────────────────────

function renderDrugCards(filterText = '') {
    const grid = document.getElementById('drug-grid');
    const drugRecords = state.records.filter(r => r.drug_asset);

    if (drugRecords.length === 0) {
        grid.innerHTML = `
            <div class="empty-state" id="drug-empty">
                <div class="empty-icon">🧪</div>
                <p>No drug asset data available</p>
                <span>Records without drug_asset data are shown only in the table</span>
            </div>`;
        return;
    }

    const filtered = filterText
        ? drugRecords.filter(r =>
            (r.drug_asset.molecule_name || '').toLowerCase().includes(filterText) ||
            (r.drug_asset.sponsor_company || '').toLowerCase().includes(filterText) ||
            (r.drug_asset.therapy_area || '').toLowerCase().includes(filterText)
        )
        : drugRecords;

    grid.innerHTML = filtered.map((r, i) => {
        const da = r.drug_asset;
        const confClass = r.confidence_score >= 0.9 ? 'confidence-high'
                        : r.confidence_score >= 0.7 ? 'confidence-medium'
                        : 'confidence-low';

        const tags = [];
        if (da.therapy_area)       tags.push(`<span class="drug-tag drug-tag--therapy">${da.therapy_area}</span>`);
        if (da.drug_class)         tags.push(`<span class="drug-tag">${da.drug_class}</span>`);
        if (r.clinical_insight?.trial_phase) tags.push(`<span class="drug-tag drug-tag--phase">${r.clinical_insight.trial_phase}</span>`);
        if (da.mechanism_of_action) tags.push(`<span class="drug-tag">${da.mechanism_of_action}</span>`);

        return `
            <div class="drug-card animate-in" style="animation-delay: ${i * 60}ms" onclick="openModal(${state.records.indexOf(r)})">
                <div class="drug-card-header">
                    <div>
                        <div class="drug-name">${escHtml(da.molecule_name)}</div>
                        <div class="drug-company">${escHtml(da.sponsor_company || '—')}</div>
                    </div>
                    <span class="confidence-badge ${confClass}">${(r.confidence_score * 100).toFixed(0)}%</span>
                </div>
                <div class="drug-meta">${tags.join('')}</div>
                <div class="drug-summary">${escHtml(r.raw_summary || '')}</div>
            </div>`;
    }).join('');
}


function filterDrugs() {
    const text = document.getElementById('drug-search').value.toLowerCase();
    renderDrugCards(text);
}


// ── Records Table ────────────────────────────────────────────────────────

function renderTable() {
    const tbody = document.getElementById('records-tbody');

    if (state.records.length === 0) {
        tbody.innerHTML = `
            <tr class="empty-row">
                <td colspan="7">
                    <div class="empty-state">
                        <div class="empty-icon">📊</div>
                        <p>No records to display</p>
                    </div>
                </td>
            </tr>`;
        return;
    }

    tbody.innerHTML = state.records.map((r, i) => {
        const typeStyle = TYPE_STYLES[r.record_type] || TYPE_STYLES['General Insight'];
        const confClass = r.confidence_score >= 0.9 ? 'confidence-high'
                        : r.confidence_score >= 0.7 ? 'confidence-medium'
                        : 'confidence-low';

        return `
            <tr onclick="openModal(${i})">
                <td>${escHtml(r.source_file || '—')}</td>
                <td><span class="type-badge ${typeStyle.css}">${escHtml(r.record_type || '—')}</span></td>
                <td class="cell-molecule">${escHtml(r.drug_asset?.molecule_name || '—')}</td>
                <td>${escHtml(r.drug_asset?.therapy_area || '—')}</td>
                <td class="cell-confidence ${confClass}">${r.confidence_score != null ? (r.confidence_score * 100).toFixed(0) + '%' : '—'}</td>
                <td>${escHtml(r.slide_range || '—')}</td>
                <td class="cell-summary" title="${escAttr(r.raw_summary || '')}">${escHtml(r.raw_summary || '—')}</td>
            </tr>`;
    }).join('');
}


function filterTable() {
    const search = document.getElementById('table-search').value.toLowerCase();
    const typeFilter = document.getElementById('type-filter').value;
    const rows = document.querySelectorAll('#records-tbody tr:not(.empty-row)');

    rows.forEach((row, i) => {
        const record = state.records[i];
        if (!record) return;

        const matchesSearch = !search ||
            JSON.stringify(record).toLowerCase().includes(search);
        const matchesType = !typeFilter || record.record_type === typeFilter;

        row.style.display = (matchesSearch && matchesType) ? '' : 'none';
    });
}


function populateTypeFilter() {
    const select = document.getElementById('type-filter');
    const types = [...new Set(state.records.map(r => r.record_type).filter(Boolean))];

    // Keep the "All Types" option
    select.innerHTML = '<option value="">All Types</option>';
    types.sort().forEach(type => {
        const opt = document.createElement('option');
        opt.value = type;
        opt.textContent = type;
        select.appendChild(opt);
    });
}


function handleSort(column) {
    const { currentSort } = state;
    const newDir = (currentSort.column === column && currentSort.direction === 'asc') ? 'desc' : 'asc';
    state.currentSort = { column, direction: newDir };

    // Update header styles
    document.querySelectorAll('.data-table th').forEach(th => {
        th.classList.remove('sort-asc', 'sort-desc');
    });
    const th = document.querySelector(`.data-table th[data-sort="${column}"]`);
    if (th) th.classList.add(newDir === 'asc' ? 'sort-asc' : 'sort-desc');

    // Sort records
    state.records.sort((a, b) => {
        let valA = getNestedValue(a, column) || '';
        let valB = getNestedValue(b, column) || '';

        if (typeof valA === 'number' && typeof valB === 'number') {
            return newDir === 'asc' ? valA - valB : valB - valA;
        }
        valA = String(valA).toLowerCase();
        valB = String(valB).toLowerCase();
        return newDir === 'asc' ? valA.localeCompare(valB) : valB.localeCompare(valA);
    });

    renderTable();
}


function getNestedValue(obj, key) {
    if (key === 'molecule_name') return obj.drug_asset?.molecule_name;
    if (key === 'therapy_area') return obj.drug_asset?.therapy_area;
    return obj[key];
}


// ── Pipeline Runs ────────────────────────────────────────────────────────

function renderPipelineRuns() {
    const list = document.getElementById('runs-list');

    if (state.pipelineRuns.length === 0) {
        list.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">🕐</div>
                <p>No pipeline runs loaded</p>
            </div>`;
        return;
    }

    list.innerHTML = state.pipelineRuns.map(run => {
        const hasFails = (run.files_failed || 0) > 0;
        const statusClass = hasFails ? 'run-status-icon--partial' : 'run-status-icon--success';
        const statusIcon = hasFails ? '⚠️' : '✅';
        const ts = run.started_at ? new Date(run.started_at).toLocaleString() : '—';

        return `
            <div class="run-item">
                <div class="run-status-icon ${statusClass}">${statusIcon}</div>
                <div class="run-info">
                    <div class="run-timestamp">${ts}</div>
                    <div class="run-details">
                        ${run.files_discovered || 0} files discovered
                        ${run.errors?.length ? ` · ${run.errors.length} error(s)` : ''}
                    </div>
                </div>
                <div class="run-stats">
                    <div class="run-stat">
                        <div class="run-stat-value">${run.files_processed || 0}</div>
                        <div class="run-stat-label">Processed</div>
                    </div>
                    <div class="run-stat">
                        <div class="run-stat-value">${run.total_records_extracted || 0}</div>
                        <div class="run-stat-label">Extracted</div>
                    </div>
                    <div class="run-stat">
                        <div class="run-stat-value">${run.total_records_written || 0}</div>
                        <div class="run-stat-label">Written</div>
                    </div>
                </div>
            </div>`;
    }).join('');
}


// ── Modal ────────────────────────────────────────────────────────────────

function openModal(index) {
    const record = state.records[index];
    if (!record) return;

    const modal = document.getElementById('record-modal');
    const typeStyle = TYPE_STYLES[record.record_type] || TYPE_STYLES['General Insight'];

    document.getElementById('modal-title').textContent =
        record.drug_asset?.molecule_name || record.record_type || 'Record Detail';

    const badge = document.getElementById('modal-type-badge');
    badge.textContent = record.record_type || '—';
    badge.className = `modal-badge ${typeStyle.css}`;

    const body = document.getElementById('modal-body');
    let html = '';

    // Source info
    html += `<div class="modal-section">
        <div class="modal-section-title">Source Information</div>
        ${modalField('Source File', record.source_file)}
        ${modalField('Slide Range', record.slide_range)}
        ${modalField('Confidence', record.confidence_score != null ? (record.confidence_score * 100).toFixed(1) + '%' : '—')}
        ${modalField('Extracted', record.extraction_timestamp ? new Date(record.extraction_timestamp).toLocaleString() : '—')}
    </div>`;

    // Drug Asset
    if (record.drug_asset) {
        const da = record.drug_asset;
        html += `<div class="modal-section">
            <div class="modal-section-title">Drug Asset</div>
            ${modalField('Molecule', da.molecule_name)}
            ${modalField('Sponsor', da.sponsor_company)}
            ${modalField('Therapy Area', da.therapy_area)}
            ${modalField('Indication', da.indication)}
            ${modalField('Drug Class', da.drug_class)}
            ${modalField('MoA', da.mechanism_of_action)}
            ${modalField('Route', da.route_of_administration)}
        </div>`;
    }

    // Clinical Insight
    if (record.clinical_insight) {
        const ci = record.clinical_insight;
        html += `<div class="modal-section">
            <div class="modal-section-title">Clinical Insight</div>
            ${modalField('Phase', ci.trial_phase)}
            ${modalField('Status', ci.trial_status)}
            ${modalField('Trial ID', ci.trial_identifier)}
            ${modalField('Primary Endpoints', Array.isArray(ci.primary_endpoints) ? ci.primary_endpoints.join('; ') : ci.primary_endpoints)}
            ${modalField('Patient Population', ci.patient_population)}
            ${modalField('Enrollment', ci.enrollment_target)}
            ${modalField('Efficacy', ci.efficacy_data)}
            ${modalField('Safety', ci.safety_signals)}
        </div>`;
    }

    // Competitive Intel
    if (record.competitive_intel) {
        const comp = record.competitive_intel;
        html += `<div class="modal-section">
            <div class="modal-section-title">Competitive Intelligence</div>
            ${modalField('Positioning', comp.competitive_positioning)}
            ${modalField('Landscape', comp.market_landscape)}
            ${modalField('Differentiators', Array.isArray(comp.key_differentiators) ? comp.key_differentiators.join('; ') : comp.key_differentiators)}
            ${modalField('Competitors', Array.isArray(comp.competitors) ? comp.competitors.join(', ') : comp.competitors)}
            ${modalField('Market Size', comp.market_size_estimate)}
            ${modalField('Strategy', comp.strategic_implications)}
        </div>`;
    }

    // Regulatory
    if (record.regulatory_update) {
        const reg = record.regulatory_update;
        html += `<div class="modal-section">
            <div class="modal-section-title">Regulatory Update</div>
            ${modalField('Status', reg.approval_status)}
            ${modalField('Authority', reg.regulatory_authority)}
            ${modalField('Submission', reg.submission_date)}
            ${modalField('Approval', reg.approval_date)}
            ${modalField('Designations', Array.isArray(reg.designations) ? reg.designations.join(', ') : reg.designations)}
            ${modalField('PDUFA Date', reg.pdufa_date)}
        </div>`;
    }

    // Summary
    html += `<div class="modal-section">
        <div class="modal-section-title">Summary</div>
        <p style="font-size:0.85rem; color:var(--text-secondary); line-height:1.7;">${escHtml(record.raw_summary || '—')}</p>
    </div>`;

    // Key Takeaways
    if (record.key_takeaways && record.key_takeaways.length > 0) {
        html += `<div class="modal-section">
            <div class="modal-section-title">Key Takeaways</div>
            <ul class="modal-takeaways">
                ${record.key_takeaways.map(t => `<li>${escHtml(t)}</li>`).join('')}
            </ul>
        </div>`;
    }

    body.innerHTML = html;
    modal.classList.add('active');
    document.body.style.overflow = 'hidden';
}


function closeModal() {
    document.getElementById('record-modal').classList.remove('active');
    document.body.style.overflow = '';
}


function modalField(label, value) {
    const display = value != null && value !== '' ? escHtml(String(value)) : '<span style="color:var(--text-tertiary)">—</span>';
    return `<div class="modal-field">
        <span class="modal-field-label">${label}</span>
        <span class="modal-field-value">${display}</span>
    </div>`;
}


// ── Export ────────────────────────────────────────────────────────────────

function handleExport() {
    if (state.records.length === 0) {
        updateStatus('No data to export', false);
        return;
    }

    const data = JSON.stringify(state.records, null, 2);
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);

    const a = document.createElement('a');
    a.href = url;
    a.download = `pharma_extraction_${new Date().toISOString().slice(0, 10)}.json`;
    a.click();

    URL.revokeObjectURL(url);
    updateStatus('Exported records as JSON', true);
}


// ── Utilities ────────────────────────────────────────────────────────────

function updateStatus(text, success = true) {
    const statusText = document.getElementById('status-text');
    const statusDot = document.querySelector('.status-dot');

    statusText.textContent = text;
    statusDot.className = success
        ? 'status-dot status-dot--active'
        : 'status-dot';
}


function escHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}


function escAttr(str) {
    return str.replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}
