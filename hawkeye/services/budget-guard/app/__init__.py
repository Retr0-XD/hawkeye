"""Hawkeye Budget Guard - keeps the project in the GCP free zone forever.

If the project's month-to-date spend exceeds a hard cap (default $0.10),
all billable services are suspended (public access revoked + schedulers
paused) until the next calendar month, then auto-resumed.
"""
