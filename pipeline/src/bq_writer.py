# coding: utf-8
"""
BigQuery writer for the streaming pipeline.

Every write passes BigQuery insert IDs (row_ids) built from stable keys, so a
message that is redelivered after a partial failure does not create duplicate
rows. BigQuery de-duplicates on insert ID on a best-effort basis for a short
window (about a minute), so this narrows duplicates rather than ruling them out.

Each method returns True on success. An empty list is a success: there was
nothing to write.
"""
from datetime import datetime, timezone
from typing import Any, Optional

import structlog
from google.cloud import bigquery

from simulator.src.config import settings

logger = structlog.get_logger(__name__)


class BigQueryWriter:

    def __init__(self, client: Optional[Any] = None) -> None:
        self.client         = client or bigquery.Client(project=settings.gcp_project_id)
        self.runs_table     = settings.bq_runs_table
        self.variants_table = settings.bq_variants_table
        self.quality_table  = settings.bq_quality_table
        self.rejected_table = settings.bq_rejected_table
        logger.info("bq_writer_initialised", project=settings.gcp_project_id)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _insert(self, table: str, rows: list[dict], row_ids: list[str], event: str, **ctx) -> bool:
        errors = self.client.insert_rows_json(table, rows, row_ids=row_ids)
        if errors:
            logger.error(f"{event}_failed", errors=errors, **ctx)
            return False
        logger.info(f"{event}_written", count=len(rows), **ctx)
        return True

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
        return self._insert(
            self.runs_table, [row], [str(row["run_id"])], "bq_run", run_id=row["run_id"]
        )

    def write_variants(self, variants: list[dict], run_id: str) -> bool:
        if not variants:
            return True
        rows, row_ids = [], []
        for i, v in enumerate(variants):
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
            row_ids.append(f"{run_id}:variant:{v.get('variant_id') or i}")
        return self._insert(self.variants_table, rows, row_ids, "bq_variants", run_id=run_id)

    def write_quality_metrics(self, metrics: list[dict], run_id: str) -> bool:
        if not metrics:
            return True
        rows, row_ids = [], []
        for i, m in enumerate(metrics):
            rows.append({
                "metric_id":    m.get("metric_id"),
                "run_id":       m.get("run_id") or run_id,
                "metric_name":  m.get("metric_name"),
                "metric_value": m.get("metric_value"),
                "threshold":    m.get("threshold"),
                "passed":       m.get("passed", True),
                "measured_at":  m.get("measured_at") or self._now(),
            })
            row_ids.append(f"{run_id}:metric:{m.get('metric_id') or i}")
        return self._insert(self.quality_table, rows, row_ids, "bq_metrics", run_id=run_id)

    def write_rejected(
        self,
        message_id: str,
        rejection_type: str,
        rejection_reason: str,
        payload: Optional[str],
        run_id: Optional[str] = None,
        delivery_attempt: Optional[int] = None,
    ) -> bool:
        row = {
            "message_id":       message_id,
            "run_id":           run_id,
            "rejection_type":   rejection_type,
            "rejection_reason": rejection_reason,
            "payload":          payload,
            "delivery_attempt": delivery_attempt,
            "received_at":      self._now(),
        }
        return self._insert(
            self.rejected_table, [row], [f"rejected:{message_id}"], "bq_rejected",
            message_id=message_id, run_id=run_id, rejection_type=rejection_type,
        )
