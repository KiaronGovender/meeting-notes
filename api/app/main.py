from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import Base, engine
from .routes import highlights, meetings, summaries, webhooks

app = FastAPI(title="Notetaker API")
app.add_middleware(
    CORSMiddleware, allow_origins=[o.strip() for o in settings.frontend_origin.split(",")]
)


@app.on_event("startup")
def init_db():
    Base.metadata.create_all(engine)  # swap for Alembic if time allows


@app.get("/health")
def health():
    return {"ok": True}


app.include_router(meetings.router)
app.include_router(summaries.router)
app.include_router(webhooks.router)
app.include_router(highlights.router)
