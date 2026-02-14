"""
Persistent settings for the Real-time Translator overlay.
Saves to / loads from  settings.json  next to the script.
"""

import json
import os
from logger_config import get_logger

logger = get_logger("Settings")

_SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")

DEFAULTS = {
    # Overlay geometry
    "overlay_width": 900,
    "overlay_height": 140,
    "overlay_x": -1,        # -1 = auto-center
    "overlay_y": -1,        # -1 = auto (just above taskbar)
    "overlay_opacity": 0.88,      # legacy (ignored when bg/text opacity set)
    "bg_opacity": 0.45,             # background panel transparency (0=invisible, 1=solid)
    "text_opacity": 0.95,           # text / content transparency

    # Colors (hex)
    "bg_color": "#0d1117",
    "game_text_color": "#58d68d",
    "mic_text_color": "#5dade2",
    "accent_color": "#444c56",
    "status_color": "#7b8794",

    # Fonts
    "font_family": "Segoe UI",
    "game_font_size": 14,
    "mic_font_size": 12,

    # Streaming preview
    "streaming_enabled": True,
    "streaming_interval_ms": 1200,   # How often to show preview text

    # Chat log (scrolling history for game translations)
    "chat_log_lines": 5,             # How many recent game translations to show (2-10)
    "chat_fade_enabled": True,       # Older messages gradually dim
    "chat_line_duration_sec": 12,    # Seconds before a line fully fades out (0 = never fade)

    # Whisper model
    "whisper_model": "medium",       # tiny, base, small, medium, large-v2, large-v3

    # Translation model
    "translation_model": "opus-mt", # opus-mt, nllb-600M, nllb-1.3B, nllb-600M-ct2, nllb-1.3B-ct2

    # Language
    "app_language": "english",       # "english" or "russian" — UI text language
    "source_language": "english",    # "english" or "russian" — YOUR language
    "filter_game_language": True,    # Only process game audio matching expected language

    # Audio filtering
    "speech_filter_enabled": True,   # Band-pass filter (300-3000 Hz) on game audio
    "game_noise_gate": 0.006,        # RMS threshold for game audio (higher = reject more noise)
                                     # 0.005 = very sensitive, 0.02 = strict, 0.04 = very strict
                                     # Lowered to 0.006 to better capture voice chat
    "clean_audio_mode": False,       # Optimize for clear voice chat (disable band-pass, gentle VAD)
                                     # Enable when friend uses good mic & game sounds are low

    # Mic overlay
    "show_mic_overlay": True,        # Show mic (your voice) subtitles on overlay

    # Transliteration
    "transliterate_mic": True,       # Show mic translations as Latin-script Russian
                                     # e.g. "ya idu" instead of "я иду"

    # First-run
    "first_run_shown": False,
}


class Settings:
    """Thread-safe settings store with JSON persistence."""

    def __init__(self):
        self._data = dict(DEFAULTS)
        self.load()

    # ── Access ──────────────────────────────────────────────────────

    def get(self, key):
        return self._data.get(key, DEFAULTS.get(key))

    def set(self, key, value):
        self._data[key] = value

    def all(self):
        return dict(self._data)

    # ── Persistence ─────────────────────────────────────────────────

    def load(self):
        if os.path.exists(_SETTINGS_FILE):
            try:
                with open(_SETTINGS_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                for k, v in saved.items():
                    if k in DEFAULTS:
                        self._data[k] = v
                logger.info("Loaded from %s", _SETTINGS_FILE)
            except Exception as e:
                logger.warning("Could not load settings: %s  (using defaults)", e)
        else:
            logger.info("No settings file found — using defaults.")

    def save(self):
        try:
            with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
            logger.info("Saved to %s", _SETTINGS_FILE)
        except Exception as e:
            logger.error("Could not save: %s", e)

    def reset(self):
        self._data = dict(DEFAULTS)
        self.save()
