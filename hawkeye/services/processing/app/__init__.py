"""Hawkeye Processing Service (Layer 2/3).

Consumes normalized records from Pub/Sub, correlates resources with costs and
metrics, builds a dependency graph, detects changes, generates recommendations,
and persists everything to Firestore + BigQuery.
"""
