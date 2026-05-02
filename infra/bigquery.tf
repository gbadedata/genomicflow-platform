# Main dataset
resource "google_bigquery_dataset" "genomicflow" {
  dataset_id  = "genomicflow"
  location    = var.region
  description = "GenomicFlow clinical sequencing data warehouse"

  labels = {
    environment = var.environment
    managed_by  = "terraform"
  }
}

# Sequencing runs fact table
resource "google_bigquery_table" "sequencing_runs" {
  dataset_id          = google_bigquery_dataset.genomicflow.dataset_id
  table_id            = "sequencing_runs"
  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "run_timestamp"
  }

  clustering = ["organism", "platform", "status"]

  schema = jsonencode([
    { name = "run_id",           type = "STRING",    mode = "REQUIRED", description = "Unique run identifier" },
    { name = "sample_id",        type = "STRING",    mode = "REQUIRED", description = "Clinical sample ID" },
    { name = "patient_id",       type = "STRING",    mode = "NULLABLE", description = "Anonymised patient ID" },
    { name = "organism",         type = "STRING",    mode = "NULLABLE", description = "Target organism" },
    { name = "platform",         type = "STRING",    mode = "NULLABLE", description = "Sequencing platform" },
    { name = "library_strategy", type = "STRING",    mode = "NULLABLE", description = "Sequencing strategy" },
    { name = "total_bases",      type = "INTEGER",   mode = "NULLABLE", description = "Total bases sequenced" },
    { name = "total_reads",      type = "INTEGER",   mode = "NULLABLE", description = "Total reads" },
    { name = "mean_quality",     type = "FLOAT",     mode = "NULLABLE", description = "Mean base quality score" },
    { name = "coverage_depth",   type = "FLOAT",     mode = "NULLABLE", description = "Mean coverage depth" },
    { name = "status",           type = "STRING",    mode = "REQUIRED", description = "PASSED | FAILED | QUARANTINED" },
    { name = "failure_reason",   type = "STRING",    mode = "NULLABLE", description = "Reason if failed" },
    { name = "run_timestamp",    type = "TIMESTAMP", mode = "REQUIRED", description = "When the run was performed" },
    { name = "ingested_at",      type = "TIMESTAMP", mode = "REQUIRED", description = "When record was ingested" },
    { name = "completeness_score", type = "FLOAT",   mode = "NULLABLE", description = "0.0 to 1.0 metadata completeness" },
  ])

  labels = {
    environment = var.environment
  }
}

# Variants table
resource "google_bigquery_table" "variants" {
  dataset_id          = google_bigquery_dataset.genomicflow.dataset_id
  table_id            = "variants"
  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "detected_at"
  }

  schema = jsonencode([
    { name = "variant_id",       type = "STRING",    mode = "REQUIRED" },
    { name = "run_id",           type = "STRING",    mode = "REQUIRED" },
    { name = "sample_id",        type = "STRING",    mode = "REQUIRED" },
    { name = "chromosome",       type = "STRING",    mode = "NULLABLE" },
    { name = "position",         type = "INTEGER",   mode = "NULLABLE" },
    { name = "reference_allele", type = "STRING",    mode = "NULLABLE" },
    { name = "alternate_allele", type = "STRING",    mode = "NULLABLE" },
    { name = "variant_type",     type = "STRING",    mode = "NULLABLE" },
    { name = "quality_score",    type = "FLOAT",     mode = "NULLABLE" },
    { name = "clinical_significance", type = "STRING", mode = "NULLABLE" },
    { name = "detected_at",      type = "TIMESTAMP", mode = "REQUIRED" },
  ])
}

# Quality metrics table
resource "google_bigquery_table" "quality_metrics" {
  dataset_id          = google_bigquery_dataset.genomicflow.dataset_id
  table_id            = "quality_metrics"
  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "measured_at"
  }

  schema = jsonencode([
    { name = "metric_id",        type = "STRING",    mode = "REQUIRED" },
    { name = "run_id",           type = "STRING",    mode = "REQUIRED" },
    { name = "metric_name",      type = "STRING",    mode = "REQUIRED" },
    { name = "metric_value",     type = "FLOAT",     mode = "REQUIRED" },
    { name = "threshold",        type = "FLOAT",     mode = "NULLABLE" },
    { name = "passed",           type = "BOOLEAN",   mode = "REQUIRED" },
    { name = "measured_at",      type = "TIMESTAMP", mode = "REQUIRED" },
  ])
}
