"""Public aggregate stats for the landing page (no auth required).

These power the Live Impact section on index.html so the numbers shown are
computed from real usage data instead of hardcoded placeholders.
"""
from __future__ import annotations

import json

from fastapi import APIRouter

from ..constants import GROUPS
from ..database import query

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/impact")
def impact_stats() -> dict:
    """Real usage numbers for the landing page's Live Impact section."""
    total = query("SELECT COUNT(*) AS n FROM reports")[0]["n"]
    resolved = query(
        "SELECT COUNT(*) AS n FROM reports WHERE status = 'RESOLVED'"
    )[0]["n"]
    crew = query(
        "SELECT COUNT(*) AS n FROM admin_users WHERE role = 'employee'"
    )[0]["n"]

    # Time-to-dispatch: report creation → first ASSIGNED history entry.
    deltas = []
    for r in query("SELECT created_at, history FROM reports WHERE history != '[]'"):
        try:
            history = json.loads(r["history"] or "[]")
        except (ValueError, TypeError):
            continue
        dispatch = next((e["at"] for e in history if e.get("to") == "ASSIGNED"), None)
        if dispatch and r["created_at"]:
            deltas.append(dispatch - r["created_at"])

    return {
        "reportsSubmitted": total,
        "verifiedCleanups": resolved,
        "resolutionRate": round(resolved / total * 100) if total else 0,
        "activeCrew": crew,
        "avgResponseHours": round(sum(deltas) / len(deltas) / 3600000, 1) if deltas else 0,
        "wards": len(GROUPS),
    }