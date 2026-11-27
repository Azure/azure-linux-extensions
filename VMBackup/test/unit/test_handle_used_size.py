"""Tests that handle.get_status_to_report reports the computed used size uncapped."""

import importlib
import json
import os
import sys
import types
import unittest


_HERE = os.path.dirname(os.path.abspath(__file__))
_MAIN_DIR = os.path.abspath(
    os.path.join(_HERE, os.pardir, os.pardir, "main"))

ONE_TIB = 1024 ** 4


class _FakeLogger(object):
    def __init__(self):
        self.messages = []

    def log(self, msg, *args, **kwargs):
        self.messages.append(msg)


class _FakeParaParser(object):
    def __init__(self, include_lun_list):
        self.includeLunList = include_lun_list
        self.taskId = "task-id"
        self.commandStartTimeUTCTicks = "0"


class GetStatusToReportUsedSizeTests(unittest.TestCase):

    def setUp(self):
        saved_modules = dict(sys.modules)
        sys.path.insert(0, _MAIN_DIR)

        def restore():
            sys.path.remove(_MAIN_DIR)
            for name in list(sys.modules):
                if name not in saved_modules:
                    del sys.modules[name]
            sys.modules.update(saved_modules)
        self.addCleanup(restore)

        waagent_util = types.ModuleType("Utils.WAAgentUtil")
        waagent_util.waagent = types.ModuleType("waagent")
        sys.modules["Utils.WAAgentUtil"] = waagent_util
        self.handle = importlib.import_module("handle")
        handler_util = importlib.import_module("Utils.HandlerUtil")
        common = importlib.import_module("common").CommonVariables
        self.common = common

        class TestHandlerUtility(handler_util.HandlerUtility):
            def __init__(self):
                self.partitioncount = 0
                self.storageDetailsObj = None

        hutil = TestHandlerUtility()
        hutil._context = handler_util.HandlerContext("VMSnapshotLinux")
        hutil.log = lambda *args, **kwargs: None
        hutil.eventlogger = None
        hutil.add_telemetry_data = lambda: None
        hutil.get_machine_id = lambda: "test-machine"
        hutil.get_public_settings = lambda: {common.vmType: common.VmTypeV2}
        handler_util.HandlerUtility.telemetry_data = {}
        handler_util.HandlerUtility.serializable_telemetry_data = []

        self.logger = _FakeLogger()
        self.size_calc_calls = []
        self.handle.hutil = hutil
        self.handle.backup_logger = self.logger
        self.handle.MyPatching = None
        self.handle.total_used_size = -1
        self.handle.size_calculation_failed = False

    def _install_size_calculation(self, computed_size, failed):
        calls = self.size_calc_calls

        class FakeSizeCalculation(object):
            def __init__(self, **kwargs):
                calls.append(kwargs)

            def get_total_used_size(self):
                return computed_size, failed

        fake_module = types.ModuleType("Utils.SizeCalculation")
        fake_module.SizeCalculation = FakeSizeCalculation
        self.handle.SizeCalculation = fake_module

    def _report(self, computed_size, lun_count, failed=False):
        self._install_size_calculation(computed_size, failed)
        self.handle.para_parser = _FakeParaParser(list(range(lun_count)))
        blob_report, file_report = self.handle.get_status_to_report(
            self.common.status_success, self.common.success, "done")
        self.assertIsNotNone(blob_report)
        self.assertIsNotNone(file_report)
        self.assertEqual(1, len(self.size_calc_calls))
        return (json.loads(blob_report)[0]["status"]["storageDetails"],
                json.loads(file_report)[0]["status"]["storageDetails"])

    def _assert_reported_uncapped(self, computed_size, lun_count):
        blob_storage, file_storage = self._report(computed_size, lun_count)
        self.assertEqual(computed_size, blob_storage["totalUsedSizeInBytes"])
        self.assertEqual(computed_size, file_storage["totalUsedSizeInBytes"])
        self.assertFalse(blob_storage["isSizeComputationFailed"])
        self.assertEqual(computed_size, self.handle.total_used_size)
        self.assertTrue(any(
            str(computed_size) in m and "number_of_blobs : {0}".format(lun_count) in m
            for m in self.logger.messages))

    def test_multiple_luns_above_lun_count_tib_is_not_capped(self):
        self._assert_reported_uncapped(10 * ONE_TIB, lun_count=4)

    def test_size_within_previous_cap_is_unchanged(self):
        self._assert_reported_uncapped(ONE_TIB - 1, lun_count=1)


if __name__ == "__main__":
    unittest.main()
