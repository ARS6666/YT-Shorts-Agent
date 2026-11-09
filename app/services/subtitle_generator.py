from pathlib import Path

from app.services.caption_keywords import get_keyword_map


COLORS = {
    "white": "&H00FFFFFF&",
    "yellow": "&H0000D4FF&",
    "green": "&H0000FF70&",
    "red": "&H000040FF&",
}


def ass_time(seconds):
    total = max(0, round(seconds * 100))
    hours = total // 360000
    minutes = (total % 360000) // 6000
    secs = (total % 6000) // 100

    return f"{hours}:{minutes:02d}:{secs:02d}.{total % 100:02d}"


def escape_ass(text):
    return (
        str(text)
        .replace("\\", r"\\")
        .replace("{", r"\{")
        .replace("}", r"\}")
        .replace("\n", " ")
    )


def group_words(words, max_words=5, max_gap=0.65):
    groups = []
    current = []

    for word in words:
        if current:
            gap = word["start"] - current[-1]["end"]

            if gap > max_gap or len(current) >= max_words:
                groups.append(current)
                current = []

        current.append(word)

    if current:
        groups.append(current)

    return groups


def build_group_text(
    group,
    global_start,
    keyword_map,
    emoji_mode=True,
    word_highlight=True,
):
    output = []

    for local_index, word in enumerate(group):
        global_index = global_start + local_index
        keyword = keyword_map.get(global_index)

        color = (
            COLORS.get(keyword["color"], COLORS["yellow"])
            if keyword
            else COLORS["white"]
        )

        text = escape_ass(word["text"])

        next_time = (
            group[local_index + 1]["start"]
            if local_index + 1 < len(group)
            else word["end"]
        )

        duration = max(
            1,
            round((next_time - word["start"]) * 100),
        )

        highlight = r"\kf" if word_highlight else r"\k"

        output.append(
            f"{{{highlight}{duration}\\c{color}}}{text}"
        )

        if (
            emoji_mode
            and keyword
            and global_index == keyword["end_index"]
        ):
            output.append(
                f" {{\\rDefault\\fnSegoe UI Emoji}}"
                f"{keyword['emoji']}"
                f"{{\\rDefault}}"
            )

    return " ".join(output)


def generate_ass_subtitles(
    words,
    output_path,
    emoji_mode=True,
    word_highlight=True,
    font_size=76,
):
    if not words:
        raise ValueError("No transcription words available.")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    keyword_map = get_keyword_map(words)
    groups = group_words(words)

    header = f"""[Script Info]
Title: TrendHunter MrBeast Emoji Captions
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Impact,{font_size},&H00FFFFFF,&H0000D4FF,&H00000000,&H99000000,-1,0,0,0,100,100,0,0,1,6,2,2,70,70,420,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    events = []
    global_start = 0

    for group in groups:
        start = group[0]["start"]
        end = max(group[-1]["end"], start + 0.08)

        text = build_group_text(
            group,
            global_start,
            keyword_map,
            emoji_mode,
            word_highlight,
        )

        text = (
            r"{\fscx85\fscy85"
            r"\t(0,100,\fscx110\fscy110)"
            r"\t(100,180,\fscx100\fscy100)}"
            + text
        )

        events.append(
            f"Dialogue: 0,{ass_time(start)},{ass_time(end)},"
            f"Default,,0,0,0,,{text}"
        )

        global_start += len(group)

    output_path.write_text(
        header + "\n".join(events) + "\n",
        encoding="utf-8-sig",
    )

    return {
        "path": str(output_path),
        "groups": len(groups),
        "words": len(words),
        "keyword_matches": len(keyword_map),
    }