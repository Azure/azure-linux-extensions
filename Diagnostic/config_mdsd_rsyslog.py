#!/usr/bin/env python
#
# Azure Linux extension
#
# Linux Azure Diagnostic Extension (Current version is specified in manifest.xml)
# Copyright (c) Microsoft Corporation
# All rights reserved.
# MIT License
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the ""Software""), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
# THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import base64
import binascii
from misc_helpers import read_uuid, get_storage_endpoint_with_account
import os.path
import traceback
import xml.dom.minidom
import xml.etree.ElementTree as ET
import Utils.ApplicationInsightsUtil as AIUtil
import Utils.LadDiagnosticUtil as LadUtil
import Utils.XmlUtil as XmlUtil


class LadExtSettings:
    """
    Wrapper class around LAD's extension settings Json objects.
    """
    def __init__(self, handler_settings):
        self._handler_settings = handler_settings if handler_settings else {}
        public_settings = self._handler_settings.get('publicSettings')
        self._public_settings = public_settings if public_settings else {}
        protected_settings = self._handler_settings.get('protectedSettings')
        self._protected_settings = protected_settings if protected_settings else {}

    def get_handler_settings(self):
        return self._handler_settings

    def has_public_config(self, key):
        return key in self._public_settings

    def read_public_config(self, key):
        if key in self._public_settings:
            return self._public_settings[key]
        return ''

    def read_protected_config(self, key):
        if key in self._protected_settings:
            return self._protected_settings[key]
        return ''

    def log_private_settings_keys(self, logger_log, logger_err):
        try:
            msg = "Keys in privateSettings (and some non-secret values): "
            first = True
            for key in self._private_settings:
                if first:
                    first = False
                else:
                    msg += ", "
                msg += key
                if key == 'storageAccountEndPoint':
                    msg += ":" + self._private_settings[key]
            logger_log(msg)
        except Exception as e:
            logger_err("Failed to log keys in privateSettings. Error:{0}\n"
                       "Stacktrace: {1}".format(e, traceback.format_exc()))


def get_deployment_id(ext_dir, logger_log, logger_error):
    """
    Get deployment ID from waagent dir (ext_dir's parent)'s HostingEnvironmentConfig.xml.
    :param ext_dir: Extension directory in full path
    :param logger_log:  Logger function (e.g., hutil.log)
    :param logger_error:  Error-logger function (e.g., hutil.error)
    :return: Obtained deployment ID string, or '' if no matching element is found, or None if no such file.
    """
    identity = "unknown"
    env_cfg_path = os.path.join(ext_dir, os.pardir, "HostingEnvironmentConfig.xml")
    if not os.path.exists(env_cfg_path):
        logger_log("No Deployment ID (not running in a hosted environment")
        return None

    try:
        with open(env_cfg_path, 'r') as env_cfg_file:
            xml_text = env_cfg_file.read()
        dom = xml.dom.minidom.parseString(xml_text)
        deployment = dom.getElementsByTagName("Deployment")
        name = deployment[0].getAttribute("name")
        if name:
            identity = name
            logger_log("Deployment ID found: {0}.".format(identity))
    except Exception as e:
        # use fallback identity
        logger_error("Failed to retrieve deployment ID. Error:{0}\nStacktrace: {1}".format(e, traceback.format_exc()))

    return identity


def get_resource_id(ext_settings):
    """
    Try to get resourceId from LadCfg. If not present, try to fetch from xmlCfg.
    """
    lad_cfg = ext_settings.read_public_config('ladCfg')
    resource_id = LadUtil.getResourceIdFromLadCfg(lad_cfg)
    if not resource_id:
        encoded_xml_cfg = ext_settings.read_public_config('xmlCfg').strip()
        if encoded_xml_cfg:
            xml_cfg = base64.b64decode(encoded_xml_cfg)
            resource_id = XmlUtil.getXmlValue(XmlUtil.createElement(xml_cfg),
                                              'diagnosticMonitorConfiguration/metrics', 'resourceId')
            # Azure portal uses xmlCfg which contains WadCfg which is pascal case
            # Currently we will support both casing and deprecate one later
            if not resource_id:
                resource_id = XmlUtil.getXmlValue(XmlUtil.createElement(xml_cfg),
                                                  'DiagnosticMonitorConfiguration/Metrics', 'resourceId')
    return resource_id


def add_portal_settings(mdsd_config_xml_tree, ext_dir, resource_id):
    """
    Update mdsd_config_xml_tree for Azure Portal metric collection setting.
    It's basically applying the resource_id as the partitionKey attribute of LADQuery elements.

    :param mdsd_config_xml_tree: Root of the mdsd config XML tree.
    :param ext_dir: Extension directory (WorkDir in diagnostic.py,
                    /var/lib/waagent/Microsoft.OSTCExtension.LinuxDiagnostic-2.3.xxxx), where the portal.xml.template
                    will be obtained.
    :param resource_id: ARM rerousce ID to provide as partitionKey in LADQuery elements
    :return: None
    """
    portal_config = ET.ElementTree()
    portal_config.parse(os.path.join(ext_dir, 'portal.xml.template'))
    XmlUtil.setXmlValue(portal_config, './DerivedEvents/DerivedEvent/LADQuery', 'partitionKey', resource_id)
    XmlUtil.addElement(mdsd_config_xml_tree, 'Events', portal_config._root.getchildren()[0])
    XmlUtil.addElement(mdsd_config_xml_tree, 'Events', portal_config._root.getchildren()[1])


def update_and_get_file_monitoring_settings(mdsd_config_xml_tree, files):
    """
    Update mdsd config's file monitoring config. Also creates/returns rsyslog imfile config.
    All the operations are based on the input param files, which is a Json-deserialized dictionary
    corresponding the following Json array example:
    [
        {"file":"/var/log/a.log", "table":"aLog"},
        {"file":"/var/log/b.log", "table":"bLog"}
    ]
    :param mdsd_config_xml_tree: XML tree object representing mdsd XML config.
    :param files: Array of dictionaries deserialized from the 'fileCfg' Json config (example as above)
    :return: rsyslog omfile module config file content
    """

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

    for file in files:
        file_id += 1
        mdsd_event_source_element = XmlUtil.createElement(mdsd_event_source_schema)
        XmlUtil.setXmlValue(mdsd_event_source_element, 'RouteEvent', 'eventName', file["table"])
        mdsd_event_source_element.set('source', 'ladfile'+str(file_id))
        XmlUtil.addElement(mdsd_config_xml_tree, 'Events/MdsdEvents', mdsd_event_source_element)

        mdsd_source_element = XmlUtil.createElement(mdsd_source_schema)
        mdsd_source_element.set('name', 'ladfile'+str(file_id))
        XmlUtil.addElement(mdsd_config_xml_tree, 'Sources', mdsd_source_element)

        imfile_per_file_config = imfile_per_file_config_template.replace('#FILE#', file['file'])
        imfile_per_file_config = imfile_per_file_config.replace('#STATFILE#', file['file'].replace("/","-"))
        imfile_per_file_config = imfile_per_file_config.replace('#FILETAG#', 'ladfile'+str(file_id))
        imfile_config += imfile_per_file_config
    return imfile_config


def update_perf_counters_settings(mdsd_config_xml_tree, omi_queries, for_app_insights=False):
    """
    Update the mdsd XML tree with the OMI queries provided.
    :param mdsd_config_xml_tree: Root of mdsd config XML tree.
    :param omi_queries: List of dictionaries specifying OMI queries and destination tables. E.g.:
     [
         {"query":"SELECT PercentAvailableMemory, AvailableMemory, UsedMemory, PercentUsedSwap FROM SCX_MemoryStatisticalInformation","table":"LinuxMemory"},
         {"query":"SELECT PercentProcessorTime, PercentIOWaitTime, PercentIdleTime FROM SCX_ProcessorStatisticalInformation WHERE Name='_TOTAL'","table":"LinuxCpu"},
         {"query":"SELECT AverageWriteTime,AverageReadTime,ReadBytesPerSecond,WriteBytesPerSecond FROM  SCX_DiskDriveStatisticalInformation WHERE Name='_TOTAL'","table":"LinuxDisk"}
     ]
    :param for_app_insights: Indicates whether we are updating perf counters settings for AppInsights.
                            AppInsights requires specific names, so we need this.
    :return: None. The passed mdsd XML tree is updated accordingly.
    """
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
        XmlUtil.addElement(xml=mdsd_config_xml_tree, path='Events/OMI', el=mdsd_omi_query_element, addOnlyOnce=True)


def apply_perf_cfgs(mdsd_config_xml_tree, ext_settings, logger_error, include_app_insights=False):
    """
    Extract the 'perfCfg' settings from ext_settings and apply them to mdsd config XML root.
    :param mdsd_config_xml_tree: The root of the mdsd config XML tree
    :param ext_settings: LAD extension settings encapsulated as a LadExtSettings object.
    :param logger_error: Error-logging function
    :param include_app_insights: Indicates whether perf counter settings for AppInsights should be included or not.
    :return: None. Changes are applied directly to the mdsd config XML tree.
    """

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
        lad_cfg = ext_settings.read_public_config('ladCfg')
        perf_cfgs = LadUtil.generatePerformanceCounterConfigurationFromLadCfg(lad_cfg)
        # If none, try the original 'perfCfg' setting.
        if not perf_cfgs:
            perf_cfgs = ext_settings.read_public_config('perfCfg')
        # If none, use default (3 OMI queries)
        if not perf_cfgs and not ext_settings.has_public_config('perfCfg'):
            perf_cfgs = default_perf_cfgs
    except Exception as e:
        logger_error("Failed to parse performance configuration with exception:{0}\n"
                     "Stacktrace: {1}".format(e, traceback.format_exc()))

    try:
        update_perf_counters_settings(mdsd_config_xml_tree, perf_cfgs)
        if include_app_insights:
            update_perf_counters_settings(mdsd_config_xml_tree, perf_cfgs, True)
    except Exception as e:
        logger_error("Failed to create perf config. Error:{0}\n"
                     "Stacktrace: {1}".format(e, traceback.format_exc()))


def get_handler_cert_pkey_paths(waagent_dir, handler_settings):
    """
    update_account_settings() helper.
    :param waagent_dir: waagent install dir (/var/lib/waagent)
    :param handler_settings: Extension "handlerSettings" Json dictionary.
    :return: 2-tupe of certificate path and private key path.
    """
    thumbprint = handler_settings['protectedSettingsCertThumbprint']
    cert_path = waagent_dir + '/' + thumbprint + '.crt'
    pkey_path = waagent_dir + '/' + thumbprint + '.prv'
    return cert_path, pkey_path


def encrypt_secret_with_cert(ext_dir, run_command, logger_error, cert_path, secret):
    """
    update_account_settings() helper.
    :param ext_dir: Extension directory (/var/lib/waagent/Microsft. ...)
    :param run_command: External command runner function (RunGetOutput)
    :param logger_error: Error logger function (hutil.error)
    :param cert_path: Cert file path
    :param secret: Secret to encrypt
    :return: Encrypted secret string. None if openssl command exec fails.
    """
    encrypted_secret_tmp_file_path = os.path.join(ext_dir, "mdsd_secret.bin")
    cmd_to_run = "echo -n '{0}' | openssl smime -encrypt -outform DER -out {1} {2}".format(secret, encrypted_secret_tmp_file_path, cert_path)
    ret_status, ret_msg = run_command(cmd_to_run, should_log=False)
    if ret_status is not 0:
        logger_error("Encrypting storage secret failed with the following message: " + ret_msg)
        return None
    with open(encrypted_secret_tmp_file_path, 'rb') as f:
        encrypted_secret = f.read()
    os.remove(encrypted_secret_tmp_file_path)
    return binascii.b2a_hex(encrypted_secret).upper()


def update_account_settings(ext_settings, run_command, ext_dir, waagent_dir, logger_error,
                            mdsd_config_xml_tree, account, key, token, endpoint, aikey=None):
    """
    Updates the MDSD configuration Account elements.
    Updates existing default Account element with Azure table storage properties.
    If an aikey is provided to the function, then it adds a new Account element for
    Application Insights with the application insights key.

    :param mdsd_config_xml_tree: MDSD config XML object where account settings will be updated
    :param account: Storage account name
    :param key: Storage account shared key
    :param token: Storage account SAS. Either key or token must be specified. If both are given, key will be used.
    :param endpoint: Storage endpoint
    :param aikey: Indicates whether AppInsights key should be updated as well
    :return:
    """
    assert key or token, "Either key or token must be given."

    handler_cert_path, handler_pkey_path = get_handler_cert_pkey_paths(waagent_dir, ext_settings.get_handler_settings())
    if key:
        key = encrypt_secret_with_cert(ext_dir, run_command, logger_error, handler_cert_path, key)
        XmlUtil.setXmlValue(mdsd_config_xml_tree, 'Accounts/Account', "account", account, ['isDefault', 'true'])
        XmlUtil.setXmlValue(mdsd_config_xml_tree, 'Accounts/Account', "key", key, ['isDefault', 'true'])
        XmlUtil.setXmlValue(mdsd_config_xml_tree, 'Accounts/Account', "decryptKeyPath", handler_pkey_path, ['isDefault', 'true'])
        XmlUtil.setXmlValue(mdsd_config_xml_tree, 'Accounts/Account', "tableEndpoint", endpoint, ['isDefault', 'true'])
        XmlUtil.removeElement(mdsd_config_xml_tree, 'Accounts', 'SharedAccessSignature')
    else:  # token
        token = encrypt_secret_with_cert(ext_dir, run_command, logger_error, handler_cert_path, token)
        XmlUtil.setXmlValue(mdsd_config_xml_tree, 'Accounts/SharedAccessSignature', "account", account, ['isDefault', 'true'])
        XmlUtil.setXmlValue(mdsd_config_xml_tree, 'Accounts/SharedAccessSignature', "key", token, ['isDefault', 'true'])
        XmlUtil.setXmlValue(mdsd_config_xml_tree, 'Accounts/SharedAccessSignature', "decryptKeyPath", handler_pkey_path, ['isDefault', 'true'])
        XmlUtil.setXmlValue(mdsd_config_xml_tree, 'Accounts/SharedAccessSignature', "tableEndpoint", endpoint, ['isDefault', 'true'])
        XmlUtil.removeElement(mdsd_config_xml_tree, 'Accounts', 'Account')

    if aikey:
        AIUtil.createAccountElement(mdsd_config_xml_tree, aikey)


def set_xml_attr(ext_settings, mdsd_config_xml_tree, key, value, xml_path, selector=[]):
    """
    Set XML attribute on the element specified with xml_path.
    :param ext_settings: Extension setting to look up for the attribute's value.
    :param mdsd_config_xml_tree: MDSD config XML tree's root
    :param key: The attribute name to set on the XML element.
    :param value: The value to be assigned for the attribute, in case there's no public config for that attribute.
    :param xml_path: The path of the XML element on which the attribute is applied.
    :param selector: Selector for finding the actual XML element (see XmlUtil.setXmlValue)
    :return: None. Change is directly applied to mdsd_config_xml_tree XML object.
    """
    v = ext_settings.read_public_config(key)
    if not v:
        v = value
    XmlUtil.setXmlValue(mdsd_config_xml_tree, xml_path, key, v, selector)


def get_syslog_config(ext_settings):
    """
    Get syslog config from extension settings.
    First look up 'ladCfg' section's 'syslogCfg' and use it. If none, then use 'syslogCfg' at the top level
    of public settings. Base64-encoded rsyslogd conf content is currently supported for 'syslogCfg' in either
    section.
    :param ext_settings: Extension setting object (LadExtSettings) to look up for 'syslogCfg'
    :return: rsyslogd configuration content string (base64-decoded 'syslogCfg' setting)
    """
    syslog_cfg = ''
    lad_cfg = ext_settings.read_public_config('ladCfg')
    encoded_syslog_cfg = LadUtil.getDiagnosticsMonitorConfigurationElement(lad_cfg, 'syslogCfg')
    if not encoded_syslog_cfg:
        encoded_syslog_cfg = ext_settings.read_public_config('syslogCfg')
    if encoded_syslog_cfg:
        syslog_cfg = base64.b64decode(encoded_syslog_cfg)
    return syslog_cfg


def get_file_monitoring_config(ext_settings):
    """
    Get rsyslog file monitoring (imfile module) config from extension settings.
    First look up 'ladCfg' and use it if one is there. If not, then get 'fileCfg' at the top level
    of public settings.
    :param ext_settings: Extension setting object (LadExtSettings type) to look up for 'fileCfg'
    :return: List of dictionaries specifying files to monitor and Azure table names for the destinations
    of the monitored files. E.g.:
    [
      {"file":"/var/log/a.log", "table":"aLog"},
      {"file":"/var/log/b.log", "table":"bLog"}
    ]
    """
    lad_cfg = ext_settings.read_public_config('ladCfg')
    file_cfg = LadUtil.getFileCfgFromLadCfg(lad_cfg)
    if not file_cfg:
        file_cfg = ext_settings.read_public_config('fileCfg')
    return file_cfg


def set_event_volume(ext_settings, logger_log, mdsd_config_xml_tree, lad_cfg):
    """
    Set event volumne in mdsd config. Check if desired event volume is specified,
    first in ladCfg then in public config. If in neither then default to Medium.
    :param ext_settings: Extension settings object (LadExtSettings type) to look up for the event volume setting
    :param logger_log: Logger function (hutil.log)
    :param mdsd_config_xml_tree: MDSD config XML tree root where eventVolume will be set
    :param lad_cfg: 'ladCfg' Json object to look up for the event volume setting.
    :return:
    """
    event_volume = LadUtil.getEventVolumeFromLadCfg(lad_cfg)
    if event_volume:
        logger_log("Event volume found in ladCfg: " + event_volume)
    else:
        event_volume = ext_settings.read_public_config("eventVolume")
        if event_volume:
            logger_log("Event volume found in public config: " + event_volume)
        else:
            event_volume = "Medium"
            logger_log("Event volume not found in config. Using default value: " + event_volume)
    XmlUtil.setXmlValue(mdsd_config_xml_tree, "Management", "eventVolume", event_volume)


def generate_mdsd_rsyslog_configs(ext_settings, ext_dir, waagent_dir, imfile_config_filename,
                                  run_command, logger_log, logger_error):
    '''
    Generates XML cfg file for mdsd, from JSON config settings (public & private).
    Also generates rsyslog imfile conf file from the 'fileCfg' setting.
    Returns (True, '') if config was valid and proper xmlCfg.xml was generated.
    Returns (False, '...') if config was invalid and the error message.
    '''
    mdsd_cfg_str = ext_settings.read_public_config('mdsdCfg')
    if not mdsd_cfg_str:
        with open(os.path.join(ext_dir, './mdsdConfig.xml.template'), "r") as defaulCfg:
            mdsd_cfg_str = defaulCfg.read()
    else:
        mdsd_cfg_str = base64.b64decode(mdsd_cfg_str)
    mdsd_cfg_xml_tree = ET.ElementTree()
    mdsd_cfg_xml_tree._setroot(XmlUtil.createElement(mdsd_cfg_str))

    # Add DeploymentId (if available) to identity columns
    deployment_id = get_deployment_id(ext_dir, logger_log, logger_error)
    if deployment_id:
        XmlUtil.setXmlValue(mdsd_cfg_xml_tree, "Management/Identity/IdentityComponent", "", deployment_id,
                            ["name", "DeploymentId"])

    try:
        resource_id = get_resource_id(ext_settings)
        if resource_id:
            escaped_resource_id_str = ''.join([ch if ch.isalnum() else ":{0:04X}".format(ord(ch)) for ch in resource_id])
            add_portal_settings(mdsd_cfg_xml_tree, ext_dir, escaped_resource_id_str)
            instanceID = ""
            if resource_id.find("providers/Microsoft.Compute/virtualMachineScaleSets") >= 0:
                instanceID = read_uuid(run_command)
            set_xml_attr(ext_settings, mdsd_cfg_xml_tree, "instanceID", instanceID,
                         "Events/DerivedEvents/DerivedEvent/LADQuery")

    except Exception as e:
        logger_error("Failed to create portal config  error:{0} {1}".format(e, traceback.format_exc()))

    # Check if Application Insights key is present in ladCfg
    lad_cfg = ext_settings.read_public_config('ladCfg')
    try:
        aikey = AIUtil.tryGetAiKey(lad_cfg)
        if aikey:
            logger_log("Application Insights key found.")
        else:
            logger_log("Application Insights key not found.")
    except Exception as e:
        logger_error("Failed check for Application Insights key in LAD configuration with exception:{0}\n"
                    "Stacktrace: {1}".format(e, traceback.format_exc()))

    apply_perf_cfgs(mdsd_cfg_xml_tree, ext_settings, logger_error, aikey != None)

    syslog_cfg = get_syslog_config(ext_settings)
    file_cfg = get_file_monitoring_config(ext_settings)
    # fileCfg = [{"file":"/var/log/waagent.log","table":"waagent"},{"file":"/var/log/waagent2.log","table":"waagent3"}]
    try:
        if file_cfg:
            syslog_cfg = update_and_get_file_monitoring_settings(mdsd_cfg_xml_tree, file_cfg) + syslog_cfg
        with open(imfile_config_filename, 'w') as hfile:
            hfile.write(syslog_cfg)
    except Exception as e:
        logger_error("Failed to create rsyslog imfile config. Error:{0}\n"
                     "Stacktrace: {1}".format(e, traceback.format_exc()))

    ext_settings.log_private_settings_keys(logger_log, logger_error)

    account = ext_settings.read_protected_config('storageAccountName')
    if not account:
        return False, "Empty storageAccountName"
    key = ext_settings.read_protected_config('storageAccountKey')
    token = ext_settings.read_protected_config('storageAccountSasToken')
    if not key and not token:
        return False, "Neither storageAccountKey nor storageAccountSasToken is given"
    if key and token:
        return False, "Either storageAccountKey or storageAccountSasToken (but not both) should be given"
    endpoint = get_storage_endpoint_with_account(account,
                                                 ext_settings.read_protected_config('storageAccountEndPoint'))

    update_account_settings(ext_settings, run_command, ext_dir, waagent_dir, logger_error,
                            mdsd_cfg_xml_tree, account, key, token, endpoint, aikey)

    # Check and add new syslog RouteEvent for Application Insights.
    if aikey:
        AIUtil.createSyslogRouteEventElement(mdsd_cfg_xml_tree)

    set_event_volume(ext_settings, logger_log, mdsd_cfg_xml_tree, lad_cfg)

    set_xml_attr(ext_settings, mdsd_cfg_xml_tree, "sampleRateInSeconds", "60", "Events/OMI/OMIQuery")

    mdsd_cfg_xml_tree.write(os.path.join(ext_dir, './xmlCfg.xml'))

    return True, ""


class ConfigMdsdRsyslog:

    def __init__(self, lad_config, logger_log, logger_error):
        self._lad_config = lad_config
        self._logger_log = logger_log
        self._logger_error = logger_error

