
from datetime import datetime, timezone
from math import log10


def normalize_datetime(value):
    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def clamp(value, minimum=0.0, maximum=100.0):
    return max(minimum, min(maximum, value))


# --------------------------------------------------
# Freshness
# --------------------------------------------------

def calculate_freshness(created_at):
    created_at = normalize_datetime(created_at)

    if created_at is None:
        return 40.0, 48.0

    age_hours = max(
        0,
        (datetime.now(timezone.utc) - created_at).total_seconds() / 3600
    )

    freshness = clamp(100 - (age_hours / 48) * 100)

    return freshness, age_hours


# --------------------------------------------------
# Views velocity
# --------------------------------------------------

def calculate_velocity(views, age_hours):
    views = max(0, views or 0)

    views_per_hour = views / max(age_hours, 1)

    return clamp(
        (log10(views_per_hour + 1) / 3) * 100
    )


# --------------------------------------------------
# Real growth from snapshots
# --------------------------------------------------

def calculate_growth(snapshots, fallback_velocity):
    if not snapshots or len(snapshots) < 2:
        return fallback_velocity

    ordered = sorted(
        snapshots,
        key=lambda item: normalize_datetime(item.captured_at)
        or datetime.min.replace(tzinfo=timezone.utc)
    )

    previous = ordered[-2]
    latest = ordered[-1]

    previous_time = normalize_datetime(previous.captured_at)
    latest_time = normalize_datetime(latest.captured_at)

    if not previous_time or not latest_time:
        return fallback_velocity

    elapsed_hours = (
        latest_time - previous_time
    ).total_seconds() / 3600

    if elapsed_hours <= 0:
        return fallback_velocity

    gained_views = max(
        0,
        (latest.views or 0) - (previous.views or 0)
    )

    views_per_hour = gained_views / elapsed_hours

    growth_score = (
        log10(views_per_hour + 1) / 3
    ) * 100

    return clamp(growth_score)


# --------------------------------------------------
# Streamer performance
# --------------------------------------------------

def calculate_streamer_performance(
    clip_views,
    streamer_average_views
):
    if streamer_average_views is None or streamer_average_views <= 0:
        return 50.0

    ratio = (
        (clip_views or 0) + 1
    ) / (
        streamer_average_views + 1
    )

    score = 50 + (20 * log10(ratio))

    return clamp(score)


# --------------------------------------------------
# Duration suitability
# --------------------------------------------------

def calculate_duration_score(duration):
    duration = duration or 0

    if 20 <= duration <= 45:
        return 100.0

    if 15 <= duration < 20:
        return 80.0 + ((duration - 15) / 5) * 20

    if 45 < duration <= 60:
        return 100 - ((duration - 45) / 15) * 20

    if 10 <= duration < 15:
        return 50 + ((duration - 10) / 5) * 30

    if 60 < duration <= 90:
        return 80 - ((duration - 60) / 30) * 60

    return 0.0


# --------------------------------------------------
# Title quality heuristic
# --------------------------------------------------

def calculate_title_score(title):
    if not title:
        return 20.0

    title = title.strip()

    if len(title) < 5:
        return 15.0

    score = 35.0

    if 15 <= len(title) <= 90:
        score += 25

    elif len(title) > 120:
        score -= 10

    words = title.split()

    if 3 <= len(words) <= 14:
        score += 20

    if any(char.isdigit() for char in title):
        score += 5

    if any(char in title for char in ("!", "?", "...")):
        score += 5

    if len(set(words)) >= 3:
        score += 10

    return clamp(score)


# --------------------------------------------------
# Final viral score
# --------------------------------------------------

def calculate_viral_score(
    clip,
    snapshots=None,
    streamer_average_views=None
):
    views = clip.views or 0

    freshness, age_hours = calculate_freshness(
        clip.created_at
    )

    fallback_velocity = calculate_velocity(
        views,
        age_hours
    )

    growth = calculate_growth(
        snapshots or [],
        fallback_velocity
    )

    streamer_performance = calculate_streamer_performance(
        views,
        streamer_average_views
    )

    duration = calculate_duration_score(
        clip.duration
    )

    title_quality = calculate_title_score(
        clip.title
    )

    final_score = (
        growth * 0.30
        + fallback_velocity * 0.20
        + streamer_performance * 0.20
        + freshness * 0.15
        + duration * 0.10
        + title_quality * 0.05
    )

    return round(clamp(final_score), 2)
