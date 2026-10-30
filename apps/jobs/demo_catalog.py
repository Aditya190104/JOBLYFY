"""Fictional database seed fixtures, never used as frontend job cards."""

import json
from pathlib import Path

DEMO_PREFIX = "joblyfy-careers-v2:"
_catalog = json.loads(
    (Path(__file__).parent / "data" / "demo_jobs.json").read_text(encoding="utf-8")
)
COMPANIES = _catalog["companies"]
JOBS = _catalog["jobs"]
