import re
import os
from datetime import datetime
from logger_config import get_logger

logger = get_logger("Glossary")

# ==============================================================================
# GAMING GLOSSARY - Post-Translation Context Fixes
# ==============================================================================
# This module applies regex-based replacements to enforce gaming terminology.
# 
# HOW TO FIND NEW GLOSSARY ENTRIES:
# 1. Run the translator normally
# 2. Check the translation_logs/ folder for daily log files
# 3. Look for entries where "Raw" and "Fixed" differ - these show active fixes
# 4. Review the console output for awkward translations that AREN'T being fixed
# 5. Add new patterns below following the existing format
# 
# EXAMPLE LOG ENTRY:
#   [14:23:45] ru->en
#     Source: банки на крыше
#     Raw:    banks on the roof
#     Fixed:  bunkers on the roof
# 
# This shows "banks" was successfully mapped to "bunkers"
# ==============================================================================

# Dictionary of terms to enforce in the OUTPUT (English)
# Key: The word NLLB/Marian likely produces (bad) or raw casual words
# Value: The word you want (good)
GAMER_GLOSSARY_EN = {
    # ==================================================================
    # MULTI-WORD patterns first (order matters — longest match wins)
    # ==================================================================

    # Fortnite POI names (translate back to proper names)
    r"\bnice\s+park\b": "Pleasant Park",       # "Приятный Парк" -> nice park -> Pleasant Park
    r"\bpleasant\s+park\b": "Pleasant Park",    # sometimes NLLB gets "pleasant" right
    r"\bsalty\s+springs?\b": "Salty Springs",    # another POI
    r"\btilted\s+towers?\b": "Tilted Towers",

    # Weapon multi-word (before single-word "machine")
    r"\bgolden\s+vending\s+machine\b": "Gold AR",   # "золотой автомат" -> golden vending machine
    r"\bvending\s+machine\b": "AR",                  # "автомат" -> vending machine -> AR
    r"\bgolden\s+machine\b": "Gold AR",              # fallback: "золотой автомат"
    r"\bgolden\s+AR\b": "Gold AR",                   # catch "golden AR" after other fixes

    # Storm / Zone (Fortnite uses "storm", not "zone")
    r"\bzone\s+narrows\b": "storm is closing",          # "зона сужается"
    r"\bzone\s+is\s+narrowing\b": "storm is closing",
    r"\bzone\s+is\s+shrinking\b": "storm is closing",
    r"\bzone\s+shrinks\b": "storm is closing",
    r"\bthe\s+zone\b": "the storm",                     # general fallback

    # Knocked / Downed (Fortnite "down" mechanic)
    r"\bhe\s+falls\b": "he's down",             # "он упал" -> he falls -> he's down
    r"\bshe\s+falls\b": "she's down",
    r"\bhe\s+fell\b": "he's down",
    r"\bI\s+hit\s+the\b": "I downed the",       # "я сбил" -> I hit the -> I downed the

    # ==================================================================
    # SINGLE-WORD patterns
    # ==================================================================

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
    r"\bspare\s?parts\b": "ammo",    # "запасные" (spare) sometimes -> spare parts
    r"\bcartridge\b": "ammo",
    r"\bmachine\b": "AR",            # "автомат" -> machine -> AR (Assault Rifle)
    r"\bautomaton\b": "AR",

    # Rarity names (Fortnite uses "Gold" not "golden")
    r"\bgolden\b": "Gold",           # "золотой" -> golden -> Gold

    # Movement / Actions
    r"\bwander\b": "loot",           # "лутать" sometimes garbles
    r"\bcleaned\s?up\b": "cleared",  # "зачистили"
    r"\bjumping\b": "dropping",      # "прыгаем" -> jumping -> dropping
    r"\brun\s?away\b": "running",
    r"\bsmoke\b": "push",            # "пушить" -> smoke -> push
    r"\bwill\s+smoke\b": "will push",
    r"\bachieve\b": "finish",        # "добить" -> achieve -> finish
    r"\bnailed\b": "knocked",        # "нокнула" -> nailed -> knocked
    r"\bcut,\s*cut\b": "rez, rez",   # "рез, рез" -> cut, cut -> rez, rez
    r"\bcut\s+to\s+a\s+sheet\b": "rez on leaf",
    r"\bthis\s+cut\b": "this rez",

    # Locations / Terrain
    r"\bupstairs\b": "on high ground",
    r"\bbanks\b": "bunkers",         # "банки" -> banks -> bunkers
    r"\bmountain\b": "hill",         # "гора" -> mountain -> hill (more natural in gaming)

    # Items / Vehicles
    r"\bjumper\b": "jump pad",       # "джамп" -> jumper -> jump pad
    r"\bvan\b": "truck",             # "фургон" -> van -> truck

    # People
    r"\badversaries\b": "enemies",
    r"\bopponents\b": "enemies",
    r"\bmen\b": "players",           # "5 men left" -> "5 players left"
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


def log_translation(source_text: str, raw_translation: str, final_translation: str, source_lang: str = "ru", target_lang: str = "en", log_dir: str = "translation_logs"):
    """
    Log translations to a file for future glossary review.
    
    Args:
        source_text: Original text in source language
        raw_translation: Translation before glossary application
        final_translation: Translation after glossary application
        source_lang: Source language code
        target_lang: Target language code
        log_dir: Directory to store log files
    """
    try:
        # Create log directory if it doesn't exist
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # Create log file name with date
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = os.path.join(log_dir, f"translations_{today}.log")
        
        # Only log if glossary made changes
        if raw_translation != final_translation:
            timestamp = datetime.now().strftime("%H:%M:%S")
            log_entry = f"[{timestamp}] {source_lang}->{target_lang}\n"
            log_entry += f"  Source: {source_text}\n"
            log_entry += f"  Raw:    {raw_translation}\n"
            log_entry += f"  Fixed:  {final_translation}\n\n"
            
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(log_entry)
    except Exception as e:
        # Don't let logging errors crash the app
        logger.error("Logging error: %s", e)
