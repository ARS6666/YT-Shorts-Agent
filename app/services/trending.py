
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from math import log10

from sqlalchemy.orm import Session

from app.models.streamer import StreamerSnapshot


EXCLUDED_CATEGORY_KEYWORDS = (
    "slots",
    "casino",
    "gambling",
    "betting",
)


def find_previous_snapshot(records, reference_time):
    """Find a snapshot captured 45–75 minutes before reference_time."""

    candidates = []

    for record in records:
        elapsed = (
            reference_time - record.captured_at
        ).total_seconds() / 60

        if 45 <= elapsed <= 75:
            candidates.append((record, elapsed))

    if not candidates:
        return None

    return min(
        candidates,
        key=lambda item: abs(item[1] - 60),
    )


def calculate_trend_score(
    current_viewers,
    viewer_change,
    growth_percent,
    consistent_growth,
):
    """Calculate a ranking score from 0 to 100."""

    # 1. Absolute viewer growth: maximum 40
    growth_points = min(max(viewer_change, 0) / 5000, 1) * 40

    # 2. Relative viewer growth: maximum 30
    percentage_points = min(max(growth_percent, 0) / 50, 1) * 30

    # 3. Current audience size: maximum 20
    audience_ratio = max(current_viewers, 1000) / 1000
    audience_points = min(log10(audience_ratio) / 2, 1) * 20

    # 4. Consistent growth across two consecutive intervals: maximum 10
    consistency_points = 10 if consistent_growth else 0

    total = (
        growth_points
        + percentage_points
        + audience_points
        + consistency_points
    )

    return round(min(total, 100), 2)


def get_trending_streamers(
    db: Session,
    platform: str = "kick",
    min_viewers: int = 1000,
):
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    snapshots = (
        db.query(StreamerSnapshot)
        .filter(
            StreamerSnapshot.platform == platform,
            StreamerSnapshot.captured_at >= now - timedelta(hours=5),
        )
        .order_by(StreamerSnapshot.captured_at.desc())
        .all()
    )

    grouped = defaultdict(list)

    for snapshot in snapshots:
        grouped[snapshot.broadcaster].append(snapshot)

    results = []

    for broadcaster, records in grouped.items():
        records.sort(
            key=lambda item: item.captured_at,
            reverse=True,
        )

        current = records[0]

        # Filter small audiences
        if current.viewer_count < min_viewers:
            continue

        # Exclude gambling-related categories
        category = (current.category or "").lower()

        if any(
            keyword in category
            for keyword in EXCLUDED_CATEGORY_KEYWORDS
        ):
            continue

        # Find the previous snapshot
        previous_result = find_previous_snapshot(
            records[1:],
            current.captured_at,
        )

        if not previous_result:
            continue

        previous, interval_minutes = previous_result

        viewer_change = (
            current.viewer_count - previous.viewer_count
        )

        # Ignore zero or negative growth
        if viewer_change <= 0:
            continue

        growth_percent = (
            viewer_change / previous.viewer_count * 100
            if previous.viewer_count > 0
            else 0
        )

        hourly_growth = (
            viewer_change * 60 / interval_minutes
        )

        # Check whether growth continued in the previous interval
        older_result = find_previous_snapshot(
            records,
            previous.captured_at,
        )

        consistent_growth = False
        older_viewers = None

        if older_result:
            older, _ = older_result
            older_viewers = older.viewer_count

            consistent_growth = (
                previous.viewer_count > older.viewer_count
            )

        trend_score = calculate_trend_score(
            current_viewers=current.viewer_count,
            viewer_change=viewer_change,
            growth_percent=growth_percent,
            consistent_growth=consistent_growth,
        )

        results.append({
            "platform": platform,
            "broadcaster": broadcaster,
            "title": current.title,
            "category": current.category,
            "previous_viewers": previous.viewer_count,
            "current_viewers": current.viewer_count,
            "viewer_change": viewer_change,
            "growth_percent": round(growth_percent, 2),
            "estimated_hourly_growth": round(hourly_growth),
            "interval_minutes": round(interval_minutes),
            "consistent_growth": consistent_growth,
            "older_viewers": older_viewers,
            "trend_score": trend_score,
        })

    results.sort(
        key=lambda item: item["trend_score"],
        reverse=True,
    )

    return results
