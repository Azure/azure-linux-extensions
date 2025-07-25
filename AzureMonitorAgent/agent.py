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
import os
import os.path
import datetime
import signal
import pwd
import glob
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
import shutil
import hashlib
import fileinput
import contextlib
import ama_tst.modules.install.supported_distros as supported_distros
from collections import OrderedDict
from hashlib import sha256
from shutil import copyfile
from shutil import copytree
from shutil import rmtree

from threading import Thread
import telegraf_utils.telegraf_config_handler as telhandler
import metrics_ext_utils.metrics_constants as metrics_constants
import metrics_ext_utils.metrics_ext_handler as me_handler
import metrics_ext_utils.metrics_common_utils as metrics_utils

try:
    import urllib.request as urllib # Python 3+
except ImportError:
    import urllib2 as urllib # Python 2

try:
    from urllib.parse import urlparse  # Python 3+
except ImportError:
    from urlparse import urlparse  # Python 2

try:
    import urllib.error as urlerror # Python 3+
except ImportError:
    import urllib2 as urlerror # Python 2


# python shim can only make IMDS calls which shouldn't go through proxy
try:
    urllib.getproxies = lambda x = None: {}
except Exception as e:
    print('Resetting proxies failed with error: {0}'.format(e))    

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
AMASyslogConfigMarkerPath = '/etc/opt/microsoft/azuremonitoragent/config-cache/syslog.marker'
AMASyslogPortFilePath = '/etc/opt/microsoft/azuremonitoragent/config-cache/syslog.port'
AMAFluentPortFilePath = '/etc/opt/microsoft/azuremonitoragent/config-cache/fluent.port'
PreviewFeaturesDirectory = '/etc/opt/microsoft/azuremonitoragent/config-cache/previewFeatures/'
ArcSettingsFile = '/var/opt/azcmagent/localconfig.json'
AMAAstTransformConfigMarkerPath = '/etc/opt/microsoft/azuremonitoragent/config-cache/agenttransform.marker'
AMAExtensionLogRotateFilePath = '/etc/logrotate.d/azuremonitoragentextension'
WAGuestAgentLogRotateFilePath = '/etc/logrotate.d/waagent-extn.logrotate'
SupportedArch = set(['x86_64', 'aarch64'])

# Error codes
GenericErrorCode = 1
UnsupportedOperatingSystem = 51
IndeterminateOperatingSystem = 51
MissingorInvalidParameterErrorCode = 53
DPKGOrRPMLockedErrorCode = 56
MissingDependency = 52

# Settings
GenevaConfigKey = "genevaConfiguration"
AzureMonitorConfigKey = "azureMonitorConfiguration"

# Configuration
HUtilObject = None
SettingsSequenceNumber = None
HandlerEnvironment = None
SettingsDict = None


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
        elif re.match('^([-/]*)(syslogconfig)', option):
            operation = 'Syslogconfig'
        elif re.match('^([-/]*)(transformconfig)', option):
            operation = 'Transformconfig'
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
            message = 'Install failed with exit code 1. For error details, check logs ' \
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
            return MissingDependency
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

def set_metrics_binaries():
    current_arch = platform.machine()
    # Rename the Arch appropriate metrics extension binary to MetricsExtension
    MetricsExtensionDir = os.path.join(os.getcwd(), 'MetricsExtensionBin')
    SupportedMEPath = os.path.join(MetricsExtensionDir, 'metricsextension_'+current_arch)

    if os.path.exists(SupportedMEPath):
        os.rename(SupportedMEPath, os.path.join(MetricsExtensionDir, 'MetricsExtension'))

    # Cleanup unused ME binaries
    for f in os.listdir(MetricsExtensionDir):
        if f != 'MetricsExtension':
            os.remove(os.path.join(MetricsExtensionDir, f))

def copy_amacoreagent_binaries():
    current_arch = platform.machine()
    amacoreagent_bin_local_path = os.getcwd() + "/amaCoreAgentBin/amacoreagent_" + current_arch
    amacoreagent_bin = "/opt/microsoft/azuremonitoragent/bin/amacoreagent"
    compare_and_copy_bin(amacoreagent_bin_local_path, amacoreagent_bin)

    if current_arch == 'x86_64':
        libgrpc_bin_local_path = os.getcwd() + "/amaCoreAgentBin/libgrpc_csharp_ext.x64.so"
        libgrpc_bin = "/opt/microsoft/azuremonitoragent/bin/libgrpc_csharp_ext.x64.so"
        compare_and_copy_bin(libgrpc_bin_local_path, libgrpc_bin)

        liblz4x64_bin_local_path = os.getcwd() + "/amaCoreAgentBin/liblz4x64.so"
        liblz4x64_bin = "/opt/microsoft/azuremonitoragent/bin/liblz4x64.so"
        compare_and_copy_bin(liblz4x64_bin_local_path, liblz4x64_bin)   
    elif current_arch == 'aarch64':
        libgrpc_bin_local_path = os.getcwd() + "/amaCoreAgentBin/libgrpc_csharp_ext.arm64.so"
        libgrpc_bin = "/opt/microsoft/azuremonitoragent/bin/libgrpc_csharp_ext.arm64.so"
        compare_and_copy_bin(libgrpc_bin_local_path, libgrpc_bin)
                  
    agentlauncher_bin_local_path = os.getcwd() + "/agentLauncherBin/agentlauncher_" + current_arch
    agentlauncher_bin = "/opt/microsoft/azuremonitoragent/bin/agentlauncher"
    compare_and_copy_bin(agentlauncher_bin_local_path, agentlauncher_bin)

def copy_mdsd_fluentbit_binaries():
    current_arch = platform.machine()
    mdsd_bin_local_path = os.getcwd() + "/mdsdBin/mdsd_" + current_arch
    mdsdmgr_bin_local_path = os.getcwd() + "/mdsdBin/mdsdmgr_" + current_arch
    fluentbit_bin_local_path = os.getcwd() + "/fluentBitBin/fluent-bit_" + current_arch
    mdsd_bin = "/opt/microsoft/azuremonitoragent/bin/mdsd"
    mdsdmgr_bin = "/opt/microsoft/azuremonitoragent/bin/mdsdmgr"
    fluentbit_bin = "/opt/microsoft/azuremonitoragent/bin/fluent-bit"

    # copy the required libs to our test directory first
    lib_dir = os.path.join(os.getcwd(), "lib")
    if os.path.exists(lib_dir):
        rmtree(lib_dir)

    if sys.version_info >= (3, 8):
        # dirs_exist_ok parameter was added in Python 3.8
        copytree("/opt/microsoft/azuremonitoragent/lib", lib_dir, dirs_exist_ok=True)
    else:
        copytree("/opt/microsoft/azuremonitoragent/lib", lib_dir)
    
    canUseSharedmdsd, _ = run_command_and_log('ldd ' + mdsd_bin_local_path + ' | grep "not found"')
    canUseSharedmdsdmgr, _ = run_command_and_log('ldd ' + mdsdmgr_bin_local_path + ' | grep "not found"')
    if canUseSharedmdsd != 0 and canUseSharedmdsdmgr != 0:        
        compare_and_copy_bin(mdsd_bin_local_path, mdsd_bin)
        compare_and_copy_bin(mdsdmgr_bin_local_path, mdsdmgr_bin)

    canUseSharedfluentbit, _ = run_command_and_log('ldd ' + fluentbit_bin_local_path + ' | grep "not found"')
    if canUseSharedfluentbit != 0:
        compare_and_copy_bin(fluentbit_bin_local_path, fluentbit_bin)

    rmtree(os.getcwd() + "/lib")    

def get_installed_package_version(package_name):
    """
    Get the installed version of a package, including architecture.
    In the case of dpkg, we need to rsplit() the architecture part, see below for why.
    Examples of version_string:
      - RPM: azuremonitoragent-1.33.4-build.main.872.x86_64.rpm -> 1.33.4-build.main.000.x86_64
      - DEB: azuremonitoragent_1.35.4-971_x86_64.deb -> 1.35.4-000
    Returns: (is_installed, version_string)
    """
    if PackageManager == "dpkg":
        # We need Architecture to match BundleFileNameDeb
        cmd = "dpkg-query -W -f='${{Version}}.${{Architecture}}' {0} 2>/dev/null".format(package_name)
    elif PackageManager == "rpm":
        cmd = "rpm -q --qf '%{{VERSION}}-%{{RELEASE}}.%{{ARCH}}' {0} 2>/dev/null".format(package_name)
    else:
        return False, "Could not determine package manager"

    exit_code, output = run_command_and_log(cmd, check_error=False)

    if exit_code != 0 or not output:
        return False, "Package not found"

    version_string = output.strip()

    if PackageManager == "dpkg":
        # For dpkg, the version string is in the format: 1.33.4-build.main.872.amd64
        # We want to return just the version part: 1.33.4-build.main.872
        version_string = version_string.rsplit('.', 1)[0]
    return True, version_string

def get_bundle_version():
    """
    Extract version number from bundle filename. (i.e. 1.3***...<build #>)
    Examples:
      - RPM: azuremonitoragent-1.33.4-build.main.000.x86_64.rpm -> 1.33.4-build.main.000.x86_64
      - DEB: azuremonitoragent_1.35.4-971_x86_64.deb -> 1.35.4-000
    """
    if PackageManager == "dpkg":
        # Match between first underscore and next underscore (version)
        match = re.search(r'azuremonitoragent_([^_]+)_', BundleFileNameDeb)
    else:  # rpm
        # Match between first dash and last dot before arch (version)
        match = re.search(r'azuremonitoragent-([^-]+(?:-[^-]+)*)\.', BundleFileNameRpm)
    if match:
        return match.group(1)
    return ""

def install():
    """
    Ensure that this VM distro and version are supported.
    Install the Azure Monitor Linux Agent package, using retries.
    Note: install operation times out from WAAgent at 15 minutes, so do not
    wait longer.
    """

    exit_if_vm_not_supported('Install')
    find_package_manager("Install")
    set_os_arch('Install')
    vm_dist, vm_ver = find_vm_distro('Install')

    # Check if Debian 12 VMs have rsyslog package (required for AMA 1.31+)
    if (vm_dist.startswith('debian')) and vm_ver.startswith('12'):
        check_rsyslog, _ = run_command_and_log("dpkg -s rsyslog")
        if check_rsyslog != 0:
            hutil_log_info("'rsyslog' package missing from Debian 12 machine, installing to allow AMA to run.")
            rsyslog_exit_code, rsyslog_output = run_command_and_log("DEBIAN_FRONTEND=noninteractive apt-get update && \
                                                                    DEBIAN_FRONTEND=noninteractive apt-get install -y rsyslog")
            if rsyslog_exit_code != 0:
                return rsyslog_exit_code, rsyslog_output
    
    # Check if Amazon 2023 VMs have rsyslog package (required for AMA 1.31+)
    if (vm_dist.startswith('amzn')) and vm_ver.startswith('2023'):
        check_rsyslog, _ = run_command_and_log("dnf list installed | grep rsyslog.x86_64")
        if check_rsyslog != 0:
            hutil_log_info("'rsyslog' package missing from Amazon Linux 2023 machine, installing to allow AMA to run.")
            rsyslog_exit_code, rsyslog_output = run_command_and_log("dnf install -y rsyslog")
            if rsyslog_exit_code != 0:
                return rsyslog_exit_code, rsyslog_output
    
    # Flag to handle the case where the same package is already installed
    same_package_installed = False

    # Check if the package is already installed with the correct version
    is_installed, installed_version = get_installed_package_version("azuremonitoragent")
    bundle_version = get_bundle_version()

    # Check if the package is already installed, if so determine if it is the same as the bundle or not
    if is_installed:
        hutil_log_info("Found installed azuremonitoragent version: {0}".format(installed_version))
        hutil_log_info("Bundle version: {0}".format(bundle_version))

        if installed_version == bundle_version:
            hutil_log_info("This version of azuremonitoragent package is already installed. Skipping package install.")
            same_package_installed = True
        else:
            error_msg = "A different version of azuremonitoragent package is already installed."
            troubleshooting = "Try deleting the VM extension via the portal or CLI using 'az vm extension delete -n AzureMonitorLinuxAgent -g <resource group name> -n <VM name>'."

            if PackageManager == "dpkg":
                manual_fix = "If that does not work you may need to repair manually by running 'rm /var/lib/dpkg/info/azuremonitoragent.*' followed by 'dpkg --force-all -P azuremonitoragent'"
            else:  # rpm
                manual_fix = "If that does not work you may need to repair manually by running 'rpm -e --noscripts --nodeps azuremonitoragent'"

            full_msg = "{0} {1} {2}".format(error_msg, troubleshooting, manual_fix)
            hutil_log_info(full_msg)
            return 1, full_msg

    # If the package is not already installed, proceed with installation otherwise skip since it is the same package version
    if not same_package_installed:
        hutil_log_info("No previous package found, installing Azure Monitor Agent package.")
        package_directory = os.path.join(os.getcwd(), PackagesDirectory)
        bundle_path = os.path.join(package_directory, BundleFileName)
        os.chmod(bundle_path, 100)
        print(PackageManager, " and ", BundleFileName)
        AMAInstallCommand = "{0} {1} -i {2}".format(PackageManager, PackageManagerOptions, bundle_path)
        hutil_log_info('Running command "{0}"'.format(AMAInstallCommand))

        # Try to install with retry, since install can fail due to concurrent package operations
        exit_code, output = run_command_with_retries_output(AMAInstallCommand, retries = 15,
                                            retry_check = retry_if_dpkg_or_rpm_locked,
                                            final_check = final_check_if_dpkg_or_rpm_locked)

        # Retry install for aarch64 rhel8 VMs as initial install fails to create symlink to /etc/systemd/system/azuremonitoragent.service
        # in /etc/systemd/system/multi-user.target.wants/azuremonitoragent.service
        if vm_dist.replace(' ','').lower().startswith('redhat') and vm_ver == '8.6' and platform.machine() == 'aarch64':
            exit_code, output = run_command_with_retries_output(AMAInstallCommand, retries = 15,
                                            retry_check = retry_if_dpkg_or_rpm_locked,
                                            final_check = final_check_if_dpkg_or_rpm_locked)

        if exit_code != 0:
            return exit_code, output

        # System daemon reload is required for systemd to pick up the new service
        exit_code, output = run_command_and_log("systemctl daemon-reload")
        if exit_code != 0:
            return exit_code, output

    # Copy the AMACoreAgent and agentlauncher binaries
    copy_amacoreagent_binaries()

    set_metrics_binaries()

    # Copy KqlExtension binaries
    # Needs to be revisited for aarch64
    copy_kqlextension_binaries()

    # Install azureotelcollector
    install_azureotelcollector()

    # Copy mdsd and fluent-bit with OpenSSL dynamically linked
    if is_feature_enabled('useDynamicSSL'):
        # Check if they have libssl.so.1.1 since AMA is built against this version
        libssl1_1, _ = run_command_and_log('ldconfig -p | grep libssl.so.1.1')
        if libssl1_1 == 0:
            copy_mdsd_fluentbit_binaries()
    
    # Set task limits to max of 65K in suse 12
    # Based on Task 9764411: AMA broken after 1.7 in sles 12 - https://dev.azure.com/msazure/One/_workitems/edit/9764411
    vm_dist, _ = find_vm_distro('Install')
    if (vm_dist.startswith('suse') or vm_dist.startswith('sles')):
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

    return 0, "Azure Monitor Agent package installed successfully"

def uninstall():
    """
    Uninstall the Azure Monitor Linux Agent.
    This is a somewhat soft uninstall. It is not a purge.
    Note: uninstall operation times out from WAAgent at 5 minutes
    """

    exit_if_vm_not_supported('Uninstall')
    find_package_manager("Uninstall")

    # Before we uninstall, we need to ensure AMA is installed to begin with
    is_installed, _ = get_installed_package_version("azuremonitoragent")
    if not is_installed:
        hutil_log_info("Azure Monitor Agent is not installed, nothing to uninstall.")
        return 0, "Azure Monitor Agent is not installed, nothing to uninstall."

    AMAUninstallCommand = ""
    if PackageManager == "dpkg":
        AMAUninstallCommand = "dpkg -P azuremonitoragent"
    elif PackageManager == "rpm":
        AMAUninstallCommand = "rpm -e azuremonitoragent"
    else:
        log_and_exit("Uninstall", UnsupportedOperatingSystem, "The OS has neither rpm nor dpkg" )
    hutil_log_info('Running command "{0}"'.format(AMAUninstallCommand))

    remove_localsyslog_configs()

    uninstall_azureotelcollector()

    # remove the logrotate config
    if os.path.exists(AMAExtensionLogRotateFilePath):   
        try:
            os.remove(AMAExtensionLogRotateFilePath)
        except Exception as ex:
            output = 'Logrotate removal failed with error: {0}\n' \
                'Stacktrace: {1}'.format(ex, traceback.format_exc())
            hutil_log_info(output)

    # Retry, since uninstall can fail due to concurrent package operations
    try:
        is_still_installed = False
        exit_code, output = run_command_with_retries_output(AMAUninstallCommand, retries = 4,
                                            retry_check = retry_if_dpkg_or_rpm_locked,
                                            final_check = final_check_if_dpkg_or_rpm_locked)

        # check if the uninstall was successful
        if PackageManager == "dpkg":
            exit_code, _ = run_command_and_log("dpkg-query -W -f='${Status}' azuremonitoragent 2>/dev/null", check_error=False)
            is_still_installed = (exit_code == 0)
        elif PackageManager == "rpm":
            exit_code, _ = run_command_and_log("rpm -q azuremonitoragent", check_error=False)
            is_still_installed = (exit_code == 0)

        # If there is still a package leftover
        if is_still_installed:
            AMAUninstallCommandForce = ""
            # do a force uninstall since the package is still installed
            if PackageManager == "dpkg":
                # we can remove the post and pre scripts first then purge
                RemoveScriptsCommand = "rm /var/lib/dpkg/info/azuremonitoragent.*"
                run_command_with_retries_output(RemoveScriptsCommand, retries = 4,
                                                retry_check = retry_if_dpkg_or_rpm_locked,
                                                final_check = final_check_if_dpkg_or_rpm_locked)
                AMAUninstallCommandForce = "dpkg --force-all -P azuremonitoragent"
            elif PackageManager == "rpm":
                AMAUninstallCommandForce = "rpm -e --noscripts --nodeps azuremonitoragent"

            hutil_log_info("Forcing uninstall due to something missing")
            exit_code, output = run_command_with_retries_output(AMAUninstallCommandForce, retries = 4,
                                                retry_check = retry_if_dpkg_or_rpm_locked,
                                                final_check = final_check_if_dpkg_or_rpm_locked)
        else:
            # If the package is not installed our exit code is non-zero so we need to "reset" it to 0
            hutil_log_info("Uninstall command executed successfully, package is no longer installed.")
            output = "Azure Monitor Agent package uninstalled successfully"
            exit_code = 0
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

    exit_if_vm_not_supported('Enable')

    ensure = OrderedDict([
        ("azuremonitoragent", False),
        ("azuremonitoragentmgr", False)
    ])

    # Set traceFlags in publicSettings to enable mdsd tracing. For example, the EventIngest flag can be enabled via "traceFlags": "0x2"
    flags = ""
    if public_settings is not None and "traceFlags" in public_settings:
        flags = "-T {} ".format(public_settings.get("traceFlags"))

    # Use an Ordered Dictionary to ensure MDSD_OPTIONS (and other dependent variables) are written after their dependencies
    default_configs = OrderedDict([
        ("MDSD_CONFIG_DIR", "/etc/opt/microsoft/azuremonitoragent"),
        ("MDSD_LOG_DIR", "/var/opt/microsoft/azuremonitoragent/log"),
        ("MDSD_ROLE_PREFIX", "/run/azuremonitoragent/default"),
        ("MDSD_SPOOL_DIRECTORY", "/var/opt/microsoft/azuremonitoragent"),
        ("MDSD_OPTIONS", "\"{}-A -R -c /etc/opt/microsoft/azuremonitoragent/mdsd.xml -d -r $MDSD_ROLE_PREFIX -S $MDSD_SPOOL_DIRECTORY/eh -L $MDSD_SPOOL_DIRECTORY/events\"".format(flags)),
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
    is_gcs_single_tenant = False
    GcsEnabled, McsEnabled = get_control_plane_mode()

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
        is_gcs_single_tenant = True
        handle_gcs_config(public_settings, protected_settings, default_configs)
        
    # generate local syslog configuration files as in auto config syslog is not driven from DCR
    # Note that internally AMCS with geneva config path can be used in which case syslog should be handled same way as default 1P
    # generate local syslog configuration files as in 1P syslog is not driven from DCR
    if GcsEnabled:
        generate_localsyslog_configs(uses_gcs=True, uses_mcs=McsEnabled)

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
        else:
            log_and_exit("Enable", GenericErrorCode, "Could not find the file {0}".format(config_file))
    except Exception as e:
        log_and_exit("Enable", GenericErrorCode, "Failed to add environment variables to {0}: {1}".format(config_file, e))

    if "ENABLE_MCS" in default_configs and default_configs["ENABLE_MCS"] == "true":
        # enable processes for Custom Logs
        ensure["azuremonitor-agentlauncher"] = True
        ensure["azuremonitor-coreagent"] = True
            
        # start the metrics, agent transform and syslog watchers only in 3P mode
        start_metrics_process()
        start_syslogconfig_process()
    elif ensure.get("azuremonitoragentmgr") or is_gcs_single_tenant:
        # In GCS scenarios, ensure that AMACoreAgent is running
        ensure["azuremonitor-coreagent"] = True

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

    if platform.machine() != 'aarch64':
        if "ENABLE_MCS" in default_configs and default_configs["ENABLE_MCS"] == "true":
            # start/enable kql extension only in 3P mode and non aarch64
            kql_start_code, kql_output = run_command_and_log(get_service_command("azuremonitor-kqlextension", *operations))
            output += kql_output # do not block if kql start fails
            # start transformation config watcher process
            start_transformconfig_process()

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
    default_configs["PA_FLUENT_SOCKET_PORT"] = "13005"
    # this port will be dynamic in future
    default_configs["PA_DATA_PORT"] = "13005"
    proxySet = False

    # fetch proxy settings
    if public_settings is not None and "proxy" in public_settings and "mode" in public_settings.get("proxy") and public_settings.get("proxy").get("mode") == "application":
        default_configs["MDSD_PROXY_MODE"] = "application"

        if "address" in public_settings.get("proxy"):
            default_configs["MDSD_PROXY_ADDRESS"] = public_settings.get("proxy").get("address")
        else:
            log_and_exit("Enable", MissingorInvalidParameterErrorCode, 'Parameter "address" is required in proxy public setting')

        if "auth" in public_settings.get("proxy") and public_settings.get("proxy").get("auth") == True:
            if protected_settings is not None and "proxy" in protected_settings and "username" in protected_settings.get("proxy") and "password" in protected_settings.get("proxy"):
                default_configs["MDSD_PROXY_USERNAME"] = protected_settings.get("proxy").get("username")
                default_configs["MDSD_PROXY_PASSWORD"] = protected_settings.get("proxy").get("password")
                set_proxy(default_configs["MDSD_PROXY_ADDRESS"], default_configs["MDSD_PROXY_USERNAME"], default_configs["MDSD_PROXY_PASSWORD"])
                proxySet = True
            else:
                log_and_exit("Enable", MissingorInvalidParameterErrorCode, 'Parameter "username" and "password" not in proxy protected setting')
        else:
            set_proxy(default_configs["MDSD_PROXY_ADDRESS"], "", "")
            proxySet = True
    
    # is this Arc? If so, check for proxy     
    if os.path.isfile(ArcSettingsFile):
        f = open(ArcSettingsFile, "r")
        data = f.read()

        if (data != ''):
            json_data = json.loads(data)
            BypassProxy = False
            if json_data is not None and "proxy.bypass" in json_data:
                bypass = json_data["proxy.bypass"]
                # proxy.bypass is an array
                if "AMA" in bypass:
                    BypassProxy = True
                    
            if not BypassProxy and json_data is not None and "proxy.url" in json_data:
                url = json_data["proxy.url"]
                # only non-authenticated proxy config is supported
                if url != '':
                    default_configs["MDSD_PROXY_ADDRESS"] = url
                    set_proxy(default_configs["MDSD_PROXY_ADDRESS"], "", "")
                    proxySet = True

    if not proxySet:
        unset_proxy()

    # set arc autonomous endpoints
    az_environment, _ = get_azure_environment_and_region()
    if az_environment == me_handler.ArcACloudName:
        try:
            _, mcs_endpoint = me_handler.get_arca_endpoints_from_himds()
        except Exception as ex:
            log_and_exit("Enable", MissingorInvalidParameterErrorCode, 'Failed to get Arc autonomous endpoints. {0}'.format(ex))

        default_configs["customRegionalEndpoint"] = mcs_endpoint
        default_configs["customGlobalEndpoint"] = mcs_endpoint
        default_configs["customResourceEndpoint"] = "https://monitoring.azs"

    # add managed identity settings if they were provided
    identifier_name, identifier_value, error_msg = get_managed_identity()

    if error_msg:
        log_and_exit("Enable", MissingorInvalidParameterErrorCode, 'Failed to determine managed identity settings. {0}.'.format(error_msg))

    if identifier_name and identifier_value:
        default_configs["MANAGED_IDENTITY"] = "{0}#{1}".format(identifier_name, identifier_value)

def get_control_plane_mode():
    """
    Identify which control plane is in use
    """
    public_settings, protected_settings = get_settings()

    GcsEnabled = False
    McsEnabled = False

    if public_settings is not None and (public_settings.get(GenevaConfigKey) or public_settings.get(AzureMonitorConfigKey)):        
        geneva_configuration = public_settings.get(GenevaConfigKey)
        azure_monitor_configuration = public_settings.get(AzureMonitorConfigKey)

        if geneva_configuration and geneva_configuration.get("enable") == True:
            GcsEnabled = True
        if azure_monitor_configuration and azure_monitor_configuration.get("enable") == True:
            McsEnabled = True
    # Legacy schema
    elif public_settings is not None and public_settings.get("GCS_AUTO_CONFIG") == True:
        GcsEnabled = True
    elif (protected_settings is None or len(protected_settings) == 0) or (public_settings is not None and "proxy" in public_settings and "mode" in public_settings.get("proxy") and public_settings.get("proxy").get("mode") == "application"):
        McsEnabled = True
    else:
        GcsEnabled = True
    
    return GcsEnabled, McsEnabled

def disable():
    """
    Disable Azure Monitor Linux Agent process on the VM.
    Note: disable operation times out from WAAgent at 15 minutes
    """

    #stop the metrics process
    stop_metrics_process()

    #stop syslog config watcher process
    stop_syslogconfig_process()

    #stop agent transform config watcher process
    stop_transformconfig_process()

    # stop amacoreagent and agent launcher
    hutil_log_info('Handler initiating Core Agent and agent launcher')
    if is_systemd():
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

    if platform.machine() != 'aarch64':
        # stop kql extensionso that is not started after system reboot. Do not block if it fails.
        kql_exit_code, disable_output = run_command_and_log(get_service_command("azuremonitor-kqlextension", "stop", "disable"))
        if kql_exit_code != 0:
            status_command = get_service_command("azuremonitor-kqlextension", "status")
            kql_exit_code, kql_status_output = run_command_and_log(status_command)
            hutil_log_info(kql_status_output)

    return exit_code, output

def update():
    """
    Update the current installation of AzureMonitorLinuxAgent
    No logic to install the agent as agent -> install() will be called
    with update because upgradeMode = "UpgradeWithInstall" set in HandlerManifest
    """

    return 0, ""

def restart_launcher():
    # start agent launcher
    hutil_log_info('Handler initiating agent launcher')
    if is_systemd():
        exit_code, output = run_command_and_log('systemctl restart azuremonitor-agentlauncher && systemctl enable azuremonitor-agentlauncher')

def restart_kqlextension():
    # start agent transformation extension process
    hutil_log_info('Handler initiating agent transformation extension (KqlExtension) restart and enable')
    if is_systemd():
        exit_code, output = run_command_and_log('systemctl restart azuremonitor-kqlextension && systemctl enable azuremonitor-kqlextension')

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
        run_command_and_log("echo 'Environment=\"https_proxy={0}\"' >> /etc/systemd/system/azuremonitor-coreagent.service.d/proxy.conf".format(http_proxy))
        os.system('chmod {1} {0}'.format("/etc/systemd/system/azuremonitor-coreagent.service.d/proxy.conf", 400))

        # Update ME
        run_command_and_log("mkdir -p /etc/systemd/system/metrics-extension.service.d")
        run_command_and_log("echo '[Service]' > /etc/systemd/system/metrics-extension.service.d/proxy.conf")
        run_command_and_log("echo 'Environment=\"http_proxy={0}\"' >> /etc/systemd/system/metrics-extension.service.d/proxy.conf".format(http_proxy))
        run_command_and_log("echo 'Environment=\"https_proxy={0}\"' >> /etc/systemd/system/metrics-extension.service.d/proxy.conf".format(http_proxy))
        os.system('chmod {1} {0}'.format("/etc/systemd/system/metrics-extension.service.d/proxy.conf", 400))

        run_command_and_log("systemctl daemon-reload")
        run_command_and_log('systemctl restart azuremonitor-coreagent')
        run_command_and_log('systemctl restart metrics-extension')
        
    except:
        log_and_exit("enable", MissingorInvalidParameterErrorCode, "Failed to update /etc/systemd/system/azuremonitor-coreagent.service.d and /etc/systemd/system/metrics-extension.service.d" )

def unset_proxy():
    """
    # Unset proxy http_proxy env var in dependent services
    """
    
    try:
        hasSettings=False
        
        # Update Coreagent
        if os.path.exists("/etc/systemd/system/azuremonitor-coreagent.service.d/proxy.conf"):
            os.remove("/etc/systemd/system/azuremonitor-coreagent.service.d/proxy.conf")
            hasSettings=True
            
        # Update ME
        if os.path.exists("/etc/systemd/system/metrics-extension.service.d/proxy.conf"):
            os.remove("/etc/systemd/system/metrics-extension.service.d/proxy.conf")
            hasSettings=True
            
        if hasSettings:
            run_command_and_log("systemctl daemon-reload")
            run_command_and_log('systemctl restart azuremonitor-coreagent')
            run_command_and_log('systemctl restart metrics-extension')
        
        
    except:
        log_and_exit("enable", MissingorInvalidParameterErrorCode, "Failed to remove /etc/systemd/system/azuremonitor-coreagent.service.d and /etc/systemd/system/metrics-extension.service.d" )

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

        if identifier_name not in ["client_id", "mi_res_id", "object_id"]:
            return identifier_name, identifier_value, 'Invalid identifier-name provided; must be "client_id" or "mi_res_id" or "object_id"'

        if not identifier_value:
            return identifier_name, identifier_value, 'Invalid identifier-value provided; cannot be empty'

        if identifier_name in ["object_id", "client_id"]:
            guid_re = re.compile(r'[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}')
            if not guid_re.search(identifier_value):
                return identifier_name, identifier_value, 'Invalid identifier-value provided for {0}; must be a GUID'.format(identifier_name)

    return identifier_name, identifier_value, ""


def azureotelcollector_is_active():
    """
    Checks if `azureotelcollector` is installed to run as a systemd service.
    """
    if is_systemd():
        return 0 == os.system('systemctl is-active --quiet azureotelcollector-watcher.path')
    return False


def install_azureotelcollector():
    """
    This method will install the azureotelcollector package and start a systemd file watcher service that watches for configuration file changes.
    MetricsExtension is responsible for writing the configuration file.
    Only if configuration is present, otelcollector process will start to run, the watcher service is responsible to monitor the configurartion file.
    """
    if is_feature_enabled("enableAzureOTelCollector") and is_systemd():
        find_package_manager("Install")
        azureotelcollector_install_command = get_otelcollector_installation_command()
        hutil_log_info('Running command "{0}"'.format(azureotelcollector_install_command))

        # Retry, since install can fail due to concurrent package operations
        exit_code, output = run_command_with_retries_output(
            azureotelcollector_install_command,
            retries = 5,
            retry_check = retry_if_dpkg_or_rpm_locked,
            final_check = final_check_if_dpkg_or_rpm_locked
        )

        if exit_code == 0:
            hutil_log_info('Successfully installed azureotelcollector')
            return True

        hutil_log_error('Error installing azureotelcollector "{0}"'.format(output))

    return False


def get_otelcollector_installation_command():
    """
    This method provides the installation command to install an azureotelcollector package as a systemd service
    """
    find_package_manager("Install")
    dir_path = os.getcwd() + "/azureotelcollector/"
    if PackageManager == "dpkg":
        package_path = find_otelcollector_package_file(dir_path, "deb")
    elif PackageManager == "rpm":
        package_path = find_otelcollector_package_file(dir_path, "rpm")
    else:
        raise Exception("Unsupported package manager to install azureotelcollector: {0}.".format(PackageManager))

    return "{0} {1} --install {2}".format(PackageManager, PackageManagerOptions, package_path)


def find_otelcollector_package_file(directory, pkg_type):
    """
    Finds the otelcollector package in a given path for a given package type using name globbing.
    """
    arch = platform.machine()

    # Create pattern based on type and arch
    if pkg_type == "deb":
        if arch == "x86_64":
            pattern = "azureotelcollector_*_amd64.deb"
        elif arch == "aarch64":
            pattern = "azureotelcollector_*_arm64.deb"
        else:
            raise Exception("Unsupported architecture for deb package: {0}".format(arch))
    elif pkg_type == "rpm":
        pattern = "azureotelcollector-*{0}.rpm".format(arch)
    else:
        raise Exception("Unsupported package type to install azureotelcollector: {0}".format(pkg_type))

    search_pattern = os.path.join(directory, pattern)
    matches = glob.glob(search_pattern)

    if not matches:
        raise IOError("No {0} package found for arch '{1}' in {2} with pattern '{3}'".format(pkg_type, arch, directory, pattern))

    # Return the most recently modified match
    return max(matches, key=os.path.getmtime)


def uninstall_azureotelcollector():
    """
    This method will uninstall azureotelcollector services.
    No need to stop it separately as the package maintainer script handles it upon uninstalling.
    """
    if is_feature_enabled("enableAzureOTelCollector"):
        # Only remove azureotelcollector if file exists
        if os.path.exists("/lib/systemd/system/azureotelcollector-watcher.path"):
            azureotelcollector_uninstall_command = ""
            find_package_manager("Uninstall")

            if PackageManager == "dpkg":
                azureotelcollector_uninstall_command = "dpkg --purge azureotelcollector"
            elif PackageManager == "rpm":
                azureotelcollector_uninstall_command = "rpm --erase azureotelcollector"
            else:
                log_and_exit("Uninstall", UnsupportedOperatingSystem, "The OS has neither rpm nor dpkg" )

            hutil_log_info('Running command "{0}"'.format(azureotelcollector_uninstall_command))

            exit_code, output = run_command_with_retries_output(
                azureotelcollector_uninstall_command,
                retries = 5,
                retry_check = retry_if_dpkg_or_rpm_locked,
                final_check = final_check_if_dpkg_or_rpm_locked
            )

            if exit_code == 0:
                hutil_log_info('Successfully removed azureotelcollector')
            else:
                hutil_log_error('Error removing azureotelcollector "{0}"'.format(output))


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

def stop_syslogconfig_process():
    
    pids_filepath = os.path.join(os.getcwd(),'amasyslogconfig.pid')

    # kill existing syslog config watcher
    if os.path.exists(pids_filepath):
        with open(pids_filepath, "r") as f:
            for pid in f.readlines():
                # Verify the pid actually belongs to AMA syslog watcher.
                cmd_file = os.path.join("/proc", str(pid.strip("\n")), "cmdline")
                if os.path.exists(cmd_file):
                    with open(cmd_file, "r") as pidf:
                        cmdline = pidf.readlines()
                        if len(cmdline) > 0 and cmdline[0].find("agent.py") >= 0 and cmdline[0].find("-syslogconfig") >= 0:
                            kill_cmd = "kill " + pid
                            run_command_and_log(kill_cmd)

        run_command_and_log("rm "+ pids_filepath)

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

def is_syslogconfig_process_running():
    pids_filepath = os.path.join(os.getcwd(),'amasyslogconfig.pid')
    if os.path.exists(pids_filepath):
        with open(pids_filepath, "r") as f:
            for pid in f.readlines():
                # Verify the pid actually belongs to AMA syslog watcher.
                cmd_file = os.path.join("/proc", str(pid.strip("\n")), "cmdline")
                if os.path.exists(cmd_file):
                    with open(cmd_file, "r") as pidf:
                        cmdline = pidf.readlines()
                        if len(cmdline) > 0 and cmdline[0].find("agent.py") >= 0 and cmdline[0].find("-syslogconfig") >= 0:
                            return True

    return False

def is_transformconfig_process_running():
    pids_filepath = os.path.join(os.getcwd(),'amatransformconfig.pid')
    if os.path.exists(pids_filepath):
        with open(pids_filepath, "r") as f:
            for pid in f.readlines():
                # Verify the pid actually belongs to AMA transform config watcher.
                cmd_file = os.path.join("/proc", str(pid.strip("\n")), "cmdline")
                if os.path.exists(cmd_file):
                    with open(cmd_file, "r") as pidf:
                        cmdline = pidf.readlines()
                        if len(cmdline) > 0 and cmdline[0].find("agent.py") >= 0 and cmdline[0].find("-transformconfig") >= 0:
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

def start_syslogconfig_process():
    """
    Start syslog check process that performs periodic DCR monitoring activities and looks for syslog config changes
    :return: None
    """

    # test
    if not is_syslogconfig_process_running():
        stop_syslogconfig_process()

        # Start syslog config watcher
        ama_path = os.path.join(os.getcwd(), 'agent.py')
        args = [sys.executable, ama_path, '-syslogconfig']
        log = open(os.path.join(os.getcwd(), 'daemon.log'), 'w')
        hutil_log_info('start syslog watcher process '+str(args))
        subprocess.Popen(args, stdout=log, stderr=log)

def start_transformconfig_process():
    """
    Start agent transform check process that performs periodic DCR monitoring activities and looks for agent transformation config changes
    :return: None
    """

    # test
    if not is_transformconfig_process_running():
        stop_transformconfig_process()

        # Start agent transform config watcher
        ama_path = os.path.join(os.getcwd(), 'agent.py')
        args = [sys.executable, ama_path, '-transformconfig']
        log = open(os.path.join(os.getcwd(), 'daemon.log'), 'w')
        hutil_log_info('start agent transform config watcher process '+str(args))
        subprocess.Popen(args, stdout=log, stderr=log)

def stop_transformconfig_process():

    pids_filepath = os.path.join(os.getcwd(),'amatransformconfig.pid')

    # kill existing agent transform config watcher
    if os.path.exists(pids_filepath):
        with open(pids_filepath, "r") as f:
            for pid in f.readlines():
                # Verify the pid actually belongs to AMA tranform config watcher.
                cmd_file = os.path.join("/proc", str(pid.strip("\n")), "cmdline")
                if os.path.exists(cmd_file):
                    with open(cmd_file, "r") as pidf:
                        cmdline = pidf.readlines()
                        if len(cmdline) > 0 and cmdline[0].find("agent.py") >= 0 and cmdline[0].find("-transformconfig") >= 0:
                            kill_cmd = "kill " + pid
                            run_command_and_log(kill_cmd)

        run_command_and_log("rm "+ pids_filepath)

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
    if identifier_name and identifier_value:
        managed_identity_str = "uai#{0}#{1}".format(identifier_name, identifier_value)
    else:
        managed_identity_str = "sai"

    # Sleep before starting the monitoring
    time.sleep(sleepTime)
    last_crc = None
    last_crc_fluent = None
    me_msi_token_expiry_epoch = None
    enabled_me_CMv2_mode = False
    log_messages = ""

    while True:
        try:
            if not me_handler.is_running(is_lad=False):
                me_service_template_path = os.getcwd() + "/services/metrics-extension.service"

                try:
                    if is_feature_enabled("enableAzureOTelCollector") and azureotelcollector_is_active():
                        if os.path.exists(me_service_template_path):
                            os.remove(me_service_template_path)
                        copyfile(os.getcwd() + "/services/metrics-extension-cmv2.service", me_service_template_path)
                        me_handler.setup_me(
                            is_lad=False,
                            managed_identity=managed_identity_str,
                            HUtilObj=HUtilObject,
                            is_local_control_channel=False,
                            user="azuremetricsext",
                            group="azuremonitoragent")
                        enabled_me_CMv2_mode, log_messages = me_handler.start_metrics_cmv2()
                    elif is_feature_enabled("enableCMV2"):
                        if os.path.exists(me_service_template_path):
                            os.remove(me_service_template_path)
                        copyfile(os.getcwd() + "/services/metrics-extension-otlp.service", me_service_template_path)
                        me_handler.setup_me(
                            is_lad=False,
                            managed_identity=managed_identity_str,
                            HUtilObj=HUtilObject,
                            is_local_control_channel=False)
                        enabled_me_CMv2_mode, log_messages = me_handler.start_metrics_cmv2()
                except Exception as e:
                    hutil_log_error("Error in setting up metrics-extension.service in CMv2 mode. Exception={0}".format(e))

                if enabled_me_CMv2_mode:
                    hutil_log_info("Successfully started metrics-extension.")
                elif log_messages:
                    hutil_log_error(log_messages)

            # update fluent config for fluent port if needed
            fluent_port = ''
            if os.path.isfile(AMAFluentPortFilePath):
                f = open(AMAFluentPortFilePath, "r")
                fluent_port = f.read()
                f.close()
            
            if fluent_port != '' and os.path.isfile(FluentCfgPath):
                portSetting = "    Port                       "  + fluent_port + "\n"
                defaultPortSetting = 'Port'
                portUpdated = True                
                with open(FluentCfgPath, 'r') as f:                    
                    for line in f:                        
                        found = re.search(r'^\s{0,}Port\s{1,}' + fluent_port + '$', line)
                        if found:
                            portUpdated = False

                if portUpdated == True:
                    with contextlib.closing(fileinput.FileInput(FluentCfgPath, inplace=True, backup='.bak')) as file:
                        for line in file:
                            if defaultPortSetting in line:
                                print(portSetting, end='')
                            else:
                                print(line, end='')
                    os.chmod(FluentCfgPath, stat.S_IRGRP | stat.S_IRUSR | stat.S_IWUSR | stat.S_IROTH)

                    # add SELinux rules if needed
                    if os.path.exists('/etc/selinux/config') and fluent_port != '':
                        sedisabled, _ = run_command_and_log('getenforce | grep -i "Disabled"',log_cmd=False, log_output=False)
                        if sedisabled != 0:                        
                            check_semanage, _ = run_command_and_log("which semanage",log_cmd=False, log_output=False)
                            if check_semanage == 0:
                                fluentPortEnabled, _ = run_command_and_log('grep -Rnw /var/lib/selinux -e http_port_t | grep ' + fluent_port,log_cmd=False, log_output=False)
                                if fluentPortEnabled != 0:                    
                                    # also check SELinux config paths for Oracle/RH
                                    fluentPortEnabled, _ = run_command_and_log('grep -Rnw /etc/selinux -e http_port_t | grep ' + fluent_port,log_cmd=False, log_output=False)
                                    if fluentPortEnabled != 0:                    
                                        # allow the fluent port in SELinux
                                        run_command_and_log('semanage port -a -t http_port_t -p tcp ' + fluent_port,log_cmd=False, log_output=False)

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

                        if not enabled_me_CMv2_mode and me_handler.is_running(is_lad=False):
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
                                "unix:///run/azuremonitoragent/mdm_influxdb.socket",
                                "unix:///run/azuremonitoragent/default_influx.socket",
                                is_lad=False)

                            start_telegraf_res, log_messages = telhandler.start_telegraf(is_lad=False)
                            if start_telegraf_res:
                                hutil_log("Successfully started metrics-sourcer.")
                            else:
                                hutil_error(log_messages)

                            if not enabled_me_CMv2_mode:
                                me_service_template_path = os.getcwd() + "/services/metrics-extension.service"
                                if os.path.exists(me_service_template_path):
                                    os.remove(me_service_template_path)

                                copyfile(os.getcwd() + "/services/metrics-extension-cmv1.service", me_service_template_path)
                                me_handler.setup_me(is_lad=False, managed_identity=managed_identity_str, HUtilObj=HUtilObject)

                                start_metrics_out, log_messages = me_handler.start_metrics(is_lad=False, managed_identity=managed_identity_str)
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
                            msi_token_generated, me_msi_token_expiry_epoch, log_messages = me_handler.generate_MSI_token(identifier_name, identifier_value, is_lad=False)
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
                                start_metrics_out, log_messages = me_handler.start_metrics(is_lad=False, managed_identity=managed_identity_str)

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

def syslogconfig_watcher(hutil_error, hutil_log):
    """
    Watcher thread to monitor syslog configuration changes and to take action on them
    """
    syslog_enabled  = False
    # Check for config changes every 30 seconds
    sleepTime =  30

    # Sleep before starting the monitoring
    time.sleep(sleepTime)

    GcsEnabled, McsEnabled = get_control_plane_mode()
        
    while True:
        try:       
            if os.path.isfile(AMASyslogConfigMarkerPath):
                f = open(AMASyslogConfigMarkerPath, "r")
                data = f.read()

                if (data != ''):
                    if "true" in data:
                        syslog_enabled = True
                f.close()
            elif GcsEnabled:
                # 1P Syslog is always enabled as each tenant could be having different mdsd.xml configuration
                syslog_enabled = True

            if syslog_enabled:
                # place syslog local configs
                syslog_enabled  = False
                generate_localsyslog_configs(uses_gcs=GcsEnabled, uses_mcs=McsEnabled)
            else:
                # remove syslog local configs
                remove_localsyslog_configs()

        except IOError as e:
            hutil_error('I/O error in setting up syslog config watcher. Exception={0}'.format(e))

        except Exception as e:
            hutil_error('Error in setting up syslog config watcher. Exception={0}'.format(e))

        finally:
            time.sleep(sleepTime)

def transformconfig_watcher(hutil_error, hutil_log):
    """
    Watcher thread to monitor agent transformation configuration changes and to take action on them
    """
    # Check for config changes every 30 seconds
    sleepTime =  30

    # Sleep before starting the monitoring
    time.sleep(sleepTime)
    last_crc = None

    while True:
        try:
            if os.path.isfile(AMAAstTransformConfigMarkerPath):
                f = open(AMAAstTransformConfigMarkerPath, "r")
                data = f.read()
                if (data != ''):
                    crc = hashlib.sha256(data.encode('utf-8')).hexdigest()

                    if (crc != last_crc):
                        restart_kqlextension()
                        last_crc = crc
                f.close()

        except IOError as e:
            hutil_error('I/O error in setting up agent transform config watcher. Exception={0}'.format(e))

        except Exception as e:
            hutil_error('Error in setting up agent transform config watcher. Exception={0}'.format(e))

        finally:
            time.sleep(sleepTime)

def generate_localsyslog_configs(uses_gcs = False, uses_mcs = False):
    """
    Install local syslog configuration files if not present and restart syslog
    """

    # don't deploy any configuration if no control plane is configured
    if not uses_gcs and not uses_mcs:
        return
    
    public_settings, _ = get_settings()
    syslog_port = ''
    if os.path.isfile(AMASyslogPortFilePath):
        f = open(AMASyslogPortFilePath, "r")
        syslog_port = f.read()
        f.close()
        
    useSyslogTcp = False
    
    # always use syslog tcp port, unless 
    # - the distro is Red Hat based and doesn't have semanage
    #   these distros seem to have SELinux on by default and we shouldn't be installing semanage ourselves
    if not os.path.exists('/etc/selinux/config'):
        useSyslogTcp = True
    else:        
        sedisabled, _ = run_command_and_log('getenforce | grep -i "Disabled"',log_cmd=False, log_output=False)
        if sedisabled == 0:
            useSyslogTcp = True
        else:            
            check_semanage, _ = run_command_and_log("which semanage",log_cmd=False, log_output=False)
            if check_semanage == 0 and syslog_port != '':
                syslogPortEnabled, _ = run_command_and_log('grep -Rnw /var/lib/selinux -e syslogd_port_t | grep ' + syslog_port,log_cmd=False, log_output=False)
                if syslogPortEnabled != 0:                    
                    # also check SELinux config paths for Oracle/RH
                    syslogPortEnabled, _ = run_command_and_log('grep -Rnw /etc/selinux -e syslogd_port_t | grep ' + syslog_port,log_cmd=False, log_output=False)
                    if syslogPortEnabled != 0:                    
                        # allow the syslog port in SELinux
                        run_command_and_log('semanage port -a -t syslogd_port_t -p tcp ' + syslog_port,log_cmd=False, log_output=False)
                useSyslogTcp = True   
        
    # 1P tenants use omuxsock, so keep using that for customers using 1P
    if useSyslogTcp == True and syslog_port != '':
        if os.path.exists('/etc/rsyslog.d/'):            
            restartRequired = False
            if uses_gcs and not os.path.exists('/etc/rsyslog.d/05-azuremonitoragent-loadomuxsock.conf'):
                copyfile("/etc/opt/microsoft/azuremonitoragent/syslog/rsyslogconf/05-azuremonitoragent-loadomuxsock.conf","/etc/rsyslog.d/05-azuremonitoragent-loadomuxsock.conf")
                restartRequired = True
            
            if not os.path.exists('/etc/rsyslog.d/10-azuremonitoragent-omfwd.conf'):
                if os.path.exists('/etc/rsyslog.d/05-azuremonitoragent-loadomuxsock.conf'):
                    os.remove("/etc/rsyslog.d/05-azuremonitoragent-loadomuxsock.conf")
                if os.path.exists('/etc/rsyslog.d/10-azuremonitoragent.conf'):
                    os.remove("/etc/rsyslog.d/10-azuremonitoragent.conf")
                copyfile("/etc/opt/microsoft/azuremonitoragent/syslog/rsyslogconf/10-azuremonitoragent-omfwd.conf","/etc/rsyslog.d/10-azuremonitoragent-omfwd.conf")
                os.chmod('/etc/rsyslog.d/10-azuremonitoragent-omfwd.conf', stat.S_IRGRP | stat.S_IRUSR | stat.S_IWUSR | stat.S_IROTH)
                restartRequired = True                
            
            portSetting = 'Port="' + syslog_port + '"'
            defaultPortSetting = 'Port="28330"'
            portUpdated = False
            with open('/etc/rsyslog.d/10-azuremonitoragent-omfwd.conf') as f:
                if portSetting not in f.read():
                    portUpdated = True

            if portUpdated == True:
                copyfile("/etc/opt/microsoft/azuremonitoragent/syslog/rsyslogconf/10-azuremonitoragent-omfwd.conf","/etc/rsyslog.d/10-azuremonitoragent-omfwd.conf")
                with contextlib.closing(fileinput.FileInput('/etc/rsyslog.d/10-azuremonitoragent-omfwd.conf', inplace=True, backup='.bak')) as file:
                    for line in file:
                        print(line.replace(defaultPortSetting, portSetting), end='')
                os.chmod('/etc/rsyslog.d/10-azuremonitoragent-omfwd.conf', stat.S_IRGRP | stat.S_IRUSR | stat.S_IWUSR | stat.S_IROTH)
                restartRequired = True
            
            if restartRequired == True:
                run_command_and_log(get_service_command("rsyslog", "restart"))
                hutil_log_info("Installed local syslog configuration files and restarted syslog")

        if os.path.exists('/etc/syslog-ng/syslog-ng.conf'):
            restartRequired = False
            if not os.path.exists('/etc/syslog-ng/conf.d/azuremonitoragent-tcp.conf'):
                if os.path.exists('/etc/syslog-ng/conf.d/azuremonitoragent.conf'):
                    os.remove("/etc/syslog-ng/conf.d/azuremonitoragent.conf")
                syslog_ng_confpath = os.path.join('/etc/syslog-ng/', 'conf.d')
                if not os.path.exists(syslog_ng_confpath):
                    os.makedirs(syslog_ng_confpath)
                copyfile("/etc/opt/microsoft/azuremonitoragent/syslog/syslog-ngconf/azuremonitoragent-tcp.conf","/etc/syslog-ng/conf.d/azuremonitoragent-tcp.conf")
                os.chmod('/etc/syslog-ng/conf.d/azuremonitoragent-tcp.conf', stat.S_IRGRP | stat.S_IRUSR | stat.S_IWUSR | stat.S_IROTH)
                restartRequired = True

            portSetting = "port(" + syslog_port + ")"
            defaultPortSetting = "port(28330)"
            portUpdated = False
            with open('/etc/syslog-ng/conf.d/azuremonitoragent-tcp.conf') as f:
                if portSetting not in f.read():
                    portUpdated = True

            if portUpdated == True:
                copyfile("/etc/opt/microsoft/azuremonitoragent/syslog/syslog-ngconf/azuremonitoragent-tcp.conf","/etc/syslog-ng/conf.d/azuremonitoragent-tcp.conf")
                with contextlib.closing(fileinput.FileInput('/etc/syslog-ng/conf.d/azuremonitoragent-tcp.conf', inplace=True, backup='.bak')) as file:
                    for line in file:
                        print(line.replace(defaultPortSetting, portSetting), end='')
                os.chmod('/etc/syslog-ng/conf.d/azuremonitoragent-tcp.conf', stat.S_IRGRP | stat.S_IRUSR | stat.S_IWUSR | stat.S_IROTH)
                restartRequired = True
            
            if restartRequired == True:
                run_command_and_log(get_service_command("syslog-ng", "restart"))
                hutil_log_info("Installed local syslog configuration files and restarted syslog")    
    else:
        if os.path.exists('/etc/rsyslog.d/') and not os.path.exists('/etc/rsyslog.d/10-azuremonitoragent.conf'):
            if os.path.exists('/etc/rsyslog.d/10-azuremonitoragent-omfwd.conf'):
                os.remove("/etc/rsyslog.d/10-azuremonitoragent-omfwd.conf")
            copyfile("/etc/opt/microsoft/azuremonitoragent/syslog/rsyslogconf/05-azuremonitoragent-loadomuxsock.conf","/etc/rsyslog.d/05-azuremonitoragent-loadomuxsock.conf")
            copyfile("/etc/opt/microsoft/azuremonitoragent/syslog/rsyslogconf/10-azuremonitoragent.conf","/etc/rsyslog.d/10-azuremonitoragent.conf")
            os.chmod('/etc/rsyslog.d/05-azuremonitoragent-loadomuxsock.conf', stat.S_IRGRP | stat.S_IRUSR | stat.S_IWUSR | stat.S_IROTH)
            os.chmod('/etc/rsyslog.d/10-azuremonitoragent.conf', stat.S_IRGRP | stat.S_IRUSR | stat.S_IWUSR | stat.S_IROTH)
            run_command_and_log(get_service_command("rsyslog", "restart"))
            hutil_log_info("Installed local syslog configuration files and restarted syslog")

        if os.path.exists('/etc/syslog-ng/syslog-ng.conf') and not os.path.exists('/etc/syslog-ng/conf.d/azuremonitoragent.conf'):
            if os.path.exists('/etc/syslog-ng/conf.d/azuremonitoragent-tcp.conf'):
                os.remove("/etc/syslog-ng/conf.d/azuremonitoragent-tcp.conf")
            syslog_ng_confpath = os.path.join('/etc/syslog-ng/', 'conf.d')
            if not os.path.exists(syslog_ng_confpath):
                os.makedirs(syslog_ng_confpath)
            copyfile("/etc/opt/microsoft/azuremonitoragent/syslog/syslog-ngconf/azuremonitoragent.conf","/etc/syslog-ng/conf.d/azuremonitoragent.conf")
            os.chmod('/etc/syslog-ng/conf.d/azuremonitoragent.conf', stat.S_IRGRP | stat.S_IRUSR | stat.S_IWUSR | stat.S_IROTH)
            run_command_and_log(get_service_command("syslog-ng", "restart"))
            hutil_log_info("Installed local syslog configuration files and restarted syslog")

def remove_localsyslog_configs():
    """
    Remove local syslog configuration files if present and restart syslog
    """    
    if os.path.exists('/etc/rsyslog.d/10-azuremonitoragent.conf') or os.path.exists('/etc/rsyslog.d/10-azuremonitoragent-omfwd.conf'):
        if os.path.exists('/etc/rsyslog.d/10-azuremonitoragent-omfwd.conf'):
            os.remove("/etc/rsyslog.d/10-azuremonitoragent-omfwd.conf")
        if os.path.exists('/etc/rsyslog.d/05-azuremonitoragent-loadomuxsock.conf'):
            os.remove("/etc/rsyslog.d/05-azuremonitoragent-loadomuxsock.conf")
        if os.path.exists('/etc/rsyslog.d/10-azuremonitoragent.conf'):            
            os.remove("/etc/rsyslog.d/10-azuremonitoragent.conf")
        run_command_and_log(get_service_command("rsyslog", "restart"))
        hutil_log_info("Removed local syslog configuration files if found and restarted syslog")

    if os.path.exists('/etc/syslog-ng/conf.d/azuremonitoragent.conf') or os.path.exists('/etc/syslog-ng/conf.d/azuremonitoragent-tcp.conf'):
        if os.path.exists('/etc/syslog-ng/conf.d/azuremonitoragent-tcp.conf'):
            os.remove("/etc/syslog-ng/conf.d/azuremonitoragent-tcp.conf")
        if os.path.exists('/etc/syslog-ng/conf.d/azuremonitoragent.conf'):
            os.remove("/etc/syslog-ng/conf.d/azuremonitoragent.conf")
        run_command_and_log(get_service_command("syslog-ng", "restart"))
        hutil_log_info("Removed local syslog configuration files if found and restarted syslog")

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

def syslogconfig():
    """
    Take care of setting up syslog configuration change watcher
    """
    pids_filepath = os.path.join(os.getcwd(), 'amasyslogconfig.pid')
    py_pid = os.getpid()
    with open(pids_filepath, 'w') as f:
        f.write(str(py_pid) + '\n')

    watcher_thread = Thread(target = syslogconfig_watcher, args = [hutil_log_error, hutil_log_info])
    watcher_thread.start()
    watcher_thread.join()

    return 0, ""

def transformconfig():
    """
    Take care of setting up agent transformation configuration change watcher
    """
    pids_filepath = os.path.join(os.getcwd(), 'amatransformconfig.pid')
    py_pid = os.getpid()
    with open(pids_filepath, 'w') as f:
        f.write(str(py_pid) + '\n')

    watcher_thread = Thread(target = transformconfig_watcher, args = [hutil_log_error, hutil_log_info])
    watcher_thread.start()
    watcher_thread.join()

    return 0, ""

# Dictionary of operations strings to methods
operations = {'Disable' : disable,
              'Uninstall' : uninstall,
              'Install' : install,
              'Enable' : enable,
              'Update' : update,
              'Metrics' : metrics,
              'Syslogconfig' : syslogconfig,
              'Transformconfig' : transformconfig
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

            # As per VM extension team, we have to manage rotation for our extension.log
            # for now, this is our extension code, but to be moved to HUtil library.
            if os.path.exists(WAGuestAgentLogRotateFilePath):      
                if os.path.exists(AMAExtensionLogRotateFilePath):
                    try:
                        os.remove(AMAExtensionLogRotateFilePath)
                    except Exception as ex:
                        output = 'Logrotate removal failed with error: {0}\nStacktrace: {1}'.format(ex, traceback.format_exc())
                        hutil_log_info(output)
            else:
                if not os.path.exists(AMAExtensionLogRotateFilePath):      
                    logrotateFilePath = os.path.join(os.getcwd(), 'azuremonitoragentextension.logrotate')
                    copyfile(logrotateFilePath,AMAExtensionLogRotateFilePath)
            
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
    

def find_package_manager(operation):
    """
    Checks if the dist is debian based or centos based and assigns the package manager accordingly
    """
    global PackageManager, PackageManagerOptions, BundleFileName
    dist, _ = find_vm_distro(operation)

    dpkg_set = set(["debian", "ubuntu"])
    rpm_set = set(["oracle", "ol", "redhat", "centos", "red hat", "suse", "sles", "opensuse", "cbl-mariner", "mariner", "azurelinux", "rhel", "rocky", "alma", "amzn"])
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
    Finds the Linux Distribution this VM is running on by directly parsing
    distribution-specific files for reliable detection.
    """
    vm_dist = vm_ver = ""
    detection_files_checked = []
    
    # Try to read from /etc/os-release first (most modern distributions)
    if os.path.exists('/etc/os-release'):
        detection_files_checked.append('/etc/os-release')
        try:
            with open('/etc/os-release', 'r') as fp:
                os_release = {}
                for line in fp:
                    if line.strip() and '=' in line:
                        k, v = line.strip().split('=', 1)
                        os_release[k] = v.strip('"\'').strip()
                
                if 'ID' in os_release:
                    vm_dist = os_release['ID'].lower()
                    # Clean up the ID by removing any vendor-specific suffixes
                    vm_dist = vm_dist.split('-')[0]
                
                if 'VERSION_ID' in os_release:
                    vm_ver = os_release['VERSION_ID'].lower()
                
                # Fallback for ID_LIKE if direct ID isn't recognized
                if not vm_dist and 'ID_LIKE' in os_release:
                    # Get first value from ID_LIKE
                    vm_dist = os_release['ID_LIKE'].lower().split()[0].strip('"\'')
                    vm_dist = vm_dist.split('-')[0]
                
                hutil_log_info("OS detected from /etc/os-release: {0} {1}".format(vm_dist, vm_ver))
        except Exception as e:
            hutil_log_error("Error reading /etc/os-release: {0}".format(str(e)))
    
    # If we couldn't get the distribution from /etc/os-release, try other files
    if not vm_dist or not vm_ver:
        # Try /etc/system-release first (used by Amazon Linux and others)
        if os.path.exists('/etc/system-release'):
            detection_files_checked.append('/etc/system-release')
            try:
                with open('/etc/system-release', 'r') as fp:
                    content = fp.read().lower()
                    if 'amazon' in content:
                        vm_dist = 'amzn'
                        # Try to extract version
                        version_match = re.search(r'release\s+(\d+(\.\d+)?)', content)
                        if version_match:
                            vm_ver = version_match.group(1)
                        hutil_log_info("OS detected from /etc/system-release: {0} {1}".format(vm_dist, vm_ver))
            except Exception as e:
                hutil_log_error("Error reading /etc/system-release: {0}".format(str(e)))
        
        # SUSE specific detection
        if not vm_dist and os.path.exists('/etc/SuSE-release'):
            detection_files_checked.append('/etc/SuSE-release')
            try:
                with open('/etc/SuSE-release', 'r') as fp:
                    content = fp.read()
                    if 'SUSE Linux Enterprise Server' in content:
                        vm_dist = 'sles'
                    elif 'openSUSE' in content:
                        vm_dist = 'opensuse'
                    else:
                        vm_dist = 'suse'
                    
                    # Try to extract the version
                    version_match = re.search(r'VERSION\s*=\s*(\d+)', content)
                    if version_match:
                        vm_ver = version_match.group(1)
                    
                    # Also look for service pack level
                    sp_match = re.search(r'PATCHLEVEL\s*=\s*(\d+)', content)
                    if sp_match and vm_ver:
                        vm_ver = '{0}.{1}'.format(vm_ver, sp_match.group(1))
                    
                    hutil_log_info("OS detected from /etc/SuSE-release: {0} {1}".format(vm_dist, vm_ver))
            except Exception as e:
                hutil_log_error("Error reading /etc/SuSE-release: {0}".format(str(e)))
        
        # Red Hat based systems
        if not vm_dist and os.path.exists('/etc/redhat-release'):
            detection_files_checked.append('/etc/redhat-release')
            try:
                with open('/etc/redhat-release', 'r') as fp:
                    content = fp.read().lower()
                    if 'red hat' in content:
                        vm_dist = 'redhat'
                    elif 'centos' in content:
                        vm_dist = 'centos'
                    elif 'oracle' in content:
                        vm_dist = 'oracle'
                    elif 'fedora' in content:
                        vm_dist = 'fedora'
                    elif 'rocky' in content:
                        vm_dist = 'rocky'
                    elif 'alma' in content:
                        vm_dist = 'alma'
                    else:
                        vm_dist = 'redhat'  # Default to redhat for RHEL-based systems
                    
                    # Try to extract version using a more flexible pattern
                    # This handles formats like "release 8.6" or "release 7.9.2009"
                    version_match = re.search(r'release\s+(\d+(\.\d+){0,2})', content)
                    if version_match:
                        vm_ver = version_match.group(1)
                    
                    hutil_log_info("OS detected from /etc/redhat-release: {0} {1}".format(vm_dist, vm_ver))
            except Exception as e:
                hutil_log_error("Error reading /etc/redhat-release: {0}".format(str(e)))
        
        # Debian based systems with lsb-release
        if not vm_dist and os.path.exists('/etc/lsb-release'):
            detection_files_checked.append('/etc/lsb-release')
            try:
                lsb_data = {}
                with open('/etc/lsb-release', 'r') as fp:
                    for line in fp:
                        if line.strip() and '=' in line:
                            k, v = line.strip().split('=', 1)
                            lsb_data[k] = v.strip('"\'')
                
                if 'DISTRIB_ID' in lsb_data:
                    vm_dist = lsb_data['DISTRIB_ID'].lower()
                if 'DISTRIB_RELEASE' in lsb_data:
                    vm_ver = lsb_data['DISTRIB_RELEASE'].lower()
                
                hutil_log_info("OS detected from /etc/lsb-release: {0} {1}".format(vm_dist, vm_ver))
            except Exception as e:
                hutil_log_error("Error reading /etc/lsb-release: {0}".format(str(e)))
        
        # Debian specific detection
        if not vm_dist and os.path.exists('/etc/debian_version'):
            detection_files_checked.append('/etc/debian_version')
            try:
                with open('/etc/debian_version', 'r') as fp:
                    vm_ver = fp.read().strip()
                vm_dist = 'debian'
                hutil_log_info("OS detected from /etc/debian_version: {0} {1}".format(vm_dist, vm_ver))
            except Exception as e:
                hutil_log_error("Error reading /etc/debian_version: {0}".format(str(e)))
    
    # Final fallback - try /proc/version
    if not vm_dist and os.path.exists('/proc/version'):
        detection_files_checked.append('/proc/version')
        try:
            with open('/proc/version', 'r') as fp:
                content = fp.read().lower()
                if 'debian' in content:
                    vm_dist = 'debian'
                elif 'ubuntu' in content:
                    vm_dist = 'ubuntu'
                elif 'red hat' in content or 'redhat' in content:
                    vm_dist = 'redhat'
                elif 'suse' in content:
                    vm_dist = 'suse'
                
                # Try to extract version - not always reliable from /proc/version
                hutil_log_info("OS detected from /proc/version: {0}".format(vm_dist))
        except Exception as e:
            hutil_log_error("Error reading /proc/version: {0}".format(str(e)))
    
    # If we still couldn't determine the OS, log what we tried and throw an error
    if not vm_dist:
        error_msg = 'Indeterminate operating system. Files checked: {0}'.format(", ".join(detection_files_checked))
        log_and_exit(operation, IndeterminateOperatingSystem, error_msg)
    
    # Normalize distribution names
    if vm_dist == 'rhel':
        vm_dist = 'redhat'
    elif vm_dist == 'ol':
        vm_dist = 'oracle'

    if vm_ver and '.' in vm_ver and vm_dist != 'ubuntu':
        # For Ubuntu, keep major.minor format (e.g., "18.04")
        # For other distributions, extract only the major version
        # This is needed for matching with supported_distros.py
        vm_ver = vm_ver.split('.')[0]
    
    # Add debugging info
    hutil_log_info("Final OS detection result: {0} {1}".format(vm_dist.lower(), vm_ver.lower()))
    
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

    if platform.machine() == 'aarch64':
        supported_dists = supported_distros.supported_dists_aarch64
    else:
        supported_dists = supported_distros.supported_dists_x86_64

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

def is_feature_enabled(feature):
    """
    Checks if the feature is enabled in the current region
    """
    feature_support_matrix = {
        'useDynamicSSL'             : ['all'],
        'enableCMV2'                : ['all'],
        'enableAzureOTelCollector'  : ['all']
    }
    
    featurePreviewFlagPath = PreviewFeaturesDirectory + feature
    if os.path.exists(featurePreviewFlagPath):
        return True
    
    featurePreviewDisabledFlagPath = PreviewFeaturesDirectory + feature + 'Disabled'
    if os.path.exists(featurePreviewDisabledFlagPath):
        return False
    
    _, region = get_azure_environment_and_region()

    if feature in feature_support_matrix.keys():
        if region in feature_support_matrix[feature] or "all" in feature_support_matrix[feature]:
            return True
    
    return False


def get_ssl_cert_info(operation):
    """
    Get the appropriate SSL_CERT_DIR / SSL_CERT_FILE based on the Linux distro
    """
    name = value = None

    distro, version = find_vm_distro(operation)

    for name in ['ubuntu', 'debian']:
        if distro.startswith(name):
            return 'SSL_CERT_DIR', '/etc/ssl/certs'

    for name in ['centos', 'redhat', 'red hat', 'oracle', 'ol', 'cbl-mariner', 'mariner', 'azurelinux', 'rhel', 'rocky', 'alma', 'amzn']:
        if distro.startswith(name):
            return 'SSL_CERT_FILE', '/etc/pki/tls/certs/ca-bundle.crt'

    for name in ['suse', 'sles', 'opensuse']:
        if distro.startswith(name):
            if version.startswith('12'):
                return 'SSL_CERT_DIR', '/var/lib/ca-certificates/openssl'
            elif version.startswith('15'):
                return 'SSL_CERT_DIR', '/etc/ssl/certs'

    log_and_exit(operation, GenericErrorCode, 'Unable to determine values for SSL_CERT_DIR or SSL_CERT_FILE')

def copy_kqlextension_binaries():
    kqlextension_bin_local_path = os.getcwd() + "/KqlExtensionBin/"
    kqlextension_bin = "/opt/microsoft/azuremonitoragent/bin/kqlextension/"
    kqlextension_runtimesbin = "/opt/microsoft/azuremonitoragent/bin/kqlextension/runtimes/"
    if os.path.exists(kqlextension_runtimesbin):
        # only for versions of AMA with .NET runtimes
        rmtree(kqlextension_runtimesbin)
    # only for versions with Kql .net cleanup .NET files as it is causing issues with AOT runtime
    for f in os.listdir(kqlextension_bin):
        if f != 'KqlExtension' and f != 'appsettings.json':
            os.remove(os.path.join(kqlextension_bin, f))

    for f in os.listdir(kqlextension_bin_local_path):
        compare_and_copy_bin(kqlextension_bin_local_path + f, kqlextension_bin + f)


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
    req = urllib.Request(imds_endpoint)
    req.add_header('Metadata', 'True')

    environment = region = None

    try:
        response = json.loads(urllib.urlopen(req).read().decode('utf-8', 'ignore'))

        if ('compute' in response):
            if ('azEnvironment' in response['compute']):
                environment = response['compute']['azEnvironment'].lower()
            if ('location' in response['compute']):
                region = response['compute']['location'].lower()
    except urlerror.HTTPError as e:
        hutil_log_error('Request to Metadata service URL failed with an HTTPError: {0}'.format(e))
        hutil_log_error('Response from Metadata service: {0}'.format(e.read()))
    except Exception as e:
        hutil_log_error('Unexpected error from Metadata service: {0}'.format(e))

    hutil_log_info('Detected environment: {0}, region: {1}'.format(environment, region))

    return environment, region


def run_command_and_log(cmd, check_error = True, log_cmd = True, log_output = True):
    """
    Run the provided shell command and log its output, including stdout and
    stderr.
    The output should not contain any PII, but the command might. In this case,
    log_cmd should be set to False.
    """
    exit_code, output = run_get_output(cmd, check_error, log_cmd)
    if log_cmd:
        hutil_log_info('Output of command "{0}": \n{1}'.format(cmd.rstrip(), output))
    elif log_output:
        hutil_log_info('Output: \n{0}'.format(output))

    if "cannot open Packages database" in output:
        # Install failures
        # External issue. Package manager db is either corrupt or needs cleanup
        # https://github.com/Azure/azure-marketplace/wiki/Extension-Build-Notes-Best-Practices#error-codes-and-messages-output-to-stderr
        exit_code = MissingDependency
        output += "Package manager database is in a bad state. Please recover package manager, db cache and try install again later."
    elif "Permission denied" in output:
        # Enable failures
        # https://github.com/Azure/azure-marketplace/wiki/Extension-Build-Notes-Best-Practices#error-codes-and-messages-output-to-stderr
        exit_code = MissingDependency

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

    try:
        unicode_type = unicode # Python 2
    except NameError:
        unicode_type = str # Python 3

    if all(ord(c) < 128 for c in output) or isinstance(output, unicode_type):
        output = output.encode('utf-8')

    # On python 3, encode returns a byte object, so we must decode back to a string
    if sys.version_info >= (3,) and type(output) == bytes:
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
