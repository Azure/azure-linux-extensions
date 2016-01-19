#!/usr/bin/env python
#
# Azure Linux extension
#
# Linux Azure Diagnostic Extension v.2.0
# Copyright (c) Microsoft Corporation
# All rights reserved. 
# MIT License
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the ""Software""), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
# THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#
# Requires Python 2.6+
#
import socket
import array
import base64
import os
import os.path
import re
import string
import subprocess
import sys
import imp
import shlex
import traceback
import platform
import time
import datetime
from Utils.WAAgentUtil import waagent
import Utils.HandlerUtil as Util
import commands
import base64
import xml.dom.minidom
import  xml.etree.ElementTree  as ET

# Version 2.2.0
ExtensionShortName = 'LinuxAzureDiagnostic'
WorkDir = os.getcwd()
MDSDPidFile = os.path.join(WorkDir, 'mdsd.pid')
OutputSize = 1024
EnableSyslog= True
waagent.LoggerInit('/var/log/waagent.log','/dev/stdout')
waagent.Log("%s started to handle." %(ExtensionShortName))
hutil =  Util.HandlerUtility(waagent.Log, waagent.Error, ExtensionShortName)
hutil.try_parse_context()
public_settings = hutil.get_public_settings()
protected_settings = hutil.get_protected_settings()
if not public_settings:
    public_settings = {}
if not protected_settings:
    protected_settings = {}


def LogRunGetOutPut(cmd):
    hutil.log("RunCmd "+cmd)
    error,msg = waagent.RunGetOutput(cmd)
    hutil.log("Return "+str(error)+":"+msg)
    return error,msg

rsyslog_ommodule_for_check='omprog.so'
RunGetOutput = LogRunGetOutPut
MdsdFolder = os.path.join(WorkDir, 'bin')
StartDaemonFilePath = os.path.join(os.getcwd(), __file__)
omi_universal_rpm_name = 'scx-1.6.2-104.universalr.1.x64.sh'
omi_universal_dpkg_name = 'scx-1.6.2-104.universald.1.x64.sh'

omfileconfig = os.path.join(WorkDir, 'omfileconfig')

DebianConfig = {"installomi":"bash "+omi_universal_dpkg_name+" --upgrade --force;",
                "installrequiredpackage":'dpkg-query -l PACKAGE |grep ^ii ;  if [ ! $? == 0 ]; then apt-get update ; apt-get install -y PACKAGE; fi',
                 "packages":('libglibmm-2.4-1c2a',),
                  "restartrsyslog":"service rsyslog restart",
                 'distrolibs':'debian/* shared/*','checkrsyslog':'(dpkg-query -s rsyslog;dpkg-query -L rsyslog) |grep "Version\|'+rsyslog_ommodule_for_check+'"'
                }

RedhatConfig =  {"installomi":"bash "+omi_universal_rpm_name+" --upgrade --force;",
                 "installrequiredpackage":'rpm -q PACKAGE ;  if [ ! $? == 0 ]; then yum install -y PACKAGE; fi','distrolibs':'redhat',
                 "packages":('glibmm24','tar','policycoreutils-python'),
                'distrolibs':'redhat/* shared/*',
                  "restartrsyslog":"service rsyslog restart",
                  'checkrsyslog':'(rpm -qi rsyslog;rpm -ql rsyslog)|grep "Version\\|'+rsyslog_ommodule_for_check+'"'
                 }


UbuntuConfig = dict(DebianConfig.items()+
                    {'distrolibs':'ubuntu1404/*'
                    }
                    .items())


UbuntuConfig1204 = dict(DebianConfig.items()+
                    {'distrolibs':'debian/* shared/*'
                    }
                    .items())

UbuntuConfig1510 = dict(DebianConfig.items()+
                    {'installrequiredpackages':'[ $(dpkg -l PACKAGES |grep ^ii |wc -l) -eq \'COUNT\' ] '
                        '||apt-get install -y PACKAGES',
                     'packages':('libxml++2.6-2v5', 'libglibmm-2.4-1v5', 'libcpprest2.6',
                        'libboost-regex1.58.0', 'libboost-log1.58.0', 'libboost-filesystem1.58.0', 
                        'libboost-system1.58.0', 'libboost-thread1.58.0', 'libboost-iostreams1.58.0'),
                     'distrolibs':'ubuntu1510/*'
                    }.items())

SuseConfig11 = dict(RedhatConfig.items()+
                    {'installrequiredpackage':'rpm -qi PACKAGE;  if [ ! $? == 0 ]; then zypper --non-interactive install PACKAGE;fi; ','restartrsyslog':'service syslog restart',
                     "packages":('glibmm2','rsyslog'),
                  'distrolibs':'suse/*'}
                  .items())
SuseConfig12 = dict(RedhatConfig.items()+
                  {'installrequiredpackage':' rpm -qi PACKAGE; if [ ! $? == 0 ]; then zypper --non-interactive install PACKAGE;fi; ','restartrsyslog':'service syslog restart',
                   "packages":('libglibmm-2_4-1','libgthread-2_0-0','ca-certificates-mozilla','rsyslog'),
                  'distrolibs':'suse12/*'}
                  .items())

CentosConfig = dict(RedhatConfig.items()+
                    {'installrequiredpackag':'rpm -qi PACKAGE; if [ ! $? == 0 ]; then  yum install  -y PACKAGE; fi',
                     "packages":('glibmm24','policycoreutils-python')}
                  .items())

RSYSLOG_OM_PORT='29131'
All_Dist= {'SuSE:11':SuseConfig11,'debian':DebianConfig,'SuSE':SuseConfig12,
           'Ubuntu':UbuntuConfig,'Ubuntu:12.04':UbuntuConfig1204, 'Ubuntu:15.10':UbuntuConfig1510,
           'SuSE:12':SuseConfig12,'redhat':RedhatConfig,'centos':CentosConfig}
distConfig = None
dist = platform.dist()
if All_Dist.has_key(dist[0]+":"+dist[1]):
    distConfig =  All_Dist[dist[0]+":"+dist[1]]
elif All_Dist.has_key(dist[0]):
    distConfig =  All_Dist[dist[0]]
else:
    hutil.error("os version:"+dist[0]+" not supported")

UseService = False
if dist[0] == 'Ubuntu' and dist[1] == '15.10':
    UseService = True


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


def setXmlValue(xml,path,property,value,selector=[]):
    elements = xml.findall(path)
    for element in elements:
        if selector and element.get(selector[0])!=selector[1]:
            continue
        if not property:
            element.text = value
        elif not element.get(property) or len(element.get(property))==0 :
            element.set(property,value)

def getXmlValue(xml,path,property):
    element = xml.find(path)
    return element.get(property)

def addElement(xml,path,el,selector=[]):
    elements = xml.findall(path)
    for element in elements:
        if selector and element.get(selector[0])!=selector[1]:
            continue
        element.append(el)


def createElement(schema):
    return ET.fromstring(schema)



def parse_context(operation):
    hutil = Util.HandlerUtility(waagent.Log, waagent.Error, ExtensionShortName)
    hutil.try_parse_context()
    return


def setup(local_only):
    global EnableSyslog

    if not local_only:
        install_package_error=""
        retry = 3
        while retry >0:
            error,msg = install_required_package()
            hutil.log(msg)
            if error ==0:
                break
            else:
                retry-=1
                hutil.log("Sleep 60 retry "+str(retry))
                install_package_error=msg
                time.sleep(60)
        if install_package_error:
            if len(install_package_error) > 1024:
                install_package_error = install_package_error[0:512]+install_package_error[-512:-1]
            hutil.error(install_package_error)
            return 2, install_package_error

    if EnableSyslog:
        error, msg = install_rsyslogom()
        if error !=0:
            hutil.error(msg)

    # copy distrolibs
    if not os.path.isdir(MdsdFolder):
        libs = distConfig['distrolibs']
        if len(libs) > 0:
            RunGetOutput('mkdir -p {0}'.format(MdsdFolder))
            RunGetOutput('\cp -f {0} {1}'.format(libs, MdsdFolder))

    install_omi()

    return 0, 'success'


def hasConfig(key):
    return  public_settings.has_key(key) or protected_settings.has_key(key)

def readConfig(key):
    if  public_settings.has_key(key):
        return public_settings[key];
    if protected_settings.has_key(key):
        return protected_settings[key];
    return ''

def createPortalSettings(tree,resourceId):
    portal_config = ET.ElementTree()
    portal_config.parse(os.path.join(WorkDir, "portal.xml.template"))
    setXmlValue(portal_config,"./DerivedEvents/DerivedEvent/LADQuery","partitionKey",resourceId)
    addElement(tree,'Events',portal_config._root.getchildren()[0])
    addElement(tree,'Events',portal_config._root.getchildren()[1])


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
    fileid = 0;
    sysconfig = """
$ModLoad imfile

                """
    if not files:
        return
    for file in files:
        fileid=fileid+1
        eventSourceElement = createElement(eventSourceSchema)
        setXmlValue(eventSourceElement,'RouteEvent','eventName',file["table"])
        eventSourceElement.set('source','ladfile'+str(fileid))
        addElement(tree,'Events/MdsdEvents',eventSourceElement)

        sourceElement = createElement(sourceSchema)
        sourceElement.set('name','ladfile'+str(fileid))
        addElement(tree,'Sources',sourceElement)

        syslog_config = syslogEventSourceConfig.replace('#FILE#',file['file'])
        syslog_config = syslog_config.replace('#STATFILE#',file['file'].replace("/","-"))
        syslog_config = syslog_config.replace('#FILETAG#','ladfile'+str(fileid))
        sysconfig+=syslog_config
    return sysconfig


perfSchema = """
    <OMIQuery cqlQuery=""
      dontUsePerNDayTable="true" eventName="" omiNamespace="" priority="High" sampleRateInSeconds="" />
    """

def createPerfSettngs(tree,perfs):
    if not perfs:
        return
    for perf in perfs:
        perfElement = createElement(perfSchema)
        perfElement.set('cqlQuery',perf['query'])
        perfElement.set('eventName',perf['table'])
        namespace="root/scx"
        if perf.has_key('namespace'):
           namespace=perf['namespace']
        perfElement.set('omiNamespace',namespace)
        addElement(tree,'Events/OMI',perfElement,["omitag","perf"])

def createAccountSettings(tree,account,key,endpoint):
    setXmlValue(tree,'Accounts/Account',"account",account,['isDefault','true'])
    setXmlValue(tree,'Accounts/Account',"key",key,['isDefault','true'])
    setXmlValue(tree,'Accounts/Account',"tableEndpoint",endpoint,['isDefault','true'])

def config(xmltree,key,value,xmlpath,selector=[]):
    v = readConfig(key)
    if not v:
        v = value
    setXmlValue(xmltree,xmlpath,key,v,selector)

def readUUID():
     code,str_ret = waagent.RunGetOutput("dmidecode |grep UUID |awk '{print $2}'",chk_err=False)
     return str_ret.strip();

def configSettings():
    mdsdCfgstr = readConfig('mdsdCfg')
    if not mdsdCfgstr :
        with open (os.path.join(WorkDir, './mdsdConfig.xml.template'),"r") as defaulCfg:
            mdsdCfgstr = defaulCfg.read()
    else:
        mdsdCfgstr = base64.b64decode(mdsdCfgstr)
    mdsdCfg = ET.ElementTree()
    mdsdCfg._setroot(createElement(mdsdCfgstr))

    # update deployment id
    deployment_id = get_deployment_id()
    setXmlValue(mdsdCfg, "Management/Identity/IdentityComponent", "", deployment_id, ["name", "DeploymentId"])

    xmlCfg = readConfig('xmlCfg')
    if xmlCfg:
        try:
            xmlCfg = base64.b64decode(xmlCfg)
            resourceId = getXmlValue(createElement(xmlCfg),'DiagnosticMonitorConfiguration/Metrics','resourceId')
            createPortalSettings(mdsdCfg,escape(resourceId))
            instanceID=""
            if resourceId.find("providers/Microsoft.Compute/virtualMachineScaleSets") >=0:
                instanceID = readUUID();
            config(mdsdCfg,"instanceID",instanceID,"Events/DerivedEvents/DerivedEvent/LADQuery")

        except Exception, e:
            hutil.error("Failed to create portal config  error:{0} {1}".format(e,traceback.format_exc()))

    perfCfg = readConfig('perfCfg')
    if not perfCfg and not hasConfig('perfCfg'):
        perfCfg = [
                    {"query":"SELECT PercentAvailableMemory, AvailableMemory, UsedMemory ,PercentUsedSwap FROM SCX_MemoryStatisticalInformation","table":"LinuxMemory"},
                    {"query":"SELECT PercentProcessorTime, PercentIOWaitTime, PercentIdleTime FROM SCX_ProcessorStatisticalInformation WHERE Name='_TOTAL'","table":"LinuxCpu"},
                    {"query":"SELECT AverageWriteTime,AverageReadTime,ReadBytesPerSecond,WriteBytesPerSecond FROM  SCX_DiskDriveStatisticalInformation WHERE Name='_TOTAL'","table":"LinuxDisk"}
                  ]
    try:
        createPerfSettngs(mdsdCfg,perfCfg)
    except Exception, e:
        hutil.error("Failed to create perf config  error:{0} {1}".format(e,traceback.format_exc()))


    syslogCfg = readConfig('syslogCfg')
    fileCfg = readConfig('fileCfg')
    #fileCfg = [{"file":"/var/log/waagent.log","table":"waagent"},{"file":"/var/log/waagent2.log","table":"waagent3"}]
    try:
        if syslogCfg:
           syslogCfg = base64.b64decode(syslogCfg)
        if fileCfg:
           syslogCfg =  createEventFileSettings(mdsdCfg,fileCfg)+syslogCfg

        with open(omfileconfig,'w') as hfile:
                hfile.write(syslogCfg)
    except Exception, e:
        hutil.error("Failed to create syslog_file config  error:{0} {1}".format(e,traceback.format_exc()))

    account = readConfig('storageAccountName')
    key = readConfig('storageAccountKey')
    endpoint = readConfig('endpoint')
    if not endpoint:
        endpoint = 'table.core.windows.net'
    endpoint = 'https://'+account+"."+endpoint;

    createAccountSettings(mdsdCfg,account,key,endpoint)


    config(mdsdCfg,"eventVolume","Medium","Management")
    config(mdsdCfg,"sampleRateInSeconds","60","Events/OMI/OMIQuery")

    mdsdCfg.write(os.path.join(WorkDir, './xmlCfg.xml'))


def install_service():
    RunGetOutput('sed s#{WORKDIR}#' + WorkDir + '# ' +
                 WorkDir + '/services/mdsd-lde.service > /lib/systemd/system/mdsd-lde.service')
    RunGetOutput('systemctl daemon-reload')


def main(command):
    #Global Variables definition

    global EnableSyslog, UseService
    if readConfig('EnableSyslog').lower() == 'false':
        EnableSyslog = False
    else:
        EnableSyslog = True

    configSettings()

    for notsupport in ('WALinuxAgent-2.0.5','WALinuxAgent-2.0.4','WALinuxAgent-1'):
        code,str_ret = waagent.RunGetOutput("grep 'GuestAgentVersion.*"+notsupport+"' /usr/sbin/waagent",chk_err=False)
        if code==0 and str_ret.find(notsupport)>-1:
            hutil.log("can run this extension on  "+notsupport)
            hutil.do_status_report("Install", "error",'1', "can run this extension on  "+notsupport)
            return

    if distConfig == None:
        hutil.do_status_report("Install", "error",'1', "can't be installed on this OS")
        waagent.AddExtensionEvent(name=hutil.get_name(),
                                op=waagent.WALAEventOperation.Enable,
                                isSuccess=False,
                                      message="can't be installed on this OS"+str(platform.dist()))
        return
    try:
        hutil.log("Dispatching command:" + command)
        if UseService:
            if re.match("^([-/]*)(disable)", command):
                RunGetOutput('systemctl stop mdsd-lde && systemctl disable mdsd-lde')
                hutil.do_status_report("Disable", "success", '0',"Disable succeeded")
            elif re.match("^([-/]*)(uninstall)", command):
                RunGetOutput('systemctl stop mdsd-lde && systemctl disable mdsd-lde ' +
                             '&& rm /lib/systemd/system/mdsd-lde.service')
                error,msg = uninstall_omi()
                if EnableSyslog:
                    error,msg = uninstall_rsyslogom()
                hutil.do_status_report("Uninstall", "success",'0', "Uninstall succeeded")
            elif re.match("^([-/]*)(install)", command):
                error, msg = setup(True)
                install_service()
                if error != 0:
                    hutil.do_status_report("Install", "error", error, msg)
                    sys.exit(error)
                else:
                    hutil.do_status_report("Install", "success",'0', "Install succeeded")
            elif re.match("^([-/]*)(enable)", command):
                hutil.exit_if_enabled()
                install_service()
                RunGetOutput('systemctl enable mdsd-lde && systemctl restart mdsd-lde')
                hutil.do_status_report("Enable","success",'0',"Enable succeeded")
            elif re.match("^([-/]*)(daemon)", command):
                start_mdsd()
            elif re.match("^([-/]*)(update)", command):
                hutil.do_status_report("Update", "success",'0', "Update succeeded")
        else:
            if re.match("^([-/]*)(disable)", command):
                error,msg = stop_mdsd()
                hutil.do_status_report("Disable", "success", '0',"Disable succeeded")
            elif re.match("^([-/]*)(uninstall)", command):
                stop_mdsd()
                error,msg = uninstall_omi()
                if EnableSyslog:
                    error,msg = uninstall_rsyslogom()
                hutil.do_status_report("Uninstall", "success",'0', "Uninstall succeeded")
            elif re.match("^([-/]*)(install)", command):
                error, msg = setup(True)
                if error != 0:
                    hutil.do_status_report("Install", "error", error, msg)
                    sys.exit(error)
                else:
                    hutil.do_status_report("Install", "success",'0', "Install succeeded")
            elif re.match("^([-/]*)(enable)", command):
                # if daemon process not runs
                hutil.log("get pid:"+str(get_mdsd_process()))
                if len(get_mdsd_process())!=2 or  hutil.is_current_config_seq_greater_inused():
                    stop_mdsd()
                    start_daemon()
                hutil.set_inused_config_seq(hutil.get_seq_no())
                hutil.do_status_report("Enable","success",'0',"Enable succeeded")
            elif re.match("^([-/]*)(daemon)", command):
                start_mdsd()
            elif re.match("^([-/]*)(update)", command):
                hutil.do_status_report("Update", "success",'0', "Update succeeded")

    except Exception, e:
        hutil.error(("Failed to enable the extension with error:{0}, "
                     "{1}").format(e, traceback.format_exc()))
        hutil.do_status_report('Enable','error','0',
                      'Enable failed:{0}'.format(e))



def start_daemon():
    args = ['python',StartDaemonFilePath, "-daemon"]
    log = open(os.path.join(os.getcwd(),'daemon.log'), 'w')
    hutil.log('start daemon '+str(args))
    child = subprocess.Popen(args, stdout=log, stderr=log)
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

    setup(False)

    if not EnableSyslog:
        uninstall_rsyslogom()

    #if EnableSyslog and distConfig.has_key("restartrsyslog"):
    # sometimes after the mdsd is killed port 29131 is accopied by sryslog, don't know why
    #    RunGetOutput(distConfig["restartrsyslog"])

    if os.path.exists("/usr/sbin/semanage"):
        RunGetOutput('semanage port -a -t syslogd_port_t -p tcp 29131;echo ignore already added')

    log_dir = hutil.get_log_dir()
    monitor_file_path = os.path.join(log_dir, 'mdsd.err')
    info_file_path = os.path.join(log_dir, 'mdsd.info')
    warn_file_path =  os.path.join(log_dir, 'mdsd.warn')


    default_port = RSYSLOG_OM_PORT
    mdsd_log_path = os.path.join(WorkDir,"mdsd.log")
    mdsd_log = None
    copy_env = os.environ
    copy_env['LD_LIBRARY_PATH']=MdsdFolder
    xml_file =  os.path.join(WorkDir, './xmlCfg.xml')
    command = '{0} -c {1} -p {2} -e {3} -w {4} -o {5}'.format(
        os.path.join(MdsdFolder,"mdsd"),
        xml_file,
        default_port,
        monitor_file_path,
        warn_file_path,
        info_file_path).split(" ")

    try:
        for restart in range(0,3):

            mdsd_log = open (mdsd_log_path,"w")
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

            last_error_time = datetime.datetime.now()
            while True:
                time.sleep(30)
                if " ".join(get_mdsd_process()).find(str(mdsd.pid)) <0 and len(get_mdsd_process()) >=2:
                    mdsd.kill()
                    hutil.log("Another process is started, now exit")
                    return
                if not (mdsd.poll() is None):
                    time.sleep(60)
                    mdsd_log.flush()
                    break
                if not os.path.exists(monitor_file_path):
                    continue
                monitor_file_ctime = datetime.datetime.strptime(time.ctime(int(os.path.getctime(monitor_file_path))), "%a %b %d %H:%M:%S %Y")
                if last_error_time >=  monitor_file_ctime:
                    continue
                last_error_time = monitor_file_ctime
                last_error = tail(monitor_file_path)
                if len(last_error) > 0 and (datetime.datetime.now()- last_error_time) < datetime.timedelta(minutes=30):
                    hutil.log("Error in MDSD:"+last_error)
                    hutil.do_status_report("Enable","success",'1',"message in /var/log/mdsd.err:"+str(last_error_time)+":"+last_error)

            if mdsd_log:
                mdsd_log.close()
                mdsd_log = None

            error = "MDSD crash:"+tail(mdsd_log_path)+tail(monitor_file_path)
            hutil.error("MDSD crashed:"+error)
            try:
                waagent.AddExtensionEvent(name=hutil.get_name(),
                                op=waagent.WALAEventOperation.Enable,
                                isSuccess=False,
                                      message=error)
            except Exception:
                pass

        hutil.do_status_report("Enable","error",'1',"mdsd stopped:"+error)

    except Exception,e:
        if mdsd_log:
            hutil.error("Error :"+tail(mdsd_log_path))
        hutil.error(("Failed to launch mdsd with error:{0},"
                     "stacktrace:{1}").format(e, traceback.format_exc()))
        hutil.do_status_report('Enable', 'error', '1',
                      'Lanch script failed:{0}'.format(e))
        waagent.AddExtensionEvent(name=hutil.get_name(),
                                  op=waagent.WALAEventOperation.Enable,
                                  isSuccess=False,
                                  message="MDSD Crash2:"+str(e))
    finally:
        if mdsd_log:
            mdsd_log.close()


def stop_mdsd():
    pid_to_kill = " ".join(get_mdsd_process())
    if len(pid_to_kill)>0:
        hutil.log("kill -9 "+pid_to_kill)
        RunGetOutput("kill -9 "+pid_to_kill)
    #left the pid file won't do bad
    #RunGetOutput("rm "+MDSDPidFile)
    return 0,"stopped"

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
    need_install_omi=0
    isMysqlNotInstalled,result = RunGetOutput("which mysql")
    isApacheNotInstalled,result = RunGetOutput("which apache2 || which httpd || which httpd2")

    if 'OMI-1.0.8-3' not in RunGetOutput('/opt/omi/bin/omiserver -v')[1]:
        need_install_omi=1
    if not isMysqlNotInstalled and not os.path.exists("/opt/microsoft/mysql-cimprov"):
        need_install_omi=1
    if not isApacheNotInstalled and not os.path.exists("/opt/microsoft/apache-cimprov"):
        need_install_omi=1


    if need_install_omi:
        hutil.log("Begin omi installation.")
        RunGetOutput(distConfig["installomi"])

    if os.path.exists("/opt/microsoft/mysql-cimprov/bin/mycimprovauth"):
        mysqladdress=readConfig("mysqladdress")
        mysqlusername=readConfig("mysqlusername")
        mysqlpassword=readConfig("mysqlpassword")
        RunGetOutput("/opt/microsoft/mysql-cimprov/bin/mycimprovauth default "+mysqladdress+" "+mysqlusername+" '"+mysqlpassword+"'")

    if os.path.exists("/opt/microsoft/apache-cimprov/bin/apache_config.sh"):
        RunGetOutput("/opt/microsoft/apache-cimprov/bin/apache_config.sh -c")

    RunGetOutput("/opt/omi/bin/service_control restart");
    return 0, "omi installed"

def uninstall_omi():
    if os.path.exists("/opt/microsoft/apache-cimprov/bin/apache_config.sh"):
        RunGetOutput("/opt/microsoft/apache-cimprov/bin/apache_config.sh -u")
    hutil.log("omi will not be uninstalled")
    return 0,"do nothing"


def uninstall_rsyslogom():
    #return RunGetOutput(distConfig['uninstallmdsd'])
    error,rsyslog_info = RunGetOutput(distConfig['checkrsyslog'])
    rsyslog_om_path = None
    match= re.search("(.*)"+rsyslog_ommodule_for_check,rsyslog_info)
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
    error,rsyslog_info = RunGetOutput(distConfig['checkrsyslog'])
    rsyslog_om_path = None
    match= re.search("(.*)"+rsyslog_ommodule_for_check,rsyslog_info)
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
    except Exception, e:
        # use fallback identity
        hutil.error("Failed to retrieve deployment ID. Error:{0} {1}".format(e, traceback.format_exc()))

    return identity

if __name__ == '__main__' :
    if len(sys.argv) > 1:
        main(sys.argv[1])

