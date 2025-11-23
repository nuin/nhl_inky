# NHL Flyers Goal Notifier

Automatically sends SMS notifications via email-to-SMS gateway when the Philadelphia Flyers score a goal.

## Features

- 🚨 Real-time goal notifications with scorer and assists
- 📱 SMS delivery via Telus email-to-SMS gateway
- ⏱️ Period and time information
- 📊 Current score included
- 🔄 Checks every 30 seconds during live games
- 💾 Tracks notified goals to avoid duplicates

## Setup

### 1. Install Dependencies

```bash
cd ~/nhl_inky
source venv/bin/activate
pip install python-dotenv
```

### 2. Configure SMTP Settings

The `.env` file is already configured with your Gmail SMTP settings from the woodpecker-detector project.

If you need to change settings, edit `.env`:

```bash
nano .env
```

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

Edit `.env` to customize:

```env
# Phone number to receive SMS
PHONE_NUMBER=5877852690

# SMTP server settings (Gmail configured)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=paulo.nuin@gmail.com
SMTP_PASSWORD=hlapqqpwrjonvfhi

# How often to check for new goals (in seconds)
CHECK_INTERVAL=30
```

## SMS Message Format

When the Flyers score, you'll receive a message like:

```
🚨 FLYERS GOAL! Travis Konecny (Travis Sanheim, Sean Couturier)
P2 12:34 | PHI 2-1 NYR
```

## How It Works

1. **Monitors Live Games**: Checks the NHL API every 30 seconds for active Flyers games
2. **Detects Goals**: Polls the play-by-play endpoint for new goal events
3. **Gets Details**: Fetches scorer and assist information from the game roster
4. **Sends SMS**: Uses email-to-SMS gateway (number@msg.telus.com) via Gmail SMTP
5. **Tracks Notifications**: Remembers sent goals to avoid duplicate messages

## API Endpoints Used

- `https://api-web.nhle.com/v1/score/{date}` - Today's games
- `https://api-web.nhle.com/v1/gamecenter/{game_id}/play-by-play` - Live game events
- `https://api-web.nhle.com/v1/gamecenter/{game_id}/boxscore` - Player roster

## Troubleshooting

### No SMS received

1. Check the log output for errors
2. Verify SMTP credentials are correct
3. Test with a manual send:
   ```python
   from goal_notifier import GoalNotifier
   notifier = GoalNotifier("5877852690")
   notifier.send_sms("Test message from goal notifier")
   ```

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
