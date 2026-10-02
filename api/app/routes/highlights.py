from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Highlight, Meeting

router = APIRouter(tags=["highlights"])


class HighlightIn(BaseModel):
    start_ms: int
    end_ms: int | None = None
    note: str | None = None


class HighlightPatch(BaseModel):
    note: str | None = None


def serialize_highlight(h: Highlight) -> dict:
    return {"id": h.id, "start_ms": h.start_ms, "end_ms": h.end_ms, "note": h.note}


@router.post("/meetings/{meeting_id}/highlights")
def create_highlight(meeting_id: int, body: HighlightIn, db: Session = Depends(get_db)):
    if not db.get(Meeting, meeting_id):
        raise HTTPException(404, "Meeting not found")
    if body.start_ms < 0 or (body.end_ms is not None and body.end_ms <= body.start_ms):
        raise HTTPException(422, "Invalid time range")
    h = Highlight(meeting_id=meeting_id, start_ms=body.start_ms, end_ms=body.end_ms, note=(body.note or "").strip() or None)
    db.add(h)
    db.commit()
    return serialize_highlight(h)


@router.patch("/highlights/{highlight_id}")
def update_highlight(highlight_id: int, body: HighlightPatch, db: Session = Depends(get_db)):
    h = db.get(Highlight, highlight_id)
    if not h:
        raise HTTPException(404, "Highlight not found")
    h.note = (body.note or "").strip() or None
    db.commit()
    return serialize_highlight(h)


@router.delete("/highlights/{highlight_id}")
def delete_highlight(highlight_id: int, db: Session = Depends(get_db)):
    h = db.get(Highlight, highlight_id)
    if not h:
        raise HTTPException(404, "Highlight not found")
    db.delete(h)
    db.commit()
    return {"ok": True}