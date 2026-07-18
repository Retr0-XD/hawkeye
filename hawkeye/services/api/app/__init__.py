"""Hawkeye API / Query Service (Layer 5).

Exposes the processed data (Firestore + BigQuery) via a REST API consumed by
the demo / user dashboards. Mirrors the GraphQL query shapes from the
architecture doc (resources, recommendations, alerts, metrics, cost summary,
dependency graph, dashboard aggregates) using plain REST endpoints.
"""
