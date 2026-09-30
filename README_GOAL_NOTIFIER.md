# NHL Flyers Goal Notifier

Automatically sends a push notification (or an SMS via an email-to-SMS gateway) when the Philadelphia Flyers score a goal. Delivery goes through [Apprise](https://github.com/caronc/apprise), so any service it supports works: [ntfy](https://ntfy.sh) push, email, Telegram, Pushover, and so on.

## Features

- 🚨 Real-time goal notifications with scorer and assists
- 📱 Delivery to any Apprise destination: ntfy push (no account or SMTP credentials needed), or the Telus email-to-SMS gateway
- ⏱️ Period and time information
- 📊 Current score included
- 🔄 Checks every 30 seconds during live games
- 💾 Tracks notified goals to avoid duplicates

## Setup

### 1. Install Dependencies

```bash
cd ~/nhl_inky
source venv/bin/activate
pip install -r requirements.txt   # includes python-dotenv and apprise
```

### 2. Configure Where Alerts Go

Copy the example and set `NOTIFY_URLS`:

```bash
cp .env.example .env
nano .env
```

For ntfy, pick a long random topic (anyone who knows it can read it), install the ntfy app on your phone and subscribe to that topic.

### 3. Run the Notifier

**On your development machine (for testing):**
```bash
python3 goal_notifier.py
```

**On the Raspberry Pi Zero (for continuous monitoring):**
```bash
# Run in foreground
python3 goal_notifier.py

# Or run in background with nohup
nohup python3 goal_notifier.py > goal_notifier.log 2>&1 &

# Check if running
ps aux | grep goal_notifier

# View logs
tail -f goal_notifier.log

# Stop background process
pkill -f goal_notifier.py
```

## Configuration

Edit `.env` (never commit it; it is git-ignored):

```env
# One or more Apprise URLs, separated by commas or spaces
NOTIFY_URLS=ntfy://ntfy.sh/your-random-topic

# Legacy email-to-SMS: used only when NOTIFY_URLS is empty
# PHONE_NUMBER=5550000000
# SMTP_SERVER=smtp.gmail.com
# SMTP_PORT=587
# SMTP_USERNAME=your.email@gmail.com
# SMTP_PASSWORD=your_app_password_here

# How often to check for new goals (in seconds)
CHECK_INTERVAL=30
```

An existing `.env` with only the `SMTP_*` and `PHONE_NUMBER` settings keeps working: those are turned into an Apprise `mailtos://` URL that emails `<PHONE_NUMBER>@msg.telus.com`, exactly as before.

## Message Format

When the Flyers score, you'll receive a message like:

```
🚨 FLYERS GOAL! Travis Konecny (Travis Sanheim, Sean Couturier)
P2 12:34 | PHI 2-1 NYR
```

## How It Works

1. **Monitors Live Games**: Checks the NHL API every 30 seconds for active Flyers games
2. **Detects Goals**: Polls the play-by-play endpoint for new goal events
3. **Gets Details**: Fetches scorer and assist information from the game roster
4. **Sends Alert**: Pushes the message to every `NOTIFY_URLS` destination via Apprise (or to the Telus email-to-SMS gateway with the legacy SMTP settings)
5. **Tracks Notifications**: Remembers sent goals to avoid duplicate messages

## API Endpoints Used

- `https://api-web.nhle.com/v1/score/{date}` - Today's games
- `https://api-web.nhle.com/v1/gamecenter/{game_id}/play-by-play` - Live game events
- `https://api-web.nhle.com/v1/gamecenter/{game_id}/boxscore` - Player roster

## Troubleshooting

### No notification received

1. Check the log output for errors
2. Verify `NOTIFY_URLS` (or the legacy SMTP credentials) are correct
3. Test with a manual send:
   ```python
   from goal_notifier import GoalNotifier
   notifier = GoalNotifier()   # reads NOTIFY_URLS from .env
   notifier.send_notification("Test message from goal notifier")
   ```
4. Or test the URL directly with the Apprise CLI: `apprise -b "test" "ntfy://ntfy.sh/your-random-topic"`

### "No active Flyers games" message

- This is normal when the Flyers aren't playing
- The script will continue monitoring and detect games when they start

### Gmail app password not working

1. Make sure 2-factor authentication is enabled on your Google account
2. Generate a new app password at: https://myaccount.google.com/apppasswords
3. Update the password in `.env`

## Running as a Service (systemd)

Create `/etc/systemd/system/flyers-notifier.service`:

```ini
[Unit]
Description=NHL Flyers Goal Notifier
After=network.target

[Service]
Type=simple
User=nuin
WorkingDirectory=/home/nuin/nhl_inky
Environment="PATH=/home/nuin/nhl_inky/venv/bin"
ExecStart=/home/nuin/nhl_inky/venv/bin/python3 goal_notifier.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable flyers-notifier
sudo systemctl start flyers-notifier
sudo systemctl status flyers-notifier
```

## License

Same as parent project.
