"""
Test: Simulates a Russian teammate conversation in a Fortnite-style game.

Two teammates speaking Russian — your translator should pick it up
via system audio loopback and show English translations on the overlay.

Usage:
    1. Start the translator:   uv run main.py
    2. In another terminal:    uv run test_conversation.py
    3. Watch the overlay for English translations.

Requires: gTTS, pygame  (auto-installed if missing)
"""

import time
import os
import sys

# ── Ensure gTTS and pygame are available ────────────────────────────
try:
    from gtts import gTTS
except ImportError:
    print("Installing gTTS...")
    os.system(f"{sys.executable} -m pip install gTTS")
    from gtts import gTTS

try:
    import pygame
except ImportError:
    print("Installing pygame...")
    os.system(f"{sys.executable} -m pip install pygame")
    import pygame


# ── The conversation ────────────────────────────────────────────────
# Two Russian teammates talking during a Fortnite match.
# Player 1 = deeper/slower voice, Player 2 = slightly faster

CONVERSATION = [
    {
        "player": "Player 1 (Алексей)",
        "ru": "Привет, братан! Ты готов? Мы прыгаем в Приятный Парк.",
        "en": "Hey bro! You ready? We're dropping at Pleasant Park.",
        "pause_after": 2.0,
    },
    {
        "player": "Player 2 (Дмитрий)",
        "ru": "Да, погнали! Я вижу там трех противников на крыше.",
        "en": "Yeah, let's go! I see three enemies on the roof.",
        "pause_after": 2.5,
    },
    {
        "player": "Player 1 (Алексей)",
        "ru": "Осторожно, у одного снайперка. Обходи слева, я прикрою.",
        "en": "Careful, one has a sniper. Flank left, I'll cover you.",
        "pause_after": 2.0,
    },
    {
        "player": "Player 2 (Дмитрий)",
        "ru": "Понял. Иду слева. О нет, у меня мало патронов! Есть запасные?",
        "en": "Got it. Going left. Oh no, I'm low on ammo! Do you have spare?",
        "pause_after": 2.5,
    },
    {
        "player": "Player 1 (Алексей)",
        "ru": "Сейчас скину. Лови! Дробовик и пятьдесят патронов.",
        "en": "I'll drop some. Catch! Shotgun and fifty rounds.",
        "pause_after": 2.0,
    },
    {
        "player": "Player 2 (Дмитрий)",
        "ru": "Спасибо! Я убил одного. Еще двое осталось, будь готов.",
        "en": "Thanks! I killed one. Two more left, stay ready.",
        "pause_after": 2.5,
    },
    {
        "player": "Player 1 (Алексей)",
        "ru": "Отлично! Я сбил второго. Последний убегает на юг, догоняй!",
        "en": "Nice! I downed the second. Last one running south, chase him!",
        "pause_after": 2.0,
    },
    {
        "player": "Player 2 (Дмитрий)",
        "ru": "Готово, всех зачистили! Надо лутать быстро, зона сужается через минуту.",
        "en": "Done, all cleared! Need to loot fast, storm is closing in one minute.",
        "pause_after": 2.5,
    },
    {
        "player": "Player 1 (Алексей)",
        "ru": "Нашел золотой автомат и аптечку. Двигаем к центру через мост.",
        "en": "Found a gold AR and a medkit. Let's move to center through the bridge.",
        "pause_after": 2.0,
    },
    {
        "player": "Player 2 (Дмитрий)",
        "ru": "Подожди, вижу снайпера на горе! Ложись, он нас видит!",
        "en": "Wait, I see a sniper on the hill! Get down, he sees us!",
        "pause_after": 3.0,
    },
    {
        "player": "Player 1 (Алексей)",
        "ru": "Строю стену! Прикрывай меня, пока я лечусь. У меня двадцать здоровья.",
        "en": "Building a wall! Cover me while I heal. I have twenty HP.",
        "pause_after": 2.5,
    },
    {
        "player": "Player 2 (Дмитрий)",
        "ru": "Стреляю по нему! Попал, он упал! Мы победим, осталось пять человек!",
        "en": "Shooting at him! Hit, he's down! We're gonna win, five people left!",
        "pause_after": 0,
    },
]


def generate_audio(text, filename, slow=False):
    """Generate a Russian TTS audio file."""
    tts = gTTS(text, lang="ru", slow=slow)
    tts.save(filename)


def play_audio(filename):
    """Play an audio file and wait for it to finish."""
    pygame.mixer.music.load(filename)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        time.sleep(0.1)


def main():
    print("=" * 60)
    print("  Fortnite Teammate Conversation Test (Russian)")
    print("  12 lines of dialogue between two players")
    print("=" * 60)
    print()
    print("  Make sure 'uv run main.py' is running in another terminal!")
    print()

    # Pre-generate all audio files
    print("[Generating TTS audio...]")
    audio_files = []
    for i, line in enumerate(CONVERSATION):
        fname = f"_test_conv_{i:02d}.mp3"
        slow = (line["player"].startswith("Player 1"))  # P1 speaks slightly slower
        generate_audio(line["ru"], fname, slow=slow)
        audio_files.append(fname)
        print(f"  {i+1:2d}/12  {line['player'][:12]}: {line['ru'][:50]}...")
    print()

    # Initialize audio playback
    pygame.mixer.init()

    # Countdown
    print("[Starting in 3 seconds... switch to your game/overlay window!]")
    for i in range(3, 0, -1):
        print(f"  {i}...")
        time.sleep(1)
    print()

    # Play the conversation
    print("[Playing conversation]")
    print("-" * 60)
    for i, line in enumerate(CONVERSATION):
        player = line["player"]
        print(f"  {player}:")
        print(f"    RU: {line['ru']}")
        print(f"    EN: {line['en']}")
        print()

        play_audio(audio_files[i])

        if line["pause_after"] > 0:
            time.sleep(line["pause_after"])

    print("-" * 60)
    print()
    print("[Conversation finished]")
    print("Check the overlay — you should see English translations for each line.")
    print()

    # Cleanup
    pygame.mixer.quit()
    for f in audio_files:
        try:
            os.remove(f)
        except OSError:
            pass
    print("[Temp files cleaned up]")


if __name__ == "__main__":
    main()
