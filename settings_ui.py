"""
Settings window — a nice GUI to configure overlay appearance.

Opens as a separate top-level window.  Changes apply live and are
persisted to settings.json on Save.
"""

import tkinter as tk
from tkinter import colorchooser, font as tkfont
from locales import t


class SettingsWindow:
    """
    Spawns a settings panel.  Call open() from the overlay's main thread.
    """

    def __init__(self, settings, on_apply_callback=None, on_restart_callback=None):
        """
        Args:
            settings:  a Settings instance (from settings.py)
            on_apply_callback:  callable() invoked after every live apply
            on_restart_callback: callable() invoked to restart the app
        """
        self.settings = settings
        self.on_apply = on_apply_callback
        self.on_restart = on_restart_callback
        self.win = None

    # ── Public ──────────────────────────────────────────────────────

    def open(self, parent_root):
        """Open (or focus) the settings window."""
        if self.win is not None and self.win.winfo_exists():
            self.win.lift()
            return

        self.win = tk.Toplevel(parent_root)
        self.win.title(t("settings_title"))
        self.win.geometry("420x660")
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
        
        # Bind mousewheel only when hovering over the canvas
        def _bind_mousewheel(event):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)
        def _unbind_mousewheel(event):
            canvas.unbind_all("<MouseWheel>")
        
        frame.bind("<Enter>", _bind_mousewheel)
        frame.bind("<Leave>", _unbind_mousewheel)
        
        # Cleanup on window destroy
        def _cleanup():
            canvas.unbind_all("<MouseWheel>")
        self.win.protocol("WM_DELETE_WINDOW", lambda: (_cleanup(), self.win.destroy()))

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

        section(t("sec_language"))
        self._vars.append(dropdown_row(t("lbl_app_language"), "app_language",
                                       ["english", "russian"]))
        self._vars.append(dropdown_row(t("lbl_my_language"), "source_language",
                                       ["english", "russian"]))
        self._vars.append(checkbox_row(t("lbl_filter_game"),
                                       "filter_game_language"))

        section(t("sec_audio_filter"))
        self._vars.append(checkbox_row(t("lbl_clean_audio_mode"),
                                       "clean_audio_mode"))
        self._vars.append(checkbox_row(t("lbl_speech_filter"),
                                       "speech_filter_enabled"))
        self._vars.append(slider_row(t("lbl_noise_gate"), "game_noise_gate",
                                     0.005, 0.05, 0.001, is_float=True))
        tk.Label(frame, text=t("lbl_noise_gate_hint"),
                 font=("Segoe UI", 8), fg="#7b8794", bg=BG, anchor="w").grid(
            row=row, column=0, columnspan=3, sticky="w", padx=16, pady=(0, 4))
        row += 1

        section(t("sec_whisper"))
        self._vars.append(dropdown_row(t("lbl_model_size"), "whisper_model",
                                       ["tiny", "base", "small", "medium", "large-v2"]))
        tk.Label(frame, text=t("lbl_model_hint"),
                 font=("Segoe UI", 8), fg="#7b8794", bg=BG, anchor="w").grid(
            row=row, column=0, columnspan=3, sticky="w", padx=16, pady=(0, 4))
        row += 1

        section(t("sec_translation"))
        self._vars.append(dropdown_row(t("lbl_trans_model"), "translation_model",
                                       ["opus-mt", "opus-mt-big", "nllb-600M", "nllb-1.3B",
                                        "nllb-600M-ct2", "nllb-1.3B-ct2"]))
        tk.Label(frame, text=t("lbl_trans_model_hint"),
                 font=("Segoe UI", 8), fg="#7b8794", bg=BG, anchor="w").grid(
            row=row, column=0, columnspan=3, sticky="w", padx=16, pady=(0, 4))
        row += 1
        self._vars.append(checkbox_row(t("lbl_transliterate_mic"),
                                       "transliterate_mic"))

        section(t("sec_overlay_size"))
        self._vars.append(slider_row(t("lbl_width"), "overlay_width", 400, 1600))
        self._vars.append(slider_row(t("lbl_height"), "overlay_height", 80, 400))
        self._vars.append(slider_row(t("lbl_opacity"), "overlay_opacity", 0.3, 1.0, 0.02, is_float=True))

        section(t("sec_colors"))
        self._vars.append(color_row(t("lbl_bg_color"), "bg_color"))
        self._vars.append(color_row(t("lbl_game_text_color"), "game_text_color"))
        self._vars.append(color_row(t("lbl_mic_text_color"), "mic_text_color"))
        self._vars.append(color_row(t("lbl_separator_color"), "accent_color"))
        self._vars.append(color_row(t("lbl_status_color"), "status_color"))

        section(t("sec_fonts"))
        self._vars.append(slider_row(t("lbl_game_font"), "game_font_size", 8, 28))
        self._vars.append(slider_row(t("lbl_mic_font"), "mic_font_size", 8, 24))

        section(t("sec_streaming"))
        self._vars.append(checkbox_row(t("lbl_streaming_enable"), "streaming_enabled"))
        self._vars.append(slider_row(t("lbl_streaming_interval"), "streaming_interval_ms", 500, 3000, 100))

        # ── Buttons ─────────────────────────────────────────────────
        btn_frame = tk.Frame(frame, bg=BG)
        btn_frame.grid(row=row, column=0, columnspan=3, pady=16)

        tk.Button(btn_frame, text=t("btn_apply"), font=("Segoe UI", 10, "bold"),
                  bg=ACCENT, fg="#000", activebackground="#79c0ff",
                  relief="flat", padx=18, pady=4,
                  command=self._apply).pack(side="left", padx=6)

        tk.Button(btn_frame, text=t("btn_save"), font=("Segoe UI", 10, "bold"),
                  bg=BTN_BG, fg=BTN_FG, activebackground="#2ea043",
                  relief="flat", padx=18, pady=4,
                  command=self._save).pack(side="left", padx=6)

        tk.Button(btn_frame, text=t("btn_reset"), font=("Segoe UI", 10),
                  bg="#da3633", fg="#fff", activebackground="#f85149",
                  relief="flat", padx=12, pady=4,
                  command=self._reset).pack(side="left", padx=6)

        # Second row for restart
        btn_frame2 = tk.Frame(frame, bg=BG)
        btn_frame2.grid(row=row + 1, column=0, columnspan=3, pady=(0, 16))

        tk.Button(btn_frame2, text=t("btn_restart"), font=("Segoe UI", 10, "bold"),
                  bg="#8957e5", fg="#fff", activebackground="#a371f7",
                  relief="flat", padx=18, pady=4,
                  command=self._save_and_restart).pack()

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

    def _save_and_restart(self):
        """Save settings and restart the application."""
        self._collect()
        self.settings.save()
        if self.on_restart:
            self.on_restart()
