
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from math import log10

from sqlalchemy.orm import Session

from app.models.clip import Clip
from app.models.clip_metric import ClipMetricSnapshot


# Accept realistic differences between collection cycles.
WINDOWS = {
    "1h": (1, 0.5, 2),
    "6h": (6, 4, 8),
    "24h": (24, 18, 30),
}


def utc_naive(value):
    """Normalize SQLite and timezone-aware datetimes to naive UTC."""
    if value is None:
        return None

    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    return value


def calculate_growth(previous, current):
    previous_time = utc_naive(previous.captured_at)
    current_time = utc_naive(current.captured_at)

    elapsed_hours = (
        current_time - previous_time
    ).total_seconds() / 3600

    if elapsed_hours <= 0:
        return None

    view_change = current.views - previous.views

    growth_percent = (
        (view_change / previous.views) * 100
        if previous.views > 0 else None
    )

    return {
        "view_change": view_change,
        "growth_percent": (
            round(growth_percent, 2)
            if growth_percent is not None else None
        ),
        "views_per_hour": round(view_change / elapsed_hours, 2),
        "interval_hours": round(elapsed_hours, 2),
    }


def calculate_clip_trend_score(
    hourly_growth,
    growth_percent,
    views,
    likes,
    comments,
    published_at,
):
    # View velocity: maximum 45 points.
    velocity_points = (
        min(log10(1 + max(hourly_growth, 0)) / log10(10001), 1)
        * 45
    )

    # Percentage growth: maximum 25 points.
    percentage_points = (
        min(max(growth_percent or 0, 0) / 50, 1) * 25
    )

    # Engagement: maximum 20 points.
    engagement_rate = (
        ((likes or 0) + (comments or 0)) / views
        if views > 0 else 0
    )
    engagement_points = min(engagement_rate / 0.10, 1) * 20

    # Freshness: maximum 10 points.
    freshness_points = 0

    if published_at:
        published_time = utc_naive(published_at)
        age_hours = max(
            0,
            (datetime.now(timezone.utc).replace(tzinfo=None)
             - published_time).total_seconds() / 3600,
        )
        freshness_points = max(0, 1 - age_hours / 48) * 10

    score = (
        velocity_points
        + percentage_points
        + engagement_points
        + freshness_points
    )

    return round(max(0, min(score, 100)), 2)


def get_trending_clips(
    db: Session,
    platform: str = "youtube",
    limit: int = 50,
):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    cutoff = now - timedelta(hours=36)

    snapshots = (
        db.query(ClipMetricSnapshot)
        .join(Clip, Clip.id == ClipMetricSnapshot.clip_id)
        .filter(
            Clip.platform == platform,
            ClipMetricSnapshot.captured_at >= cutoff,
        )
        .order_by(
            ClipMetricSnapshot.clip_id,
            ClipMetricSnapshot.captured_at,
        )
        .all()
    )

    grouped = defaultdict(list)

    for snapshot in snapshots:
        grouped[snapshot.clip_id].append(snapshot)

    results = []

    for clip_id, records in grouped.items():
        if len(records) < 2:
            continue

        records.sort(
            key=lambda item: utc_naive(item.captured_at)
        )

        latest = records[-1]
        latest_time = utc_naive(latest.captured_at)

        window_results = {}

        # Try standard comparison windows first.
        for name, (target, min_hours, max_hours) in WINDOWS.items():
            candidates = []

            for record in records[:-1]:
                elapsed = (
                    latest_time - utc_naive(record.captured_at)
                ).total_seconds() / 3600

                if min_hours <= elapsed <= max_hours:
                    candidates.append((record, elapsed))

            if not candidates:
                continue

            previous, _ = min(
                candidates,
                key=lambda item: abs(item[1] - target),
            )

            growth = calculate_growth(previous, latest)

            if growth:
                window_results[name] = growth

        # Fallback: use the closest available snapshot when no
        # standard window matches. Minimum interval is 10 minutes.
        if not window_results:
            candidates = []

            for record in records[:-1]:
                elapsed = (
                    latest_time - utc_naive(record.captured_at)
                ).total_seconds() / 3600

                if 10 / 60 <= elapsed <= 36:
                    candidates.append((record, elapsed))

            if not candidates:
                continue

            previous, _ = min(
                candidates,
                key=lambda item: abs(item[1] - 1),
            )

            growth = calculate_growth(previous, latest)

            if growth:
                window_results["observed"] = growth

        best_window = min(
            window_results,
            key=lambda name: (
                WINDOWS[name][0] if name in WINDOWS else 1
            ),
        )

        selected = window_results[best_window]

        # Do not rank clips with zero or negative view growth.
        if selected["views_per_hour"] <= 0:
            continue

        clip = db.query(Clip).filter(
            Clip.id == clip_id
        ).first()

        if not clip:
            continue

        score = calculate_clip_trend_score(
            hourly_growth=selected["views_per_hour"],
            growth_percent=selected["growth_percent"],
            views=latest.views,
            likes=latest.likes,
            comments=latest.comments,
            published_at=clip.created_at,
        )

        results.append({
            "clip_id": clip.id,
            "platform": clip.platform,
            "creator": clip.creator,
            "title": clip.title,
            "url": clip.url,
            "thumbnail_url": clip.thumbnail_url,
            "current_views": latest.views,
            "current_likes": latest.likes,
            "current_comments": latest.comments,
            "best_window": best_window,
            "growth": window_results,
            "trend_score": score,
            "confidence_windows": len(
                [name for name in window_results if name != "observed"]
            ),
        })

    results.sort(
        key=lambda item: item["trend_score"],
        reverse=True,
    )

    return results[:limit]
