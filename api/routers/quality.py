# coding: utf-8
from fastapi import APIRouter
from api.models.bq_queries import query_quality_report, query_clinical_significance_summary

router = APIRouter(prefix="/quality", tags=["quality"])


@router.get("/report")
async def quality_report():
    return query_quality_report()


@router.get("/variants/significance")
async def variants_by_significance():
    return query_clinical_significance_summary()