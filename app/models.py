from datetime import datetime
from sqlalchemy import String, Text, Enum, ForeignKey, DateTime, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
import enum

class UserRole(str, enum.Enum):
    tester = "tester"
    lead = "lead"
    admin = "admin"

class Priority(str, enum.Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"

class ExecutionStatus(str, enum.Enum):
    pending = "pending"
    pass_ = "pass"          # "pass" is reserved
    fail = "fail"
    blocked = "blocked"
    skipped = "skipped"

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    full_name: Mapped[str] = mapped_column(String(150))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.tester)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class TestSuite(Base):
    __tablename__ = "test_suites"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    description: Mapped[str | None] = mapped_column(Text)

class TestCase(Base):
    __tablename__ = "test_cases"
    id: Mapped[int] = mapped_column(primary_key=True)
    suite_id: Mapped[int | None] = mapped_column(ForeignKey("test_suites.id"))
    external_id: Mapped[str | None] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    preconditions: Mapped[str | None] = mapped_column(Text)
    steps: Mapped[str] = mapped_column(Text)
    expected_result: Mapped[str] = mapped_column(Text)
    priority: Mapped[Priority] = mapped_column(Enum(Priority), default=Priority.medium)
    tags: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    suite = relationship("TestSuite")

class TestExecution(Base):
    __tablename__ = "test_executions"
    id: Mapped[int] = mapped_column(primary_key=True)
    test_case_id: Mapped[int] = mapped_column(ForeignKey("test_cases.id"))
    assigned_to: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    executed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    status: Mapped[ExecutionStatus] = mapped_column(Enum(ExecutionStatus), default=ExecutionStatus.pending)
    notes: Mapped[str | None] = mapped_column(Text)
    failure_description: Mapped[str | None] = mapped_column(Text)
    screenshot_path: Mapped[str | None] = mapped_column(String(500))
    executed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    test_case = relationship("TestCase")
    assignee = relationship("User", foreign_keys=[assigned_to])
    executor = relationship("User", foreign_keys=[executed_by])
