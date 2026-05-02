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
