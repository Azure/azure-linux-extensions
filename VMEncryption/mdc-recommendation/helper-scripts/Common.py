#!/usr/bin/env python
#
# Azure Disk Encryption For Linux extension
#
# Copyright 2016 Microsoft Corporation
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

class CommonVariables:
    dev_mapper_root = '/dev/mapper/'
    osmapper_name = 'osencrypt'
    format_supported_file_systems = ['ext4', 'ext3', 'ext2', 'xfs', 'btrfs']
    azure_symlinks_dir = '/dev/disk/azure'
    cloud_symlinks_dir = '/dev/disk/cloud'

class DeviceItem(object):
    def __init__(self):
        # NAME,TYPE,FSTYPE,MOUNTPOINT,LABEL,UUID,MODEL,SIZE,MAJ:MIN
        self.name = None
        self.type = None
        self.file_system = None
        self.mount_point = None
        self.label = None
        self.uuid = None
        self.model = None
        self.size = None
        self.majmin = None
        self.device_id = None

    def __str__(self):
        return ("name:" + str(self.name) + " type:" + str(self.type) +
                " fstype:" + str(self.file_system) + " mountpoint:" + str(self.mount_point) +
                " label:" + str(self.label) + " model:" + str(self.model) +
                " size:" + str(self.size) + " majmin:" + str(self.majmin) +
                " device_id:" + str(self.device_id))

class LvmItem(object):
    def __init__(self):
        # lv_name,vg_name,lv_kernel_major,lv_kernel_minor
        self.lv_name = None
        self.vg_name = None
        self.lv_kernel_major = None
        self.lv_kernel_minor = None

    def __str__(self):
        return ("lv_name:" + str(self.lv_name) + " vg_name:" + str(self.vg_name) +
                " lv_kernel_major:" + str(self.lv_kernel_major) + " lv_kernel_minor:" + str(self.lv_kernel_minor))

