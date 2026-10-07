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
  $$('.sidebar a').forEach(link => link.classList.toggle('active', link.dataset.route === routeName));
  $('#sidebar').classList.remove('open');
}

function setContent(html, routeName) {
  $('#content').innerHTML = html;
  activeNav(routeName);
  $('#content').focus({preventScroll: true});
}

async function renderDashboard() {
  if (!projectRequired()) return;
  const data = await api(`/projects/${state.projectId}/dashboard`);
  const done = (data.states.passed || 0) + (data.states.failed || 0) + (data.states.blocked || 0) + (data.states.skipped || 0);
  const total = Object.values(data.states).reduce((a, b) => a + b, 0);
  const rate = total ? Math.round(done / total * 100) : 0;
  setContent(pageHead('Operations overview', 'Current testing posture across the selected project.') + `
    <section class="grid">
      <div class="metric span-3"><span>Test cases</span><strong>${data.case_count}</strong></div>
      <div class="metric span-3"><span>Open runs</span><strong>${data.open_runs}</strong></div>
      <div class="metric span-3"><span>Passed executions</span><strong>${data.states.passed || 0}</strong></div>
      <div class="metric span-3"><span>Open failures</span><strong>${data.states.failed || 0}</strong></div>
      <div class="panel span-8"><h2>Execution completion</h2><div class="progress"><span style="width:${rate}%"></span></div><p><strong>${rate}%</strong> terminal results across all runs</p></div>
      <div class="panel span-4"><h2>Queue</h2><p><span class="badge">${data.states.not_started || 0} waiting</span></p><p><span class="badge in_progress">${data.states.in_progress || 0} in progress</span></p></div>
    </section>`, 'dashboard');
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
