#!/usr/bin/env python

"""
Example Azure Handler script for Linux IaaS
Diable example
"""
import os
import imp
import time

waagent=imp.load_source('waagent','/usr/sbin/waagent')
from waagent import LoggerInit
hutil=imp.load_source('HandlerUtil','./resources/HandlerUtil.py')

LoggerInit('/var/log/waagent.log','/dev/stdout')

waagent.Log("uninstall.py starting.") 
logfile=waagent.Log

name,seqNo,version,config_dir,log_dir,settings_file,status_file,heartbeat_file,config=hutil.doParse(logfile,'Uninstall')

waagent.Log(name+" - uninstall.py starting.") 

logfile=waagent.Log

hutil.doStatusReport(name,seqNo,version,status_file,time.strftime("%Y-%M-%dT%H:%M:%SZ", time.gmtime()),time.strftime("%Y-%M-%dT%H:%M:%SZ", time.gmtime()),name,
               'Uninstall', 'transitioning', '0', 'Uninstalling', 'Process Config', 'transitioning', '0', 'Parsing ' + settings_file)
hutil.doHealthReport(heartbeat_file,'NotReady','0','Proccessing Settings')

error_string=None
servicefile='/usr/sbin/service.py'
if not os.path.isfile(servicefile):
    error_string += servicefile +" is missing."
    error_string = "Error: " + error_string
    waagent.Error(error_string)
    hutil.doExit(name,seqNo,version,1,status_file,heartbeat_file,'Uninstall','error','1', 'Uninstall Failed', 'Remove service.py failed.', 'error', '1',error_string,'NotReady','1','Exiting')
# remove 
os.unlink(servicefile)
# report ready 
waagent.Log(name+" uninstalled.")
hutil.doExit(name,seqNo,version,0,status_file,heartbeat_file,'Uninstall','success','0', 'Uninstall service.py Succeeded', 'Exit Successfull', 'success', '0', 'Uninstall Completed.','Ready','0',name+' uninstalled.')

