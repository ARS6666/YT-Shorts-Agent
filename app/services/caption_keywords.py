import re
import unicodedata


CAPTION_KEYWORDS = {
    "NO WAY": {"emoji": "😱", "color": "yellow"},
    "WHAT": {"emoji": "😳", "color": "yellow"},
    "WHAT?!": {"emoji": "😳", "color": "yellow"},
    "BRO": {"emoji": "💀", "color": "yellow"},
    "BRUH": {"emoji": "💀", "color": "yellow"},
    "INSANE": {"emoji": "🤯", "color": "yellow"},
    "CRAZY": {"emoji": "🤯", "color": "yellow"},
    "LET'S GO": {"emoji": "🔥", "color": "green"},
    "LETS GO": {"emoji": "🔥", "color": "green"},
    "OMG": {"emoji": "😱", "color": "yellow"},
    "LMAO": {"emoji": "😂", "color": "yellow"},
    "LOL": {"emoji": "😂", "color": "yellow"},
    "WIN": {"emoji": "🏆", "color": "green"},
    "WON": {"emoji": "🏆", "color": "green"},
    "FAIL": {"emoji": "😭", "color": "red"},
    "LOST": {"emoji": "😭", "color": "red"},
    "HELP": {"emoji": "💀", "color": "red"},
    "WAIT": {"emoji": "🛑", "color": "red"},
    "STOP": {"emoji": "🛑", "color": "red"},
    "UNBELIEVABLE": {"emoji": "🤯", "color": "yellow"},
    "CLUTCH": {"emoji": "🔥", "color": "green"},
    "RIP": {"emoji": "💀", "color": "red"},
    "SHEESH": {"emoji": "🔥", "color": "yellow"},
    "EZ": {"emoji": "😎", "color": "green"},
}


def normalize_word(text):
    text = unicodedata.normalize("NFKC", text or "")
    return re.sub(r"[^A-Z0-9']", "", text.upper())


def detect_keyword_matches(words):
    tokens = [
        normalize_word(word.get("text", ""))
        for word in words
    ]

    matches = []

    for phrase, config in CAPTION_KEYWORDS.items():
        phrase_tokens = [
            normalize_word(token)
            for token in phrase.split()
        ]

        phrase_tokens = [token for token in phrase_tokens if token]

        if not phrase_tokens:
            continue

        phrase_length = len(phrase_tokens)

        for index in range(len(tokens) - phrase_length + 1):
            current = tokens[index:index + phrase_length]

            if current == phrase_tokens:
                matches.append({
                    "start_index": index,
                    "end_index": index + phrase_length - 1,
                    "phrase": phrase,
                    "emoji": config["emoji"],
                    "color": config["color"],
                })

    return matches


def get_keyword_map(words):
    result = {}

    for match in detect_keyword_matches(words):
        for index in range(
            match["start_index"],
            match["end_index"] + 1
        ):
            result[index] = match

    return result