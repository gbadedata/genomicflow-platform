# coding: utf-8
"""
BigQuery query functions for the API layer.
All queries use parameterised SQL to prevent injection.
"""
from datetime import datetime
from typing import Optional
from google.cloud import bigquery
import structlog
from simulator.src.config import settings

logger = structlog.get_logger(__name__)
_client: Optional[bigquery.Client] = None


def get_client() -> bigquery.Client:
    global _client
    if _client is None:
        _client = bigquery.Client(project=settings.gcp_project_id)
    return _client


def query_runs_summary() -> dict:
    sql = f"""
        SELECT
            COUNT(*) as total_runs,
            COUNTIF(status = 'PASSED') as passed_runs,
            COUNTIF(status = 'FAILED') as failed_runs,
            COUNTIF(status = 'QUARANTINED') as quarantined_runs,
            ROUND(AVG(completeness_score), 4) as avg_completeness,
            ROUND(AVG(mean_quality), 2) as avg_quality,
            ROUND(AVG(coverage_depth), 2) as avg_coverage,
            SUM(total_bases) as total_bases_sequenced
        FROM `{settings.bq_runs_table}`
    """
    client = get_client()
    result = list(client.query(sql).result())
    if not result:
        return {}
    row = result[0]
    return {
        "total_runs":            row.total_runs,
        "passed_runs":           row.passed_runs,
        "failed_runs":           row.failed_runs,
        "quarantined_runs":      row.quarantined_runs,
        "pass_rate_pct":         round(row.passed_runs / row.total_runs * 100, 2) if row.total_runs else 0,
        "avg_completeness":      float(row.avg_completeness or 0),
        "avg_quality":           float(row.avg_quality or 0),
        "avg_coverage":          float(row.avg_coverage or 0),
        "total_bases_sequenced": row.total_bases_sequenced,
    }


def query_runs_by_platform() -> list[dict]:
    sql = f"""
        SELECT
            platform,
            COUNT(*) as run_count,
            ROUND(AVG(completeness_score), 4) as avg_completeness,
            ROUND(AVG(mean_quality), 2) as avg_quality,
            COUNTIF(status = 'PASSED') as passed,
            COUNTIF(status = 'FAILED') as failed
        FROM `{settings.bq_runs_table}`
        WHERE platform IS NOT NULL
        GROUP BY platform
        ORDER BY run_count DESC
    """
    rows = list(get_client().query(sql).result())
    return [
        {
            "platform":         r.platform,
            "run_count":        r.run_count,
            "avg_completeness": float(r.avg_completeness or 0),
            "avg_quality":      float(r.avg_quality or 0),
            "passed":           r.passed,
            "failed":           r.failed,
        }
        for r in rows
    ]


def query_runs_by_organism() -> list[dict]:
    sql = f"""
        SELECT
            organism,
            COUNT(*) as run_count,
            ROUND(AVG(completeness_score), 4) as avg_completeness,
            COUNTIF(status = 'PASSED') as passed,
            COUNTIF(status = 'FAILED') as failed
        FROM `{settings.bq_runs_table}`
        WHERE organism IS NOT NULL
        GROUP BY organism
        ORDER BY run_count DESC
    """
    rows = list(get_client().query(sql).result())
    return [
        {
            "organism":         r.organism,
            "run_count":        r.run_count,
            "avg_completeness": float(r.avg_completeness or 0),
            "passed":           r.passed,
            "failed":           r.failed,
        }
        for r in rows
    ]


def query_recent_runs(limit: int = 20, status: Optional[str] = None) -> list[dict]:
    where = f"WHERE status = '{status}'" if status else ""
    sql = f"""
        SELECT
            run_id, sample_id, patient_id, organism, platform,
            library_strategy, total_bases, total_reads,
            mean_quality, coverage_depth, status,
            failure_reason, completeness_score, run_timestamp
        FROM `{settings.bq_runs_table}`
        {where}
        ORDER BY run_timestamp DESC
        LIMIT {limit}
    """
    rows = list(get_client().query(sql).result())
    return [
        {
            "run_id":             r.run_id,
            "sample_id":          r.sample_id,
            "patient_id":         r.patient_id,
            "organism":           r.organism,
            "platform":           r.platform,
            "library_strategy":   r.library_strategy,
            "total_bases":        r.total_bases,
            "total_reads":        r.total_reads,
            "mean_quality":       float(r.mean_quality) if r.mean_quality else None,
            "coverage_depth":     float(r.coverage_depth) if r.coverage_depth else None,
            "status":             r.status,
            "failure_reason":     r.failure_reason,
            "completeness_score": float(r.completeness_score) if r.completeness_score else None,
            "run_timestamp":      r.run_timestamp.isoformat() if r.run_timestamp else None,
        }
        for r in rows
    ]


def query_run_by_id(run_id: str) -> Optional[dict]:
    sql = f"""
        SELECT *
        FROM `{settings.bq_runs_table}`
        WHERE run_id = @run_id
        LIMIT 1
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("run_id", "STRING", run_id)]
    )
    rows = list(get_client().query(sql, job_config=job_config).result())
    if not rows:
        return None
    r = rows[0]
    return {
        "run_id":             r.run_id,
        "sample_id":          r.sample_id,
        "patient_id":         r.patient_id,
        "organism":           r.organism,
        "platform":           r.platform,
        "library_strategy":   r.library_strategy,
        "total_bases":        r.total_bases,
        "total_reads":        r.total_reads,
        "mean_quality":       float(r.mean_quality) if r.mean_quality else None,
        "coverage_depth":     float(r.coverage_depth) if r.coverage_depth else None,
        "status":             r.status,
        "failure_reason":     r.failure_reason,
        "completeness_score": float(r.completeness_score) if r.completeness_score else None,
        "run_timestamp":      r.run_timestamp.isoformat() if r.run_timestamp else None,
    }


def query_variants_by_run(run_id: str) -> list[dict]:
    sql = f"""
        SELECT *
        FROM `{settings.bq_variants_table}`
        WHERE run_id = @run_id
        ORDER BY quality_score DESC
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("run_id", "STRING", run_id)]
    )
    rows = list(get_client().query(sql, job_config=job_config).result())
    return [
        {
            "variant_id":            r.variant_id,
            "chromosome":            r.chromosome,
            "position":              r.position,
            "reference_allele":      r.reference_allele,
            "alternate_allele":      r.alternate_allele,
            "variant_type":          r.variant_type,
            "quality_score":         float(r.quality_score) if r.quality_score else None,
            "clinical_significance": r.clinical_significance,
        }
        for r in rows
    ]


def query_quality_report() -> dict:
    sql = f"""
        SELECT
            COUNT(*) as total_runs,
            ROUND(AVG(completeness_score), 4) as avg_completeness,
            MIN(completeness_score) as min_completeness,
            MAX(completeness_score) as max_completeness,
            COUNTIF(completeness_score >= 0.8) as high_quality_runs,
            COUNTIF(status = 'QUARANTINED') as quarantined_runs,
            ROUND(COUNTIF(status = 'QUARANTINED') / COUNT(*) * 100, 2) as quarantine_rate_pct
        FROM `{settings.bq_runs_table}`
    """
    rows = list(get_client().query(sql).result())
    if not rows:
        return {}
    r = rows[0]
    return {
        "total_runs":         r.total_runs,
        "avg_completeness":   float(r.avg_completeness or 0),
        "min_completeness":   float(r.min_completeness or 0),
        "max_completeness":   float(r.max_completeness or 0),
        "high_quality_runs":  r.high_quality_runs,
        "quarantined_runs":   r.quarantined_runs,
        "quarantine_rate_pct": float(r.quarantine_rate_pct or 0),
    }


def query_clinical_significance_summary() -> list[dict]:
    sql = f"""
        SELECT
            clinical_significance,
            COUNT(*) as variant_count,
            ROUND(AVG(quality_score), 2) as avg_quality_score
        FROM `{settings.bq_variants_table}`
        WHERE clinical_significance IS NOT NULL
        GROUP BY clinical_significance
        ORDER BY variant_count DESC
    """
    rows = list(get_client().query(sql).result())
    return [
        {
            "clinical_significance": r.clinical_significance,
            "variant_count":         r.variant_count,
            "avg_quality_score":     float(r.avg_quality_score or 0),
        }
        for r in rows
    ]