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

import os
import os.path
import re
import sys
import traceback
import tempfile

from Utils.WAAgentUtil import waagent
import Utils.HandlerUtil as Util
import Utils.ScriptUtil as ScriptUtil

# Global Variables
ExtensionShortName = "OmsAgentForLinux"

PackagesDirectory = "packages"
BundleFileName = 'omsagent-1.3.1-15.universal.x64.sh'

# always use upgrade - will handle install if scx, omi are not installed or upgrade if they are
InstallCommandTemplate = './{0} --upgrade --force'
UninstallCommandTemplate = './{0} --remove'
OmsAdminWorkingDirectory = '/opt/microsoft/omsagent/bin'
WorkspaceCheckCommand = './omsadmin.sh -l'
OnboardCommandWithOptionalParamsTemplate = './omsadmin.sh -d opinsights.azure.us -w {0} -s {1} {2}'
ServiceControlWorkingDirectory = '/opt/microsoft/omsagent/bin'
DisableOmsAgentServiceCommand = './service_control disable'
EnableOmsAgentServiceCommand = './service_control enable'

# Change permission of log path
ext_log_path = '/var/log/azure/'
if os.path.exists(ext_log_path):
    os.chmod(ext_log_path, 700)

def main():
    waagent.LoggerInit('/var/log/waagent.log','/dev/stdout', True)
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
        exit_code = 1
        err_msg = ("Failed with error: {0}, {1}").format(e, traceback.format_exc())
        if "LINUXOMSAGENTEXTENSION_ERROR_MULTIPLECONNECTIONS" in str(e):
            exit_code = 10
            err_msg = ("Failed with error: {0}").format(e)

        waagent.Error(err_msg)
        hutil.error(err_msg)
        hutil.do_exit(exit_code, 'Enable','failed', str(exit_code),
                      'Enable failed: {0}'.format(e))


def parse_context(operation):
    hutil = Util.HandlerUtility(waagent.Log, waagent.Error)
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
    ScriptUtil.run_command(hutil, ScriptUtil.parse_args(cmd), file_directory, 'Install', ExtensionShortName, hutil.get_extension_version())


def uninstall(hutil):
    file_directory = os.path.join(os.getcwd(), PackagesDirectory)    

    cmd = UninstallCommandTemplate.format(BundleFileName)
    ScriptUtil.run_command(hutil, ScriptUtil.parse_args(cmd), file_directory, 'Uninstall', ExtensionShortName, hutil.get_extension_version())


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
    proxy = protected_settings.get("proxy")
    vmResourceId = protected_settings.get("vmResourceId")
    stopOnMultipleConnections = public_settings.get("stopOnMultipleConnections")
    if workspaceId is None:
        raise ValueError("Workspace ID cannot be None.")
    if workspaceKey is None:
        raise ValueError("Workspace key cannot be None.")

    if stopOnMultipleConnections is not None and stopOnMultipleConnections is True:
        output_file = tempfile.NamedTemporaryFile('w')
        output_file.close()

        list_exit_code = ScriptUtil.run_command(hutil, ScriptUtil.parse_args(WorkspaceCheckCommand), OmsAdminWorkingDirectory, 'Check If Already Onboarded', ExtensionShortName, hutil.get_extension_version(), False, interval = 30, std_out_file_name = output_file.name)

        # If the printout includes "No Workspace" then there are no workspaces onboarded to the machine
        # Otherwise the workspaces that have been onboarded are listed in the output
        output_file_handle = open(output_file.name, 'r')
        connectionExists = False
        if "No Workspace" not in output_file_handle.read():
            connectionExists = True
        output_file_handle.close()

        if connectionExists:
            err_msg = ("This machine is already connected to some other Log "
                       "Analytics workspace, please set stopOnMultipleConnections "
                       "to false in public settings or remove this property, "
                       "so this machine can connect to new workspaces, also it "
                       "means this machine will get billed multiple times for "
                       "each workspace it report to. "
                       "(LINUXOMSAGENTEXTENSION_ERROR_MULTIPLECONNECTIONS)")
            # This exception will get caught by the main clause
            raise Exception(err_msg)

    proxyParam = ""
    if proxy is not None:
        proxyParam = "-p {0}".format(proxy)
        
    vmResourceIdParam = ""
    if vmResourceId is not None:
        vmResourceIdParam = "-a {0}".format(vmResourceId)

    optionalParams = "{0} {1}".format(proxyParam, vmResourceIdParam)
    cmd = OnboardCommandWithOptionalParamsTemplate.format(workspaceId, workspaceKey, optionalParams)

    exit_code = ScriptUtil.run_command(hutil, ScriptUtil.parse_args(cmd), OmsAdminWorkingDirectory, 'Onboard', ExtensionShortName, hutil.get_extension_version(), False)

    # if onboard succeeds we continue, otherwise fail fast
    if exit_code == 0:
        ScriptUtil.run_command(hutil, ScriptUtil.parse_args(EnableOmsAgentServiceCommand), ServiceControlWorkingDirectory, 'Enable', ExtensionShortName, hutil.get_extension_version())
    else:
        sys.exit(exit_code)


def disable(hutil):
    ScriptUtil.run_command(hutil, ScriptUtil.parse_args(DisableOmsAgentServiceCommand), ServiceControlWorkingDirectory, 'Disable', ExtensionShortName, hutil.get_extension_version())


if __name__ == '__main__' :
    main()
