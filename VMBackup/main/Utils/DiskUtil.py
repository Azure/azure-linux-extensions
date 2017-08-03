#!/usr/bin/env python
#
# VMEncryption extension
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

import subprocess
import os
import os.path
import shlex
import sys
from subprocess import *
import shutil
import uuid
import glob
from common import DeviceItem
import HandlerUtil
import traceback

class DiskUtil(object):
    def __init__(self, patching, logger):
        self.patching = patching
        self.logger = logger

    def get_device_items_property(self, lsblk_path, dev_name, property_name):
        get_property_cmd = lsblk_path + " /dev/" + dev_name + " -b -nl -o NAME," + property_name
        get_property_cmd_args = shlex.split(get_property_cmd)
        get_property_cmd_p = Popen(get_property_cmd_args,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        output,err = get_property_cmd_p.communicate()
        lines = output.splitlines()
        for i in range(0,len(lines)):
            item_value_str = lines[i].strip()
            if(item_value_str != ""):
                disk_info_item_array = item_value_str.split()
                if(dev_name == disk_info_item_array[0]):
                    if(len(disk_info_item_array) > 1):
                        return disk_info_item_array[1]
        return None

    def get_device_items_sles(self,dev_path):
        self.logger.log("get_device_items_sles : getting the blk info from " + str(dev_path), True)
        device_items = []
        #first get all the device names
        if(dev_path is None):
            get_device_cmd = self.patching.lsblk_path + " -b -nl -o NAME"
        else:
            get_device_cmd = self.patching.lsblk_path + " -b -nl -o NAME " + dev_path
        get_device_cmd_args = shlex.split(get_device_cmd)
        p = Popen(get_device_cmd_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out_lsblk_output, err = p.communicate()
        lines = out_lsblk_output.splitlines()
        for i in range(0,len(lines)):
            item_value_str = lines[i].strip()
            if(item_value_str != ""):
                disk_info_item_array = item_value_str.split()
                device_item = DeviceItem()
                device_item.name = disk_info_item_array[0]
                device_items.append(device_item)

        for i in range(0,len(device_items)):
            device_item = device_items[i]
            device_item.file_system = self.get_device_items_property(lsblk_path=self.patching.lsblk_path,dev_name=device_item.name,property_name='FSTYPE')
            device_item.mount_point = self.get_device_items_property(lsblk_path=self.patching.lsblk_path,dev_name=device_item.name,property_name='MOUNTPOINT')
            device_item.label = self.get_device_items_property(lsblk_path=self.patching.lsblk_path,dev_name=device_item.name,property_name='LABEL')
            device_item.uuid = self.get_device_items_property(lsblk_path=self.patching.lsblk_path,dev_name=device_item.name,property_name='UUID')
            #get the type of device
            model_file_path = '/sys/block/' + device_item.name + '/device/model'
            if(os.path.exists(model_file_path)):
                with open(model_file_path,'r') as f:
                    device_item.model = f.read().strip()
            if(device_item.model == 'Virtual Disk'):
                self.logger.log("model is virtual disk", True)
                device_item.type = 'disk'
            if(device_item.type != 'disk'):
                partition_files = glob.glob('/sys/block/*/' + device_item.name + '/partition')
                if(partition_files is not None and len(partition_files) > 0):
                    self.logger.log("partition files exists", True)
                    device_item.type = 'part'
        return device_items

    def get_device_items_from_lsblk_list(self, lsblk_path, dev_path):
        self.logger.log("get_device_items_from_lsblk_list : getting the blk info from " + str(dev_path), True)
        device_items = []
        #first get all the device names
        if(dev_path is None):
            get_device_cmd = lsblk_path + " -b -nl -o NAME"
        else:
            get_device_cmd = lsblk_path + " -b -nl -o NAME " + dev_path
        get_device_cmd_args = shlex.split(get_device_cmd)
        p = Popen(get_device_cmd_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out_lsblk_output, err = p.communicate()
        lines = out_lsblk_output.splitlines()
        device_items_temp = []
        for i in range(0,len(lines)):
            item_value_str = lines[i].strip()
            if(item_value_str != ""):
                disk_info_item_array = item_value_str.split()
                device_item = DeviceItem()
                device_item.name = disk_info_item_array[0]
                device_items_temp.append(device_item)

        for i in range(0,len(device_items_temp)):
            device_item = device_items_temp[i]
            device_item.mount_point = self.get_device_items_property(lsblk_path=lsblk_path,dev_name=device_item.name,property_name='MOUNTPOINT')
            if (device_item.mount_point is not None):
                device_item.file_system = self.get_device_items_property(lsblk_path=lsblk_path,dev_name=device_item.name,property_name='FSTYPE')
                device_item.label = self.get_device_items_property(lsblk_path=lsblk_path,dev_name=device_item.name,property_name='LABEL')
                device_item.uuid = self.get_device_items_property(lsblk_path=lsblk_path,dev_name=device_item.name,property_name='UUID')
                device_item.type = self.get_device_items_property(lsblk_path=lsblk_path,dev_name=device_item.name,property_name='TYPE')
                device_items.append(device_item)
                self.logger.log("lsblk MOUNTPOINT=" + str(device_item.mount_point) + ", NAME=" + str(device_item.name) + ", TYPE=" + str(device_item.type) + ", FSTYPE=" + str(device_item.file_system) + ", LABEL=" + str(device_item.label) + ", UUID=" + str(device_item.uuid) + ", MODEL=" + str(device_item.model), True)
        return device_items

    def get_lsblk_pairs_output(self, lsblk_path, dev_path):
        self.logger.log("get_lsblk_pairs_output : getting the blk info from " + str(dev_path) + " using lsblk_path " + str(lsblk_path), True)
        out_lsblk_output = None
        error_msg = None
        is_lsblk_path_wrong = False
        try:
            if(dev_path is None):
                p = Popen([str(lsblk_path), '-b', '-n','-P','-o','NAME,TYPE,FSTYPE,MOUNTPOINT,LABEL,UUID,MODEL,SIZE'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            else:
                p = Popen([str(lsblk_path), '-b', '-n','-P','-o','NAME,TYPE,FSTYPE,MOUNTPOINT,LABEL,UUID,MODEL,SIZE',dev_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except Exception as e:
            errMsg = 'Exception in lsblk command, error: %s, stack trace: %s' % (str(e), traceback.format_exc())
            self.logger.log(errMsg, True, 'Error')
            is_lsblk_path_wrong = True
        if is_lsblk_path_wrong == False :
            out_lsblk_output, err = p.communicate()
            out_lsblk_output = str(out_lsblk_output)    
            error_msg = str(err)
            if(error_msg is not None and error_msg.strip() != ""):
                self.logger.log(str(err), True)
        return is_lsblk_path_wrong, out_lsblk_output, error_msg
    
    def get_which_command_result(self, program_to_locate):
        self.logger.log("getting the which info for  " + str(program_to_locate), True)
        out_which_output = None
        error_msg = None
        try:
            p = Popen(['which', str(program_to_locate)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out_which_output, err = p.communicate()
            out_which_output = str(out_which_output)
            error_msg = str(err)
            if(error_msg is not None and error_msg.strip() != ""):
                self.logger.log(str(err), True)
            self.logger.log("which command result :" + str(out_which_output), True)
            if (out_which_output is not None):
                out_which_output = out_which_output.splitlines()[0]
        except Exception as e:
            errMsg = 'Exception in which command, error: %s, stack trace: %s' % (str(e), traceback.format_exc())
            self.logger.log(errMsg, True, 'Error')
        return out_which_output, error_msg

    def get_device_items(self, dev_path):
        if(self.patching.distro_info[0].lower() == 'suse' and self.patching.distro_info[1] == '11'):
            return self.get_device_items_sles(dev_path)
        else:
            self.logger.log("getting the blk info from " + str(dev_path), True)
            device_items = []
            lsblk_path = self.patching.lsblk_path
            # Get lsblk command output using lsblk_path as self.patching.lsblk_path
            is_lsblk_path_wrong, out_lsblk_output, error_msg = self.get_lsblk_pairs_output(lsblk_path, dev_path)
            # if lsblk_path was wrong, use /bin/lsblk or usr/bin/lsblk based on self.patching.usr_flag to get lsblk command output again for centos/redhat distros
            if (is_lsblk_path_wrong == True) and (self.patching.distro_info[0].lower() == 'centos' or self.patching.distro_info[0].lower() == 'redhat'):
                if self.patching.usr_flag == 1:
                    self.logger.log("lsblk path is wrong, removing /usr prefix", True, 'Warning')
                    lsblk_path = "/bin/lsblk"
                else:
                    self.logger.log("lsblk path is wrong, adding /usr prefix", True, 'Warning')
                    lsblk_path = "/usr/bin/lsblk"
                is_lsblk_path_wrong, out_lsblk_output, error_msg = self.get_lsblk_pairs_output(lsblk_path, dev_path)
            # if lsblk_path was still wrong, lsblk_path using "which" command
            if (is_lsblk_path_wrong == True):
                self.logger.log("lsblk path is wrong. finding path using which command", True, 'Warning')
                out_which_output, which_error_msg = self.get_which_command_result('lsblk')
                # get lsblk command output
                if (out_which_output is not None):
                     lsblk_path = str(out_which_output)
                     is_lsblk_path_wrong, out_lsblk_output, error_msg = self.get_lsblk_pairs_output(lsblk_path, dev_path)
            # if error_msg contains "invalid option", then get device_items using method get_device_items_from_lsblk_list
            if (error_msg is not None and error_msg.strip() != "" and 'invalid option' in error_msg):
                device_items = self.get_device_items_from_lsblk_list(lsblk_path, dev_path)
            # else get device_items from parsing the lsblk command output
            elif (out_lsblk_output is not None):
                lines = out_lsblk_output.splitlines()
                for i in range(0,len(lines)):
                    item_value_str = lines[i].strip()
                    if(item_value_str != ""):
                        disk_info_item_array = item_value_str.split()
                        device_item = DeviceItem()
                        disk_info_item_array_length = len(disk_info_item_array)
                        for j in range(0, disk_info_item_array_length):
                            disk_info_property = disk_info_item_array[j]
                            property_item_pair = disk_info_property.split('=')

                            if(property_item_pair[0] == 'NAME'):
                                device_item.name = property_item_pair[1].strip('"')

                            if(property_item_pair[0] == 'TYPE'):
                                device_item.type = property_item_pair[1].strip('"')

                            if(property_item_pair[0] == 'FSTYPE'):
                                device_item.file_system = property_item_pair[1].strip('"')
                        
                            if(property_item_pair[0] == 'MOUNTPOINT'):
                                device_item.mount_point = property_item_pair[1].strip('"')

                            if(property_item_pair[0] == 'LABEL'):
                                device_item.label = property_item_pair[1].strip('"')

                            if(property_item_pair[0] == 'UUID'):
                                device_item.uuid = property_item_pair[1].strip('"')

                            if(property_item_pair[0] == 'MODEL'):
                                device_item.model = property_item_pair[1].strip('"')

                        self.logger.log("lsblk MOUNTPOINT=" + str(device_item.mount_point) + ", NAME=" + str(device_item.name) + ", TYPE=" + str(device_item.type) + ", FSTYPE=" + str(device_item.file_system) + ", LABEL=" + str(device_item.label) + ", UUID=" + str(device_item.uuid) + ", MODEL=" + str(device_item.model), True)
                        
                        if(device_item.mount_point is not None and device_item.mount_point != "" and device_item.mount_point != " "):
                            device_items.append(device_item)
            return device_items

    def get_mount_command_output(self, mount_path):
        self.logger.log("getting the mount info using mount_path " + str(mount_path), True)
        out_mount_output = None
        error_msg = None
        is_mount_path_wrong = False
        try:
            p = Popen([str(mount_path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except Exception as e:
            errMsg = 'Exception in mount command, error: %s, stack trace: %s' % (str(e), traceback.format_exc())
            self.logger.log(errMsg, True, 'Error')
            is_mount_path_wrong = True
        if is_mount_path_wrong == False :
            out_mount_output, err = p.communicate()
            out_mount_output = str(out_mount_output)
            error_msg = str(err)
            if(error_msg is not None and error_msg.strip() != ""):
                self.logger.log(str(err), True)
        return is_mount_path_wrong, out_mount_output, error_msg

    def get_mount_points(self):
        mount_points = []
        fs_types = []
        out_mount_output = self.get_mount_output()
        if (out_mount_output is not None):
            #Extract the list of mnt_point in order
            lines = out_mount_output.splitlines()
            for line in lines:
                line = line.strip()
                if(line != ""):
                    mountPrefixStr = " on /"
                    prefixIndex = line.find(mountPrefixStr)
                    if(prefixIndex >= 0):
                        mountpointStart = prefixIndex + len(mountPrefixStr) - 1
                        fstypePrefixStr = " type "
                        mountpointEnd = line.find(fstypePrefixStr, mountpointStart)
                        if(mountpointEnd >= 0):
                            mount_point = line[mountpointStart:mountpointEnd]
                            fs_type = ""
                            fstypeStart = line.find(fstypePrefixStr) + len(fstypePrefixStr) - 1
                            if(line.find(fstypePrefixStr) >= 0):
                                fstypeEnd = line.find(" ", fstypeStart+1)
                                if(fstypeEnd >=0):
                                    fs_type = line[fstypeStart+1:fstypeEnd]
                            # If there is a duplicate, keep only the first instance
                            if(mount_point not in mount_points):
                                self.logger.log("mount command mount :" + str(mount_point) + ": and fstype :"+ str(fs_type) + ":", True) 
                                fs_types.append(fs_type)
                                mount_points.append(mount_point)
        for fstype in fs_types:
            if ("fuse" in fstype.lower() or "nfs" in fstype.lower() or "cifs" in fstype.lower()):
                HandlerUtil.HandlerUtility.add_to_telemetery_data("networkFSTypePresentInMount","True")
                break
        return mount_points, fs_types

    def get_mount_file_systems(self):
        out_mount_output = self.get_mount_output()
        file_systems_info = []
        if (out_mount_output is not None):
            lines = out_mount_output.splitlines()
            for line in lines:
                line = line.strip()
                if(line != ""):
                    file_system = line.split()[0]
                    mountPrefixStr = " on /"
                    prefixIndex = line.find(mountPrefixStr)
                    if(prefixIndex >= 0):
                        mountpointStart = prefixIndex + len(mountPrefixStr) - 1
                        fstypePrefixStr = " type "
                        mountpointEnd = line.find(fstypePrefixStr, mountpointStart)
                        if(mountpointEnd >= 0):
                            mount_point = line[mountpointStart:mountpointEnd]
                            fs_type = ""
                            fstypeStart = line.find(fstypePrefixStr) + len(fstypePrefixStr) - 1
                            if(line.find(fstypePrefixStr) >= 0):
                                fstypeEnd = line.find(" ", fstypeStart+1)
                                if(fstypeEnd >=0):
                                    fs_type = line[fstypeStart+1:fstypeEnd]
                            # If there is a duplicate, keep only the first instance
                    if (file_system,fs_type,mount_point) not in file_systems_info:
                        file_systems_info.append((file_system,fs_type,mount_point))
        return file_systems_info

    def get_mount_output(self):
        # Get the output on the mount command
        self.logger.log("getting the mount-points info using mount command ", True)
        mount_path = self.patching.mount_path
        is_mount_path_wrong, out_mount_output, error_msg = self.get_mount_command_output(mount_path)
        if (is_mount_path_wrong == True):
            if self.patching.usr_flag == 1:
                self.logger.log("mount path is wrong.removing /usr prefix", True, 'Warning')
                mount_path = "/bin/mount"
            else:
                self.logger.log("mount path is wrong.Adding /usr prefix", True, 'Warning')
                mount_path = "/usr/bin/mount"
            is_mount_path_wrong, out_mount_output, error_msg = self.get_mount_command_output(mount_path)
        # if mount_path was still wrong, mount_path using "which" command
        if (is_mount_path_wrong == True):
            self.logger.log("mount path is wrong. finding path using which command", True, 'Warning')
            out_which_output, which_error_msg = self.get_which_command_result('mount')
            # get mount command output
            if (out_which_output is not None):
                 mount_path = str(out_which_output)
                 is_mount_path_wrong, out_mount_output, error_msg = self.get_mount_command_output(mount_path)
        return out_mount_output

