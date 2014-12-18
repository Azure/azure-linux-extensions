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

from Utils.WAAgentUtil import waagent
import Utils.HandlerUtil as Util

ExtensionShortName = 'AzureEnhancedMonitoring'

def installService(hutil):
    pass

def uninstallService(hutil):
    pass

def enable(hutil):
    pass

def disable(hutil):
    pass

def dummy_command(operation, status, msg):
    hutil = parse_context(operation)
    hutil.do_exit(0, operation, status, '0', msg)

def main():
    waagent.LoggerInit('/var/log/waagent.log','/dev/stdout')
    waagent.Log("{0} started to handle.".format(ExtensionShortName))

    try:
        for a in sys.argv[1:]:        
            if re.match("^([-/]*)(disable)", a):
                hutil = parse_context("Disable")
                disable(hutil)
            elif re.match("^([-/]*)(uninstall)", a):
                dummy_command("Uninstall", "success", "Uninstall succeeded")
            elif re.match("^([-/]*)(install)", a):
                dummy_command("Install", "success", "Install succeeded")
            elif re.match("^([-/]*)(enable)", a):
                hutil = parse_context("Enable")
                enable(hutil)
            elif re.match("^([-/]*)(update)", a):
                dummy_command("Update", "success", "Update succeeded")
    except Exception, e:
        hutil.error(("Failed to enable the extension with error:{0}, "
                     "{1}").format(e, traceback.format_exc()))
        hutil.do_exit(1, 'Enable','failed','0', 
                      'Enable failed:{0}'.format(e))

if __name__ == '__main__':
    main()
