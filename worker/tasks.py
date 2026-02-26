import json
import math
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import dns.resolver
import httpx
from celery import Celery
from prometheus_client import CollectorRegistry, Counter, Histogram, push_to_gateway
from sqlmodel import Session, SQLModel, create_engine, select

from worker_config import settings

celery_app = Celery(
    "mini_soar_worker",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

engine = create_engine(settings.database_url, pool_pre_ping=True)

BLOCKLIST_PATH = Path("/data/blocklist.json")
THREATFEED_DOMAINS_PATH = Path("/data/threatfeeds/sample_bad_domains.txt")
THREATFEED_IPS_PATH = Path("/data/threatfeeds/sample_bad_ips.txt")

worker_registry = CollectorRegistry()
cases_created_total = Counter(
    "cases_created_total",
    "Total cases created by worker",
    ["type"],
    registry=worker_registry,
)
playbook_runs_total = Counter(
    "playbook_runs_total",
    "Total playbook runs by worker",
    ["playbook", "outcome"],
    registry=worker_registry,
)
action_runs_total = Counter(
    "action_runs_total",
    "Total action executions by worker",
    ["action_type", "success"],
    registry=worker_registry,
)
enrichment_latency_seconds = Histogram(
    "enrichment_latency_seconds",
    "Enrichment latency in seconds",
    ["enricher"],
    registry=worker_registry,
)


def _push_metrics():
    try:
        push_to_gateway(settings.pushgateway_url, job="mini-soar-worker", registry=worker_registry)
    except Exception:
        return


def _ensure_tables():
    SQLModel.metadata.create_all(engine)


def _now():
    return datetime.now(timezone.utc)


def _parse_ts(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _dns_enrich(domain: str) -> dict:
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


def _parse_iso_dt(s: str):
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _rdap_domain(domain: str) -> dict:
    url = f"https://rdap.org/domain/{domain}"
    out = {"domain": domain, "ok": False}

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
            reg_dt = _parse_iso_dt(ev.get("eventDate", "") or "")
            break

    age_days = None
    if reg_dt:
        age_days = int((_now() - reg_dt).total_seconds() // 86400)

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


def _load_set(path: Path) -> set[str]:
    out: set[str] = set()
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                s = line.strip().lower()
                if not s or s.startswith("#"):
                    continue
                out.add(s)
    except Exception:
        return set()
    return out


def _looks_like_typosquat(domain: str) -> bool:
    d = domain.lower()
    norm = d.replace("0", "o").replace("1", "l").replace("-", "")
    brands = ["microsoft", "paypal", "google", "apple", "amazon"]
    for b in brands:
        if b in norm and not d.endswith(f"{b}.com"):
            return True
    return False


def _severity_from_score(score: int) -> str:
    if score >= 80:
        return "critical"
    if score >= 60:
        return "high"
    if score >= 30:
        return "medium"
    return "low"


def _extract_phishing(payload: dict) -> dict[str, list[str]]:
    import re

    url_re = re.compile(r"(https?://[^\s<>'\"()\]]+)", re.IGNORECASE)
    domain_re = re.compile(r"https?://([^/:\s]+)", re.IGNORECASE)
    email_re = re.compile(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)")

    body = payload.get("body", "") or ""
    subject = payload.get("subject", "") or ""
    sender = payload.get("sender", "") or ""
    recipient = payload.get("recipient", "") or ""

    urls = list(dict.fromkeys(url_re.findall(body)))
    domains = []
    seen = set()
    for u in urls:
        m = domain_re.search(u)
        if not m:
            continue
        d = m.group(1).lower()
        if d not in seen:
            seen.add(d)
            domains.append(d)

    emails = []
    emails.extend(email_re.findall(sender))
    emails.extend(email_re.findall(recipient))
    emails.extend(email_re.findall(body))
    emails.extend(email_re.findall(subject))
    if "@" in sender:
        emails.append(sender)
    if "@" in recipient:
        emails.append(recipient)
    emails = list(dict.fromkeys([e.strip().lower() for e in emails if e.strip()]))

    return {"urls": urls, "domains": domains, "emails": emails}


def _extract_login(payload: dict) -> dict[str, list[str]]:
    user = (payload.get("user") or "").strip().lower()
    ip = (payload.get("ip") or "").strip()
    ua = (payload.get("user_agent") or "").strip()
    country = (payload.get("country") or "").strip()
    city = (payload.get("city") or "").strip()

    out = {"users": [], "ips": [], "user_agents": [], "countries": [], "cities": []}
    if user:
        out["users"].append(user)
    if ip:
        out["ips"].append(ip)
    if ua:
        out["user_agents"].append(ua)
    if country:
        out["countries"].append(country)
    if city:
        out["cities"].append(city)
    return out


def _extract_beacon(payload: dict) -> dict[str, list[str]]:
    domain = (payload.get("dst_domain") or "").strip().lower()
    ip = (payload.get("dst_ip") or "").strip()
    hosts = payload.get("hosts") or []
    hosts = [str(h).strip().lower() for h in hosts if str(h).strip()]

    out = {"domains": [], "ips": [], "hosts": []}
    if domain:
        out["domains"].append(domain)
    if ip:
        out["ips"].append(ip)
    if hosts:
        out["hosts"] = list(dict.fromkeys(hosts))
    return out


def _score_phishing(payload: dict, extracted: dict, dns_results: dict, rdap_results: dict) -> tuple[int, dict]:
    suspicious_tlds = {"zip", "top", "click", "xyz", "icu", "kim", "gq", "tk"}
    keywords = ("login", "verify", "password", "mfa", "account", "reset")

    score = 0
    reasons = []

    domains = extracted.get("domains", [])
    urls = extracted.get("urls", [])
    body = (payload.get("body") or "").lower()

    bad_domains = _load_set(THREATFEED_DOMAINS_PATH)

    young = False
    for d in domains:
        age = (rdap_results.get(d) or {}).get("domain_age_days")
        if isinstance(age, int) and age >= 0 and age < 7:
            young = True
            break
    if young:
        score += 20
        reasons.append("domain_age_lt_7d")

    if any(d.split(".")[-1] in suspicious_tlds for d in domains if "." in d):
        score += 10
        reasons.append("suspicious_tld")

    if any(any(k in u.lower() for k in keywords) for u in urls) or any(k in body for k in keywords):
        score += 15
        reasons.append("credential_keywords")

    if any(_looks_like_typosquat(d) for d in domains):
        score += 15
        reasons.append("typosquat_heuristic")

    if any(d in bad_domains for d in domains):
        score += 50
        reasons.append("threatfeed_match")

    sender = (payload.get("sender") or "").lower()
    sender_display = (payload.get("sender_display") or "").lower()
    if sender_display and sender and ("@" in sender):
        sender_domain = sender.split("@", 1)[-1]
        if sender_domain and sender_domain not in sender_display:
            score += 10
            reasons.append("sender_display_mismatch")

    score = max(0, min(100, score))
    details = {"score": score, "reasons": reasons, "domains": domains, "urls": urls}
    return score, details


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    p = math.pi / 180.0
    dlat = (lat2 - lat1) * p
    dlon = (lon2 - lon1) * p
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin(dlon / 2) ** 2
    )
    return 2 * R * math.asin(math.sqrt(a))


def _score_login(payload: dict, user: str, ip: str, success: bool, country: str | None, prev: dict | None) -> tuple[int, dict]:
    score = 0
    reasons: list[str] = []

    bad_ips = _load_set(THREATFEED_IPS_PATH)

    if success and country and prev and prev.get("country") and country != prev.get("country"):
        score += 30
        reasons.append("new_country_success")

    if prev:
        ts = _parse_ts(payload.get("ts")) or _now()
        prev_ts = prev.get("ts")
        if isinstance(prev_ts, datetime):
            lat = payload.get("lat")
            lon = payload.get("lon")
            plat = prev.get("lat")
            plon = prev.get("lon")
            if all(isinstance(x, (int, float)) for x in [lat, lon, plat, plon]):
                hours = max(0.001, (ts - prev_ts).total_seconds() / 3600.0)
                dist = _haversine_km(float(plat), float(plon), float(lat), float(lon))
                speed = dist / hours
                if speed > 900.0:
                    score += 40
                    reasons.append("impossible_travel")

    if ip and ip.strip() and ip.strip() in bad_ips:
        score += 30
        reasons.append("ip_reputation_bad")

    if bool(payload.get("mfa_fatigue")):
        score += 25
        reasons.append("mfa_fatigue_signals")

    score = max(0, min(100, score))
    details = {
        "score": score,
        "reasons": reasons,
        "user": user,
        "ip": ip,
        "country": country,
        "success": success,
        "prev_context": {
            "country": prev.get("country") if prev else None,
            "ts": prev.get("ts").isoformat() if prev and isinstance(prev.get("ts"), datetime) else None,
        },
    }
    return score, details


def _periodicity_score(payload: dict) -> tuple[int, dict]:
    if bool(payload.get("periodic")):
        return 40, {"method": "flag", "periodic": True}

    intervals = payload.get("intervals")
    if isinstance(intervals, list) and len(intervals) >= 4:
        vals = [float(x) for x in intervals if isinstance(x, (int, float))]
        if len(vals) >= 4:
            mean = sum(vals) / len(vals)
            var = sum((x - mean) ** 2 for x in vals) / len(vals)
            std = math.sqrt(var)
            cv = (std / mean) if mean > 0 else 999.0
            periodic = (cv < 0.15) and (mean <= 600.0)
            return (40 if periodic else 0), {"method": "intervals", "mean": mean, "cv": cv, "periodic": periodic}

    timestamps = payload.get("timestamps")
    if isinstance(timestamps, list) and len(timestamps) >= 5:
        dts = [_parse_ts(str(x)) for x in timestamps]
        dts = [d for d in dts if isinstance(d, datetime)]
        dts.sort()
        if len(dts) >= 5:
            ints = [(dts[i] - dts[i - 1]).total_seconds() for i in range(1, len(dts))]
            if len(ints) >= 4:
                mean = sum(ints) / len(ints)
                var = sum((x - mean) ** 2 for x in ints) / len(ints)
                std = math.sqrt(var)
                cv = (std / mean) if mean > 0 else 999.0
                periodic = (cv < 0.15) and (mean <= 600.0)
                return (40 if periodic else 0), {"method": "timestamps", "mean": mean, "cv": cv, "periodic": periodic}

    return 0, {"method": "none", "periodic": False}


def _score_beacon(payload: dict, extracted: dict, rdap_results: dict) -> tuple[int, dict]:
    score = 0
    reasons: list[str] = []

    periodic_pts, periodic_details = _periodicity_score(payload)
    if periodic_pts:
        score += periodic_pts
        reasons.append("periodicity_detected")

    domain = (extracted.get("domains") or [None])[0]
    if domain:
        age = (rdap_results.get(domain) or {}).get("domain_age_days")
        if isinstance(age, int) and age >= 0 and age < 30:
            score += 20
            reasons.append("domain_age_lt_30d")

    hosts = extracted.get("hosts") or []
    if isinstance(hosts, list) and len(hosts) >= 3:
        score += 40
        reasons.append("multi_host_beacon")

    score = max(0, min(100, score))
    details = {
        "score": score,
        "reasons": reasons,
        "domain": domain,
        "dst_ip": (extracted.get("ips") or [None])[0],
        "hosts_count": len(hosts) if isinstance(hosts, list) else 0,
        "periodicity": periodic_details,
    }
    return score, details


def _read_blocklist() -> dict:
    if not BLOCKLIST_PATH.exists():
        return {"domains": [], "ips": []}
    try:
        return json.loads(BLOCKLIST_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"domains": [], "ips": []}


def _write_blocklist(data: dict) -> None:
    BLOCKLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    BLOCKLIST_PATH.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _block_domain(domain: str) -> dict:
    bl = _read_blocklist()
    domains = set([d.lower() for d in bl.get("domains", []) if isinstance(d, str)])
    domains.add(domain.lower())
    bl["domains"] = sorted(domains)
    if "ips" not in bl:
        bl["ips"] = []
    _write_blocklist(bl)
    return {"updated": True, "domain": domain, "blocklist_path": str(BLOCKLIST_PATH)}


def _block_ip(ip: str) -> dict:
    bl = _read_blocklist()
    ips = set([i for i in bl.get("ips", []) if isinstance(i, str)])
    ips.add(ip)
    bl["ips"] = sorted(ips)
    if "domains" not in bl:
        bl["domains"] = []
    _write_blocklist(bl)
    return {"updated": True, "ip": ip, "blocklist_path": str(BLOCKLIST_PATH)}


def _notify(message: str, meta: dict | None = None) -> dict:
    return {"notified": True, "message": message, "meta": meta or {}}


def _create_ticket_summary(case_id: str, severity: str, score: int) -> str:
    return f"[{severity.upper()}] Case {case_id} (score={score}) requires review"


@celery_app.task(name="run_action")
def run_action(case_id: str, action_type: str, params: dict | None = None):
    _ensure_tables()

    from sqlalchemy import Column
    from sqlalchemy.dialects.postgresql import JSONB
    from sqlmodel import Field

    class Case(SQLModel, table=True):
        __tablename__ = "cases"
        id: uuid.UUID = Field(primary_key=True)
        title: str
        type: str
        severity: str
        status: str
        score: int
        created_at: datetime
        updated_at: datetime

    class Action(SQLModel, table=True):
        __tablename__ = "actions"
        id: uuid.UUID = Field(primary_key=True)
        case_id: uuid.UUID
        action_type: str
        params: dict = Field(sa_column=Column(JSONB, nullable=False))
        started_at: datetime
        finished_at: datetime | None = None
        success: bool | None = None
        result: dict = Field(sa_column=Column(JSONB, nullable=False))

    class Ticket(SQLModel, table=True):
        __tablename__ = "tickets"
        id: uuid.UUID = Field(primary_key=True)
        case_id: uuid.UUID
        external_ref: str | None = None
        summary: str
        status: str
        created_at: datetime

    class TimelineEvent(SQLModel, table=True):
        __tablename__ = "timeline_events"
        id: uuid.UUID = Field(primary_key=True)
        case_id: uuid.UUID
        ts: datetime
        event_type: str
        message: str
        details: dict = Field(sa_column=Column(JSONB, nullable=False))

    cid = uuid.UUID(case_id)
    now = _now()
    params = params or {}

    with Session(engine) as session:
        case = session.exec(select(Case).where(Case.id == cid)).first()
        if not case:
            action_runs_total.labels(action_type=action_type, success="false").inc()
            _push_metrics()
            return {"ok": False, "error": "case not found"}

        action = Action(
            id=uuid.uuid4(),
            case_id=cid,
            action_type=action_type,
            params=params,
            started_at=now,
            finished_at=None,
            success=None,
            result={},
        )
        session.add(action)
        session.commit()
        session.refresh(action)

        ok = True
        result: dict = {}
        err: str | None = None

        try:
            if action_type == "block_domain":
                domain = (params.get("domain") or "").strip()
                if not domain:
                    raise ValueError("missing params.domain")
                result = _block_domain(domain)

            elif action_type == "block_ip":
                ip = (params.get("ip") or "").strip()
                if not ip:
                    raise ValueError("missing params.ip")
                result = _block_ip(ip)

            elif action_type == "notify":
                msg = (params.get("message") or "").strip()
                if not msg:
                    msg = f"Notification for case {case_id}"
                result = _notify(
                    msg,
                    meta={"case_id": case_id, "severity": case.severity, "score": case.score, "type": case.type},
                )

            elif action_type == "create_ticket":
                summary = (params.get("summary") or "").strip()
                if not summary:
                    summary = _create_ticket_summary(case_id, case.severity, case.score)
                ticket = Ticket(
                    id=uuid.uuid4(),
                    case_id=cid,
                    external_ref=None,
                    summary=summary,
                    status="open",
                    created_at=now,
                )
                session.add(ticket)
                session.commit()
                result = {"created": True, "ticket_id": str(ticket.id), "summary": summary}

            else:
                raise ValueError(f"unsupported action_type: {action_type}")

        except Exception as e:
            ok = False
            err = str(e)

        finished = _now()
        action.finished_at = finished
        action.success = ok
        action.result = result if ok else {"error": err, "params": params}
        session.add(action)

        session.add(
            TimelineEvent(
                id=uuid.uuid4(),
                case_id=cid,
                ts=finished,
                event_type="action",
                message=f"action {action_type} {'succeeded' if ok else 'failed'}",
                details={"action_id": str(action.id), "action_type": action_type, "success": ok, "result": action.result},
            )
        )

        session.commit()

    action_runs_total.labels(action_type=action_type, success="true" if ok else "false").inc()
    _push_metrics()

    return {"ok": ok, "action_id": str(action.id), "result": action.result}


@celery_app.task(name="process_alert")
def process_alert(alert_id: str):
    _ensure_tables()

    from sqlalchemy import Column
    from sqlalchemy.dialects.postgresql import JSONB
    from sqlmodel import Field

    class Alert(SQLModel, table=True):
        __tablename__ = "alerts"
        id: uuid.UUID = Field(primary_key=True)
        source: str
        received_at: datetime
        raw_payload: dict = Field(sa_column=Column(JSONB, nullable=False))
        dedup_hash: str
        status: str
        case_id: uuid.UUID | None = None

    class Case(SQLModel, table=True):
        __tablename__ = "cases"
        id: uuid.UUID = Field(primary_key=True)
        title: str
        type: str
        severity: str
        status: str
        score: int
        created_at: datetime
        updated_at: datetime

    class TimelineEvent(SQLModel, table=True):
        __tablename__ = "timeline_events"
        id: uuid.UUID = Field(primary_key=True)
        case_id: uuid.UUID
        ts: datetime
        event_type: str
        message: str
        details: dict = Field(sa_column=Column(JSONB, nullable=False))

    class Artifact(SQLModel, table=True):
        __tablename__ = "artifacts"
        id: uuid.UUID = Field(primary_key=True)
        case_id: uuid.UUID
        type: str
        value: str
        first_seen: datetime

    aid = uuid.UUID(alert_id)
    now = _now()

    extracted: dict = {}
    dns_results: dict = {}
    rdap_results: dict = {}
    score: int = 0

    with Session(engine) as session:
        alert = session.exec(select(Alert).where(Alert.id == aid)).first()
        if not alert:
            playbook_runs_total.labels(playbook="unknown", outcome="error").inc()
            _push_metrics()
            return {"ok": False, "error": "alert not found"}

        existing_case = session.exec(select(Case).where(Case.status == "open").where(Case.title == alert.dedup_hash)).first()

        if existing_case:
            case = existing_case
            created = False
        else:
            case_type = "unknown"
            if alert.source == "email":
                case_type = "phishing"
            elif alert.source == "auth":
                case_type = "login"
            elif alert.source == "network":
                case_type = "beacon"

            case = Case(
                id=uuid.uuid4(),
                title=alert.dedup_hash,
                type=case_type,
                severity="low",
                status="open",
                score=0,
                created_at=now,
                updated_at=now,
            )
            session.add(case)
            created = True

        alert.case_id = case.id
        alert.status = "processed"
        session.add(alert)

        session.add(
            TimelineEvent(
                id=uuid.uuid4(),
                case_id=case.id,
                ts=now,
                event_type="ingest",
                message="case created" if created else "alert attached to existing case",
                details={"alert_id": str(alert.id), "dedup_hash": alert.dedup_hash, "created": created, "source": alert.source},
            )
        )

        case_type = case.type

        if created:
            cases_created_total.labels(type=case_type).inc()

        if alert.source == "email":
            extracted = _extract_phishing(alert.raw_payload)

            for u in extracted["urls"]:
                session.add(Artifact(id=uuid.uuid4(), case_id=case.id, type="url", value=u, first_seen=now))
            for d in extracted["domains"]:
                session.add(Artifact(id=uuid.uuid4(), case_id=case.id, type="domain", value=d, first_seen=now))
            for e in extracted["emails"]:
                session.add(Artifact(id=uuid.uuid4(), case_id=case.id, type="email", value=e, first_seen=now))

            session.add(
                TimelineEvent(
                    id=uuid.uuid4(),
                    case_id=case.id,
                    ts=now,
                    event_type="extract",
                    message="extracted phishing artifacts",
                    details={"urls": extracted["urls"], "domains": extracted["domains"], "emails": extracted["emails"]},
                )
            )

            errors = []

            dns_start = time.perf_counter()
            for d in extracted["domains"]:
                try:
                    dns_results[d] = _dns_enrich(d)
                except Exception as e:
                    errors.append({"domain": d, "dns_error": str(e)})
            enrichment_latency_seconds.labels(enricher="dns").observe(time.perf_counter() - dns_start)

            rdap_start = time.perf_counter()
            for d in extracted["domains"]:
                try:
                    rdap_results[d] = _rdap_domain(d)
                except Exception as e:
                    errors.append({"domain": d, "rdap_error": str(e)})
            enrichment_latency_seconds.labels(enricher="rdap").observe(time.perf_counter() - rdap_start)

            session.add(
                TimelineEvent(
                    id=uuid.uuid4(),
                    case_id=case.id,
                    ts=now,
                    event_type="enrich",
                    message="phishing enrichment completed",
                    details={"dns": dns_results, "rdap": rdap_results, "errors": errors},
                )
            )

            score, score_details = _score_phishing(alert.raw_payload, extracted, dns_results, rdap_results)
            case.score = score
            case.severity = _severity_from_score(score)
            case.updated_at = now
            session.add(case)

            session.add(
                TimelineEvent(
                    id=uuid.uuid4(),
                    case_id=case.id,
                    ts=now,
                    event_type="score",
                    message="scored phishing case",
                    details={**score_details, "severity": case.severity},
                )
            )

            playbook_runs_total.labels(playbook="phishing_v1", outcome="ok").inc()

        elif alert.source == "auth":
            extracted = _extract_login(alert.raw_payload)

            user = (extracted.get("users") or [""])[0]
            ip = (extracted.get("ips") or [""])[0]
            ua = (extracted.get("user_agents") or [""])[0]
            country = (extracted.get("countries") or [""])[0] if extracted.get("countries") else None
            city = (extracted.get("cities") or [""])[0] if extracted.get("cities") else None

            if user:
                session.add(Artifact(id=uuid.uuid4(), case_id=case.id, type="user", value=user, first_seen=now))
            if ip:
                session.add(Artifact(id=uuid.uuid4(), case_id=case.id, type="ip", value=ip, first_seen=now))
            if ua:
                session.add(Artifact(id=uuid.uuid4(), case_id=case.id, type="user_agent", value=ua, first_seen=now))
            if country:
                session.add(Artifact(id=uuid.uuid4(), case_id=case.id, type="country", value=country, first_seen=now))
            if city:
                session.add(Artifact(id=uuid.uuid4(), case_id=case.id, type="city", value=city, first_seen=now))

            session.add(
                TimelineEvent(
                    id=uuid.uuid4(),
                    case_id=case.id,
                    ts=now,
                    event_type="extract",
                    message="extracted login artifacts",
                    details={"user": user, "ip": ip, "user_agent": ua, "country": country, "city": city},
                )
            )

            bad_ips = _load_set(THREATFEED_IPS_PATH)
            ip_rep = {"ip": ip, "bad": bool(ip and ip in bad_ips)}

            prev_ctx = None
            if user:
                rows = session.exec(select(TimelineEvent).where(TimelineEvent.event_type == "login_context").order_by(TimelineEvent.ts.desc())).all()
                for r in rows[:200]:
                    try:
                        if (r.details or {}).get("user") == user:
                            prev_ts = _parse_ts((r.details or {}).get("ts"))
                            prev_ctx = {
                                "user": user,
                                "ip": (r.details or {}).get("ip"),
                                "country": (r.details or {}).get("country"),
                                "lat": (r.details or {}).get("lat"),
                                "lon": (r.details or {}).get("lon"),
                                "ts": prev_ts,
                            }
                            break
                    except Exception:
                        continue

            session.add(
                TimelineEvent(
                    id=uuid.uuid4(),
                    case_id=case.id,
                    ts=now,
                    event_type="enrich",
                    message="login enrichment completed",
                    details={"ip_reputation": ip_rep, "prev_context_found": bool(prev_ctx)},
                )
            )

            success = bool(alert.raw_payload.get("success", True))
            score, score_details = _score_login(alert.raw_payload, user, ip, success, country, prev_ctx)
            case.score = score
            case.severity = _severity_from_score(score)
            case.updated_at = now
            session.add(case)

            session.add(
                TimelineEvent(
                    id=uuid.uuid4(),
                    case_id=case.id,
                    ts=now,
                    event_type="score",
                    message="scored login case",
                    details={**score_details, "severity": case.severity},
                )
            )

            session.add(
                TimelineEvent(
                    id=uuid.uuid4(),
                    case_id=case.id,
                    ts=now,
                    event_type="login_context",
                    message="login context saved",
                    details={
                        "user": user,
                        "ip": ip,
                        "country": country,
                        "city": city,
                        "lat": alert.raw_payload.get("lat"),
                        "lon": alert.raw_payload.get("lon"),
                        "ts": (alert.raw_payload.get("ts") or now.isoformat()),
                    },
                )
            )

            playbook_runs_total.labels(playbook="suspicious_login_v1", outcome="ok").inc()

        elif alert.source == "network":
            extracted = _extract_beacon(alert.raw_payload)

            domain = (extracted.get("domains") or [""])[0]
            ip = (extracted.get("ips") or [""])[0]
            hosts = extracted.get("hosts") or []

            if domain:
                session.add(Artifact(id=uuid.uuid4(), case_id=case.id, type="domain", value=domain, first_seen=now))
            if ip:
                session.add(Artifact(id=uuid.uuid4(), case_id=case.id, type="ip", value=ip, first_seen=now))
            for h in hosts:
                session.add(Artifact(id=uuid.uuid4(), case_id=case.id, type="host", value=h, first_seen=now))

            session.add(
                TimelineEvent(
                    id=uuid.uuid4(),
                    case_id=case.id,
                    ts=now,
                    event_type="extract",
                    message="extracted beacon artifacts",
                    details={"dst_domain": domain, "dst_ip": ip, "hosts": hosts},
                )
            )

            errors = []
            if domain:
                dns_start = time.perf_counter()
                try:
                    dns_results[domain] = _dns_enrich(domain)
                except Exception as e:
                    errors.append({"domain": domain, "dns_error": str(e)})
                enrichment_latency_seconds.labels(enricher="dns").observe(time.perf_counter() - dns_start)

                rdap_start = time.perf_counter()
                try:
                    rdap_results[domain] = _rdap_domain(domain)
                except Exception as e:
                    errors.append({"domain": domain, "rdap_error": str(e)})
                enrichment_latency_seconds.labels(enricher="rdap").observe(time.perf_counter() - rdap_start)

            session.add(
                TimelineEvent(
                    id=uuid.uuid4(),
                    case_id=case.id,
                    ts=now,
                    event_type="enrich",
                    message="beacon enrichment completed",
                    details={"dns": dns_results, "rdap": rdap_results, "errors": errors},
                )
            )

            score, score_details = _score_beacon(alert.raw_payload, extracted, rdap_results)
            case.score = score
            case.severity = _severity_from_score(score)
            case.updated_at = now
            session.add(case)

            session.add(
                TimelineEvent(
                    id=uuid.uuid4(),
                    case_id=case.id,
                    ts=now,
                    event_type="score",
                    message="scored beacon case",
                    details={**score_details, "severity": case.severity},
                )
            )

            playbook_runs_total.labels(playbook="beacon_v1", outcome="ok").inc()

        session.commit()

        case_id_str = str(case.id)
        severity = case.severity
        case_type = case.type

    _push_metrics()

    if case_type == "phishing" and severity in ("high", "critical"):
        for d in (extracted.get("domains") or []):
            celery_app.send_task("run_action", args=[case_id_str, "block_domain", {"domain": d}])
        celery_app.send_task("run_action", args=[case_id_str, "create_ticket", {}])
        celery_app.send_task(
            "run_action",
            args=[case_id_str, "notify", {"message": f"Auto-response: phishing case {case_id_str} severity={severity} score={score}"}],
        )

    if case_type == "login" and severity in ("high", "critical"):
        celery_app.send_task("run_action", args=[case_id_str, "create_ticket", {}])
        celery_app.send_task(
            "run_action",
            args=[case_id_str, "notify", {"message": f"Auto-response: suspicious login case {case_id_str} severity={severity} score={score}"}],
        )

    if case_type == "beacon" and severity in ("high", "critical"):
        for d in (extracted.get("domains") or []):
            celery_app.send_task("run_action", args=[case_id_str, "block_domain", {"domain": d}])
        for ip in (extracted.get("ips") or []):
            celery_app.send_task("run_action", args=[case_id_str, "block_ip", {"ip": ip}])
        celery_app.send_task("run_action", args=[case_id_str, "create_ticket", {}])
        celery_app.send_task(
            "run_action",
            args=[case_id_str, "notify", {"message": f"Auto-response: beacon case {case_id_str} severity={severity} score={score}"}],
        )

    return {"ok": True, "case_id": case_id_str}