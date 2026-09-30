#!/usr/bin/env python3
"""
NHL Goal Notification System
Monitors Flyers games and sends notifications (ntfy, SMS gateway, ...) when they score
"""

import os
import time
from datetime import datetime
from typing import Dict, List, Mapping, Optional, Set
from urllib.parse import quote, urlencode

import apprise
import requests
from dotenv import load_dotenv
from nhl_client import NHLClient

# Load environment variables from .env file
load_dotenv()

# Telus email-to-SMS gateway used by the original SMTP setup.
TELUS_SMS_DOMAIN = "msg.telus.com"


def split_urls(value: Optional[str]) -> List[str]:
    """Split a NOTIFY_URLS value on commas and/or whitespace."""
    if not value:
        return []
    return [url for url in value.replace(",", " ").split() if url]


def legacy_smtp_url(env: Mapping[str, str]) -> Optional[str]:
    """
    Build an Apprise mailtos:// URL from the old SMTP_* and PHONE_NUMBER settings.

    Keeps an existing .env working unchanged: the goal is still emailed to the
    Telus email-to-SMS gateway, only now Apprise does the sending.

    Returns:
        The URL, or None if any of the old settings is missing.
    """
    server = env.get('SMTP_SERVER')
    port = env.get('SMTP_PORT')
    username = env.get('SMTP_USERNAME')
    password = env.get('SMTP_PASSWORD')
    phone = env.get('PHONE_NUMBER')

    if not all([server, port, username, password, phone]):
        return None

    query = urlencode({
        'user': username,
        'pass': password,
        'from': username,
        'to': f"{phone}@{TELUS_SMS_DOMAIN}",
    }, quote_via=quote)
    return f"mailtos://{server}:{int(port)}?{query}"


def notify_urls_from_env(env: Mapping[str, str]) -> List[str]:
    """
    Resolve where goal alerts go.

    NOTIFY_URLS (any Apprise URLs, e.g. ntfy://ntfy.sh/my-topic) wins. Without
    it, fall back to the legacy SMTP_* settings.
    """
    urls = split_urls(env.get('NOTIFY_URLS'))
    if urls:
        return urls

    legacy = legacy_smtp_url(env)
    return [legacy] if legacy else []


class GoalNotifier:
    """Monitor NHL games and push notifications for Flyers goals."""

    def __init__(self, notify_urls: Optional[List[str]] = None):
        """
        Initialize goal notifier.

        Args:
            notify_urls: Apprise notification URLs (ntfy://, mailtos://, ...).
                         If None, read from NOTIFY_URLS or the legacy SMTP_* settings.

        Raises:
            ValueError: if no destination is configured or a URL is not valid.
        """
        self.client = NHLClient(favorite_team="PHI")

        urls = notify_urls if notify_urls is not None else notify_urls_from_env(os.environ)
        if not urls:
            raise ValueError(
                "No notification destination configured: set NOTIFY_URLS "
                "(see .env.example) or the legacy SMTP_* and PHONE_NUMBER settings."
            )

        self.apprise = apprise.Apprise()
        for url in urls:
            # Apprise only reports success/failure; never echo the URL, it may hold a password.
            if not self.apprise.add(url):
                raise ValueError("Invalid notification URL in NOTIFY_URLS / SMTP_* settings")

        # Track goals we've already notified about (game_id -> set of event_ids)
        self.notified_goals: Dict[int, Set[int]] = {}

    def send_notification(self, message: str) -> bool:
        """
        Send a goal alert to every configured destination.

        Args:
            message: Message to send (keep under 160 chars for a single SMS)

        Returns:
            True if every destination accepted it, False otherwise
        """
        try:
            if self.apprise.notify(body=message):
                print(f"✓ Notification sent to {len(self.apprise)} destination(s)")
                return True

            print("✗ Failed to send notification")
            return False

        except Exception as e:
            print(f"✗ Failed to send notification: {e}")
            return False

    def get_player_name(self, player_id: int, game_id: int) -> str:
        """
        Get player name from game roster.

        Args:
            player_id: NHL player ID
            game_id: NHL game ID

        Returns:
            Player name or "Unknown Player"
        """
        try:
            url = f"https://api-web.nhle.com/v1/gamecenter/{game_id}/boxscore"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Check both teams' rosters
            for team_key in ['awayTeam', 'homeTeam']:
                team = data.get('playerByGameStats', {}).get(team_key, {})

                # Check forwards
                for position in ['forwards', 'defense', 'goalies']:
                    for player in team.get(position, []):
                        if player.get('playerId') == player_id:
                            first = player.get('name', {}).get('default', '').split()[0]
                            last = player.get('name', {}).get('default', '').split()[-1]
                            return f"{first} {last}"

            return "Unknown Player"

        except Exception as e:
            print(f"Error fetching player name: {e}")
            return "Unknown Player"

    def format_goal_message(self, goal: Dict, game_info: Dict) -> str:
        """
        Format goal notification message.

        Args:
            goal: Goal event data
            game_info: Game information

        Returns:
            Formatted SMS message
        """
        period = goal.get('periodDescriptor', {}).get('number', '?')
        time_in_period = goal.get('timeInPeriod', '??:??')
        details = goal.get('details', {})

        # Get game ID for player lookups
        game_id = game_info.get('id')

        # Get scorer
        scorer_id = details.get('scoringPlayerId')
        scorer = self.get_player_name(scorer_id, game_id) if scorer_id else "Unknown"

        # Get assists
        assists = []
        assist1_id = details.get('assist1PlayerId')
        if assist1_id:
            assists.append(self.get_player_name(assist1_id, game_id))

        assist2_id = details.get('assist2PlayerId')
        if assist2_id:
            assists.append(self.get_player_name(assist2_id, game_id))

        # Build message
        away_team = game_info.get('awayTeam', {}).get('abbrev', 'UNK')
        home_team = game_info.get('homeTeam', {}).get('abbrev', 'UNK')
        away_score = details.get('awayScore', 0)
        home_score = details.get('homeScore', 0)

        message = f"🚨 FLYERS GOAL! {scorer}"

        if assists:
            message += f" ({', '.join(assists)})"

        message += f"\nP{period} {time_in_period} | {away_team} {away_score}-{home_score} {home_team}"

        return message

    def check_for_goals(self, game_id: int) -> List[Dict]:
        """
        Check game for new Flyers goals.

        Args:
            game_id: NHL game ID

        Returns:
            List of new goal events
        """
        try:
            url = f"https://api-web.nhle.com/v1/gamecenter/{game_id}/play-by-play"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Get Flyers team ID from the game
            away_team = data.get('awayTeam', {}).get('abbrev')
            home_team = data.get('homeTeam', {}).get('abbrev')

            if away_team == 'PHI':
                flyers_team_id = data.get('awayTeam', {}).get('id')
            elif home_team == 'PHI':
                flyers_team_id = data.get('homeTeam', {}).get('id')
            else:
                return []  # Not a Flyers game

            # Get all goals
            goals = [p for p in data.get('plays', []) if p.get('typeDescKey') == 'goal']

            # Filter for Flyers goals we haven't notified about
            new_goals = []
            notified = self.notified_goals.get(game_id, set())

            for goal in goals:
                event_id = goal.get('eventId')
                team_id = goal.get('details', {}).get('eventOwnerTeamId')

                if team_id == flyers_team_id and event_id not in notified:
                    new_goals.append(goal)
                    notified.add(event_id)

            # Update notified goals
            self.notified_goals[game_id] = notified

            return new_goals

        except Exception as e:
            print(f"Error checking for goals: {e}")
            return []

    def get_active_flyers_games(self) -> List[Dict]:
        """
        Get currently active Flyers games.

        Returns:
            List of active game info dictionaries
        """
        scoreboard = self.client.get_scoreboard()

        if not scoreboard or 'games' not in scoreboard:
            return []

        active_games = []
        for game in scoreboard.get('games', []):
            # Check if it's a Flyers game
            if not self.client.is_favorite_team_game(game):
                continue

            # Check if game is live
            game_state = game.get('gameState', '')
            if game_state in ['LIVE', 'CRIT']:
                active_games.append(game)

        return active_games

    def monitor_games(self, check_interval: int = 30):
        """
        Continuously monitor Flyers games for goals.

        Args:
            check_interval: Seconds between checks (default: 30)
        """
        print(f"🏒 Starting Flyers Goal Monitor")
        print(f"📱 Notifications to {len(self.apprise)} destination(s)")
        print(f"🔄 Checking every {check_interval} seconds")
        print("Press Ctrl+C to stop\n")

        try:
            while True:
                active_games = self.get_active_flyers_games()

                if not active_games:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] No active Flyers games")
                else:
                    for game in active_games:
                        game_id = game.get('id')
                        away = game.get('awayTeam', {}).get('abbrev', 'UNK')
                        home = game.get('homeTeam', {}).get('abbrev', 'UNK')

                        print(f"[{datetime.now().strftime('%H:%M:%S')}] Monitoring: {away} @ {home}")

                        # Check for new goals
                        new_goals = self.check_for_goals(game_id)

                        for goal in new_goals:
                            message = self.format_goal_message(goal, game)
                            print(f"\n🚨 NEW GOAL DETECTED!")
                            print(message)
                            print()

                            # Send notification
                            self.send_notification(message)

                time.sleep(check_interval)

        except KeyboardInterrupt:
            print("\n\n👋 Stopping goal monitor...")
            print("Goodbye!")


def main():
    """Main entry point."""
    # Get check interval from environment
    check_interval = int(os.getenv('CHECK_INTERVAL', '30'))

    print(f"\n🏒 NHL Flyers Goal Notifier")
    print(f"=" * 50)

    try:
        notifier = GoalNotifier()
    except ValueError as e:
        raise SystemExit(f"✗ {e}")

    notifier.monitor_games(check_interval=check_interval)


if __name__ == "__main__":
    main()
