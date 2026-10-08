#!/usr/bin/env python
"""
Unit tests for telegraf_utils/telegraf_name_map.py
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from telegraf_utils.telegraf_name_map import name_map


class TestNameMapStructure(unittest.TestCase):
    """Tests for the telegraf name_map data structure."""

    def test_name_map_is_dict(self):
        self.assertIsInstance(name_map, dict)

    def test_name_map_not_empty(self):
        self.assertGreater(len(name_map), 0)

    def test_all_entries_have_plugin(self):
        """Every entry must have a 'plugin' key."""
        for counter, mapping in name_map.items():
            self.assertIn("plugin", mapping,
                          f"Counter '{counter}' missing 'plugin' key")

    def test_all_entries_have_field(self):
        """Every entry must have a 'field' key."""
        for counter, mapping in name_map.items():
            self.assertIn("field", mapping,
                          f"Counter '{counter}' missing 'field' key")

    def test_lad_entries_have_ladtablekey(self):
        """LAD entries (with '->') should have a 'ladtablekey'."""
        for counter, mapping in name_map.items():
            if "->" in counter:
                self.assertIn("ladtablekey", mapping,
                              f"LAD counter '{counter}' missing 'ladtablekey'")

    def test_ama_entries_have_module(self):
        """AMA entries (without '->') should have a 'module' key."""
        for counter, mapping in name_map.items():
            if "->" not in counter:
                self.assertIn("module", mapping,
                              f"AMA counter '{counter}' missing 'module' key")

    def test_plugin_names_are_strings(self):
        for counter, mapping in name_map.items():
            self.assertIsInstance(mapping["plugin"], str)
            self.assertGreater(len(mapping["plugin"]), 0)

    def test_field_names_are_strings(self):
        for counter, mapping in name_map.items():
            self.assertIsInstance(mapping["field"], str)
            self.assertGreater(len(mapping["field"]), 0)


class TestNameMapExpectedCounters(unittest.TestCase):
    """Tests that expected counters exist in the map."""

    def test_cpu_counters_present(self):
        self.assertIn("% Processor Time", name_map)
        self.assertIn("% Idle Time", name_map)
        self.assertIn("% User Time", name_map)

    def test_memory_counters_present(self):
        self.assertIn("% Used Memory", name_map)
        self.assertIn("Available MBytes Memory", name_map)

    def test_disk_counters_present(self):
        self.assertIn("% Used Space", name_map)
        self.assertIn("Free Megabytes", name_map)
        self.assertIn("Disk Reads/sec", name_map)

    def test_network_counters_present(self):
        self.assertIn("Total Bytes Received", name_map)
        self.assertIn("Total Bytes Transmitted", name_map)
        self.assertIn("Total Packets Transmitted", name_map)

    def test_swap_counters_present(self):
        self.assertIn("% Used Swap Space", name_map)
        self.assertIn("Available MBytes Swap", name_map)

    def test_system_counters_present(self):
        self.assertIn("Uptime", name_map)
        self.assertIn("Load1", name_map)

    def test_lad_processor_counters(self):
        self.assertIn("processor->cpu user time", name_map)
        self.assertIn("processor->cpu idle time", name_map)

    def test_lad_memory_counters(self):
        self.assertIn("memory->memory used", name_map)
        self.assertIn("memory->page reads", name_map)

    def test_lad_filesystem_counters(self):
        self.assertIn("filesystem->filesystem used space", name_map)
        self.assertIn("filesystem->filesystem transfers/sec", name_map)

    def test_lad_disk_counters(self):
        self.assertIn("disk->disk read guest os", name_map)
        self.assertIn("disk->disk writes", name_map)


class TestNameMapPluginMapping(unittest.TestCase):
    """Tests that counters map to the correct plugins."""

    def test_cpu_counters_map_to_cpu_plugin(self):
        self.assertEqual(name_map["% Processor Time"]["plugin"], "cpu")
        self.assertEqual(name_map["% Idle Time"]["plugin"], "cpu")

    def test_memory_counters_map_to_mem_plugin(self):
        self.assertEqual(name_map["% Used Memory"]["plugin"], "mem")
        self.assertEqual(name_map["Available MBytes Memory"]["plugin"], "mem")

    def test_swap_counters_map_to_swap_plugin(self):
        self.assertEqual(name_map["% Used Swap Space"]["plugin"], "swap")

    def test_disk_counters_map_to_disk_plugin(self):
        self.assertEqual(name_map["% Used Space"]["plugin"], "disk")

    def test_diskio_counters_map_to_diskio_plugin(self):
        self.assertEqual(name_map["Disk Reads/sec"]["plugin"], "diskio")
        self.assertEqual(name_map["Disk Writes/sec"]["plugin"], "diskio")

    def test_network_counters_map_to_net_plugin(self):
        self.assertEqual(name_map["Total Bytes Received"]["plugin"], "net")

    def test_kernel_vmstat_counters(self):
        self.assertEqual(name_map["Page Reads/sec"]["plugin"], "kernel_vmstat")
        self.assertEqual(name_map["Pages/sec"]["plugin"], "kernel_vmstat")

    def test_rate_counters_have_op(self):
        """Counters with rate operations should have 'op': 'rate'."""
        rate_counters = ["Disk Reads/sec", "Disk Writes/sec", "Page Reads/sec"]
        for counter in rate_counters:
            self.assertIn("op", name_map[counter],
                          f"Counter '{counter}' should have 'op' key")
            self.assertEqual(name_map[counter]["op"], "rate")

    def test_non_rate_counters_no_op(self):
        """Non-rate counters should not have 'op' key."""
        non_rate = ["% Used Memory", "% Used Space", "% Idle Time"]
        for counter in non_rate:
            self.assertNotIn("op", name_map[counter],
                             f"Counter '{counter}' should not have 'op' key")


class TestNameMapModuleMapping(unittest.TestCase):
    """Tests that AMA counters map to correct modules."""

    def test_cpu_module(self):
        self.assertEqual(name_map["% Processor Time"]["module"], "processor")

    def test_memory_module(self):
        self.assertEqual(name_map["% Used Memory"]["module"], "memory")
        self.assertEqual(name_map["Page Reads/sec"]["module"], "memory")

    def test_filesystem_module(self):
        self.assertEqual(name_map["% Used Space"]["module"], "filesystem")
        self.assertEqual(name_map["Disk Reads/sec"]["module"], "filesystem")

    def test_network_module(self):
        self.assertEqual(name_map["Total Bytes Received"]["module"], "network")

    def test_system_module(self):
        self.assertEqual(name_map["Uptime"]["module"], "system")


if __name__ == '__main__':
    unittest.main()
