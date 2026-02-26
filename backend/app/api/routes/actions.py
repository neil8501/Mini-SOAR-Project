import uuid
from typing import Any, Optional

from celery import Celery
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter(tags=["actions"])

celery_app = Celery(
    "mini_soar_api",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)


class ActionRequest(BaseModel):
    params: dict[str, Any] = {}


def _require_admin_key(x_admin_key: Optional[str]) -> None:
    if not x_admin_key or x_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=401, detail="Invalid admin key")


@router.post("/cases/{case_id}/actions/{action_type}", status_code=202)
def trigger_action(
    case_id: uuid.UUID,
    action_type: str,
    body: ActionRequest,
    x_admin_key: Optional[str] = Header(default=None),
):
    _require_admin_key(x_admin_key)

    # enqueue async action
    res = celery_app.send_task("run_action", args=[str(case_id), action_type, body.params])
    # celery returns a task id; action_id is created in worker and returned in result later
    return {"queued": True, "task_id": res.id}
