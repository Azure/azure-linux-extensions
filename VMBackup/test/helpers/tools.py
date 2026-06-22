"""
Generic helpers shared by VMBackup unit tests.

This module is intentionally small and dependency-free (stdlib only). Anything
that's specific to one production module belongs in a per-feature fixtures
module under this directory, not here.
"""

import os
import sys


# Repo paths. test/helpers/tools.py -> ../.. = VMBackup/
VMBACKUP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
MAIN_DIR = os.path.join(VMBACKUP_DIR, "main")
UTILS_DIR = os.path.join(MAIN_DIR, "Utils")


def purge_modules(*names):
    """Drop the named modules from `sys.modules`.

    Useful when a test needs to force a fresh import of a module whose
    module-level (import-time) code is part of the behavior under test.
    """
    for name in names:
        sys.modules.pop(name, None)
