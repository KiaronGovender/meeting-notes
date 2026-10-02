from fastapi import APIRouter, Depends, HTTPException
from fastapi import BackgroundTasks
from ..pipeline import process_recording
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Meeting, ShareLink
from ..providers import bot
from ..providers.bot import map_status
from .highlights import serialize_highlight
from ..config import settings

router = APIRouter(prefix="/meetings", tags=["meetings"])


class MeetingIn(BaseModel):
    meeting_url: str
    title: str = "Untitled meeting"


def serialize(m: Meeting, full: bool = False) -> dict:
    d = {
        "id": m.id, "title": m.title, "status": m.status, "meeting_url": m.meeting_url,
        "media_url": m.media_url, "duration_ms": m.duration_ms, "created_at": m.created_at,
    }
    if full:
        d["segments"] = [
            {"id": s.id, "speaker": s.speaker, "start_ms": s.start_ms, "end_ms": s.end_ms, "text": s.text}
            for s in m.segments
        ]
        d["highlights"] = [serialize_highlight(h) for h in sorted(m.highlights, key=lambda h: h.start_ms)]
    return d


@router.post("")
def create_meeting(body: MeetingIn, db: Session = Depends(get_db)):
    if settings.read_only:
        raise HTTPException(403, "This demo is read-only")
    m = Meeting(title=body.title, meeting_url=body.meeting_url)
    db.add(m)
    db.flush()
    try:
        m.bot_id = bot.send_bot(body.meeting_url, m.id)
        m.status = "joining"
    except Exception as e:
        m.status = "failed"
        db.commit()
        raise HTTPException(502, f"Could not dispatch bot: {e}")
    db.commit()
    return serialize(m)


@router.get("")
def list_meetings(db: Session = Depends(get_db)):
    rows = db.scalars(select(Meeting).order_by(Meeting.created_at.desc())).all()
    return [serialize(m) for m in rows]


@router.get("/{meeting_id}")
def get_meeting(meeting_id: int, bg: BackgroundTasks, db: Session = Depends(get_db)):
    m = db.get(Meeting, meeting_id)
    if not m:
        raise HTTPException(404, "Meeting not found")
    # Reconcile with Meeting BaaS: don't rely only on the callback.
    if m.bot_id and m.status in ("joining", "recording", "processing"):
        try:
            d = bot.get_bot(m.bot_id)
            code = d.get("status", "")
            media = d.get("audio") or d.get("video")
            if code == "completed" and media:
                m.status = "transcribing"
                if d.get("duration_seconds"):
                    m.duration_ms = int(d["duration_seconds"] * 1000)
                db.commit()
                bg.add_task(process_recording, m.id, media)
            else:
                m.status = map_status(code)
                db.commit()
        except Exception:
            pass
    return serialize(m, full=True)


@router.get("/{meeting_id}/media")
def get_media(meeting_id: int, db: Session = Depends(get_db)):
    """Presigned URLs expire after ~4h, so fetch fresh ones for bot recordings."""
    m = db.get(Meeting, meeting_id)
    if not m:
        raise HTTPException(404, "Meeting not found")
    if m.media_url:  # imported recordings
        return {"video": None, "audio": m.media_url}
    if not m.bot_id:
        raise HTTPException(404, "No recording")
    d = bot.get_bot(m.bot_id)
    return {"video": d.get("video"), "audio": d.get("audio")}

@router.delete("/{meeting_id}")
def delete_meeting(meeting_id: int, db: Session = Depends(get_db)):
    if settings.read_only:
        raise HTTPException(403, "This demo is read-only")
    m = db.get(Meeting, meeting_id)
    if not m:
        raise HTTPException(404, "Meeting not found")
    # Segments, summaries, action items and highlights cascade; share links do not.
    db.query(ShareLink).filter_by(meeting_id=meeting_id).delete()
    db.delete(m)
    db.commit()
    return {"ok": True}