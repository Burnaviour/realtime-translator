import soundcard as sc
import numpy as np
import threading
import queue
import warnings
from logger_config import get_logger

logger = get_logger("Audio")

# Suppress harmless "data discontinuity" warnings from soundcard
# (occurs when CPU is briefly busy with AI models — doesn't affect audio quality)
warnings.filterwarnings("ignore", message=".*data discontinuity.*")

# ── Speech-frequency band-pass filter ──────────────────────────────
# Human speech is concentrated in 300-3000 Hz.  Filtering the system
# loopback to this band removes a huge amount of game sound (explosions,
# music, UI bleeps) before the audio ever reaches Whisper.

try:
    from scipy.signal import butter, sosfilt

    def _make_bandpass(lowcut=300, highcut=3000, fs=16000, order=5):
        """Return second-order-section coefficients for a Butterworth bandpass."""
        nyq = 0.5 * fs
        low = lowcut / nyq
        high = highcut / nyq
        return butter(order, [low, high], btype="band", output="sos")

    _SPEECH_SOS = _make_bandpass()          # pre-computed for 16 kHz
    _HAS_SCIPY = True
except ImportError:
    _HAS_SCIPY = False
    _SPEECH_SOS = None


def speech_bandpass(audio: np.ndarray, sos=None) -> np.ndarray:
    """Apply a 300-3000 Hz bandpass filter to keep only speech frequencies."""
    if not _HAS_SCIPY or sos is None:
        return audio
    return sosfilt(sos, audio).astype(np.float32)


def compute_rms(audio: np.ndarray) -> float:
    """Root-mean-square energy — better than peak for detecting sustained speech."""
    if len(audio) == 0:
        return 0.0
    return float(np.sqrt(np.mean(audio ** 2)))


def is_likely_speech(audio: np.ndarray, sample_rate: int = 16000,
                     rms_threshold: float = 0.008,
                     bandpass_applied: bool = False) -> bool:
    """
    Quick heuristic: is this audio chunk likely human speech?

    When bandpass_applied=True (audio already filtered to 300-3000 Hz),
    only checks RMS energy — the filter itself removes non-speech sounds,
    and ZCR is unreliable on filtered audio.

    When bandpass_applied=False (raw audio), also checks zero-crossing rate.

    Returns True if the audio looks like speech.
    """
    if len(audio) < sample_rate * 0.3:   # need at least 0.3s
        return False

    rms = compute_rms(audio)
    if rms < rms_threshold:
        return False

    # If band-pass filter already applied, RMS check is enough —
    # the filter stripped non-speech frequencies already.
    if bandpass_applied:
        return True

    # For raw (unfiltered) audio, also check zero-crossing rate
    signs = np.sign(audio)
    crossings = np.sum(np.abs(np.diff(signs)) > 0)
    zcr = crossings / len(audio)

    return 0.02 <= zcr <= 0.30


class AudioCapture:
    """Base class for audio capture with threaded recording."""

    def __init__(self, sample_rate=16000, block_size=1024):
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.audio_queue = queue.Queue(maxsize=150)
        self.running = False
        self.thread = None

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)

    def _capture_loop(self):
        raise NotImplementedError


class SystemAudioLoopback(AudioCapture):
    """Captures system/game audio via WASAPI loopback with speech filtering."""

    def __init__(self, sample_rate=16000, block_size=1024, apply_speech_filter=True):
        super().__init__(sample_rate, block_size)
        self.apply_speech_filter = apply_speech_filter
        # Pre-compute filter coefficients for this sample rate
        if _HAS_SCIPY and apply_speech_filter:
            self._sos = _make_bandpass(lowcut=300, highcut=3000, fs=sample_rate, order=5)
        else:
            self._sos = None

    def _capture_loop(self):
        try:
            speaker = sc.default_speaker()
            logger.info("Default speaker: %s", speaker.name)

            # Direct loopback via speaker ID - the reliable way
            loopback = sc.get_microphone(speaker.id, include_loopback=True)
            if loopback is None:
                logger.error("No loopback device found.")
                logger.error("Ensure audio is playing through your default output.")
                return

            logger.info("System loopback: %s", loopback.name)
            if self._sos is not None:
                logger.info("Speech band-pass filter: ENABLED (300-3000 Hz)")
            else:
                logger.info("Speech band-pass filter: DISABLED")

            chunk_count = 0
            with loopback.recorder(samplerate=self.sample_rate) as recorder:
                while self.running:
                    data = recorder.record(numframes=self.block_size)
                    if data.ndim > 1 and data.shape[1] > 1:
                        data = np.mean(data, axis=1)
                    else:
                        data = data.flatten()
                    data = data.astype(np.float32)

                    # Apply speech band-pass filter to strip game sounds
                    if self._sos is not None:
                        data = speech_bandpass(data, self._sos)

                    # Log RMS every 100 chunks for diagnostics
                    chunk_count += 1
                    if chunk_count % 100 == 0:
                        rms = compute_rms(data)
                        logger.debug("Game audio capture: RMS=%.4f", rms)

                    if not self.audio_queue.full():
                        self.audio_queue.put(data)

        except Exception as e:
            logger.error("System loopback error: %s", e)
            logger.info("Tip: Make sure you have an active audio output device.")


class MicAudioCapture(AudioCapture):
    """Captures microphone input."""

    def _capture_loop(self):
        try:
            mic = sc.default_microphone()
            logger.info("Microphone: %s", mic.name)
            with mic.recorder(samplerate=self.sample_rate) as recorder:
                while self.running:
                    data = recorder.record(numframes=self.block_size)
                    if data.ndim > 1 and data.shape[1] > 1:
                        data = np.mean(data, axis=1)
                    else:
                        data = data.flatten()
                    data = data.astype(np.float32)
                    if not self.audio_queue.full():
                        self.audio_queue.put(data)

        except Exception as e:
            logger.error("Microphone error: %s", e)
            logger.info("Tip: Ensure a microphone is connected.")
