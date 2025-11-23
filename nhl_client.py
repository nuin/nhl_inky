#!/usr/bin/env python3
"""
NHL Scores and Schedule Client
Fetches NHL scores and schedules every 2 minutes
Compatible with Raspberry Pi Zero (Python 3.7+)
"""

import time
import json
from datetime import datetime
from typing import Dict, List, Optional
import requests
try:
    from zoneinfo import ZoneInfo
    HAVE_ZONEINFO = True
except ImportError:
    # Python < 3.9
    import pytz
    HAVE_ZONEINFO = False


class NHLClient:
    """Client for fetching NHL scores and schedules."""

    BASE_URL = "https://api-web.nhle.com/v1"

    def __init__(self, timeout: int = 10):
        """
        Initialize NHL Client.

        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'NHL-Score-Client/1.0'
        })

    def get_daily_schedule(self, date: Optional[str] = None) -> Dict:
        """
        Get schedule for a specific date or today.

        Args:
            date: Date in YYYY-MM-DD format. If None, uses today.

        Returns:
            Dictionary containing schedule data
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        url = f"{self.BASE_URL}/schedule/{date}"

        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching schedule: {e}")
            return {}

    def get_scoreboard(self, date: Optional[str] = None) -> Dict:
        """
        Get scoreboard for a specific date or today.

        Args:
            date: Date in YYYY-MM-DD format. If None, uses today.

        Returns:
            Dictionary containing scoreboard data
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        url = f"{self.BASE_URL}/score/{date}"

        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching scoreboard: {e}")
            return {}

    def convert_to_mountain_time(self, utc_time_str: str) -> str:
        """
        Convert UTC time string to Mountain Time.

        Args:
            utc_time_str: UTC time in ISO format (e.g., "2025-11-23T18:00:00Z")

        Returns:
            Time formatted as "HH:MM MT"
        """
        try:
            # Parse UTC time
            utc_dt = datetime.fromisoformat(utc_time_str.replace('Z', '+00:00'))

            # Convert to Mountain Time
            if HAVE_ZONEINFO:
                mt_tz = ZoneInfo("America/Denver")
                mt_dt = utc_dt.astimezone(mt_tz)
            else:
                mt_tz = pytz.timezone("America/Denver")
                mt_dt = utc_dt.astimezone(mt_tz)

            return mt_dt.strftime("%I:%M %p MT").lstrip('0')
        except Exception as e:
            return utc_time_str

    def format_game_info(self, game: Dict) -> str:
        """
        Format game information for display.

        Args:
            game: Game data dictionary

        Returns:
            Formatted string with game information
        """
        away_team = game.get('awayTeam', {})
        home_team = game.get('homeTeam', {})

        away_name = away_team.get('abbrev', 'TBD')
        home_name = home_team.get('abbrev', 'TBD')

        away_score = away_team.get('score', 0)
        home_score = home_team.get('score', 0)

        game_state = game.get('gameState', 'Unknown')
        game_time_utc = game.get('startTimeUTC', '')

        if game_state in ['OFF', 'FINAL']:
            # Game is finished
            return f"{away_name} {away_score} @ {home_name} {home_score} - FINAL"
        elif game_state in ['FUT', 'PRE']:
            # Game hasn't started yet
            game_time_mt = self.convert_to_mountain_time(game_time_utc)
            return f"{away_name} @ {home_name} - {game_time_mt}"
        else:
            # Game is live (LIVE, CRIT states)
            period_desc = game.get('periodDescriptor', {})
            period_num = period_desc.get('number', '?')
            period_type = period_desc.get('periodType', '')

            # Get clock info
            clock = game.get('clock', {})
            time_remaining = clock.get('timeRemaining', '20:00')
            in_intermission = clock.get('inIntermission', False)

            if in_intermission:
                return f"{away_name} {away_score} @ {home_name} {home_score} - Intermission (after P{period_num})"
            elif period_type == 'OT':
                return f"{away_name} {away_score} @ {home_name} {home_score} - OT {time_remaining}"
            elif period_type == 'SO':
                return f"{away_name} {away_score} @ {home_name} {home_score} - Shootout"
            else:
                return f"{away_name} {away_score} @ {home_name} {home_score} - P{period_num} {time_remaining}"

    def display_scores(self) -> None:
        """Display current scores and schedule."""
        print("\n" + "="*60)
        print(f"NHL Scores - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)

        scoreboard = self.get_scoreboard()

        if not scoreboard or 'games' not in scoreboard:
            print("No games found for today.")
            return

        games = scoreboard.get('games', [])

        if not games:
            print("No games scheduled for today.")
            return

        for game in games:
            print(self.format_game_info(game))

        print("="*60)

    def run_continuous(self, interval: int = 120) -> None:
        """
        Run continuous updates at specified interval.

        Args:
            interval: Update interval in seconds (default: 120 = 2 minutes)
        """
        print(f"Starting NHL Score Client (updating every {interval} seconds)")
        print("Press Ctrl+C to stop")

        try:
            while True:
                self.display_scores()
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n\nStopping NHL Score Client...")
            print("Goodbye!")


def main():
    """Main entry point."""
    client = NHLClient()
    client.run_continuous(interval=10)  # Update every 2 minutes


if __name__ == "__main__":
    main()
