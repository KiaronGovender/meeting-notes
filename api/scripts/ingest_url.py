import sys

from app.db import Base, SessionLocal, engine
from app.models import Meeting
from app.pipeline import process_recording

url = sys.argv[1]
title = sys.argv[2] if len(sys.argv) > 2 else "Imported meeting"

Base.metadata.create_all(engine)
db = SessionLocal()
m = Meeting(title=title, status="processing")
db.add(m)
db.commit()
print(f"Meeting {m.id} created, transcribing (a long file can take several minutes)...")

process_recording(m.id, url)  # runs AssemblyAI and stores the segments

db.refresh(m)
m.media_url = url  # keep the link so playback works
db.commit()
print(f"Done: status={m.status}. Open http://localhost:3000/meetings/{m.id}")