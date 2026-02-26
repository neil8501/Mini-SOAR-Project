import re
from typing import Iterable

# Basic URL regex good enough for demo
URL_RE = re.compile(r"(https?://[^\s<>'\"()\]]+)", re.IGNORECASE)

# Domain-ish token: extract from URL using a simple approach
DOMAIN_RE = re.compile(r"https?://([^/:\s]+)", re.IGNORECASE)

EMAIL_RE = re.compile(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)")


def extract_urls(text: str) -> list[str]:
    return list(dict.fromkeys(URL_RE.findall(text or "")))  # de-dupe, preserve order


def extract_domains_from_urls(urls: Iterable[str]) -> list[str]:
    domains: list[str] = []
    seen = set()
    for u in urls:
        m = DOMAIN_RE.search(u)
        if not m:
            continue
        d = m.group(1).lower()
        if d not in seen:
            seen.add(d)
            domains.append(d)
    return domains


def extract_emails(text: str) -> list[str]:
    return list(dict.fromkeys(EMAIL_RE.findall(text or "")))


def extract_phishing_artifacts(payload: dict) -> dict[str, list[str]]:
    """
    Expected payload keys (from simulator / webhook):
      subject, sender, recipient, body
    """
    body = payload.get("body", "") or ""
    subject = payload.get("subject", "") or ""
    sender = payload.get("sender", "") or ""
    recipient = payload.get("recipient", "") or ""

    urls = extract_urls(body)
    domains = extract_domains_from_urls(urls)

    emails = []
    emails.extend(extract_emails(sender))
    emails.extend(extract_emails(recipient))
    emails.extend(extract_emails(body))
    emails.extend(extract_emails(subject))

    # also store sender/recipient as “email” even if not regex-matched (simple)
    if "@" in sender:
        emails.append(sender)
    if "@" in recipient:
        emails.append(recipient)

    # dedupe
    emails = list(dict.fromkeys([e.strip().lower() for e in emails if e.strip()]))

    return {"urls": urls, "domains": domains, "emails": emails}
