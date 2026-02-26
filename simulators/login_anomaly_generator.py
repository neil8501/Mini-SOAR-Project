import argparse
import json
import os
from datetime import datetime, timedelta, timezone
import urllib.request


def post_json(url: str, payload: dict, api_key: str):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "X-API-Key": api_key,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        body = resp.read().decode("utf-8")
        return resp.status, body


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", default=os.getenv("SOAR_BASE_URL", "http://localhost:8000"))
    p.add_argument("--api-key", default=os.getenv("SOAR_WEBHOOK_KEY", "dev-webhook-key"))
    p.add_argument("--user", default="neil@company.com")
    p.add_argument("--bad-ip", default="203.0.113.66")
    args = p.parse_args()

    now = datetime.now(timezone.utc)

    # Event 1: normal US login
    e1 = {
        "event_type": "login",
        "user": args.user,
        "ip": "198.51.100.10",
        "user_agent": "Mozilla/5.0",
        "success": True,
        "country": "US",
        "city": "Chicago",
        "lat": 41.8781,
        "lon": -87.6298,
        "ts": (now - timedelta(minutes=10)).isoformat(),
        "mfa_fatigue": False,
    }

    # Event 2: impossible travel to Paris + bad IP + success
    e2 = {
        "event_type": "login",
        "user": args.user,
        "ip": args.bad_ip,
        "user_agent": "Mozilla/5.0",
        "success": True,
        "country": "FR",
        "city": "Paris",
        "lat": 48.8566,
        "lon": 2.3522,
        "ts": now.isoformat(),
        "mfa_fatigue": True,
    }

    s1, b1 = post_json(f"{args.base_url}/webhook/auth", e1, args.api_key)
    print("event1", s1, b1)

    s2, b2 = post_json(f"{args.base_url}/webhook/auth", e2, args.api_key)
    print("event2", s2, b2)


if __name__ == "__main__":
    main()
