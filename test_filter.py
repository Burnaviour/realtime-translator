#!/usr/bin/env python
"""Quick test of the repetition filter."""
from main import _is_repetitive_translation, is_hallucination

# Test cases from the actual console log
test_cases = [
    ("Whoa, " * 50, True, "50x Whoa", _is_repetitive_translation),
    ("Weight, " * 70, True, "70x Weight", _is_repetitive_translation),
    ("Hello how are you doing today", False, "Normal sentence", _is_repetitive_translation),
    ("Okay, okay, okay, okay, okay, okay, okay, okay, okay", True, "9x okay", _is_repetitive_translation),
    ("Come on, let's go to the point", False, "Normal callout", _is_repetitive_translation),
    ("Буууууууу" + "у" * 100, True, "Long repeated char", is_hallucination),
    ("Редактор субтитров Н.Закомолдина", True, "Subtitle artifact", is_hallucination),
]

print("Testing filters:")
for text, expected, description, filter_func in test_cases:
    result = filter_func(text)
    status = "✓" if result == expected else "✗"
    func_name = filter_func.__name__
    print(f"{status} {description} ({func_name}): {result} (expected {expected})")
    if len(text) > 60:
        print(f"   Text: {text[:60]}...")
    else:
        print(f"   Text: {text}")
