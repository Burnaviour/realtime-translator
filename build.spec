# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Real-time Voice Translator.

Usage:
    pyinstaller build.spec

Output:
    dist/RealtimeTranslator/  (folder with exe + all dependencies)
"""

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

# ── Paths ───────────────────────────────────────────────────────────
# SPECPATH is set by PyInstaller to the directory containing the .spec file.
# We also resolve via __file__-style fallback in case of path issues.
PROJECT_DIR = SPECPATH  # PyInstaller sets this to the spec file's directory
VENV_SITE = os.path.join(PROJECT_DIR, ".venv", "Lib", "site-packages")

# Fallback: if .venv isn't at PROJECT_DIR, try to find torch directly
if not os.path.isdir(VENV_SITE):
    import torch as _torch
    VENV_SITE = os.path.dirname(os.path.dirname(_torch.__file__))
    print(f"[build.spec] Using fallback site-packages: {VENV_SITE}")

TORCH_DIR = os.path.join(VENV_SITE, "torch")
TORCH_LIB = os.path.join(TORCH_DIR, "lib")
CT2_DIR = os.path.join(VENV_SITE, "ctranslate2")

# ── Collect CUDA DLLs from torch/lib ───────────────────────────────
torch_dlls = []
for f in os.listdir(TORCH_LIB):
    if f.endswith(".dll"):
        torch_dlls.append((os.path.join(TORCH_LIB, f), "torch/lib"))

# ── Collect CTranslate2 DLLs ──────────────────────────────────────
ct2_dlls = []
for f in os.listdir(CT2_DIR):
    if f.endswith((".dll", ".pyd")):
        ct2_dlls.append((os.path.join(CT2_DIR, f), "ctranslate2"))

# ── Data files for transformers tokenizers ─────────────────────────
transformers_data = collect_data_files("transformers", include_py_files=True)
sentencepiece_data = collect_data_files("sentencepiece")

# ── faster_whisper assets (Silero VAD model) ───────────────────────
FW_ASSETS = os.path.join(VENV_SITE, "faster_whisper", "assets")

# ── Analysis ───────────────────────────────────────────────────────
a = Analysis(
    ["main.py"],
    pathex=[SPECPATH],
    binaries=torch_dlls + ct2_dlls,
    datas=[
        # App files
        ("settings.json", "."),
        ("overlay.py", "."),
        ("settings.py", "."),
        ("settings_ui.py", "."),
        ("audio_capture.py", "."),
        ("transcriber.py", "."),
        ("translator.py", "."),
        # faster_whisper VAD model
        (FW_ASSETS, "faster_whisper/assets"),
    ] + transformers_data + sentencepiece_data,
    hiddenimports=[
        # PyTorch
        "torch",
        "torch.cuda",
        "torch.backends",
        "torch.backends.cudnn",
        "torchaudio",
        "torchaudio.lib",
        # Whisper / CTranslate2
        "faster_whisper",
        "ctranslate2",
        "ctranslate2._ext",
        # Transformers / MarianMT
        "transformers",
        "transformers.models.marian",
        "transformers.models.marian.modeling_marian",
        "transformers.models.marian.tokenization_marian",
        "sentencepiece",
        "sacremoses",
        # Audio
        "soundcard",
        "soundcard.mediafoundation",
        # Input
        "keyboard",
        "keyboard._winkeyboard",
        # Misc
        "numpy",
        "huggingface_hub",
        "filelock",
        "requests",
        "tqdm",
        "regex",
        "safetensors",
        "safetensors.torch",
        "tokenizers",
        "packaging",
        "yaml",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "matplotlib", "PIL", "scipy", "pandas",
        "pytest", "IPython", "notebook",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="RealtimeTranslator",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # Don't compress - CUDA DLLs don't like it
    console=True,  # Keep console for log output
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="RealtimeTranslator",
)
