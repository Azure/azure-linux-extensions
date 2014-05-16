#!/usr/bin/env python

"""
Example Azure Handler script for Linux IaaS
Update example
Reads port from Public Config if present.
Creates service_port.txt in resources dir.
Copies the service to /usr/bin and updates it
with the resource path.
"""
import os
import sys
import imp
import time

waagent=imp.load_source('waagent','/usr/sbin/waagent')
from waagent import LoggerInit

hutil=imp.load_source('HandlerUtil','./resources/HandlerUtil.py')


LoggerInit('/var/log/waagent.log','/dev/stdout')

waagent.Log("update.py starting.") 
waagent.MyDistro=waagent.GetMyDistro()
logfile=waagent.Log

name,seqNo,version,config_dir,log_dir,settings_file,status_file,heartbeat_file,config=hutil.doParse(logfile,'Update')
LoggerInit('/var/log/'+name+'_Update.log','/dev/stdout')

waagent.Log(name+" - update.py starting.") 

logfile=waagent.Log

hutil.doStatusReport(name,seqNo,version,status_file,time.strftime("%Y-%M-%dT%H:%M:%SZ", time.gmtime()),time.strftime("%Y-%M-%dT%H:%M:%SZ", time.gmtime()),name,
               'Update', 'transitioning', '0', 'Updating', 'Process Config', 'transitioning', '0', 'Parsing ' + settings_file)
hutil.doHealthReport(heartbeat_file,'NotReady','0','Proccessing Settings')

# capture the config info from previous installation
# argv[1] is the path to the previous version.

waagent.SetFileContents('./resources/service_port.txt',waagent.GetFileContents(sys.argv[1]+'/resources/service_port.txt'))

# move the service to sbin
waagent.SetFileContents('/usr/sbin/service.py',waagent.GetFileContents('./bin/service.py'))
waagent.ReplaceStringInFile('/usr/sbin/service.py','RESOURCES_PATH',os.path.realpath('./resources'))
os.chmod('/usr/sbin/service.py',0700)


# report ready 
waagent.Log(name+"updating completed.")
hutil.doExit(name,seqNo,version,0,status_file,heartbeat_file,'Update','success','0', 'Update Succeeded.', 'Exit Successfull', 'success', '0', 'Updating Completed.','Ready','0',name+' update completed.')

