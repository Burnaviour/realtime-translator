"""
UI text translations for the Real-time Translator.

Usage:
    from locales import t
    t("welcome_title")          # returns text in current app_language
    t("welcome_title", "ru")    # force Russian
"""

from __future__ import annotations

# ── All translatable strings ────────────────────────────────────────

_STRINGS: dict[str, dict[str, str]] = {
    # ── Welcome popup ───────────────────────────────────────────────
    "welcome_title": {
        "en": "Welcome to Real-time Voice Translator!",
        "ru": "Добро пожаловать в Голосовой Переводчик!",
    },
    "welcome_created_for": {
        "en": "Created for VIKA",
        "ru": "Создано для ВИКИ",
    },
    "welcome_your_lang": {
        "en": "Your language: ENGLISH",
        "ru": "Ваш язык: РУССКИЙ",
    },
    "welcome_your_lang_ru": {
        "en": "Your language: RUSSIAN",
        "ru": "Ваш язык: РУССКИЙ",
    },
    "welcome_game_en": {
        "en": "Game / friend audio: Russian -> translated to English for you",
        "ru": "Аудио игры / друга: Русский -> переведено на Английский для вас",
    },
    "welcome_mic_en": {
        "en": "Your microphone: English -> translated to Russian for them",
        "ru": "Ваш микрофон: Английский -> переведено на Русский для них",
    },
    "welcome_game_ru": {
        "en": "Game / friend audio: English -> translated to Russian for you",
        "ru": "Аудио игры / друга: Английский -> переведено на Русский для вас",
    },
    "welcome_mic_ru": {
        "en": "Your microphone: Russian -> translated to English for them",
        "ru": "Ваш микрофон: Русский -> переведено на Английский для них",
    },
    "welcome_hotkeys_label": {
        "en": "Hotkeys:",
        "ru": "Горячие клавиши:",
    },
    "welcome_f8": {
        "en": "F8  — Lock / Unlock overlay (click-through toggle)",
        "ru": "F8  — Заблокировать / Разблокировать (переключить прозрачность)",
    },
    "welcome_f9": {
        "en": "F9  — Show / Hide overlay",
        "ru": "F9  — Показать / Скрыть оверлей",
    },
    "welcome_f10": {
        "en": "F10 — Open Settings panel",
        "ru": "F10 — Открыть Настройки",
    },
    "welcome_change_lang": {
        "en": "You can change your language in Settings (F10).\nNote: Changing language requires a restart to reload models.",
        "ru": "Вы можете изменить язык в Настройках (F10).\nПримечание: Изменение языка требует перезапуска.",
    },
    "welcome_got_it": {
        "en": "Got it!",
        "ru": "Понятно!",
    },

    # ── Overlay status bar ──────────────────────────────────────────
    "status_locked": {
        "en": "LOCKED \u2022 F8 Lock \u2022 F9 Hide \u2022 F10 Settings",
        "ru": "ЗАБЛОКИРОВАНО \u2022 F8 Блок \u2022 F9 Скрыть \u2022 F10 Настройки",
    },
    "status_unlocked": {
        "en": "UNLOCKED \u2013 Drag edges to resize \u2022 F8 Lock \u2022 F10 Settings",
        "ru": "РАЗБЛОКИРОВАНО \u2013 Тяните края для изменения размера \u2022 F8 Блок \u2022 F10 Настройки",
    },
    "listening_game": {
        "en": "Listening for game audio\u2026",
        "ru": "Ожидание аудио игры\u2026",
    },
    "listening_mic": {
        "en": "Listening for mic input\u2026",
        "ru": "Ожидание микрофона\u2026",
    },

    # ── Settings window ─────────────────────────────────────────────
    "settings_title": {
        "en": "Translator Settings",
        "ru": "Настройки Переводчика",
    },
    "sec_language": {
        "en": "Language",
        "ru": "Язык",
    },
    "sec_whisper": {
        "en": "Whisper Model",
        "ru": "Модель Whisper",
    },
    "sec_overlay_size": {
        "en": "Overlay Size",
        "ru": "Размер Оверлея",
    },
    "sec_colors": {
        "en": "Colors  (click swatch to pick)",
        "ru": "Цвета  (нажмите для выбора)",
    },
    "sec_fonts": {
        "en": "Fonts",
        "ru": "Шрифты",
    },
    "sec_streaming": {
        "en": "Streaming / Live Preview",
        "ru": "Потоковый / Живой Просмотр",
    },
    "lbl_my_language": {
        "en": "My language",
        "ru": "Мой язык",
    },
    "lbl_app_language": {
        "en": "App language",
        "ru": "Язык интерфейса",
    },
    "lbl_filter_game": {
        "en": "Only detect selected game language",
        "ru": "Распознавать только выбранный язык игры",
    },
    "sec_audio_filter": {
        "en": "Game Audio Filtering",
        "ru": "Фильтрация Аудио Игры",
    },
    "lbl_clean_audio_mode": {
        "en": "Clean audio mode (good mic, low game volume)",
        "ru": "Режим чистого аудио (хороший микрофон, тихая игра)",
    },
    "lbl_speech_filter": {
        "en": "Speech band-pass filter (removes game sounds)",
        "ru": "Фильтр речевых частот (убирает звуки игры)",
    },
    "lbl_noise_gate": {
        "en": "Game noise gate (higher = stricter)",
        "ru": "Порог шума игры (выше = строже)",
    },
    "lbl_noise_gate_hint": {
        "en": "  0.005=sensitive  0.012=default  0.025=strict  0.04=very strict",
        "ru": "  0.005=чувствит.  0.012=обычный  0.025=строгий  0.04=очень строгий",
    },
    "lbl_model_size": {
        "en": "Model size",
        "ru": "Размер модели",
    },
    "lbl_model_hint": {
        "en": "  tiny=fastest  base  small  medium  large-v2=best accuracy",
        "ru": "  tiny=быстрая  base  small  medium  large-v2=лучшая точность",
    },
    "sec_translation": {
        "en": "Translation Model",
        "ru": "Модель Перевода",
    },
    "lbl_trans_model": {
        "en": "Translation model",
        "ru": "Модель перевода",
    },
    "lbl_trans_model_hint": {
        "en": "  opus-mt=fast  opus-mt-big=better  nllb-600M=best  nllb-1.3B=highest",
        "ru": "  opus-mt=быстр  opus-mt-big=лучше  nllb-600M=лучшая  nllb-1.3B=макс",
    },
    "lbl_transliterate_mic": {
        "en": "Transliterate mic (show Latin-script Russian: ya idu)",
        "ru": "Транслитерация микрофона (латиницей: ya idu)",
    },
    "lbl_width": {
        "en": "Width",
        "ru": "Ширина",
    },
    "lbl_height": {
        "en": "Height",
        "ru": "Высота",
    },
    "lbl_opacity": {
        "en": "Opacity",
        "ru": "Прозрачность",
    },
    "lbl_bg_color": {
        "en": "Background",
        "ru": "Фон",
    },
    "lbl_game_text_color": {
        "en": "Game text",
        "ru": "Текст игры",
    },
    "lbl_mic_text_color": {
        "en": "Mic text",
        "ru": "Текст микрофона",
    },
    "lbl_separator_color": {
        "en": "Separator",
        "ru": "Разделитель",
    },
    "lbl_status_color": {
        "en": "Status text",
        "ru": "Статус текст",
    },
    "lbl_game_font": {
        "en": "Game font size",
        "ru": "Размер шрифта игры",
    },
    "lbl_mic_font": {
        "en": "Mic font size",
        "ru": "Размер шрифта микрофона",
    },
    "lbl_streaming_enable": {
        "en": "Enable live transcription preview",
        "ru": "Включить живой предпросмотр",
    },
    "lbl_streaming_interval": {
        "en": "Preview interval (ms)",
        "ru": "Интервал предпросмотра (мс)",
    },
    "btn_apply": {
        "en": "Apply",
        "ru": "Применить",
    },
    "btn_save": {
        "en": "Save",
        "ru": "Сохранить",
    },
    "btn_reset": {
        "en": "Reset Defaults",
        "ru": "Сбросить",
    },
    "btn_restart": {
        "en": "Save & Restart",
        "ru": "Сохранить и Перезапустить",
    },
    "console_restarting": {
        "en": "[Restart] Restarting application...",
        "ru": "[Перезапуск] Перезапуск приложения...",
    },

    # ── Console / main.py ──────────────────────────────────────────
    "console_title": {
        "en": "Real-time Voice Translator",
        "ru": "Голосовой Переводчик в Реальном Времени",
    },
    "console_my_lang": {
        "en": "My language",
        "ru": "Мой язык",
    },
    "console_loading": {
        "en": "[Init] Loading AI models (first run downloads ~1-2 GB)...",
        "ru": "[Инит] Загрузка AI моделей (первый запуск скачивает ~1-2 ГБ)...",
    },
    "console_whisper_model": {
        "en": "[Init] Whisper model",
        "ru": "[Инит] Модель Whisper",
    },
    "console_ready": {
        "en": "[Ready] All models loaded.",
        "ru": "[Готово] Все модели загружены.",
    },
    "console_keys": {
        "en": "[Keys]  F8 = Lock/Unlock  |  F9 = Show/Hide  |  F10 = Settings  |  Ctrl+C = Quit",
        "ru": "[Клавиши]  F8 = Блок  |  F9 = Скрыть  |  F10 = Настройки  |  Ctrl+C = Выход",
    },
    "console_running": {
        "en": "[Running] Listening... Speak or play game audio.",
        "ru": "[Работает] Слушаю... Говорите или включите аудио игры.",
    },
    "console_shutdown": {
        "en": "[Shutdown] Stopping...",
        "ru": "[Завершение] Остановка...",
    },
    "console_shutdown_done": {
        "en": "[Shutdown] Done.",
        "ru": "[Завершение] Готово.",
    },
    "console_ctrlc": {
        "en": "[Ctrl+C] Shutting down...",
        "ru": "[Ctrl+C] Завершение работы...",
    },
    "console_fatal": {
        "en": "FATAL ERROR \u2014 the program crashed",
        "ru": "КРИТИЧЕСКАЯ ОШИБКА \u2014 программа упала",
    },
    "console_press_enter": {
        "en": "Press Enter to close this window...",
        "ru": "Нажмите Enter чтобы закрыть окно...",
    },
}

# ── Current language (set once at startup from settings) ────────────
_current_lang: str = "en"


def set_language(lang_code: str) -> None:
    """Set the UI language. 'en' or 'ru'."""
    global _current_lang
    _current_lang = lang_code


def t(key: str, lang: str | None = None) -> str:
    """Get translated string by key. Falls back to English."""
    lang = lang or _current_lang
    entry = _STRINGS.get(key)
    if entry is None:
        return key  # missing key — return the key itself for debugging
    return entry.get(lang, entry.get("en", key))
