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
import re
import json
import traceback
from Common import CommonVariables
from MetadataUtil import MetadataUtil
from CommandExecutor import CommandExecutor
from distutils.version import LooseVersion

try:
    from urllib.parse import urlparse #python3+
except ImportError:
    from urlparse import urlparse #python2

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

    def check_kv_url(self, test_kv_url, message):
        """basic sanity check of key vault url"""
        expected = "https://keyvault-name}.{vault-endpoint}"
        pattern = re.compile(r'^https://([a-zA-Z0-9\-]+)[\.]([a-zA-Z0-9\-\.]+)(:443)?([/]?)$')
        if not (test_kv_url and pattern.match(test_kv_url)):
            raise Exception('\n' + message + '\nActual: ' + test_kv_url + '\nExpected: ' + expected + "\n")
        return

    def check_kek_url(self, test_kek_url, message):
        """basic sanity check of the key vault key url"""
        expected = "https://{keyvault-name}.{vault-endpoint}/keys/{object-name}/{object-version}"
        pattern = re.compile(r'^https://([a-zA-Z0-9\-]+)[\.]([a-zA-Z0-9\-\.]+)(:443)?/keys/([a-zA-Z0-9\-]+)/([a-zA-Z0-9]+)([/]?)$', re.IGNORECASE)
        if not (test_kek_url and pattern.match(test_kek_url)):
            raise Exception('\n' + message + '\nActual: ' + test_kek_url + '\nExpected: ' + expected + "\n")
        return

    def check_mhsm_url(self, test_mhsm_url, message):
        """basic sanity check of the MHSM url"""
        expected = "https://managedhsm-name}.{mhsm-endpoint}"
        pattern = re.compile(r'https://(.)+\\.(managedhsm)\\.(.)+(:443)?\\/keys/[^\\/]+\\/[0-9a-zA-Z]+$', re.IGNORECASE)
        if not (test_mhsm_url and pattern.match(test_mhsm_url)):
            raise Exception('\n' + message + '\nActual: ' + test_mhsm_url + '\nExpected: ' + expected + "\n")
        return

    def check_kv_id(self, test_kv_id, message):
        """basic sanity check of the key vault id"""
        expected = "/subscriptions/{subid}/resourceGroups/{rgname}/providers/Microsoft.KeyVault/vaults/{vaultname}"
        pattern = re.compile(r'^/subscriptions/([a-zA-Z0-9\-]+)/resourceGroups/([-\w\._\(\)]+)/providers/Microsoft.KeyVault/vaults/([a-zA-Z0-9\-\_]+)(/)?$',re.IGNORECASE)
        if not (test_kv_id and pattern.match(test_kv_id)):
            raise Exception('\n' + message + '\nActual: ' + test_kv_id + '\nExpected: ' + expected + "\n")
        return

    def check_mhsm_id(self, test_mhsm_id, message):
        """basic sanity check of the mhsm resource id"""
        expected = "/subscriptions/{subid}/resourceGroups/{rgname}/providers/Microsoft.KeyVault/managedHSM/{mhsmname}"
        pattern = re.compile(r'^/subscriptions/([a-zA-Z0-9\-]+)/resourceGroups/([-\w\._\(\)]+)/providers/Microsoft.KeyVault/managedHSM/([a-zA-Z0-9\-\_]+)(/)?$',re.IGNORECASE)
        if not (test_mhsm_id and pattern.match(test_mhsm_id)):
            raise Exception('\n' + message + '\nActual: ' + test_mhsm_id + '\nExpected: ' + expected + "\n")
        return

    def get_kv_id_name(self, kv_id):
        """extract key vault name from KV ID"""
        if kv_id:
            match = re.search(r'^/subscriptions/([a-zA-Z0-9\-]+)/resourceGroups/([-\w\._\(\)]+)/providers/Microsoft.KeyVault/vaults/([a-zA-Z0-9\-\_]+)(/)?$', kv_id, re.IGNORECASE)
            if match:
                return match.group(3)
        return

    def get_kv_url_name(self, kv_url):
        """extract key vault name from KV URL"""
        if kv_url:
            match = re.search(r'^https://([a-zA-Z0-9\-]+)[\.]([a-zA-Z0-9\-\.]+)(:443)?([/]?)$', kv_url)
            if match:
                return match.group(1)
        return

    def get_kek_url_name(self, kek_url):
        """extract key vault name from kek url"""
        if kek_url:
            match = re.search(r'^https://([a-zA-Z0-9\-]+)[\.]([a-zA-Z0-9\-\.]+)(:443)?/keys/([a-zA-Z0-9\-]+)/([a-zA-Z0-9]+)([/]?)$', kek_url, re.IGNORECASE)
            if match:
                return match.group(1)
        return

    def check_kv_name(self, kv_id, kv_url, message):
        """ensure KV ID vault name matches KV URL"""
        if not (kv_id and kv_url and self.get_kv_id_name(kv_id) and self.get_kv_url_name(kv_url) and self.get_kv_id_name(kv_id).lower() == self.get_kv_url_name(kv_url).lower()):
            raise Exception('\n' + message + '\nKey Vault ID: ' + kv_id + '\nKey Vault URL: ' + kv_url + '\n')
        return

    def check_kek_name(self, kek_kv_id, kek_url, message):
        """ensure KEK KV ID vault name matches KEK URL vault name"""
        if not (kek_kv_id and kek_url and self.get_kv_id_name(kek_kv_id) and self.get_kek_url_name(kek_url) and self.get_kv_id_name(kek_kv_id).lower() == self.get_kek_url_name(kek_url).lower()):
            raise Exception('\n' +message + '\nKEK Key Vault ID: ' + kek_kv_id + '\nKEK URL: ' + kek_url + '\n')
        return

    def check_mhsm_name(self, mhsm_id, mhsm_url, message):
        """ensure ManagedHSM ID vault name matches ManagedHSM URL vault name"""
        if not (mhsm_id and mhsm_url and self.get_kv_id_name(mhsm_id) and self.get_kek_url_name(mhsm_url) and self.get_kv_id_name(mhsm_id).lower() == self.get_kek_url_name(mhsm_url).lower()):
            raise Exception('\n' +message + '\nManagedHSM ID: ' + mhsm_id + '\nManagedHSM URL: ' + mhsm_url + '\n')
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

        self.check_kv_id(kv_id, "A KeyVault ID is required, but is missing or invalid")
        self.check_kv_url(kv_url, "A KeyVault URL is required, but is missing or invalid")
        self.check_kv_name(kv_id, kv_url, "A KeyVault ID and KeyVault URL were provided, but their key vault names did not match")
        if kek_url:
            self.check_kv_id(kek_kv_id, "A KEK URL was specified, but its KEK KeyVault ID was missing or invalid")
            self.check_kek_url(kek_url, "A KEK URL was specified, but it was invalid")
            self.check_kek_name(kek_kv_id, kek_url, "A KEK ID and KEK URL were provided, but their key vault names did not match")
            if kek_algorithm:
                if kek_algorithm.upper() not in CommonVariables.encryption_algorithms:
                    raise Exception("The KEK encryption algorithm requested was not recognized")
            else:
                kek_algorithm = CommonVariables.default_encryption_algorithm
                self.logger.log("No KEK algorithm specified, defaulting to {0}".format(kek_algorithm))
        else:
            if kek_kv_id:
                raise Exception(
                    "The KEK KeyVault ID was specified but the KEK URL was missing")

    def validate_volume_type(self, public_settings, DistroPatcher=None):
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
            if DistroPatcher is not None and DistroPatcher.support_online_encryption:
                self.logger.log("VMSS OS Disk Encryption Supported.")
                supported_volume_types = CommonVariables.SupportedVolumeTypes
            else:
                supported_volume_types = CommonVariables.SupportedVolumeTypesVMSS
        else:
            supported_volume_types = CommonVariables.SupportedVolumeTypes

        if not volume_type.lower() in [x.lower() for x in supported_volume_types] :
            raise Exception("Unknown Volume Type: {0}, has to be one of {1}".format(volume_type, supported_volume_types))

    def validate_lvm_os(self, public_settings, DistroPatcher):
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

        
        if DistroPatcher.support_online_encryption:
            self.logger.log('Distro supports online encryption. Skipping LVM validation.')
            return

        #  run lvm check if volume type, encryption operation were specified and OS type is LVM
        detected = False
        # first, check if the root OS volume type is LVM
        if ( encryption_operation and volume_type and 
             os.system("lsblk -o TYPE,MOUNTPOINT | grep lvm | grep -q '/$'") == 0):
            # next, check that all required logical volume names exist (swaplv not required)
            lvlist = ['rootvg-tmplv',
                      'rootvg-usrlv',
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
        distro_name = distro_name.replace('ubuntu','Ubuntu') # to upper if needed
        distro_version = DistroPatcher.distro_info[1]
        supported_os_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'SupportedOS.json')
        with open(supported_os_file) as json_file:
            data = json.load(json_file)
            if distro_name in data:
                versions = data[distro_name]
                for version in versions:
                    if distro_version.startswith(version['Version']):
                        if 'MinSupportedVersion' in version and LooseVersion(distro_version) < LooseVersion(version['MinSupportedVersion']):
                            raise Exception('Minimum supported version for distro {0} is {1}.'.format(distro_name, version['MinSupportedVersion']))
                        if 'Kernel' in version and LooseVersion(DistroPatcher.kernel_version) < LooseVersion(version['Kernel']):
                            raise Exception('Kernel version {0} is not supported. Upgrade to kernel version {1}'.format(DistroPatcher.kernel_version, version['Kernel']))
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
        self.validate_volume_type(public_settings, DistroPatcher)
        self.validate_lvm_os(public_settings, DistroPatcher)
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

    def pre_Initialization_Check(self,imdsStoredResults,iMDSUtil):
        '''This function is checking the VM compatibility for ADE'''
        self.logger.log('Pre initialization check Start.')
        try:
            security_type = None
            if imdsStoredResults.config_file_exists() and imdsStoredResults.get_security_type() != None:
                security_type = imdsStoredResults.get_security_type()
                self.logger.log("reading from imds stored results, security type is {0}.".format(security_type))
            else:
                security_type = iMDSUtil.get_vm_security_type()
                #imds does not store security type for Standard or Basic type.
                if(security_type=='' or security_type == None):
                    security_type= CommonVariables.Standard
                self.logger.log("reading from imds, security type is {0}.".format(security_type))
            supported_security_types = security_type.lower() in [x.lower() for x in CommonVariables.supported_security_types]
            if not supported_security_types:
                raise Exception("Unknown VM security type: {0}, has to be one of {1}".format(security_type,CommonVariables.supported_security_types))
            imdsStoredResults.security_type = security_type
            imdsStoredResults.commit()
        except Exception as ex:
            message = "Pre-initialization check: Exception thrown during IMDS call. \
                       exception:{0}, \n stack-trace: {1}".format(str(ex),traceback.format_exc())
            self.logger.log(msg=message,level=CommonVariables.ErrorLevel)
            raise Exception(message)
        if security_type.lower() ==  CommonVariables.ConfidentialVM.lower():
            message = "Pre-initialization check: ADE flow is blocked for confidential VM."
            self.logger.log(msg=message,level=CommonVariables.ErrorLevel)
            raise Exception(message) 
        self.logger.log('Pre initialization check End.')