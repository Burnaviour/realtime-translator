import threading
import time
import queue
import numpy as np

from audio_capture import SystemAudioLoopback, MicAudioCapture
from transcriber import Transcriber
from translator import Translator
from overlay import OverlayWindow

SAMPLE_RATE = 16000

# Common Whisper hallucinations on silence / noise (EN + RU)
HALLUCINATIONS = frozenset({
    # English
    "you", "thank you", "thanks", "thanks for watching",
    "subtitles", "subtitles by", "subs by", "mbc",
    "copyright", "allô", "allo", "bye", "goodbye",
    "the end", "thank you for watching",
    "please subscribe", "like and subscribe",
    "so", "i'm sorry", "oh", "ah", "hmm", "huh",
    "okay", "ok", "yes", "no", "yeah", "right",
    "sync corrected", "elderman", "elder_man",
    "www", "http", "com",
    # Russian hallucinations
    "субтитры", "продолжение следует", "спасибо",
    "спасибо за просмотр", "подписывайтесь",
    "до свидания", "конец", "редактор",
    "переводчик", "субтитры сделал",
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

    if len(stripped) < 3:
        return True

    # Direct match
    if stripped in HALLUCINATIONS:
        return True

    # Any hallucination keyword appears as a substring
    for h in HALLUCINATIONS:
        if h in stripped:
            return True

    # Repetition detection: "word word word word" or "фраза фраза фраза"
    words = stripped.split()
    if len(words) >= 3:
        unique = set(words)
        # If 80%+ of words are the same word repeated, it's hallucination
        if len(unique) <= max(1, len(words) * 0.2):
            return True

    # Regex-based repetition (catches "субтитры субтитры субтитры")
    if _REPEAT_PATTERN.match(stripped):
        return True

    # Very short after cleaning common filler
    if len(stripped.replace(" ", "")) < 4:
        return True

    return False


class TranslationApp:
    """
    Real-time bi-directional translation for gaming voice chat.
    
    Pipeline per audio source:
        Audio capture -> Buffer with VAD -> Whisper transcription -> MarianMT translation -> Overlay
    
    Game audio (system loopback): Russian -> English
    Microphone audio:             English -> Russian
    """

    def __init__(self):
        print("=" * 60)
        print("  Real-time Voice Translator")
        print("  Game (Russian -> English)  |  Mic (English -> Russian)")
        print("=" * 60)
        print()
        print("[Init] Loading AI models (first run downloads ~1-2 GB)...")
        print()

        # Audio sources
        self.system_audio = SystemAudioLoopback(sample_rate=SAMPLE_RATE)
        self.mic_audio = MicAudioCapture(sample_rate=SAMPLE_RATE)

        # Speech recognition (shared model)
        self.transcriber = Transcriber(model_size="small")

        # Translation models
        self.translator_ru_en = Translator(source_lang="ru", target_lang="en")
        self.translator_en_ru = Translator(source_lang="en", target_lang="ru")

        # Overlay
        self.overlay = OverlayWindow()

        self.running = True

        print()
        print("[Ready] All models loaded.")
        print("[Keys]  F8 = Lock/Unlock  |  F9 = Show/Hide  |  F10 = Settings  |  Ctrl+C = Quit")
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
        min_samples = int(SAMPLE_RATE * 2)
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
                        args=(buffer.copy(), language, preview_func, label),
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

    def _preview_transcribe(self, audio, language, preview_func, label):
        """Quick transcription for streaming preview (no translation, just raw text)."""
        try:
            text = self.transcriber.transcribe_text(audio, language=language)
            if text and not is_hallucination(text):
                preview_func(text)
        except Exception:
            pass

    def _transcribe_and_translate(self, audio, language, translator, update_func, label):
        """Transcribe an audio segment and translate the result."""
        try:
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
                self.system_audio, "ru", self.translator_ru_en,
                self.overlay.update_game_text,
                self.overlay.update_game_preview,
                "Game RU\u2192EN",
            ),
            daemon=True,
        )
        mic_thread = threading.Thread(
            target=self._audio_processor,
            args=(
                self.mic_audio, "en", self.translator_en_ru,
                self.overlay.update_mic_text,
                self.overlay.update_mic_preview,
                "Mic EN\u2192RU",
            ),
            daemon=True,
        )

        game_thread.start()
        mic_thread.start()

        print("[Running] Listening... Speak or play game audio.")
        print()

        # Overlay runs on the main thread (tkinter requirement)
        try:
            self.overlay.start()
        except KeyboardInterrupt:
            pass
        finally:
            self._shutdown()

    def _shutdown(self):
        print("\n[Shutdown] Stopping...")
        self.running = False
        self.system_audio.stop()
        self.mic_audio.stop()
        self.overlay.stop()
        print("[Shutdown] Done.")


if __name__ == "__main__":
    app = TranslationApp()
    app.run()
