output "raw_bucket" {
  value = google_storage_bucket.raw.name
}

output "processed_bucket" {
  value = google_storage_bucket.processed.name
}

output "pubsub_topic" {
  value = google_pubsub_topic.genomic_events.name
}

output "pubsub_subscription" {
  value = google_pubsub_subscription.genomic_events_sub.name
}

output "bigquery_dataset" {
  value = google_bigquery_dataset.genomicflow.dataset_id
}

output "pipeline_service_account" {
  value = google_service_account.pipeline.email
}

output "api_service_account" {
  value = google_service_account.api.email
}

output "dead_letter_topic" {
  value = google_pubsub_topic.dead_letter.name
}

output "dead_letter_subscription" {
  value = google_pubsub_subscription.dead_letter_sub.name
}

output "rejected_records_table" {
  value = "${google_bigquery_table.rejected_records.dataset_id}.${google_bigquery_table.rejected_records.table_id}"
}
