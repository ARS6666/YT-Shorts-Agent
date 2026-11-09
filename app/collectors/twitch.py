import os
from pathlib import Path
from datetime import datetime, timedelta, timezone

import httpx
from dotenv import load_dotenv

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=ENV_FILE, override=True)
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.clip import Clip
from app.models.clip_metric import ClipMetricSnapshot
from app.models.streamer import StreamerAccount
from app.services.scoring import calculate_viral_score

load_dotenv()

TWITCH_TOKEN_URL = "https://id.twitch.tv/oauth2/token"
TWITCH_API_BASE = "https://api.twitch.tv/helix"


def get_app_access_token() -> tuple[str, str]:
    client_id = os.getenv("TWITCH_CLIENT_ID")
    client_secret = os.getenv("TWITCH_CLIENT_SECRET")

    if not client_id or not client_secret:
        raise RuntimeError(
            "TWITCH_CLIENT_ID or TWITCH_CLIENT_SECRET is missing in .env"
        )

    response = httpx.post(
        TWITCH_TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "client_credentials",
        },
        timeout=20,
    )
    response.raise_for_status()

    data = response.json()
    token = data.get("access_token")

    if not token:
        raise RuntimeError("Twitch did not return an access token")

    return client_id, token


def get_headers(client_id: str, token: str) -> dict:
    return {
        "Client-Id": client_id,
        "Authorization": f"Bearer {token}",
    }


def parse_datetime(value: str | None):
    if not value:
        return None

    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def twitch_get(
    client: httpx.Client,
    endpoint: str,
    params: dict,
):
    response = client.get(
        f"{TWITCH_API_BASE}/{endpoint}",
        params=params,
    )
    response.raise_for_status()
    return response.json()


def resolve_broadcaster_id(
    client: httpx.Client,
    account: StreamerAccount,
) -> str:
    if account.external_id:
        return account.external_id

    result = twitch_get(
        client,
        "users",
        {"login": account.username},
    )

    users = result.get("data", [])

    if not users:
        raise ValueError(
            f"Twitch account not found: {account.username}"
        )

    broadcaster_id = users[0]["id"]
    account.external_id = broadcaster_id

    return broadcaster_id


def fetch_broadcaster_clips(
    client: httpx.Client,
    broadcaster_id: str,
    lookback_hours: int = 24,
    max_pages: int = 20,
) -> list[dict]:
    now = datetime.now(timezone.utc)
    started_at = now - timedelta(hours=lookback_hours)

    clips = []
    cursor = None

    for _ in range(max_pages):
        params = {
            "broadcaster_id": broadcaster_id,
            "started_at": started_at.isoformat(
                timespec="seconds"
            ).replace("+00:00", "Z"),
            "ended_at": now.isoformat(
                timespec="seconds"
            ).replace("+00:00", "Z"),
            "first": 100,
        }

        if cursor:
            params["after"] = cursor

        result = twitch_get(client, "clips", params)

        clips.extend(result.get("data", []))

        cursor = (
            result.get("pagination", {}).get("cursor")
        )

        if not cursor:
            break

    return clips



def save_twitch_clip(
    db: Session,
    data: dict,
) -> tuple[str, int]:

    external_id = data["id"]

    clip = db.query(Clip).filter(
        Clip.platform == "twitch",
        Clip.external_id == external_id,
    ).first()

    views = int(data.get("view_count") or 0)
    created_at = parse_datetime(data.get("created_at"))

    is_new = clip is None

    if is_new:
        clip = Clip(
            platform="twitch",
            external_id=external_id,
            title=data.get("title") or "Untitled Twitch Clip",
            creator=data.get("broadcaster_name"),
            url=data.get("url"),
            thumbnail_url=data.get("thumbnail_url"),
            views=views,
            likes=None,
            comments=None,
            duration=float(data.get("duration") or 0),
            created_at=created_at,
            status="discovered",
        )

        db.add(clip)
        db.flush()

    else:
        clip.title = data.get("title") or clip.title
        clip.creator = data.get("broadcaster_name") or clip.creator
        clip.url = data.get("url") or clip.url

        clip.thumbnail_url = (
            data.get("thumbnail_url") or clip.thumbnail_url
        )

        clip.views = views
        clip.duration = float(data.get("duration") or 0)

        if created_at:
            clip.created_at = created_at

    # Get previous snapshots BEFORE creating the new snapshot.
    snapshots = (
        db.query(ClipMetricSnapshot)
        .filter(ClipMetricSnapshot.clip_id == clip.id)
        .order_by(ClipMetricSnapshot.captured_at.asc())
        .all()
    )

    # Calculate average views for this streamer's other clips.
    streamer_average_views = None

    if clip.creator:
        streamer_average_views = (
            db.query(func.avg(Clip.views))
            .filter(
                Clip.platform == "twitch",
                Clip.creator == clip.creator,
                Clip.id != clip.id,
            )
            .scalar()
        )

    # Recalculate score for both new and existing clips.
    clip.viral_score = calculate_viral_score(
        clip,
        snapshots=snapshots,
        streamer_average_views=streamer_average_views,
    )

    # Save current metrics for future growth calculations.
    snapshot = ClipMetricSnapshot(
        clip_id=clip.id,
        views=views,
        likes=0,
        comments=0,
        captured_at=datetime.now(timezone.utc),
    )

    db.add(snapshot)

    return (
        "created" if is_new else "updated",
        clip.id,
    )


def collect_twitch_clips(
    db: Session,
    lookback_hours: int = 24,
    max_pages: int = 20,
) -> dict:
    client_id, token = get_app_access_token()

    accounts = db.query(StreamerAccount).filter(
        StreamerAccount.platform == "twitch",
        StreamerAccount.is_active.is_(True),
    ).all()

    result = {
        "platform": "twitch",
        "accounts_checked": 0,
        "clips_found": 0,
        "clips_created": 0,
        "clips_updated": 0,
        "errors": [],
    }

    if not accounts:
        result["message"] = (
            "No active Twitch accounts registered."
        )
        return result

    with httpx.Client(
        headers=get_headers(client_id, token),
        timeout=30,
    ) as client:

        for account in accounts:
            result["accounts_checked"] += 1

            try:
                broadcaster_id = resolve_broadcaster_id(
                    client,
                    account,
                )

                clips = fetch_broadcaster_clips(
                    client,
                    broadcaster_id,
                    lookback_hours=lookback_hours,
                    max_pages=max_pages,
                )

                result["clips_found"] += len(clips)

                for clip_data in clips:
                    action, _ = save_twitch_clip(
                        db,
                        clip_data,
                    )

                    if action == "created":
                        result["clips_created"] += 1
                    else:
                        result["clips_updated"] += 1

                db.commit()

            except Exception as exc:
                db.rollback()

                result["errors"].append({
                    "account": account.username,
                    "error": str(exc),
                })

    return result