from parser import parser
from errors import Invalid_Argument
from render import TerminalRender
from simulation import simulation
import sys


if __name__ == "__main__":
    args = sys.argv

    try:
        if len(args) != 2:
            raise Invalid_Argument(f"Argument should be 2 not {len(args)}")
        p = parser(args[1])
        s = simulation(p)
        TerminalRender(s).run()
    except KeyboardInterrupt:
        print("\nInterrupted", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(e, file=sys.stderr)
        sys.exit(1)
