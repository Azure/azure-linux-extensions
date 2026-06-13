#!/usr/bin/env python
"""
Unit tests for AzureMonitorAgent/ama_tst/modules/helpers.py - pure logic functions
"""

import sys
import os
import json
import unittest
from unittest.mock import patch, MagicMock, mock_open

# Add path for ama_tst modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'ama_tst', 'modules')))

import error_codes
from helpers import geninfo_lookup, general_info, check_ama_installed


class TestGeninfoLookup(unittest.TestCase):
    """Tests for geninfo_lookup function."""

    def setUp(self):
        general_info.clear()

    def test_existing_key(self):
        general_info['test_key'] = 'test_value'
        self.assertEqual(geninfo_lookup('test_key'), 'test_value')

    def test_missing_key(self):
        self.assertIsNone(geninfo_lookup('nonexistent'))

    def test_none_value(self):
        general_info['null_key'] = None
        self.assertIsNone(geninfo_lookup('null_key'))

    def test_empty_string_value(self):
        general_info['empty'] = ''
        self.assertEqual(geninfo_lookup('empty'), '')


class TestCheckAmaInstalled(unittest.TestCase):
    """Tests for check_ama_installed function."""

    def test_none_versions(self):
        exists, unique = check_ama_installed(None)
        self.assertFalse(exists)
        self.assertFalse(unique)

    def test_empty_list(self):
        exists, unique = check_ama_installed([])
        self.assertFalse(exists)
        self.assertFalse(unique)

    def test_single_version(self):
        exists, unique = check_ama_installed(['1.28.0'])
        self.assertTrue(exists)
        self.assertTrue(unique)

    def test_multiple_versions(self):
        exists, unique = check_ama_installed(['1.28.0', '1.27.0'])
        self.assertTrue(exists)
        self.assertFalse(unique)


class TestFindVmDistro(unittest.TestCase):
    """Tests for find_vm_distro OS parsing logic (os-release fallback)."""

    @patch('builtins.open', mock_open(read_data='ID=ubuntu\nVERSION_ID="22.04"\n'))
    def test_parses_os_release_ubuntu(self):
        from helpers import find_vm_distro
        dist, ver, err = find_vm_distro()
        self.assertEqual(dist, 'ubuntu')
        self.assertEqual(ver, '22.04')
        self.assertIsNone(err)

    @patch('builtins.open', mock_open(read_data='ID=rhel\nVERSION_ID="8.5"\n'))
    def test_parses_os_release_rhel(self):
        from helpers import find_vm_distro
        dist, ver, err = find_vm_distro()
        self.assertEqual(dist, 'rhel')
        self.assertEqual(ver, '8.5')

    @patch('builtins.open', mock_open(read_data='ID="sles"\nVERSION_ID="15.3"\n'))
    def test_parses_os_release_sles(self):
        from helpers import find_vm_distro
        dist, ver, err = find_vm_distro()
        self.assertEqual(dist, 'sles')
        self.assertEqual(ver, '15.3')

    @patch('builtins.open', side_effect=FileNotFoundError("not found"))
    def test_file_not_found(self, _):
        from helpers import find_vm_distro
        dist, ver, err = find_vm_distro()
        self.assertIsNone(dist)
        self.assertIsNone(ver)
        self.assertIsNotNone(err)


if __name__ == '__main__':
    unittest.main()
