
from datetime import datetime, timezone

from sqlalchemy import (
    Column, Integer, String, DateTime, Index,
    Boolean, Text, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import relationship

from app.database import Base


class StreamerSnapshot(Base):
    __tablename__ = "streamer_snapshots"

    id = Column(Integer, primary_key=True, index=True)

    platform = Column(String(20), nullable=False, default="kick")
    broadcaster = Column(String(150), nullable=False, index=True)

    title = Column(String(500), nullable=True)
    category = Column(String(150), nullable=True)

    viewer_count = Column(Integer, nullable=False, default=0)

    captured_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )


Index(
    "ix_streamer_platform_broadcaster_time",
    StreamerSnapshot.platform,
    StreamerSnapshot.broadcaster,
    StreamerSnapshot.captured_at,
)
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Text,
    ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

def utc_now():
    return datetime.now(timezone.utc)


class Streamer(Base):
    __tablename__ = "streamers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    slug = Column(String(150), unique=True, nullable=False, index=True)
    priority = Column(Integer, nullable=False, default=5)
    is_active = Column(Boolean, nullable=False, default=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    accounts = relationship(
        "StreamerAccount",
        back_populates="streamer",
        cascade="all, delete-orphan"
    )


class StreamerAccount(Base):
    __tablename__ = "streamer_accounts"

    id = Column(Integer, primary_key=True, index=True)
    streamer_id = Column(
        Integer,
        ForeignKey("streamers.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    platform = Column(String(20), nullable=False)
    username = Column(String(150), nullable=False)
    external_id = Column(String(150), nullable=True)
    profile_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)

    streamer = relationship("Streamer", back_populates="accounts")

    __table_args__ = (
        UniqueConstraint(
            "platform",
            "username",
            name="uq_streamer_account_platform_username"
        ),
    )