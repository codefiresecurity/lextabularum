from typing import Literal

from pydantic import BaseModel, Field, HttpUrl

from .models import ProjectRole, RunState


class LoginIn(BaseModel):
    username: str
    password: str


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=100, pattern=r"^[a-zA-Z0-9._-]+$")
    display_name: str = Field(min_length=1, max_length=160)
    password: str = Field(min_length=10, max_length=200)
    is_admin: bool = False
    must_change_password: bool = True


class PasswordChangeIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=12, max_length=200)


class PasswordResetIn(BaseModel):
    new_password: str = Field(min_length=12, max_length=200)


class ProjectCreate(BaseModel):
    key: str = Field(min_length=2, max_length=40, pattern=r"^[A-Za-z][A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=160)
    description: str = ""
    gitlab_url: HttpUrl | None = None
    gitlab_project_id: str | None = None
    gitlab_token: str | None = None
    gitlab_webhook_secret: str | None = None


class MemberIn(BaseModel):
    user_id: int
    role: ProjectRole


class RunCreate(BaseModel):
    name: str = Field(min_length=1, max_length=240)
    description: str = ""
    case_ids: list[int] = Field(default_factory=list)
    assigned_to: int | None = None
    build_version: str | None = Field(default=None, max_length=160)
    environment: str | None = Field(default=None, max_length=160)
    commit_sha: str | None = Field(default=None, max_length=80)


class AssignIn(BaseModel):
    assigned_to: int | None


class ResultIn(BaseModel):
    state: RunState
    notes: str = Field(default="", max_length=20000)
    lock_version: int = Field(ge=1)


class RetestIn(BaseModel):
    lock_version: int = Field(ge=1)


class BulkAssignIn(BaseModel):
    run_case_ids: list[int] = Field(min_length=1, max_length=5000)
    assigned_to: int | None


class RunStatusIn(BaseModel):
    status: Literal["open", "closed", "archived"]


class CaseTagsIn(BaseModel):
    tags: list[str] = Field(max_length=50)


class CaseEditIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    section: str = Field(min_length=1, max_length=300)
    priority: str | None = Field(default=None, max_length=20)
    lifecycle: str | None = Field(default=None, max_length=80)
    steps: list[str] = Field(min_length=1, max_length=500)
    expected: str = Field(min_length=1, max_length=20000)


class ProjectArchiveIn(BaseModel):
    archived: bool


class RequirementIn(BaseModel):
    key: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=20000)


class RequirementMapIn(BaseModel):
    requirement_ids: list[int] = Field(max_length=500)


class RunTemplateIn(BaseModel):
    name: str = Field(min_length=1, max_length=240)
    description: str = ""
    case_ids: list[int] = Field(min_length=1, max_length=5000)


class CommentIn(BaseModel):
    body: str = Field(min_length=1, max_length=10000)


class ProjectSettingsIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = None
    gitlab_url: HttpUrl | None = None
    gitlab_project_id: str | None = None
    gitlab_token: str | None = None
    gitlab_webhook_secret: str | None = None
