from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..summarize import TEMPLATES, get_or_create_summary

router = APIRouter(prefix="/meetings", tags=["summaries"])


class SummaryIn(BaseModel):
    template: str = "general"
    force: bool = False


@router.get("/templates/list")
def templates():
    return [{"id": k, "label": v[0]} for k, v in TEMPLATES.items()]


@router.post("/{meeting_id}/summary")
def summary(meeting_id: int, body: SummaryIn, db: Session = Depends(get_db)):
    if body.template not in TEMPLATES:
        raise HTTPException(400, f"Unknown template: {body.template}")
    try:
        return get_or_create_summary(db, meeting_id, body.template, body.force)
    except LookupError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(409, str(e))
    except Exception as e:  # LLM unreachable, bad JSON, ...
        db.rollback()
        raise HTTPException(502, f"Summary failed: {e}")