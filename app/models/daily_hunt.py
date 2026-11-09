
from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, DateTime, Text

from app.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class DailyHunt(Base):
    __tablename__ = "daily_hunts"

    id = Column(Integer, primary_key=True, index=True)

    hunt_date = Column(
        String(20),
        unique=True,
        nullable=False,
        index=True
    )

    status = Column(
        String(30),
        nullable=False,
        default="running"
    )

    started_at = Column(
        DateTime(timezone=True),
        nullable=False
    )

    ends_at = Column(
        DateTime(timezone=True),
        nullable=False
    )

    completed_at = Column(
        DateTime(timezone=True),
        nullable=True
    )

    reset_at = Column(
        DateTime(timezone=True),
        nullable=True
    )

    total_clips = Column(
        Integer,
        nullable=False,
        default=0
    )

    top_clip_ids = Column(
        Text,
        nullable=True
    )
