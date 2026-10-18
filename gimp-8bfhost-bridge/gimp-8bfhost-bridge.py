#!/usr/bin/env python3
"""GIMP 3 entry point for gimp-8bfhost-bridge.

GIMP runs this file; the code lives in the gimp_8bfhost_bridge package
next to it.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gimp_8bfhost_bridge.plugin import main  # noqa: E402

main()
