"""
Cyrillic → Latin transliteration for Russian text.

Converts Russian Cyrillic script to phonetic Latin characters so that
the overlay displays "english-typed" Russian that is readable without
knowing the Cyrillic alphabet.

Examples:
    "я иду"       → "ya idu"
    "привет"       → "privet"
    "хорошо"       → "khorosho"
    "где ты?"      → "gde ty?"
    "на крыше"     → "na kryshe"

Uses a common phonetic romanization (similar to passport / informal
transliteration used by Russian gamers in Latin-only chats).
"""

from logger_config import get_logger

logger = get_logger("Transliterate")

# ── Mapping tables ──────────────────────────────────────────────────
# Order matters for multi-char sequences — longer mappings checked first
# via the single-char dict (Python dicts are insertion-ordered 3.7+).

_CYRILLIC_TO_LATIN_LOWER: dict[str, str] = {
    "ё": "yo",
    "ж": "zh",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "shch",
    "ъ": "",       # hard sign — omitted
    "ы": "y",
    "ь": "",       # soft sign — omitted
    "э": "e",
    "ю": "yu",
    "я": "ya",
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "kh",
    "і": "i",      # Ukrainian і (occasionally appears in mixed text)
}

_CYRILLIC_TO_LATIN_UPPER: dict[str, str] = {
    k.upper(): v.capitalize() for k, v in _CYRILLIC_TO_LATIN_LOWER.items() if v
}
# Hard/soft signs uppercase too — map to empty
_CYRILLIC_TO_LATIN_UPPER["Ъ"] = ""
_CYRILLIC_TO_LATIN_UPPER["Ь"] = ""


def transliterate_russian(text: str) -> str:
    """
    Convert Cyrillic characters in *text* to their Latin phonetic equivalents.
    Non-Cyrillic characters (digits, punctuation, Latin letters) are kept as-is.

    Args:
        text: Input text potentially containing Cyrillic characters.

    Returns:
        Transliterated text using Latin characters.
    """
    if not text:
        return text

    result: list[str] = []
    for ch in text:
        if ch in _CYRILLIC_TO_LATIN_LOWER:
            result.append(_CYRILLIC_TO_LATIN_LOWER[ch])
        elif ch in _CYRILLIC_TO_LATIN_UPPER:
            result.append(_CYRILLIC_TO_LATIN_UPPER[ch])
        else:
            # Keep as-is (Latin letters, digits, punctuation, spaces)
            result.append(ch)

    transliterated = "".join(result)
    logger.debug("Transliterate: '%s' -> '%s'", text, transliterated)
    return transliterated


def has_cyrillic(text: str) -> bool:
    """Return True if text contains any Cyrillic characters."""
    if not text:
        return False
    for ch in text:
        if "\u0400" <= ch <= "\u04ff":
            return True
    return False
