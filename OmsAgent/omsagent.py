#!/usr/bin/env python
#
#OmsAgent extension
#
# Copyright 2015 Microsoft Corporation
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
import os.path
import re
import sys
import traceback
import json
from codecs import *

from Utils.WAAgentUtil import waagent
import Utils.HandlerUtil as Util
import Utils.ScriptUtil as ScriptUtil

# Global Variables
mfile = os.path.join(os.getcwd(), 'HandlerManifest.json')
with open(mfile,'r') as f:
    manifest = json.loads(f.read())[0]
    ExtensionShortName = manifest['name']
    Version = manifest['version']

PackagesDirectory = "packages"
BundleFileName = 'omsagent-1.1.0-28.universal.x64.sh'

# always use upgrade - will handle install if scx, omi are not installed or upgrade if they are
InstallCommandTemplate = './{0} --upgrade'
UninstallCommandTemplate = './{0} --remove'
OmsAdminWorkingDirectory = '/opt/microsoft/omsagent/bin'
OnboardCommandTemplate = './omsadmin.sh -w {0} -s {1}'
ServiceControlWorkingDirectory = '/opt/microsoft/omsagent/bin'
DisableOmsAgentServiceCommand = './service_control disable'
EnableOmsAgentServiceCommand = './service_control enable'

# Change permission of log path
ext_log_path = '/var/log/azure/'
if os.path.exists(ext_log_path):
    os.chmod(ext_log_path, 700)

#Main function is the only entrance to this extension handler
def main():
    #Global Variables definition
    waagent.LoggerInit('/var/log/waagent.log','/dev/stdout',True)
    waagent.Log("%s started to handle." %(ExtensionShortName))

    try:
        for a in sys.argv[1:]:
            if re.match("^([-/]*)(disable)", a):
                hutil = parse_context("Disable")
                disable(hutil)
            elif re.match("^([-/]*)(uninstall)", a):
                hutil = parse_context("Uninstall")
                uninstall(hutil)
            elif re.match("^([-/]*)(install)", a):
                hutil = parse_context("Install")
                install(hutil)
            elif re.match("^([-/]*)(enable)", a):
                hutil = parse_context("Enable")
                enable(hutil)
            elif re.match("^([-/]*)(update)", a):
                dummy_command("Update", "success", "Update succeeded")
    except Exception as e:
        err_msg = ("Failed to enable the extension with error: {0}, "
                   "{1}").format(e, traceback.format_exc())
        waagent.Error(err_msg)
        hutil.error(err_msg)
        hutil.do_exit(1, 'Enable','failed','0',
                      'Enable failed: {0}'.format(e))


def parse_context(operation):
    hutil = Util.HandlerUtility(waagent.Log, waagent.Error, ExtensionShortName)
    hutil.do_parse_context(operation)
    return hutil
    
    
def dummy_command(operation, status, msg):
    hutil = parse_context(operation)
    hutil.do_exit(0, operation, status, '0', msg)


def install(hutil):
    file_directory = os.path.join(os.getcwd(), PackagesDirectory)
    file_path = os.path.join(file_directory, BundleFileName)

    os.chmod(file_path, 100)
    cmd = InstallCommandTemplate.format(BundleFileName)
    ScriptUtil.run_command(hutil, ScriptUtil.parse_args(cmd), file_directory, 'Install', ExtensionShortName, Version)


def uninstall(hutil):
    file_directory = os.path.join(os.getcwd(), PackagesDirectory)    

    cmd = UninstallCommandTemplate.format(BundleFileName)
    ScriptUtil.run_command(hutil, ScriptUtil.parse_args(cmd), file_directory, 'Uninstall', ExtensionShortName, Version)


def enable(hutil):
    hutil.exit_if_enabled()

    public_settings = hutil.get_public_settings()
    protected_settings = hutil.get_protected_settings()
    if public_settings is None:
        raise ValueError("Public configuration cannot be None.")
    if protected_settings is None:
        raise ValueError("Private configuration cannot be None.")

    workspaceId = public_settings.get("workspaceId")
    workspaceKey = protected_settings.get("workspaceKey")
    if workspaceId is None:
        raise ValueError("Workspace ID cannot be None.")
    if workspaceKey is None:
        raise ValueError("Workspace key cannot be None.")

    cmd = OnboardCommandTemplate.format(workspaceId, workspaceKey)
    exit_code = ScriptUtil.run_command(hutil, ScriptUtil.parse_args(cmd), OmsAdminWorkingDirectory, 'Onboard', ExtensionShortName, Version, False)
    # if onboard succeeds we continue, otherwise fail fast
    if exit_code == 0:
        ScriptUtil.run_command(hutil, ScriptUtil.parse_args(EnableOmsAgentServiceCommand), ServiceControlWorkingDirectory, 'Enable', ExtensionShortName, Version)
    else:
        sys.exit(exit_code)


def disable(hutil):
    ScriptUtil.run_command(hutil, ScriptUtil.parse_args(DisableOmsAgentServiceCommand), ServiceControlWorkingDirectory, 'Disable', ExtensionShortName, Version)


if __name__ == '__main__' :
    main()
