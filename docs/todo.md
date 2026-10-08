# Delivery plan and TODO

## Milestone 1 — working MVP

- [x] Database-backed accounts and secure sessions
- [x] Global administrator and per-project manager/tester/viewer roles
- [x] Multiple projects with independent GitLab settings
- [x] Markdown web and command-line import
- [x] Idempotent imports with immutable case revisions
- [x] Test runs pinned to case revisions
- [x] Run assignment and result states
- [x] Mandatory notes and image evidence for failures
- [x] Immediate GitLab upload and issue creation
- [x] Preserve an open execution card and unsaved notes while uploading evidence
- [x] Remove mistakenly uploaded evidence before GitLab issue submission
- [x] Responsive framework-free operator interface
- [x] Operational dashboard with completion, pass rate, queue, run, and workload widgets
- [x] Filterable execution reporting with print and CSV export
- [x] Administrator-only project deletion with dependent data and evidence cleanup
- [x] Audit records for key mutations
- [ ] Exercise the upgraded flow against the target MariaDB and local GitLab installation
- [x] Add Alembic migrations and existing-installation baseline detection

## Milestone 2 — operational hardening

- [x] Account password change and administrator password reset flows
- [x] Login throttling, lockout, session revocation, and expired-session cleanup
- [x] Project settings screen for rotating GitLab tokens and webhook secrets
- [x] Close/reopen and archive controls for test runs
- [x] Bulk reassignment, run templates, and filtered run creation
- [x] Report filters for assignee, run, state, and date range
- [x] Evidence deletion and worker-driven retention policy
- [x] Durable GitLab outbox with immediate attempt, retry, and idempotency marker
- [x] Structured request logging and database/outbox health monitoring
- [x] Cross-project authorization regression coverage
- [ ] Exercise migrations and the full regression suite against the target MariaDB version

## Milestone 3 — richer test management

- [x] Case editing with immutable revisions and explicit case deactivation
- [x] Requirements mapping, tags, and advanced search
- [x] Run templates and build/environment/commit metadata
- [x] Comments and immutable execution-attempt timeline
- [x] CSV export and print-to-PDF report layout
- [x] GitLab webhook reconciliation for issue status
- [x] Optional existing-account GitLab OAuth sign-in
