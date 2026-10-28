"""Tests for FreezeSnapshotter.updateErrorCode host-telemetry handling."""

import os
import sys
import unittest


_HERE = os.path.dirname(os.path.abspath(__file__))
_MAIN_DIR = os.path.abspath(
    os.path.join(_HERE, os.pardir, os.pardir, "main"))
if _MAIN_DIR not in sys.path:
    sys.path.insert(0, _MAIN_DIR)

from freezesnapshotter import FreezeSnapshotter
from common import CommonVariables
from ExtensionErrorCodeHelper import ExtensionErrorCodeEnum
from Utils import HandlerUtil


class _FakeLogger(object):
    def log(self, *args, **kwargs):
        pass


class UpdateErrorCodeAllFailedTests(unittest.TestCase):

    def setUp(self):
        # Bypass __init__ (needs a full para_parser / hutil); only set what updateErrorCode uses.
        self.snapshotter = FreezeSnapshotter.__new__(FreezeSnapshotter)
        self.snapshotter.logger = _FakeLogger()
        self.snapshotter.extensionErrorCode = ExtensionErrorCodeEnum.success
        self._saved_telemetry = dict(HandlerUtil.HandlerUtility.telemetry_data)

    def tearDown(self):
        HandlerUtil.HandlerUtility.telemetry_data = self._saved_telemetry

    def _set_host_status(self, do_status, pre_status):
        HandlerUtil.HandlerUtility.telemetry_data[CommonVariables.hostStatusCodeDoSnapshot] = do_status
        HandlerUtil.HandlerUtility.telemetry_data[CommonVariables.hostStatusCodePreSnapshot] = pre_status

    def test_remote_server_error_when_dosnapshot_556_and_presnapshot_200(self):
        self._set_host_status("556", "200")
        run_result, _ = self.snapshotter.updateErrorCode(None, True, False, False)
        self.assertEqual(ExtensionErrorCodeEnum.FailedHostSnapshotRemoteServerError, run_result)
        self.assertEqual(
            ExtensionErrorCodeEnum.FailedHostSnapshotRemoteServerError,
            self.snapshotter.extensionErrorCode)

    def test_retryable_error_when_dosnapshot_504(self):
        self._set_host_status("504", "200")
        run_result, _ = self.snapshotter.updateErrorCode(None, True, False, False)
        self.assertEqual(ExtensionErrorCodeEnum.FailedHostSnapshotRetryableError, run_result)
        self.assertEqual(
            ExtensionErrorCodeEnum.FailedHostSnapshotRetryableError,
            self.snapshotter.extensionErrorCode)

    def test_no_network_error_for_other_dosnapshot_status(self):
        self._set_host_status("555", "200")
        run_result, _ = self.snapshotter.updateErrorCode(None, True, False, False)
        self.assertEqual(ExtensionErrorCodeEnum.FailedRetryableSnapshotFailedNoNetwork, run_result)
        self.assertEqual(
            ExtensionErrorCodeEnum.FailedRetryableSnapshotFailedNoNetwork,
            self.snapshotter.extensionErrorCode)


if __name__ == "__main__":
    unittest.main()
