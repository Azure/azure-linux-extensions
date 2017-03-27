#!/usr/bin/env python
#
# Azure Linux extension
#
# Linux Azure Diagnostic Extension (Current version is specified in manifest.xml)
# Copyright (c) Microsoft Corporation
# All rights reserved.
# MIT License
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
#  documentation files (the ""Software""), to deal in the Software without restriction, including without limitation
#  the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
#  permit persons to whom the Software is furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the
#  Software.
# THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
#  WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS
#  OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
#  OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import binascii
from misc_helpers import read_uuid, get_storage_endpoint_with_account, escape_nonalphanumerics, write_string_to_file
import os.path
import traceback
import xml.etree.ElementTree as ET
import Utils.ApplicationInsightsUtil as AIUtil
import Utils.LadDiagnosticUtil as LadUtil
import Utils.XmlUtil as XmlUtil
from Utils.lad30_syslog_config import RsyslogMdsdConfig, copy_schema_source_mdsdevent_elems
import Providers.Builtin as BuiltIn


class ConfigMdsdRsyslog:
    """
    A class to generate mdsd XML config file and rsyslog imfile config file, based on the Json extension settings.
    The mdsd XML config file generated will be /var/lib/waagent/Microsoft. ...-x.y.zzzz/xmlCfg.xml (hard-coded).
    The rsyslog imfile config file generated will be /var/lib/waagent/Microsoft. ...-x.y.zzzz/imfileconfig
       (the filename part is configurable as a constructor param).
    """

    def __init__(self, ext_settings, ext_dir, waagent_dir, deployment_id,
                 imfile_config_filename, run_command, logger_log, logger_error):
        """
        Constructor.
        :param ext_settings: A LadExtSettings (in Utils/lad_ext_settings.py) obj wrapping the Json extension settings.
        :param ext_dir: Extension directory (e.g., /var/lib/waagent/Microsoft.OSTCExtensions.LinuxDiagnostic-2.3.xxxx)
        :param waagent_dir: WAAgent directory (e.g., /var/lib/waagent)
        :param deployment_id: Deployment ID string (or None) that should be obtained & passed by the caller
                              from waagent's HostingEnvironmentCfg.xml.
        :param imfile_config_filename: Rsyslog imfile module configuration file name (that will be copied
                                       to the rsyslog config directory). This could be hard-coded and later removed.
                                       Currently '/var/lib/waagent/Microsoft...-2.3.xxxx/imfileconfig' is passed.
        :param run_command: External command execution function (e.g., RunGetOutput)
        :param logger_log: Normal logging function (e.g., hutil.log) that takes only one param for the logged msg.
        :param logger_error: Error logging function (e.g., hutil.error) that takes only one param for the logged msg.
        """
        self._ext_settings = ext_settings
        self._ext_dir = ext_dir
        self._waagent_dir = waagent_dir
        self._deployment_id = deployment_id
        self._imfile_config_filename = imfile_config_filename
        self._run_command = run_command
        self._logger_log = logger_log
        self._logger_error = logger_error

        # This should be assigned in the main API function from an mdsd XML cfg template file.
        # TODO Consider doing that right away from here. For now, just keeping the existing behavior/logic.
        self._mdsd_config_xml_tree = None

    def _add_portal_settings(self, resource_id):
        """
        Update mdsd_config_xml_tree for Azure Portal metric collection setting.
        It's basically applying the resource_id as the partitionKey attribute of LADQuery elements.

        :param resource_id: ARM resource ID to provide as partitionKey in LADQuery elements
        :return: None
        """
        assert self._mdsd_config_xml_tree is not None

        portal_config = ET.parse(os.path.join(self._ext_dir, 'portal.xml.template'))
        XmlUtil.setXmlValue(portal_config, './DerivedEvents/DerivedEvent/LADQuery', 'partitionKey', resource_id)
        root = portal_config.getroot()
        XmlUtil.addElement(self._mdsd_config_xml_tree, 'Events', root.getchildren()[0])
        XmlUtil.addElement(self._mdsd_config_xml_tree, 'Events', root.getchildren()[1])

    def _update_metric_collection_settings(self, ladCfg):
        """
        Update mdsd_config_xml_tree for Azure Portal metric collection. The mdsdCfg performanceCounters element contains
        an array of metric definitions; this method passes each definition to its provider's AddMetric method, which is
        responsible for configuring the provider to deliver the metric to mdsd and for updating the mdsd config as
        required to expect the metric to arrive. This method also builds the necessary aggregation queries (from the
        metrics.metricAggregation array) that grind the ingested data and push it to the WADmetric table.
        :param ladCfg: ladCfg object from extension config
        :return: None
        """
        assert self._mdsd_config_xml_tree is not None
        metrics = LadUtil.getPerformanceCounterCfgFromLadCfg(ladCfg)
        counter_to_table = {}
        local_tables = set()

        # Add each metric
        for metric in metrics:
            if metric['class'] is 'builtin':
                local_table_name = BuiltIn.AddMetric(metric)
                if local_table_name:
                    local_tables.add(local_table_name)
                    counter_to_table[metric['counterSpecifier']] = local_table_name

        # Finalize; update the mdsd config to be prepared to receive the metrics
        BuiltIn.UpdateXML(self._mdsd_config_xml_tree)

        # Pump the received data from the local tables to the desired sinks. The "WADmetrics" shoebox table sink is
        # always served; after that, check for other sinks and handle appropriately. The partitionKey is filled in
        # later.
        ladquery = '''
<DerivedEvent  duration="{interval}" eventName="WADMetrics{interval}P10DV2S" isFullName="true" source="{localtable}">
<LADQuery columnName="CounterName" columnValue="Value" partitionKey="" />
</DerivedEvent>
        '''
        intervals = LadUtil.getAggregationPeriodsFromLadCfg(ladCfg)
        for table_name in local_tables:
            for aggregation_interval in intervals:
                query = ladquery.format(interval=aggregation_interval, localTable=table_name)
                XmlUtil.addElement(self._mdsd_config_xml_tree, 'DerivedEvents', ET.fromstring(query))
        # Other sinks are handled here
            sinks = LadUtil.getTopLevelSinksFromLadCfg(ladCfg)
            if "eventhub" in sinks:
                eh_sink = LadUtil.getSinkDefinitionFromLadCfg(ladCfg, "eventhub")
                # Generate a <DerivedEvent> to extract data (raw or aggregated) and send it to EH

    def _update_and_get_file_monitoring_settings(self, files):
        """
        Update mdsd config's file monitoring config. Also creates/returns rsyslog imfile config.
        All the operations are based on the input param files, which is a Json-deserialized dictionary
        corresponding the following Json array example:
        [
            {"file":"/var/log/a.log", "table":"aLog"},
            {"file":"/var/log/b.log", "table":"bLog"}
        ]
        :param files: Array of dictionaries deserialized from the 'fileCfg' Json config (example as above)
        :return: rsyslog omfile module config file content
        """
        assert self._mdsd_config_xml_tree is not None

        if not files:
            return ''

        file_id = 0
        imfile_config = """
$ModLoad imfile

"""

        mdsd_event_source_schema = """
<MdsdEventSource source="ladfile">
    <RouteEvent dontUsePerNDayTable="true" eventName="" priority="High"/>
</MdsdEventSource>
"""

        mdsd_source_schema = """
<Source name="ladfile1" schema="ladfile" />
"""
        imfile_per_file_config_template = """
$InputFileName #FILE#
$InputFileTag #FILETAG#
$InputFileFacility local6
$InputFileStateFile syslog-stat#STATFILE#
$InputFileSeverity debug
$InputRunFileMonitor
"""

        for item in files:
            file_id += 1
            mdsd_event_source_element = XmlUtil.createElement(mdsd_event_source_schema)
            XmlUtil.setXmlValue(mdsd_event_source_element, 'RouteEvent', 'eventName', item["table"])
            mdsd_event_source_element.set('source', 'ladfile'+str(file_id))
            XmlUtil.addElement(self._mdsd_config_xml_tree, 'Events/MdsdEvents', mdsd_event_source_element)

            mdsd_source_element = XmlUtil.createElement(mdsd_source_schema)
            mdsd_source_element.set('name', 'ladfile'+str(file_id))
            XmlUtil.addElement(self._mdsd_config_xml_tree, 'Sources', mdsd_source_element)

            imfile_per_file_config = imfile_per_file_config_template.replace('#FILE#', item['file'])
            imfile_per_file_config = imfile_per_file_config.replace('#STATFILE#', item['file'].replace("/", "-"))
            imfile_per_file_config = imfile_per_file_config.replace('#FILETAG#', 'ladfile'+str(file_id))
            imfile_config += imfile_per_file_config
        return imfile_config

    def _update_perf_counters_settings(self, omi_queries, for_app_insights=False):
        """
        Update the mdsd XML tree with the OMI queries provided.
        :param omi_queries: List of dictionaries specifying OMI queries and destination tables. E.g.:
         [
             {"query":"SELECT PercentAvailableMemory, AvailableMemory, UsedMemory, PercentUsedSwap FROM SCX_MemoryStatisticalInformation","table":"LinuxMemory"},
             {"query":"SELECT PercentProcessorTime, PercentIOWaitTime, PercentIdleTime FROM SCX_ProcessorStatisticalInformation WHERE Name='_TOTAL'","table":"LinuxCpu"},
             {"query":"SELECT AverageWriteTime,AverageReadTime,ReadBytesPerSecond,WriteBytesPerSecond FROM  SCX_DiskDriveStatisticalInformation WHERE Name='_TOTAL'","table":"LinuxDisk"}
         ]
        :param for_app_insights: Indicates whether we are updating perf counters settings for AppInsights.
                                AppInsights requires specific names, so we need this.
        :return: None. The mdsd XML tree member is updated accordingly.
        """
        assert self._mdsd_config_xml_tree is not None

        if not omi_queries:
            return

        mdsd_omi_query_schema = """
<OMIQuery cqlQuery="" dontUsePerNDayTable="true" eventName="" omiNamespace="" priority="High" sampleRateInSeconds="" />
"""

        for omi_query in omi_queries:
            mdsd_omi_query_element = XmlUtil.createElement(mdsd_omi_query_schema)
            mdsd_omi_query_element.set('cqlQuery', omi_query['query'])
            mdsd_omi_query_element.set('eventName', omi_query['table'])
            namespace = omi_query['namespace'] if 'namespace' in omi_query else 'root/scx'
            mdsd_omi_query_element.set('omiNamespace', namespace)
            if for_app_insights:
                AIUtil.updateOMIQueryElement(mdsd_omi_query_element)
            XmlUtil.addElement(xml=self._mdsd_config_xml_tree, path='Events/OMI', el=mdsd_omi_query_element, addOnlyOnce=True)

    def _apply_perf_cfgs(self, include_app_insights=False):
        """
        Extract the 'perfCfg' settings from ext_settings and apply them to mdsd config XML root.
        :param include_app_insights: Indicates whether perf counter settings for AppInsights should be included or not.
        :return: None. Changes are applied directly to the mdsd config XML tree member.
        """
        assert self._mdsd_config_xml_tree is not None

        perf_cfgs = []
        default_perf_cfgs = [
                        {"query": "SELECT PercentAvailableMemory, AvailableMemory, UsedMemory, PercentUsedSwap "
                                  "FROM SCX_MemoryStatisticalInformation",
                         "table": "LinuxMemory"},
                        {"query": "SELECT PercentProcessorTime, PercentIOWaitTime, PercentIdleTime "
                                  "FROM SCX_ProcessorStatisticalInformation WHERE Name='_TOTAL'",
                         "table": "LinuxCpu"},
                        {"query": "SELECT AverageWriteTime,AverageReadTime,ReadBytesPerSecond,WriteBytesPerSecond "
                                  "FROM  SCX_DiskDriveStatisticalInformation WHERE Name='_TOTAL'",
                         "table": "LinuxDisk"}
                      ]
        try:
            # First try to get perf cfgs from the new 'ladCfg' setting.
            lad_cfg = self._ext_settings.read_public_config('ladCfg')
            perf_cfgs = LadUtil.generatePerformanceCounterConfigurationFromLadCfg(lad_cfg)
            # If none, try the original 'perfCfg' setting.
            if not perf_cfgs:
                perf_cfgs = self._ext_settings.read_public_config('perfCfg')
            # If none, use default (3 OMI queries)
            if not perf_cfgs and not self._ext_settings.has_public_config('perfCfg'):
                perf_cfgs = default_perf_cfgs
        except Exception as e:
            self._logger_error("Failed to parse performance configuration with exception:{0}\n"
                               "Stacktrace: {1}".format(e, traceback.format_exc()))

        try:
            self._update_perf_counters_settings(perf_cfgs)
            if include_app_insights:
                self._update_perf_counters_settings(perf_cfgs, True)
        except Exception as e:
            self._logger_error("Failed to create perf config. Error:{0}\n"
                               "Stacktrace: {1}".format(e, traceback.format_exc()))

    def _get_handler_cert_pkey_paths(self, handler_settings):
        """
        update_account_settings() helper.
        :param handler_settings: Extension "handlerSettings" Json dictionary.
        :return: 2-tupe of certificate path and private key path.
        """
        thumbprint = handler_settings['protectedSettingsCertThumbprint']
        cert_path = self._waagent_dir + '/' + thumbprint + '.crt'
        pkey_path = self._waagent_dir + '/' + thumbprint + '.prv'
        return cert_path, pkey_path

    def _encrypt_secret_with_cert(self, cert_path, secret):
        """
        update_account_settings() helper.
        :param cert_path: Cert file path
        :param secret: Secret to encrypt
        :return: Encrypted secret string. None if openssl command exec fails.
        """
        encrypted_secret_tmp_file_path = os.path.join(self._ext_dir, "mdsd_secret.bin")
        cmd = "echo -n '{0}' | openssl smime -encrypt -outform DER -out {1} {2}"
        cmd_to_run = cmd.format(secret, encrypted_secret_tmp_file_path, cert_path)
        ret_status, ret_msg = self._run_command(cmd_to_run, should_log=False)
        if ret_status is not 0:
            self._logger_error("Encrypting storage secret failed with the following message: " + ret_msg)
            return None
        with open(encrypted_secret_tmp_file_path, 'rb') as f:
            encrypted_secret = f.read()
        os.remove(encrypted_secret_tmp_file_path)
        return binascii.b2a_hex(encrypted_secret).upper()

    def _update_account_settings(self, account, key, token, endpoint, aikey=None):
        """
        Update the MDSD configuration Account element with Azure table storage properties.
        Exactly one of (key, token) must be provided. If an aikey is passed, then add a new Account element for Application
        Insights with the application insights key.
        :param account: Storage account to which LAD should write data
        :param key: Shared key secret for the storage account, if present
        :param token: SAS token to access the storage account, if present
        :param endpoint: Identifies the Azure instance (public or specific sovereign cloud) where the storage account is
        :param aikey: Key for accessing AI, if present
        """
        assert key or token, "Either key or token must be given."
        assert self._mdsd_config_xml_tree is not None

        handler_cert_path, handler_pkey_path = self._get_handler_cert_pkey_paths(self._ext_settings.get_handler_settings())
        if key:
            key = self._encrypt_secret_with_cert(handler_cert_path, key)
            XmlUtil.setXmlValue(self._mdsd_config_xml_tree, 'Accounts/Account',
                                "account", account, ['isDefault', 'true'])
            XmlUtil.setXmlValue(self._mdsd_config_xml_tree, 'Accounts/Account',
                                "key", key, ['isDefault', 'true'])
            XmlUtil.setXmlValue(self._mdsd_config_xml_tree, 'Accounts/Account',
                                "decryptKeyPath", handler_pkey_path, ['isDefault', 'true'])
            XmlUtil.setXmlValue(self._mdsd_config_xml_tree, 'Accounts/Account',
                                "tableEndpoint", endpoint, ['isDefault', 'true'])
            XmlUtil.removeElement(self._mdsd_config_xml_tree, 'Accounts', 'SharedAccessSignature')
        else:  # token
            token = self._encrypt_secret_with_cert(handler_cert_path, token)
            XmlUtil.setXmlValue(self._mdsd_config_xml_tree, 'Accounts/SharedAccessSignature',
                                "account", account, ['isDefault', 'true'])
            XmlUtil.setXmlValue(self._mdsd_config_xml_tree, 'Accounts/SharedAccessSignature',
                                "key", token, ['isDefault', 'true'])
            XmlUtil.setXmlValue(self._mdsd_config_xml_tree, 'Accounts/SharedAccessSignature',
                                "decryptKeyPath", handler_pkey_path, ['isDefault', 'true'])
            XmlUtil.setXmlValue(self._mdsd_config_xml_tree, 'Accounts/SharedAccessSignature',
                                "tableEndpoint", endpoint, ['isDefault', 'true'])
            XmlUtil.removeElement(self._mdsd_config_xml_tree, 'Accounts', 'Account')

        if aikey:
            AIUtil.createAccountElement(self._mdsd_config_xml_tree, aikey)

    # Formerly:
    # def config(xmltree, key, value, xmlpath, selector=[]):
    def _set_xml_attr(self, key, value, xml_path, selector=[]):
        """
        Set XML attribute on the element specified with xml_path.
        :param key: The attribute name to set on the XML element.
        :param value: The value to be assigned for the attribute, in case there's no public config for that attribute.
        :param xml_path: The path of the XML element on which the attribute is applied.
        :param selector: Selector for finding the actual XML element (see XmlUtil.setXmlValue)
        :return: None. Change is directly applied to mdsd_config_xml_tree XML member object.
        """
        assert self._mdsd_config_xml_tree is not None

        v = self._ext_settings.read_public_config(key)
        if not v:
            v = value
        XmlUtil.setXmlValue(self._mdsd_config_xml_tree, xml_path, key, v, selector)

    def _set_event_volume(self, lad_cfg):
        """
        Set event volumne in mdsd config. Check if desired event volume is specified,
        first in ladCfg then in public config. If in neither then default to Medium.
        :param lad_cfg: 'ladCfg' Json object to look up for the event volume setting.
        :return: None. The mdsd config XML tree's eventVolume attribute is directly updated.
        :rtype: str
        """
        assert self._mdsd_config_xml_tree is not None

        event_volume = LadUtil.getEventVolumeFromLadCfg(lad_cfg)
        if event_volume:
            self._logger_log("Event volume found in ladCfg: " + event_volume)
        else:
            event_volume = self._ext_settings.read_public_config("eventVolume")
            if event_volume:
                self._logger_log("Event volume found in public config: " + event_volume)
            else:
                event_volume = "Medium"
                self._logger_log("Event volume not found in config. Using default value: " + event_volume)
        XmlUtil.setXmlValue(self._mdsd_config_xml_tree, "Management", "eventVolume", event_volume)

    ######################################################################
    # This is the main API that's called by user. All other methods are
    # actually helpers for this, thus made private by convention.
    ######################################################################
    def generate_mdsd_rsyslog_configs(self):
        """
        Generates XML cfg file for mdsd, from JSON config settings (public & private).
        Also generates rsyslog imfile conf file from the 'fileCfg' setting.
        Returns (True, '') if config was valid and proper xmlCfg.xml was generated.
        Returns (False, '...') if config was invalid and the error message.
        """

        # 1. Get the mdsd config XML tree base.
        #    - 1st priority is from the extension setting's 'mdsdCfg' value.
        #      Note that we have never used this option.
        #    - 2nd priority is to use the provided XML template stored in <ext_dir>/mdsdConfig.xml.template.
        mdsd_cfg_str = self._ext_settings.get_mdsd_cfg()
        if mdsd_cfg_str:
            try:
                self._mdsd_config_xml_tree = ET.ElementTree(ET.fromstring(mdsd_cfg_str))
            except Exception as e:
                msg = "Error parsing supplied mdsdCfg string: {0}".format(e)
                self._logger_error(msg)
                return False, msg
        else:
            self._mdsd_config_xml_tree = ET.parse(os.path.join(self._ext_dir, './mdsdConfig.xml.template'))

        # 2. Add DeploymentId (if available) to identity columns
        if self._deployment_id:
            XmlUtil.setXmlValue(self._mdsd_config_xml_tree, "Management/Identity/IdentityComponent", "",
                                self._deployment_id, ["name", "DeploymentId"])
        # 2.1. Use ladCfg to generate OMIQuery and LADQuery elements
        lad_cfg = self._ext_settings.read_public_config('ladCfg')
        if lad_cfg:
            self._update_metric_collection_settings(lad_cfg)

        # 2.9. Apply resourceId attribute to LADQuery elements
        try:
            resource_id = self._ext_settings.get_resource_id()
            if resource_id:
                escaped_resource_id_str = escape_nonalphanumerics(resource_id)
                self._add_portal_settings(escaped_resource_id_str)
                instanceID = ""
                if resource_id.find("providers/Microsoft.Compute/virtualMachineScaleSets") >= 0:
                    instanceID = read_uuid(self._run_command)
                self._set_xml_attr("instanceID", instanceID, "Events/DerivedEvents/DerivedEvent/LADQuery")
        except Exception as e:
            self._logger_error("Failed to create portal config  error:{0} {1}".format(e, traceback.format_exc()))

        # 3. Update perf counter config. Need to distinguish between non-AppInsights scenario and AppInsights scenario,
        #    so check if Application Insights key is present in ladCfg first, and pass it to the actual helper
        #    function (self._apply_perf_cfgs()).
        do_ai = False
        aikey = None
        try:
            aikey = AIUtil.tryGetAiKey(lad_cfg)
            if aikey:
                self._logger_log("Application Insights key found.")
                do_ai = True
            else:
                self._logger_log("Application Insights key not found.")
        except Exception as e:
            self._logger_error("Failed check for Application Insights key in LAD configuration with exception:{0}\n"
                               "Stacktrace: {1}".format(e, traceback.format_exc()))
        self._apply_perf_cfgs(do_ai)

        # 4. Generate rsyslog omazuremds, imfile configs, and update corresponding mdsd config XML
        try:
            lad30_syslogCfg = self._ext_settings.get_lad30_syslogCfg_setting()
            lad30_syslogEvents = self._ext_settings.get_lad30_syslogEvents_setting()
            lad30_fileLogs = self._ext_settings.get_lad30_fileLogs_setting()
            rsyslog_mdsd_config_helper = RsyslogMdsdConfig(lad30_syslogEvents, lad30_syslogCfg, lad30_fileLogs)
            omazuremds_legacy_config = rsyslog_mdsd_config_helper.get_omazuremds_config(legacy=True)
            omazuremds_config = rsyslog_mdsd_config_helper.get_omazuremds_config(legacy=False)
            imfile_config = rsyslog_mdsd_config_helper.get_imfile_config()
            mdsd_syslog_config = rsyslog_mdsd_config_helper.get_mdsd_syslog_config()
            mdsd_filelog_config = rsyslog_mdsd_config_helper.get_mdsd_filelog_config()
            write_string_to_file('rsyslog5/omazurelinuxmds.conf', omazuremds_legacy_config)
            write_string_to_file('rsyslog7/omazurelinuxmds.conf', omazuremds_legacy_config)
            write_string_to_file('rsyslog8/omazurelinuxmds.conf', omazuremds_config)
            write_string_to_file(self._imfile_config_filename, imfile_config)
            copy_schema_source_mdsdevent_elems(self._mdsd_config_xml_tree, mdsd_syslog_config)
            copy_schema_source_mdsdevent_elems(self._mdsd_config_xml_tree, mdsd_filelog_config)
        except Exception as e:
            self._logger_error("Failed to create omazuremds/imfile configs or to update corresponding "
                               "mdsd config XML. Error: {0}\nStacktrace: {1}".format(e, traceback.format_exc()))

        # 5. Before starting to update the storage account settings, log extension's protected settings'
        #    keys only (except well-known values), for diagnostic purpose. This is mainly to make sure that
        #    the extension's Json settings include a correctly entered 'storageEndpoint'.
        self._ext_settings.log_protected_settings_keys(self._logger_log, self._logger_error)

        # 6. Actually update the storage account settings on mdsd config XML tree (based on extension's
        #    protectedSettings).
        account = self._ext_settings.read_protected_config('storageAccountName')
        if not account:
            return False, "Empty storageAccountName"
        key = self._ext_settings.read_protected_config('storageAccountKey')
        token = self._ext_settings.read_protected_config('storageAccountSasToken')
        if not key and not token:
            return False, "Neither storageAccountKey nor storageAccountSasToken is given"
        if key and token:
            return False, "Either storageAccountKey or storageAccountSasToken (but not both) should be given"
        endpoint = get_storage_endpoint_with_account(account,
                                                     self._ext_settings.read_protected_config('storageAccountEndPoint'))
        self._update_account_settings(account, key, token, endpoint, aikey)

        # 7. Check and add new syslog RouteEvent for Application Insights.
        if aikey:
            AIUtil.createSyslogRouteEventElement(self._mdsd_config_xml_tree)

        # 8. Update mdsd config XML's eventVolume attribute based on the logic specified in the helper.
        self._set_event_volume(lad_cfg)

        # 9. Update mdsd config XML's sampleRateInSeconds attribute with default '60'
        self._set_xml_attr("sampleRateInSeconds", "60", "Events/OMI/OMIQuery")

        # 10. Finally generate mdsd config XML file out of the constructed XML tree object.
        self._mdsd_config_xml_tree.write(os.path.join(self._ext_dir, './xmlCfg.xml'))

        return True, ""

