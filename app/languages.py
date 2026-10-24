"""Names for the language codes TMDB gives, so a card can say Korean rather than ko."""
from . import secretstore

NAMES = {
    "af": "Afrikaans", "ar": "Arabic", "bg": "Bulgarian", "bn": "Bengali",
    "ca": "Catalan", "cn": "Cantonese", "cs": "Czech", "da": "Danish",
    "de": "German", "el": "Greek", "es": "Spanish", "et": "Estonian",
    "fa": "Persian", "fi": "Finnish", "fr": "French", "ga": "Irish",
    "gu": "Gujarati", "he": "Hebrew", "hi": "Hindi", "hr": "Croatian",
    "hu": "Hungarian", "id": "Indonesian", "is": "Icelandic", "it": "Italian",
    "ja": "Japanese", "kn": "Kannada", "ko": "Korean", "lt": "Lithuanian",
    "lv": "Latvian", "ml": "Malayalam", "mr": "Marathi", "ms": "Malay",
    "nb": "Norwegian", "nl": "Dutch", "no": "Norwegian", "pa": "Punjabi",
    "pl": "Polish", "pt": "Portuguese", "ro": "Romanian", "ru": "Russian",
    "sk": "Slovak", "sl": "Slovenian", "sr": "Serbian", "sv": "Swedish",
    "ta": "Tamil", "te": "Telugu", "th": "Thai", "tl": "Filipino",
    "tr": "Turkish", "uk": "Ukrainian", "ur": "Urdu", "vi": "Vietnamese",
    "zh": "Mandarin",
}

UNLABELLED = {"en", "xx", ""}

def show_all():
    return secretstore.get("watch_all_languages", "1") != "0"

def watched():
    chosen = [c for c in (secretstore.get("watch_languages") or "").split(",") if c in NAMES and c != "en"]
    return ["en"] + chosen

def choices():
    have = watched()
    return sorted(((c, n) for c, n in NAMES.items() if c not in have and c != "nb"), key=lambda x: x[1])

def label(code):
    code = (code or "").strip().lower()
    if code in UNLABELLED:
        return ""
    return NAMES.get(code, code.upper())
