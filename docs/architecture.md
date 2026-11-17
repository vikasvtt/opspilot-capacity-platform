# Architecture

OpsPilot is split into an Angular client and a FastAPI service backed by PostgreSQL. The service owns authorization, placement decisions, and all writes. An AI integration may draft a proposal, but a separate human approval action will be required before the service changes inventory. Every proposal and review will be auditable.

The initial backend schema establishes users, sites, racks, servers, capacity requests, approvals, and audit logs. Alembic owns schema changes; SQLAlchemy models define the application mapping.
