
import re
from pathlib import Path
from urllib.parse import urlparse
import json
from fastapi.responses import FileResponse
from app.services.transcription import transcribe_video
import yt_dlp
import subprocess
import shutil
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field


router = APIRouter(
    prefix="/youtube",
    tags=["YouTube Clipper"],
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DOWNLOAD_DIR = PROJECT_ROOT / "data" / "youtube_downloads"

def make_safe_filename(title: str, fallback: str = "youtube_video") -> str:
    title = str(title or "").strip()

    # Remove characters that are invalid in Windows filenames
    title = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", title)

    # Convert spaces and special characters to underscores
    title = re.sub(r"\s+", "_", title)
    title = re.sub(r"[^A-Za-z0-9_-]", "_", title)
    title = re.sub(r"_+", "_", title)
    title = title.strip("_-")

    return (title or fallback)[:100]

class YouTubeInfoRequest(BaseModel):
    url: str = Field(min_length=5, max_length=2048)


def validate_youtube_url(url: str) -> str:
    url = url.strip()
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()

    allowed_hosts = {
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "music.youtube.com",
        "youtu.be",
        "www.youtube-nocookie.com",
    }

    if parsed.scheme not in ("http", "https") or hostname not in allowed_hosts:
        raise HTTPException(
            status_code=400,
            detail="Please provide a valid YouTube URL.",
        )

    return url


def format_duration(seconds):
    if seconds is None:
        return "Unknown"

    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)

    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    return f"{minutes:02d}:{secs:02d}"


def get_video_info(url: str):
    options = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        return ydl.extract_info(url, download=False)


@router.post("/info")
def get_youtube_video_info(payload: YouTubeInfoRequest):
    url = validate_youtube_url(payload.url)

    try:
        info = get_video_info(url)

        if not info:
            raise ValueError("No video information returned.")

        duration = info.get("duration")

        return {
            "success": True,
            "video": {
                "id": info.get("id"),
                "title": info.get("title"),
                "description": info.get("description"),
                "channel": info.get("channel") or info.get("uploader"),
                "channel_url": info.get("channel_url"),
                "thumbnail": info.get("thumbnail"),
                "duration": duration,
                "duration_formatted": format_duration(duration),
                "view_count": info.get("view_count"),
                "like_count": info.get("like_count"),
                "upload_date": info.get("upload_date"),
                "original_url": info.get("webpage_url") or url,
            },
        }

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Could not extract YouTube video information: {str(exc)}",
        ) from exc


@router.post("/download")
def download_youtube_video(payload: YouTubeInfoRequest):
    url = validate_youtube_url(payload.url)

    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    try:
        info = get_video_info(url)
        video_id = info.get("id")

        if not video_id or not re.fullmatch(r"[a-zA-Z0-9_-]+", video_id):
            raise ValueError("Invalid video ID.")

        duration = info.get("duration")

        if duration and duration > 3 * 60 * 60:
            raise HTTPException(
                status_code=400,
                detail="Videos longer than 3 hours are not supported.",
            )

        output_template = str(
            DOWNLOAD_DIR / f"{video_id}.%(ext)s"
        )

        options = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "format": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
            "merge_output_format": "mp4",
            "outtmpl": output_template,
        }

        with yt_dlp.YoutubeDL(options) as ydl:
            downloaded_info = ydl.extract_info(
                url,
                download=True,
            )

        expected_file = DOWNLOAD_DIR / f"{video_id}.mp4"

        if not expected_file.exists():
            candidates = list(DOWNLOAD_DIR.glob(f"{video_id}.*"))
            candidates = [
                file for file in candidates
                if file.suffix.lower() in {".mp4", ".mkv", ".webm"}
            ]

            if not candidates:
                raise FileNotFoundError(
                    "Downloaded video file was not found."
                )

            expected_file = candidates[0]
            video_title = downloaded_info.get("title") or video_id

            metadata_path = DOWNLOAD_DIR / f"{video_id}.info.json"
            metadata_path.write_text(
                json.dumps(
                    {
                        "id": video_id,
                        "title": video_title,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

        return {
            "success": True,
            "message": "Video downloaded successfully.",
            "video": {
                "id": video_id,
                "title": video_title,
                "duration": downloaded_info.get("duration"),
                "duration_formatted": format_duration(
                    downloaded_info.get("duration")
                ),
                "file_name": expected_file.name,
                "file_path": str(expected_file.resolve()),
                "file_size": expected_file.stat().st_size,
            },
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"YouTube download failed: {str(exc)}",
        ) from exc

@router.post("/transcribe/{video_id}")
def transcribe_youtube_video(video_id: str):
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", video_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid video ID.",
        )

    video_files = [
        file for file in DOWNLOAD_DIR.glob(f"{video_id}.*")
        if file.suffix.lower() in {".mp4", ".mkv", ".webm"}
    ]

    if not video_files:
        raise HTTPException(
            status_code=404,
            detail="Downloaded video not found. Download it first.",
        )

    video_path = video_files[0]

    try:
        transcription = transcribe_video(str(video_path))

        if not transcription:
            raise ValueError("Transcription returned no result.")

        words = transcription.get("words", [])
        text = transcription.get("text", "")

        if not text and words:
            text = " ".join(
                str(word.get("word", "")).strip()
                for word in words
            ).strip()

        result = {
            "success": True,
            "video_id": video_id,
            "language": transcription.get("language", "en"),
            "text": text,
            "word_count": transcription.get(
                "word_count",
                len(words),
            ),
            "words": words,
        }

        transcript_path = DOWNLOAD_DIR / f"{video_id}.transcript.json"

        transcript_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return {
            **result,
            "transcript_file": str(transcript_path.resolve()),
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Transcription failed: {str(exc)}",
        ) from exc


from collections import Counter


HOOK_WORDS = {
    "wait", "what", "why", "how", "bro", "no", "never",
    "actually", "insane", "crazy", "impossible", "look",
    "listen", "guess", "secret", "money", "free", "win",
    "lose", "dead", "help", "stop", "oh", "wow",
}

REACTION_WORDS = {
    "laugh", "laughing", "lmao", "lol", "haha", "hahaha",
    "scream", "screaming", "surprised", "shocked",
    "angry", "rage", "bruh", "damn", "wtf",
}

EMOTION_WORDS = {
    "amazing", "terrible", "crazy", "insane", "unbelievable",
    "hilarious", "embarrassing", "ridiculous", "worst",
    "best", "perfect", "fail", "mistake", "unexpected",
}


def normalize_word(item):
    word = str(
        item.get("word")
        or item.get("text")
        or ""
    ).strip()

    start = item.get("start", item.get("start_time", 0))
    end = item.get("end", item.get("end_time", start))

    try:
        start = float(start)
        end = float(end)
    except (TypeError, ValueError):
        return None

    if not word or end <= start:
        return None

    return {
        "word": word,
        "start": start,
        "end": end,
    }


def score_moment(words, start, end):
    selected = [
        word for word in words
        if word["start"] < end and word["end"] > start
    ]

    if len(selected) < 8:
        return None

    text = " ".join(item["word"] for item in selected)
    tokens = [
        token.lower().strip(".,!?;:\"'()[]{}")
        for token in (item["word"] for item in selected)
    ]

    tokens = [token for token in tokens if token]

    if not tokens:
        return None

    hook_count = sum(token in HOOK_WORDS for token in tokens)
    reaction_count = sum(token in REACTION_WORDS for token in tokens)
    emotion_count = sum(token in EMOTION_WORDS for token in tokens)

    exclamations = text.count("!")
    questions = text.count("?")

    duration = max(1, end - start)
    density = len(selected) / duration

    density_score = min(25, density * 2.5)
    hook_score = min(25, hook_count * 5)
    reaction_score = min(20, reaction_count * 8)
    emotion_score = min(15, emotion_count * 5)
    punctuation_score = min(
        15,
        exclamations * 3 + questions * 2,
    )

    total = min(
        100,
        density_score
        + hook_score
        + reaction_score
        + emotion_score
        + punctuation_score,
    )

    reasons = []

    if hook_count:
        reasons.append("Strong hook words")

    if reaction_count:
        reasons.append("Possible funny or emotional reaction")

    if emotion_count:
        reasons.append("Emotional language")

    if exclamations or questions:
        reasons.append("Expressive dialogue")

    if density >= 3:
        reasons.append("High speech activity")

    return {
        "start": round(start, 2),
        "end": round(end, 2),
        "duration": round(end - start, 2),
        "score": round(total, 1),
        "text": text,
        "word_count": len(selected),
        "reasons": reasons,
    }


def detect_viral_moments(
    words,
    min_duration=25,
    max_duration=55,
    max_clips=8,
):
    normalized = []

    for item in words:
        if not isinstance(item, dict):
            continue

        word = normalize_word(item)

        if word:
            normalized.append(word)

    normalized.sort(key=lambda item: item["start"])

    if len(normalized) < 8:
        raise ValueError("Not enough timestamped words to analyze.")

    video_end = max(item["end"] for item in normalized)

    if video_end < min_duration:
        raise ValueError("Video is too short to generate Shorts.")

    window_size = min(max_duration, video_end)
    step = 8

    candidates = []

    start = 0.0

    while start + min_duration <= video_end:
        end = min(start + window_size, video_end)

        if end - start < min_duration:
            break

        candidate = score_moment(normalized, start, end)

        if candidate:
            candidates.append(candidate)

        start += step

    candidates.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    selected = []

    for candidate in candidates:
        overlaps = False

        for existing in selected:
            intersection = max(
                0,
                min(candidate["end"], existing["end"])
                - max(candidate["start"], existing["start"]),
            )

            shorter_duration = min(
                candidate["duration"],
                existing["duration"],
            )

            if shorter_duration and intersection / shorter_duration > 0.5:
                overlaps = True
                break

        if not overlaps:
            selected.append(candidate)

        if len(selected) >= max_clips:
            break

    selected.sort(key=lambda item: item["start"])

    for index, moment in enumerate(selected, start=1):
        moment["id"] = index
        moment["title"] = " ".join(
            moment["text"].split()[:8]
        )

    return selected


class AnalyzeVideoRequest(BaseModel):
    max_clips: int = Field(default=8, ge=1, le=20)
    min_duration: int = Field(default=25, ge=15, le=60)
    max_duration: int = Field(default=55, ge=20, le=90)


@router.post("/analyze/{video_id}")
def analyze_youtube_video(
    video_id: str,
    payload: AnalyzeVideoRequest,
):
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", video_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid video ID.",
        )

    transcript_path = (
        DOWNLOAD_DIR / f"{video_id}.transcript.json"
    )

    if not transcript_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Transcript not found. Transcribe the video first.",
        )

    try:
        transcript_data = json.loads(
            transcript_path.read_text(encoding="utf-8")
        )

        words = transcript_data.get("words", [])

        moments = detect_viral_moments(
            words,
            min_duration=payload.min_duration,
            max_duration=payload.max_duration,
            max_clips=payload.max_clips,
        )

        result = {
            "success": True,
            "video_id": video_id,
            "total_moments": len(moments),
            "moments": moments,
        }

        output_path = (
            DOWNLOAD_DIR / f"{video_id}.moments.json"
        )

        output_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return result

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Moment analysis failed: {str(exc)}",
        ) from exc
def find_downloaded_video(video_id: str):
    for ext in ("mp4", "mkv", "webm", "mov"):
        path = DOWNLOAD_DIR / f"{video_id}.{ext}"
        if path.exists():
            return path
    return None


@router.post("/generate/{video_id}")
def generate_youtube_clips(video_id: str):
    if not re.fullmatch(r"[A-Za-z0-9_-]{6,20}", video_id):
        raise HTTPException(status_code=400, detail="Invalid video ID")

    video_path = find_downloaded_video(video_id)

    if not video_path:
        raise HTTPException(
            status_code=404,
            detail="Downloaded video not found. Download it first."
        )

    moments_file = DOWNLOAD_DIR / f"{video_id}.moments.json"

    if not moments_file.exists():
        raise HTTPException(
            status_code=404,
            detail="Moments file not found. Analyze the video first."
        )

    try:
        with open(moments_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        moments = data.get("moments", [])

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not read moments: {str(exc)}"
        )

    if not moments:
        raise HTTPException(
            status_code=400,
            detail="No moments available to generate."
        )

    if not shutil.which("ffmpeg"):
        raise HTTPException(
            status_code=500,
            detail="FFmpeg is not installed or not available in PATH."
        )

    output_dir = DOWNLOAD_DIR / video_id / "clips"
    output_dir.mkdir(parents=True, exist_ok=True)

    metadata_path = DOWNLOAD_DIR / f"{video_id}.info.json"
    source_title = video_id

    if metadata_path.exists():
        try:
            metadata = json.loads(
                metadata_path.read_text(encoding="utf-8")
            )
            source_title = metadata.get("title") or video_id
        except (OSError, ValueError, TypeError):
            source_title = video_id

    safe_title = make_safe_filename(source_title, video_id)
    generated = []
    errors = []

    for index, moment in enumerate(moments, start=1):
        try:
            start = float(moment.get("start", 0))
            end = float(moment.get("end", 0))
            duration = end - start

            if start < 0 or duration < 5 or duration > 120:
                errors.append({
                    "moment_id": moment.get("id", index),
                    "error": "Invalid clip duration or timestamps"
                })
                continue

            output_path = output_dir / f"{safe_title}_{index:02d}.mp4"
            
            command = [
                "ffmpeg",
                "-y",
                "-i", str(video_path),
                "-ss", str(start),
                "-t", str(duration),
                "-map", "0:v:0",
                "-map", "0:a?",
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-crf", "21",
                "-c:a", "aac",
                "-b:a", "160k",
                "-movflags", "+faststart",
                str(output_path),
            ]

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=600
            )

            if result.returncode != 0 or not output_path.exists():
                errors.append({
                    "moment_id": moment.get("id", index),
                    "error": result.stderr[-1000:]
                })
                continue

            generated.append({
                "id": moment.get("id", index),
                "title": moment.get("title", f"Clip {index}"),
                "start": start,
                "end": end,
                "duration": round(duration, 2),
                "score": moment.get("score", 0),
                "transcript": moment.get("transcript") or moment.get("text", ""),
                "file_name": output_path.name,
                "file_path": str(output_path),
                "file_size_mb": round(
                    output_path.stat().st_size / (1024 * 1024), 2
                ),
            })

        except subprocess.TimeoutExpired:
            errors.append({
                "moment_id": moment.get("id", index),
                "error": "FFmpeg processing timed out"
            })

        except Exception as exc:
            errors.append({
                "moment_id": moment.get("id", index),
                "error": str(exc)
            })

    return {
        "success": len(generated) > 0,
        "video_id": video_id,
        "total_requested": len(moments),
        "total_generated": len(generated),
        "total_errors": len(errors),
        "output_directory": str(output_dir),
        "clips": generated,
        "errors": errors,
    }



import subprocess
import uuid


CLIPS_DIR = PROJECT_ROOT / "data" / "generated_shorts"


def find_downloaded_video(video_id: str):
    if not re.fullmatch(r"[A-Za-z0-9_-]{6,20}", video_id):
        raise HTTPException(status_code=400, detail="Invalid video ID")

    for extension in ("mp4", "mkv", "webm"):
        path = DOWNLOAD_DIR / f"{video_id}.{extension}"
        if path.exists():
            return path

    raise HTTPException(status_code=404, detail="Downloaded video not found")


@router.post("/generate/{video_id}")
def generate_clips(video_id: str):
    moments_file = DOWNLOAD_DIR / f"{video_id}.moments.json"

    if not moments_file.exists():
        raise HTTPException(
            status_code=404,
            detail="Analyze the video first"
        )

    source_path = find_downloaded_video(video_id)

    try:
        with open(moments_file, "r", encoding="utf-8") as file:
            data = json.load(file)

        moments = data.get("moments", [])

        if not moments:
            raise HTTPException(
                status_code=400,
                detail="No moments found"
            )

        output_dir = CLIPS_DIR / video_id
        output_dir.mkdir(parents=True, exist_ok=True)

        generated = []

        for index, moment in enumerate(moments, start=1):
            start = max(0, float(moment["start"]))
            end = float(moment["end"])
            duration = end - start

            if duration < 5 or duration > 120:
                continue

            clip_id = uuid.uuid4().hex[:10]
            output_path = output_dir / f"clip_{index:02d}_{clip_id}.mp4"

            command = [
                "ffmpeg",
                "-y",
                "-i", str(source_path),
                "-ss", str(start),
                "-t", str(duration),
                "-map", "0:v:0",
                "-map", "0:a?",
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-crf", "23",
                "-c:a", "aac",
                "-b:a", "128k",
                "-movflags", "+faststart",
                str(output_path),
            ]

            result = subprocess.run(
                command,
                capture_output=True,
                text=True
            )

            if result.returncode != 0 or not output_path.exists():
                continue

            generated.append({
                "id": clip_id,
                "filename": output_path.name,
                "path": str(output_path),
                "title": moment.get("title", f"Clip {index}"),
                "start": start,
                "end": end,
                "duration": round(duration, 2),
                "score": moment.get("score", 0),
                "transcript": moment.get("transcript", ""),
                "size_mb": round(output_path.stat().st_size / (1024 * 1024), 2),
            })

        result_file = output_dir / "clips.json"

        with open(result_file, "w", encoding="utf-8") as file:
            json.dump(generated, file, ensure_ascii=False, indent=2)

        return {
            "success": True,
            "video_id": video_id,
            "total_generated": len(generated),
            "clips": generated,
            "output_dir": str(output_dir),
        }

    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@router.get("/generated-clips")
def list_generated_youtube_clips():
    results = []

    downloads_dir = PROJECT_ROOT / "data" / "youtube_downloads"

    if not downloads_dir.exists():
        return {"items": [], "total": 0}

    for video_dir in downloads_dir.iterdir():
        clips_dir = video_dir / "clips"

        if not clips_dir.is_dir():
            continue

        for clip_path in sorted(clips_dir.glob("*.mp4")):
            if not clip_path.is_file() or clip_path.stat().st_size < 1024:
                continue

            results.append({
                "youtube_clip_id": f"{video_dir.name}/{clip_path.name}",
                "filename": clip_path.name,
                "video_id": video_dir.name,
                "platform": "youtube",
                "source": "youtube",
                "title": f"YouTube Clip - {clip_path.stem}",
                "duration": 0,
            })

    return {
        "items": results,
        "total": len(results),
    }

    results = []

    if not CLIPS_DIR.exists():
        return {"items": [], "total": 0}

    for metadata_file in CLIPS_DIR.glob("*/clips.json"):
        try:
            data = json.loads(metadata_file.read_text(encoding="utf-8"))
            items = data if isinstance(data, list) else data.get("clips", [])

            video_id = metadata_file.parent.name

            for item in items:
                filename = (
                    item.get("filename")
                    or item.get("file_name")
                    or item.get("output")
                )

                if not filename:
                    continue

                path = (metadata_file.parent / filename).resolve()

                if (
                    path.parent != metadata_file.parent.resolve()
                    or not path.is_file()
                    or path.suffix.lower() != ".mp4"
                ):
                    continue

                results.append({
                    **item,
                    "youtube_clip_id": f"{video_id}/{path.name}",
                    "filename": path.name,
                    "video_id": video_id,
                    "platform": "youtube",
                    "source": "youtube",
                    "duration": item.get("duration", 0),
                    "title": item.get("title") or path.stem,
                })

        except (OSError, ValueError, TypeError):
            continue

    return {
        "items": results,
        "total": len(results),
    }