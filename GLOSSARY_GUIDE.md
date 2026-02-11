# Glossary Guide - Finding and Adding Translation Fixes

## Overview
The glossary system automatically fixes common mistranslations in gaming contexts. The system now includes automatic logging to help you identify new words that need to be added.

## How Translation Logging Works

When you run the translator, it automatically:
1. Translates the text using the AI model
2. Applies glossary fixes to improve gaming terminology
3. **Logs any changes to `translation_logs/`** (daily files)
4. Displays the final result

## Finding New Glossary Entries

### Method 1: Check the Translation Logs

1. Run your translator normally during gameplay
2. After your session, check the `translation_logs/` folder
3. Open today's log file: `translations_YYYY-MM-DD.log`
4. Review entries to see what's being fixed

**Example log entry:**
```
[14:23:45] ru->en
  Source: банки на крыше
  Raw:    banks on the roof
  Fixed:  bunkers on the roof
```

This shows:
- **Source**: Original Russian text
- **Raw**: What the AI model translated (incorrect)
- **Fixed**: What the glossary corrected it to (correct)

### Method 2: Watch the Console Output

Watch for awkward translations in real-time:
```
[Game RU->EN] "банки на крыше" -> "bunkers on the roof"
```

If you see something wrong that ISN'T being fixed, add it to the glossary.

## Adding New Glossary Entries

1. Open `glossary.py`
2. Find the appropriate section (Weapons, Actions, Locations, etc.)
3. Add a new regex pattern following this format:

```python
r"\b<bad_word>\b": "correct_word",
```

**Examples:**
```python
# Before: "He has many cartridges"
# After:  "He has many ammo"
r"\bcartridges\b": "ammo",

# Before: "Let's achieve the enemy"
# After:  "Let's finish the enemy"  
r"\bachieve\b": "finish",

# Before: "Banks on the roof"
# After:  "Bunkers on the roof"
r"\bbanks\b": "bunkers",
```

### Pattern Syntax

- `\b` = Word boundary (ensures whole word match)
- `\s` = Space character
- `\s?` = Optional space
- `\s+` = One or more spaces

**Good Practice:**
```python
r"\bpharmacy\b": "medkit",              # Matches "pharmacy" only
r"\bfirst\s?aid\s?kit\b": "medkit",    # Matches "first aid kit" or "firstaidkit"
```

## Common Gaming Terms to Watch For

Based on your gameplay, here are categories that often need fixes:

### Weapons/Items
- Cartridges → ammo
- Machine → AR (assault rifle)
- Van → truck
- Jumper → jump pad

### Actions
- Smoke → push (in combat context)
- Achieve → finish (completing kills)
- Nailed → knocked (downing players)
- Cut → rez/revive (reviving teammates)

### Locations
- Banks → bunkers
- Upstairs → on high ground

### General
- People/men → players
- Adversaries → enemies

## Testing Your Changes

1. Add your new glossary entry
2. Save `glossary.py`
3. Restart the translator
4. Test with actual gameplay or use the test scripts
5. Check if the translation improved
6. Review the logs to confirm the fix is applied

## Tips

- **Start with exact phrases** - Use `\b` word boundaries to match whole words only
- **Case insensitive** - The glossary automatically handles uppercase/lowercase
- **Be specific** - Don't replace common words that might be correct in other contexts
- **Test thoroughly** - Make sure your pattern doesn't break other translations
- **Check the logs** - The logs only show entries that were changed, making it easy to see what's working

## Log File Location

```
translation_logs/
  └── translations_2026-02-11.log
  └── translations_2026-02-12.log
  └── ...
```

Each file contains all glossary fixes for that day, making it easy to review and identify patterns.

## Need More Help?

- Check existing patterns in `glossary.py` for examples
- Test with `test_*.py` scripts
- Review the regex documentation: https://regex101.com/
