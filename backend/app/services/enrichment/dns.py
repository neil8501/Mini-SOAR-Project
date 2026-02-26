from __future__ import annotations

from typing import Any

import dns.resolver


def dns_enrich(domain: str) -> dict[str, Any]:
    resolver = dns.resolver.Resolver()
    resolver.lifetime = 3.0

    def q(rt: str) -> list[str]:
        try:
            ans = resolver.resolve(domain, rt)
            return [str(r).strip() for r in ans]
        except Exception:
            return []

    return {
        "domain": domain,
        "A": q("A"),
        "AAAA": q("AAAA"),
        "CNAME": q("CNAME"),
        "MX": q("MX"),
        "NS": q("NS"),
        "TXT": q("TXT"),
    }
