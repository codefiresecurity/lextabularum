<?php
declare(strict_types=1);
header('Content-Type: text/html; charset=utf-8');
header("Content-Security-Policy: default-src 'self'; img-src 'self' data: blob:; style-src 'self'; script-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'");
header('X-Content-Type-Options: nosniff');
header('Referrer-Policy: same-origin');
?>
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Lex Tabularum</title>
  <link rel="stylesheet" href="/assets/app.css">
  <script src="/assets/app.js" defer></script>
</head>
<body>
  <svg class="icon-sprite" aria-hidden="true">
    <symbol id="i-dashboard" viewBox="0 0 16 16"><path d="M1 1h6v6H1zm8 0h6v4H9zM1 9h6v6H1zm8-2h6v8H9z"/></symbol>
    <symbol id="i-cases" viewBox="0 0 16 16"><path d="M3 1h10v14H3z"/><path class="cut" d="M5 4h6M5 7h6M5 10h6"/></symbol>
    <symbol id="i-requirements" viewBox="0 0 16 16"><path d="m8 1 6 4v6l-6 4-6-4V5zm0 3L5 6v4l3 2 3-2V6z"/></symbol>
    <symbol id="i-runs" viewBox="0 0 16 16"><path d="M3 1 14 8 3 15z"/></symbol>
    <symbol id="i-reports" viewBox="0 0 16 16"><path d="M1 14h14v1H1zM3 8h2v5H3zm4-5h2v10H7zm4 3h2v7h-2z"/></symbol>
    <symbol id="i-import" viewBox="0 0 16 16"><path d="M7 11h2V5l2 2 1-1-4-4-4 4 1 1 2-2zM2 12h12v3H2z"/></symbol>
    <symbol id="i-team" viewBox="0 0 16 16"><path d="M5 7a3 3 0 1 0 0-6 3 3 0 0 0 0 6m6-1a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5M0 15v-3c0-2.2 2.2-4 5-4s5 1.8 5 4v3zm10-7c3 0 6 1.5 6 4v3h-4v-3c0-1.5-.7-2.8-2-3.7z"/></symbol>
    <symbol id="i-settings" viewBox="0 0 16 16"><path d="m9 1 .5 2a6 6 0 0 1 1.2.5l1.8-1 1.4 1.4-1 1.8c.2.4.4.8.5 1.3l2 .5v2l-2 .5a6 6 0 0 1-.5 1.2l1 1.8-1.4 1.4-1.8-1a6 6 0 0 1-1.2.5l-.5 2H7l-.5-2a6 6 0 0 1-1.2-.5l-1.8 1L2.1 13l1-1.8a6 6 0 0 1-.5-1.2l-2-.5v-2l2-.5c.1-.5.3-.9.5-1.3l-1-1.8 1.4-1.4 1.8 1A6 6 0 0 1 6.5 3L7 1zm-1 5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5"/></symbol>
    <symbol id="i-admin" viewBox="0 0 16 16"><path d="M8 0 2 2v5c0 4 2.5 7 6 9 3.5-2 6-5 6-9V2zm0 3a2 2 0 1 1 0 4 2 2 0 0 1 0-4m-3 8c.2-2 1.3-3 3-3s2.8 1 3 3c-.8 1-1.8 1.8-3 2.5A11 11 0 0 1 5 11"/></symbol>
    <symbol id="i-account" viewBox="0 0 16 16"><path d="M8 8a4 4 0 1 0 0-8 4 4 0 0 0 0 8M1 16c0-4 2.7-7 7-7s7 3 7 7z"/></symbol>
    <symbol id="i-workspace" viewBox="0 0 16 16"><path d="M1 3h6l1 2h7v9H1z"/></symbol>
    <symbol id="i-inbox" viewBox="0 0 16 16"><path d="M2 2h12l2 9v3H0v-3zm2 2-1 6h3l1 2h2l1-2h3l-1-6z"/></symbol>
    <symbol id="i-field" viewBox="0 0 16 16"><path d="m2 11-1 4 4-1 9-9-3-3zm10-10 3 3 1-1-3-3z"/></symbol>
    <symbol id="i-list" viewBox="0 0 16 16"><path d="M1 2h3v3H1zm5 0h9v3H6zM1 7h3v3H1zm5 0h9v3H6zM1 12h3v3H1zm5 0h9v3H6z"/></symbol>
    <symbol id="i-calendar" viewBox="0 0 16 16"><path d="M2 2h2V0h2v2h4V0h2v2h2v13H2zm2 4v7h8V6z"/></symbol>
    <symbol id="i-lock" viewBox="0 0 16 16"><path d="M3 7h1V4a4 4 0 0 1 8 0v3h1v8H3zm3 0h4V4a2 2 0 0 0-4 0z"/></symbol>
    <symbol id="i-search" viewBox="0 0 16 16"><path d="M7 1a6 6 0 1 0 3.7 10.7L15 16l1-1-4.3-4.3A6 6 0 0 0 7 1m0 2a4 4 0 1 1 0 8 4 4 0 0 1 0-8"/></symbol>
  </svg>
  <div id="login-view" class="login-shell hidden">
    <main class="login-panel">
      <div class="brand-mark" aria-hidden="true">LT</div>
      <p class="eyebrow">QUALITY OPERATIONS</p>
      <h1>Lex Tabularum</h1>
      <p class="muted">Test execution and evidence control.</p>
      <form id="login-form" class="stack">
        <label>Username<input name="username" autocomplete="username" required autofocus></label>
        <label>Password<input name="password" type="password" autocomplete="current-password" required></label>
        <p id="login-error" class="error hidden" role="alert"></p>
        <button class="primary" type="submit">Sign in</button>
        <a id="gitlab-login" class="sso-button hidden" href="/api/auth/gitlab/start">Sign in with GitLab</a>
      </form>
    </main>
  </div>

  <div id="app-view" class="app-shell hidden">
    <header class="topbar">
      <button id="menu-toggle" class="icon-button mobile-only" aria-label="Toggle navigation">☰</button>
      <a class="product-lockup" href="#/dashboard">
        <span class="product-kicker">QUALITY OPERATIONS PLATFORM</span>
        <span class="wordmark">Lex Tabularum</span>
      </a>
      <div class="topbar-right">
        <div class="system-health"><svg class="ui-icon icon-green" aria-hidden="true"><use href="#i-dashboard"></use></svg><span>System online</span></div>
        <div class="user-block"><span>USER</span><strong id="current-user"></strong></div>
        <a href="#/account" class="utility-button" id="notification-button"><svg class="ui-icon icon-amber" aria-hidden="true"><use href="#i-inbox"></use></svg> INBOX <span id="notification-count">0</span></a>
        <button id="logout-button" class="utility-button">LOG OUT</button>
      </div>
    </header>
    <div class="modulebar">
      <label class="project-picker"><svg class="ui-icon icon-amber" aria-hidden="true"><use href="#i-workspace"></use></svg><span>WORKSPACE</span><select id="project-select"></select></label>
      <nav class="module-tabs" aria-label="Workspace modules">
        <a href="#/dashboard" data-route="dashboard"><svg class="ui-icon icon-blue"><use href="#i-dashboard"></use></svg>Dashboard</a>
        <a href="#/cases" data-route="cases"><svg class="ui-icon icon-teal"><use href="#i-cases"></use></svg>Test Library</a>
        <a href="#/runs" data-route="runs"><svg class="ui-icon icon-green"><use href="#i-runs"></use></svg>Execution</a>
        <a href="#/reports" data-route="reports"><svg class="ui-icon icon-amber"><use href="#i-reports"></use></svg>Reports</a>
      </nav>
    </div>
    <div class="workbench">
      <aside id="sidebar" class="sidebar">
        <nav aria-label="Main navigation">
          <p class="nav-section">PROJECT OPERATIONS</p>
          <a href="#/dashboard" data-route="dashboard"><svg class="ui-icon icon-blue"><use href="#i-dashboard"></use></svg> Overview</a>
          <a href="#/cases" data-route="cases"><svg class="ui-icon icon-teal"><use href="#i-cases"></use></svg> Test library</a>
          <a href="#/requirements" data-route="requirements"><svg class="ui-icon icon-purple"><use href="#i-requirements"></use></svg> Requirements</a>
          <a href="#/runs" data-route="runs"><svg class="ui-icon icon-green"><use href="#i-runs"></use></svg> Test runs</a>
          <a href="#/reports" data-route="reports"><svg class="ui-icon icon-amber"><use href="#i-reports"></use></svg> Reports</a>
          <p class="nav-section">CONFIGURATION</p>
          <a href="#/import" data-route="import"><svg class="ui-icon icon-blue"><use href="#i-import"></use></svg> Import</a>
          <a href="#/team" data-route="team"><svg class="ui-icon icon-green"><use href="#i-team"></use></svg> Project team</a>
          <a href="#/settings" data-route="settings"><svg class="ui-icon icon-amber"><use href="#i-settings"></use></svg> Project settings</a>
          <a href="#/admin" data-route="admin" id="admin-nav"><svg class="ui-icon icon-red"><use href="#i-admin"></use></svg> Administration</a>
        </nav>
        <div class="sidebar-foot"><span class="status-dot"></span> API CONNECTED<br><small>BUILD 0.2.0</small></div>
      </aside>
      <main id="content" class="content" tabindex="-1"></main>
    </div>
    <div id="toast" class="toast hidden" role="status"></div>
    <dialog id="app-dialog" class="app-dialog" aria-labelledby="dialog-title">
      <form id="dialog-form" method="dialog">
        <header class="dialog-head">
          <strong id="dialog-title"></strong>
          <button id="dialog-close" class="dialog-close" type="button" aria-label="Close dialog">×</button>
        </header>
        <div id="dialog-body" class="dialog-body"></div>
        <footer class="dialog-actions">
          <button id="dialog-cancel" type="button">Cancel</button>
          <button id="dialog-confirm" class="primary" type="submit">Save</button>
        </footer>
      </form>
    </dialog>
  </div>
</body>
</html>
