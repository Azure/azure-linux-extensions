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
#
# Requires Python 2.6+
#


import array
import base64
import os
import os.path
import re
import string
import subprocess
import sys
import imp
import traceback
import urllib2
import urlparse
import time
import shutil
import platform

from azure.storage import BlobService
from Utils.WAAgentUtil import waagent
import Utils.HandlerUtil as Util

# Define global variables

ExtensionShortName = 'DSC'
DownloadDirectory = 'download'

omi_package_prefix = 'packages/omi-1.0.8.ssl_'
dsc_package_prefix = 'packages/dsc-1.1.0-466.ssl_'
omi_version_deb = '1.0.8.2'
omi_version_rpm = '1.0.8-2'
dsc_version_deb = '1.1.0.466'
dsc_version_rpm = '1.1.0-466'

# DSC-specific Operation
DownloadOp = "Download"
ApplyMofOp = "ApplyMof"
ApplyMetaMofOp = "ApplyMetaMof"
InstallModuleOp = "InstallModule"
RemoveModuleOp = "RemoveModule"
RegisterOp = "Register"

def main():
    waagent.LoggerInit('/var/log/waagent.log','/dev/stdout')
    waagent.Log("%s started to handle." %(ExtensionShortName))    

    global hutil
    hutil = Util.HandlerUtility(waagent.Log, waagent.Error, ExtensionShortName)
    hutil.try_parse_context()

    global public_settings
    public_settings = hutil.get_public_settings()
    if not public_settings:
        public_settings = {}

    global protected_settings
    protected_settings = hutil.get_protected_settings()
    if not protected_settings:
        protected_settings = {}

    global distro_name
    distro_info = platform.dist()
    distro_name = distro_info[0].lower()

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

def install():
    hutil.do_parse_context('Install')
    try:
        remove_old_dsc_packages()
        install_dsc_packages()
        hutil.do_exit(0, 'Install', 'success', '0', 'Install Succeeded.')
    except Exception, e:
        hutil.error("Failed to install the extension with error: %s, stack trace: %s" %(str(e), traceback.format_exc()))
        hutil.do_exit(1, 'Install', 'error', '1', 'Install Failed.')

def enable():
    hutil.do_parse_context('Enable')
    hutil.exit_if_enabled()
    try:
        start_omiserver()
        mode = get_config('Mode')
        if mode == '':
            mode = 'push'
        else:
            mode = mode.lower()
        if mode == 'remove':
            remove_module()
        elif mode == 'register':
            register_automation()
        else:
            file_path = download_file(mode)
            if mode == 'pull':
                current_config = apply_dsc_meta_configuration(file_path)
            elif mode == 'push':
                current_config = apply_dsc_configuration(file_path)
            elif mode == 'install':
                install_module(file_path)
            else:
                hutil.do_exit(1, 'Enable', 'error', '1', 'Enable failed, unknown mode: ' + mode)
                waagent.AddExtensionEvent(name=ExtensionShortName,
                                          op=ApplyMofOp,
                                          isSuccess=False,
                                          message="(03001)Argument error, invalid mode")
        if mode == 'push' or mode == 'pull':
            if check_dsc_configuration(current_config):
                hutil.do_exit(0, 'Enable', 'success', '0', 'Enable Succeeded. Current Configuration: ' + current_config)
                if mode == 'push':
                    waagent.AddExtensionEvent(name=ExtensionShortName,
                                              op=ApplyMofOp,
                                              isSuccess=True,
                                              message="(03104)Succeeded to apply MOF configuration through Push Mode")
                else:
                    waagent.AddExtensionEvent(name=ExtensionShortName,
                                              op=ApplyMetaMofOp,
                                              isSuccess=True,
                                              message="(03106)Succeeded to apply meta MOF configuration through Pull Mode")
            else:
                hutil.do_exit(1, 'Enable', 'error', '1', 'Enable failed. ' + current_config)
                if mode == 'push':
                    waagent.AddExtensionEvent(name=ExtensionShortName,
                                              op=ApplyMofOp,
                                              isSuccess=False,
                                              message="(03105)Failed to apply MOF configuration through Push Mode")
                else:
                    waagent.AddExtensionEvent(name=ExtensionShortName,
                                              op=ApplyMetaMofOp,
                                              isSuccess=False,
                                              message="(03107)Failed to apply meta MOF configuration through Pull Mode")
        hutil.do_exit(0, 'Enable', 'success', '0', 'Enable Succeeded')
    except Exception, e:
        hutil.error('Failed to enable the extension with error: %s, stack trace: %s' %(str(e), traceback.format_exc()))
        hutil.do_exit(1, 'Enable', 'error', '1', 'Enable failed: {0}'.format(e))
    
def uninstall():
    hutil.do_parse_context('Uninstall')
    try:
        uninstall_package('dsc')
        hutil.do_exit(0, 'Uninstall', 'success', '0', 'Uninstall Succeeded')
    except Exception, e:
        hutil.error('Failed to uninstall the extension with error: %s, stack trace: %s' %(str(e), traceback.format_exc()))
        hutil.do_exit(1, 'Uninstall', 'error', '1', 'Uninstall failed: {0}'.format(e))

def disable():
    hutil.do_parse_context('Disable')
    hutil.do_exit(0, 'Disable', 'success', '0', 'Disable Succeeded')

def update():
    hutil.do_parse_context('Update')
    hutil.do_exit(0, 'Update', 'success', '0', 'Update Succeeded')

def run_cmd(cmd):
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    proc.wait()
    output = proc.stdout.read()
    code = proc.returncode
    return code,output        

def get_config(key):
    if public_settings.has_key(key):
        value = public_settings.get(key)
        if value:
            return value.strip()
    if protected_settings.has_key(key):
        value = protected_settings.get(key)
        if value:
            return value.strip()
    return ''

def remove_old_dsc_packages():
    if (distro_name == 'ubuntu' or distro_name == 'debian'):
        deb_remove_old_package('dsc', dsc_version_deb)
        deb_remove_old_package('omiserver', '1.0.8.2')
        deb_remove_old_package('omi', omi_version_deb)
    elif (distro_name == 'centos' or distro_name == 'redhat' or distro_name == 'suse'):
        rpm_remove_old_package('dsc', dsc_version_rpm)
        rpm_remove_old_package('omiserver', '1.0.8-2')
        rpm_remove_old_package('omi', omi_version_rpm)

def deb_remove_old_package(package_name, version):
    if deb_check_old_package(package_name, version):
        deb_uninstall_package(package_name)

def rpm_remove_old_package(package_name, version):
    if rpm_check_old_package(package_name, version):
        rpm_uninstall_package(package_name)

def deb_check_old_package(package_name, version):
    code,output = run_cmd('dpkg -s ' + package_name + ' | grep Version:')
    if code == 0:
        code,output = run_cmd("dpkg -s " + package_name + " | grep Version: | awk '{print $2}'")
        if output < version:
            return True
    return False

def rpm_check_old_package(package_name, version):
    code,output = run_cmd('rpm -q ' + package_name)
    if code == 0:
        l = len(package_name) + 1
        if output[l:] < version:
            return True
    return False

def install_dsc_packages():
    openssl_version = get_openssl_version()
    omi_package_path = omi_package_prefix + openssl_version
    dsc_package_path = dsc_package_prefix + openssl_version
    if (distro_name == 'ubuntu' or distro_name == 'debian'):
        deb_install_pkg(omi_package_path + '.x64.deb', 'omi', omi_version_deb)
        deb_install_pkg(dsc_package_path + '.x64.deb', 'dsc', dsc_version_deb )
    elif (distro_name == 'centos' or distro_name == 'redhat' or distro_name == 'suse'):
        rpm_install_pkg(omi_package_path + '.x64.rpm', 'omi-' + omi_version_rpm)
        rpm_install_pkg(dsc_package_path + '.x64.rpm', 'dsc-' + dsc_version_rpm)
    else:
        raise Exception('Unknown distro: {0}'.format(distro_name))

def rpm_install_pkg(package_path, package_name):
    code,output = run_cmd('rpm -q ' + package_name)
    if code == 0:
        # package is already installed
        hutil.log(package_name + ' is already installed')
        return
    else:
        code,output = run_cmd('rpm -Uvh ' + package_path)
        if code == 0:
            hutil.log(package_name + ' is installed successfully')
        else:
            raise Exception('Failed to install package {0}: {1}'.format(package_name, output))

def deb_install_pkg(package_path, package_name, package_version):
    code,output = run_cmd('dpkg -s ' + package_name + ' | grep "Version: ' + package_version + '"')
    if code == 0:
        # package is already installed
        hutil.log(package_name + ' version ' + package_version + ' is already installed')
        return
    else:
        code,output = run_cmd('dpkg -i ' + package_path)
        if code == 0:
            hutil.log(package_name + ' version ' + package_version + ' is installed successfully')
        else:
            raise Exception('Failed to install package {0}: {1}'.format(package_name, output))

def install_package(package):
    if (distro_name == 'ubuntu' or distro_name == 'debian'):
        apt_package_install(package)
    elif (distro_name == 'centos' or distro_name == 'redhat'):
        yum_package_install(package)
    elif distro_name == 'suse':
        zypper_package_install(package)
    else:
        raise Exception('Unknown distro: {0}'.format(distro_name))

def zypper_package_install(package):
    hutil.log('zypper --non-interactive in ' + package)
    code,output = run_cmd('zypper --non-interactive in ' + package)
    if code == 0:
        hutil.log('Package ' + package + ' is installed successfully')
    else:
        raise Exception('Failed to install package {0}: {1}'.format(package, output))

def yum_package_install(package):
    hutil.log('yum install -y ' + package)
    code,output = run_cmd('yum install -y ' + package)
    if code == 0:
        hutil.log('Package ' + package + ' is installed successfully')
    else:
        raise Exception('Failed to install package {0}: {1}'.format(package, output))

def apt_package_install(package):
    hutil.log('apt-get install -y --force-yes ' + package)
    code,output = run_cmd('apt-get install -y --force-yes ' + package)
    if code == 0:
        hutil.log('Package ' + package + ' is installed successfully')
    else:
        raise Exception('Failed to install package {0}: {1}'.format(package, output))    

def get_openssl_version():
    cmd_result = waagent.RunGetOutput("openssl version")
    openssl_version = cmd_result[1].split()[1]
    if re.match('^1.0.*', openssl_version):
        return '100'
    elif re.match('^0.9.8*', openssl_version):
        return '098'
    else:
        error_msg = 'This system does not have a supported version of OpenSSL installed. Supported version: 0.9.8*, 1.0.*'
        hutil.error(error_msg)
        raise Exception(error_msg)                
        
def start_omiserver():
    run_cmd('service omiserverd start')
    code,output = run_cmd('service omiserverd status')
    if code == 0:
        hutil.log('Service omiserverd is started')
    else:
        raise Exception('Failed to start service omiserverd, status : {0}'.format(output))

def download_file(mode):
    download_dir = prepare_download_dir(hutil.get_seq_no())

    storage_account_name = get_config('StorageAccountName')
    storage_account_key = get_config('StorageAccountKey')
    container_name = get_config('ContainerName')
    mof_blob_name = get_config('MofFileName')
    mof_file_uri = get_config('MofFileUri')
    resource_file_name = get_config('ResourceZipFileName')
    resource_file_uri = get_config('ResourceZipFileUri')

    if mode == 'push' or mode == 'pull':
        if storage_account_name and storage_account_key and container_name and mof_blob_name:
            hutil.log('Downloading the MOF file ' + mof_blob_name + ' from azure storage')
            download_path = os.path.join(download_dir, mof_blob_name)
            download_azure_blob(storage_account_name, storage_account_key, container_name, mof_blob_name, download_path)
            return download_path
        elif mof_file_uri:
            hutil.log('Downloading the MOF file from external link')
            file_path = download_external_file(mof_file_uri, download_dir)            
            return file_path
        else:
            error_msg = 'Missing configurations of MOF file'
            waagent.AddExtensionEvent(name=ExtensionShortName,
                                      op=DownloadOp,
                                      isSuccess=False,
                                      message="(03000)Argument error, invalid file location")
        
    elif mode == 'install':
        if storage_account_name and storage_account_key and container_name and resource_file_name:
            hutil.log('Downloading the resource zip file ' + resource_file_name + ' from azure storage')
            download_path = os.path.join(download_dir, resource_file_name)
            download_azure_blob(storage_account_name, storage_account_key, container_name, resource_file_name, download_path)
            return download_path
        elif resource_file_uri:
            hutil.log('Downloading the resource zip file from external link')
            file_path = download_external_file(resource_file_uri, download_dir)
            return file_path
        else:
            error_msg = 'Missing configurations of resource zip file'
            waagent.AddExtensionEvent(name=ExtensionShortName,
                                      op=DownloadOp,
                                      isSuccess=False,
                                      message="(03000)Argument error, invalid file location")
    else:
        error_msg = 'Invalid mode: ' + mode
    hutil.error(error_msg)
    raise Exception(error_msg)

def get_path_from_uri(uri_str):
    uri = urlparse.urlparse(uri_str)
    return uri.path

def download_azure_blob(account_name, account_key, container_name, blob_name, download_path):
    blob_service = BlobService(account_name, account_key)
    max_retry = 3
    for retry in range(1, max_retry + 1):
        try:
            blob_service.get_blob_to_path(container_name, blob_name, download_path)
        except Exception, e:
            hutil.error('Failed to download Azure blob, retry = ' + str(retry) + ', max_retry = ' + str(max_retry))
            if retry != max_retry:
                hutil.log('Sleep 10 seconds')
                time.sleep(10)
            else:
                waagent.AddExtensionEvent(name=ExtensionShortName,
                                          op=DownloadOp,
                                          isSuccess=False,
                                          message="(03303)Failed to download file from Azure Storage")
                raise Exception('Failed to download azure blob: ' + blob_name)
    waagent.AddExtensionEvent(name=ExtensionShortName,
                              op=DownloadOp,
                              isSuccess=True,
                              message="(03301)Succeeded to download file from Azure Storage")

def download_external_file(file_uri, download_dir):
    path = get_path_from_uri(file_uri)
    file_name = path.split('/')[-1]
    file_path = os.path.join(download_dir, file_name)
    max_retry = 3
    for retry in range(1, max_retry + 1):
        try:
            download_and_save_file(file_uri, file_path)
            return file_path
        except Exception, e:
            hutil.error('Failed to download public file, retry = ' + str(retry) + ', max_retry = ' + str(max_retry))
            if retry != max_retry:
                hutil.log('Sleep 10 seconds')
                time.sleep(10)
            else:
                waagent.AddExtensionEvent(name=ExtensionShortName,
                                          op=DownloadOp,
                                          isSuccess=False,
                                          message="(03304)Failed to download file from public URI")
                raise Exception('Failed to download public file: ' + file_name)
    waagent.AddExtensionEvent(name=ExtensionShortName,
                              op=DownloadOp,
                              isSuccess=True,
                              message="(03302)Succeeded to download file from public URI")

def download_and_save_file(uri, file_path):
    src = urllib2.urlopen(uri)
    dest = open(file_path, 'wb')
    buf_size = 1024
    buf = src.read(buf_size)
    while(buf):
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
    code,output = run_cmd('/opt/microsoft/dsc/Scripts/StartDscConfiguration.py -configurationmof ' + config_file_path)
    if code == 0:
        code,output = run_cmd('/opt/microsoft/dsc/Scripts/GetDscConfiguration.py')
        return output
    else:
        error_msg = 'Failed to apply MOF configuration: {0}'.format(output)
        hutil.error(error_msg)
        waagent.AddExtensionEvent(name=ExtensionShortName,
                                  op=ApplyMofOp,
                                  isSuccess=False,
                                  message="(03105)" + error_msg)
        raise Exception(error_msg)

def apply_dsc_meta_configuration(config_file_path):
    code,output = run_cmd('/opt/microsoft/dsc/Scripts/SetDscLocalConfigurationManager.py -configurationmof ' + config_file_path)
    if code == 0:
        code,output = run_cmd('/opt/microsoft/dsc/Scripts/GetDscLocalConfigurationManager.py')
        return output
    else:
        error_msg = 'Failed to apply Meta MOF configuration: {0}'.format(output)
        hutil.error(error_msg)
        waagent.AddExtensionEvent(name=ExtensionShortName,
                                  op=ApplyMetaMofOp,
                                  isSuccess=False,
                                  message="(03107)" + error_msg)
        raise Exception(error_msg)

def check_dsc_configuration(current_config):
    outputlist = re.split("\n", current_config)
    for line in outputlist:
        if re.match(r'ReturnValue=0', line.strip()):
            return True
    return False

def install_module(file_path):
    install_package('unzip')
    code,output = run_cmd('/opt/microsoft/dsc/Scripts/InstallModule.py ' + file_path)
    if not code == 0:
        error_msg = 'Failed to install DSC Module ' + file_path + ':{0}'.format(output)
        hutil.error(error_msg)
        waagent.AddExtensionEvent(name=ExtensionShortName,
                                  op=InstallModuleOp,
                                  isSuccess=False,
                                  message="(03100)" + error_msg)
        raise Exception(error_msg)
    waagent.AddExtensionEvent(name=ExtensionShortName,
                              op=InstallModuleOp,
                              isSuccess=True,
                              message="(03101)Succeeded to install DSC Module")

def remove_module():
    module_name = get_config('ResourceName')
    code,output = run_cmd('/opt/microsoft/dsc/Scripts/RemoveModule.py ' + module_name)
    if not code == 0:
        error_msg = 'Failed to remove DSC Module ' + module_name + ': {0}'.format(output)
        hutil.error(error_msg)
        waagent.AddExtensionEvent(name=ExtensionShortName,
                                  op=RemoveModuleOp,
                                  isSuccess=False,
                                  message="(03102)" + error_msg)
        raise Exception(error_msg)
    waagent.AddExtensionEvent(name=ExtensionShortName,
                              op=RemoveModuleOp,
                              isSuccess=True,
                              message="(03103)Succeeded to remove DSC Module")

def uninstall_package(package_name):
    if (distro_name == 'ubuntu' or distro_name == 'debian'):
        deb_uninstall_package(package_name)
    elif (distro_name == 'centos' or distro_name == 'redhat' or distro_name == 'suse'):
        rpm_uninstall_package(package_name)

def deb_uninstall_package(package_name):
    cmd = 'dpkg -P ' + package_name
    code,output = run_cmd(cmd)
    if code == 0:
        hutil.log('Package ' + package_name + ' is removed successfully')
    else:
        raise Exception('Failed to remove package ' + package_name)

def rpm_uninstall_package(package_name):
    cmd = 'rpm -e ' + package_name
    code,output = run_cmd(cmd)
    if code == 0:
        hutil.log('Package ' + package_name + ' is removed successfully')
    else:
        raise Exception('Failed to remove package ' + package_name)

def register_automation():
    registration_key = get_config('RegistrationKey')
    registation_url = get_config('RegistrationUrl')
    code,output = run_cmd('/opt/microsoft/dsc/Scripts/Register.py ' + registration_key + ' ' + registation_url)
    if not code == 0:
        error_msg = 'Failed to register with Azure Automation DSC: {0}'.format(output)
        hutil.error(error_msg)
        waagent.AddExtensionEvent(name=ExtensionShortName,
                                  op=RegisterOp,
                                  isSuccess=False,
                                  message="(03109)" + error_msg)
        raise Exception(error_msg)
    waagent.AddExtensionEvent(name=ExtensionShortName,
                              op=RegisterOp,
                              isSuccess=True,
                              message="(03108)Succeeded to register with Azure Automation DSC")
    
if __name__ == '__main__':
    main()

