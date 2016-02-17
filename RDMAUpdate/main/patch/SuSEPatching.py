#!/usr/bin/python
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
# Requires Python 2.4+


import os
import sys
import imp
import base64
import re
import json
import platform
import shutil
import time
import traceback
import datetime
import subprocess
from AbstractPatching import AbstractPatching
from Common import *
from CommandExecuter import CommandExecuter
from RdmaException import RdmaException
from SecondStageMarkConfig import SecondStageMarkConfig

class SuSEPatching(AbstractPatching):
    def __init__(self,logger,distro_info):
        super(SuSEPatching,self).__init__(distro_info)
        self.logger = logger
        if(distro_info[1] == "11"):
            self.base64_path = '/usr/bin/base64'
            self.bash_path = '/bin/bash'
            self.blkid_path = '/sbin/blkid'
            self.cryptsetup_path = '/sbin/cryptsetup'
            self.cat_path = '/bin/cat'
            self.dd_path = '/bin/dd'
            self.e2fsck_path = '/sbin/e2fsck'
            self.echo_path = '/bin/echo'
            self.lsblk_path = '/bin/lsblk'
            self.lsscsi_path = '/usr/bin/lsscsi'
            self.mkdir_path = '/bin/mkdir'
            self.modprobe_path = '/usr/bin/modprobe'
            self.mount_path = '/bin/mount'
            self.openssl_path = '/usr/bin/openssl'
            self.ps_path = '/bin/ps'
            self.resize2fs_path = '/sbin/resize2fs'
            self.reboot_path = '/sbin/reboot'
            self.rmmod_path = '/sbin/rmmod'
            self.service_path='/usr/sbin/service'
            self.umount_path = '/bin/umount'
            self.zypper_path = '/usr/bin/zypper'
        else:
            self.base64_path = '/usr/bin/base64'
            self.bash_path = '/bin/bash'
            self.blkid_path = '/usr/bin/blkid'
            self.cat_path = '/bin/cat'
            self.cryptsetup_path = '/usr/sbin/cryptsetup'
            self.dd_path = '/usr/bin/dd'
            self.e2fsck_path = '/sbin/e2fsck'
            self.echo_path = '/usr/bin/echo'
            self.lsblk_path = '/usr/bin/lsblk'
            self.lsscsi_path = '/usr/bin/lsscsi'
            self.mkdir_path = '/usr/bin/mkdir'
            self.modprobe_path = '/usr/sbin/modprobe'
            self.mount_path = '/usr/bin/mount'
            self.openssl_path = '/usr/bin/openssl'
            self.ps_path = '/usr/bin/ps'
            self.resize2fs_path = '/sbin/resize2fs'
            self.reboot_path = '/sbin/reboot'
            self.rmmod_path = '/usr/sbin/rmmod'
            self.service_path = '/usr/sbin/service'
            self.umount_path = '/usr/bin/umount'
            self.zypper_path = '/usr/bin/zypper'

    def rdmaupdate(self):
        check_install_result = self.check_install_hv_utils()
        if(check_install_result == CommonVariables.process_success):
            time.sleep(40)
            check_result = self.check_rdma()

            if(check_result == CommonVariables.UpToDate):
                return
            elif(check_result == CommonVariables.OutOfDate):
                nd_driver_version = self.get_nd_driver_version()
                rdma_package_installed_version = self.get_rdma_package_version()
                update_rdma_driver_result = self.update_rdma_driver(nd_driver_version, rdma_package_installed_version)
            elif(check_result == CommonVariables.DriverVersionNotFound):
                raise RdmaException(CommonVariables.driver_version_not_found)
            elif(check_result == CommonVariables.Unknown):
                raise RdmaException(CommonVariables.unknown_error)
        else:
            raise RdmaException(CommonVariables.install_hv_utils_failed)

    def check_rdma(self):
        nd_driver_version = self.get_nd_driver_version()
        if(nd_driver_version is None or nd_driver_version == ""):
            return CommonVariables.DriverVersionNotFound
        package_version = self.get_rdma_package_version()
        if(package_version is None or package_version == ""):
            return CommonVariables.OutOfDate
        else:
            # package_version would be like this :20150707_k3.12.28_4-3.1
            # nd_driver_version 140.0
            self.logger.log("nd_driver_version is " + str(nd_driver_version) + " package_version is " + str(package_version))
            if(nd_driver_version is not None):
                r = re.match(".+(%s)$" % nd_driver_version, package_version)# NdDriverVersion should be at the end of package version
                if not r :	#host ND version is the same as the package version, do an update
                    return CommonVariables.OutOfDate
                else:
                    return CommonVariables.UpToDate
            return CommonVariables.Unknown

    def reload_hv_utils(self):
        commandExecuter = CommandExecuter(self.logger)
        #clear /run/hv_kvp_daemon folder for the service could not be restart walkaround

        error,output = commandExecuter.RunGetOutput(self.rmmod_path + " hv_utils")	#find a way to force install non-prompt
        self.logger.log("rmmod hv_utils return code: " + str(error) + " output:" + str(output))
        if(error != CommonVariables.process_success):
            return CommonVariables.common_failed
        error,output = commandExecuter.RunGetOutput(self.modprobe_path + " hv_utils")	#find a way to force install non-prompt
        self.logger.log("modprobe hv_utils return code: " + str(error) + " output:" + str(output))
        if(error != CommonVariables.process_success):
            return CommonVariables.common_failed
        return CommonVariables.process_success

    def restart_hv_kvp_daemon(self):
        commandExecuter = CommandExecuter(self.logger)
        reload_result = self.reload_hv_utils()
        if(reload_result == CommonVariables.process_success):
            if(os.path.exists('/run/hv_kvp_daemon')):
                os.rmdir('/run/hv_kvp_daemon')
            error,output = commandExecuter.RunGetOutput(self.service_path + " hv_kvp_daemon start")	#find a way to force install non-prompt
            self.logger.log("service hv_kvp_daemon start return code: " + str(error) + " output:" + str(output))
            if(error != CommonVariables.process_success):
                return CommonVariables.common_failed
            return CommonVariables.process_success
        else:
            return CommonVariables.common_failed

    def check_install_hv_utils(self):
        commandExecuter = CommandExecuter(self.logger)
        error, output = commandExecuter.RunGetOutput(self.ps_path + " -ef")
        if(error != CommonVariables.process_success):
            return CommonVariables.common_failed
        else:
            r = re.search("hv_kvp_daemon", output)
            if r is None :
                self.logger.log("KVP deamon is not running, install it")
                error,output = commandExecuter.RunGetOutput(self.zypper_path + " -n install --force hyper-v")
                self.logger.log("install hyper-v return code: " + str(error) + " output:" + str(output))
                if(error != CommonVariables.process_success):
                    return CommonVariables.common_failed
                secondStageMarkConfig = SecondStageMarkConfig()
                secondStageMarkConfig.MarkIt()
                self.reboot_machine()
                return CommonVariables.process_success
            else :
                self.logger.log("KVP deamon is running")
                return CommonVariables.process_success

    def get_nd_driver_version(self):
        """
        if error happens, raise a RdmaException
        """
        try:
            with open("/var/lib/hyperv/.kvp_pool_0", "r") as f:
                lines = f.read()
            r = re.search("NdDriverVersion\0+(\d\d\d\.\d)", lines)
            if r is not None:
                NdDriverVersion = r.groups()[0]
                return NdDriverVersion #e.g.  NdDriverVersion = 142.0
            else :
                self.logger.log("Error: NdDriverVersion not found.")
                return None
        except Exception as e:
            errMsg = 'Failed to enable the extension with error: %s, stack trace: %s' % (str(e), traceback.format_exc())
            self.logger.log("Can't update status: " + errMsg)
            raise RdmaException(CommonVariables.nd_driver_detect_error)

    def get_rdma_package_version(self):
        """
        """
        commandExecuter = CommandExecuter(self.logger)
        error, output = commandExecuter.RunGetOutput(self.zypper_path + " info msft-lis-rdma-kmp-default")
        if(error == CommonVariables.process_success):
            r = re.search("Version: (\S+)", output)
            if r is not None:
                package_version = r.groups()[0]# e.g.  package_version is "20150707_k3.12.28_4-3.1.140.0"
                return package_version
            else:
                return None
        else:
            return None

    def update_rdma_driver(self, host_version, rdma_package_installed_version):
        """
        """
        commandExecuter = CommandExecuter(self.logger)
        error, output = commandExecuter.RunGetOutput(self.zypper_path + " lr -u")
        rdma_pack_result = re.search("msft-rdma-pack", output)
        if rdma_pack_result is None :
            self.logger.log("rdma_pack_result is None")
            error, output = commandExecuter.RunGetOutput(self.zypper_path + " ar https://drivers.suse.com/microsoft/Microsoft-LIS-RDMA/sle-12/updates msft-rdma-pack")
            #wait for the cache build.
            time.sleep(20)
            self.logger.log("error result is " + str(error) + " output is : " + str(output))
        else:
            self.logger.log("output is: "+str(output))
            self.logger.log("msft-rdma-pack found")
        returnCode,message = commandExecuter.RunGetOutput(self.zypper_path + " --no-gpg-checks refresh")
        self.logger.log("refresh repro return code is " + str(returnCode) + " output is: " + str(message))
        #install the wrapper package, that will put the driver RPM packages under /opt/microsoft/rdma
        returnCode,message = commandExecuter.RunGetOutput(self.zypper_path + " -n remove " + CommonVariables.wrapper_package_name)
        self.logger.log("remove wrapper package return code is " + str(returnCode) + " output is: " + str(message))
        returnCode,message = commandExecuter.RunGetOutput(self.zypper_path + " --non-interactive install --force " + CommonVariables.wrapper_package_name)
        self.logger.log("install wrapper package return code is " + str(returnCode) + " output is: " + str(message))
        r = os.listdir("/opt/microsoft/rdma")
        if r is not None :
            for filename in r :
                if re.match("msft-lis-rdma-kmp-default-\d{8}\.(%s).+" % host_version, filename) :
                    error,output = commandExecuter.RunGetOutput(self.zypper_path + " --non-interactive remove msft-lis-rdma-kmp-default")
                    self.logger.log("remove msft-lis-rdma-kmp-default result is " + str(error) + " output is: " + str(output))
                    self.logger.log("Installing RPM /opt/microsoft/rdma/" + filename)
                    error,output = commandExecuter.RunGetOutput(self.zypper_path + " --non-interactive install --force /opt/microsoft/rdma/%s" % filename)
                    self.logger.log("Install msft-lis-rdma-kmp-default result is " + str(error) + " output is: " + str(output))
                    if(error == CommonVariables.process_success):
                        self.reboot_machine()
                    else:
                        raise RdmaException(CommonVariables.package_install_failed)
        else:
            self.logger.log("RDMA drivers not found in /opt/microsoft/rdma")
            raise RdmaException(CommonVariables.package_not_found)

    def reboot_machine(self):
        self.logger.log("rebooting machine")
        commandExecuter = CommandExecuter(self.logger)
        commandExecuter.RunGetOutput(self.reboot_path)
