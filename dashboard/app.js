/**
 * PharmaPipeline — Sidebar Dashboard Application
 *
 * Multi-view layout:
 *   • Chat — LLM-style landing that explains the platform
 *   • Dashboard — KPIs & pipeline runs
 *   • Analytics — Charts
 *   • Drug Assets — Card grid
 *   • Records — Data table
 *   • Pipeline Runs — History
 *   • Add Data — AI Extract / Manual Entry
 */

// ── State ────────────────────────────────────────────────────────────────

const state = {
    records: [],
    pipelineRuns: [],
    currentSort: { column: null, direction: 'asc' },
    charts: {},
    currentView: 'chat',
    inputMode: 'extract',
    chatHistory: [],
};

// ── Colors ───────────────────────────────────────────────────────────────

const COLORS = {
    blue:    { bg: 'rgba(66, 133, 244, 0.55)',  border: '#4285f4' },
    cyan:    { bg: 'rgba(45, 212, 191, 0.55)',   border: '#2dd4bf' },
    violet:  { bg: 'rgba(167, 139, 250, 0.55)',  border: '#a78bfa' },
    emerald: { bg: 'rgba(16, 185, 129, 0.55)',   border: '#10b981' },
    amber:   { bg: 'rgba(251, 191, 36, 0.55)',   border: '#fbbf24' },
    rose:    { bg: 'rgba(251, 113, 133, 0.55)',   border: '#fb7185' },
    indigo:  { bg: 'rgba(129, 140, 248, 0.55)',  border: '#818cf8' },
    slate:   { bg: 'rgba(100, 116, 139, 0.55)',  border: '#64748b' },
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

const VIEW_META = {
    chat:      { icon: '💬', label: 'Chat' },
    dashboard: { icon: '📊', label: 'Dashboard' },
    analytics: { icon: '📈', label: 'Analytics' },
    drugs:     { icon: '🧪', label: 'Drug Assets' },
    records:   { icon: '📋', label: 'Records' },
    runs:      { icon: '🕐', label: 'Pipeline Runs' },
    input:     { icon: '⚡', label: 'Add Data' },
};


// ── Initialization ───────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    bindEvents();
    initCharts();
    initChat();
    loadDemoDataIfAvailable();
});


function bindEvents() {
    // Sidebar navigation
    document.querySelectorAll('.sidebar-item[data-view]').forEach(item => {
        item.addEventListener('click', () => navigateTo(item.dataset.view));
    });

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

    // Table search & filter
    document.getElementById('table-search').addEventListener('input', filterTable);
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

    // Mode toggle (Add Data view)
    document.getElementById('mode-btn-extract').addEventListener('click', () => setInputMode('extract'));
    document.getElementById('mode-btn-manual').addEventListener('click', () => setInputMode('manual'));

    // AI Extract
    document.getElementById('btn-bar-extract').addEventListener('click', handleAIExtract);
    document.getElementById('extract-url-input').addEventListener('keydown', (e) => {
        if (e.key === 'Enter') handleAIExtract();
    });
    document.getElementById('btn-bar-upload').addEventListener('click', () => {
        document.getElementById('file-input').click();
    });

    // Manual entry
    document.getElementById('btn-submit-manual').addEventListener('click', handleManualSubmit);
    document.getElementById('btn-clear-form').addEventListener('click', clearManualForm);

    // Chat
    document.getElementById('chat-send-btn').addEventListener('click', handleChatSend);
    document.getElementById('chat-input').addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleChatSend(); }
    });
}


// ── Navigation ───────────────────────────────────────────────────────────

function navigateTo(viewId) {
    state.currentView = viewId;

    // Update sidebar active state
    document.querySelectorAll('.sidebar-item').forEach(item => {
        item.classList.toggle('active', item.dataset.view === viewId);
    });

    // Switch views
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    const target = document.getElementById(`view-${viewId}`);
    if (target) target.classList.add('active');

    // Update top bar
    const meta = VIEW_META[viewId] || { icon: '📄', label: viewId };
    document.getElementById('topbar-icon').textContent = meta.icon;
    document.getElementById('topbar-label').textContent = meta.label;

    // Render view-specific content when switching to it
    if (viewId === 'analytics' && state.records.length > 0) {
        // Delay chart render to let canvas mount
        setTimeout(() => renderCharts(), 100);
    }
    if (viewId === 'input') {
        setTimeout(() => updateModeSlider(), 50);
    }
}


// ── Chat (LLM Landing) ──────────────────────────────────────────────────

function initChat() {
    const welcomeMessage = `
        <h3>Welcome to PharmaPipeline 🧬</h3>
        <p>I'm your AI assistant for pharmaceutical data extraction and analysis. Here's what this platform can do:</p>
        <div class="feature-grid">
            <div class="feature-item"><span class="fi-icon">🌐</span> Extract pharma data from URLs</div>
            <div class="feature-item"><span class="fi-icon">✍️</span> Manually enter drug records</div>
            <div class="feature-item"><span class="fi-icon">📊</span> Dashboard with live KPIs</div>
            <div class="feature-item"><span class="fi-icon">📈</span> Analytics & chart breakdowns</div>
            <div class="feature-item"><span class="fi-icon">🧪</span> Drug asset cards & search</div>
            <div class="feature-item"><span class="fi-icon">📋</span> Sortable records table</div>
        </div>
        <p>Use the <span class="highlight">sidebar</span> to navigate between sections. Go to <span class="highlight">Add Data</span> to extract from the web or enter records manually.</p>
        <p>Ask me anything — I can explain features, help interpret data, or guide you through the workflow!</p>
    `;

    addChatMessage('ai', welcomeMessage);
}


const CHAT_RESPONSES = {
    extract: `Great question! The <span class="highlight">AI Extract</span> mode lets you paste any pharmaceutical URL — news articles, FDA announcements, clinical trial pages — and our AI pipeline will automatically identify and extract structured data like drug assets, clinical insights, competitive intelligence, and regulatory updates.\n\nHead to <span class="highlight">Add Data → AI Extract</span> in the sidebar to try it out!`,

    manual: `The <span class="highlight">Manual Entry</span> mode gives you a comprehensive form to enter pharmaceutical records yourself. It supports all data types:\n<ul><li>Drug Asset details (molecule, sponsor, MoA, therapy area)</li><li>Clinical Insight (trial phase, endpoints, efficacy data)</li><li>Competitive Intelligence (positioning, competitors, market size)</li><li>Regulatory Updates (approval status, designations)</li></ul>\nGo to <span class="highlight">Add Data → Manual Entry</span> to start entering data.`,

    dashboard: `The <span class="highlight">Dashboard</span> gives you a birds-eye view of your data — how many files processed, records extracted, validation status, and average confidence scores. It also shows your recent pipeline runs.\n\nAll KPIs update automatically when you add new data through either mode.`,

    analytics: `The <span class="highlight">Analytics</span> section provides three key visualizations:\n<ul><li><strong>Record Types</strong> — doughnut chart showing distribution across Drug Assets, Clinical Insights, etc.</li><li><strong>Therapy Areas</strong> — horizontal bar chart of the most common therapy areas</li><li><strong>Confidence Distribution</strong> — shows how confident the AI is in each extraction</li></ul>\nThese charts update live as you add more data.`,

    drugs: `The <span class="highlight">Drug Assets</span> view shows all extracted drug/molecule data as visual cards. Each card displays the molecule name, sponsor company, therapy tags, confidence score, and a summary.\n\nYou can search and filter molecules using the search bar. Click any card to see full details in a modal.`,

    records: `The <span class="highlight">Records</span> table is a comprehensive, sortable, and filterable view of every extracted record. You can:\n<ul><li>Sort by clicking any column header</li><li>Filter by record type using the dropdown</li><li>Search across all fields with the search bar</li><li>Click any row to see full details</li></ul>`,

    export: `You can export all your data as a JSON file by clicking the <span class="highlight">Export All Data</span> button at the bottom of the sidebar. This downloads every record in the standard pipeline format, ready for import into Airtable or other systems.`,

    help: `Here's a quick guide to get started:\n<ul><li><strong>Step 1:</strong> Go to <span class="highlight">Add Data</span> in the sidebar</li><li><strong>Step 2:</strong> Choose AI Extract (paste a URL) or Manual Entry (fill a form)</li><li><strong>Step 3:</strong> Check <span class="highlight">Dashboard</span> for KPIs and <span class="highlight">Analytics</span> for charts</li><li><strong>Step 4:</strong> Browse <span class="highlight">Drug Assets</span> and <span class="highlight">Records</span> for detailed data</li><li><strong>Step 5:</strong> Export your data when ready</li></ul>\nFeel free to ask me anything specific!`,
};


function handleChatSend() {
    const input = document.getElementById('chat-input');
    const text = input.value.trim();
    if (!text) return;

    addChatMessage('user', escHtml(text));
    input.value = '';

    // Show typing indicator
    showTypingIndicator();

    // Generate response after delay
    setTimeout(() => {
        hideTypingIndicator();
        const response = generateChatResponse(text);
        addChatMessage('ai', response);
    }, 800 + Math.random() * 700);
}


function generateChatResponse(userText) {
    const lower = userText.toLowerCase();

    if (lower.includes('extract') || lower.includes('url') || lower.includes('ai mode') || lower.includes('web'))
        return CHAT_RESPONSES.extract;
    if (lower.includes('manual') || lower.includes('form') || lower.includes('enter') || lower.includes('input'))
        return CHAT_RESPONSES.manual;
    if (lower.includes('dashboard') || lower.includes('kpi') || lower.includes('overview') || lower.includes('summary'))
        return CHAT_RESPONSES.dashboard;
    if (lower.includes('analytic') || lower.includes('chart') || lower.includes('graph') || lower.includes('visualiz'))
        return CHAT_RESPONSES.analytics;
    if (lower.includes('drug') || lower.includes('molecule') || lower.includes('asset') || lower.includes('compound'))
        return CHAT_RESPONSES.drugs;
    if (lower.includes('record') || lower.includes('table') || lower.includes('data'))
        return CHAT_RESPONSES.records;
    if (lower.includes('export') || lower.includes('download') || lower.includes('save') || lower.includes('json'))
        return CHAT_RESPONSES.export;
    if (lower.includes('help') || lower.includes('how') || lower.includes('start') || lower.includes('guide') || lower.includes('what'))
        return CHAT_RESPONSES.help;

    // Generic fallback
    const stats = state.records.length > 0
        ? `\n\nYou currently have <span class="highlight">${state.records.length} records</span> loaded. Check the Dashboard for a full overview.`
        : `\n\nYou haven't loaded any data yet. Head to <span class="highlight">Add Data</span> to get started!`;

    return `I can help you with anything related to PharmaPipeline! Try asking me about:\n<ul><li>How to <strong>extract data</strong> from URLs</li><li>How <strong>manual entry</strong> works</li><li>What the <strong>dashboard</strong> shows</li><li>How to use <strong>analytics</strong> and charts</li><li>How to <strong>export</strong> your data</li></ul>${stats}`;
}


function addChatMessage(role, html) {
    const container = document.getElementById('chat-messages');
    const isAi = role === 'ai';

    const msg = document.createElement('div');
    msg.className = `chat-message chat-message--${role}`;
    msg.innerHTML = `
        <div class="chat-avatar ${isAi ? 'chat-avatar--ai' : 'chat-avatar--user'}">
            ${isAi ? '✨' : '👤'}
        </div>
        <div class="chat-bubble">${html}</div>
    `;
    container.appendChild(msg);
    container.scrollTop = container.scrollHeight;
}


function showTypingIndicator() {
    const container = document.getElementById('chat-messages');
    const typing = document.createElement('div');
    typing.className = 'chat-typing';
    typing.id = 'typing-indicator';
    typing.innerHTML = `
        <div class="typing-dots"><span></span><span></span><span></span></div>
        PharmaPipeline is thinking…
    `;
    container.appendChild(typing);
    container.scrollTop = container.scrollHeight;
}

function hideTypingIndicator() {
    const el = document.getElementById('typing-indicator');
    if (el) el.remove();
}


// ── Input Mode Toggle ────────────────────────────────────────────────────

function setInputMode(mode) {
    state.inputMode = mode;

    document.querySelectorAll('.mode-toggle-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.mode === mode);
    });
    updateModeSlider();

    const extractPanel = document.getElementById('extract-panel');
    const manualPanel = document.getElementById('manual-entry-panel');

    if (mode === 'extract') {
        extractPanel.style.display = '';
        manualPanel.classList.remove('visible');
    } else {
        extractPanel.style.display = 'none';
        manualPanel.classList.add('visible');
    }
}


function updateModeSlider() {
    const slider = document.getElementById('mode-slider');
    const activeBtn = document.querySelector('.mode-toggle-btn.active');
    if (activeBtn && slider) {
        requestAnimationFrame(() => {
            slider.style.width = activeBtn.offsetWidth + 'px';
            slider.style.left = activeBtn.offsetLeft + 'px';
        });
    }
}


// ── AI Extraction ────────────────────────────────────────────────────────

function handleAIExtract() {
    const input = document.getElementById('extract-url-input');
    const url = input.value.trim();
    if (!url) { showToast('⚠️', 'Please enter a URL'); return; }

    const shimmer = document.getElementById('shimmer-loading');
    const shimmerText = document.getElementById('shimmer-text');
    shimmer.classList.add('visible');

    const steps = [
        'Connecting to source…',
        'Analyzing page content…',
        'Extracting pharmaceutical data…',
        'Identifying drug assets…',
        'Validating extracted records…',
        'Finalizing extraction…',
    ];

    let stepIndex = 0;
    const stepInterval = setInterval(() => {
        if (stepIndex < steps.length) { shimmerText.textContent = steps[stepIndex]; stepIndex++; }
    }, 500);

    setTimeout(() => {
        clearInterval(stepInterval);
        shimmer.classList.remove('visible');

        const extracted = generateExtractedRecords(url);
        state.records.push(...extracted);

        state.pipelineRuns.push({
            started_at: new Date().toISOString(),
            completed_at: new Date().toISOString(),
            files_discovered: 1, files_processed: 1, files_failed: 0,
            total_records_extracted: extracted.length,
            total_records_validated: extracted.length,
            total_records_written: extracted.length,
            source_url: url,
            errors: [],
        });

        renderAll();
        input.value = '';
        showToast('✅', `Extracted ${extracted.length} records from URL`);
        updateStatus(`Extracted ${extracted.length} records`, true);
    }, 3500);
}


function generateExtractedRecords(url) {
    const ts = new Date().toISOString();
    const domain = (() => { try { return new URL(url).hostname; } catch { return url.split('/')[0]; } })();

    return [
        {
            record_type: 'Drug Asset',
            confidence_score: +(0.87 + Math.random() * 0.1).toFixed(2),
            source_file: `Web — ${domain}`,
            slide_range: 'N/A',
            extraction_timestamp: ts,
            drug_asset: {
                molecule_name: 'Extracted Compound',
                mechanism_of_action: 'Under analysis',
                drug_class: 'Targeted therapy',
                sponsor_company: 'From source',
                therapy_area: 'Oncology',
                indication: 'Extracted from publication',
                route_of_administration: 'IV',
            },
            clinical_insight: { trial_phase: 'Phase II', trial_status: 'Recruiting', primary_endpoints: ['PFS'], patient_population: 'Identified from source' },
            competitive_intel: null, regulatory_update: null,
            key_takeaways: ['Novel compound identified from web', 'Early-stage clinical development', 'Further validation recommended'],
            raw_summary: `AI-extracted pharma data from ${domain}. Contains targeted therapy information in oncology.`,
            _source: 'ai',
        },
        {
            record_type: 'Competitive Intelligence',
            confidence_score: +(0.78 + Math.random() * 0.12).toFixed(2),
            source_file: `Web — ${domain}`,
            slide_range: 'N/A',
            extraction_timestamp: ts,
            drug_asset: null, clinical_insight: null,
            competitive_intel: {
                market_landscape: `Competitive data extracted from ${domain}.`,
                key_differentiators: ['Differentiated mechanism', 'Oral formulation'],
                competitors: ['Competitor A', 'Competitor B'],
                market_size_estimate: 'Under evaluation',
            },
            regulatory_update: null,
            key_takeaways: ['Market landscape data identified', 'Competitive positioning analysis available'],
            raw_summary: `Competitive intelligence from ${domain}. Market landscape and competitor analysis.`,
            _source: 'ai',
        },
    ];
}


// ── Manual Entry ─────────────────────────────────────────────────────────

function handleManualSubmit() {
    const molecule = document.getElementById('manual-molecule').value.trim();
    const summary = document.getElementById('manual-summary').value.trim();
    if (!summary) { showToast('⚠️', 'Please provide at least a summary'); return; }

    const record = {
        source_file: document.getElementById('manual-source-file').value.trim() || 'Manual Entry',
        slide_range: document.getElementById('manual-slide-range').value.trim() || 'N/A',
        extraction_timestamp: new Date().toISOString(),
        record_type: document.getElementById('manual-record-type').value,
        confidence_score: parseFloat(document.getElementById('manual-confidence').value) || 0.85,
        raw_summary: summary,
        key_takeaways: getListValues('takeaways-list'),
        _source: 'manual',
    };

    // Drug Asset
    if (molecule) {
        record.drug_asset = {
            molecule_name: molecule,
            sponsor_company: document.getElementById('manual-sponsor').value.trim() || null,
            mechanism_of_action: document.getElementById('manual-moa').value.trim() || null,
            drug_class: document.getElementById('manual-drug-class').value.trim() || null,
            therapy_area: document.getElementById('manual-therapy-area').value.trim() || null,
            indication: document.getElementById('manual-indication').value.trim() || null,
            route_of_administration: document.getElementById('manual-route').value || null,
        };
    } else { record.drug_asset = null; }

    // Clinical
    const tp = document.getElementById('manual-trial-phase').value;
    const ts2 = document.getElementById('manual-trial-status').value;
    const tid = document.getElementById('manual-trial-id').value.trim();
    const pe = getListValues('primary-endpoints-list');
    const eff = document.getElementById('manual-efficacy').value.trim();
    const saf = document.getElementById('manual-safety').value.trim();

    if (tp || ts2 || tid || pe.length || eff || saf) {
        record.clinical_insight = {
            trial_phase: tp || null, trial_status: ts2 || null, trial_identifier: tid || null,
            primary_endpoints: pe, secondary_endpoints: [],
            patient_population: document.getElementById('manual-population').value.trim() || null,
            enrollment_target: parseInt(document.getElementById('manual-enrollment').value) || null,
            efficacy_data: eff || null, safety_signals: saf || null,
        };
    } else { record.clinical_insight = null; }

    // Competitive
    const pos = document.getElementById('manual-positioning').value.trim();
    const land = document.getElementById('manual-landscape').value.trim();
    const ms = document.getElementById('manual-market-size').value.trim();
    const comp = getListValues('competitors-list');
    const diff = getListValues('differentiators-list');

    if (pos || land || ms || comp.length || diff.length) {
        record.competitive_intel = {
            competitive_positioning: pos || null, market_landscape: land || null,
            key_differentiators: diff, competitors: comp, market_size_estimate: ms || null,
            strategic_implications: null,
        };
    } else { record.competitive_intel = null; }

    // Regulatory
    const as = document.getElementById('manual-approval-status').value.trim();
    const ra = document.getElementById('manual-reg-authority').value;
    const sd = document.getElementById('manual-submission-date').value;
    const ad = document.getElementById('manual-approval-date').value;
    const pd = document.getElementById('manual-pdufa').value;
    const des = getListValues('designations-list');

    if (as || ra || sd || ad || des.length) {
        record.regulatory_update = {
            approval_status: as || null, regulatory_authority: ra || null,
            submission_date: sd || null, approval_date: ad || null,
            designations: des, pdufa_date: pd || null,
        };
    } else { record.regulatory_update = null; }

    state.records.push(record);
    renderAll();
    showToast('✅', `Record "${molecule || record.record_type}" added`);
    updateStatus(`Added: ${molecule || record.record_type}`, true);
    clearManualForm();
}


function clearManualForm() {
    const panel = document.getElementById('manual-entry-panel');
    panel.querySelectorAll('.form-input, .form-textarea').forEach(el => {
        el.value = el.id === 'manual-confidence' ? '0.85' : '';
    });
    panel.querySelectorAll('.form-select').forEach(el => { el.selectedIndex = 0; });

    ['primary-endpoints-list', 'competitors-list', 'differentiators-list', 'designations-list', 'takeaways-list'].forEach(id => {
        const c = document.getElementById(id);
        const rows = c.querySelectorAll('.list-input-row');
        for (let i = 1; i < rows.length; i++) rows[i].remove();
        const fi = c.querySelector('.form-input');
        if (fi) fi.value = '';
    });
}


// ── Form Helpers ─────────────────────────────────────────────────────────

function toggleFormSection(id) {
    document.getElementById(id).classList.toggle('open');
}

function addListItem(listId) {
    const c = document.getElementById(listId);
    const rows = c.querySelectorAll('.list-input-row');
    const last = rows[rows.length - 1].querySelector('.form-input');
    if (!last.value.trim()) { last.focus(); return; }

    const row = document.createElement('div');
    row.className = 'list-input-row';
    row.innerHTML = `<input class="form-input" type="text" placeholder="${last.placeholder}"><button class="btn-remove-item" onclick="removeListItem(this)">−</button>`;
    c.appendChild(row);
    row.querySelector('.form-input').focus();
}

function removeListItem(btn) { btn.closest('.list-input-row').remove(); }

function getListValues(listId) {
    return Array.from(document.getElementById(listId).querySelectorAll('.form-input'))
        .map(i => i.value.trim()).filter(Boolean);
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
            showToast('📂', `Loaded ${file.name}`);
        } catch (err) {
            showToast('❌', `Invalid JSON: ${err.message}`);
        }
    };
    reader.readAsText(file);
    e.target.value = '';
}

function processLoadedData(data) {
    if (data.file_results) {
        state.records = [];
        state.pipelineRuns.push(data);
        data.file_results.forEach(fr => { if (fr.records) state.records.push(...fr.records); });
        if (state.records.length === 0 && data.records) state.records = data.records;
    } else if (Array.isArray(data)) {
        state.records = data;
    } else if (data.records && Array.isArray(data.records)) {
        state.records = data.records;
    }
    renderAll();
}

function loadDemoDataIfAvailable() {
    fetch('demo_data.json')
        .then(res => res.ok ? res.json() : null)
        .then(data => { if (data) { processLoadedData(data); updateStatus('Loaded demo data', true); } })
        .catch(() => {});
}


// ── Rendering ────────────────────────────────────────────────────────────

function renderAll() {
    renderKPIs();
    renderDrugCards();
    renderTable();
    renderPipelineRuns();
    renderPipelineRunsFull();
    populateTypeFilter();
    updateBadges();
    document.getElementById('last-updated').textContent = new Date().toLocaleTimeString();

    // If currently on analytics view, render charts
    if (state.currentView === 'analytics') {
        setTimeout(() => renderCharts(), 50);
    }
}


function updateBadges() {
    const drugCount = state.records.filter(r => r.drug_asset).length;
    document.getElementById('drug-count-badge').textContent = drugCount;
    document.getElementById('record-count-badge').textContent = state.records.length;
}


// ── KPIs ─────────────────────────────────────────────────────────────────

function renderKPIs() {
    const records = state.records;
    const lastRun = state.pipelineRuns[state.pipelineRuns.length - 1];

    animateValue('kpi-files-value', lastRun?.files_processed ?? 0);
    animateValue('kpi-records-value', records.length);
    animateValue('kpi-validated-value', lastRun?.total_records_validated ?? records.length);

    if (records.length > 0) {
        const avg = records.reduce((s, r) => s + (r.confidence_score || 0), 0) / records.length;
        document.getElementById('kpi-confidence-value').textContent = (avg * 100).toFixed(1) + '%';
    } else {
        document.getElementById('kpi-confidence-value').textContent = '—';
    }
}

function animateValue(id, target) {
    const el = document.getElementById(id);
    const dur = 600, start = parseInt(el.textContent) || 0, t0 = performance.now();
    function tick(now) {
        const p = Math.min((now - t0) / dur, 1);
        el.textContent = Math.round(start + (target - start) * (1 - Math.pow(1 - p, 3)));
        if (p < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
}


// ── Charts ───────────────────────────────────────────────────────────────

function initCharts() {
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
    state.records.forEach(r => { const t = r.record_type || 'Unknown'; counts[t] = (counts[t] || 0) + 1; });
    const labels = Object.keys(counts), data = Object.values(counts);
    const colors = labels.map(l => TYPE_STYLES[l]?.color || COLORS.slate);

    if (state.charts.recordTypes) state.charts.recordTypes.destroy();
    const ctx = document.getElementById('chart-record-types');
    if (!ctx) return;
    state.charts.recordTypes = new Chart(ctx.getContext('2d'), {
        type: 'doughnut',
        data: { labels, datasets: [{ data, backgroundColor: colors.map(c => c.bg), borderColor: colors.map(c => c.border), borderWidth: 2, hoverOffset: 8 }] },
        options: { responsive: true, maintainAspectRatio: false, cutout: '60%', plugins: { legend: { position: 'bottom' } } },
    });
}

function renderTherapyAreasChart() {
    const counts = {};
    state.records.forEach(r => { const ta = r.drug_asset?.therapy_area || 'Unspecified'; counts[ta] = (counts[ta] || 0) + 1; });
    const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 8);

    if (state.charts.therapyAreas) state.charts.therapyAreas.destroy();
    const ctx = document.getElementById('chart-therapy-areas');
    if (!ctx) return;
    state.charts.therapyAreas = new Chart(ctx.getContext('2d'), {
        type: 'bar',
        data: { labels: sorted.map(([k]) => k), datasets: [{ data: sorted.map(([, v]) => v), backgroundColor: sorted.map((_, i) => COLOR_LIST[i % COLOR_LIST.length].bg), borderColor: sorted.map((_, i) => COLOR_LIST[i % COLOR_LIST.length].border), borderWidth: 1, borderRadius: 6 }] },
        options: { responsive: true, maintainAspectRatio: false, indexAxis: 'y', plugins: { legend: { display: false } }, scales: { x: { grid: { color: 'rgba(255,255,255,0.03)' }, ticks: { stepSize: 1 } }, y: { grid: { display: false } } } },
    });
}

function renderConfidenceChart() {
    const buckets = { '90-100%': 0, '70-89%': 0, '50-69%': 0, '<50%': 0 };
    state.records.forEach(r => { const c = (r.confidence_score || 0) * 100; if (c >= 90) buckets['90-100%']++; else if (c >= 70) buckets['70-89%']++; else if (c >= 50) buckets['50-69%']++; else buckets['<50%']++; });

    if (state.charts.confidence) state.charts.confidence.destroy();
    const ctx = document.getElementById('chart-confidence');
    if (!ctx) return;
    state.charts.confidence = new Chart(ctx.getContext('2d'), {
        type: 'bar',
        data: { labels: Object.keys(buckets), datasets: [{ data: Object.values(buckets), backgroundColor: [COLORS.emerald.bg, COLORS.blue.bg, COLORS.amber.bg, COLORS.rose.bg], borderColor: [COLORS.emerald.border, COLORS.blue.border, COLORS.amber.border, COLORS.rose.border], borderWidth: 1, borderRadius: 6 }] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { grid: { color: 'rgba(255,255,255,0.03)' }, ticks: { stepSize: 1 } }, x: { grid: { display: false } } } },
    });
}


// ── Drug Cards ───────────────────────────────────────────────────────────

function renderDrugCards(filterText = '') {
    const grid = document.getElementById('drug-grid');
    const drugRecords = state.records.filter(r => r.drug_asset);

    if (!drugRecords.length) {
        grid.innerHTML = `<div class="empty-state"><div class="empty-icon">🧪</div><p>No drug asset data available</p><span>Add records via AI Extract or Manual Entry</span></div>`;
        return;
    }

    const filtered = filterText ? drugRecords.filter(r =>
        (r.drug_asset.molecule_name || '').toLowerCase().includes(filterText) ||
        (r.drug_asset.sponsor_company || '').toLowerCase().includes(filterText) ||
        (r.drug_asset.therapy_area || '').toLowerCase().includes(filterText)
    ) : drugRecords;

    grid.innerHTML = filtered.map((r, i) => {
        const da = r.drug_asset;
        const cc = r.confidence_score >= 0.9 ? 'confidence-high' : r.confidence_score >= 0.7 ? 'confidence-medium' : 'confidence-low';
        const tags = [];
        if (da.therapy_area) tags.push(`<span class="drug-tag drug-tag--therapy">${da.therapy_area}</span>`);
        if (da.drug_class) tags.push(`<span class="drug-tag">${da.drug_class}</span>`);
        if (r.clinical_insight?.trial_phase) tags.push(`<span class="drug-tag drug-tag--phase">${r.clinical_insight.trial_phase}</span>`);
        if (da.mechanism_of_action) tags.push(`<span class="drug-tag">${da.mechanism_of_action}</span>`);
        const sb = r._source === 'manual' ? '<span class="source-badge source-badge--manual">Manual</span>' : r._source === 'ai' ? '<span class="source-badge source-badge--ai">AI</span>' : '';

        return `<div class="drug-card animate-in" style="animation-delay:${i * 60}ms" onclick="openModal(${state.records.indexOf(r)})">
            <div class="drug-card-header"><div><div class="drug-name">${escHtml(da.molecule_name)} ${sb}</div><div class="drug-company">${escHtml(da.sponsor_company || '—')}</div></div><span class="confidence-badge ${cc}">${(r.confidence_score * 100).toFixed(0)}%</span></div>
            <div class="drug-meta">${tags.join('')}</div>
            <div class="drug-summary">${escHtml(r.raw_summary || '')}</div>
        </div>`;
    }).join('');
}

function filterDrugs() { renderDrugCards(document.getElementById('drug-search').value.toLowerCase()); }


// ── Records Table ────────────────────────────────────────────────────────

function renderTable() {
    const tbody = document.getElementById('records-tbody');
    if (!state.records.length) {
        tbody.innerHTML = `<tr class="empty-row"><td colspan="7"><div class="empty-state"><div class="empty-icon">📋</div><p>No records to display</p></div></td></tr>`;
        return;
    }

    tbody.innerHTML = state.records.map((r, i) => {
        const ts = TYPE_STYLES[r.record_type] || TYPE_STYLES['General Insight'];
        const cc = r.confidence_score >= 0.9 ? 'confidence-high' : r.confidence_score >= 0.7 ? 'confidence-medium' : 'confidence-low';
        const sb = r._source === 'manual' ? ' <span class="source-badge source-badge--manual">M</span>' : r._source === 'ai' ? ' <span class="source-badge source-badge--ai">AI</span>' : '';

        return `<tr onclick="openModal(${i})">
            <td>${escHtml(r.source_file || '—')}${sb}</td>
            <td><span class="type-badge ${ts.css}">${escHtml(r.record_type || '—')}</span></td>
            <td class="cell-molecule">${escHtml(r.drug_asset?.molecule_name || '—')}</td>
            <td>${escHtml(r.drug_asset?.therapy_area || '—')}</td>
            <td class="cell-confidence ${cc}">${r.confidence_score != null ? (r.confidence_score * 100).toFixed(0) + '%' : '—'}</td>
            <td>${escHtml(r.slide_range || '—')}</td>
            <td class="cell-summary" title="${escAttr(r.raw_summary || '')}">${escHtml(r.raw_summary || '—')}</td>
        </tr>`;
    }).join('');
}

function filterTable() {
    const search = document.getElementById('table-search').value.toLowerCase();
    const typeFilter = document.getElementById('type-filter').value;
    document.querySelectorAll('#records-tbody tr:not(.empty-row)').forEach((row, i) => {
        const r = state.records[i];
        if (!r) return;
        const ms = !search || JSON.stringify(r).toLowerCase().includes(search);
        const mt = !typeFilter || r.record_type === typeFilter;
        row.style.display = (ms && mt) ? '' : 'none';
    });
}

function populateTypeFilter() {
    const sel = document.getElementById('type-filter');
    const types = [...new Set(state.records.map(r => r.record_type).filter(Boolean))];
    sel.innerHTML = '<option value="">All Types</option>';
    types.sort().forEach(t => { const o = document.createElement('option'); o.value = t; o.textContent = t; sel.appendChild(o); });
}

function handleSort(column) {
    const { currentSort } = state;
    const dir = (currentSort.column === column && currentSort.direction === 'asc') ? 'desc' : 'asc';
    state.currentSort = { column, direction: dir };
    document.querySelectorAll('.data-table th').forEach(th => th.classList.remove('sort-asc', 'sort-desc'));
    const th = document.querySelector(`.data-table th[data-sort="${column}"]`);
    if (th) th.classList.add(dir === 'asc' ? 'sort-asc' : 'sort-desc');
    state.records.sort((a, b) => {
        let va = getNestedValue(a, column) || '', vb = getNestedValue(b, column) || '';
        if (typeof va === 'number' && typeof vb === 'number') return dir === 'asc' ? va - vb : vb - va;
        return dir === 'asc' ? String(va).toLowerCase().localeCompare(String(vb).toLowerCase()) : String(vb).toLowerCase().localeCompare(String(va).toLowerCase());
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
    renderRunsList(document.getElementById('runs-list'));
}

function renderPipelineRunsFull() {
    renderRunsList(document.getElementById('runs-list-full'));
}

function renderRunsList(list) {
    if (!list) return;
    if (!state.pipelineRuns.length) {
        list.innerHTML = `<div class="empty-state"><div class="empty-icon">🕐</div><p>No pipeline runs loaded</p></div>`;
        return;
    }
    list.innerHTML = state.pipelineRuns.map(run => {
        const fail = (run.files_failed || 0) > 0;
        const sc = fail ? 'run-status-icon--partial' : 'run-status-icon--success';
        const si = fail ? '⚠️' : '✅';
        const ts = run.started_at ? new Date(run.started_at).toLocaleString() : '—';
        const src = run.source_url ? ` · <em style="color:var(--accent-blue)">${run.source_url.substring(0, 40)}…</em>` : '';
        return `<div class="run-item">
            <div class="run-status-icon ${sc}">${si}</div>
            <div class="run-info"><div class="run-timestamp">${ts}</div><div class="run-details">${run.files_discovered || 0} files${run.errors?.length ? ` · ${run.errors.length} error(s)` : ''}${src}</div></div>
            <div class="run-stats">
                <div class="run-stat"><div class="run-stat-value">${run.files_processed || 0}</div><div class="run-stat-label">Processed</div></div>
                <div class="run-stat"><div class="run-stat-value">${run.total_records_extracted || 0}</div><div class="run-stat-label">Extracted</div></div>
                <div class="run-stat"><div class="run-stat-value">${run.total_records_written || 0}</div><div class="run-stat-label">Written</div></div>
            </div>
        </div>`;
    }).join('');
}


// ── Modal ────────────────────────────────────────────────────────────────

function openModal(index) {
    const r = state.records[index];
    if (!r) return;
    const modal = document.getElementById('record-modal');
    const ts = TYPE_STYLES[r.record_type] || TYPE_STYLES['General Insight'];

    document.getElementById('modal-title').textContent = r.drug_asset?.molecule_name || r.record_type || 'Record Detail';
    const badge = document.getElementById('modal-type-badge');
    badge.textContent = r.record_type || '—';
    badge.className = `modal-badge ${ts.css}`;

    let html = '';
    html += `<div class="modal-section"><div class="modal-section-title">Source</div>${mf('File', r.source_file)}${mf('Slides', r.slide_range)}${mf('Confidence', r.confidence_score != null ? (r.confidence_score * 100).toFixed(1) + '%' : null)}${mf('Extracted', r.extraction_timestamp ? new Date(r.extraction_timestamp).toLocaleString() : null)}${mf('Mode', r._source === 'manual' ? '✍️ Manual' : r._source === 'ai' ? '🌐 AI' : '📂 File')}</div>`;

    if (r.drug_asset) { const d = r.drug_asset; html += `<div class="modal-section"><div class="modal-section-title">Drug Asset</div>${mf('Molecule', d.molecule_name)}${mf('Sponsor', d.sponsor_company)}${mf('Therapy Area', d.therapy_area)}${mf('Indication', d.indication)}${mf('Class', d.drug_class)}${mf('MoA', d.mechanism_of_action)}${mf('Route', d.route_of_administration)}</div>`; }

    if (r.clinical_insight) { const c = r.clinical_insight; html += `<div class="modal-section"><div class="modal-section-title">Clinical Insight</div>${mf('Phase', c.trial_phase)}${mf('Status', c.trial_status)}${mf('Trial ID', c.trial_identifier)}${mf('Endpoints', Array.isArray(c.primary_endpoints) ? c.primary_endpoints.join('; ') : c.primary_endpoints)}${mf('Population', c.patient_population)}${mf('Enrollment', c.enrollment_target)}${mf('Efficacy', c.efficacy_data)}${mf('Safety', c.safety_signals)}</div>`; }

    if (r.competitive_intel) { const ci = r.competitive_intel; html += `<div class="modal-section"><div class="modal-section-title">Competitive Intelligence</div>${mf('Positioning', ci.competitive_positioning)}${mf('Landscape', ci.market_landscape)}${mf('Differentiators', Array.isArray(ci.key_differentiators) ? ci.key_differentiators.join('; ') : ci.key_differentiators)}${mf('Competitors', Array.isArray(ci.competitors) ? ci.competitors.join(', ') : ci.competitors)}${mf('Market Size', ci.market_size_estimate)}${mf('Strategy', ci.strategic_implications)}</div>`; }

    if (r.regulatory_update) { const rg = r.regulatory_update; html += `<div class="modal-section"><div class="modal-section-title">Regulatory</div>${mf('Status', rg.approval_status)}${mf('Authority', rg.regulatory_authority)}${mf('Submitted', rg.submission_date)}${mf('Approved', rg.approval_date)}${mf('Designations', Array.isArray(rg.designations) ? rg.designations.join(', ') : rg.designations)}${mf('PDUFA', rg.pdufa_date)}</div>`; }

    html += `<div class="modal-section"><div class="modal-section-title">Summary</div><p style="font-size:0.82rem;color:var(--text-secondary);line-height:1.7">${escHtml(r.raw_summary || '—')}</p></div>`;
    if (r.key_takeaways?.length) html += `<div class="modal-section"><div class="modal-section-title">Key Takeaways</div><ul class="modal-takeaways">${r.key_takeaways.map(t => `<li>${escHtml(t)}</li>`).join('')}</ul></div>`;

    document.getElementById('modal-body').innerHTML = html;
    modal.classList.add('active');
    document.body.style.overflow = 'hidden';
}

function closeModal() { document.getElementById('record-modal').classList.remove('active'); document.body.style.overflow = ''; }
function mf(label, val) { const d = val != null && val !== '' ? escHtml(String(val)) : '<span style="color:var(--text-tertiary)">—</span>'; return `<div class="modal-field"><span class="modal-field-label">${label}</span><span class="modal-field-value">${d}</span></div>`; }


// ── Export ────────────────────────────────────────────────────────────────

function handleExport() {
    if (!state.records.length) { showToast('⚠️', 'No data to export'); return; }
    const blob = new Blob([JSON.stringify(state.records, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `pharma_extraction_${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
    showToast('📥', 'Exported as JSON');
}


// ── Utilities ────────────────────────────────────────────────────────────

function updateStatus(text, ok = true) {
    document.getElementById('status-text').textContent = text;
    document.querySelector('.status-dot').className = ok ? 'status-dot status-dot--active' : 'status-dot';
}

function showToast(icon, text) {
    const t = document.getElementById('toast');
    document.getElementById('toast-icon').textContent = icon;
    document.getElementById('toast-text').textContent = text;
    t.classList.add('visible');
    setTimeout(() => t.classList.remove('visible'), 3000);
}

function escHtml(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }
function escAttr(s) { return s.replace(/"/g, '&quot;').replace(/'/g, '&#39;'); }
