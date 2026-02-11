import torch
from faster_whisper import WhisperModel
from logger_config import get_logger

logger = get_logger("Whisper")


class Transcriber:
    """Speech-to-text using faster-whisper with automatic CUDA/CPU detection."""

    def __init__(self, model_size="small", clean_audio_mode=False):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.compute_type = "float16" if self.device == "cuda" else "int8"
        self.clean_audio_mode = clean_audio_mode

        logger.info("Loading '%s' on %s (%s)...", model_size, self.device, self.compute_type)
        try:
            self.model = WhisperModel(
                model_size, device=self.device, compute_type=self.compute_type
            )
            logger.info("Model loaded successfully.")
        except Exception as e:
            logger.error("ERROR loading model: %s", e)
            logger.warning("Falling back to CPU with int8...")
            try:
                self.model = WhisperModel(model_size, device="cpu", compute_type="int8")
                logger.info("CPU fallback loaded.")
            except Exception as e2:
                logger.critical("FATAL: Could not load model: %s", e2)
                self.model = None

    def transcribe_text(self, audio_data, language=None):
        """
        Transcribe audio (numpy float32 array at 16kHz) to text.
        
        Args:
            audio_data: numpy array of audio samples
            language: forced language code ('ru', 'en', etc.) — Whisper will
                      only look for this language, preventing misdetection.
        
        Returns:
            Transcribed text string, or empty string on failure.
        """
        if self.model is None:
            return ""

        try:
            # Lower temp + no cross-segment conditioning reduces hallucinations
            # on noisy / gaming audio.
            kwargs = {
                "beam_size": 3,
                "best_of": 1,
                "patience": 1.0,
                "temperature": [0.0, 0.2],
                "compression_ratio_threshold": 2.0,
                # Drop low-confidence / non-speech segments early
                "log_prob_threshold": -0.8,
                "no_speech_threshold": 0.75,
                # Reduce repetitive gibberish
                "repetition_penalty": 1.15,
                "no_repeat_ngram_size": 3,
                "condition_on_previous_text": False,
                "vad_filter": True,
            }
            
            # Clean audio mode: gentler VAD to respect natural pauses
            if self.clean_audio_mode:
                kwargs["vad_parameters"] = {
                    "min_silence_duration_ms": 1200,  # Longer gap for TTS/clean audio
                    "speech_pad_ms": 400,
                }
            else:
                kwargs["vad_parameters"] = {"min_silence_duration_ms": 400}
            if language:
                kwargs["language"] = language
                # Provide an initial prompt that anchors the language context.
                # This dramatically reduces Whisper misdetecting the language
                # on short or noisy audio clips.
                if language == "en":
                    kwargs["initial_prompt"] = "This is a conversation in English."
                elif language == "ru":
                    kwargs["initial_prompt"] = "Это разговор на русском языке."

            segments, info = self.model.transcribe(audio_data, **kwargs)
            text = " ".join(seg.text for seg in segments).strip()
            return text
        except Exception as e:
            logger.error("Transcription error: %s", e)
            return ""

    def transcribe_with_lang(self, audio_data, language=None):
        """
        Transcribe audio and also return the detected language.
        
        Args:
            audio_data: numpy array of audio samples
            language: expected language hint ('ru', 'en', etc.) — NOT forced,
                      but used as initial_prompt to nudge detection.
        
        Returns:
            (text, detected_language, language_probability) tuple.
            detected_language is a 2-letter code like 'en', 'ru'.
        """
        if self.model is None:
            return "", "", 0.0

        try:
            kwargs = {
                "beam_size": 3,
                "best_of": 1,
                "patience": 1.0,
                "temperature": [0.0, 0.2],
                "compression_ratio_threshold": 2.0,
                "log_prob_threshold": -0.8,
                "no_speech_threshold": 0.75,
                "repetition_penalty": 1.15,
                "no_repeat_ngram_size": 3,
                "condition_on_previous_text": False,
                "vad_filter": True,
            }
            
            # Clean audio mode: gentler VAD
            if self.clean_audio_mode:
                kwargs["vad_parameters"] = {
                    "min_silence_duration_ms": 1200,
                    "speech_pad_ms": 400,
                }
            else:
                kwargs["vad_parameters"] = {"min_silence_duration_ms": 400}
            
            # Do NOT force language — let Whisper auto-detect so we can filter.
            # But provide a gentle hint via initial_prompt.
            if language == "ru":
                kwargs["initial_prompt"] = "Это разговор на русском языке."
            elif language == "en":
                kwargs["initial_prompt"] = "This is a conversation in English."

            segments, info = self.model.transcribe(audio_data, **kwargs)
            text = " ".join(seg.text for seg in segments).strip()
            return text, info.language, info.language_probability
        except Exception as e:
            logger.error("Transcription error: %s", e)
            return "", "", 0.0
