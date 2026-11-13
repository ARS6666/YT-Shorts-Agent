
from functools import lru_cache
from pathlib import Path

import stable_whisper


@lru_cache(maxsize=2)
def get_whisper_model(model_size="small.en", engine="faster"):
    if engine == "native":
        return stable_whisper.load_model(
            model_size,
            device="cpu",
        )

    return stable_whisper.load_faster_whisper(
        model_size,
        device="cpu",
        compute_type="int8",
        cpu_threads=4,
    )


def empty_transcription():
    return {
        "language": "en",
        "text": "",
        "words": [],
        "word_count": 0,
    }


def transcribe_video(video_path, model_size="small.en"):
    video_path = Path(video_path)

    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    options = {
        "language": "en",
        "word_timestamps": True,
        "vad": False,
        "regroup": False,
        "suppress_silence": True,
    }

    result = None

    # First attempt: Faster Whisper
    try:
        print("[TRANSCRIPTION] Trying Faster Whisper...")
        model = get_whisper_model(model_size, "faster")
        result = model.transcribe(str(video_path), **options)

    except IndexError as error:
        if "boolean index did not match indexed array" not in str(error):
            raise

        print("[TRANSCRIPTION] Alignment error. Trying native Whisper...")

        # Second attempt: Native Stable Whisper
        try:
            model = get_whisper_model(model_size, "native")
            result = model.transcribe(str(video_path), **options)

        except IndexError as native_error:
            if "boolean index did not match indexed array" not in str(native_error):
                raise

            print("[TRANSCRIPTION] No reliable word alignment. Continuing without subtitles.")
            return empty_transcription()

    if result is None:
        return empty_transcription()

    data = result.to_dict()

    words = []
    full_text = []

    for segment in data.get("segments", []):
        segment_text = str(segment.get("text", "")).strip()

        if segment_text:
            full_text.append(segment_text)

        for word in segment.get("words") or []:
            word_text = str(word.get("word", "")).strip()

            if not word_text:
                continue

            start = float(word.get("start", 0))
            end = float(word.get("end", 0))

            if end <= start:
                continue

            words.append({
                "text": word_text,
                "start": round(start, 3),
                "end": round(end, 3),
            })

    return {
        "language": data.get("language", "en"),
        "text": " ".join(full_text).strip(),
        "words": words,
        "word_count": len(words),
    }
