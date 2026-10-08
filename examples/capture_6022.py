#!/usr/bin/python3
"""
Thin wrapper, the implementation lives in PyHT6022.capture.

Run directly from a checkout (the PyHT6022 symlink in this directory makes
the package importable) or use the installed 'capture_6022' command.
"""

import sys

from PyHT6022.capture import main

if __name__ == "__main__":
    sys.exit(main())
