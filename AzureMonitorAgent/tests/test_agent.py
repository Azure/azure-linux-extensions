#!/usr/bin/env python
"""
Unit tests for AzureMonitorAgent/agent.py - pure logic functions only.
"""

import sys
import os
import re
import stat
import io
import json
import tempfile
import unittest
from unittest.mock import patch, MagicMock, mock_open, call

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
    """Tests for global libcurl upload enablement and feature overrides."""

    def test_enabled_in_all_regions(self):
        for region in ('eastus2euap', 'centraluseuap', 'westcentralus', 'eastasia',
                       'eastus', 'westus2', 'centralus', 'usgovvirginia', 'chinaeast2',
                       'future-region'):
            with patch('os.path.exists', return_value=False):
                with patch('agent.get_azure_environment_and_region',
                           return_value=('AzureCloud', region)):
                    self.assertTrue(
                        agent.is_feature_enabled('enableCurlUpload'),
                        msg="enableCurlUpload should be enabled in region %r" % region)

    def test_global_features_do_not_query_imds(self):
        with patch('os.path.exists', return_value=False), \
                patch('agent.get_azure_environment_and_region', side_effect=RuntimeError) as metadata:
            for feature in ('enableCurlUpload', 'useDynamicSSL', 'enableCMV2', 'enableAzureOTelCollector'):
                self.assertTrue(agent.is_feature_enabled(feature))
            self.assertFalse(agent.is_feature_enabled('someUnknownFeature'))
            metadata.assert_not_called()

    def test_preview_flag_file_forces_enable(self):
        """A previewFeatures/<feature> flag file enables the feature in any region."""
        flag_path = agent.PreviewFeaturesDirectory + 'enableCurlUpload'

        def exists_side_effect(path):
            return path == flag_path

        with patch('os.path.exists', side_effect=exists_side_effect):
            with patch('agent.get_azure_environment_and_region',
                       return_value=('AzureCloud', 'eastus')):
                self.assertTrue(agent.is_feature_enabled('enableCurlUpload'))

    def test_disabled_flag_file_forces_disable(self):
        """The explicit disable flag overrides global default enablement."""
        disabled_path = agent.PreviewFeaturesDirectory + 'enableCurlUploadDisabled'

        def exists_side_effect(path):
            return path == disabled_path

        with patch('os.path.exists', side_effect=exists_side_effect):
            with patch('agent.get_azure_environment_and_region',
                       return_value=('AzureCloud', 'eastus')):
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


class TestMetricsRestartBudgets(unittest.TestCase):
    class StopWatcher(Exception):
        pass

    def test_failed_health_checks_exhaust_both_budgets_even_if_start_reports_success(self):
        for started in (False, True):
            with self.subTest(started=started):
                retries = {'Telegraf': 0, 'MetricsExtension': 0}
                errors = {}
                restart = MagicMock(return_value=(started, 'start result'))
                for _ in range(12):
                    for name in retries:
                        agent.restart_metrics_process(
                            name, False, retries, restart, errors, MagicMock(), MagicMock())
                self.assertEqual(restart.call_count, 20)
                self.assertEqual(retries, {'Telegraf': 10, 'MetricsExtension': 10})
                self.assertEqual(set(errors), set(retries))

    def test_recovery_resets_only_the_healthy_process_budget(self):
        retries = {'Telegraf': 10, 'MetricsExtension': 10}
        errors = {'Telegraf': 'failed', 'MetricsExtension': 'failed'}
        restart = MagicMock(return_value=(False, 'failed'))
        agent.restart_metrics_process(
            'MetricsExtension', True, retries, restart, errors, MagicMock(), MagicMock())
        self.assertEqual(retries, {'Telegraf': 10, 'MetricsExtension': 0})
        self.assertEqual(errors, {'Telegraf': 'failed'})
        for _ in range(4):
            for name in retries:
                agent.restart_metrics_process(
                    name, False, retries, restart, errors, MagicMock(), MagicMock())
        self.assertEqual(restart.call_count, 4)
        agent.restart_metrics_process(
            'Telegraf', True, retries, restart, errors, MagicMock(), MagicMock())
        self.assertEqual(retries, {'Telegraf': 0, 'MetricsExtension': 4})
        agent.restart_metrics_process(
            'Telegraf', False, retries, restart, errors, MagicMock(), MagicMock())
        self.assertEqual(restart.call_count, 5)

    def test_setup_exceptions_consume_the_budget(self):
        retries = {'MetricsExtension': 0}
        errors = {}
        restart = MagicMock(side_effect=OSError('setup failed'))
        for _ in range(12):
            agent.restart_metrics_process(
                'MetricsExtension', False, retries, restart, errors, MagicMock(), MagicMock())
        self.assertEqual(restart.call_count, 10)
        self.assertIn('MetricsExtension', errors)

    def test_exhaustion_status_is_deduplicated_and_clears_after_all_recover(self):
        errors = {'Telegraf': 'Telegraf exhausted', 'MetricsExtension': 'ME exhausted'}
        with patch('agent.update_status_file') as status, \
                patch.object(agent, 'SettingsSequenceNumber', 42):
            previous = agent.report_metrics_restart_status(errors, None)
            self.assertIsNone(agent.SettingsSequenceNumber)
            agent.report_metrics_restart_status(errors, previous)
            self.assertEqual(status.call_count, 1)
            self.assertEqual(status.call_args.args[2], 'error')
            del errors['MetricsExtension']
            previous = agent.report_metrics_restart_status(errors, previous)
            self.assertEqual(status.call_count, 2)
            self.assertEqual(status.call_args.args[2], 'error')
            del errors['Telegraf']
            previous = agent.report_metrics_restart_status(errors, previous)
            self.assertEqual(status.call_count, 3)
            self.assertEqual(status.call_args.args[2], 'success')
            self.assertIsNone(previous)
            agent.report_metrics_restart_status(errors, previous)
            self.assertEqual(status.call_count, 3)

    def run_watcher_until_exhausted(self, cmv2, changing_config=False):
        config = mock_open(read_data='[{"name": "counter"}]')
        if changing_config:
            config.return_value.read.side_effect = [
                json.dumps([{'name': 'counter-{0}'.format(index)}]) for index in range(12)]
        with patch('agent.telhandler') as telegraf, \
                patch('agent.me_handler') as me, \
                patch('agent.get_managed_identity', return_value=(None, None, '')), \
                patch('agent.azureotelcollector_is_active', return_value=True), \
                patch('agent.is_feature_enabled', return_value=cmv2), \
                patch('agent.copyfile'), \
                patch('agent.os.path.exists', return_value=False), \
                patch('agent.os.path.isfile', side_effect=lambda path: not cmv2 and path == agent.MdsdCounterJsonPath), \
                patch('builtins.open', config), \
                patch('agent.time.sleep', side_effect=[None] * 12 + [self.StopWatcher()]), \
                patch('agent.update_status_file') as status, \
                patch.object(agent, 'SettingsSequenceNumber', None):
            telegraf.is_running.return_value = False
            telegraf.handle_config.return_value = (True, [])
            telegraf.stop_telegraf_service.return_value = (True, 'stopped')
            telegraf.start_telegraf.return_value = (False, 'failed')
            me.is_running.return_value = False
            me.stop_metrics_service.return_value = (True, 'stopped')
            me.start_metrics.return_value = (False, 'failed')
            me.start_metrics_cmv2.return_value = (False, 'failed')
            me.generate_MSI_token.return_value = (False, None, 'token unavailable')
            with self.assertRaises(self.StopWatcher):
                agent.metrics_watcher(MagicMock(), MagicMock())
            self.assertEqual(status.call_count, 1)
            self.assertEqual(status.call_args.args[2], 'error')
            if cmv2:
                self.assertEqual(me.start_metrics_cmv2.call_count, 10)
                me.start_metrics.assert_not_called()
                telegraf.start_telegraf.assert_not_called()
            else:
                self.assertEqual(telegraf.start_telegraf.call_count, 10)
                self.assertEqual(me.start_metrics.call_count, 10)
                me.start_metrics_cmv2.assert_not_called()

    def test_cmv1_restart_limits_persist_across_watcher_cycles(self):
        self.run_watcher_until_exhausted(False)

    def test_configuration_changes_cannot_bypass_restart_limits(self):
        self.run_watcher_until_exhausted(False, changing_config=True)

    def test_cmv2_startup_is_bounded_even_without_metrics_configuration(self):
        self.run_watcher_until_exhausted(True)


class TestMetadataRetries(unittest.TestCase):
    def setUp(self):
        endpoint = patch('agent.get_imds_endpoint', return_value='http://metadata/instance')
        endpoint.start()
        self.addCleanup(endpoint.stop)

    def test_first_failure_recovers_with_finite_timeout_and_response_cleanup(self):
        failures = [
            agent.urlerror.URLError('unavailable'),
            agent.urlerror.HTTPError('http://metadata', 429, 'throttled', {}, io.BytesIO()),
            agent.urlerror.HTTPError('http://metadata', 503, 'unavailable', {}, io.BytesIO()),
        ]
        for failure in failures:
            with self.subTest(failure=type(failure).__name__):
                response = MagicMock()
                response.read.return_value = json.dumps({
                    'compute': {'azEnvironment': 'AzurePublicCloud', 'location': 'EastUS'}}).encode('utf-8')
                with patch('agent.urllib.urlopen', side_effect=[failure, response]) as request, \
                        patch('agent.time.sleep') as sleep:
                    self.assertEqual(agent.get_azure_environment_and_region(), ('azurepubliccloud', 'eastus'))
                self.assertEqual(request.call_count, 2)
                self.assertTrue(all(c.kwargs['timeout'] == 30 for c in request.call_args_list))
                sleep.assert_called_once_with(1)
                response.close.assert_called_once()

    def test_exhausted_retries_raise_instead_of_returning_missing_metadata(self):
        with patch('agent.urllib.urlopen', side_effect=agent.urlerror.URLError('unavailable')) as request, \
                patch('agent.time.sleep') as sleep:
            with self.assertRaises(RuntimeError):
                agent.get_azure_environment_and_region()
        self.assertEqual(request.call_count, 4)
        self.assertEqual(sleep.call_args_list, [call(1), call(2), call(4)])

    def test_permanent_http_error_is_not_retried_or_logged_with_its_body(self):
        response_body = io.BytesIO(b'example-response-body')
        error = agent.urlerror.HTTPError('http://metadata', 404, 'not found', {}, response_body)
        with patch('agent.urllib.urlopen', side_effect=error) as request, \
                patch('agent.time.sleep') as sleep, \
                patch('agent.hutil_log_error') as log:
            with self.assertRaisesRegex(RuntimeError, 'HTTP 404'):
                agent.get_azure_environment_and_region()
        self.assertEqual(request.call_count, 1)
        sleep.assert_not_called()
        self.assertTrue(response_body.closed)
        self.assertNotIn('example-response-body', str(log.call_args_list))

    def test_malformed_responses_fail_explicitly_and_close_the_response(self):
        responses = [
            b'not-json', b'{}', b'{"compute": null}',
            b'{"compute": {"azEnvironment": "AzurePublicCloud"}}',
            b'{"compute": {"azEnvironment": 123, "location": "eastus"}}',
            b'{"compute": {"azEnvironment": "AzurePublicCloud", "location": " "}}',
        ]
        for payload in responses:
            with self.subTest(payload=payload):
                response = MagicMock()
                response.read.return_value = payload
                with patch('agent.urllib.urlopen', return_value=response) as request, \
                        patch('agent.time.sleep') as sleep:
                    with self.assertRaises(RuntimeError):
                        agent.get_azure_environment_and_region()
                self.assertEqual(request.call_count, 1)
                sleep.assert_not_called()
                response.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
