# Direct deployment

This guide assumes a Linux host with Nginx, PHP-FPM, MariaDB, Python 3.11–3.13, and a dedicated unprivileged service account. Commands vary by distribution. Python 3.14 should wait until its async ecosystem is fully validated for the target distribution.

## 1. Database

Create a database and restricted application account:

```sql
CREATE DATABASE lextabularum CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'lextabularum'@'127.0.0.1' IDENTIFIED BY 'replace-this-password';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, REFERENCES
  ON lextabularum.* TO 'lextabularum'@'127.0.0.1';
FLUSH PRIVILEGES;
```

## 2. Application

Create a virtual environment, install dependencies, and create `.env` from `.env.example`. Generate a long random `APP_SECRET` and do not rotate it without first replacing stored GitLab tokens.

`GITLAB_VERIFY_SSL=false` permits a local GitLab instance with a self-signed or otherwise invalid certificate. This disables certificate validation for GitLab API traffic. Prefer installing the internal certificate authority on the application host and setting this value to `true` when possible.

The evidence directory must be writable by the API service account and must not be inside the Nginx document root. Only the authenticated evidence API route should serve its files.

Upgrade the schema, then create the first administrator:

```bash
.venv/bin/python -m api.app.migrate
.venv/bin/python -m api.app.bootstrap \
  --username admin \
  --display-name "System Administrator" \
  --password 'a-long-one-time-password'
```

`api.app.migrate` detects installations originally created before Alembic, stamps their existing baseline schema, and applies later migrations. Back up MariaDB and evidence storage before every upgrade. Follow the exact upgrade and rollback sequence in [operations.md](operations.md).

Copy and customize the example units and Nginx configuration from `deploy/`. Set TLS up before setting `SESSION_COOKIE_SECURE=true`. In production that setting must remain true.

Reload systemd and start both services:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now lextabularum-api.service lextabularum-worker.service
curl --fail http://127.0.0.1:8000/api/health
```

## 3. Runtime

The API listens only on loopback. Nginx serves `web/` through PHP-FPM and proxies `/api/` to Uvicorn. The browser therefore sees a single origin and never receives the GitLab token. Enable both `lextabularum-api.service` and `lextabularum-worker.service`; the worker retries durable GitLab issue jobs after provider outages.

After deployment:

1. Sign in as the bootstrap administrator.
2. Create standard users.
3. Create a project and provide its GitLab URL, numeric ID or URL-encoded path, and project access token.
4. Add project members.
5. Import a Markdown plan.
6. Create a run and verify a failure against a disposable GitLab project.

## Operations

Back up MariaDB and the evidence directory together. Audit events and run snapshots live in MariaDB; screenshots remain in evidence storage even after they are copied to GitLab. Treat application logs as sensitive because integration errors may include internal hostnames.

System administrators can permanently delete a project from **Administration → Projects**. The operation removes the project's cases and revisions, test runs and results, memberships, local evidence files, encrypted GitLab configuration, and project-scoped audit events. It retains a minimal global deletion audit event and does not delete issues already created in GitLab.

`EVIDENCE_RETENTION_DAYS` controls how long submitted local evidence files are retained. The worker purges expired files while retaining their metadata and GitLab issue history. Staged evidence that has not been submitted is not purged automatically.
