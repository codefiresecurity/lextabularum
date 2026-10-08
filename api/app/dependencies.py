from datetime import datetime, timezone

from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from .db import get_db
from .models import ProjectMember, ProjectRole, Session, User
from .security import session_hash


async def current_session(
    request: Request,
    db: DBSession = Depends(get_db),
    lt_session: str | None = Cookie(default=None),
) -> Session:
    if not lt_session:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    session = db.scalar(select(Session).where(Session.token_hash == session_hash(lt_session)))
    expires = session.expires_at if session else None
    if expires and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if not session or expires <= datetime.now(timezone.utc) or not session.user.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired")
    if session.user.must_change_password and request.url.path not in {
        "/api/auth/me", "/api/auth/change-password", "/api/auth/logout",
    }:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Password change required")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        csrf = request.headers.get("X-CSRF-Token")
        if not csrf or not secrets_equal(csrf, session.csrf_token):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid CSRF token")
    return session


def secrets_equal(a: str, b: str) -> bool:
    import hmac

    return hmac.compare_digest(a.encode(), b.encode())


async def current_user(session: Session = Depends(current_session)) -> User:
    return session.user


async def require_admin(user: User = Depends(current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator access required")
    return user


def membership(project_id: int, user: User, db: DBSession) -> ProjectMember | None:
    return db.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user.id,
        )
    )


def require_project(project_id: int, user: User, db: DBSession, roles: set[ProjectRole] | None = None):
    member = membership(project_id, user, db)
    if not user.is_admin and (not member or (roles and member.role not in roles)):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Project access denied")
    return member
