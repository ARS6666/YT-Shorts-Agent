from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    Integer,
    DateTime,
    ForeignKey,
    Index
)

from app.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class ClipMetricSnapshot(Base):
    __tablename__ = "clip_metric_snapshots"

    id = Column(Integer, primary_key=True, index=True)

    clip_id = Column(
        Integer,
        ForeignKey("clips.id"),
        nullable=False,
        index=True
    )

    views = Column(Integer, nullable=False, default=0)
    likes = Column(Integer, nullable=False, default=0)
    comments = Column(Integer, nullable=False, default=0)

    captured_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        index=True
    )

    __table_args__ = (
        Index(
            "ix_clip_metrics_clip_time",
            "clip_id",
            "captured_at"
        ),
    )