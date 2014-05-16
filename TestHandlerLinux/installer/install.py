#!/usr/bin/env python

"""
Example Azure Handler script for Linux IaaS
Install example
Reads port from Public Config if present.
Creates service_port.txt in resources dir.
"""
import os
import imp
import time

waagent=imp.load_source('waagent','/usr/sbin/waagent')
from waagent import LoggerInit

hutil=imp.load_source('HandlerUtil','./resources/HandlerUtil.py')

LoggerInit('/var/log/waagent.log','/dev/stdout')

waagent.Log("install.py starting.") 
logfile=waagent.Log

name,seqNo,version,config_dir,log_dir,settings_file,status_file,heartbeat_file,config=hutil.doParse(logfile,'Install')
LoggerInit('/var/log/'+name+'_Install.log','/dev/stdout')

waagent.Log(name+" - install.py starting.") 

logfile=waagent.Log

hutil.doStatusReport(name,seqNo,version,status_file,time.strftime("%Y-%M-%dT%H:%M:%SZ", time.gmtime()),time.strftime("%Y-%M-%dT%H:%M:%SZ", time.gmtime()),name,
               'Install', 'transitioning', '0', 'Installing', 'Process Config', 'transitioning', '0', 'Parsing ' + settings_file)
hutil.doHealthReport(heartbeat_file,'NotReady','0','Proccessing Settings')
pub=""
priv = ""
# process the config info from public and private config
try:
    pub = config['runtimeSettings'][0]['handlerSettings']['publicSettings']
except:
    waagent.Error("json threw an exception processing config PublicSettings.")    
try:
    priv = config['runtimeSettings'][0]['handlerSettings']['protectedSettings']
except:
    waagent.Error("json threw an exception processing config protectedSettings.")    

waagent.Log("PublicConfig =" + repr(pub) )
port=None
if len(pub):
    try:
        port = pub['port']
    except:
        waagent.Error("json threw an exception processing public setting: port")

waagent.Log("ProtectedConfig =" + repr(priv) )
if len(priv):
    try:
        port = priv['port']
    except:
        waagent.Error("json threw an exception processing protected setting: port")

if port == None:
    port = "3000"

error_string=None
if port == None:
    error_string += "ServicePort is empty. "
    error_string = "Error: " + error_string
    waagent.Error(error_string)
    hutil.doExit(name,seqNo,version,1,status_file,heartbeat_file,'Install/Enable','errior','1', 'Install Failed', 'Parse Config', 'error', '1',error_string,'NotReady','1','Exiting')

error_string=None
waagent.SetFileContents('./resources/service_port.txt',port)

# move the service to sbin
waagent.SetFileContents('/usr/sbin/service.py',waagent.GetFileContents('./bin/service.py'))
waagent.ReplaceStringInFile('/usr/sbin/service.py','RESOURCES_PATH',os.path.realpath('./resources'))
os.chmod('/usr/sbin/service.py',0700)


# report ready 
waagent.Log("HandlerTestLinux installation completed.")
hutil.doExit(name,seqNo,version,0,status_file,heartbeat_file,'Install','success','0', 'Install Succeeded.', 'Exit Successfull', 'success', '0', 'Installation Completed.','Ready','0',name+' installation completed.')

