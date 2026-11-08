"""Allow ``python -m chartgen``."""

import sys

from chartgen.cli import main

if __name__ == "__main__":
    sys.exit(main())
