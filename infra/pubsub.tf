# Main topic for genomic events
resource "google_pubsub_topic" "genomic_events" {
  name = "genomic-events"

  message_retention_duration = "86400s"

  labels = {
    environment = var.environment
  }
}

# Subscription for pipeline to consume events
resource "google_pubsub_subscription" "genomic_events_sub" {
  name  = "genomic-events-sub"
  topic = google_pubsub_topic.genomic_events.name

  ack_deadline_seconds = 60

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "300s"
  }

  expiration_policy {
    ttl = "604800s"
  }

  labels = {
    environment = var.environment
  }
}

# Dead letter topic for failed messages
resource "google_pubsub_topic" "dead_letter" {
  name = "genomic-events-dead-letter"

  labels = {
    environment = var.environment
  }
}
