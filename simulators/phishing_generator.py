import argparse
import json
import os
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
    p.add_argument("--domain", default="micros0ft-support.com")
    args = p.parse_args()

    payload = {
        "subject": "Verify your account",
        "sender": "security@micros0ft-support.com",
        "recipient": "user@company.com",
        "body": f"Verify here: https://{args.domain}/login",
    }

    status, body = post_json(f"{args.base_url}/webhook/email", payload, args.api_key)
    print(status)
    print(body)


if __name__ == "__main__":
    main()
