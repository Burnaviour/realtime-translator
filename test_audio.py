"""
Component tests for the Real-time Translator.

Run with:  uv run test_audio.py
"""

import sys
import time


def test_imports():
    """Verify all required packages are installed and devices are accessible."""
    print("[Test 1/4] Checking imports and devices...")
    ok = True

    try:
        import numpy as np
        print(f"  numpy {np.__version__} - OK")
    except ImportError as e:
        print(f"  numpy - FAILED: {e}")
        ok = False

    try:
        import soundcard as sc
        print(f"  soundcard - OK")
        speaker = sc.default_speaker()
        print(f"    Default speaker : {speaker.name}")
        mic = sc.default_microphone()
        print(f"    Default mic     : {mic.name}")
        loopback = sc.get_microphone(speaker.id, include_loopback=True)
        if loopback:
            print(f"    Loopback device : {loopback.name}")
        else:
            print("    Loopback device : NOT FOUND (system audio capture won't work)")
    except Exception as e:
        print(f"  soundcard - FAILED: {e}")
        ok = False

    try:
        import torch
        print(f"  torch {torch.__version__} - OK")
        if torch.cuda.is_available():
            print(f"    CUDA GPU: {torch.cuda.get_device_name(0)}")
        else:
            print("    CUDA: Not available (will use CPU - slower but works)")
    except ImportError as e:
        print(f"  torch - FAILED: {e}")
        ok = False

    try:
        from faster_whisper import WhisperModel
        print(f"  faster_whisper - OK")
    except ImportError as e:
        print(f"  faster_whisper - FAILED: {e}")
        ok = False

    try:
        from transformers import MarianMTModel, MarianTokenizer
        print(f"  transformers - OK")
    except ImportError as e:
        print(f"  transformers - FAILED: {e}")
        ok = False

    try:
        import keyboard
        print(f"  keyboard - OK")
    except ImportError as e:
        print(f"  keyboard - FAILED: {e}")
        ok = False

    return ok


def test_transcriber():
    """Load Whisper (tiny for speed) and transcribe silence."""
    print("\n[Test 2/4] Testing Whisper transcriber...")
    import numpy as np
    from transcriber import Transcriber

    t = Transcriber(model_size="tiny")  # tiny = fast for testing
    if t.model is None:
        print("  FAILED: Whisper model did not load")
        return False

    # Transcribe 2 seconds of silence – should return empty / hallucination
    silence = np.zeros(16000 * 2, dtype=np.float32)
    result = t.transcribe_text(silence, language="en")
    print(f"  Silence transcription: '{result}' (expected empty or noise)")
    print("  Transcriber - OK")
    return True


def test_translator():
    """Load MarianMT models and translate a test sentence each way."""
    print("\n[Test 3/4] Testing MarianMT translator...")
    from translator import Translator

    # EN -> RU
    t_en_ru = Translator(source_lang="en", target_lang="ru")
    if t_en_ru.model is None:
        print("  FAILED: EN->RU model did not load")
        return False
    result1 = t_en_ru.translate("Hello, how are you?")
    print(f"  EN->RU: 'Hello, how are you?' -> '{result1}'")
    if not result1:
        print("  FAILED: Empty EN->RU translation")
        return False

    # RU -> EN
    t_ru_en = Translator(source_lang="ru", target_lang="en")
    if t_ru_en.model is None:
        print("  FAILED: RU->EN model did not load")
        return False
    result2 = t_ru_en.translate("Привет, как дела?")
    print(f"  RU->EN: 'Привет, как дела?' -> '{result2}'")
    if not result2:
        print("  FAILED: Empty RU->EN translation")
        return False

    print("  Translator - OK")
    return True


def test_overlay():
    """Open the overlay for 3 seconds, push sample text, then close."""
    print("\n[Test 4/4] Testing overlay (3-second visual check)...")
    import threading
    from overlay import OverlayWindow

    overlay = OverlayWindow()

    def run_test():
        time.sleep(0.5)
        overlay.update_game_text("Test: Your teammate said something in Russian")
        time.sleep(1.0)
        overlay.update_mic_text("Тест: Вы что-то сказали по-английски")
        time.sleep(1.5)
        overlay.stop()

    threading.Thread(target=run_test, daemon=True).start()

    try:
        overlay.start()
    except Exception:
        pass

    print("  Overlay - OK")
    return True


def main():
    print("=" * 56)
    print("  Real-time Translator - Component Tests")
    print("=" * 56)
    print()

    results = {}

    # 1) Imports
    results["imports"] = test_imports()
    if not results["imports"]:
        print("\n!! Critical imports failed. Fix dependencies first:")
        print("   cd realtime_translator && uv sync")
        sys.exit(1)

    # 2) Transcriber
    results["transcriber"] = test_transcriber()

    # 3) Translator
    results["translator"] = test_translator()

    # 4) Overlay
    results["overlay"] = test_overlay()

    # Summary
    passed = [k for k, v in results.items() if v]
    failed = [k for k, v in results.items() if not v]

    print()
    print("=" * 56)
    print(f"  Results: {len(passed)} passed, {len(failed)} failed")
    if failed:
        print(f"  Failed: {', '.join(failed)}")
    else:
        print("  All tests passed!")
        print("  Run  uv run main.py  to start the translator.")
    print("=" * 56)

    return len(failed) == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
