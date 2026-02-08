# WindowMgrUsage

Tools for monitoring window usage and displaying live stock data on Linux/GNOME (X11).

## Stock Ticker Overlay

A transparent scrolling stock ticker that sits at the top of your screen, just below the GNOME panel.

### Features

- Transparent overlay, full screen width, always on top
- Scrolling stock symbols colored green (up) or red (down) with price and daily % change
- Date and time displayed before each ticker loop
- Live data from Yahoo Finance, refreshed every 15 minutes
- Left-click settings menu to adjust:
  - Font size (16, 20, 28, 32)
  - Scroll speed (Slow, Medium, Fast, Very Fast)
  - Background opacity
  - Refresh interval (5, 15, 30, 60 min)
  - Stock symbols
- Right-click to quit
- Settings persist across restarts (`.ticker-config.json`)

### Requirements

- Python 3.10+
- GTK3 with GObject Introspection (`python3-gi`)
- `curl_cffi` (installed automatically with yfinance)

### Setup

```bash
# Create a venv with access to system GTK3 bindings
python3 -m venv venv --system-site-packages

# Install dependencies
venv/bin/pip install yfinance
```

### Usage

```bash
venv/bin/python stock-ticker.py
```

### Default Symbols

AAPL, GOOGL, MSFT, AMZN, TSLA, META, NVDA, SPY, QQQ, BTC-USD

Edit symbols via the left-click settings menu or by modifying `.ticker-config.json`.

---

## Window Usage Tracker

A bash script that tracks how long each application window is in focus.

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
