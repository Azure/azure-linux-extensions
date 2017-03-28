import unittest
import json
import os
from xml.etree import ElementTree as ET
# This test suite uses xmlunittest package. Install it by running 'pip install xmlunittest'.
# Documentation at http://python-xmlunittest.readthedocs.io/en/latest/
from xmlunittest import XmlTestMixin

from Utils.lad_logging_config import *


class LadLoggingConfigTest(unittest.TestCase, XmlTestMixin):

    def setUp(self):
        """
        Create LadLoggingConfig objects for use by test cases
        """
        # "syslogEvents" LAD config example
        syslog_basic_json_ext_settings = """
            {
                "syslogEventConfiguration": {
                    "LOG_LOCAL0": "LOG_CRIT",
                    "LOG_USER": "LOG_ERR"
                }
            }
            """
        # "syslogCfg" LAD config example
        syslog_extended_json_ext_settings = """
            [
                {
                    "facility": "LOG_USER",
                    "minSeverity": "LOG_ERR",
                    "table": "SyslogUserErrorEvents"
                },
                {
                    "facility": "LOG_LOCAL0",
                    "minSeverity": "LOG_CRIT",
                    "table": "SyslogLocal0CritEvents"
                }
            ]
            """
        # "fileLogs" LAD config example
        filelogs_json_ext_settings = """
            [
                {
                    "file": "/var/log/mydaemonlog1",
                    "table": "MyDaemon1Events"
                },
                {
                    "file": "/var/log/mydaemonlog2",
                    "table": "MyDaemon2Events"
                }
            ]
            """

        syslogEvents = json.loads(syslog_basic_json_ext_settings)
        syslogCfg = json.loads(syslog_extended_json_ext_settings)
        self.cfg_syslog_basic = LadLoggingConfig(syslogEvents, None, None, True)
        self.cfg_syslog_ext = LadLoggingConfig(None, syslogCfg, None, True)
        self.cfg_syslog_all = LadLoggingConfig(None, None, None, True)
        fileLogs = json.loads(filelogs_json_ext_settings)
        self.cfg_filelog = LadLoggingConfig(None, None, fileLogs, False)
        self.cfg_none = LadLoggingConfig(None, None, None, False)

        # XPaths representations of expected XML outputs, for use with xmlunittests package
        self.oms_syslog_basic_expected_xpaths = ('./Sources/Source[@name="mdsd.syslog" and @dynamic_schema="true"]',
                                                 './Events/MdsdEvents/MdsdEventSource[@source="mdsd.syslog"]',
                                                 './Events/MdsdEvents/MdsdEventSource[@source="mdsd.syslog"]/RouteEvent[@dontUsePerNDayTable="true" and @eventName="LinuxSyslog" and @priority="High"]',
                                                 )
        self.oms_syslog_ext_expected_xpaths = ('./Sources/Source[@name="mdsd.ext_syslog.local0" and @dynamic_schema="true"]',
                                               './Sources/Source[@name="mdsd.ext_syslog.user" and @dynamic_schema="true"]',
                                               './Events/MdsdEvents/MdsdEventSource[@source="mdsd.ext_syslog.local0"]',
                                               './Events/MdsdEvents/MdsdEventSource[@source="mdsd.ext_syslog.local0"]/RouteEvent[@dontUsePerNDayTable="true" and @eventName="SyslogLocal0CritEvents" and @priority="High"]',
                                               './Events/MdsdEvents/MdsdEventSource[@source="mdsd.ext_syslog.user"]',
                                               './Events/MdsdEvents/MdsdEventSource[@source="mdsd.ext_syslog.user"]/RouteEvent[@dontUsePerNDayTable="true" and @eventName="SyslogUserErrorEvents" and @priority="High"]',
                                              )
        self.oms_filelog_expected_xpaths = ('./Sources/Source[@name="mdsd.filelog.var.log.mydaemonlog1" and @dynamic_schema="true"]',
                                            './Sources/Source[@name="mdsd.filelog.var.log.mydaemonlog2" and @dynamic_schema="true"]',
                                            './Events/MdsdEvents/MdsdEventSource[@source="mdsd.filelog.var.log.mydaemonlog1"]',
                                            './Events/MdsdEvents/MdsdEventSource[@source="mdsd.filelog.var.log.mydaemonlog1"]/RouteEvent[@dontUsePerNDayTable="true" and @eventName="MyDaemon1Events" and @priority="High"]',
                                            './Events/MdsdEvents/MdsdEventSource[@source="mdsd.filelog.var.log.mydaemonlog2"]',
                                            './Events/MdsdEvents/MdsdEventSource[@source="mdsd.filelog.var.log.mydaemonlog2"]/RouteEvent[@dontUsePerNDayTable="true" and @eventName="MyDaemon2Events" and @priority="High"]',
                                           )

    def test_oms_syslog_config(self):
        """
        Test whether syslog/syslog-ng config (for use with omsagent) is correctly generated for both 'syslogEvents'
        and 'syslogCfg' settings. Also test whether the coresponding mdsd XML config is correctly generated.
        """
        # Basic config (single dest table)
        self.__helper_test_oms_syslog_config(self.cfg_syslog_basic, self.oms_syslog_basic_expected_xpaths)
        self.__helper_test_oms_syslog_config(self.cfg_syslog_all, self.oms_syslog_basic_expected_xpaths)

        # Extended config (per-facility dest table)
        self.__helper_test_oms_syslog_config(self.cfg_syslog_ext, self.oms_syslog_ext_expected_xpaths)

        # No syslog config case
        self.assertFalse(self.cfg_none.get_oms_rsyslog_config())
        self.assertFalse(self.cfg_none.get_oms_syslog_ng_config())
        self.assertFalse(self.cfg_none.get_oms_mdsd_syslog_config())

    def __helper_test_oms_syslog_config(self, cfg, expected_xpaths):
        """
        Helper for test_oms_rsyslog().
        :param cfg: SyslogMdsdConfig object containing syslog config
        """
        print '=== Actual oms rsyslog config output ==='
        oms_rsyslog_config = cfg.get_oms_rsyslog_config()
        print oms_rsyslog_config
        print '========================================'
        lines = oms_rsyslog_config.strip().split('\n')
        if cfg._all_syslog_facility_severity_enabled:
            # Only 1 line should be out: "*.*  @127.0.0.1:%SYSLOG_PORT%"
            self.assertEqual(1, len(lines))
            self.assertRegexpMatches(lines[0], r"\*\.\*\s+@127\.0\.0\.1:%SYSLOG_PORT%")
        else:
            # Item (line) count should match
            self.assertEqual(len(cfg._fac_sev_map), len(lines))
            # Each line should be correctly formatted
            for l in lines:
                self.assertRegexpMatches(l, r"\w+\.\w+\s+@127\.0\.0\.1:%SYSLOG_PORT%")
            # For each facility-severity, there should be corresponding line.
            for fac, sev in cfg._fac_sev_map.iteritems():
                index = oms_rsyslog_config.find('{0}.{1}'.format(syslog_name_to_rsyslog_name(fac),
                                                                 syslog_name_to_rsyslog_name(sev)))
                self.assertGreaterEqual(index, 0)
        print "*** Actual output verified ***\n"

        print '=== Actual oms syslog-ng config output ==='
        oms_syslog_ng_config = cfg.get_oms_syslog_ng_config()
        print oms_syslog_ng_config
        print '=========================================='
        lines = oms_syslog_ng_config.strip().split('\n')
        if cfg._all_syslog_facility_severity_enabled:
            # Only 1 line should be out: "*.*  @127.0.0.1:%SYSLOG_PORT%"
            self.assertEqual(1, len(lines))
            self.assertRegexpMatches(lines[0], r"log \{ source\(s_src\); destination\(d_LAD_oms\); \}")
        else:
            # Item (line) count should match
            self.assertGreaterEqual(len(lines), len(cfg._fac_sev_map))
            # Each line should be correctly formatted
            for l in lines:
                self.assertRegexpMatches(l, r"log \{ source\(s_src\); filter\(f_LAD_oms_f_\w+\); filter\(f_LAD_oms_ml_\w+\); destination\(d_LAD_oms\); \}")
            # For each facility-severity, there should be corresponding line.
            for fac, sev in cfg._fac_sev_map.iteritems():
                index = oms_syslog_ng_config.find('log {{ source(s_src); filter(f_LAD_oms_f_{0}); filter(f_LAD_oms_ml_{1}); '
                                                  'destination(d_LAD_oms); }}'.format(syslog_name_to_rsyslog_name(fac),
                                                                                      syslog_name_to_rsyslog_name(sev)))
                self.assertGreaterEqual(index, 0)
        print "*** Actual output verified ***\n"

        print '=== Actual oms syslog mdsd XML output ==='
        xml = cfg.get_oms_mdsd_syslog_config()
        print xml
        print '========================================='
        root = self.assertXmlDocument(xml)
        self.assertXpathsOnlyOne(root, expected_xpaths)
        print "*** Actual output verified ***\n"

    def test_oms_filelog_mdsd_config(self):
        """
        Test whether mdsd XML config for LAD fileLog settings is correctly generated.
        """
        print '=== Actual oms filelog mdsd XML config output ==='
        xml = self.cfg_filelog.get_oms_mdsd_filelog_config()
        print xml
        print '================================================='
        root = self.assertXmlDocument(xml)

        self.assertXpathsOnlyOne(root, self.oms_filelog_expected_xpaths)
        print "*** Actual output verified ***\n"

        # Other configs should be all ''
        self.assertFalse(self.cfg_syslog_all.get_oms_mdsd_filelog_config())
        self.assertFalse(self.cfg_syslog_basic.get_oms_mdsd_filelog_config())
        self.assertFalse(self.cfg_syslog_ext.get_oms_mdsd_filelog_config())
        self.assertFalse(self.cfg_none.get_oms_mdsd_filelog_config())

    def __helper_test_oms_fluentd_config(self, header_text, expected, actual):
        header = "=== Actual output of {0} ===".format(header_text)
        print header
        print actual
        print '=' * len(header)
        # TODO BADBAD exact string matching...
        self.assertEqual(expected, actual)
        pass

    def test_oms_fluentd_configs(self):
        """
        Test whether fluentd syslog/tail source configs & out_mdsd config are correctly generated.
        """
        actual = self.cfg_syslog_basic.get_oms_fluentd_syslog_src_config()
        expected = """
<source>
  type syslog
  port %SYSLOG_PORT%
  bind 127.0.0.1
  protocol_type udp
  tag mdsd.syslog
</source>

# Generate fields expected for existing mdsd syslog collection schema.
<filter mdsd.syslog.**>
  type record_transformer
  enable_ruby
  <record>
    # Fields expected by mdsd for syslog messages
    Ignore "syslog"
    Facility ${tag_parts[2]}
    Severity ${tag_parts[3]}
    EventTime ${time.strftime('%Y-%m-%dT%H:%M:%S%z')}
    SendingHost ${record["source_host"]}
    Msg ${record["message"]}
  </record>
  remove_keys host,ident,pid,message,source_host  # No need of these fields for mdsd so remove
</filter>
"""
        self.__helper_test_oms_fluentd_config('fluentd basic syslog src config', expected, actual)

        actual = self.cfg_syslog_all.get_oms_fluentd_syslog_src_config()
        self.__helper_test_oms_fluentd_config('fluentd all syslog src config', expected, actual)

        actual = self.cfg_syslog_ext.get_oms_fluentd_syslog_src_config()
        expected = """
<source>
  type syslog
  port %SYSLOG_PORT%
  bind 127.0.0.1
  protocol_type udp
  tag mdsd.ext_syslog
</source>

# Generate fields expected for existing mdsd syslog collection schema.
<filter mdsd.ext_syslog.**>
  type record_transformer
  enable_ruby
  <record>
    # Fields expected by mdsd for syslog messages
    Ignore "syslog"
    Facility ${tag_parts[2]}
    Severity ${tag_parts[3]}
    EventTime ${time.strftime('%Y-%m-%dT%H:%M:%S%z')}
    SendingHost ${record["source_host"]}
    Msg ${record["message"]}
  </record>
  remove_keys host,ident,pid,message,source_host  # No need of these fields for mdsd so remove
</filter>
"""
        self.__helper_test_oms_fluentd_config('fluentd extended syslog src config', expected, actual)

        actual = self.cfg_filelog.get_oms_fluentd_syslog_src_config()
        expected = ''
        self.__helper_test_oms_fluentd_config('fluentd syslog src config for no syslog', expected, actual)

        actual = self.cfg_syslog_basic.get_oms_fluentd_out_mdsd_config()
        expected_out_mdsd_cfg_template = r"""
# Output to mdsd
<match mdsd.**>
    type mdsd
    log_level warn
    djsonsocket /var/run/mdsd/lad_mdsd_djson.socket  # Full path to mdsd dynamic json socket file
    acktimeoutms 5000  # max time in milli-seconds to wait for mdsd acknowledge response. If 0, no wait.
{optional_lines}    num_threads 1
    buffer_chunk_limit 1000k
    buffer_type file
    buffer_path /var/opt/microsoft/omsagent/state/out_mdsd*.buffer
    buffer_queue_limit 128
    flush_interval 10s
    retry_limit 3
    retry_wait 10s
</match>
"""
        out_mdsd_optional_config_lines = r"""    mdsd_tag_regex_patterns [ "^mdsd\\.syslog" ] # fluentd tag patterns whose match will be used as mdsd source name
"""
        self.__helper_test_oms_fluentd_config('fluentd out_mdsd config for basic syslog cfg',
                                              expected_out_mdsd_cfg_template.format(
                                                  optional_lines=out_mdsd_optional_config_lines), actual)

        actual = self.cfg_syslog_all.get_oms_fluentd_out_mdsd_config()
        self.__helper_test_oms_fluentd_config('fluentd out_mdsd config for all syslog cfg',
                                              expected_out_mdsd_cfg_template.format(
                                                  optional_lines=out_mdsd_optional_config_lines), actual)

        actual = self.cfg_syslog_ext.get_oms_fluentd_out_mdsd_config()
        out_mdsd_optional_config_lines = r"""    mdsd_tag_regex_patterns [ "^mdsd\\.ext_syslog\\.\\w+" ] # fluentd tag patterns whose match will be used as mdsd source name
"""
        self.__helper_test_oms_fluentd_config('fluentd out_mdsd config for extended syslog cfg',
                                              expected_out_mdsd_cfg_template.format(
                                                  optional_lines=out_mdsd_optional_config_lines), actual)

        actual = self.cfg_filelog.get_oms_fluentd_filelog_src_config()
        expected = """
# For all monitored files
<source>
  @type tail
  path /var/log/mydaemonlog1,/var/log/mydaemonlog2
  pos_file /var/opt/microsoft/omsagent/LAD/tmp/filelogs.pos
  tag mdsd.filelog.*
  format none
  message_key Msg  # LAD uses "Msg" as the field name
</source>

# Add FileTag field (existing LAD behavior)
<filter mdsd.filelog.**>
  @type record_transformer
  <record>
    FileTag ${tag_suffix[2]}
  </record>
</filter>
"""
        self.__helper_test_oms_fluentd_config('fluentd tail src config for fileLogs', expected, actual)

        actual = self.cfg_filelog.get_oms_fluentd_out_mdsd_config()
        self.__helper_test_oms_fluentd_config('fluentd out_mdsd config for filelog only (no syslog) cfg',
                                              expected_out_mdsd_cfg_template.format(optional_lines=''), actual)

        actual = self.cfg_none.get_oms_fluentd_out_mdsd_config()
        self.__helper_test_oms_fluentd_config('fluentd out_mdsd config for blank cfg (syslog disabled)',
                                              expected_out_mdsd_cfg_template.format(optional_lines=''), actual)

    def test_copy_schema_source_mdsdevent_elems(self):
        """
        Tests whether copy_schema_source_mdsdevent_elems() works fine.
        Uses syslog_mdsd_extended_expected_output and filelogs_mdsd_expected_output XML strings
        to test the operation.
        """
        xml_string_srcs = [ self.cfg_syslog_ext.get_oms_mdsd_syslog_config(),
                            self.cfg_filelog.get_oms_mdsd_filelog_config()
                          ]
        dst_xml_tree = ET.parse(os.path.join(os.path.dirname(__file__), os.pardir, 'mdsdConfig.xml.template'))
        map(lambda x: copy_source_mdsdevent_elems(dst_xml_tree, x), xml_string_srcs)
        print '=== mdsd config XML after combining syslog/filelogs XML configs ==='
        xml = ET.tostring(dst_xml_tree.getroot())
        print xml
        print '==================================================================='
        # Verify using xmlunittests
        root = self.assertXmlDocument(xml)
        self.assertXpathsOnlyOne(root, self.oms_syslog_ext_expected_xpaths)
        self.assertXpathsOnlyOne(root, self.oms_filelog_expected_xpaths)
        print "*** Actual output verified ***\n"


if __name__ == '__main__':
    unittest.main()
