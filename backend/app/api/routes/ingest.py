import hashlib
import json
import time
from typing import Any, Optional

from celery import Celery
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlmodel import Session

from app.core.config import settings
from app.db.session import get_session
from app.metrics.prometheus import alerts_received_total, webhook_db_write_latency_seconds, webhook_requests_total
from app.models.alert import Alert

router = APIRouter(tags=["ingest"])

celery_app = Celery(
    "mini_soar_api",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)


def _stable_hash(source: str, payload: Any) -> str:
    blob = json.dumps({"source": source, "payload": payload}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _require_webhook_key(x_api_key: Optional[str]) -> None:
    if not x_api_key or x_api_key != settings.webhook_api_key:
        raise HTTPException(status_code=401, detail="Invalid webhook API key")


def _store_alert(session: Session, source: str, payload: dict) -> Alert:
    start = time.perf_counter()
    dedup_hash = _stable_hash(source, payload)
    alert = Alert(source=source, raw_payload=payload, dedup_hash=dedup_hash, status="new")
    session.add(alert)
    session.commit()
    session.refresh(alert)
    webhook_db_write_latency_seconds.labels(source=source).observe(time.perf_counter() - start)
    return alert


@router.post("/webhook/email", status_code=202)
def webhook_email(
    payload: dict,
    session: Session = Depends(get_session),
    x_api_key: Optional[str] = Header(default=None),
):
    _require_webhook_key(x_api_key)
    source = "email"
    alerts_received_total.labels(source=source).inc()
    webhook_requests_total.labels(source=source).inc()
    alert = _store_alert(session, source, payload)
    celery_app.send_task("process_alert", args=[str(alert.id)])
    return {"alert_id": str(alert.id), "case_id": None}


@router.post("/webhook/auth", status_code=202)
def webhook_auth(
    payload: dict,
    session: Session = Depends(get_session),
    x_api_key: Optional[str] = Header(default=None),
):
    _require_webhook_key(x_api_key)
    source = "auth"
    alerts_received_total.labels(source=source).inc()
    webhook_requests_total.labels(source=source).inc()
    alert = _store_alert(session, source, payload)
    celery_app.send_task("process_alert", args=[str(alert.id)])
    return {"alert_id": str(alert.id), "case_id": None}


@router.post("/webhook/network", status_code=202)
def webhook_network(
    payload: dict,
    session: Session = Depends(get_session),
    x_api_key: Optional[str] = Header(default=None),
):
    _require_webhook_key(x_api_key)
    source = "network"
    alerts_received_total.labels(source=source).inc()
    webhook_requests_total.labels(source=source).inc()
    alert = _store_alert(session, source, payload)
    celery_app.send_task("process_alert", args=[str(alert.id)])
    return {"alert_id": str(alert.id), "case_id": None}
