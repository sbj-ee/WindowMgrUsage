#!/usr/bin/env python3
"""
Transparent scrolling stock ticker overlay for the top of the screen.
Uses Yahoo Finance chart API for price data, GTK3+Cairo for rendering.
Left-click for settings, right-click to quit.
"""

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('PangoCairo', '1.0')
from gi.repository import Gtk, Gdk, GLib, Pango, PangoCairo
import cairo
import threading
import time
import signal
import sys
import subprocess
import os
import json as jsonlib
from datetime import datetime
from curl_cffi import requests

# ── Defaults ─────────────────────────────────────────────────────────────────

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".ticker-config.json")

DEFAULTS = {
    "symbols": ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA",
                 "META", "NVDA", "SPY", "QQQ", "BTC-USD"],
    "ticker_font_size": 20,
    "scroll_speed": 1,
    "fps": 40,
    "item_gap": 40,
    "bg_alpha": 0.55,
    "update_interval_min": 15,
}

COLOR_UP   = (0.0, 0.9, 0.2)
COLOR_DOWN = (0.9, 0.15, 0.15)
COLOR_FLAT = (0.7, 0.7, 0.7)

MAX_RETRIES = 3
RETRY_DELAY = 30

YAHOO_CHART_URL = "https://query2.finance.yahoo.com/v8/finance/chart/{symbol}?range=5d&interval=1d"
YAHOO_HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0"}


# ── Runtime config ───────────────────────────────────────────────────────────

class Config:
    """Mutable runtime configuration with JSON persistence."""

    def __init__(self):
        self.symbols = list(DEFAULTS["symbols"])
        self.ticker_font_size = DEFAULTS["ticker_font_size"]
        self.scroll_speed = DEFAULTS["scroll_speed"]
        self.fps = DEFAULTS["fps"]
        self.item_gap = DEFAULTS["item_gap"]
        self.bg_alpha = DEFAULTS["bg_alpha"]
        self.update_interval_min = DEFAULTS["update_interval_min"]
        self.load()

    @property
    def price_font_size(self):
        return max(10, self.ticker_font_size - 6)

    @property
    def bar_height(self):
        return self.ticker_font_size + 24

    def load(self):
        try:
            with open(CONFIG_PATH) as f:
                d = jsonlib.load(f)
            for k, v in d.items():
                if hasattr(self, k):
                    setattr(self, k, v)
        except (FileNotFoundError, jsonlib.JSONDecodeError):
            pass

    def save(self):
        d = {
            "symbols": self.symbols,
            "ticker_font_size": self.ticker_font_size,
            "scroll_speed": self.scroll_speed,
            "fps": self.fps,
            "item_gap": self.item_gap,
            "bg_alpha": self.bg_alpha,
            "update_interval_min": self.update_interval_min,
        }
        with open(CONFIG_PATH, "w") as f:
            jsonlib.dump(d, f, indent=2)


# ── Stock data ───────────────────────────────────────────────────────────────

class StockStore:
    """Fetches and stores stock quotes via Yahoo Finance chart API."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.lock = threading.Lock()
        self.quotes = []
        self.session = requests.Session(impersonate="chrome")
        self.session.headers.update(YAHOO_HEADERS)

    def fetch(self):
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                new_quotes = self._fetch_all()
                if new_quotes:
                    with self.lock:
                        self.quotes = new_quotes
                    print(f"[stock-ticker] fetched {len(new_quotes)} quotes", file=sys.stderr)
                    return
            except Exception as e:
                print(f"[stock-ticker] attempt {attempt}/{MAX_RETRIES}: {e}", file=sys.stderr)
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
        print("[stock-ticker] all attempts failed, keeping cached data", file=sys.stderr)

    def _fetch_all(self):
        new_quotes = []
        for sym in self.cfg.symbols:
            q = self._fetch_one(sym)
            if q is None:
                continue
            if q == "RATE_LIMITED":
                raise RuntimeError("rate limited (429)")
            new_quotes.append(q)
            time.sleep(0.5)
        return new_quotes

    def _fetch_one(self, symbol):
        url = YAHOO_CHART_URL.format(symbol=symbol)
        resp = self.session.get(url, timeout=10)
        if resp.status_code == 429:
            return "RATE_LIMITED"
        resp.raise_for_status()
        data = resp.json()
        result = data["chart"]["result"][0]
        closes = result["indicators"]["adjclose"][0]["adjclose"]
        closes = [c for c in closes if c is not None]
        if len(closes) < 2:
            return None
        cur = closes[-1]
        prev = closes[-2]
        change = cur - prev
        pct = (change / prev) * 100 if prev else 0
        return {
            "symbol": symbol, "price": cur,
            "change": change, "pct": pct, "up": change >= 0,
        }

    def get_quotes(self):
        with self.lock:
            return list(self.quotes)


# ── Settings menu ────────────────────────────────────────────────────────────

def build_settings_menu(win):
    """Build and return a Gtk.Menu for the left-click settings popup."""
    menu = Gtk.Menu()
    cfg = win.cfg

    # ── Font Size ──
    font_item = Gtk.MenuItem(label="Font Size")
    font_sub = Gtk.Menu()
    font_group = []
    for size in (16, 20, 28, 32):
        ri = Gtk.RadioMenuItem(label=str(size))
        if font_group:
            ri.join_group(font_group[0])
        font_group.append(ri)
        if size == cfg.ticker_font_size:
            ri.set_active(True)
        ri.connect("toggled", _on_font_size, win, size)
        font_sub.append(ri)
    font_item.set_submenu(font_sub)
    menu.append(font_item)

    # ── Scroll Speed ──
    speed_item = Gtk.MenuItem(label="Scroll Speed")
    speed_sub = Gtk.Menu()
    speed_group = []
    speeds = [("Slow", 0.5), ("Medium", 1), ("Fast", 2), ("Very Fast", 4)]
    for label, val in speeds:
        ri = Gtk.RadioMenuItem(label=label)
        if speed_group:
            ri.join_group(speed_group[0])
        speed_group.append(ri)
        if val == cfg.scroll_speed:
            ri.set_active(True)
        ri.connect("toggled", _on_scroll_speed, win, val)
        speed_sub.append(ri)
    speed_item.set_submenu(speed_sub)
    menu.append(speed_item)

    # ── Opacity ──
    opacity_item = Gtk.MenuItem(label="Opacity")
    opacity_sub = Gtk.Menu()
    opacity_group = []
    opacities = [("Light (25%)", 0.25), ("Medium (55%)", 0.55),
                 ("Dark (75%)", 0.75), ("Solid (90%)", 0.90)]
    for label, val in opacities:
        ri = Gtk.RadioMenuItem(label=label)
        if opacity_group:
            ri.join_group(opacity_group[0])
        opacity_group.append(ri)
        if abs(val - cfg.bg_alpha) < 0.05:
            ri.set_active(True)
        ri.connect("toggled", _on_opacity, win, val)
        opacity_sub.append(ri)
    opacity_item.set_submenu(opacity_sub)
    menu.append(opacity_item)

    # ── Update Interval ──
    interval_item = Gtk.MenuItem(label="Refresh Interval")
    interval_sub = Gtk.Menu()
    interval_group = []
    intervals = [("5 min", 5), ("15 min", 15), ("30 min", 30), ("60 min", 60)]
    for label, val in intervals:
        ri = Gtk.RadioMenuItem(label=label)
        if interval_group:
            ri.join_group(interval_group[0])
        interval_group.append(ri)
        if val == cfg.update_interval_min:
            ri.set_active(True)
        ri.connect("toggled", _on_interval, win, val)
        interval_sub.append(ri)
    interval_item.set_submenu(interval_sub)
    menu.append(interval_item)

    # ── Edit Symbols ──
    menu.append(Gtk.SeparatorMenuItem())
    sym_item = Gtk.MenuItem(label="Edit Symbols...")
    sym_item.connect("activate", _on_edit_symbols, win)
    menu.append(sym_item)

    # ── Refresh Now ──
    refresh_item = Gtk.MenuItem(label="Refresh Now")
    refresh_item.connect("activate", _on_refresh_now, win)
    menu.append(refresh_item)

    # ── Quit ──
    menu.append(Gtk.SeparatorMenuItem())
    quit_item = Gtk.MenuItem(label="Quit")
    quit_item.connect("activate", lambda *_: Gtk.main_quit())
    menu.append(quit_item)

    menu.show_all()
    return menu


def _on_font_size(item, win, size):
    if not item.get_active():
        return
    win.cfg.ticker_font_size = size
    win.apply_config()

def _on_scroll_speed(item, win, val):
    if not item.get_active():
        return
    win.cfg.scroll_speed = val
    win.cfg.save()

def _on_opacity(item, win, val):
    if not item.get_active():
        return
    win.cfg.bg_alpha = val
    win.cfg.save()

def _on_interval(item, win, val):
    if not item.get_active():
        return
    win.cfg.update_interval_min = val
    win.apply_config()

def _on_refresh_now(item, win):
    threading.Thread(target=win._do_fetch, daemon=True).start()

def _on_edit_symbols(item, win):
    dialog = Gtk.Dialog(
        title="Edit Symbols",
        parent=win,
        flags=Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
    )
    dialog.add_buttons(
        Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
        Gtk.STOCK_OK, Gtk.ResponseType.OK,
    )
    dialog.set_default_size(350, 200)

    # Override the dialog's visual to avoid inheriting the transparent one
    screen = Gdk.Screen.get_default()
    visual = screen.get_system_visual()
    dialog.set_visual(visual)
    dialog.set_app_paintable(False)

    content = dialog.get_content_area()
    content.set_spacing(8)
    content.set_margin_start(12)
    content.set_margin_end(12)
    content.set_margin_top(8)

    label = Gtk.Label(label="Enter stock symbols, one per line:")
    label.set_halign(Gtk.Align.START)
    content.add(label)

    scroll = Gtk.ScrolledWindow()
    scroll.set_vexpand(True)
    textview = Gtk.TextView()
    textview.set_wrap_mode(Gtk.WrapMode.WORD)
    buf = textview.get_buffer()
    buf.set_text("\n".join(win.cfg.symbols))
    scroll.add(textview)
    content.add(scroll)

    dialog.show_all()
    resp = dialog.run()

    if resp == Gtk.ResponseType.OK:
        start, end = buf.get_bounds()
        text = buf.get_text(start, end, False)
        symbols = [s.strip().upper() for s in text.split("\n") if s.strip()]
        if symbols:
            win.cfg.symbols = symbols
            win.store.cfg = win.cfg
            win.apply_config()
            threading.Thread(target=win._do_fetch, daemon=True).start()

    dialog.destroy()


# ── GTK Overlay Window ──────────────────────────────────────────────────────

class TickerWindow(Gtk.Window):
    def __init__(self, cfg, store):
        super().__init__(title="Stock Ticker")
        self.cfg = cfg
        self.store = store
        self.scroll_x = 0.0
        self.content_width = 0
        self._anim_source = None
        self._refresh_source = None

        screen = Gdk.Screen.get_default()
        display = Gdk.Display.get_default()
        monitor = display.get_primary_monitor() or display.get_monitor(0)
        geom = monitor.get_geometry()
        self.screen_width = geom.width
        self._geom = geom

        # Detect GNOME panel height from _NET_WORKAREA
        self.panel_height = 32
        try:
            out = subprocess.check_output(
                ["xprop", "-root", "_NET_WORKAREA"], text=True
            )
            vals = out.split("=")[1].strip().split(",")
            self.panel_height = int(vals[1].strip())
        except Exception:
            pass

        # Transparent RGBA visual
        visual = screen.get_rgba_visual()
        if visual:
            self.set_visual(visual)
        self.set_app_paintable(True)

        # Window behaviour
        self.set_decorated(False)
        self.set_keep_above(True)
        self.set_type_hint(Gdk.WindowTypeHint.DOCK)
        self.stick()

        # Drawing area
        self.drawing_area = Gtk.DrawingArea()
        self.drawing_area.connect("draw", self.on_draw)
        self.drawing_area.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.drawing_area.connect("button-press-event", self.on_click)
        self.add(self.drawing_area)

        # Apply initial layout & start timers
        self._apply_geometry()
        self._start_timers()

        # Initial data fetch
        GLib.idle_add(self._initial_fetch)

    def _apply_geometry(self):
        h = self.cfg.bar_height
        self.set_default_size(self.screen_width, h)
        self.set_size_request(self.screen_width, h)
        self.move(self._geom.x, self._geom.y + self.panel_height)

    def _start_timers(self):
        if self._anim_source:
            GLib.source_remove(self._anim_source)
        self._anim_source = GLib.timeout_add(1000 // self.cfg.fps, self.on_tick)

        if self._refresh_source:
            GLib.source_remove(self._refresh_source)
        self._refresh_source = GLib.timeout_add_seconds(
            self.cfg.update_interval_min * 60, self._periodic_fetch
        )

    def apply_config(self):
        """Re-apply config after a settings change."""
        self._apply_geometry()
        self._start_timers()
        self.cfg.save()
        self.resize(self.screen_width, self.cfg.bar_height)
        self.drawing_area.queue_draw()

    def _initial_fetch(self):
        threading.Thread(target=self._do_fetch, daemon=True).start()
        return False

    def _periodic_fetch(self):
        threading.Thread(target=self._do_fetch, daemon=True).start()
        return True

    def _do_fetch(self):
        self.store.fetch()
        GLib.idle_add(self.drawing_area.queue_draw)

    def on_tick(self):
        self.scroll_x -= self.cfg.scroll_speed
        # Reset once a full content width has scrolled by to avoid overflow
        if self.content_width > 0 and self.scroll_x <= -self.content_width:
            self.scroll_x += self.content_width
        self.drawing_area.queue_draw()
        return True

    def on_click(self, widget, event):
        if event.button == 1:  # left-click → settings
            menu = build_settings_menu(self)
            menu.popup_at_pointer(event)
        elif event.button == 3:  # right-click → quit
            Gtk.main_quit()

    # ── Drawing ──────────────────────────────────────────────────────────

    def on_draw(self, widget, cr):
        cfg = self.cfg
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0.05, 0.05, 0.1, cfg.bg_alpha)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)

        quotes = self.store.get_quotes()
        if not quotes:
            self._draw_loading(cr, cfg)
            return

        layout = PangoCairo.create_layout(cr)
        total_w = self._measure_content(layout, quotes, cfg)
        self.content_width = total_w

        # Tile enough copies to seamlessly fill the entire screen width
        if total_w > 0:
            start_x = self.scroll_x % total_w - total_w
            x = start_x
            while x < self.screen_width:
                self._draw_items(cr, quotes, x, cfg)
                x += total_w

    def _draw_loading(self, cr, cfg):
        layout = PangoCairo.create_layout(cr)
        font = Pango.FontDescription(f"Sans Bold {cfg.ticker_font_size}")
        layout.set_font_description(font)
        layout.set_text("Loading stock data...", -1)
        cr.set_source_rgba(0.7, 0.7, 0.7, 0.8)
        cr.move_to(20, (cfg.bar_height - cfg.ticker_font_size) / 2 - 2)
        PangoCairo.show_layout(cr, layout)

    def _get_timestamp(self):
        return datetime.now().strftime("%a %b %d  %I:%M %p")

    def _measure_content(self, layout, quotes, cfg):
        total = 0
        sym_font = Pango.FontDescription(f"Sans Bold {cfg.ticker_font_size}")
        price_font = Pango.FontDescription(f"Sans {cfg.price_font_size}")

        # Date/time prefix
        layout.set_font_description(price_font)
        layout.set_text(self._get_timestamp(), -1)
        ts_w, _ = layout.get_pixel_size()
        total += ts_w + cfg.item_gap

        for q in quotes:
            layout.set_font_description(sym_font)
            layout.set_text(q["symbol"], -1)
            sym_w, _ = layout.get_pixel_size()

            layout.set_font_description(price_font)
            arrow = "\u25B2" if q["up"] else "\u25BC"
            price_str = f" ${q['price']:.2f} {arrow}{abs(q['pct']):.1f}%"
            layout.set_text(price_str, -1)
            price_w, _ = layout.get_pixel_size()

            total += sym_w + price_w + cfg.item_gap
        return total

    def _draw_items(self, cr, quotes, x_start, cfg):
        x = x_start
        sym_font = Pango.FontDescription(f"Sans Bold {cfg.ticker_font_size}")
        price_font = Pango.FontDescription(f"Sans {cfg.price_font_size}")
        layout = PangoCairo.create_layout(cr)

        # Date/time prefix
        layout.set_font_description(price_font)
        ts_text = self._get_timestamp()
        layout.set_text(ts_text, -1)
        ts_w, ts_h = layout.get_pixel_size()
        y_ts = (cfg.bar_height - ts_h) / 2
        cr.set_source_rgba(0.8, 0.8, 0.8, 0.9)
        cr.move_to(x, y_ts)
        PangoCairo.show_layout(cr, layout)
        x += ts_w + cfg.item_gap

        for q in quotes:
            color = COLOR_UP if q["up"] else COLOR_DOWN
            if q["change"] == 0:
                color = COLOR_FLAT

            # Symbol
            layout.set_font_description(sym_font)
            layout.set_text(q["symbol"], -1)
            sym_w, sym_h = layout.get_pixel_size()
            y_sym = (cfg.bar_height - sym_h) / 2

            cr.set_source_rgb(*color)
            cr.move_to(x, y_sym)
            PangoCairo.show_layout(cr, layout)
            x += sym_w

            # Price + change
            layout.set_font_description(price_font)
            arrow = "\u25B2" if q["up"] else "\u25BC"
            price_str = f" ${q['price']:.2f} {arrow}{abs(q['pct']):.1f}%"
            layout.set_text(price_str, -1)
            price_w, price_h = layout.get_pixel_size()
            y_price = (cfg.bar_height - price_h) / 2

            cr.set_source_rgba(*color, 0.85)
            cr.move_to(x, y_price)
            PangoCairo.show_layout(cr, layout)
            x += price_w + cfg.item_gap


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    cfg = Config()
    store = StockStore(cfg)
    win = TickerWindow(cfg, store)
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
