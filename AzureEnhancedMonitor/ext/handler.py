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

import os
import subprocess

from Utils.WAAgentUtil import waagent
import Utils.HandlerUtil as util

ExtensionShortName = 'AzureEnhancedMonitor'

def enable(hutil):
    pid = None
    baseDir = hutil.get_base_dir()
    pidFile = os.path.join(baseDir, "pid")
   
    #Check whether monitor process is running.
    #If it does, return. Otherwise clear pid file
    if os.path.isfile(pidFile):
        pid = waagent.GetFileContents(pidFile)
        if os.path.isfile(os.path.join("/proc", pid)):
            hutil.do_exit(0, 'Enable', 'success', '0', 
                          'Azure Enhanced Monitor is already running')
            return
        else:
            os.remove(pidFile)

    aemFile = os.path.join(baseDir, "aem.py")
    devnull = open(os.devnull, 'w')
    child = subprocess.Popen([aemFile], stdout=devnull, stderr=devnull)
    if child.pid == None or child.pid < 1:
        hutil.do_exit(1, 'Enable', 'error', '1', 
                      'Failed to launch Azure Enhanced Monitor')
    else:
        waagent.SetFileContents(pidFile, str(child.pid))
        hutil.do_exit(0, 'Enable', 'success', '0', 
                      'Azure Enhanced Monitor is enabled')

def disable(hutil):
    pid = None
    baseDir = hutil.get_base_dir()
    pidFile = os.path.join(baseDir, "pid")
   
    #Check whether monitor process is running.
    #If it does, kill it. Otherwise clear pid file
    if os.path.isfile(pidFile):
        pid = waagent.GetFileContents(pidFile)
        if os.path.isfile(os.path.join("/proc", pid)):
            os.kill(pid, 9)
            os.remove(pidFile)
            hutil.do_exit(0, 'Disable', 'success', '0', 
                          'Azure Enhanced Monitor is disabled')
        os.remove(pidFile)

    hutil.do_exit(0, 'Disable', 'success', '0', 
                  'Azure Enhanced Monitor is not running')

def dummy_command(operation, status, msg):
    hutil = parse_context(operation)
    hutil.do_exit(0, operation, status, '0', msg)

def main():
    waagent.LoggerInit('/var/log/waagent.log','/dev/stdout')
    waagent.Log("{0} started to handle.".format(ExtensionShortName))

    operation = None
    try:
        for a in sys.argv[1:]:        
            if re.match("^([-/]*)(disable)", a):
                operation = "Disable"
                hutil = parse_context("Disable")
                disable(hutil)
            elif re.match("^([-/]*)(uninstall)", a):
                operation = "Uninstall"
                dummy_command("Uninstall", "success", "Uninstall succeeded")
            elif re.match("^([-/]*)(install)", a):
                operation = "Install"
                dummy_command("Install", "success", "Install succeeded")
            elif re.match("^([-/]*)(enable)", a):
                operation = "Enable"
                hutil = parse_context("Enable")
                enable(hutil)
            elif re.match("^([-/]*)(update)", a):
                operation = "Update"
                dummy_command("Update", "success", "Update succeeded")
    except Exception, e:
        hutil.error(("Extension has run into an error:{0}, {1}, "
                     "{2}").format(operation, e, traceback.format_exc()))
        hutil.do_exit(1, operation,'failed','0', 
                      '{0} failed:{1}'.format(operation, e))

def parse_context(operation):
    hutil = util.HandlerUtility(waagent.Log, waagent.Error, ExtensionShortName)
    hutil.do_parse_context(operation)
    return hutil

if __name__ == '__main__':
    main()
