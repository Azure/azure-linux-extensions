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

class DiskUtil(object):
    def __init__(self, patching, logger):
        self.patching = patching
        self.logger = logger

    def get_device_items_property(self, dev_name, property_name):
        get_property_cmd = self.patching.lsblk_path + " /dev/" + dev_name + " -b -nl -o NAME," + property_name
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
        self.logger.log(msg=("getting the blk info from " + str(dev_path)))
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
            device_item.file_system = self.get_device_items_property(dev_name=device_item.name,property_name='FSTYPE')
            device_item.mount_point = self.get_device_items_property(dev_name=device_item.name,property_name='MOUNTPOINT')
            device_item.label = self.get_device_items_property(dev_name=device_item.name,property_name='LABEL')
            device_item.uuid = self.get_device_items_property(dev_name=device_item.name,property_name='UUID')
            #get the type of device
            model_file_path = '/sys/block/' + device_item.name + '/device/model'
            if(os.path.exists(model_file_path)):
                with open(model_file_path,'r') as f:
                    device_item.model = f.read().strip()
            if(device_item.model == 'Virtual Disk'):
                self.logger.log(msg="model is virtual disk")
                device_item.type = 'disk'
            if(device_item.type != 'disk'):
                partition_files = glob.glob('/sys/block/*/' + device_item.name + '/partition')
                if(partition_files is not None and len(partition_files) > 0):
                    self.logger.log(msg="partition files exists")
                    device_item.type = 'part'
        return device_items

    def get_device_items(self, dev_path):
        if(self.patching.distro_info[0].lower() == 'suse' and self.patching.distro_info[1] == '11'):
            return self.get_device_items_sles(dev_path)
        else:
            self.logger.log(msg=("getting the blk info from " + str(dev_path)))
            device_items = []
            if(dev_path is None):
                p = Popen([self.patching.lsblk_path, '-b', '-n','-P','-o','NAME,TYPE,FSTYPE,MOUNTPOINT,LABEL,UUID,MODEL,SIZE'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            else:
                p = Popen([self.patching.lsblk_path, '-b', '-n','-P','-o','NAME,TYPE,FSTYPE,MOUNTPOINT,LABEL,UUID,MODEL,SIZE',dev_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out_lsblk_output, err = p.communicate()
            out_lsblk_output = str(out_lsblk_output)
            error_msg = str(err)
            if(error_msg is not None and error_msg.strip() != ""):
                self.logger.log(msg=str(err))
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

                    device_items.append(device_item)
            return device_items
