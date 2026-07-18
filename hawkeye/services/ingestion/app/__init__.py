"""Hawkeye Ingestion Service.

Continuously fetches GCP resources, billing, metrics and audit logs,
normalizes them to a common schema and publishes them to Pub/Sub topics
for downstream processing.

See HAWKEYE_COMPLETE_ARCHITECTURE.md -> Layer 1: Data Ingestion Service.
"""
