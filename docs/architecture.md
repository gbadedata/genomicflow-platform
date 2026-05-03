\# Architecture Decision Records — GenomicFlow Platform



\## ADR-001: Real-time streaming over batch ingestion



\*\*Decision:\*\* Use Google Cloud Pub/Sub for event-driven ingestion rather than scheduled batch pulls.



\*\*Rationale:\*\* Clinical genomics labs generate results continuously. A batch approach would introduce latency between a run completing and data being available to clinicians. Pub/Sub enables sub-minute latency from instrument to dashboard.



\*\*Alternatives considered:\*\* Scheduled Cloud Scheduler jobs pulling from a lab API. Rejected because latency is unacceptable for clinical decision support.



\---



\## ADR-002: BigQuery as the analytical warehouse



\*\*Decision:\*\* Use BigQuery as the primary data store rather than Cloud SQL (managed PostgreSQL).



\*\*Rationale:\*\* BigQuery is serverless, scales to petabytes, and is optimised for analytical queries across large datasets. Clinical genomics data grows rapidly — a single lab can generate terabytes per month. BigQuery handles this without infrastructure management.



\*\*Alternatives considered:\*\* Cloud SQL PostgreSQL. Better for transactional workloads but requires instance management and doesn't scale as naturally for analytical queries.



\---



\## ADR-003: Quarantine-not-delete for failed validation



\*\*Decision:\*\* Records failing validation are logged with rejection reasons, not deleted.



\*\*Rationale:\*\* In clinical settings, losing data — even bad data — can have regulatory implications. Quarantined records with rejection reasons enable root cause analysis and reprocessing.



\---



\## ADR-004: Cloud Run over GKE for the API



\*\*Decision:\*\* Deploy the FastAPI service on Cloud Run rather than Google Kubernetes Engine.



\*\*Rationale:\*\* Cloud Run is serverless — scales to zero when not in use (zero cost), scales up automatically under load. GKE requires cluster management and has minimum costs even when idle. For an API serving intermittent scientific queries, Cloud Run is more cost-efficient.



\---



\## ADR-005: Terraform for all infrastructure



\*\*Decision:\*\* All GCP resources provisioned via Terraform, not gcloud commands or console clicks.



\*\*Rationale:\*\* Reproducibility. The entire platform can be destroyed and recreated in under 5 minutes. Infrastructure changes are version-controlled. Onboarding a new team member requires only terraform apply.



\---



\## ADR-006: AWS portability



\*\*Mapping to AWS equivalents:\*\*

\- Pub/Sub → Amazon Kinesis or SNS/SQS

\- BigQuery → Amazon Redshift or Athena

\- Cloud Run → AWS Lambda or ECS Fargate

\- GCS → Amazon S3

\- Cloud Build → GitHub Actions or AWS CodeBuild

\- Looker Studio → Amazon QuickSight

