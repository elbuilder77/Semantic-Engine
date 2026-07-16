# Purpose

Use this skill to fix, test, and prove the critical SES API flows.

This skill owns:
- `/api/v1/search`
- `/api/v1/ingest/file` and `/api/v1/ingest/text`
- `/api/v1/documents` and `/api/v1/stats`
- `/api/v1/admin/keys` and `/api/v1/admin/analytics`
- `/api/v1/reports/evidence` and administrative reports
- integration tests around those endpoints
- real-service validation for Qdrant, Redis, Ollama, SQL, and the API

## Core responsibility

Convert critical API paths from assumed behavior into validated behavior.
