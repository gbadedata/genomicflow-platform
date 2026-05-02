# coding: utf-8
"""
Centralised configuration using Pydantic Settings.
All values loaded from environment variables or .env file.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # GCP
    gcp_project_id: str = "genomicflow-platform"
    gcp_region: str = "europe-west2"
    gcp_zone: str = "europe-west2-a"

    # Pub/Sub
    pubsub_topic_id: str = "genomic-events"
    pubsub_subscription_id: str = "genomic-events-sub"

    # BigQuery
    bq_dataset: str = "genomicflow"
    bq_table_runs: str = "sequencing_runs"
    bq_table_variants: str = "variants"
    bq_table_quality: str = "quality_metrics"

    # GCS
    gcs_raw_bucket: str = "genomicflow-raw"
    gcs_processed_bucket: str = "genomicflow-processed"

    # App
    log_level: str = "INFO"
    environment: str = "development"
    app_version: str = "0.1.0"

    @property
    def pubsub_topic_path(self) -> str:
        return f"projects/{self.gcp_project_id}/topics/{self.pubsub_topic_id}"

    @property
    def pubsub_subscription_path(self) -> str:
        return (
            f"projects/{self.gcp_project_id}"
            f"/subscriptions/{self.pubsub_subscription_id}"
        )

    @property
    def bq_runs_table(self) -> str:
        return f"{self.gcp_project_id}.{self.bq_dataset}.{self.bq_table_runs}"

    @property
    def bq_variants_table(self) -> str:
        return f"{self.gcp_project_id}.{self.bq_dataset}.{self.bq_table_variants}"

    @property
    def bq_quality_table(self) -> str:
        return f"{self.gcp_project_id}.{self.bq_dataset}.{self.bq_table_quality}"


settings = Settings()