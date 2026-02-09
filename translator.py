import torch
from transformers import MarianMTModel, MarianTokenizer


class Translator:
    """Neural machine translation using Helsinki-NLP MarianMT models."""

    def __init__(self, source_lang="en", target_lang="ru"):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model_name = f"Helsinki-NLP/opus-mt-{source_lang}-{target_lang}"

        print(f"[Translator] Loading {self.model_name} on {self.device}...")
        try:
            self.tokenizer = MarianTokenizer.from_pretrained(self.model_name)
            self.model = MarianMTModel.from_pretrained(self.model_name).to(self.device)
            self.model.eval()  # Set to evaluation mode for inference
            print(f"[Translator] {self.model_name} loaded.")
        except Exception as e:
            print(f"[Translator] ERROR loading model: {e}")
            self.model = None
            self.tokenizer = None

    def translate(self, text):
        """
        Translate text from source language to target language.
        
        Args:
            text: Input text string
            
        Returns:
            Translated text string, or empty string on failure.
        """
        if not self.model or not text or not text.strip():
            return ""

        try:
            batch = self.tokenizer(
                [text],
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=512,
            ).to(self.device)

            with torch.no_grad():
                generated = self.model.generate(**batch)

            result = self.tokenizer.batch_decode(generated, skip_special_tokens=True)[0]
            return result
        except Exception as e:
            print(f"[Translator] Translation error: {e}")
            return ""
