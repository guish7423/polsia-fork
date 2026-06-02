"""Weekly reports API — list and view generated reports."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db

router = APIRouter(tags=["reports"])


@router.get("/reports")
async def list_reports(limit: int = 20, db: AsyncSession = Depends(get_db)):
    """List weekly reports, newest first."""
    rows = (
        await db.execute(
            text(
                "SELECT id, period_start, period_end, summary, created_at, recipient_count "
                "FROM weekly_reports ORDER BY created_at DESC LIMIT :lim"
            ),
            {"lim": limit},
        )
    ).fetchall()
    return {
        "data": [
            {
                "id": r[0],
                "period_start": r[1],
                "period_end": r[2],
                "summary": r[3],
                "created_at": r[4],
                "recipient_count": r[5],
            }
            for r in rows
        ]
    }


@router.get("/reports/{report_id}")
async def get_report(report_id: int, db: AsyncSession = Depends(get_db)):
    """Get full report with HTML content."""
    row = (
        await db.execute(
            text(
                "SELECT id, period_start, period_end, summary, html_content, created_at, recipient_count "
                "FROM weekly_reports WHERE id = :id"
            ),
            {"id": report_id},
        )
    ).fetchone()
    if not row:
        from fastapi import HTTPException

        raise HTTPException(404, "Report not found")
    return {
        "id": row[0],
        "period_start": row[1],
        "period_end": row[2],
        "summary": row[3],
        "html_content": row[4],
        "created_at": row[5],
        "recipient_count": row[6],
    }
