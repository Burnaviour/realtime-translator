import soundcard as sc
import numpy as np
import threading
import queue
import warnings

# Suppress harmless "data discontinuity" warnings from soundcard
# (occurs when CPU is briefly busy with AI models — doesn't affect audio quality)
warnings.filterwarnings("ignore", message=".*data discontinuity.*")


class AudioCapture:
    """Base class for audio capture with threaded recording."""

    def __init__(self, sample_rate=16000, block_size=1024):
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.audio_queue = queue.Queue(maxsize=300)
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
    """Captures system/game audio via WASAPI loopback."""

    def _capture_loop(self):
        try:
            speaker = sc.default_speaker()
            print(f"[Audio] Default speaker: {speaker.name}")

            # Direct loopback via speaker ID - the reliable way
            loopback = sc.get_microphone(speaker.id, include_loopback=True)
            if loopback is None:
                print("[Audio] ERROR: No loopback device found.")
                print("[Audio] Ensure audio is playing through your default output.")
                return

            print(f"[Audio] System loopback: {loopback.name}")
            with loopback.recorder(samplerate=self.sample_rate) as recorder:
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
            print(f"[Audio] System loopback error: {e}")
            print("[Audio] Tip: Make sure you have an active audio output device.")


class MicAudioCapture(AudioCapture):
    """Captures microphone input."""

    def _capture_loop(self):
        try:
            mic = sc.default_microphone()
            print(f"[Audio] Microphone: {mic.name}")
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
            print(f"[Audio] Microphone error: {e}")
            print("[Audio] Tip: Ensure a microphone is connected.")
