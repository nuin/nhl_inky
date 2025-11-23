#!/usr/bin/env python3
"""
NHL Goal Notification System
Monitors Flyers games and sends SMS notifications when they score
"""

import os
import time
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
from typing import Dict, List, Set, Optional
import requests
from dotenv import load_dotenv
from nhl_client import NHLClient

# Load environment variables from .env file
load_dotenv()


class GoalNotifier:
    """Monitor NHL games and send SMS notifications for Flyers goals."""

    def __init__(self, phone_number: str, smtp_config: Optional[Dict] = None):
        """
        Initialize goal notifier.

        Args:
            phone_number: Telus phone number (e.g., "5877852690")
            smtp_config: SMTP configuration dict with keys: server, port, username, password
                        If None, will prompt for configuration
        """
        self.client = NHLClient(favorite_team="PHI")
        self.phone_number = phone_number
        self.sms_email = f"{phone_number}@msg.telus.com"
        self.smtp_config = smtp_config or self._get_smtp_config()

        # Track goals we've already notified about (game_id -> set of event_ids)
        self.notified_goals: Dict[int, Set[int]] = {}

    def _get_smtp_config(self) -> Dict:
        """
        Get SMTP configuration from environment or interactively.

        Returns:
            Dictionary with SMTP settings
        """
        # Try to load from environment variables
        server = os.getenv('SMTP_SERVER')
        port = os.getenv('SMTP_PORT')
        username = os.getenv('SMTP_USERNAME')
        password = os.getenv('SMTP_PASSWORD')

        if all([server, port, username, password]):
            return {
                "server": server,
                "port": int(port),
                "username": username,
                "password": password
            }

        # If not in environment, ask interactively
        print("\nSMTP Configuration for Email-to-SMS")
        print("=" * 50)
        print("You'll need an email account to send SMS via email gateway.")
        print("Gmail example:")
        print("  - Server: smtp.gmail.com")
        print("  - Port: 587")
        print("  - Username: your.email@gmail.com")
        print("  - Password: your app-specific password")
        print("\nFor Gmail, create an app password at:")
        print("  https://myaccount.google.com/apppasswords")
        print("\nTip: Create a .env file to avoid entering this each time!")
        print("=" * 50)

        server = input("\nSMTP Server (e.g., smtp.gmail.com): ").strip()
        port = int(input("SMTP Port (587 for TLS): ").strip() or "587")
        username = input("SMTP Username (email address): ").strip()
        password = input("SMTP Password (app password): ").strip()

        return {
            "server": server,
            "port": port,
            "username": username,
            "password": password
        }

    def send_sms(self, message: str) -> bool:
        """
        Send SMS via email-to-SMS gateway.

        Args:
            message: Message to send (keep under 160 chars for single SMS)

        Returns:
            True if sent successfully, False otherwise
        """
        try:
            msg = MIMEText(message)
            msg['From'] = self.smtp_config['username']
            msg['To'] = self.sms_email
            msg['Subject'] = ''  # Empty subject for cleaner SMS

            with smtplib.SMTP(self.smtp_config['server'], self.smtp_config['port']) as server:
                server.starttls()
                server.login(self.smtp_config['username'], self.smtp_config['password'])
                server.send_message(msg)

            print(f"✓ SMS sent to {self.phone_number}")
            return True

        except Exception as e:
            print(f"✗ Failed to send SMS: {e}")
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
        print(f"📱 SMS notifications to: {self.phone_number}")
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

                            # Send SMS notification
                            self.send_sms(message)

                time.sleep(check_interval)

        except KeyboardInterrupt:
            print("\n\n👋 Stopping goal monitor...")
            print("Goodbye!")


def main():
    """Main entry point."""
    import sys

    # Get phone number from environment or use default
    phone = os.getenv('PHONE_NUMBER', "5877852690")

    # Check for phone number argument (overrides environment)
    if len(sys.argv) > 1:
        phone = sys.argv[1].replace("-", "").replace(" ", "")

    # Get check interval from environment
    check_interval = int(os.getenv('CHECK_INTERVAL', '30'))

    print(f"\n🏒 NHL Flyers Goal Notifier")
    print(f"=" * 50)

    notifier = GoalNotifier(phone_number=phone)
    notifier.monitor_games(check_interval=check_interval)


if __name__ == "__main__":
    main()
