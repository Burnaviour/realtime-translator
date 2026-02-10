import torch
import ctranslate2
from huggingface_hub import snapshot_download
from transformers import (
    MarianMTModel, MarianTokenizer,
    AutoModelForSeq2SeqLM, AutoTokenizer,
)

# ── Model registry ──────────────────────────────────────────────────
# Each entry: (how to build the HF model name, tokenizer class, model class, extra kwargs for generate)
#
# "opus-mt"      – Helsinki-NLP MarianMT  (small, fast, decent)
# "opus-mt-big"  – Helsinki-NLP MarianMT Big  (larger, better quality)
# "nllb-600M"    – Meta NLLB-200 distilled 600M  (best quality for EN↔RU)
# "nllb-1.3B"    – Meta NLLB-200 distilled 1.3B  (highest quality, needs more VRAM)

_NLLB_LANG_MAP = {
    "en": "eng_Latn",
    "ru": "rus_Cyrl",
}

MODEL_INFO = {
    "opus-mt": {
        "label": "MarianMT (fast, OK quality)",
        "label_ru": "MarianMT (быстрая, норм. качество)",
    },
    "opus-mt-big": {
        "label": "MarianMT Big (good quality)",
        "label_ru": "MarianMT Big (хорошее качество)",
    },
    "nllb-600M": {
        "label": "NLLB 600M (best quality)",
        "label_ru": "NLLB 600M (лучшее качество)",
    },
    "nllb-1.3B": {
        "label": "NLLB 1.3B (highest quality, heavy)",
        "label_ru": "NLLB 1.3B (макс. качество, тяжёлая)",
    },
    "nllb-600M-ct2": {
        "label": "NLLB 600M (Quantized Fast)",
        "label_ru": "NLLB 600M (Квантованная, Быстрая)",
    },
    "nllb-1.3B-ct2": {
        "label": "NLLB 1.3B (Quantized Fast)",
        "label_ru": "NLLB 1.3B (Квантованная, Быстрая)",
    },
}


class Translator:
    """
    Neural machine translation with multiple model backends.

    Supported translation_model values:
        "opus-mt"      -> Helsinki-NLP/opus-mt-{src}-{tgt}
        "opus-mt-big"  -> Helsinki-NLP/opus-mt-tc-big-{src}-{tgt}
        "nllb-600M"    -> facebook/nllb-200-distilled-600M
        "nllb-1.3B"    -> facebook/nllb-200-distilled-1.3B
        "nllb-600M-ct2" -> entai2965/nllb-200-distilled-600M-ctranslate2 (INT8)
        "nllb-1.3B-ct2" -> entai2965/nllb-200-distilled-1.3B-ctranslate2 (INT8)
    """

    def __init__(self, source_lang="en", target_lang="ru",
                 translation_model="opus-mt"):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.backend = translation_model
        self.model = None
        self.tokenizer = None
        self._forced_bos_id = None  # used by NLLB (Transformers)
        self._ct2_target_lang = None # used by NLLB (CTranslate2)

        if translation_model.endswith("-ct2"):
            self._load_ct2(translation_model)
        elif translation_model.startswith("nllb"):
            self._load_nllb(translation_model)
        elif translation_model == "opus-mt-big":
            self._load_marian_big()
        else:
            self._load_marian()

    # ── Loaders ─────────────────────────────────────────────────────

    def _load_ct2(self, variant):
        # Determine HF repo based on variant
        if "1.3B" in variant:
            repo = "entai2965/nllb-200-distilled-1.3B-ctranslate2"
            tokenizer_repo = "facebook/nllb-200-distilled-1.3B"
        else:
            repo = "entai2965/nllb-200-distilled-600M-ctranslate2"
            tokenizer_repo = "facebook/nllb-200-distilled-600M"

        print(f"[Translator] Downloading/Loading {repo} (CTranslate2) on {self.device}...")
        try:
            # Download/Cache model from HF Hub
            model_path = snapshot_download(repo_id=repo)
            print(f"[Translator] Model cached at: {model_path}")

            # Load the converter model
            self.model = ctranslate2.Translator(
                model_path, 
                device=self.device,
                compute_type="int8" # Forced quantization loading
            )
            # We still need the tokenizer to convert text <-> tokens
            self.tokenizer = AutoTokenizer.from_pretrained(
                tokenizer_repo, src_lang=_NLLB_LANG_MAP[self.source_lang]
            )
            self._ct2_target_lang = _NLLB_LANG_MAP[self.target_lang]
            print(f"[Translator] {repo} loaded.")
        except Exception as e:
            print(f"[Translator] ERROR loading {repo}: {e}")
            print(f"[Translator] Falling back to standard opus-mt...")
            self.backend = "opus-mt"
            self._load_marian()

    def _load_marian(self):
        model_name = f"Helsinki-NLP/opus-mt-{self.source_lang}-{self.target_lang}"
        print(f"[Translator] Loading {model_name} on {self.device}...")
        try:
            self.tokenizer = MarianTokenizer.from_pretrained(model_name)
            self.model = MarianMTModel.from_pretrained(model_name).to(self.device)
            self.model.eval()
            print(f"[Translator] {model_name} loaded.")
        except Exception as e:
            print(f"[Translator] ERROR loading {model_name}: {e}")

    def _load_marian_big(self):
        model_name = f"Helsinki-NLP/opus-mt-tc-big-{self.source_lang}-{self.target_lang}"
        print(f"[Translator] Loading {model_name} on {self.device}...")
        try:
            self.tokenizer = MarianTokenizer.from_pretrained(model_name)
            self.model = MarianMTModel.from_pretrained(model_name).to(self.device)
            self.model.eval()
            print(f"[Translator] {model_name} loaded.")
        except Exception as e:
            print(f"[Translator] ERROR loading {model_name}: {e}")
            print(f"[Translator] Falling back to standard opus-mt...")
            self._load_marian()

    def _load_nllb(self, variant):
        if variant == "nllb-1.3B":
            model_name = "facebook/nllb-200-distilled-1.3B"
        else:
            model_name = "facebook/nllb-200-distilled-600M"

        print(f"[Translator] Loading {model_name} on {self.device}...")
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(
                model_name, src_lang=_NLLB_LANG_MAP[self.source_lang]
            )
            self.model = AutoModelForSeq2SeqLM.from_pretrained(model_name).to(self.device)
            self.model.eval()
            # NLLB needs forced_bos_token_id for the target language
            self._forced_bos_id = self.tokenizer.convert_tokens_to_ids(
                _NLLB_LANG_MAP[self.target_lang]
            )
            print(f"[Translator] {model_name} loaded.")
        except Exception as e:
            print(f"[Translator] ERROR loading {model_name}: {e}")
            print(f"[Translator] Falling back to opus-mt...")
            self.backend = "opus-mt"
            self._load_marian()

    # ── Translation ─────────────────────────────────────────────────

    def translate(self, text):
        """
        Translate text from source language to target language.

        Returns:
            Translated text string, or empty string on failure.
        """
        if not self.model or not text or not text.strip():
            return ""

        try:
            # 1. CTranslate2 Inference
            if self.backend.endswith("-ct2"):
                # Tokenize source
                source = self.tokenizer.convert_ids_to_tokens(self.tokenizer.encode(text))
                # Hardware inference
                results = self.model.translate_batch([source], target_prefix=[[self._ct2_target_lang]])
                # Decode target tokens
                target_tokens = results[0].hypotheses[0]
                return self.tokenizer.decode(self.tokenizer.convert_tokens_to_ids(target_tokens), skip_special_tokens=True)

            # 2. Transformers Inference
            batch = self.tokenizer(
                [text],
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=512,
            ).to(self.device)

            gen_kwargs = {}
            if self._forced_bos_id is not None:
                gen_kwargs["forced_bos_token_id"] = self._forced_bos_id

            with torch.no_grad():
                generated = self.model.generate(**batch, **gen_kwargs)

            result = self.tokenizer.batch_decode(
                generated, skip_special_tokens=True
            )[0]
            return result
        except Exception as e:
            print(f"[Translator] Translation error: {e}")
            return ""
