import unittest
import check_util
import console_logger

class TestCheckUtil(unittest.TestCase):
    """ unit tests for functions in the check_util module """
    def setUp(self):
        self.logger = console_logger.ConsoleLogger()
        self.cutil = check_util.CheckUtil(self.logger)

    def test_appcompat(self):
        self.assertFalse(self.cutil.is_app_compat_issue_detected())

    def test_memory(self):
        self.assertFalse(self.cutil.is_insufficient_memory())

    def test_mount_scheme(self):
        self.assertFalse(self.cutil.is_unsupported_mount_scheme())

    def test_lvm_os(self):
        self.assertFalse(self.cutil.is_invalid_lvm_os())

    def test_precheck_failure(self):
        self.assertFalse(self.cutil.is_precheck_failure())
