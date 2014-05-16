#!/usr/bin/env python

"""
Example Azure Handler script for Linux IaaS
Heartbeat example
"""
import os
import imp
import time

waagent=imp.load_source('waagent','/usr/sbin/waagent')
from waagent import LoggerInit

hutil=imp.load_source('HandlerUtil','./resources/HandlerUtil.py')
LoggerInit('/var/log/waagent.log','/dev/stdout')

waagent.Log("hearbeat.py starting.") 

logfile=waagent.Log

name,seqNo,version,config_dir,log_dir,settings_file,status_file,heartbeat_file,config=hutil.doParse(logfile,'Hearbeat')
LoggerInit('/var/log/'+name+'_Hearbeat.log','/dev/stdout')

waagent.Log(name+" - hearbeat.py starting.") 

logfile=waagent.Log
pid=None
pidfile='./service_pid.txt'
retries=5

waagent.SetFileContents('./heartbeat.pid',str(os.getpid()))

while(True):
    if os.path.exists(pidfile):
        pid=waagent.GetFileContents('./service_pid.txt')
        if waagent.Run("ps --no-headers " + str(pid),chk_err=False) == 0:
            # running
            retries=5
            waagent.Log(name+" service.py is running with PID="+pid)
            hutil.doHealthReport(heartbeat_file,'Ready','0','service.py is running.')
            time.sleep(30)
            continue
        else:
            # died -- retries and wait for 2 min
            retries-=1
            waagent.Error(name+" service.py is Not running.")
            if retries==4:
                hutil.doHealthReport(heartbeat_file,'NotRunning','1','ERROR -  service.py Unknown or NOT running')
            if retries!=0:
                time.sleep(120)
            else:
                break
    else:
        # dead.  report not ready 
        waagent.Error(name+" service.py is Not running.")
        hutil.doHealthReport(heartbeat_file,'NotReady','1','ERROR -  service.py is NOT running')
        break

waagent.Log(name+" heartbeat.py exiting.  service.py is NOT running")

