#!/usr/bin/env python
#
# AzureMonitoringLinuxAgent Extension
#
# Copyright 2021 Microsoft Corporation
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

from __future__ import print_function
import sys
# future imports have no effect on python 3 (verified in official docs)
# importing from source causes import errors on python 3, lets skip import
if sys.version_info[0] < 3:
    from future import standard_library
    standard_library.install_aliases()
    from builtins import str

import os
import os.path
import datetime
import signal
import pwd
import grp
import re
import filecmp
import stat
import traceback
import time
import platform
import subprocess
import json
import base64
import inspect
import urllib.request, urllib.parse, urllib.error
import shutil
import crypt
import xml.dom.minidom
import re
import hashlib
from collections import OrderedDict
from distutils.version import LooseVersion
from hashlib import sha256
from shutil import copyfile

from threading import Thread
import telegraf_utils.telegraf_config_handler as telhandler
import metrics_ext_utils.metrics_constants as metrics_constants
import metrics_ext_utils.metrics_ext_handler as me_handler
import metrics_ext_utils.metrics_common_utils as metrics_utils

try:
    from Utils.WAAgentUtil import waagent
    import Utils.HandlerUtil as HUtil
except Exception as e:
    # These utils have checks around the use of them; this is not an exit case
    print('Importing utils failed with error: {0}'.format(e))

# This code is taken from the omsagent's extension wrapper.
# This same monkey patch fix is relevant for AMA extension as well.
# This monkey patch duplicates the one made in the waagent import above.
# It is necessary because on 2.6, the waagent monkey patch appears to be overridden
# by the python-future subprocess.check_output backport.
if sys.version_info < (2,7):
    def check_output(*popenargs, **kwargs):
        r"""Backport from subprocess module from python 2.7"""
        if 'stdout' in kwargs:
            raise ValueError('stdout argument not allowed, it will be overridden.')
        process = subprocess.Popen(stdout=subprocess.PIPE, *popenargs, **kwargs)
        output, unused_err = process.communicate()
        retcode = process.poll()
        if retcode:
            cmd = kwargs.get("args")
            if cmd is None:
                cmd = popenargs[0]
            raise subprocess.CalledProcessError(retcode, cmd, output=output)
        return output

    # Exception classes used by this module.
    class CalledProcessError(Exception):
        def __init__(self, returncode, cmd, output=None):
            self.returncode = returncode
            self.cmd = cmd
            self.output = output

        def __str__(self):
            return "Command '%s' returned non-zero exit status %d" % (self.cmd, self.returncode)

    subprocess.check_output = check_output
    subprocess.CalledProcessError = CalledProcessError

# Global Variables
PackagesDirectory = 'packages'
# The BundleFileName values will be replaced by actual values in the release pipeline. See apply_version.sh.
BundleFileNameDeb = 'azuremonitoragent.deb'
BundleFileNameRpm = 'azuremonitoragent.rpm'
BundleFileName = ''
TelegrafBinName = 'telegraf'
InitialRetrySleepSeconds = 30
PackageManager = ''
PackageManagerOptions = ''
MdsdCounterJsonPath = '/etc/opt/microsoft/azuremonitoragent/config-cache/metricCounters.json'
FluentCfgPath = '/etc/opt/microsoft/azuremonitoragent/config-cache/fluentbit/td-agent.conf'

SupportedArch = set(['x86_64', 'aarch64'])

# Error codes
GenericErrorCode = 1
UnsupportedOperatingSystem = 51
IndeterminateOperatingSystem = 51
MissingorInvalidParameterErrorCode = 53
DPKGOrRPMLockedErrorCode = 56

# Settings
GenevaConfigKey = "genevaConfiguration"
AzureMonitorConfigKey = "azureMonitorConfiguration"

# Configuration
HUtilObject = None
SettingsSequenceNumber = None
HandlerEnvironment = None
SettingsDict = None


# Change permission of log path - if we fail, that is not an exit case
try:
    ext_log_path = '/var/log/azure/'
    if os.path.exists(ext_log_path):
        os.chmod(ext_log_path, 700)
except:
    pass


def main():
    """
    Main method
    Parse out operation from argument, invoke the operation, and finish.
    """
    init_waagent_logger()
    waagent_log_info('Azure Monitoring Agent for Linux started to handle.')

    # Determine the operation being executed
    operation = None
    try:
        option = sys.argv[1]
        if re.match('^([-/]*)(disable)', option):
            operation = 'Disable'
        elif re.match('^([-/]*)(uninstall)', option):
            operation = 'Uninstall'
        elif re.match('^([-/]*)(install)', option):
            operation = 'Install'
        elif re.match('^([-/]*)(enable)', option):
            operation = 'Enable'
        elif re.match('^([-/]*)(update)', option):
            operation = 'Update'
        elif re.match('^([-/]*)(metrics)', option):
            operation = 'Metrics'
    except Exception as e:
        waagent_log_error(str(e))

    if operation is None:
        log_and_exit('Unknown', GenericErrorCode, 'No valid operation provided')

    # Set up for exit code and any error messages
    exit_code = 0
    message = '{0} succeeded'.format(operation)

    # Avoid entering broken state where manual purge actions are necessary in low disk space scenario
    destructive_operations = ['Disable', 'Uninstall']
    if operation not in destructive_operations:
        exit_code = check_disk_space_availability()
        if exit_code != 0:
            message = '{0} failed due to low disk space'.format(operation)
            log_and_exit(operation, exit_code, message)

    # Invoke operation
    try:
        global HUtilObject
        HUtilObject = parse_context(operation)
        exit_code, output = operations[operation]()

        # Exit code 1 indicates a general problem that doesn't have a more
        # specific error code; it often indicates a missing dependency
        if exit_code == 1 and operation == 'Install':
            message = 'Install failed with exit code 1. Please check that ' \
                      'dependencies are installed. For details, check logs ' \
                      'in /var/log/azure/Microsoft.Azure.Monitor' \
                      '.AzureMonitorLinuxAgent'
        elif exit_code is DPKGOrRPMLockedErrorCode and operation == 'Install':
            message = 'Install failed with exit code {0} because the ' \
                      'package manager on the VM is currently locked: ' \
                      'please wait and try again'.format(DPKGOrRPMLockedErrorCode)
        elif exit_code != 0:
            message = '{0} failed with exit code {1} {2}'.format(operation,
                                                             exit_code, output)

    except AzureMonitorAgentForLinuxException as e:
        exit_code = e.error_code
        message = e.get_error_message(operation)
    except Exception as e:
        exit_code = GenericErrorCode
        message = '{0} failed with error: {1}\n' \
                  'Stacktrace: {2}'.format(operation, e,
                                           traceback.format_exc())

    # Finish up and log messages
    log_and_exit(operation, exit_code, message)

def check_disk_space_availability():
    """
    Check if there is the required space on the machine.
    """
    try:
        if get_free_space_mb("/var") < 500 or get_free_space_mb("/etc") < 500 or get_free_space_mb("/opt") < 500 :
            # 52 is the exit code for missing dependency i.e. disk space
            # https://github.com/Azure/azure-marketplace/wiki/Extension-Build-Notes-Best-Practices#error-codes-and-messages-output-to-stderr
            return 52
        else:
            return 0
    except:
        print('Failed to check disk usage.')
        return 0

def get_free_space_mb(dirname):
    """
    Get the free space in MB in the directory path.
    """
    st = os.statvfs(dirname)
    return (st.f_bavail * st.f_frsize) // (1024 * 1024)

def is_systemd():
    """
    Check if the system is using systemd
    """
    return os.path.isdir("/run/systemd/system")

def get_service_command(service, *operations):
    """
    Get the appropriate service command [sequence] for the provided service name and operation(s)
    """
    if is_systemd():
        return " && ".join(["systemctl {0} {1}".format(operation, service) for operation in operations])
    else:
        hutil_log_info("The VM doesn't have systemctl. Using the init.d service to start {0}.".format(service))
        return '/etc/init.d/{0} {1}'.format(service, operations[0])

def check_kill_process(pstring):
    for line in os.popen("ps ax | grep " + pstring + " | grep -v grep"):
        fields = line.split()
        pid = fields[0]
        os.kill(int(pid), signal.SIGKILL)

def compare_and_copy_bin(src, dest):
    # Check if previous file exist at the location, compare the two binaries,
    # If the files are not same, remove the older file, and copy the new one
    # If they are the same, then we ignore it and don't copy
    if os.path.isfile(src ):
        if os.path.isfile(dest):
            if not filecmp.cmp(src, dest):
                # Removing the file in case it is already being run in a process,
                # in which case we can get an error "text file busy" while copying
                os.remove(dest)
                copyfile(src, dest)

        else:
            # No previous binary exist, simply copy it and make it executable
            copyfile(src, dest)
        
        os.chmod(dest, stat.S_IXGRP | stat.S_IRGRP | stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR | stat.S_IXOTH | stat.S_IROTH)

def copy_amacoreagent_binaries():
    amacoreagent_bin_local_path = os.getcwd() + "/amaCoreAgentBin/amacoreagent"
    amacoreagent_bin = "/opt/microsoft/azuremonitoragent/bin/amacoreagent"

    compare_and_copy_bin(amacoreagent_bin_local_path, amacoreagent_bin)
                  
    agentlauncher_bin_local_path = os.getcwd() + "/agentLauncherBin/agentlauncher"
    agentlauncher_bin = "/opt/microsoft/azuremonitoragent/bin/agentlauncher"

    compare_and_copy_bin(agentlauncher_bin_local_path, agentlauncher_bin)
    
def install():
    """
    Ensure that this VM distro and version are supported.
    Install the Azure Monitor Linux Agent package, using retries.
    Note: install operation times out from WAAgent at 15 minutes, so do not
    wait longer.
    """

    find_package_manager("Install")
    set_os_arch('Install')
    exit_if_vm_not_supported('Install')
    vm_dist, vm_ver = find_vm_distro('Install')

    # Check if SUSE 15 VMs have /sbin/insserv package (required for AMA 1.14.4+)
    if (vm_dist.startswith('suse') or vm_dist.startswith('sles') or vm_dist.startswith('opensuse')) and vm_ver.startswith('15'):
        check_insserv, _ = run_command_and_log("which insserv")
        if check_insserv != 0:
            hutil_log_info("'insserv-compat' package missing from SUSE 15 machine, installing to allow AMA to run.")
            insserv_exit_code, insserv_output = run_command_and_log("zypper --non-interactive install insserv-compat")
            if insserv_exit_code != 0:
                return insserv_exit_code, insserv_output

    package_directory = os.path.join(os.getcwd(), PackagesDirectory)
    bundle_path = os.path.join(package_directory, BundleFileName)
    os.chmod(bundle_path, 100)
    print(PackageManager, " and ", BundleFileName)
    AMAInstallCommand = "{0} {1} -i {2}".format(PackageManager, PackageManagerOptions, bundle_path)
    hutil_log_info('Running command "{0}"'.format(AMAInstallCommand))

    # Retry, since install can fail due to concurrent package operations
    exit_code, output = run_command_with_retries_output(AMAInstallCommand, retries = 15,
                                         retry_check = retry_if_dpkg_or_rpm_locked,
                                         final_check = final_check_if_dpkg_or_rpm_locked)

    # Copy the AMACoreAgent and agentlauncher binaries
    copy_amacoreagent_binaries()

    # Retry install for aarch64 rhel8 VMs as initial install fails to create symlink to /etc/systemd/system/azuremonitoragent.service
    # in /etc/systemd/system/multi-user.target.wants/azuremonitoragent.service
    if vm_dist.replace(' ','').lower().startswith('redhat') and vm_ver == '8.6' and platform.machine() == 'aarch64':
        exit_code, output = run_command_with_retries_output(AMAInstallCommand, retries = 15,
                                         retry_check = retry_if_dpkg_or_rpm_locked,
                                         final_check = final_check_if_dpkg_or_rpm_locked)

    # CL is diabled in arm64 until we have arm64 binaries from pipelineAgent
    if is_systemd() and platform.machine() == 'aarch64':
        exit_code, output = run_command_and_log('systemctl stop azuremonitor-coreagent && systemctl disable azuremonitor-coreagent')
        exit_code, output = run_command_and_log('systemctl stop azuremonitor-agentlauncher && systemctl disable azuremonitor-agentlauncher')
    
    # Set task limits to max of 65K in suse 12
    # Based on Task 9764411: AMA broken after 1.7 in sles 12 - https://dev.azure.com/msazure/One/_workitems/edit/9764411
    if exit_code == 0:
        vm_dist, _ = find_vm_distro('Install')
        if vm_dist.startswith('suse'):
            try:
                suse_exit_code, suse_output = run_command_and_log("mkdir -p /etc/systemd/system/azuremonitoragent.service.d")
                if suse_exit_code != 0:
                    return suse_exit_code, suse_output

                suse_exit_code, suse_output = run_command_and_log("echo '[Service]' > /etc/systemd/system/azuremonitoragent.service.d/override.conf")
                if suse_exit_code != 0:
                    return suse_exit_code, suse_output

                suse_exit_code, suse_output = run_command_and_log("echo 'TasksMax=65535' >> /etc/systemd/system/azuremonitoragent.service.d/override.conf")
                if suse_exit_code != 0:
                    return suse_exit_code, suse_output

                suse_exit_code, suse_output = run_command_and_log("systemctl daemon-reload")
                if suse_exit_code != 0:
                    return suse_exit_code, suse_output
            except:
                log_and_exit("install", MissingorInvalidParameterErrorCode, "Failed to update /etc/systemd/system/azuremonitoragent.service.d for suse 12,15" )

    return exit_code, output

def uninstall():
    """
    Uninstall the Azure Monitor Linux Agent.
    This is a somewhat soft uninstall. It is not a purge.
    Note: uninstall operation times out from WAAgent at 5 minutes
    """

    find_package_manager("Uninstall")
    if PackageManager == "dpkg":
        AMAUninstallCommand = "dpkg -P azuremonitoragent"
    elif PackageManager == "rpm":
        AMAUninstallCommand = "rpm -e azuremonitoragent"
    else:
        log_and_exit("Uninstall", UnsupportedOperatingSystem, "The OS has neither rpm nor dpkg" )
    hutil_log_info('Running command "{0}"'.format(AMAUninstallCommand))

    # Retry, since uninstall can fail due to concurrent package operations
    try:
        exit_code, output = run_command_with_retries_output(AMAUninstallCommand, retries = 4,
                                            retry_check = retry_if_dpkg_or_rpm_locked,
                                            final_check = final_check_if_dpkg_or_rpm_locked)
    except Exception as ex:
        exit_code = GenericErrorCode
        output = 'Uninstall failed with error: {0}\n' \
                'Stacktrace: {1}'.format(ex, traceback.format_exc())
    return exit_code, output

def enable():
    """
    Start the Azure Monitor Linux Agent Service
    This call will return non-zero or throw an exception if
    the settings provided are incomplete or incorrect.
    Note: enable operation times out from WAAgent at 5 minutes
    """

    public_settings, protected_settings = get_settings()

    # start the metrics watcher if its not already running
    if ((protected_settings is None or len(protected_settings) == 0) or
        (public_settings is not None and "proxy" in public_settings and "mode" in public_settings.get("proxy") and public_settings.get("proxy").get("mode") == "application") or
        (public_settings is not None and public_settings.get(AzureMonitorConfigKey) is not None and public_settings.get(AzureMonitorConfigKey).get("ensure") == True)):
        start_metrics_process()

    exit_if_vm_not_supported('Enable')

    ensure = OrderedDict([
        ("azuremonitoragent", False),
        ("azuremonitoragentmgr", False)
    ])

    # Use an Ordered Dictionary to ensure MDSD_OPTIONS (and other dependent variables) are written after their dependencies
    default_configs = OrderedDict([
        ("MDSD_CONFIG_DIR", "/etc/opt/microsoft/azuremonitoragent"),
        ("MDSD_LOG_DIR", "/var/opt/microsoft/azuremonitoragent/log"),
        ("MDSD_ROLE_PREFIX", "/run/azuremonitoragent/default"),
        ("MDSD_SPOOL_DIRECTORY", "/var/opt/microsoft/azuremonitoragent"),
        ("MDSD_OPTIONS", "\"-A -c /etc/opt/microsoft/azuremonitoragent/mdsd.xml -d -r $MDSD_ROLE_PREFIX -S $MDSD_SPOOL_DIRECTORY/eh -L $MDSD_SPOOL_DIRECTORY/events\""),
        ("MDSD_USE_LOCAL_PERSISTENCY", "true"),
        ("MDSD_TCMALLOC_RELEASE_FREQ_SEC", "1"),
        ("MONITORING_USE_GENEVA_CONFIG_SERVICE", "false"),
        ("ENABLE_MCS", "false")
    ])

    ssl_cert_var_name, ssl_cert_var_value = get_ssl_cert_info('Enable')
    default_configs[ssl_cert_var_name] = ssl_cert_var_value

    """
    Decide the mode and configuration. There are two supported configuration schema, mix-and-match between schemas is disallowed:
        Legacy:          allows one of [MCS, GCS single tenant, or GCS multi tenant ("Auto-Config")] modes
        Next-Generation: allows MCS, GCS multi tenant, or both
    """

    # Next-generation schema
    if public_settings is not None and (public_settings.get(GenevaConfigKey) or public_settings.get(AzureMonitorConfigKey)):

        geneva_configuration = public_settings.get(GenevaConfigKey)
        azure_monitor_configuration = public_settings.get(AzureMonitorConfigKey)

        # Check for mix-and match of next-generation and legacy schema content
        if len(public_settings) > 1 and ((geneva_configuration and not azure_monitor_configuration) or (azure_monitor_configuration and not geneva_configuration)):
            log_and_exit("Enable", MissingorInvalidParameterErrorCode, 'Mixing genevaConfiguration or azureMonitorConfiguration with other configuration schemas is not allowed')

        if geneva_configuration and geneva_configuration.get("enable") == True:
            hutil_log_info("Detected Geneva+ mode; azuremonitoragentmgr service will be started to handle Geneva tenants")
            ensure["azuremonitoragentmgr"] = True

        if azure_monitor_configuration and azure_monitor_configuration.get("enable") == True:
            hutil_log_info("Detected Azure Monitor+ mode; azuremonitoragent service will be started to handle Azure Monitor tenant")
            ensure["azuremonitoragent"] = True
            azure_monitor_public_settings = azure_monitor_configuration.get("configuration")
            azure_monitor_protected_settings = protected_settings.get(AzureMonitorConfigKey) if protected_settings is not None else None
            handle_mcs_config(azure_monitor_public_settings, azure_monitor_protected_settings, default_configs)

    # Legacy schema
    elif public_settings is not None and public_settings.get("GCS_AUTO_CONFIG") == True:
        hutil_log_info("Detected Auto-Config mode; azuremonitoragentmgr service will be started to handle Geneva tenants")
        ensure["azuremonitoragentmgr"] = True

    elif (protected_settings is None or len(protected_settings) == 0) or (public_settings is not None and "proxy" in public_settings and "mode" in public_settings.get("proxy") and public_settings.get("proxy").get("mode") == "application"):
        hutil_log_info("Detected Azure Monitor mode; azuremonitoragent service will be started to handle Azure Monitor configuration")
        ensure["azuremonitoragent"] = True
        handle_mcs_config(public_settings, protected_settings, default_configs)

    else:
        hutil_log_info("Detected Geneva mode; azuremonitoragent service will be started to handle Geneva configuration")
        ensure["azuremonitoragent"] = True
        handle_gcs_config(public_settings, protected_settings, default_configs)

    config_file = "/etc/default/azuremonitoragent"
    temp_config_file = "/etc/default/azuremonitoragent_temp"

    try:
        if os.path.isfile(config_file):
            new_config = "\n".join(["export {0}={1}".format(key, value) for key, value in default_configs.items()]) + "\n"

            with open(temp_config_file, "w") as f:
                f.write(new_config)

            if not os.path.isfile(temp_config_file):
                log_and_exit("Enable", GenericErrorCode, "Error while updating environment variables in {0}".format(config_file))

            os.remove(config_file)
            os.rename(temp_config_file, config_file)

            uid = pwd.getpwnam("syslog").pw_uid
            gid = grp.getgrnam("syslog").gr_gid
            os.chown(config_file, uid, gid)
            os.system('chmod {1} {0}'.format(config_file, 400))
        else:
            log_and_exit("Enable", GenericErrorCode, "Could not find the file {0}".format(config_file))
    except Exception as e:
        log_and_exit("Enable", GenericErrorCode, "Failed to add environment variables to {0}: {1}".format(config_file, e))

    if "ENABLE_MCS" in default_configs and default_configs["ENABLE_MCS"] == "true":
        start_amacoreagent()
        restart_launcher()

    hutil_log_info('Handler initiating onboarding.')

    if HUtilObject and HUtilObject.is_seq_smaller():
        # Either upgrade has just happened (in which case we need to start), or enable was called with no change to extension config
        hutil_log_info("Current sequence number, " + HUtilObject._context._seq_no + ", is not greater than the LKG sequence number. Starting service(s) only if it is not yet running.")
        operations = ["start", "enable"]
    else:
        # Either this is a clean install (in which case restart is effectively start), or extension config has changed
        hutil_log_info("Current sequence number, " + HUtilObject._context._seq_no + ", is greater than the LKG sequence number. Restarting service(s) to pick up the new config.")
        operations = ["restart", "enable"]

    output = ""

    # Ensure non-required services are not running; do not block if this step fails
    for service in [s for s in ensure.keys() if not ensure[s]]:
        exit_code, disable_output = run_command_and_log(get_service_command(service, "stop", "disable"))
        output += disable_output

    for service in [s for s in ensure.keys() if ensure[s]]:
        exit_code, enable_output = run_command_and_log(get_service_command(service, *operations))
        output += enable_output

        if exit_code != 0:
            status_command = get_service_command(service, "status")
            status_exit_code, status_output = run_command_and_log(status_command)

            if status_exit_code != 0:
                output += "Output of '{0}':\n{1}".format(status_command, status_output)
                return exit_code, output

    # Service(s) were successfully configured and started; increment sequence number
    HUtilObject.save_seq()

    return exit_code, output

def handle_gcs_config(public_settings, protected_settings, default_configs):
    """
    Populate the defaults for legacy-path GCS mode
    """
    # look for LA protected settings
    for var in list(protected_settings.keys()):
        if "_key" in var or "_id" in var:
            default_configs[var] = protected_settings.get(var)

    # check if required GCS params are available
    MONITORING_GCS_CERT_CERTFILE = None
    if "certificate" in protected_settings:
        MONITORING_GCS_CERT_CERTFILE = base64.standard_b64decode(protected_settings.get("certificate"))

    if "certificatePath" in protected_settings:
        try:
            with open(protected_settings.get("certificatePath"), 'r') as f:
                MONITORING_GCS_CERT_CERTFILE = f.read()
        except Exception as ex:
            log_and_exit('Enable', MissingorInvalidParameterErrorCode, 'Failed to read certificate {0}: {1}'.format(protected_settings.get("certificatePath"), ex))

    MONITORING_GCS_CERT_KEYFILE = None
    if "certificateKey" in protected_settings:
        MONITORING_GCS_CERT_KEYFILE = base64.standard_b64decode(protected_settings.get("certificateKey"))

    if "certificateKeyPath" in protected_settings:
        try:
            with open(protected_settings.get("certificateKeyPath"), 'r') as f:
                MONITORING_GCS_CERT_KEYFILE = f.read()
        except Exception as ex:
            log_and_exit('Enable', MissingorInvalidParameterErrorCode, 'Failed to read certificate key {0}: {1}'.format(protected_settings.get("certificateKeyPath"), ex))

    MONITORING_GCS_ENVIRONMENT = ""
    if "monitoringGCSEnvironment" in protected_settings:
        MONITORING_GCS_ENVIRONMENT = protected_settings.get("monitoringGCSEnvironment")

    MONITORING_GCS_NAMESPACE = ""
    if "namespace" in protected_settings:
        MONITORING_GCS_NAMESPACE = protected_settings.get("namespace")

    MONITORING_GCS_ACCOUNT = ""
    if "monitoringGCSAccount" in protected_settings:
        MONITORING_GCS_ACCOUNT = protected_settings.get("monitoringGCSAccount")

    MONITORING_GCS_REGION = ""
    if "monitoringGCSRegion" in protected_settings:
        MONITORING_GCS_REGION = protected_settings.get("monitoringGCSRegion")

    MONITORING_CONFIG_VERSION = ""
    if "configVersion" in protected_settings:
        MONITORING_CONFIG_VERSION = protected_settings.get("configVersion")

    MONITORING_GCS_AUTH_ID_TYPE = ""
    if "monitoringGCSAuthIdType" in protected_settings:
        MONITORING_GCS_AUTH_ID_TYPE = protected_settings.get("monitoringGCSAuthIdType")

    MONITORING_GCS_AUTH_ID = ""
    if "monitoringGCSAuthId" in protected_settings:
        MONITORING_GCS_AUTH_ID = protected_settings.get("monitoringGCSAuthId")

    MONITORING_TENANT = ""
    if "monitoringTenant" in protected_settings:
        MONITORING_TENANT = protected_settings.get("monitoringTenant")

    MONITORING_ROLE = ""
    if "monitoringRole" in protected_settings:
        MONITORING_ROLE = protected_settings.get("monitoringRole")

    MONITORING_ROLE_INSTANCE = ""
    if "monitoringRoleInstance" in protected_settings:
        MONITORING_ROLE_INSTANCE = protected_settings.get("monitoringRoleInstance")


    if ((MONITORING_GCS_CERT_CERTFILE is None or MONITORING_GCS_CERT_KEYFILE is None) and (MONITORING_GCS_AUTH_ID_TYPE == "")) or MONITORING_GCS_ENVIRONMENT == "" or MONITORING_GCS_NAMESPACE == "" or MONITORING_GCS_ACCOUNT == "" or MONITORING_GCS_REGION == "" or MONITORING_CONFIG_VERSION == "":
        log_and_exit("Enable", MissingorInvalidParameterErrorCode, 'Not all required GCS parameters are provided')
    else:
        # set the values for GCS
        default_configs["MONITORING_USE_GENEVA_CONFIG_SERVICE"] = "true"
        default_configs["MONITORING_GCS_ENVIRONMENT"] = MONITORING_GCS_ENVIRONMENT
        default_configs["MONITORING_GCS_NAMESPACE"] = MONITORING_GCS_NAMESPACE
        default_configs["MONITORING_GCS_ACCOUNT"] = MONITORING_GCS_ACCOUNT
        default_configs["MONITORING_GCS_REGION"] = MONITORING_GCS_REGION
        default_configs["MONITORING_CONFIG_VERSION"] = MONITORING_CONFIG_VERSION

        # write the certificate and key to disk
        uid = pwd.getpwnam("syslog").pw_uid
        gid = grp.getgrnam("syslog").gr_gid

        if MONITORING_GCS_AUTH_ID_TYPE != "":
            default_configs["MONITORING_GCS_AUTH_ID_TYPE"] = MONITORING_GCS_AUTH_ID_TYPE

        if MONITORING_GCS_AUTH_ID != "":
            default_configs["MONITORING_GCS_AUTH_ID"] = MONITORING_GCS_AUTH_ID

        if MONITORING_GCS_CERT_CERTFILE is not None:
            default_configs["MONITORING_GCS_CERT_CERTFILE"] = "/etc/opt/microsoft/azuremonitoragent/gcscert.pem"
            with open("/etc/opt/microsoft/azuremonitoragent/gcscert.pem", "wb") as f:
                f.write(MONITORING_GCS_CERT_CERTFILE)
            os.chown("/etc/opt/microsoft/azuremonitoragent/gcscert.pem", uid, gid)
            os.system('chmod {1} {0}'.format("/etc/opt/microsoft/azuremonitoragent/gcscert.pem", 400))

        if MONITORING_GCS_CERT_KEYFILE is not None:
            default_configs["MONITORING_GCS_CERT_KEYFILE"] = "/etc/opt/microsoft/azuremonitoragent/gcskey.pem"
            with open("/etc/opt/microsoft/azuremonitoragent/gcskey.pem", "wb") as f:
                f.write(MONITORING_GCS_CERT_KEYFILE)
            os.chown("/etc/opt/microsoft/azuremonitoragent/gcskey.pem", uid, gid)
            os.system('chmod {1} {0}'.format("/etc/opt/microsoft/azuremonitoragent/gcskey.pem", 400))

        if MONITORING_TENANT != "":
            default_configs["MONITORING_TENANT"] = MONITORING_TENANT

        if MONITORING_ROLE != "":
            default_configs["MONITORING_ROLE"] = MONITORING_ROLE

        if MONITORING_TENANT != "":
            default_configs["MONITORING_ROLE_INSTANCE"] = MONITORING_ROLE_INSTANCE

def handle_mcs_config(public_settings, protected_settings, default_configs):
    """
    Populate the defaults for MCS mode
    """
    default_configs["ENABLE_MCS"] = "true"
    default_configs["PA_GIG_BRIDGE_MODE"] = "true"
    # April 2022: PA_FLUENT_SOCKET_PORT setting is being deprecated in place of PA_DATA_PORT. Remove when AMA 1.17 and earlier no longer need servicing.
    default_configs["PA_FLUENT_SOCKET_PORT"] = "13000"
    # this port will be dynamic in future
    default_configs["PA_DATA_PORT"] = "13000"

    # fetch proxy settings
    if public_settings is not None and "proxy" in public_settings and "mode" in public_settings.get("proxy") and public_settings.get("proxy").get("mode") == "application":
        default_configs["MDSD_PROXY_MODE"] = "application"

        if "address" in public_settings.get("proxy"):
            default_configs["MDSD_PROXY_ADDRESS"] = public_settings.get("proxy").get("address")
        else:
            log_and_exit("Enable", MissingorInvalidParameterErrorCode, 'Parameter "address" is required in proxy public setting')

        if "auth" in public_settings.get("proxy") and public_settings.get("proxy").get("auth") == "true":
            if protected_settings is not None and "proxy" in protected_settings and "username" in protected_settings.get("proxy") and "password" in protected_settings.get("proxy"):
                default_configs["MDSD_PROXY_USERNAME"] = protected_settings.get("proxy").get("username")
                default_configs["MDSD_PROXY_PASSWORD"] = protected_settings.get("proxy").get("password")
                set_proxy(default_configs["MDSD_PROXY_ADDRESS"], default_configs["MDSD_PROXY_USERNAME"], default_configs["MDSD_PROXY_PASSWORD"])
            else:
                log_and_exit("Enable", MissingorInvalidParameterErrorCode, 'Parameter "username" and "password" not in proxy protected setting')
         else:
            set_proxy(default_configs["MDSD_PROXY_ADDRESS"], "", "")

    # add managed identity settings if they were provided
    identifier_name, identifier_value, error_msg = get_managed_identity()

    if error_msg:
        log_and_exit("Enable", MissingorInvalidParameterErrorCode, 'Failed to determine managed identity settings. {0}.'.format(error_msg))

    if identifier_name and identifier_value:
        default_configs["MANAGED_IDENTITY"] = "{0}#{1}".format(identifier_name, identifier_value)

def disable():
    """
    Disable Azure Monitor Linux Agent process on the VM.
    Note: disable operation times out from WAAgent at 15 minutes
    """

    #stop the metrics process
    stop_metrics_process()

    # stop amacoreagent and agent launcher
    hutil_log_info('Handler initiating Core Agent and agent launcher')
    if is_systemd() and platform.machine() != 'aarch64':
        exit_code, output = run_command_and_log('systemctl stop azuremonitor-coreagent && systemctl disable azuremonitor-coreagent')
        exit_code, output = run_command_and_log('systemctl stop azuremonitor-agentlauncher && systemctl disable azuremonitor-agentlauncher')
        # in case AL is not cleaning up properly
        check_kill_process('/opt/microsoft/azuremonitoragent/bin/fluent-bit')

    # Stop and disable systemd services so they are not started after system reboot.
    for service in ["azuremonitoragent", "azuremonitoragentmgr"]:
        exit_code, output = run_command_and_log(get_service_command(service, "stop", "disable"))

        if exit_code != 0:
            status_command = get_service_command(service, "status")
            status_exit_code, status_output = run_command_and_log(status_command)

            if status_exit_code != 0:
                output += "Output of '{0}':\n{1}".format(status_command, status_output)

    return exit_code, output

def update():
    """
    Update the current installation of AzureMonitorLinuxAgent
    No logic to install the agent as agent -> install() will be called
    with update because upgradeMode = "UpgradeWithInstall" set in HandlerManifest
    """

    return 0, ""

def start_amacoreagent():
    if platform.machine() == 'aarch64':
        return
    # start Core Agent
    hutil_log_info('Handler initiating Core Agent')
    if is_systemd():
        exit_code, output = run_command_and_log('systemctl start azuremonitor-coreagent && systemctl enable azuremonitor-coreagent')

def restart_launcher():
    if platform.machine() == 'aarch64':
        return
    # start agent launcher
    hutil_log_info('Handler initiating agent launcher')
    if is_systemd():
        exit_code, output = run_command_and_log('systemctl stop azuremonitor-agentlauncher && systemctl disable azuremonitor-agentlauncher')
        # in case AL is not cleaning up properly
        check_kill_process('/opt/microsoft/azuremonitoragent/bin/fluent-bit')
        exit_code, output = run_command_and_log('systemctl restart azuremonitor-agentlauncher && systemctl enable azuremonitor-agentlauncher')

def set_proxy(address, username, password):
    """
    # Set proxy http_proxy env var in dependent services
    """
    
    try:
        http_proxy = address
        address = address.replace("http://","")

        if username:
            http_proxy = "http://" + username + ":" + password + "@" + address

        # Update Coreagent
        run_command_and_log("mkdir -p /etc/systemd/system/azuremonitor-coreagent.service.d")
        run_command_and_log("echo '[Service]' > /etc/systemd/system/azuremonitor-coreagent.service.d/proxy.conf")
        run_command_and_log("echo 'Environment=\"http_proxy={0}\"' >> /etc/systemd/system/azuremonitor-coreagent.service.d/proxy.conf".format(http_proxy))
        os.system('chmod {1} {0}'.format("/etc/systemd/system/azuremonitor-coreagent.service.d/proxy.conf", 400))

        # Update ME
        run_command_and_log("mkdir -p /etc/systemd/system/metrics-extension.service.d")
        run_command_and_log("echo '[Service]' > /etc/systemd/system/metrics-extension.service.d/proxy.conf")
        run_command_and_log("echo 'Environment=\"http_proxy={0}\"' >> /etc/systemd/system/metrics-extension.service.d/proxy.conf".format(http_proxy))
        os.system('chmod {1} {0}'.format("/etc/systemd/system/metrics-extension.service.d/proxy.conf", 400))

        run_command_and_log("systemctl daemon-reload")
        
    except:
        log_and_exit("enable", MissingorInvalidParameterErrorCode, "Failed to update /etc/systemd/system/azuremonitor-coreagent.service.d and mkdir -p /etc/systemd/system/metrics-extension.service.d" )
    
def get_managed_identity():
    """
    # Determine Managed Identity (MI) settings
    # Nomenclature: Managed System Identity (MSI), System-Assigned Identity (SAI), User-Assigned Identity (UAI)
    # Unspecified MI scenario: MSI returns SAI token if exists, otherwise returns UAI token if exactly one UAI exists, otherwise failure
    # Specified MI scenario: MSI returns token for specified MI
    # Returns identifier_name, identifier_value, and error message (if any)
    """
    identifier_name = identifier_value = ""
    public_settings, _ = get_settings()

    if public_settings is not None and public_settings.get(AzureMonitorConfigKey):
        azure_monitor_configuration = public_settings.get(AzureMonitorConfigKey)

        if azure_monitor_configuration and azure_monitor_configuration.get("enable") == True:
            public_settings = azure_monitor_configuration.get("configuration")

    if public_settings is not None and "authentication" in public_settings and "managedIdentity" in public_settings.get("authentication"):
        managedIdentity = public_settings.get("authentication").get("managedIdentity")

        if "identifier-name" not in managedIdentity or "identifier-value" not in managedIdentity:
            return identifier_name, identifier_value, 'Parameters "identifier-name" and "identifier-value" are both required in authentication.managedIdentity public setting'

        identifier_name = managedIdentity.get("identifier-name")
        identifier_value = managedIdentity.get("identifier-value")

        if identifier_name not in ["client_id", "mi_res_id"]:
            return identifier_name, identifier_value, 'Invalid identifier-name provided; must be "client_id" or "mi_res_id"'

        if not identifier_value:
            return identifier_name, identifier_value, 'Invalid identifier-value provided; cannot be empty'

        if identifier_name in ["object_id", "client_id"]:
            guid_re = re.compile(r'[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}')
            if not guid_re.search(identifier_value):
                return identifier_name, identifier_value, 'Invalid identifier-value provided for {0}; must be a GUID'.format(identifier_name)

    return identifier_name, identifier_value, ""

def stop_metrics_process():

    if telhandler.is_running(is_lad=False):
        #Stop the telegraf and ME services
        tel_out, tel_msg = telhandler.stop_telegraf_service(is_lad=False)
        if tel_out:
            hutil_log_info(tel_msg)
        else:
            hutil_log_error(tel_msg)

        #Delete the telegraf and ME services
        tel_rm_out, tel_rm_msg = telhandler.remove_telegraf_service(is_lad=False)
        if tel_rm_out:
            hutil_log_info(tel_rm_msg)
        else:
            hutil_log_error(tel_rm_msg)

    if me_handler.is_running(is_lad=False):
        me_out, me_msg = me_handler.stop_metrics_service(is_lad=False)
        if me_out:
            hutil_log_info(me_msg)
        else:
            hutil_log_error(me_msg)

        me_rm_out, me_rm_msg = me_handler.remove_metrics_service(is_lad=False)
        if me_rm_out:
            hutil_log_info(me_rm_msg)
        else:
            hutil_log_error(me_rm_msg)

    pids_filepath = os.path.join(os.getcwd(),'amametrics.pid')

    # kill existing metrics watcher
    if os.path.exists(pids_filepath):
        with open(pids_filepath, "r") as f:
            for pid in f.readlines():
                # Verify the pid actually belongs to AMA metrics watcher.
                cmd_file = os.path.join("/proc", str(pid.strip("\n")), "cmdline")
                if os.path.exists(cmd_file):
                    with open(cmd_file, "r") as pidf:
                        cmdline = pidf.readlines()
                        if len(cmdline) > 0 and cmdline[0].find("agent.py") >= 0 and cmdline[0].find("-metrics") >= 0:
                            kill_cmd = "kill " + pid
                            run_command_and_log(kill_cmd)

        run_command_and_log("rm "+pids_filepath)

def is_metrics_process_running():
    pids_filepath = os.path.join(os.getcwd(),'amametrics.pid')
    if os.path.exists(pids_filepath):
        with open(pids_filepath, "r") as f:
            for pid in f.readlines():
                # Verify the pid actually belongs to AMA metrics watcher.
                cmd_file = os.path.join("/proc", str(pid.strip("\n")), "cmdline")
                if os.path.exists(cmd_file):
                    with open(cmd_file, "r") as pidf:
                        cmdline = pidf.readlines()
                        if len(cmdline) > 0 and cmdline[0].find("agent.py") >= 0 and cmdline[0].find("-metrics") >= 0:
                            return True

    return False

def start_metrics_process():
    """
    Start metrics process that performs periodic monitoring activities
    :return: None
    """

    # if metrics process is already running, it should manage lifecycle of telegraf, ME, 
    # process to refresh ME MSI token and look for new config changes if counters change, etc, so this is no-op
    if not is_metrics_process_running():
        stop_metrics_process()

        # Start metrics watcher
        ama_path = os.path.join(os.getcwd(), 'agent.py')
        args = [sys.executable, ama_path, '-metrics']
        log = open(os.path.join(os.getcwd(), 'daemon.log'), 'w')
        hutil_log_info('start watcher process '+str(args))
        subprocess.Popen(args, stdout=log, stderr=log)

def metrics_watcher(hutil_error, hutil_log):
    """
    Watcher thread to monitor metric configuration changes and to take action on them
    """

    # Check every 30 seconds
    sleepTime =  30

    # Retrieve managed identity info that may be needed for token retrieval
    identifier_name, identifier_value, error_msg = get_managed_identity()
    if error_msg:
        hutil_error('Failed to determine managed identity settings; MSI token retreival will rely on default identity, if any. {0}.'.format(error_msg))

    # Sleep before starting the monitoring
    time.sleep(sleepTime)
    last_crc = None
    last_crc_fluent = None
    me_msi_token_expiry_epoch = None

    while True:
        try:
            if os.path.isfile(FluentCfgPath):
                f = open(FluentCfgPath, "r")
                data = f.read()

                if (data != ''):
                    crc_fluent = hashlib.sha256(data.encode('utf-8')).hexdigest()

                    if (crc_fluent != last_crc_fluent):
                        restart_launcher()
                        last_crc_fluent = crc_fluent
           
            if os.path.isfile(MdsdCounterJsonPath):
                f = open(MdsdCounterJsonPath, "r")
                data = f.read()

                if (data != ''):
                    json_data = json.loads(data)

                    if len(json_data) == 0:
                        last_crc = hashlib.sha256(data.encode('utf-8')).hexdigest()
                        if telhandler.is_running(is_lad=False):
                            # Stop the telegraf and ME services
                            tel_out, tel_msg = telhandler.stop_telegraf_service(is_lad=False)
                            if tel_out:
                                hutil_log(tel_msg)
                            else:
                                hutil_error(tel_msg)

                            # Delete the telegraf and ME services
                            tel_rm_out, tel_rm_msg = telhandler.remove_telegraf_service(is_lad=False)
                            if tel_rm_out:
                                hutil_log(tel_rm_msg)
                            else:
                                hutil_error(tel_rm_msg)

                        if me_handler.is_running(is_lad=False):
                            me_out, me_msg = me_handler.stop_metrics_service(is_lad=False)
                            if me_out:
                                hutil_log(me_msg)
                            else:
                                hutil_error(me_msg)

                            me_rm_out, me_rm_msg = me_handler.remove_metrics_service(is_lad=False)
                            if me_rm_out:
                                hutil_log(me_rm_msg)
                            else:
                                hutil_error(me_rm_msg)
                    else:
                        crc = hashlib.sha256(data.encode('utf-8')).hexdigest()

                        if(crc != last_crc):
                            # Resetting the me_msi_token_expiry_epoch variable if we set up ME again.
                            me_msi_token_expiry_epoch = None
                            hutil_log("Start processing metric configuration")
                            hutil_log(data)

                            telegraf_config, telegraf_namespaces = telhandler.handle_config(
                                json_data,
                                "udp://127.0.0.1:" + metrics_constants.ama_metrics_extension_udp_port,
                                "unix:///run/azuremonitoragent/default_influx.socket",
                                is_lad=False)

                            me_handler.setup_me(is_lad=False, HUtilObj=HUtilObject)

                            start_telegraf_res, log_messages = telhandler.start_telegraf(is_lad=False)
                            if start_telegraf_res:
                                hutil_log("Successfully started metrics-sourcer.")
                            else:
                                hutil_error(log_messages)


                            start_metrics_out, log_messages = me_handler.start_metrics(is_lad=False)
                            if start_metrics_out:
                                hutil_log("Successfully started metrics-extension.")
                            else:
                                hutil_error(log_messages)

                            last_crc = crc

                        generate_token = False
                        me_token_path = os.path.join(os.getcwd(), "/config/metrics_configs/AuthToken-MSI.json")

                        if me_msi_token_expiry_epoch is None or me_msi_token_expiry_epoch == "":
                            if os.path.isfile(me_token_path):
                                with open(me_token_path, "r") as f:
                                    authtoken_content = f.read()
                                    if authtoken_content and "expires_on" in authtoken_content:
                                        me_msi_token_expiry_epoch = authtoken_content["expires_on"]
                                    else:
                                        generate_token = True
                            else:
                                generate_token = True

                        if me_msi_token_expiry_epoch:
                            currentTime = datetime.datetime.now()
                            token_expiry_time = datetime.datetime.fromtimestamp(int(me_msi_token_expiry_epoch))
                            if token_expiry_time - currentTime < datetime.timedelta(minutes=30):
                                # The MSI Token will expire within 30 minutes. We need to refresh the token
                                generate_token = True

                        if generate_token:
                            generate_token = False
                            msi_token_generated, me_msi_token_expiry_epoch, log_messages = me_handler.generate_MSI_token(identifier_name, identifier_value)
                            if msi_token_generated:
                                hutil_log("Successfully refreshed metrics-extension MSI Auth token.")
                            else:
                                hutil_error(log_messages)

                        telegraf_restart_retries = 0
                        me_restart_retries = 0
                        max_restart_retries = 10

                        # Check if telegraf is running, if not, then restart
                        if not telhandler.is_running(is_lad=False):
                            if telegraf_restart_retries < max_restart_retries:
                                telegraf_restart_retries += 1
                                hutil_log("Telegraf binary process is not running. Restarting telegraf now. Retry count - {0}".format(telegraf_restart_retries))
                                tel_out, tel_msg = telhandler.stop_telegraf_service(is_lad=False)
                                if tel_out:
                                    hutil_log(tel_msg)
                                else:
                                    hutil_error(tel_msg)
                                start_telegraf_res, log_messages = telhandler.start_telegraf(is_lad=False)
                                if start_telegraf_res:
                                    hutil_log("Successfully started metrics-sourcer.")
                                else:
                                    hutil_error(log_messages)
                            else:
                                hutil_error("Telegraf binary process is not running. Failed to restart after {0} retries. Please check telegraf.log".format(max_restart_retries))
                        else:
                            telegraf_restart_retries = 0

                        # Check if ME is running, if not, then restart
                        if not me_handler.is_running(is_lad=False):
                            if me_restart_retries < max_restart_retries:
                                me_restart_retries += 1
                                hutil_log("MetricsExtension binary process is not running. Restarting MetricsExtension now. Retry count - {0}".format(me_restart_retries))
                                me_out, me_msg = me_handler.stop_metrics_service(is_lad=False)
                                if me_out:
                                    hutil_log(me_msg)
                                else:
                                    hutil_error(me_msg)
                                start_metrics_out, log_messages = me_handler.start_metrics(is_lad=False)

                                if start_metrics_out:
                                    hutil_log("Successfully started metrics-extension.")
                                else:
                                    hutil_error(log_messages)
                            else:
                                hutil_error("MetricsExtension binary process is not running. Failed to restart after {0} retries. Please check /var/log/syslog for ME logs".format(max_restart_retries))
                        else:
                            me_restart_retries = 0

        except IOError as e:
            hutil_error('I/O error in setting up or monitoring metrics. Exception={0}'.format(e))

        except Exception as e:
            hutil_error('Error in setting up or monitoring metrics. Exception={0}'.format(e))

        finally:
            time.sleep(sleepTime)

def metrics():
    """
    Take care of setting up telegraf and ME for metrics if configuration is present
    """
    pids_filepath = os.path.join(os.getcwd(), 'amametrics.pid')
    py_pid = os.getpid()
    with open(pids_filepath, 'w') as f:
        f.write(str(py_pid) + '\n')

    watcher_thread = Thread(target = metrics_watcher, args = [hutil_log_error, hutil_log_info])
    watcher_thread.start()
    watcher_thread.join()

    return 0, ""


# Dictionary of operations strings to methods
operations = {'Disable' : disable,
              'Uninstall' : uninstall,
              'Install' : install,
              'Enable' : enable,
              'Update' : update,
              'Metrics' : metrics
}


def parse_context(operation):
    """
    Initialize a HandlerUtil object for this operation.
    If the required modules have not been imported, this will return None.
    """
    hutil = None
    if ('Utils.WAAgentUtil' in sys.modules
            and 'Utils.HandlerUtil' in sys.modules):
        try:

            logFileName = 'extension.log'
            hutil = HUtil.HandlerUtility(waagent.Log, waagent.Error, logFileName=logFileName)
            hutil.do_parse_context(operation)
        # parse_context may throw KeyError if necessary JSON key is not
        # present in settings
        except KeyError as e:
            waagent_log_error('Unable to parse context with error: ' \
                              '{0}'.format(e))
            raise ParameterMissingException
    return hutil

def set_os_arch(operation):
    """
    Checks if the current system architecture is present in the SupportedArch set and replaces 
    the package names accordingly
    """
    global BundleFileName, SupportedArch
    current_arch = platform.machine()

    if current_arch in SupportedArch:

        # Replace the AMA package name according to architecture
        BundleFileName = BundleFileName.replace('x86_64', current_arch)

        # Rename the Arch appropriate metrics extension binary to MetricsExtension
        MetricsExtensionDir = os.path.join(os.getcwd(), 'MetricsExtensionBin')
        SupportedMEPath = os.path.join(MetricsExtensionDir, 'MetricsExtension_'+current_arch)

        vm_dist, vm_ver = find_vm_distro(operation)
        if current_arch == 'aarch64' and vm_dist.startswith('centos') and vm_ver.startswith('7'): 
            SupportedMEPath += '_centos7' 
 
        if os.path.exists(SupportedMEPath):
            os.rename(SupportedMEPath, os.path.join(MetricsExtensionDir, 'MetricsExtension'))

        # Cleanup unused ME binaries
        for f in os.listdir(MetricsExtensionDir):
            if f != 'MetricsExtension':
                os.remove(os.path.join(MetricsExtensionDir, f))
    

def find_package_manager(operation):
    """
    Checks if the dist is debian based or centos based and assigns the package manager accordingly
    """
    global PackageManager, PackageManagerOptions, BundleFileName
    dist, _ = find_vm_distro(operation)

    dpkg_set = set(["debian", "ubuntu"])
    rpm_set = set(["oracle", "redhat", "centos", "red hat", "suse", "sles", "opensuse", "cbl-mariner", "mariner", "rhel", "rocky", "alma"])
    for dpkg_dist in dpkg_set:
        if dist.startswith(dpkg_dist):
            PackageManager = "dpkg"
            # OK to replace the /etc/default/azuremonitoragent, since the placeholders gets replaced again.
            # Otherwise, the package manager prompts for action (Y/I/N/O/D/Z) [default=N]
            PackageManagerOptions = "--force-overwrite --force-confnew"
            BundleFileName = BundleFileNameDeb
            break

    for rpm_dist in rpm_set:
        if dist.startswith(rpm_dist):
            PackageManager = "rpm"
            # Same as above.
            PackageManagerOptions = "--force"
            BundleFileName = BundleFileNameRpm
            break

    if PackageManager == "":
        log_and_exit(operation, UnsupportedOperatingSystem, "The OS has neither rpm nor dpkg" )


def find_vm_distro(operation):
    """
    Finds the Linux Distribution this vm is running on.
    """
    vm_dist = vm_id = vm_ver =  None
    parse_manually = False
    try:
        vm_dist, vm_ver, vm_id = platform.linux_distribution()
    except AttributeError:
        try:
            vm_dist, vm_ver, vm_id = platform.dist()
        except AttributeError:
            hutil_log_info("Falling back to /etc/os-release distribution parsing")
    # Some python versions *IF BUILT LOCALLY* (ex 3.5) give string responses (ex. 'bullseye/sid') to platform.dist() function
    # This causes exception in the method below. Thus adding a check to switch to manual parsing in this case
    try:
        temp_vm_ver = int(vm_ver.split('.')[0])
    except:
        parse_manually = True

    if (not vm_dist and not vm_ver) or parse_manually: # SLES 15 and others
        try:
            with open('/etc/os-release', 'r') as fp:
                for line in fp:
                    if line.startswith('ID='):
                        vm_dist = line.split('=')[1]
                        vm_dist = vm_dist.split('-')[0]
                        vm_dist = vm_dist.replace('\"', '').replace('\n', '')
                    elif line.startswith('VERSION_ID='):
                        vm_ver = line.split('=')[1]
                        vm_ver = vm_ver.replace('\"', '').replace('\n', '')
        except:
            log_and_exit(operation, IndeterminateOperatingSystem, 'Indeterminate operating system')
    return vm_dist.lower(), vm_ver.lower()


def is_vm_supported_for_extension(operation):
    """
    Checks if the VM this extension is running on is supported by AzureMonitorAgent
    Returns for platform.linux_distribution() vary widely in format, such as
    '7.3.1611' returned for a VM with CentOS 7, so the first provided
    digits must match
    The supported distros of the AzureMonitorLinuxAgent are allowed to utilize
    this VM extension. All other distros will get error code 51
    """
    supported_dists_x86_64 = {'redhat' : ['7', '8'], # Rhel
                       'rhel' : ['7', '8'], # Rhel
                       'centos' : ['7', '8'], # CentOS
                       'red hat' : ['7', '8'], # Oracle, RHEL
                       'oracle' : ['7', '8'], # Oracle
                       'debian' : ['9', '10', '11'], # Debian
                       'ubuntu' : ['16.04', '18.04', '20.04', '22.04'], # Ubuntu
                       'suse' : ['12'], 'sles' : ['15'], # SLES
                       'cbl-mariner' : ['1'], # Mariner 1.0
                       'mariner' : ['2'], # Mariner 2.0
                       'rocky' : ['8'], # Rocky
                       'alma' : ['8'], # Alma
                       'opensuse' : ['15'] # openSUSE
    }

    supported_dists_aarch64 = {'red hat' : ['8'], # Rhel
                       'ubuntu' : ['18.04', '20.04'], # Ubuntu
                       'alma' : ['8'], # Alma
                       'centos' : ['7'], # CentOS
                       'mariner' : ['2'], # Mariner 2.0
                       'sles' : ['15'], # SLES
                       'debian' : ['11'] # Debian
    }

    if platform.machine() == 'aarch64':
        supported_dists = supported_dists_aarch64
    else:
        supported_dists = supported_dists_x86_64

    vm_supported = False
    vm_dist, vm_ver = find_vm_distro(operation)
    # Find this VM distribution in the supported list
    for supported_dist in list(supported_dists.keys()):
        if not vm_dist.startswith(supported_dist):
            continue

        # Check if this VM distribution version is supported
        vm_ver_split = vm_ver.split('.')
        for supported_ver in supported_dists[supported_dist]:
            supported_ver_split = supported_ver.split('.')

            # If vm_ver is at least as precise (at least as many digits) as
            # supported_ver and matches all the supported_ver digits, then
            # this VM is guaranteed to be supported
            vm_ver_match = True
            for idx, supported_ver_num in enumerate(supported_ver_split):
                try:
                    supported_ver_num = int(supported_ver_num)
                    vm_ver_num = int(vm_ver_split[idx])
                except IndexError:
                    vm_ver_match = False
                    break
                if vm_ver_num != supported_ver_num:
                    vm_ver_match = False
                    break
            if vm_ver_match:
                vm_supported = True
                break

        if vm_supported:
            break

    return vm_supported, vm_dist, vm_ver


def exit_if_vm_not_supported(operation):
    """
    Check if this VM distro and version are supported by the AzureMonitorLinuxAgent.
    If VM is supported, find the package manager present in this distro
    If this VM is not supported, log the proper error code and exit.
    """
    vm_supported, vm_dist, vm_ver = is_vm_supported_for_extension(operation)
    if not vm_supported:
        log_and_exit(operation, UnsupportedOperatingSystem, 'Unsupported operating system: ' \
                                    '{0} {1}'.format(vm_dist, vm_ver))
    return 0


def get_ssl_cert_info(operation):
    """
    Get the appropriate SSL_CERT_DIR / SSL_CERT_FILE based on the Linux distro
    """
    name = value = None

    distro, version = find_vm_distro(operation)

    for name in ['ubuntu', 'debian']:
        if distro.startswith(name):
            return 'SSL_CERT_DIR', '/etc/ssl/certs'

    for name in ['centos', 'redhat', 'red hat', 'oracle', 'cbl-mariner', 'mariner', 'rhel', 'rocky', 'alma']:
        if distro.startswith(name):
            return 'SSL_CERT_FILE', '/etc/pki/tls/certs/ca-bundle.crt'

    for name in ['suse', 'sles', 'opensuse']:
        if distro.startswith(name):
            if version.startswith('12'):
                return 'SSL_CERT_DIR', '/var/lib/ca-certificates/openssl'
            elif version.startswith('15'):
                return 'SSL_CERT_DIR', '/etc/ssl/certs'

    log_and_exit(operation, GenericErrorCode, 'Unable to determine values for SSL_CERT_DIR or SSL_CERT_FILE')


def is_arc_installed():
    """
    Check if this is an Arc machine
    """
    # Using systemctl to check this since Arc only supports VMs that have systemd
    check_arc = os.system('systemctl status himdsd 1>/dev/null 2>&1')
    return check_arc == 0


def get_arc_endpoint():
    """
    Find the endpoint for Arc IMDS
    """
    endpoint_filepath = '/lib/systemd/system.conf.d/azcmagent.conf'
    endpoint = ''
    try:
        with open(endpoint_filepath, 'r') as f:
            data = f.read()
        endpoint = data.split("\"IMDS_ENDPOINT=")[1].split("\"\n")[0]
    except:
        hutil_log_error('Unable to load Arc IMDS endpoint from {0}'.format(endpoint_filepath))
    return endpoint


def get_imds_endpoint():
    """
    Find the appropriate endpoint (Azure or Arc) for IMDS
    """
    azure_imds_endpoint = 'http://169.254.169.254/metadata/instance?api-version=2018-10-01'
    if (is_arc_installed()):
        hutil_log_info('Arc is installed, loading Arc-specific IMDS endpoint')
        imds_endpoint = get_arc_endpoint()
        if imds_endpoint:
            imds_endpoint += '/metadata/instance?api-version=2019-08-15'
        else:
            # Fall back to the traditional IMDS endpoint; the cloud domain and VM
            # resource id detection logic are resilient to failed queries to IMDS
            imds_endpoint = azure_imds_endpoint
            hutil_log_info('Falling back to default Azure IMDS endpoint')
    else:
        imds_endpoint = azure_imds_endpoint

    hutil_log_info('Using IMDS endpoint "{0}"'.format(imds_endpoint))
    return imds_endpoint


def get_azure_environment_and_region():
    """
    Retreive the Azure environment and region from Azure or Arc IMDS
    """
    imds_endpoint = get_imds_endpoint()
    req = urllib.request.Request(imds_endpoint)
    req.add_header('Metadata', 'True')

    environment = region = None

    try:
        response = json.loads(urllib.request.urlopen(req).read())

        if ('compute' in response):
            if ('azEnvironment' in response['compute']):
                environment = response['compute']['azEnvironment']
            if ('location' in response['compute']):
                region = response['compute']['location'].lower()
    except urllib.error.HTTPError as e:
        hutil_log_error('Request to Metadata service URL failed with an HTTPError: {0}'.format(e))
        hutil_log_error('Response from Metadata service: {0}'.format(e.read()))
    except:
        hutil_log_error('Unexpected error from Metadata service')

    return environment, region


def run_command_and_log(cmd, check_error = True, log_cmd = True):
    """
    Run the provided shell command and log its output, including stdout and
    stderr.
    The output should not contain any PII, but the command might. In this case,
    log_cmd should be set to False.
    """
    exit_code, output = run_get_output(cmd, check_error, log_cmd)
    if log_cmd:
        hutil_log_info('Output of command "{0}": \n{1}'.format(cmd.rstrip(), output))
    else:
        hutil_log_info('Output: \n{0}'.format(output))

    # also write output to STDERR since WA agent uploads that to Azlinux Kusto DB
    # take only the last 100 characters as extension cuts off after that
    try:
        if exit_code != 0:
            sys.stderr.write(output[-500:])

        if "Permission denied" in output:
            # Enable failures
            # https://github.com/Azure/azure-marketplace/wiki/Extension-Build-Notes-Best-Practices#error-codes-and-messages-output-to-stderr
            exit_code = 52

    except:
        hutil_log_info('Failed to write output to STDERR')

    return exit_code, output

def run_command_with_retries_output(cmd, retries, retry_check, final_check = None,
                             check_error = True, log_cmd = True,
                             initial_sleep_time = InitialRetrySleepSeconds,
                             sleep_increase_factor = 1):
    """
    Caller provides a method, retry_check, to use to determine if a retry
    should be performed. This must be a function with two parameters:
    exit_code and output
    The final_check can be provided as a method to perform a final check after
    retries have been exhausted
    Logic used: will retry up to retries times with initial_sleep_time in
    between tries
    If the retry_check retuns True for retry_verbosely, we will try cmd with
    the standard -v verbose flag added
    """
    try_count = 0
    sleep_time = initial_sleep_time
    run_cmd = cmd
    run_verbosely = False

    while try_count <= retries:
        if run_verbosely:
            run_cmd = cmd + ' -v'
        exit_code, output = run_command_and_log(run_cmd, check_error, log_cmd)
        should_retry, retry_message, run_verbosely = retry_check(exit_code,
                                                                 output)
        if not should_retry:
            break
        try_count += 1
        hutil_log_info(retry_message)
        time.sleep(sleep_time)
        sleep_time *= sleep_increase_factor

    if final_check is not None:
        exit_code = final_check(exit_code, output)

    return exit_code, output


def is_dpkg_or_rpm_locked(exit_code, output):
    """
    If dpkg is locked, the output will contain a message similar to 'dpkg
    status database is locked by another process'
    """
    if exit_code != 0:
        dpkg_locked_search = r'^.*dpkg.+lock.*$'
        dpkg_locked_re = re.compile(dpkg_locked_search, re.M)
        if dpkg_locked_re.search(output):
            return True

        rpm_locked_search = r'^.*rpm.+lock.*$'
        rpm_locked_re = re.compile(rpm_locked_search, re.M)
        if rpm_locked_re.search(output):
            return True
    return False


def retry_if_dpkg_or_rpm_locked(exit_code, output):
    """
    Some commands fail because the package manager is locked (apt-get/dpkg
    only); this will allow retries on failing commands.
    """
    retry_verbosely = False
    dpkg_or_rpm_locked = is_dpkg_or_rpm_locked(exit_code, output)
    apt_get_exit_code, apt_get_output = run_get_output('which apt-get',
                                                       chk_err = False,
                                                       log_cmd = False)
    if dpkg_or_rpm_locked:
        return True, 'Retrying command because package manager is locked.', \
               retry_verbosely
    else:
        return False, '', False


def final_check_if_dpkg_or_rpm_locked(exit_code, output):
    """
    If dpkg or rpm is still locked after the retries, we want to return a specific
    error code
    """
    dpkg_or_rpm_locked = is_dpkg_or_rpm_locked(exit_code, output)
    if dpkg_or_rpm_locked:
        exit_code = DPKGOrRPMLockedErrorCode
    return exit_code


def get_settings():
    """
    Retrieve the configuration for this extension operation
    """
    global SettingsDict
    public_settings = None
    protected_settings = None

    if HUtilObject is not None:
        public_settings = HUtilObject.get_public_settings()
        protected_settings = HUtilObject.get_protected_settings()
    elif SettingsDict is not None:
        public_settings = SettingsDict['public_settings']
        protected_settings = SettingsDict['protected_settings']
    else:
        SettingsDict = {}
        handler_env = get_handler_env()
        try:
            config_dir = str(handler_env['handlerEnvironment']['configFolder'])
        except:
            config_dir = os.path.join(os.getcwd(), 'config')

        seq_no = get_latest_seq_no()
        settings_path = os.path.join(config_dir, '{0}.settings'.format(seq_no))
        try:
            with open(settings_path, 'r') as settings_file:
                settings_txt = settings_file.read()
            settings = json.loads(settings_txt)
            h_settings = settings['runtimeSettings'][0]['handlerSettings']
            public_settings = h_settings['publicSettings']
            SettingsDict['public_settings'] = public_settings
        except:
            hutil_log_error('Unable to load handler settings from ' \
                            '{0}'.format(settings_path))

        if ('protectedSettings' in h_settings
                and 'protectedSettingsCertThumbprint' in h_settings
                and h_settings['protectedSettings'] is not None
                and h_settings['protectedSettingsCertThumbprint'] is not None):
            encoded_settings = h_settings['protectedSettings']
            settings_thumbprint = h_settings['protectedSettingsCertThumbprint']
            encoded_cert_path = os.path.join('/var/lib/waagent',
                                             '{0}.crt'.format(
                                                       settings_thumbprint))
            encoded_key_path = os.path.join('/var/lib/waagent',
                                            '{0}.prv'.format(
                                                      settings_thumbprint))
            decoded_settings = base64.standard_b64decode(encoded_settings)
            decrypt_cmd = 'openssl smime -inform DER -decrypt -recip {0} ' \
                          '-inkey {1}'.format(encoded_cert_path,
                                              encoded_key_path)

            try:
                session = subprocess.Popen([decrypt_cmd], shell = True,
                                           stdin = subprocess.PIPE,
                                           stderr = subprocess.STDOUT,
                                           stdout = subprocess.PIPE)
                output = session.communicate(decoded_settings)
            except OSError:
                pass
            protected_settings_str = output[0]

            if protected_settings_str is None:
                log_and_exit('Enable', GenericErrorCode, 'Failed decrypting protectedSettings')
            protected_settings = ''
            try:
                protected_settings = json.loads(protected_settings_str)
            except:
                hutil_log_error('JSON exception decoding protected settings')
            SettingsDict['protected_settings'] = protected_settings

    return public_settings, protected_settings


def update_status_file(operation, exit_code, exit_status, message):
    """
    Mimic HandlerUtil method do_status_report in case hutil method is not
    available
    Write status to status file
    """
    handler_env = get_handler_env()
    try:
        extension_version = str(handler_env['version'])
        status_dir = str(handler_env['handlerEnvironment']['statusFolder'])
    except:
        extension_version = "1.0"
        status_dir = os.path.join(os.getcwd(), 'status')

    status_txt = [{
        "version" : extension_version,
        "timestampUTC" : time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status" : {
            "name" : "Microsoft.Azure.Monitor.AzureMonitorLinuxAgent",
            "operation" : operation,
            "status" : exit_status,
            "code" : exit_code,
            "formattedMessage" : {
                "lang" : "en-US",
                "message" : message
            }
        }
    }]

    status_json = json.dumps(status_txt)

    # Find the most recently changed config file and then use the
    # corresponding status file
    latest_seq_no = get_latest_seq_no()

    status_path = os.path.join(status_dir, '{0}.status'.format(latest_seq_no))
    status_tmp = '{0}.tmp'.format(status_path)
    with open(status_tmp, 'w+') as tmp_file:
        tmp_file.write(status_json)
    os.rename(status_tmp, status_path)


def get_handler_env():
    """
    Set and retrieve the contents of HandlerEnvironment.json as JSON
    """
    global HandlerEnvironment
    if HandlerEnvironment is None:
        handler_env_path = os.path.join(os.getcwd(), 'HandlerEnvironment.json')
        try:
            with open(handler_env_path, 'r') as handler_env_file:
                handler_env_txt = handler_env_file.read()
            handler_env = json.loads(handler_env_txt)
            if type(handler_env) == list:
                handler_env = handler_env[0]
            HandlerEnvironment = handler_env
        except Exception as e:
            waagent_log_error(str(e))
    return HandlerEnvironment


def get_latest_seq_no():
    """
    Determine the latest operation settings number to use
    """
    global SettingsSequenceNumber
    if SettingsSequenceNumber is None:
        handler_env = get_handler_env()
        try:
            config_dir = str(handler_env['handlerEnvironment']['configFolder'])
        except:
            config_dir = os.path.join(os.getcwd(), 'config')

        latest_seq_no = -1
        cur_seq_no = -1
        latest_time = None
        try:
            for dir_name, sub_dirs, file_names in os.walk(config_dir):
                for file_name in file_names:
                    file_basename = os.path.basename(file_name)
                    match = re.match(r'[0-9]{1,10}\.settings', file_basename)
                    if match is None:
                        continue
                    cur_seq_no = int(file_basename.split('.')[0])
                    file_path = os.path.join(config_dir, file_name)
                    cur_time = os.path.getmtime(file_path)
                    if latest_time is None or cur_time > latest_time:
                        latest_time = cur_time
                        latest_seq_no = cur_seq_no
        except:
            pass
        if latest_seq_no < 0:
            latest_seq_no = 0
        SettingsSequenceNumber = latest_seq_no

    return SettingsSequenceNumber


def run_get_output(cmd, chk_err = False, log_cmd = True):
    """
    Mimic waagent mothod RunGetOutput in case waagent is not available
    Run shell command and return exit code and output
    """
    if 'Utils.WAAgentUtil' in sys.modules:
        # WALinuxAgent-2.0.14 allows only 2 parameters for RunGetOutput
        # If checking the number of parameters fails, pass 2
        try:
            sig = inspect.signature(waagent.RunGetOutput)
            params = sig.parameters
            waagent_params = len(params)
        except:
            try:
                spec = inspect.getargspec(waagent.RunGetOutput)
                params = spec.args
                waagent_params = len(params)
            except:
                waagent_params = 2
        if waagent_params >= 3:
            exit_code, output = waagent.RunGetOutput(cmd, chk_err, log_cmd)
        else:
            exit_code, output = waagent.RunGetOutput(cmd, chk_err)
    else:
        try:
            output = subprocess.check_output(cmd, stderr = subprocess.STDOUT,
                                             shell = True)
            exit_code = 0
        except subprocess.CalledProcessError as e:
            exit_code = e.returncode
            output = e.output

    output = output.encode('utf-8')

    # On python 3, encode returns a byte object, so we must decode back to a string
    if sys.version_info >= (3,):
        output = output.decode('utf-8', 'ignore')

    return exit_code, output.strip()


def init_waagent_logger():
    """
    Initialize waagent logger
    If waagent has not been imported, catch the exception
    """
    try:
        waagent.LoggerInit('/var/log/waagent.log', '/dev/stdout', True)
    except Exception as e:
        print('Unable to initialize waagent log because of exception ' \
              '{0}'.format(e))


def waagent_log_info(message):
    """
    Log informational message, being cautious of possibility that waagent may
    not be imported
    """
    if 'Utils.WAAgentUtil' in sys.modules:
        waagent.Log(message)
    else:
        print('Info: {0}'.format(message))


def waagent_log_error(message):
    """
    Log error message, being cautious of possibility that waagent may not be
    imported
    """
    if 'Utils.WAAgentUtil' in sys.modules:
        waagent.Error(message)
    else:
        print('Error: {0}'.format(message))


def hutil_log_info(message):
    """
    Log informational message, being cautious of possibility that hutil may
    not be imported and configured
    """
    if HUtilObject is not None:
        HUtilObject.log(message)
    else:
        print('Info: {0}'.format(message))


def hutil_log_error(message):
    """
    Log error message, being cautious of possibility that hutil may not be
    imported and configured
    """
    if HUtilObject is not None:
        HUtilObject.error(message)
    else:
        print('Error: {0}'.format(message))


def log_and_exit(operation, exit_code = GenericErrorCode, message = ''):
    """
    Log the exit message and perform the exit
    """
    if exit_code == 0:
        waagent_log_info(message)
        hutil_log_info(message)
        exit_status = 'success'
    else:
        waagent_log_error(message)
        hutil_log_error(message)
        exit_status = 'failed'

    if HUtilObject is not None:
        HUtilObject.do_exit(exit_code, operation, exit_status, str(exit_code),
                            message)
    else:
        update_status_file(operation, str(exit_code), exit_status, message)
        sys.exit(exit_code)


# Exceptions
# If these exceptions are expected to be caught by the main method, they
# include an error_code field with an integer with which to exit from main

class AzureMonitorAgentForLinuxException(Exception):
    """
    Base exception class for all exceptions; as such, its error code is the
    basic error code traditionally returned in Linux: 1
    """
    error_code = GenericErrorCode
    def get_error_message(self, operation):
        """
        Return a descriptive error message based on this type of exception
        """
        return '{0} failed with exit code {1}'.format(operation,
                                                      self.error_code)


class ParameterMissingException(AzureMonitorAgentForLinuxException):
    """
    There is a missing parameter for the AzureMonitorLinuxAgent Extension
    """
    error_code = MissingorInvalidParameterErrorCode
    def get_error_message(self, operation):
        return '{0} failed due to a missing parameter: {1}'.format(operation,
                                                                   self.error_code)

if __name__ == '__main__' :
    main()
