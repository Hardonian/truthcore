import type { RunData, DashboardState, Finding, Severity, VerdictState } from './types';
import { RunLoader, StateManager, FilterManager } from './utils/data';
import { generateBarChart, generatePieChart, generateTrendChart } from './utils/charts';

// Initialize managers
const runLoader = new RunLoader();
const stateManager = new StateManager();
const filterManager = new FilterManager();

// DOM elements
const app = document.getElementById('app')!;
const runsView = document.getElementById('runs-view')!;
const runDetailView = document.getElementById('run-detail-view')!;
const settingsView = document.getElementById('settings-view')!;
const emptyState = document.getElementById('empty-state')!;
const runsList = document.getElementById('runs-list')!;
const statsGrid = document.getElementById('stats-grid')!;
const runsCount = document.getElementById('runs-count')!;
const themeToggle = document.getElementById('theme-toggle')!;
const importBtn = document.getElementById('import-btn')!;
const exportBtn = document.getElementById('export-btn')!;
const emptyImportBtn = document.getElementById('empty-import-btn')!;
const fileInput = document.getElementById('file-input') as HTMLInputElement;
const backBtn = document.getElementById('back-btn')!;
const detailTitle = document.getElementById('detail-title')!;
const detailVerdict = document.getElementById('detail-verdict')!;
const detailStats = document.getElementById('detail-stats')!;
const tabContent = document.getElementById('tab-content')!;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
  stateManager.loadTheme();
  applyTheme();
  setupEventListeners();
  loadEmbeddedRuns();
});

function setupEventListeners(): void {
  // Theme toggle
  themeToggle.addEventListener('click', () => {
    const current = stateManager.getState().theme;
    const next = current === 'light' ? 'dark' : 'light';
    stateManager.setState({ theme: next });
    stateManager.saveTheme();
    applyTheme();
  });
  
  // Import
  importBtn.addEventListener('click', handleImport);
  emptyImportBtn.addEventListener('click', handleImport);
  fileInput.addEventListener('change', handleFileSelect);
  
  // Export
  exportBtn.addEventListener('click', handleExport);
  
  // Navigation
  document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const view = (btn as HTMLElement).dataset.view as 'runs' | 'settings';
      stateManager.setState({ view });
      renderView();
    });
  });
  
  // Back button
  backBtn.addEventListener('click', () => {
    stateManager.setState({ view: 'runs', selectedRunId: null });
    renderView();
  });
  
  // Tabs
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const tab = (btn as HTMLElement).dataset.tab!;
      renderTab(tab);
    });
  });
}

function applyTheme(): void {
  const theme = stateManager.getState().theme;
  document.documentElement.setAttribute('data-theme', theme);
}

async function loadEmbeddedRuns(): Promise<void> {
  const runs = await runLoader.loadFromEmbedded();
  if (runs.length > 0) {
    stateManager.setState({ runs });
    renderRunsView();
  } else {
    showEmptyState();
  }
}

function handleImport(): void {
  // Try to use File System Access API
  if ('showDirectoryPicker' in window) {
    importWithPicker();
  } else {
    // Fall back to file input
    fileInput.click();
  }
}

async function importWithPicker(): Promise<void> {
  try {
    const dirHandle = await (window as unknown as { showDirectoryPicker: () => Promise<FileSystemDirectoryHandle> }).showDirectoryPicker();
    const runs = await runLoader.loadFromDirectoryHandle(dirHandle);
    stateManager.setState({ runs });
    renderRunsView();
  } catch (e) {
    console.error('Import failed:', e);
    alert('Failed to import runs. Please try again.');
  }
}

async function handleFileSelect(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement;
  const files = input.files;
  if (!files || files.length === 0) return;
  
  // Process files - simplified version
  alert('File import via input is limited. Use the File System Access API for better results.');
}

async function handleExport(): Promise<void> {
  const { runs } = stateManager.getState();
  if (runs.length === 0) {
    alert('No runs to export');
    return;
  }
  
  try {
    const dirHandle = await (window as unknown as { showDirectoryPicker: () => Promise<FileSystemDirectoryHandle> }).showDirectoryPicker();
    
    // Create snapshot
    const runsDir = await dirHandle.getDirectoryHandle('runs', { create: true });
    
    for (const run of runs) {
      const runDir = await runsDir.getDirectoryHandle(run.run_id, { create: true });
      
      if (run.manifest) {
        await writeFile(runDir, 'run_manifest.json', JSON.stringify(run.manifest, null, 2));
      }
      if (run.verdict) {
        await writeFile(runDir, 'verdict.json', JSON.stringify(run.verdict, null, 2));
      }
      if (run.readiness) {
        await writeFile(runDir, 'readiness.json', JSON.stringify(run.readiness, null, 2));
      }
      if (run.invariants) {
        await writeFile(runDir, 'invariants.json', JSON.stringify(run.invariants, null, 2));
      }
      if (run.policy) {
        await writeFile(runDir, 'policy_findings.json', JSON.stringify(run.policy, null, 2));
      }
    }
    
    // Create embedded data file
    const dashboardDir = await dirHandle.getDirectoryHandle('dashboard', { create: true });
    await writeFile(dashboardDir, 'embedded-runs.js', `window.__EMBEDDED_RUNS__ = ${JSON.stringify(runs)};`);
    
    alert('Snapshot exported successfully!');
  } catch (e) {
    console.error('Export failed:', e);
    alert('Export failed. Please try again.');
  }
}

async function writeFile(dirHandle: FileSystemDirectoryHandle, filename: string, content: string): Promise<void> {
  const fileHandle = await dirHandle.getFileHandle(filename, { create: true });
  const writable = await fileHandle.createWritable();
  await writable.write(content);
  await writable.close();
}

function renderView(): void {
  const state = stateManager.getState();
  
  // Update nav buttons
  document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.classList.toggle('active', (btn as HTMLElement).dataset.view === state.view);
  });
  
  // Show/hide views
  runsView.style.display = state.view === 'runs' ? 'block' : 'none';
  runDetailView.style.display = state.view === 'run-detail' ? 'block' : 'none';
  settingsView.style.display = state.view === 'settings' ? 'block' : 'none';
  
  if (state.view === 'runs') {
    renderRunsView();
  } else if (state.view === 'run-detail' && state.selectedRunId) {
    renderRunDetail(state.selectedRunId);
  }
}

function showEmptyState(): void {
  runsView.style.display = 'none';
  emptyState.style.display = 'block';
}

function renderRunsView(): void {
  const { runs } = stateManager.getState();
  
  if (runs.length === 0) {
    showEmptyState();
    return;
  }
  
  emptyState.style.display = 'none';
  runsView.style.display = 'block';
  
  // Update count
  runsCount.textContent = `${runs.length} run${runs.length === 1 ? '' : 's'}`;
  
  // Render stats
  renderStats(runs);
  
  // Render runs list
  runsList.innerHTML = runs.map(run => renderRunItem(run)).join('');
  
  // Add click handlers
  runsList.querySelectorAll('.run-item').forEach((item, index) => {
    item.addEventListener('click', () => {
      const run = runs[index];
      stateManager.setState({ view: 'run-detail', selectedRunId: run.run_id });
      renderView();
    });
  });
}

function renderStats(runs: RunData[]): void {
  const totalRuns = runs.length;
  const passRuns = runs.filter(r => r.verdict?.verdict === 'PASS').length;
  const failRuns = runs.filter(r => r.verdict?.verdict === 'FAIL').length;
  const avgScore = runs.length > 0
    ? Math.round(runs.reduce((sum, r) => sum + (r.verdict?.score || 0), 0) / runs.length)
    : 0;
  
  const totalFindings = runs.reduce((sum, r) => sum + (r.verdict?.total_findings || 0), 0);
  
  statsGrid.innerHTML = `
    <div class="stat-card">
      <div class="stat-value">${totalRuns}</div>
      <div class="stat-label">Total Runs</div>
    </div>
    <div class="stat-card">
      <div class="stat-value" style="color: var(--success);">${passRuns}</div>
      <div class="stat-label">Passed</div>
    </div>
    <div class="stat-card">
      <div class="stat-value" style="color: var(--danger);">${failRuns}</div>
      <div class="stat-label">Failed</div>
    </div>
    <div class="stat-card">
      <div class="stat-value">${avgScore}</div>
      <div class="stat-label">Avg Score</div>
    </div>
    <div class="stat-card">
      <div class="stat-value">${totalFindings}</div>
      <div class="stat-label">Total Findings</div>
    </div>
  `;
}

function renderRunItem(run: RunData): string {
  const verdict = run.verdict?.verdict || 'UNKNOWN';
  const score = run.verdict?.score || 0;
  const timestamp = run.manifest?.timestamp || 'Unknown';
  const profile = run.manifest?.profile || 'default';
  const duration = run.manifest?.duration_ms || 0;
  
  const verdictClass = verdict === 'PASS' ? 'badge-pass' : verdict === 'FAIL' ? 'badge-fail' : 'badge-conditional';
  
  return `
    <div class="run-item">
      <div class="run-item-left">
        <span class="badge ${verdictClass}">${verdict}</span>
        <div class="run-info">
          <h3>${run.run_id}</h3>
          <div class="run-meta">
            ${timestamp} • Profile: ${profile} • Duration: ${duration}ms
          </div>
        </div>
      </div>
      <div class="run-score" style="color: ${score >= 90 ? 'var(--success)' : score >= 70 ? 'var(--warning)' : 'var(--danger)'};">
        ${score}
      </div>
    </div>
  `;
}

function renderRunDetail(runId: string): void {
  const { runs } = stateManager.getState();
  const run = runs.find(r => r.run_id === runId);
  if (!run) return;
  
  // Update header
  detailTitle.textContent = `Run: ${run.run_id}`;
  const verdict = run.verdict?.verdict || 'UNKNOWN';
  detailVerdict.textContent = verdict;
  detailVerdict.className = `badge ${verdict === 'PASS' ? 'badge-pass' : verdict === 'FAIL' ? 'badge-fail' : 'badge-conditional'}`;
  
  // Update stats
  const score = run.verdict?.score || 0;
  const findings = run.verdict?.total_findings || 0;
  const duration = run.manifest?.duration_ms || 0;
  const profile = run.manifest?.profile || 'default';
  
  detailStats.innerHTML = `
    <div class="stat-card">
      <div class="stat-value">${score}</div>
      <div class="stat-label">Score</div>
    </div>
    <div class="stat-card">
      <div class="stat-value">${findings}</div>
      <div class="stat-label">Findings</div>
    </div>
    <div class="stat-card">
      <div class="stat-value">${duration}ms</div>
      <div class="stat-label">Duration</div>
    </div>
    <div class="stat-card">
      <div class="stat-value">${profile}</div>
      <div class="stat-label">Profile</div>
    </div>
  `;
  
  // Render initial tab (overview)
  document.querySelectorAll('.tab-btn').forEach((btn, i) => {
    btn.classList.toggle('active', i === 0);
  });
  renderTab('overview');
}

function renderTab(tab: string): void {
  const { runs, selectedRunId } = stateManager.getState();
  const run = runs.find(r => r.run_id === selectedRunId);
  if (!run) return;
  
  switch (tab) {
    case 'overview':
      renderOverviewTab(run);
      break;
    case 'findings':
      renderFindingsTab(run);
      break;
    case 'invariants':
      renderInvariantsTab(run);
      break;
    case 'policy':
      renderPolicyTab(run);
      break;
    case 'provenance':
      renderProvenanceTab(run);
      break;
    case 'files':
      renderFilesTab(run);
      break;
  }
}

function renderOverviewTab(run: RunData): void {
  let html = '<div class="overview-content">';
  
  // Severity distribution chart
  if (run.verdict?.findings_by_severity) {
    const severityData = Object.entries(run.verdict.findings_by_severity)
      .filter(([, count]) => count > 0)
      .map(([label, value]) => ({ label, value, color: getSeverityColor(label as Severity) }));
    
    if (severityData.length > 0) {
      html += '<div class="card">';
      html += '<h3 class="card-title">Severity Distribution</h3>';
      html += generateBarChart(severityData, { width: 600, height: 300 });
      html += '</div>';
    }
  }
  
  // Engine breakdown
  if (run.verdict?.findings) {
    const engineCounts: Record<string, number> = {};
    run.verdict.findings.forEach(f => {
      engineCounts[f.engine] = (engineCounts[f.engine] || 0) + 1;
    });
    
    const engineData = Object.entries(engineCounts).map(([label, value]) => ({ label, value }));
    if (engineData.length > 0) {
      html += '<div class="card">';
      html += '<h3 class="card-title">Findings by Engine</h3>';
      html += generatePieChart(engineData, { width: 400, height: 300, innerRadius: 50 });
      html += '</div>';
    }
  }
  
  html += '</div>';
  tabContent.innerHTML = html;
}

function renderFindingsTab(run: RunData): void {
  const findings = run.verdict?.findings || [];
  
  if (findings.length === 0) {
    tabContent.innerHTML = '<div class="empty-state"><p>No findings for this run</p></div>';
    return;
  }
  
  // Filter bar
  let html = `
    <div class="filter-bar">
      <div class="filter-group">
        <span class="filter-label">Search:</span>
        <input type="text" class="filter-input" id="findings-search" placeholder="Search findings...">
      </div>
      <div class="filter-group">
        <span class="filter-label">Severity:</span>
        <select class="filter-select" id="findings-severity">
          <option value="">All</option>
          <option value="BLOCKER">Blocker</option>
          <option value="CRITICAL">Critical</option>
          <option value="HIGH">High</option>
          <option value="MEDIUM">Medium</option>
          <option value="LOW">Low</option>
          <option value="INFO">Info</option>
        </select>
      </div>
    </div>
  `;
  
  // Findings table
  html += '<div class="table-container"><table class="table"><thead><tr>';
  html += '<th>Severity</th><th>Category</th><th>Engine</th><th>Rule</th><th>Message</th>';
  html += '</tr></thead><tbody>';
  
  findings.forEach(finding => {
    html += `<tr>
      <td><span class="badge badge-severity-${finding.severity.toLowerCase()}">${finding.severity}</span></td>
      <td>${escapeHtml(finding.category)}</td>
      <td>${escapeHtml(finding.engine)}</td>
      <td>${escapeHtml(finding.rule)}</td>
      <td>${escapeHtml(finding.message)}</td>
    </tr>`;
  });
  
  html += '</tbody></table></div>';
  tabContent.innerHTML = html;
  
  // Add filter handlers
  const searchInput = document.getElementById('findings-search') as HTMLInputElement;
  const severitySelect = document.getElementById('findings-severity') as HTMLSelectElement;
  
  const applyFilters = () => {
    const search = searchInput.value.toLowerCase();
    const severity = severitySelect.value as Severity | '';
    
    filterManager.setFilters({ search, severity: severity ? [severity] : [] });
    // Re-render with filters (simplified - in production, filter the DOM or re-render)
  };
  
  searchInput?.addEventListener('input', applyFilters);
  severitySelect?.addEventListener('change', applyFilters);
}

function renderInvariantsTab(run: RunData): void {
  const results = run.invariants?.results || [];
  
  if (results.length === 0) {
    tabContent.innerHTML = '<div class="empty-state"><p>No invariants for this run</p></div>';
    return;
  }
  
  let html = '<div class="table-container"><table class="table"><thead><tr>';
  html += '<th>Rule</th><th>Status</th><th>Severity</th><th>Message</th>';
  html += '</tr></thead><tbody>';
  
  results.forEach(result => {
    const statusBadge = result.passed 
      ? '<span class="badge badge-pass">PASS</span>' 
      : '<span class="badge badge-fail">FAIL</span>';
    
    html += `<tr>
      <td>${escapeHtml(result.name)}</td>
      <td>${statusBadge}</td>
      <td><span class="badge badge-severity-${result.severity.toLowerCase()}">${result.severity}</span></td>
      <td>${escapeHtml(result.message || '')}</td>
    </tr>`;
  });
  
  html += '</tbody></table></div>';
  tabContent.innerHTML = html;
}

function renderPolicyTab(run: RunData): void {
  const findings = run.policy?.findings || [];
  
  if (findings.length === 0) {
    tabContent.innerHTML = '<div class="empty-state"><p>No policy findings for this run</p></div>';
    return;
  }
  
  let html = '<div class="table-container"><table class="table"><thead><tr>';
  html += '<th>Rule</th><th>Severity</th><th>Message</th><th>File</th>';
  html += '</tr></thead><tbody>';
  
  findings.forEach(finding => {
    html += `<tr>
      <td>${escapeHtml(finding.rule_id)}</td>
      <td><span class="badge badge-severity-${finding.severity.toLowerCase()}">${finding.severity}</span></td>
      <td>${escapeHtml(finding.message)}</td>
      <td>${escapeHtml(finding.file || '')}</td>
    </tr>`;
  });
  
  html += '</tbody></table></div>';
  tabContent.innerHTML = html;
}

function renderProvenanceTab(run: RunData): void {
  if (!run.provenance && !run.manifest) {
    tabContent.innerHTML = '<div class="empty-state"><p>No provenance data for this run</p></div>';
    return;
  }
  
  let html = '<div class="card">';
  html += '<h3 class="card-title">Provenance Information</h3>';
  html += '<table class="table"><tbody>';
  
  if (run.manifest) {
    html += `<tr><td>Run ID</td><td>${escapeHtml(run.manifest.run_id)}</td></tr>`;
    html += `<tr><td>Timestamp</td><td>${escapeHtml(run.manifest.timestamp)}</td></tr>`;
    html += `<tr><td>Input Hash</td><td><code>${escapeHtml(run.manifest.input_hash)}</code></td></tr>`;
    html += `<tr><td>Config Hash</td><td><code>${escapeHtml(run.manifest.config_hash)}</code></td></tr>`;
  }
  
  if (run.provenance) {
    html += `<tr><td>Bundle Hash</td><td><code>${escapeHtml(run.provenance.bundle_hash)}</code></td></tr>`;
    html += `<tr><td>Files in Bundle</td><td>${run.provenance.files.length}</td></tr>`;
    if (run.provenance.signature) {
      html += `<tr><td>Signed</td><td><span class="badge badge-pass">Yes</span></td></tr>`;
      html += `<tr><td>Signature Algorithm</td><td>${escapeHtml(run.provenance.signature.algorithm)}</td></tr>`;
    }
  }
  
  html += '</tbody></table></div>';
  tabContent.innerHTML = html;
}

function renderFilesTab(run: RunData): void {
  if (run.files.length === 0) {
    tabContent.innerHTML = '<div class="empty-state"><p>No files recorded for this run</p></div>';
    return;
  }
  
  let html = '<ul class="file-list">';
  run.files.forEach(file => {
    const icon = getFileIcon(file);
    html += `<li class="file-item"><span class="file-icon">${icon}</span>${escapeHtml(file)}</li>`;
  });
  html += '</ul>';
  tabContent.innerHTML = html;
}

function getSeverityColor(severity: Severity): string {
  const colors: Record<Severity, string> = {
    'BLOCKER': '#dc2626',
    'CRITICAL': '#dc2626',
    'HIGH': '#ea580c',
    'MEDIUM': '#d97706',
    'LOW': '#65a30d',
    'INFO': '#0891b2',
  };
  return colors[severity];
}

function getFileIcon(filename: string): string {
  if (filename.endsWith('.json')) return '📋';
  if (filename.endsWith('.md')) return '📝';
  if (filename.endsWith('.csv')) return '📊';
  if (filename.endsWith('.yaml') || filename.endsWith('.yml')) return '⚙️';
  if (filename.includes('sig')) return '🔏';
  return '📄';
}

function escapeHtml(text: string): string {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}
