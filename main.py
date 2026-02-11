import threading
import time
import queue
import numpy as np
from collections import Counter

from audio_capture import (
    SystemAudioLoopback, MicAudioCapture,
    compute_rms, is_likely_speech,
)
from transcriber import Transcriber
from translator import Translator
from overlay import OverlayWindow
from glossary import apply_gaming_glossary, log_translation
from locales import t
from transliterate import transliterate_russian, has_cyrillic
from logger_config import get_logger

logger = get_logger("App")

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


def _is_repetitive_translation(text: str) -> bool:
    """
    Detect when a translation has excessive word-level repetition.
    E.g., "Whoa" repeated 50+ times, "weight" repeated 70 times.
    """
    if not text or len(text) < 40:
        return False

    words = text.lower().split()
    if len(words) < 6:  # Changed from 10 to 6 to catch shorter spam
        return False

    # Count word frequency (strip common punctuation)

    cleaned_words = [w.strip('.,!?;:"\'-') for w in words]
    word_counts = Counter(cleaned_words)
    # If ANY single word appears more than 6 times, it's likely spam
    for word, count in word_counts.items():
        if len(word) >= 2 and count >= 6:
            return True

    # Also check if top 2 words make up >60% of the text
    total = len(words)
    top_two = word_counts.most_common(2)
    if len(top_two) >= 2:
        top_two_count = top_two[0][1] + top_two[1][1]
        if top_two_count / total > 0.6:
            return True

    return False


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

    # Repeated-character spam: "Ааааааааа...", "ههههه...", etc.
    # (Common when the input is noise/music but the model tries to form text.)
    if len(stripped) >= 20:  # Lowered from 30 to catch shorter spam
        # Ignore spaces for this check
        compact = "".join(ch for ch in stripped if not ch.isspace())
        if compact:
            counts = Counter(compact)
            most_common = counts.most_common(1)[0][1]
            # More aggressive: 75% same character (was 85%)
            if most_common / len(compact) >= 0.75:
                return True
            # Also catch very low character variety on long strings
            if len(compact) >= 80 and len(counts) <= 3:
                return True

    # Subtitle/credit boilerplate patterns that show up in videos/streams
    # (Not useful for voice chat translation.)
    if (
        "редактор субтитров" in stripped
        or "корректор" in stripped
        or "subtitles" in stripped
        or "subtitle" in stripped
        or "sync corrected" in stripped
        or "@elder_man" in stripped
        or "elderman" in stripped
        or "закомолдина" in stripped
        or "голубкина" in stripped
    ):
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
        # ── GPU memory optimization ─────────────────────────────────
        import torch
        if torch.cuda.is_available():
            # Free fragmented GPU memory before loading models
            torch.cuda.empty_cache()
            # Use memory-efficient CUDA allocator to reduce fragmentation
            import os
            os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

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

        logger.info("=" * 60)
        logger.info("  %s", t('console_title'))
        logger.info("  %s: %s", t('console_my_lang'), src.upper())
        logger.info("  %s  |  %s", game_label, mic_label)
        logger.info("=" * 60)
        logger.info(t("console_loading"))

        # Audio sources
        clean_mode = self.overlay.cfg.get("clean_audio_mode")
        speech_filter = self.overlay.cfg.get("speech_filter_enabled") and not clean_mode
        self.system_audio = SystemAudioLoopback(
            sample_rate=SAMPLE_RATE,
            apply_speech_filter=speech_filter,
        )
        self.mic_audio = MicAudioCapture(sample_rate=SAMPLE_RATE)

        # Speech recognition (model from settings)
        whisper_model = self.overlay.cfg.get("whisper_model")
        logger.info("%s: %s", t('console_whisper_model'), whisper_model)
        self.transcriber = Transcriber(
            model_size=whisper_model,
            clean_audio_mode=clean_mode,
        )

        # Translation models (direction based on source_language setting)
        trans_model = self.overlay.cfg.get("translation_model")
        logger.info("Translation model: %s", trans_model)
        self.translator_game = Translator(
            source_lang=game_src, target_lang=game_tgt,
            translation_model=trans_model,
        )
        self.translator_mic = Translator(
            source_lang=mic_src, target_lang=mic_tgt,
            translation_model=trans_model,
        )

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

        logger.info(t("console_ready"))
        logger.info(t("console_keys"))

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

        Game audio pipeline has extra filtering:
          - Higher energy threshold (game sounds are louder but non-speech)
          - RMS-based detection (speech has sustained energy)
          - Zero-crossing rate check (speech vs. noise/music)
          - Configurable noise gate from settings
        """
        buffer = np.array([], dtype=np.float32)
        min_samples = int(SAMPLE_RATE * 0.8)   # 0.8s — allow short phrases like "ok"
        max_samples = int(SAMPLE_RATE * 20)

        is_game = self._is_game_source(label)
        bandpass_on = is_game and self._settings.get("speech_filter_enabled")

        # Game audio uses a noise gate from settings.
        # When band-pass filter is active, use LOWER thresholds because
        # the filter already strips non-speech energy.
        if is_game:
            noise_gate = self._settings.get("game_noise_gate")
            if bandpass_on:
                # Band-pass reduces overall RMS — use gentler thresholds
                silence_threshold = max(0.003, noise_gate * 0.5)
                rms_threshold = max(0.002, noise_gate * 0.4)
            else:
                silence_threshold = max(0.005, noise_gate)
                rms_threshold = max(0.004, noise_gate * 0.8)
        else:
            silence_threshold = 0.005
            rms_threshold = 0.003

        consecutive_silent = 0
        silence_trigger = 10

        # Streaming preview state
        last_preview_time = time.time()
        preview_min_samples = int(SAMPLE_RATE * 1.0)  # Need >=1s for preview
        # Limit concurrent preview threads to reduce CPU load
        preview_in_progress = threading.Event()

        while self.running:
            try:
                chunk = audio_source.audio_queue.get(timeout=0.3)
            except queue.Empty:
                if len(buffer) >= min_samples:
                    rms = compute_rms(buffer)
                    if rms > rms_threshold:
                        # For game audio WITHOUT bandpass, check speech characteristics
                        if is_game and not bandpass_on and not is_likely_speech(
                            buffer, SAMPLE_RATE, rms_threshold,
                            bandpass_applied=False,
                        ):
                            logger.debug("[%s] Skipped — audio doesn't look like speech (RMS=%.4f)",
                                         label, rms)
                            buffer = np.array([], dtype=np.float32)
                            consecutive_silent = 0
                            last_preview_time = time.time()
                            continue
                        self._transcribe_and_translate(
                            buffer, language, translator, update_func, label
                        )
                    buffer = np.array([], dtype=np.float32)
                    consecutive_silent = 0
                    last_preview_time = time.time()
                continue

            buffer = np.concatenate((buffer, chunk))

            # Track silence using RMS (more robust than peak)
            chunk_rms = compute_rms(chunk)
            if chunk_rms < silence_threshold:
                consecutive_silent += 1
            else:
                consecutive_silent = 0

            # ── Streaming preview ───────────────────────────────────
            # Only run one preview at a time to reduce CPU load
            if (self.overlay.is_streaming_enabled()
                    and len(buffer) >= preview_min_samples
                    and consecutive_silent < silence_trigger
                    and not preview_in_progress.is_set()):
                now = time.time()
                interval_s = self.overlay.streaming_interval_ms() / 1000.0
                if now - last_preview_time >= interval_s:
                    last_preview_time = now
                    preview_in_progress.set()
                    threading.Thread(
                        target=self._preview_transcribe,
                        args=(buffer.copy(), language, translator,
                              preview_func, label, preview_in_progress),
                        daemon=True,
                    ).start()

            # ── Full processing on silence / max length ─────────────
            should_process = False
            if len(buffer) >= max_samples:
                should_process = True
            elif len(buffer) >= min_samples and consecutive_silent >= silence_trigger:
                should_process = True

            if should_process:
                rms = compute_rms(buffer)
                if rms > rms_threshold:
                    # For game audio WITHOUT bandpass, verify it looks like speech
                    if is_game and not bandpass_on and not is_likely_speech(
                        buffer, SAMPLE_RATE, rms_threshold,
                        bandpass_applied=False,
                    ):
                        logger.debug("[%s] Skipped — not speech (RMS=%.4f)", label, rms)
                        buffer = np.array([], dtype=np.float32)
                        consecutive_silent = 0
                        last_preview_time = time.time()
                        continue

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

    def _preview_transcribe(self, audio, language, translator, preview_func,
                            label, done_event=None):
        """Streaming preview: transcribe + translate so the user sees their language."""
        try:
            # For game audio with filtering ON, use language detection
            if self._is_game_source(label) and self._should_filter_language():
                text, detected_lang, prob = self.transcriber.transcribe_with_lang(
                    audio, language=language
                )
                # Clean audio mode: be more lenient (skip only at >90%)
                # Normal mode: skip at >75%
                clean_mode = self._settings.get("clean_audio_mode")
                threshold = 0.9 if clean_mode else 0.75
                
                if detected_lang != language and prob > threshold:
                    return  # silently skip — confidently wrong language
            else:
                text = self.transcriber.transcribe_text(audio, language=language)

            if text and not is_hallucination(text):
                translated = translator.translate(text)
                if translated and translated.strip():
                    # Transliterate Cyrillic → Latin for mic output
                    if (not self._is_game_source(label)
                            and self._settings.get("transliterate_mic")
                            and has_cyrillic(translated)):
                        translated = transliterate_russian(translated)
                    preview_func(translated)
        except Exception:
            pass
        finally:
            if done_event is not None:
                done_event.clear()

    def _transcribe_and_translate(self, audio, language, translator, update_func, label):
        """Transcribe an audio segment and translate the result."""
        try:
            t0 = time.time()
            clean_mode = self._settings.get("clean_audio_mode")
            threshold = 0.9 if clean_mode else 0.75
            
            # For game audio with filtering ON, detect language and skip mismatches
            if self._is_game_source(label) and self._should_filter_language():
                text, detected_lang, prob = self.transcriber.transcribe_with_lang(
                    audio, language=language
                )
                
                if detected_lang != language and prob > threshold:
                    logger.debug("[%s] Skipped — detected '%s' (prob %.0f%%), expected '%s'",
                                 label, detected_lang, prob * 100, language)
                    return
                elif detected_lang != language:
                    # Low confidence mismatch — re-transcribe with forced language
                    # since the detection is unreliable
                    logger.debug("[%s] Low-confidence '%s' (%.0f%%) — forcing '%s' transcription",
                                 label, detected_lang, prob * 100, language)
                    text = self.transcriber.transcribe_text(audio, language=language)
            else:
                text = self.transcriber.transcribe_text(audio, language=language)

            if not text or is_hallucination(text):
                return

            t1 = time.time()
            translated = translator.translate(text)
            t2 = time.time()
            
            if translated and translated.strip():
                # Post-translation filter: catch garbage/repeated output
                if is_hallucination(translated) or _is_repetitive_translation(translated):
                    logger.debug('[%s] Blocked repetitive/garbage translation: "%s"', label, text)
                    return
                
                # Apply Gaming Glossary / Context Fixes
                raw_translation = translated
                translated = apply_gaming_glossary(translated)
                
                # Log translation for glossary review (only if changed)
                if raw_translation != translated:
                    # Determine source and target languages based on translator
                    src_lang = translator.source_lang
                    tgt_lang = translator.target_lang
                    log_translation(text, raw_translation, translated, src_lang, tgt_lang)
                
                # Transliterate Cyrillic → Latin for mic output
                if (not self._is_game_source(label)
                        and self._settings.get("transliterate_mic")
                        and has_cyrillic(translated)):
                    translated = transliterate_russian(translated)

                latency_transcribe = (t1 - t0) * 1000
                latency_translate = (t2 - t1) * 1000
                total_latency = (t2 - t0) * 1000
                
                logger.info('[%s] "%s" -> "%s" [Tr: %.0fms | Tl: %.0fms | Total: %.0fms]',
                            label, text, translated,
                            latency_transcribe, latency_translate, total_latency)
                update_func(translated)
        except Exception as e:
            logger.error("[%s] Processing error: %s", label, e)

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

        logger.info(t("console_running"))

        # Ctrl+C handler — tkinter on Windows doesn't propagate KeyboardInterrupt
        # so we poll for it via a periodic callback
        import signal

        def _signal_handler(sig, frame):
            logger.info(t('console_ctrlc'))
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
        logger.info(t('console_shutdown'))
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
        logger.info(t("console_shutdown_done"))
        # Force-exit to avoid Fortran / native-library cleanup errors
        import os
        os._exit(0)

    def _restart(self):
        """Save settings, stop everything, and re-launch the process."""
        if not self.running:
            return
        self.running = False
        logger.info(t('console_restarting'))
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
        logger.critical(t('console_fatal'))
        traceback.print_exc()
        input(t("console_press_enter"))
