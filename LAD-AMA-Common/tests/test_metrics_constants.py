#!/usr/bin/env python
"""
Unit tests for metrics_ext_utils/metrics_constants.py
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import metrics_ext_utils.metrics_constants as metrics_constants


class TestMetricsConstants(unittest.TestCase):
    """Tests for metrics_constants module values."""

    def test_namespace_value(self):
        self.assertEqual(metrics_constants.metrics_extension_namespace,
                         "Azure.VM.Linux.GuestMetrics")

    def test_ama_binary_path(self):
        self.assertEqual(metrics_constants.ama_metrics_extension_bin,
                         "/opt/microsoft/azuremonitoragent/bin/MetricsExtension")

    def test_lad_binary_path(self):
        self.assertEqual(metrics_constants.lad_metrics_extension_bin,
                         "/usr/local/lad/bin/MetricsExtension")

    def test_ama_telegraf_bin(self):
        self.assertEqual(metrics_constants.ama_telegraf_bin,
                         "/opt/microsoft/azuremonitoragent/bin/telegraf")

    def test_lad_telegraf_bin(self):
        self.assertEqual(metrics_constants.lad_telegraf_bin,
                         "/usr/local/lad/bin/telegraf")

    def test_service_names(self):
        self.assertEqual(metrics_constants.metrics_extension_service_name, "metrics-extension")
        self.assertEqual(metrics_constants.telegraf_service_name, "metrics-sourcer")
        self.assertEqual(metrics_constants.lad_metrics_extension_service_name, "metrics-extension-lad")
        self.assertEqual(metrics_constants.lad_telegraf_service_name, "metrics-sourcer-lad")

    def test_udp_ports_are_strings(self):
        self.assertIsInstance(metrics_constants.ama_metrics_extension_udp_port, str)
        self.assertIsInstance(metrics_constants.lad_metrics_extension_udp_port, str)

    def test_influx_url_format(self):
        self.assertTrue(
            metrics_constants.lad_metrics_extension_influx_udp_url.startswith("udp://"))
        self.assertIn(metrics_constants.lad_metrics_extension_udp_port,
                      metrics_constants.lad_metrics_extension_influx_udp_url)

    def test_telegraf_influx_url(self):
        self.assertTrue(
            metrics_constants.telegraf_influx_url.startswith("unix://"))


if __name__ == '__main__':
    unittest.main()
