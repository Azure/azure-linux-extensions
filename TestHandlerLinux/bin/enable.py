#!/usr/bin/env python

"""
Example Azure Handler script for Linux IaaS
Enable example
"""
import os
import imp
import subprocess
import time
import json

waagent=imp.load_source('waagent','/usr/sbin/waagent')
from waagent import LoggerInit

hutil=imp.load_source('HandlerUtil','./resources/HandlerUtil.py')


LoggerInit('/var/log/waagent.log','/dev/stdout')

waagent.Log("enable.py starting.") 

logfile=waagent.Log

name,seqNo,version,config_dir,log_dir,settings_file,status_file,heartbeat_file,config=hutil.doParse(logfile,'Enable')
LoggerInit('/var/log/'+name+'_Enable.log','/dev/stdout')

waagent.Log(name+" - enable.py starting.") 

logfile=waagent.Log

hutil.doStatusReport(name,seqNo,version,status_file,time.strftime("%Y-%M-%dT%H:%M:%SZ", time.gmtime()),
                     time.strftime("%Y-%M-%dT%H:%M:%SZ", time.gmtime()),name,'Enable', 'NotReady', '0', 'Enabling',
                     'Process Config', 'NotReady', '0', 'Parsing ' + settings_file)
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

error_string=''

if port == None:
    error_string += "ServicePort is empty. "
    error_string = "Error: " + error_string
    waagent.Error(error_string)
    hutil.doExit(name,seqNo,version,1,status_file,heartbeat_file,'Enable','NotReady','1', 'Enable Failed', 'Read service_port.txt', 'NotReady', '1',error_string,'NotReady','1','Exiting')


#if already running, kill and spawn new service.py to get current port
pid=None
pathdir='/usr/sbin'
filepath=pathdir+'/service.py'
pidfile='./service_pid.txt'
if os.path.exists(pidfile):
    pid=waagent.GetFileContents('./service_pid.txt')
    try :
        os.kill(int(pid),7)
    except Exception as e:
        pass
    try:
        os.unlink(pidfile)
    except Exception as e:
        pass
    time.sleep(3) # wait for the socket to close
try:
    pid = subprocess.Popen(filepath+' -p ' + port,shell=True,cwd=pathdir).pid
except Exception as e:
    waagent.Error('Exception launching ' + filepath + str(e))

if pid == None or pid < 1 :
    waagent.Error('Error launching ' + filepath + '.')
else :
    waagent.Log("Spawned "+ filepath + " PID = " + str(pid))
        
waagent.SetFileContents('./service_pid.txt',str(pid))

# report ready 
waagent.Log(name+" enabled.")

hutil.doStatusReport(name,seqNo,version,status_file,time.strftime("%Y-%M-%dT%H:%M:%SZ", time.gmtime()),
                     time.strftime("%Y-%M-%dT%H:%M:%SZ", time.gmtime()),name,'Enable','Ready','0',
                     'Enable service Succeed.', 'Exit Successfull', 'Ready', '0', 'Enable Completed.')

#Spawn heartbeat.py if required.
manifest = waagent.GetFileContents('./HandlerManifest.json')
s=None
try:
    s=json.loads(manifest)
except:
    waagent.Error('Error parsing HandlerManifest.json.  Health reports will not be available.')
    hutil.doExit(name,seqNo,version,0,status_file,heartbeat_file,'Enable','Ready','0', 'Enable service Succeed.  Health  reports will not be available.', 'Exit Successfull', 'success', '0', 'Enable Completed.','Ready','0',name+' enabled.')
if s and s[0]['handlerManifest']['reportHeartbeat'] != True :
        waagent.Log('No heartbeat required.  Health reports will not be available.')
        hutil.doExit(name,seqNo,version,0,status_file,heartbeat_file,'Enable','Ready','0', 'Enable service Succeed.  Health  reports will not be available.', 'Exit Successfull', 'success', '0', 'Enable Completed.','Ready','0',name+' enabled.')

dirpath=os.path.realpath('./')
try:
    pid = subprocess.Popen(dirpath+'/bin/heartbeat.py',shell=True,cwd=dirpath).pid
except:
    waagent.Error('Error launching'+dirpath+'/bin/heartbeat.py!  Health reports will not be available.')
    hutil.doExit(name,seqNo,version,0,status_file,heartbeat_file,'Enable','Ready','0', 'Enable service Succeed.  Health reports will not be available.', 'Exit Successfull', 'success', '0', 'Enable Completed.','Ready','0',name+' enabled.')
    
waagent.Log(name+" heartbeat.py started Health reports are available.")
hutil.doExit(name,seqNo,version,0,status_file,heartbeat_file,'Enable','Ready','0', 'Enable service Succeed.  Health reports are available.', 'Exit Successfull', 'success', '0', 'Enable Completed.','Ready','0',name+' enabled.')

        
        
