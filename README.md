# WindowMgrUsage

Tools for monitoring window usage and displaying live stock data. Supports Linux/GNOME (X11) and macOS.

## Stock Ticker Overlay

A transparent scrolling stock ticker that sits at the top of your screen, just below the system panel/menu bar.

### Features

- Transparent overlay, full screen width, always on top
- Reserves screen space via `_NET_WM_STRUT_PARTIAL` so maximized/tiled windows won't overlap the ticker (Linux/X11 only)
- Continuous seamless scrolling across the full screen width
- Scrolling stock symbols colored green (up), red (down), or gray (flat) with price and daily % change
- Exchange market timestamp (e.g. "Fri Feb 06 04:00 PM EST") displayed before each ticker loop
- Live data from Yahoo Finance chart API via `curl_cffi` (browser TLS impersonation), refreshed every 15 minutes
- Left-click settings menu to adjust:
  - Font size (16, 20, 28, 32)
  - Scroll speed (Slow, Medium, Fast, Very Fast)
  - Background opacity (Light, Medium, Dark, Solid)
  - Refresh interval (5, 15, 30, 60 min)
  - Stock symbols (add/remove via dialog)
  - Refresh now
  - Quit
- Right-click to quit
- All settings persist across restarts (`.ticker-config.json`)

### Requirements

- Python 3.10+
- GTK3 with GObject Introspection
- `curl_cffi`

### Setup (Linux)

```bash
# Install system dependencies (Debian/Ubuntu)
sudo apt install python3-gi gir1.2-gtk-3.0

# Create a venv with access to system GTK3 bindings
python3 -m venv venv --system-site-packages

# Install Python dependencies
venv/bin/pip install -r requirements.txt
```

### Setup (macOS)

```bash
# Install system dependencies via Homebrew
brew install gtk+3 pygobject3 gobject-introspection

# Create a venv and install Python dependencies
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

### Usage

**Linux:**

```bash
venv/bin/python stock-ticker.py
```

**macOS:**

```bash
venv/bin/python stock-ticker.py
```

The script automatically sets `DYLD_FALLBACK_LIBRARY_PATH` to find Homebrew's GTK3 shared libraries (via a one-time re-exec), so no manual environment variables are needed.

### macOS Notes

- The ticker uses the Quartz backend (no X11/XQuartz required)
- Screen space reservation (`_NET_WM_STRUT_PARTIAL`) is not available on macOS, so maximized windows may overlap the ticker
- The dyld warnings about `_CGLSetCurrentContext` on startup are harmless and can be ignored

### Default Symbols

AAPL, GOOGL, MSFT, AMZN, TSLA, META, NVDA, SPY, QQQ, BTC-USD

Edit symbols via the left-click settings menu or by modifying `.ticker-config.json`.

---

## Window Usage Tracker (Linux only)

A bash script that tracks how long each application window is in focus. Requires X11.

### Requirements

- `xdotool`
- `xprop`

### Usage

```bash
./track-usage.sh
```

Switch between windows while it runs, then press `Ctrl+C` to see a summary of time spent per application.

### Example Output

```
========================================
 Window Usage Summary
 Tracked for: 0h 15m 32s
========================================
TIME        APPLICATION               LAST TITLE
----        -----------               ----------
0h 08m 12s  firefox                   GitHub - sbj-ee/WindowMgrUsage
0h 04m 45s  Gnome-terminal            ~/Development
0h 02m 35s  Code                      stock-ticker.py - VSCode
========================================
```
