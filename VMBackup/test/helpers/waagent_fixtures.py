"""
Test fixtures for `main/Utils/WAAgentUtil.py`.

`WAAgentUtil.py` runs filesystem-dependent code at import time to locate and
load a `waagent` module. To exercise that behavior in tests, we need to
stage a fresh, minimal copy of the extension tree on disk and import the
module against it.
"""

import importlib
import os
import shutil
import sys

from test.helpers import tools


# Modules that get cached in `sys.modules` once WAAgentUtil is imported.
# Tests must drop these before re-importing so module-level code re-runs.
_CACHED_MODULES = ("waagent", "WAAgentUtil", "Utils", "Utils.WAAgentUtil")

# Minimal stand-in for `main/WaagentLib.py`. The real file is large; tests
# only need the symbols WAAgentUtil's module-level code touches.
_BUNDLED_LIB_STUB = '''
"""Test stub for WaagentLib.py."""
SOURCE = "bundled"

def RunGetOutput(cmd, chk_err=True):
    return 0, ""

def AddExtensionEvent(*args, **kwargs):
    pass

class WALAEventOperation:
    HeartBeat = "HeartBeat"
    Provision = "Provision"
    Install = "Install"
    UnInstall = "UnInstall"
    Disable = "Disable"
    Enable = "Enable"
    Download = "Download"
    Upgrade = "Upgrade"
    Update = "Update"
'''


def stage_extension_tree(dest_dir, with_bundled_lib=True, bundled_lib_source=None):
    """Lay out a minimal extension tree under `dest_dir` and return the path
    to the staged `main/` directory.

    Layout produced::

        dest_dir/
          main/
            __init__.py
            WaagentLib.py        (only if with_bundled_lib=True)
            Utils/
              __init__.py
              WAAgentUtil.py     (copied verbatim from the repo)

    `bundled_lib_source`, when given, overrides the contents written to
    `WaagentLib.py`.
    """
    main_dir = os.path.join(dest_dir, "main")
    utils_dir = os.path.join(main_dir, "Utils")
    os.makedirs(utils_dir, exist_ok=True)
    open(os.path.join(main_dir, "__init__.py"), "w").close()
    open(os.path.join(utils_dir, "__init__.py"), "w").close()
    shutil.copy(
        os.path.join(tools.UTILS_DIR, "WAAgentUtil.py"),
        os.path.join(utils_dir, "WAAgentUtil.py"),
    )
    if with_bundled_lib:
        with open(os.path.join(main_dir, "WaagentLib.py"), "w") as f:
            f.write(bundled_lib_source if bundled_lib_source is not None else _BUNDLED_LIB_STUB)
    return main_dir


def import_waagent_util_from(main_dir):
    """Force a fresh import of `Utils.WAAgentUtil` against a staged tree."""
    purge_module_cache()
    sys.path.insert(0, main_dir)
    try:
        return importlib.import_module("Utils.WAAgentUtil")
    finally:
        try:
            sys.path.remove(main_dir)
        except ValueError:
            pass


def purge_module_cache():
    """Drop any cached WAAgentUtil-related modules from `sys.modules`."""
    tools.purge_modules(*_CACHED_MODULES)
