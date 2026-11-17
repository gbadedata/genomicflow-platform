# Email channel for alerts. Created only when alert_email is set, so the
# alerts below always have somewhere to go once an address is supplied.
resource "google_monitoring_notification_channel" "email" {
  count        = var.alert_email == "" ? 0 : 1
  display_name = "GenomicFlow data team"
  type         = "email"

  labels = {
    email_address = var.alert_email
  }
}

# Messages waiting on the main subscription: the pipeline is down or falling behind.
resource "google_monitoring_alert_policy" "backlog" {
  display_name = "GenomicFlow unprocessed message backlog"
  combiner     = "OR"

  conditions {
    display_name = "More than ${var.backlog_alert_threshold} undelivered messages for 5 minutes"

    condition_threshold {
      filter          = "metric.type=\"pubsub.googleapis.com/subscription/num_undelivered_messages\" AND resource.type=\"pubsub_subscription\" AND resource.labels.subscription_id=\"${google_pubsub_subscription.genomic_events_sub.name}\""
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = var.backlog_alert_threshold

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  notification_channels = google_monitoring_notification_channel.email[*].id
  enabled               = true

  alert_strategy {
    auto_close = "604800s"
  }
}

# Any message on the dead-letter subscription failed every delivery attempt.
resource "google_monitoring_alert_policy" "dead_lettered" {
  display_name = "GenomicFlow messages dead-lettered"
  combiner     = "OR"

  conditions {
    display_name = "At least one message on the dead-letter subscription"

    condition_threshold {
      filter          = "metric.type=\"pubsub.googleapis.com/subscription/num_undelivered_messages\" AND resource.type=\"pubsub_subscription\" AND resource.labels.subscription_id=\"${google_pubsub_subscription.dead_letter_sub.name}\""
      duration        = "60s"
      comparison      = "COMPARISON_GT"
      threshold_value = 0

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MAX"
      }
    }
  }

  notification_channels = google_monitoring_notification_channel.email[*].id
  enabled               = true

  alert_strategy {
    auto_close = "604800s"
  }
}
