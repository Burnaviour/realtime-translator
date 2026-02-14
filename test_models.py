"""
Model Comparison Test — uses REAL conversation lines from translation logs
to benchmark translation quality across all supported models.

Tests Russian→English accuracy on short, noisy, gaming-context sentences
that are typical of real-time voice chat transcription.

Usage:
    python test_models.py                   # test all models
    python test_models.py nllb-600M         # test one specific model
    python test_models.py --quick           # test only fast models
"""

import sys
import time
import torch

# ── Test data extracted from translation_logs/translations_2026-02-14.log ────
# Format: (russian_source, bad_translation_we_got, expected_correct_english)
#
# These represent REAL mistakes from the gaming session.

TEST_CASES = [
    # === WRONG MEANING (translator picks wrong word sense) ===
    (
        "Бочка.",
        "A bottle.",
        "Barrel.",  # бочка = barrel, not bottle
    ),
    (
        "Сундук.",
        "The soundtrack.",
        "Chest.",  # сундук = chest (treasure chest), not soundtrack
    ),
    (
        "Я люблю кушать.",
        "I love to cook.",
        "I love to eat.",  # кушать = eat, not cook
    ),
    (
        "Типа плов с курицей.",
        "It's kind of like a chicken flower.",
        "Like pilaf with chicken.",  # плов = pilaf, not flower
    ),
    (
        "Я хочу вернуться назад, там был лук.",
        "I want to go back, there was onion.",
        "I want to go back, there was a bow.",  # лук = bow (Fortnite weapon)
    ),
    (
        "У вас хватает сил на фортнайт?",
        "Do you have the strength to forty-nine?",
        "Do you have the energy for Fortnite?",  # фортнайт = Fortnite
    ),
    (
        "Молодцы.",
        "Young people.",
        "Well done.",  # молодцы = well done / good job
    ),
    (
        "Убила.",
        "He killed her.",
        "She killed.",  # убила = feminine past tense = SHE killed
    ),
    (
        "Откручиваем.",
        "Let's roll it up.",
        "Let's crank.",  # откручиваем = unscrewing/cranking (gaming: cranking builds)
    ),
    (
        "Мне нужны шутганы.",
        "I need a joke.",
        "I need shotguns.",  # шутганы = shotguns (borrowed English)
    ),
    (
        "Колесо обозрения.",
        "the sighting wheel.",
        "Ferris wheel.",  # колесо обозрения = Ferris wheel
    ),
    (
        "Шлюпки.",
        "It's a shed.",
        "Boats.",  # шлюпки = boats / dinghies
    ),
    (
        "Автоматический автомат.",
        "Automatically automated.",
        "Automatic assault rifle.",  # автомат = assault rifle in gaming
    ),

    # === HALLUCINATED EXTRA WORDS (model adds meaning that doesn't exist) ===
    (
        "О, нет.",
        "Oh, no, not at all.",
        "Oh, no.",  # simple exclamation, no "not at all"
    ),
    (
        "Нет.",
        "No, not at all.",
        "No.",  # just "no", not "not at all"
    ),
    (
        "Нет, нет, нет.",
        "No, no, no, no.",
        "No, no, no.",  # 3 nos, not 4
    ),
    (
        "Найс.",
        "Nice work.",
        "Nice.",  # just "nice", no extra "work"
    ),
    (
        "Оу!",
        "Oh, my God!",
        "Oh!",  # simple exclamation, not "oh my god"
    ),
    (
        "ГОС",
        "The State of the Union address.",
        "GOS",  # garbled word/abbreviation, not State of the Union
    ),

    # === GAMING CONTEXT (needs gaming awareness) ===
    (
        "Пушка.",
        "A rifle.",
        "Gun.",  # пушка = gun/cannon in gaming slang
    ),
    (
        "Возьми мой автомат.",
        "Take my machine gun.",
        "Take my AR.",  # автомат = assault rifle (AR) in Fortnite
    ),
    (
        "Бункер, бункер.",
        "The bunker, the bunker.",
        "Bunker, bunker.",  # OK but articles are unnecessary in callouts
    ),
    (
        "Три команды.",
        "Three teams.",
        "Three teams.",  # this one was correct
    ),
    (
        "Рома!",
        "Rome!",
        "Roma!",  # Рома is a person's name, not the city
    ),
    (
        "Роман.",
        "The novel.",
        "Roman.",  # Роман is a person's name here, not "a novel"
    ),
    (
        "Мне нужен дробовик.",
        "I need a shotgun.",
        "I need a shotgun.",  # this one was correct
    ),
    (
        "Сиди пока, всё равно ещё много времени.",
        "Sit down for now, there's still a lot of time.",
        "Stay put, there's still a lot of time.",  # decent
    ),

    # === CONVERSATIONAL / REAL SPEECH ===
    (
        "Я пила молоко.",
        "I drank milk.",
        "I was drinking milk.",  # пила = was drinking (fem.)
    ),
    (
        "Молодец.",
        "A young man.",
        "Well done.",  # молодец = well done / good job
    ),
    (
        "Давайте ещё одну игру, и я пойду спать.",
        "Let's play one more game, and I'll go to bed.",
        "Let's play one more game, and I'll go to bed.",  # correct
    ),
    (
        "Я за вас переживала.",
        "I was worried about you.",
        "I was worried about you.",  # correct
    ),
    (
        "Вы убили четыре человека один.",
        "You killed four people alone.",
        "You killed four people alone.",  # correct — good if model gets this
    ),
    (
        "Я не вижу вас.",
        "I can't see you.",
        "I can't see you.",  # correct
    ),
    (
        "Какая ваша любимая еда?",
        "What's your favorite food?",
        "What's your favorite food?",  # correct
    ),
    (
        "Спокойной ночи!",
        "Have a good night!",
        "Good night!",  # simpler is better for real-time
    ),
    (
        "Поехали!",
        "Let's go!",
        "Let's go!",  # correct
    ),
    (
        "Это ещё одна команда пришла.",
        "That's another team coming.",
        "Another team just showed up.",  # or similar
    ),

    # === SHORT EXCLAMATIONS (should NOT be over-translated) ===
    (
        "Вот.",
        "There you go.",
        "Here.",  # вот = here / here it is (simple)
    ),
    (
        "Ага.",
        "Oh yeah.",
        "Yeah.",  # ага = yeah / uh-huh
    ),
    (
        "Да.",
        "Yes.",
        "Yes.",  # correct
    ),
    (
        "Спасибо.",
        "Thank you.",
        "Thank you.",  # correct
    ),

    # === GENDER / GRAMMAR ISSUES ===
    (
        "Я вас поняла, вы это певица.",
        "I understand you, you're a singer.",
        "I see, you're a singer.",  # поняла = feminine understood
    ),
    (
        "Она поднялась, она поднялась, которую ты убил.",
        "She rose, she rose, the one you killed.",
        "She got up, she got up, the one you killed.",  # gaming: she got revived
    ),

    # === PROFANITY HANDLING (should translate accurately, not escalate) ===
    (
        "Кусок дерьма.",
        "A piece of shit.",
        "A piece of shit.",  # correct translation
    ),
    (
        "Чёрт возьми, ты чёртовщина!",
        "Damn you motherfucker, why don't you do it?",
        "Damn, what devilry!",  # чёртовщина = devilry, NOT motherfucker
    ),
]


def score_translation(model_output: str, expected: str, source: str) -> dict:
    """
    Score a translation against the expected output.
    Returns a dict with scores and details.
    """
    model_output = model_output.strip()
    expected = expected.strip()
    source = source.strip()

    # Exact match (case insensitive)
    exact = model_output.lower() == expected.lower()

    # Key-word overlap (how many expected words appear in output)
    expected_words = set(expected.lower().split())
    output_words = set(model_output.lower().split())
    if expected_words:
        overlap = len(expected_words & output_words) / len(expected_words)
    else:
        overlap = 1.0 if not output_words else 0.0

    # Penalty for hallucinated extra content
    extra_words = output_words - expected_words
    # Common filler that's acceptable
    acceptable_extras = {"the", "a", "an", "is", "it", "of", "to", "and", "in", "for", "its", "i", "you", "we", "he", "she"}
    meaningful_extras = extra_words - acceptable_extras
    hallucination_penalty = min(len(meaningful_extras) * 0.1, 0.5)

    # Length ratio penalty (penalise much longer outputs)
    len_ratio = len(model_output) / max(len(expected), 1)
    length_penalty = max(0, (len_ratio - 1.5) * 0.2) if len_ratio > 1.5 else 0

    # Compute final score 0-100
    base_score = overlap * 100
    if exact:
        base_score = 100
    final_score = max(0, base_score - hallucination_penalty * 100 - length_penalty * 100)

    return {
        "score": round(final_score, 1),
        "exact": exact,
        "overlap": round(overlap, 3),
        "output": model_output,
        "expected": expected,
        "hallucination_extra_words": len(meaningful_extras),
    }


def test_model(model_name: str, test_cases: list, apply_glossary: bool = False) -> dict:
    """
    Load a model, run all test cases, return results.
    If apply_glossary=True, also apply glossary fixes (simulates real-world usage).
    """
    from translator import Translator
    if apply_glossary:
        from glossary import apply_gaming_glossary, apply_name_corrections

    label = f"{model_name} + glossary" if apply_glossary else model_name
    print(f"\n{'='*70}")
    print(f"  TESTING: {label}")
    print(f"{'='*70}")

    # Load model
    t0 = time.time()
    try:
        translator = Translator(
            source_lang="ru", target_lang="en",
            translation_model=model_name
        )
    except Exception as e:
        print(f"  FAILED to load: {e}")
        return {"model": label, "error": str(e), "results": [], "avg_score": 0}
    load_time = time.time() - t0
    print(f"  Loaded in {load_time:.1f}s")

    results = []
    total_time = 0

    for i, (source, bad_output, expected) in enumerate(test_cases):
        t0 = time.time()
        # Optionally apply pre-translation name corrections
        src_text = source
        if apply_glossary:
            src_text = apply_name_corrections(src_text, language="ru")
        output = translator.translate(src_text)
        # Optionally apply post-translation glossary
        if apply_glossary:
            output = apply_gaming_glossary(output, target_lang="en")
        elapsed = time.time() - t0
        total_time += elapsed

        score_info = score_translation(output, expected, source)
        score_info["source"] = source
        score_info["bad_previous"] = bad_output
        score_info["time_ms"] = round(elapsed * 1000, 1)
        results.append(score_info)

        # Print result with color indicators
        status = "✓" if score_info["exact"] else ("~" if score_info["score"] >= 60 else "✗")
        print(f"  [{status}] {score_info['score']:5.1f}  {source[:50]:<50s}")
        if not score_info["exact"]:
            print(f"         Got:      {output[:70]}")
            print(f"         Expected: {expected[:70]}")

    avg_score = sum(r["score"] for r in results) / len(results) if results else 0
    avg_time = (total_time / len(results) * 1000) if results else 0
    exact_count = sum(1 for r in results if r["exact"])
    good_count = sum(1 for r in results if r["score"] >= 60)

    print(f"\n  ── SUMMARY for {model_name} ──")
    print(f"  Average Score:  {avg_score:.1f}/100")
    print(f"  Exact matches:  {exact_count}/{len(results)}")
    print(f"  Good (≥60):     {good_count}/{len(results)}")
    print(f"  Avg latency:    {avg_time:.0f}ms per sentence")
    print(f"  Load time:      {load_time:.1f}s")

    # Free GPU memory
    del translator
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    return {
        "model": model_name,
        "avg_score": round(avg_score, 1),
        "exact_matches": exact_count,
        "good_matches": good_count,
        "total": len(results),
        "avg_latency_ms": round(avg_time, 0),
        "load_time_s": round(load_time, 1),
        "results": results,
    }


def print_comparison(all_results: list):
    """Print a comparison table of all models."""
    print(f"\n{'='*80}")
    print(f"  FINAL COMPARISON — {len(all_results)} models tested")
    print(f"{'='*80}")
    print(f"  {'Model':<25s} {'Score':>6s} {'Exact':>6s} {'Good':>6s} {'Latency':>8s} {'Load':>6s}")
    print(f"  {'-'*25} {'-'*6} {'-'*6} {'-'*6} {'-'*8} {'-'*6}")

    # Sort by score descending
    sorted_results = sorted(all_results, key=lambda x: x["avg_score"], reverse=True)
    for r in sorted_results:
        if "error" in r:
            print(f"  {r['model']:<25s}  ERROR: {r['error'][:40]}")
            continue
        print(f"  {r['model']:<25s} {r['avg_score']:5.1f}% "
              f"{r['exact_matches']:>3d}/{r['total']:<2d} "
              f"{r['good_matches']:>3d}/{r['total']:<2d} "
              f"{r['avg_latency_ms']:>6.0f}ms "
              f"{r['load_time_s']:>5.1f}s")

    # Show which model wins for categories
    print(f"\n  ── CATEGORY WINNERS ──")
    if sorted_results:
        valid = [r for r in sorted_results if "error" not in r]
        if valid:
            best_quality = max(valid, key=lambda x: x["avg_score"])
            fastest = min(valid, key=lambda x: x["avg_latency_ms"])
            best_balance = max(valid, key=lambda x: x["avg_score"] / max(x["avg_latency_ms"], 1) * 100)
            print(f"  Best Quality:     {best_quality['model']} ({best_quality['avg_score']}%)")
            print(f"  Fastest:          {fastest['model']} ({fastest['avg_latency_ms']}ms)")
            print(f"  Best Balance:     {best_balance['model']} (quality/speed ratio)")

    # Show worst translations per model for the problem cases
    print(f"\n  ── WORST PROBLEM CASES ──")
    problem_sources = [
        "Бочка.", "Сундук.", "Молодцы.", "Рома!", "Роман.",
        "О, нет.", "Мне нужны шутганы.", "Убила."
    ]
    for source in problem_sources:
        print(f"\n  Source: {source}")
        for r in sorted_results:
            if "error" in r:
                continue
            for res in r["results"]:
                if res["source"] == source:
                    status = "✓" if res["exact"] else "✗"
                    print(f"    [{status}] {r['model']:<22s} → {res['output'][:60]}")


def main():
    args = sys.argv[1:]

    use_glossary = "--with-glossary" in args
    args = [a for a in args if not a.startswith("--")]

    # Default set of models to test
    if args:
        models_to_test = [args[0]]
    else:
        # Only test VRAM-safe models (< 2GB)
        models_to_test = [
            "opus-mt",
            "nllb-600M",
            "nllb-600M-ct2",
        ]

    mode_label = " + GLOSSARY" if use_glossary else " (raw, no glossary)"
    print(f"Testing {len(models_to_test)} models with {len(TEST_CASES)} real conversation test cases{mode_label}")
    print(f"GPU: {'CUDA' if torch.cuda.is_available() else 'CPU'}")
    if torch.cuda.is_available():
        print(f"Device: {torch.cuda.get_device_name(0)}")
        print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")

    all_results = []
    for model_name in models_to_test:
        result = test_model(model_name, TEST_CASES, apply_glossary=use_glossary)
        all_results.append(result)

    print_comparison(all_results)


if __name__ == "__main__":
    main()
