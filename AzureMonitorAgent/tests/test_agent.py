#!/usr/bin/env python
"""
Unit tests for AzureMonitorAgent/agent.py - pure logic functions only.
"""

import sys
import os
import re
import unittest
from unittest.mock import patch, MagicMock

# Mock Linux-only modules before importing
for mod_name in ('grp', 'pwd'):
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()

# Mock waagent/HUtil imports that agent.py tries to load at module level
sys.modules['Utils'] = MagicMock()
sys.modules['Utils.WAAgentUtil'] = MagicMock()
sys.modules['Utils.WAAgentUtil'].waagent = MagicMock()
sys.modules['Utils.HandlerUtil'] = MagicMock()

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'LAD-AMA-Common')))

import agent


class TestIsTruthy(unittest.TestCase):
    """Tests for is_truthy function."""

    def test_true_bool(self):
        self.assertTrue(agent.is_truthy(True))

    def test_false_bool(self):
        self.assertFalse(agent.is_truthy(False))

    def test_true_string(self):
        self.assertTrue(agent.is_truthy("true"))

    def test_true_string_capitalized(self):
        self.assertTrue(agent.is_truthy("True"))

    def test_true_string_uppercase(self):
        self.assertTrue(agent.is_truthy("TRUE"))

    def test_true_string_with_whitespace(self):
        self.assertTrue(agent.is_truthy("  true  "))

    def test_false_string(self):
        self.assertFalse(agent.is_truthy("false"))

    def test_none(self):
        self.assertFalse(agent.is_truthy(None))

    def test_empty_string(self):
        self.assertFalse(agent.is_truthy(""))

    def test_zero(self):
        self.assertFalse(agent.is_truthy(0))

    def test_one(self):
        self.assertFalse(agent.is_truthy(1))


class TestIsDpkgOrRpmLocked(unittest.TestCase):
    """Tests for is_dpkg_or_rpm_locked."""

    def test_dpkg_locked(self):
        output = "E: Could not get lock /var/lib/dpkg/lock - open"
        self.assertTrue(agent.is_dpkg_or_rpm_locked(1, output))

    def test_rpm_locked(self):
        output = "error: waiting for transaction rpm lock on /var/lib/rpm/.rpm.lock"
        self.assertTrue(agent.is_dpkg_or_rpm_locked(1, output))

    def test_not_locked_success(self):
        self.assertFalse(agent.is_dpkg_or_rpm_locked(0, "Success"))

    def test_not_locked_other_error(self):
        self.assertFalse(agent.is_dpkg_or_rpm_locked(1, "Package not found"))


class TestRetryIfDpkgOrRpmLocked(unittest.TestCase):
    """Tests for retry_if_dpkg_or_rpm_locked."""

    def test_locked_returns_retry(self):
        result = agent.retry_if_dpkg_or_rpm_locked(
            1, "dpkg status database is locked by another process"
        )
        self.assertTrue(result[0])

    def test_not_locked_no_retry(self):
        result = agent.retry_if_dpkg_or_rpm_locked(0, "ok")
        self.assertFalse(result[0])


class TestFinalCheckIfDpkgOrRpmLocked(unittest.TestCase):
    """Tests for final_check_if_dpkg_or_rpm_locked."""

    def test_locked_returns_special_code(self):
        code = agent.final_check_if_dpkg_or_rpm_locked(
            1, "dpkg lock held"
        )
        self.assertEqual(code, agent.DPKGOrRPMLockedErrorCode)

    def test_not_locked_returns_original_code(self):
        code = agent.final_check_if_dpkg_or_rpm_locked(0, "ok")
        self.assertEqual(code, 0)


class TestValidatePortNumber(unittest.TestCase):
    """Tests for validate_port_number."""

    @patch('agent.hutil_log_error')
    def test_valid_port(self, mock_log):
        self.assertEqual(agent.validate_port_number("8080", "test"), "8080")

    @patch('agent.hutil_log_error')
    def test_valid_port_with_whitespace(self, mock_log):
        self.assertEqual(agent.validate_port_number("  443  ", "test"), "443")

    @patch('agent.hutil_log_error')
    def test_port_min(self, mock_log):
        self.assertEqual(agent.validate_port_number("1", "test"), "1")

    @patch('agent.hutil_log_error')
    def test_port_max(self, mock_log):
        self.assertEqual(agent.validate_port_number("65535", "test"), "65535")

    @patch('agent.hutil_log_error')
    def test_port_zero_invalid(self, mock_log):
        self.assertEqual(agent.validate_port_number("0", "test"), "")

    @patch('agent.hutil_log_error')
    def test_port_too_high(self, mock_log):
        self.assertEqual(agent.validate_port_number("65536", "test"), "")

    @patch('agent.hutil_log_error')
    def test_port_negative(self, mock_log):
        self.assertEqual(agent.validate_port_number("-1", "test"), "")

    @patch('agent.hutil_log_error')
    def test_port_non_numeric(self, mock_log):
        self.assertEqual(agent.validate_port_number("abc", "test"), "")

    @patch('agent.hutil_log_error')
    def test_port_empty(self, mock_log):
        self.assertEqual(agent.validate_port_number("", "test"), "")

    @patch('agent.hutil_log_error')
    def test_port_none(self, mock_log):
        self.assertEqual(agent.validate_port_number(None, "test"), "")


class TestGetProxyMode(unittest.TestCase):
    """Tests for get_proxy_mode."""

    def test_none_settings(self):
        self.assertIsNone(agent.get_proxy_mode(None))

    def test_no_proxy_key(self):
        self.assertIsNone(agent.get_proxy_mode({"other": "value"}))

    def test_proxy_no_mode(self):
        self.assertIsNone(agent.get_proxy_mode({"proxy": {}}))

    def test_proxy_with_mode(self):
        self.assertEqual(
            agent.get_proxy_mode({"proxy": {"mode": "application"}}),
            "application"
        )

    def test_proxy_none_value(self):
        self.assertIsNone(agent.get_proxy_mode({"proxy": None}))


class TestGetServiceCommand(unittest.TestCase):
    """Tests for get_service_command."""

    @patch('agent.is_systemd', return_value=True)
    def test_systemd_single_op(self, _):
        cmd = agent.get_service_command("myservice", "start")
        self.assertEqual(cmd, "systemctl start myservice")

    @patch('agent.is_systemd', return_value=True)
    def test_systemd_multiple_ops(self, _):
        cmd = agent.get_service_command("myservice", "daemon-reload", "restart")
        self.assertEqual(cmd, "systemctl daemon-reload myservice && systemctl restart myservice")

    @patch('agent.is_systemd', return_value=False)
    @patch('agent.hutil_log_info')
    def test_initd_fallback(self, _, __):
        cmd = agent.get_service_command("myservice", "start")
        self.assertEqual(cmd, "/etc/init.d/myservice start")


class TestConstants(unittest.TestCase):
    """Tests for agent constants."""

    def test_error_codes(self):
        self.assertEqual(agent.GenericErrorCode, 1)
        self.assertEqual(agent.UnsupportedOperatingSystem, 51)
        self.assertEqual(agent.MissingorInvalidParameterErrorCode, 53)
        self.assertEqual(agent.DPKGOrRPMLockedErrorCode, 56)
        self.assertEqual(agent.MissingDependency, 52)

    def test_supported_arch(self):
        self.assertIn('x86_64', agent.SupportedArch)
        self.assertIn('aarch64', agent.SupportedArch)

    def test_config_keys(self):
        self.assertEqual(agent.GenevaConfigKey, "genevaConfiguration")
        self.assertEqual(agent.AzureMonitorConfigKey, "azureMonitorConfiguration")


if __name__ == '__main__':
    unittest.main()
