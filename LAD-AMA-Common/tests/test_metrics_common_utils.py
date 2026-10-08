#!/usr/bin/env python
"""
Unit tests for metrics_ext_utils/metrics_common_utils.py
"""

import sys
import os
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from metrics_ext_utils.metrics_common_utils import is_systemd, is_arc_installed, get_arc_endpoint


class TestIsSystemd(unittest.TestCase):
    """Tests for is_systemd function."""

    @patch('os.path.isdir')
    def test_returns_true_when_systemd_dir_exists(self, mock_isdir):
        mock_isdir.return_value = True
        self.assertTrue(is_systemd())
        mock_isdir.assert_called_with("/run/systemd/system")

    @patch('os.path.isdir')
    def test_returns_false_when_systemd_dir_missing(self, mock_isdir):
        mock_isdir.return_value = False
        self.assertFalse(is_systemd())


class TestIsArcInstalled(unittest.TestCase):
    """Tests for is_arc_installed function."""

    @patch('os.system')
    def test_returns_true_when_himdsd_running(self, mock_system):
        mock_system.return_value = 0
        self.assertTrue(is_arc_installed())
        mock_system.assert_called_with("systemctl status himdsd 1>/dev/null 2>&1")

    @patch('os.system')
    def test_returns_false_when_himdsd_not_running(self, mock_system):
        mock_system.return_value = 3  # systemctl returns non-zero for inactive
        self.assertFalse(is_arc_installed())


class TestGetArcEndpoint(unittest.TestCase):
    """Tests for get_arc_endpoint function."""

    @patch('builtins.open', unittest.mock.mock_open(
        read_data='DefaultEnvironment="IMDS_ENDPOINT=http://localhost:40342"\n'))
    def test_parses_endpoint_from_conf(self):
        endpoint = get_arc_endpoint()
        self.assertEqual(endpoint, "http://localhost:40342")

    @patch('builtins.open', unittest.mock.mock_open(
        read_data='DefaultEnvironment="IMDS_ENDPOINT=http://10.0.0.1:40342"\nOTHER="value"\n'))
    def test_parses_custom_endpoint(self):
        endpoint = get_arc_endpoint()
        self.assertEqual(endpoint, "http://10.0.0.1:40342")


if __name__ == '__main__':
    unittest.main()
