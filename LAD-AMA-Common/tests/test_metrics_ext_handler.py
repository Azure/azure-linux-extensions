#!/usr/bin/env python
"""
Unit tests for metrics_ext_utils/metrics_ext_handler.py
"""

import sys
import os
import json
import unittest
from unittest.mock import patch, MagicMock, mock_open

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock Linux-only modules before importing the handler
for mod_name in ('grp', 'pwd'):
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()

import metrics_ext_utils.metrics_constants as metrics_constants
from metrics_ext_utils.metrics_ext_handler import (
    create_metrics_extension_conf,
    create_custom_metrics_conf,
    get_metrics_extension_service_name,
    get_arm_domain,
    ARMDomainMap,
    PublicCloudName,
    FairfaxCloudName,
    MooncakeCloudName,
    USNatCloudName,
    USSecCloudName,
)


class TestCreateMetricsExtensionConf(unittest.TestCase):
    """Tests for create_metrics_extension_conf."""

    def test_contains_resource_id(self):
        resource_id = "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1"
        conf = create_metrics_extension_conf(resource_id, "https://login.microsoftonline.com/tenant1")
        conf_json = json.loads(conf)
        self.assertEqual(conf_json["azureResourceId"], resource_id)

    def test_contains_aad_authority(self):
        aad_url = "https://login.microsoftonline.com/tenant1"
        conf = create_metrics_extension_conf("/sub/rg/vm1", aad_url)
        conf_json = json.loads(conf)
        self.assertEqual(conf_json["aadAuthority"], aad_url)

    def test_valid_json(self):
        conf = create_metrics_extension_conf("/some/id", "https://aad.url")
        conf_json = json.loads(conf)
        self.assertIn("timeToTerminateInMs", conf_json)
        self.assertIn("maxPublicationMetricsPerMinute", conf_json)
        self.assertEqual(conf_json["publicationIntervalInSec"], 60)

    def test_publish_min_max_default_true(self):
        conf = create_metrics_extension_conf("/id", "https://aad")
        conf_json = json.loads(conf)
        self.assertTrue(conf_json["publishMinMaxByDefault"])


class TestCreateCustomMetricsConf(unittest.TestCase):
    """Tests for create_custom_metrics_conf."""

    def test_default_gig_endpoint(self):
        conf = create_custom_metrics_conf("westus2")
        conf_json = json.loads(conf)
        self.assertEqual(conf_json["homeStampGslbHostname"], "westus2.monitoring.azure.com")
        self.assertIn("https://westus2.monitoring.azure.com/api/v1/ingestion/ingest",
                      conf_json["endpointsForClientPublication"])

    def test_custom_gig_endpoint(self):
        custom_ep = "https://custom.endpoint.example.com"
        conf = create_custom_metrics_conf("eastus", gig_endpoint=custom_ep)
        conf_json = json.loads(conf)
        self.assertEqual(conf_json["homeStampGslbHostname"], "custom.endpoint.example.com")
        self.assertIn(custom_ep + "/api/v1/ingestion/ingest",
                      conf_json["endpointsForClientPublication"])

    def test_valid_json_structure(self):
        conf = create_custom_metrics_conf("centralus")
        conf_json = json.loads(conf)
        self.assertIn("version", conf_json)
        self.assertEqual(conf_json["version"], 17)


class TestGetMetricsExtensionServiceName(unittest.TestCase):
    """Tests for get_metrics_extension_service_name."""

    def test_lad_service_name(self):
        name = get_metrics_extension_service_name(True)
        self.assertEqual(name, metrics_constants.lad_metrics_extension_service_name)

    def test_ama_service_name(self):
        name = get_metrics_extension_service_name(False)
        self.assertEqual(name, metrics_constants.metrics_extension_service_name)


class TestGetArmDomain(unittest.TestCase):
    """Tests for get_arm_domain."""

    def test_public_cloud(self):
        domain = get_arm_domain("AzurePublicCloud")
        self.assertEqual(domain, "management.azure.com")

    def test_fairfax_cloud(self):
        domain = get_arm_domain("AzureUSGovernmentCloud")
        self.assertEqual(domain, "management.usgovcloudapi.net")

    def test_mooncake_cloud(self):
        domain = get_arm_domain("AzureChinaCloud")
        self.assertEqual(domain, "management.chinacloudapi.cn")

    def test_usnat_cloud(self):
        domain = get_arm_domain("USNat")
        self.assertEqual(domain, "management.azure.eaglex.ic.gov")

    def test_ussec_cloud(self):
        domain = get_arm_domain("USSec")
        self.assertEqual(domain, "management.azure.microsoft.scloud")

    def test_unknown_cloud_raises(self):
        with self.assertRaises(Exception) as ctx:
            get_arm_domain("UnknownCloud")
        self.assertIn("Unknown cloud environment", str(ctx.exception))

    @patch('metrics_ext_utils.metrics_ext_handler.get_arca_endpoints_from_himds')
    def test_arca_cloud(self, mock_arca):
        mock_arca.return_value = ("https://arm.azurestackcloud.example.com", "https://mcs.example.com")
        domain = get_arm_domain("AzureStackCloud")
        self.assertEqual(domain, "arm.azurestackcloud.example.com")


class TestGetMetricsExtensionServicePath(unittest.TestCase):
    """Tests for get_metrics_extension_service_path."""

    @patch('os.path.exists')
    def test_lad_lib_systemd(self, mock_exists):
        from metrics_ext_utils.metrics_ext_handler import get_metrics_extension_service_path
        mock_exists.side_effect = lambda p: p == "/lib/systemd/system/"
        path = get_metrics_extension_service_path(True)
        self.assertEqual(path, metrics_constants.lad_metrics_extension_service_path)

    @patch('os.path.exists')
    def test_lad_usr_lib_systemd(self, mock_exists):
        from metrics_ext_utils.metrics_ext_handler import get_metrics_extension_service_path
        mock_exists.side_effect = lambda p: p == "/usr/lib/systemd/system/"
        path = get_metrics_extension_service_path(True)
        self.assertEqual(path, metrics_constants.lad_metrics_extension_service_path_usr_lib)

    @patch('os.path.exists')
    def test_lad_no_systemd_raises(self, mock_exists):
        from metrics_ext_utils.metrics_ext_handler import get_metrics_extension_service_path
        mock_exists.return_value = False
        with self.assertRaises(Exception):
            get_metrics_extension_service_path(True)

    @patch('os.path.exists')
    def test_ama_etc_systemd(self, mock_exists):
        from metrics_ext_utils.metrics_ext_handler import get_metrics_extension_service_path
        mock_exists.side_effect = lambda p: p == "/etc/systemd/system"
        path = get_metrics_extension_service_path(False)
        self.assertEqual(path, metrics_constants.metrics_extension_service_path_etc)

    @patch('os.path.exists')
    def test_ama_no_systemd_raises(self, mock_exists):
        from metrics_ext_utils.metrics_ext_handler import get_metrics_extension_service_path
        mock_exists.return_value = False
        with self.assertRaises(Exception):
            get_metrics_extension_service_path(False)


class TestIsRunning(unittest.TestCase):
    """Tests for is_running (metrics)."""

    @patch('subprocess.Popen')
    def test_returns_true_when_process_found(self, mock_popen):
        from metrics_ext_utils.metrics_ext_handler import is_running
        mock_proc = MagicMock()
        mock_proc.communicate.return_value = (
            b"/opt/microsoft/azuremonitoragent/bin/MetricsExtension --args", b""
        )
        mock_popen.return_value = mock_proc
        self.assertTrue(is_running(False))

    @patch('subprocess.Popen')
    def test_returns_false_when_process_not_found(self, mock_popen):
        from metrics_ext_utils.metrics_ext_handler import is_running
        mock_proc = MagicMock()
        mock_proc.communicate.return_value = (b"", b"")
        mock_popen.return_value = mock_proc
        self.assertFalse(is_running(False))


class TestGetHandlerVars(unittest.TestCase):
    """Tests for get_handler_vars in metrics_ext_handler."""

    @patch('os.path.exists')
    def test_returns_empty_when_no_handler_env(self, mock_exists):
        from metrics_ext_utils.metrics_ext_handler import get_handler_vars
        mock_exists.return_value = False
        log_folder, config_folder = get_handler_vars()
        self.assertEqual(log_folder, "")
        self.assertEqual(config_folder, "")

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', mock_open(read_data=json.dumps([{
        "handlerEnvironment": {
            "logFolder": "/var/log/azure/ext",
            "configFolder": "/etc/azure/ext"
        }
    }])))
    def test_parses_handler_env_list(self, mock_exists):
        from metrics_ext_utils.metrics_ext_handler import get_handler_vars
        log_folder, config_folder = get_handler_vars()
        self.assertEqual(log_folder, "/var/log/azure/ext")
        self.assertEqual(config_folder, "/etc/azure/ext")


if __name__ == '__main__':
    unittest.main()
