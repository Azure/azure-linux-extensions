#!/usr/bin/env python
#
#CustomScript extension
#
# Copyright 2014 Microsoft Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Requires Python 2.6+
#
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

ExtensionShortName = 'LinuxAzureDiagnostic'
AgentDir = '/var/lib/waagent'
MDSDPidFile = AgentDir + '/mdsd.pid'
WorkDir = os.getcwd()
OutputSize = 1024
EnableSyslog= False
waagent.LoggerInit('/var/log/waagent.log','/dev/stdout')
waagent.Log("%s started to handle." %(ExtensionShortName))
hutil =  Util.HandlerUtility(waagent.Log, waagent.Error, ExtensionShortName)
hutil.try_parse_context()

def LogRunGetOutPut(cmd):
    hutil.log("RunCmd "+cmd)
    error,msg = waagent.RunGetOutput(cmd)
    hutil.log("Return "+str(error)+":"+msg)
    return error,msg
rsyslog_ommodule_for_check='omprog.so'
RunGetOutput = LogRunGetOutPut
MdsdFolder = os.path.join(WorkDir,'mdsd')
StartDaemonFilePath = os.path.join(os.getcwd(), __file__)
omi_universal_rpm_name = 'scx-1.6.0-152.universalr.1.x64.sh'
omi_universal_dpkg_name = 'scx-1.6.0-152.universald.1.x64.sh'

DebianConfig = {"installomi":"bash "+omi_universal_dpkg_name+" --install --force;",
                "installrequiredpackage":'dpkg-query -l PACKAGE ;  if [ ! $? == 0 ]; then apt-get update ; apt-get install -y PACKAGE; fi',
                 "packages":('libglibmm-2.4-1c2a',),
                  "restartrsyslog":"service rsyslog restart",
                  "syslogpackages":(),
                 'distrolibs':'debian/* shared/*','checkrsyslog':'(dpkg-query -s rsyslog;dpkg-query -L rsyslog) |grep "Version\|'+rsyslog_ommodule_for_check+'"'
                }

RedhatConfig =  {"installomi":"bash "+omi_universal_rpm_name+" --install --force;",
                 "installrequiredpackage":'rpm -q PACKAGE ;  if [ ! $? == 0 ]; then yum install -y PACKAGE; fi','distrolibs':'redhat',
                 "packages":('glibmm24','tar',),
                'distrolibs':'redhat/* shared/*',
                  "restartrsyslog":"service rsyslog restart",
                 "syslogpackages":('policycoreutils-python',),
                  'checkrsyslog':'(rpm -qi rsyslog;rpm -ql rsyslog)|grep "Version\\|'+rsyslog_ommodule_for_check+'"'
                 }

UbuntuConfig = dict(DebianConfig.items()+
                    {'distrolibs':'debian/* shared/*'
                    }
                    .items())
SuseConfig11 = dict(RedhatConfig.items()+
                    {'installrequiredpackage':'rpm -qi PACKAGE;  if [ ! $? == 0 ]; then zypper --non-interactive install PACKAGE;fi; ','restartrsyslog':'service syslog restart',
                     "packages":('glibmm2',),
                     "syslogpackages":('rsyslog',),
                  'distrolibs':'suse/*'}
                  .items())
SuseConfig12 = dict(RedhatConfig.items()+
                  {'installrequiredpackage':' rpm -qi PACKAGE; if [ ! $? == 0 ]; then zypper --non-interactive install PACKAGE;fi; ','restartrsyslog':'service syslog restart',
                   "packages":('libglibmm-2_4-1','libgthread-2_0-0','ca-certificates-mozilla',),
                    "syslogpackages":('rsyslog',),
                  'distrolibs':'suse12/*'}
                  .items())

CentosConfig = dict(RedhatConfig.items()+
                    {'installrequiredpackag':'rpm -qi PACKAGE; if [ ! $? == 0 ]; then  yum install  -y PACKAGE; fi',
                     "packages":('glibmm24',)}
                  .items())

RSYSLOG_OM_PORT='29131'
All_Dist= {'SuSE:11':SuseConfig11,'debian':DebianConfig,'SuSE':SuseConfig12,'Ubuntu':UbuntuConfig,'SuSE:12':SuseConfig12,'redhat':RedhatConfig,'centos':CentosConfig}
distConfig = None  
dist = platform.dist()
if All_Dist.has_key(dist[0]+":"+dist[1]):
    distConfig =  All_Dist[dist[0]+":"+dist[1]]
elif All_Dist.has_key(dist[0]):
    distConfig =  All_Dist[dist[0]]
else:
    hutil.error("os version:"+dist[0]+" not supported")


def main(command):
    #Global Variables definition
    global EnableSyslog
    if  hutil.get_protected_settings().has_key('enableSyslog'):
        if hutil.get_protected_settings()['enableSyslog'].lower() == 'true':
            EnableSyslog = True
        else:
            EnableSyslog = False
   
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
            setup()
            hutil.do_status_report("Install", "success",'0', "Install succeeded")
        elif re.match("^([-/]*)(enable)", command):
            # if daemon process not runs
            hutil.log("get pid:"+str(get_mdsd_process()))
            if len(get_mdsd_process())!=2 or  hutil.is_current_config_seq_greater_inused():
                stop_mdsd()
                start_daemon()
            hutil.set_inused_config_seq(hutil.get_seq_no())
            hutil.do_status_report("Enable","success",'0',"Enable successded")


        elif re.match("^([-/]*)(daemon)", command):
            start_mdsd()
        elif re.match("^([-/]*)(update)", command):
            hutil.do_status_report("Update", "success",'0', "Update succeeded")

    except Exception, e:
        hutil.error(("Failed to enable the extension with error:{0}, "
                     "{1}").format(e, traceback.format_exc()))
        hutil.do_status_report('Enable','error','0',
                      'Enable failed:{0}'.format(e))


def parse_context(operation):
    hutil = Util.HandlerUtility(waagent.Log, waagent.Error, ExtensionShortName)
    hutil.try_parse_context()
    return 

def setup():
    global EnableSyslog
    if EnableSyslog:
        error,msg = install_rsyslogom()
        if error !=0:
            hutil.error(msg)
    error,msg = copy_distrolibs()
    if error !=0:
        hutil.error(msg)


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
    agent_dir = AgentDir 
    with open(os.path.join(agent_dir,MDSDPidFile),"w") as pidfile:
         pidfile.write(str(os.getpid())+'\n')
         pidfile.close()
    retry = 4
    while retry >0:
        error,msg = install_required_package()
        hutil.log(msg)
        if error ==0:
            break
        else:
            retry-=1
            hutil.log("Sleep 60 retry "+str(retry))
            time.sleep(60)

    install_omi()

    if EnableSyslog and not is_rsylogom_installed():
        install_rsyslogom()
    
    #if EnableSyslog and distConfig.has_key("restartrsyslog"):
    # sometimes after the mdsd is killed port 29131 is accopied by sryslog, don't know why
    #    RunGetOutput(distConfig["restartrsyslog"])   
 
    if os.path.exists("/usr/sbin/semanage"):
        RunGetOutput('semanage port -a -t syslogd_port_t -p tcp 29131;echo ignore already added')

    monitor_file_path = '/var/log/mdsd.err'
    public_settings = hutil.get_public_settings()
    protected_settings = hutil.get_protected_settings()
    xmlContent = protected_settings.get("xmlCfg")
    if not xmlContent or len(xmlContent)==0:
        with open (os.path.join(WorkDir, './defaultCfg.xml'),"r") as defaulCfg:
            xmlContent = defaulCfg.read()
    xml_file =  os.path.join(WorkDir, './xmlCfg.xml')
    
    settings = {
                'storageAccountName':'',
                'storageAccountKey':'',
                'version':'1',
                'namespace':'Linux',    
                 'perftable' :'Perf',
                  'logtable' : 'syslog'
                 }
 
    for s in settings.keys():
        if protected_settings.has_key(s):
            settings[s]=protected_settings[s]
        xmlContent=re.compile(re.escape("#"+s+"#"), re.IGNORECASE).sub(settings[s],xmlContent)


    with open(xml_file,'w') as hfile:
        hfile.write(xmlContent)

    if len(settings['storageAccountName']) >0:
        try:
            from azure.storage import TableService
            ts = TableService(settings['storageAccountName'], settings['storageAccountKey'])
            for t in (settings['perftable']+'Cpu',settings['perftable']+'Disk',settings['perftable']+'Mem',settings['logtable']):
                ts.create_table(settings['namespace']+t+'Ver'+settings['version']+'v0')
            ts.create_table('SchemasTable')
        except Exception,e:
            hutil.error(("Failed to create azure tables (will continue) with error:{0},"
                     "stacktrace:{1}").format(e, traceback.format_exc()))
 
    default_port = RSYSLOG_OM_PORT
    mdsd_log_path = os.path.join(WorkDir,"mdsd.log")
    mdsd_log = None
    copy_env = os.environ
    copy_env['LD_LIBRARY_PATH']=MdsdFolder
    
    command = '{0} -c {1} -p {2} -e {3}'.format(os.path.join(MdsdFolder,"mdsd"),xml_file,default_port,monitor_file_path).split(" ")

    try:
        for restart in range(0,3):
            
            mdsd_log = open (mdsd_log_path,"w")
            hutil.log("Start mdsd "+str(command))
            mdsd = subprocess.Popen(command,
                                     cwd=WorkDir,
                                     stdout=mdsd_log,
                                     stderr=mdsd_log,
                                     env=copy_env)

            with open(os.path.join(agent_dir,MDSDPidFile),"w") as pidfile:
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
                    hutil.do_status_report("Enable","warning",'1',"WARNING: error happens at:"+str(last_error_time)+":"+last_error)
                #if len(last_error) >0 and last_error.find("Error: EnumerateInstances failed") >=0:
                #    hutil.error("Error: EnumerateInstances means mdsd is now in busy loop:")
                #    mdsd.kill()
                #    os.remove(monitor_file_path)
            
                                    
            if mdsd_log:
                mdsd_log.close()
                mdsd_log = None

            error = tail(mdsd_log_path)
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
                                  message=str(e))
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
            if is_still_alive.find('LinuxDiagnostic') > 0 :
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

def copy_distrolibs():
    libs = distConfig['distrolibs']
    if len(libs) >0:
        return RunGetOutput('\cp -f {0} {1}'.format(libs,MdsdFolder))
    return 0,""

def install_omi():
    #Update scenario will be considerd when it comes
    if os.path.exists("/opt/microsoft/omi/bin/omiserver"):
        return 0,"Already installed"
    #hostname=os.uname()[1]
    #if len(hostname) > 20:
        #if hostname is too long, install omi would fail because certificate 
    #   RunGetOutput("hostname "+hostname[0:20]+".domain")
    ret_code,ret_string=RunGetOutput(distConfig["installomi"])
    ret_c2,ret_s2 = RunGetOutput('/opt/microsoft/scx/bin/tools/scxsslconfig -f -d omilocal.cloudapp.net -h omilocal')
    ret_c3,ret_s3 = RunGetOutput('service omiserverd  restart')
    #if len(hostname) > 20:
    #    RunGetOutput("hostname "+hostname)
    return ret_code+ret_c2+ret_c3,ret_string+"####Cert for OMI service may fail to generate, ReDO: ####"+ret_s2+ret_s3
    
def uninstall_omi():
    hutil.log("omi will not be uninstalled")
    return 0,"do nothing"

def is_rsylogom_installed():
    return  os.path.exists("/etc/rsyslog.d/omazurelinuxmds.conf")

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
    else:
        return 1,"rsyslog version can't be deteced"

    if distConfig.has_key("restartrsyslog"):
        RunGetOutput(distConfig["restartrsyslog"])
    else:
        RunGetOutput("service rsyslog restart")
    return 0,"install mdsdom completed"

def install_required_package():
    global EnableSyslog
    cmd_temp = distConfig['installrequiredpackage']
    packages = distConfig['packages']
    if EnableSyslog:
        packages += distConfig["syslogpackages"]
    errorcode = 0
    output_all = ""
    if len(cmd_temp) >0:
        for p in packages:
            cmd = cmd_temp.replace("PACKAGE",p)
            hutil.log(cmd)
            process = subprocess.Popen(cmd,stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True,executable='/bin/bash')
            timeout=360
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
    pos = min(output_size, os.path.getsize(log_file))
    with open(log_file, "r") as log:
        log.seek(-pos, 2)
        buf = log.read(output_size)
        buf = filter(lambda x: x in string.printable, buf)
        return buf.decode("ascii", "ignore")

if __name__ == '__main__' :
    if len(sys.argv) > 1:
        main(sys.argv[1])

