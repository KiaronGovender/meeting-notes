import hmac

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import Meeting
from ..pipeline import process_recording

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/meetingbaas")
async def meetingbaas(
    request: Request,
    bg: BackgroundTasks,
    x_mb_secret: str = Header(default=""),
    db: Session = Depends(get_db),
):
    # Per-bot callback: Meeting BaaS sends our secret back in x-mb-secret.
    if not hmac.compare_digest(x_mb_secret, settings.webhook_secret):
        raise HTTPException(401, "bad secret")
    payload = await request.json()
    event, data = payload.get("event"), payload.get("data", {})

    m = db.scalar(select(Meeting).where(Meeting.bot_id == data.get("bot_id")))
    if not m and (data.get("extra") or {}).get("meeting_id"):
        m = db.get(Meeting, data["extra"]["meeting_id"])
    if not m:
        return {"ok": True, "ignored": "unknown bot"}

    if event == "bot.completed":
        media = data.get("audio") or data.get("mp4")
        # Idempotent: callbacks can be delivered more than once.
        if media and m.status not in ("transcribing", "done"):
            m.status = "transcribing"
            m.bot_id = m.bot_id or data.get("bot_id")
            if data.get("duration_seconds"):
                m.duration_ms = int(data["duration_seconds"] * 1000)
            db.commit()
            bg.add_task(process_recording, m.id, media)
    elif event == "bot.failed":
        m.status = "failed"
        db.commit()
    return {"ok": True}  # must be 2xx within 30s, otherwise it is retried
