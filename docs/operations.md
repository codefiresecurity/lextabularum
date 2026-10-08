# Operations runbook

This runbook covers direct Nginx, MariaDB, PHP-FPM, and systemd deployments. Run commands from the application directory as the deployment account unless `sudo` is shown.

## Upgrade an existing installation

1. Announce a maintenance window and stop writers:

   ```bash
   sudo systemctl stop lextabularum-worker.service lextabularum-api.service
   ```

2. Back up the database and evidence as one recovery point:

   ```bash
   mkdir -p backups
   mariadb-dump --single-transaction --routines --triggers lextabularum > backups/lextabularum.sql
   tar -C storage -czf backups/evidence.tgz evidence
   ```

   Store the two files together outside the application host. Protect them as production data because they contain account, execution, and screenshot evidence.

3. Deploy the new application files and install the pinned dependency ranges:

   ```bash
   .venv/bin/pip install -r requirements.txt
   ```

4. Apply database migrations exactly once:

   ```bash
   .venv/bin/python -m api.app.migrate
   .venv/bin/alembic current
   ```

   A database created by the earlier bootstrap flow has no Alembic marker. The migration command recognizes that baseline, stamps it as revision `0001`, and then applies the later revisions. Do not run `alembic stamp` manually.

5. Start the API and worker, then verify health:

   ```bash
   sudo systemctl start lextabularum-api.service lextabularum-worker.service
   curl --fail http://127.0.0.1:8000/api/health
   sudo systemctl --no-pager --full status lextabularum-api.service lextabularum-worker.service
   ```

6. Sign in and smoke-test project selection, a passing attempt, and a disposable failed attempt that creates a GitLab issue.

## Rollback and restore

Application rollback is safe only when the old code understands the upgraded schema. When in doubt, restore both database and evidence from the same pre-upgrade recovery point. Restore the SQL into an empty database; importing over the upgraded database can leave new tables and the Alembic revision marker behind.

```bash
sudo systemctl stop lextabularum-worker.service lextabularum-api.service
sudo mariadb -e "DROP DATABASE lextabularum; CREATE DATABASE lextabularum CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
mariadb lextabularum < backups/lextabularum.sql
mv storage/evidence storage/evidence.failed-upgrade
tar -C storage -xzf backups/evidence.tgz
sudo systemctl start lextabularum-api.service lextabularum-worker.service
```

The database account grants created during deployment remain valid after recreating the database. Choose a unique name instead of `evidence.failed-upgrade` if it already exists. Practice this restore on a non-production database and storage path before relying on it. Never test a restore over the only production copy.

## GitLab delivery

Failed attempts are committed locally before GitLab is called. If GitLab is unavailable, `/api/health` reports pending delivery jobs and the worker retries them with an idempotency marker. Keep exactly one worker service running per database until distributed job claiming is introduced.

For issue status reconciliation, configure a GitLab Issue Hook with the URL displayed under **Project settings** and use the same webhook secret. Prefer a trusted internal certificate authority and `GITLAB_VERIFY_SSL=true`; `false` is available for private installations with invalid certificates.

Useful checks:

```bash
journalctl -u lextabularum-api.service -u lextabularum-worker.service --since today
curl --fail http://127.0.0.1:8000/api/health
```

## Evidence retention

`EVIDENCE_RETENTION_DAYS` controls when the worker removes local files for submitted attempts. Metadata, attempt history, and GitLab links remain. Staged files are deliberately excluded so an unfinished execution is not silently damaged. Backups may retain evidence longer than the live setting, so apply the same retention policy to backup storage.

## Account recovery

A system administrator can reset a password and revoke all sessions from **Administration → Accounts**. Reset passwords are temporary and must be changed at next sign-in. If all administrators are inaccessible, use the bootstrap command with a new username to create a recovery administrator, sign in, repair the affected account, and then disable or remove the recovery access according to local policy.

## Routine verification

- Review `/api/health` and service restart counts.
- Confirm backups complete and periodically perform a separate-host restore drill.
- Review pending GitLab jobs after GitLab outages.
- Test login, case import preview, one execution, CSV export, and webhook reconciliation after upgrades.
- Rotate project access tokens and webhook secrets from **Project settings**.
- Archive completed runs and inactive projects; reserve permanent deletion for approved data-destruction requests.
