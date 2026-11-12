"""Regression tests for extension error codes in terminal status reporting."""

import importlib
import json
import os
import shutil
import sys
import tempfile
import types
import unittest


_HERE = os.path.dirname(os.path.abspath(__file__))
_MAIN_DIR = os.path.abspath(
    os.path.join(_HERE, os.pardir, os.pardir, "main"))


class HandlerUtilityStatusTests(unittest.TestCase):
    # Code 556 and one unknown code cover the incident and shared fallback in
    # status writing and exit reporting; enumerating every error code adds no
    # coverage of those paths.

    def setUp(self):
        self._saved_modules = {}
        for name in list(sys.modules):
            if self._is_extension_module(name):
                self._saved_modules[name] = sys.modules.pop(name)
        sys.path.insert(0, _MAIN_DIR)
        self.addCleanup(self._restore_imports)

        # Only the guest-agent dependency is replaced; serialization is real.
        waagent_util = types.ModuleType("Utils.WAAgentUtil")
        waagent_util.waagent = types.ModuleType("waagent")
        sys.modules["Utils.WAAgentUtil"] = waagent_util
        self.module = importlib.import_module("Utils.HandlerUtil")
        self.status = importlib.import_module("Utils.Status")
        self.codes = importlib.import_module("ExtensionErrorCodeHelper")
        self.common = importlib.import_module("common").CommonVariables

        self._status_dir = tempfile.mkdtemp(prefix="vmbackup-status-test-")
        self.addCleanup(shutil.rmtree, self._status_dir)
        self.logs = []
        class TestHandlerUtility(self.module.HandlerUtility):
            def __init__(self):
                pass

        self.handler = TestHandlerUtility()
        self.handler._context = self.module.HandlerContext("VMSnapshotLinux")
        self.handler._context._status_dir = self._status_dir
        self.handler._context._status_file = os.path.join(
            self._status_dir, "1.status")
        self.handler.log = self.logs.append
        self.handler.eventlogger = None
        self.handler.add_telemetry_data = lambda: None
        self.handler.get_storage_details = lambda *args: None
        self.handler.get_machine_id = lambda: "test-machine"
        self.handler.get_public_settings = lambda: {
            self.common.vmType: self.common.VmTypeV2}
        self.module.HandlerUtility.telemetry_data = {}
        self.module.HandlerUtility.serializable_telemetry_data = []

    @staticmethod
    def _is_extension_module(name):
        return (name == "Utils" or name.startswith("Utils.") or
                name in ("ExtensionErrorCodeHelper", "common",
                         "MachineIdentity"))

    def _restore_imports(self):
        sys.path.remove(_MAIN_DIR)
        for name in list(sys.modules):
            if self._is_extension_module(name):
                del sys.modules[name]
        sys.modules.update(self._saved_modules)

    def _report_status(self, error_code):
        self.handler.ExtErrorCode = error_code
        return self.handler.do_status_report(
            "Enable", self.common.status_error, error_code, "Snapshot failed")

    def _assert_terminal_status_written(self, error_code, health):
        report, status_file = self._report_status(error_code)
        self.handler.write_to_status_file(status_file)
        with open(self.handler._context._status_file) as status_stream:
            written = json.load(status_stream)[0]["status"]
        # V2 reports terminal success to WALA; the embedded status retains error.
        self.assertEqual(self.common.status_success, written["status"])
        self.assertEqual(error_code, written["code"])
        embedded = json.loads(written["substatus"][0]["name"])[0]["status"]
        self.assertEqual(json.loads(report)[0]["status"], embedded)
        self.assertEqual(self.common.status_error, embedded["status"])
        self.assertEqual(error_code, embedded["code"])
        self.assertEqual(
            {"vmHealthState": health, "vmHealthStatusCode": error_code},
            embedded["vmHealthInfo"])
        return dict((item["Key"], item["Value"])
                    for item in embedded["telemetryData"])

    def test_code_556_writes_terminal_status_with_green_health(self):
        telemetry = self._assert_terminal_status_written(
            self.codes.ExtensionErrorCodeEnum.FailedHostSnapshotRemoteServerError,
            self.status.ExtVmHealthStateEnum.green)
        self.assertNotIn("unmappedExtensionErrorCode", telemetry)

    def test_unknown_code_writes_terminal_status_with_red_health(self):
        telemetry = self._assert_terminal_status_written(
            987654, self.status.ExtVmHealthStateEnum.red)
        self.assertEqual("987654", telemetry["unmappedExtensionErrorCode"])
        self.assertTrue(any("987654" in message and "red" in message
                            for message in self.logs))

    def _assert_exit_reports_status(self, error_code, health):
        self.handler.ExtErrorCode = error_code
        reports = []
        original_report = self.handler.do_status_report

        def capture_report(*args, **kwargs):
            reports.append(original_report(*args, **kwargs))

        self.handler.do_status_report = capture_report
        with self.assertRaises(SystemExit) as raised:
            self.handler.do_exit(
                7, "Enable", self.common.status_error,
                error_code, "Snapshot failed")
        self.assertEqual(7, raised.exception.code)
        self.assertEqual(1, len(reports))
        status = json.loads(reports[0][0])[0]["status"]
        self.assertEqual(error_code, status["vmHealthInfo"]["vmHealthStatusCode"])
        telemetry = dict((item["Key"], item["Value"])
                         for item in status["telemetryData"])
        self.assertEqual(str(health), telemetry["extErrorCode"])
        self.assertFalse(any("Can't update status" in message
                             for message in self.logs))
        return telemetry

    def test_exit_reports_code_556_without_lookup_failure(self):
        self._assert_exit_reports_status(
            self.codes.ExtensionErrorCodeEnum.FailedHostSnapshotRemoteServerError,
            self.status.ExtVmHealthStateEnum.green)

    def test_exit_reports_unknown_code_and_fallback_telemetry(self):
        telemetry = self._assert_exit_reports_status(
            987654, self.status.ExtVmHealthStateEnum.red)
        self.assertEqual("987654", telemetry["unmappedExtensionErrorCode"])


if __name__ == "__main__":
    unittest.main()
