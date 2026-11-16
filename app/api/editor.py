
import bisect
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
import traceback
import cv2
import base64
import binascii
import re
from typing import Optional
import random

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
PROJECT_DIR = BASE_DIR
BACKGROUND_MUSIC_DIR = PROJECT_DIR / "assets" / "audio" / "background_music"

BACKGROUND_MUSIC_DIR = (
    PROJECT_DIR
    / "assets"
    / "audio"
    / "background_music"
)

BACKGROUND_MUSIC_DIR.mkdir(
    parents=True,
    exist_ok=True,
)
class SoundEffectTrack(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    file_name: str = Field(min_length=1, max_length=255)
    file_data: str = Field(min_length=1)

    start_time: float = Field(ge=0, le=3600)
    volume: float = Field(default=0.25, ge=0, le=1)

    visual_impact: bool = True
# =========================================================
# RENDER SETTINGS
# =========================================================

class RenderRequest(BaseModel):
    clip_id: int | None = None
    youtube_clip_id: str | None = Field(
        default=None,
        max_length=100,
    )   
    # Video and audio
    zoom: float = Field(default=1.0, ge=1.0, le=1.5)
    volume: float = Field(default=1.0, ge=0.0, le=2.0)

    # Crop
    crop_mode: str = Field(
        default="auto",
        pattern="^(auto|center|manual|stream_split|gta_split)$",
    )

    # GTA Gameplay Split
    gta_gameplay_file_name: str | None = Field(
        default=None,
        max_length=255,
    )

    gta_gameplay_data: str | None = Field(
        default=None,
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

    caption_glow_intensity: float = Field(
        default=0.8,
        ge=0.0,
        le=1.5,
    )

    caption_position: str = Field(
        default="lower",
        pattern="^(lower|center|upper)$",
    )

    caption_animation: str = Field(
        default="pop_bounce",
        pattern="^(pop_bounce|pop|shake|elastic|slide_up|zoom_in|tilt|fade_pop|pulse|none)$",
    )

    animation_intensity: float = Field(
        default=1.0,
        ge=0.5,
        le=1.5,
    )
    # Sound Effects
    sound_effects: bool = True

    sfx_volume: float = Field(
        default=0.25,
        ge=0.0,
        le=1.0,
    )

    sfx_tracks: list[SoundEffectTrack] = Field(
        default_factory=list,
        max_length=20,
    )

    # Visual Impact FX
    visual_impact_enabled: bool = True

    impact_intensity: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
    )
    # Background music
    bg_music_enabled: bool = False

    bg_music_track: str = Field(
        default="",
        max_length=100,
        pattern=r"^[a-zA-Z0-9_-]*$",
    )

    bg_music_volume: float = Field(
        default=0.20,
        ge=0.0,
        le=1.0,
    )

    bg_music_fade_in: float = Field(
        default=1.5,
        ge=0.0,
        le=30.0,
    )

    bg_music_fade_out: float = Field(
        default=2.0,
        ge=0.0,
        le=30.0,
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


def create_vertical_video(
    source_path,
    silent_path,
    payload,
    gameplay_path=None,
):
    tracking_points = []

    is_gta_split = payload.crop_mode == "gta_split"

    needs_tracking = payload.crop_mode in (
        "auto",
        "stream_split",
        "gta_split",
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

    if payload.crop_mode in ("stream_split", "gta_split"):
        if not tracking_points:
            raise HTTPException(
                status_code=422,
                detail=(
                    "No streamer face was detected. "
                    "Try another clip or use Auto/Center mode."
                ),
            )

    gameplay_capture = None

    if is_gta_split:
        if not gameplay_path:
            raise HTTPException(
                status_code=422,
                detail="Please upload a GTA gameplay video.",
            )

        gameplay_capture = cv2.VideoCapture(
            str(gameplay_path)
        )

        if not gameplay_capture.isOpened():
            raise RuntimeError(
                "Could not open GTA gameplay video."
            )

    capture = cv2.VideoCapture(str(source_path))

    if not capture.isOpened():
        if gameplay_capture:
            gameplay_capture.release()

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

        if gameplay_capture:
            gameplay_capture.release()

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

        if gameplay_capture:
            gameplay_capture.release()

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

            if payload.crop_mode in (
                "stream_split",
                "gta_split",
            ):
                face = interpolate_tracking(
                    tracking_points,
                    timestamp,
                )

                if not face or face.get("width", 0) <= 0:
                    raise RuntimeError(
                        "Face tracking data is unavailable "
                        "for this frame."
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

                if is_gta_split:
                    gameplay_success, gameplay_frame = (
                        gameplay_capture.read()
                    )

                    # Loop GTA gameplay when it reaches its end.
                    if not gameplay_success:
                        gameplay_capture.set(
                            cv2.CAP_PROP_POS_FRAMES,
                            0,
                        )

                        gameplay_success, gameplay_frame = (
                            gameplay_capture.read()
                        )

                    if not gameplay_success:
                        raise RuntimeError(
                            "Could not read frames from GTA gameplay video."
                        )

                    bottom_panel = crop_panel(
                        gameplay_frame,
                        0.5,
                        0.5,
                        1080,
                        bottom_height,
                        payload.zoom,
                    )

                else:
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

        if gameplay_capture:
            gameplay_capture.release()

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
# CUSTOM SOUND EFFECTS
# =========================================================

ALLOWED_SFX_EXTENSIONS = {
    ".mp3",
    ".wav",
    ".m4a",
    ".aac",
    ".ogg",
    ".flac",
}


def save_uploaded_sound_effects(payload, job_dir):
    saved_tracks = []

    if not payload.sound_effects:
        return saved_tracks

    total_size = 0
    max_file_size = 15 * 1024 * 1024
    max_total_size = 50 * 1024 * 1024

    for index, track in enumerate(payload.sfx_tracks):
        extension = Path(track.file_name).suffix.lower()

        if extension not in ALLOWED_SFX_EXTENSIONS:
            raise HTTPException(
                status_code=422,
                detail=f"Unsupported audio format: {extension}",
            )

        safe_name = re.sub(
            r"[^a-zA-Z0-9_-]",
            "_",
            Path(track.file_name).stem,
        )[:80]

        try:
            audio_data = base64.b64decode(
                track.file_data,
                validate=True,
            )
        except (binascii.Error, ValueError):
            raise HTTPException(
                status_code=422,
                detail=f"Invalid audio data for {track.file_name}.",
            )

        if not audio_data:
            raise HTTPException(
                status_code=422,
                detail=f"Empty audio file: {track.file_name}.",
            )

        if len(audio_data) > max_file_size:
            raise HTTPException(
                status_code=413,
                detail=f"Audio file is too large: {track.file_name}.",
            )

        total_size += len(audio_data)

        if total_size > max_total_size:
            raise HTTPException(
                status_code=413,
                detail="Total uploaded sound effects exceed 50 MB.",
            )

        output_path = (
            job_dir
            / f"sfx_{index}_{safe_name}{extension}"
        )

        output_path.write_bytes(audio_data)

        saved_tracks.append({
            "id": track.id,
            "name": track.name,
            "path": output_path,
            "start_time": track.start_time,
            "volume": track.volume,
            "visual_impact": track.visual_impact,
        })

    return saved_tracks

ALLOWED_GAMEPLAY_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".mkv",
    ".webm",
}


def save_gta_gameplay(payload, job_dir):
    if payload.crop_mode != "gta_split":
        return None

    if not payload.gta_gameplay_file_name or not payload.gta_gameplay_data:
        raise HTTPException(
            status_code=422,
            detail="Please upload a GTA gameplay video.",
        )

    extension = Path(
        payload.gta_gameplay_file_name
    ).suffix.lower()

    if extension not in ALLOWED_GAMEPLAY_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail="Unsupported gameplay video format.",
        )

    try:
        video_data = base64.b64decode(
            payload.gta_gameplay_data,
            validate=True,
        )
    except (binascii.Error, ValueError):
        raise HTTPException(
            status_code=422,
            detail="Invalid GTA gameplay video data.",
        )

    if not video_data:
        raise HTTPException(
            status_code=422,
            detail="The gameplay video is empty.",
        )

    max_size = 150 * 1024 * 1024

    if len(video_data) > max_size:
        raise HTTPException(
            status_code=413,
            detail="GTA gameplay video must be smaller than 150 MB.",
        )

    gameplay_path = job_dir / f"gta_gameplay{extension}"
    gameplay_path.write_bytes(video_data)

    return gameplay_path
# =========================================================
# FINAL AUDIO + VIDEO RENDER
# =========================================================

def mux_final_video(
    render_video_path,
    source_path,
    output_path,
    payload,
    sfx_path=None,
    duration=None,
    custom_sfx_tracks=None,
):
    custom_sfx_tracks = custom_sfx_tracks or []

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(render_video_path),
        "-i",
        str(source_path),
    ]

    input_index = 2
    audio_inputs = []

    # -----------------------------------------------------
    # Original streamer audio
    # -----------------------------------------------------

    audio_inputs.append({
        "index": 1,
        "label": "base",
        "filter": f"volume={payload.volume}",
    })

    # -----------------------------------------------------
    # Generated caption sound effects
    # -----------------------------------------------------

    if sfx_path and sfx_path.exists():
        command.extend(["-i", str(sfx_path)])

        audio_inputs.append({
            "index": input_index,
            "label": "caption_sfx",
            "filter": "volume=1",
        })

        input_index += 1

    # -----------------------------------------------------
    # Uploaded custom sound effects
    # -----------------------------------------------------

    for index, track in enumerate(custom_sfx_tracks):
        command.extend([
            "-i",
            str(track["path"]),
        ])

        delay_ms = int(track["start_time"] * 1000)

        audio_filter = (
            f"volume={track['volume']},"
            f"adelay={delay_ms}|{delay_ms}"
        )

        audio_inputs.append({
            "index": input_index,
            "label": f"custom_sfx_{index}",
            "filter": audio_filter,
        })

        input_index += 1

    # -----------------------------------------------------
    # Background music
    # -----------------------------------------------------

    if payload.bg_music_enabled:
        track_name = payload.bg_music_track.strip()

        if not track_name:
            raise HTTPException(
                status_code=422,
                detail="Please select a background music track.",
            )

        allowed_extensions = (
            ".mp3",
            ".wav",
            ".m4a",
            ".aac",
            ".ogg",
        )

        music_path = None

        for extension in allowed_extensions:
            candidate = (
                BACKGROUND_MUSIC_DIR
                / f"{track_name}{extension}"
            )

            if candidate.is_file():
                music_path = candidate
                break

        if music_path is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Background music '{track_name}' "
                    "was not found."
                ),
            )

        command.extend([
            "-stream_loop",
            "-1",
            "-i",
            str(music_path),
        ])

        music_filter = (
            f"volume={payload.bg_music_volume}"
        )

        if duration and payload.bg_music_fade_in > 0:
            fade_in = min(
                payload.bg_music_fade_in,
                duration,
            )

            music_filter += (
                f",afade=t=in:st=0:d={fade_in}"
            )

        if duration and payload.bg_music_fade_out > 0:
            fade_out = min(
                payload.bg_music_fade_out,
                duration,
            )

            fade_start = max(0, duration - fade_out)

            music_filter += (
                f",afade=t=out:"
                f"st={fade_start}:"
                f"d={fade_out}"
            )

        audio_inputs.append({
            "index": input_index,
            "label": "music",
            "filter": music_filter,
        })

        input_index += 1

    # -----------------------------------------------------
    # VIDEO EFFECTS: IMPACT ZOOM + SHAKE + WHITE FLASH
    # -----------------------------------------------------

    video_filters = []
    current_video = "0:v"

    visual_tracks = [
        track
        for track in custom_sfx_tracks
        if track.get("visual_impact", False)
        and (
            duration is None
            or track["start_time"] < duration
        )
    ]

    intensity = float(payload.impact_intensity or 0)

    effects_enabled = (
        payload.sound_effects
        and payload.visual_impact_enabled
        and duration
        and intensity > 0
        and visual_tracks
    )

    if effects_enabled:
        pulse_terms = []
        shake_x_terms = []
        shake_y_terms = []

        for track in visual_tracks:
            start = float(track["start_time"])

            center = start + 0.11
            half_duration = 0.11

            pulse = (
                f"max(0,1-abs(t-{center:.4f})/"
                f"{half_duration:.4f})"
            )

            pulse_terms.append(pulse)

            shake_x_terms.append(
                f"sin((t-{start:.4f})*110)*({pulse})"
            )

            shake_y_terms.append(
                f"cos((t-{start:.4f})*90)*({pulse})"
            )

        pulse_expression = "+".join(pulse_terms)
        shake_x_expression = "+".join(shake_x_terms)
        shake_y_expression = "+".join(shake_y_terms)

        zoom_expression = (
            f"1+0.055*{intensity:.3f}*"
            f"min(1,{pulse_expression})"
        )

        video_filters.append(
            f"[0:v]"
            f"scale="
            f"w='trunc(iw*({zoom_expression})/2)*2':"
            f"h='trunc(ih*({zoom_expression})/2)*2':"
            f"eval=frame,"
            f"crop=1080:1920:"
            f"x='(iw-1080)/2+"
            f"7*{intensity:.3f}*({shake_x_expression})':"
            f"y='(ih-1920)/2+"
            f"5*{intensity:.3f}*({shake_y_expression})'"
            f"[impact_zoom]"
        )

        current_video = "impact_zoom"


        # Single Flash Overlay - Fast
        flash_path = PROJECT_DIR / "assets" / "flash_white.png"

        if not flash_path.is_file():
            raise HTTPException(
                status_code=404,
                detail="Flash overlay image not found.",
            )

        flash_input_index = input_index

        command.extend([
            "-loop", "1",
            "-framerate", "30",
            "-i", str(flash_path),
        ])

        flash_intervals = []

        for track in visual_tracks:
            start = max(0.0, float(track["start_time"]) - 0.015)
            end = start + 0.180

            flash_intervals.append(
                f"between(t,{start:.4f},{end:.4f})"
            )

        flash_enable = "+".join(flash_intervals)

        video_filters.append(
            f"[{flash_input_index}:v]"
            f"format=rgba,"
            f"geq="
            f"r='r(X,Y)':"  
            f"g='g(X,Y)':"
            f"b='b(X,Y)':"
            f"a='255*0.85*min(1,T/1.05)*"
            f"min(1,(5.4-T)/3)'"
            f"[flash_overlay]"
        )
        video_filters.append(
            f"[{current_video}][flash_overlay]"
            f"overlay=0:0:"
            f"eof_action=pass:"
            f"shortest=0:"
            f"repeatlast=0:"
            f"enable='{flash_enable}'"
            f"[flash_result]"
        )

        current_video = "flash_result"
   
    # Always create the final video output
    video_filters.append(
        f"[{current_video}]fps=30,format=yuv420p[vout]"
    )

    # -----------------------------------------------------
    # Audio filter graph
    # -----------------------------------------------------

    audio_filters = []
    mix_labels = []

    for audio in audio_inputs:
        label = audio["label"]

        audio_filters.append(
            f"[{audio['index']}:a:0]"
            f"{audio['filter']}"
            f"[{label}]"
        )

        mix_labels.append(f"[{label}]")

    if len(mix_labels) == 1:
        audio_filters.append(
            f"{mix_labels[0]}anull[aout]"
        )
    else:
        audio_filters.append(
            "".join(mix_labels)
            + f"amix=inputs={len(mix_labels)}:"
              "duration=first:"
              "dropout_transition=0:"
              "normalize=0[aout]"
        )

    # -----------------------------------------------------
    # Final FFmpeg command
    # -----------------------------------------------------

    filter_complex = ";".join(
        video_filters + audio_filters
    )

    command.extend([
        "-filter_complex",
        filter_complex,
        "-map",
        "[vout]",
        "-map",
        "[aout]",
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
    ])

    if duration:
        command.extend([
            "-t",
            str(duration),
        ])

    command.extend([
        "-movflags",
        "+faststart",
        str(output_path),
    ])

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=900,
    )

    if result.returncode != 0 or not output_path.exists():
        raise RuntimeError(
            "FFmpeg rendering failed: "
            + result.stderr[-3500:]
        )

    return output_path

YOUTUBE_CLIPS_DIR = BASE_DIR / "data" / "youtube_downloads"

def resolve_youtube_clip(clip_id: str) -> Path:
    parts = clip_id.split("/", 1)

    if len(parts) != 2:
        raise HTTPException(400, "Invalid YouTube clip ID.")

    video_id, filename = parts

    if not re.fullmatch(r"[A-Za-z0-9_-]{6,20}", video_id):
        raise HTTPException(400, "Invalid YouTube video ID.")

    if not re.fullmatch(r"[A-Za-z0-9_-]+\.mp4", filename):
        raise HTTPException(400, "Invalid YouTube clip filename.")

    base = (YOUTUBE_CLIPS_DIR / video_id / "clips").resolve()
    path = (base / filename).resolve()

    if (
        path.parent != base
        or not path.is_file()
        or path.stat().st_size < 1024
    ):
        print("YOUTUBE CLIP NOT FOUND:", path)
        raise HTTPException(
            status_code=404,
            detail=f"YouTube clip file not found: {path}",
        )

    print("YOUTUBE CLIP FOUND:", path)
    return path

# =========================================================
# RENDER ENDPOINT
# =========================================================


@router.post("/render")
def render_clip(
    payload: RenderRequest,
    db: Session = Depends(get_db),
):
    check_tools()

    if bool(payload.clip_id) == bool(payload.youtube_clip_id):
        raise HTTPException(
            status_code=400,
            detail="Select exactly one clip source.",
        )

    print("\n========== RENDER REQUEST DEBUG ==========")
    print("clip_id:", payload.clip_id)
    print("youtube_clip_id:", repr(payload.youtube_clip_id))
    print("subtitles_enabled:", payload.subtitles_enabled)
    print("==========================================\n")

    clip = None
    youtube_source = False
    source_label = ""

    if payload.youtube_clip_id:
        print("YOUTUBE CLIP ID:", repr(payload.youtube_clip_id))
        print("YOUTUBE CLIPS DIR:", YOUTUBE_CLIPS_DIR.resolve())
        print("RESOLVED CLIP PATH:", (
            YOUTUBE_CLIPS_DIR / payload.youtube_clip_id.split("/", 1)[0]
            / "clips" / payload.youtube_clip_id.split("/", 1)[-1]
        ).resolve())
        source_path = resolve_youtube_clip(payload.youtube_clip_id)
        youtube_source = True
        source_label = Path(payload.youtube_clip_id).name

    else:
        clip = (
            db.query(Clip)
            .filter(Clip.id == payload.clip_id)
            .first()
        )

        if not clip:
            raise HTTPException(404, "Clip not found.")

        if clip.platform != "twitch":
            raise HTTPException(400, "Unsupported clip platform.")

        if not clip.url:
            raise HTTPException(400, "Clip URL is missing.")

        source_label = str(clip.id)

    job_id = uuid.uuid4().hex[:12]

    job_dir = EDIT_DIR / job_id
    job_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        # 1. Save uploaded sound effects
        custom_sfx_tracks = save_uploaded_sound_effects(
            payload,
            job_dir,
        )

        # 2. Save GTA gameplay if GTA Split is selected
        gameplay_path = save_gta_gameplay(
            payload,
            job_dir,
        )

        # 3. Download original clip
        if not youtube_source:
            source_path = download_clip(
                clip.url,
                job_dir,
            )

        silent_path = job_dir / "vertical_silent.mp4"

        output_path = (
            job_dir
            / f"trendhunter_{source_label}_{job_id}.mp4"
        )

        # 4. Crop and convert to vertical format
        processing = create_vertical_video(
            source_path,
            silent_path,
            payload,
            gameplay_path=gameplay_path,
        )

        # 5. Transcription
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

        print("\n========== TRANSCRIPTION DEBUG ==========")
        print("TYPE:", type(transcription))
        print("KEYS:", transcription.keys() if isinstance(transcription, dict) else "NOT DICT")
        print("WORD COUNT:", len(transcription.get("words", [])))

        for word in transcription.get("words", [])[:10]:
            print("WORD:", word)

        print("=========================================\n")

        # 6. Generate and burn subtitles
        if (
            payload.subtitles_enabled
            and transcription.get("words")
        ):
            subtitle_path = job_dir / "subtitles.ass"

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
                glow_intensity=payload.caption_glow_intensity,
            )

            burn_subtitles(
                silent_path,
                subtitle_path,
                subtitled_path,
            )

            render_video_path = subtitled_path

        # 7. Generate caption sound effects
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

        # 8. Final FFmpeg render
        video_duration = (
            processing["frames_processed"]
            / processing["fps"]
        )

        mux_final_video(
            render_video_path,
            source_path,
            output_path,
            payload,
            sfx_path=sfx_path,
            duration=video_duration,
            custom_sfx_tracks=custom_sfx_tracks,
        )

        applied_mode = payload.crop_mode

        if (
            payload.crop_mode == "auto"
            and processing["tracking_samples"] == 0
        ):
            applied_mode = "center_fallback"

        # 9. Response
        return {
            "status": "completed",
            "clip_id": clip.id if clip else None,
            "youtube_clip_id": payload.youtube_clip_id,
            "source": "youtube" if youtube_source else "twitch",
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
                if payload.crop_mode in (
                    "stream_split",
                    "gta_split",
                )
                else None
            ),

            "face_scale": (
                payload.face_scale
                if payload.crop_mode in (
                    "stream_split",
                    "gta_split",
                )
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

            "audio": {
                "background_music": {
                    "enabled": payload.bg_music_enabled,
                    "track": payload.bg_music_track,
                    "volume": payload.bg_music_volume,
                },

                "sound_effects": {
                    "enabled": payload.sound_effects,
                    "count": len(custom_sfx_tracks),

                    "tracks": [
                        {
                            "name": track["name"],
                            "start_time": track["start_time"],
                            "volume": track["volume"],
                            "visual_impact": track["visual_impact"],
                        }
                        for track in custom_sfx_tracks
                    ],
                },

                "visual_impact": {
                    "enabled": (
                        payload.sound_effects
                        and payload.visual_impact_enabled
                    ),
                    "intensity": payload.impact_intensity,
                },
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
        print("\n" + "=" * 80)
        print("TREND HUNTER RENDER ERROR")
        print("=" * 80)

        traceback.print_exc()

        print("=" * 80 + "\n")

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
