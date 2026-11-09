from functools import lru_cache
from pathlib import Path

import stable_whisper


@lru_cache(maxsize=2)
def get_whisper_model(model_size="small.en"):
    return stable_whisper.load_faster_whisper(
        model_size,
        device="cpu",
        compute_type="int8",
        cpu_threads=4,
    )


def transcribe_video(video_path, model_size="small.en"):
    video_path = Path(video_path)

    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    model = get_whisper_model(model_size)

    result = model.transcribe(
        str(video_path),
        language="en",
        word_timestamps=True,
        vad=False,
        regroup=False,
        suppress_silence=True,
    )

    data = result.to_dict()
    words = []
    full_text = []

    for segment in data.get("segments", []):
        segment_text = str(segment.get("text", "")).strip()

        if segment_text:
            full_text.append(segment_text)

        for word in segment.get("words") or []:
            text = str(word.get("word", "")).strip()

            if not text:
                continue

            start = float(word.get("start", 0))
            end = float(word.get("end", 0))

            if end <= start:
                continue

            words.append({
                "text": text,
                "start": round(start, 3),
                "end": round(end, 3),
            })

    return {
        "language": data.get("language", "en"),
        "text": " ".join(full_text).strip(),
        "words": words,
        "word_count": len(words),
    }
