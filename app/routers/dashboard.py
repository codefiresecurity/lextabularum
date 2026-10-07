from fastapi import APIRouter, Depends
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import TestExecution, User
from app.schemas import DashboardStats
from app.auth import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

@router.get("/stats", response_model=DashboardStats)
async def get_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(
            func.sum(case((TestExecution.status == "pending", 1), else_=0)).label("pending"),
            func.sum(case((TestExecution.status == "pass", 1), else_=0)).label("passed"),
            func.sum(case((TestExecution.status == "fail", 1), else_=0)).label("failed"),
            func.sum(case((TestExecution.status == "blocked", 1), else_=0)).label("blocked"),
            func.count().label("total"),
        ).where(TestExecution.assigned_to == current_user.id)
    )
    row = result.one()
    return DashboardStats(
        pending=row.pending or 0,
        passed=row.passed or 0,
        failed=row.failed or 0,
        blocked=row.blocked or 0,
        total=row.total or 0,
    )
