# Main topic for genomic events
resource "google_pubsub_topic" "genomic_events" {
  name = "genomic-events"

  message_retention_duration = "86400s"

  labels = {
    environment = var.environment
  }
}

# Subscription for pipeline to consume events.
# A message the pipeline cannot process is nacked and redelivered with back-off.
# After max_delivery_attempts it moves to the dead-letter topic instead of
# being retried forever or lost.
resource "google_pubsub_subscription" "genomic_events_sub" {
  name  = "genomic-events-sub"
  topic = google_pubsub_topic.genomic_events.name

  ack_deadline_seconds = 60

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "300s"
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dead_letter.id
    max_delivery_attempts = var.max_delivery_attempts
  }

  # Never expire. Pub/Sub deletes an idle subscription after its TTL, and the
  # original 7-day TTL deleted this one: messages published while it was gone
  # were lost, because a topic only delivers to subscriptions that exist.
  expiration_policy {
    ttl = ""
  }

  labels = {
    environment = var.environment
  }
}

# Dead letter topic for messages that failed every delivery attempt
resource "google_pubsub_topic" "dead_letter" {
  name = "genomic-events-dead-letter"

  labels = {
    environment = var.environment
  }
}

# Holds dead-lettered messages for inspection and replay.
# A topic with no subscription would discard them.
resource "google_pubsub_subscription" "dead_letter_sub" {
  name  = "genomic-events-dead-letter-sub"
  topic = google_pubsub_topic.dead_letter.name

  message_retention_duration = "604800s"
  ack_deadline_seconds       = 60

  expiration_policy {
    ttl = "" # never expires
  }

  labels = {
    environment = var.environment
  }
}

# Pub/Sub forwards dead-lettered messages as its own service agent, which needs
# publish rights on the dead-letter topic and subscribe rights on the source
# subscription. Without these grants the dead-letter policy silently does nothing.
data "google_project" "current" {
  project_id = var.project_id
}

locals {
  pubsub_service_agent = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

resource "google_pubsub_topic_iam_member" "dead_letter_publisher" {
  topic  = google_pubsub_topic.dead_letter.name
  role   = "roles/pubsub.publisher"
  member = local.pubsub_service_agent
}

resource "google_pubsub_subscription_iam_member" "source_subscriber" {
  subscription = google_pubsub_subscription.genomic_events_sub.name
  role         = "roles/pubsub.subscriber"
  member       = local.pubsub_service_agent
}
