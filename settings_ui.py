"""
Settings window — a nice GUI to configure overlay appearance.

Opens as a separate top-level window.  Changes apply live and are
persisted to settings.json on Save.
"""

import tkinter as tk
from tkinter import colorchooser, font as tkfont


class SettingsWindow:
    """
    Spawns a settings panel.  Call open() from the overlay's main thread.
    """

    def __init__(self, settings, on_apply_callback=None):
        """
        Args:
            settings:  a Settings instance (from settings.py)
            on_apply_callback:  callable() invoked after every live apply
        """
        self.settings = settings
        self.on_apply = on_apply_callback
        self.win = None

    # ── Public ──────────────────────────────────────────────────────

    def open(self, parent_root):
        """Open (or focus) the settings window."""
        if self.win is not None and self.win.winfo_exists():
            self.win.lift()
            return

        self.win = tk.Toplevel(parent_root)
        self.win.title("Translator Settings")
        self.win.geometry("420x620")
        self.win.resizable(False, False)
        self.win.configure(bg="#1c2128")
        self.win.attributes("-topmost", True)

        self._build_ui()

    # ── UI Builder ──────────────────────────────────────────────────

    def _build_ui(self):
        s = self.settings
        BG = "#1c2128"
        FG = "#c9d1d9"
        ENTRY_BG = "#2d333b"
        ACCENT = "#58a6ff"
        BTN_BG = "#238636"
        BTN_FG = "#ffffff"
        FONT = ("Segoe UI", 10)

        canvas = tk.Canvas(self.win, bg=BG, highlightthickness=0)
        scrollbar = tk.Scrollbar(self.win, orient="vertical", command=canvas.yview)
        frame = tk.Frame(canvas, bg=BG)

        frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        # Helper to bind mouse wheel
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        row = 0

        def section(title):
            nonlocal row
            tk.Label(frame, text=title, font=("Segoe UI", 11, "bold"),
                     fg=ACCENT, bg=BG, anchor="w").grid(
                row=row, column=0, columnspan=3, sticky="w", padx=12, pady=(14, 4))
            row += 1

        def slider_row(label, key, from_, to_, resolution=1, is_float=False):
            nonlocal row
            tk.Label(frame, text=label, font=FONT, fg=FG, bg=BG, anchor="w").grid(
                row=row, column=0, sticky="w", padx=(16, 4), pady=3)
            var = tk.DoubleVar(value=s.get(key)) if is_float else tk.IntVar(value=s.get(key))
            sl = tk.Scale(frame, from_=from_, to=to_, resolution=resolution,
                          orient="horizontal", variable=var, length=200,
                          bg=BG, fg=FG, troughcolor=ENTRY_BG,
                          highlightthickness=0, font=("Segoe UI", 8))
            sl.grid(row=row, column=1, columnspan=2, sticky="ew", padx=(0, 16), pady=3)
            row += 1
            return var, key

        def color_row(label, key):
            nonlocal row
            tk.Label(frame, text=label, font=FONT, fg=FG, bg=BG, anchor="w").grid(
                row=row, column=0, sticky="w", padx=(16, 4), pady=3)
            swatch = tk.Label(frame, text="  ", bg=s.get(key), width=4,
                              relief="solid", borderwidth=1)
            swatch.grid(row=row, column=1, sticky="w", padx=4, pady=3)
            hex_var = tk.StringVar(value=s.get(key))
            entry = tk.Entry(frame, textvariable=hex_var, width=10,
                             bg=ENTRY_BG, fg=FG, font=FONT,
                             insertbackground=FG, relief="flat")
            entry.grid(row=row, column=2, sticky="w", padx=(4, 16), pady=3)

            def pick():
                color = colorchooser.askcolor(initialcolor=s.get(key), title=f"Pick {label}")
                if color and color[1]:
                    hex_var.set(color[1])
                    swatch.config(bg=color[1])

            swatch.bind("<Button-1>", lambda e: pick())
            row += 1
            return hex_var, key, swatch

        def checkbox_row(label, key):
            nonlocal row
            var = tk.BooleanVar(value=s.get(key))
            cb = tk.Checkbutton(frame, text=label, variable=var,
                                bg=BG, fg=FG, selectcolor=ENTRY_BG,
                                activebackground=BG, activeforeground=FG,
                                font=FONT, anchor="w")
            cb.grid(row=row, column=0, columnspan=3, sticky="w", padx=12, pady=3)
            row += 1
            return var, key

        def dropdown_row(label, key, options):
            nonlocal row
            tk.Label(frame, text=label, font=FONT, fg=FG, bg=BG, anchor="w").grid(
                row=row, column=0, sticky="w", padx=(16, 4), pady=3)
            var = tk.StringVar(value=s.get(key))
            menu = tk.OptionMenu(frame, var, *options)
            menu.config(bg=ENTRY_BG, fg=FG, font=FONT, activebackground="#3d4450",
                        activeforeground=FG, highlightthickness=0, relief="flat")
            menu["menu"].config(bg=ENTRY_BG, fg=FG, font=FONT,
                                activebackground=ACCENT, activeforeground="#000")
            menu.grid(row=row, column=1, columnspan=2, sticky="ew", padx=(0, 16), pady=3)
            row += 1
            return var, key

        # ── Build all rows ──────────────────────────────────────────

        self._vars = []  # (var, key, [swatch]) tuples for collect()

        section("Language")
        self._vars.append(dropdown_row("My language", "source_language",
                                       ["english", "russian"]))
        self._vars.append(checkbox_row("Only detect selected game language",
                                       "filter_game_language"))

        section("Whisper Model")
        self._vars.append(dropdown_row("Model size", "whisper_model",
                                       ["tiny", "base", "small", "medium", "large-v2"]))
        tk.Label(frame, text="  tiny=fastest  base  small  medium  large-v2=best accuracy",
                 font=("Segoe UI", 8), fg="#7b8794", bg=BG, anchor="w").grid(
            row=row, column=0, columnspan=3, sticky="w", padx=16, pady=(0, 4))
        row += 1

        section("Overlay Size")
        self._vars.append(slider_row("Width", "overlay_width", 400, 1600))
        self._vars.append(slider_row("Height", "overlay_height", 80, 400))
        self._vars.append(slider_row("Opacity", "overlay_opacity", 0.3, 1.0, 0.02, is_float=True))

        section("Colors  (click swatch to pick)")
        self._vars.append(color_row("Background", "bg_color"))
        self._vars.append(color_row("Game text", "game_text_color"))
        self._vars.append(color_row("Mic text", "mic_text_color"))
        self._vars.append(color_row("Separator", "accent_color"))
        self._vars.append(color_row("Status text", "status_color"))

        section("Fonts")
        self._vars.append(slider_row("Game font size", "game_font_size", 8, 28))
        self._vars.append(slider_row("Mic font size", "mic_font_size", 8, 24))

        section("Streaming / Live Preview")
        self._vars.append(checkbox_row("Enable live transcription preview", "streaming_enabled"))
        self._vars.append(slider_row("Preview interval (ms)", "streaming_interval_ms", 500, 3000, 100))

        # ── Buttons ─────────────────────────────────────────────────
        btn_frame = tk.Frame(frame, bg=BG)
        btn_frame.grid(row=row, column=0, columnspan=3, pady=16)

        tk.Button(btn_frame, text="Apply", font=("Segoe UI", 10, "bold"),
                  bg=ACCENT, fg="#000", activebackground="#79c0ff",
                  relief="flat", padx=18, pady=4,
                  command=self._apply).pack(side="left", padx=6)

        tk.Button(btn_frame, text="Save", font=("Segoe UI", 10, "bold"),
                  bg=BTN_BG, fg=BTN_FG, activebackground="#2ea043",
                  relief="flat", padx=18, pady=4,
                  command=self._save).pack(side="left", padx=6)

        tk.Button(btn_frame, text="Reset Defaults", font=("Segoe UI", 10),
                  bg="#da3633", fg="#fff", activebackground="#f85149",
                  relief="flat", padx=12, pady=4,
                  command=self._reset).pack(side="left", padx=6)

    # ── Actions ─────────────────────────────────────────────────────

    def _collect(self):
        """Read all widget values back into settings."""
        for item in self._vars:
            var = item[0]
            key = item[1]
            val = var.get()
            self.settings.set(key, val)

    def _apply(self):
        self._collect()
        if self.on_apply:
            self.on_apply()

    def _save(self):
        self._collect()
        self.settings.save()
        if self.on_apply:
            self.on_apply()

    def _reset(self):
        self.settings.reset()
        # Close and re-open to refresh widgets
        if self.win and self.win.winfo_exists():
            self.win.destroy()
            self.win = None
        if self.on_apply:
            self.on_apply()
