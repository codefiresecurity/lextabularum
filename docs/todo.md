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
- [x] Responsive framework-free operator interface
- [x] Operational dashboard with completion, pass rate, queue, run, and workload widgets
- [x] Filterable execution reporting with print and CSV export
- [x] Audit records for key mutations
- [ ] Exercise the full flow against the target MariaDB and local GitLab installation
- [ ] Add migration tooling before the first production upgrade

## Milestone 2 — operational hardening

- [ ] Account password change and administrator password reset flows
- [ ] Login throttling and temporary lockout policy
- [ ] Project settings screen for rotating GitLab tokens
- [ ] Close/reopen and archive controls for test runs
- [ ] Bulk reassignment and filtered run creation
- [ ] Dashboard filters for assignee, run, and date range
- [ ] Evidence deletion/retention policy
- [ ] Background retry queue for transient GitLab outages, if desired
- [ ] Structured application logging and health monitoring
- [ ] MariaDB integration and authorization test suites

## Milestone 3 — richer test management

- [ ] Case editing and explicit case deactivation
- [ ] Requirements/tags and advanced search
- [ ] Run templates and release metadata
- [ ] Comments and execution timeline
- [ ] CSV/PDF reports and export
- [ ] GitLab webhook reconciliation for issue status
- [ ] Optional GitLab sign-in
