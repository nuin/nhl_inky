#!/usr/bin/env python3
"""
NHL Scores and Schedule Client
Fetches NHL scores and schedules every 2 minutes
Compatible with Raspberry Pi Zero (Python 3.7+)
"""

import time
import json
import curses
from datetime import datetime
from typing import Dict, List, Optional, Tuple
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
    FLYERS_ABBREV = "PHI"  # Philadelphia Flyers team abbreviation

    def __init__(self, timeout: int = 10, favorite_team: str = "PHI"):
        """
        Initialize NHL Client.

        Args:
            timeout: Request timeout in seconds
            favorite_team: Team abbreviation to highlight (default: PHI for Flyers)
        """
        self.timeout = timeout
        self.favorite_team = favorite_team
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

    def is_favorite_team_game(self, game: Dict) -> bool:
        """
        Check if game involves the favorite team.

        Args:
            game: Game data dictionary

        Returns:
            True if favorite team is playing
        """
        away_team = game.get('awayTeam', {}).get('abbrev', '')
        home_team = game.get('homeTeam', {}).get('abbrev', '')
        return away_team == self.favorite_team or home_team == self.favorite_team

    def get_team_schedule(self, team_abbrev: str, start_date: Optional[str] = None,
                          end_date: Optional[str] = None, limit: int = 10) -> List[Dict]:
        """
        Get upcoming games for a specific team.

        Args:
            team_abbrev: Team abbreviation (e.g., 'PHI')
            start_date: Start date in YYYY-MM-DD format (default: today)
            end_date: End date in YYYY-MM-DD format (default: 30 days from start)
            limit: Maximum number of games to return

        Returns:
            List of upcoming games
        """
        from datetime import timedelta

        if start_date is None:
            start_dt = datetime.now()
            start_date = start_dt.strftime("%Y-%m-%d")
        else:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")

        if end_date is None:
            end_dt = start_dt + timedelta(days=30)
            end_date = end_dt.strftime("%Y-%m-%d")

        # Get games for the date range
        upcoming_games = []
        current_dt = start_dt

        while current_dt.strftime("%Y-%m-%d") <= end_date and len(upcoming_games) < limit:
            date_str = current_dt.strftime("%Y-%m-%d")
            scoreboard = self.get_scoreboard(date_str)

            if scoreboard and 'games' in scoreboard:
                for game in scoreboard.get('games', []):
                    if self.is_favorite_team_game(game):
                        # Only include future or live games
                        game_state = game.get('gameState', '')
                        if game_state not in ['OFF', 'FINAL']:
                            upcoming_games.append(game)
                            if len(upcoming_games) >= limit:
                                break

            current_dt += timedelta(days=1)

        return upcoming_games

    def get_game_state_info(self, game: Dict) -> Tuple[str, str]:
        """
        Get game state and color for display.

        Args:
            game: Game data dictionary

        Returns:
            Tuple of (state_name, color_name)
        """
        game_state = game.get('gameState', 'Unknown')

        if game_state in ['OFF', 'FINAL']:
            return ('FINAL', 'final')
        elif game_state in ['FUT', 'PRE']:
            return ('SCHEDULED', 'scheduled')
        elif game_state in ['LIVE', 'CRIT']:
            return ('LIVE', 'live')
        else:
            return (game_state, 'default')

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

    def run_tui(self, stdscr, interval: int = 120) -> None:
        """
        Run TUI with refreshing display.

        Args:
            stdscr: curses screen object
            interval: Update interval in seconds (default: 120 = 2 minutes)
        """
        # Initialize colors
        curses.start_color()
        curses.use_default_colors()

        # Define color pairs
        curses.init_pair(1, curses.COLOR_GREEN, -1)   # Live games
        curses.init_pair(2, curses.COLOR_YELLOW, -1)  # Scheduled games
        curses.init_pair(3, curses.COLOR_WHITE, -1)   # Final games
        curses.init_pair(4, curses.COLOR_CYAN, -1)    # Header
        curses.init_pair(5, curses.COLOR_RED, -1)     # Error
        curses.init_pair(6, curses.COLOR_MAGENTA, -1) # Flyers highlight

        COLOR_LIVE = curses.color_pair(1) | curses.A_BOLD
        COLOR_SCHEDULED = curses.color_pair(2)
        COLOR_FINAL = curses.color_pair(3)
        COLOR_HEADER = curses.color_pair(4) | curses.A_BOLD
        COLOR_ERROR = curses.color_pair(5)
        COLOR_FLYERS = curses.color_pair(6) | curses.A_BOLD | curses.A_REVERSE

        # Hide cursor
        curses.curs_set(0)

        # Set nodelay for non-blocking input
        stdscr.nodelay(True)

        last_update = 0

        while True:
            current_time = time.time()

            # Check for 'q' key to quit
            try:
                key = stdscr.getch()
                if key == ord('q') or key == ord('Q'):
                    break
            except:
                pass

            # Update display if interval has passed
            if current_time - last_update >= interval or last_update == 0:
                stdscr.clear()
                height, width = stdscr.getmaxyx()

                # Draw header
                title = "NHL SCORES & SCHEDULE"
                now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S MT')
                next_update = interval - int(current_time - last_update) if last_update > 0 else interval

                stdscr.addstr(0, (width - len(title)) // 2, title, COLOR_HEADER)
                stdscr.addstr(1, 0, "=" * width, COLOR_HEADER)
                stdscr.addstr(2, 2, f"Last Update: {now_str}", COLOR_HEADER)
                stdscr.addstr(2, width - 30, f"Next update in: {next_update}s", COLOR_HEADER)
                stdscr.addstr(3, 2, "Press 'q' to quit", curses.color_pair(2))
                stdscr.addstr(4, 0, "=" * width, COLOR_HEADER)

                # Fetch and display games
                scoreboard = self.get_scoreboard()

                if not scoreboard or 'games' not in scoreboard:
                    stdscr.addstr(6, 2, "No games found for today.", COLOR_ERROR)
                else:
                    games = scoreboard.get('games', [])

                    if not games:
                        stdscr.addstr(6, 2, "No games scheduled for today.", COLOR_SCHEDULED)
                    else:
                        row = 6
                        for game in games:
                            if row >= height - 12:  # Leave room for Flyers section
                                break

                            state, color_name = self.get_game_state_info(game)
                            is_flyers = self.is_favorite_team_game(game)

                            # Select color based on game state and Flyers involvement
                            if is_flyers:
                                color = COLOR_FLYERS
                            elif color_name == 'live':
                                color = COLOR_LIVE
                            elif color_name == 'scheduled':
                                color = COLOR_SCHEDULED
                            elif color_name == 'final':
                                color = COLOR_FINAL
                            else:
                                color = curses.color_pair(0)

                            game_info = self.format_game_info(game)

                            # Add state indicator and Flyers marker
                            marker = ">>> " if is_flyers else "    "
                            state_str = f"{marker}[{state:>9}] "
                            stdscr.addstr(row, 2, state_str, color)
                            stdscr.addstr(row, 2 + len(state_str), game_info, color if is_flyers else curses.color_pair(0))

                            row += 1

                        # Add Flyers upcoming schedule section
                        row += 1
                        if row < height - 8:
                            stdscr.addstr(row, 0, "=" * width, COLOR_HEADER)
                            row += 1
                            flyers_title = f"{self.favorite_team} UPCOMING GAMES"
                            stdscr.addstr(row, (width - len(flyers_title)) // 2, flyers_title, COLOR_HEADER)
                            row += 1
                            stdscr.addstr(row, 0, "=" * width, COLOR_HEADER)
                            row += 1

                            # Get upcoming Flyers games
                            upcoming = self.get_team_schedule(self.favorite_team, limit=5)

                            if not upcoming:
                                stdscr.addstr(row, 2, "No upcoming games in next 30 days", COLOR_SCHEDULED)
                            else:
                                for flyers_game in upcoming[:min(5, height - row - 2)]:
                                    game_date = flyers_game.get('gameDate', '')
                                    game_info = self.format_game_info(flyers_game)

                                    # Format: Date - Game Info
                                    display_str = f"{game_date}  {game_info}"
                                    stdscr.addstr(row, 2, display_str, curses.color_pair(6))
                                    row += 1

                # Draw footer
                footer = "Powered by NHL API | Updates every 2 minutes"
                stdscr.addstr(height - 1, (width - len(footer)) // 2, footer, curses.color_pair(2))

                stdscr.refresh()
                last_update = current_time

            # Sleep briefly to reduce CPU usage
            time.sleep(0.1)


def main():
    """Main entry point."""
    import sys

    # Check if --no-tui flag is provided
    use_tui = '--no-tui' not in sys.argv

    client = NHLClient()

    if use_tui:
        try:
            curses.wrapper(client.run_tui, 10)  # Update every 2 minutes
        except KeyboardInterrupt:
            print("\n\nStopping NHL Score Client...")
    else:
        # Fall back to simple print mode
        client.run_continuous(interval=120)


if __name__ == "__main__":
    main()
