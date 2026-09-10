import sys
from classes import drone
from simulation import simulation


class TerminalRender:
    """Print the simulation turn by turn in the terminal.

    Each turn is one line of space-separated moves:
    ``D<ID>-<zone>`` or ``D<ID>-<zone1>-<zone2>`` while a drone is flying
    toward a restricted zone. Zone names are colored with their metadata
    color when the output is a real terminal.

    Attributes:
        sim: The simulation controller.
        use_color: Whether ANSI colors are printed.
    """

    COLORS: dict[str, tuple[int, int, int]] = {
        "black": (0, 0, 0),
        "white": (255, 255, 255),
        "red": (255, 0, 0),
        "blue": (0, 120, 255),
        "green": (0, 255, 0),
        "gray": (128, 128, 128),
        "grey": (128, 128, 128),
        "purple": (160, 32, 240),
        "orange": (255, 165, 0),
        "maroon": (128, 0, 0),
        "gold": (255, 215, 0),
        "darkred": (139, 0, 0),
        "crimson": (220, 20, 60),
        "brown": (139, 69, 19),
        "violet": (238, 130, 238),
        "yellow": (255, 255, 0),
        "cyan": (0, 255, 255),
        "magenta": (255, 0, 255),
        "pink": (255, 105, 180),
        "lime": (50, 205, 50),
    }
    RESET = "\033[0m"

    def __init__(self, sim: simulation) -> None:
        """Store the simulation and detect color support.

        Args:
            sim: The simulation to display.
        """
        self.sim = sim
        # no ANSI codes when the output is redirected to a file / pipe
        self.use_color = sys.stdout.isatty()

    def colorize(self, text: str, color: str) -> str:
        """Wrap text in an ANSI color code if the color is known.

        Args:
            text: The text to color.
            color: The color name from the zone metadata.

        Returns:
            The colored (or unchanged) text.
        """
        rgb = self.COLORS.get(color.lower())
        if not self.use_color or rgb is None:
            return text
        r, g, b = rgb
        return f"\033[38;2;{r};{g};{b}m{text}{self.RESET}"

    def format_move(self, d: drone, label: str) -> str:
        """Format a single drone move like ``D1-roof1``.

        Args:
            d: The drone that moved.
            label: The destination zone or connection name.

        Returns:
            The formatted move.
        """
        color = str(d.target_zone.metadata["color"])
        return f"D{d.id}-{self.colorize(label, color)}"

    def run(self) -> None:
        """Run the simulation until all drones are delivered."""
        while not self.sim.is_finished():
            moves = self.sim.turn()
            print(" ".join(self.format_move(d, lbl) for d, lbl in moves))

        summary = (
            f"Total turns: {self.sim.nb_turn} | "
            f"Drones delivered: {len(self.sim.drones)}"
        )
        print()
        print(self.colorize(summary, "cyan"))
