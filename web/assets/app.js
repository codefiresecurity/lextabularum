const state = { user: null, csrf: null, projects: [], projectId: null, users: [], notifications: [] };
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

function modalField(field) {
  if (field.type === 'checkboxes') {
    return `<fieldset class="modal-checks"><legend>${escapeHtml(field.label)}</legend>${field.help ? `<p class="field-help">${escapeHtml(field.help)}</p>` : ''}<div class="check-list">${field.options.map(option => `<label><input type="checkbox" name="${escapeHtml(field.name)}" value="${escapeHtml(option.value)}" ${option.checked ? 'checked' : ''}><span><strong>${escapeHtml(option.label)}</strong>${option.description ? `<small>${escapeHtml(option.description)}</small>` : ''}</span></label>`).join('') || '<p class="muted">No options are available.</p>'}</div></fieldset>`;
  }
  const attributes = `${field.required ? ' required' : ''}${field.minlength ? ` minlength="${field.minlength}"` : ''}${field.maxlength ? ` maxlength="${field.maxlength}"` : ''}${field.autocomplete ? ` autocomplete="${escapeHtml(field.autocomplete)}"` : ''}`;
  const control = field.type === 'textarea'
    ? `<textarea name="${escapeHtml(field.name)}" rows="${field.rows || 4}"${attributes}>${escapeHtml(field.value || '')}</textarea>`
    : `<input name="${escapeHtml(field.name)}" type="${escapeHtml(field.type || 'text')}" value="${escapeHtml(field.value || '')}"${attributes}>`;
  return `<label>${escapeHtml(field.label)}${control}${field.help ? `<small class="field-help">${escapeHtml(field.help)}</small>` : ''}</label>`;
}

function openModal({title, message = '', fields = [], confirmLabel = 'Save', danger = false, size = ''}) {
  const dialog = $('#app-dialog');
  const form = $('#dialog-form');
  $('#dialog-title').textContent = title;
  $('#dialog-body').innerHTML = `${message ? `<p class="dialog-message">${escapeHtml(message)}</p>` : ''}${fields.map(modalField).join('')}`;
  const confirmButton = $('#dialog-confirm');
  confirmButton.textContent = confirmLabel;
  confirmButton.className = danger ? 'danger' : 'primary';
  dialog.className = `app-dialog ${size ? `dialog-${size}` : ''}`.trim();
  return new Promise(resolve => {
    let settled = false;
    const finish = value => {
      if (settled) return;
      settled = true;
      dialog.close();
      resolve(value);
    };
    form.onsubmit = event => {
      event.preventDefault();
      if (!form.reportValidity()) return;
      const data = new FormData(form);
      const values = {};
      fields.forEach(field => { values[field.name] = field.type === 'checkboxes' ? data.getAll(field.name) : String(data.get(field.name) || ''); });
      finish(values);
    };
    $('#dialog-cancel').onclick = () => finish(null);
    $('#dialog-close').onclick = () => finish(null);
    dialog.oncancel = event => { event.preventDefault(); finish(null); };
    dialog.showModal();
    requestAnimationFrame(() => $('#dialog-body input:not([type="checkbox"]), #dialog-body textarea, #dialog-body select')?.focus());
  });
}

async function confirmModal(title, message, confirmLabel = 'Continue', danger = false) {
  return Boolean(await openModal({title, message, confirmLabel, danger}));
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
  if (state.user.must_change_password) { location.hash = '#/account'; route(); return; }
  await loadProjects();
  await loadNotifications();
  route();
}

async function loadNotifications() {
  state.notifications = await api('/notifications');
  $('#notification-count').textContent = state.notifications.filter(item => !item.read_at).length;
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
function applyProjectPermissions() {
  $('[data-route="import"]').classList.toggle('hidden', !canManage());
  $('[data-route="settings"]').classList.toggle('hidden', !canManage());
}

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

function evidenceItem(file) {
  return `<span class="evidence-item" data-evidence-id="${file.id}"><a href="/api/projects/${state.projectId}/evidence/${file.id}" target="_blank" rel="noopener">${escapeHtml(file.name)}</a><button type="button" class="remove-evidence">Remove</button></span>`;
}

function setContent(html, routeName) {
  $('#content').innerHTML = html;
  activeNav(routeName);
  $('#content').focus({preventScroll: true});
}

async function renderDashboard(filters = {}) {
  if (!projectRequired()) return;
  const params = new URLSearchParams(Object.entries(filters).filter(([,value]) => value));
  const [data, runs, members] = await Promise.all([api(`/projects/${state.projectId}/dashboard?${params}`), api(`/projects/${state.projectId}/runs`), api(`/projects/${state.projectId}/members`)]);
  const total = data.total_executions || 0;
  const width = value => total ? value / total * 100 : 0;
  const recentRows = data.recent_runs.map(run => `<tr><td><a class="panel-link" href="#/runs/${run.id}">${escapeHtml(run.name)}</a><br><small class="muted">${formatDate(run.created_at)}</small></td><td>${run.total}</td><td><div class="mini-meter"><div class="progress"><span style="width:${run.completion_rate}%"></span></div><small>${run.completed}/${run.total} complete</small></div></td><td>${run.pass_rate === null ? '—' : `${run.pass_rate}%`}</td><td><span class="badge ${run.failed ? 'failed' : ''}">${run.failed} failed</span></td></tr>`).join('');
  const workloadRows = data.workload.slice(0, 8).map(item => `<tr><td>${escapeHtml(item.display_name)}</td><td>${item.total}</td><td>${item.states.not_started || 0}</td><td>${item.states.in_progress || 0}</td><td>${item.states.failed || 0}</td></tr>`).join('');
  setContent(pageHead('Operations dashboard', 'Live execution posture for the selected project.', '<a href="#/reports"><button>Open reports</button></a>') + `<form id="dashboard-filters" class="report-controls report-controls-wide"><label>Run<select name="run_id"><option value="">All runs</option>${runs.map(run => `<option value="${run.id}" ${String(run.id) === String(filters.run_id || '') ? 'selected' : ''}>${escapeHtml(run.name)}</option>`).join('')}</select></label><label>Assignee<select name="assignee_id"><option value="">All testers</option>${members.map(member => `<option value="${member.id}" ${String(member.id) === String(filters.assignee_id || '') ? 'selected' : ''}>${escapeHtml(member.display_name)}</option>`).join('')}</select></label><label>Completed from<input name="date_from" type="date" value="${escapeHtml(filters.date_from || '')}"></label><label>Through<input name="date_to" type="date" value="${escapeHtml(filters.date_to || '')}"></label><button>Apply</button></form>
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
  $('#dashboard-filters').onsubmit = event => { event.preventDefault(); renderDashboard({run_id:event.target.run_id.value, assignee_id:event.target.assignee_id.value, date_from:event.target.date_from.value, date_to:event.target.date_to.value}); };
}

async function renderReports() {
  if (!projectRequired()) return;
  const [runs, members] = await Promise.all([api(`/projects/${state.projectId}/runs`), api(`/projects/${state.projectId}/members`)]);
  setContent(pageHead('Execution reports', 'Filter, review, print, or export test execution evidence.', '<button id="print-report">Print report</button><button id="export-report" class="primary">Export CSV</button>') + `
    <form id="report-controls" class="report-controls report-controls-wide">
      <label>Test run<select name="run_id"><option value="">All runs</option>${runs.map(run => `<option value="${run.id}">${escapeHtml(run.name)}</option>`).join('')}</select></label>
      <label>Result<select name="state"><option value="">All states</option><option value="not_started">Not started</option><option value="in_progress">In progress</option><option value="passed">Passed</option><option value="failed">Failed</option><option value="blocked">Blocked</option><option value="skipped">Skipped</option></select></label>
      <label>Assignee<select name="assignee_id"><option value="">All testers</option>${members.map(member => `<option value="${member.id}">${escapeHtml(member.display_name)}</option>`).join('')}</select></label>
      <label>Completed from<input name="date_from" type="date"></label><label>Completed through<input name="date_to" type="date"></label>
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
    if (form.assignee_id.value) params.set('assignee_id', form.assignee_id.value);
    if (form.date_from.value) params.set('date_from', form.date_from.value);
    if (form.date_to.value) params.set('date_to', form.date_to.value);
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

async function renderCases(filters = {}) {
  if (!projectRequired()) return;
  const params = new URLSearchParams(Object.entries(filters).filter(([,value]) => value));
  const cases = await api(`/projects/${state.projectId}/cases?${params}`);
  let rows = cases.map(item => `<tr><td class="mono"><strong>${escapeHtml(item.external_id)}</strong></td><td>${escapeHtml(item.title)}</td><td>${escapeHtml(item.section)}</td><td><span class="badge">${escapeHtml(item.priority || '—')}</span></td><td>${item.tags.map(tag => `<span class="badge">${escapeHtml(tag)}</span>`).join(' ') || '—'}</td><td>r${item.version}</td><td><button class="case-history" data-case-id="${item.id}">History</button>${canManage() ? `<button class="edit-case" data-case-id="${item.id}">Edit</button><button class="case-tags" data-case-id="${item.id}" data-tags="${escapeHtml(item.tags.join(','))}">Tags</button><button class="case-requirements" data-case-id="${item.id}">Requirements</button><button class="deactivate-case danger" data-case-id="${item.id}" data-case-name="${escapeHtml(item.external_id)}">Deactivate</button>` : ''}</td></tr>`).join('');
  setContent(pageHead('Test library', `${cases.length} reusable cases in the selected project.`, canManage() ? '<a href="#/import"><button>Import Markdown</button></a>' : '') +
    `<form id="case-filters" class="report-controls"><label>Search<input name="q" value="${escapeHtml(filters.q || '')}" placeholder="ID, title, module"></label><label>Priority<select name="priority"><option value="">All</option>${['P0','P1','P2','P3'].map(value => `<option ${filters.priority === value ? 'selected' : ''}>${value}</option>`).join('')}</select></label><label>Tag<input name="tag" value="${escapeHtml(filters.tag || '')}"></label><button>Filter</button></form><div id="case-history-panel"></div>` +
    (cases.length ? `<div class="table-wrap"><table><thead><tr><th>ID</th><th>Title</th><th>Module</th><th>Priority</th><th>Tags</th><th>Revision</th><th>Actions</th></tr></thead><tbody>${rows}</tbody></table></div>` : '<div class="empty">No matching cases.</div>'), 'cases');
  $('#case-filters').onsubmit = event => { event.preventDefault(); renderCases({q:event.target.q.value, priority:event.target.priority.value, tag:event.target.tag.value}); };
  $$('.case-history').forEach(button => button.onclick = async () => {
    try {
      const versions = await api(`/projects/${state.projectId}/cases/${button.dataset.caseId}/revisions`);
      $('#case-history-panel').innerHTML = `<div class="panel"><h2>Revision history</h2>${versions.map((version,index) => `<details ${index === 0 ? 'open' : ''}><summary><strong>r${version.version} — ${escapeHtml(version.title)}</strong> · ${formatDate(version.imported_at)} · ${escapeHtml(version.source_file || '')}</summary><ol>${version.steps.map(step => `<li>${escapeHtml(step)}</li>`).join('')}</ol><p class="expected"><strong>Expected:</strong> ${escapeHtml(version.expected)}</p></details>`).join('')}</div>`;
      $('#case-history-panel').scrollIntoView({behavior:'smooth', block:'start'});
    } catch (error) { toast(error.message, true); }
  });
  $$('.case-tags').forEach(button => button.onclick = async () => {
    const values = await openModal({title:'Edit case tags', message:'Use commas to separate tags.', fields:[{name:'tags', label:'Tags', value:button.dataset.tags, help:'Example: smoke, authentication, release-blocker'}]});
    if (!values) return;
    try { await api(`/projects/${state.projectId}/cases/${button.dataset.caseId}/tags`, {method:'PATCH', body:JSON.stringify({tags:values.tags.split(',').map(tag => tag.trim()).filter(Boolean)})}); toast('Tags updated.'); renderCases(filters); }
    catch (error) { toast(error.message, true); }
  });
  $$('.edit-case').forEach(button => button.onclick = async () => {
    try {
      const item = await api(`/projects/${state.projectId}/cases/${button.dataset.caseId}`);
      const values = await openModal({title:`Edit ${item.external_id}`, message:'Saving creates a new immutable revision. Existing runs keep their pinned revision.', size:'wide', fields:[
        {name:'title', label:'Title', value:item.title, required:true, maxlength:300},
        {name:'section', label:'Module / section', value:item.section, required:true, maxlength:300},
        {name:'priority', label:'Priority', value:item.priority || '', maxlength:20},
        {name:'steps', label:'Steps — one per line', value:item.steps.join('\n'), type:'textarea', rows:7, required:true},
        {name:'expected', label:'Expected result', value:item.expected, type:'textarea', rows:4, required:true},
      ], confirmLabel:'Create revision'});
      if (!values) return;
      await api(`/projects/${state.projectId}/cases/${button.dataset.caseId}`, {method:'PATCH', body:JSON.stringify({title:values.title, section:values.section, priority:values.priority || null, lifecycle:item.lifecycle || null, steps:values.steps.split('\n').map(step => step.trim()).filter(Boolean), expected:values.expected})});
      toast('A new test-case revision was created.'); renderCases(filters);
    } catch (error) { toast(error.message, true); }
  });
  $$('.deactivate-case').forEach(button => button.onclick = async () => { if (!await confirmModal('Deactivate test case', `Deactivate ${button.dataset.caseName}? Existing runs will keep their pinned copy.`, 'Deactivate', true)) return; try { await api(`/projects/${state.projectId}/cases/${button.dataset.caseId}/deactivate`, {method:'POST'}); toast('Test case deactivated.'); renderCases(filters); } catch (error) { toast(error.message, true); } });
  $$('.case-requirements').forEach(button => button.onclick = async () => { try {
    const [all,current] = await Promise.all([api(`/projects/${state.projectId}/requirements`),api(`/projects/${state.projectId}/cases/${button.dataset.caseId}/requirements`)]);
    const selectedIds = new Set(current.map(item => item.id));
    const values = await openModal({title:'Map requirements', message:'Select every requirement covered by this test case.', size:'wide', fields:[{name:'requirements', label:'Available requirements', type:'checkboxes', options:all.map(item => ({value:item.id, label:`${item.key} — ${item.title}`, description:item.description, checked:selectedIds.has(item.id)}))}], confirmLabel:'Save mapping'});
    if (!values) return;
    await api(`/projects/${state.projectId}/cases/${button.dataset.caseId}/requirements`, {method:'PUT', body:JSON.stringify({requirement_ids:values.requirements.map(Number)})}); toast('Requirements mapped.');
  } catch (error) { toast(error.message, true); } });
}

async function renderRequirements() {
  if (!projectRequired()) return;
  const items = await api(`/projects/${state.projectId}/requirements`);
  setContent(pageHead('Requirements', 'Trace product and compliance requirements to test cases.') + `<section class="grid"><div class="span-8 table-wrap"><table><thead><tr><th>Key</th><th>Title</th><th>Description</th></tr></thead><tbody>${items.map(item => `<tr><td class="mono"><strong>${escapeHtml(item.key)}</strong></td><td>${escapeHtml(item.title)}</td><td>${escapeHtml(item.description)}</td></tr>`).join('')}</tbody></table></div>${canManage() ? `<div class="panel span-4"><h2>New requirement</h2><form id="requirement-form" class="stack"><label>Key<input name="key" required></label><label>Title<input name="title" required></label><label>Description<textarea name="description"></textarea></label><button class="primary">Create requirement</button></form></div>` : ''}</section>`, 'requirements');
  if ($('#requirement-form')) $('#requirement-form').onsubmit = async event => { event.preventDefault(); try { await api(`/projects/${state.projectId}/requirements`, {method:'POST', body:JSON.stringify({key:event.target.key.value,title:event.target.title.value,description:event.target.description.value})}); toast('Requirement created.'); renderRequirements(); } catch (error) { toast(error.message, true); } };
}

async function renderImport() {
  if (!projectRequired()) return;
  if (!canManage()) { location.hash = '#/cases'; return; }
  setContent(pageHead('Import test plan', 'Existing IDs are updated as new revisions; unchanged cases are left alone.') + `
    <section class="grid"><div class="panel span-8"><h2>Markdown source</h2>
      <form id="import-form" class="stack"><label>Test plan file (.md)<input name="file" type="file" accept=".md,.markdown,text/markdown" required></label>
      <p class="muted">Each case requires an ID/title heading, numbered steps, and an <span class="mono">Expected:</span> line.</p>
      <div class="actions"><button type="submit">Preview changes</button><button id="confirm-import" class="primary hidden" type="button">Apply import</button></div></form><div id="import-preview"></div></div>
      <aside class="panel span-4"><h2>Recognized pattern</h2><pre class="mono">### PR-001 — Login (\`P0\`)\n\n1. Open the form.\n2. Sign in.\n\nExpected: Dashboard opens.</pre></aside></section>`, 'import');
  $('#import-form').addEventListener('submit', async event => {
    event.preventDefault();
    const button = $('button[type="submit"]', event.target); button.disabled = true; button.textContent = 'Checking…';
    try {
      const result = await api(`/projects/${state.projectId}/imports/preview`, {method: 'POST', body: new FormData(event.target)});
      $('#import-preview').innerHTML = `<h3>Proposed changes</h3><p><span class="badge">${result.create} new</span> <span class="badge in_progress">${result.update} changed</span> <span class="badge passed">${result.unchanged} unchanged</span></p><div class="table-wrap"><table><thead><tr><th>ID</th><th>Title</th><th>Module</th><th>Action</th></tr></thead><tbody>${result.rows.map(row => `<tr><td class="mono">${escapeHtml(row.external_id)}</td><td>${escapeHtml(row.title)}</td><td>${escapeHtml(row.section)}</td><td><span class="badge ${row.action === 'update' ? 'in_progress' : row.action === 'unchanged' ? 'passed' : ''}">${row.action}</span></td></tr>`).join('')}</tbody></table></div>${result.omitted.length ? `<p class="error"><strong>${result.omitted.length} existing cases are absent from this file.</strong> They will remain active and will not be deleted.</p>` : ''}`;
      $('#confirm-import').classList.remove('hidden');
    } catch (error) { toast(error.message, true); $('#confirm-import').classList.add('hidden'); }
    finally { button.disabled = false; button.textContent = 'Preview changes'; }
  });
  $('#confirm-import').onclick = async event => {
    event.target.disabled = true; event.target.textContent = 'Importing…';
    try {
      const result = await api(`/projects/${state.projectId}/imports`, {method:'POST', body:new FormData($('#import-form'))});
      toast(`${result.created} created, ${result.updated} updated, ${result.unchanged} unchanged.`); location.hash = '#/cases';
    } catch (error) { toast(error.message, true); event.target.disabled = false; event.target.textContent = 'Apply import'; }
  };
}

async function renderRuns() {
  if (!projectRequired()) return;
  const [runs, cases, members, templates] = await Promise.all([
    api(`/projects/${state.projectId}/runs`), api(`/projects/${state.projectId}/cases`), api(`/projects/${state.projectId}/members`), api(`/projects/${state.projectId}/run-templates`)
  ]);
  const rows = runs.map(run => {
    const complete = (run.counts.passed || 0) + (run.counts.failed || 0) + (run.counts.blocked || 0) + (run.counts.skipped || 0);
    const pct = run.total ? Math.round(complete / run.total * 100) : 0;
    return `<tr><td><a href="#/runs/${run.id}"><strong>${escapeHtml(run.name)}</strong></a><br><small class="muted">${escapeHtml(run.description)}</small></td><td>${escapeHtml(run.build_version || '—')}<br><small>${escapeHtml(run.environment || '')}</small></td><td>${run.total}</td><td><div class="progress"><span style="width:${pct}%"></span></div><small>${pct}% complete</small></td><td><span class="badge">${escapeHtml(run.status)}</span></td></tr>`;
  }).join('');
  setContent(pageHead('Test runs', 'Release, regression, and acceptance execution sets.', canManage() ? '<button id="new-run-button" class="primary">New test run</button>' : '') + `
    <div id="new-run-panel" class="panel hidden"><h2>Create run</h2><form id="run-form" class="form-grid">
      <label>Name<input name="name" required maxlength="240" placeholder="Release 2.4 regression"></label>
      <label>Default assignee<select name="assigned_to"><option value="">Unassigned</option>${members.filter(m => m.role !== 'viewer').map(m => `<option value="${m.id}">${escapeHtml(m.display_name)}</option>`).join('')}</select></label>
      <label>Build / version<input name="build_version" maxlength="160" placeholder="2.4.0-rc1"></label>
      <label>Environment<input name="environment" maxlength="160" placeholder="Staging / Firefox / Windows"></label>
      <label class="wide">Commit SHA<input name="commit_sha" maxlength="80" placeholder="Optional source revision"></label>
      <label class="wide">Start from template<select name="template_id"><option value="">All active cases</option>${templates.map(template => `<option value="${template.id}">${escapeHtml(template.name)}</option>`).join('')}</select></label>
      <label class="wide">Description<textarea name="description"></textarea></label>
      <label class="wide">Cases<select name="case_ids" multiple size="8">${cases.map(c => `<option value="${c.id}" selected>${escapeHtml(c.external_id)} — ${escapeHtml(c.title)}</option>`).join('')}</select></label>
      <div class="wide actions"><button class="primary" type="submit">Create run</button><button type="button" id="save-template">Save selection as template</button><button type="button" id="cancel-run">Cancel</button></div>
    </form></div>
    <div class="table-wrap">${runs.length ? `<table><thead><tr><th>Run</th><th>Build / environment</th><th>Cases</th><th>Progress</th><th>Status</th></tr></thead><tbody>${rows}</tbody></table>` : '<div class="empty">No runs created yet.</div>'}</div>`, 'runs');
  if ($('#new-run-button')) $('#new-run-button').onclick = () => $('#new-run-panel').classList.remove('hidden');
  $('#cancel-run').onclick = () => $('#new-run-panel').classList.add('hidden');
  $('#run-form').template_id.onchange = event => { const template = templates.find(item => item.id === Number(event.target.value)); [...$('#run-form').case_ids.options].forEach(option => option.selected = !template || template.case_ids.includes(Number(option.value))); };
  $('#save-template').onclick = async () => { const form = $('#run-form'); const values = await openModal({title:'Save run template', message:'The currently selected test cases will be saved for reuse.', fields:[{name:'name', label:'Template name', required:true, maxlength:240}]}); if (!values) return; try { await api(`/projects/${state.projectId}/run-templates`, {method:'POST', body:JSON.stringify({name:values.name, description:form.description.value, case_ids:[...form.case_ids.selectedOptions].map(option => Number(option.value))})}); toast('Run template saved.'); renderRuns(); } catch (error) { toast(error.message, true); } };
  $('#run-form').onsubmit = async event => {
    event.preventDefault(); const form = event.target;
    const payload = {name: form.name.value, description: form.description.value,
      assigned_to: form.assigned_to.value ? Number(form.assigned_to.value) : null,
      build_version: form.build_version.value || null, environment: form.environment.value || null,
      commit_sha: form.commit_sha.value || null,
      case_ids: [...form.case_ids.selectedOptions].map(option => Number(option.value))};
    try { const run = await api(`/projects/${state.projectId}/runs`, {method:'POST', body:JSON.stringify(payload)}); location.hash = `#/runs/${run.id}`; }
    catch (error) { toast(error.message, true); }
  };
}

async function renderRun(runId) {
  if (!projectRequired()) return;
  const [run, members] = await Promise.all([api(`/projects/${state.projectId}/runs/${runId}`), api(`/projects/${state.projectId}/members`)]);
  const terminalStates = ['passed','failed','blocked','skipped'];
  const cases = run.cases.map(item => `<article class="case-card" data-run-case="${item.id}" data-lock-version="${item.lock_version}">
    <div class="case-summary ${canManage() ? 'with-select' : ''}" role="button" tabindex="0" aria-expanded="false">${canManage() ? `<input class="bulk-case" type="checkbox" aria-label="Select ${escapeHtml(item.external_id)}">` : ''}<strong class="mono">${escapeHtml(item.external_id)}</strong><span>${escapeHtml(item.title)}</span><span class="case-assignee">${escapeHtml(item.assignee || 'Unassigned')}</span><span class="badge ${item.state}">${escapeHtml(item.state.replace('_',' '))}</span></div>
    <div class="case-detail hidden"><ol>${item.steps.map(step => `<li>${escapeHtml(step)}</li>`).join('')}</ol><p class="expected"><strong>Expected:</strong> ${escapeHtml(item.expected)}</p>
      <p class="issue-slot">${item.gitlab_issue_url ? `<a href="${escapeHtml(item.gitlab_issue_url)}" target="_blank" rel="noopener">Open GitLab issue ↗</a>` : ''}</p>
      ${item.attempts.length ? `<div class="attempt-history"><h3>Execution history</h3><table><thead><tr><th>Attempt</th><th>Result</th><th>Tester</th><th>Completed</th><th>GitLab</th></tr></thead><tbody>${item.attempts.map(attempt => `<tr><td>#${attempt.number}</td><td><span class="badge ${attempt.state}">${escapeHtml(attempt.state)}</span></td><td>${escapeHtml(attempt.executor)}</td><td>${formatDate(attempt.completed_at)}</td><td>${attempt.gitlab_issue_url ? `<a href="${escapeHtml(attempt.gitlab_issue_url)}" target="_blank" rel="noopener">Issue ↗</a>` : escapeHtml(attempt.gitlab_status)}</td></tr>`).join('')}</tbody></table></div>` : ''}
      ${canManage() ? `<form class="assignment-form form-grid"><label>Assignee<select name="assigned_to"><option value="">Unassigned</option>${members.filter(member => member.role !== 'viewer').map(member => `<option value="${member.id}" ${member.id === item.assigned_to ? 'selected' : ''}>${escapeHtml(member.display_name)}</option>`).join('')}</select></label><div><button type="submit">Update assignment</button></div></form>` : ''}
      <div class="run-tools">
        <label>Result<select class="result-state">${[['in_progress','In progress'],['passed','Passed'],['failed','Failed'],['blocked','Blocked'],['skipped','Skipped']].map(([value,label]) => `<option value="${value}" ${value === item.state ? 'selected' : ''}>${label}</option>`).join('')}</select></label>
        <label>Execution notes<textarea class="result-notes" placeholder="Required when failed">${escapeHtml(item.notes)}</textarea></label>
        <div class="actions"><button class="save-result primary ${terminalStates.includes(item.state) ? 'hidden' : ''}">Save result</button><button class="start-retest ${terminalStates.includes(item.state) ? '' : 'hidden'}">Start retest</button></div>
      </div>
      <form class="evidence-form stack"><label class="evidence-drop">Failure screenshot — choose, drop, or paste an image<input name="file" type="file" accept="image/png,image/jpeg,image/webp,image/gif"></label><div class="actions"><button type="submit">Upload evidence</button><span class="inline-status" aria-live="polite"></span></div></form>
      <div class="evidence-list">${item.evidence.map(evidenceItem).join('')}</div>
      <div class="comment-thread"><h3>Comments</h3><div class="comment-list">${item.comments.map(comment => `<article><strong>${escapeHtml(comment.author)}</strong> <small>${formatDate(comment.created_at)}</small><p>${escapeHtml(comment.body)}</p></article>`).join('') || '<p class="muted">No comments yet.</p>'}</div><form class="comment-form actions"><input name="body" maxlength="10000" placeholder="Add a comment" required><button>Post comment</button></form></div>
    </div></article>`).join('');
  const lifecycle = canManage() ? `<button class="run-status" data-status="${run.status === 'open' ? 'closed' : 'open'}">${run.status === 'open' ? 'Close run' : 'Reopen run'}</button>${run.status !== 'archived' ? '<button class="run-status" data-status="archived">Archive</button>' : ''}` : '';
  const runMeta = [run.build_version && `Build ${run.build_version}`, run.environment, run.commit_sha && `Commit ${run.commit_sha}`].filter(Boolean).join(' · ');
  const bulkBar = canManage() && run.status === 'open' ? `<form id="bulk-assignment" class="report-controls"><label>Bulk assignee<select name="assigned_to"><option value="">Unassigned</option>${members.filter(member => member.role !== 'viewer').map(member => `<option value="${member.id}">${escapeHtml(member.display_name)}</option>`).join('')}</select></label><button>Assign selected</button></form>` : '';
  setContent(pageHead(run.name, [run.description, runMeta].filter(Boolean).join(' — '), `<span class="badge">${escapeHtml(run.status)}</span>${lifecycle}<a href="#/runs"><button>Back to runs</button></a>`) + bulkBar + (cases || '<div class="empty">This run is empty.</div>'), 'runs');
  $$('.run-status').forEach(button => button.onclick = async () => {
    if (!await confirmModal('Change run status', `Change this run to ${button.dataset.status}?`, 'Update status')) return;
    try { await api(`/projects/${state.projectId}/runs/${runId}/status`, {method:'PATCH', body:JSON.stringify({status:button.dataset.status})}); toast('Run status updated.'); renderRun(runId); }
    catch (error) { toast(error.message, true); }
  });
  if (run.status !== 'open') {
    $$('.case-card input, .case-card select, .case-card textarea, .case-card button').forEach(control => control.disabled = true);
    $$('.comment-form input, .comment-form button').forEach(control => control.disabled = false);
  }
  $$('.case-summary').forEach(summary => {
    const toggle = event => { if (event?.target.matches('input')) return; const detail = summary.nextElementSibling; detail.classList.toggle('hidden'); summary.setAttribute('aria-expanded', String(!detail.classList.contains('hidden'))); };
    summary.onclick = toggle; summary.onkeydown = event => { if (['Enter',' '].includes(event.key)) { event.preventDefault(); toggle(event); } };
  });
  if ($('#bulk-assignment')) $('#bulk-assignment').onsubmit = async event => {
    event.preventDefault(); const selected = $$('.bulk-case:checked').map(input => Number(input.closest('[data-run-case]').dataset.runCase));
    if (!selected.length) return toast('Select at least one test case.', true);
    try { const result = await api(`/projects/${state.projectId}/run-cases/bulk-assignment`, {method:'PATCH', body:JSON.stringify({run_case_ids:selected, assigned_to:event.target.assigned_to.value ? Number(event.target.assigned_to.value) : null})}); toast(`${result.updated} assignments updated.`); renderRun(runId); }
    catch (error) { toast(error.message, true); }
  };
  const sendEvidence = async (card, file, form) => {
    if (!file?.size) return toast('Choose a screenshot first.', true);
    const data = new FormData(); data.append('file', file, file.name || `pasted-${Date.now()}.png`);
    const button = $('button[type="submit"]', form); const status = $('.inline-status', form);
    button.disabled = true; button.textContent = 'Uploading…'; status.textContent = '';
    try {
      const uploaded = await api(`/projects/${state.projectId}/run-cases/${card.dataset.runCase}/evidence`, {method:'POST', body:data});
      const list = $('.evidence-list', card);
      list.insertAdjacentHTML('beforeend', evidenceItem(uploaded));
      form.reset(); status.textContent = 'Uploaded'; toast('Evidence uploaded. Your notes were preserved.');
    } catch (error) { status.textContent = 'Upload failed'; toast(error.message, true); }
    finally { button.disabled = false; button.textContent = 'Upload evidence'; }
  };
  $$('.evidence-form').forEach(form => {
    form.onsubmit = event => { event.preventDefault(); sendEvidence(form.closest('[data-run-case]'), form.file.files[0], form); };
    form.ondragover = event => { event.preventDefault(); form.classList.add('dragging'); };
    form.ondragleave = () => form.classList.remove('dragging');
    form.ondrop = event => { event.preventDefault(); form.classList.remove('dragging'); const file = [...event.dataTransfer.files].find(item => item.type.startsWith('image/')); sendEvidence(form.closest('[data-run-case]'), file, form); };
  });
  $$('.case-detail').forEach(detail => detail.addEventListener('paste', event => { const file = [...(event.clipboardData?.files || [])].find(item => item.type.startsWith('image/')); if (file) { event.preventDefault(); sendEvidence(detail.closest('[data-run-case]'), file, $('.evidence-form', detail)); } }));
  $$('.evidence-list').forEach(list => list.onclick = async event => {
    const button = event.target.closest('.remove-evidence');
    if (!button) return;
    const item = button.closest('.evidence-item'); const card = button.closest('[data-run-case]');
    const name = $('a', item).textContent;
    if (!await confirmModal('Remove evidence', `Remove ${name} from this test execution?`, 'Remove evidence', true)) return;
    button.disabled = true; button.textContent = 'Removing…';
    try {
      const result = await api(`/projects/${state.projectId}/run-cases/${card.dataset.runCase}/evidence/${item.dataset.evidenceId}`, {method:'DELETE'});
      item.remove();
      toast(result.file_deleted ? 'Evidence removed.' : 'Evidence record removed; the local file requires manual cleanup.', !result.file_deleted);
    } catch (error) { toast(error.message, true); button.disabled = false; button.textContent = 'Remove'; }
  });
  $$('.assignment-form').forEach(form => form.onsubmit = async event => {
    event.preventDefault(); const card = form.closest('[data-run-case]');
    try {
      const result = await api(`/projects/${state.projectId}/run-cases/${card.dataset.runCase}/assignment`, {method:'PATCH', body:JSON.stringify({assigned_to:form.assigned_to.value ? Number(form.assigned_to.value) : null})});
      card.dataset.lockVersion = result.lock_version;
      const label = form.assigned_to.selectedOptions[0]?.textContent || 'Unassigned';
      $('.case-assignee', card).textContent = label; toast('Assignment updated.');
    }
    catch (error) { toast(error.message, true); }
  });
  $$('.save-result').forEach(button => button.onclick = async () => {
    const card = button.closest('[data-run-case]'); const resultState = $('.result-state', card).value; const notes = $('.result-notes', card).value;
    if (resultState === 'failed' && !notes.trim()) return toast('Describe what went wrong before failing the case.', true);
    button.disabled = true; button.textContent = resultState === 'failed' ? 'Opening GitLab issue…' : 'Saving…';
    try {
      const result = await api(`/projects/${state.projectId}/run-cases/${card.dataset.runCase}/result`, {method:'PATCH', body:JSON.stringify({state:resultState, notes, lock_version:Number(card.dataset.lockVersion)})});
      const badge = $('.case-summary .badge', card); badge.className = `badge ${result.state}`; badge.textContent = result.state.replaceAll('_', ' ');
      card.dataset.lockVersion = result.lock_version;
      if (result.gitlab_issue_url) {
        const link = document.createElement('a'); link.href = result.gitlab_issue_url;
        link.target = '_blank'; link.rel = 'noopener'; link.textContent = 'Open GitLab issue ↗';
        $('.issue-slot', card).replaceChildren(link);
      }
      if (terminalStates.includes(result.state)) { button.classList.add('hidden'); $('.start-retest', card).classList.remove('hidden'); $$('.remove-evidence', card).forEach(control => { control.disabled = true; control.title = 'Submitted attempt evidence is immutable'; }); }
      toast(result.gitlab_issue_url ? 'Failure saved and GitLab issue opened.' : result.gitlab_status === 'pending' ? 'Failure saved. GitLab issue creation is pending retry.' : 'Result saved.');
    }
    catch (error) { toast(error.message, true); }
    finally { button.disabled = false; button.textContent = 'Save result'; }
  });
  $$('.start-retest').forEach(button => button.onclick = async () => {
    const card = button.closest('[data-run-case]');
    if (!await confirmModal('Start retest', 'Start a new attempt? The previous result and evidence will remain in execution history.', 'Start retest')) return;
    button.disabled = true; button.textContent = 'Starting…';
    try {
      const result = await api(`/projects/${state.projectId}/run-cases/${card.dataset.runCase}/retest`, {method:'POST', body:JSON.stringify({lock_version:Number(card.dataset.lockVersion)})});
      card.dataset.lockVersion = result.lock_version;
      const badge = $('.case-summary .badge', card); badge.className = 'badge not_started'; badge.textContent = 'not started';
      $('.result-notes', card).value = ''; $('.result-state', card).value = 'in_progress';
      $('.issue-slot', card).replaceChildren(); $('.evidence-list', card).replaceChildren();
      button.classList.add('hidden'); $('.save-result', card).classList.remove('hidden');
      toast('Retest ready. The prior attempt remains in execution history.');
    } catch (error) { toast(error.message, true); }
    finally { button.disabled = false; button.textContent = 'Start retest'; }
  });
  $$('.comment-form').forEach(form => form.onsubmit = async event => { event.preventDefault(); const card = form.closest('[data-run-case]'); try { const comment = await api(`/projects/${state.projectId}/run-cases/${card.dataset.runCase}/comments`, {method:'POST', body:JSON.stringify({body:form.body.value})}); const list = $('.comment-list', card); if (list.querySelector('.muted')) list.replaceChildren(); list.insertAdjacentHTML('beforeend', `<article><strong>${escapeHtml(comment.author)}</strong> <small>${formatDate(comment.created_at)}</small><p>${escapeHtml(comment.body)}</p></article>`); form.reset(); toast('Comment added.'); } catch (error) { toast(error.message, true); } });
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

async function renderSettings() {
  if (!projectRequired()) return;
  if (!canManage()) { location.hash = '#/dashboard'; return; }
  const project = await api(`/projects/${state.projectId}/settings`);
  setContent(pageHead('Project settings', 'Repository integration and project identity.') + `<section class="grid"><div class="panel span-8"><h2>General and GitLab</h2><form id="settings-form" class="stack">
    <label>Project name<input name="name" value="${escapeHtml(project.name)}" required></label><label>Description<textarea name="description">${escapeHtml(project.description)}</textarea></label>
    <label>GitLab URL<input name="gitlab_url" type="url" value="${escapeHtml(project.gitlab_url || '')}"></label><label>GitLab project ID or path<input name="gitlab_project_id" value="${escapeHtml(project.gitlab_project_id || '')}"></label>
    <label>Replace access token<input name="gitlab_token" type="password" placeholder="${project.gitlab_token_configured ? 'Configured — leave blank to retain' : 'Required for failures'}"></label>
    <label>Replace webhook secret<input name="gitlab_webhook_secret" type="password" placeholder="${project.gitlab_webhook_configured ? 'Configured — leave blank to retain' : 'Choose a secret'}"></label>
    <button class="primary">Save settings</button></form></div><aside class="panel span-4"><h2>GitLab webhook</h2><p>Configure an Issue Hook in GitLab using this URL:</p><p class="mono">${escapeHtml(project.webhook_url)}</p><p>Send the same secret entered here as the GitLab secret token.</p></aside></section>`, 'settings');
  $('#settings-form').onsubmit = async event => {
    event.preventDefault(); const form = event.target; const payload = {name:form.name.value, description:form.description.value, gitlab_url:form.gitlab_url.value || null, gitlab_project_id:form.gitlab_project_id.value || null};
    if (form.gitlab_token.value) payload.gitlab_token = form.gitlab_token.value;
    if (form.gitlab_webhook_secret.value) payload.gitlab_webhook_secret = form.gitlab_webhook_secret.value;
    try { await api(`/projects/${state.projectId}`, {method:'PATCH', body:JSON.stringify(payload)}); toast('Project settings saved.'); await loadProjects(); renderSettings(); }
    catch (error) { toast(error.message, true); }
  };
}

async function renderAccount() {
  if (!state.user.must_change_password) await loadNotifications();
  setContent(pageHead('My account', state.user.must_change_password ? 'A password change is required before continuing.' : 'Password and notification controls.') + `<section class="grid"><div class="panel span-5"><h2>Change password</h2><form id="password-form" class="stack"><label>Current password<input name="current_password" type="password" required></label><label>New password<input name="new_password" type="password" minlength="12" required></label><button class="primary">Change password</button></form></div><div class="panel span-7"><h2>Notifications</h2><div class="notification-list">${state.notifications.length ? state.notifications.map(item => `<article class="notification ${item.read_at ? '' : 'unread'}" data-id="${item.id}"><strong>${escapeHtml(item.title)}</strong><p>${escapeHtml(item.body)}</p><small>${formatDate(item.created_at)}</small>${item.link ? `<a href="${escapeHtml(item.link)}">Open</a>` : ''}</article>`).join('') : '<div class="empty">No notifications.</div>'}</div></div></section>`, 'account');
  $('#password-form').onsubmit = async event => { event.preventDefault(); try { await api('/auth/change-password', {method:'POST', body:JSON.stringify({current_password:event.target.current_password.value, new_password:event.target.new_password.value})}); state.user.must_change_password = false; event.target.reset(); await loadProjects(); await loadNotifications(); toast('Password changed and other sessions revoked.'); location.hash = '#/dashboard'; } catch (error) { toast(error.message, true); } };
  $$('.notification').forEach(item => item.onclick = async event => { if (event.target.closest('a')) return; if (!item.classList.contains('unread')) return; await api(`/notifications/${item.dataset.id}/read`, {method:'POST'}); item.classList.remove('unread'); loadNotifications(); });
}

async function renderAdmin() {
  if (!state.user.is_admin) return renderDashboard();
  const [users, adminProjects] = await Promise.all([api('/users'), api('/projects?include_inactive=true')]);
  setContent(pageHead('Administration', 'Create accounts and project workspaces.') + `<section class="grid">
    <div class="panel span-6"><h2>New user</h2><form id="user-form" class="stack"><label>Username<input name="username" required minlength="3"></label><label>Display name<input name="display_name" required></label><label>Temporary password<input name="password" type="password" required minlength="10"></label><label><span><input name="is_admin" type="checkbox" style="width:auto;min-height:auto"> System administrator</span></label><button class="primary">Create user</button></form></div>
    <div class="panel span-6"><h2>New project</h2><form id="project-form" class="stack"><label>Key<input name="key" required placeholder="DUTYARC"></label><label>Name<input name="name" required></label><label>Description<textarea name="description"></textarea></label><label>GitLab URL<input name="gitlab_url" type="url" placeholder="https://gitlab.internal"></label><label>GitLab project ID or path<input name="gitlab_project_id" placeholder="group/repository"></label><label>Access token<input name="gitlab_token" type="password"></label><button class="primary">Create project</button></form></div>
    <div class="panel span-12"><h2>Projects</h2><div class="table-wrap"><table><thead><tr><th>Key</th><th>Project</th><th>Description</th><th>Status</th><th>Lifecycle actions</th></tr></thead><tbody>${adminProjects.map(project => `<tr><td class="mono"><strong>${escapeHtml(project.key)}</strong></td><td>${escapeHtml(project.name)}</td><td>${escapeHtml(project.description || '—')}</td><td><span class="badge">${project.active ? 'active' : 'archived'}</span></td><td><button class="archive-project" data-project-id="${project.id}" data-archived="${project.active}">${project.active ? 'Archive' : 'Restore'}</button> <button class="danger delete-project" data-project-id="${project.id}" data-project-key="${escapeHtml(project.key)}" data-project-name="${escapeHtml(project.name)}">Delete project…</button></td></tr>`).join('')}</tbody></table></div><p class="widget-note">Archive first whenever possible. Permanent deletion removes the test library, revisions, runs, results, memberships, evidence, and GitLab configuration. Existing GitLab issues are retained.</p></div>
    <div class="panel span-12"><h2>Accounts</h2><div class="table-wrap"><table><thead><tr><th>Name</th><th>Username</th><th>Type</th><th>Security</th></tr></thead><tbody>${users.map(u => `<tr><td>${escapeHtml(u.display_name)}</td><td class="mono">${escapeHtml(u.username)}</td><td>${u.is_admin ? 'Administrator' : 'Standard user'}</td><td><button class="reset-password" data-user-id="${u.id}" data-user-name="${escapeHtml(u.display_name)}">Reset password…</button><button class="revoke-sessions" data-user-id="${u.id}">Revoke sessions</button></td></tr>`).join('')}</tbody></table></div></div></section>`, 'admin');
  $('#user-form').onsubmit = async event => { event.preventDefault(); const form = event.target; try { await api('/users', {method:'POST', body:JSON.stringify({username:form.username.value, display_name:form.display_name.value, password:form.password.value, is_admin:form.is_admin.checked})}); toast('User created.'); renderAdmin(); } catch (error) { toast(error.message, true); } };
  $('#project-form').onsubmit = async event => { event.preventDefault(); const form = event.target; const value = name => form[name].value || null; try { await api('/projects', {method:'POST', body:JSON.stringify({key:value('key'), name:value('name'), description:value('description') || '', gitlab_url:value('gitlab_url'), gitlab_project_id:value('gitlab_project_id'), gitlab_token:value('gitlab_token')})}); toast('Project created.'); await loadProjects(); location.hash = '#/dashboard'; } catch (error) { toast(error.message, true); } };
  $$('.delete-project').forEach(button => button.onclick = async () => {
    const values = await openModal({title:'Permanently delete project', message:`This deletes ${button.dataset.projectName}, its test library, runs, execution history, and local evidence. Existing GitLab issues remain.`, fields:[{name:'confirmation', label:`Type ${button.dataset.projectKey} to confirm`, required:true, autocomplete:'off'}], confirmLabel:'Delete project', danger:true});
    if (!values) return;
    if (values.confirmation !== button.dataset.projectKey) {
      toast('Project key did not match. Nothing was deleted.', true);
      return;
    }
    button.disabled = true; button.textContent = 'Deleting…';
    try {
      const result = await api(`/projects/${button.dataset.projectId}`, {method:'DELETE'});
      await loadProjects();
      toast(`${result.project_name} deleted: ${result.test_cases} cases, ${result.runs} runs, ${result.evidence} evidence files.`);
      renderAdmin();
    } catch (error) { toast(error.message, true); button.disabled = false; button.textContent = 'Delete project…'; }
  });
  $$('.archive-project').forEach(button => button.onclick = async () => { const archived = button.dataset.archived === 'true'; if (!await confirmModal(`${archived ? 'Archive' : 'Restore'} project`, `${archived ? 'Archive' : 'Restore'} this project?`, archived ? 'Archive' : 'Restore')) return; try { await api(`/projects/${button.dataset.projectId}/archive`, {method:'POST', body:JSON.stringify({archived})}); await loadProjects(); toast(archived ? 'Project archived.' : 'Project restored.'); renderAdmin(); } catch (error) { toast(error.message, true); } });
  $$('.reset-password').forEach(button => button.onclick = async () => { const values = await openModal({title:'Reset password', message:`Set a temporary password for ${button.dataset.userName}. They will be required to change it after signing in.`, fields:[{name:'password', label:'Temporary password', type:'password', required:true, minlength:12, maxlength:200, autocomplete:'new-password'}], confirmLabel:'Reset password'}); if (!values) return; try { await api(`/users/${button.dataset.userId}/reset-password`, {method:'POST', body:JSON.stringify({new_password:values.password})}); toast('Password reset. The user must change it at next sign-in.'); } catch (error) { toast(error.message, true); } });
  $$('.revoke-sessions').forEach(button => button.onclick = async () => { if (!await confirmModal('Revoke active sessions', 'Sign this user out of every active session?', 'Revoke sessions', true)) return; try { const result = await api(`/users/${button.dataset.userId}/revoke-sessions`, {method:'POST'}); toast(`${result.revoked} sessions revoked.`); } catch (error) { toast(error.message, true); } });
}

async function route() {
  if (!state.user) return;
  const parts = location.hash.replace(/^#\/?/, '').split('/').filter(Boolean);
  const name = parts[0] || 'dashboard';
  try {
    if (name === 'dashboard') await renderDashboard();
    else if (name === 'cases') await renderCases();
    else if (name === 'requirements') await renderRequirements();
    else if (name === 'import') await renderImport();
    else if (name === 'runs' && parts[1]) await renderRun(Number(parts[1]));
    else if (name === 'runs') await renderRuns();
    else if (name === 'reports') await renderReports();
    else if (name === 'team') await renderTeam();
    else if (name === 'settings') await renderSettings();
    else if (name === 'account') await renderAccount();
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
  try { const providers = await api('/auth/providers'); $('#gitlab-login').classList.toggle('hidden', !providers.gitlab); } catch (_) {}
  try { const data = await api('/auth/me'); state.user = data.user; state.csrf = data.csrf_token; await showApp(); }
  catch (_) { showLogin(); }
})();
