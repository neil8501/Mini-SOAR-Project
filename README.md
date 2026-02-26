# Mini-SOAR Incident Automation Platform

[![CI](https://img.shields.io/badge/CI-GitHub%20Actions-blue)](#ci--cd)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](#license)
[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)](#tech-stack)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.1xx-teal)](#tech-stack)

A **Security Orchestration, Automation & Response (SOAR)** mini-platform that ingests alerts, enriches them, runs automated playbooks, and tracks cases end-to-end with dashboards, metrics, and audit trails.

> **Why this exists:** demonstrate real-world SOC automation patterns (alert → triage → enrichment → response → reporting) using modern backend engineering practices.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Quick Start (Docker)](#quick-start-docker)
- [Local Dev Setup](#local-dev-setup)
- [Configuration](#configuration)
- [How It Works](#how-it-works)
- [API Overview](#api-overview)
- [Observability](#observability)
- [Testing](#testing)
- [CI / CD](#ci--cd)
- [Security Notes](#security-notes)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

---

## Features

### Alert ingestion & normalization
- Ingest alerts via **REST webhook** (e.g., SIEM, EDR, email parser, custom sources)
- Normalize to a standard schema (source, severity, entity, timestamps, raw payload)
- De-duplicate / correlate by entity + time window (configurable)

### Case management
- Create cases automatically from high-confidence alerts
- Case lifecycle: `NEW → TRIAGED → IN_PROGRESS → RESOLVED → CLOSED`
- Assignments, tags, notes, timeline, and audit events

### Enrichment
- IP / domain / URL enrichment (pluggable providers)
- User / host context (directory/CMDB stubs or connectors)
- Evidence capture stored on the case timeline

### Playbooks & automation
- Execute playbooks asynchronously (Celery workers)
- Safe actions by default: blocklists, ticket creation, notifications
- Human-in-the-loop approvals for destructive actions

### Reporting & dashboards
- Operational metrics: MTTA, MTTR, case volume, severity distribution
- Prometheus metrics + Grafana dashboards
- Exportable reports (CSV/JSON) and an audit log

---

## Architecture

High-level flow:

```text
           ┌──────────────┐
           │ Alert Source  │ (SIEM/EDR/Webhook)
           └──────┬───────┘
                  │ POST /alerts
                  v
        ┌─────────────────────┐
        │ FastAPI API Service  │
        │  - auth / RBAC       │
        │  - validation        │
        │  - persistence       │
        └──────┬──────────────┘
               │ enqueue job
               v
        ┌─────────────────────┐
        │ Redis (Broker/Cache) │
        └──────┬──────────────┘
               │
               v
        ┌─────────────────────┐
        │ Celery Workers       │
        │  - enrich            │
        │  - correlate         │
        │  - playbooks         │
        └──────┬──────────────┘
               │ write results
               v
        ┌─────────────────────┐
        │ Postgres             │
        │  cases / alerts      │
        │  evidence / audit    │
        └──────┬──────────────┘
               │ metrics/logs
               v
   ┌─────────────────┐   ┌─────────────────┐
   │ Prometheus       │   │ Grafana          │
   └─────────────────┘   └─────────────────┘
