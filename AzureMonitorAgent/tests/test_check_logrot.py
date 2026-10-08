#!/usr/bin/env python
"""
Unit tests for AzureMonitorAgent/ama_tst/modules/high_cpu_mem/check_logrot.py
"""

import sys
import os
import unittest
from unittest.mock import patch

# Add path for ama_tst modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'ama_tst', 'modules')))

import error_codes
from errors import error_info
from high_cpu_mem.check_logrot import hr2bytes, check_size_config


class TestHr2Bytes(unittest.TestCase):
    """Tests for hr2bytes function."""

    def test_plain_digits(self):
        self.assertEqual(hr2bytes("1024"), 1024)

    def test_kilobytes(self):
        self.assertEqual(hr2bytes("5k"), 5000)

    def test_megabytes(self):
        self.assertEqual(hr2bytes("10M"), 10000000)

    def test_gigabytes(self):
        self.assertEqual(hr2bytes("2G"), 2000000000)

    def test_invalid_unit(self):
        self.assertIsNone(hr2bytes("5X"))

    def test_invalid_format(self):
        self.assertIsNone(hr2bytes("abc"))

    def test_zero_kilobytes(self):
        self.assertEqual(hr2bytes("0k"), 0)

    def test_one_megabyte(self):
        self.assertEqual(hr2bytes("1M"), 1000000)


class TestCheckSizeConfig(unittest.TestCase):
    """Tests for check_size_config function."""

    def setUp(self):
        error_info.clear()

    def test_no_size_config(self):
        configs = {"/var/log/test.log": {"rotate 5", "daily"}}
        result = check_size_config(configs)
        self.assertEqual(result, error_codes.NO_ERROR)

    def test_invalid_size_format(self):
        configs = {"/var/log/test.log": {"size XYZ", "rotate 5"}}
        result = check_size_config(configs)
        self.assertEqual(result, error_codes.ERR_LOGROTATE_SIZE)

    @patch('os.path.getsize', return_value=500)
    def test_file_under_limit(self, mock_size):
        configs = {"/var/log/test.log": {"size 1M", "rotate 5"}}
        result = check_size_config(configs)
        self.assertEqual(result, error_codes.NO_ERROR)

    @patch('os.path.getsize', return_value=2000000)
    def test_file_over_limit(self, mock_size):
        configs = {"/var/log/test.log": {"size 1M", "rotate 5"}}
        result = check_size_config(configs)
        self.assertEqual(result, error_codes.WARN_LOGROTATE)

    @patch('os.path.getsize', side_effect=OSError(13, "Permission denied"))
    def test_permission_denied(self, mock_size):
        import errno
        err = OSError(errno.EACCES, "Permission denied")
        with patch('os.path.getsize', side_effect=err):
            configs = {"/var/log/test.log": {"size 1M", "rotate 5"}}
            result = check_size_config(configs)
            self.assertEqual(result, error_codes.ERR_SUDO_PERMS)

    @patch('os.path.getsize')
    def test_file_not_found_missingok(self, mock_size):
        import errno
        mock_size.side_effect = OSError(errno.ENOENT, "No such file")
        configs = {"/var/log/test.log": {"size 1M", "missingok"}}
        result = check_size_config(configs)
        self.assertEqual(result, error_codes.NO_ERROR)

    @patch('os.path.getsize')
    def test_file_not_found_no_missingok(self, mock_size):
        import errno
        mock_size.side_effect = OSError(errno.ENOENT, "No such file")
        configs = {"/var/log/test.log": {"size 1M", "rotate 5"}}
        result = check_size_config(configs)
        self.assertEqual(result, error_codes.ERR_FILE_MISSING)


if __name__ == '__main__':
    unittest.main()
