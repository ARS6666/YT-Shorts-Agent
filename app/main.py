
from contextlib import asynccontextmanager
from typing import Optional
from datetime import datetime

from fastapi import FastAPI, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from app.database import Base, engine, get_db
from app.models.clip import Clip
from app.models.streamer import StreamerSnapshot, Streamer, StreamerAccount
from app.models.clip_metric import ClipMetricSnapshot
from app.collectors.twitch import collect_twitch_clips
from sqlalchemy import func
from app.collectors.youtube import collect_youtube_videos
from app.services.clip_trends import get_trending_clips
from app.services.live_terminal import terminal, router as terminal_router
from app.api.editor import router as editor_router
from app.models.daily_hunt import DailyHunt
from app.services.daily_hunt import (
    start_daily_hunt,
    get_today_hunt,
    get_hunt_archive,
    reset_daily_hunt,
    start_daily_hunt_scheduler,
    stop_daily_hunt_scheduler,
)
from app.api.youtube_clipper import router as youtube_clipper_router
from fastapi.middleware.cors import CORSMiddleware
from app.api.streamers import router as streamers_router
from app.services.scoring import calculate_viral_score


@asynccontextmanager
async def lifespan(app: FastAPI):
    terminal.install()

    try:
        Base.metadata.create_all(bind=engine)
        start_daily_hunt_scheduler()

        yield

    finally:
        stop_daily_hunt_scheduler()
        terminal.restore()
app = FastAPI(
    title="TrendHunter AI",
    description="Streamer Clip Discovery and Viral Scoring Engine",
    version="0.1.0",
    lifespan=lifespan
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(streamers_router)
app.include_router(editor_router)
app.include_router(youtube_clipper_router)
app.include_router(terminal_router)
# -------------------------
# Request schemas
# -------------------------

class ClipCreate(BaseModel):

    platform: str = Field(
        pattern="^(youtube|twitch|kick)$"
    )

    external_id: str = Field(min_length=1, max_length=255)

    title: str = Field(min_length=1, max_length=500)

    url: str

    creator: Optional[str] = None

    thumbnail_url: Optional[str] = None

    views: int = Field(default=0, ge=0)

    likes: Optional[int] = Field(default=None, ge=0)

    comments: Optional[int] = Field(default=None, ge=0)

    duration: float = Field(default=0, ge=0)

    created_at: Optional[datetime] = None


class ClipResponse(BaseModel):

    model_config = ConfigDict(from_attributes=True)

    id: int
    platform: str
    external_id: str
    title: str
    creator: Optional[str]
    url: str
    views: int
    likes: Optional[int]
    comments: Optional[int]
    duration: float
    viral_score: float
    status: str
    thumbnail_url: Optional[str] = None


class StatusUpdate(BaseModel):

    status: str = Field(
        pattern="^(approved|rejected)$"
    )


# -------------------------
# General endpoints
# -------------------------

@app.get("/")
def home():

    return {
        "name": "TrendHunter AI",
        "version": "0.1.0",
        "status": "running"
    }


@app.get("/health")
def health():

    return {
        "status": "healthy",
        "database": "connected"
    }


# -------------------------
# Clip endpoints
# -------------------------

@app.post(
    "/clips",
    response_model=ClipResponse,
    status_code=201
)
def add_clip(
    payload: ClipCreate,
    db: Session = Depends(get_db)
):

    existing = db.query(Clip).filter(
        Clip.platform == payload.platform,
        Clip.external_id == payload.external_id
    ).first()

    if existing:
        raise HTTPException(
            status_code=409,
            detail="Clip already exists"
        )

    clip = Clip(**payload.model_dump())

    db.add(clip)
    db.flush()

    clip.viral_score = calculate_viral_score(clip)
    clip.status = "scored"

    db.commit()
    db.refresh(clip)

    return clip


@app.get(
    "/clips",
    response_model=list[ClipResponse]
)
def get_clips(
    status: Optional[str] = None,
    platform: Optional[str] = None,
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db)
):

    query = db.query(Clip)

    if status:
        query = query.filter(Clip.status == status)

    if platform:
        query = query.filter(Clip.platform == platform)

    return query.order_by(
        Clip.viral_score.desc()
    ).limit(limit).all()

@app.delete("/clips/reset")
def reset_clips(db: Session = Depends(get_db)):
    try:
        deleted_snapshots = db.query(ClipMetricSnapshot).delete(
            synchronize_session=False
        )

        deleted_clips = db.query(Clip).delete(
            synchronize_session=False
        )

        db.commit()

        return {
            "success": True,
            "message": "Clip list has been reset successfully.",
            "deleted_clips": deleted_clips,
            "deleted_snapshots": deleted_snapshots,
        }

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to reset clip list."
        )
@app.get(
    "/clips/{clip_id}",
    response_model=ClipResponse
)
def get_clip(
    clip_id: int,
    db: Session = Depends(get_db)
):

    clip = db.query(Clip).filter(
        Clip.id == clip_id
    ).first()

    if not clip:
        raise HTTPException(
            status_code=404,
            detail="Clip not found"
        )

    return clip


@app.patch(
    "/clips/{clip_id}/status",
    response_model=ClipResponse
)
def update_clip_status(
    clip_id: int,
    payload: StatusUpdate,
    db: Session = Depends(get_db)
):

    clip = db.query(Clip).filter(
        Clip.id == clip_id
    ).first()

    if not clip:
        raise HTTPException(
            status_code=404,
            detail="Clip not found"
        )

    clip.status = payload.status

    db.commit()
    db.refresh(clip)

    return clip

# -------------------------
# Trend and analytics endpoints
# -------------------------

@app.get("/trends/clips")
def trending_clips(
    platform: str = Query(default="youtube", pattern="^(youtube|twitch|kick)$"),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Return clips ranked by actual view growth and engagement.
    Requires at least two metric snapshots per clip.
    """
    results = get_trending_clips(
        db=db,
        platform=platform,
        limit=limit,
    )

    return {
        "platform": platform,
        "count": len(results),
        "items": results,
    }


@app.get("/analytics/overview")
def analytics_overview(
    db: Session = Depends(get_db),
):
    # Global statistics
    total_clips = db.query(func.count(Clip.id)).scalar() or 0

    total_views = db.query(
        func.coalesce(func.sum(Clip.views), 0)
    ).scalar() or 0

    total_likes = db.query(
        func.coalesce(func.sum(Clip.likes), 0)
    ).scalar() or 0

    total_comments = db.query(
        func.coalesce(func.sum(Clip.comments), 0)
    ).scalar() or 0

    average_viral_score = db.query(
        func.coalesce(func.avg(Clip.viral_score), 0)
    ).scalar() or 0

    # Twitch-only statistics
    twitch_query = db.query(Clip).filter(
        Clip.platform == "twitch"
    )

    twitch_total = twitch_query.count()

    twitch_views = db.query(
        func.coalesce(func.sum(Clip.views), 0)
    ).filter(
        Clip.platform == "twitch"
    ).scalar() or 0

    twitch_pending = db.query(
        func.count(Clip.id)
    ).filter(
        Clip.platform == "twitch",
        Clip.status.notin_(["approved", "rejected"])
    ).scalar() or 0

    twitch_approved = db.query(
        func.count(Clip.id)
    ).filter(
        Clip.platform == "twitch",
        Clip.status == "approved"
    ).scalar() or 0

    twitch_rejected = db.query(
        func.count(Clip.id)
    ).filter(
        Clip.platform == "twitch",
        Clip.status == "rejected"
    ).scalar() or 0

    total_snapshots = db.query(
        func.count(ClipMetricSnapshot.id)
    ).scalar() or 0

    status_rows = (
        db.query(Clip.status, func.count(Clip.id))
        .group_by(Clip.status)
        .all()
    )

    platform_rows = (
        db.query(Clip.platform, func.count(Clip.id))
        .group_by(Clip.platform)
        .all()
    )

    streamer_count = db.query(
        func.count(Streamer.id)
    ).scalar() or 0

    active_streamer_count = db.query(
        func.count(Streamer.id)
    ).filter(
        Streamer.is_active.is_(True)
    ).scalar() or 0

    return {
        "clips": {
            "total": total_clips,
            "total_views": int(total_views),
            "total_likes": int(total_likes),
            "total_comments": int(total_comments),
            "average_viral_score": round(
                float(average_viral_score), 2
            ),
        },
        "twitch": {
            "total": twitch_total,
            "total_views": int(twitch_views),
            "pending": twitch_pending,
            "approved": twitch_approved,
            "rejected": twitch_rejected,
        },
        "snapshots": {
            "total": total_snapshots,
        },
        "streamers": {
            "total": streamer_count,
            "active": active_streamer_count,
        },
        "by_status": {
            status: count for status, count in status_rows
        },
        "by_platform": {
            platform: count for platform, count in platform_rows
        },
    }

@app.post("/collect/youtube")
def run_youtube_collection(
    streamer_id: Optional[int] = Query(default=None, ge=1),
    limit_per_channel: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """
    Manually trigger YouTube collection for active registered accounts.
    """

    try:
        result = collect_youtube_videos(
            db=db,
            streamer_id=streamer_id,
            limit_per_channel=limit_per_channel,
        )

        return {
            "status": "completed",
            "collection": result,
        }

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"YouTube collection failed: {str(exc)}",
        ) from exc
@app.post("/collect/twitch")
def run_twitch_collection(
    lookback_hours: int = Query(default=24, ge=1, le=168),
    max_pages: int = Query(default=20, ge=1, le=20),
    db: Session = Depends(get_db),
):
    try:
        result = collect_twitch_clips(
            db=db,
            lookback_hours=lookback_hours,
            max_pages=max_pages,
        )

        return {
            "status": "completed",
            "collection": result,
        }

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Twitch collection failed: {str(exc)}",
        ) from exc

# -------------------------
# Daily Hunt endpoints
# -------------------------

@app.post("/daily-hunt/start")
def start_daily_hunt_endpoint(
    db: Session = Depends(get_db)
):
    try:
        result = start_daily_hunt(db)

        if not result["created"]:
            hunt = result["hunt"]

            if hunt.status == "running":
                return {
                    "status": "already_running",
                    "message": "Today's hunt is already running.",
                    "hunt_id": hunt.id
                }

            raise HTTPException(
                status_code=409,
                detail="Today's hunt has already been completed."
            )

        return {
            "status": "started",
            "message": "Daily Hunt started. It will run for 60 minutes.",
            "hunt_id": result["hunt"].id,
            "started_at": result["hunt"].started_at.isoformat(),
            "ends_at": result["hunt"].ends_at.isoformat()
        }

    except HTTPException:
        raise

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Could not start Daily Hunt: {str(exc)}"
        ) from exc


@app.get("/daily-hunt/today")
def daily_hunt_today_endpoint(
    db: Session = Depends(get_db)
):
    return get_today_hunt(db)


@app.get("/daily-hunt/archive")
def daily_hunt_archive_endpoint(
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db)
):
    return {
        "items": get_hunt_archive(db, limit)
    }

@app.post("/daily-hunt/reset")
def daily_hunt_reset_endpoint(
    db: Session = Depends(get_db)
):
    try:
        result = reset_daily_hunt(db)

        if not result["success"]:
            raise HTTPException(
                status_code=409,
                detail=result["message"],
            )

        return {
            "status": "reset",
            "message": result["message"],
            "hunt": result["hunt"],
        }

    except HTTPException:
        raise

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Could not reset Daily Hunt: {str(exc)}",
        ) from exc