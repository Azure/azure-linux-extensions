#!/usr/bin/env python
#
# Azure Linux extension
#
# Linux Azure Diagnostic Extension (Current version is specified in manifest.xml)
# Copyright (c) Microsoft Corporation All rights reserved.
# MIT License
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the ""Software""), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following
# conditions: The above copyright notice and this permission notice shall be included in all copies or substantial
# portions of the Software. THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import base64
import binascii
import datetime
import exceptions
import os
import os.path
import platform
import signal
import subprocess
import sys
import syslog
import threading
import time
import traceback
import xml.dom.minidom
import xml.etree.ElementTree as ET

import Utils.ApplicationInsightsUtil as AIUtil
import Utils.LadDiagnosticUtil as LadUtil
import Utils.XmlUtil as XmlUtil
from Utils.imds_util import ImdsLogger
import watcherutil
import DistroSpecific
from misc_helpers import get_extension_operation_type, wala_event_type_for_telemetry,\
    get_storage_endpoint_with_account, check_suspected_memory_leak, read_uuid, log_private_settings_keys, tail,\
    escape_nonalphanumerics

try:  # Just wanted to be able to run 'python diagnostic.py ...' from a local dev box where there's no waagent.
    import Utils.HandlerUtil as Util
    from Utils.WAAgentUtil import waagent
except Exception as e:
    print('waagent import failed.\nException thrown: {0}\nStacktrace: {1}'.format(e, traceback.format_exc()))
    print('Are you running without waagent for some reason? Just passing here for now...')
    # We may add some waagent mock later to support this scenario.


def init_distro_specific_actions():
    """
    Identify the specific Linux distribution in use. Set the global distConfig to point to the corresponding
    implementation class. If the distribution isn't supported, set the extension status appropriately and exit.
    Expects the global hutil to already be initialized.
    """
    # TODO Exit immediately if distro is unknown
    global distConfig, RunGetOutput
    dist = platform.dist()
    distroNameAndVersion = dist[0] + ":" + dist[1]
    try:
        distConfig = DistroSpecific.get_distro_actions(dist[0], dist[1], hutil.log)
        RunGetOutput = distConfig.log_run_get_output
    except exceptions.LookupError as ex:
        hutil.error("os version:" + distroNameAndVersion + " not supported")
        # TODO Exit immediately if distro is unknown
        distConfig = None


def init_public_and_private_settings():
    """Initialize extension's public & private settings. hutil must be already initialized prior to calling this."""
    global public_settings, private_settings

    hutil.try_parse_context()
    hutil.set_verbose_log(False)  # This is default, but this choice will be made explicit and logged.
    public_settings = hutil.get_public_settings()
    private_settings = hutil.get_protected_settings()
    if not public_settings:
        public_settings = {}
    if not private_settings:
        private_settings = {}


def init_globals():
    """Initialize all the globals in a function so that we can catch any exceptions that might be raised."""
    global hutil, WorkDir, MDSDFileResourcesDir, MDSDRoleName, MDSDFileResourcesPrefix, MDSDPidFile, MDSDPidPortFile
    global EnableSyslog, ExtensionOperationType, MdsdFolder, StartDaemonFilePath, MDSD_LISTEN_PORT, omfileconfig
#    global rsyslog_ommodule_for_check, RunGetOutput, MdsdFolder, omi_universal_pkg_name
#    global DebianConfig, RedhatConfig, UbuntuConfig1510OrHigher, SUSE11_MDSD_SSL_CERTS_FILE
#    global SuseConfig11, SuseConfig12, CentosConfig, All_Dist

    waagent.LoggerInit('/var/log/waagent.log', '/dev/stdout')
    waagent.Log("LinuxAzureDiagnostic started to handle.")
    hutil = Util.HandlerUtility(waagent.Log, waagent.Error)
    init_distro_specific_actions()

    WorkDir = os.getcwd()
    MDSDFileResourcesDir = "/var/run/mdsd"
    MDSDRoleName = 'lad_mdsd'
    MDSDFileResourcesPrefix = os.path.join(MDSDFileResourcesDir, MDSDRoleName)
    MDSDPidFile = os.path.join(WorkDir, 'mdsd.pid')
    MDSDPidPortFile = MDSDFileResourcesPrefix + '.pidport'
    EnableSyslog = True
    ExtensionOperationType = None
    MdsdFolder = os.path.join(WorkDir, 'bin')
    StartDaemonFilePath = os.path.join(os.getcwd(), __file__)
    MDSD_LISTEN_PORT = 29131
    omfileconfig = os.path.join(WorkDir, 'omfileconfig')

    init_public_and_private_settings()


def setup_dependencies_and_mdsd():
    global EnableSyslog

    # Install dependencies
    install_package_error = ""
    retry = 3
    while retry > 0:
        error, msg = install_required_package()
        hutil.log(msg)
        if error == 0:
            break
        else:
            retry -= 1
            hutil.log("Sleep 60 retry " + str(retry))
            install_package_error = msg
            time.sleep(60)
    if install_package_error:
        if len(install_package_error) > 1024:
            install_package_error = install_package_error[0:512] + install_package_error[-512:-1]
        hutil.error(install_package_error)
        return 2, install_package_error

    if EnableSyslog:
        error, msg = install_rsyslogom()
        if error != 0:
            hutil.error(msg)
            return 3, msg

    # Run mdsd prep commands
    distConfig.prepare_for_mdsd_install()

    # Install/start OMI
    omi_err, omi_msg = install_omi()
    if omi_err is not 0:
        return 4, omi_msg

    return 0, 'success'


def hasPublicConfig(key):
    """
    Determine if a particular setting is present in the public config
    :param str key: The setting to look for
    :return: True if the setting is present (regardless of its value)
    :rtype: bool
    """
    return key in public_settings


def readPublicConfig(key):
    """
    Return the value of a particular public config setting
    :param str key: The setting to retrieve
    :return: The value of the setting if present; an empty string (*not* None) if the setting is not present
    :rtype: str
    """
    if key in public_settings:
        return public_settings[key]
    return ''


def readPrivateConfig(key):
    if key in private_settings:
        return private_settings[key]
    return ''


def createPortalSettings(tree, resourceId):
    portal_config = ET.ElementTree()
    portal_config.parse(os.path.join(WorkDir, "portal.xml.template"))
    XmlUtil.setXmlValue(portal_config, "./DerivedEvents/DerivedEvent/LADQuery", "partitionKey", resourceId)
    XmlUtil.addElement(tree, 'Events', portal_config._root.getchildren()[0])
    XmlUtil.addElement(tree, 'Events', portal_config._root.getchildren()[1])


eventSourceSchema = """
<MdsdEventSource source="ladfile">
    <RouteEvent dontUsePerNDayTable="true" eventName="" priority="High"/>
</MdsdEventSource>
"""
sourceSchema = """
<Source name="ladfile1" schema="ladfile" />
"""

syslogEventSourceConfig = """

$InputFileName #FILE#
$InputFileTag #FILETAG#
$InputFileFacility local6
$InputFileStateFile syslog-stat#STATFILE#
$InputFileSeverity debug
$InputRunFileMonitor

"""


def createEventFileSettings(tree, files):
    fileid = 0
    sysconfig = """
$ModLoad imfile

                """
    if not files:
        return
    for item in files:
        fileid += 1
        eventSourceElement = XmlUtil.createElement(eventSourceSchema)
        XmlUtil.setXmlValue(eventSourceElement, 'RouteEvent', 'eventName', item["table"])
        eventSourceElement.set('source', 'ladfile' + str(fileid))
        XmlUtil.addElement(tree, 'Events/MdsdEvents', eventSourceElement)

        sourceElement = XmlUtil.createElement(sourceSchema)
        sourceElement.set('name', 'ladfile' + str(fileid))
        XmlUtil.addElement(tree, 'Sources', sourceElement)

        syslog_config = syslogEventSourceConfig.replace('#FILE#', item['file'])
        syslog_config = syslog_config.replace('#STATFILE#', item['file'].replace("/", "-"))
        syslog_config = syslog_config.replace('#FILETAG#', 'ladfile' + str(fileid))
        sysconfig += syslog_config
    return sysconfig


perfSchema = """
    <OMIQuery cqlQuery=""
      dontUsePerNDayTable="true" eventName="" omiNamespace="" priority="High" sampleRateInSeconds="" />
    """


def createPerfSettngs(tree, perfs, forAI=False):
    if not perfs:
        return
    for perf in perfs:
        perfElement = XmlUtil.createElement(perfSchema)
        perfElement.set('cqlQuery', perf['query'])
        perfElement.set('eventName', perf['table'])
        namespace = "root/scx"
        if perf.has_key('namespace'):
            namespace = perf['namespace']
        perfElement.set('omiNamespace', namespace)
        if forAI:
            AIUtil.updateOMIQueryElement(perfElement)
        XmlUtil.addElement(xml=tree, path='Events/OMI', el=perfElement, addOnlyOnce=True)


def createAccountSettings(tree, account, key, token, endpoint, aikey=None):
    """
    Update the MDSD configuration Account element with Azure table storage properties.
    Exactly one of (key, token) must be provided. If an aikey is passed, then add a new Account element for Application
    Insights with the application insights key.
    :param tree: The XML doc to be updated.
    :param account: Storage account to which LAD should write data
    :param key: Shared key secret for the storage account, if present
    :param token: SAS token to access the storage account, if present
    :param endpoint: Identifies the Azure instance (public or specific sovereign cloud) where the storage account is
    :param aikey: Key for accessing AI, if present
    """
    assert key or token, "Either key or token must be given."

    def get_handler_cert_pkey_paths():
        handler_settings = hutil.get_handler_settings()
        thumbprint = handler_settings['protectedSettingsCertThumbprint']
        cert_path = waagent.LibDir + '/' + thumbprint + '.crt'
        pkey_path = waagent.LibDir + '/' + thumbprint + '.prv'
        return cert_path, pkey_path

    def encrypt_secret_with_cert(cert_path, secret):
        encrypted_secret_tmp_file_path = os.path.join(WorkDir, "mdsd_secret.bin")
        cmd = "echo -n '{0}' | openssl smime -encrypt -outform DER -out {1} {2}"
        cmd_to_run = cmd.format(secret, encrypted_secret_tmp_file_path, cert_path)
        ret_status, ret_msg = RunGetOutput(cmd_to_run, should_log=False)
        if ret_status is not 0:
            hutil.error("Encrypting storage secret failed with the following message: " + ret_msg)
            return None
        with open(encrypted_secret_tmp_file_path, 'rb') as f:
            encrypted_secret = f.read()
        os.remove(encrypted_secret_tmp_file_path)
        return binascii.b2a_hex(encrypted_secret).upper()

    handler_cert_path, handler_pkey_path = get_handler_cert_pkey_paths()
    if key:
        key = encrypt_secret_with_cert(handler_cert_path, key)
        XmlUtil.setXmlValue(tree, 'Accounts/Account', "account", account, ['isDefault', 'true'])
        XmlUtil.setXmlValue(tree, 'Accounts/Account', "key", key, ['isDefault', 'true'])
        XmlUtil.setXmlValue(tree, 'Accounts/Account', "decryptKeyPath", handler_pkey_path, ['isDefault', 'true'])
        XmlUtil.setXmlValue(tree, 'Accounts/Account', "tableEndpoint", endpoint, ['isDefault', 'true'])
        XmlUtil.removeElement(tree, 'Accounts', 'SharedAccessSignature')
    else:  # token
        token = encrypt_secret_with_cert(handler_cert_path, token)
        XmlUtil.setXmlValue(tree, 'Accounts/SharedAccessSignature', "account", account, ['isDefault', 'true'])
        XmlUtil.setXmlValue(tree, 'Accounts/SharedAccessSignature', "key", token, ['isDefault', 'true'])
        XmlUtil.setXmlValue(tree, 'Accounts/SharedAccessSignature', "decryptKeyPath", handler_pkey_path,
                            ['isDefault', 'true'])
        XmlUtil.setXmlValue(tree, 'Accounts/SharedAccessSignature', "tableEndpoint", endpoint, ['isDefault', 'true'])
        XmlUtil.removeElement(tree, 'Accounts', 'Account')

    if aikey:
        AIUtil.createAccountElement(tree, aikey)


def config(xmltree, key, value, xmlpath, selector=[]):
    v = readPublicConfig(key)
    if not v:
        v = value
    XmlUtil.setXmlValue(xmltree, xmlpath, key, v, selector)


def generatePerformanceCounterConfiguration(mdsdCfg, includeAI=False):
    perfCfgList = []
    try:
        ladCfg = readPublicConfig('ladCfg')
        perfCfgList = LadUtil.generatePerformanceCounterConfigurationFromLadCfg(ladCfg)
        if not perfCfgList:
            perfCfgList = readPublicConfig('perfCfg')
        if not perfCfgList and not hasPublicConfig('perfCfg'):
            perfCfgList = [
                {
                    "query": "SELECT PercentAvailableMemory, AvailableMemory, UsedMemory, PercentUsedSwap FROM SCX_MemoryStatisticalInformation",
                    "table": "LinuxMemory"},
                {
                    "query": "SELECT PercentProcessorTime, PercentIOWaitTime, PercentIdleTime FROM SCX_ProcessorStatisticalInformation WHERE Name='_TOTAL'",
                    "table": "LinuxCpu"},
                {
                    "query": "SELECT AverageWriteTime,AverageReadTime,ReadBytesPerSecond,WriteBytesPerSecond FROM  SCX_DiskDriveStatisticalInformation WHERE Name='_TOTAL'",
                    "table": "LinuxDisk"}
            ]
    except Exception as e:
        hutil.error(
            "Failed to parse performance configuration with exception:{0} {1}".format(e, traceback.format_exc()))

    try:
        createPerfSettngs(mdsdCfg,perfCfgList)
        if includeAI:
            createPerfSettngs(mdsdCfg,perfCfgList,True)
    except Exception as e:
        hutil.error("Failed to create perf config  error:{0} {1}".format(e, traceback.format_exc()))


# Try to get resourceId from LadCfg, if not present
# try to fetch from xmlCfg
def getResourceId():
    ladCfg = readPublicConfig('ladCfg')
    resourceId = LadUtil.getResourceIdFromLadCfg(ladCfg)
    if not resourceId:
        encodedXmlCfg = readPublicConfig('xmlCfg').strip()
        if encodedXmlCfg:
            xmlCfg = base64.b64decode(encodedXmlCfg)
            resourceId = XmlUtil.getXmlValue(XmlUtil.createElement(xmlCfg), 'diagnosticMonitorConfiguration/metrics',
                                             'resourceId')
            # Azure portal uses xmlCfg which contains WadCfg which is pascal case, Currently we will support both
            # casing and deprecate one later
            if not resourceId:
                resourceId = XmlUtil.getXmlValue(XmlUtil.createElement(xmlCfg),
                                                 'DiagnosticMonitorConfiguration/Metrics', 'resourceId')
    return resourceId


def getSyslogCfg():
    """
    Try to get syslogCfg from LadCfg, if not present fetch it from public settings
    :return: Configuration string for syslog, or empty string
    """
    syslogCfg = ""
    ladCfg = readPublicConfig('ladCfg')
    encodedSyslogCfg = LadUtil.getDiagnosticsMonitorConfigurationElement(ladCfg, 'syslogCfg')
    if not encodedSyslogCfg:
        encodedSyslogCfg = readPublicConfig('syslogCfg')
    if encodedSyslogCfg:
        syslogCfg = base64.b64decode(encodedSyslogCfg)
    return syslogCfg


def getFileCfg():
    """
    Try to get fileCfg from LadCfg, if not present fetch it from public settings
    :return: fileCfg, or None if not set anywhere in the public config
    """
    ladCfg = readPublicConfig('ladCfg')
    fileCfg = LadUtil.getFileCfgFromLadCfg(ladCfg)
    if not fileCfg:
        fileCfg = readPublicConfig('fileCfg')
    return fileCfg


def setEventVolume(mdsdCfg, ladCfg):
    """
    Set event volume in mdsd config. Check if desired event volume is specified, first in ladCfg then in public config.
    :param mdsdCfg: The XML document holding the mdsd config
    :param ladCfg: The ladCfg part of the public config
    :return: The event volume. If not set anywhere in public config, return "Medium"
    :rtype: str
    """
    eventVolume = LadUtil.getEventVolumeFromLadCfg(ladCfg)
    if eventVolume:
        hutil.log("Event volume found in ladCfg: " + eventVolume)
    else:
        eventVolume = readPublicConfig("eventVolume")
        if eventVolume:
            hutil.log("Event volume found in public config: " + eventVolume)
        else:
            eventVolume = "Medium"
            hutil.log("Event volume not found in config. Using default value: " + eventVolume)

    XmlUtil.setXmlValue(mdsdCfg, "Management", "eventVolume", eventVolume)


def configSettings():
    """
    Generates XML cfg file for mdsd, from JSON config settings (public & private).
    Returns (True, '') if config was valid and proper xmlCfg.xml was generated.
    Returns (False, '...') if config was invalid and the error message.
    """
    mdsdCfgstr = readPublicConfig('mdsdCfg')
    if not mdsdCfgstr:
        with open(os.path.join(WorkDir, './mdsdConfig.xml.template'), "r") as defaulCfg:
            mdsdCfgstr = defaulCfg.read()
    else:
        mdsdCfgstr = base64.b64decode(mdsdCfgstr)
    mdsdCfg = ET.ElementTree()
    mdsdCfg._setroot(XmlUtil.createElement(mdsdCfgstr))

    # Add DeploymentId (if available) to identity columns
    deployment_id = get_deployment_id()
    if deployment_id:
        XmlUtil.setXmlValue(mdsdCfg, "Management/Identity/IdentityComponent", "", deployment_id,
                            ["name", "DeploymentId"])

    try:
        resourceId = getResourceId()
        if resourceId:
            createPortalSettings(mdsdCfg, escape_nonalphanumerics(resourceId))
            instanceID = ""
            if resourceId.find("providers/Microsoft.Compute/virtualMachineScaleSets") >= 0:
                instanceID = read_uuid(waagent.RunGetOutput)
            config(mdsdCfg, "instanceID", instanceID, "Events/DerivedEvents/DerivedEvent/LADQuery")

    except Exception as e:
        hutil.error("Failed to create portal config  error:{0} {1}".format(e, traceback.format_exc()))

    # Check if Application Insights key is present in ladCfg
    ladCfg = readPublicConfig('ladCfg')
    do_ai = False
    aikey = None
    try:
        aikey = AIUtil.tryGetAiKey(ladCfg)
        if aikey:
            hutil.log("Application Insights key found.")
            do_ai = True
        else:
            hutil.log("Application Insights key not found.")
    except Exception as e:
        msg = "Failed check for Application Insights key in LAD configuration with exception:{0} {1}"
        hutil.error(msg.format(e, traceback.format_exc()))

    generatePerformanceCounterConfiguration(mdsdCfg, do_ai)

    syslogCfg = getSyslogCfg()
    fileCfg = getFileCfg()
    # fileCfg = [{"file":"/var/log/waagent.log","table":"waagent"},{"file":"/var/log/waagent2.log","table":"waagent3"}]
    try:
        if fileCfg:
            syslogCfg = createEventFileSettings(mdsdCfg, fileCfg) + syslogCfg

        with open(omfileconfig, 'w') as hfile:
            hfile.write(syslogCfg)
    except Exception as e:
        hutil.error("Failed to create syslog_file config  error:{0} {1}".format(e, traceback.format_exc()))

    log_private_settings_keys(private_settings, hutil.log, hutil.error)

    account = readPrivateConfig('storageAccountName')
    if not account:
        return False, "Empty storageAccountName"
    key = readPrivateConfig('storageAccountKey')
    token = readPrivateConfig('storageAccountSasToken')
    if not key and not token:
        return False, "Neither storageAccountKey nor storageAccountSasToken is given"
    if key and token:
        return False, "Either storageAccountKey or storageAccountSasToken (but not both) should be given"
    endpoint = get_storage_endpoint_with_account(account, readPrivateConfig('storageAccountEndPoint'))

    createAccountSettings(mdsdCfg, account, key, token, endpoint, aikey)

    # Check and add new syslog RouteEvent for Application Insights.
    if aikey:
        AIUtil.createSyslogRouteEventElement(mdsdCfg)

    setEventVolume(mdsdCfg, ladCfg)

    config(mdsdCfg, "sampleRateInSeconds", "60", "Events/OMI/OMIQuery")

    mdsdCfg.write(os.path.join(WorkDir, './xmlCfg.xml'))

    return True, ""


def install_service():
    RunGetOutput('sed s#{WORKDIR}#' + WorkDir + '# ' +
                 WorkDir + '/services/mdsd-lde.service > /lib/systemd/system/mdsd-lde.service')
    RunGetOutput('systemctl daemon-reload')


def main(command):
    init_globals()

    global EnableSyslog, ExtensionOperationType

    # 'enableSyslog' is to be used for consistency, but we've had 'EnableSyslog' all the time, so accommodate it.
    EnableSyslog = readPublicConfig('enableSyslog').lower() != 'false' and readPublicConfig(
        'EnableSyslog').lower() != 'false'

    ExtensionOperationType = get_extension_operation_type(command)

    config_valid, config_invalid_reason = configSettings()
    if not config_valid:
        config_invalid_log = "Invalid config settings given: " + config_invalid_reason + \
                             ". Install will proceed, but enable can't proceed, " \
                             "in which case it's still considered a success as it's an external error."
        hutil.log(config_invalid_log)
        if ExtensionOperationType is waagent.WALAEventOperation.Enable:
            hutil.do_status_report(ExtensionOperationType, "success", '0', config_invalid_log)
            waagent.AddExtensionEvent(name=hutil.get_name(),
                                      op=ExtensionOperationType,
                                      isSuccess=True,
                                      version=hutil.get_extension_version(),
                                      message=config_invalid_log)
            return

    for notsupport in ('WALinuxAgent-2.0.5', 'WALinuxAgent-2.0.4', 'WALinuxAgent-1'):
        code, str_ret = waagent.RunGetOutput("grep 'GuestAgentVersion.*" + notsupport + "' /usr/sbin/waagent",
                                             chk_err=False)
        if code == 0 and str_ret.find(notsupport) > -1:
            hutil.log("cannot run this extension on  " + notsupport)
            hutil.do_status_report(ExtensionOperationType, "error", '1', "cannot run this extension on  " + notsupport)
            return

    if distConfig is None:
        msg = ("LAD does not support distro/version ({0}); not installed. This extension install/enable operation is "
               "still considered a success as it's an external error.").format(str(platform.dist()))
        hutil.log(msg)
        hutil.do_status_report(ExtensionOperationType, "success", '0', msg)
        waagent.AddExtensionEvent(name=hutil.get_name(),
                                  op=ExtensionOperationType,
                                  isSuccess=True,
                                  version=hutil.get_extension_version(),
                                  message="Can't be installed on this OS " + str(platform.dist()))
        return
    try:
        hutil.log("Dispatching command:" + command)

        if ExtensionOperationType is waagent.WALAEventOperation.Disable:
            if distConfig.use_systemd():
                RunGetOutput('systemctl stop mdsd-lde && systemctl disable mdsd-lde')
            else:
                stop_mdsd()
            hutil.do_status_report(ExtensionOperationType, "success", '0', "Disable succeeded")

        elif ExtensionOperationType is waagent.WALAEventOperation.Uninstall:
            if distConfig.use_systemd():
                RunGetOutput('systemctl stop mdsd-lde && systemctl disable mdsd-lde ' +
                             '&& rm /lib/systemd/system/mdsd-lde.service')
            else:
                stop_mdsd()
            uninstall_omi()
            if EnableSyslog:
                uninstall_rsyslogom()
            hutil.do_status_report(ExtensionOperationType, "success", '0', "Uninstall succeeded")

        elif ExtensionOperationType is waagent.WALAEventOperation.Install:
            if distConfig.use_systemd():
                install_service()
            hutil.do_status_report(ExtensionOperationType, "success", '0', "Install succeeded")

        elif ExtensionOperationType is waagent.WALAEventOperation.Enable:
            if distConfig.use_systemd():
                install_service()
                RunGetOutput('systemctl enable mdsd-lde')
                mdsd_lde_active = RunGetOutput('systemctl status mdsd-lde')[0] is 0
                if not mdsd_lde_active or hutil.is_current_config_seq_greater_inused():
                    RunGetOutput('systemctl restart mdsd-lde')
            else:
                # if daemon process not runs
                mdsd_procs = get_mdsd_process()
                hutil.log("get pid:" + str(mdsd_procs))
                if len(mdsd_procs) != 2 or hutil.is_current_config_seq_greater_inused():
                    stop_mdsd()
                    start_daemon()
            hutil.set_inused_config_seq(hutil.get_seq_no())
            hutil.do_status_report(ExtensionOperationType, "success", '0', "Enable succeeded")

        elif ExtensionOperationType is "Daemon":
            start_mdsd()

        elif ExtensionOperationType is waagent.WALAEventOperation.Update:
            hutil.do_status_report(ExtensionOperationType, "success", '0', "Update succeeded")

    except Exception as e:
        hutil.error("Failed to perform extension operation {0} with error:{1}, {2}".format(ExtensionOperationType, e,
                                                                                           traceback.format_exc()))
        hutil.do_status_report(ExtensionOperationType, 'error', '0',
                               'Extension operation {0} failed:{1}'.format(ExtensionOperationType, e))


def update_selinux_settings_for_rsyslogomazuremds():
    # This is still needed for Redhat-based distros, which still require SELinux to be allowed
    # for even Unix domain sockets.
    # Anyway, we no longer use 'semanage' (so no need to install policycoreutils-python).
    # We instead compile from the bundled SELinux module def for lad_mdsd
    # TODO Either check the output of these commands or run without capturing output
    if os.path.exists("/usr/sbin/semodule") or os.path.exists("/sbin/semodule"):
        RunGetOutput('checkmodule -M -m -o {0}/lad_mdsd.mod {1}/lad_mdsd.te'.format(WorkDir, WorkDir))
        RunGetOutput('semodule_package -o {0}/lad_mdsd.pp -m {1}/lad_mdsd.mod'.format(WorkDir, WorkDir))
        RunGetOutput('semodule -u {0}/lad_mdsd.pp'.format(WorkDir))


def start_daemon():
    args = ['python', StartDaemonFilePath, "-daemon"]
    log = open(os.path.join(os.getcwd(), 'daemon.log'), 'w')
    hutil.log('start daemon ' + str(args))
    subprocess.Popen(args, stdout=log, stderr=log)
    wait_n = 20
    while len(get_mdsd_process()) == 0 and wait_n > 0:
        time.sleep(5)
        wait_n -= 1
    if wait_n <= 0:
        hutil.error("wait daemon start time out")


def start_watcher_thread():
    # Create monitor object that encapsulates monitoring activities
    watcher = watcherutil.Watcher(hutil.error, hutil.log, log_to_console=True)
    # Create an IMDS data logger and set it to the monitor object
    imds_logger = ImdsLogger(hutil.get_name(), hutil.get_extension_version(),
                             waagent.WALAEventOperation.HeartBeat, waagent.AddExtensionEvent)
    watcher.set_imds_logger(imds_logger)
    # Start a thread to perform periodic monitoring activity (e.g., /etc/fstab watcher, IMDS data logging)
    threadObj = threading.Thread(target=watcher.watch)
    threadObj.daemon = True
    threadObj.start()


def start_mdsd():
    global EnableSyslog, ExtensionOperationType
    with open(MDSDPidFile, "w") as pidfile:
        pidfile.write(str(os.getpid()) + '\n')
        pidfile.close()

    # Assign correct ext op type for correct ext status/event reporting.
    # start_mdsd() is called only through "./diagnostic.py -daemon"
    # which has to be recognized as "Daemon" ext op type, but it's not a standard Azure ext op
    # type, so it needs to be reverted back to a standard one (which is "Enable").
    ExtensionOperationType = waagent.WALAEventOperation.Enable

    dependencies_err, dependencies_msg = setup_dependencies_and_mdsd()
    if dependencies_err != 0:
        dependencies_err_log_msg = "Failed to set up mdsd dependencies: {0}".format(dependencies_msg)
        hutil.error(dependencies_err_log_msg)
        hutil.do_status_report(ExtensionOperationType, 'error', '1', dependencies_err_log_msg)
        waagent.AddExtensionEvent(name=hutil.get_name(),
                                  op=ExtensionOperationType,
                                  isSuccess=False,
                                  version=hutil.get_extension_version(),
                                  message=dependencies_err_log_msg)
        return

    # Start OMI if it's not running.
    # This shouldn't happen, but this measure is put in place just in case (e.g., Ubuntu 16.04 systemd).
    # Don't check if starting succeeded, as it'll be done in the loop below anyway.
    omi_running = RunGetOutput("/opt/omi/bin/service_control is-running")[0] is 1
    if not omi_running:
        RunGetOutput("/opt/omi/bin/service_control restart")

    if not EnableSyslog:
        uninstall_rsyslogom()

    log_dir = hutil.get_log_dir()
    monitor_file_path = os.path.join(log_dir, 'mdsd.err')
    info_file_path = os.path.join(log_dir, 'mdsd.info')
    warn_file_path = os.path.join(log_dir, 'mdsd.warn')

    update_selinux_settings_for_rsyslogomazuremds()

    mdsd_log_path = os.path.join(WorkDir, "mdsd.log")
    mdsd_log = None
    copy_env = os.environ
    copy_env['LD_LIBRARY_PATH'] = MdsdFolder
    distConfig.extend_environment(copy_env)

    # mdsd http proxy setting
    proxy_config_name = 'mdsdHttpProxy'
    proxy_config = waagent.HttpProxyConfigString  # /etc/waagent.conf has highest priority
    if not proxy_config:
        proxy_config = readPrivateConfig(proxy_config_name)  # Private (protected) setting has next priority
    if not proxy_config:
        proxy_config = readPublicConfig(proxy_config_name)
    if not isinstance(proxy_config, basestring):
        hutil.log("Error: mdsdHttpProxy config is not a string. Ignored.")
    else:
        proxy_config = proxy_config.strip()
        if proxy_config:
            hutil.log(
                "mdsdHttpProxy setting was given and will be passed to mdsd, but not logged here in case there's a password in it")
            copy_env['MDSD_http_proxy'] = proxy_config

    xml_file = os.path.join(WorkDir, './xmlCfg.xml')

    # We now validate the config and proceed only when it succeeds.
    config_validate_cmd = '{0} -v -c {1}'.format(os.path.join(MdsdFolder, "mdsd"), xml_file)
    config_validate_cmd_status, config_validate_cmd_msg = RunGetOutput(config_validate_cmd)
    if config_validate_cmd_status is not 0:
        # Invalid config. Log error and report success.
        message = "Invalid mdsd config given. Can't enable. This extension install/enable operation is reported as " \
            "successful so the VM can complete successful startup. Linux Diagnostic Extension will exit. " \
            "Config validation message: {0}."
        hutil.log(message.format(config_validate_cmd_msg))
        # No need to do success status report (it's already done). Just silently return.
        return

    # Config validated. Prepare actual mdsd cmdline.
    command = '{0} -A -C -c {1} -p {2} -R -r {3} -e {4} -w {5} -o {6}'.format(
        os.path.join(MdsdFolder, "mdsd"),
        xml_file,
        MDSD_LISTEN_PORT,
        MDSDRoleName,
        monitor_file_path,
        warn_file_path,
        info_file_path).split(" ")

    try:
        start_watcher_thread()

        num_quick_consecutive_crashes = 0

        while num_quick_consecutive_crashes < 3:  # We consider only quick & consecutive crashes for retries

            RunGetOutput("rm -f " + MDSDPidPortFile)  # Must delete any existing port num file
            mdsd_log = open(mdsd_log_path, "w")
            hutil.log("Start mdsd " + str(command))
            mdsd = subprocess.Popen(command,
                                    cwd=WorkDir,
                                    stdout=mdsd_log,
                                    stderr=mdsd_log,
                                    env=copy_env)

            with open(MDSDPidFile, "w") as pidfile:
                pidfile.write(str(os.getpid()) + '\n')
                pidfile.write(str(mdsd.pid) + '\n')
                pidfile.close()

            last_mdsd_start_time = datetime.datetime.now()
            last_error_time = last_mdsd_start_time
            omi_installed = True
            omicli_path = "/opt/omi/bin/omicli"
            omicli_noop_query_cmd = omicli_path + " noop"
            # Continuously monitors mdsd process
            while True:
                time.sleep(30)
                if " ".join(get_mdsd_process()).find(str(mdsd.pid)) < 0 and len(get_mdsd_process()) >= 2:
                    mdsd.kill()
                    hutil.log("Another process is started, now exit")
                    return
                if mdsd.poll() is not None:  # if mdsd has terminated
                    time.sleep(60)
                    mdsd_log.flush()
                    break

                # mdsd is now up for at least 30 seconds.

                # Mitigate if memory leak is suspected.
                mdsd_memory_leak_suspected, mdsd_memory_usage_in_KB = check_suspected_memory_leak(mdsd.pid, hutil.error)
                if mdsd_memory_leak_suspected:
                    memory_leak_msg = "Suspected mdsd memory leak (Virtual memory usage: {0}MB). " \
                                      "Recycling mdsd to self-mitigate.".format(int((mdsd_memory_usage_in_KB+1023)/1024))
                    hutil.log(memory_leak_msg)
                    # Add a telemetry for a possible statistical analysis
                    waagent.AddExtensionEvent(name=hutil.get_name(),
                                              op=waagent.WALAEventOperation.HeartBeat,
                                              isSuccess=True,
                                              version=hutil.get_extension_version(),
                                              message=memory_leak_msg)
                    mdsd.kill()
                    break

                # Issue #128 LAD should restart OMI if it crashes
                omi_was_installed = omi_installed  # Remember the OMI install status from the last iteration
                omi_installed = os.path.isfile(omicli_path)

                if omi_was_installed and not omi_installed:
                    hutil.log(
                        "OMI is uninstalled. This must have been intentional and externally done. Will no longer check if OMI is up and running.")

                omi_reinstalled = not omi_was_installed and omi_installed
                if omi_reinstalled:
                    hutil.log("OMI is reinstalled. Will resume checking if OMI is up and running.")

                should_restart_omi = False
                if omi_installed:
                    cmd_exit_status, cmd_output = RunGetOutput(cmd=omicli_noop_query_cmd, should_log=False)
                    should_restart_omi = cmd_exit_status is not 0
                    if should_restart_omi:
                        hutil.error(
                            "OMI noop query failed. Output: " + cmd_output + ". OMI crash suspected. Restarting OMI and sending SIGHUP to mdsd after 5 seconds.")
                        omi_restart_msg = RunGetOutput("/opt/omi/bin/service_control restart")[1]
                        hutil.log("OMI restart result: " + omi_restart_msg)
                        time.sleep(5)

                should_signal_mdsd = should_restart_omi or omi_reinstalled
                if should_signal_mdsd:
                    omi_up_and_running = RunGetOutput(omicli_noop_query_cmd)[0] is 0
                    if omi_up_and_running:
                        mdsd.send_signal(signal.SIGHUP)
                        hutil.log("SIGHUP sent to mdsd")
                    else:  # OMI restarted but not staying up...
                        log_msg = "OMI restarted but not staying up. Will be restarted in the next iteration."
                        hutil.error(log_msg)
                        # Also log this issue on syslog as well
                        syslog.openlog('diagnostic.py', syslog.LOG_PID,
                                       syslog.LOG_DAEMON)  # syslog.openlog(ident, logoption, facility) -- not taking kw args in Python 2.6
                        syslog.syslog(syslog.LOG_ALERT,
                                      log_msg)  # syslog.syslog(priority, message) -- not taking kw args
                        syslog.closelog()

                if not os.path.exists(monitor_file_path):
                    continue
                monitor_file_ctime = datetime.datetime.strptime(time.ctime(int(os.path.getctime(monitor_file_path))),
                                                                "%a %b %d %H:%M:%S %Y")
                if last_error_time >= monitor_file_ctime:
                    continue
                last_error_time = monitor_file_ctime
                last_error = tail(monitor_file_path)
                if len(last_error) > 0 and (datetime.datetime.now() - last_error_time) < datetime.timedelta(minutes=30):
                    hutil.log("Error in MDSD:" + last_error)
                    hutil.do_status_report(ExtensionOperationType, "success", '1',
                                           "message in /var/log/mdsd.err:" + str(last_error_time) + ":" + last_error)

            # mdsd terminated.
            if mdsd_log:
                mdsd_log.close()
                mdsd_log = None

            # Check if this is NOT a quick crash -- we consider a crash quick
            # if it's within 30 minutes from the start time. If it's not quick,
            # we just continue by restarting mdsd.
            mdsd_up_time = datetime.datetime.now() - last_mdsd_start_time
            if mdsd_up_time > datetime.timedelta(minutes=30):
                mdsd_terminated_msg = "MDSD terminated after " + str(mdsd_up_time) + ". " + tail(mdsd_log_path) + tail(
                    monitor_file_path)
                hutil.log(mdsd_terminated_msg)
                num_quick_consecutive_crashes = 0
                continue

            # It's a quick crash. Log error and add an extension event.
            num_quick_consecutive_crashes += 1

            error = "MDSD crash(uptime=" + str(mdsd_up_time) + "):" + tail(mdsd_log_path) + tail(monitor_file_path)
            hutil.error("MDSD crashed:" + error)

            # Needs to reset rsyslog omazurelinuxmds config before retrying mdsd
            install_rsyslogom()

        # mdsd all 3 allowed quick/consecutive crashes exhausted
        hutil.do_status_report(ExtensionOperationType, "error", '1', "mdsd stopped:" + error)

        try:
            waagent.AddExtensionEvent(name=hutil.get_name(),
                                      op=ExtensionOperationType,
                                      isSuccess=False,
                                      version=hutil.get_extension_version(),
                                      message=error)
        except Exception:
            pass

    except Exception as e:
        if mdsd_log:
            hutil.error("Error :" + tail(mdsd_log_path))
        hutil.error(("Failed to launch mdsd with error:{0},"
                     "stacktrace:{1}").format(e, traceback.format_exc()))
        hutil.do_status_report(ExtensionOperationType, 'error', '1', 'Launch script failed:{0}'.format(e))
        waagent.AddExtensionEvent(name=hutil.get_name(),
                                  op=ExtensionOperationType,
                                  isSuccess=False,
                                  version=hutil.get_extension_version(),
                                  message="Launch script failed:" + str(e))
    finally:
        if mdsd_log:
            mdsd_log.close()


def stop_mdsd():
    pids = get_mdsd_process()
    if not pids:
        return 0, "Already stopped"

    kill_cmd = "kill " + " ".join(pids)
    hutil.log(kill_cmd)
    RunGetOutput(kill_cmd)

    terminated = False
    num_checked = 0
    while not terminated and num_checked < 10:
        time.sleep(2)
        num_checked += 1
        pids = get_mdsd_process()
        if not pids:
            hutil.log("stop_mdsd(): All processes successfully terminated")
            terminated = True
        else:
            hutil.log("stop_mdsd() terminate check #{0}: Processes not terminated yet, rechecking in 2 seconds".format(
                num_checked))

    if not terminated:
        kill_cmd = "kill -9 " + " ".join(get_mdsd_process())
        hutil.log("stop_mdsd(): Processes not terminated in 20 seconds. Sending SIGKILL (" + kill_cmd + ")")
        RunGetOutput(kill_cmd)

    RunGetOutput("rm " + MDSDPidFile)

    return 0, "Terminated" if terminated else "SIGKILL'ed"


def get_mdsd_process():
    mdsd_pids = []
    if not os.path.exists(MDSDPidFile):
        return mdsd_pids

    with open(MDSDPidFile, "r") as pidfile:
        for pid in pidfile.readlines():
            is_still_alive = waagent.RunGetOutput("cat /proc/" + pid.strip() + "/cmdline", chk_err=False)[1]
            if is_still_alive.find('/waagent/') > 0:
                mdsd_pids.append(pid.strip())
            else:
                hutil.log("return not alive " + is_still_alive.strip())
    return mdsd_pids


def install_omi():
    need_fresh_install_omi = not os.path.exists('/opt/omi/bin/omiserver')

    isMysqlInstalled = RunGetOutput("which mysql")[0] is 0
    isApacheInstalled = RunGetOutput("which apache2 || which httpd || which httpd2")[0] is 0

    # Explicitly uninstall apache-cimprov & mysql-cimprov on rpm-based distros
    # to avoid hitting the scx upgrade issue (from 1.6.2-241 to 1.6.2-337)
    omi_version = RunGetOutput('/opt/omi/bin/omiserver -v', should_log=False)[1]
    if 'OMI-1.0.8-4' in omi_version and distConfig.is_package_handler('rpm'):
        RunGetOutput('rpm --erase apache-cimprov', should_log=False)
        RunGetOutput('rpm --erase mysql-cimprov', should_log=False)

    need_install_omi = ('OMI-1.0.8-6' not in omi_version) \
        or (isMysqlInstalled and not os.path.exists("/opt/microsoft/mysql-cimprov")) \
        or (isApacheInstalled and not os.path.exists("/opt/microsoft/apache-cimprov"))

    if need_install_omi:
        hutil.log("Begin omi installation.")
        is_omi_installed_correctly = False
        maxTries = 5  # Try up to 5 times to install OMI
        for trialNum in range(1, maxTries + 1):
            is_omi_installed_correctly = distConfig.install_omi() is 0
            if is_omi_installed_correctly:
                break
            hutil.error("OMI install failed (trial #" + str(trialNum) + ").")
            if trialNum < maxTries:
                hutil.error("Retrying in 30 seconds...")
                time.sleep(30)
        if not is_omi_installed_correctly:
            hutil.error("OMI install failed " + str(maxTries) + " times. Giving up...")
            return 1, "OMI install failed " + str(maxTries) + " times"

    shouldRestartOmi = False

    # Issue #265. OMI httpsport shouldn't be reconfigured when LAD is re-enabled or just upgraded.
    # In other words, OMI httpsport config should be updated only on a fresh OMI install.
    if need_fresh_install_omi:
        # Check if OMI is configured to listen to any non-zero port and reconfigure if so.
        omi_listens_to_nonzero_port = RunGetOutput(
            r"grep '^\s*httpsport\s*=' /etc/opt/omi/conf/omiserver.conf | grep -v '^\s*httpsport\s*=\s*0\s*$'")[0] is 0
        if omi_listens_to_nonzero_port:
            RunGetOutput(
                "/opt/omi/bin/omiconfigeditor httpsport -s 0 < /etc/opt/omi/conf/omiserver.conf > /etc/opt/omi/conf/omiserver.conf_temp")
            RunGetOutput("mv /etc/opt/omi/conf/omiserver.conf_temp /etc/opt/omi/conf/omiserver.conf")
            shouldRestartOmi = True

    # Quick and dirty way of checking if mysql/apache process is running
    isMysqlRunning = RunGetOutput("ps -ef | grep mysql | grep -v grep")[0] is 0
    isApacheRunning = RunGetOutput("ps -ef | grep -E 'httpd|apache2' | grep -v grep")[0] is 0

    if os.path.exists("/opt/microsoft/mysql-cimprov/bin/mycimprovauth") and isMysqlRunning:
        mysqladdress = readPrivateConfig("mysqladdress")
        mysqlusername = readPrivateConfig("mysqlusername")
        mysqlpassword = readPrivateConfig("mysqlpassword")
        RunGetOutput(
            "/opt/microsoft/mysql-cimprov/bin/mycimprovauth default " + mysqladdress + " " + mysqlusername + " '" + mysqlpassword + "'",
            should_log=False)
        shouldRestartOmi = True

    if os.path.exists("/opt/microsoft/apache-cimprov/bin/apache_config.sh") and isApacheRunning:
        RunGetOutput("/opt/microsoft/apache-cimprov/bin/apache_config.sh -c")
        shouldRestartOmi = True

    if shouldRestartOmi:
        RunGetOutput("/opt/omi/bin/service_control restart")

    return 0, "omi installed"


def uninstall_omi():
    isApacheRunning = RunGetOutput("ps -ef | grep -E 'httpd|apache' | grep -v grep")[0] is 0
    if os.path.exists("/opt/microsoft/apache-cimprov/bin/apache_config.sh") and isApacheRunning:
        RunGetOutput("/opt/microsoft/apache-cimprov/bin/apache_config.sh -u")
    hutil.log("omi will not be uninstalled")
    return 0, "do nothing"


rsyslog_om_mdsd_syslog_conf_path = "/etc/rsyslog.d/10-omazurelinuxmds.conf"
rsyslog_om_mdsd_file_conf_path = "/etc/rsyslog.d/10-omazurelinuxmds-fileom.conf"


def uninstall_rsyslogom():
    rsyslog_om_path, rsyslog_version = distConfig.get_rsyslog_info()
    if os.path.exists(rsyslog_om_mdsd_syslog_conf_path):
        cmd = "rm -f {0}/omazuremds.so {1} {2}"
        RunGetOutput(cmd.format(rsyslog_om_path, rsyslog_om_mdsd_syslog_conf_path, rsyslog_om_mdsd_file_conf_path))

    distConfig.restart_rsyslog()

    return 0, "rm omazurelinuxmds done"


def install_rsyslogom():
    rsyslog_om_path, rsyslog_version = distConfig.get_rsyslog_info()
    if rsyslog_om_path is None:
        return 1, "rsyslog not installed"

    if rsyslog_version == '':
        return 1, "rsyslog version can't be detected"
    elif rsyslog_version not in ('5', '7', '8'):
        return 1, "Unsupported rsyslog version ({0})".format(rsyslog_version)

    rsyslog_om_folder = 'rsyslog' + rsyslog_version
    mdsd_socket_path = MDSDFileResourcesPrefix + "_json.socket"

    script = """\
cp -f {0}/omazuremds.so {1};\
rm -f /etc/rsyslog.d/omazurelinuxmds.conf /etc/rsyslog.d/omazurelinuxmds_fileom.conf {2};\
cp -f {3} {4};\
sed 's#__MDSD_SOCKET_FILE_PATH__#{5}#g' {0}/omazurelinuxmds.conf > {2}"""
    cmd = script.format(rsyslog_om_folder, rsyslog_om_path, rsyslog_om_mdsd_syslog_conf_path,
                        omfileconfig, rsyslog_om_mdsd_file_conf_path, mdsd_socket_path)
    RunGetOutput(cmd)

    distConfig.restart_rsyslog()
    return 0, "install mdsdom completed"


def install_required_package():
    return distConfig.install_required_packages()


def get_deployment_id():
    identity = "unknown"
    env_cfg_path = os.path.join(WorkDir, os.pardir, "HostingEnvironmentConfig.xml")
    if not os.path.exists(env_cfg_path):
        hutil.log("No Deployment ID (not running in a hosted environment")
        return None

    try:
        with open(env_cfg_path, 'r') as env_cfg_file:
            xml_text = env_cfg_file.read()
        dom = xml.dom.minidom.parseString(xml_text)
        deployment = dom.getElementsByTagName("Deployment")
        name = deployment[0].getAttribute("name")
        if name:
            identity = name
            hutil.log("Deployment ID found: {0}.".format(identity))
    except Exception as e:
        # use fallback identity
        hutil.error("Failed to retrieve deployment ID. Error:{0} {1}".format(e, traceback.format_exc()))

    return identity


if __name__ == '__main__' :
    if len(sys.argv) <= 1:
        print('No command line argument was specified.\nYou must be executing this program manually for testing.\n'
              'In that case, one of "install", "enable", "disable", "uninstall", or "update" should be given.')
    else:
        try:
            main(sys.argv[1])
        except Exception as e:
            ext_version = ET.parse('manifest.xml').find('{http://schemas.microsoft.com/windowsazure}Version').text
            waagent.AddExtensionEvent(name="Microsoft.OSTCExtension.LinuxDiagnostic",
                                      op=wala_event_type_for_telemetry(get_extension_operation_type(sys.argv[1])),
                                      isSuccess=False,
                                      version=ext_version,
                                      message="Unknown exception thrown from diagnostic.py.\n"
                                              "Error: {0}\nStackTrace: {1}".format(e, traceback.format_exc()))
