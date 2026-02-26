from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

import httpx


def _parse_rdap_date(s: str) -> Optional[datetime]:
    # RDAP often returns ISO-8601 like "2024-01-02T03:04:05Z"
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def rdap_domain(domain: str) -> dict[str, Any]:
    url = f"https://rdap.org/domain/{domain}"
    out: dict[str, Any] = {"domain": domain, "ok": False}

    try:
        with httpx.Client(timeout=5.0, follow_redirects=True) as client:
            r = client.get(url, headers={"Accept": "application/rdap+json"})
            out["status_code"] = r.status_code
            if r.status_code >= 400:
                out["error"] = f"HTTP {r.status_code}"
                return out
            data = r.json()
    except Exception as e:
        out["error"] = str(e)
        return out

    events = data.get("events") or []
    reg_dt = None
    for ev in events:
        if ev.get("eventAction") in ("registration", "registered"):
            reg_dt = _parse_rdap_date(ev.get("eventDate", "") or "")
            break

    now = datetime.now(timezone.utc)
    age_days = None
    if reg_dt:
        age_days = int((now - reg_dt).total_seconds() // 86400)

    out.update(
        {
            "ok": True,
            "ldhName": data.get("ldhName"),
            "handle": data.get("handle"),
            "status": data.get("status"),
            "registration_date": reg_dt.isoformat() if reg_dt else None,
            "domain_age_days": age_days,
            "events": [
                {"action": ev.get("eventAction"), "date": ev.get("eventDate")}
                for ev in events[:10]
            ],
        }
    )
    return out
