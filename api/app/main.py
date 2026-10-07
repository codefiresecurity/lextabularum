import json
import mimetypes
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DBSession

from .config import settings
from .db import Base, engine, get_db
from .dependencies import current_session, current_user, membership, require_admin, require_project
from .gitlab import GitLabClient
from .importer import import_cases, parse_markdown
from .models import (
    AuditEvent, Evidence, Project, ProjectMember, ProjectRole, RunCase, RunState, Session,
    TestCase, TestCaseVersion, TestRun, User, utcnow,
)
from .schemas import AssignIn, LoginIn, MemberIn, ProjectCreate, ProjectSettingsIn, ResultIn, RunCreate, UserCreate
from .security import decrypt_secret, encrypt_secret, hash_password, new_session, verify_password


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.evidence_dir.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="Lex Tabularum", version="0.1.0", docs_url="/api/docs",
              openapi_url="/api/openapi.json", lifespan=lifespan)


def audit(db: DBSession, user_id: int | None, action: str, entity_type: str, entity_id, project_id=None, detail=None):
    db.add(AuditEvent(user_id=user_id, project_id=project_id, action=action, entity_type=entity_type,
                      entity_id=str(entity_id), detail_json=json.dumps(detail or {})))


def user_dict(user: User):
    return {"id": user.id, "username": user.username, "display_name": user.display_name,
            "is_admin": user.is_admin, "active": user.active}


def case_dict(case: TestCase):
    return {"id": case.id, "external_id": case.external_id, "title": case.title, "section": case.section,
            "priority": case.priority, "lifecycle": case.lifecycle, "version": case.current_version,
            "active": case.active}


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "lex-tabularum"}


@app.post("/api/auth/login")
async def login(body: LoginIn, response: Response, db: DBSession = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == body.username))
    if not user or not user.active or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid username or password")
    raw, token_hash, csrf, expires = new_session()
    db.add(Session(user_id=user.id, token_hash=token_hash, csrf_token=csrf, expires_at=expires))
    audit(db, user.id, "auth.login", "user", user.id)
    db.commit()
    response.set_cookie("lt_session", raw, httponly=True, secure=settings.session_cookie_secure,
                        samesite="strict", max_age=settings.session_hours * 3600, path="/")
    return {"user": user_dict(user), "csrf_token": csrf}


@app.post("/api/auth/logout", status_code=204)
async def logout(response: Response, session: Session = Depends(current_session), db: DBSession = Depends(get_db)):
    audit(db, session.user_id, "auth.logout", "user", session.user_id)
    db.delete(session)
    db.commit()
    response.delete_cookie("lt_session", path="/")


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
    user = User(username=username, display_name=body.display_name, password_hash=hash_password(body.password), is_admin=body.is_admin)
    db.add(user)
    db.flush()
    audit(db, admin.id, "user.create", "user", user.id, detail={"username": username})
    db.commit()
    return user_dict(user)


@app.get("/api/projects")
async def list_projects(user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    query = select(Project).where(Project.active.is_(True)).order_by(Project.name)
    if not user.is_admin:
        query = query.join(ProjectMember).where(ProjectMember.user_id == user.id)
    projects = db.scalars(query).all()
    result = []
    for project in projects:
        member = membership(project.id, user, db)
        result.append({"id": project.id, "key": project.key, "name": project.name, "description": project.description,
                       "role": "admin" if user.is_admin else member.role.value})
    return result


@app.post("/api/projects", status_code=201)
async def create_project(body: ProjectCreate, admin: User = Depends(require_admin), db: DBSession = Depends(get_db)):
    key = body.key.upper()
    if db.scalar(select(Project).where(Project.key == key)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Project key already exists")
    project = Project(key=key, name=body.name, description=body.description,
                      gitlab_url=str(body.gitlab_url).rstrip("/") if body.gitlab_url else None,
                      gitlab_project_id=body.gitlab_project_id,
                      gitlab_token_encrypted=encrypt_secret(body.gitlab_token))
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
    for key, value in values.items():
        setattr(project, key, value)
    if token:
        project.gitlab_token_encrypted = encrypt_secret(token)
    audit(db, user.id, "project.update", "project", project.id, project.id)
    db.commit()
    return {"id": project.id, "name": project.name, "gitlab_configured": bool(project.gitlab_url and project.gitlab_project_id and project.gitlab_token_encrypted)}


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
async def list_cases(project_id: int, q: str = "", user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    require_project(project_id, user, db)
    query = select(TestCase).where(TestCase.project_id == project_id, TestCase.active.is_(True))
    if q:
        pattern = f"%{q}%"
        query = query.where((TestCase.external_id.like(pattern)) | (TestCase.title.like(pattern)) | (TestCase.section.like(pattern)))
    return [case_dict(case) for case in db.scalars(query.order_by(TestCase.section, TestCase.external_id)).all()]


@app.get("/api/projects/{project_id}/cases/{case_id}")
async def get_case(project_id: int, case_id: int, user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    require_project(project_id, user, db)
    case = db.get(TestCase, case_id)
    if not case or case.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Test case not found")
    version = db.scalar(select(TestCaseVersion).where(TestCaseVersion.test_case_id == case.id,
                                                       TestCaseVersion.version == case.current_version))
    return {**case_dict(case), "steps": json.loads(version.steps_json), "expected": version.expected,
            "source_file": version.source_file}


@app.post("/api/projects/{project_id}/imports", status_code=201)
async def import_markdown(project_id: int, file: UploadFile = File(...), user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    require_project(project_id, user, db, {ProjectRole.manager})
    if not file.filename or not file.filename.lower().endswith((".md", ".markdown")):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "A Markdown file is required")
    content = await file.read(2 * 1024 * 1024 + 1)
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Markdown file exceeds 2 MB")
    try:
        parsed = parse_markdown(content.decode("utf-8"))
        result = import_cases(db, project_id, parsed, Path(file.filename).name)
    except (UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    audit(db, user.id, "cases.import", "project", project_id, project_id, result)
    db.commit()
    return result


@app.get("/api/projects/{project_id}/runs")
async def list_runs(project_id: int, user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    require_project(project_id, user, db)
    runs = db.scalars(select(TestRun).where(TestRun.project_id == project_id).order_by(TestRun.created_at.desc())).all()
    result = []
    for run in runs:
        counts = dict(db.execute(select(RunCase.state, func.count()).where(RunCase.run_id == run.id).group_by(RunCase.state)).all())
        result.append({"id": run.id, "name": run.name, "description": run.description, "status": run.status,
                       "created_at": run.created_at, "counts": {key.value: value for key, value in counts.items()},
                       "total": sum(counts.values())})
    return result


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
    run = TestRun(project_id=project_id, name=body.name, description=body.description, created_by=user.id)
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


@app.get("/api/projects/{project_id}/runs/{run_id}")
async def get_run(project_id: int, run_id: int, user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    require_project(project_id, user, db)
    run = db.get(TestRun, run_id)
    if not run or run.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Run not found")
    rows = db.scalars(select(RunCase).where(RunCase.run_id == run_id).order_by(RunCase.id)).all()
    cases = []
    for row in rows:
        cases.append({"id": row.id, "test_case_id": row.test_case_id, "external_id": row.case.external_id,
                      "title": row.version.title, "section": row.version.section, "priority": row.version.priority,
                      "state": row.state.value, "notes": row.notes, "assigned_to": row.assigned_to,
                      "assignee": row.assignee.display_name if row.assignee else None,
                      "steps": json.loads(row.version.steps_json), "expected": row.version.expected,
                      "evidence": [{"id": item.id, "name": item.original_name} for item in row.evidence],
                      "gitlab_issue_url": row.gitlab_issue_url})
    return {"id": run.id, "name": run.name, "description": run.description, "status": run.status, "cases": cases}


def get_run_case(project_id: int, run_case_id: int, db: DBSession) -> RunCase:
    row = db.get(RunCase, run_case_id)
    run = db.get(TestRun, row.run_id) if row else None
    if not row or not run or run.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Run case not found")
    return row


@app.patch("/api/projects/{project_id}/run-cases/{run_case_id}/assignment")
async def assign_case(project_id: int, run_case_id: int, body: AssignIn, user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    require_project(project_id, user, db, {ProjectRole.manager})
    row = get_run_case(project_id, run_case_id, db)
    if body.assigned_to and not db.scalar(select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == body.assigned_to)):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Assignee is not a project member")
    row.assigned_to = body.assigned_to
    audit(db, user.id, "run_case.assign", "run_case", row.id, project_id, {"assigned_to": body.assigned_to})
    db.commit()
    return {"ok": True}


@app.post("/api/projects/{project_id}/run-cases/{run_case_id}/evidence", status_code=201)
async def upload_evidence(project_id: int, run_case_id: int, file: UploadFile = File(...), user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    member = require_project(project_id, user, db, {ProjectRole.manager, ProjectRole.tester})
    row = get_run_case(project_id, run_case_id, db)
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
    return FileResponse(settings.evidence_dir / item.stored_name, media_type=item.mime_type, filename=item.original_name)


@app.patch("/api/projects/{project_id}/run-cases/{run_case_id}/result")
async def record_result(project_id: int, run_case_id: int, body: ResultIn, user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    member = require_project(project_id, user, db, {ProjectRole.manager, ProjectRole.tester})
    row = get_run_case(project_id, run_case_id, db)
    if not user.is_admin and member.role != ProjectRole.manager and row.assigned_to not in (None, user.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This case is assigned to another tester")
    if body.state == RunState.failed:
        if not body.notes.strip():
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Failure notes are required")
        if not row.evidence:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "At least one screenshot is required")
        if not row.gitlab_issue_url:
            project = db.get(Project, project_id)
            token = decrypt_secret(project.gitlab_token_encrypted)
            if not project.gitlab_url or not project.gitlab_project_id or not token:
                raise HTTPException(status.HTTP_409_CONFLICT, "Configure GitLab before recording failures")
            client = GitLabClient(project.gitlab_url, project.gitlab_project_id, token,
                                  verify_ssl=settings.gitlab_verify_ssl)
            links = []
            try:
                for item in row.evidence:
                    upload = client.upload(settings.evidence_dir / item.stored_name, item.mime_type)
                    links.append(upload.get("markdown") or f"[{item.original_name}]({upload.get('url', '')})")
                description = (f"## Automated test execution failure\n\n"
                               f"**Test case:** {row.case.external_id} — {row.version.title}\n"
                               f"**Run:** {db.get(TestRun, row.run_id).name}\n"
                               f"**Reported by:** {user.display_name}\n\n"
                               f"### What went wrong\n{body.notes.strip()}\n\n"
                               f"### Expected\n{row.version.expected}\n\n"
                               f"### Evidence\n" + "\n\n".join(links))
                issue = client.create_issue(f"Test failure: {row.case.external_id} — {row.version.title}", description)
            except (httpx.HTTPError, OSError) as exc:
                raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"GitLab issue creation failed: {exc}") from exc
            row.gitlab_issue_iid = issue["iid"]
            row.gitlab_issue_url = issue["web_url"]
    now = utcnow()
    row.state = body.state
    row.notes = body.notes.strip()
    row.updated_by = user.id
    if body.state == RunState.in_progress and not row.started_at:
        row.started_at = now
    if body.state in {RunState.passed, RunState.failed, RunState.blocked, RunState.skipped}:
        row.completed_at = now
    audit(db, user.id, "run_case.result", "run_case", row.id, project_id,
          {"state": body.state.value, "gitlab_issue": row.gitlab_issue_url})
    db.commit()
    return {"id": row.id, "state": row.state.value, "gitlab_issue_url": row.gitlab_issue_url}


@app.get("/api/projects/{project_id}/dashboard")
async def dashboard(project_id: int, user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    require_project(project_id, user, db)
    case_count = db.scalar(select(func.count()).select_from(TestCase).where(TestCase.project_id == project_id, TestCase.active.is_(True)))
    open_runs = db.scalar(select(func.count()).select_from(TestRun).where(TestRun.project_id == project_id, TestRun.status == "open"))
    state_rows = db.execute(select(RunCase.state, func.count()).join(TestRun).where(TestRun.project_id == project_id).group_by(RunCase.state)).all()
    states = {state.value: count for state, count in state_rows}
    recent = []
    runs = db.scalars(select(TestRun).where(TestRun.project_id == project_id).order_by(TestRun.created_at.desc()).limit(6)).all()
    for run in runs:
        counts = dict(db.execute(select(RunCase.state, func.count()).where(RunCase.run_id == run.id).group_by(RunCase.state)).all())
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
        .where(TestRun.project_id == project_id)
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
        .where(TestRun.project_id == project_id, RunCase.assigned_to.is_(None))
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
