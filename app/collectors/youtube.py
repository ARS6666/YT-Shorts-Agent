
import os
import re
from datetime import datetime, timezone
from typing import Optional

import httpx
from dotenv import load_dotenv
from sqlalchemy.orm import Session

from app.models.clip import Clip
from app.models.clip_metric import ClipMetricSnapshot
from app.models.streamer import Streamer, StreamerAccount

load_dotenv()

API_KEY = os.getenv("YOUTUBE_API_KEY")
BASE_URL = "https://www.googleapis.com/youtube/v3"


class YouTubeAPIError(Exception):
    pass


def api_get(endpoint: str, params: dict) -> dict:
    if not API_KEY:
        raise YouTubeAPIError("YOUTUBE_API_KEY is missing")

    params["key"] = API_KEY

    try:
        response = httpx.get(
            f"{BASE_URL}/{endpoint}",
            params=params,
            timeout=30
        )
        data = response.json()

        if response.status_code != 200:
            message = data.get("error", {}).get("message", "Unknown API error")
            raise YouTubeAPIError(message)

        return data

    except httpx.HTTPError as exc:
        raise YouTubeAPIError(str(exc)) from exc


def parse_duration(value: str) -> int:
    """Convert ISO 8601 duration to seconds."""
    match = re.fullmatch(
        r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?",
        value or ""
    )

    if not match:
        return 0

    hours, minutes, seconds = (
        int(part or 0) for part in match.groups()
    )

    return hours * 3600 + minutes * 60 + seconds


def parse_datetime(value: Optional[str]):
    if not value:
        return None

    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def resolve_channel(handle: str) -> Optional[dict]:
    """Find a YouTube channel using its handle."""
    data = api_get(
        "channels",
        {
            "part": "snippet,contentDetails",
            "forHandle": handle.lstrip("@"),
            "maxResults": 1
        }
    )

    items = data.get("items", [])
    return items[0] if items else None


def get_upload_video_ids(playlist_id: str, limit: int = 20) -> list[str]:
    """Get recent video IDs from a channel's uploads playlist."""
    video_ids = []
    page_token = None

    while len(video_ids) < limit:
        params = {
            "part": "contentDetails",
            "playlistId": playlist_id,
            "maxResults": min(50, limit - len(video_ids))
        }

        if page_token:
            params["pageToken"] = page_token

        data = api_get("playlistItems", params)

        for item in data.get("items", []):
            video_id = (
                item.get("contentDetails", {}).get("videoId")
            )
            if video_id:
                video_ids.append(video_id)

        page_token = data.get("nextPageToken")
        if not page_token:
            break

    return video_ids


def get_video_details(video_ids: list[str]) -> list[dict]:
    """Fetch video metadata and statistics in batches."""
    results = []

    for start in range(0, len(video_ids), 50):
        batch = video_ids[start:start + 50]

        data = api_get(
            "videos",
            {
                "part": "snippet,statistics,contentDetails",
                "id": ",".join(batch),
                "maxResults": 50
            }
        )

        results.extend(data.get("items", []))

    return results



def collect_channel(
    db: Session,
    streamer: Streamer,
    account: StreamerAccount,
    limit: int = 20
) -> dict:
    handle = account.username.strip()
    channel = resolve_channel(handle)

    if not channel:
        return {
            "streamer": streamer.name,
            "handle": handle,
            "status": "channel_not_found",
            "saved": 0,
            "snapshots_saved": 0
        }

    channel_id = channel["id"]

    uploads_playlist = (
        channel.get("contentDetails", {})
        .get("relatedPlaylists", {})
        .get("uploads")
    )

    if not uploads_playlist:
        return {
            "streamer": streamer.name,
            "handle": handle,
            "status": "uploads_playlist_not_found",
            "saved": 0,
            "snapshots_saved": 0
        }

    if account.external_id != channel_id:
        account.external_id = channel_id

    video_ids = get_upload_video_ids(uploads_playlist, limit)
    videos = get_video_details(video_ids)

    saved = 0
    updated = 0
    snapshots_saved = 0
    captured_at = datetime.now(timezone.utc)

    for video in videos:
        video_id = video["id"]
        snippet = video.get("snippet", {})
        statistics = video.get("statistics", {})
        content = video.get("contentDetails", {})

        views = int(statistics.get("viewCount", 0))
        likes = int(statistics.get("likeCount", 0))
        comments = int(statistics.get("commentCount", 0))

        clip = db.query(Clip).filter(
            Clip.platform == "youtube",
            Clip.external_id == video_id
        ).first()

        if clip:
            # Update current metrics without deleting history.
            clip.views = views
            clip.likes = likes
            clip.comments = comments
            updated += 1

        else:
            thumbnails = snippet.get("thumbnails", {})
            thumbnail = (
                thumbnails.get("high")
                or thumbnails.get("medium")
                or thumbnails.get("default")
                or {}
            )

            clip = Clip(
                platform="youtube",
                external_id=video_id,
                title=snippet.get("title") or "Untitled",
                creator=streamer.name,
                url=f"https://www.youtube.com/watch?v={video_id}",
                thumbnail_url=thumbnail.get("url"),
                views=views,
                likes=likes,
                comments=comments,
                duration=parse_duration(
                    content.get("duration", "PT0S")
                ),
                created_at=parse_datetime(
                    snippet.get("publishedAt")
                ),
                discovered_at=captured_at,
                status="discovered"
            )

            db.add(clip)
            db.flush()
            saved += 1

        snapshot = ClipMetricSnapshot(
            clip_id=clip.id,
            views=views,
            likes=likes,
            comments=comments,
            captured_at=captured_at
        )

        db.add(snapshot)
        snapshots_saved += 1

    db.commit()

    return {
        "streamer": streamer.name,
        "handle": handle,
        "channel_id": channel_id,
        "videos_found": len(videos),
        "saved": saved,
        "updated": updated,
        "snapshots_saved": snapshots_saved,
        "status": "success"
    }

def collect_youtube_videos(
    db: Session,
    streamer_id: Optional[int] = None,
    limit_per_channel: int = 20
) -> dict:
    """Collect recent uploads from registered active YouTube accounts."""
    query = (
        db.query(Streamer, StreamerAccount)
        .join(StreamerAccount, Streamer.id == StreamerAccount.streamer_id)
        .filter(
            Streamer.is_active.is_(True),
            StreamerAccount.is_active.is_(True),
            StreamerAccount.platform == "youtube"
        )
    )

    if streamer_id is not None:
        query = query.filter(Streamer.id == streamer_id)

    accounts = query.order_by(
        Streamer.priority.desc()
    ).all()

    results = []

    for streamer, account in accounts:
        try:
            result = collect_channel(
                db,
                streamer,
                account,
                limit=limit_per_channel
            )
            results.append(result)

        except YouTubeAPIError as exc:
            db.rollback()
            results.append({
                "streamer": streamer.name,
                "handle": account.username,
                "status": "api_error",
                "error": str(exc)
            })

        except Exception as exc:
            db.rollback()
            results.append({
                "streamer": streamer.name,
                "handle": account.username,
                "status": "error",
                "error": str(exc)
            })

    return {
        "platform": "youtube",
        "channels_checked": len(accounts),
        "total_saved": sum(item.get("saved", 0) for item in results),
        "results": results
    }
