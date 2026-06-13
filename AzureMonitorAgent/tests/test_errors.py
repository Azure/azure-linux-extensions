#!/usr/bin/env python
"""
Unit tests for AzureMonitorAgent/ama_tst/modules/error_codes.py and errors.py
"""

import sys
import os
import unittest
from unittest.mock import patch

# Add path for ama_tst modules (they use relative imports from 'modules' dir)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'ama_tst', 'modules')))

import error_codes
from errors import is_error, warnings, error_messages, print_errors, error_info, err_summary


class TestErrorCodes(unittest.TestCase):
    """Tests for error_codes constants."""

    def test_no_error_is_zero(self):
        self.assertEqual(error_codes.NO_ERROR, 0)

    def test_user_exit_is_one(self):
        self.assertEqual(error_codes.USER_EXIT, 1)

    def test_installation_errors_in_100_range(self):
        self.assertGreaterEqual(error_codes.ERR_BITS, 100)
        self.assertLess(error_codes.ERR_BITS, 200)
        self.assertGreaterEqual(error_codes.ERR_AMA_INSTALL, 100)
        self.assertLess(error_codes.ERR_AMA_INSTALL, 200)

    def test_onboarding_errors_in_200_range(self):
        self.assertGreaterEqual(error_codes.ERR_AMA_PARAMETERS, 200)
        self.assertLess(error_codes.ERR_AMA_PARAMETERS, 300)

    def test_cpu_mem_errors_in_300_range(self):
        self.assertGreaterEqual(error_codes.ERR_FILE_MISSING, 300)
        self.assertLess(error_codes.ERR_FILE_MISSING, 400)

    def test_syslog_errors_in_400_range(self):
        self.assertGreaterEqual(error_codes.ERR_SYSLOG, 400)
        self.assertLess(error_codes.ERR_SYSLOG, 500)

    def test_custom_logs_errors_in_500_range(self):
        self.assertGreaterEqual(error_codes.ERR_CL_CONF, 500)
        self.assertLess(error_codes.ERR_CL_CONF, 600)


class TestIsError(unittest.TestCase):
    """Tests for errors.is_error function."""

    def test_no_error_is_not_error(self):
        self.assertFalse(is_error(error_codes.NO_ERROR))

    def test_warnings_are_not_errors(self):
        self.assertFalse(is_error(error_codes.WARN_INTERNET))
        self.assertFalse(is_error(error_codes.WARN_INTERNET_CONN))
        self.assertFalse(is_error(error_codes.WARN_OPENSSL_PROXY))
        self.assertFalse(is_error(error_codes.WARN_MDSD_ERR_FILE))
        self.assertFalse(is_error(error_codes.WARN_RESTART_LOOP))

    def test_actual_errors_are_errors(self):
        self.assertTrue(is_error(error_codes.ERR_SUDO_PERMS))
        self.assertTrue(is_error(error_codes.ERR_OS))
        self.assertTrue(is_error(error_codes.ERR_AMA_INSTALL))
        self.assertTrue(is_error(error_codes.ERR_ENDPT))
        self.assertTrue(is_error(error_codes.ERR_SYSLOG))


class TestWarnings(unittest.TestCase):
    """Tests for warning set correctness."""

    def test_all_warnings_have_messages(self):
        for warn_code in warnings:
            self.assertIn(warn_code, error_messages,
                          f"Warning code {warn_code} missing from error_messages")

    def test_warnings_set_size(self):
        self.assertGreaterEqual(len(warnings), 5)


class TestErrorMessages(unittest.TestCase):
    """Tests for error_messages dictionary."""

    def test_all_error_codes_have_messages(self):
        """All defined error codes (except NO_ERROR, USER_EXIT) should have messages."""
        all_codes = [
            error_codes.ERR_SUDO_PERMS, error_codes.ERR_FOUND, error_codes.ERR_BITS,
            error_codes.ERR_OS_VER, error_codes.ERR_OS, error_codes.ERR_FINDING_OS,
            error_codes.ERR_FREE_SPACE, error_codes.ERR_PKG_MANAGER,
            error_codes.ERR_MULTIPLE_AMA, error_codes.ERR_AMA_INSTALL,
            error_codes.ERR_AMA_PARAMETERS, error_codes.ERR_NO_DCR,
            error_codes.ERR_ENDPT, error_codes.ERR_SYSLOG,
        ]
        for code in all_codes:
            self.assertIn(code, error_messages,
                          f"Error code {code} missing from error_messages")

    def test_messages_are_strings(self):
        for code, msg in error_messages.items():
            self.assertIsInstance(msg, str)
            self.assertGreater(len(msg), 0)


class TestPrintErrors(unittest.TestCase):
    """Tests for print_errors function."""

    def setUp(self):
        # Clear global state before each test
        error_info.clear()
        err_summary.clear()

    def test_no_error_returns_no_error(self):
        result = print_errors(error_codes.NO_ERROR)
        self.assertEqual(result, error_codes.NO_ERROR)

    def test_user_exit_returns_user_exit(self):
        result = print_errors(error_codes.USER_EXIT)
        self.assertEqual(result, error_codes.USER_EXIT)

    def test_warning_returns_no_error(self):
        error_info.append(("test_cmd",))
        result = print_errors(error_codes.WARN_INTERNET_CONN)
        self.assertEqual(result, error_codes.NO_ERROR)

    def test_error_returns_err_found(self):
        error_info.append(("test",))
        result = print_errors(error_codes.ERR_SUDO_PERMS)
        self.assertEqual(result, error_codes.ERR_FOUND)

    def test_error_appends_to_summary(self):
        error_info.append(("/etc/test",))
        print_errors(error_codes.ERR_SUDO_PERMS)
        self.assertTrue(len(err_summary) > 0)
        self.assertIn("ERROR FOUND", err_summary[0])


if __name__ == '__main__':
    unittest.main()
