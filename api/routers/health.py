# coding: utf-8
from fastapi import APIRouter
from google.cloud import bigquery
from simulator.src.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    db_connected = False
    total_runs   = 0
    try:
        client = bigquery.Client(project=settings.gcp_project_id)
        sql    = f"SELECT COUNT(*) as cnt FROM `{settings.bq_runs_table}`"
        rows   = list(client.query(sql).result())
        total_runs   = rows[0].cnt if rows else 0
        db_connected = True
    except Exception as exc:
        pass
    return {
        "status":       "healthy" if db_connected else "degraded",
        "version":      settings.app_version,
        "environment":  settings.environment,
        "bq_connected": db_connected,
        "total_runs":   total_runs,
        "project":      settings.gcp_project_id,
    }