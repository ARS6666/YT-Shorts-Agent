
import bisect
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import cv2

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.clip import Clip
from app.services.face_tracking import detect_faces_in_video
from app.services.transcription import transcribe_video
from app.services.subtitles import (
    generate_ass_subtitles,
    generate_sfx_track,
)


router = APIRouter(prefix="/editor", tags=["Clip Editor"])

BASE_DIR = Path(__file__).resolve().parents[2]
EDIT_DIR = BASE_DIR / "data" / "edits"
EDIT_DIR.mkdir(parents=True, exist_ok=True)


# =========================================================
# RENDER SETTINGS
# =========================================================

class RenderRequest(BaseModel):
    clip_id: int

    # Video and audio
    zoom: float = Field(default=1.0, ge=1.0, le=1.5)
    volume: float = Field(default=1.0, ge=0.0, le=2.0)

    # Crop
    crop_mode: str = Field(
        default="auto",
        pattern="^(auto|center|manual|stream_split)$",
    )

    manual_x: float = Field(default=0.5, ge=0.0, le=1.0)
    manual_y: float = Field(default=0.5, ge=0.0, le=1.0)

    split_ratio: float = Field(default=0.5, ge=0.35, le=0.65)
    face_scale: float = Field(default=3.4, ge=2.0, le=6.0)

    gameplay_x: float = Field(default=0.5, ge=0.0, le=1.0)
    gameplay_y: float = Field(default=0.5, ge=0.0, le=1.0)

    # Subtitles
    subtitles_enabled: bool = True

    caption_display_mode: str = Field(
        default="word",
        pattern="^(word|phrase)$",
    )

    caption_size: str = Field(
        default="extra_large",
        pattern="^(small|medium|large|extra_large)$",
    )

    caption_font_size: int | None = Field(
        default=None,
        ge=40,
        le=140,
    )

    caption_color: str = Field(
        default="mrbeast",
        pattern="^(mrbeast|white|green|cyan|pink)$",
    )

    caption_bold: bool = True

    caption_outline: str = Field(
        default="white_black",
        pattern="^(white_black|black_white|color_black)$",
    )

    caption_shadow: str = Field(
        default="strong",
        pattern="^(none|soft|strong|glow)$",
    )

    caption_position: str = Field(
        default="lower",
        pattern="^(lower|center|upper)$",
    )

    caption_animation: str = Field(
        default="pop_bounce",
        pattern="^(pop_bounce|pop|shake|none)$",
    )

    animation_intensity: float = Field(
        default=1.0,
        ge=0.5,
        le=1.5,
    )

    # Sound effects
    sound_effects: bool = True

    sfx_volume: float = Field(
        default=0.25,
        ge=0.0,
        le=1.0,
    )


# =========================================================
# SYSTEM TOOLS
# =========================================================

def check_tools():
    if not shutil.which("ffmpeg"):
        raise HTTPException(
            status_code=500,
            detail="FFmpeg is not available in PATH.",
        )

    if not shutil.which("ffprobe"):
        raise HTTPException(
            status_code=500,
            detail="FFprobe is not available in PATH.",
        )


# =========================================================
# DOWNLOAD CLIP
# =========================================================

def download_clip(url: str, output_dir: Path) -> Path:
    output_template = str(output_dir / "source.%(ext)s")

    ffmpeg_path = shutil.which("ffmpeg")

    command = [
        sys.executable,
        "-m",
        "yt_dlp",
        "--no-warnings",
        "--no-playlist",
        "-f",
        "bv*+ba/b",
        "--merge-output-format",
        "mp4",
        "--ffmpeg-location",
        ffmpeg_path,
        "-o",
        output_template,
        url,
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=300,
    )

    if result.returncode != 0:
        raise HTTPException(
            status_code=502,
            detail=(
                "Twitch download failed: "
                + result.stderr[-2000:]
            ),
        )

    candidates = [
        path
        for path in output_dir.glob("source.*")
        if path.suffix.lower() in (
            ".mp4",
            ".mkv",
            ".webm",
            ".mov",
        )
    ]

    if not candidates:
        raise HTTPException(
            status_code=502,
            detail="Downloaded video file was not found.",
        )

    return candidates[0]


# =========================================================
# FACE TRACKING
# =========================================================

def interpolate_tracking(points, timestamp):
    if not points:
        return None

    times = [point["time"] for point in points]
    index = bisect.bisect_left(times, timestamp)

    if index <= 0:
        return points[0]

    if index >= len(points):
        return points[-1]

    previous = points[index - 1]
    following = points[index]

    duration = following["time"] - previous["time"]

    if duration <= 0:
        return previous

    ratio = (timestamp - previous["time"]) / duration

    result = {"time": timestamp}

    for field in ("x", "y", "width", "height"):
        result[field] = (
            previous[field]
            + (following[field] - previous[field]) * ratio
        )

    result["confidence"] = min(
        previous.get("confidence", 0),
        following.get("confidence", 0),
    )

    return result


# =========================================================
# VIDEO CROPPING
# =========================================================

def crop_panel(
    frame,
    center_x,
    center_y,
    output_width,
    output_height,
    zoom=1.0,
):
    height, width = frame.shape[:2]

    target_ratio = output_width / output_height
    source_ratio = width / height

    if source_ratio > target_ratio:
        crop_height = height / zoom
        crop_width = crop_height * target_ratio
    else:
        crop_width = width / zoom
        crop_height = crop_width / target_ratio

    crop_width = max(2, min(width, int(crop_width)))
    crop_height = max(2, min(height, int(crop_height)))

    center_x = max(0.0, min(1.0, center_x)) * width
    center_y = max(0.0, min(1.0, center_y)) * height

    left = int(center_x - crop_width / 2)
    top = int(center_y - crop_height / 2)

    left = max(0, min(left, width - crop_width))
    top = max(0, min(top, height - crop_height))

    cropped = frame[
        top:top + crop_height,
        left:left + crop_width,
    ]

    return cv2.resize(
        cropped,
        (output_width, output_height),
        interpolation=cv2.INTER_LANCZOS4,
    )


def crop_face_panel(
    frame,
    face,
    output_width,
    output_height,
    face_scale,
):
    height, width = frame.shape[:2]

    face_width = max(1.0, face["width"] * width)
    face_height = max(1.0, face["height"] * height)

    target_ratio = output_width / output_height

    crop_height = face_height * face_scale
    crop_width = crop_height * target_ratio

    if crop_width > width:
        crop_width = width
        crop_height = crop_width / target_ratio

    if crop_height > height:
        crop_height = height
        crop_width = crop_height * target_ratio

    crop_width = max(2, min(width, int(crop_width)))
    crop_height = max(2, min(height, int(crop_height)))

    center_x = face["x"] * width
    center_y = face["y"] * height

    left = int(center_x - crop_width / 2)
    top = int(center_y - crop_height / 2)

    left = max(0, min(left, width - crop_width))
    top = max(0, min(top, height - crop_height))

    cropped = frame[
        top:top + crop_height,
        left:left + crop_width,
    ]

    return cv2.resize(
        cropped,
        (output_width, output_height),
        interpolation=cv2.INTER_LANCZOS4,
    )


# =========================================================
# CREATE VERTICAL VIDEO
# =========================================================

def create_vertical_video(source_path, silent_path, payload):
    tracking_points = []

    needs_tracking = payload.crop_mode in (
        "auto",
        "stream_split",
    )

    if needs_tracking:
        analysis = detect_faces_in_video(
            source_path,
            sample_interval=0.5,
            max_width=960,
            confidence_threshold=0.75,
        )

        tracking_points = analysis.get(
            "tracking_points",
            [],
        )

    if payload.crop_mode == "stream_split" and not tracking_points:
        raise HTTPException(
            status_code=422,
            detail=(
                "No streamer face was detected. "
                "Try another clip or use Auto/Center mode."
            ),
        )

    capture = cv2.VideoCapture(str(source_path))

    if not capture.isOpened():
        raise RuntimeError(
            "Could not open downloaded video."
        )

    fps = capture.get(cv2.CAP_PROP_FPS)

    if fps <= 0:
        fps = 30.0

    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))

    if width <= 0 or height <= 0:
        capture.release()
        raise RuntimeError(
            "Invalid source video dimensions."
        )

    writer = cv2.VideoWriter(
        str(silent_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (1080, 1920),
    )

    if not writer.isOpened():
        capture.release()
        raise RuntimeError(
            "Could not initialize video writer."
        )

    frame_index = 0

    try:
        while True:
            success, frame = capture.read()

            if not success:
                break

            timestamp = frame_index / fps

            if payload.crop_mode == "stream_split":
                face = interpolate_tracking(
                    tracking_points,
                    timestamp,
                )

                if not face or face.get("width", 0) <= 0:
                    raise RuntimeError(
                        "Face tracking data is unavailable for this frame."
                    )

                top_height = int(
                    1920 * payload.split_ratio
                )

                bottom_height = 1920 - top_height

                top_panel = crop_face_panel(
                    frame,
                    face,
                    1080,
                    top_height,
                    payload.face_scale,
                )

                bottom_panel = crop_panel(
                    frame,
                    payload.gameplay_x,
                    payload.gameplay_y,
                    1080,
                    bottom_height,
                    payload.zoom,
                )

                output_frame = cv2.vconcat([
                    top_panel,
                    bottom_panel,
                ])

            else:
                if payload.crop_mode == "manual":
                    center_x = payload.manual_x
                    center_y = payload.manual_y

                elif (
                    payload.crop_mode == "auto"
                    and tracking_points
                ):
                    face = interpolate_tracking(
                        tracking_points,
                        timestamp,
                    )

                    center_x = face["x"]
                    center_y = face["y"]

                else:
                    center_x = 0.5
                    center_y = 0.5

                output_frame = crop_panel(
                    frame,
                    center_x,
                    center_y,
                    1080,
                    1920,
                    payload.zoom,
                )

            writer.write(output_frame)
            frame_index += 1

    finally:
        capture.release()
        writer.release()

    if frame_index == 0:
        raise RuntimeError(
            "No frames were processed."
        )

    return {
        "frames_processed": frame_index,
        "fps": round(fps, 2),
        "tracking_samples": len(tracking_points),
    }


# =========================================================
# BURN SUBTITLES
# =========================================================

def burn_subtitles(
    video_path,
    subtitle_path,
    output_path,
):
    fonts_dir = BASE_DIR / "assets" / "fonts"

    subtitle_relative = (
        subtitle_path.relative_to(BASE_DIR).as_posix()
    )

    fonts_relative = (
        fonts_dir.relative_to(BASE_DIR).as_posix()
    )

    subtitle_filter = (
        f"ass=filename='{subtitle_relative}':"
        f"fontsdir='{fonts_relative}'"
    )

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vf",
        subtitle_filter,
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(output_path),
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=900,
        cwd=str(BASE_DIR),
    )

    if result.returncode != 0 or not output_path.exists():
        raise RuntimeError(
            "Subtitle rendering failed: "
            + result.stderr[-2500:]
        )

    return output_path


# =========================================================
# FINAL AUDIO + VIDEO RENDER
# =========================================================

def mux_final_video(
    render_video_path,
    source_path,
    output_path,
    payload,
    sfx_path=None,
):
    if sfx_path and sfx_path.exists():
        command = [
            "ffmpeg",
            "-y",
            "-i",
            str(render_video_path),
            "-i",
            str(source_path),
            "-i",
            str(sfx_path),
            "-map",
            "0:v:0",
            "-filter_complex",
            (
                f"[1:a:0]volume={payload.volume}[base];"
                f"[2:a:0]volume={payload.sfx_volume}[fx];"
                "[base][fx]amix=inputs=2:"
                "duration=first:"
                "dropout_transition=0[aout]"
            ),
            "-map",
            "[aout]",
            "-vf",
            "fps=30",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            "-movflags",
            "+faststart",
            str(output_path),
        ]

    else:
        command = [
            "ffmpeg",
            "-y",
            "-i",
            str(render_video_path),
            "-i",
            str(source_path),
            "-map",
            "0:v:0",
            "-map",
            "1:a?",
            "-vf",
            "fps=30",
            "-af",
            f"volume={payload.volume}",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            "-movflags",
            "+faststart",
            str(output_path),
        ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=900,
    )

    if result.returncode != 0 or not output_path.exists():
        raise RuntimeError(
            "FFmpeg rendering failed: "
            + result.stderr[-2500:]
        )

    return output_path


# =========================================================
# RENDER ENDPOINT
# =========================================================

@router.post("/render")
def render_clip(
    payload: RenderRequest,
    db: Session = Depends(get_db),
):
    check_tools()

    clip = (
        db.query(Clip)
        .filter(Clip.id == payload.clip_id)
        .first()
    )

    if not clip:
        raise HTTPException(
            status_code=404,
            detail="Clip not found.",
        )

    if clip.platform != "twitch":
        raise HTTPException(
            status_code=400,
            detail="Only Twitch clips are supported.",
        )

    if not clip.url:
        raise HTTPException(
            status_code=400,
            detail="Clip URL is missing.",
        )

    job_id = uuid.uuid4().hex[:12]

    job_dir = EDIT_DIR / job_id
    job_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        # 1. Download original clip
        source_path = download_clip(
            clip.url,
            job_dir,
        )

        silent_path = job_dir / "vertical_silent.mp4"

        output_path = (
            job_dir
            / f"trendhunter_{clip.id}_{job_id}.mp4"
        )

        # 2. Crop and convert to vertical format
        processing = create_vertical_video(
            source_path,
            silent_path,
            payload,
        )

        # 3. Transcription
        transcription = {
            "language": "en",
            "text": "",
            "words": [],
            "word_count": 0,
        }

        subtitle_info = None
        render_video_path = silent_path
        sfx_path = None

        needs_transcription = (
            payload.subtitles_enabled
            or payload.sound_effects
        )

        if needs_transcription:
            transcription = transcribe_video(
                source_path
            )

        # 4. Generate and burn subtitles
        if (
            payload.subtitles_enabled
            and transcription.get("words")
        ):
            subtitle_path = (
                job_dir / "subtitles.ass"
            )

            subtitled_path = (
                job_dir / "vertical_subtitled.mp4"
            )

            selected_font_size = (
                payload.caption_font_size
                if payload.caption_font_size is not None
                else payload.caption_size
            )

            subtitle_info = generate_ass_subtitles(
                transcription,
                subtitle_path,
                video_width=1080,
                video_height=1920,
                font_size=selected_font_size,
                color_preset=payload.caption_color,
                display_mode=payload.caption_display_mode,
                animation=payload.caption_animation,
                intensity=payload.animation_intensity,
                position=payload.caption_position,
                bold=payload.caption_bold,
                outline_preset=payload.caption_outline,
                shadow_preset=payload.caption_shadow,
            )

            burn_subtitles(
                silent_path,
                subtitle_path,
                subtitled_path,
            )

            render_video_path = subtitled_path

        # 5. Generate sound effects
        if (
            payload.sound_effects
            and transcription.get("words")
        ):
            sfx_path = job_dir / "caption_sfx.wav"

            duration = (
                processing["frames_processed"]
                / processing["fps"]
            )

            generate_sfx_track(
                transcription,
                sfx_path,
                duration=duration,
                volume=payload.sfx_volume,
                intensity=payload.animation_intensity,
            )

        # 6. Final FFmpeg render
        mux_final_video(
            render_video_path,
            source_path,
            output_path,
            payload,
            sfx_path=sfx_path,
        )

        applied_mode = payload.crop_mode

        if (
            payload.crop_mode == "auto"
            and processing["tracking_samples"] == 0
        ):
            applied_mode = "center_fallback"

        # 7. Response
        return {
            "status": "completed",
            "clip_id": clip.id,
            "job_id": job_id,
            "filename": output_path.name,
            "download_url": f"/editor/download/{job_id}",
            "resolution": "1080x1920",
            "format": "mp4",
            "crop_mode": applied_mode,
            "tracking_samples": processing["tracking_samples"],
            "frames_processed": processing["frames_processed"],
            "fps": processing["fps"],
            "split_ratio": (
                payload.split_ratio
                if payload.crop_mode == "stream_split"
                else None
            ),
            "face_scale": (
                payload.face_scale
                if payload.crop_mode == "stream_split"
                else None
            ),
            "subtitles": {
                "enabled": bool(subtitle_info),
                "style": "Rubik",
                "font": "Rubik",
                "font_size": (
                    subtitle_info["font_size"]
                    if subtitle_info
                    else None
                ),
                "color": payload.caption_color,
                "outline": payload.caption_outline,
                "shadow": payload.caption_shadow,
                "bold": payload.caption_bold,
                "display_mode": payload.caption_display_mode,
                "position": payload.caption_position,
                "animation": payload.caption_animation,
                "sound_effects": bool(
                    sfx_path and sfx_path.exists()
                ),
                "language": transcription.get(
                    "language",
                    "en",
                ),
                "text": transcription.get("text", ""),
                "word_count": transcription.get(
                    "word_count",
                    0,
                ),
                "caption_groups": (
                    subtitle_info["caption_groups"]
                    if subtitle_info
                    else 0
                ),
            },
        }

    except subprocess.TimeoutExpired as exc:
        raise HTTPException(
            status_code=504,
            detail="Video processing timed out.",
        ) from exc

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Video editing failed: {str(exc)}",
        ) from exc


# =========================================================
# DOWNLOAD ENDPOINT
# =========================================================

@router.get("/download/{job_id}")
def download_rendered_clip(job_id: str):
    if not job_id.isalnum() or len(job_id) != 12:
        raise HTTPException(
            status_code=400,
            detail="Invalid job ID.",
        )

    job_dir = EDIT_DIR / job_id

    if not job_dir.exists():
        raise HTTPException(
            status_code=404,
            detail="Rendered video not found.",
        )

    files = list(
        job_dir.glob("trendhunter_*.mp4")
    )

    if not files:
        raise HTTPException(
            status_code=404,
            detail="Rendered video not found.",
        )

    return FileResponse(
        path=files[0],
        media_type="video/mp4",
        filename=files[0].name,
    )
