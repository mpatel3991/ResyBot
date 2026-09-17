# ResyGrabber

An open-source tool that automatically books restaurant reservations on [Resy.com](https://resy.com). It monitors availability and grabs a table the moment one opens up — perfect for hard-to-get restaurants.

## Features

- **Web interface** — no terminal needed, runs in your browser
- **Auto-booking** — continuously polls Resy and books the first matching slot
- **Multiple time windows** — search for lunch AND dinner in one task (e.g., 12–2pm and 6–9pm)
- **Multiple date ranges** — search across non-consecutive dates (e.g., May 18–20 and May 25–30)
- **Table type filtering** — choose Dining Room, Bar, Kitchen Counter, etc.
- **Save & reuse tasks** — save reservation presets so you don't re-enter details every time
- **Multiple accounts** — manage several Resy accounts
- **Proxy support** — optional rotating proxies to avoid rate limits
- **Discord notifications** — get notified when a reservation is booked
- **Live log window** — watch the bot's activity in real time
- **One-click Mac launcher** — double-click to start everything

## Requirements

- **macOS** (the launcher is Mac-specific, but the bot itself works on any OS with Python)
- **Python 3.7+** (macOS comes with Python pre-installed)
- A **Resy.com account** with a payment method on file

## Setup (One Time)

1. **Download this project** — click the green "Code" button above, then "Download ZIP". Unzip it somewhere on your computer.

2. **Open Terminal** — press `Cmd + Space`, type "Terminal", and hit Enter.

3. **Navigate to the project folder** — type this, replacing the path with where you unzipped it:
   ```bash
   cd ~/Downloads/resybot-main
   ```

4. **Create the virtual environment and install dependencies:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r client/requirements.txt -r server/requirements.txt
   ```

5. **You're done with Terminal!** You can close it.

## Your Data Stays Local

This repo ships with **no accounts, tasks, or presets** — you add your own the first time you run it.

Everything you enter is written to files inside `client/` on your own machine:

| File | What it holds |
|------|---------------|
| `client/accounts.json` | Your saved Resy accounts (auth token + payment ID) |
| `client/presets.json` | Your saved task presets |
| `client/tasks.json` | Tasks created by the CLI |
| `client/info.json` | Optional captcha keys and Discord webhook |
| `client/proxies.json` | Optional proxy list |

All of these are listed in `.gitignore`, so they will **never** be committed if you fork this repo — but double-check before pushing anyway. Your auth token is effectively your Resy password: never share it, and never paste it into an issue or a screenshot.

The `.example.json` files in `client/` show the expected format if you'd rather create them by hand.

## Running the Bot

### Option A: Double-Click (Mac)

Open the project folder in Finder and double-click **ResyGrabber.command**. Your browser will open automatically.

> **First time:** macOS may say the file can't be opened. Go to **System Settings → Privacy & Security**, scroll down, and click "Open Anyway."

### Option B: From Terminal

```bash
cd /path/to/resybot
source venv/bin/activate
python3 start_web.py
```

Then open [http://127.0.0.1:5001](http://127.0.0.1:5001) in your browser.

## How to Use

### 1. Get Your Resy Credentials

You need two things from your Resy account:

- **Auth Token** — your login session token
- **Payment ID** — identifies your payment method

To find them:
1. Open [resy.com](https://resy.com) in **Chrome** and log in
2. Press `F12` (or `Cmd + Option + I`) to open Developer Tools
3. Click the **Network** tab
4. Browse to any restaurant on Resy — you'll see network requests appear
5. Click on any request to `api.resy.com`
6. In the **Headers** section, find `x-resy-auth-token` — that's your **Auth Token**
7. For **Payment ID**: go to your Resy account settings, click on your payment method. In the Network tab, look for a request to the `user` endpoint — the response will contain your payment method ID

### 2. Add Your Account

In the web interface:
1. Enter your **Account Name** (any label you want), **Auth Token**, and **Payment ID**
2. Click **Save Account** — it's saved for future use and appears in the dropdown

### 3. Find a Restaurant's Venue ID

You need the Resy venue ID for the restaurant you want. To find it:
1. Go to the restaurant's page on resy.com
2. Open Developer Tools (`F12`) → Network tab
3. Look at the API requests — the `venue_id` parameter will be in the URL

### 4. Create a Task

1. Select your account from the dropdown (or enter credentials manually)
2. Enter the **Venue ID**
3. Set **Party Size**
4. Add one or more **Date Ranges** (click "+ Add Date Range" for more)
5. Add one or more **Time Windows** (click "+ Add Window" for more) — hours are in 24-hour format (e.g., 18 = 6pm)
6. Optionally set a **Table Type** (e.g., "Dining Room", "Bar")
7. Set **Delay** — how often to check, in milliseconds (60000 = every 60 seconds)
8. Click **START**

### 5. Watch the Logs

The log window at the bottom shows real-time activity. When the bot finds and books a reservation, you'll see a success message.

Click **STOP** to cancel at any time.

### 6. Save a Preset

To reuse a task later, fill in the form and click **Save Current Form** in the "Saved Tasks" section. Next time, just select it from the dropdown and click START.

## Optional Features

### Proxies

If you're running the bot aggressively (low delay, multiple tasks), Resy may rate-limit your IP. Add rotating proxies in the format `ip:port:username:password` (one per line) in the Proxies field.

### Discord Notifications

Paste a Discord webhook URL in the Discord Webhook field to get notified when a reservation is booked (or fails).

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Port 8000 already in use" | A previous instance is still running. Close all Terminal windows and try again, or run: `lsof -ti:8000 \| xargs kill -9` |
| "No module named 'fastapi'" | Your virtual environment isn't activated. Run `source venv/bin/activate` first |
| Bot returns 500 errors | Check that your auth token is still valid (they expire). Get a fresh one from resy.com |
| "python: command not found" | Use `python3` instead of `python` |
| Can't double-click .command file | Right-click → Open, or go to System Settings → Privacy & Security → Open Anyway |

## Project Structure

```
resybot/
├── web_app.py              # Web interface (Flask)
├── start_web.py             # Launches everything
├── start.py                 # CLI launcher (alternative)
├── ResyGrabber.command       # Mac double-click launcher
├── templates/
│   └── index.html           # Web UI
├── client/
│   ├── resygrabber.py       # CLI interface
│   ├── task_executor.py     # Core booking logic
│   ├── *.example.json       # Config templates (copy & fill in)
│   └── requirements.txt
└── server/
    ├── server.py            # API proxy server
    └── requirements.txt
```

## Disclaimer

This project is not affiliated with, endorsed by, or connected to Resy in any way. It's provided as-is for personal use. Automated booking may violate Resy's terms of service — use it at your own risk and be considerate: don't run aggressive polling delays, and don't book tables you won't use.

## License

MIT License — see [LICENSE](LICENSE) for details.

## Credits

Originally created as a SaaS product, now open-sourced. Web interface and additional features added with the help of Claude Code.
