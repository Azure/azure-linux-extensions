#!/usr/bin/env python
#
# DSC extension
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
import subprocess
import sys
import traceback
import urllib.request
import urllib.error
import urllib.parse
import time
import platform
import json
import datetime
import serializerfactory
import httpclient
import urllib2httpclient
import httpclientfactory

from azure.storage import BlobService
from Utils.WAAgentUtil import waagent
import Utils.HandlerUtil as Util

# Define global variables

ExtensionName = 'Microsoft.OSTCExtensions.DSCForLinux'
ExtensionShortName = 'DSCForLinux'
DownloadDirectory = 'download'

omi_package_prefix = 'packages/omi-1.4.2-5.ssl_'
dsc_package_prefix = 'packages/dsc-1.1.1-926.ssl_'
omi_major_version = 1
omi_minor_version = 4
omi_build = 2
omi_release = 5
dsc_major_version = 1
dsc_minor_version = 1
dsc_build = 1
dsc_release = 926
package_pattern = '(\d+).(\d+).(\d+).(\d+)'
nodeid_path = '/etc/opt/omi/conf/dsc/agentid'
date_time_format = "%Y-%m-%dT%H:%M:%SZ"
extension_handler_version = "2.71.1.0"

# Error codes
UnsupportedDistro = 51 #excludes from SLA
DPKGLockedErrorCode = 51 #excludes from SLA

# DSC-specific Operation
class Operation:
    Download = "Download"
    ApplyMof = "ApplyMof"
    ApplyMetaMof = "ApplyMetaMof"
    InstallModule = "InstallModule"
    RemoveModule = "RemoveModule"
    Register = "Register"
    Enable = "Enable"


class DistroCategory:
    debian = 1
    redhat = 2
    suse = 3


class Mode:
    push = "push"
    pull = "pull"
    install = "install"
    remove = "remove"
    register = "register"


def main():
    waagent.LoggerInit('/var/log/waagent.log', '/dev/stdout')
    waagent.Log("%s started to handle." % (ExtensionShortName))

    global hutil
    hutil = Util.HandlerUtility(waagent.Log, waagent.Error)
    hutil.try_parse_context()

    global public_settings
    public_settings = hutil.get_public_settings()
    if not public_settings:
        waagent.AddExtensionEvent(name=ExtensionShortName, op='MainInProgress', isSuccess=True,
                                  message="Public settings are NOT provided.")
        public_settings = {}

    global protected_settings
    protected_settings = hutil.get_protected_settings()
    if not protected_settings:
        waagent.AddExtensionEvent(name=ExtensionShortName, op='MainInProgress', isSuccess=True,
                                  message="protected settings are NOT provided.")
        protected_settings = {}

    global distro_category
    distro_category = get_distro_category()
    check_supported_OS()

    for a in sys.argv[1:]:
        if re.match("^([-/]*)(disable)", a):
            disable()
        elif re.match("^([-/]*)(uninstall)", a):
            uninstall()
        elif re.match("^([-/]*)(install)", a):
            install()
        elif re.match("^([-/]*)(enable)", a):
            enable()
        elif re.match("^([-/]*)(update)", a):
            update()


def get_distro_category():
    distro_info = platform.dist()
    distro_name = distro_info[0].lower()
    distro_version = distro_info[1]
    if distro_name == 'ubuntu' or (distro_name == 'debian'):
        return DistroCategory.debian
    elif distro_name == 'centos' or distro_name == 'redhat' or distro_name == 'oracle':
        return DistroCategory.redhat
    elif distro_name == 'suse':
        return DistroCategory.suse 
    waagent.AddExtensionEvent(name=ExtensionShortName, op='InstallInProgress', isSuccess=True, message="Unsupported distro :" + distro_name + "; distro_version: " + distro_version)
    hutil.do_exit(UnsupportedDistro, 'Install', 'error', str(UnsupportedDistro), distro_name + 'is not supported.')
    
def check_supported_OS():
    """
    Checks if the VM this extension is running on is supported by DSC
    Returns for platform.linux_distribution() vary widely in format, such as
    '7.3.1611' returned for a VM with CentOS 7, so the first provided
    digits must match.
    All other distros not supported will get error code 51
    """
    supported_dists = {'redhat' : ['6', '7'], # CentOS
                       'centos' : ['6', '7'], # CentOS
                       'red hat' : ['6', '7'], # Redhat
                       'debian' : ['8'], # Debian
                       'ubuntu' : ['14.04', '16.04', '18.04'], # Ubuntu
                       'oracle' : ['6', '7'], # Oracle
                       'suse' : ['11', '12'], #SLES
                       'opensuse' : ['13', '42.3'] #OpenSuse
    }
    vm_supported = False

    try:
        vm_dist, vm_ver, vm_id = platform.linux_distribution()
    except AttributeError:
        vm_dist, vm_ver, vm_id = platform.dist()

    # Find this VM distribution in the supported list
    for supported_dist in supported_dists.keys():
        if vm_dist.lower().startswith(supported_dist):
            # Check if this VM distribution version is supported
            vm_ver_split = vm_ver.split('.')
            for supported_ver in supported_dists[supported_dist]:
                supported_ver_split = supported_ver.split('.')

                # If vm_ver is at least as precise (at least as many digits) as
                # supported_ver and matches all the supported_ver digits, then
                # this VM is supported
                vm_ver_match = True
                for idx, supported_ver_num in enumerate(supported_ver_split):
                    try:
                        supported_ver_num = int(supported_ver_num)
                        vm_ver_num = int(vm_ver_split[idx])
                    except IndexError:
                        vm_ver_match = False
                        break
                    if vm_ver_num is not supported_ver_num:
                        vm_ver_match = False
                        break
                if vm_ver_match:
                    vm_supported = True
                    break

    if not vm_supported:
        waagent.AddExtensionEvent(name=ExtensionShortName, op='InstallInProgress', isSuccess=True, message="Unsupported OS :" + vm_dist + "; distro_version: " + vm_ver)
        hutil.do_exit(UnsupportedDistro, 'Install', 'error', str(UnsupportedDistro), vm_dist + "; distro_version: " + vm_ver + ' is not supported.')


def install():
    hutil.do_parse_context('Install')
    try:
        waagent.AddExtensionEvent(name=ExtensionShortName, op='InstallInProgress', isSuccess=True,
                                  message="Installing DSCForLinux extension")
        remove_old_dsc_packages()
        install_dsc_packages()
        waagent.AddExtensionEvent(name=ExtensionShortName, op='InstallInProgress', isSuccess=True,
                                  message="successfully installed DSCForLinux extension")
        hutil.do_exit(0, 'Install', 'success', '0', 'Install Succeeded.')
    except Exception as e:
        waagent.AddExtensionEvent(name=ExtensionShortName, op='InstallInProgress', isSuccess=True,
                                  message="failed to install DSC extension with error: {0} and stacktrace: {1}".format(
                                      str(e), traceback.format_exc()))
        hutil.error(
            "Failed to install DSC extension with error: %s, stack trace: %s" % (str(e), traceback.format_exc()))
        hutil.do_exit(1, 'Install', 'error', '1', 'Install Failed.')


def enable():
    hutil.do_parse_context('Enable')
    hutil.exit_if_enabled()
    try:
        start_omiservice()
        mode = get_config('Mode')
        if mode == '':
            mode = get_config('ExtensionAction')
        waagent.AddExtensionEvent(name=ExtensionShortName, op='EnableInProgress', isSuccess=True,
                                  message="Enabling the DSC extension - mode/ExtensionAction: " + mode)
        if mode == '':
            mode = Mode.push
        else:
            mode = mode.lower()
            if not hasattr(Mode, mode):
                waagent.AddExtensionEvent(name=ExtensionShortName,
                                          op=Operation.Enable,
                                          isSuccess=True,
                                          message="(03001)Argument error, invalid ExtensionAction/mode.")
                hutil.do_exit(51, 'Enable', 'error', '51', 'Enable failed, unknown ExtensionAction/mode: ' + mode)
        if mode == Mode.remove:
            remove_module()
        elif mode == Mode.register:
            registration_key = get_config('RegistrationKey')
            registation_url = get_config('RegistrationUrl')
            # Optional
            node_configuration_name = get_config('NodeConfigurationName')
            refresh_freq = get_config('RefreshFrequencyMins')
            configuration_mode_freq = get_config('ConfigurationModeFrequencyMins')
            configuration_mode = get_config('ConfigurationMode')
            exit_code, err_msg = register_automation(registration_key, registation_url, node_configuration_name,
                                                     refresh_freq, configuration_mode_freq, configuration_mode.lower())
            if exit_code != 0:
                hutil.do_exit(exit_code, 'Enable', 'error', str(exit_code), err_msg)

            extension_status_event = "ExtensionRegistration"
            response = send_heart_beat_msg_to_agent_service(extension_status_event)
            status_file_path, agent_id, vm_uuid = get_status_message_details()
            update_statusfile(status_file_path, agent_id, vm_uuid, response)
            sys.exit(0)
        else:
            file_path = download_file()
            if mode == Mode.pull:
                current_config = apply_dsc_meta_configuration(file_path)
            elif mode == Mode.push:
                current_config = apply_dsc_configuration(file_path)
            else:
                install_module(file_path)
        if mode == Mode.push or mode == Mode.pull:
            if check_dsc_configuration(current_config):
                if mode == Mode.push:
                    waagent.AddExtensionEvent(name=ExtensionShortName,
                                              op=Operation.ApplyMof,
                                              isSuccess=True,
                                              message="(03104)Succeeded to apply MOF configuration through Push Mode")
                else:
                    waagent.AddExtensionEvent(name=ExtensionShortName,
                                              op=Operation.ApplyMetaMof,
                                              isSuccess=True,
                                              message="(03106)Succeeded to apply meta MOF configuration through Pull Mode")
                    extension_status_event = "ExtensionRegistration"
                    response = send_heart_beat_msg_to_agent_service(extension_status_event)
                    status_file_path, agent_id, vm_uuid = get_status_message_details()
                    update_statusfile(status_file_path, agent_id, vm_uuid, response)
                    sys.exit(0)
            else:
                if mode == Mode.push:
                    waagent.AddExtensionEvent(name=ExtensionShortName,
                                              op=Operation.ApplyMof,
                                              isSuccess=False,
                                              message="(03105)Failed to apply MOF configuration through Push Mode")
                else:
                    waagent.AddExtensionEvent(name=ExtensionShortName,
                                              op=Operation.ApplyMetaMof,
                                              isSuccess=False,
                                              message="(03107)Failed to apply meta MOF configuration through Pull Mode")
                hutil.do_exit(1, 'Enable', 'error', '1', 'Enable failed. ' + current_config)

        hutil.do_exit(0, 'Enable', 'success', '0', 'Enable Succeeded')
    except Exception as e:
        waagent.AddExtensionEvent(name=ExtensionShortName, op='EnableInProgress', isSuccess=True,
                                  message="Enable failed with the error: {0}, stacktrace: {1} ".format(str(e),
                                                                                                       traceback.format_exc()))
        hutil.error('Failed to enable the extension with error: %s, stack trace: %s' % (str(e), traceback.format_exc()))
        hutil.do_exit(1, 'Enable', 'error', '1', 'Enable failed: {0}'.format(e))


def send_heart_beat_msg_to_agent_service(status_event_type):
    response = None
    try:
        retry_count = 0
        canRetry = True
        while retry_count <= 5 and canRetry:
            waagent.AddExtensionEvent(name=ExtensionShortName, op='HeartBeatInProgress', isSuccess=True,
                                      message="In send_heart_beat_msg_to_agent_service method")
            code, output, stderr = run_cmd("python /opt/microsoft/dsc/Scripts/GetDscLocalConfigurationManager.py")
            if code == 0 and "RefreshMode=Pull" in output:
                waagent.AddExtensionEvent(name=ExtensionShortName, op='HeartBeatInProgress', isSuccess=True,
                                          message="sends heartbeat message in pullmode")
                m = re.search("ServerURL=([^\n]+)", output)
                if not m:
                    return
                registration_url = m.group(1)
                agent_id = get_nodeid(nodeid_path)
                node_extended_properties_url = registration_url + "/Nodes(AgentId='" + agent_id + "')/ExtendedProperties"
                waagent.AddExtensionEvent(name=ExtensionShortName, op='HeartBeatInProgress', isSuccess=True,
                                          message="Url is " + node_extended_properties_url)
                headers = {'Content-Type': "application/json; charset=utf-8", 'Accept': "application/json",
                           "ProtocolVersion": "2.0"}
                data = construct_node_extension_properties(output, status_event_type)

                http_client_factory = httpclientfactory.HttpClientFactory("/etc/opt/omi/ssl/oaas.crt",
                                                                          "/etc/opt/omi/ssl/oaas.key")
                http_client = http_client_factory.create_http_client(sys.version_info)

                response = http_client.post(node_extended_properties_url, headers=headers, data=data)
                waagent.AddExtensionEvent(name=ExtensionShortName, op='HeartBeatInProgress', isSuccess=True,
                                          message="response code is " + str(response.status_code))
                if response.status_code >= 500 and response.status_code < 600:
                    canRetry = True
                    time.sleep(10)
                else:
                    canRetry = False
            retry_count += 1
    except Exception as e:
        waagent.AddExtensionEvent(name=ExtensionShortName, op='HeartBeatInProgress', isSuccess=True,
                                  message="Failed to send heartbeat message to DSC agent service: {0}, stacktrace: {1} ".format(
                                      str(e), traceback.format_exc()))
        hutil.error('Failed to send heartbeat message to DSC agent service: %s, stack trace: %s' % (
            str(e), traceback.format_exc()))
    return response


def get_lcm_config_setting(setting_name, lcmconfig):
    valuegroup = re.search(setting_name + "=([^\n]+)", lcmconfig)
    if not valuegroup:
        return ""
    value = valuegroup.group(1)

    return value


def construct_node_extension_properties(lcmconfig, status_event_type):
    waagent.AddExtensionEvent(name=ExtensionShortName, op='HeartBeatInProgress', isSuccess=True,
                              message="Getting properties")
    OMSCLOUD_ID = get_omscloudid()
    distro_info = platform.dist()
    if len(distro_info[1].split('.')) == 1:
        major_version = distro_info[1].split('.')[0]
        minor_version = 0
    if len(distro_info[1].split('.')) >= 2:
        major_version = distro_info[1].split('.')[0]
        minor_version = distro_info[1].split('.')[1]

    VMUUID = get_vmuuid()
    node_config_names = get_lcm_config_setting('ConfigurationNames', lcmconfig)
    configuration_mode = get_lcm_config_setting("ConfigurationMode", lcmconfig)
    configuration_mode_frequency = get_lcm_config_setting("ConfigurationModeFrequencyMins", lcmconfig)
    refresh_frequency_mins = get_lcm_config_setting("RefreshFrequencyMins", lcmconfig)
    reboot_node = get_lcm_config_setting("RebootNodeIfNeeded", lcmconfig)
    action_after_reboot = get_lcm_config_setting("ActionAfterReboot", lcmconfig)
    allow_module_overwrite = get_lcm_config_setting("AllowModuleOverwrite", lcmconfig)

    waagent.AddExtensionEvent(name=ExtensionShortName, op='HeartBeatInProgress', isSuccess=True,
                              message="Constructing properties data")

    properties_data = {
        "OMSCloudId": OMSCLOUD_ID,
        "TimeStamp": time.strftime(date_time_format, time.gmtime()),
        "VMResourceId": "",
        "ExtensionStatusEvent": status_event_type,
        "ExtensionInformation": {
            "Name": "Microsoft.OSTCExtensions.DSCForLinux",
            "Version": extension_handler_version
        },
        "OSProfile": {
            "Name": distro_info[0],
            "Type": "Linux",
            "MinorVersion": minor_version,
            "MajorVersion": major_version,
            "VMUUID": VMUUID
        },
        "RegistrationMetaData": {
            "NodeConfigurationName": node_config_names,
            "ConfigurationMode": configuration_mode,
            "ConfigurationModeFrequencyMins": configuration_mode_frequency,
            "RefreshFrequencyMins": refresh_frequency_mins,
            "RebootNodeIfNeeded": reboot_node,
            "ActionAfterReboot": action_after_reboot,
            "AllowModuleOverwrite": allow_module_overwrite
        }
    }
    return properties_data


def uninstall():
    hutil.do_parse_context('Uninstall')
    try:
        extension_status_event = "ExtensionUninstall"
        send_heart_beat_msg_to_agent_service(extension_status_event)
        hutil.do_exit(0, 'Uninstall', 'success', '0', 'Uninstall Succeeded')
    except Exception as e:
        waagent.AddExtensionEvent(name=ExtensionShortName, op='UninstallInProgress', isSuccess=False,
                                  message='Failed to uninstall the extension with error: %s, stack trace: %s' % (
                                      str(e), traceback.format_exc()))
        hutil.error(
            'Failed to uninstall the extension with error: %s, stack trace: %s' % (str(e), traceback.format_exc()))
        hutil.do_exit(1, 'Uninstall', 'error', '1', 'Uninstall failed: {0}'.format(e))


def disable():
    hutil.do_parse_context('Disable')
    hutil.do_exit(0, 'Disable', 'success', '0', 'Disable Succeeded')


def update():
    hutil.do_parse_context('Update')
    try:
        extension_status_event = "ExtensionUpgrade"
        send_heart_beat_msg_to_agent_service(extension_status_event)
        hutil.do_exit(0, 'Update', 'success', '0', 'Update Succeeded')
    except Exception as e:
        waagent.AddExtensionEvent(name=ExtensionShortName, op='UpdateInProgress', isSuccess=False,
                                  message='Failed to update the extension with error: %s, stack trace: %s' % (
                                      str(e), traceback.format_exc()))
        hutil.error('Failed to update the extension with error: %s, stack trace: %s' % (str(e), traceback.format_exc()))
        hutil.do_exit(1, 'Update', 'error', '1', 'Update failed: {0}'.format(e))


def run_cmd(cmd):
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, close_fds=True)
    exit_code = proc.wait()
    stdout, stderr = proc.communicate()
    return exit_code, stdout, stderr

def run_dpkg_cmd_with_retry(cmd):
    """
    Attempts to run the cmd - if it fails, checks to see if dpkg is locked by another
    process, if so, it will sleep for 5 seconds and then try running the command again.
    If dpkg is still locked, then it will return the DPKGLockedErrorCode which won't
    count against our SLA numbers.
    """
    exit_code, output, stderr = run_cmd(cmd)
    if not exit_code == 0:
        dpkg_locked = is_dpkg_locked(exit_code, stderr)
        if dpkg_locked:
            # Try one more time:
            time.sleep(5)
            exit_code, output, stderr = run_cmd(cmd)
            dpkg_locked = is_dpkg_locked(exit_code, stderr)
            if dpkg_locked:
                exit_code = DPKGLockedErrorCode

    return exit_code, output, stderr

def get_config(key):
    if key in public_settings:
        value = public_settings.get(key)
        if value:
            return str(value).strip()
    if key in protected_settings:
        value = protected_settings.get(key)
        if value:
            return str(value).strip()
    return ''


def remove_old_dsc_packages():
    waagent.AddExtensionEvent(name=ExtensionShortName, op='InstallInProgress', isSuccess=True,
                              message="Deleting DSC and omi packages")
    if distro_category == DistroCategory.debian:
        deb_remove_incomptible_dsc_package()
        # remove the package installed by Linux DSC 1.0, in later versions the package name is changed to 'omi'
        deb_remove_old_oms_package('omiserver', '1.0.8.2')
    elif distro_category == DistroCategory.redhat or distro_category == DistroCategory.suse:
        rpm_remove_incomptible_dsc_package()
        # remove the package installed by Linux DSC 1.0, in later versions the package name is changed to 'omi'
        rpm_remove_old_oms_package('omiserver', '1.0.8-2')


def deb_remove_incomptible_dsc_package():
    version = deb_get_pkg_version('dsc')
    if version is not None and is_incomptible_dsc_package(version):
        deb_uninstall_package('dsc')


def is_incomptible_dsc_package(package_version):
    version = re.match(package_pattern, package_version)
    # uninstall DSC package if the version is 1.0.x because upgrading from 1.0 to 1.1 is broken
    if version is not None and (int(version.group(1)) == 1 and int(version.group(2)) == 0):
        return True
    return False


def is_old_oms_server(package_name):
    if package_name == 'omiserver':
        return True
    return False


def deb_remove_old_oms_package(package_name, version):
    system_pkg_version = deb_get_pkg_version(package_name)
    if system_pkg_version is not None and is_old_oms_server(package_name):
        deb_uninstall_package(package_name)


def deb_get_pkg_version(package_name):
    code, output, stderr = run_dpkg_cmd_with_retry('dpkg -s ' + package_name + ' | grep Version:')
    if code == 0:
        code, output, stderr = run_dpkg_cmd_with_retry("dpkg -s " + package_name + " | grep Version: | awk '{print $2}'")
        if code == 0:
            return output


def rpm_remove_incomptible_dsc_package():
    code, version, stderr = run_cmd('rpm -q --queryformat "%{VERSION}.%{RELEASE}" dsc')
    if code == 0 and is_incomptible_dsc_package(version):
        rpm_uninstall_package('dsc')


def rpm_remove_old_oms_package(package_name, version):
    if rpm_check_old_oms_package(package_name, version):
        rpm_uninstall_package(package_name)


def rpm_check_old_oms_package(package_name, version):
    code, output, stderr = run_cmd('rpm -q ' + package_name)
    if code == 0 and is_old_oms_server(package_name):
        return True
    return False


def install_dsc_packages():
    openssl_version = get_openssl_version()
    omi_package_path = omi_package_prefix + openssl_version
    dsc_package_path = dsc_package_prefix + openssl_version
    waagent.AddExtensionEvent(name=ExtensionShortName, op='InstallInProgress', isSuccess=True,
                              message="Installing omipackage version: " + omi_package_path + "; dsc package version: " + dsc_package_path)
    if distro_category == DistroCategory.debian:
        deb_install_pkg(omi_package_path + '.x64.deb', 'omi', omi_major_version, omi_minor_version, omi_build,
                        omi_release, ' --force-confold --force-confdef --refuse-downgrade ')
        deb_install_pkg(dsc_package_path + '.x64.deb', 'dsc', dsc_major_version, dsc_minor_version, dsc_build,
                        dsc_release, '')
    elif distro_category == DistroCategory.redhat or distro_category == DistroCategory.suse:
        rpm_install_pkg(omi_package_path + '.x64.rpm', 'omi', omi_major_version, omi_minor_version, omi_build,
                        omi_release)
        rpm_install_pkg(dsc_package_path + '.x64.rpm', 'dsc', dsc_major_version, dsc_minor_version, dsc_build,
                        dsc_release)


def compare_pkg_version(system_package_version, major_version, minor_version, build, release):
    version = re.match(package_pattern, system_package_version)
    if version is not None and ((int(version.group(1)) > major_version) or (
            int(version.group(1)) == major_version and int(version.group(2)) > minor_version) or (
                                        int(version.group(1)) == major_version and int(
                                    version.group(2)) == minor_version and int(version.group(3)) > build) or (
                                        int(version.group(1)) == major_version and int(
                                    version.group(2)) == minor_version and int(version.group(3)) == build and int(
                                    version.group(4)) >= release)):
        return 1
    return 0


def rpm_check_pkg_exists(package_name, major_version, minor_version, build, release):
    code, output, stderr = run_cmd('rpm -q --queryformat "%{VERSION}.%{RELEASE}" ' + package_name)
    waagent.AddExtensionEvent(name=ExtensionShortName, op='InstallInProgress', isSuccess=True,
                              message="package name: " + package_name + ";  existing package version:" + output)
    hutil.log("package name: " + package_name + ";  existing package version:" + output)
    if code == 0:
        return compare_pkg_version(output, major_version, minor_version, build, release)


def rpm_install_pkg(package_path, package_name, major_version, minor_version, build, release):
    if rpm_check_pkg_exists(package_name, major_version, minor_version, build, release) == 1:
        # package is already installed
        return
    else:
        code, output, stderr = run_cmd('rpm -Uvh ' + package_path)
        if code == 0:
            hutil.log(package_name + ' is installed successfully')
        else:
            waagent.AddExtensionEvent(name=ExtensionShortName, op='InstallInProgress', isSuccess=True,
                                      message="Failed to install RPM package :" + package_path)
             raise Exception('Failed to install package {0}: stdout: {1}, stderr: {2}'.format(package_name, output, stderr))


def deb_install_pkg(package_path, package_name, major_version, minor_version, build, release, install_options):
    version = deb_get_pkg_version(package_name)
    if version is not None and compare_pkg_version(version, major_version, minor_version, build, release) == 1:
        # package is already installed
        hutil.log(package_name + ' version ' + version + ' is already installed')
        waagent.AddExtensionEvent(name=ExtensionShortName, op='InstallInProgress', isSuccess=True,
                                  message="dsc package with version: " + version + "is already installed.")
        return
    else:
        cmd = 'dpkg -i ' + install_options + ' ' + package_path
        code, output, stderr = run_dpkg_cmd_with_retry(cmd)
        if code == 0:
            hutil.log(package_name + ' version ' + str(major_version) + '.' + str(minor_version) + '.' + str(
                build) + '.' + str(release) + ' is installed successfully')
        elif code == DPKGLockedErrorCode:
            hutil.do_exit(DPKGLockedErrorCode, 'Install', 'error', str(DPKGLockedErrorCode), 'Install failed because the package manager on the VM is currently locked. Please try installing again.')
        else:
            waagent.AddExtensionEvent(name=ExtensionShortName, op='InstallInProgress', isSuccess=False,
                                      message="Failed to install debian package :" + package_path)
            raise Exception('Failed to install package {0}: stdout: {1}, stderr: {2}'.format(package_name, output, stderr))


def install_package(package):
    if distro_category == DistroCategory.debian:
        apt_package_install(package)
    elif distro_category == DistroCategory.redhat:
        yum_package_install(package)
    elif distro_category == DistroCategory.suse:
        zypper_package_install(package)


def zypper_package_install(package):
    hutil.log('zypper --non-interactive in ' + package)
    code, output, stderr = run_cmd('zypper --non-interactive in ' + package)
    if code == 0:
        hutil.log('Package ' + package + ' is installed successfully')
    else:
        waagent.AddExtensionEvent(name=ExtensionShortName, op='InstallInProgress', isSuccess=True,
                                  message="Failed to install zypper package :" + package)
         raise Exception('Failed to install package {0}: stdout: {1}, stderr: {2}'.format(package, output, stderr))


def yum_package_install(package):
    hutil.log('yum install -y ' + package)
    code, output, stderr = run_cmd('yum install -y ' + package)
    if code == 0:
        hutil.log('Package ' + package + ' is installed successfully')
    else:
        waagent.AddExtensionEvent(name=ExtensionShortName, op='InstallInProgress', isSuccess=True,
                                  message="Failed to install yum package :" + package)
        raise Exception('Failed to install package {0}: stdout: {1}, stderr: {2}'.format(package, output, stderr))


def apt_package_install(package):
    hutil.log('apt-get install -y --force-yes ' + package)
    code, output, stderr = run_cmd('apt-get install -y --force-yes ' + package)
    if code == 0:
        hutil.log('Package ' + package + ' is installed successfully')
    else:
        waagent.AddExtensionEvent(name=ExtensionShortName, op='InstallInProgress', isSuccess=True,
                                  message="Failed to install apt package :" + package)
        raise Exception('Failed to install package {0}: stdout: {1}, stderr: {2}'.format(package, output, stderr))


def get_openssl_version():
    cmd_result = waagent.RunGetOutput("openssl version")
    openssl_version = cmd_result[1].split()[1]
    if re.match('^1.0.*', openssl_version):
        return '100'
    elif re.match('^0.9.8*', openssl_version):
        return '098'
    elif re.match('^1.1.*', openssl_version):
        return '110'
    else:
        error_msg = 'This system does not have a supported version of OpenSSL installed. Supported version: 0.9.8*, 1.0.*, 1.1.*'
        hutil.error(error_msg)
        waagent.AddExtensionEvent(name=ExtensionShortName, op='InstallInProgress', isSuccess=True,
                                  message="System doesn't have supported OpenSSL version:" + openssl_version)
        hutil.do_exit(51, 'Install', 'error', '51', openssl_version + 'is not supported.')


def start_omiservice():
    run_cmd('/opt/omi/bin/service_control start')
    code, output, stderr =run_cmd('service omid status')
    if code == 0:
        hutil.log('Service omid is started')
    else:
        raise Exception('Failed to start service omid, status: stdout: {0}, stderr: {1}'.format(output, stderr))


def download_file():
    waagent.AddExtensionEvent(name=ExtensionShortName, op="EnableInProgress", isSuccess=True,
                              message="Downloading file")
    download_dir = prepare_download_dir(hutil.get_seq_no())
    storage_account_name = get_config('StorageAccountName')
    storage_account_key = get_config('StorageAccountKey')
    file_uri = get_config('FileUri')

    if not file_uri:
        error_msg = 'Missing FileUri configuration'
        waagent.AddExtensionEvent(name=ExtensionShortName,
                                  op=Operation.Download,
                                  isSuccess=False,
                                  message="(03000)Argument error, invalid file location")
        hutil.do_exit(51, 'Enable', 'error', '51', '(03000)Argument error, invalid file location')

    if storage_account_name and storage_account_key:
        hutil.log('Downloading file from azure storage...')
        path = download_azure_blob(storage_account_name, storage_account_key, file_uri, download_dir)
        return path
    else:
        hutil.log('Downloading file from external link...')
        waagent.AddExtensionEvent(name=ExtensionShortName, op="EnableInProgress", isSuccess=True,
                                  message="Downloading file from external link...")
        path = download_external_file(file_uri, download_dir)
        return path


def download_azure_blob(account_name, account_key, file_uri, download_dir):
    waagent.AddExtensionEvent(name=ExtensionShortName, op="EnableInProgress", isSuccess=True,
                              message="Downloading from azure blob")
    try:
        (blob_name, container_name) = parse_blob_uri(file_uri)
        host_base = get_host_base_from_uri(file_uri)

        blob_parent_path = os.path.join(download_dir, os.path.dirname(blob_name))
        if not os.path.exists(blob_parent_path):
            os.makedirs(blob_parent_path)

        download_path = os.path.join(download_dir, blob_name)
        blob_service = BlobService(account_name, account_key, host_base=host_base)
    except Exception as e:
        waagent.AddExtensionEvent(name=ExtensionShortName, op='DownloadInProgress', isSuccess=True,
                                  message='Enable failed with the azure storage error : {0}, stack trace: {1}'.format(
                                      str(e), traceback.format_exc()))
        hutil.error('Failed to enable the extension with error: %s, stack trace: %s' % (str(e), traceback.format_exc()))
        hutil.do_exit(1, 'Enable', 'error', '1', 'Enable failed: {0}'.format(e))

    max_retry = 3
    for retry in range(1, max_retry + 1):
        try:
            blob_service.get_blob_to_path(container_name, blob_name, download_path)
        except Exception:
            hutil.error('Failed to download Azure blob, retry = ' + str(retry) + ', max_retry = ' + str(max_retry))
            if retry != max_retry:
                hutil.log('Sleep 10 seconds')
                time.sleep(10)
            else:
                waagent.AddExtensionEvent(name=ExtensionShortName,
                                          op=Operation.Download,
                                          isSuccess=False,
                                          message="(03303)Failed to download file from Azure Storage")
                raise Exception('Failed to download azure blob: ' + blob_name)
    waagent.AddExtensionEvent(name=ExtensionShortName,
                              op=Operation.Download,
                              isSuccess=True,
                              message="(03301)Succeeded to download file from Azure Storage")
    return download_path


def parse_blob_uri(blob_uri):
    path = get_path_from_uri(blob_uri).strip('/')
    first_sep = path.find('/')
    if first_sep == -1:
        waagent.AddExtensionEvent(name=ExtensionShortName, op="EnableInProgress", isSuccess=False,
                                  message="Error occured while extracting container and blob name.")
        hutil.error("Failed to extract container and blob name from " + blob_uri)
    blob_name = path[first_sep + 1:]
    container_name = path[:first_sep]
    return (blob_name, container_name)


def get_path_from_uri(uri):
    uri = urllib.parse.urlparse(uri)
    return uri.path


def get_host_base_from_uri(blob_uri):
    uri = urllib.parse.urlparse(blob_uri)
    netloc = uri.netloc
    if netloc is None:
        return None
    return netloc[netloc.find('.'):]


def download_external_file(file_uri, download_dir):
    waagent.AddExtensionEvent(name=ExtensionShortName, op="EnableInProgress", isSuccess=True,
                              message="Downloading from external file")
    path = get_path_from_uri(file_uri)
    file_name = path.split('/')[-1]
    file_path = os.path.join(download_dir, file_name)
    max_retry = 3
    for retry in range(1, max_retry + 1):
        try:
            download_and_save_file(file_uri, file_path)
            waagent.AddExtensionEvent(name=ExtensionShortName, op=Operation.Download, isSuccess=True,
                                      message="(03302)Succeeded to download file from public URI")
            return file_path
        except Exception as e:
            hutil.error('Failed to download public file, retry = ' + str(retry) + ', max_retry = ' + str(max_retry))
            if retry != max_retry:
                hutil.log('Sleep 10 seconds')
                time.sleep(10)
            else:
                waagent.AddExtensionEvent(name=ExtensionShortName,
                                          op=Operation.Download,
                                          isSuccess=False,
                                          message='(03304)Failed to download file from public URI,  error : %s, stack trace: %s' % (
                                              str(e), traceback.format_exc()))
                raise Exception('Failed to download public file: ' + file_name)


def download_and_save_file(uri, file_path):
    src = urllib.request.urlopen(uri)
    dest = open(file_path, 'wb')
    buf_size = 1024
    buf = src.read(buf_size)
    while (buf):
        dest.write(buf)
        buf = src.read(buf_size)


def prepare_download_dir(seq_no):
    main_download_dir = os.path.join(os.getcwd(), DownloadDirectory)
    if not os.path.exists(main_download_dir):
        os.makedirs(main_download_dir)
    cur_download_dir = os.path.join(main_download_dir, seq_no)
    if not os.path.exists(cur_download_dir):
        os.makedirs(cur_download_dir)
    return cur_download_dir


def apply_dsc_configuration(config_file_path):
    cmd = '/opt/microsoft/dsc/Scripts/StartDscConfiguration.py -configurationmof ' + config_file_path
    waagent.AddExtensionEvent(name=ExtensionShortName, op='EnableInProgress', isSuccess=True,
                              message='running the cmd: ' + cmd)
    code, output, stderr = run_cmd(cmd)
    if code == 0:
        code, output, stderr = run_cmd('/opt/microsoft/dsc/Scripts/GetDscConfiguration.py')
        return output
    else:
        error_msg = 'Failed to apply MOF configuration: stdout: {0}, stderr: {1}'.format(output, stderr)
        waagent.AddExtensionEvent(name=ExtensionShortName, op=Operation.ApplyMof, isSuccess=True, message=error_msg)
        hutil.error(error_msg)
        raise Exception(error_msg)


def apply_dsc_meta_configuration(config_file_path):
    cmd = '/opt/microsoft/dsc/Scripts/SetDscLocalConfigurationManager.py -configurationmof ' + config_file_path
    waagent.AddExtensionEvent(name=ExtensionShortName, op='EnableInProgress', isSuccess=True,
                              message='running the cmd: ' + cmd)
    code, output, stderr = run_cmd(cmd)
    if code == 0:
        code, output, stderr = run_cmd('/opt/microsoft/dsc/Scripts/GetDscLocalConfigurationManager.py')
        return output
    else:
        error_msg = 'Failed to apply Meta MOF configuration: stdout: {0}, stderr: {1}'.format(output, stderr)
        hutil.error(error_msg)
        waagent.AddExtensionEvent(name=ExtensionShortName,
                                  op=Operation.ApplyMetaMof,
                                  isSuccess=False,
                                  message="(03107)" + error_msg)
        raise Exception(error_msg)


def get_statusfile_path():
    seq_no = hutil.get_seq_no()
    waagent.AddExtensionEvent(name=ExtensionShortName, op="EnableInProgress", isSuccess=True,
                              message="sequence number is :" + seq_no)
    status_file = None

    handlerEnvironment = None
    handler_env_path = os.path.join(os.getcwd(), 'HandlerEnvironment.json')
    try:
        with open(handler_env_path, 'r') as handler_env_file:
            handler_env_txt = handler_env_file.read()
        handler_env = json.loads(handler_env_txt)
        if type(handler_env) == list:
            handler_env = handler_env[0]
        handlerEnvironment = handler_env
    except Exception as e:
        hutil.error(e.message)
        waagent.AddExtensionEvent(name=ExtensionShortName, op="EnableInProgress", isSuccess=True,
                                  message='exception in retrieving status_dir error : %s, stack trace: %s' % (
                                      str(e), traceback.format_exc()))

    status_dir = handlerEnvironment['handlerEnvironment']['statusFolder']
    status_file = status_dir + '/' + seq_no + '.status'
    waagent.AddExtensionEvent(name=ExtensionShortName, op="EnableInProgress", isSuccess=True,
                              message="status file path: " + status_file)
    return status_file


def get_status_message_details():
    agent_id = get_nodeid(nodeid_path)
    vm_uuid = get_vmuuid()
    status_file_path = None
    if vm_uuid is not None and agent_id is not None:
        status_file_path = get_statusfile_path()

    return status_file_path, agent_id, vm_uuid


def update_statusfile(status_filepath, node_id, vmuuid, response):
    waagent.AddExtensionEvent(name=ExtensionShortName, op="EnableInProgress", isSuccess=True,
                              message="updating the status file " + '[statusfile={0}][vmuuid={1}][node_id={2}]'.format(
                                  status_filepath, vmuuid, node_id))
    if status_filepath is None:
        error_msg = "Unable to locate a status file"
        hutil.error(error_msg)
        waagent.AddExtensionEvent(name=ExtensionShortName, op="EnableInProgress", isSuccess=False, message=error_msg)
        return None

    status_data = None
    if os.path.exists(status_filepath):
        jsonData = open(status_filepath)
        status_data = json.load(jsonData)
        jsonData.close()

    accountName = response.deserialized_data["AccountName"]
    rgName = response.deserialized_data["ResourceGroupName"]
    subId = response.deserialized_data["SubscriptionId"]

    metadatastatus = [{"status": "success", "code": "0", "name": "metadata", "formattedMessage": {"lang": "en-US",
                                                                                                  "message": "AgentID=" + node_id + ";VMUUID=" + vmuuid + ";AutomationAccountName=" + accountName + ";ResourceGroupName=" + rgName + ";Subscription=" + subId}}]
    with open(status_filepath, "w") as fp:
        status_file_content = [{"status":
                                    {"status": "success",
                                     "formattedMessage": {"lang": "en-US", "message": "Enable Succeeded"},
                                     "operation": "Enable", "code": "0", "name": "Microsoft.OSTCExtensions.DSCForLinux",
                                     "substatus": metadatastatus
                                     },
                                "version": "1.0", "timestampUTC": time.strftime(date_time_format, time.gmtime())
                                }]
        json.dump(status_file_content, fp)
    waagent.AddExtensionEvent(name=ExtensionShortName, op="EnableInProgress", isSuccess=True,
                              message="successfully written nodeid and vmuuid")
    waagent.AddExtensionEvent(name=ExtensionName, op="Enable", isSuccess=True,
                              message="successfully executed enable functionality")


def get_nodeid(file_path):
    id = None
    try:
        if os.path.exists(file_path):
            with open(file_path) as f:
                id = f.readline().strip()
    except Exception as e:
        error_msg = 'get_nodeid() failed: Unable to open id file {0}'.format(file_path)
        hutil.error(error_msg)
        waagent.AddExtensionEvent(name=ExtensionShortName, op="EnableInProgress", isSuccess=False, message=error_msg)
        return None
    if not id:
        error_msg = 'get_nodeid() failed: Empty content in id file {0}'.format(file_path)
        hutil.error(error_msg)
        waagent.AddExtensionEvent(name=ExtensionShortName, op="EnableInProgress", isSuccess=False, message=error_msg)
        return None
    return id


def get_vmuuid():
    UUID = None
    code, output, stderr = run_cmd("sudo dmidecode | grep UUID | sed -e 's/UUID: //'")
    if code == 0:
        UUID = output.strip()
    return UUID


def get_omscloudid():
    OMSCLOUD_ID = None
    code, output, stderr = run_cmd("sudo dmidecode | grep 'Tag: 77' | sed -e 's/Asset Tag: //'")
    if code == 0:
        OMSCLOUD_ID = output.strip()
    return OMSCLOUD_ID


def check_dsc_configuration(current_config):
    outputlist = re.split("\n", current_config)
    for line in outputlist:
        if re.match(r'ReturnValue=0', line.strip()):
            return True
    return False


def install_module(file_path):
    install_package('unzip')
    cmd = '/opt/microsoft/dsc/Scripts/InstallModule.py ' + file_path
    code, output, stderr = run_cmd(cmd)
    waagent.AddExtensionEvent(name=ExtensionShortName,
                              op="InstallModuleInProgress",
                              isSuccess=True,
                              message="Running the cmd: " + cmd)
    if not code == 0:
        error_msg = 'Failed to install DSC Module ' + file_path + ' stdout: {0}, stderr: {1}'.format(output, stderr)
        hutil.error(error_msg)
        waagent.AddExtensionEvent(name=ExtensionShortName,
                                  op=Operation.InstallModule,
                                  isSuccess=False,
                                  message="(03100)" + error_msg)
        raise Exception(error_msg)
    waagent.AddExtensionEvent(name=ExtensionShortName,
                              op=Operation.InstallModule,
                              isSuccess=True,
                              message="(03101)Succeeded to install DSC Module")


def remove_module():
    module_name = get_config('ResourceName')
    cmd = '/opt/microsoft/dsc/Scripts/RemoveModule.py ' + module_name
    code, output, stderr = run_cmd(cmd)
    waagent.AddExtensionEvent(name=ExtensionShortName,
                              op="RemoveModuleInProgress",
                              isSuccess=True,
                              message="Running the cmd: " + cmd)
    if not code == 0:
        error_msg = 'Failed to remove DSC Module ' + module_name + ' stdout: {0}, stderr: {1}'.format(output, stderr)
        hutil.error(error_msg)
        waagent.AddExtensionEvent(name=ExtensionShortName,
                                  op=Operation.RemoveModule,
                                  isSuccess=False,
                                  message="(03102)" + error_msg)
        raise Exception(error_msg)
    waagent.AddExtensionEvent(name=ExtensionShortName,
                              op=Operation.RemoveModule,
                              isSuccess=True,
                              message="(03103)Succeeded to remove DSC Module")


def uninstall_package(package_name):
    waagent.AddExtensionEvent(name=ExtensionShortName, op='InstallInProgress', isSuccess=True,
                              message="uninstalling the package" + package_name)
    if distro_category == DistroCategory.debian:
        deb_uninstall_package(package_name)
    elif distro_category == DistroCategory.redhat or distro_category == DistroCategory.suse:
        rpm_uninstall_package(package_name)


def deb_uninstall_package(package_name):
    cmd = 'dpkg -P ' + package_name
    code, output, stderr = run_dpkg_cmd_with_retry(cmd)
    if code == 0:
        hutil.log('Package ' + package_name + ' was removed successfully')
    elif code == DPKGLockedErrorCode:
        hutil.do_exit(DPKGLockedErrorCode, 'Install', 'error', str(DPKGLockedErrorCode), 'Operation failed because the package manager on the VM is currently locked. Please try again.')
    else:
        waagent.AddExtensionEvent(name=ExtensionShortName, op='InstallInProgress', isSuccess=True,
                                  message="failed to remove the package" + package_name)
        raise Exception('Failed to remove package ' + package_name)


def rpm_uninstall_package(package_name):
    cmd = 'rpm -e ' + package_name
    code, output, stderr = run_cmd(cmd)
    if code == 0:
        hutil.log('Package ' + package_name + ' was removed successfully')
    else:
        waagent.AddExtensionEvent(name=ExtensionShortName, op='InstallInProgress', isSuccess=True,
                                  message="failed to remove the package" + package_name)
        raise Exception('Failed to remove package ' + package_name)
        
def is_dpkg_locked(exit_code, output):
    """
    If dpkg is locked, the output will contain a message similar to 'dpkg
    status database is locked by another process'
    """
    if exit_code is not 0:
        dpkg_locked_search = r'^.*dpkg.+lock.*$'
        dpkg_locked_re = re.compile(dpkg_locked_search, re.M)
        if dpkg_locked_re.search(output):
            return True
    return False


def register_automation(registration_key, registation_url, node_configuration_name, refresh_freq,
                        configuration_mode_freq, configuration_mode):
    if (registration_key == '' or registation_url == ''):
        err_msg = "Either the Registration Key or Registration URL is NOT provided"
        hutil.error(err_msg)
        waagent.AddExtensionEvent(name=ExtensionShortName, op='RegisterInProgress', isSuccess=True, message=err_msg)
        return 51, err_msg
    if configuration_mode != '' and not (
            configuration_mode == 'applyandmonitor' or configuration_mode == 'applyandautocorrect' or configuration_mode == 'applyonly'):
        err_msg = "ConfigurationMode: " + configuration_mode + " is not valid."
        hutil.error(err_msg + "It should be one of the values : (ApplyAndMonitor | ApplyAndAutoCorrect | ApplyOnly)")
        waagent.AddExtensionEvent(name=ExtensionShortName, op='RegisterInProgress', isSuccess=True, message=err_msg)
        return 51, err_msg
    cmd = '/opt/microsoft/dsc/Scripts/Register.py' + ' --RegistrationKey ' + registration_key \
          + ' --ServerURL ' + registation_url
    optional_parameters = ""
    if node_configuration_name != '':
        optional_parameters += ' --ConfigurationName ' + node_configuration_name
    if refresh_freq != '':
        optional_parameters += ' --RefreshFrequencyMins ' + refresh_freq
    if configuration_mode_freq != '':
        optional_parameters += ' --ConfigurationModeFrequencyMins ' + configuration_mode_freq
    if configuration_mode != '':
        optional_parameters += ' --ConfigurationMode ' + configuration_mode
    waagent.AddExtensionEvent(name=ExtensionShortName,
                              op="RegisterInProgress",
                              isSuccess=True,
                              message="Registration URL " + registation_url + "Optional parameters to Registration" + optional_parameters)
    code, output, stderr = run_cmd(cmd + optional_parameters)
    if not code == 0:
        error_msg = '(03109)Failed to register with Azure Automation DSC: stdout: {0}, stderr: {1}'.format(output, stderr)
        hutil.error(error_msg)
        waagent.AddExtensionEvent(name=ExtensionShortName,
                                  op=Operation.Register,
                                  isSuccess=False,
                                  message=error_msg)
        return 1, error_msg
    waagent.AddExtensionEvent(name=ExtensionShortName,
                              op=Operation.Register,
                              isSuccess=True,
                              message="(03108)Succeeded to register with Azure Automation DSC")
    return 0, ''


if __name__ == '__main__':
    main()
