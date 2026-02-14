import re
import os
from datetime import datetime
from logger_config import get_logger

logger = get_logger("Glossary")

# ==============================================================================
# PROPER NAME PROTECTION - Pre-Translation Fixes (Source Language Side)
# ==============================================================================
# Whisper often misrecognizes proper names (player names, real names, etc.)
# because they don't exist in its vocabulary. These corrections fix the
# TRANSCRIPTION before it goes to the translator.
#
# Format: { "garbled_transcription": "correct_name" }
# Add entries here when you notice Whisper consistently garbling a name.
# ==============================================================================

# Corrections applied to RUSSIAN transcriptions (before translation)
NAME_CORRECTIONS_RU = {
    r"\bМузыкар\b": "Музаффар",      # Whisper hears "Muzaffar" as "Музыкар"
    r"\bМузыка\b(?!\s)": "Музаффар",  # Sometimes garbled as just "Музыка" (music)
    r"\bМузык\b": "Музаффар",        # Truncated garble of Музаффар
    r"\bМузафар\b": "Музаффар",      # Close but missing double ф

    # "переводчик" (translator) — Whisper garbles to "приводчик" (driver)
    r"\bприводчик\b": "переводчик",
    r"\bприводчик привёл\b": "переводчик перевёл",
    r"\bприводчик привел\b": "переводчик перевёл",

    # Fortnite — Whisper doesn't know the game name
    r"\bфортнайт\b": "Fortnite",
    r"\bфорнайт\b": "Fortnite",
    r"\bфортнайте\b": "Fortnite",

    # Gaming callouts Whisper garbles
    r"\bшутган[ыи]?\b": "дробовик",   # "shotgun" borrowed word -> proper Russian
    r"\bшотган[ыи]?\b": "дробовик",
    r"\bграун\b": "ground",            # English "ground" transliterated into Russian
    r"\bвайт\b": "wait",              # English "wait" transliterated into Russian
}

# Corrections applied to ENGLISH transcriptions (before translation)
NAME_CORRECTIONS_EN = {
    # Add English-side name corrections here if needed
    # e.g. r"\bmusiker\b": "Muzaffar",
}


def apply_name_corrections(text: str, language: str = "ru") -> str:
    """
    Fix commonly misrecognized proper names in transcriptions.
    Applied BEFORE translation to fix Whisper's garbled output.
    """
    if not text:
        return text
    
    corrections = NAME_CORRECTIONS_RU if language == "ru" else NAME_CORRECTIONS_EN
    original = text
    for pattern, replacement in corrections.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    
    if text != original:
        logger.info("Name correction: '%s' -> '%s'", original, text)
    
    return text


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
    r"\bgolden\s+machine\s+gun\b": "Gold AR",       # "золотой автомат" -> golden machine gun
    r"\bgolden\s+machine\b": "Gold AR",              # fallback: "золотой автомат"
    r"\bgolden\s+AR\b": "Gold AR",                   # catch "golden AR" after other fixes
    # "автомат" can mean assault rifle OR vending machine — only fix when weapon context
    r"\bvending\s+machine\s+sell\b": "AR sell",      # "автомат продает" in weapon context
    r"\bmachine\s+gun\b": "AR",                      # "пулемет/автомат" -> machine gun -> AR
    r"\bnormal\s+machine\b": "normal AR",            # e.g. "возьми нормальный автомат"

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
    r"\bbulletins\b": "bullets",    # "бульеты" (borrowed English) -> bulletins -> bullets
    r"\bbullets\b": "ammo",
    r"\bspare\s?parts\b": "ammo",    # "запасные" (spare) sometimes -> spare parts
    r"\bcartridge\b": "ammo",
    r"\bthe\s+machine\b": "the AR",  # "автомат" -> the machine -> the AR
    r"\ba\s+machine\b": "an AR",     # "автомат" -> a machine -> an AR
    r"\bautomaton\b": "AR",
    r"\bvending machine\b": "AR",    # opus-mt: "автомат" -> vending machine -> AR
    r"\bmy vending machine\b": "my AR",
    r"\bjokers?\b": "shotguns",      # opus-mt: "шутганы" -> jokers -> shotguns
    r"\bAuto-machine machine\b": "Automatic AR",  # opus-mt: "автоматический автомат"
    r"\bNope\b": "No",               # opus-mt: "Нет" -> Nope (too informal)
    r"\bHere we go\b": "Let's go",   # opus-mt: "Поехали" -> Here we go
    r"\bGood job\b": "Well done",    # opus-mt: "Молодцы" -> Good job (close but not exact)
    r"\bchicken pows\b": "chicken pilaf",  # opus-mt: "плов" -> pows
    r"\bFortnight\b": "Fortnite",    # opus-mt: close but wrong spelling
    r"\bLet's pull it off\b": "Let's crank",  # opus-mt: "Откручиваем"
    r"\byou're fucking shit\b": "you're crazy",  # opus-mt: escalates "чёртовщина"

    # Rarity names (Fortnite uses "Gold" not "golden")
    r"\bgolden\b": "Gold",           # "золотой" -> golden -> Gold

    # Movement / Actions
    r"\bwander\b": "loot",           # "лутать" sometimes garbles
    r"\bcleaned\s?up\b": "cleared",  # "зачистили"
    r"\bwe(?:'re|\s+are)?\s+jumping\b": "we're dropping",  # "прыгаем" -> we're jumping -> we're dropping
    r"\brun\s?away\b": "running",
    r"\blet(?:'s)?\s+smoke\b": "let's push",  # "пушить" -> let's smoke -> let's push
    r"\bwill\s+smoke\b": "will push",
    r"\bachieve\b": "finish",        # "добить" -> achieve -> finish
    r"\bnailed\b": "knocked",        # "нокнула" -> nailed -> knocked
    r"\bcut,\s*cut\b": "rez, rez",   # "рез, рез" -> cut, cut -> rez, rez
    r"\bcut\s+to\s+a\s+sheet\b": "rez on leaf",
    r"\bthis\s+cut\b": "this rez",
    r"\bI'm\s+jumping\b": "I'm pushing",      # "я прыгаю" solo context
    r"\bfollow the stone\b": "behind the rock",  # "за камнем" -> follow stone
    r"\bbehind a tree\b": "behind tree",       # simplify

    # Locations / Terrain
    r"\bupstairs\b": "on high ground",
    r"\bbanks\b": "bunkers",         # "банки" -> banks -> bunkers
    r"\bmountain\b": "hill",         # "гора" -> mountain -> hill (more natural in gaming)
    r"\b(\d+)\s+stores\b": r"\1 squads",  # "склада" -> stores -> squads (gaming context)
    r"\bdifferent\s+stores\b": "different squads",

    # Items / Vehicles
    r"\bjumper\b": "jump pad",       # "джамп" -> jumper -> jump pad
    r"\bvan\b": "truck",             # "фургон" -> van -> truck

    # Bots (AI players)
    r"\bboots\b": "bots",            # "боты" -> boots -> bots (AI players)
    r"\bit's a boot\b": "it's a bot",
    r"\bthese boots\b": "these bots",

    # Shotgun ("шотган/шутган" - borrowed from English, Whisper garbles it)
    r"\bjokes\b(?=.*\b(?:shoot|gun|kill|damage|hit))": "shotgun shells",  # context-aware

    # People
    r"\badversaries\b": "enemies",
    r"\bopponents\b": "enemies",
    r"\bschoolchildren\b": "kids",        # "школьники" -> schoolchildren -> kids

    # Угу -> Uh-huh/Yeah (not "Ugo" transliteration)
    r"\bUgo\b": "Uh-huh",                                   # "Угу" -> Ugo -> Uh-huh

    # Жесть -> Damn/Insane (not "A meal")
    r"\bA meal\b": "Damn!",                                  # "Жесть" -> A meal -> Damn!

    # Молодец -> Well done (not "Young man" / "Young people")
    r"\bYoung man\b": "Well done",                           # "Молодец" -> Young man -> Well done
    r"\bYoung people\b": "Well done!",                       # "Молодцы" -> Young people -> Well done!

    # Разбил -> Cracked (shield), not "smashed"
    r"\bHe smashed one\b": "He cracked one",                 # "Разбил одного" -> cracked shield
    r"\bsmashed\b": "cracked",                               # gaming: break shield

    # Ног/нокнул -> knocked/downed (not "foot"/"leg")
    r"\bThe foot\b": "Knocked!",                              # "Ног" (short for нок) -> knocked
    r"\bWhite leg\b": "White, knocked!",                      # "Белый ног" -> white HP, knocked
    r"\bLeg,\s*I've been kicking his legs\b": "Knocked, I knocked him",

    # заныкнулся -> hid (not "drowned")
    r"\bI drowned under a tree\b": "I hid under a tree",     # "заныкнулся" = hid

    # Жетпак -> Jetpack (not "badge")
    r"\bA badge can be bought\b": "A jetpack can be bought",
    r"\bbadge\b(?=.*(?:fly|buy|bought|launch))": "jetpack",  # context-aware

    # золотарство -> gold loot (not "goldsmithing")
    r"\bgoldsmithing\b": "gold looting",

    # Fasting -> posted up ("пост" = position)
    r"\bThey're fasting\b": "They're posted up",             # "с постом" = at the post

    # Hallucinations / Idioms / Common Mistranslations
    r"\bthe hair is white\b": "bad aim",             # "косой" -> hair is white -> bad aim
    r"\bdrifting down the road\b": "dropping",       # "скидываешься" -> drifting -> dropping
    r"\bready to press\b": "Ready",                  # "готову (нажать)" -> ready to press -> Ready
    r"\bI get the fuck\b": "I got it, fuck",        # "я понял, блять" -> I get the fuck
    r"\bI'm getting pretty\b": "I'm jumping",       # "я прыгаю" -> I'm getting pretty (CRITICAL FIX)
    r"\bthe walk\b": "seems like",                   # "походу" -> the walk -> seems like
    r"\bthe psychic\b": "psychos",                   # "психи" -> the psychic -> psychos
    r"\bLAUGH is a joke\b": "[laughing]",           # "СМЕХ" -> LAUGH is a joke
    r"\bLAUGH\b": "[laughing]",                       # "СМЕХ" simplified
    r"\bSoca\b": "Bitch",                            # "Сука" -> Soca (transliteration error)
    r"\bthat's right!\b": "Fuuuck!",                  # "Ебааа!" -> that's right (wrong exclamation)
    r"\bOh, my God!\b(?=.*(?:wow|whoa))": "Whoa!",  # "Ухты!" context-aware

    # ── Feb 14 log fixes ────────────────────────────────────────────
    # Over-translation: translator adds "not at all" to simple negatives
    r"\bOh, no, not at all\.\b": "Oh, no.",          # "О, нет" should just be "Oh, no."
    r"\bNo, not at all\.\b": "No.",                   # "Нет" should just be "No."

    # Over-translation: 3x "нет" becomes 4x "no"
    r"\bNo, no, no, no\.\b": "No, no, no.",          # "Нет, нет, нет" = 3 nos, not 4

    # Over-translation: simple exclamations padded
    r"^Nice work\.?$": "Nice.",                       # "Найс" = just "Nice"
    r"^Nice work!$": "Nice!",                         # "Найс!" = just "Nice!"

    # Бочка -> Barrel (not "bottle")
    r"\bA bottle\b": "A barrel",                      # "Бочка" = barrel
    r"\bthe bottle\b": "the barrel",

    # Сундук -> Chest (not "soundtrack")
    r"\bThe soundtrack\b": "The chest",               # "Сундук" = chest/treasure chest
    r"\bthe soundtrack\b": "the chest",

    # кушать -> eat (not "cook")
    r"\bI love to cook\b": "I love to eat",           # "Я люблю кушать" = eat

    # плов -> pilaf (not "flower")
    r"\bchicken flower\b": "chicken pilaf",           # "плов с курицей" = pilaf

    # лук -> bow (Fortnite weapon, not "onion")
    r"\bthere was onion\b": "there was a bow",        # Fortnite bow weapon
    r"\bonions?\b(?=.*(?:pick|grab|take|loot|found|shoot|damage|bow))": "bows",

    # Fortnite -> not "forty-nine"
    r"\bforty-nine\b": "Fortnite",                    # "фортнайт" mistranslated
    r"\bfortnight\b": "Fortnite",                     # alternate misspelling

    # Рома/Роман -> proper name (not "Rome"/"novel")
    r"^Rome\!?\s*$": "Roma!",                         # "Рома" = person's name
    r"\bRome!\b": "Roma!",
    r"\bRome,\s*Rome\b": "Roma, Roma",
    r"\bRoma, no!\b": "Roma, no!",
    r"^The novel\.?$": "Roman.",                      # "Роман" = person's name

    # ground (not "crow") — gaming callout
    r"\bCrow, crow\b": "Ground, ground",              # "граун" = ground

    # wait (not "white") — gaming callout
    r"\bWhite-white\b": "Wait-wait",                  # "вайт-вайт" = wait-wait
    r"\bWhite, white, white\b": "Wait, wait, wait",

    # Ferris wheel (not "sighting wheel")
    r"\bsighting wheel\b": "Ferris wheel",            # "колесо обозрения" = Ferris wheel

    # Шлюпки -> boats (not "shed")
    r"\bIt's a shed\b": "Boats",                      # "Шлюпки" = boats/dinghies

    # жопа -> ass/damn (not "my God")
    # Note: hard to fix without context since "Oh, my God" is used elsewhere

    # Откручиваем -> cranking (not "roll it up")
    r"\bLet's roll it up\b": "Let's crank it",        # "Откручиваем" = unscrewing/cranking

    # Автоматически автоматизированный -> automatic AR
    r"\bAutomatically automated\b": "Automatic AR",   # "автоматический автомат"

    # пылесос/пылесосить -> vacuum/loot everything (Fortnite slang)
    r"\bYou're a dirtbag\b": "You're a vacuum",       # "Вы пылесос" = you loot everything
    r"\bYou've ruined everything\b": "You've looted everything",
    r"\bYou're pollinating onions\b": "You're vacuuming the bows",  # looting all bows

    # He killed her -> She killed (feminine verb "убила")
    r"\bHe killed her\b": "She killed him",            # "Убила" = she killed

    # shoot yourself -> shoot back
    r"\bwhy don't you shoot yourself\b": "why aren't you shooting back",

    # motherfucker escalation fix
    r"\bmotherfucker\b": "damn thing",                 # "чёртовщина" = devilry, not motherfucker

    # shotgun (not "joke")
    r"\bI need a joke\b": "I need shotguns",           # "шутганы" = shotguns
    
    # Knocked/Downed (CRITICAL GAMING FIX)
    r"\bnaked and naked\b": "knocked knocked",       # "нока-нака-накан" -> naked and naked -> knocked knocked
    r"\balready naked\b": "already knocked",         # "уже нокан" -> already naked -> already knocked
    r"\bnaked\b(?=.*(player|enemy|he|she|down|kill))": "knocked",  # "нокан" -> naked (context-aware)

    # Only replace "men/people" when preceded by a number or "many/few/some"
    r"\b(\d+)\s+men\b": r"\1 players",                    # "5 men left" -> "5 players left"
    r"\b(many|few|some|more|several)\s+men\b": r"\1 players",
    r"\b(\d+)\s+people\b": r"\1 players",                  # "5 people left" -> "5 players left"
    r"\b(many|few|some|more|several|so many)\s+people\b": r"\1 players",
}

# ==============================================================================
# EN -> RU Gaming Glossary (for Mic translations going to Russian teammates)
# ==============================================================================
GAMER_GLOSSARY_RU = {
    # Lobby (don't translate as "вестибюль" - use gaming term "лобби")
    r"\bвестибюл[ьеи]\b": "лобби",          # lobby -> вестибюль -> лобби
    r"\bв\s+вестибюл[ьеи]\b": "в лобби",

    # Noob (keep as-is, don't translate)
    r"\bнооб\b": "нуб",                      # noob -> нооб -> нуб
    r"\bноб\b": "нуб",                        # noob -> ноб -> нуб

    # "He's low" / "they're low" => low HP, not short/small
    r"\bон\s+низкий\b": "у него мало хп",                  # he's low HP
    r"\bона\s+низкая\b": "у неё мало хп",                  # she's low HP
    r"\bони\s+низкие\b": "у них мало хп",                  # they're low HP
    r"\bодин\s+(?:из\s+них\s+)?низкий\b": "один ваншот",  # one is low
    r"\bнет,\s+нет,\s+нет,\s+он\s+низкий\b": "нет, нет, нет, у него мало хп",

    # Rush => раш (gaming loan word, not "hurry")
    r"\bРасс,\s*расс,\s*расс\b": "раш, раш, раш",        # Rush transliteration fail
    r"\bпоспешите,\s*поспешите,\s*поспешите\b": "раш, раш, раш",
    r"\bпоспешите\b": "рашьте",                             # hurry -> rush
    r"\bПоторопись,\s*поторопись\b": "раш, раш",
    r"\bпоторопись\b": "рашь",
    r"\bспешите\b": "рашите",                               # rush (imperative)
    r"\bреш,\s*шеш,\s*шеш\b": "раш, раш, раш",           # garbled "rush"

    # "gogogogo" => давай давай (not бабушка/grandma)
    r"\bДавай,\s*бабушка\b": "Давай, давай, давай",         # gogo misheard as grandma
    r"\bДа,\s*бабушка\b": "Да, давай, давай",               # "Yeah, gogogogo"
    r"\bбабушка\b": "давай давай",                           # fallback

    # Come here => Иди сюда (not "Приезжайте" = drive/travel here)
    r"\bПриезжайте\s+сюда\b": "Идите сюда",
    r"\bприезжайте\b": "идите",
    r"\bПриезжай\s+сюда\b": "Иди сюда",
    r"\bприезжай\b": "иди",

    # Pump (shotgun) => помповик, not насос (water pump)
    r"\bфиолетовых?\s+насосо?в?\b": "фиолетовый помповик",
    r"\bнасос\s+портала\b": "помповик",
    r"\bнасос\b": "помповик",                               # pump (shotgun)

    # Mark => отметь (ping), not person name "Марк"
    r"\bМарк,\s*Марк,\s*Марк\b": "отметь, отметь, отметь",
    r"\bМарк,\s*Марк\b": "отметь, отметь",
    r"(?i)\bГде\s+враг\?\s*Марк,\s*Марк,\s*Марк\b": "Где враг? Отметь, отметь, отметь",
    r"(?i)\bГде\s+знак\s+Марк\s+Марк\b": "Где? Отметь, отметь",

    # Push => пуш (gaming attack), not "толкнуть" (physical push)
    r"\bНаталкивай,\s*наталкивай\b": "пуш, пуш",
    r"\bтолкнуть\b": "пуш",
    r"\bНатолкните\b": "Пуш",

    # Reload => перезарядить (weapon), not перезагрузить (reboot computer)
    r"\bперезагрузить,\s*перезагрузить,\s*перезагрузить\b": "перезарядись, перезарядись, перезарядись",
    r"\bперезагрузить,\s*перезагрузить\b": "перезарядись, перезарядись",
    r"\bперезагрузить\b": "перезарядить",
    r"\bперезагружаются\b": "ребутятся",                    # rebooting (Fortnite respawn)
    r"\bперезагрузили\b": "ребутнули",
    r"\bперезагрузились\b": "респнулись",
    r"\bна\s+перезагрузку\b": "на ребут",
    r"\bперезагрузка,\s*перезагрузка\b": "ребут, ребут",
    r"\bперезагрузка\b": "ребут",
    r"\bперезагрузился\b": "ребутнулся",
    r"\bбыли\s+перезагружены\b": "были ребутнуты",

    # Launchpad => лаунчпад/трамплин (not "запускная панель")
    r"\bЗапускная\s+панель\b": "Лаунчпад",
    r"\bзапускная\s+панель\b": "лаунчпад",
    r"\bзапускную\s+панель\b": "лаунчпад",

    # Shotgun => дробовик/шотган (not "пистолет")
    r"\bФиолетовый\s+пистолет\b": "Фиолетовый дробовик",
    r"\bфиолетовый\s+пистолет\b": "фиолетовый дробовик",

    # Knock (downed) => нокнут (not "стучит" = knocking on door)
    r"\bОдин\s+стучит,\s*другой\s+стучит\b": "Один нокнут, другой нокнут",
    r"\bстучит\b": "нокнут",                                # knock = downed

    # Sniper ammo => снайперские патроны (not "оружие")
    r"\bСнайперское\s+оружие,\s*снайперское\s+оружие\b": "Снайперские патроны, снайперские патроны",
    r"\bснайперское\s+оружие\b": "снайперские патроны",

    # Skin (don't translate as "кожа")
    r"\bновая\s+кожа\b": "новый скин",       # new skin -> новая кожа -> новый скин
    r"\bкожа\b": "скин",                      # skin -> кожа -> скин (in gaming context)

    # Bug (don't translate as "жучок")
    r"\bжучок\b": "баг",                      # bug -> жучок -> баг
    r"\bжучк[аиов]\b": "баг",

    # Weapons / Actions
    r"\bстрело[к]\b": "дробовик",            # shotgun -> стрелок -> дробовик (NLLB error fix)
    r"\bя\s+загружу\b": "перезаряжаюсь",     # I will load -> я загружу -> перезаряжаюсь
    r"\bстреля[ют]\b": "стреляют",           # keep shooting as-is

    # Exclamations & Slang (Russian output corrections)
    r"\bСока\b": "Сука",                       # Soca -> Сука (bitch/damn)
    r"\bПоходу\b": "Похоже",                   # The walk -> Seems like
    r"\bпрыгаю\b(?!.*парашют)": "пушу",       # jumping -> pushing (without parachute)
    r"\bсмех\b": "[смеется]",                 # LAUGH -> [laughing]
    r"\bпсихиатр\b": "псих",                   # psychiatrist -> psycho
    r"\bнака\b": "нокнут",                     # garbled knock -> нака -> нокнут
    r"\bнока\b": "нокнут",                     # garbled knock -> нока -> нокнут

    # Team ("командное сообщество" is wrong — just "команда")
    r"\bкомандное\s+сообщество\b": "команда",  # team -> командное сообщество -> команда
}

def apply_gaming_glossary(text: str, target_lang: str = "en") -> str:
    """Applies regex replacements to enforce gaming terminology.
    
    Args:
        text: The translated text to fix
        target_lang: The target language ('en' or 'ru') to pick the right glossary
    """
    if not text:
        return text
    
    glossary = GAMER_GLOSSARY_EN if target_lang == "en" else GAMER_GLOSSARY_RU
    
    # Case-insensitive replacement
    for pattern, replacement in glossary.items():
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
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        if raw_translation != final_translation:
            # Glossary made changes — show before/after
            log_entry = f"[{timestamp}] {source_lang}->{target_lang}\n"
            log_entry += f"  Source: {source_text}\n"
            log_entry += f"  Raw:    {raw_translation}\n"
            log_entry += f"  Fixed:  {final_translation}\n\n"
        else:
            # No glossary changes — still log for review
            log_entry = f"[{timestamp}] {source_lang}->{target_lang}\n"
            log_entry += f"  Source: {source_text}\n"
            log_entry += f"  Result: {final_translation}\n\n"
        
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_entry)
    except Exception as e:
        # Don't let logging errors crash the app
        logger.error("Logging error: %s", e)
