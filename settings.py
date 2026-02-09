"""
Persistent settings for the Real-time Translator overlay.
Saves to / loads from  settings.json  next to the script.
"""

import json
import os

_SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")

DEFAULTS = {
    # Overlay geometry
    "overlay_width": 900,
    "overlay_height": 140,
    "overlay_x": -1,        # -1 = auto-center
    "overlay_y": -1,        # -1 = auto (just above taskbar)
    "overlay_opacity": 0.88,

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

    # Whisper model
    "whisper_model": "medium",       # tiny, base, small, medium, large-v2

    # Language
    "app_language": "english",       # "english" or "russian" — UI text language
    "source_language": "english",    # "english" or "russian" — YOUR language
    "filter_game_language": True,    # Only process game audio matching expected language

    # Audio filtering
    "speech_filter_enabled": True,   # Band-pass filter (300-3000 Hz) on game audio
    "game_noise_gate": 0.012,        # RMS threshold for game audio (higher = reject more noise)
                                     # 0.005 = very sensitive, 0.02 = strict, 0.04 = very strict

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
                print(f"[Settings] Loaded from {_SETTINGS_FILE}")
            except Exception as e:
                print(f"[Settings] Could not load settings: {e}  (using defaults)")
        else:
            print("[Settings] No settings file found — using defaults.")

    def save(self):
        try:
            with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
            print(f"[Settings] Saved to {_SETTINGS_FILE}")
        except Exception as e:
            print(f"[Settings] Could not save: {e}")

    def reset(self):
        self._data = dict(DEFAULTS)
        self.save()
