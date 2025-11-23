#!/usr/bin/env python3
"""
NHL Scores Display for Inky Impression 7.3" (800x480, Spectra 6)
Displays NHL scores with Philadelphia Flyers highlighting
"""

import time
from datetime import datetime
from typing import List, Dict, Optional
from PIL import Image, ImageDraw, ImageFont
try:
    from inky.auto import auto
    from inky import Inky7Colour as Inky
    HAVE_INKY = True
except ImportError:
    HAVE_INKY = False
    print("Warning: Inky library not found. Install with: pip install inky")

from nhl_client import NHLClient


class NHLInkyDisplay:
    """Display NHL scores on Inky Impression 7.3\" display."""

    # Display dimensions
    WIDTH = 800
    HEIGHT = 480

    # Inky Impression 7.3" Spectra 6 colors
    WHITE = (255, 255, 255)
    BLACK = (0, 0, 0)
    RED = (255, 0, 0)
    YELLOW = (255, 255, 0)
    ORANGE = (255, 140, 0)
    GREEN = (0, 255, 0)

    # Color scheme for game states
    COLOR_BACKGROUND = WHITE
    COLOR_HEADER = BLACK
    COLOR_LIVE = GREEN
    COLOR_SCHEDULED = ORANGE
    COLOR_FINAL = BLACK
    COLOR_FLYERS = RED

    def __init__(self, client: NHLClient):
        """
        Initialize Inky display.

        Args:
            client: NHLClient instance
        """
        self.client = client

        if not HAVE_INKY:
            print("Running in simulation mode (no Inky hardware)")
            self.inky = None
        else:
            try:
                self.inky = auto()
                self.inky.set_border(self.inky.WHITE)
            except Exception as e:
                print(f"Failed to initialize Inky display: {e}")
                self.inky = None

        # Try to load fonts
        try:
            self.font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)
            self.font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
            self.font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
            self.font_tiny = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
        except Exception as e:
            print(f"Warning: Could not load fonts: {e}")
            self.font_large = ImageFont.load_default()
            self.font_medium = ImageFont.load_default()
            self.font_small = ImageFont.load_default()
            self.font_tiny = ImageFont.load_default()

    def create_image(self) -> Image.Image:
        """
        Create image with NHL scores.

        Returns:
            PIL Image ready for display
        """
        # Create blank image
        img = Image.new("RGB", (self.WIDTH, self.HEIGHT), self.COLOR_BACKGROUND)
        draw = ImageDraw.Draw(img)

        y_position = 10

        # Draw header
        header = "NHL SCORES & SCHEDULE"
        draw.text((self.WIDTH // 2, y_position), header, font=self.font_large,
                  fill=self.COLOR_HEADER, anchor="mt")
        y_position += 45

        # Draw timestamp
        now_str = datetime.now().strftime('%Y-%m-%d %I:%M %p MT')
        draw.text((self.WIDTH // 2, y_position), now_str, font=self.font_small,
                  fill=self.COLOR_HEADER, anchor="mt")
        y_position += 30

        # Draw separator line
        draw.line([(10, y_position), (self.WIDTH - 10, y_position)], fill=self.COLOR_HEADER, width=2)
        y_position += 15

        # Fetch today's games
        scoreboard = self.client.get_scoreboard()

        if not scoreboard or 'games' not in scoreboard:
            draw.text((self.WIDTH // 2, y_position + 50), "No games found for today",
                      font=self.font_medium, fill=self.COLOR_HEADER, anchor="mt")
        else:
            games = scoreboard.get('games', [])

            if not games:
                draw.text((self.WIDTH // 2, y_position + 50), "No games scheduled today",
                          font=self.font_medium, fill=self.COLOR_HEADER, anchor="mt")
            else:
                # Display today's games
                for game in games[:8]:  # Max 8 games to fit on screen
                    if y_position > 280:  # Leave room for Flyers section
                        break

                    y_position = self._draw_game(draw, game, y_position)

                # Draw Flyers upcoming schedule section
                y_position += 10
                if y_position < 350:
                    draw.line([(10, y_position), (self.WIDTH - 10, y_position)],
                              fill=self.COLOR_FLYERS, width=3)
                    y_position += 15

                    flyers_title = f"{self.client.favorite_team} UPCOMING GAMES"
                    draw.text((self.WIDTH // 2, y_position), flyers_title,
                              font=self.font_medium, fill=self.COLOR_FLYERS, anchor="mt")
                    y_position += 30

                    # Get upcoming Flyers games
                    upcoming = self.client.get_team_schedule(self.client.favorite_team, limit=3)

                    if upcoming:
                        for flyers_game in upcoming[:3]:
                            if y_position > self.HEIGHT - 30:
                                break

                            game_date = flyers_game.get('gameDate', '')
                            game_info = self.client.format_game_info(flyers_game)

                            display_str = f"{game_date}  {game_info}"
                            draw.text((20, y_position), display_str,
                                      font=self.font_small, fill=self.COLOR_FLYERS)
                            y_position += 25

        # Draw footer
        footer = "Updates every 2 minutes | Powered by NHL API"
        draw.text((self.WIDTH // 2, self.HEIGHT - 10), footer,
                  font=self.font_tiny, fill=self.COLOR_HEADER, anchor="mb")

        return img

    def _draw_game(self, draw: ImageDraw.ImageDraw, game: Dict, y_position: int) -> int:
        """
        Draw a single game on the display.

        Args:
            draw: ImageDraw object
            game: Game data dictionary
            y_position: Current Y position

        Returns:
            Updated Y position
        """
        state, color_name = self.client.get_game_state_info(game)
        is_flyers = self.client.is_favorite_team_game(game)

        # Select color
        if is_flyers:
            color = self.COLOR_FLYERS
            marker = ">>> "
        else:
            if color_name == 'live':
                color = self.COLOR_LIVE
            elif color_name == 'scheduled':
                color = self.COLOR_SCHEDULED
            elif color_name == 'final':
                color = self.COLOR_FINAL
            else:
                color = self.COLOR_HEADER
            marker = ""

        game_info = self.client.format_game_info(game)

        # Draw marker and state
        x_pos = 20
        state_str = f"{marker}[{state:>9}]"
        draw.text((x_pos, y_position), state_str, font=self.font_small, fill=color)

        # Draw game info
        draw.text((x_pos + 150, y_position), game_info, font=self.font_small, fill=color)

        return y_position + 28

    def display(self) -> None:
        """Create and display image on Inky screen."""
        img = self.create_image()

        if self.inky is None:
            # Save to file for testing
            filename = f"nhl_scores_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            img.save(filename)
            print(f"Saved to {filename} (no Inky hardware detected)")
        else:
            # Display on Inky
            self.inky.set_image(img)
            self.inky.show()
            print("Display updated on Inky screen")

    def run_continuous(self, interval: int = 120) -> None:
        """
        Run continuous updates at specified interval.

        Args:
            interval: Update interval in seconds (default: 120 = 2 minutes)
        """
        print(f"Starting NHL Inky Display (updating every {interval} seconds)")
        print("Press Ctrl+C to stop")

        try:
            while True:
                print(f"\nUpdating display at {datetime.now().strftime('%H:%M:%S')}")
                self.display()
                print(f"Next update in {interval} seconds...")
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n\nStopping NHL Inky Display...")
            print("Goodbye!")


def main():
    """Main entry point."""
    client = NHLClient()
    display = NHLInkyDisplay(client)

    import sys
    if '--once' in sys.argv:
        # Single update
        display.display()
    else:
        # Continuous updates
        display.run_continuous(interval=120)


if __name__ == "__main__":
    main()
