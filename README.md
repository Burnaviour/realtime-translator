# Real-time Game Audio Translator

This is a custom Python script for real-time bi-directional translation (Russian <-> English) for gaming. It captures system audio (gameplay) and microphone input, transcribes them using OpenAI's Whisper (via `faster-whisper`), translates them using Helsinki-NLP models, and displays the text on a transparent, click-through overlay.

## Prerequisites

- **OS**: Windows (tested on Windows 10/11)
- **GPU**: NVIDIA GPU with CUDA support (RTX 5070 is perfect)
- **Tool**: [uv](https://github.com/astral-sh/uv) (for fast Python package management)

## Installation

1.  **Open a terminal** in this directory:
    ```powershell
    cd C:\Users\Burnaviour\Desktop\soundtest\realtime_translator
    ```

2.  **Install dependencies** using `uv`:
    ```powershell
    uv sync
    ```
    *This will automatically create a virtual environment and install PyTorch with CUDA support.*

## Usage

1.  **Run the script**:
    ```powershell
    uv run main.py
    ```

2.  **Wait for initialization**:
    - The script will download the necessary models on the first run. This might take a few minutes.
    - You will see "Listening..." when it's ready.

3.  **Overlay**:
    - A transparent overlay will appear at the top of your screen.
    - **Top Section (Yellow)**: Shows translated game audio (Russian -> English).
    - **Bottom Section (Cyan)**: Shows translated microphone input (English -> Russian).
    - The overlay is "click-through", so it won't interfere with your game controls.

4.  **Stop**:
    - Close the overlay window or press `Ctrl+C` in the terminal to stop.

## Configuration

- **Models**:
    - **ASR**: `transcriber.py` uses `model_size="small"`. You can change this to `medium` or `large-v2` if you want higher accuracy (but higher latency).
    - **Translation**: `translator.py` uses `Helsinki-NLP/opus-mt-ru-en` and `en-ru`.

## Troubleshooting

- **No Game Audio**: Ensure "Stereo Mix" is enabled in Windows Sound settings if `soundcard` fails to capture loopback, although `soundcard` usually handles WASAPI loopback natively.
- **CUDA Errors**: Ensure you have the latest NVIDIA drivers installed.
