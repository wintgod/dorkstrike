"""Allow running DorkStrike as a module: python -m dorkstrike"""

import sys

try:
    from dorkstrike import main
    sys.exit(main())
except KeyboardInterrupt:
    print("\n\n  ⚠  DorkStrike interrupted. Exiting.\n")
    sys.exit(130)
