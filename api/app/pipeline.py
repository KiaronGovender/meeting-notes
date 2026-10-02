from .db import SessionLocal
from .models import Meeting, Segment
from .providers.transcriber import AssemblyAITranscriber


def process_recording(meeting_id: int, media_url: str) -> None:
    db = SessionLocal()
    try:
        m = db.get(Meeting, meeting_id)
        m.media_url = None  # presigned URLs expire; media is fetched fresh via /meetings/{id}/media
        m.status = "processing"
        db.commit()
        segs = AssemblyAITranscriber().transcribe(media_url)
        db.query(Segment).filter_by(meeting_id=meeting_id).delete()
        db.add_all(Segment(meeting_id=meeting_id, **s) for s in segs)
        m.duration_ms = segs[-1]["end_ms"] if segs else None
        m.status = "done"  # next: summary + action items (task 7)
        db.commit()
    except Exception:
        db.rollback()
        m = db.get(Meeting, meeting_id)
        m.status = "failed"
        db.commit()
        raise
    finally:
        db.close()
