import re

# Dictionary of terms to enforce in the OUTPUT (English)
# Key: The word NLLB/Marian likely produces (bad) or raw casual words
# Value: The word you want (good)
GAMER_GLOSSARY_EN = {
    # Medical / Health
    r"\bpharmacy\b": "medkit",            
    r"\bhealth\s?issues\b": "HP",
    r"\bmedicine\s?cabinet\b": "medkit",
    r"\bfirst\s?aid\s?kit\b": "medkit",
    r"\btreating\b": "healing",
    r"\btreatment\b": "healing",
    r"\bhealing\s?myself\b": "healing",

    # Ammo / Weapons
    r"\bcartridges\b": "ammo",
    r"\bbullets\b": "ammo",
    r"\bspare\s?parts\b": "ammo",  # sometimes "запасные" (spare) translates to spare parts
    r"\brounds\b": "ammo",
    r"\bmachine\b": "AR", # "автомат" -> machine -> AR (Assault Rifle)
    r"\bautomaton\b": "AR",
    r"\bgolden\s?machine\b": "Gold AR",

    # Movement / Actions
    r"\bwander\b": "loot",  # "лутать" sometimes garbles
    r"\bcleaned\s?up\b": "cleared", # "зачистили"
    r"\bjumping\b": "dropping", # "прыгаем" context
    r"\brun\s?away\b": "running",
    
    # Locations
    r"\bupstairs\b": "on high ground",
    
    # Misc
    r"\badversaries\b": "enemies",
    r"\bopponents\b": "enemies",
    r"\bmen\b": "players", # "5 men left" -> "5 players left"
    r"\bpeople\b": "players",
}

def apply_gaming_glossary(text: str) -> str:
    """Applies regex replacements to enforce gaming terminology."""
    if not text:
        return text
    
    # Case-insensitive replacement
    for pattern, replacement in GAMER_GLOSSARY_EN.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    
    return text
