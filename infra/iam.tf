# Service account for the pipeline
resource "google_service_account" "pipeline" {
  account_id   = "genomicflow-pipeline"
  display_name = "GenomicFlow Pipeline Service Account"
  description  = "Used by ingestion pipeline and Dataflow jobs"
}

# Service account for Cloud Run API
resource "google_service_account" "api" {
  account_id   = "genomicflow-api"
  display_name = "GenomicFlow API Service Account"
  description  = "Used by the FastAPI Cloud Run service"
}

# Pipeline permissions
resource "google_project_iam_member" "pipeline_pubsub" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.pipeline.email}"
}

resource "google_project_iam_member" "pipeline_pubsub_sub" {
  project = var.project_id
  role    = "roles/pubsub.subscriber"
  member  = "serviceAccount:${google_service_account.pipeline.email}"
}

resource "google_project_iam_member" "pipeline_bigquery" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.pipeline.email}"
}

resource "google_project_iam_member" "pipeline_storage" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.pipeline.email}"
}

# API permissions
resource "google_project_iam_member" "api_bigquery" {
  project = var.project_id
  role    = "roles/bigquery.dataViewer"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_project_iam_member" "api_bigquery_job" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.api.email}"
}
