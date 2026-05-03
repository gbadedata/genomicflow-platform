# GenomicFlow Clinical Data Platform

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Google_Cloud-4285F4?style=for-the-badge&logo=google-cloud&logoColor=white" />
  <img src="https://img.shields.io/badge/BigQuery-669DF6?style=for-the-badge&logo=google-bigquery&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/Terraform-7B42BC?style=for-the-badge&logo=terraform&logoColor=white" />
  <img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white" />
</p>

<p align="center">
  <strong>A production-grade, real-time clinical genomics data engineering platform on Google Cloud Platform.</strong>
</p>

<p align="center">
  Simulates a clinical lab environment where sequencing instruments publish run results continuously through a
  streaming pipeline into a BigQuery data warehouse — validated, structured, and served via a serverless
  Cloud Run REST API and visualised in a live Looker Studio dashboard.
</p>

<p align="center">
  <a href="https://genomicflow-api-173173517949.europe-west2.run.app/docs"><strong>Live API Docs</strong></a> ·
  <a href="https://datastudio.google.com/reporting/16db7e41-2ac2-4a0f-8cf4-5fc0686dcd52"><strong>Live Dashboard</strong></a> ·
  <a href="docs/architecture.md"><strong>Architecture Decisions</strong></a>
</p>

---

## The Problem

Clinical genomics labs generate sequencing run results continuously — from instruments like Illumina NovaSeq,
Oxford Nanopore PromethION, and PacBio Sequel. Each run produces critical metadata: quality scores, coverage
depth, variant calls, and sample identifiers.

Without a data platform, this data sits in flat files, is shared via email, and is impossible to query at
scale. Clinicians and researchers cannot ask questions like *"show me all runs with coverage below 30x in the
last 7 days"* without manually scraping spreadsheets.

**GenomicFlow solves this** by building a real-time streaming pipeline that captures every sequencing run the
moment it completes, validates it against clinical quality standards, loads it into a structured BigQuery
warehouse, and exposes it through a self-documenting REST API and live dashboard.

---

## Architecture

```
+---------------------------------------------------------------------+
|                    Lab Instrument Simulator                          |
|         (Python · Faker · Pydantic · 5 platform types)              |
+------------------------------+--------------------------------------+
                               | publishes events
                               v
+---------------------------------------------------------------------+
|                  Google Cloud Pub/Sub                                |
|     Topic: genomic-events  ·  Dead-letter: genomic-events-dead      |
|     Message retention: 24h  ·  Retry with exponential back-off      |
+------------------------------+--------------------------------------+
                               | streaming pull
                               v
+---------------------------------------------------------------------+
|                  Validation & Streaming Pipeline                     |
|                        (Python consumer)                             |
|                                                                      |
|   9 validation rules across 4 categories                            |
|        |                          |                                  |
|        v                          v                                  |
|   PASSED records             FAILED / QUARANTINED                    |
|        |                     logged with rejection reason            |
|        v                                                             |
|   BigQuery Writer                                                    |
|   +-- sequencing_runs  (partitioned by day, clustered)              |
|   +-- variants         (genomic variant calls per run)              |
|   +-- quality_metrics  (7 QC metrics per run)                       |
+------------------------------+--------------------------------------+
                               |
              +----------------+----------------+
              v                v                v
     +-------------+  +--------------+  +----------------+
     |  FastAPI    |  |  BigQuery    |  | Looker Studio  |
     | Cloud Run   |  |  SQL layer   |  |  Dashboard     |
     | (serverless)|  | (ad-hoc SQL) |  | (live charts)  |
     +-------------+  +--------------+  +----------------+

Infrastructure: Terraform  ·  CI/CD: GitHub Actions  ·  Containers: Docker
```

---

## Technology Stack

| Category | Technologies |
|----------|-------------|
| **Language** | Python 3.11 |
| **Streaming** | Google Cloud Pub/Sub (topic + dead-letter + subscription) |
| **Warehouse** | Google BigQuery (day-partitioned, clustered tables) |
| **Storage** | Google Cloud Storage (raw + processed + dataflow zones) |
| **API** | FastAPI on Cloud Run (serverless, scales to zero) |
| **Infrastructure** | Terraform (all GCP resources as code) |
| **Containers** | Docker (multi-stage, non-root user) + Artifact Registry |
| **CI/CD** | GitHub Actions (lint + test + Docker build) |
| **Visualisation** | Looker Studio (live BigQuery connection) |
| **IAM** | GCP Service Accounts with least-privilege roles |
| **Testing** | pytest · 24 passing tests · 95%+ coverage on core modules |
| **Logging** | structlog (structured JSON logs with correlation IDs) |

---

## Data Model

Three BigQuery tables with day partitioning and clustering for query efficiency:

### `sequencing_runs` - Primary fact table

| Column | Type | Description |
|--------|------|-------------|
| run_id | STRING | Unique run identifier (RUN-XXXXXXXXXXXX) |
| sample_id | STRING | Clinical sample identifier |
| patient_id | STRING | Anonymised patient identifier |
| organism | STRING | Target organism (Homo sapiens etc.) |
| platform | STRING | Sequencing instrument model |
| library_strategy | STRING | WGS, WES, RNA-Seq, AMPLICON, Targeted |
| total_bases | INTEGER | Total bases sequenced |
| total_reads | INTEGER | Total sequencing reads |
| mean_quality | FLOAT | Mean base quality score |
| coverage_depth | FLOAT | Mean coverage depth (x) |
| status | STRING | PASSED / FAILED / QUARANTINED |
| failure_reason | STRING | Rejection reason if failed |
| completeness_score | FLOAT | 0.0 to 1.0 metadata completeness |
| run_timestamp | TIMESTAMP | When the run was performed (partition key) |
| ingested_at | TIMESTAMP | When record was ingested |

### `variants` — Genomic variant calls per run

Partitioned by `detected_at`. Fields: chromosome, position, reference/alternate alleles, variant type,
quality score, clinical significance (PATHOGENIC through BENIGN).

### `quality_metrics` — 7 QC metrics per run

Partitioned by `measured_at`. Tracks: mean_base_quality, coverage_depth, Q30_percentage, duplicate_rate,
mapping_rate, GC_content, insert_size_median — each with threshold and pass/fail flag.

---

## Data Quality Engine

9 validation rules enforced on every message before it reaches BigQuery:

| Category | Rule | Action on failure |
|----------|------|-------------------|
| Identity | run_id non-null | Quarantine |
| Identity | run_id matches RUN- format | Quarantine |
| Identity | sample_id non-null | Quarantine |
| Status | Valid PASSED/FAILED/QUARANTINED value | Quarantine |
| Metric | mean_quality non-negative | Warning log |
| Metric | coverage_depth non-negative | Warning log |
| Completeness | organism present | Warning log |
| Completeness | platform present | Warning log |
| Completeness | total_bases positive | Warning log |

**Blocking rules** (identity + status) quarantine the record and prevent BigQuery insertion.
**Warning rules** log the issue but allow the record through — nothing is silently dropped.

From 50 runs ingested: **45 passed (90%) · 3 failed (6%) · 2 quarantined (4%)**

---

## API Endpoints

**Base URL:** `https://genomicflow-api-173173517949.europe-west2.run.app`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Service health + BigQuery connectivity + run count |
| GET | `/runs/summary` | Aggregate stats: total runs, pass rate, avg quality, total bases |
| GET | `/runs` | Recent runs with optional status filter (limit, status params) |
| GET | `/runs/{run_id}` | Individual run detail including all variants |
| GET | `/platforms/summary` | Platform distribution with quality breakdown |
| GET | `/organisms` | Organism breakdown with run counts |
| GET | `/quality/report` | Quality KPIs: completeness, quarantine rate |
| GET | `/quality/variants/significance` | Clinical significance distribution |

Interactive documentation at `/docs` (Swagger UI) and `/redoc`.

---

## Live Resources

| Resource | URL |
|----------|-----|
| **Live API** | https://genomicflow-api-173173517949.europe-west2.run.app |
| **API Docs** | https://genomicflow-api-173173517949.europe-west2.run.app/docs |
| **Dashboard** | https://datastudio.google.com/reporting/16db7e41-2ac2-4a0f-8cf4-5fc0686dcd52 |

---

## Project Structure

```
genomicflow-platform/
+-- infra/                        # Terraform - all GCP resources
|   +-- main.tf                   # Provider configuration
|   +-- variables.tf              # Input variables
|   +-- storage.tf                # GCS buckets (raw, processed, dataflow)
|   +-- pubsub.tf                 # Pub/Sub topic, subscription, dead-letter
|   +-- bigquery.tf               # Dataset + 3 tables with schemas
|   +-- iam.tf                    # Service accounts + least-privilege roles
|   +-- monitoring.tf             # Alert policies
|   +-- outputs.tf                # Resource names and endpoints
|
+-- simulator/                    # Clinical lab instrument simulator
|   +-- src/
|   |   +-- config.py             # Pydantic settings
|   |   +-- models.py             # Pydantic event models
|   |   +-- generator.py          # Realistic genomic data generator
|   |   +-- publisher.py          # Pub/Sub publisher
|   |   +-- runner.py             # Simulator orchestrator
|   +-- tests/
|       +-- test_generator.py     # 10 unit tests
|
+-- pipeline/                     # Streaming pipeline
|   +-- src/
|   |   +-- validator.py          # 9-rule validation engine
|   |   +-- bq_writer.py          # BigQuery writer (3 tables)
|   |   +-- pipeline.py           # Pub/Sub consumer + orchestrator
|   +-- tests/
|       +-- test_validator.py     # 14 unit tests
|
+-- api/                          # FastAPI Cloud Run service
|   +-- main.py                   # App factory + middleware
|   +-- models/
|   |   +-- bq_queries.py         # Parameterised BigQuery query functions
|   +-- routers/
|       +-- health.py             # /health
|       +-- runs.py               # /runs, /runs/summary, /runs/{id}
|       +-- platforms.py          # /platforms/summary
|       +-- organisms.py          # /organisms
|       +-- quality.py            # /quality/report and /quality/variants/significance
|
+-- docs/
|   +-- architecture.md           # Architecture Decision Records (6 ADRs)
|   +-- screenshots/              # GCP console evidence (18 screenshots)
|
+-- .github/
|   +-- workflows/
|       +-- ci.yml                # GitHub Actions: lint + test + Docker build
|
+-- Dockerfile                    # Multi-stage, non-root user
+-- .env.example                  # Environment variable template
+-- requirements.txt              # Pinned dependencies
+-- setup.py                      # Editable install
+-- pyproject.toml                # Tool configuration (pytest, black, flake8)
```

---

## Running Locally

### Prerequisites

- Python 3.11
- Google Cloud SDK (`gcloud auth application-default login`)
- GCP project with billing enabled
- Terraform >= 1.5.0

### Setup

```bash
# Clone and install
git clone https://github.com/gbadedata/genomicflow-platform.git
cd genomicflow-platform
python -m venv .venv

# Windows
.venv\Scripts\activate

# Mac/Linux
source .venv/bin/activate

pip install -r requirements.txt
pip install -e .
cp .env.example .env
# Edit .env with your GCP project ID
```

### Run the simulator (dry run - no GCP calls)

```bash
python -c "
from simulator.src.runner import run_simulator
run_simulator(dry_run=True, max_runs=5, interval_seconds=0.5)
"
```

### Publish real events to Pub/Sub

```bash
python -c "
from simulator.src.runner import run_simulator
run_simulator(dry_run=False, max_runs=20, interval_seconds=1.0)
"
```

### Run the streaming pipeline

```bash
python -c "
from pipeline.src.pipeline import run_pipeline
run_pipeline(max_messages=20)
"
```

### Start the API locally

```bash
uvicorn api.main:app --reload --port 8000
# Visit http://localhost:8000/docs
```

---

## Infrastructure

All GCP resources are provisioned via Terraform:

```bash
cd infra
terraform init
terraform plan
terraform apply
```

**Resources created:**

- 3 GCS buckets (raw, processed, dataflow staging)
- Pub/Sub topic + subscription + dead-letter topic
- BigQuery dataset with 3 partitioned and clustered tables
- 2 service accounts with least-privilege IAM roles
- Cloud Monitoring alert policy for high failure rates
- Artifact Registry repository for Docker images

Full infrastructure recreatable in under 5 minutes.

---

## Testing

```bash
# Run all tests
pytest simulator/tests/ pipeline/tests/ -v

# With coverage report
pytest simulator/tests/ pipeline/tests/ \
  --cov=simulator --cov=pipeline \
  --cov-report=term-missing
```

| Module | Coverage |
|--------|----------|
| simulator/src/generator.py | 100% |
| simulator/src/models.py | 100% |
| pipeline/src/validator.py | 95% |
| **Total** | **24 passing tests** |

---

## Architecture Decisions

Key decisions documented in [`docs/architecture.md`](docs/architecture.md):

| ADR | Decision | Rationale |
|-----|----------|-----------|
| ADR-001 | Pub/Sub streaming over batch | Sub-minute latency for clinical decisions |
| ADR-002 | BigQuery over Cloud SQL | Petabyte scale, serverless, optimised for analytical queries |
| ADR-003 | Quarantine-not-delete | Clinical data integrity and full audit trail |
| ADR-004 | Cloud Run over GKE | Serverless, scales to zero, no cluster management overhead |
| ADR-005 | Terraform for all infrastructure | Reproducibility, version control, instant teardown |
| ADR-006 | AWS portability mapping | Architecture patterns identical, only infrastructure config changes |

---

## GCP to AWS Portability

This platform is intentionally designed to be portable. The Python application code is cloud-agnostic —
only the infrastructure configuration (Terraform) changes between providers.

| GCP (this project) | AWS Equivalent |
|--------------------|---------------|
| Cloud Pub/Sub | Amazon Kinesis Data Streams |
| BigQuery | Amazon Redshift or Athena |
| Cloud Run | AWS Lambda or ECS Fargate |
| Google Cloud Storage | Amazon S3 |
| Artifact Registry | Amazon ECR |
| Cloud Monitoring | Amazon CloudWatch |
| Looker Studio | Amazon QuickSight |
| Cloud Build | AWS CodeBuild |
