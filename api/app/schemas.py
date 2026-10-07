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


class ProjectCreate(BaseModel):
    key: str = Field(min_length=2, max_length=40, pattern=r"^[A-Za-z][A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=160)
    description: str = ""
    gitlab_url: HttpUrl | None = None
    gitlab_project_id: str | None = None
    gitlab_token: str | None = None


class MemberIn(BaseModel):
    user_id: int
    role: ProjectRole


class RunCreate(BaseModel):
    name: str = Field(min_length=1, max_length=240)
    description: str = ""
    case_ids: list[int] = Field(default_factory=list)
    assigned_to: int | None = None


class AssignIn(BaseModel):
    assigned_to: int | None


class ResultIn(BaseModel):
    state: RunState
    notes: str = Field(default="", max_length=20000)


class ProjectSettingsIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = None
    gitlab_url: HttpUrl | None = None
    gitlab_project_id: str | None = None
    gitlab_token: str | None = None
