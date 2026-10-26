import json
import hashlib
import hmac
import logging
import time
from urllib.parse import urlencode
import mimetypes
import secrets
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx
from fastapi import Cookie, Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session as DBSession

from .config import settings
from .db import Base, SessionLocal, engine, get_db
from .dependencies import current_session, current_user, membership, require_admin, require_project
from .gitlab import GitLabClient
from .importer import import_cases, parse_upload
from .models import (
    AuditEvent, CaseRequirement, Evidence, ExecutionAttempt, GitLabOutbox, Notification, Project,
    ProjectMember, ProjectRole, Requirement, RunCase, RunCaseComment, RunState, RunTemplate, Session,
    TestCase, TestCaseVersion, TestRun, User, WebhookEvent, utcnow,
)
from .schemas import (
    AssignIn, BulkAssignIn, CaseEditIn, CaseTagsIn, CommentIn, LoginIn, MemberIn, PasswordChangeIn,
    PasswordResetIn, ProjectArchiveIn, ProjectCreate, ProjectSettingsIn, RequirementIn, RequirementMapIn,
    ResultIn, RetestIn, RunCreate, RunStatusIn, RunTemplateIn, UserCreate,
)
from .outbox import process_gitlab_item
from .security import decrypt_secret, encrypt_secret, hash_password, new_session, verify_password


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.evidence_dir.mkdir(parents=True, exist_ok=True)
    with SessionLocal() as db:
        db.execute(delete(Session).where(Session.expires_at < utcnow()))
        db.commit()
    yield


app = FastAPI(title="Lex Tabularum", version="0.2.0", docs_url="/api/docs",
              openapi_url="/api/openapi.json", lifespan=lifespan)
logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO),
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("lextabularum.api")


@app.middleware("http")
async def request_log(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or secrets.token_hex(8)
    started = time.monotonic()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    logger.info("request_id=%s method=%s path=%s status=%s duration_ms=%s",
                request_id, request.method, request.url.path, response.status_code,
                round((time.monotonic() - started) * 1000))
    return response


def audit(db: DBSession, user_id: int | None, action: str, entity_type: str, entity_id, project_id=None, detail=None):
    db.add(AuditEvent(user_id=user_id, project_id=project_id, action=action, entity_type=entity_type,
                      entity_id=str(entity_id), detail_json=json.dumps(detail or {})))


def user_dict(user: User):
    return {"id": user.id, "username": user.username, "display_name": user.display_name,
            "is_admin": user.is_admin, "active": user.active,
            "must_change_password": user.must_change_password}


def case_dict(case: TestCase):
    return {"id": case.id, "external_id": case.external_id, "title": case.title, "section": case.section,
            "priority": case.priority, "lifecycle": case.lifecycle, "version": case.current_version,
            "active": case.active}


def requirement_dict(item: Requirement):
    return {"id": item.id, "key": item.key, "title": item.title,
            "description": item.description, "active": item.active}


@app.get("/api/health")
async def health(db: DBSession = Depends(get_db)):
    db.execute(select(1)).scalar_one()
    pending = db.scalar(select(func.count()).select_from(GitLabOutbox).where(GitLabOutbox.status == "pending"))
    return {"status": "ok", "service": "lex-tabularum", "database": "ok", "gitlab_jobs_pending": pending}


@app.post("/api/auth/login")
async def login(body: LoginIn, response: Response, db: DBSession = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == body.username.lower()))
    now = datetime.now(timezone.utc)
    locked_until = user.locked_until if user else None
    if locked_until and locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=timezone.utc)
    if user and locked_until and locked_until > now:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Account temporarily locked. Try again later.")
    if not user or not user.active or not verify_password(body.password, user.password_hash):
        if user and user.active:
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= settings.login_max_attempts:
                user.locked_until = now + timedelta(minutes=settings.login_lock_minutes)
                user.failed_login_attempts = 0
            db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid username or password")
    user.failed_login_attempts = 0
    user.locked_until = None
    raw, token_hash, csrf, expires = new_session()
    db.add(Session(user_id=user.id, token_hash=token_hash, csrf_token=csrf, expires_at=expires))
    audit(db, user.id, "auth.login", "user", user.id)
    db.commit()
    response.set_cookie("lt_session", raw, httponly=True, secure=settings.session_cookie_secure,
                        samesite="strict", max_age=settings.session_hours * 3600, path="/")
    return {"user": user_dict(user), "csrf_token": csrf}


@app.get("/api/auth/providers")
async def auth_providers():
    return {"gitlab": bool(settings.gitlab_oauth_url and settings.gitlab_oauth_client_id and settings.gitlab_oauth_client_secret)}


@app.get("/api/auth/gitlab/start")
async def gitlab_login_start():
    if not settings.gitlab_oauth_url or not settings.gitlab_oauth_client_id or not settings.gitlab_oauth_client_secret:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "GitLab sign-in is not configured")
    state_value = secrets.token_urlsafe(24)
    state_signature = hmac.new(settings.app_secret.encode(), state_value.encode(), hashlib.sha256).hexdigest()
    params = urlencode({"client_id": settings.gitlab_oauth_client_id,
                        "redirect_uri": f"{settings.public_origin.rstrip('/')}/api/auth/gitlab/callback",
                        "response_type": "code", "scope": "read_user", "state": state_value})
    response = RedirectResponse(f"{settings.gitlab_oauth_url.rstrip('/')}/oauth/authorize?{params}")
    response.set_cookie("lt_oauth_state", f"{state_value}.{state_signature}", httponly=True,
                        secure=settings.session_cookie_secure, samesite="lax", max_age=600)
    return response


@app.get("/api/auth/gitlab/callback")
async def gitlab_login_callback(code: str, state: str, response: Response,
                                 lt_oauth_state: str | None = Cookie(default=None), db: DBSession = Depends(get_db)):
    if not lt_oauth_state or "." not in lt_oauth_state:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "OAuth state is missing")
    stored_state, stored_signature = lt_oauth_state.rsplit(".", 1)
    expected_signature = hmac.new(settings.app_secret.encode(), stored_state.encode(), hashlib.sha256).hexdigest()
    if state != stored_state or not hmac.compare_digest(stored_signature, expected_signature):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "OAuth state is invalid")
    async with httpx.AsyncClient(verify=settings.gitlab_verify_ssl, timeout=30) as client:
        token_response = await client.post(f"{settings.gitlab_oauth_url.rstrip('/')}/oauth/token", data={
            "client_id": settings.gitlab_oauth_client_id, "client_secret": settings.gitlab_oauth_client_secret,
            "code": code, "grant_type": "authorization_code",
            "redirect_uri": f"{settings.public_origin.rstrip('/')}/api/auth/gitlab/callback",
        })
        token_response.raise_for_status()
        identity_response = await client.get(f"{settings.gitlab_oauth_url.rstrip('/')}/api/v4/user",
                                             headers={"Authorization": f"Bearer {token_response.json()['access_token']}"})
        identity_response.raise_for_status()
    username = identity_response.json().get("username", "").lower()
    user = db.scalar(select(User).where(User.username == username, User.active.is_(True)))
    if not user:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No active Lex Tabularum account matches this GitLab username")
    raw, token_hash, csrf, expires = new_session()
    db.add(Session(user_id=user.id, token_hash=token_hash, csrf_token=csrf, expires_at=expires))
    audit(db, user.id, "auth.gitlab_login", "user", user.id)
    db.commit()
    redirect = RedirectResponse(f"{settings.public_origin.rstrip('/')}/#/dashboard")
    redirect.set_cookie("lt_session", raw, httponly=True, secure=settings.session_cookie_secure,
                        samesite="strict", max_age=settings.session_hours * 3600, path="/")
    redirect.delete_cookie("lt_oauth_state")
    return redirect


@app.post("/api/auth/logout", status_code=204)
async def logout(response: Response, session: Session = Depends(current_session), db: DBSession = Depends(get_db)):
    audit(db, session.user_id, "auth.logout", "user", session.user_id)
    db.delete(session)
    db.commit()
    response.delete_cookie("lt_session", path="/")


@app.get("/api/notifications")
async def list_notifications(user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    items = db.scalars(select(Notification).where(Notification.user_id == user.id)
                       .order_by(Notification.created_at.desc()).limit(100)).all()
    return [{"id": item.id, "kind": item.kind, "title": item.title, "body": item.body,
             "link": item.link, "read_at": item.read_at, "created_at": item.created_at} for item in items]


@app.post("/api/notifications/{notification_id}/read")
async def read_notification(notification_id: int, user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    item = db.get(Notification, notification_id)
    if not item or item.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found")
    item.read_at = utcnow()
    db.commit()
    return {"ok": True}


@app.post("/api/webhooks/gitlab/{project_id}")
async def gitlab_webhook(project_id: int, request: Request, db: DBSession = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    expected = decrypt_secret(project.gitlab_webhook_secret_encrypted) or settings.gitlab_webhook_secret
    supplied = request.headers.get("X-Gitlab-Token", "")
    if not expected or not hmac.compare_digest(supplied.encode(), expected.encode()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid webhook token")
    raw = await request.body()
    payload_hash = hashlib.sha256(raw).hexdigest()
    event_id = request.headers.get("X-Gitlab-Event-UUID") or payload_hash
    if db.scalar(select(WebhookEvent).where(WebhookEvent.provider_event_id == event_id)):
        return {"duplicate": True}
    payload = json.loads(raw or b"{}")
    event_type = request.headers.get("X-Gitlab-Event", "unknown")
    db.add(WebhookEvent(project_id=project_id, provider_event_id=event_id,
                        event_type=event_type, payload_hash=payload_hash))
    attributes = payload.get("object_attributes", {})
    if event_type == "Issue Hook" and attributes.get("iid"):
        attempts = db.scalars(
            select(ExecutionAttempt).join(RunCase).join(TestRun)
            .where(TestRun.project_id == project_id, ExecutionAttempt.gitlab_issue_iid == int(attributes["iid"]))
        ).all()
        for attempt in attempts:
            attempt.gitlab_status = f"issue_{attributes.get('state', 'updated')}"
            row = db.get(RunCase, attempt.run_case_id)
            if row.assigned_to:
                db.add(Notification(user_id=row.assigned_to, project_id=project_id, kind="gitlab_issue_update",
                                    title=f"GitLab issue updated for {row.case.external_id}",
                                    body=f"Issue is now {attributes.get('state', 'updated')}",
                                    link=f"#/runs/{row.run_id}"))
    db.commit()
    return {"accepted": True}


@app.get("/api/auth/me")
async def me(session: Session = Depends(current_session)):
    return {"user": user_dict(session.user), "csrf_token": session.csrf_token}


@app.get("/api/users")
async def list_users(_: User = Depends(require_admin), db: DBSession = Depends(get_db)):
    return [user_dict(user) for user in db.scalars(select(User).order_by(User.display_name)).all()]


@app.post("/api/users", status_code=201)
async def create_user(body: UserCreate, admin: User = Depends(require_admin), db: DBSession = Depends(get_db)):
    username = body.username.lower()
    if db.scalar(select(User).where(User.username == username)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Username already exists")
    user = User(username=username, display_name=body.display_name, password_hash=hash_password(body.password),
                is_admin=body.is_admin, must_change_password=body.must_change_password)
    db.add(user)
    db.flush()
    audit(db, admin.id, "user.create", "user", user.id, detail={"username": username})
    db.commit()
    return user_dict(user)


@app.post("/api/auth/change-password")
async def change_password(body: PasswordChangeIn, session: Session = Depends(current_session), db: DBSession = Depends(get_db)):
    user = session.user
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Current password is incorrect")
    if body.current_password == body.new_password:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "New password must be different")
    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False
    user.password_changed_at = utcnow()
    db.execute(delete(Session).where(Session.user_id == user.id, Session.id != session.id))
    audit(db, user.id, "auth.password_change", "user", user.id)
    db.commit()
    return {"ok": True}


@app.post("/api/users/{user_id}/reset-password")
async def reset_password(user_id: int, body: PasswordResetIn, admin: User = Depends(require_admin), db: DBSession = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    user.password_hash = hash_password(body.new_password)
    user.must_change_password = True
    user.password_changed_at = utcnow()
    user.failed_login_attempts = 0
    user.locked_until = None
    db.execute(delete(Session).where(Session.user_id == user.id))
    audit(db, admin.id, "auth.password_reset", "user", user.id)
    db.commit()
    return {"ok": True}


@app.post("/api/users/{user_id}/revoke-sessions")
async def revoke_sessions(user_id: int, admin: User = Depends(require_admin), db: DBSession = Depends(get_db)):
    if not db.get(User, user_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    count = db.execute(delete(Session).where(Session.user_id == user_id)).rowcount
    audit(db, admin.id, "auth.sessions_revoke", "user", user_id, detail={"sessions": count})
    db.commit()
    return {"revoked": count}


@app.get("/api/projects")
async def list_projects(include_inactive: bool = False, user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    query = select(Project).order_by(Project.name)
    if not (user.is_admin and include_inactive):
        query = query.where(Project.active.is_(True))
    if not user.is_admin:
        query = query.join(ProjectMember).where(ProjectMember.user_id == user.id)
    projects = db.scalars(query).all()
    result = []
    for project in projects:
        member = membership(project.id, user, db)
        result.append({"id": project.id, "key": project.key, "name": project.name, "description": project.description,
                       "role": "admin" if user.is_admin else member.role.value, "active": project.active})
    return result


@app.post("/api/projects", status_code=201)
async def create_project(body: ProjectCreate, admin: User = Depends(require_admin), db: DBSession = Depends(get_db)):
    key = body.key.upper()
    if db.scalar(select(Project).where(Project.key == key)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Project key already exists")
    project = Project(key=key, name=body.name, description=body.description,
                      gitlab_url=str(body.gitlab_url).rstrip("/") if body.gitlab_url else None,
                      gitlab_project_id=body.gitlab_project_id,
                      gitlab_token_encrypted=encrypt_secret(body.gitlab_token),
                      gitlab_webhook_secret_encrypted=encrypt_secret(body.gitlab_webhook_secret))
    db.add(project)
    db.flush()
    db.add(ProjectMember(project_id=project.id, user_id=admin.id, role=ProjectRole.manager))
    audit(db, admin.id, "project.create", "project", project.id, project.id, {"key": key})
    db.commit()
    return {"id": project.id, "key": project.key, "name": project.name}


@app.patch("/api/projects/{project_id}")
async def update_project(project_id: int, body: ProjectSettingsIn, user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    require_project(project_id, user, db, {ProjectRole.manager})
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    values = body.model_dump(exclude_unset=True)
    if "gitlab_url" in values:
        values["gitlab_url"] = str(values["gitlab_url"]).rstrip("/") if values["gitlab_url"] else None
    token = values.pop("gitlab_token", None)
    webhook_secret = values.pop("gitlab_webhook_secret", None)
    for key, value in values.items():
        setattr(project, key, value)
    if token:
        project.gitlab_token_encrypted = encrypt_secret(token)
    if webhook_secret:
        project.gitlab_webhook_secret_encrypted = encrypt_secret(webhook_secret)
    audit(db, user.id, "project.update", "project", project.id, project.id)
    db.commit()
    return {"id": project.id, "name": project.name, "gitlab_configured": bool(project.gitlab_url and project.gitlab_project_id and project.gitlab_token_encrypted)}


@app.get("/api/projects/{project_id}/settings")
async def project_settings(project_id: int, user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    require_project(project_id, user, db, {ProjectRole.manager})
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return {"id": project.id, "key": project.key, "name": project.name, "description": project.description,
            "gitlab_url": project.gitlab_url, "gitlab_project_id": project.gitlab_project_id,
            "gitlab_token_configured": bool(project.gitlab_token_encrypted),
            "gitlab_webhook_configured": bool(project.gitlab_webhook_secret_encrypted),
            "webhook_url": f"{settings.public_origin.rstrip('/')}/api/webhooks/gitlab/{project.id}"}


@app.post("/api/projects/{project_id}/archive")
async def archive_project(project_id: int, body: ProjectArchiveIn, admin: User = Depends(require_admin), db: DBSession = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    project.active = not body.archived
    project.archived_at = utcnow() if body.archived else None
    audit(db, admin.id, "project.archive" if body.archived else "project.restore", "project", project.id,
          project.id, {"archived": body.archived})
    db.commit()
    return {"id": project.id, "active": project.active, "archived_at": project.archived_at}


@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: int, admin: User = Depends(require_admin), db: DBSession = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")

    run_ids = list(db.scalars(select(TestRun.id).where(TestRun.project_id == project_id)).all())
    run_case_ids = list(db.scalars(select(RunCase.id).where(RunCase.run_id.in_(run_ids))).all()) if run_ids else []
    attempt_ids = list(db.scalars(select(ExecutionAttempt.id).where(ExecutionAttempt.run_case_id.in_(run_case_ids))).all()) if run_case_ids else []
    case_ids = list(db.scalars(select(TestCase.id).where(TestCase.project_id == project_id)).all())
    evidence = list(db.scalars(select(Evidence).where(Evidence.run_case_id.in_(run_case_ids))).all()) if run_case_ids else []
    evidence_files = [settings.evidence_dir / Path(item.stored_name).name for item in evidence]
    summary = {
        "project_id": project.id, "project_key": project.key, "project_name": project.name,
        "runs": len(run_ids), "run_cases": len(run_case_ids), "test_cases": len(case_ids),
        "evidence": len(evidence),
    }

    if run_case_ids:
        if attempt_ids:
            db.execute(delete(GitLabOutbox).where(GitLabOutbox.attempt_id.in_(attempt_ids)))
        db.execute(delete(Evidence).where(Evidence.run_case_id.in_(run_case_ids)))
        db.execute(delete(RunCaseComment).where(RunCaseComment.run_case_id.in_(run_case_ids)))
        if attempt_ids:
            db.execute(delete(ExecutionAttempt).where(ExecutionAttempt.id.in_(attempt_ids)))
        db.execute(delete(RunCase).where(RunCase.id.in_(run_case_ids)))
    if run_ids:
        db.execute(delete(TestRun).where(TestRun.id.in_(run_ids)))
    if case_ids:
        db.execute(delete(CaseRequirement).where(CaseRequirement.test_case_id.in_(case_ids)))
        db.execute(delete(TestCaseVersion).where(TestCaseVersion.test_case_id.in_(case_ids)))
        db.execute(delete(TestCase).where(TestCase.id.in_(case_ids)))
    requirement_ids = list(db.scalars(select(Requirement.id).where(Requirement.project_id == project_id)).all())
    if requirement_ids:
        db.execute(delete(CaseRequirement).where(CaseRequirement.requirement_id.in_(requirement_ids)))
        db.execute(delete(Requirement).where(Requirement.id.in_(requirement_ids)))
    db.execute(delete(RunTemplate).where(RunTemplate.project_id == project_id))
    db.execute(delete(ProjectMember).where(ProjectMember.project_id == project_id))
    db.execute(delete(Notification).where(Notification.project_id == project_id))
    db.execute(delete(WebhookEvent).where(WebhookEvent.project_id == project_id))
    db.execute(delete(AuditEvent).where(AuditEvent.project_id == project_id))
    db.delete(project)
    db.flush()
    audit(db, admin.id, "project.delete", "project", project_id, detail=summary)
    db.commit()

    file_errors = 0
    for path in evidence_files:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            file_errors += 1
    return {**summary, "deleted": True, "evidence_file_errors": file_errors}


@app.get("/api/projects/{project_id}/members")
async def list_members(project_id: int, user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    require_project(project_id, user, db)
    rows = db.scalars(select(ProjectMember).where(ProjectMember.project_id == project_id)).all()
    return [{**user_dict(row.user), "role": row.role.value} for row in rows]


@app.get("/api/projects/{project_id}/available-users")
async def available_users(project_id: int, user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    require_project(project_id, user, db, {ProjectRole.manager})
    return [user_dict(item) for item in db.scalars(select(User).where(User.active.is_(True)).order_by(User.display_name)).all()]


@app.put("/api/projects/{project_id}/members")
async def add_member(project_id: int, body: MemberIn, user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    require_project(project_id, user, db, {ProjectRole.manager})
    if not db.get(User, body.user_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    row = db.scalar(select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == body.user_id))
    if row:
        row.role = body.role
    else:
        db.add(ProjectMember(project_id=project_id, user_id=body.user_id, role=body.role))
    audit(db, user.id, "member.upsert", "user", body.user_id, project_id, {"role": body.role.value})
    db.commit()
    return {"ok": True}


@app.get("/api/projects/{project_id}/cases")
async def list_cases(project_id: int, q: str = "", priority: str = "", section: str = "", tag: str = "",
                     limit: int = 500, offset: int = 0,
                     user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    require_project(project_id, user, db)
    limit = min(max(limit, 1), 1000)
    query = select(TestCase).where(TestCase.project_id == project_id, TestCase.active.is_(True))
    if q:
        pattern = f"%{q}%"
        query = query.where((TestCase.external_id.like(pattern)) | (TestCase.title.like(pattern)) | (TestCase.section.like(pattern)))
    if priority:
        query = query.where(TestCase.priority == priority)
    if section:
        query = query.where(TestCase.section == section)
    if tag:
        query = query.where(TestCase.tags_json.like(f'%"{tag.lower()}"%'))
    return [{**case_dict(case), "tags": json.loads(case.tags_json)} for case in
            db.scalars(query.order_by(TestCase.section, TestCase.external_id).offset(offset).limit(limit)).all()]


@app.get("/api/projects/{project_id}/cases/{case_id}")
async def get_case(project_id: int, case_id: int, user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    require_project(project_id, user, db)
    case = db.get(TestCase, case_id)
    if not case or case.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Test case not found")
    version = db.scalar(select(TestCaseVersion).where(TestCaseVersion.test_case_id == case.id,
                                                       TestCaseVersion.version == case.current_version))
    return {**case_dict(case), "steps": json.loads(version.steps_json), "expected": version.expected,
            "source_file": version.source_file, "tags": json.loads(case.tags_json)}


@app.get("/api/projects/{project_id}/cases/{case_id}/revisions")
async def case_revisions(project_id: int, case_id: int, user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    require_project(project_id, user, db)
    case = db.get(TestCase, case_id)
    if not case or case.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Test case not found")
    versions = db.scalars(select(TestCaseVersion).where(TestCaseVersion.test_case_id == case_id)
                          .order_by(TestCaseVersion.version.desc())).all()
    return [{"version": item.version, "title": item.title, "section": item.section,
             "priority": item.priority, "lifecycle": item.lifecycle, "steps": json.loads(item.steps_json),
             "expected": item.expected, "content_hash": item.content_hash,
             "source_file": item.source_file, "imported_at": item.imported_at} for item in versions]


@app.patch("/api/projects/{project_id}/cases/{case_id}/tags")
async def update_case_tags(project_id: int, case_id: int, body: CaseTagsIn, user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    require_project(project_id, user, db, {ProjectRole.manager})
    case = db.get(TestCase, case_id)
    if not case or case.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Test case not found")
    tags = sorted({tag.strip().lower() for tag in body.tags if tag.strip()})
    case.tags_json = json.dumps(tags)
    audit(db, user.id, "case.tags", "test_case", case.id, project_id, {"tags": tags})
    db.commit()
    return {"id": case.id, "tags": tags}


@app.get("/api/projects/{project_id}/requirements")
async def list_requirements(project_id: int, user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    require_project(project_id, user, db)
    return [requirement_dict(item) for item in db.scalars(select(Requirement).where(
        Requirement.project_id == project_id, Requirement.active.is_(True)).order_by(Requirement.key)).all()]


@app.post("/api/projects/{project_id}/requirements", status_code=201)
async def create_requirement(project_id: int, body: RequirementIn, user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    require_project(project_id, user, db, {ProjectRole.manager})
    key = body.key.upper()
    if db.scalar(select(Requirement).where(Requirement.project_id == project_id, Requirement.key == key)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Requirement key already exists")
    item = Requirement(project_id=project_id, key=key, title=body.title, description=body.description)
    db.add(item); db.flush()
    audit(db, user.id, "requirement.create", "requirement", item.id, project_id, {"key": key})
    db.commit()
    return requirement_dict(item)


@app.put("/api/projects/{project_id}/cases/{case_id}/requirements")
async def map_requirements(project_id: int, case_id: int, body: RequirementMapIn,
                           user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    require_project(project_id, user, db, {ProjectRole.manager})
    case = db.get(TestCase, case_id)
    valid = set(db.scalars(select(Requirement.id).where(
        Requirement.project_id == project_id, Requirement.id.in_(body.requirement_ids))).all())
    if not case or case.project_id != project_id or valid != set(body.requirement_ids):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid case or requirement selection")
    db.execute(delete(CaseRequirement).where(CaseRequirement.test_case_id == case_id))
    db.add_all([CaseRequirement(test_case_id=case_id, requirement_id=item_id) for item_id in valid])
    audit(db, user.id, "case.requirements", "test_case", case_id, project_id, {"requirements": sorted(valid)})
    db.commit()
    return {"test_case_id": case_id, "requirement_ids": sorted(valid)}


@app.get("/api/projects/{project_id}/cases/{case_id}/requirements")
async def case_requirements(project_id: int, case_id: int, user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    require_project(project_id, user, db)
    case = db.get(TestCase, case_id)
    if not case or case.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Test case not found")
    items = db.scalars(select(Requirement).join(CaseRequirement).where(CaseRequirement.test_case_id == case_id)).all()
    return [requirement_dict(item) for item in items]


@app.patch("/api/projects/{project_id}/cases/{case_id}")
async def edit_case(project_id: int, case_id: int, body: CaseEditIn, user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    require_project(project_id, user, db, {ProjectRole.manager})
    case = db.get(TestCase, case_id)
    if not case or case.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Test case not found")
    canonical = json.dumps({"title": body.title, "section": body.section, "priority": body.priority,
                            "lifecycle": body.lifecycle, "steps": body.steps, "expected": body.expected},
                           sort_keys=True, ensure_ascii=False)
    content_hash = hashlib.sha256(canonical.encode()).hexdigest()
    latest = db.scalar(select(TestCaseVersion).where(TestCaseVersion.test_case_id == case.id,
                                                     TestCaseVersion.version == case.current_version))
    if latest.content_hash == content_hash:
        return {"id": case.id, "version": case.current_version, "unchanged": True}
    case.title, case.section, case.priority, case.lifecycle = body.title, body.section, body.priority, body.lifecycle
    case.current_version += 1
    db.add(TestCaseVersion(test_case_id=case.id, version=case.current_version, title=body.title,
                           section=body.section, priority=body.priority, lifecycle=body.lifecycle,
                           steps_json=json.dumps(body.steps), expected=body.expected, content_hash=content_hash,
                           source_file="manual edit"))
    audit(db, user.id, "case.edit", "test_case", case.id, project_id, {"version": case.current_version})
    db.commit()
    return {"id": case.id, "version": case.current_version, "unchanged": False}


@app.post("/api/projects/{project_id}/cases/{case_id}/deactivate")
async def deactivate_case(project_id: int, case_id: int, active: bool = False,
                          user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    require_project(project_id, user, db, {ProjectRole.manager})
    case = db.get(TestCase, case_id)
    if not case or case.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Test case not found")
    case.active = active
    audit(db, user.id, "case.activate" if active else "case.deactivate", "test_case", case.id, project_id)
    db.commit()
    return {"id": case.id, "active": case.active}


@app.post("/api/projects/{project_id}/imports", status_code=201)
async def import_test_cases(project_id: int, file: UploadFile = File(...), user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    require_project(project_id, user, db, {ProjectRole.manager})
    if not file.filename or not file.filename.lower().endswith((".md", ".markdown", ".csv")):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "A Markdown or CSV file is required")
    content = await file.read(2 * 1024 * 1024 + 1)
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Import file exceeds 2 MB")
    try:
        parsed = parse_upload(file.filename or "", content)
        result = import_cases(db, project_id, parsed, Path(file.filename).name)
    except (UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    audit(db, user.id, "cases.import", "project", project_id, project_id, result)
    db.commit()
    return result


@app.post("/api/projects/{project_id}/imports/preview")
async def preview_import(project_id: int, file: UploadFile = File(...), user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    require_project(project_id, user, db, {ProjectRole.manager})
    if not file.filename or not file.filename.lower().endswith((".md", ".markdown", ".csv")):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "A Markdown or CSV file is required")
    content = await file.read(2 * 1024 * 1024 + 1)
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Import file exceeds 2 MB")
    try:
        parsed = parse_upload(file.filename or "", content)
    except (UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    existing = {case.external_id: case for case in db.scalars(select(TestCase).where(TestCase.project_id == project_id)).all()}
    rows = []
    incoming_ids = set()
    for item in parsed:
        incoming_ids.add(item.external_id)
        current = existing.get(item.external_id)
        if not current:
            action = "create"
        else:
            version = db.scalar(select(TestCaseVersion).where(TestCaseVersion.test_case_id == current.id,
                                                               TestCaseVersion.version == current.current_version))
            action = "unchanged" if version.content_hash == item.content_hash else "update"
        rows.append({"external_id": item.external_id, "title": item.title, "section": item.section,
                     "priority": item.priority, "action": action})
    omitted = [{"external_id": case.external_id, "title": case.title} for key, case in existing.items()
               if key not in incoming_ids and case.active]
    return {"total": len(rows), "create": sum(row["action"] == "create" for row in rows),
            "update": sum(row["action"] == "update" for row in rows),
            "unchanged": sum(row["action"] == "unchanged" for row in rows),
            "rows": rows, "omitted": omitted}


@app.get("/api/projects/{project_id}/runs")
async def list_runs(project_id: int, user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    require_project(project_id, user, db)
    runs = db.scalars(select(TestRun).where(TestRun.project_id == project_id).order_by(TestRun.created_at.desc())).all()
    result = []
    for run in runs:
        counts = dict(db.execute(select(RunCase.state, func.count()).where(RunCase.run_id == run.id).group_by(RunCase.state)).all())
        result.append({"id": run.id, "name": run.name, "description": run.description, "status": run.status,
                       "created_at": run.created_at, "counts": {key.value: value for key, value in counts.items()},
                       "total": sum(counts.values()), "build_version": run.build_version,
                       "environment": run.environment, "commit_sha": run.commit_sha})
    return result


@app.get("/api/projects/{project_id}/run-templates")
async def list_run_templates(project_id: int, user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    require_project(project_id, user, db)
    items = db.scalars(select(RunTemplate).where(RunTemplate.project_id == project_id).order_by(RunTemplate.name)).all()
    return [{"id": item.id, "name": item.name, "description": item.description,
             "case_ids": json.loads(item.case_ids_json), "created_at": item.created_at} for item in items]


@app.post("/api/projects/{project_id}/run-templates", status_code=201)
async def create_run_template(project_id: int, body: RunTemplateIn, user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    require_project(project_id, user, db, {ProjectRole.manager})
    valid = set(db.scalars(select(TestCase.id).where(
        TestCase.project_id == project_id, TestCase.active.is_(True), TestCase.id.in_(body.case_ids))).all())
    if valid != set(body.case_ids):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "One or more template cases are invalid")
    item = RunTemplate(project_id=project_id, name=body.name, description=body.description,
                       case_ids_json=json.dumps(sorted(valid)), created_by=user.id)
    db.add(item); db.flush()
    audit(db, user.id, "run_template.create", "run_template", item.id, project_id, {"cases": len(valid)})
    db.commit()
    return {"id": item.id, "name": item.name, "case_ids": sorted(valid)}


@app.post("/api/projects/{project_id}/runs", status_code=201)
async def create_run(project_id: int, body: RunCreate, user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    require_project(project_id, user, db, {ProjectRole.manager})
    query = select(TestCase).where(TestCase.project_id == project_id, TestCase.active.is_(True))
    if body.case_ids:
        query = query.where(TestCase.id.in_(body.case_ids))
    cases = db.scalars(query.order_by(TestCase.external_id)).all()
    if not cases:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Select or import at least one test case")
    if body.assigned_to:
        assignee = db.get(User, body.assigned_to)
        if not assignee or not membership(project_id, assignee, db):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Assignee is not a project member")
    run = TestRun(project_id=project_id, name=body.name, description=body.description, created_by=user.id,
                  build_version=body.build_version, environment=body.environment, commit_sha=body.commit_sha)
    db.add(run)
    db.flush()
    versions = db.scalars(select(TestCaseVersion).where(TestCaseVersion.test_case_id.in_([case.id for case in cases]))).all()
    version_map = {(version.test_case_id, version.version): version.id for version in versions}
    for case in cases:
        db.add(RunCase(run_id=run.id, test_case_id=case.id,
                       test_case_version_id=version_map[(case.id, case.current_version)], assigned_to=body.assigned_to))
    audit(db, user.id, "run.create", "run", run.id, project_id, {"cases": len(cases)})
    db.commit()
    return {"id": run.id, "name": run.name, "cases": len(cases)}


@app.patch("/api/projects/{project_id}/runs/{run_id}/status")
async def update_run_status(project_id: int, run_id: int, body: RunStatusIn, user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    require_project(project_id, user, db, {ProjectRole.manager})
    run = db.get(TestRun, run_id)
    if not run or run.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Run not found")
    if body.status == "open":
        run.status, run.closed_at, run.archived_at = "open", None, None
    elif body.status == "closed":
        run.status, run.closed_at, run.archived_at = "closed", utcnow(), None
    else:
        run.status, run.archived_at = "archived", utcnow()
        run.closed_at = run.closed_at or utcnow()
    audit(db, user.id, "run.status", "run", run.id, project_id, {"status": run.status})
    db.commit()
    return {"id": run.id, "status": run.status, "closed_at": run.closed_at, "archived_at": run.archived_at}


@app.get("/api/projects/{project_id}/runs/{run_id}")
async def get_run(project_id: int, run_id: int, user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    require_project(project_id, user, db)
    run = db.get(TestRun, run_id)
    if not run or run.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Run not found")
    rows = db.scalars(select(RunCase).where(RunCase.run_id == run_id).order_by(RunCase.id)).all()
    cases = []
    for row in rows:
        attempts = db.scalars(select(ExecutionAttempt).where(ExecutionAttempt.run_case_id == row.id)
                              .order_by(ExecutionAttempt.attempt_number.desc())).all()
        comments = db.scalars(select(RunCaseComment).where(RunCaseComment.run_case_id == row.id)
                              .order_by(RunCaseComment.created_at)).all()
        cases.append({"id": row.id, "test_case_id": row.test_case_id, "external_id": row.case.external_id,
                      "title": row.version.title, "section": row.version.section, "priority": row.version.priority,
                      "state": row.state.value, "notes": row.notes, "assigned_to": row.assigned_to,
                      "assignee": row.assignee.display_name if row.assignee else None,
                      "steps": json.loads(row.version.steps_json), "expected": row.version.expected,
                      "evidence": [{"id": item.id, "name": item.original_name} for item in row.evidence if item.attempt_id is None],
                      "gitlab_issue_url": row.gitlab_issue_url, "lock_version": row.lock_version,
                      "attempts": [{"id": item.id, "number": item.attempt_number, "state": item.state.value,
                                    "notes": item.notes, "executor": item.executor.display_name,
                                    "completed_at": item.completed_at, "gitlab_issue_url": item.gitlab_issue_url,
                                    "gitlab_status": item.gitlab_status} for item in attempts],
                      "comments": [{"id": item.id, "body": item.body, "author": item.user.display_name,
                                    "created_at": item.created_at} for item in comments]})
    return {"id": run.id, "name": run.name, "description": run.description, "status": run.status,
            "build_version": run.build_version, "environment": run.environment, "commit_sha": run.commit_sha,
            "cases": cases}


def get_run_case(project_id: int, run_case_id: int, db: DBSession) -> RunCase:
    row = db.get(RunCase, run_case_id)
    run = db.get(TestRun, row.run_id) if row else None
    if not row or not run or run.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Run case not found")
    return row


def require_open_run(row: RunCase, db: DBSession):
    run = db.get(TestRun, row.run_id)
    if run.status != "open":
        raise HTTPException(status.HTTP_409_CONFLICT, "This test run is not open")


@app.patch("/api/projects/{project_id}/run-cases/{run_case_id}/assignment")
async def assign_case(project_id: int, run_case_id: int, body: AssignIn, user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    require_project(project_id, user, db, {ProjectRole.manager})
    row = get_run_case(project_id, run_case_id, db)
    require_open_run(row, db)
    if body.assigned_to and not db.scalar(select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == body.assigned_to)):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Assignee is not a project member")
    row.assigned_to = body.assigned_to
    row.lock_version += 1
    audit(db, user.id, "run_case.assign", "run_case", row.id, project_id, {"assigned_to": body.assigned_to})
    db.commit()
    return {"ok": True, "lock_version": row.lock_version}


@app.patch("/api/projects/{project_id}/run-cases/bulk-assignment")
async def bulk_assign(project_id: int, body: BulkAssignIn, user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    require_project(project_id, user, db, {ProjectRole.manager})
    if body.assigned_to and not db.scalar(select(ProjectMember).where(
            ProjectMember.project_id == project_id, ProjectMember.user_id == body.assigned_to)):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Assignee is not a project member")
    rows = db.scalars(select(RunCase).join(TestRun).where(
        TestRun.project_id == project_id, TestRun.status == "open", RunCase.id.in_(body.run_case_ids))).all()
    if len(rows) != len(set(body.run_case_ids)):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "One or more cases are missing or belong to a closed run")
    for row in rows:
        row.assigned_to = body.assigned_to
        row.lock_version += 1
    if body.assigned_to:
        db.add(Notification(user_id=body.assigned_to, project_id=project_id, kind="assignment",
                            title=f"{len(rows)} test cases assigned to you", body="Open the project test runs to begin."))
    audit(db, user.id, "run_case.bulk_assign", "run_case", "bulk", project_id,
          {"count": len(rows), "assigned_to": body.assigned_to})
    db.commit()
    return {"updated": len(rows)}


@app.post("/api/projects/{project_id}/run-cases/{run_case_id}/evidence", status_code=201)
async def upload_evidence(project_id: int, run_case_id: int, file: UploadFile = File(...), user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    member = require_project(project_id, user, db, {ProjectRole.manager, ProjectRole.tester})
    row = get_run_case(project_id, run_case_id, db)
    require_open_run(row, db)
    if not user.is_admin and member.role != ProjectRole.manager and row.assigned_to not in (None, user.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This case is assigned to another tester")
    allowed = {"image/png", "image/jpeg", "image/webp", "image/gif"}
    if file.content_type not in allowed:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Evidence must be PNG, JPEG, WebP, or GIF")
    content = await file.read(settings.max_upload_bytes + 1)
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Evidence file is too large")
    signatures = {
        "image/png": lambda value: value.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/jpeg": lambda value: value.startswith(b"\xff\xd8\xff"),
        "image/gif": lambda value: value.startswith((b"GIF87a", b"GIF89a")),
        "image/webp": lambda value: value.startswith(b"RIFF") and value[8:12] == b"WEBP",
    }
    if not signatures[file.content_type](content):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "File content does not match its image type")
    extension = mimetypes.guess_extension(file.content_type) or ".img"
    stored_name = f"{secrets.token_hex(20)}{extension}"
    destination = settings.evidence_dir / stored_name
    destination.write_bytes(content)
    item = Evidence(run_case_id=row.id, original_name=Path(file.filename or "screenshot").name[:255],
                    stored_name=stored_name, mime_type=file.content_type, size_bytes=len(content), uploaded_by=user.id)
    db.add(item)
    db.flush()
    audit(db, user.id, "evidence.upload", "evidence", item.id, project_id, {"run_case_id": row.id})
    db.commit()
    return {"id": item.id, "name": item.original_name}


@app.get("/api/projects/{project_id}/evidence/{evidence_id}")
async def download_evidence(project_id: int, evidence_id: int, user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    require_project(project_id, user, db)
    item = db.get(Evidence, evidence_id)
    row = db.get(RunCase, item.run_case_id) if item else None
    run = db.get(TestRun, row.run_id) if row else None
    if not item or not run or run.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evidence not found")
    if item.purged_at:
        raise HTTPException(status.HTTP_410_GONE, "Evidence expired under the retention policy")
    return FileResponse(settings.evidence_dir / item.stored_name, media_type=item.mime_type, filename=item.original_name)


@app.delete("/api/projects/{project_id}/run-cases/{run_case_id}/evidence/{evidence_id}")
async def delete_evidence(
    project_id: int,
    run_case_id: int,
    evidence_id: int,
    user: User = Depends(current_user),
    db: DBSession = Depends(get_db),
):
    member = require_project(project_id, user, db, {ProjectRole.manager, ProjectRole.tester})
    row = get_run_case(project_id, run_case_id, db)
    if not user.is_admin and member.role != ProjectRole.manager and row.assigned_to not in (None, user.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This case is assigned to another tester")
    if item := db.get(Evidence, evidence_id):
        if item.attempt_id is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "Submitted attempt evidence is immutable")
    if row.gitlab_issue_url:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This evidence is already part of a GitLab issue. Remove or replace it in GitLab.",
        )
    if not item or item.run_case_id != row.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evidence not found")
    path = settings.evidence_dir / Path(item.stored_name).name
    original_name = item.original_name
    db.delete(item)
    audit(db, user.id, "evidence.delete", "evidence", evidence_id, project_id,
          {"run_case_id": row.id, "original_name": original_name})
    db.commit()
    file_deleted = True
    try:
        path.unlink(missing_ok=True)
    except OSError:
        file_deleted = False
    return {"deleted": True, "id": evidence_id, "name": original_name, "file_deleted": file_deleted}


@app.patch("/api/projects/{project_id}/run-cases/{run_case_id}/result")
async def record_result(project_id: int, run_case_id: int, body: ResultIn, user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    member = require_project(project_id, user, db, {ProjectRole.manager, ProjectRole.tester})
    row = get_run_case(project_id, run_case_id, db)
    require_open_run(row, db)
    if not user.is_admin and member.role != ProjectRole.manager and row.assigned_to not in (None, user.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This case is assigned to another tester")
    if row.lock_version != body.lock_version:
        raise HTTPException(status.HTTP_409_CONFLICT, "This execution changed in another session. Reload before saving.")
    terminal = {RunState.passed, RunState.failed, RunState.blocked, RunState.skipped}
    if row.state in terminal:
        raise HTTPException(status.HTTP_409_CONFLICT, "Start a retest before recording another result")
    staged_evidence = db.scalars(select(Evidence).where(Evidence.run_case_id == row.id, Evidence.attempt_id.is_(None))).all()
    if body.state == RunState.failed:
        if not body.notes.strip():
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Failure notes are required")
        if not staged_evidence:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "At least one screenshot is required")
    now = utcnow()
    row.state = body.state
    row.notes = body.notes.strip()
    row.updated_by = user.id
    if body.state == RunState.in_progress and not row.started_at:
        row.started_at = now
    outbox_item = None
    attempt = None
    if body.state in terminal:
        row.completed_at = now
        row.latest_attempt += 1
        attempt = ExecutionAttempt(run_case_id=row.id, attempt_number=row.latest_attempt, state=body.state,
                                   notes=body.notes.strip(), executed_by=user.id, started_at=row.started_at,
                                   completed_at=now, gitlab_status="pending" if body.state == RunState.failed else "not_required")
        db.add(attempt)
        db.flush()
        for evidence in staged_evidence:
            evidence.attempt_id = attempt.id
        if body.state == RunState.failed:
            outbox_item = GitLabOutbox(attempt_id=attempt.id)
            db.add(outbox_item)
    row.lock_version += 1
    audit(db, user.id, "run_case.result", "run_case", row.id, project_id,
          {"state": body.state.value, "attempt": row.latest_attempt, "lock_version": row.lock_version})
    db.commit()
    if outbox_item:
        process_gitlab_item(db, outbox_item)
        db.refresh(attempt)
    return {"id": row.id, "state": row.state.value, "gitlab_issue_url": attempt.gitlab_issue_url if attempt else None,
            "gitlab_status": attempt.gitlab_status if attempt else "not_required",
            "attempt": attempt.attempt_number if attempt else None, "lock_version": row.lock_version}


@app.post("/api/projects/{project_id}/run-cases/{run_case_id}/retest")
async def start_retest(project_id: int, run_case_id: int, body: RetestIn, user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    member = require_project(project_id, user, db, {ProjectRole.manager, ProjectRole.tester})
    row = get_run_case(project_id, run_case_id, db)
    require_open_run(row, db)
    if not user.is_admin and member.role != ProjectRole.manager and row.assigned_to not in (None, user.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This case is assigned to another tester")
    if row.lock_version != body.lock_version:
        raise HTTPException(status.HTTP_409_CONFLICT, "This execution changed in another session. Reload before retesting.")
    if row.state not in {RunState.passed, RunState.failed, RunState.blocked, RunState.skipped}:
        raise HTTPException(status.HTTP_409_CONFLICT, "Only a completed execution can be retested")
    row.state = RunState.not_started
    row.notes = ""
    row.started_at = None
    row.completed_at = None
    row.gitlab_issue_iid = None
    row.gitlab_issue_url = None
    row.lock_version += 1
    audit(db, user.id, "run_case.retest", "run_case", row.id, project_id,
          {"next_attempt": row.latest_attempt + 1, "lock_version": row.lock_version})
    db.commit()
    return {"id": row.id, "state": row.state.value, "lock_version": row.lock_version}


@app.post("/api/projects/{project_id}/run-cases/{run_case_id}/comments", status_code=201)
async def add_run_case_comment(project_id: int, run_case_id: int, body: CommentIn,
                               user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    require_project(project_id, user, db)
    row = get_run_case(project_id, run_case_id, db)
    item = RunCaseComment(run_case_id=row.id, user_id=user.id, body=body.body.strip())
    db.add(item); db.flush()
    if row.assigned_to and row.assigned_to != user.id:
        db.add(Notification(user_id=row.assigned_to, project_id=project_id, kind="comment",
                            title=f"Comment on {row.case.external_id}", body=item.body,
                            link=f"#/runs/{row.run_id}"))
    audit(db, user.id, "run_case.comment", "run_case", row.id, project_id, {"comment_id": item.id})
    db.commit()
    return {"id": item.id, "body": item.body, "author": user.display_name, "created_at": item.created_at}


@app.get("/api/projects/{project_id}/dashboard")
async def dashboard(project_id: int, run_id: int | None = None, assignee_id: int | None = None,
                    date_from: date | None = None, date_to: date | None = None,
                    user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    require_project(project_id, user, db)
    case_count = db.scalar(select(func.count()).select_from(TestCase).where(TestCase.project_id == project_id, TestCase.active.is_(True)))
    open_runs = db.scalar(select(func.count()).select_from(TestRun).where(TestRun.project_id == project_id, TestRun.status == "open"))
    filters = [TestRun.project_id == project_id]
    if run_id is not None:
        filters.append(TestRun.id == run_id)
    if assignee_id is not None:
        filters.append(RunCase.assigned_to == assignee_id)
    if date_from is not None:
        filters.append(RunCase.completed_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to is not None:
        filters.append(RunCase.completed_at < datetime.combine(date_to + timedelta(days=1), datetime.min.time()))
    state_rows = db.execute(select(RunCase.state, func.count()).join(TestRun).where(*filters).group_by(RunCase.state)).all()
    states = {state.value: count for state, count in state_rows}
    recent = []
    run_query = select(TestRun).where(TestRun.project_id == project_id)
    if run_id is not None:
        run_query = run_query.where(TestRun.id == run_id)
    runs = db.scalars(run_query.order_by(TestRun.created_at.desc()).limit(6)).all()
    for run in runs:
        count_query = select(RunCase.state, func.count()).where(RunCase.run_id == run.id)
        if assignee_id is not None:
            count_query = count_query.where(RunCase.assigned_to == assignee_id)
        if date_from is not None:
            count_query = count_query.where(RunCase.completed_at >= datetime.combine(date_from, datetime.min.time()))
        if date_to is not None:
            count_query = count_query.where(RunCase.completed_at < datetime.combine(date_to + timedelta(days=1), datetime.min.time()))
        counts = dict(db.execute(count_query.group_by(RunCase.state)).all())
        total = sum(counts.values())
        terminal = sum(counts.get(state, 0) for state in (RunState.passed, RunState.failed, RunState.blocked, RunState.skipped))
        decisive = counts.get(RunState.passed, 0) + counts.get(RunState.failed, 0)
        recent.append({
            "id": run.id, "name": run.name, "status": run.status, "created_at": run.created_at,
            "total": total, "completed": terminal, "passed": counts.get(RunState.passed, 0),
            "failed": counts.get(RunState.failed, 0),
            "completion_rate": round(terminal / total * 100) if total else 0,
            "pass_rate": round(counts.get(RunState.passed, 0) / decisive * 100) if decisive else None,
        })
    workload_rows = db.execute(
        select(User.id, User.display_name, RunCase.state, func.count())
        .join(RunCase, RunCase.assigned_to == User.id)
        .join(TestRun, TestRun.id == RunCase.run_id)
        .where(*filters)
        .group_by(User.id, User.display_name, RunCase.state)
        .order_by(User.display_name)
    ).all()
    workload = {}
    for user_id, display_name, state, count in workload_rows:
        entry = workload.setdefault(user_id, {"user_id": user_id, "display_name": display_name, "total": 0, "states": {}})
        entry["states"][state.value] = count
        entry["total"] += count
    unassigned = db.scalar(
        select(func.count()).select_from(RunCase).join(TestRun)
        .where(*filters, RunCase.assigned_to.is_(None))
    )
    decisive = states.get("passed", 0) + states.get("failed", 0)
    terminal = sum(states.get(state.value, 0) for state in (RunState.passed, RunState.failed, RunState.blocked, RunState.skipped))
    total = sum(states.values())
    return {"case_count": case_count, "open_runs": open_runs,
            "states": states, "total_executions": total, "unassigned": unassigned,
            "completion_rate": round(terminal / total * 100) if total else 0,
            "pass_rate": round(states.get("passed", 0) / decisive * 100) if decisive else None,
            "recent_runs": recent, "workload": list(workload.values())}


@app.get("/api/projects/{project_id}/reports/executions")
async def execution_report(
    project_id: int,
    run_id: int | None = None,
    state: RunState | None = None,
    assignee_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 5000,
    user: User = Depends(current_user),
    db: DBSession = Depends(get_db),
):
    require_project(project_id, user, db)
    query = (
        select(RunCase, TestRun, TestCaseVersion, User)
        .join(TestRun, TestRun.id == RunCase.run_id)
        .join(TestCaseVersion, TestCaseVersion.id == RunCase.test_case_version_id)
        .outerjoin(User, User.id == RunCase.assigned_to)
        .where(TestRun.project_id == project_id)
        .order_by(TestRun.created_at.desc(), RunCase.id)
    )
    if run_id is not None:
        query = query.where(TestRun.id == run_id)
    if state is not None:
        query = query.where(RunCase.state == state)
    if assignee_id is not None:
        query = query.where(RunCase.assigned_to == assignee_id)
    if date_from is not None:
        query = query.where(RunCase.completed_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to is not None:
        query = query.where(RunCase.completed_at < datetime.combine(date_to + timedelta(days=1), datetime.min.time()))
    query = query.limit(min(max(limit, 1), 10000))
    rows = []
    counts = {item.value: 0 for item in RunState}
    for run_case, run, version, assignee in db.execute(query).all():
        counts[run_case.state.value] += 1
        rows.append({
            "run_id": run.id, "run_name": run.name, "run_status": run.status,
            "case_id": run_case.case.external_id, "title": version.title,
            "section": version.section, "priority": version.priority,
            "assignee": assignee.display_name if assignee else None,
            "state": run_case.state.value, "notes": run_case.notes,
            "gitlab_issue_url": run_case.gitlab_issue_url,
            "started_at": run_case.started_at, "completed_at": run_case.completed_at,
        })
    terminal = sum(counts[item.value] for item in (RunState.passed, RunState.failed, RunState.blocked, RunState.skipped))
    decisive = counts[RunState.passed.value] + counts[RunState.failed.value]
    return {
        "total": len(rows), "counts": counts,
        "completion_rate": round(terminal / len(rows) * 100) if rows else 0,
        "pass_rate": round(counts[RunState.passed.value] / decisive * 100) if decisive else None,
        "rows": rows,
    }
