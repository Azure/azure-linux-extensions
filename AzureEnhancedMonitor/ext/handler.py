#!/usr/bin/env python
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

import sys
import re
import os
import subprocess
import traceback
import time
import aem
import string
from Utils.WAAgentUtil import waagent, InitExtensionEventLog
import Utils.HandlerUtil as util

ExtensionShortName = 'AzureEnhancedMonitor'
ExtensionFullName  = 'Microsoft.OSTCExtensions.AzureEnhancedMonitor'
ExtensionVersion   = 'AzureEnhancedMonitor'

def printable(s):
    return filter(lambda c : c in string.printable, str(s))

def enable(hutil):
    pidFile = os.path.join(aem.LibDir, "pid");
   
    #Check whether monitor process is running.
    #If it does, return. Otherwise clear pid file
    if os.path.isfile(pidFile):
        pid = waagent.GetFileContents(pidFile)
        if os.path.isdir(os.path.join("/proc", pid)):
            if hutil.is_seq_smaller():
                hutil.do_exit(0, 'Enable', 'success', '0', 
                              'Azure Enhanced Monitor is already running')
            else:
                waagent.Log("Stop old daemon: {0}".format(pid))
                os.kill(int(pid), 9)
        os.remove(pidFile)

    args = [os.path.join(os.getcwd(), __file__), "daemon"]
    devnull = open(os.devnull, 'w')
    child = subprocess.Popen(args, stdout=devnull, stderr=devnull)
    if child.pid == None or child.pid < 1:
        hutil.do_exit(1, 'Enable', 'error', '1', 
                      'Failed to launch Azure Enhanced Monitor')
    else:
        hutil.save_seq()
        waagent.SetFileContents(pidFile, str(child.pid))
        waagent.Log(("Daemon pid: {0}").format(child.pid))
        hutil.do_exit(0, 'Enable', 'success', '0', 
                      'Azure Enhanced Monitor is enabled')

def disable(hutil):
    pidFile = os.path.join(aem.LibDir, "pid");
   
    #Check whether monitor process is running.
    #If it does, kill it. Otherwise clear pid file
    if os.path.isfile(pidFile):
        pid = waagent.GetFileContents(pidFile)
        if os.path.isdir(os.path.join("/proc", pid)):
            waagent.Log(("Stop daemon: {0}").format(pid))
            os.kill(int(pid), 9)
            os.remove(pidFile)
            hutil.do_exit(0, 'Disable', 'success', '0', 
                          'Azure Enhanced Monitor is disabled')
        os.remove(pidFile)
    
    hutil.do_exit(0, 'Disable', 'success', '0', 
                  'Azure Enhanced Monitor is not running')

def daemon(hutil):
    publicConfig = hutil.get_public_settings()
    privateConfig = hutil.get_protected_settings()
    config = aem.EnhancedMonitorConfig(publicConfig, privateConfig)
    monitor = aem.EnhancedMonitor(config)
    hutil.set_verbose_log(config.isVerbose())
    InitExtensionEventLog(hutil.get_name())
    while True:
        waagent.Log("Collecting performance counter.")
        startTime = time.time()
        try:
            monitor.run()
            message = ("deploymentId={0} roleInstance={1} OK"
                       "").format(config.getVmDeploymentId(), 
                                  config.getVmRoleInstance())
            hutil.do_status_report("Enable", "success", 0, message)

        except Exception as e:
            waagent.Error("{0} {1}".format(printable(e), 
                                           traceback.format_exc()))
            hutil.do_status_report("Enable", "error", 0, "{0}".format(e))
        waagent.Log("Finished collection.")
        timeElapsed = time.time() - startTime
        timeToWait = (aem.MonitoringInterval - timeElapsed)
        #Make sure timeToWait is in the range [0, aem.MonitoringInterval)
        timeToWait = timeToWait % aem.MonitoringInterval
        time.sleep(timeToWait)

def grace_exit(operation, status, msg):
    hutil = parse_context(operation)
    hutil.do_exit(0, operation, status, '0', msg)

def parse_context(operation):
    hutil = util.HandlerUtility(waagent.Log, waagent.Error, ExtensionShortName, ExtensionFullName, ExtensionVersion)
    hutil.do_parse_context(operation)
    return hutil

def main():
    waagent.LoggerInit('/var/log/waagent.log','/dev/stdout')
    waagent.Log("{0} started to handle.".format(ExtensionShortName))
    
    if not os.path.isdir(aem.LibDir):
        os.makedirs(aem.LibDir)
    
    for command in sys.argv[1:]:
        if re.match("^([-/]*)(install)", command):
            grace_exit("install", "success", "Install succeeded")
        if re.match("^([-/]*)(uninstall)", command):
            grace_exit("uninstall", "success", "Uninstall succeeded")
        if re.match("^([-/]*)(update)", command):
            grace_exit("update", "success", "Update succeeded")

        try:
            if re.match("^([-/]*)(enable)", command):
                hutil = parse_context("enable")
                enable(hutil)
            elif re.match("^([-/]*)(disable)", command):
                hutil = parse_context("disable")
                disable(hutil)
            elif re.match("^([-/]*)(daemon)", command):
                hutil = parse_context("enable")
                daemon(hutil)
        except Exception as e:
            hutil.error("{0}, {1}".format(e, traceback.format_exc()))
            hutil.do_exit(1, command, 'failed','0', 
                          '{0} failed:{1}'.format(command, e))

if __name__ == '__main__':
    main()
