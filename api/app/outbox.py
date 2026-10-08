from datetime import timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .gitlab import GitLabClient
from .models import (
    Evidence, ExecutionAttempt, GitLabOutbox, Notification, Project, RunCase, TestRun, utcnow,
)
from .security import decrypt_secret


def process_gitlab_item(db: Session, item: GitLabOutbox) -> bool:
    attempt = db.get(ExecutionAttempt, item.attempt_id)
    row = db.get(RunCase, attempt.run_case_id) if attempt else None
    run = db.get(TestRun, row.run_id) if row else None
    project = db.get(Project, run.project_id) if run else None
    if not attempt or not row or not run or not project:
        item.status = "failed"
        item.last_error = "Referenced execution data no longer exists"
        db.commit()
        return False
    token = decrypt_secret(project.gitlab_token_encrypted)
    if not project.gitlab_url or not project.gitlab_project_id or not token:
        item.status = "pending"
        item.last_error = "GitLab integration is not configured"
        item.next_attempt_at = utcnow() + timedelta(seconds=settings.gitlab_retry_seconds)
        attempt.gitlab_status = "pending"
        db.commit()
        return False

    marker = f"[LT-A{attempt.id}]"
    client = GitLabClient(project.gitlab_url, project.gitlab_project_id, token,
                          verify_ssl=settings.gitlab_verify_ssl)
    try:
        issue = client.find_issue(marker)
        if not issue:
            links = []
            evidence = db.scalars(select(Evidence).where(Evidence.attempt_id == attempt.id).order_by(Evidence.id)).all()
            for item_evidence in evidence:
                upload = client.upload(settings.evidence_dir / item_evidence.stored_name, item_evidence.mime_type)
                links.append(upload.get("markdown") or f"[{item_evidence.original_name}]({upload.get('url', '')})")
            description = (
                f"<!-- lex-tabularum-attempt:{attempt.id} -->\n"
                f"## Automated test execution failure\n\n"
                f"**Test case:** {row.case.external_id} — {row.version.title}\n"
                f"**Run:** {run.name}\n"
                f"**Build:** {run.build_version or 'Not specified'}\n"
                f"**Environment:** {run.environment or 'Not specified'}\n"
                f"**Commit:** {run.commit_sha or 'Not specified'}\n"
                f"**Reported by:** {attempt.executor.display_name}\n"
                f"**Attempt:** {attempt.attempt_number}\n\n"
                f"### What went wrong\n{attempt.notes}\n\n"
                f"### Expected\n{row.version.expected}\n\n"
                f"### Evidence\n" + "\n\n".join(links)
            )
            issue = client.create_issue(f"{marker} Test failure: {row.case.external_id} — {row.version.title}", description)
        attempt.gitlab_issue_iid = issue["iid"]
        attempt.gitlab_issue_url = issue["web_url"]
        attempt.gitlab_status = "created"
        row.gitlab_issue_iid = issue["iid"]
        row.gitlab_issue_url = issue["web_url"]
        item.status = "complete"
        item.completed_at = utcnow()
        item.last_error = ""
        if row.assigned_to:
            db.add(Notification(user_id=row.assigned_to, project_id=project.id, kind="gitlab_issue_created",
                                title=f"GitLab issue created for {row.case.external_id}",
                                body=issue["web_url"], link=f"#/runs/{run.id}"))
        db.commit()
        return True
    except (httpx.HTTPError, OSError, KeyError) as exc:
        item.tries += 1
        item.status = "pending"
        item.last_error = str(exc)[:4000]
        item.next_attempt_at = utcnow() + timedelta(seconds=settings.gitlab_retry_seconds * min(10, 2 ** min(item.tries, 5)))
        attempt.gitlab_status = "pending"
        db.commit()
        return False


def process_pending(db: Session, limit: int = 20) -> tuple[int, int]:
    now = utcnow()
    items = db.scalars(
        select(GitLabOutbox).where(GitLabOutbox.status == "pending", GitLabOutbox.next_attempt_at <= now)
        .order_by(GitLabOutbox.id).limit(limit)
    ).all()
    succeeded = sum(1 for item in items if process_gitlab_item(db, item))
    return succeeded, len(items) - succeeded

