# Architecture

## Product boundary

Lex Tabularum manages multiple software projects. Each project maps to one GitLab repository and has its own members, reusable test case library, and test runs. A user can hold a different role in each project.

The initial roles are:

- **System administrator:** creates accounts and projects and can access all projects.
- **Project manager:** imports cases, manages membership, creates runs, and can execute cases.
- **Tester:** executes cases assigned to them or currently unassigned.
- **Viewer:** read-only project access.

## Components

```text
Browser
  ├─ PHP serves the application shell
  ├─ JavaScript calls same-origin /api routes
  └─ HttpOnly session cookie + CSRF header
               │
             Nginx
       ┌───────┴────────┐
       │                │
   PHP-FPM         FastAPI/Uvicorn
                        ├─ MariaDB
                        ├─ local evidence storage
                        └─ local GitLab REST API
```

PHP intentionally contains no domain or database logic. It supplies the hardened HTML shell and static assets. The Python API owns authentication, authorization, persistence, importing, audit records, evidence, and GitLab integration.

## Core data behavior

- `test_cases` represents the stable project-scoped ID, such as `DF-001`.
- `test_case_versions` contains an immutable snapshot of the title, module, priority, lifecycle, steps, and expected result. Re-importing changed content increments the revision.
- `run_cases` pins the exact case version in use when a run is created. Later imports cannot rewrite prior execution instructions.
- A failed result requires non-empty notes and at least one image.
- Terminal results create immutable numbered execution attempts. Retesting resets only the working run case; prior results, notes, evidence, and GitLab links remain in history.
- Failed attempts commit before external delivery and create a durable outbox row. The API tries immediate delivery while the worker retries transient failures with an idempotency marker.
- A tester may remove mistakenly uploaded evidence before submitting a failed result. Once GitLab issue creation succeeds, evidence removal is blocked locally because the attachment is already embedded in GitLab.
- GitLab access tokens are encrypted at rest using a key derived from `APP_SECRET`.
- Authentication uses database sessions stored as SHA-256 token digests. Passwords use scrypt with a unique salt.
- Mutating browser requests require the session's CSRF token.

## API discovery

When enabled internally, interactive OpenAPI documentation is available at `/api/docs`. Nginx may restrict that route to administrators or an internal subnet.

## Reporting

The project dashboard calculates completion, decisive pass rate, current execution-state distribution, attention queues, recent-run health, and tester workload directly from pinned run cases. The Reports workspace can filter execution rows by run and state, search the current result set, print a clean report, and export CSV. A failed execution links back to its GitLab issue from the report.
