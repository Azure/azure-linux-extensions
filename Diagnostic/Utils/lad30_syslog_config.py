#!/usr/bin/env python
#
# Azure Linux extension
#
# Copyright (c) Microsoft Corporation
# All rights reserved.
# MIT License
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the ""Software""), to deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit
# persons to whom the Software is furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the
# Software.
# THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
# WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
# OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.


class RsyslogMdsdConfig:
    """
    Utility class for obtaining rsyslog configurations for omazuremds output module and imfile input module
    and corresponding mdsd configurations, based on the LAD 3.0 syslog config schema.
    Diagnostic/README.md will include documentation for the LAD 3.0 syslog config schema.
    """

    def __init__(self, syslogEvents, syslogCfg, fileLogs):
        """
        Constructor to receive/store necessary LAD settings for the desired configuration generation.

        :param syslogEvents: LAD 3.0 "ladCfg" - "syslogEvents" JSON object, or a False object if it's not given
                             in the extension settings. An example is as follows:

                             "ladCfg": {
                                 "syslogEvents" : {
                                     "syslogEventConfiguration": {
                                         "facilityName1": "minSeverity1",
                                         "facilityName2": "minSeverity2"
                                     }
                                 }
                             }

                             Only the JSON object corresponding to "syslogEvents" key should be passed.

                             facilityName1/2 is a syslog facility name (e.g., "LOG_USER", "LOG_LOCAL0").
                             minSeverity1/2 is a syslog severity level (e.g., "LOG_ERR", "LOG_CRIT") or "NONE".
                                 "NONE" means no logs from the facility will be captured (thus it's equivalent to
                                  not specifying the facility at all).

        :param syslogCfg: LAD 3.0 "syslogCfg" JSON object, or a False object if it's not given in the ext settings.
                          This parameter must be a False object if syslogEvents is given as a non-False object.
                          An example is as follows:

                          "syslogCfg": [
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

                          Only the JSON array corresponding to "syslogCfg" key should be passed.

                          "facility" and "minSeverity" are self-explanatory. "table" is for the Azure storage table
                          into which the matching syslog events will be placed.

        :param fileLogs: LAD 3.0 "fileLogs" JSON object, or a False object if it's not given in the ext settings.
                         An example is as follows:

                         "fileLogs": {
                             "fileLogConfiguration": [
                                 {
                                     "file": "/var/log/mydaemonlog",
                                     "table": "MyDaemonEvents"
                                 },
                                 {
                                     "file": "/var/log/myotherdaemonelog",
                                     "table": "MyOtherDaemonEvents"
                                 }
                             ]
                         }

                         Only the JSON array corresponding to "fileLogConfiguration" key should be passed.

                         "file" is the full path of the log file to be watched and captured. "table" is for the
                         Azure storage table into which the lines of the watched file will be placed (one row per line).
        """

        if syslogEvents and syslogCfg:
            raise LadSyslogConfigException("Can't specify both syslogEvents and syslogCfg")

        self._syslogEvents = syslogEvents
        self._syslogCfg = syslogCfg
        self._fileLogs = fileLogs

        try:
            if self._syslogCfg:
                # Convert the 'syslogCfg' JSON object array into a Python dictionary of 'facility;minSeverity' - 'table'
                # E.g., { 'user.err': 'SyslogUserErrorEvents', 'local0.crit': 'SyslogLocal0CritEvent' }
                self._facsev_table_map = dict([('{0}.{1}'.format(syslog_name_to_rsyslog_name(entry['facility']),
                                                                 syslog_name_to_rsyslog_name(entry['minSeverity'])),
                                                entry['table'])
                                               for entry in self._syslogCfg])
            if self._fileLogs:
                # Convert the 'fileLogs' JSON object array into a Python dictionary of 'file' - 'table'
                # E.g., { '/var/log/mydaemonlog1': 'MyDaemon1Events', '/var/log/mydaemonlog2': 'MyDaemon2Events' }
                self._file_table_map = dict([(entry['file'], entry['table']) for entry in self._fileLogs])
            self._omazuremds_legacy_config = self._create_omazuremds_config(legacy=True)
            self._omazuremds_config = self._create_omazuremds_config(legacy=False)
            self._mdsd_syslog_config = self._create_mdsd_syslog_config()
            self._imfile_config = self._create_imfile_config()
            self._mdsd_filelog_config = self._create_mdsd_filelog_config()
        except KeyError as e:
            raise LadSyslogConfigException("Invalid setting name provided (KeyError). Exception msg: {0}".format(e))

    def get_omazuremds_config(self, legacy):
        """
        Get omazuremds rsyslog output module config that corresponds to the syslogEvents or the syslogCfg JSON
        object given in the construction parameters.

        :param legacy: A boolean indicating whether to get omazuremds config for rsyslog 5/7 (legacy rsyslog config)
        :return: omazuremds rsyslog output module config string that should be saved to a file and placed in
                 /etc/rsyslog.d/ directory
        """
        return self._omazuremds_legacy_config if legacy else self._omazuremds_config

    def get_mdsd_syslog_config(self):
        """
        Get mdsd XML config string for the LAD 3.0 syslog config.
        :return: XML string that should be added to the mdsd config XML tree for the LAD 3.0 syslog config.
        """
        return self._mdsd_syslog_config

    def get_imfile_config(self):
        """
        Get imfile rsyslog input module config that corresponds to the fileLogs JSON object given in the construction
        parameters.
        :return: imfile rsyslog input module config string that should be saved to a file and placed in
                 /etc/rsyslog.d/ directory
        """
        return self._imfile_config

    def get_mdsd_filelog_config(self):
        """
        Get mdsd XML config string for the LAD 3.0 filelog config.
        :return: XML string that should be added to the mdsd config XML tree for the LAD 3.0 filelog config.
        """
        return self._mdsd_filelog_config

    def _create_omazuremds_config(self, legacy):
        """
        Create omazure rsyslog output module config for the get method.
        :param legacy: Indicates whether we are creating omazuremds config for rsyslog legacy versions (5/7) or not (8).
        :return: rsyslog omazuremds config string
        """
        return self._create_omazuremds_config_from_basic(legacy) if self._syslogEvents else \
               self._create_omazuremds_config_from_extended(legacy)

    def _create_omazuremds_config_from_basic(self, legacy):
        """
        Create omazure rsyslog output module config from "syslogEvents" setting
        :param legacy: Indicates whether to create for syslog legacy versions (5/7) or not (8).
        :return: rsyslog omazuremds config string
        """
        if 'syslogEventConfiguration' not in self._syslogEvents:
            raise LadSyslogConfigException('Invalid schema for "syslogEvents": No "syslogEventConfiguration"')

        fac_sev_map = self._syslogEvents['syslogEventConfiguration']
        if len(fac_sev_map) == 0:
            return ''

        fac_sev_list = ''
        for facility in sorted(fac_sev_map):
            if fac_sev_list:
                fac_sev_list += ';'
            fac_sev_list += '{0}.{1}'.format(syslog_name_to_rsyslog_name(facility),
                                             syslog_name_to_rsyslog_name(fac_sev_map[facility]))

        omazuremds_basic_config_legacy_template = """
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
<<<FACILITY_SEVERITY_LIST>>> :omazuremds:;fmt_basic
"""
        omazuremds_basic_config_template = """
$ModLoad omazuremds

$template fmt_basic,"\"syslog_basic\",\"%syslogfacility-text:::json%\",\"%syslogseverity%\",\"%timereported:::date-rfc3339%\",\"%fromhost-ip%\",\"%rawmsg:::json%\""
<<<FACILITY_SEVERITY_LIST>>> action( type="omazuremds"
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
        omazuremds_basic_config_string = omazuremds_basic_config_legacy_template if legacy \
            else omazuremds_basic_config_template
        return omazuremds_basic_config_string.replace('<<<FACILITY_SEVERITY_LIST>>>', fac_sev_list)

    def _create_omazuremds_config_from_extended(self, legacy):
        """
        Create omazuremds config string for LAD 3.0 "syslogCfg" (extended) settings.
        :param legacy: Indicates whether to create for syslog legacy versions (5/7) or not (8).
        :return: rsyslog omazuremds config string
        """

        if not self._syslogCfg:
            return ''

        # Start creating omazuremds config
        omazuremds_extended_config = """
$ModLoad omazuremds.so
$legacymdsdconnections 1
$legacymdsdsocketfile __MDSD_SOCKET_FILE_PATH__
""" if legacy else """
$ModLoad omazuremds
"""
        omazuremds_per_table_template = """
$template fmt_ext_<<<INDEX>>>, "\"syslog_ext_<<<INDEX>>>\",%syslogfacility-text:::csv%,\"%syslogseverity%\",\"%timereported:::date-rfc3339%\",\"%fromhost-ip%\",#TOJSON#%rawmsg%"
$ActionQueueType LinkedList
$ActionQueueDequeueBatchSize 100
$ActionQueueSize 10000
$ActionResumeRetryCount -1
$ActionQueueSaveOnShutdown on
$ActionQueueFileName lad_mdsd_queue_syslog_ext_<<<INDEX>>>
$ActionQueueDiscardSeverity 8
<<<FACILITY_SEVERITY>>> :omazuremds:;fmt_ext_<<<INDEX>>>
""" if legacy else """
$template fmt_ext_<<<INDEX>>>,"\"syslog_ext_<<<INDEX>>>\",\"%syslogfacility-text:::json%\",\"%syslogseverity%\",\"%timereported:::date-rfc3339%\",\"%fromhost-ip%\",\"%rawmsg:::json%\""
<<<FACILITY_SEVERITY>>> action( type="omazuremds"
    template="fmt_ext_<<<INDEX>>>"
    mdsdsocketfile="__MDSD_SOCKET_FILE_PATH__"
    queue.workerthreads="1"
    queue.dequeuebatchsize="16"
    queue.type="fixedarray"
    queue.filename="lad_mdsd_queue_syslog_ext_<<<INDEX>>>"
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
        index = 0
        for entry in sorted(self._facsev_table_map):
            index += 1
            omazuremds_extended_config += omazuremds_per_table_template.replace("<<<INDEX>>>", str(index))\
                                                                       .replace("<<<FACILITY_SEVERITY>>>", entry)
        return omazuremds_extended_config

    def _create_mdsd_syslog_config(self):
        """
        Create mdsd XML config string for LAD 3.0 syslog settings.
        :return: mdsd XML config string (may need to be merged to the main mdsd config XML tree)
        """
        return self._create_mdsd_syslog_basic_config() if self._syslogEvents else self._create_mdsd_syslog_extended_config()

    def _create_mdsd_syslog_basic_config(self):
        """
        Create mdsd XML config string for basic syslog config ("syslogEvents")
        :return: mdsd XML config string (may need to be merged to the main mdsd config XML tree)
        """
        return """
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
    def _create_mdsd_syslog_extended_config(self):
        """
        Create mdsd XML config string for extended syslog config ("syslogCfg")
        :return: mdsd XML config string (may need to be merged to the main mdsd config XML tree)
        """
        if not self._syslogCfg:
            return ''

        syslog_mdsd_config = """
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
{0}  </Sources>

  <Events>
    <MdsdEvents>
{1}    </MdsdEvents>
  </Events>
</MonitoringManagement>
"""
        per_table_source_template = """    <Source name="syslog_ext_{0}" schema="syslog" />
"""
        per_table_mdsd_event_source_template = """      <MdsdEventSource source="syslog_ext_{0}">
        <RouteEvent dontUsePerNDayTable="true" eventName="{1}" priority="High" />
      </MdsdEventSource>
"""
        syslog_sources = ''
        syslog_mdsd_event_sources = ''
        index = 0
        for facsev_key in sorted(self._facsev_table_map):
            index += 1
            syslog_sources += per_table_source_template.format(index)
            syslog_mdsd_event_sources += per_table_mdsd_event_source_template.format(index, self._facsev_table_map[facsev_key])

        return syslog_mdsd_config.format(syslog_sources, syslog_mdsd_event_sources)

    def _create_imfile_config(self):
        """
        Create imfile rsyslog input module config for the get method.
        :return: rsyslog imfile config string
        """
        if not self._fileLogs:
            return ''
        imfile_config_template = """
$ModLoad imfile
{0}
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
        per_file_template = """
$InputFileName {0}
$InputFileTag ladfile_{1}
$InputFileFacility local6
$InputFileStateFile syslog-stat{2}
$InputFileSeverity debug
$InputRunFileMonitor
"""
        all_files_config = ''
        index = 0
        for file_key in self._file_table_map:
            index += 1
            all_files_config += per_file_template.format(file_key, index, file_key.replace('/', '-'))

        return imfile_config_template.format(all_files_config)

    def _create_mdsd_filelog_config(self):
        """
        Create mdsd XML config string for LAD 3.0 filelog settings.
        :return: mdsd XML config string (may need to be merged to the main mdsd config XML tree)
        """
        if not self._fileLogs:
            return ''

        filelogs_mdsd_config = """
<MonitoringManagement eventVersion="2" namespace="" timestamp="2014-12-01T20:00:00.000" version="1.0">
  <Schemas>
    <Schema name="ladfile">
      <Column mdstype="mt:wstr" name="FileTag" type="str" />
      <Column mdstype="mt:wstr" name="Msg" type="str" />
    </Schema>
  </Schemas>
  <Sources>
{0}  </Sources>

  <Events>
    <MdsdEvents>
{1}    </MdsdEvents>
  </Events>
</MonitoringManagement>
"""
        per_file_source_template = """    <Source name="ladfile_{0}" schema="ladfile" />
"""
        per_file_mdsd_event_source_template = """      <MdsdEventSource source="ladfile_{0}">
        <RouteEvent dontUsePerNDayTable="true" eventName="{1}" priority="High" />
      </MdsdEventSource>
"""
        filelogs_sources = ''
        filelogs_mdsd_event_sources = ''
        index = 0
        for file_key in sorted(self._file_table_map):
            index += 1
            filelogs_sources += per_file_source_template.format(index)
            filelogs_mdsd_event_sources += per_file_mdsd_event_source_template.format(index,
                                                                                      self._file_table_map[file_key])

        return filelogs_mdsd_config.format(filelogs_sources, filelogs_mdsd_event_sources)


syslog_name_to_rsyslog_name_map = {
    # facilities
    'LOG_AUTH': 'auth',
    'LOG_AUTHPRIV': 'authpriv',
    'LOG_CRON': 'cron',
    'LOG_DAEMON': 'daemon',
    'LOG_FTP': 'ftp',
    'LOG_KERN': 'kern',
    'LOG_LOCAL0': 'local0',
    'LOG_LOCAL1': 'local1',
    'LOG_LOCAL2': 'local2',
    'LOG_LOCAL3': 'local3',
    'LOG_LOCAL4': 'local4',
    'LOG_LOCAL5': 'local5',
    'LOG_LOCAL6': 'local6',
    'LOG_LOCAL7': 'local7',
    'LOG_LPR': 'lpr',
    'LOG_MAIL': 'mail',
    'LOG_NEWS': 'news',
    'LOG_SYSLOG': 'syslog',
    'LOG_USER': 'user',
    'LOG_UUCP': 'uucp',
    # severities
    'LOG_EMERG': 'emerg',
    'LOG_ALERT': 'alert',
    'LOG_CRIT': 'crit',
    'LOG_ERR': 'err',
    'LOG_WARNING': 'warning',
    'LOG_NOTICE': 'notice',
    'LOG_INFO': 'info',
    'LOG_DEBUG': 'debug'
}


def syslog_name_to_rsyslog_name(syslog_name):
    """
    Convert a syslog name (e.g., "LOG_USER") to the corresponding rsyslog name (e.g., "user")
    :param syslog_name: A syslog name for a facility (e.g., "LOG_USER") or a severity (e.g., "LOG_ERR")
    :return: Corresponding rsyslog name (e.g., "user" or "error")
    """
    if syslog_name not in syslog_name_to_rsyslog_name_map:
        raise LadSyslogConfigException('Invalid syslog name given: {0}'.format(syslog_name))
    return syslog_name_to_rsyslog_name_map[syslog_name]


class LadSyslogConfigException(Exception):
    """
    Custom exception class for LAD syslog config errors
    """
    pass
