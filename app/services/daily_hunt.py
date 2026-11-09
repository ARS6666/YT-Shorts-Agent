
import json
import threading
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.daily_hunt import DailyHunt
from app.models.clip import Clip
from app.collectors.twitch import collect_twitch_clips


# --------------------------------------------------
# Scheduler and locks
# --------------------------------------------------

scheduler = BackgroundScheduler(timezone="UTC")
hunt_lock = threading.Lock()


# --------------------------------------------------
# Time helpers
# --------------------------------------------------

def now_utc():
    return datetime.now(timezone.utc)


def now_local():
    return datetime.now().astimezone()


def get_today_date():
    return now_local().date().isoformat()


# --------------------------------------------------
# Scheduler helpers
# --------------------------------------------------

def start_daily_hunt_scheduler():
    if not scheduler.running:
        scheduler.start()

    resume_active_hunts()


def stop_daily_hunt_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)


def remove_hunt_jobs(hunt_id: int):
    if not scheduler.running:
        return

    for job_id in (
        f"hunt-collect-{hunt_id}",
        f"hunt-finish-{hunt_id}",
    ):
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)


def schedule_hunt(hunt):
    if not scheduler.running:
        scheduler.start()

    interval_job_id = f"hunt-collect-{hunt.id}"
    finish_job_id = f"hunt-finish-{hunt.id}"

    if scheduler.get_job(interval_job_id):
        scheduler.remove_job(interval_job_id)

    scheduler.add_job(
        collect_cycle,
        trigger="interval",
        minutes=5,
        args=[hunt.id, False],
        id=interval_job_id,
        replace_existing=True,
        next_run_time=now_utc(),
        max_instances=1,
        coalesce=True,
    )

    if scheduler.get_job(finish_job_id):
        scheduler.remove_job(finish_job_id)

    finish_time = hunt.ends_at

    if finish_time <= now_utc():
        finish_time = now_utc() + timedelta(seconds=2)

    scheduler.add_job(
        collect_cycle,
        trigger="date",
        run_date=finish_time,
        args=[hunt.id, True],
        id=finish_job_id,
        replace_existing=True,
    )


def resume_active_hunts():
    db = SessionLocal()

    try:
        active_hunts = (
            db.query(DailyHunt)
            .filter(DailyHunt.status == "running")
            .all()
        )

        for hunt in active_hunts:
            schedule_hunt(hunt)

    finally:
        db.close()


# --------------------------------------------------
# Clip selection
# --------------------------------------------------

def get_hunt_clips(db: Session, hunt):
    reset_at = getattr(hunt, "reset_at", None)

    query = db.query(Clip).filter(
        Clip.platform == "twitch",
        Clip.status != "rejected",
    )

    if reset_at:
        query = query.filter(
            Clip.discovered_at >= reset_at
        )
    else:
        cutoff = now_utc() - timedelta(hours=24)
        query = query.filter(
            Clip.created_at >= cutoff
        )

    return (
        query
        .order_by(Clip.viral_score.desc())
        .all()
    )


def serialize_clip(clip):
    return {
        "id": clip.id,
        "platform": clip.platform,
        "external_id": clip.external_id,
        "title": clip.title,
        "creator": clip.creator,
        "url": clip.url,
        "thumbnail_url": getattr(clip, "thumbnail_url", None),
        "views": clip.views,
        "likes": clip.likes,
        "comments": clip.comments,
        "duration": clip.duration,
        "viral_score": clip.viral_score,
        "status": clip.status,
    }


# --------------------------------------------------
# Daily Hunt serialization
# --------------------------------------------------

def serialize_hunt(db: Session, hunt):
    top_ids = []

    if hunt.top_clip_ids:
        try:
            top_ids = json.loads(hunt.top_clip_ids)
        except (TypeError, ValueError):
            top_ids = []

    top_clips = []

    if top_ids:
        clips = (
            db.query(Clip)
            .filter(Clip.id.in_(top_ids))
            .all()
        )

        clips_by_id = {
            clip.id: clip
            for clip in clips
        }

        for clip_id in top_ids:
            clip = clips_by_id.get(clip_id)

            if clip:
                top_clips.append(
                    serialize_clip(clip)
                )

    current_clips = get_hunt_clips(db, hunt)

    return {
        "id": hunt.id,
        "hunt_date": hunt.hunt_date,
        "status": hunt.status,
        "started_at": hunt.started_at.isoformat(),
        "ends_at": hunt.ends_at.isoformat(),
        "completed_at": (
            hunt.completed_at.isoformat()
            if hunt.completed_at
            else None
        ),
        "reset_at": (
            hunt.reset_at.isoformat()
            if getattr(hunt, "reset_at", None)
            else None
        ),
        "total_clips": len(current_clips),
        "top_clip_ids": top_ids,
        "top_clips": top_clips,
        "clips": [
            serialize_clip(clip)
            for clip in current_clips
        ],
    }


# --------------------------------------------------
# Finalize hunt
# --------------------------------------------------

def finalize_hunt(db: Session, hunt):
    clips = get_hunt_clips(db, hunt)

    top_two = clips[:2]

    hunt.total_clips = len(clips)
    hunt.top_clip_ids = json.dumps(
        [clip.id for clip in top_two]
    )
    hunt.status = "completed"
    hunt.completed_at = now_utc()

    db.commit()

    return hunt


# --------------------------------------------------
# Collection cycle
# --------------------------------------------------

def collect_cycle(hunt_id: int, finish: bool = False):
    acquired = hunt_lock.acquire(blocking=False)

    if not acquired:
        if finish and scheduler.running:
            scheduler.add_job(
                collect_cycle,
                trigger="date",
                run_date=now_utc() + timedelta(seconds=10),
                args=[hunt_id, True],
                id=f"hunt-finish-{hunt_id}",
                replace_existing=True,
            )

        return

    db = SessionLocal()

    try:
        hunt = (
            db.query(DailyHunt)
            .filter(DailyHunt.id == hunt_id)
            .first()
        )

        if not hunt or hunt.status != "running":
            return

        collect_twitch_clips(
            db=db,
            lookback_hours=24,
            max_pages=20,
        )

        db.refresh(hunt)

        clips = get_hunt_clips(db, hunt)
        hunt.total_clips = len(clips)

        if finish:
            finalize_hunt(db, hunt)
            remove_hunt_jobs(hunt_id)
        else:
            db.commit()

    except Exception as exc:
        db.rollback()
        print(f"[Daily Hunt] Collection error: {exc}")

        if finish and scheduler.running:
            scheduler.add_job(
                collect_cycle,
                trigger="date",
                run_date=now_utc() + timedelta(seconds=30),
                args=[hunt_id, True],
                id=f"hunt-finish-{hunt_id}",
                replace_existing=True,
            )

    finally:
        db.close()
        hunt_lock.release()


# --------------------------------------------------
# Start a new Daily Hunt
# --------------------------------------------------

def start_daily_hunt(db: Session):
    today = get_today_date()

    existing = (
        db.query(DailyHunt)
        .filter(DailyHunt.hunt_date == today)
        .first()
    )

    if existing:
        return {
            "created": False,
            "hunt": existing,
        }

    started_at = now_utc()
    ends_at = started_at + timedelta(minutes=60)

    hunt = DailyHunt(
        hunt_date=today,
        status="running",
        started_at=started_at,
        ends_at=ends_at,
        total_clips=0,
        top_clip_ids=None,
        reset_at=started_at,
    )

    db.add(hunt)
    db.commit()
    db.refresh(hunt)

    schedule_hunt(hunt)

    return {
        "created": True,
        "hunt": hunt,
    }


# --------------------------------------------------
# Reset today's Daily Hunt
# --------------------------------------------------

def reset_daily_hunt(db: Session):
    if not hunt_lock.acquire(blocking=False):
        return {
            "success": False,
            "message": "A collection cycle is currently running. Try again shortly.",
        }

    try:
        today = get_today_date()

        hunt = (
            db.query(DailyHunt)
            .filter(DailyHunt.hunt_date == today)
            .first()
        )

        if not hunt:
            reset_time = now_utc()

            hunt = DailyHunt(
                hunt_date=today,
                status="running",
                started_at=reset_time,
                ends_at=reset_time + timedelta(minutes=60),
                completed_at=None,
                total_clips=0,
                top_clip_ids=None,
                reset_at=reset_time,
            )

            db.add(hunt)

        else:
            reset_time = now_utc()

            hunt.status = "running"
            hunt.started_at = reset_time
            hunt.ends_at = reset_time + timedelta(minutes=60)
            hunt.completed_at = None
            hunt.total_clips = 0
            hunt.top_clip_ids = None
            hunt.reset_at = reset_time

        db.commit()
        db.refresh(hunt)

        remove_hunt_jobs(hunt.id)
        schedule_hunt(hunt)

        return {
            "success": True,
            "message": "Daily Hunt has been reset successfully.",
            "hunt": serialize_hunt(db, hunt),
        }

    except Exception as exc:
        db.rollback()
        print(f"[Daily Hunt] Reset error: {exc}")

        return {
            "success": False,
            "message": str(exc),
        }

    finally:
        hunt_lock.release()


# --------------------------------------------------
# Get today's hunt
# --------------------------------------------------

def get_today_hunt(db: Session):
    today = get_today_date()

    hunt = (
        db.query(DailyHunt)
        .filter(DailyHunt.hunt_date == today)
        .first()
    )

    if not hunt:
        return {
            "exists": False,
            "hunt": None,
        }

    if hunt.status == "running" and hunt.ends_at <= now_utc():
        collect_cycle(hunt.id, True)
        db.refresh(hunt)

    return {
        "exists": True,
        "hunt": serialize_hunt(db, hunt),
    }


# --------------------------------------------------
# Daily Hunt archive
# --------------------------------------------------

def get_hunt_archive(db: Session, limit: int = 30):
    hunts = (
        db.query(DailyHunt)
        .filter(DailyHunt.status == "completed")
        .order_by(DailyHunt.hunt_date.desc())
        .limit(limit)
        .all()
    )

    return [
        serialize_hunt(db, hunt)
        for hunt in hunts
    ]
