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
import datetime
import os
import os.path
import platform
import re
import signal
import string
import subprocess
import sys
import syslog
import time
import traceback
import xml.dom.minidom
import xml.etree.ElementTree as ET

import Utils.HandlerUtil as Util
import Utils.LadDiagnosticUtil as LadUtil
import Utils.XmlUtil as XmlUtil
import Utils.ApplicationInsightsUtil as AIUtil
from Utils.WAAgentUtil import waagent

WorkDir = os.getcwd()
MDSDPidFile = os.path.join(WorkDir, 'mdsd.pid')
MDSDPidPortFile = os.path.join(WorkDir, 'mdsd.pidport')
OutputSize = 1024
EnableSyslog = True
waagent.LoggerInit('/var/log/waagent.log','/dev/stdout')
waagent.Log("LinuxAzureDiagnostic started to handle.")
hutil = Util.HandlerUtility(waagent.Log, waagent.Error)
hutil.try_parse_context()
hutil.set_verbose_log(False)  # Explicitly set verbose flag to False. This is default anyway, but it will be made explicit and logged.
public_settings = hutil.get_public_settings()
private_settings = hutil.get_protected_settings()
if not public_settings:
    public_settings = {}
if not private_settings:
    private_settings = {}
ExtensionOperationType = None
# Better deal with the silly waagent typo, in anticipation of a proper fix of the typo later on waagent
if not hasattr(waagent.WALAEventOperation, 'Uninstall'):
    if hasattr(waagent.WALAEventOperation, 'UnIsntall'):
        waagent.WALAEventOperation.Uninstall = waagent.WALAEventOperation.UnIsntall
    else:  # This shouldn't happen, but just in case...
        waagent.WALAEventOperation.Uninstall = 'Uninstall'

def LogRunGetOutPut(cmd, should_log=True):
    if should_log:
        hutil.log("RunCmd "+cmd)
    error, msg = waagent.RunGetOutput(cmd, chk_err=should_log)
    if should_log:
        hutil.log("Return "+str(error)+":"+msg)
    return error, msg

rsyslog_ommodule_for_check = 'omprog.so'
RunGetOutput = LogRunGetOutPut
MdsdFolder = os.path.join(WorkDir, 'bin')
StartDaemonFilePath = os.path.join(os.getcwd(), __file__)
omi_universal_pkg_name = 'scx-1.6.2-241.universal.x64.sh'

omfileconfig = os.path.join(WorkDir, 'omfileconfig')

DebianConfig = {"installomi":"bash "+omi_universal_pkg_name+" --upgrade;",
                "installrequiredpackage":'dpkg-query -l PACKAGE |grep ^ii ;  if [ ! $? == 0 ]; then apt-get update ; apt-get install -y PACKAGE; fi',
                "packages":(),
                "restartrsyslog":"service rsyslog restart",
                'checkrsyslog':'(dpkg-query -s rsyslog;dpkg-query -L rsyslog) |grep "Version\|'+rsyslog_ommodule_for_check+'"',
                'mdsd_env_vars': {"SSL_CERT_DIR": "/usr/lib/ssl/certs", "SSL_CERT_FILE ": "/usr/lib/ssl/cert.pem"}
                }

RedhatConfig =  {"installomi":"bash "+omi_universal_pkg_name+" --upgrade;",
                 "installrequiredpackage":'rpm -q PACKAGE ;  if [ ! $? == 0 ]; then yum install -y PACKAGE; fi',
                 "packages":('policycoreutils-python',),  # This is needed for /usr/sbin/semanage on Redhat.
                 "restartrsyslog":"service rsyslog restart",
                 'checkrsyslog':'(rpm -qi rsyslog;rpm -ql rsyslog)|grep "Version\\|'+rsyslog_ommodule_for_check+'"',
                 'mdsd_env_vars': {"SSL_CERT_DIR": "/etc/pki/tls/certs", "SSL_CERT_FILE": "/etc/pki/tls/cert.pem"}
                 }

UbuntuConfig1510OrHigher = dict(DebianConfig.items()+
                    {'installrequiredpackages':'[ $(dpkg -l PACKAGES |grep ^ii |wc -l) -eq \'COUNT\' ] '
                        '||apt-get install -y PACKAGES',
                     'packages':()
                    }.items())

# For SUSE11, we need to create a CA certs file for our statically linked OpenSSL 1.0 libs
SUSE11_MDSD_SSL_CERTS_FILE = "/etc/ssl/certs/mdsd-ca-certs.pem"

SuseConfig11 = dict(RedhatConfig.items()+
                  {'installrequiredpackage':'rpm -qi PACKAGE;  if [ ! $? == 0 ]; then zypper --non-interactive install PACKAGE;fi; ',
                   "packages":('rsyslog',),
                   'restartrsyslog':"""\
if [ ! -f /etc/sysconfig/syslog.org_lad ]; then cp /etc/sysconfig/syslog /etc/sysconfig/syslog.org_lad; fi;
sed -i 's/SYSLOG_DAEMON="syslog-ng"/SYSLOG_DAEMON="rsyslogd"/g' /etc/sysconfig/syslog;
service syslog restart""",
                   'mdsd_prep_cmds' :
                        (r'\cp /dev/null {0}'.format(SUSE11_MDSD_SSL_CERTS_FILE),
                         r'chown 0:0 {0}'.format(SUSE11_MDSD_SSL_CERTS_FILE),
                         r'chmod 0644 {0}'.format(SUSE11_MDSD_SSL_CERTS_FILE),
                         r"cat /etc/ssl/certs/????????.[0-9a-f] | sed '/^#/d' >> {0}".format(SUSE11_MDSD_SSL_CERTS_FILE)
                        ),
                   'mdsd_env_vars': {"SSL_CERT_FILE": SUSE11_MDSD_SSL_CERTS_FILE}
                  }.items())

SuseConfig12 = dict(RedhatConfig.items()+
                  {'installrequiredpackage':' rpm -qi PACKAGE; if [ ! $? == 0 ]; then zypper --non-interactive install PACKAGE;fi; ','restartrsyslog':'service syslog restart',
                   "packages":('libgthread-2_0-0','ca-certificates-mozilla','rsyslog'),
                   'mdsd_env_vars': {"SSL_CERT_DIR": "/var/lib/ca-certificates/openssl", "SSL_CERT_FILE": "/etc/ssl/cert.pem"}
                  }.items())

CentosConfig = dict(RedhatConfig.items()+
                    {'installrequiredpackage':'rpm -qi PACKAGE; if [ ! $? == 0 ]; then  yum install  -y PACKAGE; fi',
                     "packages":('policycoreutils-python',)
                    }.items())

RSYSLOG_OM_PORT='29131'
All_Dist= {'debian':DebianConfig,
           'Ubuntu':DebianConfig, 'Ubuntu:15.10':UbuntuConfig1510OrHigher,
           'Ubuntu:16.04' : UbuntuConfig1510OrHigher, 'Ubuntu:16.10' : UbuntuConfig1510OrHigher,
           'redhat':RedhatConfig, 'centos':CentosConfig, 'oracle':RedhatConfig,
           'SuSE:11':SuseConfig11, 'SuSE:12':SuseConfig12, 'SuSE':SuseConfig12}
distConfig = None
dist = platform.dist()
distroNameAndVersion = dist[0] + ":" + dist[1]
if distroNameAndVersion in All_Dist:  # if All_Dist.has_key(distroNameAndVersion):
    distConfig = All_Dist[distroNameAndVersion]
elif All_Dist.has_key(dist[0]):
    distConfig = All_Dist[dist[0]]

if distConfig is None:
    hutil.error("os version:" + distroNameAndVersion + " not supported")

UseSystemdServiceManager = False
if dist[0] == 'Ubuntu' and dist[1] >= '15.10':  # Use systemd for Ubuntu 15.10 or later
    UseSystemdServiceManager = True


def escape(datas):
    s_build=''
    for c in datas:
        if c.isalnum():
            s_build+=c
        else:
            s_build+=":{0:04X}".format(ord(c))
    return s_build

def getChildNode(p,tag):
   for node in p.childNodes:
       if not hasattr(node, 'tagName'):
           continue
       print(str(node.tagName)+":"+tag)
       if node.tagName == tag:
           return node

def parse_context(operation):
    hutil = Util.HandlerUtility(waagent.Log, waagent.Error)
    hutil.try_parse_context()
    return


def setup(should_install_required_package):
    global EnableSyslog

    if should_install_required_package:
        install_package_error = ""
        retry = 3
        while retry > 0:
            error, msg = install_required_package()
            hutil.log(msg)
            if error == 0:
                break
            else:
                retry -= 1
                hutil.log("Sleep 60 retry "+str(retry))
                install_package_error = msg
                time.sleep(60)
        if install_package_error:
            if len(install_package_error) > 1024:
                install_package_error = install_package_error[0:512]+install_package_error[-512:-1]
            hutil.error(install_package_error)
            return 2, install_package_error

    if EnableSyslog:
        error, msg = install_rsyslogom()
        if error != 0:
            hutil.error(msg)
            return 3, msg

    # Run prep commands
    if 'mdsd_prep_cmds' in distConfig:
        for cmd in distConfig['mdsd_prep_cmds']:
            RunGetOutput(cmd)

    omi_err, omi_msg = install_omi()
    if omi_err is not 0:
        return 4, omi_msg

    return 0, 'success'


def hasPublicConfig(key):
    return public_settings.has_key(key)

def readPublicConfig(key):
    if public_settings.has_key(key):
        return public_settings[key]
    return ''

def readPrivateConfig(key):
    if private_settings.has_key(key):
        return private_settings[key]
    return ''

def createPortalSettings(tree,resourceId):
    portal_config = ET.ElementTree()
    portal_config.parse(os.path.join(WorkDir, "portal.xml.template"))
    XmlUtil.setXmlValue(portal_config,"./DerivedEvents/DerivedEvent/LADQuery","partitionKey",resourceId)
    XmlUtil.addElement(tree,'Events',portal_config._root.getchildren()[0])
    XmlUtil.addElement(tree,'Events',portal_config._root.getchildren()[1])


eventSourceSchema = """
 <MdsdEventSource source="ladfile">
     <RouteEvent dontUsePerNDayTable="true" eventName="" priority="High"/>
</MdsdEventSource>
                    """
sourceSchema = """
<Source name="ladfile1" schema="ladfile" />
"""

syslogEventSourceConfig ="""

$InputFileName #FILE#
$InputFileTag #FILETAG#
$InputFileFacility local6
$InputFileStateFile syslog-stat#STATFILE#
$InputFileSeverity debug
$InputRunFileMonitor

"""



def createEventFileSettings(tree,files):
    fileid = 0
    sysconfig = """
$ModLoad imfile

                """
    if not files:
        return
    for file in files:
        fileid=fileid+1
        eventSourceElement = XmlUtil.createElement(eventSourceSchema)
        XmlUtil.setXmlValue(eventSourceElement,'RouteEvent','eventName',file["table"])
        eventSourceElement.set('source','ladfile'+str(fileid))
        XmlUtil.addElement(tree,'Events/MdsdEvents',eventSourceElement)

        sourceElement = XmlUtil.createElement(sourceSchema)
        sourceElement.set('name','ladfile'+str(fileid))
        XmlUtil.addElement(tree,'Sources',sourceElement)

        syslog_config = syslogEventSourceConfig.replace('#FILE#',file['file'])
        syslog_config = syslog_config.replace('#STATFILE#',file['file'].replace("/","-"))
        syslog_config = syslog_config.replace('#FILETAG#','ladfile'+str(fileid))
        sysconfig+=syslog_config
    return sysconfig


perfSchema = """
    <OMIQuery cqlQuery=""
      dontUsePerNDayTable="true" eventName="" omiNamespace="" priority="High" sampleRateInSeconds="" />
    """

def createPerfSettngs(tree,perfs,forAI=False):
    if not perfs:
        return
    for perf in perfs:
        perfElement = XmlUtil.createElement(perfSchema)
        perfElement.set('cqlQuery',perf['query'])
        perfElement.set('eventName',perf['table'])
        namespace="root/scx"
        if perf.has_key('namespace'):
           namespace=perf['namespace']
        perfElement.set('omiNamespace',namespace)
        if forAI:
            AIUtil.updateOMIQueryElement(perfElement)
        XmlUtil.addElement(tree,'Events/OMI',perfElement)

# Updates the MDSD configuration Account elements.
# Updates existing default Account element with Azure table storage properties.
# If an aikey is provided to the function, then it adds a new Account element for
# Application Insights with the application insights key.
def createAccountSettings(tree,account,key,endpoint,aikey=None):
    XmlUtil.setXmlValue(tree,'Accounts/Account',"account",account,['isDefault','true'])
    XmlUtil.setXmlValue(tree,'Accounts/Account',"key",key,['isDefault','true'])
    XmlUtil.setXmlValue(tree,'Accounts/Account',"tableEndpoint",endpoint,['isDefault','true'])
    
    if aikey:
        AIUtil.createAccountElement(tree,aikey)

def config(xmltree,key,value,xmlpath,selector=[]):
    v = readPublicConfig(key)
    if not v:
        v = value
    XmlUtil.setXmlValue(xmltree,xmlpath,key,v,selector)

def readUUID():
     code,str_ret = waagent.RunGetOutput("dmidecode |grep UUID |awk '{print $2}'",chk_err=False)
     return str_ret.strip()

def generatePerformanceCounterConfiguration(mdsdCfg,includeAI=False):
    perfCfgList = []
    try:
        ladCfg = readPublicConfig('ladCfg')
        perfCfgList = LadUtil.generatePerformanceCounterConfigurationFromLadCfg(ladCfg)
        if not perfCfgList:
            perfCfgList = readPublicConfig('perfCfg')
        if not perfCfgList and not hasPublicConfig('perfCfg'):
            perfCfgList = [
                    {"query":"SELECT PercentAvailableMemory, AvailableMemory, UsedMemory ,PercentUsedSwap FROM SCX_MemoryStatisticalInformation","table":"LinuxMemory"},
                    {"query":"SELECT PercentProcessorTime, PercentIOWaitTime, PercentIdleTime FROM SCX_ProcessorStatisticalInformation WHERE Name='_TOTAL'","table":"LinuxCpu"},
                    {"query":"SELECT AverageWriteTime,AverageReadTime,ReadBytesPerSecond,WriteBytesPerSecond FROM  SCX_DiskDriveStatisticalInformation WHERE Name='_TOTAL'","table":"LinuxDisk"}
                  ]
    except Exception as e:
        hutil.error("Failed to parse performance configuration with exception:{0} {1}".format(e,traceback.format_exc()))

    try:
        createPerfSettngs(mdsdCfg,perfCfgList)
        if includeAI:
            createPerfSettngs(mdsdCfg,perfCfgList,True)
    except Exception as e:
        hutil.error("Failed to create perf config  error:{0} {1}".format(e,traceback.format_exc()))

# Try to get resourceId from LadCfg, if not present
# try to fetch from xmlCfg
def getResourceId():
    ladCfg = readPublicConfig('ladCfg')
    resourceId = LadUtil.getResourceIdFromLadCfg(ladCfg)
    if not resourceId:
        encodedXmlCfg = readPublicConfig('xmlCfg').strip()
        if encodedXmlCfg:
            xmlCfg = base64.b64decode(encodedXmlCfg)
            resourceId = XmlUtil.getXmlValue(XmlUtil.createElement(xmlCfg),'diagnosticMonitorConfiguration/metrics','resourceId')
# Azure portal uses xmlCfg which contains WadCfg which is pascal case, Currently we will support both casing and deprecate one later
            if not resourceId:
                resourceId = XmlUtil.getXmlValue(XmlUtil.createElement(xmlCfg),'DiagnosticMonitorConfiguration/Metrics','resourceId')
    return resourceId

# Try to get syslogCfg from LadCfg, if not present
# fetch it from public settings
def getSyslogCfg():
    syslogCfg = ""
    ladCfg = readPublicConfig('ladCfg')
    encodedSyslogCfg = LadUtil.getDiagnosticsMonitorConfigurationElement(ladCfg, 'syslogCfg')
    if not encodedSyslogCfg:
        encodedSyslogCfg = readPublicConfig('syslogCfg')
    if encodedSyslogCfg:
        syslogCfg = base64.b64decode(encodedSyslogCfg)
    return syslogCfg

# Try to get fileCfg from LadCfg, if not present
# fetch it from public settings
def getFileCfg():
    ladCfg = readPublicConfig('ladCfg')
    fileCfg = LadUtil.getFileCfgFromLadCfg(ladCfg)
    if not fileCfg:
        fileCfg = readPublicConfig('fileCfg')
    return fileCfg

# Set event volume in mdsd config.
# Check if desired event volume is specified, first in ladCfg then in public config.
# If in neither then default to Medium.
def setEventVolume(mdsdCfg,ladCfg):
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
            
    XmlUtil.setXmlValue(mdsdCfg,"Management","eventVolume",eventVolume)
        
def configSettings():
    '''
    Generates XML cfg file for mdsd, from JSON config settings (public & private).
    Returns (True, '') if config was valid and proper xmlCfg.xml was generated.
    Returns (False, '...') if config was invalid and the error message.
    '''
    mdsdCfgstr = readPublicConfig('mdsdCfg')
    if not mdsdCfgstr:
        with open(os.path.join(WorkDir, './mdsdConfig.xml.template'),"r") as defaulCfg:
            mdsdCfgstr = defaulCfg.read()
    else:
        mdsdCfgstr = base64.b64decode(mdsdCfgstr)
    mdsdCfg = ET.ElementTree()
    mdsdCfg._setroot(XmlUtil.createElement(mdsdCfgstr))

    # update deployment id
    deployment_id = get_deployment_id()
    XmlUtil.setXmlValue(mdsdCfg, "Management/Identity/IdentityComponent", "", deployment_id, ["name", "DeploymentId"])

    try:
        resourceId = getResourceId()
        if resourceId:
            createPortalSettings(mdsdCfg,escape(resourceId))
            instanceID=""
            if resourceId.find("providers/Microsoft.Compute/virtualMachineScaleSets") >=0:
                instanceID = readUUID()
            config(mdsdCfg,"instanceID",instanceID,"Events/DerivedEvents/DerivedEvent/LADQuery")

    except Exception as e:
        hutil.error("Failed to create portal config  error:{0} {1}".format(e,traceback.format_exc()))
    
    # Check if Application Insights key is present in ladCfg
    ladCfg = readPublicConfig('ladCfg')
    try:
        aikey = AIUtil.tryGetAiKey(ladCfg)
        if aikey:
            hutil.log("Application Insights key found.")
        else:
            hutil.log("Application Insights key not found.")
    except Exception as e:
        hutil.error("Failed check for Application Insights key in LAD configuration with exception:{0} {1}".format(e,traceback.format_exc()))

    generatePerformanceCounterConfiguration(mdsdCfg,aikey != None)

    syslogCfg = getSyslogCfg()
    fileCfg = getFileCfg() 
    #fileCfg = [{"file":"/var/log/waagent.log","table":"waagent"},{"file":"/var/log/waagent2.log","table":"waagent3"}]
    try:
        if fileCfg:
           syslogCfg =  createEventFileSettings(mdsdCfg,fileCfg)+syslogCfg

        with open(omfileconfig,'w') as hfile:
                hfile.write(syslogCfg)
    except Exception as e:
        hutil.error("Failed to create syslog_file config  error:{0} {1}".format(e,traceback.format_exc()))

    account = readPrivateConfig('storageAccountName')
    if not account:
        return False, "Empty storageAccountName"
    key = readPrivateConfig('storageAccountKey')
    if not key:
        return False, "Empty storageAccountKey"
    endpoint = readPrivateConfig('endpoint')
    if not endpoint:
        endpoint = 'table.core.windows.net'
    endpoint = 'https://'+account+"."+endpoint

    createAccountSettings(mdsdCfg,account,key,endpoint,aikey)

    # Check and add new syslog RouteEvent for Application Insights.
    if aikey:
        AIUtil.createSyslogRouteEventElement(mdsdCfg)

    setEventVolume(mdsdCfg,ladCfg)

    config(mdsdCfg,"sampleRateInSeconds","60","Events/OMI/OMIQuery")

    mdsdCfg.write(os.path.join(WorkDir, './xmlCfg.xml'))

    return True, ""

def install_service():
    RunGetOutput('sed s#{WORKDIR}#' + WorkDir + '# ' +
                 WorkDir + '/services/mdsd-lde.service > /lib/systemd/system/mdsd-lde.service')
    RunGetOutput('systemctl daemon-reload')


def get_extension_operation_type(command):
    if re.match("^([-/]*)(enable)", command):
        return waagent.WALAEventOperation.Enable
    if re.match("^([-/]*)(daemon)", command):   # LAD-specific extension operation (invoked from "./diagnostic.py -enable")
        return "Daemon"
    if re.match("^([-/]*)(install)", command):
        return waagent.WALAEventOperation.Install
    if re.match("^([-/]*)(disable)", command):
        return waagent.WALAEventOperation.Disable
    if re.match("^([-/]*)(uninstall)", command):
        return waagent.WALAEventOperation.Uninstall
    if re.match("^([-/]*)(update)", command):
        return waagent.WALAEventOperation.Update


def main(command):
    #Global Variables definition

    global EnableSyslog, UseSystemdServiceManager

    # 'enableSyslog' is to be used for consistency, but we've had 'EnableSyslog' all the time, so accommodate it.
    EnableSyslog = readPublicConfig('enableSyslog').lower() != 'false' and readPublicConfig('EnableSyslog').lower() != 'false'

    ExtensionOperationType = get_extension_operation_type(command)

    config_valid, config_invalid_reason = configSettings()
    if not config_valid:
        config_invalid_log = "Invalid config settings given: " + config_invalid_reason +\
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

    for notsupport in ('WALinuxAgent-2.0.5','WALinuxAgent-2.0.4','WALinuxAgent-1'):
        code, str_ret = waagent.RunGetOutput("grep 'GuestAgentVersion.*" + notsupport + "' /usr/sbin/waagent", chk_err=False)
        if code == 0 and str_ret.find(notsupport) > -1:
            hutil.log("cannot run this extension on  " + notsupport)
            hutil.do_status_report(ExtensionOperationType, "error", '1', "cannot run this extension on  " + notsupport)
            return

    if distConfig is None:
        unsupported_distro_version_log = "LAD can't be installed on this distro/version (" + str(platform.dist()) + "), as it's not supported. This extension install/enable operation is still considered a success as it's an external error."
        hutil.log(unsupported_distro_version_log)
        hutil.do_status_report(ExtensionOperationType, "success", '0', unsupported_distro_version_log)
        waagent.AddExtensionEvent(name=hutil.get_name(),
                                  op=ExtensionOperationType,
                                  isSuccess=True,
                                  version=hutil.get_extension_version(),
                                  message="Can't be installed on this OS "+str(platform.dist()))
        return
    try:
        hutil.log("Dispatching command:" + command)

        if ExtensionOperationType is waagent.WALAEventOperation.Disable:
            if UseSystemdServiceManager:
                RunGetOutput('systemctl stop mdsd-lde && systemctl disable mdsd-lde')
            else:
                stop_mdsd()
            hutil.do_status_report(ExtensionOperationType, "success", '0', "Disable succeeded")

        elif ExtensionOperationType is waagent.WALAEventOperation.Uninstall:
            if UseSystemdServiceManager:
                RunGetOutput('systemctl stop mdsd-lde && systemctl disable mdsd-lde ' +
                             '&& rm /lib/systemd/system/mdsd-lde.service')
            else:
                stop_mdsd()
            uninstall_omi()
            if EnableSyslog:
                uninstall_rsyslogom()
            hutil.do_status_report(ExtensionOperationType, "success", '0', "Uninstall succeeded")

        elif ExtensionOperationType is waagent.WALAEventOperation.Install:
            error, msg = setup(should_install_required_package=True)
            if error != 0:
                hutil.do_status_report(ExtensionOperationType, "error", error, msg)
                waagent.AddExtensionEvent(name=hutil.get_name(),
                                          op=ExtensionOperationType,
                                          isSuccess=False,
                                          version=hutil.get_extension_version(),
                                          message="Install failed: " + msg)
                sys.exit(error)  # Per extension specification, we must exit with a non-zero status code when install fails

            if UseSystemdServiceManager:
                install_service()
            hutil.do_status_report(ExtensionOperationType, "success", '0', "Install succeeded")

        elif ExtensionOperationType is waagent.WALAEventOperation.Enable:
            if UseSystemdServiceManager:
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
        hutil.error(("Failed to perform extension operation {0} with error:{1}, {2}").format(ExtensionOperationType, e, traceback.format_exc()))
        hutil.do_status_report(ExtensionOperationType,'error','0',
                      'Extension operation {0} failed:{1}'.format(ExtensionOperationType, e))


def update_selinux_port_setting_for_rsyslogomazuremds(action, port):
    # This is needed for Redhat-based distros.
    # 'action' param should be '-a' for adding and '-d' for deleting.
    # Caller is responsible to make sure a correct action param is passed.
    if os.path.exists("/usr/sbin/semanage"):
        RunGetOutput('semanage port {0} -t syslogd_port_t -p tcp {1};echo ignore already added or not found'.format(action, port))


def start_daemon():
    args = ['python', StartDaemonFilePath, "-daemon"]
    log = open(os.path.join(os.getcwd(),'daemon.log'), 'w')
    hutil.log('start daemon '+str(args))
    subprocess.Popen(args, stdout=log, stderr=log)
    wait_n = 20
    while len(get_mdsd_process())==0 and wait_n >0:
        time.sleep(10)
        wait_n=wait_n-1
    if wait_n <=0:
        hutil.error("wait daemon start time out")


def start_mdsd():
    global EnableSyslog
    with open(MDSDPidFile, "w") as pidfile:
         pidfile.write(str(os.getpid())+'\n')
         pidfile.close()

    setup(should_install_required_package=False)

    # Start OMI if it's not running.
    # This shouldn't happen, but this measure is put in place just in case (e.g., Ubuntu 16.04 systemd).
    # Don't check if starting succeeded, as it'll be done in the loop below anyway.
    omi_running = RunGetOutput("/opt/omi/bin/service_control is-running")[0] is 1
    if not omi_running:
        RunGetOutput("/opt/omi/bin/service_control restart")

    if not EnableSyslog:
        uninstall_rsyslogom()

    #if EnableSyslog and distConfig.has_key("restartrsyslog"):
    # sometimes after the mdsd is killed port 29131 is accopied by sryslog, don't know why
    #    RunGetOutput(distConfig["restartrsyslog"])

    log_dir = hutil.get_log_dir()
    monitor_file_path = os.path.join(log_dir, 'mdsd.err')
    info_file_path = os.path.join(log_dir, 'mdsd.info')
    warn_file_path = os.path.join(log_dir, 'mdsd.warn')


    default_port = RSYSLOG_OM_PORT
    update_selinux_port_setting_for_rsyslogomazuremds('-a', default_port)

    mdsd_log_path = os.path.join(WorkDir,"mdsd.log")
    mdsd_log = None
    copy_env = os.environ
    copy_env['LD_LIBRARY_PATH']=MdsdFolder
    if 'mdsd_env_vars' in distConfig:
        env_vars = distConfig['mdsd_env_vars']
        for var_name, var_value in env_vars.items():
            copy_env[var_name] = var_value

    # mdsd http proxy setting
    proxy_config_name = 'mdsdHttpProxy'
    proxy_config = waagent.HttpProxyConfigString    # /etc/waagent.conf has highest priority
    if not proxy_config:
        proxy_config = readPrivateConfig(proxy_config_name)  # Private (protected) setting has next priority
    if not proxy_config:
        proxy_config = readPublicConfig(proxy_config_name)
    if not isinstance(proxy_config, basestring):
        hutil.log("Error: mdsdHttpProxy config is not a string. Ignored.")
    else:
        proxy_config = proxy_config.strip()
        if proxy_config:
            hutil.log("mdsdHttpProxy setting was given and will be passed to mdsd, but not logged here in case there's a password in it")
            copy_env['MDSD_http_proxy'] = proxy_config

    xml_file = os.path.join(WorkDir, './xmlCfg.xml')

    # We now validate the config and proceed only when it succeeds.
    config_validate_cmd = '{0} -v -c {1}'.format(os.path.join(MdsdFolder, "mdsd"), xml_file)
    config_validate_cmd_status, config_validate_cmd_msg = RunGetOutput(config_validate_cmd)
    if config_validate_cmd_status is not 0:
        # Invalid config. Log error and report success.
        message = "Invalid mdsd config given. Can't enable. This extension install/enable operation is still considered a success as it's an external error. Config validation result: "\
                  + config_validate_cmd_msg + ". Terminating LAD as it can't proceed."
        hutil.log(message)
        # No need to do success status report (it's already done). Just silently return.
        return

    # Config validated. Prepare actual mdsd cmdline.
    command = '{0} -A -C -c {1} -p {2} -r {3} -e {4} -w {5} -o {6}'.format(
        os.path.join(MdsdFolder,"mdsd"),
        xml_file,
        default_port,
        MDSDPidPortFile,
        monitor_file_path,
        warn_file_path,
        info_file_path).split(" ")

    try:
        num_quick_consecutive_crashes = 0

        while num_quick_consecutive_crashes < 3:  # We consider only quick & consecutive crashes for retries

            RunGetOutput("rm -f " + MDSDPidPortFile)  # Must delete any existing port num file
            mdsd_pid_port_file_checked = False
            mdsd_log = open(mdsd_log_path,"w")
            hutil.log("Start mdsd "+str(command))
            mdsd = subprocess.Popen(command,
                                     cwd=WorkDir,
                                     stdout=mdsd_log,
                                     stderr=mdsd_log,
                                     env=copy_env)

            with open(MDSDPidFile,"w") as pidfile:
                pidfile.write(str(os.getpid())+'\n')
                pidfile.write(str(mdsd.pid)+'\n')
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
                if mdsd.poll() is not None:     # if mdsd has terminated
                    time.sleep(60)
                    mdsd_log.flush()
                    break

                # mdsd is now up for at least 30 seconds.

                # Issue #137 Can't start mdsd if port 29131 is in use.
                # mdsd now binds to another randomly available port,
                # and LAD still needs to reconfigure rsyslogd.
                if not mdsd_pid_port_file_checked and os.path.isfile(MDSDPidPortFile):
                    with open(MDSDPidPortFile, 'r') as mdsd_pid_port_file:
                        mdsd_pid_port_file.readline()                    # This is actually PID, so ignore.
                        new_port = mdsd_pid_port_file.readline().strip() # .strip() is important!
                        if default_port != new_port:
                            hutil.log("Specified mdsd port ({0}) is in use, so a randomly available port ({1}) was picked, and now reconfiguring omazurelinuxmds".format(default_port, new_port))
                            reconfigure_omazurelinuxmds_and_restart_rsyslog(default_port, new_port)
                        mdsd_pid_port_file_checked = True

                # Issue #128 LAD should restart OMI if it crashes
                omi_was_installed = omi_installed   # Remember the OMI install status from the last iteration
                omi_installed = os.path.isfile(omicli_path)

                if omi_was_installed and not omi_installed:
                    hutil.log("OMI is uninstalled. This must have been intentional and externally done. Will no longer check if OMI is up and running.")

                omi_reinstalled = not omi_was_installed and omi_installed
                if omi_reinstalled:
                    hutil.log("OMI is reinstalled. Will resume checking if OMI is up and running.")

                should_restart_omi = False
                if omi_installed:
                    cmd_exit_status, cmd_output = RunGetOutput(cmd=omicli_noop_query_cmd, should_log=False)
                    should_restart_omi = cmd_exit_status is not 0
                    if should_restart_omi:
                        hutil.error("OMI noop query failed. Output: " + cmd_output + ". OMI crash suspected. Restarting OMI and sending SIGHUP to mdsd after 5 seconds.")
                        omi_restart_msg = RunGetOutput("/opt/omi/bin/service_control restart")[1]
                        hutil.log("OMI restart result: " + omi_restart_msg)
                        time.sleep(5)

                should_signal_mdsd = should_restart_omi or omi_reinstalled
                if should_signal_mdsd:
                    omi_up_and_running = RunGetOutput(omicli_noop_query_cmd)[0] is 0
                    if omi_up_and_running:
                        mdsd.send_signal(signal.SIGHUP)
                        hutil.log("SIGHUP sent to mdsd")
                    else:   # OMI restarted but not staying up...
                        log_msg = "OMI restarted but not staying up. Will be restarted in the next iteration."
                        hutil.error(log_msg)
                        # Also log this issue on syslog as well
                        syslog.openlog('diagnostic.py', syslog.LOG_PID, syslog.LOG_DAEMON)  # syslog.openlog(ident, logoption, facility) -- not taking kw args in Python 2.6
                        syslog.syslog(syslog.LOG_ALERT, log_msg)    # syslog.syslog(priority, message) -- not taking kw args
                        syslog.closelog()

                if not os.path.exists(monitor_file_path):
                    continue
                monitor_file_ctime = datetime.datetime.strptime(time.ctime(int(os.path.getctime(monitor_file_path))), "%a %b %d %H:%M:%S %Y")
                if last_error_time >= monitor_file_ctime:
                    continue
                last_error_time = monitor_file_ctime
                last_error = tail(monitor_file_path)
                if len(last_error) > 0 and (datetime.datetime.now() - last_error_time) < datetime.timedelta(minutes=30):
                    hutil.log("Error in MDSD:"+last_error)
                    hutil.do_status_report(ExtensionOperationType, "success", '1', "message in /var/log/mdsd.err:"+str(last_error_time)+":"+last_error)

            # mdsd terminated.
            if mdsd_log:
                mdsd_log.close()
                mdsd_log = None

            # Check if this is NOT a quick crash -- we consider a crash quick
            # if it's within 30 minutes from the start time. If it's not quick,
            # we just continue by restarting mdsd.
            mdsd_up_time = datetime.datetime.now() - last_mdsd_start_time
            if mdsd_up_time > datetime.timedelta(minutes=30):
                mdsd_terminated_msg = "MDSD terminated after "+str(mdsd_up_time)+". "+tail(mdsd_log_path)+tail(monitor_file_path)
                hutil.log(mdsd_terminated_msg)
                num_quick_consecutive_crashes = 0
                continue

            # It's a quick crash. Log error and add an extension event.
            num_quick_consecutive_crashes += 1

            error = "MDSD crash(uptime=" + str(mdsd_up_time) + "):"+tail(mdsd_log_path)+tail(monitor_file_path)
            hutil.error("MDSD crashed:"+error)

            # Needs to reset rsyslog omazurelinuxmds config before retrying mdsd
            install_rsyslogom()

        # mdsd all 3 allowed quick/consecutive crashes exhausted
        hutil.do_status_report(ExtensionOperationType, "error", '1', "mdsd stopped:"+error)

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
            hutil.error("Error :"+tail(mdsd_log_path))
        hutil.error(("Failed to launch mdsd with error:{0},"
                     "stacktrace:{1}").format(e, traceback.format_exc()))
        hutil.do_status_report(ExtensionOperationType, 'error', '1', 'Launch script failed:{0}'.format(e))
        waagent.AddExtensionEvent(name=hutil.get_name(),
                                  op=ExtensionOperationType,
                                  isSuccess=False,
                                  version=hutil.get_extension_version(),
                                  message="Launch script failed:"+str(e))
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
            hutil.log("stop_mdsd() terminate check #{0}: Processes not terminated yet, rechecking in 2 seconds".format(num_checked))

    if not terminated:
        kill_cmd = "kill -9 " + " ".join(get_mdsd_process())
        hutil.log("stop_mdsd(): Processes not terminated in 20 seconds. Sending SIGKILL (" + kill_cmd + ")")
        RunGetOutput(kill_cmd)

    RunGetOutput("rm "+MDSDPidFile)

    return 0, "Terminated" if terminated else "SIGKILL'ed"


def get_mdsd_process():
    mdsd_pids = []
    if not os.path.exists(MDSDPidFile):
        return mdsd_pids

    with open(MDSDPidFile,"r") as pidfile:
        for pid in pidfile.readlines():
            is_still_alive = waagent.RunGetOutput("cat /proc/"+pid.strip()+"/cmdline",chk_err=False)[1]
            if is_still_alive.find('/waagent/') > 0 :
                mdsd_pids.append(pid.strip())
            else:
                hutil.log("return not alive "+is_still_alive.strip())
    return mdsd_pids


def get_dist_config():
    dist = platform.dist()
    if All_Dist.has_key(dist[0]+":"+dist[1]):
        return All_Dist[dist[0]+":"+dist[1]]
    elif All_Dist.has_key(dist[0]):
        return All_Dist[dist[0]]
    else:
        return None


def install_omi():
    need_install_omi = 0

    isMysqlInstalled = RunGetOutput("which mysql")[0] is 0
    isApacheInstalled = RunGetOutput("which apache2 || which httpd || which httpd2")[0] is 0

    if 'OMI-1.0.8-4' not in RunGetOutput('/opt/omi/bin/omiserver -v')[1]:
        need_install_omi=1
    if isMysqlInstalled and not os.path.exists("/opt/microsoft/mysql-cimprov"):
        need_install_omi=1
    if isApacheInstalled and not os.path.exists("/opt/microsoft/apache-cimprov"):
        need_install_omi=1

    if need_install_omi:
        hutil.log("Begin omi installation.")
        isOmiInstalledSuccessfully = False
        maxTries = 5      # Try up to 5 times to install OMI
        for trialNum in range(1, maxTries+1):
            isOmiInstalledSuccessfully = RunGetOutput(distConfig["installomi"])[0] is 0
            if isOmiInstalledSuccessfully:
                break
            hutil.error("OMI install failed (trial #" + str(trialNum) + ").")
            if trialNum < maxTries:
                hutil.error("Retrying in 30 seconds...")
                time.sleep(30)
        if not isOmiInstalledSuccessfully:
            hutil.error("OMI install failed " + str(maxTries) + " times. Giving up...")
            return 1, "OMI install failed " + str(maxTries) + " times"

    shouldRestartOmi = False

    # Check if OMI is configured to listen to any non-zero port and reconfigure if so.
    omi_listens_to_nonzero_port = RunGetOutput(r"grep '^\s*httpsport\s*=' /etc/opt/omi/conf/omiserver.conf | grep -v '^\s*httpsport\s*=\s*0\s*$'")[0] is 0
    if omi_listens_to_nonzero_port:
        RunGetOutput("/opt/omi/bin/omiconfigeditor httpsport -s 0 < /etc/opt/omi/conf/omiserver.conf > /etc/opt/omi/conf/omiserver.conf_temp")
        RunGetOutput("mv /etc/opt/omi/conf/omiserver.conf_temp /etc/opt/omi/conf/omiserver.conf")
        shouldRestartOmi = True

    # Quick and dirty way of checking if mysql/apache process is running
    isMysqlRunning = RunGetOutput("ps -ef | grep mysql | grep -v grep")[0] is 0
    isApacheRunning = RunGetOutput("ps -ef | grep -E 'httpd|apache2' | grep -v grep")[0] is 0

    if os.path.exists("/opt/microsoft/mysql-cimprov/bin/mycimprovauth") and isMysqlRunning:
        mysqladdress=readPrivateConfig("mysqladdress")
        mysqlusername=readPrivateConfig("mysqlusername")
        mysqlpassword=readPrivateConfig("mysqlpassword")
        RunGetOutput("/opt/microsoft/mysql-cimprov/bin/mycimprovauth default "+mysqladdress+" "+mysqlusername+" '"+mysqlpassword+"'", should_log=False)
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


def uninstall_rsyslogom():
    #return RunGetOutput(distConfig['uninstallmdsd'])
    error,rsyslog_info = RunGetOutput(distConfig['checkrsyslog'])
    rsyslog_om_path = None
    match = re.search("(.*)"+rsyslog_ommodule_for_check,rsyslog_info)
    if match:
       rsyslog_om_path = match.group(1)
    if rsyslog_om_path == None:
        return 1,"rsyslog not installed"
    if os.path.exists("/etc/rsyslog.d/omazurelinuxmds.conf"):
        RunGetOutput("rm "+rsyslog_om_path+"/omazuremdslegacy.so")
        RunGetOutput("rm /etc/rsyslog.d/omazurelinuxmds.conf")
        RunGetOutput("rm /etc/rsyslog.d/omazurelinuxmds_fileom.conf")

    if distConfig.has_key("restartrsyslog"):
        RunGetOutput(distConfig["restartrsyslog"])
    else:
        RunGetOutput("service rsyslog restart")

    return 0,"rm omazurelinuxmds done"


def install_rsyslogom():
    error, rsyslog_info = RunGetOutput(distConfig['checkrsyslog'])
    rsyslog_om_path = None
    match = re.search("(.*)"+rsyslog_ommodule_for_check, rsyslog_info)
    if match:
       rsyslog_om_path = match.group(1)
    if rsyslog_om_path == None:
        return 1,"rsyslog not installed"

    #error,output = RunGetOutput(distConfig['installmdsd'])

    rsyslog_om_folder = None
    for v in {'8':'rsyslog8','7':'rsyslog7','5':'rsyslog5'}.items():
        if re.search('Version\s*:\s*'+v[0],rsyslog_info):
            rsyslog_om_folder = v[1]

    if rsyslog_om_folder and rsyslog_om_path:
        RunGetOutput("\cp -f "+rsyslog_om_folder+"/omazuremdslegacy.so"+" "+rsyslog_om_path)
        RunGetOutput("\cp -f "+rsyslog_om_folder+"/omazurelinuxmds.conf"+" /etc/rsyslog.d/omazurelinuxmds.conf")
        RunGetOutput("\cp -f "+omfileconfig+" /etc/rsyslog.d/omazurelinuxmds_fileom.conf")

    else:
        return 1,"rsyslog version can't be deteced"

    if distConfig.has_key("restartrsyslog"):
        RunGetOutput(distConfig["restartrsyslog"])
    else:
        RunGetOutput("service rsyslog restart")
    return 0,"install mdsdom completed"


def reconfigure_omazurelinuxmds_and_restart_rsyslog(default_port, new_port):
    files_to_modify = ['/etc/rsyslog.d/omazurelinuxmds.conf', '/etc/rsyslog.d/omazurelinuxmds_fileom.conf']
    cmd_to_run = "sed -i 's/$legacymdsport [0-9]*/$legacymdsport {0}/g' {1}"

    for f in files_to_modify:
        RunGetOutput(cmd_to_run.format(new_port, f))

    update_selinux_port_setting_for_rsyslogomazuremds('-d', default_port)
    update_selinux_port_setting_for_rsyslogomazuremds('-a', new_port)

    if distConfig.has_key("restartrsyslog"):
        RunGetOutput(distConfig["restartrsyslog"])
    else:
        RunGetOutput("service rsyslog restart")


def install_required_package():
    packages = distConfig['packages']

    errorcode = 0
    output_all = ""

    if 'installrequiredpackages' in distConfig:
        package_str = str.join(' ', packages)
        if package_str:
            cmd = distConfig['installrequiredpackages'].replace('PACKAGES', package_str).replace('COUNT', str(len(packages)))
            hutil.log(cmd)
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, executable='/bin/bash')
            timeout=360
            time.sleep(1)
            while process.poll() is None and timeout > 0:
                time.sleep(10)
                timeout-=1
            if process.poll() is None:
                hutil.error("Timeout when execute:"+cmd)
                errorcode = 1
                process.kill()
            output_all, unused_err = process.communicate()
            errorcode += process.returncode
            return errorcode,str(output_all)
    else:
        cmd_temp = distConfig['installrequiredpackage']
        if len(cmd_temp) >0:
            for p in packages:
                cmd = cmd_temp.replace("PACKAGE",p)
                hutil.log(cmd)
                process = subprocess.Popen(cmd,stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True,executable='/bin/bash')
                timeout=360
                time.sleep(1)
                while process.poll() is None and timeout > 0:
                    time.sleep(10)
                    timeout-=1
                if process.poll() is None:
                    hutil.error("Timeout when execute:"+cmd)
                    errorcode = 1
                    process.kill()
                output, unused_err = process.communicate()
                output_all += output
                errorcode+=process.returncode
            return errorcode,str(output_all)
    return 0,"not pacakge need install"


def tail(log_file, output_size = OutputSize):
    if not os.path.exists(log_file):
        return ""
    pos = min(output_size, os.path.getsize(log_file))
    with open(log_file, "r") as log:
        log.seek(-pos, 2)
        buf = log.read(output_size)
        buf = filter(lambda x: x in string.printable, buf)
        return buf.decode("ascii", "ignore")


def get_deployment_id():
    identity = "unknown"
    env_cfg_path = os.path.join(WorkDir, os.pardir, "HostingEnvironmentConfig.xml")
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
    if len(sys.argv) > 1:
        main(sys.argv[1])

