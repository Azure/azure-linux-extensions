#!/usr/bin/env python
"""
Unit tests for telegraf_config_handler.parse_config
"""

import sys
import os
import json
import unittest
from unittest.mock import patch, MagicMock

# Add parent dir to path so we can import the modules under test
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from telegraf_utils.telegraf_config_handler import parse_config, write_configs


def make_counter(display_name, interval="60s", sink=None, config_ids=None):
    """Helper to create a counter entry for parse_config input data."""
    if sink is None:
        sink = ["mdsd", "me"]
    if config_ids is None:
        config_ids = ["configId1"]
    return {
        "displayName": display_name,
        "interval": interval,
        "sink": sink,
        "configurationId": config_ids,
    }


ME_URL = "unix:///var/run/me/me_influx.socket"
MDSD_URL = "unix:///var/run/mdsd/mdsd_influx.socket"
AZ_RESOURCE_ID = "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1"
SUBSCRIPTION_ID = "sub1"
RESOURCE_GROUP = "rg1"
REGION = "westus2"
VM_NAME = ""


class TestParseConfigBasic(unittest.TestCase):
    """Basic tests for parse_config."""

    def test_empty_data_raises(self):
        """parse_config should raise on empty input."""
        with self.assertRaises(Exception) as ctx:
            parse_config([], ME_URL, MDSD_URL, False, AZ_RESOURCE_ID,
                         SUBSCRIPTION_ID, RESOURCE_GROUP, REGION, VM_NAME)
        self.assertIn("Empty config data", str(ctx.exception))

    def test_none_urls_raises(self):
        """parse_config should raise if me_url or mdsd_url is None."""
        data = [make_counter("% Used Memory")]
        with self.assertRaises(Exception):
            parse_config(data, None, MDSD_URL, False, AZ_RESOURCE_ID,
                         SUBSCRIPTION_ID, RESOURCE_GROUP, REGION, VM_NAME)
        with self.assertRaises(Exception):
            parse_config(data, ME_URL, None, False, AZ_RESOURCE_ID,
                         SUBSCRIPTION_ID, RESOURCE_GROUP, REGION, VM_NAME)

    @patch('telegraf_utils.telegraf_config_handler.get_handler_vars')
    def test_single_counter_generates_config(self, mock_handler):
        """A single valid counter should produce config output."""
        mock_handler.return_value = ("/var/log/azure", "/etc/azure")
        data = [make_counter("% Used Memory")]
        output, namespaces = parse_config(data, ME_URL, MDSD_URL, False,
                                          AZ_RESOURCE_ID, SUBSCRIPTION_ID,
                                          RESOURCE_GROUP, REGION, VM_NAME)
        # Should have intermediate.json + at least one plugin config + telegraf.conf
        self.assertGreaterEqual(len(output), 3)
        filenames = [f["filename"] for f in output]
        self.assertIn("intermediate.json", filenames)
        self.assertIn("telegraf.conf", filenames)

    @patch('telegraf_utils.telegraf_config_handler.get_handler_vars')
    def test_config_contains_input_plugin(self, mock_handler):
        """Generated config should contain the correct [[inputs.*]] directive."""
        mock_handler.return_value = ("/var/log/azure", "/etc/azure")
        data = [make_counter("% Used Memory")]
        output, _ = parse_config(data, ME_URL, MDSD_URL, False,
                                 AZ_RESOURCE_ID, SUBSCRIPTION_ID,
                                 RESOURCE_GROUP, REGION, VM_NAME)
        plugin_configs = [f for f in output if f["filename"] not in ("intermediate.json", "telegraf.conf")]
        self.assertTrue(len(plugin_configs) > 0)
        # mem plugin should have [[inputs.mem]]
        mem_configs = [f for f in plugin_configs if "mem" in f["filename"]]
        self.assertTrue(len(mem_configs) > 0)
        self.assertIn("[[inputs.mem]]", mem_configs[0]["data"])


class TestParseConfigUniqueFilenames(unittest.TestCase):
    """Tests that config filenames are unique across plugins in the same omiclass."""

    @patch('telegraf_utils.telegraf_config_handler.get_handler_vars')
    def test_multiple_plugins_same_omiclass_unique_filenames(self, mock_handler):
        """
        When multiple plugins share an omiclass (e.g. 'memory' has 'mem', 'swap',
        'kernel_vmstat'), each should get a unique filename so they don't overwrite
        each other.
        """
        mock_handler.return_value = ("/var/log/azure", "/etc/azure")
        data = [
            make_counter("% Used Memory", config_ids=["dcr1"]),
            make_counter("Available MBytes Memory", config_ids=["dcr1"]),
            make_counter("Used MBytes Swap Space", config_ids=["dcr1"]),
            make_counter("% Used Swap Space", config_ids=["dcr1"]),
            make_counter("Page Reads/sec", config_ids=["dcr1"]),
            make_counter("Page Writes/sec", config_ids=["dcr1"]),
            make_counter("Pages/sec", config_ids=["dcr1"]),
        ]
        output, _ = parse_config(data, ME_URL, MDSD_URL, False,
                                 AZ_RESOURCE_ID, SUBSCRIPTION_ID,
                                 RESOURCE_GROUP, REGION, VM_NAME)
        plugin_configs = [f for f in output if f["filename"] not in ("intermediate.json", "telegraf.conf")]
        filenames = [f["filename"] for f in plugin_configs]
        # All filenames should be unique
        self.assertEqual(len(filenames), len(set(filenames)),
                         f"Duplicate filenames detected: {filenames}")

    @patch('telegraf_utils.telegraf_config_handler.get_handler_vars')
    def test_filesystem_disk_and_diskio_unique_filenames(self, mock_handler):
        """
        The 'filesystem' omiclass has both 'disk' and 'diskio' plugins.
        They must produce different filenames.
        """
        mock_handler.return_value = ("/var/log/azure", "/etc/azure")
        data = [
            make_counter("% Used Space", config_ids=["dcr1"]),
            make_counter("Free Megabytes", config_ids=["dcr1"]),
            make_counter("Disk Transfers/sec", config_ids=["dcr1"]),
            make_counter("Disk Reads/sec", config_ids=["dcr1"]),
            make_counter("Disk Writes/sec", config_ids=["dcr1"]),
        ]
        output, _ = parse_config(data, ME_URL, MDSD_URL, False,
                                 AZ_RESOURCE_ID, SUBSCRIPTION_ID,
                                 RESOURCE_GROUP, REGION, VM_NAME)
        plugin_configs = [f for f in output if f["filename"] not in ("intermediate.json", "telegraf.conf")]
        filenames = [f["filename"] for f in plugin_configs]
        # All filenames should be unique
        self.assertEqual(len(filenames), len(set(filenames)),
                         f"Duplicate filenames detected: {filenames}")
        # Should have both disk and diskio configs
        disk_files = [f for f in filenames if "-disk-" in f]
        diskio_files = [f for f in filenames if "-diskio-" in f]
        self.assertTrue(len(disk_files) > 0, "Expected disk config file")
        self.assertTrue(len(diskio_files) > 0, "Expected diskio config file")

    @patch('telegraf_utils.telegraf_config_handler.get_handler_vars')
    def test_all_plugins_generate_config(self, mock_handler):
        """
        When mem, swap, and kernel_vmstat are all configured under 'memory' omiclass,
        all three should produce config files (not just the last one).
        """
        mock_handler.return_value = ("/var/log/azure", "/etc/azure")
        data = [
            make_counter("% Used Memory", config_ids=["dcr1"]),
            make_counter("Available MBytes Memory", config_ids=["dcr1"]),
            make_counter("Used MBytes Swap Space", config_ids=["dcr1"]),
            make_counter("Page Reads/sec", config_ids=["dcr1"]),
        ]
        output, _ = parse_config(data, ME_URL, MDSD_URL, False,
                                 AZ_RESOURCE_ID, SUBSCRIPTION_ID,
                                 RESOURCE_GROUP, REGION, VM_NAME)
        plugin_configs = [f for f in output if f["filename"] not in ("intermediate.json", "telegraf.conf")]
        all_data = "\n".join(f["data"] for f in plugin_configs)
        self.assertIn("[[inputs.mem]]", all_data, "mem plugin config missing")
        self.assertIn("[[inputs.swap]]", all_data, "swap plugin config missing")
        self.assertIn("[[inputs.kernel_vmstat]]", all_data, "kernel_vmstat plugin config missing")


class TestParseConfigMultipleDCRs(unittest.TestCase):
    """Tests for multi-DCR scenarios (the fix this commit addresses)."""

    @patch('telegraf_utils.telegraf_config_handler.get_handler_vars')
    def test_multiple_config_ids_produce_separate_files(self, mock_handler):
        """
        When a counter is associated with multiple configurationIds (multiple DCRs),
        each configId should get its own config file.
        """
        mock_handler.return_value = ("/var/log/azure", "/etc/azure")
        data = [
            make_counter("% Used Memory", config_ids=["dcr1", "dcr2"]),
            make_counter("Available MBytes Memory", config_ids=["dcr1", "dcr2"]),
        ]
        output, _ = parse_config(data, ME_URL, MDSD_URL, False,
                                 AZ_RESOURCE_ID, SUBSCRIPTION_ID,
                                 RESOURCE_GROUP, REGION, VM_NAME)
        plugin_configs = [f for f in output if f["filename"] not in ("intermediate.json", "telegraf.conf")]
        # Should have 2 config files for mem (one per DCR)
        mem_configs = [f for f in plugin_configs if "-mem-" in f["filename"]]
        self.assertEqual(len(mem_configs), 2,
                         f"Expected 2 mem configs for 2 DCRs, got {len(mem_configs)}: {[f['filename'] for f in mem_configs]}")

    @patch('telegraf_utils.telegraf_config_handler.get_handler_vars')
    def test_config_id_tag_in_output(self, mock_handler):
        """Each config file should have the correct configurationId tag."""
        mock_handler.return_value = ("/var/log/azure", "/etc/azure")
        data = [
            make_counter("% Used Memory", config_ids=["dcr-alpha"]),
        ]
        output, _ = parse_config(data, ME_URL, MDSD_URL, False,
                                 AZ_RESOURCE_ID, SUBSCRIPTION_ID,
                                 RESOURCE_GROUP, REGION, VM_NAME)
        plugin_configs = [f for f in output if f["filename"] not in ("intermediate.json", "telegraf.conf")]
        mem_configs = [f for f in plugin_configs if "-mem-" in f["filename"]]
        self.assertTrue(len(mem_configs) > 0)
        self.assertIn('configurationId="dcr-alpha"', mem_configs[0]["data"])

    @patch('telegraf_utils.telegraf_config_handler.get_handler_vars')
    def test_different_counters_different_dcrs(self, mock_handler):
        """
        When counters in the same plugin map to different DCRs, all DCR configs
        should be generated.
        """
        mock_handler.return_value = ("/var/log/azure", "/etc/azure")
        data = [
            make_counter("% Used Memory", config_ids=["dcr1"]),
            make_counter("Available MBytes Memory", config_ids=["dcr2"]),
        ]
        output, _ = parse_config(data, ME_URL, MDSD_URL, False,
                                 AZ_RESOURCE_ID, SUBSCRIPTION_ID,
                                 RESOURCE_GROUP, REGION, VM_NAME)
        plugin_configs = [f for f in output if f["filename"] not in ("intermediate.json", "telegraf.conf")]
        mem_configs = [f for f in plugin_configs if "-mem-" in f["filename"]]
        self.assertEqual(len(mem_configs), 2,
                         f"Expected 2 mem configs (dcr1 + dcr2), got {len(mem_configs)}")
        all_data = "\n".join(f["data"] for f in mem_configs)
        self.assertIn('configurationId="dcr1"', all_data)
        self.assertIn('configurationId="dcr2"', all_data)


class TestParseConfigContent(unittest.TestCase):
    """Tests for correctness of generated telegraf config content."""

    @patch('telegraf_utils.telegraf_config_handler.get_handler_vars')
    def test_fieldpass_includes_all_fields(self, mock_handler):
        """fieldpass should include all fields for the plugin."""
        mock_handler.return_value = ("/var/log/azure", "/etc/azure")
        data = [
            make_counter("% Used Memory", config_ids=["dcr1"]),
            make_counter("Available MBytes Memory", config_ids=["dcr1"]),
        ]
        output, _ = parse_config(data, ME_URL, MDSD_URL, False,
                                 AZ_RESOURCE_ID, SUBSCRIPTION_ID,
                                 RESOURCE_GROUP, REGION, VM_NAME)
        plugin_configs = [f for f in output if "-mem-" in f["filename"]]
        self.assertTrue(len(plugin_configs) > 0)
        config_data = plugin_configs[0]["data"]
        self.assertIn('"used_percent"', config_data)
        self.assertIn('"available"', config_data)

    @patch('telegraf_utils.telegraf_config_handler.get_handler_vars')
    def test_interval_uses_shortest(self, mock_handler):
        """When fields have different intervals, the shortest should be used."""
        mock_handler.return_value = ("/var/log/azure", "/etc/azure")
        data = [
            make_counter("% Used Memory", interval="60s", config_ids=["dcr1"]),
            make_counter("Available MBytes Memory", interval="30s", config_ids=["dcr1"]),
        ]
        output, _ = parse_config(data, ME_URL, MDSD_URL, False,
                                 AZ_RESOURCE_ID, SUBSCRIPTION_ID,
                                 RESOURCE_GROUP, REGION, VM_NAME)
        plugin_configs = [f for f in output if "-mem-" in f["filename"]]
        self.assertTrue(len(plugin_configs) > 0)
        config_data = plugin_configs[0]["data"]
        # interval should be half of min (30s) = 15s
        self.assertIn('interval = "15s"', config_data)

    @patch('telegraf_utils.telegraf_config_handler.get_handler_vars')
    def test_rate_counter_has_aggregator(self, mock_handler):
        """Rate counters (like diskio) should have aggregator config."""
        mock_handler.return_value = ("/var/log/azure", "/etc/azure")
        data = [
            make_counter("Disk Reads/sec", config_ids=["dcr1"]),
            make_counter("Disk Writes/sec", config_ids=["dcr1"]),
        ]
        output, _ = parse_config(data, ME_URL, MDSD_URL, False,
                                 AZ_RESOURCE_ID, SUBSCRIPTION_ID,
                                 RESOURCE_GROUP, REGION, VM_NAME)
        plugin_configs = [f for f in output if "-diskio-" in f["filename"]]
        self.assertTrue(len(plugin_configs) > 0)
        config_data = plugin_configs[0]["data"]
        self.assertIn("[[aggregators.basicstats]]", config_data)
        self.assertIn('"rate"', config_data)

    @patch('telegraf_utils.telegraf_config_handler.get_handler_vars')
    def test_cpu_has_report_active(self, mock_handler):
        """CPU plugin should include report_active = true."""
        mock_handler.return_value = ("/var/log/azure", "/etc/azure")
        data = [
            make_counter("% Processor Time", config_ids=["dcr1"]),
        ]
        output, _ = parse_config(data, ME_URL, MDSD_URL, False,
                                 AZ_RESOURCE_ID, SUBSCRIPTION_ID,
                                 RESOURCE_GROUP, REGION, VM_NAME)
        plugin_configs = [f for f in output if "-cpu-" in f["filename"]]
        self.assertTrue(len(plugin_configs) > 0)
        config_data = plugin_configs[0]["data"]
        self.assertIn("report_active = true", config_data)


class TestParseConfigTelegrafConf(unittest.TestCase):
    """Tests for the main telegraf.conf content."""

    @patch('telegraf_utils.telegraf_config_handler.get_handler_vars')
    def test_telegraf_conf_has_me_output(self, mock_handler):
        """telegraf.conf should have ME output when sink includes 'me'."""
        mock_handler.return_value = ("/var/log/azure", "/etc/azure")
        data = [make_counter("% Used Memory", sink=["mdsd", "me"])]
        output, _ = parse_config(data, ME_URL, MDSD_URL, False,
                                 AZ_RESOURCE_ID, SUBSCRIPTION_ID,
                                 RESOURCE_GROUP, REGION, VM_NAME)
        telegraf_conf = next(f for f in output if f["filename"] == "telegraf.conf")
        self.assertIn("[[outputs.socket_writer]]", telegraf_conf["data"])
        self.assertIn(ME_URL, telegraf_conf["data"])

    @patch('telegraf_utils.telegraf_config_handler.get_handler_vars')
    def test_telegraf_conf_has_mdsd_output(self, mock_handler):
        """telegraf.conf should have MDSD output when sink includes 'mdsd'."""
        mock_handler.return_value = ("/var/log/azure", "/etc/azure")
        data = [make_counter("% Used Memory", sink=["mdsd", "me"])]
        output, _ = parse_config(data, ME_URL, MDSD_URL, False,
                                 AZ_RESOURCE_ID, SUBSCRIPTION_ID,
                                 RESOURCE_GROUP, REGION, VM_NAME)
        telegraf_conf = next(f for f in output if f["filename"] == "telegraf.conf")
        self.assertIn(MDSD_URL, telegraf_conf["data"])

    @patch('telegraf_utils.telegraf_config_handler.get_handler_vars')
    def test_telegraf_conf_has_global_tags(self, mock_handler):
        """telegraf.conf should include subscription, resourceGroup, region tags."""
        mock_handler.return_value = ("/var/log/azure", "/etc/azure")
        data = [make_counter("% Used Memory")]
        output, _ = parse_config(data, ME_URL, MDSD_URL, False,
                                 AZ_RESOURCE_ID, SUBSCRIPTION_ID,
                                 RESOURCE_GROUP, REGION, VM_NAME)
        telegraf_conf = next(f for f in output if f["filename"] == "telegraf.conf")
        self.assertIn(SUBSCRIPTION_ID, telegraf_conf["data"])
        self.assertIn(RESOURCE_GROUP, telegraf_conf["data"])
        self.assertIn(REGION, telegraf_conf["data"])


class TestWriteConfigs(unittest.TestCase):
    """Tests for write_configs function."""

    @patch('telegraf_utils.telegraf_config_handler.rmtree')
    @patch('telegraf_utils.telegraf_config_handler.os.path.exists')
    @patch('telegraf_utils.telegraf_config_handler.os.mkdir')
    @patch('builtins.open', new_callable=unittest.mock.mock_open)
    def test_write_configs_writes_all_files(self, mock_open, mock_mkdir, mock_exists, mock_rmtree):
        """write_configs should write each config entry to the correct path."""
        mock_exists.return_value = True
        configs = [
            {"filename": "telegraf.conf", "data": "agent config"},
            {"filename": "memory-mem-dcr1.conf", "data": "mem config"},
            {"filename": "memory-swap-dcr1.conf", "data": "swap config"},
        ]
        write_configs(configs, "/etc/telegraf/", "/etc/telegraf/telegraf.d/")
        # Should have opened 3 files for writing
        self.assertEqual(mock_open.call_count, 3)

    @patch('telegraf_utils.telegraf_config_handler.rmtree')
    @patch('telegraf_utils.telegraf_config_handler.os.path.exists')
    @patch('telegraf_utils.telegraf_config_handler.os.mkdir')
    @patch('builtins.open', new_callable=unittest.mock.mock_open)
    def test_write_configs_removes_old_dir(self, mock_open, mock_mkdir, mock_exists, mock_rmtree):
        """write_configs should remove existing conf directory before writing."""
        mock_exists.return_value = True
        configs = [{"filename": "telegraf.conf", "data": "data"}]
        write_configs(configs, "/etc/telegraf/", "/etc/telegraf/telegraf.d/")
        mock_rmtree.assert_called_once_with("/etc/telegraf/")


if __name__ == '__main__':
    unittest.main()
