
import os

import httpx
from dotenv import load_dotenv

load_dotenv()

KICK_TOKEN_URL = "https://id.kick.com/oauth/token"
KICK_API_BASE = "https://api.kick.com/public/v1"


def get_app_access_token() -> str:
    client_id = os.getenv("KICK_CLIENT_ID")
    client_secret = os.getenv("KICK_CLIENT_SECRET")

    if not client_id or not client_secret:
        raise RuntimeError(
            "KICK_CLIENT_ID or KICK_CLIENT_SECRET is missing in .env"
        )

    response = httpx.post(
        KICK_TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
        headers={
            "Content-Type": "application/x-www-form-urlencoded"
        },
        timeout=20,
    )

    response.raise_for_status()
    token_data = response.json()

    access_token = token_data.get("access_token")

    if not access_token:
        raise RuntimeError("Kick did not return an access token")

    return access_token


def get_api_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }


def get_live_streams(limit: int = 100) -> list:
    token = get_app_access_token()

    response = httpx.get(
        f"{KICK_API_BASE}/livestreams",
        headers=get_api_headers(token),
        params={
            "limit": min(max(limit, 1), 100),
            "sort": "viewer_count",
        },
        timeout=30,
    )

    response.raise_for_status()

    result = response.json()
    return result.get("data", [])


def get_categories() -> list:
    token = get_app_access_token()

    response = httpx.get(
        f"{KICK_API_BASE}/categories",
        headers=get_api_headers(token),
        timeout=30,
    )

    response.raise_for_status()

    result = response.json()
    return result.get("data", [])


def test_connection() -> dict:
    token = get_app_access_token()

    headers = get_api_headers(token)

    response = httpx.get(
        f"{KICK_API_BASE}/livestreams",
        headers=headers,
        params={"limit": 10, "sort": "viewer_count"},
        timeout=30,
    )

    response.raise_for_status()

    result = response.json()
    streams = result.get("data", [])

    return {
        "connected": True,
        "platform": "kick",
        "live_streams_found": len(streams),
        "streams": [
            {
                "broadcaster": stream.get("slug"),
                "title": stream.get("stream_title"),
                "viewers": stream.get("viewer_count"),
                "category": (
                    stream.get("category", {}).get("name")
                    if isinstance(stream.get("category"), dict)
                    else None
                ),
            }
            for stream in streams
        ],
    }

from datetime import datetime, timezone

from app.models.streamer import StreamerSnapshot


def save_live_streams(db) -> dict:
    streams = get_live_streams(limit=100)

    saved = 0

    for stream in streams:
        broadcaster = stream.get("slug")

        if not broadcaster:
            continue

        category_data = stream.get("category") or {}

        category = (
            category_data.get("name")
            if isinstance(category_data, dict)
            else None
        )

        snapshot = StreamerSnapshot(
            platform="kick",
            broadcaster=broadcaster,
            title=stream.get("stream_title"),
            category=category,
            viewer_count=int(stream.get("viewer_count") or 0),
            captured_at=datetime.now(timezone.utc),
        )

        db.add(snapshot)
        saved += 1

    db.commit()

    return {
        "platform": "kick",
        "streams_found": len(streams),
        "snapshots_saved": saved,
    }
