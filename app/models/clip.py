
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    Text,
    UniqueConstraint,
    Index
)

from app.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class Clip(Base):

    __tablename__ = "clips"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    # Source information
    platform = Column(
        String(30),
        nullable=False
    )

    external_id = Column(
        String(255),
        nullable=False
    )

    # Content information
    title = Column(
        String(500),
        nullable=False
    )

    creator = Column(
        String(255),
        nullable=True
    )

    url = Column(
        Text,
        nullable=False
    )

    thumbnail_url = Column(
        Text,
        nullable=True
    )

    # Engagement metrics
    views = Column(
        Integer,
        default=0,
        nullable=False
    )

    likes = Column(
        Integer,
        nullable=True
    )

    comments = Column(
        Integer,
        nullable=True
    )

    duration = Column(
        Float,
        default=0
    )

    # Dates
    created_at = Column(
        DateTime(timezone=True),
        nullable=True
    )

    discovered_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False
    )

    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now
    )

    # AI scoring
    viral_score = Column(
        Float,
        default=0,
        nullable=False
    )

    status = Column(
        String(30),
        default="discovered",
        nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "platform",
            "external_id",
            name="uq_platform_external_id"
        ),
        Index("ix_clips_viral_score", "viral_score"),
        Index("ix_clips_status", "status"),
    )
