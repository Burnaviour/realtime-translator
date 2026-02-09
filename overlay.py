"""
Professional gaming overlay with:
  - Live settings panel (F10 or gear icon)
  - Mouse-resizable edges
  - Streaming / live preview text (dimmed partial transcription)
  - All colors, sizes, opacity configurable and saved to settings.json

Hotkeys:
    F8  - Lock / Unlock  (click-through toggle)
    F9  - Show / Hide overlay
    F10 - Open settings panel
"""

import tkinter as tk
import ctypes
import queue

from settings import Settings
from settings_ui import SettingsWindow

# Resize handle size in pixels
_GRIP = 8


class OverlayWindow:
    def __init__(self):
        self.cfg = Settings()
        self.root = tk.Tk()
        self.root.withdraw()

        self.queue = queue.Queue()
        self.locked = True
        self.visible = True
        self._drag_x = 0
        self._drag_y = 0
        self._resizing = False
        self._resize_edge = None
        self._on_close_callback = None   # set by main app for clean exit

        # Settings window (lazy)
        self._settings_win = SettingsWindow(self.cfg, on_apply_callback=self._apply_settings)

        self._build()
        self._setup_hotkeys()
        self._apply_click_through()

        self.root.deiconify()
        self.root.after(80, self._process_queue)
        self.root.after(2000, self._keep_on_top)  # Periodic topmost re-assert

        # Welcome popup every launch
        self.root.after(300, self._show_welcome)

    # ════════════════════════════════════════════════════════════════
    #  WELCOME POPUP (first run)
    # ════════════════════════════════════════════════════════════════

    def _show_welcome(self):
        """Show a one-time welcome / quick-start popup."""
        popup = tk.Toplevel(self.root)
        popup.title("Welcome — Real-time Translator")
        popup.geometry("520x370")
        popup.resizable(False, False)
        popup.configure(bg="#1c2128")
        popup.attributes("-topmost", True)

        # Temporarily remove click-through so user can interact
        was_locked = self.locked
        if was_locked:
            self.locked = False
            self._remove_click_through()

        BG = "#1c2128"
        FG = "#c9d1d9"
        ACCENT = "#58a6ff"
        FONT = ("Segoe UI", 10)

        # Title
        tk.Label(popup, text=" to Real-time Voice Translator!",
                 font=("Segoe UI", 14, "bold"), fg=ACCENT, bg=BG).pack(pady=(18, 6))

        # Body
        src = self.cfg.get("source_language")
        if src == "russian":
            direction_text = (
                "Created for VIKA\n"
                "Your language: RUSSIAN\n"
                "Game / friend audio: English → translated to Russian for you\n"
                "Your microphone: Russian → translated to English for them"
            )
        else:
            direction_text = (
                "Created for VIKA .\n"
                "Your language: ENGLISH\n"
                "Game / friend audio: Russian → translated to English for you\n"
                "Your microphone: English → translated to Russian for them"
            )

        info = (
            f"{direction_text}\n\n"
            "Hotkeys:\n"
            "  F8  — Lock / Unlock overlay (click-through toggle)\n"
            "  F9  — Show / Hide overlay\n"
            "  F10 — Open Settings panel\n\n"
            "You can change your language in Settings (F10).\n"
            "Note: Changing language requires a restart to reload models."
        )

        tk.Label(popup, text=info, font=FONT, fg=FG, bg=BG,
                 justify="left", anchor="nw", wraplength=480).pack(
            padx=20, pady=(6, 10), fill="both", expand=True)

        def _close():
            popup.destroy()
            # Restore lock state
            if was_locked:
                self.locked = True
                self._apply_click_through()

        tk.Button(popup, text="Got it!", font=("Segoe UI", 11, "bold"),
                  bg="#238636", fg="#fff", activebackground="#2ea043",
                  relief="flat", padx=24, pady=6,
                  command=_close).pack(pady=(0, 16))

        popup.protocol("WM_DELETE_WINDOW", _close)

    # ════════════════════════════════════════════════════════════════
    #  BUILD
    # ════════════════════════════════════════════════════════════════

    def _build(self):
        c = self.cfg
        bg = c.get("bg_color")

        self.root.title("Translator")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", c.get("overlay_opacity"))
        self.root.configure(bg=bg)

        # Geometry
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        w = min(c.get("overlay_width"), sw - 40)
        h = c.get("overlay_height")
        x = c.get("overlay_x")
        y = c.get("overlay_y")
        if x < 0:
            x = (sw - w) // 2
        if y < 0:
            y = sh - h - 80
        self.root.geometry(f"{w}x{h}+{x}+{y}")

        font = c.get("font_family")

        # ── Main container ──────────────────────────────────────────
        self.container = tk.Frame(self.root, bg=bg, padx=14, pady=6)
        self.container.pack(fill="both", expand=True)

        wrap = max(300, w - 80)

        # ── Game text row ───────────────────────────────────────────
        game_row = tk.Frame(self.container, bg=bg)
        game_row.pack(fill="x", pady=(0, 2))

        self._game_icon = tk.Label(
            game_row, text="\u25b6", font=(font, 9),
            fg=c.get("game_text_color"), bg=bg,
        )
        self._game_icon.pack(side="left", padx=(0, 6))

        self.label_game = tk.Label(
            game_row, text="Listening for game audio\u2026",
            font=(font, c.get("game_font_size"), "bold"),
            fg=c.get("game_text_color"), bg=bg,
            anchor="w", wraplength=wrap, justify="left",
        )
        self.label_game.pack(side="left", fill="x", expand=True)

        # ── Separator ──────────────────────────────────────────────
        self._sep = tk.Frame(self.container, bg=c.get("accent_color"), height=1)
        self._sep.pack(fill="x", pady=2)

        # ── Mic text row ───────────────────────────────────────────
        mic_row = tk.Frame(self.container, bg=bg)
        mic_row.pack(fill="x", pady=(2, 0))

        self._mic_icon = tk.Label(
            mic_row, text="\u25c0", font=(font, 9),
            fg=c.get("mic_text_color"), bg=bg,
        )
        self._mic_icon.pack(side="left", padx=(0, 6))

        self.label_mic = tk.Label(
            mic_row, text="Listening for mic input\u2026",
            font=(font, c.get("mic_font_size")),
            fg=c.get("mic_text_color"), bg=bg,
            anchor="w", wraplength=wrap, justify="left",
        )
        self.label_mic.pack(side="left", fill="x", expand=True)

        # ── Status / bottom bar ─────────────────────────────────────
        status_row = tk.Frame(self.container, bg=bg)
        status_row.pack(side="bottom", fill="x", pady=(4, 0))

        self.label_status = tk.Label(
            status_row,
            text="LOCKED \u2022 F8 Lock \u2022 F9 Hide \u2022 F10 Settings",
            font=(font, 8), fg=c.get("status_color"), bg=bg, anchor="w",
        )
        self.label_status.pack(side="left", fill="x", expand=True)

        # ✕ close button (always visible, even when locked)
        self.btn_close = tk.Label(
            status_row, text="\u2715", font=(font, 12, "bold"),
            fg=c.get("status_color"), bg=bg, cursor="hand2",
        )
        self.btn_close.pack(side="right", padx=(8, 0))
        self.btn_close.bind("<Button-1>", lambda e: self._request_close())

        # ⚙ gear button (always visible, even when locked)
        self.btn_settings = tk.Label(
            status_row, text="\u2699", font=(font, 13),
            fg=c.get("status_color"), bg=bg, cursor="hand2",
        )
        self.btn_settings.pack(side="right", padx=(8, 0))
        self.btn_settings.bind("<Button-1>", lambda e: self._open_settings())

        # ── Drag & resize bindings ──────────────────────────────────
        # Bind to every widget in the overlay so the entire area is draggable
        self._bind_drag_recursive(self.root)

    # ════════════════════════════════════════════════════════════════
    #  APPLY SETTINGS (live update)
    # ════════════════════════════════════════════════════════════════

    def _apply_settings(self):
        """Re-skin the overlay from current settings without rebuilding."""
        c = self.cfg
        bg = c.get("bg_color")
        font = c.get("font_family")
        gfz = c.get("game_font_size")
        mfz = c.get("mic_font_size")
        gc = c.get("game_text_color")
        mc = c.get("mic_text_color")
        ac = c.get("accent_color")
        sc_ = c.get("status_color")

        w = c.get("overlay_width")
        h = c.get("overlay_height")
        wrap = max(300, w - 80)

        # Geometry
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.root.attributes("-alpha", c.get("overlay_opacity"))

        # Colors and fonts
        for widget in (self.root, self.container):
            widget.configure(bg=bg)
        for widget_list in (self.container.winfo_children(),):
            for child in widget_list:
                try:
                    child.configure(bg=bg)
                except tk.TclError:
                    pass
                for grandchild in child.winfo_children():
                    try:
                        grandchild.configure(bg=bg)
                    except tk.TclError:
                        pass

        self.label_game.config(fg=gc, bg=bg, font=(font, gfz, "bold"), wraplength=wrap)
        self._game_icon.config(fg=gc, bg=bg)
        self.label_mic.config(fg=mc, bg=bg, font=(font, mfz), wraplength=wrap)
        self._mic_icon.config(fg=mc, bg=bg)
        self._sep.config(bg=ac)
        self.label_status.config(fg=sc_, bg=bg)
        self.btn_settings.config(fg=sc_, bg=bg)
        self.btn_close.config(fg=sc_, bg=bg)

    # ════════════════════════════════════════════════════════════════
    #  DRAG & RESIZE
    # ════════════════════════════════════════════════════════════════

    def set_on_close(self, callback):
        """Register a callback invoked when the user clicks the ✕ button."""
        self._on_close_callback = callback

    def _request_close(self):
        """Handle the ✕ close button click."""
        if self._on_close_callback:
            self._on_close_callback()
        else:
            self.stop()

    def _bind_drag_recursive(self, widget):
        """Bind drag/resize events to a widget and all its descendants."""
        # Skip the gear / close buttons — they have their own click handlers
        if widget is self.btn_settings or widget is self.btn_close:
            return
        widget.bind("<Button-1>", self._on_press)
        widget.bind("<B1-Motion>", self._on_motion)
        widget.bind("<ButtonRelease-1>", self._on_release)
        widget.bind("<Motion>", self._on_hover)
        for child in widget.winfo_children():
            self._bind_drag_recursive(child)

    def _edge_at(self, x_root, y_root):
        """Return which edge/corner the cursor is near, or None.
        Uses screen (root) coordinates for consistency across child widgets."""
        rx = self.root.winfo_rootx()
        ry = self.root.winfo_rooty()
        w = self.root.winfo_width()
        h = self.root.winfo_height()

        # Local position relative to the overlay window
        lx = x_root - rx
        ly = y_root - ry

        edge = ""
        if ly <= _GRIP:
            edge += "n"
        elif ly >= h - _GRIP:
            edge += "s"
        if lx <= _GRIP:
            edge += "w"
        elif lx >= w - _GRIP:
            edge += "e"
        return edge or None

    def _on_hover(self, event):
        if self.locked:
            self.root.config(cursor="")
            return
        edge = self._edge_at(event.x_root, event.y_root)
        cursors = {
            "n": "top_side", "s": "bottom_side",
            "w": "left_side", "e": "right_side",
            "nw": "top_left_corner", "ne": "top_right_corner",
            "sw": "bottom_left_corner", "se": "bottom_right_corner",
        }
        self.root.config(cursor=cursors.get(edge, "fleur"))  # fleur = move

    def _on_press(self, event):
        if self.locked:
            return
        edge = self._edge_at(event.x_root, event.y_root)
        if edge:
            self._resizing = True
            self._resize_edge = edge
        else:
            self._resizing = False
        self._drag_x = event.x_root
        self._drag_y = event.y_root
        # Capture current geometry as the baseline for both drag and resize
        geo = self.root.winfo_geometry()  # "WxH+X+Y"
        dims, pos = geo.split("+", 1)
        parts = pos.split("+")
        self._orig_w, self._orig_h = [int(v) for v in dims.split("x")]
        self._orig_x, self._orig_y = int(parts[0]), int(parts[1])

    def _on_motion(self, event):
        if self.locked:
            return
        dx = event.x_root - self._drag_x
        dy = event.y_root - self._drag_y

        if self._resizing:
            nw, nh, nx, ny = self._orig_w, self._orig_h, self._orig_x, self._orig_y
            edge = self._resize_edge

            if "e" in edge:
                nw = max(300, self._orig_w + dx)
            if "w" in edge:
                nw = max(300, self._orig_w - dx)
                nx = self._orig_x + dx
            if "s" in edge:
                nh = max(80, self._orig_h + dy)
            if "n" in edge:
                nh = max(80, self._orig_h - dy)
                ny = self._orig_y + dy

            self.root.geometry(f"{nw}x{nh}+{nx}+{ny}")
            self.cfg.set("overlay_width", nw)
            self.cfg.set("overlay_height", nh)

            # Update wrap width live
            wrap = max(300, nw - 80)
            self.label_game.config(wraplength=wrap)
            self.label_mic.config(wraplength=wrap)
        else:
            # Drag / move — use stored origin for reliability
            nx = self._orig_x + dx
            ny = self._orig_y + dy
            self.root.geometry(f"+{nx}+{ny}")

    def _on_release(self, event):
        self._resizing = False
        self._resize_edge = None

    # ════════════════════════════════════════════════════════════════
    #  HOTKEYS
    # ════════════════════════════════════════════════════════════════

    def _setup_hotkeys(self):
        try:
            import keyboard
            keyboard.add_hotkey("F8", lambda: self.root.after(0, self._toggle_lock))
            keyboard.add_hotkey("F9", lambda: self.root.after(0, self._toggle_visible))
            keyboard.add_hotkey("F10", lambda: self.root.after(0, self._open_settings))
        except ImportError:
            print("[Overlay] 'keyboard' package missing – hotkeys disabled.")
        except Exception as e:
            print(f"[Overlay] Hotkey error: {e}")

    def _toggle_lock(self):
        self.locked = not self.locked
        if self.locked:
            self._apply_click_through()
            self.label_status.config(
                text="LOCKED \u2022 F8 Lock \u2022 F9 Hide \u2022 F10 Settings"
            )
        else:
            self._remove_click_through()
            self.label_status.config(
                text="UNLOCKED \u2013 Drag edges to resize \u2022 F8 Lock \u2022 F10 Settings"
            )

    def _toggle_visible(self):
        self.visible = not self.visible
        if self.visible:
            self.root.deiconify()
        else:
            self.root.withdraw()

    def _open_settings(self):
        # Temporarily unlock so the settings window is usable
        was_locked = self.locked
        if was_locked:
            self.locked = False
            self._remove_click_through()
        self._settings_win.open(self.root)

    # ════════════════════════════════════════════════════════════════
    #  CLICK-THROUGH (Windows)
    # ════════════════════════════════════════════════════════════════

    def _apply_click_through(self):
        try:
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
            style |= 0x80000 | 0x20
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, style)
        except Exception:
            pass

    def _remove_click_through(self):
        try:
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
            style &= ~0x20
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, style)
        except Exception:
            pass

    # ════════════════════════════════════════════════════════════════
    #  THREAD-SAFE TEXT UPDATES
    # ════════════════════════════════════════════════════════════════

    def _process_queue(self):
        try:
            while True:
                msg_type, text = self.queue.get_nowait()
                if msg_type == "game":
                    self.label_game.config(
                        text=text,
                        fg=self.cfg.get("game_text_color"),
                        font=(self.cfg.get("font_family"),
                              self.cfg.get("game_font_size"), "bold"),
                    )
                elif msg_type == "game_preview":
                    # Streaming preview — dimmed italic
                    base_color = self.cfg.get("game_text_color")
                    self.label_game.config(
                        text=f"\u23f3 {text}",
                        fg=self._dim_color(base_color),
                        font=(self.cfg.get("font_family"),
                              self.cfg.get("game_font_size"), "italic"),
                    )
                elif msg_type == "mic":
                    self.label_mic.config(
                        text=text,
                        fg=self.cfg.get("mic_text_color"),
                        font=(self.cfg.get("font_family"),
                              self.cfg.get("mic_font_size")),
                    )
                elif msg_type == "mic_preview":
                    base_color = self.cfg.get("mic_text_color")
                    self.label_mic.config(
                        text=f"\u23f3 {text}",
                        fg=self._dim_color(base_color),
                        font=(self.cfg.get("font_family"),
                              self.cfg.get("mic_font_size"), "italic"),
                    )
                elif msg_type == "status":
                    self.label_status.config(text=text)
        except queue.Empty:
            pass
        if self.root.winfo_exists():
            self.root.after(80, self._process_queue)

    def _dim_color(self, hex_color):
        """Return a dimmer version of a hex color for preview text."""
        try:
            r = int(hex_color[1:3], 16)
            g = int(hex_color[3:5], 16)
            b = int(hex_color[5:7], 16)
            r = int(r * 0.55)
            g = int(g * 0.55)
            b = int(b * 0.55)
            return f"#{r:02x}{g:02x}{b:02x}"
        except Exception:
            return "#555555"

    def update_game_text(self, text):
        """Thread-safe: final translated game text."""
        self.queue.put(("game", text))

    def update_game_preview(self, text):
        """Thread-safe: streaming preview (partial transcription, dimmed)."""
        self.queue.put(("game_preview", text))

    def update_mic_text(self, text):
        """Thread-safe: final translated mic text."""
        self.queue.put(("mic", text))

    def update_mic_preview(self, text):
        """Thread-safe: streaming preview for mic."""
        self.queue.put(("mic_preview", text))

    def update_status(self, text):
        """Thread-safe: update status bar."""
        self.queue.put(("status", text))

    # ════════════════════════════════════════════════════════════════
    #  HELPERS
    # ════════════════════════════════════════════════════════════════

    def is_streaming_enabled(self):
        return self.cfg.get("streaming_enabled")

    def streaming_interval_ms(self):
        return self.cfg.get("streaming_interval_ms")

    # ════════════════════════════════════════════════════════════════
    #  LIFECYCLE
    # ════════════════════════════════════════════════════════════════

    def start(self):
        self.root.mainloop()

    def _keep_on_top(self):
        """Re-assert topmost every 3s so the overlay stays above borderless games."""
        try:
            if self.root.winfo_exists():
                self.root.attributes("-topmost", False)
                self.root.attributes("-topmost", True)
                self.root.after(3000, self._keep_on_top)
        except Exception:
            pass

    def stop(self):
        # Save position on exit
        try:
            self.cfg.set("overlay_x", self.root.winfo_x())
            self.cfg.set("overlay_y", self.root.winfo_y())
            self.cfg.set("overlay_width", self.root.winfo_width())
            self.cfg.set("overlay_height", self.root.winfo_height())
            self.cfg.save()
        except Exception:
            pass
        try:
            self.root.quit()
            self.root.destroy()
        except Exception:
            pass
