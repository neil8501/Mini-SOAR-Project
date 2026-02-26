import uuid
from datetime import datetime, timezone

from sqlmodel import Session

from app.core.config import settings
from app.db.session import get_session
from app.models.case import Case


def test_close_case_generates_report(client):
    # create a case directly in sqlite test DB
    dep = list(client.app.dependency_overrides.values())[0]
    gen = dep()
    session: Session = next(gen)

    cid = uuid.uuid4()
    now = datetime.now(timezone.utc)
    case = Case(
        id=cid,
        title="test",
        type="phishing",
        severity="low",
        status="open",
        score=10,
        created_at=now,
        updated_at=now,
    )
    session.add(case)
    session.commit()

    # close (requires admin header)
    r = client.post(f"/cases/{cid}/close", headers={"X-Admin-Key": settings.admin_api_key})
    assert r.status_code == 200
    body = r.json()
    assert body["closed"] is True
    assert body["report"]["markdown_path"] is not None
    assert "Incident Report" in body["markdown_preview"]
