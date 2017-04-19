#!/usr/bin/env python
#
# OmsAgentForLinux Extension
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
import time
import platform

from Utils.WAAgentUtil import waagent
import Utils.HandlerUtil as Util

# Global Variables
PackagesDirectory = 'packages'
BundleFileName = 'omsagent-1.3.4-15.universal.x64.sh'

# Always use upgrade - will handle install if scx, omi are not installed or upgrade if they are
InstallCommandTemplate = '{0} --upgrade'
UninstallCommandTemplate = '{0} --remove'
OmsAdminPath = '/opt/microsoft/omsagent/bin/omsadmin.sh'
WorkspaceCheckCommandTemplate = '{0} -l'
OnboardCommandWithOptionalParamsTemplate = '{0} -d opinsights.azure.us -w {1} -s {2} {3}'
ServiceControlPath = '/opt/microsoft/omsagent/bin/service_control'
DisableOmsAgentServiceCommandTemplate = '{0} disable'
EnableOmsAgentServiceCommandTemplate = '{0} enable'

# Change permission of log path
ext_log_path = '/var/log/azure/'
if os.path.exists(ext_log_path):
    os.chmod(ext_log_path, 700)


def main():
    waagent.LoggerInit('/var/log/waagent.log','/dev/stdout', True)
    waagent.Log('OmsAgentForLinux started to handle.')

    # Determine the operation being executed
    operation = None
    try:
        for a in sys.argv[1:]:
            if re.match('^([-/]*)(disable)', a):
                operation = 'Disable'
            elif re.match('^([-/]*)(uninstall)', a):
                operation = 'Uninstall'
            elif re.match('^([-/]*)(install)', a):
                operation = 'Install'
            elif re.match('^([-/]*)(enable)', a):
                operation = 'Enable'
            elif re.match('^([-/]*)(update)', a):
                operation = 'Update'
    except Exception as e:
        waagent.Error(e.message)

    if operation is None:
        waagent.Error('No valid operation provided')
        sys.exit(1)

    # Set up for exit code and any error messages
    exit_code = 0
    message = operation + ' succeeded'

    # Invoke operation
    try:
        hutil = parse_context(operation)
        vm_supported, vm_dist, vm_ver = is_vm_supported_for_extension()
        if vm_supported:
            exit_code = operations[operation](hutil)
        else:
            log_and_exit(hutil, operation, 51, 'Unsupported operation system: {0} {1}'.format(
                         vm_dist, vm_ver))

        if exit_code is not 0:
            message = (operation + ' failed with exit code {0}').format(exit_code)

    # ValueError may be thrown by enable
    # KeyError may be thrown by parse_context
    except (ValueError, KeyError) as e:
        exit_code = 11
        message = (operation + ' failed with error: {0}').format(e.message)

    except Exception as e:
        exit_code = 1
        message = (operation + ' failed with error: {0}, {1}').format(e, traceback.format_exc())

        if 'LINUXOMSAGENTEXTENSION_ERROR_MULTIPLECONNECTIONS' in str(e):
            exit_code = 10
            message = (operation + ' failed with error: {0}').format(e.message)

    # Finish up and log messages
    log_and_exit(hutil, operation, exit_code, message)


def parse_context(operation):
    hutil = Util.HandlerUtility(waagent.Log, waagent.Error)
    hutil.do_parse_context(operation)
    return hutil


def is_vm_supported_for_extension():
    '''
    Returns for platform.linux_distribution() vary widely in format, such as '7.3.1611' returned
    for a machine with CentOS 7, so the first provided digits must match
    '''
    supported_dists = {'redhat' : ('5', '6', '7'), # CentOS
                       'centos' : ('5', '6', '7'), # CentOS
                       'red hat' : ('5', '6', '7'), # Oracle, RHEL
                       'oracle' : ('5', '6', '7'), # Oracle
                       'debian' : ('6', '7', '8'), # Debian
                       'ubuntu' : ('12.04', '14.04', '15.04', '15.10', '16.04'), # Ubuntu
                       'suse' : ('11', '12') #SLES
    }

    try:
        vm_dist, vm_ver, vm_id = platform.linux_distribution()
    except AttributeError:
        vm_dist, vm_ver, vm_id = platform.dist()

    vm_supported = False

    # Find this VM distribution in the supported list
    for supported_dist in supported_dists.keys():
        if not vm_dist.lower().startswith(supported_dist):
            continue

        # Check if this VM distribution version is supported
        vm_ver_split = vm_ver.split('.')
        for supported_ver in supported_dists[supported_dist]:
            supported_ver_split = supported_ver.split('.')

            # If vm_ver is at least as precise (at least as many digits) as supported_ver and
            #   matches all the supported_ver digits, then this VM is guaranteed to be supported
            vm_ver_match = True
            for idx, supported_ver_num in enumerate(supported_ver_split):
                try:
                    vm_ver_num = vm_ver_split[idx]
                except IndexError:
                    vm_ver_match = False
                    break
                if vm_ver_num is not supported_ver_num:
                    vm_ver_match = False
                    break
            if vm_ver_match:
                vm_supported = True
                break

        if vm_supported:
            break

    return vm_supported, vm_dist, vm_ver


def dummy_command(hutil):
    return 0


def run_command_and_log(hutil, cmd, check_error = True, log_cmd = True):
    exit_code, output = waagent.RunGetOutput(cmd, check_error, log_cmd)
    hutil.log('Output of command "{0}": \n{1}'.format(cmd, output))
    return exit_code


def run_command_with_retries(hutil, cmd, retries, check_error = True, log_cmd = True,
                             initial_sleep_time = 30, sleep_increase_factor = 1):
    '''
    Some commands fail because the package manager is locked (apt-get/dpkg only); this will
      allow retries on failing commands.
    Logic used: will retry up to retries times with initial_sleep_time in between tries
    Note: install operation times out from WAAgent at 15 minutes, so do not wait longer.
    '''
    try_count = 0
    sleep_time = initial_sleep_time # seconds
    while try_count <= retries:
        exit_code = run_command_and_log(hutil, cmd, check_error, log_cmd)
        if exit_code is 0:
            break
        try_count += 1
        hutil.log('Retrying command {0} because it failed with exit code {1}'.format(cmd,
                  exit_code))
        time.sleep(sleep_time)
        sleep_time *= sleep_increase_factor

    return exit_code


def log_and_exit(hutil, operation, exit_code = 1, message = ''):
    if exit_code is 0:
        waagent.Log(message)
        hutil.log(message)
        hutil.do_exit(exit_code, operation, 'success', str(exit_code), message)
    else:
        waagent.Error(message)
        hutil.error(message)
        hutil.do_exit(exit_code, operation, 'failed', str(exit_code), message)


def install(hutil):
    file_directory = os.path.join(os.getcwd(), PackagesDirectory)
    file_path = os.path.join(file_directory, BundleFileName)

    os.chmod(file_path, 100)
    cmd = InstallCommandTemplate.format(file_path)
    waagent.Log('Running command "{0}"'.format(cmd))

    # Retry, since install can fail due to concurrent package operations
    exit_code = run_command_with_retries(hutil, cmd, retries = 10)
    return exit_code


def uninstall(hutil):
    file_directory = os.path.join(os.getcwd(), PackagesDirectory)
    file_path = os.path.join(file_directory, BundleFileName)

    os.chmod(file_path, 100)
    cmd = UninstallCommandTemplate.format(file_path)
    waagent.Log('Running command "{0}"'.format(cmd))

    # Retry, since uninstall can fail due to concurrent package operations
    exit_code = run_command_with_retries(hutil, cmd, retries = 10)
    return exit_code


def enable(hutil):
    waagent.Log('Handler not enabled. Starting onboarding.')
    public_settings = hutil.get_public_settings()
    protected_settings = hutil.get_protected_settings()
    if public_settings is None:
        raise ValueError('Public configuration must be provided')
    if protected_settings is None:
        raise ValueError('Private configuration must be provided')

    workspaceId = public_settings.get('workspaceId')
    workspaceKey = protected_settings.get('workspaceKey')
    proxy = protected_settings.get('proxy')
    vmResourceId = protected_settings.get('vmResourceId')
    stopOnMultipleConnections = public_settings.get('stopOnMultipleConnections')
    if workspaceId is None:
        raise ValueError('Workspace ID must be provided')
    if workspaceKey is None:
        raise ValueError('Workspace key must be provided')

    if stopOnMultipleConnections is not None and stopOnMultipleConnections is True:
        check_wkspc_cmd = WorkspaceCheckCommandTemplate.format(OmsAdminPath)
        list_exit_code, output = waagent.RunGetOutput(check_wkspc_cmd, chk_err=False)

        # If the printout includes "No Workspace" then there are no workspaces onboarded to the
        #   machine; otherwise the workspaces that have been onboarded are listed in the output
        connectionExists = False
        if 'No Workspace' not in output:
            connectionExists = True

        if connectionExists:
            err_msg = ('This machine is already connected to some other Log '
                       'Analytics workspace, please set stopOnMultipleConnections '
                       'to false in public settings or remove this property, '
                       'so this machine can connect to new workspaces, also it '
                       'means this machine will get billed multiple times for '
                       'each workspace it report to. '
                       '(LINUXOMSAGENTEXTENSION_ERROR_MULTIPLECONNECTIONS)')
            # This exception will get caught by the main method
            raise Exception(err_msg)

    proxyParam = ''
    if proxy is not None:
        proxyParam = '-p {0}'.format(proxy)

    vmResourceIdParam = ''
    if vmResourceId is not None:
        vmResourceIdParam = '-a {0}'.format(vmResourceId)

    optionalParams = '{0} {1}'.format(proxyParam, vmResourceIdParam)
    onboard_cmd = OnboardCommandWithOptionalParamsTemplate.format(OmsAdminPath, workspaceId, workspaceKey,
                                                          optionalParams)

    exit_code = run_command_and_log(hutil, onboard_cmd)

    # If onboard succeeds we continue, otherwise fail fast
    if exit_code == 0:
        enable_cmd = EnableOmsAgentServiceCommandTemplate.format(ServiceControlPath)
        exit_code = run_command_and_log(hutil, enable_cmd)
    else:
        hutil.error(('Onboard failed with exit code {0}; Enable not attempted').format(exit_code))

    return exit_code


def disable(hutil):
    cmd = DisableOmsAgentServiceCommandTemplate.format(ServiceControlPath)
    exit_code = run_command_and_log(hutil, cmd)
    return exit_code


# Dictionary of operations strings to methods
operations = {'Disable' : disable,
              'Uninstall' : uninstall,
              'Install' : install,
              'Enable' : enable,
              # Upgrade is noop since omsagent.py->install() will be called everytime upgrade
              #   is done due to upgradeMode = "UpgradeWithInstall" set in HandlerManifest
              'Update' : dummy_command
}


if __name__ == '__main__' :
    main()
