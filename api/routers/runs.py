# coding: utf-8
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from api.models.bq_queries import (
    query_recent_runs, query_run_by_id,
    query_runs_summary, query_variants_by_run,
)

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("/summary")
async def runs_summary():
    return query_runs_summary()


@router.get("")
async def list_runs(
    limit:  int           = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="Filter by status: PASSED, FAILED, QUARANTINED"),
):
    if status and status not in {"PASSED", "FAILED", "QUARANTINED"}:
        raise HTTPException(status_code=400, detail="Invalid status value")
    runs = query_recent_runs(limit=limit, status=status)
    return {"total": len(runs), "items": runs}


@router.get("/{run_id}")
async def get_run(run_id: str):
    run = query_run_by_id(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    variants = query_variants_by_run(run_id)
    run["variants"] = variants
    return run