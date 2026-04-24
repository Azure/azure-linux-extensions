"""Tests for `main/Utils/WAAgentUtil.py` — module-level loading behavior."""

import os
import shutil
import sys
import tempfile
import unittest

# Make `from test.helpers import ...` resolvable when running from VMBackup root.
_HERE = os.path.dirname(os.path.abspath(__file__))
_VMBACKUP_DIR = os.path.abspath(os.path.join(_HERE, os.pardir, os.pardir, os.pardir))
if _VMBACKUP_DIR not in sys.path:
    sys.path.insert(0, _VMBACKUP_DIR)

from test.helpers import waagent_fixtures  # noqa: E402


class WAAgentUtilLoadTests(unittest.TestCase):
    """Verifies that WAAgentUtil reliably locates and loads the bundled
    `WaagentLib.py` regardless of process CWD or `PYTHONPATH` state."""

    def setUp(self):
        self._original_cwd = os.getcwd()
        self._tmp_root = tempfile.mkdtemp(prefix="vmbackup-test-ext-")
        self._unrelated_cwd = tempfile.mkdtemp(prefix="vmbackup-test-cwd-")
        # Exercise the unset case — see test_pythonpath_unset_does_not_raise.
        self._saved_pythonpath = os.environ.pop("PYTHONPATH", None)

    def tearDown(self):
        os.chdir(self._original_cwd)
        shutil.rmtree(self._tmp_root, ignore_errors=True)
        shutil.rmtree(self._unrelated_cwd, ignore_errors=True)
        if self._saved_pythonpath is not None:
            os.environ["PYTHONPATH"] = self._saved_pythonpath
        waagent_fixtures.purge_module_cache()

    def test_loads_bundled_lib_when_cwd_is_extension_root(self):
        """Happy path: CWD == extension root."""
        main_dir = waagent_fixtures.stage_extension_tree(self._tmp_root)
        os.chdir(self._tmp_root)

        mod = waagent_fixtures.import_waagent_util_from(main_dir)

        self.assertEqual(getattr(mod.waagent, "SOURCE", None), "bundled")
        self.assertEqual(mod.GetPathUsed(), 1)

    def test_loads_bundled_lib_when_cwd_is_not_extension_root(self):
        """The bundled lib must be located via `__file__`, not `os.getcwd()`."""
        main_dir = waagent_fixtures.stage_extension_tree(self._tmp_root)
        os.chdir(self._unrelated_cwd)
        self.assertNotEqual(os.getcwd(), self._tmp_root)

        mod = waagent_fixtures.import_waagent_util_from(main_dir)

        self.assertEqual(getattr(mod.waagent, "SOURCE", None), "bundled")
        self.assertEqual(mod.GetPathUsed(), 1)

    def test_pythonpath_unset_does_not_raise(self):
        """Module load must tolerate `PYTHONPATH` being absent from the env."""
        self.assertNotIn("PYTHONPATH", os.environ)
        main_dir = waagent_fixtures.stage_extension_tree(self._tmp_root)

        mod = waagent_fixtures.import_waagent_util_from(main_dir)

        self.assertEqual(getattr(mod.waagent, "SOURCE", None), "bundled")


if __name__ == "__main__":
    unittest.main()
