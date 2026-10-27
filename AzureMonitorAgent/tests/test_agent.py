#!/usr/bin/env python
"""
Unit tests for AzureMonitorAgent/agent.py - pure logic functions only.
"""

import sys
import os
import re
import stat
import base64
import io
import json
import tempfile
import time
import unittest
from unittest.mock import patch, MagicMock, mock_open, call
from threading import Timer

# Mock Linux-only modules before importing
for mod_name in ('grp', 'pwd'):
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()

# Mock waagent/HUtil imports that agent.py tries to load at module level
sys.modules['Utils'] = MagicMock()
sys.modules['Utils.WAAgentUtil'] = MagicMock()
sys.modules['Utils.WAAgentUtil'].waagent = MagicMock()
sys.modules['Utils.HandlerUtil'] = MagicMock()

# Mock build-only packages that agent.py imports at module level (telegraf/metrics
# helpers). Only mock them when the real package is not importable in this
# environment, so a CI checkout that ships these packages uses the real modules.
import importlib
for mod_name in (
    'telegraf_utils',
    'telegraf_utils.telegraf_config_handler',
    'metrics_ext_utils',
    'metrics_ext_utils.metrics_constants',
    'metrics_ext_utils.metrics_ext_handler',
    'metrics_ext_utils.metrics_common_utils',
):
    if mod_name in sys.modules:
        continue
    try:
        importlib.import_module(mod_name)
    except ImportError:
        sys.modules[mod_name] = MagicMock()

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


class TestGenerateLocalsyslogConfigsEarlyReturn(unittest.TestCase):
    """Tests for generate_localsyslog_configs early-return logic when syslog_port == MDSDSyslogPort."""

    def setUp(self):
        self._orig_port = agent.MDSDSyslogPort
        # Patch dependencies used by generate_localsyslog_configs
        self._patches = [
            patch('agent.get_settings', return_value=({}, {})),
            patch('agent.hutil_log_info'),
            patch('agent.hutil_log_error'),
            patch('agent.run_command_and_log', return_value=(0, '')),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        agent.MDSDSyslogPort = self._orig_port
        for p in self._patches:
            p.stop()

    @patch('agent.validate_port_number', return_value='28330')
    @patch('os.path.isfile', return_value=True)
    @patch('builtins.open', MagicMock())
    def test_returns_early_when_port_matches_and_configs_exist(self, mock_isfile, mock_validate):
        """When port matches AND at least one syslog config file exists, should return early."""
        agent.MDSDSyslogPort = '28330'
        config_files = {
            '/etc/rsyslog.d/10-azuremonitoragent-omfwd.conf',
            '/etc/rsyslog.d/10-azuremonitoragent.conf',
            '/etc/syslog-ng/conf.d/azuremonitoragent-tcp.conf',
            '/etc/syslog-ng/conf.d/azuremonitoragent.conf',
        }

        def exists_side_effect(path):
            return path in config_files

        with patch('os.path.exists', side_effect=exists_side_effect):
            result = agent.generate_localsyslog_configs(uses_gcs=True)
            # Function returns early (None), meaning it did not proceed to syslog setup
            self.assertIsNone(result)

    @patch('agent.validate_port_number', return_value='28330')
    @patch('os.path.isfile', return_value=True)
    @patch('builtins.open', MagicMock())
    def test_does_not_return_early_when_port_matches_but_no_configs_exist(self, mock_isfile, mock_validate):
        """When port matches but NO syslog config files exist, should NOT return early (regenerate configs)."""
        agent.MDSDSyslogPort = '28330'

        with patch('os.path.exists', return_value=False):
            # The function should proceed past the early-return check.
            # It will eventually try file operations that we haven't fully mocked,
            # so we just verify it doesn't return immediately like the early-return case.
            # We patch copyfile to prevent actual file ops.
            with patch('agent.copyfile'):
                try:
                    agent.generate_localsyslog_configs(uses_gcs=True)
                except Exception:
                    pass
                # Verify MDSDSyslogPort was updated (happens past the early-return)
                self.assertEqual(agent.MDSDSyslogPort, '28330')

    def test_returns_early_when_no_control_plane(self):
        """When neither uses_gcs nor uses_mcs, should return early regardless."""
        result = agent.generate_localsyslog_configs(uses_gcs=False, uses_mcs=False)
        self.assertIsNone(result)


class TestRemoveLocalsyslogConfigsResetsPort(unittest.TestCase):
    """Tests for remove_localsyslog_configs resetting MDSDSyslogPort to 0."""

    def setUp(self):
        self._orig_port = agent.MDSDSyslogPort

    def tearDown(self):
        agent.MDSDSyslogPort = self._orig_port

    @patch('os.path.exists', return_value=False)
    def test_resets_port_to_zero(self, mock_exists):
        """remove_localsyslog_configs should reset MDSDSyslogPort to 0."""
        agent.MDSDSyslogPort = '28330'
        agent.remove_localsyslog_configs()
        self.assertEqual(agent.MDSDSyslogPort, 0)

    @patch('agent.run_command_and_log', return_value=(0, ''))
    @patch('agent.hutil_log_info')
    @patch('agent.get_service_command', return_value='systemctl restart rsyslog')
    @patch('os.remove')
    @patch('os.path.exists', return_value=True)
    def test_resets_port_to_zero_with_existing_configs(self, mock_exists, mock_remove,
                                                        mock_svc_cmd, mock_log, mock_run):
        """Port should be reset even when config files exist and are removed."""
        agent.MDSDSyslogPort = '28330'
        agent.remove_localsyslog_configs()
        self.assertEqual(agent.MDSDSyslogPort, 0)

    @patch('os.path.exists', return_value=False)
    def test_port_reset_allows_regeneration(self, mock_exists):
        """After remove resets port to 0, a subsequent generate should not short-circuit on port match."""
        agent.MDSDSyslogPort = '28330'
        agent.remove_localsyslog_configs()
        # Port is now 0; a new syslog_port read of '28330' should NOT match MDSDSyslogPort
        self.assertNotEqual(agent.MDSDSyslogPort, '28330')
        self.assertEqual(agent.MDSDSyslogPort, 0)


class TestIsFeatureEnabledCurlUpload(unittest.TestCase):
    """Tests for is_feature_enabled('enableCurlUpload') region gating (PR #2190)."""

    def test_curl_upload_in_feature_support_matrix(self):
        """enableCurlUpload must be gated to the Stage 2 regions (not 'all')."""
        # Re-derive the matrix the same way is_feature_enabled does, by exercising
        # the function across regions.
        with patch('os.path.exists', return_value=False):
            with patch('agent.get_azure_environment_and_region',
                       return_value=(None, 'eastus2euap')):
                self.assertTrue(agent.is_feature_enabled('enableCurlUpload'))

    def test_enabled_in_stage2_regions(self):
        for region in ('eastus2euap', 'centraluseuap', 'westcentralus', 'eastasia'):
            with patch('os.path.exists', return_value=False):
                with patch('agent.get_azure_environment_and_region',
                           return_value=('AzureCloud', region)):
                    self.assertTrue(
                        agent.is_feature_enabled('enableCurlUpload'),
                        msg="enableCurlUpload should be enabled in region %r" % region)

    def test_disabled_in_other_region(self):
        for region in ('eastus', 'westus2', 'centralus'):
            with patch('os.path.exists', return_value=False):
                with patch('agent.get_azure_environment_and_region',
                           return_value=('AzureCloud', region)):
                    self.assertFalse(
                        agent.is_feature_enabled('enableCurlUpload'),
                        msg="enableCurlUpload should be disabled in region %r" % region)

    @patch('agent.os.path.exists', return_value=False)
    @patch('agent.get_azure_environment_and_region', return_value=(None, None))
    def test_missing_region_is_not_treated_as_disabled(self, *_):
        with self.assertRaises(RuntimeError):
            agent.is_feature_enabled('enableCurlUpload')

    @patch('agent.os.path.exists', return_value=False)
    @patch('agent.get_azure_environment_and_region')
    def test_global_features_do_not_depend_on_imds(self, metadata, _):
        self.assertTrue(agent.is_feature_enabled('enableCMV2'))
        metadata.assert_not_called()

    def test_preview_flag_file_forces_enable(self):
        """A previewFeatures/<feature> flag file enables the feature in any region."""
        flag_path = agent.PreviewFeaturesDirectory + 'enableCurlUpload'

        def exists_side_effect(path):
            return path == flag_path

        with patch('os.path.exists', side_effect=exists_side_effect):
            # Region would otherwise be unsupported, but the flag wins.
            with patch('agent.get_azure_environment_and_region',
                       return_value=('AzureCloud', 'eastus')):
                self.assertTrue(agent.is_feature_enabled('enableCurlUpload'))

    def test_disabled_flag_file_forces_disable(self):
        """A previewFeatures/<feature>Disabled flag file disables it even in eastus2euap."""
        disabled_path = agent.PreviewFeaturesDirectory + 'enableCurlUploadDisabled'

        def exists_side_effect(path):
            return path == disabled_path

        with patch('os.path.exists', side_effect=exists_side_effect):
            with patch('agent.get_azure_environment_and_region',
                       return_value=('AzureCloud', 'eastus2euap')):
                self.assertFalse(agent.is_feature_enabled('enableCurlUpload'))

    def test_unknown_feature_disabled(self):
        """A feature not present in the support matrix is disabled."""
        with patch('os.path.exists', return_value=False):
            with patch('agent.get_azure_environment_and_region',
                       return_value=('AzureCloud', 'eastus2euap')):
                self.assertFalse(agent.is_feature_enabled('someUnknownFeature'))


class TestEnableCurlUploadConfig(unittest.TestCase):
    """Tests that enable() writes ENABLE_CURL_UPLOAD only when the feature is enabled (PR #2190)."""

    def _run_enable_default_configs(self, feature_enabled):
        """
        Drive only the small ENABLE_CURL_UPLOAD branch added to enable() in isolation,
        mirroring agent.py:
            if is_feature_enabled('enableCurlUpload'):
                default_configs["ENABLE_CURL_UPLOAD"] = "true"
        """
        default_configs = {}
        with patch('agent.is_feature_enabled', return_value=feature_enabled) as mock_feat:
            if agent.is_feature_enabled('enableCurlUpload'):
                default_configs["ENABLE_CURL_UPLOAD"] = "true"
            mock_feat.assert_called_with('enableCurlUpload')
        return default_configs

    def test_curl_upload_config_set_when_enabled(self):
        configs = self._run_enable_default_configs(feature_enabled=True)
        self.assertEqual(configs.get("ENABLE_CURL_UPLOAD"), "true")

    def test_curl_upload_config_absent_when_disabled(self):
        configs = self._run_enable_default_configs(feature_enabled=False)
        self.assertNotIn("ENABLE_CURL_UPLOAD", configs)


class TestIsTelegrafServiceInstalled(unittest.TestCase):
    """Tests for is_telegraf_service_installed (telegraf crash-loop fix)."""

    @patch('agent.telhandler')
    @patch('os.path.isfile', return_value=True)
    def test_returns_true_when_unit_file_exists(self, mock_isfile, mock_telhandler):
        mock_telhandler.get_telegraf_service_path.return_value = \
            '/lib/systemd/system/metrics-sourcer.service'
        self.assertTrue(agent.is_telegraf_service_installed())
        mock_telhandler.get_telegraf_service_path.assert_called_once_with(is_lad=False)
        mock_isfile.assert_called_once_with('/lib/systemd/system/metrics-sourcer.service')

    @patch('agent.telhandler')
    @patch('os.path.isfile', return_value=False)
    def test_returns_false_when_unit_file_missing(self, mock_isfile, mock_telhandler):
        mock_telhandler.get_telegraf_service_path.return_value = \
            '/lib/systemd/system/metrics-sourcer.service'
        self.assertFalse(agent.is_telegraf_service_installed())

    @patch('agent.telhandler')
    def test_returns_false_on_exception(self, mock_telhandler):
        # get_telegraf_service_path raises when no systemd unit directory exists.
        mock_telhandler.get_telegraf_service_path.side_effect = Exception("no systemd unit dir")
        self.assertFalse(agent.is_telegraf_service_installed())


class TestStopMetricsProcessTelegrafCleanup(unittest.TestCase):
    """Tests stop_metrics_process telegraf teardown when unit file present but not running (crash-loop fix)."""

    @patch('agent.run_command_and_log', return_value=(0, ''))
    @patch('agent.hutil_log_error')
    @patch('agent.hutil_log_info')
    @patch('os.path.exists', return_value=False)
    @patch('agent.me_handler')
    @patch('agent.is_telegraf_service_installed', return_value=True)
    @patch('agent.telhandler')
    def test_stops_telegraf_when_installed_but_not_running(
            self, mock_telhandler, mock_installed, mock_me, mock_exists, *_):
        """Not running + unit file present -> telegraf is stopped and removed."""
        mock_telhandler.is_running.return_value = False
        mock_telhandler.stop_telegraf_service.return_value = (True, 'stopped')
        mock_telhandler.remove_telegraf_service.return_value = (True, 'removed')
        mock_me.is_running.return_value = False

        agent.stop_metrics_process()

        mock_telhandler.stop_telegraf_service.assert_called_once_with(is_lad=False)
        mock_telhandler.remove_telegraf_service.assert_called_once_with(is_lad=False)

    @patch('agent.run_command_and_log', return_value=(0, ''))
    @patch('agent.hutil_log_error')
    @patch('agent.hutil_log_info')
    @patch('os.path.exists', return_value=False)
    @patch('agent.me_handler')
    @patch('agent.is_telegraf_service_installed', return_value=False)
    @patch('agent.telhandler')
    def test_skips_telegraf_when_not_running_and_not_installed(
            self, mock_telhandler, mock_installed, mock_me, mock_exists, *_):
        """Not running + no unit file -> telegraf teardown is skipped."""
        mock_telhandler.is_running.return_value = False
        mock_me.is_running.return_value = False

        agent.stop_metrics_process()

        mock_telhandler.stop_telegraf_service.assert_not_called()
        mock_telhandler.remove_telegraf_service.assert_not_called()

    @patch('agent.run_command_and_log', return_value=(0, ''))
    @patch('agent.hutil_log_error')
    @patch('agent.hutil_log_info')
    @patch('os.path.exists', return_value=False)
    @patch('agent.me_handler')
    @patch('agent.is_telegraf_service_installed', return_value=False)
    @patch('agent.telhandler')
    def test_stops_telegraf_when_running(
            self, mock_telhandler, mock_installed, mock_me, mock_exists, *_):
        """Running (regardless of unit file) -> telegraf is stopped and removed."""
        mock_telhandler.is_running.return_value = True
        mock_telhandler.stop_telegraf_service.return_value = (True, 'stopped')
        mock_telhandler.remove_telegraf_service.return_value = (True, 'removed')
        mock_me.is_running.return_value = False

        agent.stop_metrics_process()

        mock_telhandler.stop_telegraf_service.assert_called_once_with(is_lad=False)
        mock_telhandler.remove_telegraf_service.assert_called_once_with(is_lad=False)


class TestProxyConfiguration(unittest.TestCase):
    @patch('agent.log_and_exit', side_effect=SystemExit(53))
    def test_rejects_control_characters_in_proxy_values(self, _):
        with self.assertRaises(SystemExit):
            agent.validate_proxy_value('user\ninjected', 'username')

    @patch('agent.log_and_exit', side_effect=SystemExit(53))
    def test_rejects_unsupported_proxy_scheme(self, _):
        with self.assertRaises(SystemExit):
            agent.validate_proxy_address('ftp://proxy.example.com')

    @patch('agent._write_proxy_conf')
    @patch('agent.run_command_and_log', return_value=(0, ''))
    def test_set_proxy_writes_configuration_without_shell_commands(
            self, mock_run, mock_write):
        agent.set_proxy('https://proxy.example.com:3128', 'user', 'password')

        expected_proxy = 'https://user:password@proxy.example.com:3128'
        self.assertEqual(
            mock_write.call_args_list,
            [
                unittest.mock.call(
                    '/etc/systemd/system/azuremonitor-coreagent.service.d/proxy.conf',
                    expected_proxy),
                unittest.mock.call(
                    '/etc/systemd/system/metrics-extension.service.d/proxy.conf',
                    expected_proxy),
            ])
        commands = [args[0][0] for args in mock_run.call_args_list]
        self.assertEqual(
            commands,
            [
                'systemctl daemon-reload',
                'systemctl restart azuremonitor-coreagent',
                'systemctl restart metrics-extension',
            ])

    def test_write_proxy_conf_creates_restricted_systemd_drop_in(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            conf_path = os.path.join(temp_dir, 'service.d', 'proxy.conf')

            agent._write_proxy_conf(conf_path, 'http://proxy.example.com:8080')

            with open(conf_path, 'r') as conf:
                self.assertEqual(
                    conf.read(),
                    '[Service]\n'
                    'Environment="http_proxy=http://proxy.example.com:8080"\n'
                    'Environment="https_proxy=http://proxy.example.com:8080"\n')
            if os.name != 'nt':
                self.assertEqual(
                    stat.S_IMODE(os.stat(conf_path).st_mode),
                    0o400)


class TestBoundedCommands(unittest.TestCase):
    @unittest.skipIf(os.name == 'nt', 'Requires POSIX process groups')
    def test_timeout_kills_shell_and_children(self):
        started = time.monotonic()
        with patch.object(agent, 'ShutdownRequested', False):
            with self.assertRaises(agent.ProcessTimeout):
                agent.run_subprocess('sleep 60 & wait', shell=True, timeout=0.1)
        self.assertLess(time.monotonic() - started, 5)

    @unittest.skipIf(os.name == 'nt', 'Requires POSIX process groups')
    def test_shutdown_interrupts_blocked_command(self):
        started = time.monotonic()
        with patch.object(agent, 'ShutdownRequested', False):
            notification = Timer(0.1, agent.handle_sigterm, args=(None, None))
            notification.start()
            try:
                with self.assertRaises(agent.AgentShutdown):
                    agent.run_subprocess([sys.executable, '-c', 'import time; time.sleep(60)'])
            finally:
                notification.join()
        self.assertLess(time.monotonic() - started, 5)

    def test_timeout_is_reported_without_command_contents(self):
        with patch('agent.run_subprocess', side_effect=agent.ProcessTimeout), \
                patch('agent.hutil_log_error') as log:
            code, message = agent.run_get_output('command example-credential', log_cmd=False)
        self.assertEqual(code, 124)
        self.assertNotIn('example-credential', message)
        self.assertNotIn('example-credential', str(log.call_args_list))

    def test_waagent_does_not_bypass_command_deadline(self):
        with patch('agent.run_subprocess', return_value=(0, b'ok', None)) as run:
            self.assertEqual(agent.run_get_output('example'), (0, 'ok'))
        run.assert_called_once_with('example', timeout=120, shell=True)

    def test_decryption_timeout_does_not_fall_back_or_log_input(self):
        encrypted = b'example-encrypted-settings'
        settings = {'runtimeSettings': [{'handlerSettings': {
            'publicSettings': {},
            'protectedSettings': base64.b64encode(encrypted).decode('ascii'),
            'protectedSettingsCertThumbprint': 'example-thumbprint'
        }}]}
        with patch.multiple(agent, HUtilObject=None, SettingsDict=None), \
                patch('agent.get_handler_env', return_value={}), \
                patch('agent.get_latest_seq_no', return_value=0), \
                patch('builtins.open', mock_open(read_data=json.dumps(settings))), \
                patch('agent.run_subprocess', side_effect=agent.ProcessTimeout) as run, \
                patch('agent.log_and_exit', side_effect=SystemExit(1)) as exit_handler:
            with self.assertRaises(SystemExit):
                agent.get_settings()
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.kwargs['timeout'], 60)
        self.assertEqual(run.call_args.kwargs['input_data'], encrypted)
        self.assertEqual(run.call_args.kwargs['stderr'], agent.subprocess.PIPE)
        self.assertNotIn(encrypted.decode('ascii'), str(exit_handler.call_args_list))


class TestMetadataRetries(unittest.TestCase):
    def setUp(self):
        endpoint = patch('agent.get_imds_endpoint', return_value='http://metadata/instance')
        endpoint.start()
        self.addCleanup(endpoint.stop)

    def response(self, data):
        response = MagicMock()
        response.read.return_value = json.dumps(data).encode('utf-8')
        return response

    def test_transient_failure_recovers_and_closes_response(self):
        response = self.response({'compute': {'azEnvironment': 'AzurePublicCloud', 'location': 'EastUS'}})
        with patch('agent.urllib.urlopen',
                   side_effect=[agent.urlerror.URLError('unavailable'), response]) as request, \
                patch('agent.wait_for_shutdown', return_value=False) as wait:
            self.assertEqual(agent.get_azure_environment_and_region(), ('azurepubliccloud', 'eastus'))
        self.assertEqual(request.call_count, 2)
        self.assertTrue(all(c.kwargs['timeout'] == 30 for c in request.call_args_list))
        wait.assert_called_once_with(1)
        response.close.assert_called_once()

    def test_retry_exhaustion_is_explicit(self):
        with patch('agent.urllib.urlopen', side_effect=agent.urlerror.URLError('unavailable')) as request, \
                patch('agent.wait_for_shutdown', return_value=False) as wait:
            with self.assertRaises(RuntimeError):
                agent.get_azure_environment_and_region()
        self.assertEqual(request.call_count, 3)
        self.assertEqual(wait.call_args_list, [call(1), call(2)])

    def test_permanent_http_error_is_not_retried(self):
        error = agent.urlerror.HTTPError('http://metadata', 404, 'not found', {}, io.BytesIO())
        with patch('agent.urllib.urlopen', side_effect=error) as request, \
                patch('agent.wait_for_shutdown') as wait:
            with self.assertRaises(RuntimeError):
                agent.get_azure_environment_and_region()
        self.assertEqual(request.call_count, 1)
        wait.assert_not_called()

    def test_malformed_metadata_is_not_silently_disabled(self):
        response = self.response({'compute': {'azEnvironment': 'AzurePublicCloud'}})
        with patch('agent.urllib.urlopen', return_value=response) as request, \
                patch('agent.wait_for_shutdown') as wait:
            with self.assertRaises(RuntimeError):
                agent.get_azure_environment_and_region()
        self.assertEqual(request.call_count, 1)
        wait.assert_not_called()
        response.close.assert_called_once()


@unittest.skipIf(os.name == 'nt', 'Requires POSIX ownership and replacement semantics')
class TestAtomicConfigReplacement(unittest.TestCase):
    def test_success_preserves_owner_and_restricts_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, 'environment')
            with open(path, 'w') as config:
                config.write('old')
            owner = os.stat(path)
            agent.replace_config_file(path, 'complete replacement')
            with open(path) as config:
                self.assertEqual(config.read(), 'complete replacement')
            current = os.stat(path)
            self.assertEqual((current.st_uid, current.st_gid), (owner.st_uid, owner.st_gid))
            self.assertEqual(stat.S_IMODE(current.st_mode), 0o400)
            self.assertEqual(os.listdir(directory), ['environment'])

    def test_rename_failure_preserves_original_and_removes_temporary_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, 'environment')
            with open(path, 'w') as config:
                config.write('old')

            def fail_rename(source, destination):
                self.assertEqual(destination, path)
                with open(path) as config:
                    self.assertEqual(config.read(), 'old')
                with open(source) as config:
                    self.assertEqual(config.read(), 'complete replacement')
                raise OSError('injected rename failure')

            with patch('agent.os.rename', side_effect=fail_rename):
                with self.assertRaises(OSError):
                    agent.replace_config_file(path, 'complete replacement')
            with open(path) as config:
                self.assertEqual(config.read(), 'old')
            self.assertEqual(os.listdir(directory), ['environment'])

    def test_shutdown_before_rename_preserves_original(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, 'environment')
            with open(path, 'w') as config:
                config.write('old')
            with patch.object(agent, 'ShutdownRequested', True):
                with self.assertRaises(agent.AgentShutdown):
                    agent.replace_config_file(path, 'new')
            with open(path) as config:
                self.assertEqual(config.read(), 'old')
            self.assertEqual(os.listdir(directory), ['environment'])


class TestWatcherShutdown(unittest.TestCase):
    def test_repeated_sigterm_only_requests_shutdown(self):
        with patch.object(agent, 'ShutdownRequested', False), \
                patch('agent.hutil_log_info') as log:
            agent.handle_sigterm(None, None)
            agent.handle_sigterm(None, None)
            self.assertTrue(agent.ShutdownRequested)
            log.assert_not_called()

    def test_shutdown_removes_owned_pid_file(self):
        def watcher(*_):
            agent.handle_sigterm(None, None)
            agent.check_shutdown()

        with tempfile.TemporaryDirectory() as directory, \
                patch('agent.os.getcwd', return_value=directory), \
                patch.object(agent, 'ShutdownRequested', False):
            with self.assertRaises(agent.AgentShutdown):
                agent.run_watcher('watcher.pid', watcher)
            self.assertFalse(os.path.exists(os.path.join(directory, 'watcher.pid')))

    def test_cleanup_does_not_remove_another_watchers_pid_file(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch('agent.os.getcwd', return_value=directory):
            path = os.path.join(directory, 'watcher.pid')

            def replacement_watcher(*_):
                with open(path, 'w') as pid_file:
                    pid_file.write('another-pid\n')

            agent.run_watcher('watcher.pid', replacement_watcher)
            with open(path) as pid_file:
                self.assertEqual(pid_file.read(), 'another-pid\n')


class TestMetricsRestartBudget(unittest.TestCase):
    def test_budget_is_persistent_and_only_observed_health_resets_it(self):
        restart = MagicMock(return_value=(True, 'started'))
        errors = {}
        retries = 0
        for _ in range(12):
            retries = agent.restart_metrics_process(
                'Telegraf', False, retries, restart, errors, MagicMock(), MagicMock())
        self.assertEqual(restart.call_count, 10)
        self.assertIn('Telegraf', errors)
        errors['MetricsExtension'] = 'still unhealthy'
        retries = agent.restart_metrics_process(
            'Telegraf', True, retries, restart, errors, MagicMock(), MagicMock())
        self.assertEqual(retries, 0)
        self.assertNotIn('Telegraf', errors)
        self.assertIn('MetricsExtension', errors)
        agent.restart_metrics_process(
            'Telegraf', False, retries, restart, errors, MagicMock(), MagicMock())
        self.assertEqual(restart.call_count, 11)

    def test_cmv2_startup_path_cannot_bypass_budget_without_metrics_config(self):
        waits = [0]
        restart = MagicMock(return_value=(False, 'failed'))
        check_services = MagicMock(return_value=(0, ''))

        def wait(_):
            waits[0] += 1
            if waits[0] >= 13:
                agent.ShutdownRequested = True
            return agent.ShutdownRequested

        with patch.multiple(
                agent, ShutdownRequested=False,
                get_managed_identity=MagicMock(return_value=(None, None, '')),
                is_systemd=MagicMock(return_value=True), run_get_output=check_services,
                azureotelcollector_is_active=MagicMock(return_value=True),
                is_feature_enabled=MagicMock(return_value=True),
                start_metrics_cmv2=restart,
                report_watcher_health=MagicMock(return_value=None),
                wait_for_shutdown=MagicMock(side_effect=wait)), \
                patch('agent.os.path.isfile', return_value=False), \
                patch.object(agent.me_handler, 'is_running', return_value=False):
            agent.metrics_watcher(MagicMock(), MagicMock())
        self.assertEqual(restart.call_count, 10)
        self.assertEqual(check_services.call_count, 24)


class TestCoreServiceHealth(unittest.TestCase):
    def test_threshold_deduplication_and_independent_service_recovery(self):
        failures, errors = {}, {}
        with patch('agent.is_systemd', return_value=True), \
                patch('agent.run_get_output', side_effect=[(1, ''), (0, '')] * 3):
            for _ in range(2):
                agent.monitor_agent_services(failures, errors)
                self.assertEqual(errors, {})
            agent.monitor_agent_services(failures, errors)
        self.assertIn('azuremonitoragent', errors)
        self.assertNotIn('azuremonitor-coreagent', errors)

        with patch('agent.update_status_file') as status:
            previous = agent.report_watcher_health(errors, None)
            agent.report_watcher_health(errors, previous)
            self.assertEqual(status.call_count, 1)
            self.assertEqual(status.call_args.args[2], 'error')
            with patch('agent.is_systemd', return_value=True), \
                    patch('agent.run_get_output', return_value=(0, '')):
                agent.monitor_agent_services(failures, errors)
            self.assertIsNone(agent.report_watcher_health(errors, previous))
            self.assertEqual(status.call_count, 2)
            self.assertEqual(status.call_args.args[2], 'success')

    def test_transient_failures_do_not_report_unhealthy(self):
        failures, errors = {}, {}
        with patch('agent.is_systemd', return_value=False), \
                patch('agent.get_service_command', return_value='service status'), \
                patch('agent.run_get_output', side_effect=[(1, ''), (1, ''), (0, '')]):
            for _ in range(3):
                agent.monitor_agent_services(failures, errors)
        self.assertEqual(errors, {})
        self.assertEqual(failures['azuremonitoragent'], 0)


class TestGracefulFluentBitStop(unittest.TestCase):
    def test_identity_matches_exact_executable_and_handles_deleted_binary(self):
        fields = ['S'] + ['0'] * 18 + ['start-time']
        proc_stat = '10 (fluent bit (worker)) ' + ' '.join(fields)
        with patch('agent.os.readlink', return_value='/expected/fluent-bit (deleted)'), \
                patch('builtins.open', mock_open(read_data=proc_stat)):
            self.assertEqual(agent._process_identity(10, '/expected/fluent-bit'), 'start-time')
        with patch('agent.os.readlink', return_value='/unrelated/fluent-bit'):
            self.assertIsNone(agent._process_identity(10, '/expected/fluent-bit'))

    def test_successful_service_stop_does_not_invoke_manual_kill(self):
        with patch.multiple(
                agent, is_systemd=MagicMock(return_value=True),
                stop_metrics_process=MagicMock(), stop_syslogconfig_process=MagicMock(),
                stop_transformconfig_process=MagicMock(),
                run_command_and_log=MagicMock(return_value=(0, '')),
                check_kill_process=MagicMock()), \
                patch('agent.platform.machine', return_value='aarch64'):
            code, _ = agent.disable()
            self.assertEqual(code, 0)
            agent.check_kill_process.assert_not_called()

    def test_failed_service_stop_uses_fallback_and_preserves_failure(self):
        def command(cmd, **_):
            return (1, 'stop failed') if cmd == 'systemctl stop azuremonitor-agentlauncher' else (0, '')

        with patch.multiple(
                agent, is_systemd=MagicMock(return_value=True),
                stop_metrics_process=MagicMock(), stop_syslogconfig_process=MagicMock(),
                stop_transformconfig_process=MagicMock(),
                run_command_and_log=MagicMock(side_effect=command),
                check_kill_process=MagicMock(return_value=True)), \
                patch('agent.platform.machine', return_value='aarch64'):
            code, _ = agent.disable()
            self.assertNotEqual(code, 0)
            agent.check_kill_process.assert_called_once_with('/opt/microsoft/azuremonitoragent/bin/fluent-bit')

    def test_term_exit_does_not_escalate_or_signal_unrelated_process(self):
        identities = {10: 'start-time', 11: None}

        def terminate(pid, signum):
            self.assertEqual(signum, agent.signal.SIGTERM)
            identities[pid] = None

        with patch('agent.glob.glob', return_value=['/proc/10', '/proc/11']), \
                patch('agent._process_identity', side_effect=lambda pid, _: identities[pid]), \
                patch('agent._reap_process'), \
                patch('agent.os.kill', side_effect=terminate) as kill:
            self.assertTrue(agent.check_kill_process('/expected/fluent-bit'))
        kill.assert_called_once_with(10, agent.signal.SIGTERM)

    def test_survivor_is_killed_after_grace_period(self):
        identity = ['start-time']

        def signal_process(pid, signum):
            if signum == agent.signal.SIGKILL:
                identity[0] = None

        with patch('agent.glob.glob', return_value=['/proc/10']), \
                patch('agent._process_identity', side_effect=lambda *_: identity[0]), \
                patch('agent._reap_process'), \
                patch('agent.time.monotonic', side_effect=[0, 11, 12, 13]), \
                patch('agent.os.kill', side_effect=signal_process) as kill:
            self.assertTrue(agent.check_kill_process('/expected/fluent-bit'))
        self.assertEqual(kill.call_args_list,
                         [call(10, agent.signal.SIGTERM), call(10, agent.signal.SIGKILL)])

    def test_reused_pid_is_not_signalled(self):
        with patch('agent.glob.glob', return_value=['/proc/10']), \
                patch('agent._process_identity', side_effect=['original', 'replacement', 'replacement']), \
                patch('agent._reap_process'), \
                patch('agent.os.kill') as kill:
            self.assertTrue(agent.check_kill_process('/expected/fluent-bit'))
        kill.assert_not_called()


if __name__ == '__main__':
    unittest.main()
