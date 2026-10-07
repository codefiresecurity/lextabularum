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

The evidence directory must be writable by the API service account and must not be inside the Nginx document root. Only the authenticated evidence API route should serve its files.

Initialize the schema and first administrator:

```bash
.venv/bin/python -m api.app.bootstrap \
  --username admin \
  --display-name "System Administrator" \
  --password 'a-long-one-time-password'
```

Copy and customize the example units and Nginx configuration from `deploy/`. Set TLS up before setting `SESSION_COOKIE_SECURE=true`. In production that setting must remain true.

## 3. Runtime

The API listens only on loopback. Nginx serves `web/` through PHP-FPM and proxies `/api/` to Uvicorn. The browser therefore sees a single origin and never receives the GitLab token.

After deployment:

1. Sign in as the bootstrap administrator.
2. Create standard users.
3. Create a project and provide its GitLab URL, numeric ID or URL-encoded path, and project access token.
4. Add project members.
5. Import a Markdown plan.
6. Create a run and verify a failure against a disposable GitLab project.

## Operations

Back up MariaDB and the evidence directory together. Audit events and run snapshots live in MariaDB; screenshots remain in evidence storage even after they are copied to GitLab. Treat application logs as sensitive because integration errors may include internal hostnames.
