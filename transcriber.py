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
                "vad_filter": True,
                "vad_parameters": {"min_silence_duration_ms": 500},
            }
            if language:
                kwargs["language"] = language

            segments, info = self.model.transcribe(audio_data, **kwargs)
            text = " ".join(seg.text for seg in segments).strip()
            return text
        except Exception as e:
            print(f"[Whisper] Transcription error: {e}")
            return ""
