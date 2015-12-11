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
            self.rmmod_path = '/sbin/rmmod'
            self.umount_path = '/bin/umount'
            self.zypper_path = '/bin/zypper'
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
            self.rmmod_path = '/usr/sbin/rmmod'
            self.service_path = '/usr/sbin/service'
            self.umount_path = '/usr/bin/umount'
            self.zypper_path = '/usr/bin/zypper'

    def rmdaupdate(self):
        check_install_result = self.check_install_hv_utils()
        if(check_install_result == CommonVariables.process_success):
            time.sleep(40)
            check_result = self.check_rdma()

            if(check_result == CommonVariables.UpToDate):
                return
            elif(check_result == CommonVariables.OutOfDate):
                update_rdma_driver_result = self.update_rdma_driver()
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
                    return CommonVariables.OutofDate
                else:
                    return CommonVariables.UpToDate
            return CommonVariables.Unknown

    def check_install_hv_utils(self):
        commandExecuter = CommandExecuter(self.logger)
        error, output = commandExecuter.RunGetOutput(self.ps_path + " -ef")
        if(error != CommonVariables.process_success):
            return CommonVariables.common_failed
        else:
            r = re.search("hv_kvp_daemon", output)
            if not r :
                self.logger.log("KVP deamon is not running, install it")
                error,output = commandExecuter.RunGetOutput(self.zypper_path + " -n install -l hyper-v")
                self.logger.log("install hyper-v output:" + str(output))
                if(error != CommonVariables.process_success):
                    return CommonVariables.common_failed
                error,output = commandExecuter.RunGetOutput(self.rmmod_path + " hv_utils")	#find a way to force install non-prompt
                self.logger.log("rmmod hv_utils output:" + str(output))
                if(error != CommonVariables.process_success):
                    return CommonVariables.common_failed
                error,output = commandExecuter.RunGetOutput(self.modprobe_path + " hv_utils")	#find a way to force install non-prompt
                self.logger.log("modprobe hv_utils output:" + str(output))
                if(error != CommonVariables.process_success):
                    return CommonVariables.common_failed
                error,output = commandExecuter.RunGetOutput(self.service_path + " hv_kvp_daemon start ")	#find a way to force install non-prompt
                self.logger.log("service hv_kvp_daemon start output:" + str(output))
                if(error != CommonVariables.process_success):
                    return CommonVariables.common_failed
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
            r = re.match("NdDriverVersion\0+(\d\d\d\.\d)", lines)
            if r :
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
            if r :
                package_version = r.groups()[0]# e.g.  package_version is "20150707_k3.12.28_4-3.1.140.0"
                return package_version
            else:
                return None
        else:
            return None

    def update_rdma_driver(host_version):
        """
        """
        commandExecuter = CommandExecuter(self.logger)
        returnCode,message = commandExecuter.RunGetOutput(self.zypper_path + " -n remove " + CommonVariables.wrapper_package_name)
        returnCode,message = commandExecuter.RunGetOutput(self.zypper_path + " --non-interactive install " + CommonVariables.wrapper_package_name)
        r = os.listdir("/opt/microsoft/rdma")
        if r :
            for filename in r :
                if re.match("msft-lis-rdma-kmp-default-\d{8}\.(%s).+" % host_version, filename) :
                    print "Installing RPM /opt/microsoft/rdma/" + filename
                    RunGetOutput(self.zypper_path + " --non-interactive install /opt/microsoft/rdma/%s" % filename)
                    return
        else:
            print "RDMA drivers not found in /opt/microsoft/rdma"
