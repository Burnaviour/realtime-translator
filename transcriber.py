import torch
from faster_whisper import WhisperModel


class Transcriber:
    """Speech-to-text using faster-whisper with automatic CUDA/CPU detection."""

    def __init__(self, model_size="small"):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.compute_type = "float16" if self.device == "cuda" else "int8"

        print(f"[Whisper] Loading '{model_size}' on {self.device} ({self.compute_type})...")
        try:
            self.model = WhisperModel(
                model_size, device=self.device, compute_type=self.compute_type
            )
            print("[Whisper] Model loaded successfully.")
        except Exception as e:
            print(f"[Whisper] ERROR loading model: {e}")
            print("[Whisper] Falling back to CPU with int8...")
            try:
                self.model = WhisperModel(model_size, device="cpu", compute_type="int8")
                print("[Whisper] CPU fallback loaded.")
            except Exception as e2:
                print(f"[Whisper] FATAL: Could not load model: {e2}")
                self.model = None

    def transcribe_text(self, audio_data, language=None):
        """
        Transcribe audio (numpy float32 array at 16kHz) to text.
        
        Args:
            audio_data: numpy array of audio samples
            language: language hint ('ru', 'en', etc.) for better accuracy
        
        Returns:
            Transcribed text string, or empty string on failure.
        """
        if self.model is None:
            return ""

        try:
            kwargs = {
                "beam_size": 5,
                "best_of": 3,
                "patience": 1.5,
                "temperature": [0.0, 0.2, 0.4, 0.6],
                "compression_ratio_threshold": 2.4,
                "condition_on_previous_text": True,
                "vad_filter": True,
                "vad_parameters": {"min_silence_duration_ms": 400},
            }
            if language:
                kwargs["language"] = language
                # Prompt hints improve accuracy for accented speech
                if language == "en":
                    kwargs["initial_prompt"] = "This is a conversation in English."
                elif language == "ru":
                    kwargs["initial_prompt"] = "Это разговор на русском языке."

            segments, info = self.model.transcribe(audio_data, **kwargs)
            text = " ".join(seg.text for seg in segments).strip()
            return text
        except Exception as e:
            print(f"[Whisper] Transcription error: {e}")
            return ""

    def transcribe_with_lang(self, audio_data, language=None):
        """
        Transcribe audio and also return the detected language.
        
        Args:
            audio_data: numpy array of audio samples
            language: language hint ('ru', 'en', etc.) — NOT forced when
                      we want auto-detection
        
        Returns:
            (text, detected_language, language_probability) tuple.
            detected_language is a 2-letter code like 'en', 'ru'.
        """
        if self.model is None:
            return "", "", 0.0

        try:
            kwargs = {
                "beam_size": 5,
                "best_of": 3,
                "patience": 1.5,
                "temperature": [0.0, 0.2, 0.4, 0.6],
                "compression_ratio_threshold": 2.4,
                "condition_on_previous_text": True,
                "vad_filter": True,
                "vad_parameters": {"min_silence_duration_ms": 400},
            }
            # Do NOT force language — let Whisper auto-detect so we can filter
            if language:
                if language == "en":
                    kwargs["initial_prompt"] = "This is a conversation in English."
                elif language == "ru":
                    kwargs["initial_prompt"] = "Это разговор на русском языке."

            segments, info = self.model.transcribe(audio_data, **kwargs)
            text = " ".join(seg.text for seg in segments).strip()
            return text, info.language, info.language_probability
        except Exception as e:
            print(f"[Whisper] Transcription error: {e}")
            return "", "", 0.0
