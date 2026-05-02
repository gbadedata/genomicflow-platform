# coding: utf-8
from fastapi import APIRouter
from api.models.bq_queries import query_runs_by_organism

router = APIRouter(prefix="/organisms", tags=["organisms"])


@router.get("")
async def list_organisms():
    return query_runs_by_organism()