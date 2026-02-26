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
    p.add_argument("--domain", default="login-verify-now.top")
    p.add_argument("--dst-ip", default="198.51.100.23")
    args = p.parse_args()

    now = datetime.now(timezone.utc)
    # generate timestamps every 60s (periodic)
    timestamps = [(now - timedelta(seconds=60 * i)).isoformat() for i in range(12)][::-1]

    payload = {
        "event_type": "network_beacon",
        "dst_domain": args.domain,
        "dst_ip": args.dst_ip,
        "hosts": ["host-a", "host-b", "host-c"],
        "timestamps": timestamps,
        "periodic": False,
    }

    status, body = post_json(f"{args.base_url}/webhook/network", payload, args.api_key)
    print(status)
    print(body)


if __name__ == "__main__":
    main()
