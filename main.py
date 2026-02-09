import threading
import time
import queue
import numpy as np

from audio_capture import SystemAudioLoopback, MicAudioCapture
from transcriber import Transcriber
from translator import Translator
from overlay import OverlayWindow
from locales import t

SAMPLE_RATE = 16000

# Common Whisper hallucinations on silence / noise (EN + RU)
# NOTE: Only include phrases that are NEVER legitimate speech.
#       Do NOT add common words like "ok", "yes", "bye" — they are real speech.
HALLUCINATIONS = frozenset({
    # English — subtitle / broadcast artifacts only
    "thank you for watching", "thanks for watching",
    "subtitles", "subtitles by", "subs by", "mbc",
    "copyright", "please subscribe", "like and subscribe",
    "sync corrected", "elderman", "elder_man",
    "the end", "www", "http",
    # Whisper prompt leak hallucinations
    "this is a conversation in english",
    "this is a conversation in english. this is a conversation in english",
    "это разговор на русском языке",
    # Russian — subtitle / broadcast artifacts only
    "субтитры", "продолжение следует",
    "спасибо за просмотр", "подписывайтесь",
    "редактор", "переводчик", "субтитры сделал",
})

# Patterns that indicate repetitive hallucination (compiled once)
import re
_REPEAT_PATTERN = re.compile(r"^(.{2,15})\s*(\1[\s,.!?]*){2,}$", re.IGNORECASE)


def is_hallucination(text: str) -> bool:
    """Return True if the text is likely a Whisper hallucination."""
    if not text:
        return True

    clean = text.strip().lower()
    # Strip trailing/leading punctuation for matching
    stripped = clean.strip(".!?,;:…\u2026 \t\n\"'")

    # Only reject truly empty output
    if len(stripped) == 0:
        return True

    # Direct exact match against known artifacts
    if stripped in HALLUCINATIONS:
        return True

    # Repetition detection: "word word word word" or "фраза фраза фраза"
    words = stripped.split()
    if len(words) >= 4:
        unique = set(words)
        # If 80%+ of words are the same word repeated, it's hallucination
        if len(unique) <= max(1, len(words) * 0.2):
            return True

    # Regex-based repetition (catches "субтитры субтитры субтитры")
    if _REPEAT_PATTERN.match(stripped):
        return True

    return False


class TranslationApp:
    """
    Real-time bi-directional translation for gaming voice chat.
    
    Pipeline per audio source:
        Audio capture -> Buffer with VAD -> Whisper transcription -> MarianMT translation -> Overlay
    
    Language direction is configurable via source_language setting:
        source_language = "english": Game(RU→EN), Mic(EN→RU)
        source_language = "russian": Game(EN→RU), Mic(RU→EN)
    """

    def __init__(self):
        # Overlay first (reads settings)
        self.overlay = OverlayWindow()
        src = self.overlay.cfg.get("source_language")  # "english" or "russian"

        if src == "russian":
            game_src, game_tgt = "en", "ru"
            mic_src, mic_tgt = "ru", "en"
            game_label = "Game EN->RU"
            mic_label = "Mic RU->EN"
            game_lang_hint = "en"
            mic_lang_hint = "ru"
        else:
            game_src, game_tgt = "ru", "en"
            mic_src, mic_tgt = "en", "ru"
            game_label = "Game RU->EN"
            mic_label = "Mic EN->RU"
            game_lang_hint = "ru"
            mic_lang_hint = "en"

        print("=" * 60)
        print(f"  {t('console_title')}")
        print(f"  {t('console_my_lang')}: {src.upper()}")
        print(f"  {game_label}  |  {mic_label}")
        print("=" * 60)
        print()
        print(t("console_loading"))
        print()

        # Audio sources
        self.system_audio = SystemAudioLoopback(sample_rate=SAMPLE_RATE)
        self.mic_audio = MicAudioCapture(sample_rate=SAMPLE_RATE)

        # Speech recognition (model from settings)
        whisper_model = self.overlay.cfg.get("whisper_model")
        print(f"{t('console_whisper_model')}: {whisper_model}")
        self.transcriber = Transcriber(model_size=whisper_model)

        # Translation models (direction based on source_language setting)
        self.translator_game = Translator(source_lang=game_src, target_lang=game_tgt)
        self.translator_mic = Translator(source_lang=mic_src, target_lang=mic_tgt)

        self.game_lang_hint = game_lang_hint
        self.mic_lang_hint = mic_lang_hint
        self.game_label = game_label
        self.mic_label = mic_label

        # Language filtering — read live from settings so the toggle
        # takes effect without restarting
        self._settings = self.overlay.cfg

        # Overlay
        # (already created above)

        self.running = True

        print()
        print(t("console_ready"))
        print(t("console_keys"))
        print()

    def _find_silence_split(self, buffer, threshold, chunk_size=1024):
        """
        When we must force-split a long buffer, find the last silent region
        to split at (so we don't cut mid-word). Searches backwards from the end.
        Returns the split index, or len(buffer) if no silence found.
        """
        search_region = min(len(buffer), SAMPLE_RATE * 4)  # Search last 4 seconds
        start = len(buffer) - search_region
        best_split = len(buffer)

        # Walk backwards in chunk_size steps looking for silence
        for i in range(len(buffer) - chunk_size, start, -chunk_size):
            segment = buffer[i : i + chunk_size]
            if np.max(np.abs(segment)) < threshold:
                best_split = i + chunk_size  # Split right after the silence
                break

        return best_split

    def _audio_processor(self, audio_source, language, translator,
                         update_func, preview_func, label):
        """
        Background thread with streaming preview support.

        While speech is being buffered, periodically transcribe the buffer-so-far
        and push a dimmed "preview" to the overlay.  When silence boundary is
        detected, do the full transcription + translation as the "final" result.
        """
        buffer = np.array([], dtype=np.float32)
        min_samples = int(SAMPLE_RATE * 0.8)   # 0.8s — allow short phrases like "ok"
        max_samples = int(SAMPLE_RATE * 20)
        silence_threshold = 0.005
        consecutive_silent = 0
        silence_trigger = 10

        # Streaming preview state
        last_preview_time = time.time()
        preview_min_samples = int(SAMPLE_RATE * 1.0)  # Need >=1s for preview

        while self.running:
            try:
                chunk = audio_source.audio_queue.get(timeout=0.3)
            except queue.Empty:
                if len(buffer) >= min_samples:
                    energy = np.max(np.abs(buffer))
                    if energy > silence_threshold:
                        self._transcribe_and_translate(
                            buffer, language, translator, update_func, label
                        )
                    buffer = np.array([], dtype=np.float32)
                    consecutive_silent = 0
                    last_preview_time = time.time()
                continue

            buffer = np.concatenate((buffer, chunk))

            # Track silence
            chunk_energy = np.max(np.abs(chunk))
            if chunk_energy < silence_threshold:
                consecutive_silent += 1
            else:
                consecutive_silent = 0

            # ── Streaming preview ───────────────────────────────────
            if (self.overlay.is_streaming_enabled()
                    and len(buffer) >= preview_min_samples
                    and consecutive_silent < silence_trigger):
                now = time.time()
                interval_s = self.overlay.streaming_interval_ms() / 1000.0
                if now - last_preview_time >= interval_s:
                    last_preview_time = now
                    threading.Thread(
                        target=self._preview_transcribe,
                        args=(buffer.copy(), language, translator,
                              preview_func, label),
                        daemon=True,
                    ).start()

            # ── Full processing on silence / max length ─────────────
            should_process = False
            if len(buffer) >= max_samples:
                should_process = True
            elif len(buffer) >= min_samples and consecutive_silent >= silence_trigger:
                should_process = True

            if should_process:
                energy = np.max(np.abs(buffer))
                if energy > silence_threshold:
                    if len(buffer) >= max_samples:
                        split_at = self._find_silence_split(buffer, silence_threshold)
                        process_buf = buffer[:split_at]
                        buffer = buffer[split_at:]
                    else:
                        process_buf = buffer
                        buffer = np.array([], dtype=np.float32)

                    self._transcribe_and_translate(
                        process_buf, language, translator, update_func, label
                    )
                else:
                    buffer = np.array([], dtype=np.float32)
                consecutive_silent = 0
                last_preview_time = time.time()

            # Safety: prevent unbounded memory growth
            if len(buffer) > SAMPLE_RATE * 30:
                buffer = buffer[-max_samples:]

    def _is_game_source(self, label):
        """Return True if this label belongs to the game audio pipeline."""
        return "Game" in label

    def _should_filter_language(self):
        """Check if language filtering is enabled in settings."""
        return self._settings.get("filter_game_language")

    def _preview_transcribe(self, audio, language, translator, preview_func, label):
        """Streaming preview: transcribe + translate so the user sees their language."""
        try:
            # For game audio with filtering ON, use language detection
            if self._is_game_source(label) and self._should_filter_language():
                text, detected_lang, prob = self.transcriber.transcribe_with_lang(
                    audio, language=language
                )
                if detected_lang != language:
                    return  # silently skip — wrong language
            else:
                text = self.transcriber.transcribe_text(audio, language=language)

            if text and not is_hallucination(text):
                translated = translator.translate(text)
                if translated and translated.strip():
                    preview_func(translated)
        except Exception:
            pass

    def _transcribe_and_translate(self, audio, language, translator, update_func, label):
        """Transcribe an audio segment and translate the result."""
        try:
            # For game audio with filtering ON, detect language and skip mismatches
            if self._is_game_source(label) and self._should_filter_language():
                text, detected_lang, prob = self.transcriber.transcribe_with_lang(
                    audio, language=language
                )
                if detected_lang != language:
                    print(f"[{label}] Skipped — detected '{detected_lang}' "
                          f"(prob {prob:.0%}), expected '{language}'")
                    return
            else:
                text = self.transcriber.transcribe_text(audio, language=language)

            if not text or is_hallucination(text):
                return

            translated = translator.translate(text)
            if translated and translated.strip():
                print(f'[{label}] "{text}" -> "{translated}"')
                update_func(translated)
        except Exception as e:
            print(f"[{label}] Processing error: {e}")

    def run(self):
        """Start all components and run the app."""
        # Start audio capture threads
        self.system_audio.start()
        self.mic_audio.start()

        # Start audio processing threads
        game_thread = threading.Thread(
            target=self._audio_processor,
            args=(
                self.system_audio, self.game_lang_hint, self.translator_game,
                self.overlay.update_game_text,
                self.overlay.update_game_preview,
                self.game_label,
            ),
            daemon=True,
        )
        mic_thread = threading.Thread(
            target=self._audio_processor,
            args=(
                self.mic_audio, self.mic_lang_hint, self.translator_mic,
                self.overlay.update_mic_text,
                self.overlay.update_mic_preview,
                self.mic_label,
            ),
            daemon=True,
        )

        game_thread.start()
        mic_thread.start()

        print(t("console_running"))
        print()

        # Ctrl+C handler — tkinter on Windows doesn't propagate KeyboardInterrupt
        # so we poll for it via a periodic callback
        import signal

        def _signal_handler(sig, frame):
            print(f"\n{t('console_ctrlc')}")
            self._shutdown()

        signal.signal(signal.SIGINT, _signal_handler)

        # Wire close / restart buttons on overlay
        self.overlay.set_on_close(self._shutdown)
        self.overlay.set_on_restart(self._restart)

        # Periodic check keeps the signal handler responsive
        def _keepalive():
            if self.running:
                self.overlay.root.after(500, _keepalive)
        self.overlay.root.after(500, _keepalive)

        # Overlay runs on the main thread (tkinter requirement)
        try:
            self.overlay.start()
        except (KeyboardInterrupt, SystemExit):
            pass
        finally:
            self._shutdown()

    def _shutdown(self):
        if not self.running:
            return  # Already shut down
        self.running = False
        print(f"\n{t('console_shutdown')}")
        try:
            self.system_audio.stop()
        except Exception:
            pass
        try:
            self.mic_audio.stop()
        except Exception:
            pass
        try:
            self.overlay.stop()
        except Exception:
            pass
        print(t("console_shutdown_done"))
        # Force-exit to avoid Fortran / native-library cleanup errors
        import os
        os._exit(0)

    def _restart(self):
        """Save settings, stop everything, and re-launch the process."""
        if not self.running:
            return
        self.running = False
        print(f"\n{t('console_restarting')}")
        try:
            self.overlay.stop()
        except Exception:
            pass
        try:
            self.system_audio.stop()
        except Exception:
            pass
        try:
            self.mic_audio.stop()
        except Exception:
            pass
        import sys, os
        # Re-launch the same process
        os.execv(sys.executable, [sys.executable] + sys.argv)


if __name__ == "__main__":
    try:
        app = TranslationApp()
        app.run()
    except Exception as e:
        import traceback
        print("\n" + "=" * 60)
        print(f"  {t('console_fatal')}")
        print("=" * 60)
        traceback.print_exc()
        print("\n" + "=" * 60)
        input(t("console_press_enter"))
