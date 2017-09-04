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

from xml.etree import ElementTree as ET

import Utils.LadDiagnosticUtil as LadUtil
from Utils.lad_exceptions import LadLoggingConfigException
import Utils.mdsd_xml_templates as mxt
from Utils.omsagent_util import get_syslog_ng_src_name


syslog_src_name = 'mdsd.syslog'


class LadLoggingConfig:
    """
    Utility class for obtaining syslog (rsyslog or syslog-ng) configurations for use with fluentd
    (currently omsagent), and corresponding omsagent & mdsd configurations, based on the LAD 3.0
    syslog config schema. This class also generates omsagent (fluentd) config for LAD 3.0's fileLogs settings
    (using the fluentd tail plugin).
    """

    def __init__(self, syslogEvents, fileLogs, sinksConfig, pkey_path, cert_path, encrypt_secret):
        """
        Constructor to receive/store necessary LAD settings for the desired configuration generation.

        :param dict syslogEvents: LAD 3.0 "ladCfg" - "syslogEvents" JSON object, or a False object if it's not given
                             in the extension settings. An example is as follows:

                             "ladCfg": {
                                 "syslogEvents" : {
                                     "sinks": "SyslogSinkName0",
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

        :param dict fileLogs: LAD 3.0 "fileLogs" JSON object, or a False object if it's not given in the ext settings.
                         An example is as follows:

                         "fileLogs": {
                             "fileLogConfiguration": [
                                 {
                                     "file": "/var/log/mydaemonlog",
                                     "table": "MyDaemonEvents",
                                     "sinks": "FilelogSinkName1",
                                 },
                                 {
                                     "file": "/var/log/myotherdaemonelog",
                                     "table": "MyOtherDaemonEvents",
                                     "sinks": "FilelogSinkName2"
                                 }
                             ]
                         }

                         Only the JSON array corresponding to "fileLogConfiguration" key should be passed.

                         "file" is the full path of the log file to be watched and captured. "table" is for the
                         Azure storage table into which the lines of the watched file will be placed (one row per line).
        :param LadUtil.SinkConfiguration sinksConfig:  SinkConfiguration object that's created out of "sinksConfig"
                    LAD 3.0 JSON setting. Refer to LadUtil.SinkConfiguraiton documentation.
        :param str pkey_path: Path to the VM's private key that should be passed to mdsd XML for decrypting encrypted
                    secrets (EH SAS URL)
        :param str cert_path: Path to the VM's certificate that should be used to encrypt secrets (EH SAS URL)
        :param encrypt_secret: Function to encrypt a secret (string, 2nd param) with the provided cert path param (1st)
        """
        self._syslogEvents = syslogEvents
        self._fileLogs = fileLogs
        self._sinksConfig = sinksConfig
        self._pkey_path = pkey_path
        self._cert_path = cert_path
        self._encrypt_secret = encrypt_secret
        self._fac_sev_map = None

        try:
            # Create facility-severity map. E.g.: { "LOG_USER" : "LOG_ERR", "LOG_LOCAL0", "LOG_CRIT" }
            if self._syslogEvents:
                self._fac_sev_map = self._syslogEvents['syslogEventConfiguration']
            self._syslog_disabled = not self._fac_sev_map  # A convenience predicate

            if self._fileLogs:
                # Convert the 'fileLogs' JSON object array into a Python dictionary of 'file' - 'table'
                # E.g., [{ 'file': '/var/log/mydaemonlog1', 'table': 'MyDaemon1Events', 'sinks': 'File1Sink'},
                #        { 'file': '/var/log/mydaemonlog2', 'table': 'MyDaemon2Events', 'sinks': 'File2SinkA,File2SinkB'}]
                self._file_table_map = dict([(entry['file'], entry['table'] if 'table' in entry else '')
                                             for entry in self._fileLogs])
                self._file_sinks_map = dict([(entry['file'], entry['sinks'] if 'sinks' in entry else '')
                                             for entry in self._fileLogs])

            self._rsyslog_config = None
            self._syslog_ng_config = None
            self._mdsd_syslog_config = None
            self._mdsd_filelog_config = None
        except KeyError as e:
            raise LadLoggingConfigException("Invalid setting name provided (KeyError). Exception msg: {0}".format(e))

    def get_rsyslog_config(self):
        """
        Returns rsyslog config (for use with omsagent) that corresponds to the syslogEvents or the syslogCfg
        JSON object given in the construction parameters.

        :rtype: str
        :return: rsyslog config string that should be appended to /etc/rsyslog.d/95-omsagent.conf (new rsyslog)
                 or to /etc/rsyslog.conf (old rsyslog)
        """
        if not self._rsyslog_config:
            if self._syslog_disabled:
                self._rsyslog_config = ''
            else:
                # Generate/save/return rsyslog config string for the facility-severity pairs.
                # E.g.: "user.err @127.0.0.1:%SYSLOG_PORT%\nlocal0.crit @127.0.0.1:%SYSLOG_PORT%\n'
                self._rsyslog_config = \
                    '\n'.join('{0}.{1}  @127.0.0.1:%SYSLOG_PORT%'.format(syslog_name_to_rsyslog_name(fac),
                                                                         syslog_name_to_rsyslog_name(sev))
                              for fac, sev in self._fac_sev_map.iteritems()) + '\n'
        return self._rsyslog_config

    def get_syslog_ng_config(self):
        """
        Returns syslog-ng config (for use with omsagent) that corresponds to the syslogEvents or the syslogCfg
        JSON object given in the construction parameters.

        :rtype: str
        :return: syslog-ng config string that should be appended to /etc/syslog-ng/syslog-ng.conf
        """
        if not self._syslog_ng_config:
            if self._syslog_disabled:
                self._syslog_ng_config = ''
            else:
                # Generate/save/return syslog-ng config string for the facility-severity pairs.
                # E.g.: "log { source(src); filter(f_LAD_oms_f_user); filter(f_LAD_oms_ml_err); destination(d_LAD_oms); };\nlog { source(src); filter(f_LAD_oms_f_local0); filter(f_LAD_oms_ml_crit); destination(d_LAD_oms); };\n"
                self._syslog_ng_config = \
                    '\n'.join('log {{ source({0}); filter(f_LAD_oms_f_{1}); filter(f_LAD_oms_ml_{2}); '
                              'destination(d_LAD_oms); }};'.format(get_syslog_ng_src_name(),
                                                                   syslog_name_to_rsyslog_name(fac),
                                                                   syslog_name_to_rsyslog_name(sev))
                              for fac, sev in self._fac_sev_map.iteritems()) + '\n'
        return self._syslog_ng_config

    def get_mdsd_syslog_config(self):
        """
        Get mdsd XML config string for syslog use with omsagent in LAD 3.0.
        :rtype: str
        :return: XML string that should be added to the mdsd config XML tree for syslog use with omsagent in LAD 3.0.
        """
        if not self._mdsd_syslog_config:
            self._mdsd_syslog_config = self.__generate_mdsd_syslog_config()
        return self._mdsd_syslog_config

    def __generate_mdsd_syslog_config(self):
        """
        Helper method to generate oms_mdsd_syslog_config
        """
        if self._syslog_disabled:
            return ''

        # For basic syslog conf (single dest table): Source name is unified as 'mdsd.syslog' and
        # dest table (eventName) is 'LinuxSyslog'. This is currently the only supported syslog conf scheme.
        syslog_routeevents = mxt.per_RouteEvent_tmpl.format(event_name='LinuxSyslog', opt_store_type='')
        # Add RouteEvent elements for specified "sinks" for "syslogEvents" feature
        # Also add EventStreamingAnnotation for EventHub sinks
        syslog_eh_urls = ''
        for sink_name in LadUtil.getSinkList(self._syslogEvents):
            if sink_name == 'LinuxSyslog':
                raise LadLoggingConfigException("'LinuxSyslog' can't be used as a sink name. "
                    "It's reserved for default Azure Table name for syslog events.")
            routeevent, eh_url = self.__generate_routeevent_and_eh_url_for_extra_sink(sink_name,
                                                                                      syslog_src_name)
            syslog_routeevents += routeevent
            syslog_eh_urls += eh_url

        mdsd_event_source = ''
        if syslog_routeevents:  # Do not add MdsdEventSource element if there's no associated RouteEvent generated.
            mdsd_event_source = mxt.per_MdsdEventSource_tmpl.format(source=syslog_src_name,
                                                                    routeevents=syslog_routeevents)

        return mxt.top_level_tmpl_for_logging_only.format(
            sources=mxt.per_source_tmpl.format(name=syslog_src_name), events=mdsd_event_source, eh_urls=syslog_eh_urls)

    def __generate_routeevent_and_eh_url_for_extra_sink(self, sink_name, src_name):
        """
        Helper method to generate one RouteEvent element for each extra sink given.
        Also generates an EventStreamingAnnotation element for EventHub sinks.
        :param str sink_name: The name of the sink for the RouteEvent.
        :param str src_name: The name of the ingested source that should be used for EventStreamingAnnotation.
        :rtype str,str:
        :return: A pair of the XML RouteEvent element string for the sink and the EventHubStreamingAnnotation
                 XML string.
        """
        sink = self._sinksConfig.get_sink_by_name(sink_name)
        if not sink:
            raise LadLoggingConfigException('Sink name "{0}" is not defined in sinksConfig'.format(sink_name))
        sink_type = sink['type']
        if not sink_type:
            raise LadLoggingConfigException('Sink type for sink "{0}" is not defined in sinksConfig'.format(sink_name))
        if sink_type == 'JsonBlob':
            return mxt.per_RouteEvent_tmpl.format(event_name=sink_name,
                                                  opt_store_type='storeType="JsonBlob"'),\
                   ''  # No EventStreamingAnnotation for JsonBlob
        elif sink_type == 'EventHub':
            if 'sasURL' not in sink:
                raise LadLoggingConfigException('sasURL is not specified for EventHub sink_name={0}'.format(sink_name))
            # For syslog/filelogs (ingested events), the source name should be used for EventStreamingAnnotation name.
            eh_url = mxt.per_eh_url_tmpl.format(eh_name=src_name, key_path=self._pkey_path,
                                                enc_eh_url=self._encrypt_secret(self._cert_path, sink['sasURL']))
            return '', eh_url  # No RouteEvent for logging event's EventHub sink
        else:
            raise LadLoggingConfigException('{0} sink type (for sink_name={1}) is not supported'.format(sink_type,
                                                                                                        sink_name))

    def get_mdsd_filelog_config(self):
        """
        Get mdsd XML config string for filelog (tail) use with omsagent in LAD 3.0.
        :rtype: str
        :return: XML string that should be added to the mdsd config XML tree for filelog use with omsagent in LAD 3.0.
        """
        if not self._mdsd_filelog_config:
            self._mdsd_filelog_config = self.__generate_mdsd_filelog_config()
        return self._mdsd_filelog_config

    def __generate_mdsd_filelog_config(self):
        """
        Helper method to generate oms_mdsd_filelog_config
        """
        if not self._fileLogs:
            return ''

        # Per-file source name is 'mdsd.filelog<.path.to.file>' where '<.path.to.file>' is a full path
        # with all '/' replaced by '.'.
        filelogs_sources = ''
        filelogs_mdsd_event_sources = ''
        filelogs_eh_urls = ''
        for file_key in sorted(self._file_table_map):
            if not self._file_table_map[file_key] and not self._file_sinks_map[file_key]:
                raise LadLoggingConfigException('Neither "table" nor "sinks" defined for file "{0}"'.format(file_key))
            source_name = 'mdsd.filelog{0}'.format(file_key.replace('/', '.'))
            filelogs_sources += mxt.per_source_tmpl.format(name=source_name)
            per_file_routeevents = ''
            if self._file_table_map[file_key]:
                per_file_routeevents += mxt.per_RouteEvent_tmpl.format(event_name=self._file_table_map[file_key], opt_store_type='')
            if self._file_sinks_map[file_key]:
                for sink_name in self._file_sinks_map[file_key].split(','):
                    routeevent, eh_url = self.__generate_routeevent_and_eh_url_for_extra_sink(sink_name, source_name)
                    per_file_routeevents += routeevent
                    filelogs_eh_urls += eh_url
            if per_file_routeevents:  # Do not add MdsdEventSource element if there's no associated RouteEvent generated.
                filelogs_mdsd_event_sources += \
                    mxt.per_MdsdEventSource_tmpl.format(source=source_name, routeevents=per_file_routeevents)
        return mxt.top_level_tmpl_for_logging_only.format(sources=filelogs_sources, events=filelogs_mdsd_event_sources,
                                                      eh_urls=filelogs_eh_urls)

    def get_fluentd_syslog_src_config(self):
        """
        Get Fluentd's syslog source config that should be used for this LAD's syslog configs.
        :rtype: str
        :return: Fluentd config string that should be overwritten to
                 /etc/opt/microsoft/omsagent/LAD/conf/omsagent.d/syslog.conf
                 (after replacing '%SYSLOG_PORT%' with the assigned/picked port number)
        """
        fluentd_syslog_src_config = """
<source>
  type syslog
  port %SYSLOG_PORT%
  bind 127.0.0.1
  protocol_type udp
  include_source_host true
  tag mdsd.syslog
</source>

# Generate fields expected for existing mdsd syslog collection schema.
<filter mdsd.syslog.**>
  type record_transformer
  enable_ruby
  <record>
    # Fields for backward compatibility with Azure Shoebox V1 (Table storage)
    Ignore "syslog"
    Facility ${tag_parts[2]}
    Severity ${tag_parts[3]}
    EventTime ${time.strftime('%Y-%m-%dT%H:%M:%S%z')}
    SendingHost ${record["source_host"]}
    Msg ${record["message"]}
    # Rename 'host' key, as mdsd will add 'Host' for Azure Table and it'll be confusing
    hostname ${record["host"]}
  </record>
  remove_keys host,message,source_host  # Renamed (duplicated) fields, so just remove
</filter>
"""
        return '' if self._syslog_disabled else fluentd_syslog_src_config

    def get_fluentd_filelog_src_config(self):
        """
        Get Fluentd's filelog (tail) source config that should be used for this LAD's fileLogs settings.
        :rtype: str
        :return: Fluentd config string that should be overwritten to
                 /etc/opt/microsoft/omsagent/LAD/conf/omsagent.d/file.conf
        """
        if not self._fileLogs:
            return ''

        fluentd_tail_src_config_template = """
# For all monitored files
<source>
  @type tail
  path {file_paths}
  pos_file /var/opt/microsoft/omsagent/LAD/tmp/filelogs.pos
  tag mdsd.filelog.*
  format none
  message_key Msg  # LAD uses "Msg" as the field name
</source>

# Add FileTag field (existing LAD behavior)
<filter mdsd.filelog.**>
  @type record_transformer
  <record>
    FileTag ${{tag_suffix[2]}}
  </record>
</filter>
"""
        return fluentd_tail_src_config_template.format(file_paths=','.join(self._file_table_map.keys()))

    def get_fluentd_out_mdsd_config(self):
        """
        Get Fluentd's out_mdsd output config that should be used for LAD.
        TODO This is not really syslog-specific, so should be moved outside from here.
        :rtype: str
        :return: Fluentd config string that should be overwritten to
                 /etc/opt/microsoft/omsagent/LAD/conf/omsagent.d/z_out_mdsd.conf
        """
        fluentd_out_mdsd_config_template = """
# Output to mdsd
<match mdsd.**>
    type mdsd
    log_level warn
    djsonsocket /var/run/mdsd/lad_mdsd_djson.socket  # Full path to mdsd dynamic json socket file
    acktimeoutms 5000  # max time in milli-seconds to wait for mdsd acknowledge response. If 0, no wait.
{tag_regex_cfg_line}    num_threads 1
    buffer_chunk_limit 1000k
    buffer_type file
    buffer_path /var/opt/microsoft/omsagent/state/out_mdsd*.buffer
    buffer_queue_limit 128
    flush_interval 10s
    retry_limit 3
    retry_wait 10s
</match>
"""
        tag_regex_cfg_line = '' if self._syslog_disabled \
            else r"""    mdsd_tag_regex_patterns [ "^mdsd\\.syslog" ] # fluentd tag patterns whose match will be used as mdsd source name
"""
        return fluentd_out_mdsd_config_template.format(tag_regex_cfg_line=tag_regex_cfg_line)


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
    :param str syslog_name: A syslog name for a facility (e.g., "LOG_USER") or a severity (e.g., "LOG_ERR")
    :rtype: str
    :return: Corresponding rsyslog name (e.g., "user" or "error")
    """
    if syslog_name == '*':
        # We accept '*' as a facility name (also as a severity name, though it's not required)
        # to allow customers to collect for reserved syslog facility numeric IDs (12-15)
        return '*'
    if syslog_name not in syslog_name_to_rsyslog_name_map:
        raise LadLoggingConfigException('Invalid syslog name given: {0}'.format(syslog_name))
    return syslog_name_to_rsyslog_name_map[syslog_name]


def copy_sub_elems(dst_xml, src_xml, path):
    """
    Copy sub-elements of src_elem (XML) to dst_elem.
    :param xml.etree.ElementTree.ElementTree dst_xml: Python xml tree object to which sub-elements will be copied.
    :param xml.etree.ElementTree.ElementTree src_xml: Python xml tree object from which sub-elements will be copied.
    :param str path: The path of the element whose sub-elements will be copied.
    :return: None. dst_xml will be updated with copied sub-elements
    """
    dst_elem = dst_xml.find(path)
    src_elem = src_xml.find(path)
    if src_elem is None:
        return
    for sub_elem in src_elem:
        dst_elem.append(sub_elem)


def copy_source_mdsdevent_eh_url_elems(mdsd_xml_tree, mdsd_logging_xml_string):
    """
    Copy MonitoringManagement/Schemas/Schema, MonitoringManagement/Sources/Source,
    MonitoringManagement/Events/MdsdEvents/MdsdEventSource elements, and MonitoringManagement/EventStreamingAnnotations
    /EventStreamingAnnontation elements from mdsd_rsyslog_xml_string to mdsd_xml_tree.
    Used to actually add generated rsyslog mdsd config XML elements to the mdsd config XML tree.

    :param xml.etree.ElementTree.ElementTree mdsd_xml_tree: Python xml.etree.ElementTree object that's generated from mdsd config XML template
    :param str mdsd_logging_xml_string: XML string containing the generated logging (syslog/filelog) mdsd config XML elements.
            See oms_syslog_mdsd_*_expected_xpaths member variables in test_lad_logging_config.py for examples in XPATHS format.
    :return: None. mdsd_xml_tree object will contain the added elements.
    """
    if not mdsd_logging_xml_string:
        return

    mdsd_logging_xml_tree = ET.ElementTree(ET.fromstring(mdsd_logging_xml_string))

    # Copy Source elements (sub-elements of Sources element)
    copy_sub_elems(mdsd_xml_tree, mdsd_logging_xml_tree, 'Sources')

    # Copy MdsdEventSource elements (sub-elements of Events/MdsdEvents element)
    copy_sub_elems(mdsd_xml_tree, mdsd_logging_xml_tree, 'Events/MdsdEvents')

    # Copy EventStreamingAnnotation elements (sub-elements of EventStreamingAnnotations element)
    copy_sub_elems(mdsd_xml_tree, mdsd_logging_xml_tree, 'EventStreamingAnnotations')
