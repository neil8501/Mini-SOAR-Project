# Mini-SOAR Incident Automation Platform (Local, Free)

A practical SOAR-style system you can run locally: **alerts → case → enrichment → playbook → actions → metrics/dashboard → report**.

## What it includes

- FastAPI ingest + Swagger docs
- Case management (cases, artifacts, timeline, actions, tickets)
- Celery worker processing pipeline
- Enrichment: DNS + RDAP (public)
- 3 pipelines: phishing, suspicious login, beaconing
- Mock responders: blocklist update, notify, create internal ticket
- Observability: Prometheus + Grafana
- Incident report generation (Markdown, optional PDF)

## Architecture (high level)

- API receives webhook → stores alert → enqueues Celery task
- Worker creates/updates case → extracts artifacts → enriches → scores → triggers responders
- API exposes /metrics and case endpoints
- Worker pushes metrics to Pushgateway → Prometheus scrapes → Grafana dashboard

## Quickstart

### 1) Start the stack
```bash
docker compose up --build
