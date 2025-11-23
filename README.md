# NHL Scores and Schedule Client

A lightweight Python client that fetches NHL scores and schedules with a beautiful TUI (Text User Interface), updating every 2 minutes. Designed to run on Raspberry Pi Zero with Python 3.7+.

## Features

- **Interactive TUI** with color-coded games and live updates
- **Philadelphia Flyers Highlighting** - Flyers games shown in bold magenta with >>> markers
- **Upcoming Flyers Schedule** - Shows next 5 Flyers games at the bottom
- Fetches current NHL scores and schedules
- Auto-updates every 2 minutes
- Displays game status (scheduled, live, or final)
- Shows live game period and time remaining
- Mountain Time zone conversion for all game times
- Color-coded game states:
  - **Green/Bold**: Live games
  - **Yellow**: Scheduled games
  - **White**: Final games
  - **Magenta/Bold/Reverse**: Philadelphia Flyers games
- Lightweight with minimal dependencies
- Compatible with Raspberry Pi Zero

## Requirements

- Python 3.7 or higher
- Internet connection

## Installation on Raspberry Pi Zero

### Option 1: Using uv (Recommended)

1. **Install uv on your Pi Zero:**
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   source $HOME/.cargo/env
   ```

2. **Clone or copy the project files to your Pi Zero:**
   ```bash
   # Copy the entire project directory to your Pi
   ```

3. **Install dependencies:**
   ```bash
   uv sync
   ```

### Option 2: Using pip and venv

1. **Clone or copy the files to your Pi Zero:**
   ```bash
   # Copy nhl_client.py and requirements.txt to your Pi
   ```

2. **Create a virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### TUI Mode (Default - Recommended)

Run the client with the interactive TUI:

**With uv:**
```bash
uv run python nhl_client.py
```

**With venv:**
```bash
source venv/bin/activate
python3 nhl_client.py
```

The TUI will display:
- **Top section**: All today's NHL games with color-coded status
- **Flyers games**: Highlighted in magenta with >>> markers
- **Bottom section**: Next 5 upcoming Philadelphia Flyers games
- **Live countdown**: Shows seconds until next update
- **Press 'q' to quit**

### Simple Print Mode

For systems without curses support or if you prefer scrolling output:

```bash
uv run python nhl_client.py --no-tui
```

The client will:
- Display current scores and game status
- Update automatically every 2 minutes
- Continue running until you press Ctrl+C

### Running as a Background Service

To run the client as a systemd service on your Pi Zero:

1. **Create a service file:**
   ```bash
   sudo nano /etc/systemd/system/nhl-client.service
   ```

2. **Add the following content (adjust paths as needed):**

   **For uv:**
   ```ini
   [Unit]
   Description=NHL Scores Client
   After=network.target

   [Service]
   Type=simple
   User=pi
   WorkingDirectory=/home/pi/nhl
   ExecStart=/home/pi/.cargo/bin/uv run python /home/pi/nhl/nhl_client.py
   Restart=always
   RestartSec=10

   [Install]
   WantedBy=multi-user.target
   ```

   **For venv:**
   ```ini
   [Unit]
   Description=NHL Scores Client
   After=network.target

   [Service]
   Type=simple
   User=pi
   WorkingDirectory=/home/pi/nhl
   ExecStart=/home/pi/nhl/venv/bin/python3 /home/pi/nhl/nhl_client.py
   Restart=always
   RestartSec=10

   [Install]
   WantedBy=multi-user.target
   ```

3. **Enable and start the service:**
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable nhl-client.service
   sudo systemctl start nhl-client.service
   ```

4. **Check service status:**
   ```bash
   sudo systemctl status nhl-client.service
   ```

5. **View logs:**
   ```bash
   sudo journalctl -u nhl-client.service -f
   ```

## API Information

This client uses the official NHL Web API:
- Base URL: `https://api-web.nhle.com/v1`
- No API key required
- Endpoints used:
  - `/schedule/{date}` - Game schedules
  - `/score/{date}` - Live scores

## Customization

### Change Update Interval

Edit `nhl_client.py` and modify the interval in the `main()` function:

```python
client.run_continuous(interval=300)  # Update every 5 minutes
```

### Display More Information

The API returns extensive game data. You can modify the `format_game_info()` method to display additional information such as:
- Venue name
- Shot statistics
- Player stats
- Playoff information

## Troubleshooting

**Connection errors:**
- Ensure your Pi Zero has internet connectivity
- Check if the NHL API is accessible: `curl https://api-web.nhle.com/v1/score/$(date +%Y-%m-%d)`

**Memory issues on Pi Zero:**
- The client is designed to be lightweight
- If you experience issues, consider reducing the update frequency

**Python version:**
- Check your Python version: `python3 --version`
- Minimum required: Python 3.7

## References

- [NHL API Reference (Unofficial)](https://github.com/Zmalski/NHL-API-Reference)
- [nhl-api-py Library](https://github.com/coreyjs/nhl-api-py)

## License

This project uses the publicly accessible NHL API endpoints. Please be respectful of API usage and don't make excessive requests.
