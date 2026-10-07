const state = { user: null, csrf: null, projects: [], projectId: null, users: [] };
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

function escapeHtml(value = '') {
  return String(value).replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
}

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (state.csrf && !['GET', 'HEAD'].includes((options.method || 'GET').toUpperCase())) headers.set('X-CSRF-Token', state.csrf);
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  const response = await fetch(`/api${path}`, {...options, headers, credentials: 'same-origin'});
  if (response.status === 401) { showLogin(); throw new Error('Your session has expired.'); }
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try { const data = await response.json(); message = data.detail || message; } catch (_) {}
    throw new Error(message);
  }
  return response.status === 204 ? null : response.json();
}

function toast(message, error = false) {
  const node = $('#toast');
  node.textContent = message;
  node.classList.toggle('error-toast', error);
  node.classList.remove('hidden');
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => node.classList.add('hidden'), 4500);
}

function showLogin() {
  state.user = null; state.csrf = null;
  $('#app-view').classList.add('hidden');
  $('#login-view').classList.remove('hidden');
}

async function showApp() {
  $('#login-view').classList.add('hidden');
  $('#app-view').classList.remove('hidden');
  $('#current-user').textContent = state.user.display_name;
  $('#admin-nav').classList.toggle('hidden', !state.user.is_admin);
  await loadProjects();
  route();
}

async function loadProjects() {
  state.projects = await api('/projects');
  const saved = Number(localStorage.getItem('lt_project'));
  state.projectId = state.projects.some(p => p.id === saved) ? saved : state.projects[0]?.id || null;
  const select = $('#project-select');
  select.innerHTML = state.projects.map(p => `<option value="${p.id}">${escapeHtml(p.key)} — ${escapeHtml(p.name)}</option>`).join('');
  if (state.projectId) select.value = state.projectId;
  applyProjectPermissions();
}

function currentProject() { return state.projects.find(project => project.id === state.projectId); }
function canManage() { return state.user?.is_admin || currentProject()?.role === 'manager'; }
function applyProjectPermissions() { $('[data-route="import"]').classList.toggle('hidden', !canManage()); }

function projectRequired() {
  if (state.projectId) return true;
  $('#content').innerHTML = pageHead('No project selected', 'Ask an administrator to add you to a project.') + '<div class="empty">No accessible projects.</div>';
  return false;
}

function pageHead(title, subtitle = '', actions = '') {
  return `<header class="page-head"><div><p class="eyebrow">LEX TABULARUM / OPERATIONS</p><h1>${escapeHtml(title)}</h1><p>${escapeHtml(subtitle)}</p></div><div class="actions">${actions}</div></header>`;
}

function activeNav(routeName) {
  $$('[data-route]').forEach(link => link.classList.toggle('active', link.dataset.route === routeName));
  $('#sidebar').classList.remove('open');
}

function formatDate(value) {
  if (!value) return '—';
  return new Intl.DateTimeFormat(undefined, {dateStyle: 'medium', timeStyle: 'short'}).format(new Date(value));
}

function setContent(html, routeName) {
  $('#content').innerHTML = html;
  activeNav(routeName);
  $('#content').focus({preventScroll: true});
}

async function renderDashboard() {
  if (!projectRequired()) return;
  const data = await api(`/projects/${state.projectId}/dashboard`);
  const total = data.total_executions || 0;
  const width = value => total ? value / total * 100 : 0;
  const recentRows = data.recent_runs.map(run => `<tr><td><a class="panel-link" href="#/runs/${run.id}">${escapeHtml(run.name)}</a><br><small class="muted">${formatDate(run.created_at)}</small></td><td>${run.total}</td><td><div class="mini-meter"><div class="progress"><span style="width:${run.completion_rate}%"></span></div><small>${run.completed}/${run.total} complete</small></div></td><td>${run.pass_rate === null ? '—' : `${run.pass_rate}%`}</td><td><span class="badge ${run.failed ? 'failed' : ''}">${run.failed} failed</span></td></tr>`).join('');
  const workloadRows = data.workload.slice(0, 8).map(item => `<tr><td>${escapeHtml(item.display_name)}</td><td>${item.total}</td><td>${item.states.not_started || 0}</td><td>${item.states.in_progress || 0}</td><td>${item.states.failed || 0}</td></tr>`).join('');
  setContent(pageHead('Operations dashboard', 'Live execution posture for the selected project.', '<a href="#/reports"><button>Open reports</button></a>') + `
    <section class="grid">
      <div class="metric span-3"><span>Case library</span><strong>${data.case_count}</strong><p class="widget-note">Reusable test definitions</p></div>
      <div class="metric span-3"><span>Open runs</span><strong>${data.open_runs}</strong><p class="widget-note">Active execution sets</p></div>
      <div class="metric good span-3"><span>Completion rate</span><strong>${data.completion_rate}%</strong><p class="widget-note">${total} total executions</p></div>
      <div class="metric ${data.states.failed ? 'bad' : 'good'} span-3"><span>Pass rate</span><strong>${data.pass_rate === null ? '—' : `${data.pass_rate}%`}</strong><p class="widget-note">${data.states.failed || 0} recorded failures</p></div>
      <div class="panel span-8"><h2>Execution state distribution</h2>
        <div class="state-distribution" title="Execution status distribution">
          <span class="passed" style="width:${width(data.states.passed || 0)}%"></span><span class="failed" style="width:${width(data.states.failed || 0)}%"></span><span class="blocked" style="width:${width(data.states.blocked || 0)}%"></span><span class="in-progress" style="width:${width(data.states.in_progress || 0)}%"></span><span class="waiting" style="width:${width(data.states.not_started || 0)}%"></span><span class="skipped" style="width:${width(data.states.skipped || 0)}%"></span>
        </div>
        <div class="state-legend"><span class="legend-key" style="--key-color:#3a9160">Passed ${data.states.passed || 0}</span><span class="legend-key" style="--key-color:#b64b42">Failed ${data.states.failed || 0}</span><span class="legend-key" style="--key-color:#ce8b2d">Blocked ${data.states.blocked || 0}</span><span class="legend-key" style="--key-color:#3f78aa">In progress ${data.states.in_progress || 0}</span><span class="legend-key" style="--key-color:#aebbc4">Waiting ${data.states.not_started || 0}</span><span class="legend-key" style="--key-color:#7f8c94">Skipped ${data.states.skipped || 0}</span></div>
      </div>
      <div class="panel span-4"><h2>Attention queue</h2><table><tbody><tr><td>Unassigned cases</td><td><strong>${data.unassigned}</strong></td></tr><tr><td>Blocked</td><td><strong>${data.states.blocked || 0}</strong></td></tr><tr><td>In progress</td><td><strong>${data.states.in_progress || 0}</strong></td></tr><tr><td>Not started</td><td><strong>${data.states.not_started || 0}</strong></td></tr></tbody></table></div>
      <div class="panel span-8"><h2>Recent test runs</h2>${recentRows ? `<div class="table-wrap"><table><thead><tr><th>Run</th><th>Total</th><th>Completion</th><th>Pass rate</th><th>Failures</th></tr></thead><tbody>${recentRows}</tbody></table></div>` : '<div class="empty">No test runs yet.</div>'}</div>
      <div class="panel span-4"><h2>Tester workload</h2>${workloadRows ? `<div class="table-wrap"><table><thead><tr><th>Tester</th><th>Total</th><th>Queue</th><th>Active</th><th>Failed</th></tr></thead><tbody>${workloadRows}</tbody></table></div>` : '<div class="empty">No assigned executions.</div>'}</div>
    </section>`, 'dashboard');
}

async function renderReports() {
  if (!projectRequired()) return;
  const runs = await api(`/projects/${state.projectId}/runs`);
  setContent(pageHead('Execution reports', 'Filter, review, print, or export test execution evidence.', '<button id="print-report">Print report</button><button id="export-report" class="primary">Export CSV</button>') + `
    <form id="report-controls" class="report-controls">
      <label>Test run<select name="run_id"><option value="">All runs</option>${runs.map(run => `<option value="${run.id}">${escapeHtml(run.name)}</option>`).join('')}</select></label>
      <label>Result<select name="state"><option value="">All states</option><option value="not_started">Not started</option><option value="in_progress">In progress</option><option value="passed">Passed</option><option value="failed">Failed</option><option value="blocked">Blocked</option><option value="skipped">Skipped</option></select></label>
      <label>Search current results<input name="search" type="search" placeholder="Case, title, module, tester…"></label>
      <button type="submit">Apply filters</button>
    </form>
    <section id="report-summary" class="grid report-summary"></section>
    <div id="report-results" class="table-wrap"></div>`, 'reports');

  let report = null;
  const paintRows = () => {
    if (!report) return;
    const search = $('#report-controls').search.value.trim().toLowerCase();
    const rows = report.rows.filter(row => !search || [row.case_id, row.title, row.section, row.assignee, row.run_name, row.notes].some(value => String(value || '').toLowerCase().includes(search)));
    $('#report-results').innerHTML = rows.length ? `<table class="report-table"><thead><tr><th>Run</th><th>Case</th><th>Title / module</th><th>Priority</th><th>Assignee</th><th>Result</th><th>Completed</th><th>Notes / issue</th></tr></thead><tbody>${rows.map(row => `<tr><td>${escapeHtml(row.run_name)}</td><td class="mono"><strong>${escapeHtml(row.case_id)}</strong></td><td>${escapeHtml(row.title)}<br><small class="muted">${escapeHtml(row.section)}</small></td><td>${escapeHtml(row.priority || '—')}</td><td>${escapeHtml(row.assignee || 'Unassigned')}</td><td><span class="badge ${row.state}">${escapeHtml(row.state.replaceAll('_',' '))}</span></td><td>${formatDate(row.completed_at)}</td><td class="notes-cell" title="${escapeHtml(row.notes || '')}">${escapeHtml(row.notes || '—')}${row.gitlab_issue_url ? `<br><a href="${escapeHtml(row.gitlab_issue_url)}" target="_blank" rel="noopener">GitLab issue ↗</a>` : ''}</td></tr>`).join('')}</tbody></table>` : '<div class="empty">No executions match these filters.</div>';
  };
  const loadReport = async () => {
    const form = $('#report-controls'); const params = new URLSearchParams();
    if (form.run_id.value) params.set('run_id', form.run_id.value);
    if (form.state.value) params.set('state', form.state.value);
    report = await api(`/projects/${state.projectId}/reports/executions?${params}`);
    $('#report-summary').innerHTML = `<div class="metric span-3"><span>Executions</span><strong>${report.total}</strong></div><div class="metric good span-3"><span>Completion</span><strong>${report.completion_rate}%</strong></div><div class="metric good span-3"><span>Pass rate</span><strong>${report.pass_rate === null ? '—' : `${report.pass_rate}%`}</strong></div><div class="metric ${report.counts.failed ? 'bad' : 'good'} span-3"><span>Failures</span><strong>${report.counts.failed}</strong></div>`;
    paintRows();
  };
  $('#report-controls').onsubmit = event => { event.preventDefault(); loadReport().catch(error => toast(error.message, true)); };
  $('#report-controls').search.oninput = paintRows;
  $('#print-report').onclick = () => window.print();
  $('#export-report').onclick = () => {
    if (!report) return;
    const columns = ['Run','Case ID','Title','Module','Priority','Assignee','Result','Completed','Notes','GitLab issue'];
    const quote = value => `"${String(value ?? '').replaceAll('"','""')}"`;
    const csv = [columns, ...report.rows.map(row => [row.run_name,row.case_id,row.title,row.section,row.priority,row.assignee,row.state,row.completed_at,row.notes,row.gitlab_issue_url])].map(row => row.map(quote).join(',')).join('\r\n');
    const url = URL.createObjectURL(new Blob([csv], {type:'text/csv;charset=utf-8'}));
    const link = document.createElement('a'); link.href = url; link.download = `lex-tabularum-report-${new Date().toISOString().slice(0,10)}.csv`; link.click(); URL.revokeObjectURL(url);
  };
  await loadReport();
}

async function renderCases() {
  if (!projectRequired()) return;
  const cases = await api(`/projects/${state.projectId}/cases`);
  let rows = cases.map(item => `<tr><td class="mono"><strong>${escapeHtml(item.external_id)}</strong></td><td>${escapeHtml(item.title)}</td><td>${escapeHtml(item.section)}</td><td><span class="badge">${escapeHtml(item.priority || '—')}</span></td><td>r${item.version}</td></tr>`).join('');
  setContent(pageHead('Test library', `${cases.length} reusable cases in the selected project.`, canManage() ? '<a href="#/import"><button>Import Markdown</button></a>' : '') +
    (cases.length ? `<div class="table-wrap"><table><thead><tr><th>ID</th><th>Title</th><th>Module</th><th>Priority</th><th>Revision</th></tr></thead><tbody>${rows}</tbody></table></div>` : '<div class="empty">No cases imported yet.</div>'), 'cases');
}

async function renderImport() {
  if (!projectRequired()) return;
  if (!canManage()) { location.hash = '#/cases'; return; }
  setContent(pageHead('Import test plan', 'Existing IDs are updated as new revisions; unchanged cases are left alone.') + `
    <section class="grid"><div class="panel span-8"><h2>Markdown source</h2>
      <form id="import-form" class="stack"><label>Test plan file (.md)<input name="file" type="file" accept=".md,.markdown,text/markdown" required></label>
      <p class="muted">Each case requires an ID/title heading, numbered steps, and an <span class="mono">Expected:</span> line.</p>
      <button class="primary" type="submit">Validate and import</button></form></div>
      <aside class="panel span-4"><h2>Recognized pattern</h2><pre class="mono">### PR-001 — Login (\`P0\`)\n\n1. Open the form.\n2. Sign in.\n\nExpected: Dashboard opens.</pre></aside></section>`, 'import');
  $('#import-form').addEventListener('submit', async event => {
    event.preventDefault();
    const button = $('button', event.target); button.disabled = true; button.textContent = 'Importing…';
    try {
      const result = await api(`/projects/${state.projectId}/imports`, {method: 'POST', body: new FormData(event.target)});
      toast(`${result.created} created, ${result.updated} updated, ${result.unchanged} unchanged.`);
      location.hash = '#/cases';
    } catch (error) { toast(error.message, true); button.disabled = false; button.textContent = 'Validate and import'; }
  });
}

async function renderRuns() {
  if (!projectRequired()) return;
  const [runs, cases, members] = await Promise.all([
    api(`/projects/${state.projectId}/runs`), api(`/projects/${state.projectId}/cases`), api(`/projects/${state.projectId}/members`)
  ]);
  const rows = runs.map(run => {
    const complete = (run.counts.passed || 0) + (run.counts.failed || 0) + (run.counts.blocked || 0) + (run.counts.skipped || 0);
    const pct = run.total ? Math.round(complete / run.total * 100) : 0;
    return `<tr><td><a href="#/runs/${run.id}"><strong>${escapeHtml(run.name)}</strong></a><br><small class="muted">${escapeHtml(run.description)}</small></td><td>${run.total}</td><td><div class="progress"><span style="width:${pct}%"></span></div><small>${pct}% complete</small></td><td><span class="badge">${escapeHtml(run.status)}</span></td></tr>`;
  }).join('');
  setContent(pageHead('Test runs', 'Release, regression, and acceptance execution sets.', canManage() ? '<button id="new-run-button" class="primary">New test run</button>' : '') + `
    <div id="new-run-panel" class="panel hidden"><h2>Create run</h2><form id="run-form" class="form-grid">
      <label>Name<input name="name" required maxlength="240" placeholder="Release 2.4 regression"></label>
      <label>Default assignee<select name="assigned_to"><option value="">Unassigned</option>${members.filter(m => m.role !== 'viewer').map(m => `<option value="${m.id}">${escapeHtml(m.display_name)}</option>`).join('')}</select></label>
      <label class="wide">Description<textarea name="description"></textarea></label>
      <label class="wide">Cases<select name="case_ids" multiple size="8">${cases.map(c => `<option value="${c.id}" selected>${escapeHtml(c.external_id)} — ${escapeHtml(c.title)}</option>`).join('')}</select></label>
      <div class="wide actions"><button class="primary" type="submit">Create run</button><button type="button" id="cancel-run">Cancel</button></div>
    </form></div>
    <div class="table-wrap">${runs.length ? `<table><thead><tr><th>Run</th><th>Cases</th><th>Progress</th><th>Status</th></tr></thead><tbody>${rows}</tbody></table>` : '<div class="empty">No runs created yet.</div>'}</div>`, 'runs');
  if ($('#new-run-button')) $('#new-run-button').onclick = () => $('#new-run-panel').classList.remove('hidden');
  $('#cancel-run').onclick = () => $('#new-run-panel').classList.add('hidden');
  $('#run-form').onsubmit = async event => {
    event.preventDefault(); const form = event.target;
    const payload = {name: form.name.value, description: form.description.value,
      assigned_to: form.assigned_to.value ? Number(form.assigned_to.value) : null,
      case_ids: [...form.case_ids.selectedOptions].map(option => Number(option.value))};
    try { const run = await api(`/projects/${state.projectId}/runs`, {method:'POST', body:JSON.stringify(payload)}); location.hash = `#/runs/${run.id}`; }
    catch (error) { toast(error.message, true); }
  };
}

async function renderRun(runId) {
  if (!projectRequired()) return;
  const [run, members] = await Promise.all([api(`/projects/${state.projectId}/runs/${runId}`), api(`/projects/${state.projectId}/members`)]);
  const cases = run.cases.map(item => `<article class="case-card" data-run-case="${item.id}">
    <div class="case-summary" role="button" tabindex="0" aria-expanded="false"><strong class="mono">${escapeHtml(item.external_id)}</strong><span>${escapeHtml(item.title)}</span><span>${escapeHtml(item.assignee || 'Unassigned')}</span><span class="badge ${item.state}">${escapeHtml(item.state.replace('_',' '))}</span></div>
    <div class="case-detail hidden"><ol>${item.steps.map(step => `<li>${escapeHtml(step)}</li>`).join('')}</ol><p class="expected"><strong>Expected:</strong> ${escapeHtml(item.expected)}</p>
      <p class="issue-slot">${item.gitlab_issue_url ? `<a href="${escapeHtml(item.gitlab_issue_url)}" target="_blank" rel="noopener">Open GitLab issue ↗</a>` : ''}</p>
      ${canManage() ? `<form class="assignment-form form-grid"><label>Assignee<select name="assigned_to"><option value="">Unassigned</option>${members.filter(member => member.role !== 'viewer').map(member => `<option value="${member.id}" ${member.id === item.assigned_to ? 'selected' : ''}>${escapeHtml(member.display_name)}</option>`).join('')}</select></label><div><button type="submit">Update assignment</button></div></form>` : ''}
      <div class="run-tools">
        <label>Result<select class="result-state">${[['in_progress','In progress'],['passed','Passed'],['failed','Failed'],['blocked','Blocked'],['skipped','Skipped']].map(([value,label]) => `<option value="${value}" ${value === item.state ? 'selected' : ''}>${label}</option>`).join('')}</select></label>
        <label>Execution notes<textarea class="result-notes" placeholder="Required when failed">${escapeHtml(item.notes)}</textarea></label>
        <button class="save-result primary">Save result</button>
      </div>
      <form class="evidence-form stack"><label>Failure screenshot<input name="file" type="file" accept="image/png,image/jpeg,image/webp,image/gif"></label><div class="actions"><button type="submit">Upload evidence</button><span class="inline-status" aria-live="polite"></span></div></form>
      <div class="evidence-list">${item.evidence.map(file => `<a href="/api/projects/${state.projectId}/evidence/${file.id}" target="_blank">${escapeHtml(file.name)}</a>`).join('<br>')}</div>
    </div></article>`).join('');
  setContent(pageHead(run.name, run.description, '<a href="#/runs"><button>Back to runs</button></a>') + (cases || '<div class="empty">This run is empty.</div>'), 'runs');
  $$('.case-summary').forEach(summary => {
    const toggle = () => { const detail = summary.nextElementSibling; detail.classList.toggle('hidden'); summary.setAttribute('aria-expanded', String(!detail.classList.contains('hidden'))); };
    summary.onclick = toggle; summary.onkeydown = event => { if (['Enter',' '].includes(event.key)) { event.preventDefault(); toggle(); } };
  });
  $$('.evidence-form').forEach(form => form.onsubmit = async event => {
    event.preventDefault(); const card = event.target.closest('[data-run-case]'); const data = new FormData(form);
    if (!data.get('file')?.size) return toast('Choose a screenshot first.', true);
    const button = $('button[type="submit"]', form); const status = $('.inline-status', form);
    button.disabled = true; button.textContent = 'Uploading…'; status.textContent = '';
    try {
      const uploaded = await api(`/projects/${state.projectId}/run-cases/${card.dataset.runCase}/evidence`, {method:'POST', body:data});
      const link = document.createElement('a');
      link.href = `/api/projects/${state.projectId}/evidence/${uploaded.id}`;
      link.target = '_blank'; link.rel = 'noopener'; link.textContent = uploaded.name;
      const list = $('.evidence-list', card);
      if (list.childElementCount) list.append(document.createElement('br'));
      list.append(link); form.reset(); status.textContent = 'Uploaded'; toast('Evidence uploaded. Your notes were preserved.');
    } catch (error) { status.textContent = 'Upload failed'; toast(error.message, true); }
    finally { button.disabled = false; button.textContent = 'Upload evidence'; }
  });
  $$('.assignment-form').forEach(form => form.onsubmit = async event => {
    event.preventDefault(); const card = form.closest('[data-run-case]');
    try {
      await api(`/projects/${state.projectId}/run-cases/${card.dataset.runCase}/assignment`, {method:'PATCH', body:JSON.stringify({assigned_to:form.assigned_to.value ? Number(form.assigned_to.value) : null})});
      const label = form.assigned_to.selectedOptions[0]?.textContent || 'Unassigned';
      $('.case-summary', card).children[2].textContent = label; toast('Assignment updated.');
    }
    catch (error) { toast(error.message, true); }
  });
  $$('.save-result').forEach(button => button.onclick = async () => {
    const card = button.closest('[data-run-case]'); const resultState = $('.result-state', card).value; const notes = $('.result-notes', card).value;
    if (resultState === 'failed' && !notes.trim()) return toast('Describe what went wrong before failing the case.', true);
    button.disabled = true; button.textContent = resultState === 'failed' ? 'Opening GitLab issue…' : 'Saving…';
    try {
      const result = await api(`/projects/${state.projectId}/run-cases/${card.dataset.runCase}/result`, {method:'PATCH', body:JSON.stringify({state:resultState, notes})});
      const badge = $('.case-summary .badge', card); badge.className = `badge ${result.state}`; badge.textContent = result.state.replaceAll('_', ' ');
      if (result.gitlab_issue_url) {
        const link = document.createElement('a'); link.href = result.gitlab_issue_url;
        link.target = '_blank'; link.rel = 'noopener'; link.textContent = 'Open GitLab issue ↗';
        $('.issue-slot', card).replaceChildren(link);
      }
      toast(result.gitlab_issue_url ? 'Failure saved and GitLab issue opened.' : 'Result saved.');
    }
    catch (error) { toast(error.message, true); }
    finally { button.disabled = false; button.textContent = 'Save result'; }
  });
}

async function renderTeam() {
  if (!projectRequired()) return;
  const members = await api(`/projects/${state.projectId}/members`);
  const users = canManage() ? await api(`/projects/${state.projectId}/available-users`) : [];
  const rows = members.map(member => `<tr><td>${escapeHtml(member.display_name)}</td><td class="mono">${escapeHtml(member.username)}</td><td><span class="badge">${escapeHtml(member.role)}</span></td></tr>`).join('');
  setContent(pageHead('Project team', 'Membership and project-scoped permissions.') + `<section class="grid"><div class="span-8 table-wrap"><table><thead><tr><th>Name</th><th>Username</th><th>Role</th></tr></thead><tbody>${rows}</tbody></table></div>
    ${canManage() ? `<div class="panel span-4"><h2>Add or update member</h2><form id="member-form" class="stack"><label>User<select name="user_id">${users.map(user => `<option value="${user.id}">${escapeHtml(user.display_name)}</option>`).join('')}</select></label><label>Role<select name="role"><option value="tester">Tester</option><option value="manager">Project manager</option><option value="viewer">Viewer</option></select></label><button class="primary">Save membership</button></form></div>` : ''}</section>`, 'team');
  if ($('#member-form')) $('#member-form').onsubmit = async event => { event.preventDefault(); try { await api(`/projects/${state.projectId}/members`, {method:'PUT', body:JSON.stringify({user_id:Number(event.target.user_id.value), role:event.target.role.value})}); toast('Membership saved.'); renderTeam(); } catch (error) { toast(error.message, true); } };
}

async function renderAdmin() {
  if (!state.user.is_admin) return renderDashboard();
  const users = await api('/users');
  setContent(pageHead('Administration', 'Create accounts and project workspaces.') + `<section class="grid">
    <div class="panel span-6"><h2>New user</h2><form id="user-form" class="stack"><label>Username<input name="username" required minlength="3"></label><label>Display name<input name="display_name" required></label><label>Temporary password<input name="password" type="password" required minlength="10"></label><label><span><input name="is_admin" type="checkbox" style="width:auto;min-height:auto"> System administrator</span></label><button class="primary">Create user</button></form></div>
    <div class="panel span-6"><h2>New project</h2><form id="project-form" class="stack"><label>Key<input name="key" required placeholder="DUTYARC"></label><label>Name<input name="name" required></label><label>Description<textarea name="description"></textarea></label><label>GitLab URL<input name="gitlab_url" type="url" placeholder="https://gitlab.internal"></label><label>GitLab project ID or path<input name="gitlab_project_id" placeholder="group/repository"></label><label>Access token<input name="gitlab_token" type="password"></label><button class="primary">Create project</button></form></div>
    <div class="panel span-12"><h2>Accounts</h2><div class="table-wrap"><table><thead><tr><th>Name</th><th>Username</th><th>Type</th></tr></thead><tbody>${users.map(u => `<tr><td>${escapeHtml(u.display_name)}</td><td class="mono">${escapeHtml(u.username)}</td><td>${u.is_admin ? 'Administrator' : 'Standard user'}</td></tr>`).join('')}</tbody></table></div></div></section>`, 'admin');
  $('#user-form').onsubmit = async event => { event.preventDefault(); const form = event.target; try { await api('/users', {method:'POST', body:JSON.stringify({username:form.username.value, display_name:form.display_name.value, password:form.password.value, is_admin:form.is_admin.checked})}); toast('User created.'); renderAdmin(); } catch (error) { toast(error.message, true); } };
  $('#project-form').onsubmit = async event => { event.preventDefault(); const form = event.target; const value = name => form[name].value || null; try { await api('/projects', {method:'POST', body:JSON.stringify({key:value('key'), name:value('name'), description:value('description') || '', gitlab_url:value('gitlab_url'), gitlab_project_id:value('gitlab_project_id'), gitlab_token:value('gitlab_token')})}); toast('Project created.'); await loadProjects(); location.hash = '#/dashboard'; } catch (error) { toast(error.message, true); } };
}

async function route() {
  if (!state.user) return;
  const parts = location.hash.replace(/^#\/?/, '').split('/').filter(Boolean);
  const name = parts[0] || 'dashboard';
  try {
    if (name === 'dashboard') await renderDashboard();
    else if (name === 'cases') await renderCases();
    else if (name === 'import') await renderImport();
    else if (name === 'runs' && parts[1]) await renderRun(Number(parts[1]));
    else if (name === 'runs') await renderRuns();
    else if (name === 'reports') await renderReports();
    else if (name === 'team') await renderTeam();
    else if (name === 'admin') await renderAdmin();
    else location.hash = '#/dashboard';
  } catch (error) { setContent(pageHead('Unable to load', error.message) + `<div class="error">${escapeHtml(error.message)}</div>`, name); }
}

$('#login-form').addEventListener('submit', async event => {
  event.preventDefault(); const form = event.target; const errorNode = $('#login-error'); errorNode.classList.add('hidden');
  try { const data = await api('/auth/login', {method:'POST', body:JSON.stringify({username:form.username.value, password:form.password.value})}); state.user = data.user; state.csrf = data.csrf_token; form.reset(); await showApp(); }
  catch (error) { errorNode.textContent = error.message; errorNode.classList.remove('hidden'); }
});
$('#logout-button').onclick = async () => { try { await api('/auth/logout', {method:'POST'}); } finally { showLogin(); } };
$('#project-select').onchange = event => { state.projectId = Number(event.target.value); localStorage.setItem('lt_project', state.projectId); applyProjectPermissions(); route(); };
$('#menu-toggle').onclick = () => $('#sidebar').classList.toggle('open');
window.addEventListener('hashchange', route);

(async function boot() {
  try { const data = await api('/auth/me'); state.user = data.user; state.csrf = data.csrf_token; await showApp(); }
  catch (_) { showLogin(); }
})();
