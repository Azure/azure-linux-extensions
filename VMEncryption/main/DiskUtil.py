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
import json
import os
import os.path
import re
from subprocess import Popen
import traceback
import glob

from EncryptionConfig import EncryptionConfig
from DecryptionMarkConfig import DecryptionMarkConfig
from EncryptionMarkConfig import EncryptionMarkConfig
from TransactionalCopyTask import TransactionalCopyTask
from CommandExecutor import CommandExecutor, ProcessCommunicator
from Common import CommonVariables, LvmItem, DeviceItem
from io import open
from distutils.version import LooseVersion


class DiskUtil(object):
    os_disk_lvm = None
    # TBD Add support for custom VG and LV with online encryption
    os_lvm_vg = 'rootvg'
    os_lvm_lv = 'rootlv'
    sles_cache = {}

    def __init__(self, hutil, patching, logger, encryption_environment):
        self.encryption_environment = encryption_environment
        self.hutil = hutil
        self.distro_patcher = patching
        self.logger = logger
        self.ide_class_id = "{32412632-86cb-44a2-9b5c-50d1417354f5}"
        self.vmbus_sys_path = '/sys/bus/vmbus/devices'

        self.command_executor = CommandExecutor(self.logger)
        self._LUN_PREFIX = "lun"
        self._SCSI_PREFIX = "scsi"
    
    def _get_SKR_exe_path(self):
        '''getting cvm_secure_key_release_app path AzureSttestSRK'''
        absFilePath=os.path.abspath(__file__)
        currentDir = os.path.dirname(absFilePath)
        return os.path.normpath(os.path.join(currentDir,".."))
    
    def get_osmapper_path(self):
        return os.path.join(CommonVariables.dev_mapper_root, CommonVariables.osmapper_name)

    def copy(self, ongoing_item_config, status_prefix=''):
        copy_task = TransactionalCopyTask(logger=self.logger,
                                          disk_util=self,
                                          hutil=self.hutil,
                                          ongoing_item_config=ongoing_item_config,
                                          patching=self.distro_patcher,
                                          encryption_environment=self.encryption_environment,
                                          status_prefix=status_prefix)
        try:
            mem_fs_result = copy_task.prepare_mem_fs()
            if mem_fs_result != CommonVariables.process_success:
                return CommonVariables.tmpfs_error
            else:
                return copy_task.begin_copy()
        except Exception as e:
            message = "Failed to perform dd copy: {0}, stack trace: {1}".format(e, traceback.format_exc())
            self.logger.log(msg=message, level=CommonVariables.ErrorLevel)
        finally:
            copy_task.clear_mem_fs()

    def format_disk(self, dev_path, file_system):
        mkfs_command = ""
        if file_system in CommonVariables.format_supported_file_systems:
            mkfs_command = "mkfs." + file_system
        mkfs_cmd = "{0} {1}".format(mkfs_command, dev_path)
        return self.command_executor.Execute(mkfs_cmd)

    def make_sure_path_exists(self, path):
        if os.path.exists(path):
            self.logger.log("Path {0} already exists.".format(path))
            return 0
        mkdir_cmd = self.distro_patcher.mkdir_path + ' -p ' + path
        self.logger.log("make sure path exists, executing: {0}".format(mkdir_cmd))
        return self.command_executor.Execute(mkdir_cmd)

    def touch_file(self, path):
        mkdir_cmd = self.distro_patcher.touch_path + ' ' + path
        self.logger.log("touching file, executing: {0}".format(mkdir_cmd))
        return self.command_executor.Execute(mkdir_cmd)

    def is_luks_device(self, device_path, device_header_path):
        """ checks if the device is set up with a luks header """
        path_var = device_header_path if device_header_path else device_path
        cmd = 'cryptsetup isLuks ' + path_var
        return (int)(self.command_executor.Execute(cmd, suppress_logging=True)) == CommonVariables.process_success
      
    def is_device_locked(self, device_path, device_header_path):
        '''Checks if device is locked or unlocked'''
        if not self.is_luks_device(device_path=device_path, device_header_path=device_header_path):
            return False
        path_var = device_header_path if device_header_path else device_path
        cmd = 'test -b /dev/disk/by-id/dm-uuid-*$(cryptsetup luksUUID {0} | tr -d -)*'.format(path_var)
        if self.command_executor.ExecuteInBash(cmd,suppress_logging=True) == CommonVariables.process_success:
            self.logger.log("is_device_locked device path {0} is opened.".format(device_path))
            return False
        #test command is failed for multiple mappers for same crypted device. 
        #if any of mapper status is valid.
        #luksClose to non valid mapper status 
        cmd="ls -C /dev/disk/by-id/dm-uuid-*$(cryptsetup luksUUID {0} | tr -d -)*".format(path_var)
        comm = ProcessCommunicator()
        locked = True
        if self.command_executor.ExecuteInBash(cmd,communicator=comm,suppress_logging=True) == CommonVariables.process_success:
            import io
            buf = io.StringIO(comm.stdout) 
            for line in buf:
                file = os.path.basename(line.strip())
                sp = "-".join(file.split('-')[:-5])
                mapper_name = file.split('{0}-'.format(sp))[-1:][0]
                cmd = "cryptsetup status {0}".format(mapper_name)
                comm = ProcessCommunicator()
                if self.command_executor.Execute(cmd,communicator=comm,suppress_logging=True) == CommonVariables.process_success:
                    locked = False
                    self.logger.log("is_device_locked device path {0} is opened.".format(device_path))
                    continue
                msg = comm.stderr
                if not msg:
                    msg = comm.stdout
                self.logger.log("is_device_locked status for mapper {0} is {1}".format(mapper_name,msg))
                cmd = "cryptsetup luksClose {0}".format(mapper_name)
                self.command_executor.Execute(cmd)
            self.logger.log("is_device_locked device path {0} is locked.".format(device_path))
        return locked
           
    def create_luks_header(self, mapper_name):
        luks_header_file_path = self.encryption_environment.luks_header_base_path + mapper_name
        if not os.path.exists(luks_header_file_path):
            dd_command = self.distro_patcher.dd_path + ' if=/dev/zero bs=33554432 count=1 > ' + luks_header_file_path
            self.command_executor.ExecuteInBash(dd_command, raise_exception_on_failure=True)
        return luks_header_file_path

    def create_cleartext_key(self, mapper_name):
        cleartext_key_file_path = self.encryption_environment.cleartext_key_base_path + mapper_name
        if not os.path.exists(cleartext_key_file_path):
            dd_command = self.distro_patcher.dd_path + ' if=/dev/urandom bs=128 count=1 > ' + cleartext_key_file_path
            self.command_executor.ExecuteInBash(dd_command, raise_exception_on_failure=True)
        return cleartext_key_file_path
       
    def secure_key_release_operation(self,protectorbase64,kekUrl,operation,attestationUrl=None):
        '''This function release key and does wrap/unwrap operation on protector'''
        self.logger.log("secure_key_release_operation {0} started.".format(operation))
        skr_app_dir = self._get_SKR_exe_path()
        skr_app = os.path.join(skr_app_dir,CommonVariables.secure_key_release_app)
        if not os.path.isdir(skr_app_dir):
            self.logger.log("secure_key_release_operation app directory {0} is not valid.".format(skr_app_dir))
            return None
        if not os.path.isfile(skr_app):
            self.logger.log("secure_key_release_operation app {0} is not present.".format(skr_app))
            return None
        if attestationUrl:
            cmd = "{0} -a {1} -k {2} -s {3}".format(skr_app,attestationUrl,kekUrl,protectorbase64)
        else:
            cmd = "{0} -k {1} -s {2}".format(skr_app,kekUrl,protectorbase64)
        cmd = "{0} {1}".format(cmd,operation)
        process_comm = ProcessCommunicator()
        #needed to subpress logic for this execute command. run this command silently due to password. 
        ret = self.command_executor.Execute(cmd,communicator=process_comm,suppress_logging=True)
        if ret!=CommonVariables.process_success:
            msg = ""
            if process_comm.stderr:
                msg = process_comm.stderr.strip()
            elif process_comm.stdout:
                msg = process_comm.stdout.strip()
            else:
                pass
            self.logger.log("secure_key_release_operation {0} unsuccessful.".format(operation))
            self.logger.log(msg=msg)
            return None
        self.logger.log("secure_key_release_operation {0} end.".format(operation))
        return process_comm.stdout.strip()
    
    def import_token(self,device_path,passphrase_file,public_settings):
        '''this function reads passphrase from passphrase file, wrap it and update in token field of LUKS2 header.'''
        self.logger.log(msg="import_token for device: {0} started.".format(device_path))
        protector = ""
        with open(passphrase_file,"rb") as protector_file:
            #passphrase stored in keyfile is base64
            protector = protector_file.read().decode('utf-8')
        KekVaultResourceId=public_settings.get(CommonVariables.KekVaultResourceIdKey)
        KeyEncryptionKeyUrl=public_settings.get(CommonVariables.KeyEncryptionKeyURLKey)
        AttestationUrl = public_settings.get(CommonVariables.AttestationURLKey)
        wrappedProtector = self.secure_key_release_operation(protectorbase64=protector,
                                                        kekUrl=KeyEncryptionKeyUrl,
                                                        operation=CommonVariables.secure_key_release_wrap,
                                                        attestationUrl=AttestationUrl)
        if not wrappedProtector:
            self.logger.log("import_token protector wrapping is unsuccessful for device {0}".format(device_path))
            return False
        data={
            "version":CommonVariables.ADEEncryptionVersionInLuksToken_1_0,
            "type":"Azure_Disk_Encryption",
            "keyslots":[],
            CommonVariables.KekVaultResourceIdKey:KekVaultResourceId,
            CommonVariables.KeyEncryptionKeyURLKey:KeyEncryptionKeyUrl,
            CommonVariables.KeyVaultResourceIdKey:public_settings.get(CommonVariables.KeyVaultResourceIdKey),
            CommonVariables.KeyVaultURLKey:public_settings.get(CommonVariables.KeyVaultURLKey),
            CommonVariables.AttestationURLKey:AttestationUrl,
            CommonVariables.PassphraseNameKey:CommonVariables.PassphraseNameValue,
            CommonVariables.PassphraseKey:wrappedProtector
        }
        #TODO: needed to decide on temp path.
        custom_cmk = os.path.join("/var/lib/azure_disk_encryption_config/","custom_cmk.json")
        out_file = open(custom_cmk,"w")
        json.dump(data,out_file,indent=4)
        out_file.close()
        cmd = "cryptsetup token import --json-file {0} --token-id {1} {2}".format(custom_cmk,CommonVariables.cvm_ade_vm_encryption_token_id,device_path)
        process_comm = ProcessCommunicator()
        status = self.command_executor.Execute(cmd,communicator=process_comm)
        self.logger.log(msg="import_token: device: {0} status: {1}".format(device_path,status))
        os.remove(custom_cmk)
        self.logger.log(msg="import_token: device: {0} end.".format(device_path))
        return status==CommonVariables.process_success
    
    def export_token(self,device_name):
        '''This function reads token id from luks2 header field and unwrap passphrase'''
        self.logger.log("export_token to device {0} started.".format(device_name))
        device_path = os.path.join("/dev",device_name)
        protector = None
        cmd = "cryptsetup token export --token-id {0} {1}".format(CommonVariables.cvm_ade_vm_encryption_token_id,device_path)
        process_comm = ProcessCommunicator()
        status = self.command_executor.Execute(cmd, communicator=process_comm)
        if status != 0:
            self.logger.log("export_token token id {0} not found in device {1} LUKS header".format(CommonVariables.cvm_ade_vm_encryption_token_id,device_name))
            return None
        token = process_comm.stdout
        disk_encryption_setting=json.loads(token)
        if disk_encryption_setting['version'] != CommonVariables.ADEEncryptionVersionInLuksToken_1_0:
            self.logger.log("export_token token version {0} is not a vaild version.".format(disk_encryption_setting['version']))
            return None
        keyEncryptionKeyUrl=disk_encryption_setting[CommonVariables.KeyEncryptionKeyURLKey]
        wrappedProtector = disk_encryption_setting[CommonVariables.PassphraseKey]
        attestationUrl = disk_encryption_setting[CommonVariables.AttestationURLKey]
        if wrappedProtector:
            #unwrap the protector.
            protector=self.secure_key_release_operation(attestationUrl=attestationUrl,
                                                        kekUrl=keyEncryptionKeyUrl,
                                                        protectorbase64=wrappedProtector,
                                                        operation=CommonVariables.secure_key_release_unwrap)
        self.logger.log("export_token to device {0} end.".format(device_name))
        return protector

    def encrypt_disk(self, dev_path, passphrase_file, mapper_name, header_file):
        return_code = self.luks_format(passphrase_file=passphrase_file, dev_path=dev_path, header_file=header_file)
        if return_code != CommonVariables.process_success:
            self.logger.log(msg=('cryptsetup luksFormat failed, return_code is:{0}'.format(return_code)), level=CommonVariables.ErrorLevel)
            return return_code
        else:
            return_code = self.luks_open(passphrase_file=passphrase_file,
                                         dev_path=dev_path,
                                         mapper_name=mapper_name,
                                         header_file=header_file,
                                         uses_cleartext_key=False)
            if return_code != CommonVariables.process_success:
                self.logger.log(msg=('cryptsetup luksOpen failed, return_code is:{0}'.format(return_code)), level=CommonVariables.ErrorLevel)
            return return_code

    def check_fs(self, dev_path):
        self.logger.log("checking fs:" + str(dev_path))
        check_fs_cmd = self.distro_patcher.e2fsck_path + " -f -y " + dev_path
        return self.command_executor.Execute(check_fs_cmd)

    def expand_fs(self, dev_path):
        expandfs_cmd = self.distro_patcher.resize2fs_path + " " + str(dev_path)
        return self.command_executor.Execute(expandfs_cmd)

    def shrink_fs(self, dev_path, size_shrink_to):
        """
        size_shrink_to is in sector (512 byte)
        """
        shrinkfs_cmd = self.distro_patcher.resize2fs_path + ' ' + str(dev_path) + ' ' + str(int(size_shrink_to)) + 's'
        return self.command_executor.Execute(shrinkfs_cmd)

    def check_shrink_fs(self, dev_path, size_shrink_to):
        return_code = self.check_fs(dev_path)
        # e2fsck return code means fs errors corrected. We should be good in that case.
        if return_code in [CommonVariables.process_success, CommonVariables.e2fsck_fserrors_correctedode]:
            return_code = self.shrink_fs(dev_path=dev_path, size_shrink_to=size_shrink_to)
            return return_code
        else:
            return return_code

    def luks_format(self, passphrase_file, dev_path, header_file):
        """
        return the return code of the process for error handling.
        """
        self.hutil.log("dev path to cryptsetup luksFormat {0}".format(dev_path))
        # walkaround for sles sp3
        if self.distro_patcher.distro_info[0].lower() == 'suse' and self.distro_patcher.distro_info[1] == '11':
            proc_comm = ProcessCommunicator()
            passphrase_cmd = self.distro_patcher.cat_path + ' ' + passphrase_file
            self.command_executor.Execute(passphrase_cmd, communicator=proc_comm)
            passphrase = proc_comm.stdout

            cryptsetup_cmd = "{0} luksFormat {1} -q".format(self.distro_patcher.cryptsetup_path, dev_path)
            return self.command_executor.Execute(cryptsetup_cmd, input=passphrase)
        else:
            if header_file is not None:
                cryptsetup_cmd = "{0} luksFormat {1} --header {2} -d {3} -q".format(self.distro_patcher.cryptsetup_path, dev_path, header_file, passphrase_file)
            else:
                cryptsetup_cmd = "{0} luksFormat {1} -d {2} -q".format(self.distro_patcher.cryptsetup_path, dev_path, passphrase_file)

            return self.command_executor.Execute(cryptsetup_cmd)

    def luks_add_key(self, passphrase_file, dev_path, mapper_name, header_file, new_key_path):
        """
        return the return code of the process for error handling.
        """
        self.hutil.log("new key path: " + (new_key_path))

        if not os.path.exists(new_key_path):
            self.hutil.error("new key does not exist")
            return None

        if header_file:
            cryptsetup_cmd = "{0} luksAddKey {1} {2} -d {3} -q".format(self.distro_patcher.cryptsetup_path, header_file, new_key_path, passphrase_file)
        else:
            cryptsetup_cmd = "{0} luksAddKey {1} {2} -d {3} -q".format(self.distro_patcher.cryptsetup_path, dev_path, new_key_path, passphrase_file)

        return self.command_executor.Execute(cryptsetup_cmd)

    def luks_remove_key(self, passphrase_file, dev_path, header_file):
        """
        return the return code of the process for error handling.
        """
        self.hutil.log("removing keyslot: {0}".format(passphrase_file))

        if header_file:
            cryptsetup_cmd = "{0} luksRemoveKey {1} -d {2} -q".format(self.distro_patcher.cryptsetup_path, header_file, passphrase_file)
        else:
            cryptsetup_cmd = "{0} luksRemoveKey {1} -d {2} -q".format(self.distro_patcher.cryptsetup_path, dev_path, passphrase_file)

        return self.command_executor.Execute(cryptsetup_cmd)

    def luks_kill_slot(self, passphrase_file, dev_path, header_file, keyslot):
        """
        return the return code of the process for error handling.
        """
        self.hutil.log("killing keyslot: {0}".format(keyslot))

        if header_file:
            cryptsetup_cmd = "{0} luksKillSlot {1} {2} -d {3} -q".format(self.distro_patcher.cryptsetup_path, header_file, keyslot, passphrase_file)
        else:
            cryptsetup_cmd = "{0} luksKillSlot {1} {2} -d {3} -q".format(self.distro_patcher.cryptsetup_path, dev_path, keyslot, passphrase_file)

        return self.command_executor.Execute(cryptsetup_cmd)

    def luks_add_cleartext_key(self, passphrase_file, dev_path, mapper_name, header_file):
        """
        return the return code of the process for error handling.
        """
        cleartext_key_file_path = self.encryption_environment.cleartext_key_base_path + mapper_name

        self.hutil.log("cleartext key path: " + (cleartext_key_file_path))

        return self.luks_add_key(passphrase_file, dev_path, mapper_name, header_file, cleartext_key_file_path)

    def _luks_get_header_dump(self, header_or_dev_path):
        cryptsetup_cmd = "{0} luksDump {1}".format(self.distro_patcher.cryptsetup_path, header_or_dev_path)

        proc_comm = ProcessCommunicator()
        self.command_executor.Execute(cryptsetup_cmd, communicator=proc_comm)

        return proc_comm.stdout

    def luks_get_uuid(self, header_or_dev_path):
        luks_dump_out = self._luks_get_header_dump(header_or_dev_path)

        lines = filter(lambda l: "uuid" in l.lower(), luks_dump_out.split("\n"))

        for line in lines:
            splits = line.split()
            if len(splits) == 2 and len(splits[1]) == 36:
                return splits[1]
        return None

    def _get_cryptsetup_version(self):
        # get version of currently installed cryptsetup
        cryptsetup_cmd = "{0} --version".format(self.distro_patcher.cryptsetup_path)
        proc_comm = ProcessCommunicator()
        self.command_executor.Execute(cryptsetup_cmd, communicator=proc_comm, raise_exception_on_failure=True)
        return proc_comm.stdout

    def _extract_luks_version_from_dump(self, luks_dump_out):
        lines = luks_dump_out.split("\n")
        for line in lines:
            if "version:" in line.lower():
                return line.split()[-1]

    def _extract_luksv2_keyslot_lines(self, luks_dump_out):
        """
        A luks v2 luksheader looks kind of like this: (inessential stuff removed)

        LUKS header information
        Version:        2
        Data segments:
            0: crypt
                offset: 0 [bytes]
                length: 5539430400 [bytes]
                cipher: aes-xts-plain64
                sector: 512 [bytes]
        Keyslots:
            1: luks2
                    Key:        512 bits
            3: reencrypt (unbound)
                    Key:        8 bits
        Tokens:

        In order to parse out the keyslots, we focus into the "Keyslots:" section by looking for that exact string.
        Then we look for the keyslot number (if present, we return that line)

        Output for the example above:
        ["1: luks2", "3: reencrypt (unbound)"]
        """

        lines = luks_dump_out.split("\n")

        # This flag will be set to true once we enounter the line "Keyslots:"
        keyslot_segment = False
        keyslot_lines = []
        for line in lines:
            parts = line.split(":")
            if len(parts) < 2:
                continue

            if "keyslots" in parts[0].lower():
                keyslot_segment = True
                continue

            if keyslot_segment and self._isnumeric(parts[0].strip()):
                keyslot_lines.append(line)
                continue

            if not parts[0][0].isspace():
                keyslot_segment = False

        return keyslot_lines

    def _isnumeric(self, chars):
        try:
            int(chars)
            return True
        except ValueError:
            return False

    def luks_dump_keyslots(self, dev_path, header_file):
        luks_dump_out = self._luks_get_header_dump(header_file or dev_path)

        luks_version = self._extract_luks_version_from_dump(luks_dump_out)

        if luks_version == "2":
            keyslot_lines = self._extract_luksv2_keyslot_lines(luks_dump_out)
            # The code below converts keyslot line array ["0: luks", "2: reencrypt"]
            # into the keyslots occupancy array [True, False, True, False]
            # (We add an extra False slot at the end because we always assume luksv2 header is large enough to accomodate another slot)
            keyslot_numbers = [int(line.split(":")[0].strip()) for line in keyslot_lines]
            keyslot_array_size = max(keyslot_numbers) + 2
            keyslots = [i in keyslot_numbers for i in range(keyslot_array_size)]
            return keyslots
        else:
            lines = [l for l in luks_dump_out.split("\n") if "key slot" in l.lower()]
            keyslots = ["enabled" in l.lower() for l in lines]
            return keyslots

    def luks_check_reencryption(self, dev_path, header_file):
        device_header = None
        if header_file is None:
            device_header = dev_path
        else:
            device_header = header_file

        luks_dump_out = self._luks_get_header_dump(device_header)

        luks_version = self._extract_luks_version_from_dump(luks_dump_out)

        if luks_version == "2":
            keyslot_lines = self._extract_luksv2_keyslot_lines(luks_dump_out)
            for line in keyslot_lines:
                if "reencrypt" in line:
                    return True

        return False

    def luks_open(self, passphrase_file, dev_path, mapper_name, header_file, uses_cleartext_key):
        """
        return the return code of the process for error handling.
        """
        self.hutil.log("dev mapper name to cryptsetup luksOpen " + (mapper_name))

        if uses_cleartext_key:
            passphrase_file = self.encryption_environment.cleartext_key_base_path + mapper_name

        self.hutil.log("keyfile: " + (passphrase_file))

        if not passphrase_file:
            return CommonVariables.passphrase_too_long_or_none

        if header_file:
            cryptsetup_cmd = "{0} luksOpen {1} {2} --header {3} -d {4} -q".format(self.distro_patcher.cryptsetup_path, dev_path, mapper_name, header_file, passphrase_file)
        else:
            cryptsetup_cmd = "{0} luksOpen {1} {2} -d {3} -q".format(self.distro_patcher.cryptsetup_path, dev_path, mapper_name, passphrase_file)

        return self.command_executor.Execute(cryptsetup_cmd)

    def luks_close(self, mapper_name):
        """
        returns the exit code for cryptsetup process.
        """
        self.hutil.log("dev mapper name to cryptsetup luksClose " + (mapper_name))
        cryptsetup_cmd = "{0} luksClose {1} -q".format(self.distro_patcher.cryptsetup_path, mapper_name)

        return self.command_executor.Execute(cryptsetup_cmd)

    def mount_by_label(self, label, mount_point, option_string=None):
        """
        mount the BEK volume
        """
        self.make_sure_path_exists(mount_point)
        if option_string is not None and option_string != "":
            mount_cmd = self.distro_patcher.mount_path + ' -L "' + label + '" ' + mount_point + ' -o ' + option_string
        else:
            mount_cmd = self.distro_patcher.mount_path + ' -L "' + label + '" ' + mount_point

        return self.command_executor.Execute(mount_cmd)

    def mount_auto(self, dev_path_or_mount_point):
        """
        mount the file system via fstab entry
        """
        mount_cmd = self.distro_patcher.mount_path + ' ' + dev_path_or_mount_point
        return self.command_executor.Execute(mount_cmd)

    def mount_filesystem(self, dev_path, mount_point, file_system=None):
        """
        mount the file system.
        """
        self.make_sure_path_exists(mount_point)
        if file_system is None:
            mount_cmd = self.distro_patcher.mount_path + ' ' + dev_path + ' ' + mount_point
        else:
            mount_cmd = self.distro_patcher.mount_path + ' ' + dev_path + ' ' + mount_point + ' -t ' + file_system

        return self.command_executor.Execute(mount_cmd)

    def mount_crypt_item(self, crypt_item, passphrase):
        self.logger.log("trying to mount the crypt item:" + str(crypt_item))
        if crypt_item.mapper_name == CommonVariables.osmapper_name:
            self.logger.log("Skipping OS disk.")
            return
        if self.is_device_mounted(crypt_item.mapper_name):
            self.logger.log("Device {0} is already mounted".format(crypt_item.mapper_name))
            return
        self.logger.log(msg=('First trying to auto mount for the item'))
        mount_filesystem_result = self.mount_auto(os.path.join(CommonVariables.dev_mapper_root, crypt_item.mapper_name))
        if str(crypt_item.mount_point) != 'None' and mount_filesystem_result != CommonVariables.process_success:
            self.logger.log(msg=('mount_point is not None and auto mount failed. Trying manual mount.'), level=CommonVariables.WarningLevel)
            mount_filesystem_result = self.mount_filesystem(os.path.join(CommonVariables.dev_mapper_root, crypt_item.mapper_name),
                                                            crypt_item.mount_point,
                                                            crypt_item.file_system)
            self.logger.log("mount file system result:{0}".format(mount_filesystem_result))

    def is_device_mounted(self, device_name):
        try:
            mount_point = self.get_device_items_property(device_name, "MOUNTPOINT")
            if len(mount_point) > 0:
                return True
            return False
        except Exception:
            return False

    def swapoff(self):
        return self.command_executor.Execute('swapoff -a')

    def umount(self, path):
        umount_cmd = self.distro_patcher.umount_path + ' ' + path
        return self.command_executor.Execute(umount_cmd)

    def mount_all(self):
        # Reload systemd daemon to get lastest changes from fstab
        # pidof systemd seems unreliable on Ubuntu hence directly invoking systemctl
        # This command will just fail without side effects on system without systemd
        self.logger.log("Trying to reload fstab dependencies before mount all.")
        self.command_executor.Execute('systemctl daemon-reload', suppress_logging=True)
        mount_all_cmd = self.distro_patcher.mount_path + ' -a'
        return self.command_executor.Execute(mount_all_cmd)

    def unescape(self, s):
        # python2 and python3+ compatible function for converting escaped unicode bytes to unicode string
        if s is None:
            return None
        else:
            # decode unicode escape sequences, encode back to latin1, then decode all as
            return s.decode('unicode-escape').encode('latin1').decode('utf-8')

    def get_mount_items(self):
        items = []
        # open as binary in both python2 and python3+ prior to unescape
        for line in open('/proc/mounts', 'rb'):
            mp_line = self.unescape(line)
            mp_list = [s for s in mp_line.split()]
            mp_item = {
                "src": mp_list[0],
                "dest": mp_list[1],
                "fs": mp_list[2]
            }
            items.append(mp_item)
        return items

    def is_in_memfs_root(self):
        # TODO: make this more robust. This could fail due to mount paths with spaces and tmpfs (e.g. '/mnt/ tmpfs')
        mounts_file = open('/proc/mounts', 'rb')
        mounts_data = mounts_file.read()
        mounts_text = self.unescape(mounts_data)

        return bool(re.search(r'/\s+tmpfs', mounts_text))

    def get_encryption_status(self):
        encryption_status = {
            "data": "NotEncrypted",
            "os": "NotEncrypted"
        }

        mount_items = self.get_mount_items()
        device_items = self.get_device_items(None)
        device_items_dict = dict([(device_item.mount_point, device_item) for device_item in device_items])

        os_drive_encrypted = False
        data_drives_found = False
        all_data_drives_encrypted = True

        if self.is_os_disk_lvm():
            grep_result = self.command_executor.ExecuteInBash('pvdisplay | grep {0}'.format(self.get_osmapper_path()),
                                                              suppress_logging=True)
            if grep_result == 0 and not os.path.exists('/volumes.lvm'):
                self.logger.log("OS PV is encrypted")
                os_drive_encrypted = True

        special_azure_devices_to_skip = self.get_azure_devices()
        for mount_item in mount_items:
            device_item = device_items_dict.get(mount_item["dest"])

            if device_item is not None and \
               mount_item["fs"] in CommonVariables.format_supported_file_systems and \
               self.is_data_disk(device_item, special_azure_devices_to_skip):
                data_drives_found = True

                if not device_item.type == "crypt":
                    self.logger.log("Data volume {0} is mounted from {1}".format(mount_item["dest"], mount_item["src"]))
                    all_data_drives_encrypted = False

            if mount_item["dest"] == "/" and \
               not self.is_os_disk_lvm() and \
               CommonVariables.dev_mapper_root in mount_item["src"] or \
               "/dev/dm" in mount_item["src"]:
                self.logger.log("OS volume {0} is mounted from {1}".format(mount_item["dest"], mount_item["src"]))
                os_drive_encrypted = True

        if not data_drives_found:
            encryption_status["data"] = "NotMounted"
        elif all_data_drives_encrypted:
            encryption_status["data"] = "Encrypted"
        if os_drive_encrypted:
            encryption_status["os"] = "Encrypted"

        encryption_marker = EncryptionMarkConfig(self.logger, self.encryption_environment)
        decryption_marker = DecryptionMarkConfig(self.logger, self.encryption_environment)
        if decryption_marker.config_file_exists():
            print(decryption_marker.config_file_exists)
            encryption_status["data"] = "DecryptionInProgress"
        elif encryption_marker.config_file_exists():
            encryption_config = EncryptionConfig(self.encryption_environment, self.logger)
            volume_type = encryption_config.get_volume_type().lower()

            if volume_type == CommonVariables.VolumeTypeData.lower() or \
               volume_type == CommonVariables.VolumeTypeAll.lower():
                encryption_status["data"] = "EncryptionInProgress"

            if volume_type == CommonVariables.VolumeTypeOS.lower() or \
               volume_type == CommonVariables.VolumeTypeAll.lower():
                if not os_drive_encrypted or self.luks_check_reencryption(dev_path=None, header_file="/boot/luks/osluksheader"):
                    encryption_status["os"] = "EncryptionInProgress"

        elif os.path.exists(self.get_osmapper_path()) and not os_drive_encrypted:
            encryption_status["os"] = "VMRestartPending"

        return json.dumps(encryption_status)

    def query_dev_sdx_path_by_scsi_id(self, scsi_number):
        p = Popen([self.distro_patcher.lsscsi_path, scsi_number], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        identity, err = p.communicate()
        # identity sample: [5:0:0:0] disk Msft Virtual Disk 1.0 /dev/sdc
        self.logger.log("lsscsi output is: {0}\n".format(identity))
        vals = identity.split()
        if vals is None or len(vals) == 0:
            return None
        sdx_path = vals[len(vals) - 1]
        return sdx_path

    def query_dev_sdx_path_by_uuid(self, uuid):
        """
        return /dev/disk/by-id that maps to the sdx_path, otherwise return the original path
        """
        desired_uuid_path = os.path.join(CommonVariables.disk_by_uuid_root, uuid)
        for disk_by_uuid in os.listdir(CommonVariables.disk_by_uuid_root):
            disk_by_uuid_path = os.path.join(CommonVariables.disk_by_uuid_root, disk_by_uuid)

            if disk_by_uuid_path == desired_uuid_path:
                return os.path.realpath(disk_by_uuid_path)

        return desired_uuid_path

    def query_dev_id_path_by_sdx_path(self, sdx_path):
        """
        return /dev/disk/by-id that maps to the sdx_path, otherwise return the original path
        Update: now we have realised that by-id is not a good way to refer to devices (they can change on reallocations or resizes).
        Try not to use this- use get_persistent_path_by_sdx_path instead
        """
        for disk_by_id in os.listdir(CommonVariables.disk_by_id_root):
            disk_by_id_path = os.path.join(CommonVariables.disk_by_id_root, disk_by_id)
            if os.path.realpath(disk_by_id_path) == sdx_path:
                return disk_by_id_path

        return sdx_path

    def get_persistent_path_by_sdx_path(self, sdx_path):
        """
        return a stable path for this /dev/sdx device
        """
        sdx_realpath = os.path.realpath(sdx_path)

        # First try finding an Azure symlink
        azure_name_table = self.get_block_device_to_azure_udev_table()
        if sdx_realpath in azure_name_table:
            return azure_name_table[sdx_realpath]

        # A mapper path is also pretty good (especially for raid or lvm)
        for mapper_name in os.listdir(CommonVariables.dev_mapper_root):
            mapper_path = os.path.join(CommonVariables.dev_mapper_root, mapper_name)
            if os.path.realpath(mapper_path) == sdx_realpath:
                return mapper_path

        # Then try matching a uuid symlink. Those are probably the best
        for disk_by_uuid in os.listdir(CommonVariables.disk_by_uuid_root):
            disk_by_uuid_path = os.path.join(CommonVariables.disk_by_uuid_root, disk_by_uuid)

            if os.path.realpath(disk_by_uuid_path) == sdx_realpath:
                return disk_by_uuid_path

        # Found nothing very persistent. Just return the original sdx path.
        # And Log it.
        self.logger.log(msg="Failed to find a persistent path for [{0}].".format(sdx_path), level=CommonVariables.WarningLevel)

        return sdx_path

    def get_device_path(self, dev_name):
        device_path = None
        # ensure the use of a string representation for python2 + python3 compat
        dev_name = str(dev_name)

        if os.path.exists("/dev/" + dev_name):
            device_path = "/dev/" + dev_name
        elif os.path.exists(os.path.join(CommonVariables.dev_mapper_root, dev_name)):
            device_path = os.path.join(CommonVariables.dev_mapper_root, dev_name)

        return device_path

    def get_device_id(self, dev_path):
        udev_cmd = "udevadm info -a -p $(udevadm info -q path -n {0}) | grep device_id".format(dev_path)
        proc_comm = ProcessCommunicator()
        self.command_executor.ExecuteInBash(udev_cmd, communicator=proc_comm, suppress_logging=True)
        match = re.findall(r'"{(.*)}"', proc_comm.stdout.strip())
        return match[0] if match else ""

    def get_device_items_property(self, dev_name, property_name):
        if (dev_name, property_name) in DiskUtil.sles_cache:
            return DiskUtil.sles_cache[(dev_name, property_name)]

        self.logger.log("getting property of device {0}".format(dev_name))

        device_path = self.get_device_path(dev_name)
        property_value = ""

        if property_name == "SIZE":
            get_property_cmd = self.distro_patcher.blockdev_path + " --getsize64 " + device_path
            proc_comm = ProcessCommunicator()
            self.command_executor.Execute(get_property_cmd, communicator=proc_comm, suppress_logging=True)
            property_value = proc_comm.stdout.strip()
        elif property_name == "DEVICE_ID":
            property_value = self.get_device_id(device_path)
        else:
            get_property_cmd = self.distro_patcher.lsblk_path + " " + device_path + " -b -nl -o NAME," + property_name
            proc_comm = ProcessCommunicator()
            self.command_executor.Execute(get_property_cmd, communicator=proc_comm, raise_exception_on_failure=True, suppress_logging=True)
            for line in proc_comm.stdout.splitlines():
                if line.strip():
                    disk_info_item_array = line.strip().split()
                    if dev_name == disk_info_item_array[0]:
                        if len(disk_info_item_array) > 1:
                            property_value = disk_info_item_array[1]

        DiskUtil.sles_cache[(dev_name, property_name)] = property_value
        return property_value

    def get_block_device_to_azure_udev_table(self):
        table = {}
        azure_links_dir = CommonVariables.azure_symlinks_dir

        if not os.path.exists(azure_links_dir):
            return table

        for top_level_item in os.listdir(azure_links_dir):
            top_level_item_full_path = os.path.join(azure_links_dir, top_level_item)
            if os.path.isdir(top_level_item_full_path):
                scsi_path = os.path.join(azure_links_dir, top_level_item)
                for symlink in os.listdir(scsi_path):
                    symlink_full_path = os.path.join(scsi_path, symlink)
                    table[os.path.realpath(symlink_full_path)] = symlink_full_path
            else:
                table[os.path.realpath(top_level_item_full_path)] = top_level_item_full_path
        return table

    def is_parent_of_any(self, parent_dev_path, children_dev_path_set):
        """
        check if the device whose path is parent_dev_path is actually a parent of any of the children in children_dev_path_set
        All the paths need to be "realpaths" (not symlinks)
        """
        actual_children_dev_items = self.get_device_items(parent_dev_path)
        actual_children_dev_path_set = set([os.path.realpath(self.get_device_path(di.name)) for di in actual_children_dev_items])
        # the sets being disjoint would mean the candidate parent is not parent of any of the candidate children. So we return the opposite of that
        return not actual_children_dev_path_set.isdisjoint(children_dev_path_set)

    def get_all_azure_data_disk_controller_and_lun_numbers(self):
        """
        Return the controller ids and lun numbers for data disks that show up in the dev_items
        """
        list_devices = []
        azure_links_dir = CommonVariables.azure_symlinks_dir

        if not os.path.exists(azure_links_dir):
            return list_devices

        for top_level_item in os.listdir(azure_links_dir):
            top_level_item_full_path = os.path.join(azure_links_dir, top_level_item)
            if os.path.isdir(top_level_item_full_path) and top_level_item.startswith(self._SCSI_PREFIX):
                # this works because apparently all data disks go int a scsi[x] where x is one of [1,2,3,4]
                try:
                    controller_id = int(top_level_item[4:])  # strip the first 4 letters of the folder
                except ValueError:
                    # if its not an integer, probably just best to skip it
                    continue

                if controller_id == 0:
                    # scsi0 is a Gen2 special controller which never has Data disks, so we skip it here
                    continue

                for symlink in os.listdir(top_level_item_full_path):
                    if symlink.startswith(self._LUN_PREFIX):
                        try:
                            lun_number = int(symlink[3:])
                        except ValueError:
                            # parsing will fail if "symlink" was a partition (e.g. "lun0-part1")
                            continue  # so just ignore it
                        list_devices.append((controller_id, lun_number))
        return list_devices

    def get_azure_data_disk_controller_and_lun_numbers(self, dev_items_real_paths):
        """
        Return the controller ids and lun numbers for data disks that show up in the dev_items
        """
        list_devices = []
        is_os_nvme, root_device_path_nvme = self.is_os_disk_nvme()

        if is_os_nvme:
            list_devices = self.get_all_nvme_controllers_and_namespaces(root_device_path_nvme, dev_items_real_paths)
            return list_devices
        
        all_controller_and_lun_numbers = self.get_all_azure_data_disk_controller_and_lun_numbers()

        azure_links_dir = CommonVariables.azure_symlinks_dir

        for controller_id, lun_number in all_controller_and_lun_numbers:
            scsi_dir = os.path.join(azure_links_dir, self._SCSI_PREFIX + str(controller_id))
            symlink = os.path.join(scsi_dir, self._LUN_PREFIX + str(lun_number))
            if self.is_parent_of_any(os.path.realpath(symlink), dev_items_real_paths):
                list_devices.append((controller_id, lun_number))

        return list_devices
    
    def get_all_nvme_controllers_and_namespaces(self, root_device_path_nvme, dev_items_real_paths):
        list_devices = []
        proc_comm = ProcessCommunicator()
        self.command_executor.Execute('nvme list -o json', communicator=proc_comm, raise_exception_on_failure=True)
        nvme_devices_json = json.loads(proc_comm.stdout)
        self.logger.log("NVMe Devices: "+str(nvme_devices_json))
        nvme_devices = nvme_devices_json['Devices']
        for nvme_device in nvme_devices:
            nvme_device_path = nvme_device['DevicePath']
            if nvme_device_path == root_device_path_nvme:
                self.logger.log("Skip NVMe OS disk")
                continue
            #Sample Device Path
            #/dev/nvme0n2
            slot_id = nvme_device['NameSpace'] - 2 # slot_id = Namspace - 2. It will be used to locate disk in CCF
            if self.is_parent_of_any(os.path.realpath(nvme_device_path), dev_items_real_paths):
                list_devices.append((1, slot_id)) # Hardcode conyroller to 1 to meet CCF check
            
        return list_devices



    def log_lsblk_output(self):
        lsblk_command = 'lsblk -o NAME,TYPE,FSTYPE,LABEL,SIZE,RO,MOUNTPOINT'
        proc_comm = ProcessCommunicator()
        self.command_executor.Execute(lsblk_command, communicator=proc_comm)
        output = proc_comm.stdout
        self.logger.log('\n' + output + '\n')

    def get_device_items_sles(self, dev_path):
        if dev_path:
            self.logger.log(msg=("getting blk info for: {0}".format(dev_path)))
        device_items_to_return = []
        device_items = []

        # first get all the device names
        if dev_path is None:
            lsblk_command = 'lsblk -b -nl -o NAME'
        else:
            lsblk_command = 'lsblk -b -nl -o NAME ' + dev_path

        proc_comm = ProcessCommunicator()
        self.command_executor.Execute(lsblk_command, communicator=proc_comm, raise_exception_on_failure=True)

        for line in proc_comm.stdout.splitlines():
            item_value_str = line.strip()
            if item_value_str:
                device_item = DeviceItem()
                device_item.name = item_value_str.split()[0]
                device_items.append(device_item)

        for device_item in device_items:
            device_item.file_system = self.get_device_items_property(dev_name=device_item.name, property_name='FSTYPE')
            device_item.mount_point = self.get_device_items_property(dev_name=device_item.name, property_name='MOUNTPOINT')
            device_item.label = self.get_device_items_property(dev_name=device_item.name, property_name='LABEL')
            device_item.uuid = self.get_device_items_property(dev_name=device_item.name, property_name='UUID')
            device_item.majmin = self.get_device_items_property(dev_name=device_item.name, property_name='MAJ:MIN')
            device_item.device_id = self.get_device_items_property(dev_name=device_item.name, property_name='DEVICE_ID')

            # get the type of device
            model_file_path = '/sys/block/' + device_item.name + '/device/model'

            if os.path.exists(model_file_path):
                with open(model_file_path, 'r') as f:
                    device_item.model = f.read().strip()
            else:
                self.logger.log(msg=("no model file found for device {0}".format(device_item.name)))

            if device_item.model == 'Virtual Disk':
                self.logger.log(msg="model is virtual disk")
                device_item.type = 'disk'
            else:
                partition_files = glob.glob('/sys/block/*/' + device_item.name + '/partition')
                self.logger.log(msg="partition files exists")
                if partition_files is not None and len(partition_files) > 0:
                    device_item.type = 'part'

            size_string = self.get_device_items_property(dev_name=device_item.name, property_name='SIZE')

            if size_string is not None and size_string != "":
                device_item.size = int(size_string)

            if device_item.type is None:
                device_item.type = ''

            if device_item.size is not None:
                device_items_to_return.append(device_item)
            else:
                self.logger.log(msg=("skip the device {0} because we could not get size of it.".format(device_item.name)))

        return device_items_to_return

    def get_device_items(self, dev_path):
        if self.distro_patcher.distro_info[0].lower() == 'suse' and self.distro_patcher.distro_info[1] == '11':
            return self.get_device_items_sles(dev_path)
        else:
            if dev_path:
                self.logger.log(msg=("getting blk info for: " + str(dev_path)))

            if dev_path is None:
                lsblk_command = 'lsblk -b -n -P -o NAME,TYPE,FSTYPE,MOUNTPOINT,LABEL,UUID,MODEL,SIZE,MAJ:MIN'
            else:
                lsblk_command = 'lsblk -b -n -P -o NAME,TYPE,FSTYPE,MOUNTPOINT,LABEL,UUID,MODEL,SIZE,MAJ:MIN ' + dev_path

            proc_comm = ProcessCommunicator()
            self.command_executor.Execute(lsblk_command, communicator=proc_comm, raise_exception_on_failure=True, suppress_logging=True)

            device_items = []
            lvm_items = self.get_lvm_items()
            for line in proc_comm.stdout.splitlines():
                if line:
                    device_item = DeviceItem()

                    for disk_info_property in str(line).split():
                        property_item_pair = disk_info_property.split('=')
                        if property_item_pair[0] == 'SIZE':
                            device_item.size = int(property_item_pair[1].strip('"'))

                        if property_item_pair[0] == 'NAME':
                            device_item.name = property_item_pair[1].strip('"')

                        if property_item_pair[0] == 'TYPE':
                            device_item.type = property_item_pair[1].strip('"')

                        if property_item_pair[0] == 'FSTYPE':
                            device_item.file_system = property_item_pair[1].strip('"')

                        if property_item_pair[0] == 'MOUNTPOINT':
                            device_item.mount_point = property_item_pair[1].strip('"')

                        if property_item_pair[0] == 'LABEL':
                            device_item.label = property_item_pair[1].strip('"')

                        if property_item_pair[0] == 'UUID':
                            device_item.uuid = property_item_pair[1].strip('"')

                        if property_item_pair[0] == 'MODEL':
                            device_item.model = property_item_pair[1].strip('"')

                        if property_item_pair[0] == 'MAJ:MIN' or property_item_pair[0] == "MAJ_MIN":
                            device_item.majmin = property_item_pair[1].strip('"')

                    device_item.device_id = self.get_device_id(self.get_device_path(device_item.name))

                    if device_item.type is None:
                        device_item.type = ''

                    if device_item.type.lower() == 'lvm':
                        for lvm_item in lvm_items:
                            majmin = lvm_item.lv_kernel_major + ':' + lvm_item.lv_kernel_minor

                            if majmin == device_item.majmin:
                                device_item.name = lvm_item.vg_name + '/' + lvm_item.lv_name

                    device_items.append(device_item)

            return device_items

    def get_lvm_items(self):
        lvs_command = 'lvs --noheadings --nameprefixes --unquoted -o lv_name,vg_name,lv_kernel_major,lv_kernel_minor'
        proc_comm = ProcessCommunicator()

        try:
            self.command_executor.Execute(lvs_command, communicator=proc_comm, raise_exception_on_failure=True)
        except Exception:
            return []  # return empty list on non-lvm systems that do not have lvs

        lvm_items = []

        for line in proc_comm.stdout.splitlines():
            if not line:
                continue

            lvm_item = LvmItem()

            for pair in str(line).strip().split():
                if len(pair.split('=')) != 2:
                    continue

                key, value = pair.split('=')

                if key == 'LVM2_LV_NAME':
                    lvm_item.lv_name = value

                if key == 'LVM2_VG_NAME':
                    lvm_item.vg_name = value

                if key == 'LVM2_LV_KERNEL_MAJOR':
                    lvm_item.lv_kernel_major = value

                if key == 'LVM2_LV_KERNEL_MINOR':
                    lvm_item.lv_kernel_minor = value

            lvm_items.append(lvm_item)

        return lvm_items

    def is_os_disk_lvm(self):
        if DiskUtil.os_disk_lvm is not None:
            return DiskUtil.os_disk_lvm

        device_items = self.get_device_items(None)

        if not any([item.type.lower() == 'lvm' for item in device_items]):
            DiskUtil.os_disk_lvm = False
            return False

        if self.distro_patcher.support_online_encryption:
            if os.system("lsblk -o TYPE,MOUNTPOINT | grep lvm | grep -q '/$'") == 0:
                DiskUtil.os_disk_lvm = True
                return True

        lvm_items = [item for item in self.get_lvm_items() if item.vg_name == "rootvg"]

        current_lv_names = set([item.lv_name for item in lvm_items])

        DiskUtil.os_disk_lvm = False

        if 'homelv' in current_lv_names and 'rootlv' in current_lv_names:
            DiskUtil.os_disk_lvm = True

        return DiskUtil.os_disk_lvm

    """
    To check if OS disk is NVMe we try to get OS disk block device name.
    If block device name starts with /dev/nvme then we consider it as NVMe.
    Below are the steps to get OS disk block device name:
    - If OS is LVM then get the backing physical volume using pvs command
    - For RAW OS get the device for / mountpoint from /proc/mounts
      -  For non online encryption OS could be mounted on /oldroot in stripdown state.
      -  if device for / is none then it could be the stripdown state.
      -  Use /oldroot mountpoint for such cases.
    - Ubuntu /proc/mounts contains /dev/root as OS disk. Use findmnt to get the actual OS disk.
    - If OS is encrypted, use dmsetup to get the backing block device for the device mapper.
    """
    def is_os_disk_nvme(self):
        try:
            os_block_device = None
            proc_comm = ProcessCommunicator()
            if self.is_os_disk_lvm():
                self.command_executor.Execute('pvs', True, communicator=proc_comm)
                
                for line in proc_comm.stdout.split("\n"):
                    if DiskUtil.os_lvm_vg in line:
                        os_block_device = line.strip().split()[0]
            else:
                rootfs_mountpoint = '/'
                mount_items = self.get_mount_items()
                for mount_item in mount_items:
                    if mount_item["dest"] == "/" or mount_item["dest"] == "/oldroot":
                        os_block_device = mount_item["src"]
                        if os_block_device == 'none':
                            self.logger.log('In MemFS. Will check for /oldroot mountpoint')
                            continue
                        if mount_item["dest"] == "/oldroot":
                            rootfs_mountpoint = '/oldroot'
                        break
            self.logger.log('Found OS block device: ' + os_block_device)
            if os_block_device == '/dev/root':
                self.command_executor.ExecuteInBash('findmnt -n -o SOURCE {}'.format(rootfs_mountpoint), True, communicator=proc_comm)
                os_block_device = proc_comm.stdout
            if os_block_device.startswith(CommonVariables.dev_mapper_root):
                osmapper_name = self.get_osmapper_name()
                if os_block_device == os.path.join(CommonVariables.dev_mapper_root, osmapper_name):
                    self.command_executor.Execute('dmsetup deps -o blkdevname {0}'.format(os_block_device), True, communicator=proc_comm)
                    # Sample output
                    # 1 dependencies  : (nvme0n1p1)
                    os_block_device = '/dev/' + proc_comm.stdout[proc_comm.stdout.index('(')+1:proc_comm.stdout.index(')')]
            self.logger.log('Normalized OS block device: '+ os_block_device)
            if os_block_device.startswith(CommonVariables.nvme_device_identifier):
                self.logger.log('OS disk is NVMe. Treating the VM as ASAP')
                return True, os_block_device[:os_block_device.index("p")]
            else:
                return False, ''
        except Exception as ex:
            self.logger.log("Exception {0} occured while trying to check for NVMe SKU".format(ex))
            return False, '' # Treat expection as non fatal for now to avoid any regression


    def is_data_disk(self, device_item, special_azure_devices_to_skip):
        # Root disk
        if device_item.device_id.startswith('00000000-0000'):
            self.logger.log(msg="skipping root disk", level=CommonVariables.WarningLevel)
            return False
        # Resource Disk. Not considered a "data disk" exactly (is not attached via portal and we have a separate code path for encrypting it)
        if device_item.device_id.startswith('00000000-0001'):
            self.logger.log(msg="skipping resource disk", level=CommonVariables.WarningLevel)
            return False
        # BEK VOLUME
        if device_item.file_system == "vfat" and device_item.label.lower() == "bek":
            self.logger.log(msg="skipping BEK VOLUME", level=CommonVariables.WarningLevel)
            return False

        # We let the caller specify a list of devices to skip. Usually its just a list of IDE devices.
        # IDE devices (in Gen 1) include Resource disk and BEK VOLUME. This check works pretty wel in Gen 1, but not in Gen 2.
        for azure_blk_item in special_azure_devices_to_skip:
            if azure_blk_item.name == device_item.name:
                if device_item.name:
                    self.logger.log(msg="{0} is one of special azure devices that should be not considered data disks.".format(device_item.name))
                return False

        return True

    def should_skip_for_inplace_encryption(self, device_item, special_azure_devices_to_skip, encrypt_volume_type):
        """
        TYPE="raid0"
        TYPE="part"
        TYPE="crypt"

        first check whether there's one file system on it.
        if the type is disk, then to check whether it have child-items, say the part, lvm or crypt luks.
        if the answer is yes, then skip it.
        """

        if encrypt_volume_type.lower() == 'data' and not self.is_data_disk(device_item, special_azure_devices_to_skip):
            return True  # Skip non-data disks

        if device_item.file_system is None or device_item.file_system == "":
            self.logger.log(msg=("there's no file system on this device: {0}, so skip it.").format(device_item))
            return True
        else:
            if device_item.size < CommonVariables.min_filesystem_size_support:
                self.logger.log(msg="the device size is too small," + str(device_item.size) + " so skip it.", level=CommonVariables.WarningLevel)
                return True

            supported_device_type = ["disk", "part", "raid0", "raid1", "raid5", "raid10", "lvm"]
            if device_item.type not in supported_device_type:
                self.logger.log(msg="the device type: " + str(device_item.type) + " is not supported yet, so skip it.", level=CommonVariables.WarningLevel)
                return True

            if device_item.uuid is None or device_item.uuid == "":
                self.logger.log(msg="the device do not have the related uuid, so skip it.", level=CommonVariables.WarningLevel)
                return True
            sub_items = self.get_device_items(self.get_device_path(device_item.name))
            if len(sub_items) > 1:
                self.logger.log(msg=("there's sub items for the device:{0} , so skip it.".format(device_item.name)), level=CommonVariables.WarningLevel)
                return True

            if device_item.file_system == "crypto_LUKS":
                self.logger.log(msg ="device {0} fs type is crypto_LUKS, so skip it.".format(device_item.name),level=CommonVariables.WarningLevel)
                return True

            if device_item.type == "crypt":
                self.logger.log(msg=("device_item.type is:{0}, so skip it.".format(device_item.type)), level=CommonVariables.WarningLevel)
                return True

            if device_item.mount_point == "/":
                self.logger.log(msg=("the mountpoint is root:{0}, so skip it.".format(device_item)), level=CommonVariables.WarningLevel)
                return True

            for azure_blk_item in special_azure_devices_to_skip:
                if azure_blk_item.name == device_item.name:
                    self.logger.log(msg="the mountpoint is the azure disk root or resource, so skip it.")
                    return True
            return False

    def get_azure_devices(self):
        device_names = []
        blk_items = []

        # Get all IDE devices
        ide_devices = self.get_ide_devices()
        for ide_device in ide_devices:
            device_names.append("/dev/" + ide_device)

        # get all SCSI 0 devices
        device_names += self.get_scsi0_device_names()

        # some machines use special root dir symlinks instead of scsi0 symlinks
        device_names += self.get_azure_symlinks_root_dir_devices()

        device_names += self.get_azure_nvme_os_devices()

        # let us do some de-duping
        device_names_realpaths = set(map(os.path.realpath, device_names))

        for device_path in device_names_realpaths:
            current_blk_items = self.get_device_items(device_path)
            for current_blk_item in current_blk_items:
                blk_items.append(current_blk_item)

        return blk_items
    
    def get_azure_nvme_os_devices(self):
        devices = []
        is_os_nvme, os_block_device = self.is_os_disk_nvme()
        if is_os_nvme:
            proc_comm = ProcessCommunicator()
            self.command_executor.ExecuteInBash('ls {0}*'.format(os_block_device), True, communicator=proc_comm)
            os_devices = re.split('[ \n]', proc_comm.stdout)
            for os_device in os_devices:
                if os_device.startswith(os_block_device) and os.path.exists(os_device):
                    devices.append(os_device)
        return devices

    def get_azure_symlinks_root_dir_devices(self):
        """
        There is a directory that provide helpful persistent symlinks to important devices
        We scrape the directory to identify "special" devices that should not be
        encrypted along with other data disks
        """

        devices = []

        azure_links_dir = CommonVariables.azure_symlinks_dir
        if os.path.exists(azure_links_dir):
            known_special_device_names = ["root", "resource"]
            for device_name in known_special_device_names:
                full_device_path = os.path.join(azure_links_dir, device_name)
                if os.path.exists(full_device_path):
                    devices.append(full_device_path)

        azure_links_dir = CommonVariables.cloud_symlinks_dir
        if os.path.exists(azure_links_dir):
            known_special_device_names = ["azure_root", "azure_resource"]
            for device_name in known_special_device_names:
                full_device_path = os.path.join(azure_links_dir, device_name)
                if os.path.exists(full_device_path):
                    devices.append(full_device_path)

        return devices

    def get_ide_devices(self):
        """
        this only return the device names of the ide.
        """
        ide_devices = []
        for vmbus in os.listdir(self.vmbus_sys_path):
            f = open('%s/%s/%s' % (self.vmbus_sys_path, vmbus, 'class_id'), 'r')
            class_id = f.read()
            f.close()
            if class_id.strip() == self.ide_class_id:
                device_sdx_path = self.find_block_sdx_path(vmbus)
                self.logger.log("found one ide with vmbus: {0} and the sdx path is: {1}".format(vmbus,
                                                                                                device_sdx_path))
                ide_devices.append(device_sdx_path)
        return ide_devices

    def get_scsi0_device_names(self):
        """
        gen2 equivalent of get_ide_devices()
        """
        devices = []
        azure_links_dir = CommonVariables.azure_symlinks_dir
        scsi0_dir = os.path.join(azure_links_dir, self._SCSI_PREFIX + "0")

        if not os.path.exists(scsi0_dir):
            return devices

        for symlink in os.listdir(scsi0_dir):
            if symlink.startswith(self._LUN_PREFIX) and self._isnumeric(symlink[3:]):
                devices.append(os.path.join(scsi0_dir, symlink))

        return devices

    def find_block_sdx_path(self, vmbus):
        device = None
        for root, dirs, files in os.walk(os.path.join(self.vmbus_sys_path, vmbus)):
            if root.endswith("/block"):
                device = dirs[0]
            else:  # older distros
                for d in dirs:
                    if ':' in d and "block" == d.split(':')[0]:
                        device = d.split(':')[1]
                        break
        return device

    def get_luks_header_size(self, device_path=None):
        if device_path is None:
            # LUKS2 headers are the default in cryptsetup 2.1.0 and higher
            cryptsetup_ver = self._get_cryptsetup_version()
            if LooseVersion(cryptsetup_ver) >= LooseVersion('cryptsetup 2.1.0'):
                return CommonVariables.luks_header_size_v2
            else:
                return CommonVariables.luks_header_size
        else:
            # Parse the luksDump output to identify what LUKS version the header is
            # The dump file contents contain the offset to the first data segment (payload)
            # which is in turn equal to the size of the LUKS header prior to that
            # https://gitlab.com/cryptsetup/cryptsetup/-/wikis/FrequentlyAskedQuestions#2-setup

            # Dump the in place LUKS header and version
            luksDump = self._luks_get_header_dump(device_path)
            luksVer = self._extract_luks_version_from_dump(luksDump)

            if luksVer and int(luksVer) == 1:
                # parse V1 LUKS dump format to get the offset in sectors, then convert to bytes
                # V1 file format example:
                #   Payload offset: 4096
                result = re.findall(r"Payload.*?(\d+)", luksDump)
                if result:
                    offset_in_sectors = int(result[0])
                    header_size = offset_in_sectors * CommonVariables.sector_size
                else:
                    self.logger.log("LUKS1 payload offset not found", level=CommonVariables.ErrorLevel)
                    header_size = None
            elif luksVer and int(luksVer) == 2:
                # parse V2 LUKS dump format which provides offset to first data segment in bytes
                # V2 file format example:
                #   Data segments:
                #   0: crypt
                #       offset: 16777216 [bytes]
                result = re.findall(r"0:\s+crypt\s+offset:\s?(\d+)", luksDump)
                if result:
                    self.logger.log("LUKS2 data segment offset not found", level=CommonVariables.ErrorLevel)
                    header_size = int(result[0])
                else:
                    header_size = None
            else:
                self.logger.log("LUKS header version not found", level=CommonVariables.ErrorLevel)
                header_size = None

            return header_size
            
    def get_osmapper_name(self):
        osmapper_name = CommonVariables.osmapper_name
        try:
            rootfs_device = list(filter(lambda d:d.mount_point=='/',self.get_device_items(None)))
            if rootfs_device and rootfs_device[0].type == 'crypt':
                osmapper_name = rootfs_device[0].name
        except ex as Exception:
            self.logger.log("getting exception on finding osmapper.")
            raise
        return osmapper_name

    
