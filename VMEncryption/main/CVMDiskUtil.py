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

import json
import os
import os.path
import tempfile
import io

from CommandExecutor import CommandExecutor, ProcessCommunicator
from Common import CommonVariables, LvmItem, DeviceItem
from io import open

class CVMDiskUtil(object):
    ''' CVM disk util class has cvm specific util function for disk encryption.'''

    def __init__(self, disk_util, logger):
        '''initialize to cvm disk util class'''
        self.disk_util = disk_util
        self.logger = logger
        self.command_executor = CommandExecutor(self.logger)

    def _isnumeric(self, chars):
        '''check if chars is numeric type'''
        try:
            int(chars)
            return True
        except ValueError:
            return False

    def _get_skr_exe_path(self):
        '''getting cvm secure key release (SKR) app, i.e., AzureAttestSRK binary path'''
        abs_file_path=os.path.abspath(__file__)
        current_dir = os.path.dirname(abs_file_path)
        return os.path.normpath(os.path.join(current_dir,".."))

    def _secure_key_release_operation(self,protector_base64,kek_url,operation,attestation_url=None):
        '''This is private function, used for releasing key and wrap/unwrap operation on protector'''
        self.logger.log("secure_key_release_operation {0} started.".format(operation))
        skr_app_dir = self._get_skr_exe_path()
        skr_app = os.path.join(skr_app_dir,CommonVariables.secure_key_release_app)
        if not os.path.isdir(skr_app_dir):
            self.logger.log("secure_key_release_operation app directory {0} is not valid.".format(skr_app_dir))
            return None
        if not os.path.isfile(skr_app):
            self.logger.log("secure_key_release_operation app {0} is not present.".format(skr_app))
            return None
        if attestation_url:
            cmd = "{0} -a {1} -k {2} -s {3}".format(skr_app,attestation_url,kek_url,protector_base64)
        else:
            cmd = "{0} -k {1} -s {2}".format(skr_app,kek_url,protector_base64)
        cmd = "{0} {1}".format(cmd,operation)
        process_comm = ProcessCommunicator()
        #suppressing logging enabled due to password use.
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

    def import_token_data(self, device_path, token_data, token_id):
        '''Updating token_data json object to LUKS2 header's Tokens field.
        token data is as follow for version 1.0.
        "version": "1.0",
        "type": "Azure_Disk_Encryption",
        "keyslots": [],
        "KekVaultResourceId": "<kek_res_id>",
        "KeyEncryptionKeyURL": "<kek_url>",
        "KeyVaultResourceId": "<kv_res_id>",
        "KeyVaultURL": "https://<vault_name>.vault.azure.net/",
        "AttestationURL": null,
        "PassphraseName": "LUKSPasswordProtector",
        "Passphrase": "M53XE09n7O9r2AdKa7FYRYe..."
        '''
        self.logger.log(msg="import_token_data for device: {0} started.".format(device_path))
        if not token_data or not isinstance(token_data, dict):
            self.logger.log(level=CommonVariables.WarningLevel, msg="import_token_data: token_data: {0} for device: {1} is not valid.".format(token_data,device_path))
            return False
        if not token_id:
            self.logger.log(level= CommonVariables.WarningLevel, msg = "import_token_data: token_id: {0} for device: {1} is not valid.".format(token_id,device_path) )
            return False
        temp_file = tempfile.NamedTemporaryFile(delete=False,mode='w+')
        json.dump(token_data,temp_file,indent=4)
        temp_file.close()
        cmd = "cryptsetup token import --json-file {0} --token-id {1} {2}".format(temp_file.name,token_id,device_path)
        process_comm = ProcessCommunicator()
        status = self.command_executor.Execute(cmd,communicator=process_comm)
        self.logger.log(msg="import_token_data: device: {0} status: {1}".format(device_path,status))
        os.unlink(temp_file.name)
        return status==CommonVariables.process_success

    def import_token(self, device_path, passphrase_file, public_settings,
                     passphrase_name_value=CommonVariables.PassphraseNameValueProtected):
        '''This function reads passphrase from passphrase_file, do SKR and wrap passphrase with securely 
        released key. Then it updates metadata (required encryption settings for SKR + wrapped passphrase) 
        to primary token id: 5 type: Azure_Disk_Encryption in Tokens field of LUKS2 header.'''
        self.logger.log(msg="import_token for device: {0} started.".format(device_path))
        self.logger.log(msg="import_token for passphrase file path: {0}.".format(passphrase_file))
        if not passphrase_file or not os.path.exists(passphrase_file):
            self.logger.log(level=CommonVariables.WarningLevel,msg="import_token for passphrase file path: {0} not exists.".format(passphrase_file))
            return False
        protector= ""
        with open(passphrase_file,"rb") as protector_file:
            #passphrase stored in keyfile is base64
            protector = protector_file.read().decode('utf-8')
        kek_vault_resource_id=public_settings.get(CommonVariables.KekVaultResourceIdKey)
        key_encryption_key_url=public_settings.get(CommonVariables.KeyEncryptionKeyURLKey)
        attestation_url = public_settings.get(CommonVariables.AttestationURLKey)
        if passphrase_name_value == CommonVariables.PassphraseNameValueProtected:
            protector = self._secure_key_release_operation(protector_base64=protector,
                                                        kek_url=key_encryption_key_url,
                                                        operation=CommonVariables.secure_key_release_wrap,
                                                        attestation_url=attestation_url)
        else:
            self.logger.log(msg="import_token passphrase is not wrapped, value of passphrase name key: {0}".format(passphrase_name_value))

        if not protector:
            self.logger.log("import_token protector wrapping is unsuccessful for device {0}".format(device_path))
            return False
        data={
            "version":CommonVariables.ADEEncryptionVersionInLuksToken_1_0,
            "type":"Azure_Disk_Encryption",
            "keyslots":[],
            CommonVariables.KekVaultResourceIdKey:kek_vault_resource_id,
            CommonVariables.KeyEncryptionKeyURLKey:key_encryption_key_url,
            CommonVariables.KeyVaultResourceIdKey:public_settings.get(CommonVariables.KeyVaultResourceIdKey),
            CommonVariables.KeyVaultURLKey:public_settings.get(CommonVariables.KeyVaultURLKey),
            CommonVariables.AttestationURLKey:attestation_url,
            CommonVariables.PassphraseNameKey:passphrase_name_value,
            CommonVariables.PassphraseKey:protector
        }
        status = self.import_token_data(device_path=device_path,
                                        token_data=data,
                                        token_id=CommonVariables.cvm_ade_vm_encryption_token_id)
        self.logger.log(msg="import_token: device: {0} end.".format(device_path))
        return status

    def export_token(self,device_name):
        '''This function reads wrapped passphrase from LUKS2 Tokens for
        token id:5, which belongs to primary token type: Azure_Disk_Encryption
        and do SKR and returns unwrapped passphrase'''
        self.logger.log("export_token: for device_name: {0} started.".format(device_name))
        device_path = self.disk_util.get_device_path(device_name)
        if not device_path:
            self.logger.log(level= CommonVariables.WarningLevel, msg="export_token Input is not valid. device name: {0}".format(device_name))
            return None
        protector = None
        cvm_ade_vm_encryption_token_id = self.get_token_id(header_or_dev_path=device_path,token_name=CommonVariables.AzureDiskEncryptionToken)
        if not cvm_ade_vm_encryption_token_id:
            self.logger.log("export_token token id {0} not found in device {1} LUKS header".format(cvm_ade_vm_encryption_token_id,device_name))
            return None
        disk_encryption_setting=self.read_token(device_name=device_name,token_id=cvm_ade_vm_encryption_token_id)
        if disk_encryption_setting['version'] != CommonVariables.ADEEncryptionVersionInLuksToken_1_0:
            self.logger.log("export_token token version {0} is not a vaild version.".format(disk_encryption_setting['version']))
            return None
        key_encryption_key_url=disk_encryption_setting[CommonVariables.KeyEncryptionKeyURLKey]
        wrapped_protector = disk_encryption_setting[CommonVariables.PassphraseKey]
        attestation_url = disk_encryption_setting[CommonVariables.AttestationURLKey]
        if disk_encryption_setting[CommonVariables.PassphraseNameKey] != CommonVariables.PassphraseNameValueProtected:
            self.logger.log(level=CommonVariables.WarningLevel, msg="passphrase is not Protected. No need to do SKR.")
            return wrapped_protector if wrapped_protector else None
        if wrapped_protector:
            #unwrap the protector.
            protector=self._secure_key_release_operation(attestation_url=attestation_url,
                                                        kek_url=key_encryption_key_url,
                                                        protector_base64=wrapped_protector,
                                                        operation=CommonVariables.secure_key_release_unwrap)
        self.logger.log("export_token to device {0} end.".format(device_name))
        return protector

    def remove_token(self, device_name, token_id):
        '''this function remove the token'''
        device_path = self.disk_util.get_device_path(dev_name=device_name)
        if not device_path or not token_id:
            self.logger.log(level=CommonVariables.WarningLevel,
                            msg="remove_token: Inputs are not valid. device name: {0}, token_id: {1}".format(device_name,token_id))
            return False
        cmd = "cryptsetup token remove --token-id {0} {1}".format(token_id,device_path)
        process_comm = ProcessCommunicator()
        status = self.command_executor.Execute(cmd, communicator=process_comm)
        if status != 0:
            self.logger.log(level=CommonVariables.WarningLevel,
                            msg="remove_token: token id: {0} is not found for device_name: {1} in LUKS header".format(token_id,device_name))
            return False
        return True

    def read_token(self, device_name, token_id):
        '''this functions reads tokens from LUKS2 header.'''
        device_path = self.disk_util.get_device_path(dev_name=device_name)
        if not device_path or not token_id:
            self.logger.log(level=CommonVariables.WarningLevel,
                            msg="read_token: Inputs are not valid. device_name: {0}, token id: {1}".format(device_name,token_id))
            return None
        cmd = "cryptsetup token export --token-id {0} {1}".format(token_id,device_path)
        process_comm = ProcessCommunicator()
        status = self.command_executor.Execute(cmd, communicator=process_comm)
        if status != 0:
            self.logger.log(level=CommonVariables.WarningLevel,
                            msg="read_token: token id: {0} is not found for device_name: {1} in LUKS header".format(token_id,device_name))
            return None
        token = process_comm.stdout
        return json.loads(token)

    def get_token_id(self, header_or_dev_path, token_name):
        '''if LUKS2 header has token name return the id else return none.'''
        if not header_or_dev_path or not os.path.exists(header_or_dev_path) or not token_name:
            self.logger.log("get_token_id: invalid input, header_or_dev_path:{0} token_name:{1}".format(header_or_dev_path,token_name))
            return None
        luks_dump_out = self.disk_util.luks_get_header_dump(header_or_dev_path)
        tokens = self.extract_luks2_token(luks_dump_out)
        for token in tokens:
            if len(token) == 2 and token[1] == token_name:
                return token[0]
        return None

    def restore_luks2_token(self, device_name=None):
        '''this function restores token
        type:Azure_Disk_Encryption_BackUp, id:6 to type:Azure_Disk_Encryption id:5,
        this function acts on 4 scenarios.
        1. both token id: 5 and 6 present in LUKS2 Tokens field, due to reboot/interrupt during
        KEK rotation, such case remove token id 5 has latest data so remove token id 6.
        2. token id 5 present but 6 is not present in LUKS2 Tokens field. do nothing.
        3. token id 5 not present but 6 present in LUKS2 Tokens field, restore token id 5 using
        token id 6, then remove token id 6.
        4. no token ids 5 or 6 present in LUKS2 Tokens field, do nothing.'''
        device_path = self.disk_util.get_device_path(device_name)
        if not device_path:
            self.logger.log(level=CommonVariables.WarningLevel,msg="restore_luks2_token invalid input. device_name = {0}".format(device_name))
            return
        ade_token_id_primary = self.get_token_id(header_or_dev_path=device_path,token_name=CommonVariables.AzureDiskEncryptionToken)
        ade_token_id_backup = self.get_token_id(header_or_dev_path=device_path,token_name=CommonVariables.AzureDiskEncryptionBackUpToken)
        if not ade_token_id_backup:
            #do nothing
            return
        if ade_token_id_primary:
            #remove backup token id
            self.remove_token(device_name=device_name,token_id=ade_token_id_backup)
            return
        #ade_token_id_backup having value but ade_token_id_primary is none
        self.logger.log("restore luks2 token for device {0} is started.".format(device_name))
        #read from backup and update AzureDiskEncryptionToken
        data = self.read_token(device_name=device_name,token_id=ade_token_id_backup)
        data['type']=CommonVariables.AzureDiskEncryptionToken
        self.import_token_data(device_path=device_path,token_data=data,token_id=CommonVariables.cvm_ade_vm_encryption_token_id)
        #remove backup
        self.remove_token(device_name=device_name,token_id=ade_token_id_backup)
        self.logger.log("restore luks2 token id {0} to {1} for device {2} is successful.".format(ade_token_id_backup,CommonVariables.cvm_ade_vm_encryption_token_id,device_name))

    def extract_luks2_token(self, luks_dump_out):
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
            6: Azure_Disk_Encryption_BackUp
            5: Azure_Disk_Encryption
        ...
        """
        if not luks_dump_out:
            return []
        lines = luks_dump_out.split("\n")
        token_segment = False
        token_lines = []
        for line in lines:
            parts = line.split(":")
            if len(parts)<2:
                continue
            if token_segment and parts[1].strip() == '':
                break
            if "tokens" in parts[0].strip().lower():
                token_segment = True
                continue
            if token_segment and self._isnumeric(parts[0].strip()):
                token_lines.append([int(parts[0].strip()),parts[1].strip()])
                continue
        return token_lines