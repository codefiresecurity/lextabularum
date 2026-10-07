from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional
from app.models import UserRole, Priority, ExecutionStatus

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserOut(BaseModel):
    id: int
    username: str
    email: str
    full_name: str
    role: UserRole

    class Config:
        from_attributes = True

class LoginRequest(BaseModel):
    username: str
    password: str

class DashboardStats(BaseModel):
    pending: int
    passed: int
    failed: int
    blocked: int
    total: int

class TestCaseBrief(BaseModel):
    id: int
    external_id: Optional[str]
    title: str
    priority: Priority
    suite_name: Optional[str] = None

class ExecutionOut(BaseModel):
    id: int
    status: ExecutionStatus
    test_case: TestCaseBrief
    created_at: datetime

    class Config:
        from_attributes = True

class ExecutionResult(BaseModel):
    status: ExecutionStatus = Field(..., description="pass | fail | blocked | skipped")
    notes: Optional[str] = None
    failure_description: Optional[str] = None
