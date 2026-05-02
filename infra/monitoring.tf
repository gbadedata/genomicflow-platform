# Alert policy for high failure rate
resource "google_monitoring_alert_policy" "high_failure_rate" {
  display_name = "GenomicFlow High Sequencing Failure Rate"
  combiner     = "OR"

  conditions {
    display_name = "Sequencing failure rate > 10%"

    condition_threshold {
      filter          = "metric.type=\"pubsub.googleapis.com/subscription/num_undelivered_messages\" AND resource.type=\"pubsub_subscription\""
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = 100

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  notification_channels = []
  enabled               = true

  alert_strategy {
    auto_close = "604800s"
  }
}
