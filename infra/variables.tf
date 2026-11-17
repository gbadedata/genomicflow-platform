variable "project_id" {
  description = "GCP project ID"
  type        = string
  default     = "genomicflow-platform"
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "europe-west2"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "dev"
}

variable "max_delivery_attempts" {
  description = "Deliveries before a message moves to the dead-letter topic (Pub/Sub allows 5 to 100)"
  type        = number
  default     = 5

  validation {
    condition     = var.max_delivery_attempts >= 5 && var.max_delivery_attempts <= 100
    error_message = "max_delivery_attempts must be between 5 and 100."
  }
}

variable "alert_email" {
  description = "Address that receives alerts. Leave empty to create the alerts without a notification channel."
  type        = string
  default     = ""
}

variable "backlog_alert_threshold" {
  description = "Undelivered messages on the main subscription that trigger the backlog alert"
  type        = number
  default     = 100
}
