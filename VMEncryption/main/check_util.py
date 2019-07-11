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
import json
from Common import CommonVariables
from MetadataUtil import MetadataUtil
from CommandExecutor import CommandExecutor
from distutils.version import LooseVersion

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

    def check_kv_url(self, test_url, message):
        """basic sanity check of the key vault url"""

        if test_url is None:
            raise Exception(message + '\nNo URL supplied')

        try:
            parse_result = urlparse.urlparse(test_url)
        except:
            raise Exception(message + '\nMalformed URL: ' + test_url)

        if not parse_result.scheme.lower() == "https" :
            raise Exception('\n' + message + '\n URL should be https: ' + test_url + "\n")

        if not parse_result.netloc:
            raise Exception(message + '\nMalformed URL: ' + test_url)

        # Don't bother with explicit dns check, the host already does and should start returning better error messages.

        # dns_suffix_list = ["vault.azure.net", "vault.azure.cn", "vault.usgovcloudapi.net", "vault.microsoftazure.de"]
        # Add new suffixes here when a new national cloud is introduced.
        # Relevant link: https://docs.microsoft.com/en-us/azure/key-vault/key-vault-access-behind-firewall#key-vault-operations

        # dns_match = False
        # for dns_suffix in dns_suffix_list:
        #     escaped_dns_suffix = dns_suffix.replace(".","\.")
        #     if re.match('[a-zA-Z0-9\-]+\.' + escaped_dns_suffix + '(:443)?$', parse_result.netloc):
        #         # matched a valid dns, set matched to true
        #         dns_match = True
        # if not dns_match:
        #     raise Exception('\n' + message + '\nProvided URL does not match known valid URL formats: ' + \
        #         "\n\tProvided URL: " + test_url + \
        #         "\n\tKnown valid formats:\n\t\t" + \
        #         "\n\t\t".join(["https://<keyvault-name>." + dns_suffix + "/" for dns_suffix in dns_suffix_list]) )

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

        encryption_operation = public_settings.get(CommonVariables.EncryptionEncryptionOperationKey)
        if encryption_operation not in [CommonVariables.EnableEncryption, CommonVariables.EnableEncryptionFormat, CommonVariables.EnableEncryptionFormatAll]:
            # No need to check the KV urls if its not an encryption operation
            return

        kek_url = public_settings.get(CommonVariables.KeyEncryptionKeyURLKey)
        kv_url = public_settings.get(CommonVariables.KeyVaultURLKey)
        kv_id = public_settings.get(CommonVariables.KeyVaultResourceIdKey)
        kek_kv_id = public_settings.get(CommonVariables.KekVaultResourceIdKey)
        kek_algorithm = public_settings.get(CommonVariables.KeyEncryptionAlgorithmKey)

        self.check_kv_url(kv_url, "Encountered an error while checking the Key Vault URL")
        self.check_kv_id(kv_id, "Enountered an error while checking the Key Vault ID")
        if kek_url:
            self.check_kv_url(kek_url, "A KEK URL was specified, but was invalid")
            self.check_kv_id(kek_kv_id, "A KEK URL was specified, but its KeyVault ID was invalid")
            if kek_algorithm is None or kek_algorithm.lower() not in [algo.lower() for algo in CommonVariables.encryption_algorithms]:
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
        encryption_operation = public_settings.get(CommonVariables.EncryptionEncryptionOperationKey)
        if encryption_operation in [CommonVariables.QueryEncryptionStatus]:
            # No need to validate volume type for Query Encryption Status operation
            self.logger.log(
                "Ignore validating volume type for {0}".format(
                CommonVariables.QueryEncryptionStatus))
            return

        volume_type = public_settings.get(CommonVariables.VolumeTypeKey)

        # get supported volume types
        instance = MetadataUtil(self.logger)
        if instance.is_vmss():
            supported_volume_types = CommonVariables.SupportedVolumeTypesVMSS
        else:
            supported_volume_types = CommonVariables.SupportedVolumeTypes

        if not volume_type.lower() in map(lambda x: x.lower(), supported_volume_types) :
            raise Exception("Unknown Volume Type: {0}, has to be one of {1}".format(volume_type, supported_volume_types))

    def validate_lvm_os(self, public_settings):
        encryption_operation = public_settings.get(CommonVariables.EncryptionEncryptionOperationKey)
        if not encryption_operation:
            self.logger.log("LVM OS validation skipped (no encryption operation)")
            return
        elif encryption_operation.lower() == CommonVariables.QueryEncryptionStatus.lower():
            self.logger.log("LVM OS validation skipped (Encryption Operation: QueryEncryptionStatus)")
            return

        volume_type = public_settings.get(CommonVariables.VolumeTypeKey)
        if not volume_type:
            self.logger.log("LVM OS validation skipped (no volume type)")
            return
        elif volume_type.lower() == CommonVariables.VolumeTypeData.lower():
            self.logger.log("LVM OS validation skipped (Volume Type: DATA)")
            return

        #  run lvm check if volume type, encryption operation were specified and OS type is LVM
        detected = False
        # first, check if the root OS volume type is LVM
        if ( encryption_operation and volume_type and 
             os.system("lsblk -o TYPE,MOUNTPOINT | grep lvm | grep -q '/$'") == 0):
            # next, check that all required logical volume names exist (swaplv not required)
            lvlist = ['rootvg-tmplv',
                      'rootvg-usrlv',
                      'rootvg-optlv',
                      'rootvg-homelv',
                      'rootvg-varlv',
                      'rootvg-rootlv']
            for lvname in lvlist:
                if not os.system("lsblk -o NAME | grep -q '" + lvname + "'") == 0:
                    self.logger.log('LVM OS scheme is missing LV [' + lvname + ']')
                    detected = True
        if detected:
            raise Exception("LVM OS disk layout does not satisfy prerequisites ( see https://aka.ms/adelvm )")

    def validate_vfat(self):
        """ Check for vfat module using modprobe and raise exception if not found """
        try:
            executor = CommandExecutor(self.logger)
            executor.Execute("modprobe vfat", True)
        except:
            raise RuntimeError('Incompatible system, prerequisite vfat module was not found.')

    def validate_memory_os_encryption(self, public_settings, encryption_status):
        is_enable_operation = False
        encryption_operation = public_settings.get(CommonVariables.EncryptionEncryptionOperationKey)
        if encryption_operation in [CommonVariables.EnableEncryption, CommonVariables.EnableEncryptionFormat, CommonVariables.EnableEncryptionFormatAll]:
            is_enable_operation = True
        volume_type = public_settings.get(CommonVariables.VolumeTypeKey)
        if is_enable_operation and not volume_type.lower() == CommonVariables.VolumeTypeData.lower() and encryption_status["os"] == "NotEncrypted":
            if self.is_insufficient_memory():
                raise Exception("Not enough memory for enabling encryption on OS volume. 8 GB memory is recommended.")

    def is_supported_os(self, public_settings, DistroPatcher, encryption_status):
        encryption_operation = public_settings.get(CommonVariables.EncryptionEncryptionOperationKey)
        if encryption_operation in [CommonVariables.QueryEncryptionStatus]:
            self.logger.log("Query encryption operation detected. Skipping OS encryption validation check.")
            return
        volume_type = public_settings.get(CommonVariables.VolumeTypeKey)
        # If volume type is data allow the operation (At this point we are sure a patch file for the distro exist)
        if volume_type.lower() == CommonVariables.VolumeTypeData.lower():
            self.logger.log("Volume Type is DATA. Skipping OS encryption validation check.")
            return
        # If OS volume is already encrypted just return (Should not break already encryted VM's)
        if encryption_status["os"] != "NotEncrypted":
            self.logger.log("OS volume already encrypted. Skipping OS encryption validation check.")
            return
        distro_name = DistroPatcher.distro_info[0]
        distro_version = DistroPatcher.distro_info[1]
        supported_os_file = os.path.join(os.getcwd(), 'main/SupportedOS.json')
        with open(supported_os_file) as json_file:
            data = json.load(json_file)
            if distro_name in data:
                versions = data[distro_name]
                for version in versions:
                    if distro_version.startswith(version['Version']):
                        if 'Kernel' in version and LooseVersion(DistroPatcher.kernel_version) < LooseVersion(version['Kernel']):
                            raise Exception('Kernel version {0} is not supported. Upgrade to kernel version {1}'.format(DistroPatcher.kernel_version, version['Kernel']))
                        else:
                            return
            raise Exception('Distro {0} {1} is not supported for OS encryption'.format(distro_name, distro_version))

    def validate_volume_type_for_enable(self, public_settings, existing_volume_type):
        encryption_operation = public_settings.get(CommonVariables.EncryptionEncryptionOperationKey)
        if not encryption_operation in [CommonVariables.EnableEncryption, CommonVariables.EnableEncryptionFormat, CommonVariables.EnableEncryptionFormatAll]:
            self.logger.log("Current operation is not an enable. Skipping volume type validation.")
            return
        if not existing_volume_type:
            self.logger.log('Existing volume type not found. First enable.')
            return
        volume_type = public_settings.get(CommonVariables.VolumeTypeKey)
        if volume_type.lower() == existing_volume_type.lower():
            self.logger.log('No change in volume type.')
            return
        if volume_type.lower() == CommonVariables.VolumeTypeAll.lower():
            self.logger.log('Upgrading volume type from {0} to {1}'.format(existing_volume_type, volume_type))
            return
        raise Exception('Moving from volume type {0} to volume type {1} is not allowed'.format(existing_volume_type, volume_type))

    def precheck_for_fatal_failures(self, public_settings, encryption_status, DistroPatcher, existing_volume_type):
        """ run all fatal prechecks, they should throw an exception if anything is wrong """
        self.validate_key_vault_params(public_settings)
        self.validate_volume_type(public_settings)
        self.validate_lvm_os(public_settings)
        self.validate_vfat()
        self.validate_memory_os_encryption(public_settings, encryption_status)
        self.is_supported_os(public_settings, DistroPatcher, encryption_status)
        self.validate_volume_type_for_enable(public_settings, existing_volume_type)

    def is_non_fatal_precheck_failure(self):
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
        return detected
