"""Filesystem fixtures for testing WAAgentUtil import behavior."""

import importlib
import os
import shutil
import sys

from test.helpers import tools


_CACHED_MODULES = ("waagent", "WAAgentUtil", "Utils", "Utils.WAAgentUtil")

_BUNDLED_LIB_STUB = '''
SOURCE = "bundled"

def AddExtensionEvent(*args, **kwargs):
    pass

class WALAEventOperation:
    Enable = "Enable"
'''


def stage_extension_tree(dest_dir):
    """Create a minimal extension tree and return its main directory."""
    main_dir = os.path.join(dest_dir, "main")
    utils_dir = os.path.join(main_dir, "Utils")
    os.makedirs(utils_dir)

    for package_dir in (main_dir, utils_dir):
        with open(os.path.join(package_dir, "__init__.py"), "w"):
            pass

    shutil.copy(
        os.path.join(tools.UTILS_DIR, "WAAgentUtil.py"),
        os.path.join(utils_dir, "WAAgentUtil.py"))

    with open(os.path.join(main_dir, "WaagentLib.py"), "w") as bundled_lib:
        bundled_lib.write(_BUNDLED_LIB_STUB)

    return main_dir


def import_waagent_util_from(main_dir):
    """Import WAAgentUtil from a staged extension tree."""
    purge_module_cache()
    sys.path.insert(0, main_dir)
    try:
        return importlib.import_module("Utils.WAAgentUtil")
    finally:
        sys.path.remove(main_dir)


def purge_module_cache():
    """Remove modules loaded by WAAgentUtil."""
    tools.purge_modules(*_CACHED_MODULES)
