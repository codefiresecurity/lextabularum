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
        <div class="system-health"><span class="status-dot"></span><span>System online</span></div>
        <div class="user-block"><span>USER</span><strong id="current-user"></strong></div>
        <a href="#/account" class="utility-button" id="notification-button">INBOX <span id="notification-count">0</span></a>
        <button id="logout-button" class="utility-button">LOG OUT</button>
      </div>
    </header>
    <div class="modulebar">
      <label class="project-picker"><span>WORKSPACE</span><select id="project-select"></select></label>
      <nav class="module-tabs" aria-label="Workspace modules">
        <a href="#/dashboard" data-route="dashboard">Dashboard</a>
        <a href="#/cases" data-route="cases">Test Library</a>
        <a href="#/runs" data-route="runs">Execution</a>
        <a href="#/reports" data-route="reports">Reports</a>
      </nav>
    </div>
    <div class="workbench">
      <aside id="sidebar" class="sidebar">
        <nav aria-label="Main navigation">
          <p class="nav-section">PROJECT OPERATIONS</p>
          <a href="#/dashboard" data-route="dashboard"><span>▦</span> Overview</a>
          <a href="#/cases" data-route="cases"><span>≡</span> Test library</a>
          <a href="#/requirements" data-route="requirements"><span>◇</span> Requirements</a>
          <a href="#/runs" data-route="runs"><span>▶</span> Test runs</a>
          <a href="#/reports" data-route="reports"><span>▤</span> Reports</a>
          <p class="nav-section">CONFIGURATION</p>
          <a href="#/import" data-route="import"><span>⇧</span> Import</a>
          <a href="#/team" data-route="team"><span>◎</span> Project team</a>
          <a href="#/settings" data-route="settings"><span>⚒</span> Project settings</a>
          <a href="#/admin" data-route="admin" id="admin-nav"><span>⚙</span> Administration</a>
        </nav>
        <div class="sidebar-foot"><span class="status-dot"></span> API CONNECTED<br><small>BUILD 0.2.0</small></div>
      </aside>
      <main id="content" class="content" tabindex="-1"></main>
    </div>
    <div id="toast" class="toast hidden" role="status"></div>
  </div>
</body>
</html>
