"""Shared helpers for VMBackup unit tests."""

import os
import sys


VMBACKUP_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
UTILS_DIR = os.path.join(VMBACKUP_DIR, "main", "Utils")


def purge_modules(*names):
    """Remove modules so import-time behavior can be tested again."""
    for name in names:
        sys.modules.pop(name, None)
