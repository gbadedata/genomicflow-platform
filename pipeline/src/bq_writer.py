# coding: utf-8
from datetime import datetime, timezone
from typing import Any
from google.cloud import bigquery
import structlog
from simulator.src.config import settings

logger = structlog.get_logger(__name__)


class BigQueryWriter:

    def __init__(self) -> None:
        self.client         = bigquery.Client(project=settings.gcp_project_id)
        self.runs_table     = settings.bq_runs_table
        self.variants_table = settings.bq_variants_table
        self.quality_table  = settings.bq_quality_table
        logger.info("bq_writer_initialised", project=settings.gcp_project_id)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def write_run(self, record: dict, completeness_score: float) -> bool:
        row = {
            "run_id":             record.get("run_id"),
            "sample_id":          record.get("sample_id"),
            "patient_id":         record.get("patient_id"),
            "organism":           record.get("organism"),
            "platform":           record.get("platform"),
            "library_strategy":   record.get("library_strategy"),
            "total_bases":        record.get("total_bases"),
            "total_reads":        record.get("total_reads"),
            "mean_quality":       record.get("mean_quality"),
            "coverage_depth":     record.get("coverage_depth"),
            "status":             record.get("status", "PASSED"),
            "failure_reason":     record.get("failure_reason"),
            "run_timestamp":      record.get("run_timestamp") or self._now(),
            "ingested_at":        self._now(),
            "completeness_score": completeness_score,
        }
        errors = self.client.insert_rows_json(self.runs_table, [row])
        if errors:
            logger.error("bq_write_run_failed", run_id=row["run_id"], errors=errors)
            return False
        logger.info("bq_run_written", run_id=row["run_id"], status=row["status"])
        return True

    def write_variants(self, variants: list[dict], run_id: str) -> int:
        if not variants:
            return 0
        rows = []
        for v in variants:
            rows.append({
                "variant_id":            v.get("variant_id"),
                "run_id":                run_id,
                "sample_id":             v.get("sample_id"),
                "chromosome":            v.get("chromosome"),
                "position":              v.get("position"),
                "reference_allele":      v.get("reference_allele"),
                "alternate_allele":      v.get("alternate_allele"),
                "variant_type":          v.get("variant_type"),
                "quality_score":         v.get("quality_score"),
                "clinical_significance": v.get("clinical_significance"),
                "detected_at":           v.get("detected_at") or self._now(),
            })
        errors = self.client.insert_rows_json(self.variants_table, rows)
        if errors:
            logger.error("bq_write_variants_failed", run_id=run_id, errors=errors)
            return 0
        logger.info("bq_variants_written", run_id=run_id, count=len(rows))
        return len(rows)

    def write_quality_metrics(self, metrics: list[dict], run_id: str) -> int:
        if not metrics:
            return 0
        rows = []
        for m in metrics:
            rows.append({
                "metric_id":    m.get("metric_id"),
                "run_id":       m.get("run_id"),
                "metric_name":  m.get("metric_name"),
                "metric_value": m.get("metric_value"),
                "threshold":    m.get("threshold"),
                "passed":       m.get("passed", True),
                "measured_at":  m.get("measured_at") or self._now(),
            })
        errors = self.client.insert_rows_json(self.quality_table, rows)
        if errors:
            logger.error("bq_write_metrics_failed", run_id=run_id, errors=errors)
            return 0
        logger.info("bq_metrics_written", run_id=run_id, count=len(rows))
        return len(rows)