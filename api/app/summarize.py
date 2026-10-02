"""Chunked (map-reduce) summaries so an hour-long, 8-person call fits a small local model.

map:    each ~10k-char transcript chunk -> key points, decisions, topics, action items (with timestamps)
reduce: merged notes -> one template-specific summary (cheap, so switching templates is fast)
Notes are cached as Summary(template="_notes"); action items are stored once per meeting.
"""
import json
import re
import threading
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import ActionItem, Meeting, Summary
from .providers.llm import get_llm

CHUNK_CHARS = 10_000
NOTES_CAP = 12_000

TEMPLATES = {
    "general": ("General", "Sections: Key points, Decisions, Topics discussed."),
    "sales": ("Sales call", "Sections: Customer needs and pain points, Objections, Buying signals, Next steps."),
    "one_on_one": ("1:1", "Sections: Wins, Blockers, Feedback, Follow-ups."),
    "standup": ("Standup", "Sections: Done, In progress, Blockers."),
}

_locks: dict[int, threading.Lock] = defaultdict(threading.Lock)

GROUND = "Use ONLY information in the transcript. Never invent names, numbers or tasks. If nothing applies, return empty lists. Reply with JSON only."


def _fmt(ms: int) -> str:
    s = ms // 1000
    h, m, sec = s // 3600, (s % 3600) // 60, s % 60
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def _parse_ts(value) -> int | None:
    nums = [int(n) for n in re.findall(r"\d+", str(value or ""))[:3]]
    if not nums:
        return None
    secs = 0
    for n in nums:
        secs = secs * 60 + n
    return secs * 1000


def _chunks(meeting: Meeting) -> list[str]:
    out, cur, size = [], [], 0
    for s in meeting.segments:
        line = f"[{_fmt(s.start_ms)}] {s.speaker}: {s.text}"
        if size + len(line) > CHUNK_CHARS and cur:
            out.append("\n".join(cur))
            cur, size = [], 0
        cur.append(line)
        size += len(line) + 1
    if cur:
        out.append("\n".join(cur))
    return out


def _strs(v) -> list[str]:
    return [str(x).strip() for x in v if str(x).strip()] if isinstance(v, list) else []


def _map_chunk(llm, chunk: str) -> dict:
    system = (
        "You take notes on one part of a meeting transcript. Lines look like '[mm:ss] Speaker: text'. " + GROUND
    )
    user = (
        'Return {"key_points": [str], "decisions": [str], "topics": [str], '
        '"action_items": [{"text": str, "owner": str or null, "time": "mm:ss copied from the line where it was assigned"}]}.'
        " Action items are concrete tasks someone committed to or was asked to do.\n\nTRANSCRIPT:\n" + chunk
    )
    return llm.complete_json(system, user)


def _ensure_notes(db: Session, m: Meeting) -> list[dict]:
    row = db.scalar(select(Summary).where(Summary.meeting_id == m.id, Summary.template == "_notes"))
    if row:
        return row.content["chunks"]
    llm = get_llm()
    notes = [_map_chunk(llm, c) for c in _chunks(m)]
    db.add(Summary(meeting_id=m.id, template="_notes", content={"chunks": notes}))

    seen = set()
    for n in notes:
        for it in n.get("action_items") or []:
            if not isinstance(it, dict) or not str(it.get("text", "")).strip():
                continue
            text = str(it["text"]).strip()
            key = re.sub(r"\W+", " ", text.lower()).strip()[:60]
            if key in seen:
                continue
            seen.add(key)
            owner = it.get("owner")
            db.add(ActionItem(
                meeting_id=m.id, text=text, at_ms=_parse_ts(it.get("time")),
                owner=str(owner).strip() if owner and str(owner).lower() != "null" else None,
            ))
    db.commit()
    return notes


def _reduce(template: str, notes: list[dict]) -> dict:
    merged = {
        "key_points": [p for n in notes for p in _strs(n.get("key_points"))],
        "decisions": [p for n in notes for p in _strs(n.get("decisions"))],
        "topics": [p for n in notes for p in _strs(n.get("topics"))],
        "action_items": [str(i.get("text")) for n in notes for i in (n.get("action_items") or []) if isinstance(i, dict)],
    }
    blob = json.dumps(merged)[:NOTES_CAP]
    label, guide = TEMPLATES[template]
    system = f"You write a '{label}' meeting summary from notes taken on a transcript. " + GROUND
    user = (
        'Return {"overview": "2-3 sentence summary", "sections": [{"title": str, "items": [str]}]}. '
        f"{guide} Keep items short; omit empty sections.\n\nNOTES:\n{blob}"
    )
    out = get_llm().complete_json(system, user)
    sections = [
        {"title": str(s.get("title", "")).strip(), "items": _strs(s.get("items"))}
        for s in out.get("sections") or [] if isinstance(s, dict)
    ]
    return {"overview": str(out.get("overview", "")).strip(), "sections": [s for s in sections if s["items"]]}


def _items(db: Session, meeting_id: int) -> list[dict]:
    rows = db.scalars(select(ActionItem).where(ActionItem.meeting_id == meeting_id).order_by(ActionItem.at_ms)).all()
    return [{"id": a.id, "text": a.text, "owner": a.owner, "at_ms": a.at_ms, "done": a.done} for a in rows]


def get_or_create_summary(db: Session, meeting_id: int, template: str, force: bool = False) -> dict:
    with _locks[meeting_id]:  # one generation per meeting at a time
        m = db.get(Meeting, meeting_id)
        if not m:
            raise LookupError("Meeting not found")
        if not m.segments:
            raise ValueError("No transcript yet")
        if force:
            db.query(Summary).filter(Summary.meeting_id == meeting_id, Summary.template.in_([template, "_notes"])).delete(synchronize_session=False)
            db.query(ActionItem).filter_by(meeting_id=meeting_id).delete()
            db.commit()
        row = db.scalar(select(Summary).where(Summary.meeting_id == meeting_id, Summary.template == template))
        if not row:
            row = Summary(meeting_id=meeting_id, template=template, content=_reduce(template, _ensure_notes(db, m)))
            db.add(row)
            db.commit()
        return {"template": template, "content": row.content, "action_items": _items(db, meeting_id)}