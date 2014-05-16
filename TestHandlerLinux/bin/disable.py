#!/usr/bin/env python

"""
Example Azure Handler script for Linux IaaS
Diable example
"""
import os
import imp
import time
import json

waagent=imp.load_source('waagent','/usr/sbin/waagent')
from waagent import LoggerInit

hutil=imp.load_source('HandlerUtil','./resources/HandlerUtil.py')

LoggerInit('/var/log/waagent.log','/dev/stdout')

waagent.Log("disable.py starting.") 

logfile=waagent.Log

name,seqNo,version,config_dir,log_dir,settings_file,status_file,heartbeat_file,config=hutil.doParse(logfile,'Disable')

LoggerInit('/var/log/'+name+'_Disable.log','/dev/stdout')

waagent.Log(name+" - disable.py starting.") 

logfile=waagent.Log

hutil.doStatusReport(name,seqNo,version,status_file,time.strftime("%Y-%M-%dT%H:%M:%SZ", time.gmtime()),
                     time.strftime("%Y-%M-%dT%H:%M:%SZ", time.gmtime()),name,
                     'Disable', 'transitioning', '0', 'Disabling', 'Process Config', 'transitioning', '0', 'Parsing ' + settings_file)
hutil.doHealthReport(heartbeat_file,'NotReady','0','Proccessing Settings')

error_string=''
pid=None
pidfile='./service_pid.txt'
if not os.path.isfile(pidfile):
    error_string += pidfile +" is missing."
    error_string = "Error: " + error_string
    waagent.Error(error_string)
    hutil.doStatusReport(name,seqNo,version,status_file,time.strftime("%Y-%M-%dT%H:%M:%SZ", time.gmtime()),
                     time.strftime("%Y-%M-%dT%H:%M:%SZ", time.gmtime()),name,
                     'Disable', 'transitioning', '0', 'Disabling', 'Process Config', 'transitioning', '0', 'Parsing ' + settings_file)
else:
    pid = waagent.GetFileContents(pidfile)
    
    #stop service.py
    try:
        os.kill(int(pid),7)
    except Exception as e:
        pass
    
    # remove pifdile
    try:
        os.unlink(pidfile)
    except Exception as e:
        pass
    
#Kill heartbeat.py if required.
manifest = waagent.GetFileContents('./HandlerManifest.json')
try:
    s=json.loads(manifest)
except:
    waagent.Error('Error parsing HandlerManifest.json.  Heath report will not be available.')
    hutil.doExit(name,seqNo,version,0,status_file,heartbeat_file,'Disable','NotReady','0', 'Disable service.py succeeded.' + str(pid) + ' created.', 'Exit Successfull', 'success', '0', 'Enable Completed.','NotReady','0',name+' enabled.')
if s[0]['handlerManifest']['reportHeartbeat'] != True :
    hutil.doExit(name,seqNo,version,0,status_file,heartbeat_file,'Disable','NotReady','0', 'Disable service.py succeeded.' + str(pid) + ' created.', 'Exit Successfull', 'success', '0', 'Enable Completed.','Ready','0',name+' enabled.')
try:
    pid = waagent.GetFileContents('./heartbeat.pid')
except:
    waagent.Error('Error reading ./heartbeat.pid.')
    hutil.doExit(name,seqNo,version,0,status_file,heartbeat_file,'Disable','NotReady','0', 'Disable service.py succeeded.' + str(pid) + ' created.', 'Exit Successfull', 'success', '0', 'Enable Completed.','NotReady','0',name+' enabled.')

if waagent.Run('kill '+pid)==0:
    waagent.Log(name+" disabled.")
    hutil.doExit(name,seqNo,version,0,status_file,heartbeat_file,'Disable','NotReady','0', 'Disable service Succeed. Health reporting stoppped.', 'Exit Successfull', 'success', '0', 'Disable Completed.','NotReady','0',name+' disabled.')

