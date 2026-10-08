#!/usr/bin/env python
"""
Unit tests for AzureMonitorAgent/ama_tst/modules/install/check_os.py and supported_distros.py
"""

import sys
import os
import unittest
from unittest.mock import patch

# Add path for ama_tst modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'ama_tst', 'modules')))

import error_codes
from errors import error_info
from install import supported_distros
from install.check_os import format_alternate_versions, check_vm_supported


class TestSupportedDistros(unittest.TestCase):
    """Tests for supported_distros data."""

    def test_x86_64_has_ubuntu(self):
        self.assertIn('ubuntu', supported_distros.supported_dists_x86_64)

    def test_x86_64_has_rhel(self):
        self.assertIn('redhat', supported_distros.supported_dists_x86_64)

    def test_x86_64_has_debian(self):
        self.assertIn('debian', supported_distros.supported_dists_x86_64)

    def test_aarch64_has_ubuntu(self):
        self.assertIn('ubuntu', supported_distros.supported_dists_aarch64)

    def test_aarch64_has_rhel(self):
        self.assertIn('redhat', supported_distros.supported_dists_aarch64)

    def test_ubuntu_versions_x86(self):
        versions = supported_distros.supported_dists_x86_64['ubuntu']
        self.assertIn('22.04', versions)
        self.assertIn('20.04', versions)

    def test_all_versions_are_strings(self):
        for dist, versions in supported_distros.supported_dists_x86_64.items():
            for v in versions:
                self.assertIsInstance(v, str,
                                     f"{dist} has non-string version: {v}")


class TestFormatAlternateVersions(unittest.TestCase):
    """Tests for format_alternate_versions."""

    def test_single_version(self):
        result = format_alternate_versions("ubuntu", ["22.04"])
        self.assertEqual(result, "22.04")

    def test_two_versions(self):
        result = format_alternate_versions("ubuntu", ["20.04", "22.04"])
        self.assertEqual(result, "20.04 or 22.04")

    def test_three_versions(self):
        result = format_alternate_versions("rhel", ["7", "8", "9"])
        self.assertEqual(result, "7, 8 or 9")


class TestCheckVmSupported(unittest.TestCase):
    """Tests for check_vm_supported."""

    def setUp(self):
        error_info.clear()

    @patch('platform.machine', return_value='x86_64')
    def test_ubuntu_2204_supported(self, _):
        result = check_vm_supported("ubuntu", "22.04")
        self.assertEqual(result, error_codes.NO_ERROR)

    @patch('platform.machine', return_value='x86_64')
    def test_ubuntu_2004_supported(self, _):
        result = check_vm_supported("ubuntu", "20.04")
        self.assertEqual(result, error_codes.NO_ERROR)

    @patch('platform.machine', return_value='x86_64')
    def test_rhel_8_supported(self, _):
        result = check_vm_supported("redhat", "8.5")
        self.assertEqual(result, error_codes.NO_ERROR)

    @patch('platform.machine', return_value='x86_64')
    def test_debian_12_supported(self, _):
        result = check_vm_supported("debian", "12.0")
        self.assertEqual(result, error_codes.NO_ERROR)

    @patch('platform.machine', return_value='x86_64')
    def test_unsupported_distro(self, _):
        result = check_vm_supported("gentoo", "2.8")
        self.assertEqual(result, error_codes.ERR_OS)

    @patch('platform.machine', return_value='x86_64')
    def test_unsupported_version(self, _):
        result = check_vm_supported("ubuntu", "14.04")
        self.assertEqual(result, error_codes.ERR_OS_VER)

    @patch('platform.machine', return_value='aarch64')
    def test_aarch64_ubuntu_2204(self, _):
        result = check_vm_supported("ubuntu", "22.04")
        self.assertEqual(result, error_codes.NO_ERROR)

    @patch('platform.machine', return_value='aarch64')
    def test_aarch64_unsupported_amazon(self, _):
        # Amazon Linux not in aarch64 list
        result = check_vm_supported("amzn", "2")
        self.assertEqual(result, error_codes.ERR_OS)


if __name__ == '__main__':
    unittest.main()
