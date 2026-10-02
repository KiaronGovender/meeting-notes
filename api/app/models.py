import secrets
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class Meeting(Base):
    __tablename__ = "meetings"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), default="Untitled meeting")
    meeting_url: Mapped[str | None] = mapped_column(String(500))
    bot_id: Mapped[str | None] = mapped_column(String(100), index=True)
    # scheduled | joining | recording | processing | done | failed
    status: Mapped[str] = mapped_column(String(20), default="scheduled")
    media_url: Mapped[str | None] = mapped_column(Text)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    segments: Mapped[list["Segment"]] = relationship(
        back_populates="meeting", order_by="Segment.start_ms", cascade="all, delete-orphan"
    )
    summaries: Mapped[list["Summary"]] = relationship(cascade="all, delete-orphan")
    action_items: Mapped[list["ActionItem"]] = relationship(cascade="all, delete-orphan")
    highlights: Mapped[list["Highlight"]] = relationship(cascade="all, delete-orphan")


class Segment(Base):
    __tablename__ = "segments"
    id: Mapped[int] = mapped_column(primary_key=True)
    meeting_id: Mapped[int] = mapped_column(ForeignKey("meetings.id"), index=True)
    speaker: Mapped[str] = mapped_column(String(100), default="Speaker")
    start_ms: Mapped[int] = mapped_column(Integer)
    end_ms: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    meeting: Mapped[Meeting] = relationship(back_populates="segments")


class Summary(Base):
    __tablename__ = "summaries"
    id: Mapped[int] = mapped_column(primary_key=True)
    meeting_id: Mapped[int] = mapped_column(ForeignKey("meetings.id"), index=True)
    template: Mapped[str] = mapped_column(String(50))  # general | sales | one_on_one | standup
    content: Mapped[dict] = mapped_column(JSON)


class ActionItem(Base):
    __tablename__ = "action_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    meeting_id: Mapped[int] = mapped_column(ForeignKey("meetings.id"), index=True)
    text: Mapped[str] = mapped_column(Text)
    owner: Mapped[str | None] = mapped_column(String(100))
    at_ms: Mapped[int | None] = mapped_column(Integer)
    done: Mapped[bool] = mapped_column(default=False)


class Highlight(Base):
    __tablename__ = "highlights"
    id: Mapped[int] = mapped_column(primary_key=True)
    meeting_id: Mapped[int] = mapped_column(ForeignKey("meetings.id"), index=True)
    start_ms: Mapped[int] = mapped_column(Integer)
    end_ms: Mapped[int | None] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(Text)


class ShareLink(Base):
    __tablename__ = "share_links"
    id: Mapped[int] = mapped_column(primary_key=True)
    meeting_id: Mapped[int] = mapped_column(ForeignKey("meetings.id"), index=True)
    token: Mapped[str] = mapped_column(String(40), unique=True, default=lambda: secrets.token_urlsafe(16))
    start_ms: Mapped[int | None] = mapped_column(Integer)  # set both for a clip
    end_ms: Mapped[int | None] = mapped_column(Integer)
