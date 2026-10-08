"""Tests for WAAgentUtil module loading."""

import os
import shutil
import sys
import tempfile
import unittest


_HERE = os.path.dirname(os.path.abspath(__file__))
_VMBACKUP_DIR = os.path.abspath(
    os.path.join(_HERE, os.pardir, os.pardir))
if _VMBACKUP_DIR not in sys.path:
    sys.path.insert(0, _VMBACKUP_DIR)

from test.helpers import waagent_fixtures


class WAAgentUtilLoadTests(unittest.TestCase):

    def setUp(self):
        self._original_cwd = os.getcwd()
        self._extension_root = tempfile.mkdtemp(prefix="vmbackup-test-ext-")
        self._unrelated_cwd = tempfile.mkdtemp(prefix="vmbackup-test-cwd-")
        self._saved_pythonpath = os.environ.pop("PYTHONPATH", None)

    def tearDown(self):
        os.chdir(self._original_cwd)
        shutil.rmtree(self._extension_root, ignore_errors=True)
        shutil.rmtree(self._unrelated_cwd, ignore_errors=True)
        if self._saved_pythonpath is not None:
            os.environ["PYTHONPATH"] = self._saved_pythonpath
        waagent_fixtures.purge_module_cache()

    def test_loads_bundled_lib_from_extension_root(self):
        main_dir = waagent_fixtures.stage_extension_tree(self._extension_root)
        os.chdir(self._extension_root)

        module = waagent_fixtures.import_waagent_util_from(main_dir)

        self.assertEqual("bundled", module.waagent.SOURCE)
        self.assertEqual(1, module.GetPathUsed())

    def test_loads_bundled_lib_from_unrelated_cwd(self):
        main_dir = waagent_fixtures.stage_extension_tree(self._extension_root)
        os.chdir(self._unrelated_cwd)

        module = waagent_fixtures.import_waagent_util_from(main_dir)

        self.assertEqual("bundled", module.waagent.SOURCE)
        self.assertEqual(1, module.GetPathUsed())

    def test_searches_tolerate_unset_pythonpath(self):
        self.assertNotIn("PYTHONPATH", os.environ)
        main_dir = waagent_fixtures.stage_extension_tree(self._extension_root)
        module = waagent_fixtures.import_waagent_util_from(main_dir)

        original_isfile = module.os.path.isfile
        module.os.path.isfile = lambda path: False
        try:
            self.assertIsNone(module.searchWAAgent())
            self.assertIsNone(module.searchWAAgentOld())
        finally:
            module.os.path.isfile = original_isfile


if __name__ == "__main__":
    unittest.main()
