import unittest
import json
from xml.etree import ElementTree as ET
# This test suite uses xmlunittest package. Install it by running 'pip install xmlunittest'.
# Documentation at http://python-xmlunittest.readthedocs.io/en/latest/
from xmlunittest import XmlTestMixin

from Utils.lad30_syslog_config import *


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

# <!-- Expected mdsd XML config for syslog_extended_json_ext_settings -->
# This resulting XML will need to be merged to the main mdsd config XML that's created from mdsdConfig.xml.template.
oms_syslog_mdsd_ext_expected_xml = """
<MonitoringManagement eventVersion="2" namespace="" timestamp="2014-12-01T20:00:00.000" version="1.0">
  <Sources>
    <Source name="mdsd.ext_syslog.local0" dynamic_schema="true" />
    <Source name="mdsd.ext_syslog.user" dynamic_schema="true" />
  </Sources>

  <Events>
    <MdsdEvents>
      <MdsdEventSource source="mdsd.ext_syslog.local0">
        <RouteEvent dontUsePerNDayTable="true" eventName="SyslogLocal0CritEvents" priority="High" />
      </MdsdEventSource>
      <MdsdEventSource source="mdsd.ext_syslog.user">
        <RouteEvent dontUsePerNDayTable="true" eventName="SyslogUserErrorEvents" priority="High" />
      </MdsdEventSource>
    </MdsdEvents>
  </Events>
</MonitoringManagement>
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

# <!-- Expected mdsd XML config for filelogs_json_ext_settings -->
# This resulting XML will need to be merged to the main mdsd config XML that's created from mdsdConfig.xml.template.
oms_filelogs_mdsd_expected_xml = """
<MonitoringManagement eventVersion="2" namespace="" timestamp="2014-12-01T20:00:00.000" version="1.0">
  <Sources>
    <Source name="mdsd.filelog.var.log.mydaemonlog1" dynamic_schema="true" />
    <Source name="mdsd.filelog.var.log.mydaemonlog2" dynamic_schema="true" />
  </Sources>

  <Events>
    <MdsdEvents>
      <MdsdEventSource source="mdsd.filelog.var.log.mydaemonlog1">
        <RouteEvent dontUsePerNDayTable="true" eventName="MyDaemon1Events" priority="High" />
      </MdsdEventSource>
      <MdsdEventSource source="mdsd.filelog.var.log.mydaemonlog2">
        <RouteEvent dontUsePerNDayTable="true" eventName="MyDaemon2Events" priority="High" />
      </MdsdEventSource>
    </MdsdEvents>
  </Events>
</MonitoringManagement>
"""

# XPaths representations of expected XML outputs, for use with xmlunittests package
oms_syslog_basic_expected_xpaths = ('./Sources/Source[@name="mdsd.syslog" and @dynamic_schema="true"]',
                                    './Events/MdsdEvents/MdsdEventSource[@source="mdsd.syslog"]',
                                    './Events/MdsdEvents/MdsdEventSource[@source="mdsd.syslog"]/RouteEvent[@dontUsePerNDayTable="true" and @eventName="LinuxSyslog" and @priority="High"]',
                                   )

oms_syslog_ext_expected_xpaths = ('./Sources/Source[@name="mdsd.ext_syslog.local0" and @dynamic_schema="true"]',
                                  './Sources/Source[@name="mdsd.ext_syslog.user" and @dynamic_schema="true"]',
                                  './Events/MdsdEvents/MdsdEventSource[@source="mdsd.ext_syslog.local0"]',
                                  './Events/MdsdEvents/MdsdEventSource[@source="mdsd.ext_syslog.local0"]/RouteEvent[@dontUsePerNDayTable="true" and @eventName="SyslogLocal0CritEvents" and @priority="High"]',
                                  './Events/MdsdEvents/MdsdEventSource[@source="mdsd.ext_syslog.user"]',
                                  './Events/MdsdEvents/MdsdEventSource[@source="mdsd.ext_syslog.user"]/RouteEvent[@dontUsePerNDayTable="true" and @eventName="SyslogUserErrorEvents" and @priority="High"]',
                                  )

oms_filelog_expected_xpaths = ('./Sources/Source[@name="mdsd.filelog.var.log.mydaemonlog1" and @dynamic_schema="true"]',
                               './Sources/Source[@name="mdsd.filelog.var.log.mydaemonlog2" and @dynamic_schema="true"]',
                               './Events/MdsdEvents/MdsdEventSource[@source="mdsd.filelog.var.log.mydaemonlog1"]',
                               './Events/MdsdEvents/MdsdEventSource[@source="mdsd.filelog.var.log.mydaemonlog1"]/RouteEvent[@dontUsePerNDayTable="true" and @eventName="MyDaemon1Events" and @priority="High"]',
                               './Events/MdsdEvents/MdsdEventSource[@source="mdsd.filelog.var.log.mydaemonlog2"]',
                               './Events/MdsdEvents/MdsdEventSource[@source="mdsd.filelog.var.log.mydaemonlog2"]/RouteEvent[@dontUsePerNDayTable="true" and @eventName="MyDaemon2Events" and @priority="High"]',
                              )


class Lad30RsyslogConfigTest(unittest.TestCase, XmlTestMixin):

    def test_oms_syslog_config(self):
        """
        Test whether syslog/syslog-ng config (for use with omsagent) is correctly generated for both 'syslogEvents'
        and 'syslogCfg' settings. Also test whether the coresponding mdsd XML config is correctly generated.
        :return: None
        """
        # Basic config (single dest table)
        syslogEvents = json.loads(syslog_basic_json_ext_settings)
        cfg = SyslogMdsdConfig(syslogEvents, None, None)
        self.helper_test_oms_syslog_config(cfg, oms_syslog_basic_expected_xpaths)

        # Extended config (per-facility dest table)
        syslogCfg = json.loads(syslog_extended_json_ext_settings)
        cfg = SyslogMdsdConfig(None, syslogCfg, None)
        self.helper_test_oms_syslog_config(cfg, oms_syslog_ext_expected_xpaths)

    def helper_test_oms_syslog_config(self, cfg, expected_xpaths):
        """
        Helper for test_oms_rsyslog().
        :param cfg: SyslogMdsdConfig object containing syslog config
        :return: None
        """
        print '=== Actual oms rsyslog config output ==='
        oms_rsyslog_config = cfg.get_oms_rsyslog_config()
        print oms_rsyslog_config
        print '============================================='
        lines = oms_rsyslog_config.strip().split('\n')
        # Item (line) count should match
        self.assertEqual(len(lines), len(cfg._fac_sev_map))
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
        # Item (line) count should match
        self.assertGreaterEqual(len(lines), len(cfg._fac_sev_map))
        # Each line should be correctly formatted
        for l in lines:
            self.assertRegexpMatches(l, r"log \{ source\(src\); filter\(f_LAD_oms_f_\w+\); filter\(f_LAD_oms_ml_\w+\); destination\(d_LAD_oms\); \}")
        # For each facility-severity, there should be corresponding line.
        for fac, sev in cfg._fac_sev_map.iteritems():
            index = oms_syslog_ng_config.find('log {{ source(src); filter(f_LAD_oms_f_{0}); filter(f_LAD_oms_ml_{1}); '
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

    def test_oms_filelog_config(self):
        """
        Test whether mdsd XML config for LAD fileLog settings is correctly generated.
        :return: None
        """
        fileLogs = json.loads(filelogs_json_ext_settings)
        cfg = SyslogMdsdConfig(None, None, fileLogs)
        print '=== Actual oms filelog mdsd XML config output ==='
        xml = cfg.get_oms_mdsd_filelog_config()
        print xml
        print '================================================='
        root = self.assertXmlDocument(xml)
        self.assertXpathsOnlyOne(root, oms_filelog_expected_xpaths)
        print "*** Actual output verified ***\n"

    def test_copy_schema_source_mdsdevent_elems(self):
        """
        Tests whether copy_schema_source_mdsdevent_elems() works fine.
        Uses syslog_mdsd_extended_expected_output and filelogs_mdsd_expected_output XML strings
        to test the operation.
        :return:  None
        """
        xml_string_srcs = [oms_syslog_mdsd_ext_expected_xml, oms_filelogs_mdsd_expected_xml]
        dst_xml_tree = ET.parse('../mdsdConfig.xml.template')
        map(lambda x: copy_source_mdsdevent_elems(dst_xml_tree, x), xml_string_srcs)
        print '=== mdsd config XML after combining syslog/filelogs XML configs ==='
        xml = ET.tostring(dst_xml_tree.getroot())
        print xml
        print '==================================================================='
        # Verify using xmlunittests
        root = self.assertXmlDocument(xml)
        self.assertXpathsOnlyOne(root, oms_syslog_ext_expected_xpaths)
        self.assertXpathsOnlyOne(root, oms_filelog_expected_xpaths)
        print "*** Actual output verified ***\n"


if __name__ == '__main__':
    unittest.main()
