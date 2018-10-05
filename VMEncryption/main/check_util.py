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
import urlparse
import re
from Common import CommonVariables

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
            self.logger.log('WARNING: total memory [' + str(memtotal) + 'kb] is less than 7GB')
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

    def check_kv_url(self, test_url, message):
        """basic sanity check of the key vault url"""
        expected = "https://{keyvault-name}.vault.azure.net/"

        if test_url is None:
            raise Exception(message + '\nNo URL supplied')

        try:
            parse_result = urlparse.urlparse(test_url)
        except:
            raise Exception(message + '\nMalformed URL: ' + test_url)

        if not (parse_result.scheme.lower() == "https" and \
                re.match('[a-zA-Z0-9\-]+\.vault\.azure\.net$', parse_result.netloc)):
            raise Exception('\n' + message + '\nActual: ' + test_url + '\nExpected: ' + expected + "\n")
        return

    def check_kv_id(self, test_id, message):
        """basic sanity check of the key vault id"""
        # more strict checking would validate the full key vault id format
        expected = "/subscriptions/{subid}/resourceGroups/{rgname}/providers/Microsoft.KeyVault/vaults/{vaultname}"

        if test_id is None:
            raise Exception(message + '\nNo Resource ID supplied')

        id_splits = test_id.lower().split('/')

        if not (len(id_splits) >= 9 and \
                id_splits[0] == "" and \
                id_splits[1] == "subscriptions" and \
                id_splits[2] != "" and \
                id_splits[3] == "resourcegroups" and \
                id_splits[4] != "" and \
                id_splits[5] == "providers" and \
                id_splits[6] == "microsoft.keyvault" and \
                id_splits[7] == "vaults" and \
                id_splits[8] != ""):
            raise Exception('\n' + message + '\nActual: ' + test_id + '\nExpected: ' + expected + "\n")
        return

    def validate_key_vault_params(self, public_settings):
        kek_url = public_settings.get(CommonVariables.KeyEncryptionKeyURLKey)
        kv_url = public_settings.get(CommonVariables.KeyVaultURLKey)
        kv_id = public_settings.get(CommonVariables.KeyVaultResourceIdKey)
        kek_kv_id = public_settings.get(CommonVariables.KekVaultResourceIdKey)
        kek_algorithm = public_settings.get(CommonVariables.KeyEncryptionAlgorithmKey)

        self.check_kv_url(kv_url, "Key Vault URL is required, but was missing or invalid")
        self.check_kv_id(kv_id, "Key Vault ID is required, but was missing or invalid")
        if kek_url:
            self.check_kv_url(kek_url, "A KEK URL was specified, but was invalid")
            self.check_kv_id(kek_kv_id, "A KEK URL was specified, but its KeyVault ID was invalid")
            if kek_algorithm not in CommonVariables.encryption_algorithms:
                if kek_algorithm:
                    raise Exception(
                        "The KEK encryption algorithm requested was not recognized")
                else:
                    self.logger.log(
                        "No KEK algorithm specified will default to {0}".format(
                            CommonVariables.default_encryption_algorithm))
        else:
            if kek_kv_id:
                raise Exception(
                    "The KEK KeyVault ID was specified but the KEK URL was missing")

    def validate_volume_type(self, public_settings):
        volume_type = public_settings.get(CommonVariables.VolumeTypeKey)
        supported_types = CommonVariables.SupportedVolumeTypes
        if not volume_type.lower() in map(lambda x: x.lower(), supported_types) :
            raise Exception("Unknown Volume Type: {0}, has to be one of {1}".format(volume_type, supported_types))

    def precheck_for_fatal_failures(self, public_settings):
        """ run all fatal prechecks, they should throw an exception if anything is wrong """
        self.validate_key_vault_params(public_settings)
        self.validate_volume_type(public_settings)


    def is_non_fatal_precheck_failure(self, public_settings):
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
