#!/usr/bin/env python
#
# *********************************************************
# Copyright (c) Microsoft. All rights reserved.
#
# Apache 2.0 License
#
# You may obtain a copy of the License at
# http:#www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied. See the License for the specific language governing
# permissions and limitations under the License.
#
# *********************************************************

"""This module checks validity of the environment prior to disk encryption"""

import os
import os.path

class CheckUtil(object):
    """Checks compatibility for disk encryption"""
    def __init__(self, logger):
        self.logger = logger

    def is_app_compat_issue_detected(self):
        """check for the existence of applications that enable is not yet compatible with"""
        detected = False
        dirs = ['./usr/sap']
        files = ['/etc/init.d/mongodb',
                 '/etc/init.d/cassandra',
                 '/etc/init.d/docker',
                 '/opt/Symantec/symantec_antivirus']
        for testdir in dirs:
            if os.path.isdir(testdir):
                self.logger.log('WARNING: likely app compat issue [' + testdir + ']')
                detected = True
        for testfile in files:
            if os.path.isfile(testfile):
                self.logger.log('WARNING: likely app compat issue [' + testfile + ']')
                detected = True
        return detected

    def is_insufficient_memory(self):
        """check if memory total is greater than or equal to the recommended minimum size"""
        minsize = 7000000
        memtotal = int(os.popen("grep MemTotal /proc/meminfo | grep -o -E [0-9]+").read())
        if memtotal < minsize:
            self.logger.log('WARNING: total memory [' + memtotal + 'kb] is less than 7GB')
            return True
        return False

    def is_unsupported_mount_scheme(self):
        """ check for data disks mounted under /mnt and for recursively mounted
            data disks such as /mnt/data1, /mnt/data2, or /data3 + /data3/data4 """
        detected = False
        ignorelist = ['/', '/dev', '/proc', '/run', '/sys', '/sys/fs/cgroup']
        mounts = []
        with open('/proc/mounts') as infile:
            for line in infile:
                mountpoint = line.split()[1]
                if mountpoint not in ignorelist:
                    mounts.append(line.split()[1])
        for mnt1 in mounts:
            for mnt2 in mounts:
                if (mnt1 != mnt2) and (mnt2.startswith(mnt1)):
                    self.logger.log('WARNING: unsupported mount scheme [' + mnt1 + ' ' + mnt2 + ']')
                    detected = True
        return detected

    def is_invalid_lvm_os(self):
        """ if an lvm os disk is present, check the lv names """
        detected = False
        # run checks only when the root OS volume type is LVM
        if os.system("lsblk -o TYPE,MOUNTPOINT | grep lvm | grep -q '/$'") == 0:
            # LVM OS volume detected, check that required logical volume names exist
            lvlist = ['rootvg-tmplv',
                      'rootvg-usrlv',
                      'rootvg-swaplv',
                      'rootvg-optlv',
                      'rootvg-homelv',
                      'rootvg-varlv',
                      'rootvg-rootlv']
            for lvname in lvlist:
                if not os.system("lsblk -o NAME | grep -q '" + lvname + "'") == 0:
                    self.logger.log('WARNING: LVM OS scheme is missing LV [' + lvname + ']')
                    detected = True
        return detected

    def is_precheck_failure(self):
        """ run all prechecks """
        detected = False
        if self.is_app_compat_issue_detected():
            detected = True
            self.logger.log("PRECHECK: Likely app compat issue detected")
        if self.is_insufficient_memory():
            detected = True
            self.logger.log("PRECHECK: Low memory condition detected")
        if self.is_unsupported_mount_scheme():
            detected = True
            self.logger.log("PRECHECK: Unsupported mount scheme detected")
        if self.is_invalid_lvm_os():
            detected = True
            self.logger.log("PRECHECK: Invalid LVM OS scheme detected")
        return detected
