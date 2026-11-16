"""Tests for used-size reporting in handle.get_status_to_report (billing)."""

import os
import sys
import types
import unittest

try:
    from unittest import mock
except ImportError:
    import mock


_HERE = os.path.dirname(os.path.abspath(__file__))
_MAIN_DIR = os.path.abspath(
    os.path.join(_HERE, os.pardir, os.pardir, "main"))
if _MAIN_DIR not in sys.path:
    sys.path.insert(0, _MAIN_DIR)

# Allow importing handle.py on non-Linux dev boxes.
for _name in ("pwd", "grp", "fcntl", "termios"):
    try:
        __import__(_name)
    except ImportError:
        sys.modules[_name] = types.ModuleType(_name)
if not hasattr(sys.modules["pwd"], "getpwuid"):
    sys.modules["pwd"].getpwuid = lambda uid: None

import handle
from Utils import HandlerUtil

ONE_TIB = 1024 ** 4


class _FakeLogger(object):
    def __init__(self):
        self.messages = []

    def log(self, msg, *args, **kwargs):
        self.messages.append(msg)


class _FakeParaParser(object):
    def __init__(self, include_lun_list):
        self.includeLunList = include_lun_list
        self.taskId = "task"
        self.commandStartTimeUTCTicks = "0"


class GetStatusToReportUsedSizeTests(unittest.TestCase):

    def setUp(self):
        self._saved_telemetry = dict(HandlerUtil.HandlerUtility.telemetry_data)
        self.hutil = mock.Mock()
        self.hutil.do_status_report.return_value = ("blob", "file")
        self.logger = _FakeLogger()
        self._patches = [
            mock.patch.object(handle, "hutil", self.hutil, create=True),
            mock.patch.object(handle, "backup_logger", self.logger, create=True),
            mock.patch.object(handle, "MyPatching", None, create=True),
            mock.patch.object(handle, "total_used_size", -1, create=True),
            mock.patch.object(handle, "size_calculation_failed", False, create=True),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        HandlerUtil.HandlerUtility.telemetry_data = self._saved_telemetry

    def _report(self, computed_size, include_lun_list, failed=False):
        with mock.patch.object(handle, "para_parser", _FakeParaParser(include_lun_list), create=True), \
                mock.patch.object(handle.SizeCalculation, "SizeCalculation") as size_calc_cls:
            size_calc_cls.return_value.get_total_used_size.return_value = (computed_size, failed)
            handle.get_status_to_report("success", 1, "msg")
        return self.hutil.do_status_report.call_args[1]

    def test_used_size_above_1tib_per_lun_is_not_capped(self):
        computed = 3 * ONE_TIB + 12345
        kwargs = self._report(computed, include_lun_list=[-1])

        self.assertEqual(computed, kwargs["total_size"])
        self.assertFalse(kwargs["failure_flag"])
        telemetry = HandlerUtil.HandlerUtility.telemetry_data
        self.assertEqual(str(computed), telemetry["totalUsedSizeInBytes"])
        self.assertEqual("False", telemetry["isSizeComputationFailed"])
        self.assertEqual("1", telemetry["includedLunCount"])
        self.assertTrue(any(str(computed) in m for m in self.logger.messages))

    def test_size_computation_failure_is_reported(self):
        kwargs = self._report(0, include_lun_list=[], failed=True)

        self.assertEqual(0, kwargs["total_size"])
        self.assertTrue(kwargs["failure_flag"])
        telemetry = HandlerUtil.HandlerUtility.telemetry_data
        self.assertEqual("True", telemetry["isSizeComputationFailed"])
        self.assertEqual("0", telemetry["includedLunCount"])


if __name__ == "__main__":
    unittest.main()
