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
    utils_path_name = 'Utils'
    extension_name = 'AzureDiskEncryptionForLinux'
    extension_version = '1.1.0.33'
    extension_type = extension_name
    extension_media_link = 'https://amextpaas.blob.core.windows.net/prod/' + extension_name + '-' + str(extension_version) + '.zip'
    extension_label = 'Azure Disk Encryption For Linux VMSS'
    extension_description = extension_label
    extension_shim_filename = "extension_shim.sh"

    """
    wire protocol message format
    """
    encryption_key_file_name = 'LinuxPassPhraseFileName'
    encryption_key_mount_point = '/mnt/azure_bek_disk'
    encryption_algorithms = ['RSA-OAEP', 'RSA-OAEP-256', 'RSA1_5']
    default_encryption_algorithm = 'RSA-OAEP'
    encryption_settings_file_name_pattern = 'settings_{0}.json'
    encryption_settings_counter_file = 'counter.txt'
    encryption_settings_counter_path = encryption_key_mount_point + '/' + encryption_settings_counter_file

    wireserver_endpoint = "http://169.254.169.254:80/machine?comp=diskEncryptionData"
    wireprotocol_msg_headers = {
        "Content-Type": "text/xml",
        "x-ms-version": "2015-04-05"
    }
    wireprotocol_msg_template_v2 = """<?xml version="1.0"?>
    <DiskEncryptionData version="2.0">
        <DiskEncryptionSettingsFile>{settings_file_name}</DiskEncryptionSettingsFile>
    </DiskEncryptionData>
    """

    """
    disk/file system related
    """
    sector_size = 512
    luks_header_size = 4096 * 512
    default_block_size = 52428800
    min_filesystem_size_support = 52428800 * 3
    default_file_system = 'ext4'
    default_mount_name = 'encrypted_disk'
    dev_mapper_root = '/dev/mapper/'
    osmapper_name = 'osencrypt'
    azure_symlinks_dir = '/dev/disk/azure'
    disk_by_id_root = '/dev/disk/by-id'
    disk_by_uuid_root = '/dev/disk/by-uuid'

    """
    parameter key names
    """
    PassphraseFileNameKey = 'BekFileName'
    KeyEncryptionKeyURLKey = 'KeyEncryptionKeyURL'
    KeyVaultURLKey = 'KeyVaultURL'
    KeyVaultResourceIdKey = 'KeyVaultResourceId'
    KekVaultResourceIdKey = 'KekVaultResourceId'
    KeyEncryptionAlgorithmKey = 'KeyEncryptionAlgorithm'
    DiskFormatQuerykey = "DiskFormatQuery"
    PassphraseKey = 'Passphrase'

    """
    value for VolumeType could be Data
    """
    VolumeTypeKey = 'VolumeType'
    SecretUriKey = 'SecretUri'
    SecretSeqNum = 'SecretSeqNum'
    VolumeTypeOS = 'OS'
    VolumeTypeData = 'Data'
    VolumeTypeAll = 'All'
    SupportedVolumeTypes = [VolumeTypeOS, VolumeTypeData, VolumeTypeAll]
    SupportedVolumeTypesVMSS = [VolumeTypeData]
    """
    command types
    """
    EnableEncryption = 'EnableEncryption'
    EnableEncryptionFormat = 'EnableEncryptionFormat'
    EnableEncryptionFormatAll = 'EnableEncryptionFormatAll'
    UpdateEncryptionSettings = 'UpdateEncryptionSettings'
    DisableEncryption = 'DisableEncryption'
    QueryEncryptionStatus = 'QueryEncryptionStatus'

    """
    encryption config keys
    """
    EncryptionEncryptionOperationKey = 'EncryptionOperation'
    EncryptionDecryptionOperationKey = 'DecryptionOperation'
    EncryptionVolumeTypeKey = 'VolumeType'
    EncryptionDiskFormatQueryKey = 'DiskFormatQuery'

    """
    crypt ongoing item config keys
    """
    OngoingItemMapperNameKey = 'MapperName'
    OngoingItemHeaderFilePathKey = 'HeaderFilePath'
    OngoingItemOriginalDevNamePathKey = 'DevNamePath'
    OngoingItemOriginalDevPathKey = 'DevicePath'
    OngoingItemPhaseKey = 'Phase'
    OngoingItemHeaderSliceFilePathKey = 'HeaderSliceFilePath'
    OngoingItemFileSystemKey = 'FileSystem'
    OngoingItemMountPointKey = 'MountPoint'
    OngoingItemDeviceSizeKey = 'Size'
    OngoingItemCurrentSliceIndexKey = 'CurrentSliceIndex'
    OngoingItemFromEndKey = 'FromEnd'
    OngoingItemCurrentDestinationKey = 'CurrentDestination'
    OngoingItemCurrentTotalCopySizeKey = 'CurrentTotalCopySize'
    OngoingItemCurrentLuksHeaderFilePathKey = 'CurrentLuksHeaderFilePath'
    OngoingItemCurrentSourcePathKey = 'CurrentSourcePath'
    OngoingItemCurrentBlockSizeKey = 'CurrentBlockSize'

    """
    encryption phase devinitions
    """
    EncryptionPhaseBackupHeader = 'BackupHeader'
    EncryptionPhaseCopyData = 'EncryptingData'
    EncryptionPhaseRecoverHeader = 'RecoverHeader'
    EncryptionPhaseEncryptDevice = 'EncryptDevice'
    EncryptionPhaseDone = 'Done'

    """
    decryption phase constants
    """
    DecryptionPhaseCopyData = 'DecryptingData'
    DecryptionPhaseDone = 'Done'

    """
    logs related
    """
    InfoLevel = 'Info'
    WarningLevel = 'Warning'
    ErrorLevel = 'Error'

    """
    error codes
    """
    extension_transitioning_status = 'transitioning'
    extension_success_status = 'success'
    extension_error_status = 'error'
    process_success = 0
    success = 0
    os_not_supported = 51
    missing_dependency = 52
    configuration_error = 53
    luks_format_error = 2
    scsi_number_not_found = 3
    device_not_blank = 4
    environment_error = 5
    luks_open_error = 6
    mkfs_error = 7
    folder_conflict_error = 8
    mount_error = 9
    mount_point_not_exists = 10
    passphrase_too_long_or_none = 11
    parameter_error = 12
    create_encryption_secret_failed = 13
    encrypttion_already_enabled = 14
    passphrase_file_not_found = 15
    command_not_support = 16
    volue_type_not_support = 17
    copy_data_error = 18
    encryption_failed = 19
    tmpfs_error = 20
    backup_slice_file_error = 21
    unmount_oldroot_error = 22
    operation_lookback_failed = 23
    unknown_error = 100

class TestHooks:
    search_not_only_ide = False
    use_hard_code_passphrase = False
    hard_code_passphrase = "Quattro!"

class DeviceItem(object):
    def __init__(self):
        #NAME,TYPE,FSTYPE,MOUNTPOINT,LABEL,UUID,MODEL,SIZE,MAJ:MIN
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
        #lv_name,vg_name,lv_kernel_major,lv_kernel_minor
        self.lv_name = None
        self.vg_name = None
        self.lv_kernel_major = None
        self.lv_kernel_minor = None
    def __str__(self):
        return ("lv_name:" + str(self.lv_name) + " vg_name:" + str(self.vg_name) +
                " lv_kernel_major:" + str(self.lv_kernel_major) + " lv_kernel_minor:" + str(self.lv_kernel_minor))

class CryptItem(object):
    def __init__(self):
        self.mapper_name = None
        self.dev_path = None
        self.mount_point = None
        self.file_system = None
        self.luks_header_path = None
        self.uses_cleartext_key = None
        self.current_luks_slot = None
        
    def __str__(self):
        return ("name: " + str(self.mapper_name) + " dev_path:" + str(self.dev_path) +
                " mount_point:" + str(self.mount_point) + " file_system:" + str(self.file_system) +
                " luks_header_path:" + str(self.luks_header_path) +
                " uses_cleartext_key:" + str(self.uses_cleartext_key) +
                " current_luks_slot:" + str(self.current_luks_slot))
