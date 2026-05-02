# coding: utf-8
from fastapi import APIRouter
from api.models.bq_queries import query_runs_by_platform

router = APIRouter(prefix="/platforms", tags=["platforms"])


@router.get("/summary")
async def platforms_summary():
    return query_runs_by_platform()