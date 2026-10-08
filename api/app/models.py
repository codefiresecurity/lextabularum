import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ProjectRole(str, enum.Enum):
    manager = "manager"
    tester = "tester"
    viewer = "viewer"


class RunState(str, enum.Enum):
    not_started = "not_started"
    in_progress = "in_progress"
    passed = "passed"
    failed = "failed"
    blocked = "blocked"
    skipped = "skipped"


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(160))
    password_hash: Mapped[str] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_token: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    user: Mapped[User] = relationship()


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    gitlab_url: Mapped[str | None] = mapped_column(String(500))
    gitlab_project_id: Mapped[str | None] = mapped_column(String(255))
    gitlab_token_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary)
    gitlab_webhook_secret_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProjectMember(Base):
    __tablename__ = "project_members"
    __table_args__ = (UniqueConstraint("project_id", "user_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    role: Mapped[ProjectRole] = mapped_column(Enum(ProjectRole))
    user: Mapped[User] = relationship()
    project: Mapped[Project] = relationship()


class TestCase(Base):
    __tablename__ = "test_cases"
    __table_args__ = (UniqueConstraint("project_id", "external_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    external_id: Mapped[str] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(300))
    section: Mapped[str] = mapped_column(String(300), default="General")
    priority: Mapped[str | None] = mapped_column(String(20))
    lifecycle: Mapped[str | None] = mapped_column(String(80))
    tags_json: Mapped[str] = mapped_column(Text, default="[]")
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    versions: Mapped[list["TestCaseVersion"]] = relationship(back_populates="case", cascade="all, delete-orphan")


class TestCaseVersion(Base):
    __tablename__ = "test_case_versions"
    __table_args__ = (UniqueConstraint("test_case_id", "version"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    test_case_id: Mapped[int] = mapped_column(ForeignKey("test_cases.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(300))
    section: Mapped[str] = mapped_column(String(300), default="General")
    priority: Mapped[str | None] = mapped_column(String(20))
    lifecycle: Mapped[str | None] = mapped_column(String(80))
    steps_json: Mapped[str] = mapped_column(Text)
    expected: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    source_file: Mapped[str | None] = mapped_column(String(500))
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    case: Mapped[TestCase] = relationship(back_populates="versions")


class TestRun(Base):
    __tablename__ = "test_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(240))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), default="open")
    build_version: Mapped[str | None] = mapped_column(String(160))
    environment: Mapped[str | None] = mapped_column(String(160))
    commit_sha: Mapped[str | None] = mapped_column(String(80))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RunCase(Base):
    __tablename__ = "run_cases"
    __table_args__ = (UniqueConstraint("run_id", "test_case_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("test_runs.id", ondelete="CASCADE"), index=True)
    test_case_id: Mapped[int] = mapped_column(ForeignKey("test_cases.id"))
    test_case_version_id: Mapped[int] = mapped_column(ForeignKey("test_case_versions.id"))
    assigned_to: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    state: Mapped[RunState] = mapped_column(Enum(RunState), default=RunState.not_started)
    notes: Mapped[str] = mapped_column(Text, default="")
    gitlab_issue_iid: Mapped[int | None] = mapped_column(Integer)
    gitlab_issue_url: Mapped[str | None] = mapped_column(String(800))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    lock_version: Mapped[int] = mapped_column(Integer, default=1)
    latest_attempt: Mapped[int] = mapped_column(Integer, default=0)
    case: Mapped[TestCase] = relationship()
    version: Mapped[TestCaseVersion] = relationship()
    assignee: Mapped[User | None] = relationship(foreign_keys=[assigned_to])
    evidence: Mapped[list["Evidence"]] = relationship(cascade="all, delete-orphan")


class Evidence(Base):
    __tablename__ = "evidence"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_case_id: Mapped[int] = mapped_column(ForeignKey("run_cases.id", ondelete="CASCADE"), index=True)
    attempt_id: Mapped[int | None] = mapped_column(ForeignKey("execution_attempts.id", ondelete="CASCADE"), index=True)
    original_name: Mapped[str] = mapped_column(String(255))
    stored_name: Mapped[str] = mapped_column(String(255), unique=True)
    mime_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"))
    action: Mapped[str] = mapped_column(String(120), index=True)
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[str] = mapped_column(String(80))
    detail_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class ExecutionAttempt(Base):
    __tablename__ = "execution_attempts"
    __table_args__ = (UniqueConstraint("run_case_id", "attempt_number"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    run_case_id: Mapped[int] = mapped_column(ForeignKey("run_cases.id", ondelete="CASCADE"), index=True)
    attempt_number: Mapped[int] = mapped_column(Integer)
    state: Mapped[RunState] = mapped_column(Enum(RunState))
    notes: Mapped[str] = mapped_column(Text, default="")
    executed_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    gitlab_issue_iid: Mapped[int | None] = mapped_column(Integer)
    gitlab_issue_url: Mapped[str | None] = mapped_column(String(800))
    gitlab_status: Mapped[str] = mapped_column(String(30), default="not_required")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    executor: Mapped[User] = relationship(foreign_keys=[executed_by])


class GitLabOutbox(Base):
    __tablename__ = "gitlab_outbox"
    id: Mapped[int] = mapped_column(primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("execution_attempts.id", ondelete="CASCADE"), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    tries: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    last_error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(60))
    title: Mapped[str] = mapped_column(String(240))
    body: Mapped[str] = mapped_column(Text, default="")
    link: Mapped[str | None] = mapped_column(String(500))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    provider_event_id: Mapped[str] = mapped_column(String(255), unique=True)
    event_type: Mapped[str] = mapped_column(String(100))
    payload_hash: Mapped[str] = mapped_column(String(64))
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Requirement(Base):
    __tablename__ = "requirements"
    __table_args__ = (UniqueConstraint("project_id", "key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class CaseRequirement(Base):
    __tablename__ = "case_requirements"
    __table_args__ = (UniqueConstraint("test_case_id", "requirement_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    test_case_id: Mapped[int] = mapped_column(ForeignKey("test_cases.id", ondelete="CASCADE"), index=True)
    requirement_id: Mapped[int] = mapped_column(ForeignKey("requirements.id", ondelete="CASCADE"), index=True)


class RunTemplate(Base):
    __tablename__ = "run_templates"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(240))
    description: Mapped[str] = mapped_column(Text, default="")
    case_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RunCaseComment(Base):
    __tablename__ = "run_case_comments"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_case_id: Mapped[int] = mapped_column(ForeignKey("run_cases.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    user: Mapped[User] = relationship()


Index("ix_run_cases_run_state", RunCase.run_id, RunCase.state)
