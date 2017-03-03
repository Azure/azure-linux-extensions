import unittest
import json
from xml.etree import ElementTree as ET

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

# Expected omazuremds rsyslog output module config string corresponding to syslog_basic_json_ext_settings
# for rsyslog legacy versions (5/7)
syslog_omazuremds_basic_expected_output_legacy = """
$ModLoad omazuremds.so
$legacymdsdconnections 1
$legacymdsdsocketfile __MDSD_SOCKET_FILE_PATH__

$template fmt_basic, "\"syslog_basic\",%syslogfacility-text:::csv%,\"%syslogseverity%\",\"%timereported:::date-rfc3339%\",\"%fromhost-ip%\",#TOJSON#%rawmsg%"
$ActionQueueType LinkedList
$ActionQueueDequeueBatchSize 100
$ActionQueueSize 10000
$ActionResumeRetryCount -1
$ActionQueueSaveOnShutdown on
$ActionQueueFileName lad_mdsd_queue_syslog_basic
$ActionQueueDiscardSeverity 8
local0.crit;user.err :omazuremds:;fmt_basic
"""

# Expected omazuremds rsyslog output module config string corresponding to syslog_basic_json_ext_settings
# for rsyslog non-legacy version (8)
syslog_omazuremds_basic_expected_output = """
$ModLoad omazuremds

$template fmt_basic,"\"syslog_basic\",\"%syslogfacility-text:::json%\",\"%syslogseverity%\",\"%timereported:::date-rfc3339%\",\"%fromhost-ip%\",\"%rawmsg:::json%\""
local0.crit;user.err action( type="omazuremds"
    template="fmt_basic"
    mdsdsocketfile="__MDSD_SOCKET_FILE_PATH__"
    queue.workerthreads="1"
    queue.dequeuebatchsize="16"
    queue.type="fixedarray"
    queue.filename="lad_mdsd_queue_syslog_basic"
    queue.highwatermark="400"
    queue.lowwatermark="100"
    queue.discardseverity="8"
    queue.maxdiskspace="5g"
    queue.size="500"
    queue.saveonshutdown="on"
    action.resumeretrycount="-1"
    action.resumeinterval = "3"
)
"""

# <!-- Expected mdsd XML config for syslog_basic_json_ext_settings -->
# The below should be actually already in the mdsdConfig.xml.template. This code here is to document the logic
# or for some future extension (like, remove the portions below from mdsdConfig.xml.template, and merge the XML tree
# from the string below, to the main mdsd config XML tree?).
syslog_mdsd_basic_expected_output = """
<MonitoringManagement eventVersion="2" namespace="" timestamp="2014-12-01T20:00:00.000" version="1.0">
  <Schemas>
    <Schema name="syslog">
      <Column mdstype="mt:wstr" name="Ignore" type="str" />
      <Column mdstype="mt:wstr" name="Facility" type="str" />
      <Column mdstype="mt:int32" name="Severity" type="str" />
      <Column mdstype="mt:utc" name="EventTime" type="str-rfc3339" />
      <Column mdstype="mt:wstr" name="SendingHost" type="str" />
      <Column mdstype="mt:wstr" name="Msg" type="str" />
    </Schema>
  </Schemas>
  <Sources>
    <Source name="syslog_basic" schema="syslog" />
  </Sources>

  <Events>
    <MdsdEvents>
      <MdsdEventSource source="syslog_basic">
        <RouteEvent dontUsePerNDayTable="true" eventName="LinuxSyslog" priority="High" />
      </MdsdEventSource>
    </MdsdEvents>
  </Events>
</MonitoringManagement>
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

# Expected omazuremds rsyslog output module config string corresponding to syslog_extended_json_ext_settings
# for rsyslog legacy versions (5/7)
syslog_omazuremds_extended_expected_output_legacy = """
$ModLoad omazuremds.so
$legacymdsdconnections 1
$legacymdsdsocketfile __MDSD_SOCKET_FILE_PATH__

$template fmt_ext_1, "\"syslog_ext_1\",%syslogfacility-text:::csv%,\"%syslogseverity%\",\"%timereported:::date-rfc3339%\",\"%fromhost-ip%\",#TOJSON#%rawmsg%"
$ActionQueueType LinkedList
$ActionQueueDequeueBatchSize 100
$ActionQueueSize 10000
$ActionResumeRetryCount -1
$ActionQueueSaveOnShutdown on
$ActionQueueFileName lad_mdsd_queue_syslog_ext_1
$ActionQueueDiscardSeverity 8
local0.crit :omazuremds:;fmt_ext_1

$template fmt_ext_2, "\"syslog_ext_2\",%syslogfacility-text:::csv%,\"%syslogseverity%\",\"%timereported:::date-rfc3339%\",\"%fromhost-ip%\",#TOJSON#%rawmsg%"
$ActionQueueType LinkedList
$ActionQueueDequeueBatchSize 100
$ActionQueueSize 10000
$ActionResumeRetryCount -1
$ActionQueueSaveOnShutdown on
$ActionQueueFileName lad_mdsd_queue_syslog_ext_2
$ActionQueueDiscardSeverity 8
user.err :omazuremds:;fmt_ext_2
"""

# Expected omazuremds rsyslog output module config string corresponding to syslog_extended_json_ext_settings
# for rsyslog non-legacy version (8)
syslog_omazuremds_extended_expected_output = """
$ModLoad omazuremds

$template fmt_ext_1,"\"syslog_ext_1\",\"%syslogfacility-text:::json%\",\"%syslogseverity%\",\"%timereported:::date-rfc3339%\",\"%fromhost-ip%\",\"%rawmsg:::json%\""
local0.crit action( type="omazuremds"
    template="fmt_ext_1"
    mdsdsocketfile="__MDSD_SOCKET_FILE_PATH__"
    queue.workerthreads="1"
    queue.dequeuebatchsize="16"
    queue.type="fixedarray"
    queue.filename="lad_mdsd_queue_syslog_ext_1"
    queue.highwatermark="400"
    queue.lowwatermark="100"
    queue.discardseverity="8"
    queue.maxdiskspace="5g"
    queue.size="500"
    queue.saveonshutdown="on"
    action.resumeretrycount="-1"
    action.resumeinterval = "3"
)

$template fmt_ext_2,"\"syslog_ext_2\",\"%syslogfacility-text:::json%\",\"%syslogseverity%\",\"%timereported:::date-rfc3339%\",\"%fromhost-ip%\",\"%rawmsg:::json%\""
user.err action( type="omazuremds"
    template="fmt_ext_2"
    mdsdsocketfile="__MDSD_SOCKET_FILE_PATH__"
    queue.workerthreads="1"
    queue.dequeuebatchsize="16"
    queue.type="fixedarray"
    queue.filename="lad_mdsd_queue_syslog_ext_2"
    queue.highwatermark="400"
    queue.lowwatermark="100"
    queue.discardseverity="8"
    queue.maxdiskspace="5g"
    queue.size="500"
    queue.saveonshutdown="on"
    action.resumeretrycount="-1"
    action.resumeinterval = "3"
)
"""

# <!-- Expected mdsd XML config for syslog_extended_json_ext_settings -->
# This resulting XML will need to be merged to the main mdsd config XML that's created from mdsdConfig.xml.template.
syslog_mdsd_extended_expected_output = """
<MonitoringManagement eventVersion="2" namespace="" timestamp="2014-12-01T20:00:00.000" version="1.0">
  <Schemas>
    <Schema name="syslog">
      <Column mdstype="mt:wstr" name="Ignore" type="str" />
      <Column mdstype="mt:wstr" name="Facility" type="str" />
      <Column mdstype="mt:int32" name="Severity" type="str" />
      <Column mdstype="mt:utc" name="EventTime" type="str-rfc3339" />
      <Column mdstype="mt:wstr" name="SendingHost" type="str" />
      <Column mdstype="mt:wstr" name="Msg" type="str" />
    </Schema>
  </Schemas>
  <Sources>
    <Source name="syslog_ext_1" schema="syslog" />
    <Source name="syslog_ext_2" schema="syslog" />
  </Sources>

  <Events>
    <MdsdEvents>
      <MdsdEventSource source="syslog_ext_1">
        <RouteEvent dontUsePerNDayTable="true" eventName="SyslogLocal0CritEvents" priority="High" />
      </MdsdEventSource>
      <MdsdEventSource source="syslog_ext_2">
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

# Expected imfile rsyslog input module config string corresponding to imfile_basic_json_ext_settings
filelogs_imfile_expected_output = """
$ModLoad imfile

$InputFileName /var/log/mydaemonlog1
$InputFileTag ladfile_1
$InputFileFacility local6
$InputFileStateFile syslog-stat-var-log-mydaemonlog1
$InputFileSeverity debug
$InputRunFileMonitor

$InputFileName /var/log/mydaemonlog2
$InputFileTag ladfile_2
$InputFileFacility local6
$InputFileStateFile syslog-stat-var-log-mydaemonlog2
$InputFileSeverity debug
$InputRunFileMonitor

$ModLoad omazuremds.so
$legacymdsdconnections 1
$legacymdsdsocketfile __MDSD_SOCKET_FILE_PATH__

$ActionQueueType LinkedList
$ActionQueueDequeueBatchSize 100
$ActionQueueSize 10000
$ActionResumeRetryCount -1
$ActionQueueSaveOnShutdown on
$ActionQueueFileName lad_mdsd_queue_filelog
$ActionQueueDiscardSeverity 8

$template fmt_file,"\"%syslogtag%\",#TOJSON#%rawmsg%"
local6.* :omazuremds:;fmt_file

& ~
"""

# <!-- Expected mdsd XML config for filelogs_json_ext_settings -->
# This resulting XML will need to be merged to the main mdsd config XML that's created from mdsdConfig.xml.template.
filelogs_mdsd_expected_output = """
<MonitoringManagement eventVersion="2" namespace="" timestamp="2014-12-01T20:00:00.000" version="1.0">
  <Schemas>
    <Schema name="ladfile">
      <Column mdstype="mt:wstr" name="FileTag" type="str" />
      <Column mdstype="mt:wstr" name="Msg" type="str" />
    </Schema>
  </Schemas>
  <Sources>
    <Source name="ladfile_1" schema="ladfile" />
    <Source name="ladfile_2" schema="ladfile" />
  </Sources>

  <Events>
    <MdsdEvents>
      <MdsdEventSource source="ladfile_1">
        <RouteEvent dontUsePerNDayTable="true" eventName="MyDaemon1Events" priority="High" />
      </MdsdEventSource>
      <MdsdEventSource source="ladfile_2">
        <RouteEvent dontUsePerNDayTable="true" eventName="MyDaemon2Events" priority="High" />
      </MdsdEventSource>
    </MdsdEvents>
  </Events>
</MonitoringManagement>
"""


class Lad30RsyslogConfigTest(unittest.TestCase):

    def test_omazuremds_basic(self):
        """
        Tests whether omazuremds and mdsd configs are correctly generated for 'syslogEvents' setting
        (writing to the single 'LinuxSyslog' table). Tests both legacy (rsyslog 5/7) and non-legacy (rsyslog 8).
        :return: None
        """
        syslogEvents = json.loads(syslog_basic_json_ext_settings)
        cfg = RsyslogMdsdConfig(syslogEvents, None, None)
        self.assertEqual(syslog_omazuremds_basic_expected_output_legacy, cfg.get_omazuremds_config(legacy=True))
        self.assertEqual(syslog_omazuremds_basic_expected_output, cfg.get_omazuremds_config(legacy=False))
        self.assertEqual(syslog_mdsd_basic_expected_output, cfg.get_mdsd_syslog_config())

    def test_omazuremds_extended(self):
        """
        Tests whether omazuremds and mdsd configs are correctly generated for 'syslogCfg' setting
        (writing to the specified table for each facility.minSeverity).
        Tests both legacy (rsyslog 5/7) and non-legacy (rsyslog 8).
        :return: None
        """
        syslogCfg = json.loads(syslog_extended_json_ext_settings)
        cfg = RsyslogMdsdConfig(None, syslogCfg, None)
        self.assertEqual(syslog_omazuremds_extended_expected_output_legacy, cfg.get_omazuremds_config(legacy=True))
        self.assertEqual(syslog_omazuremds_extended_expected_output, cfg.get_omazuremds_config(legacy=False))
        self.assertEqual(syslog_mdsd_extended_expected_output, cfg.get_mdsd_syslog_config())

    def test_imfile(self):
        """
        Tests whether imfile and mdsd configs are correctly generated for 'fileLogs' setting
        (writing to the specified table for each monitored).
        :return: None
        """
        fileLogs = json.loads(filelogs_json_ext_settings)
        cfg = RsyslogMdsdConfig(None, None, fileLogs)
        self.assertEqual(filelogs_imfile_expected_output, cfg.get_imfile_config())
        self.assertEqual(filelogs_mdsd_expected_output, cfg.get_mdsd_filelog_config())

    def test_copy_schema_source_mdsdevent_elems(self):
        """
        Tests whether copy_schema_source_mdsdevent_elems() works fine.
        Uses syslog_mdsd_extended_expected_output and filelogs_mdsd_expected_output XML strings
        to test the operation.
        :return:  None
        """
        xml_string_srcs = [syslog_mdsd_extended_expected_output, filelogs_mdsd_expected_output]
        dst_xml_tree = ET.parse('../mdsdConfig.xml.template')
        map(lambda x: copy_schema_source_mdsdevent_elems(dst_xml_tree, x), xml_string_srcs)
        # Just print the output for now (no easy XML comparison)
        print '=== mdsd config XML after combining syslog/filelogs XML configs ==='
        print ET.tostring(dst_xml_tree.getroot())
        print '==================================================================='
        # And verify some elementary properties
        self.assertEqual(2, len(dst_xml_tree.find('Schemas')))  # 2 Schema elements under Schemas
        self.assertEqual(4, len(dst_xml_tree.find('Sources')))  # 4 Source elements under Sources
        self.assertEqual(4, len(dst_xml_tree.find('Events/MdsdEvents')))  # 4 MdsdEventSource elements under Events/MdsdEvents


if __name__ == '__main__':
    unittest.main()
