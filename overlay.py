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
import time

from settings import Settings
from settings_ui import SettingsWindow
from locales import t, set_language
from logger_config import get_logger

logger = get_logger("Overlay")

# Resize handle size in pixels
_GRIP = 8

# Chromakey colour – transparent via -transparentcolor.  Must NOT match
# any text colour or accent colour used in the UI.
_CHROMA = "#010101"


class OverlayWindow:
    def __init__(self):
        self.cfg = Settings()

        # Set UI language from config
        app_lang = self.cfg.get("app_language")
        set_language("ru" if app_lang == "russian" else "en")

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
        self._on_restart_callback = None  # set by main app for restart
        self._bg_win = None              # background window (created in _build)
        
        # ── Chat log history ── (replaces old current/prev model)
        # Each entry: {"text": str, "timestamp": float}
        self._game_history = []
        self._game_labels = []          # tk.Label references in the overlay
        self._game_preview_text = ""     # current streaming preview (not in history)
        
        # Mic still uses simple current/prev (only your voice)
        self._current_mic_final = ""
        self._prev_mic_final = ""

        # Settings window (lazy)
        self._settings_win = SettingsWindow(
            self.cfg,
            on_apply_callback=self._apply_settings,
            on_restart_callback=lambda: self._request_restart(),
        )

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
        popup.title(t("welcome_title"))
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
        tk.Label(popup, text=t("welcome_title"),
                 font=("Segoe UI", 14, "bold"), fg=ACCENT, bg=BG).pack(pady=(18, 6))

        # Body
        src = self.cfg.get("source_language")
        if src == "russian":
            direction_text = (
                f"{t('welcome_created_for')}\n"
                f"{t('welcome_your_lang_ru')}\n"
                f"{t('welcome_game_ru')}\n"
                f"{t('welcome_mic_ru')}"
            )
        else:
            direction_text = (
                f"{t('welcome_created_for')}\n"
                f"{t('welcome_your_lang')}\n"
                f"{t('welcome_game_en')}\n"
                f"{t('welcome_mic_en')}"
            )

        info = (
            f"{direction_text}\n\n"
            f"{t('welcome_hotkeys_label')}\n"
            f"  {t('welcome_f8')}\n"
            f"  {t('welcome_f9')}\n"
            f"  {t('welcome_f10')}\n\n"
            f"{t('welcome_change_lang')}"
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

        tk.Button(popup, text=t("welcome_got_it"), font=("Segoe UI", 11, "bold"),
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

        # ── Geometry (shared by both windows) ─────────────────────
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
        geo = f"{w}x{h}+{x}+{y}"

        # ── Background window (semi-transparent backdrop) ─────────
        self._bg_win = tk.Toplevel(self.root)
        self._bg_win.overrideredirect(True)
        self._bg_win.attributes("-topmost", True)
        self._bg_win.attributes("-alpha", c.get("bg_opacity"))
        self._bg_win.configure(bg=bg)
        self._bg_win.geometry(geo)
        # bg window is ALWAYS click-through
        self.root.after(50, lambda: self._apply_click_through_win(self._bg_win))

        # ── Main / text window (chromakey bg → transparent) ───────
        self.root.title("Translator")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", c.get("text_opacity"))
        self.root.configure(bg=_CHROMA)
        self.root.attributes("-transparentcolor", _CHROMA)
        self.root.geometry(geo)

        font = c.get("font_family")

        # ── Main container ──────────────────────────────────────────
        # All widget backgrounds use _CHROMA so they appear transparent;
        # the coloured backdrop is provided by _bg_win.
        self.container = tk.Frame(self.root, bg=_CHROMA, padx=14, pady=6)
        self.container.pack(fill="both", expand=True)

        wrap = max(300, w - 80)

        # ── Chat log frame (scrolling game translation history) ──
        self._chat_frame = tk.Frame(self.container, bg=_CHROMA)
        self._chat_frame.pack(fill="both", expand=True)
        
        max_lines = c.get("chat_log_lines")
        gfz = c.get("game_font_size")
        gc = c.get("game_text_color")
        
        self._game_labels = []
        for i in range(max_lines):
            row = tk.Frame(self._chat_frame, bg=_CHROMA)
            row.pack(fill="x", anchor="sw", pady=(0, 1))
            
            # Arrow icon only for the newest line (index 0 = oldest, last = newest)
            icon = tk.Label(
                row, text="", font=(font, 9),
                fg=gc, bg=_CHROMA, width=2, anchor="e",
            )
            icon.pack(side="left", padx=(0, 2))
            
            label = tk.Label(
                row, text="",
                font=(font, gfz),
                fg=gc, bg=_CHROMA,
                anchor="w", wraplength=wrap, justify="left",
            )
            label.pack(side="left", fill="x", expand=True)
            
            self._game_labels.append({"row": row, "icon": icon, "label": label})

        # ── Separator ──────────────────────────────────────────────
        self._sep = tk.Frame(self.container, bg=c.get("accent_color"), height=1)
        self._sep.pack(fill="x", pady=2)

        # ── Mic text rows ───────────────────────────────────────
        # Previous mic text (dimmed)
        prev_mic_row = tk.Frame(self.container, bg=_CHROMA)
        prev_mic_row.pack(fill="x", pady=(2, 1))
        
        self.label_prev_mic = tk.Label(
            prev_mic_row, text="",
            font=(font, max(8, c.get("mic_font_size") - 2)),
            fg=self._dim_color(c.get("mic_text_color")), bg=_CHROMA,
            anchor="w", wraplength=wrap, justify="left",
        )
        self.label_prev_mic.pack(side="left", fill="x", expand=True, padx=(20, 0))
        
        # Current mic text
        mic_row = tk.Frame(self.container, bg=_CHROMA)
        mic_row.pack(fill="x", pady=(0, 0))

        self._mic_icon = tk.Label(
            mic_row, text="\u25c0", font=(font, 9),
            fg=c.get("mic_text_color"), bg=_CHROMA,
        )
        self._mic_icon.pack(side="left", padx=(0, 6))

        self.label_mic = tk.Label(
            mic_row, text=t("listening_mic"),
            font=(font, c.get("mic_font_size")),
            fg=c.get("mic_text_color"), bg=_CHROMA,
            anchor="w", wraplength=wrap, justify="left",
        )
        self.label_mic.pack(side="left", fill="x", expand=True)

        # ── Status / bottom bar ─────────────────────────────────────
        status_row = tk.Frame(self.container, bg=_CHROMA)
        status_row.pack(side="bottom", fill="x", pady=(4, 0))

        self.label_status = tk.Label(
            status_row,
            text=t("status_locked"),
            font=(font, 8), fg=c.get("status_color"), bg=_CHROMA, anchor="w",
        )
        self.label_status.pack(side="left", fill="x", expand=True)

        # ✕ close button (always visible, even when locked)
        self.btn_close = tk.Label(
            status_row, text="\u2715", font=(font, 12, "bold"),
            fg=c.get("status_color"), bg=_CHROMA, cursor="hand2",
        )
        self.btn_close.pack(side="right", padx=(8, 0))
        self.btn_close.bind("<Button-1>", lambda e: self._request_close())

        # ↻ restart button
        self.btn_restart = tk.Label(
            status_row, text="\u21bb", font=(font, 13),
            fg=c.get("status_color"), bg=_CHROMA, cursor="hand2",
        )
        self.btn_restart.pack(side="right", padx=(8, 0))
        self.btn_restart.bind("<Button-1>", lambda e: self._request_restart())

        # ⚙ gear button (always visible, even when locked)
        self.btn_settings = tk.Label(
            status_row, text="\u2699", font=(font, 13),
            fg=c.get("status_color"), bg=_CHROMA, cursor="hand2",
        )
        self.btn_settings.pack(side="right", padx=(8, 0))
        self.btn_settings.bind("<Button-1>", lambda e: self._open_settings())

        # ── Drag & resize bindings ──────────────────────────────────
        # Bind to every widget in the overlay so the entire area is draggable
        self._bind_drag_recursive(self.root)

        # ── Start fade-out timer ────────────────────────────────────
        self.root.after(1000, self._tick_fade)

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

        # ── Geometry – sync both windows ──
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        geo = f"{w}x{h}+{x}+{y}"
        self.root.geometry(geo)
        self.root.attributes("-alpha", c.get("text_opacity"))
        if self._bg_win and self._bg_win.winfo_exists():
            self._bg_win.geometry(geo)
            self._bg_win.attributes("-alpha", c.get("bg_opacity"))
            self._bg_win.configure(bg=bg)

        # ── All widget backgrounds use _CHROMA (transparent) ──
        for widget in (self.root, self.container):
            widget.configure(bg=_CHROMA)
        for widget_list in (self.container.winfo_children(),):
            for child in widget_list:
                try:
                    child.configure(bg=_CHROMA)
                except tk.TclError:
                    pass
                for grandchild in child.winfo_children():
                    try:
                        grandchild.configure(bg=_CHROMA)
                    except tk.TclError:
                        pass

        # Update chat log labels
        for entry in self._game_labels:
            entry["row"].config(bg=_CHROMA)
            entry["icon"].config(fg=gc, bg=_CHROMA)
            entry["label"].config(bg=_CHROMA, wraplength=wrap, font=(font, gfz))
        self._render_chat_log()
        
        self.label_mic.config(fg=mc, bg=_CHROMA, font=(font, mfz), wraplength=wrap)
        self._mic_icon.config(fg=mc, bg=_CHROMA)
        self.label_prev_mic.config(fg=self._dim_color(mc), bg=_CHROMA, font=(font, max(8, mfz - 2)), wraplength=wrap)
        self._sep.config(bg=ac)
        self.label_status.config(fg=sc_, bg=_CHROMA)
        self.btn_settings.config(fg=sc_, bg=_CHROMA)
        self.btn_close.config(fg=sc_, bg=_CHROMA)
        self.btn_restart.config(fg=sc_, bg=_CHROMA)

    # ════════════════════════════════════════════════════════════════
    #  DRAG & RESIZE
    # ════════════════════════════════════════════════════════════════

    def set_on_close(self, callback):
        """Register a callback invoked when the user clicks the ✕ button."""
        self._on_close_callback = callback

    def set_on_restart(self, callback):
        """Register a callback invoked when the user clicks the ↻ button."""
        self._on_restart_callback = callback

    def _request_close(self):
        """Handle the ✕ close button click."""
        if self._on_close_callback:
            self._on_close_callback()
        else:
            self.stop()

    def _request_restart(self):
        """Handle the ↻ restart button click."""
        if self._on_restart_callback:
            self._on_restart_callback()
        else:
            self.stop()

    def _bind_drag_recursive(self, widget):
        """Bind drag/resize events to a widget and all its descendants."""
        # Skip the gear / close buttons — they have their own click handlers
        if widget in (self.btn_settings, self.btn_close, self.btn_restart):
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

            geo = f"{nw}x{nh}+{nx}+{ny}"
            self.root.geometry(geo)
            self._sync_bg_geo(geo)
            self.cfg.set("overlay_width", nw)
            self.cfg.set("overlay_height", nh)

            # Update wrap width live
            wrap = max(300, nw - 80)
            for entry in self._game_labels:
                entry["label"].config(wraplength=wrap)
            self.label_mic.config(wraplength=wrap)
        else:
            # Drag / move — use stored origin for reliability
            nx = self._orig_x + dx
            ny = self._orig_y + dy
            geo = f"+{nx}+{ny}"
            self.root.geometry(geo)
            self._sync_bg_geo(geo)

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
            logger.warning("'keyboard' package missing – hotkeys disabled.")
        except Exception as e:
            logger.error("Hotkey error: %s", e)

    def _toggle_lock(self):
        self.locked = not self.locked
        bg = self.cfg.get("bg_color")
        if self.locked:
            # Re-enable two-window transparency
            self._apply_click_through()
            self.root.attributes("-transparentcolor", _CHROMA)
            self.root.attributes("-alpha", self.cfg.get("text_opacity"))
            self._set_all_widget_bg(_CHROMA)
            if self._bg_win and self._bg_win.winfo_exists():
                self._bg_win.deiconify()
                self._apply_click_through_win(self._bg_win)
            self.label_status.config(text=t("status_locked"))
        else:
            # Disable two-window mode so drag/resize works
            self._remove_click_through()
            self.root.attributes("-transparentcolor", "")
            self.root.attributes("-alpha", max(self.cfg.get("bg_opacity"),
                                                 self.cfg.get("text_opacity")))
            self._set_all_widget_bg(bg)
            if self._bg_win and self._bg_win.winfo_exists():
                self._bg_win.withdraw()
            self.label_status.config(text=t("status_unlocked"))

    def _toggle_visible(self):
        self.visible = not self.visible
        if self.visible:
            self.root.deiconify()
            if self._bg_win and self._bg_win.winfo_exists():
                self._bg_win.deiconify()
                self._apply_click_through_win(self._bg_win)
        else:
            self.root.withdraw()
            if self._bg_win and self._bg_win.winfo_exists():
                self._bg_win.withdraw()

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
        self._apply_click_through_win(self.root)

    def _remove_click_through(self):
        self._remove_click_through_win(self.root)

    @staticmethod
    def _apply_click_through_win(win):
        """Set WS_EX_TRANSPARENT + WS_EX_LAYERED on a window."""
        try:
            hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
            style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
            style |= 0x80000 | 0x20
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, style)
        except Exception:
            pass

    @staticmethod
    def _remove_click_through_win(win):
        try:
            hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
            style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
            style &= ~0x20
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, style)
        except Exception:
            pass

    def _sync_bg_geo(self, geometry_str):
        """Keep the background window aligned with the main window."""
        try:
            if self._bg_win and self._bg_win.winfo_exists():
                self._bg_win.geometry(geometry_str)
        except Exception:
            pass

    def _set_all_widget_bg(self, color):
        """Switch every widget background between _CHROMA and bg_color."""
        for w in (self.root, self.container, self._chat_frame):
            try:
                w.configure(bg=color)
            except Exception:
                pass
        for entry in self._game_labels:
            for key in ("row", "icon", "label"):
                try:
                    entry[key].configure(bg=color)
                except Exception:
                    pass
        for w in (self.label_mic, self._mic_icon, self.label_prev_mic,
                  self.label_status, self.btn_settings, self.btn_close,
                  self.btn_restart):
            try:
                w.configure(bg=color)
            except Exception:
                pass
        # Walk any remaining frames (mic_row, status_row, prev_mic_row)
        for child in self.container.winfo_children():
            try:
                child.configure(bg=color)
            except tk.TclError:
                pass

    # ════════════════════════════════════════════════════════════════
    #  THREAD-SAFE TEXT UPDATES
    # ════════════════════════════════════════════════════════════════

    def _process_queue(self):
        try:
            while True:
                msg_type, text = self.queue.get_nowait()
                logger.debug("Processing queue message: type=%s, text=%s",
                             msg_type, text[:50] if text else "(empty)")

                if msg_type == "game":
                    # ── Final translation → append to chat history ──
                    max_lines = self.cfg.get("chat_log_lines")
                    self._game_history.append({
                        "text": text,
                        "timestamp": time.time(),
                    })
                    # Trim oldest entries that exceed visible lines
                    if len(self._game_history) > max_lines:
                        self._game_history = self._game_history[-max_lines:]
                    # Clear any lingering preview
                    self._game_preview_text = ""
                    self._render_chat_log()
                    logger.info("Chat log updated (%d lines): %s",
                                len(self._game_history),
                                text[:50])

                elif msg_type == "game_preview":
                    # Streaming preview — shows in the next available slot
                    if text and text.strip():
                        self._game_preview_text = text
                    else:
                        self._game_preview_text = ""
                    self._render_chat_log()

                elif msg_type == "mic":
                    if not self.cfg.get("show_mic_overlay"):
                        continue
                    if self._current_mic_final:
                        self._prev_mic_final = self._current_mic_final
                        self.label_prev_mic.config(
                            text=self._prev_mic_final,
                            fg=self._dim_color(self.cfg.get("mic_text_color")),
                            font=(self.cfg.get("font_family"),
                                  max(8, self.cfg.get("mic_font_size") - 2)),
                        )
                    self._current_mic_final = text
                    self.label_mic.config(
                        text=text,
                        fg=self.cfg.get("mic_text_color"),
                        font=(self.cfg.get("font_family"),
                              self.cfg.get("mic_font_size")),
                    )

                elif msg_type == "mic_preview":
                    if not self.cfg.get("show_mic_overlay"):
                        continue
                    if text and text.strip():
                        base_color = self.cfg.get("mic_text_color")
                        self.label_mic.config(
                            text=f"\u23f3 {text}",
                            fg=self._dim_color(base_color),
                            font=(self.cfg.get("font_family"),
                                  self.cfg.get("mic_font_size"), "italic"),
                        )
                    elif text == "":
                        if self._current_mic_final:
                            self.label_mic.config(
                                text=self._current_mic_final,
                                fg=self.cfg.get("mic_text_color"),
                                font=(self.cfg.get("font_family"),
                                      self.cfg.get("mic_font_size")),
                            )
                        else:
                            self.label_mic.config(
                                text="",
                                fg=self.cfg.get("mic_text_color"),
                                font=(self.cfg.get("font_family"),
                                      self.cfg.get("mic_font_size")),
                            )

                elif msg_type == "status":
                    self.label_status.config(text=text)
        except queue.Empty:
            pass
        except Exception as e:
            logger.error("Overlay queue error: %s", e)
        if self.root.winfo_exists():
            self.root.after(80, self._process_queue)

    # ────────────────────────────────────────────────────────────────
    #  CHAT LOG  rendering + fade
    # ────────────────────────────────────────────────────────────────

    def _render_chat_log(self):
        """Redraw all chat-log label widgets from self._game_history."""
        c = self.cfg
        font = c.get("font_family")
        gfz = c.get("game_font_size")
        base_color = c.get("game_text_color")
        fade_enabled = c.get("chat_fade_enabled")
        fade_sec = c.get("chat_line_duration_sec")
        max_lines = c.get("chat_log_lines")
        now = time.time()

        # Build display list: history lines + optional preview
        display = list(self._game_history[-max_lines:])  # oldest first
        show_preview = bool(self._game_preview_text)

        for idx, slot in enumerate(self._game_labels):
            hist_idx = idx  # 0 = oldest visual row, last = newest
            if hist_idx < len(display):
                entry = display[hist_idx]
                age = now - entry["timestamp"]

                # Newest entry in history?
                is_newest = (hist_idx == len(display) - 1) and not show_preview

                # Fade colour: full brightness → dim over fade_sec
                if fade_enabled and fade_sec > 0:
                    ratio = max(0.0, min(1.0, age / fade_sec))
                    color = self._fade_color(base_color, ratio)
                else:
                    color = base_color

                slot["label"].config(
                    text=entry["text"],
                    fg=color,
                    font=(font, gfz, "bold") if is_newest else (font, max(8, gfz - 1)),
                )
                slot["icon"].config(
                    text="\u25b6" if is_newest else "",
                    fg=color,
                )
            elif hist_idx == len(display) and show_preview:
                # Show streaming preview in the slot right after history
                slot["label"].config(
                    text=f"\u23f3 {self._game_preview_text}",
                    fg=self._dim_color(base_color),
                    font=(font, gfz, "italic"),
                )
                slot["icon"].config(text="", fg=base_color)
            else:
                # Empty slot
                slot["label"].config(text="", fg=base_color)
                slot["icon"].config(text="", fg=base_color)

    def _tick_fade(self):
        """Periodic timer: update colours for age-based fade and prune old lines."""
        try:
            if not self.root.winfo_exists():
                return
            fade_enabled = self.cfg.get("chat_fade_enabled")
            fade_sec = self.cfg.get("chat_line_duration_sec")

            if fade_enabled and fade_sec > 0:
                now = time.time()
                # Remove lines that have fully faded out
                self._game_history = [
                    e for e in self._game_history
                    if (now - e["timestamp"]) < fade_sec
                ]
                self._render_chat_log()

            self.root.after(1000, self._tick_fade)
        except Exception:
            pass

    def _fade_color(self, hex_color, ratio):
        """Blend hex_color toward dark (#111) by ratio (0=full, 1=invisible)."""
        try:
            r = int(hex_color[1:3], 16)
            g = int(hex_color[3:5], 16)
            b = int(hex_color[5:7], 16)
            # Blend toward very dark background
            r = int(r * (1 - ratio * 0.85))
            g = int(g * (1 - ratio * 0.85))
            b = int(b * (1 - ratio * 0.85))
            return f"#{max(0,r):02x}{max(0,g):02x}{max(0,b):02x}"
        except Exception:
            return "#555555"

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
        logger.info("update_game_text called with: %s", text[:50] if text else "(empty)")
        self.queue.put(("game", text))

    def update_game_preview(self, text):
        """Thread-safe: streaming preview (partial transcription, dimmed)."""
        logger.debug("update_game_preview called with: %s", text[:50] if text else "(empty)")
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
                # bg window first so root stays on top
                if self._bg_win and self._bg_win.winfo_exists():
                    self._bg_win.attributes("-topmost", False)
                    self._bg_win.attributes("-topmost", True)
                    # Re-apply click-through (toggling topmost can reset it)
                    self._apply_click_through_win(self._bg_win)
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
            if self._bg_win and self._bg_win.winfo_exists():
                self._bg_win.destroy()
        except Exception:
            pass
        try:
            self.root.quit()
            self.root.destroy()
        except Exception:
            pass
