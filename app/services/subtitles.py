
import math
import random
import re
import struct
import wave
from pathlib import Path


# ---------------------------------------------------------
# CAPTION PRESETS
# ---------------------------------------------------------

CAPTION_SIZE_PRESETS = {
    "small": 62,
    "medium": 74,
    "large": 88,
    "extra_large": 104,
}

CAPTION_COLOR_PRESETS = {
    "mrbeast": "&H0000D7FF&",
    "white": "&H00FFFFFF&",
    "green": "&H0000FF66&",
    "cyan": "&H00FFFF00&",
    "pink": "&H00FF66CC&",
}

WHITE = "&H00FFFFFF&"
YELLOW = "&H0000FFFF&"
GREEN = "&H0000FF00&"
RED = "&H000000FF&"


# ---------------------------------------------------------
# KEYWORD EMOJIS AND HIGHLIGHTS
# ---------------------------------------------------------

KEYWORD_RULES = {
    "NO WAY": ("\U0001F631", YELLOW),
    "BRO": ("\U0001F480", YELLOW),
    "BRUH": ("\U0001F480", YELLOW),
    "LET'S GO": ("\U0001F525", GREEN),
    "LETS GO": ("\U0001F525", GREEN),
    "OMG": ("\U0001F631", YELLOW),
    "LOL": ("\U0001F602", YELLOW),
    "LMAO": ("\U0001F602", YELLOW),
    "WIN": ("\U0001F3C6", GREEN),
    "WON": ("\U0001F3C6", GREEN),
    "FAIL": ("\U0001F62D", RED),
    "LOST": ("\U0001F62D", RED),
    "INSANE": ("\U0001F92F", YELLOW),
    "CRAZY": ("\U0001F92F", YELLOW),
    "WAIT": ("\U0001F6D1", RED),
    "STOP": ("\U0001F6D1", RED),
    "HELP": ("\U0001F480", RED),
    "UNBELIEVABLE": ("\U0001F92F", YELLOW),
    "CLUTCH": ("\U0001F525", GREEN),
    "RIP": ("\U0001F480", RED),
    "SHEESH": ("\U0001F525", YELLOW),
    "EZ": ("\U0001F60E", GREEN),
}


# ---------------------------------------------------------
# OUTLINE PRESETS
# The selected caption color is always preserved.
# These presets control the outline color only.
# ---------------------------------------------------------

OUTLINE_PRESETS = {
    "white_black": {
        "outline_color": "&H00000000&",
        "outline": 5,
    },
    "black_white": {
        "outline_color": "&H00FFFFFF&",
        "outline": 5,
    },
    "color_black": {
        "outline_color": "&H00000000&",
        "outline": 5,
    },
}


# ---------------------------------------------------------
# SHADOW PRESETS
# ---------------------------------------------------------

SHADOW_PRESETS = {
    "none": {
        "shadow": 0,
        "glow": False,
    },
    "soft": {
        "shadow": 1,
        "glow": False,
    },
    "strong": {
        "shadow": 3,
        "glow": False,
    },
    "glow": {
        "shadow": 0,
        "glow": True,
    },
}


# ---------------------------------------------------------
# BASIC HELPERS
# ---------------------------------------------------------

def ass_time(seconds):
    seconds = max(0.0, float(seconds))

    total_cs = int(round(seconds * 100))
    hours = total_cs // 360000
    minutes = (total_cs // 6000) % 60
    centiseconds = total_cs % 100
    whole_seconds = (total_cs // 100) % 60

    return (
        f"{hours}:{minutes:02d}:"
        f"{whole_seconds:02d}.{centiseconds:02d}"
    )


def clean_word(value):
    return re.sub(r"[^\w']+", "", str(value)).upper()


# ---------------------------------------------------------
# PROFANITY FILTER
# ---------------------------------------------------------

PROFANITY_WORDS = {
    "fuck",
    "fucking",
    "fucked",
    "fucker",
    "fuckers",
    "fucks",
    "motherfucker",
    "motherfuckers",
    "shit",
    "shitty",
    "bullshit",
    "bitch",
    "bitches",
    "bitchy",
    "asshole",
    "assholes",
    "dick",
    "dicks",
    "dickhead",
    "dickheads",
    "pussy",
    "bastard",
    "bastards",
    "cunt",
    "cunts",
    "whore",
    "whores",
    "slut",
    "sluts",
    "nigger",
    "nigga",
}

PROFANITY_PATTERN = re.compile(
    r"[A-Za-z0-9']+"
)

def censor_profanity(text):
    text = str(text)

    def replace_match(match):
        word = match.group(0)
        normalized = word.lower().replace("'", "")

        if normalized in PROFANITY_WORDS:
            return "*" * len(word)

        return word

    return PROFANITY_PATTERN.sub(replace_match, text)



def escape_ass_text(value):
    return (
        str(value)
        .replace("\\", r"\\")
        .replace("{", r"\{")
        .replace("}", r"\}")
        .replace("\n", " ")
    )


def get_keyword_style(words, index):
    current = clean_word(words[index]["text"])

    if index + 1 < len(words):
        next_word = clean_word(words[index + 1]["text"])
        phrase = f"{current} {next_word}"

        if phrase in KEYWORD_RULES:
            return KEYWORD_RULES[phrase]

    return KEYWORD_RULES.get(current, ("", YELLOW))


# ---------------------------------------------------------
# CAPTION GROUPING
# ---------------------------------------------------------

def build_caption_groups(words, max_words=4, max_chars=25):
    groups = []
    current = []

    for word in words:
        text = str(word.get("text", "")).strip()

        if not text:
            continue

        if max_words == 1:
            groups.append([word])
            continue

        candidate = current + [word]

        candidate_text = " ".join(
            str(item["text"]).strip()
            for item in candidate
        )

        if current and (
            len(candidate) > max_words
            or len(candidate_text) > max_chars
        ):
            groups.append(current)
            current = [word]
        else:
            current = candidate

    if current:
        groups.append(current)

    return groups


# ---------------------------------------------------------
# FONT SIZE
# ---------------------------------------------------------

def resolve_font_size(value):
    if isinstance(value, str):
        return CAPTION_SIZE_PRESETS.get(value, 104)

    try:
        return max(40, min(int(value), 140))
    except (TypeError, ValueError):
        return 104


# ---------------------------------------------------------
# CAPTION POSITION
# ---------------------------------------------------------

def resolve_position(position, video_height):
    positions = {
        "lower": int(video_height * 0.79),
        "center": int(video_height * 0.50),
        "upper": int(video_height * 0.30),
    }

    return positions.get(position, positions["lower"])


# ---------------------------------------------------------
# ANIMATION
# ---------------------------------------------------------


def get_animation_tags(animation, start, end, intensity, font_size):
    intensity = max(0.5, min(float(intensity), 1.5))

    if animation == "none":
        return ""

    if animation == "pop":
        scale = int(70 + (intensity * 10))
        return (
            f"{{\\fscx{scale}\\fscy{scale}"
            f"\\t(0,130,\\fscx100\\fscy100)}}"
        )

    if animation == "pop_bounce":
        peak = int(108 + intensity * 8)
        return (
            "{\\fscx70\\fscy70"
            f"\\t(0,90,\\fscx{peak}\\fscy{peak})"
            "\\t(90,180,\\fscx100\\fscy100)}"
        )

    if animation == "shake":
        angle = 3.5 * intensity
        return (
            f"{{\\frz{-angle:.1f}"
            f"\\t(0,45,\\frz{angle:.1f})"
            f"\\t(45,90,\\frz{-angle:.1f})"
            "\\t(90,140,\\frz0)}"
        )

    if animation == "elastic":
        peak = int(118 + intensity * 10)
        return (
            "{\\fscx35\\fscy140"
            f"\\t(0,100,\\fscx{peak}\\fscy{peak})"
            "\\t(100,180,\\fscx94\\fscy106)"
            "\\t(180,260,\\fscx103\\fscy97)"
            "\\t(260,330,\\fscx100\\fscy100)}"
        )

    if animation == "slide_up":
        scale = int(92 + intensity * 4)
        return (
            f"{{\\fscx{scale}\\fscy{scale}"
            "\\blur3\\t(0,160,\\fscx100\\fscy100\\blur0)}"
        )

    if animation == "zoom_in":
        scale = int(35 + intensity * 15)
        return (
            f"{{\\fscx{scale}\\fscy{scale}\\blur2"
            "\\t(0,180,\\fscx100\\fscy100\\blur0)}"
        )

    if animation == "tilt":
        angle = 8 * intensity
        return (
            f"{{\\frz{angle:.1f}\\fscx90\\fscy90"
            "\\t(0,180,\\frz0\\fscx100\\fscy100)}"
        )

    if animation == "fade_pop":
        scale = int(65 + intensity * 10)
        return (
            f"{{\\alpha&HFF&\\fscx{scale}\\fscy{scale}"
            "\\t(0,160,\\alpha&H00&\\fscx100\\fscy100)}"
        )

    if animation == "pulse":
        peak = int(105 + intensity * 7)
        return (
            "{\\fscx95\\fscy95"
            f"\\t(0,100,\\fscx{peak}\\fscy{peak})"
            "\\t(100,220,\\fscx100\\fscy100)}"
        )

    return ""

# ---------------------------------------------------------
# RESOLVE OUTLINE AND SHADOW
# ---------------------------------------------------------

def resolve_outline(outline_preset, color_preset):
    settings = OUTLINE_PRESETS.get(
        outline_preset,
        OUTLINE_PRESETS["white_black"],
    ).copy()

    # Always use the selected caption color.
    settings["primary"] = CAPTION_COLOR_PRESETS.get(
        color_preset,
        CAPTION_COLOR_PRESETS["mrbeast"],
    )

    return settings


def resolve_shadow(shadow_preset):
    return SHADOW_PRESETS.get(
        shadow_preset,
        SHADOW_PRESETS["strong"],
    ).copy()


def make_transparent_color(color, alpha="60"):
    """
    ASS color format: &HAABBGGRR&
    Higher alpha means more transparent.
    """
    if not color.startswith("&H"):
        return color

    return f"&H{alpha}{color[2:]}"


# ---------------------------------------------------------
# GENERATE ASS SUBTITLES
# ---------------------------------------------------------

def generate_ass_subtitles(
    transcription,
    output_path,
    video_width=1080,
    video_height=1920,
    font_size=104,
    color_preset="mrbeast",
    display_mode="word",
    animation="pop_bounce",
    intensity=1.0,
    position="lower",
    bold=True,
    outline_preset="white_black",
    shadow_preset="strong",
    glow_intensity=0.8,
):
    words = [
        {
            **word,
            "text": censor_profanity(word.get("text", "")),
        }
        for word in transcription.get("words", [])
    ]
    if not words:
        raise ValueError(
            "No word timestamps found in transcription."
        )

    font_size = resolve_font_size(font_size)

    if display_mode not in ("word", "phrase"):
        display_mode = "word"

    SUPPORTED_ANIMATIONS = (
        "pop_bounce",
        "pop",
        "shake",
        "elastic",
        "slide_up",
        "zoom_in",
        "tilt",
        "fade_pop",
        "pulse",
        "none",
    )

    if animation not in SUPPORTED_ANIMATIONS:
        animation = "pop_bounce"
    outline_settings = resolve_outline(
        outline_preset,
        color_preset,
    )

    shadow_settings = resolve_shadow(shadow_preset)

    primary_color = outline_settings["primary"]
    outline_color = outline_settings["outline_color"]
    outline_width = outline_settings["outline"]

    shadow_width = shadow_settings["shadow"]
    glow_enabled = shadow_settings["glow"]
    glow_intensity = max(
        0.0,
        min(float(glow_intensity), 1.5),
    )

    glow_alpha = max(
        25,
        min(95, int(95 - glow_intensity * 45)),
    )

    glow_blur = max(
        1,
        round(1 + glow_intensity * 4),
    )

    glow_outline = round(
        3 + glow_intensity * 6
    )

    bold_value = -1 if bold else 0

    max_words = 1 if display_mode == "word" else 4

    groups = build_caption_groups(
        words,
        max_words=max_words,
        max_chars=25,
    )

    y_position = resolve_position(
        position,
        video_height,
    )

    output_path = Path(output_path)
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    header = f"""[Script Info]
Title: TrendHunter Animated Captions
ScriptType: v4.00+
PlayResX: {video_width}
PlayResY: {video_height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Rubik,{font_size},{primary_color},&H000000FF&,{outline_color},&H80000000&,{bold_value},0,0,0,100,100,0,0,1,{outline_width},{shadow_width},5,60,60,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    events = []

    for group in groups:
        for active_index, active_word in enumerate(group):
            try:
                start = float(active_word["start"])
                end = float(active_word["end"])
            except (KeyError, TypeError, ValueError):
                continue

            if end <= start:
                continue

            caption_parts = []

            for index, word in enumerate(group):
                original_text = str(
                    word.get("text", "")
                ).strip()

                if not original_text:
                    continue

                text = escape_ass_text(original_text)

                emoji, keyword_color = get_keyword_style(
                    group,
                    index,
                )

                if index == active_index:
                    active_color = (
                        keyword_color if emoji else primary_color
                    )

                    animation_tag = get_animation_tags(
                        animation,
                        start,
                        end,
                        intensity,
                        font_size,
                    )

                    active_tags = (
                        f"{{\\c{active_color}"
                        f"\\3c{outline_color}"
                        f"\\fs{font_size}"
                        f"\\b{bold_value}"
                        f"\\bord{outline_width}"
                        f"\\shad{shadow_width}"
                    )

                    active_tags += "}"

                    caption_parts.append(
                        active_tags
                        + animation_tag
                        + text
                        + "{\\rDefault}"
                    )

                    if emoji:
                        caption_parts.append(
                            f"{{\\fnSegoe UI Emoji"
                            f"\\fs{int(font_size * 0.72)}"
                            f"\\bord0\\shad0}}"
                            f"{emoji}"
                            f"{{\\rDefault}}"
                        )

                else:
                    caption_parts.append(
                        f"{{\\c{primary_color}"
                        f"\\3c{outline_color}"
                        f"\\fs{font_size}"
                        f"\\b{bold_value}"
                        f"\\bord{outline_width}"
                        f"\\shad{shadow_width}"
                        f"}}"
                        f"{text}"
                        f"{{\\rDefault}}"
                    )

            if not caption_parts:
                continue

            caption = " ".join(caption_parts)

            caption = (
                f"{{\\an5"
                f"\\pos({video_width // 2},{y_position})"
                f"\\fad(70,50)}}"
                + caption
            )

 
            event_start = ass_time(start)
            event_end = ass_time(end + 0.08)

            # Glow layer: configurable colored light behind captions.
            if glow_enabled:
                glow_color = make_transparent_color(
                    primary_color,
                    alpha=f"{glow_alpha:02d}",
                )

                glow_caption = caption.replace(
                    f"\\3c{outline_color}",
                    f"\\3c{glow_color}",
                )

                glow_caption = glow_caption.replace(
                    f"\\bord{outline_width}",
                    f"\\bord{outline_width + glow_outline}",
                )

                glow_caption = glow_caption.replace(
                    "\\shad0",
                    f"\\shad0\\blur{glow_blur}",
                )

                events.append(
                    "Dialogue: 0,"
                    f"{event_start},"
                    f"{event_end},"
                    f"Default,,0,0,0,,{glow_caption}"
                )

                normal_layer = 1
            else:
                normal_layer = 0

            # Always add the normal caption layer.
            events.append(
                f"Dialogue: {normal_layer},"
                f"{event_start},"
                f"{event_end},"
                f"Default,,0,0,0,,{caption}"
            )


    if not events:
        raise ValueError(
            "Could not generate subtitle events from word timestamps."
        )

    output_path.write_text(
        header + "\n".join(events) + "\n",
        encoding="utf-8-sig",
    )

    return {
        "subtitle_path": str(output_path),
        "word_count": len(words),
        "caption_groups": len(groups),
        "events": len(events),
        "display_mode": display_mode,
        "font_size": font_size,
        "color": color_preset,
        "outline": outline_preset,
        "shadow": shadow_preset,
        "bold": bold,
        "position": position,
        "animation": animation,
    }


# ---------------------------------------------------------
# GENERATE SOUND EFFECT TRACK
# ---------------------------------------------------------

def generate_sfx_track(
    transcription,
    output_path,
    duration,
    volume=0.25,
    intensity=1.0,
    sample_rate=48000,
):
    output_path = Path(output_path)
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    duration = max(0.1, float(duration))
    total_samples = int(duration * sample_rate)

    audio = [0.0] * total_samples

    volume = max(0.0, min(float(volume), 1.0))
    intensity = max(0.5, min(float(intensity), 1.5))

    scale = volume * intensity * 0.35

    words = transcription.get("words", [])

    for index, word in enumerate(words):
        try:
            start = float(word.get("start", 0))
            end = float(word.get("end", 0))
        except (TypeError, ValueError):
            continue

        if end <= start or start >= duration:
            continue

        text = clean_word(word.get("text", ""))

        if not text:
            continue

        emoji, _ = get_keyword_style(words, index)

        if emoji:
            frequency = 950
            effect_duration = 0.09
        elif index % 3 == 0:
            frequency = 550
            effect_duration = 0.045
        else:
            continue

        start_sample = int(start * sample_rate)
        effect_samples = int(
            effect_duration * sample_rate
        )

        for sample_index in range(effect_samples):
            position = start_sample + sample_index

            if position >= total_samples:
                break

            t = sample_index / sample_rate

            progress = sample_index / max(
                1,
                effect_samples,
            )

            envelope = math.exp(-progress * 7)

            tone = math.sin(
                2 * math.pi * frequency * t
            )

            noise = random.uniform(-0.15, 0.15)

            value = (
                (tone + noise)
                * envelope
                * scale
            )

            audio[position] += value

    with wave.open(str(output_path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)

        frames = bytearray()

        for sample in audio:
            sample = max(-1.0, min(1.0, sample))

            frames.extend(
                struct.pack(
                    "<h",
                    int(sample * 32767),
                )
            )

        wav_file.writeframes(frames)

    return {
        "sfx_path": str(output_path),
        "duration": duration,
        "sample_rate": sample_rate,
        "volume": volume,
        "intensity": intensity,
    }
