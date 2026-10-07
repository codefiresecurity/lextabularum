# Lex Tabularum

Lex Tabularum is a small, self-hosted test case management system for teams using GitLab. It imports human-readable Markdown plans, preserves case revisions, creates assigned execution runs, and opens a GitLab issue with required notes and screenshot evidence when a test fails.

The application uses a FastAPI service for all data and integrations and a framework-free PHP/JavaScript interface. MariaDB is the production database.

## Quick start for development

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
# For a no-setup local trial, set DATABASE_URL=sqlite:///./lextabularum-dev.db
.venv/bin/python -m api.app.bootstrap --username admin --display-name "System Administrator" --password 'replace-this-password'
.venv/bin/uvicorn api.app.main:app --reload --port 8000
php -S 127.0.0.1:8080 -t web web/dev-router.php
```

Open `http://127.0.0.1:8080`. See [docs/deployment.md](docs/deployment.md) for a direct Nginx/MariaDB deployment and [docs/import-format.md](docs/import-format.md) for the supported Markdown format.

## Command-line import

```bash
.venv/bin/python -m cli.import_tests docs/example-plan.md --project MYPROJECT --dry-run
.venv/bin/python -m cli.import_tests docs/example-plan.md --project MYPROJECT
```

The CLI and API importer are idempotent. Changed content creates a new case revision; unchanged content is not duplicated.

