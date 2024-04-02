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
import sys
import re
import os
import tempfile
import traceback

from Common import CommonVariables, CryptItem
from EncryptionConfig import EncryptionConfig
from ExtensionParameter import ExtensionParameter
from DiskUtil import DiskUtil
from BekUtil import BekUtil
from CVMDiskUtil import CVMDiskUtil
class CVMLuksUtil(object):
    '''This class contains CVM utils used in handle.py'''

    @staticmethod
    def create_temp_file(file_content):
        '''This function is creating a temp file of file_content. returning a file name.'''
        temp_keyfile = tempfile.NamedTemporaryFile(delete=False)
        if isinstance(file_content, bytes):
            temp_keyfile.write(file_content)
        else:
            temp_keyfile.write(file_content.encode("utf-8"))
        temp_keyfile.close()
        return temp_keyfile.name
    
    @staticmethod
    def is_confidential_temp_disk_encryption(public_settings,logger):
        '''this function reads cvm public setting NoConfidentialEncryptionTempDisk for cvm temp disk encryption.
        function returns true/false for for temp disk encryption. by default return is True.'''
        no_confidential_encryption_tempdisk = public_settings.get("NoConfidentialEncryptionTempDisk")
        no_confidential_encryption_tempdisk_flag = False
        msg = ""
        if no_confidential_encryption_tempdisk.__class__.__name__ in ['str','bool']:
            if no_confidential_encryption_tempdisk.__class__.__name__ == 'str' and no_confidential_encryption_tempdisk.lower() == "true":
                no_confidential_encryption_tempdisk_flag=True
            else:
                no_confidential_encryption_tempdisk_flag=no_confidential_encryption_tempdisk
            msg="NoConfidentialEncryptionTempDisk: {0}".format(no_confidential_encryption_tempdisk_flag)
        else:
            if no_confidential_encryption_tempdisk:
                msg="Invalid input {0}. NoConfidentialEncryptionTempDisk is set an invalid value by customer.".format(no_confidential_encryption_tempdisk)
            else:
                msg="NoConfidentialEncryptionTempDisk is not set,default value is false."
        logger.log(msg=msg)
        return not no_confidential_encryption_tempdisk_flag        
    
    @staticmethod
    def add_new_passphrase_luks2_key_slot(disk_util,\
                        existing_passphrase,\
                        new_passphrase,\
                        device_path,\
                        luks_header_path,\
                        logger):
        '''This function is used to add a new passphrase in luks key slot.'''
        logger.log("add_new_passphrase_luks2_key_slot: start!")
        ret = False
        try:
            before_key_slots = disk_util.luks_dump_keyslots(device_path, luks_header_path)
            logger.log("Before key addition, key slots for {0}: {1}".format(device_path, before_key_slots))
            logger.log("Adding new key for {0}".format(device_path))
            existing_passphrase_file_name = CVMLuksUtil.create_temp_file(existing_passphrase)
            new_passphrase_file_name = CVMLuksUtil.create_temp_file(new_passphrase)
            luks_add_result = disk_util.luks_add_key(passphrase_file=existing_passphrase_file_name,
                                                dev_path=device_path,
                                                mapper_name=None,
                                                header_file=luks_header_path,
                                                new_key_path=new_passphrase_file_name)
            logger.log("luks add result is {0}".format(luks_add_result))
            after_key_slots = disk_util.luks_dump_keyslots(device_path, luks_header_path)
            logger.log("After key addition, key slots for {0}: {1}".format(device_path, after_key_slots))
            new_key_slot = list([x[0] != x[1] for x in zip(before_key_slots, after_key_slots)]).index(True)
            logger.log("New key was added in key slot {0}".format(new_key_slot))
            os.unlink(existing_passphrase_file_name)
            os.unlink(new_passphrase_file_name)
            ret = True
        except Exception as e:
            msg="add_new_passphrase_luks2_key_slot failed with error {0}, stack trace: {1}".format(e, traceback.format_exc())
            logger.log(msg=msg,level=CommonVariables.WarningLevel)
        logger.log("add_new_passphrase_luks2_key_slot: end!")
        return ret

    @staticmethod
    def remove_passphrase_luks2_key_slot(disk_util,\
                            passphrase,\
                            device_path,\
                            luks_header_path,\
                            logger):
        '''This function is used for removing a passphrase from luks key slot.'''
        logger.log("remove_passphrase_luks2_key_slot: start!")
        ret = False
        try:
            before_key_slots = disk_util.luks_dump_keyslots(device_path, luks_header_path)
            logger.log("Before key removal, key slots for {0}: {1}".format(device_path, before_key_slots))
            logger.log("Removing new key for {0}".format(device_path))
            passphrase_file_name = CVMLuksUtil.create_temp_file(passphrase)
            luks_remove_result = disk_util.luks_remove_key(passphrase_file=passphrase_file_name,
                                                        dev_path=device_path,
                                                        header_file=luks_header_path)
            logger.log("luks remove result is {0}".format(luks_remove_result))
            after_key_slots = disk_util.luks_dump_keyslots(device_path, luks_header_path)
            logger.log("After key removal, key slots for {0}: {1}".format(device_path, after_key_slots))
            os.unlink(passphrase_file_name)
            ret = True
        except Exception as e:
            msg="remove_passphrase_luks2_key_slot failed with error {0}, stack trace: {1}".format(e, traceback.format_exc())
            logger.log(msg=msg,level=CommonVariables.WarningLevel)
        logger.log("remove_passphrase_luks2_key_slot: end!")
        return ret

    @staticmethod
    def update_encryption_settings_luks2_header(hutil,logger,public_setting,encryption_environment,protected_settings,extra_items_to_encrypt=None):
        '''This function is used for updating metadata information in LUKS2 header.'''
        if extra_items_to_encrypt is None:
            extra_items_to_encrypt=[]
        hutil.do_parse_context('UpdateEncryptionSettingsLuks2Header')
        logger.log('Updating encryption settings LUKS-2 header')
        # ensure cryptsetup package is still available in case it was for some reason removed after enable
        try:
            hutil.patching.install_cryptsetup()
        except Exception as e:
            hutil.save_seq()
            message = "Failed to update encryption settings with error: {0}, stack trace: {1}".format(e, traceback.format_exc())
            hutil.do_exit(exit_code=CommonVariables.missing_dependency,
                        operation='UpdateEncryptionSettingsLuks2Header',
                        status=CommonVariables.extension_error_status,
                        code=str(CommonVariables.missing_dependency),
                        message=message)
        try:
            encryption_config = EncryptionConfig(encryption_environment, logger)
            extension_parameter = ExtensionParameter(hutil, logger, hutil.patching, encryption_environment, protected_settings, public_setting)
            disk_util = DiskUtil(hutil=hutil, patching=hutil.patching, logger=logger, encryption_environment=encryption_environment)
            bek_util = BekUtil(disk_util, logger, encryption_environment)
            cvm_disk_util = CVMDiskUtil(disk_util=disk_util, logger=logger)
            device_items = disk_util.get_device_items(None)
            if extension_parameter.passphrase is None or extension_parameter.passphrase == "":
                extension_parameter.passphrase = bek_util.generate_passphrase()

            for device_item in device_items:
                device_item_path = disk_util.get_device_path(device_item.name)
                if not disk_util.is_luks_device(device_item_path,None):
                    logger.log("Not a LUKS device, device path: {0}".format(device_item_path))
                    continue
                #restoring the token data to type Azure_Disk_Encryption
                #It is necessary to restore if we are resuming from previous attempt, otherwise its no-op.
                cvm_disk_util.restore_luks2_token(device_name=device_item.name)
                logger.log("Reading passphrase from LUKS2 header, device name: {0}".format(device_item.name))
                #copy primary token to backup token for recovery, if reboot or interrupt happened during KEK rotation.
                ade_primary_token_id = cvm_disk_util.get_token_id(header_or_dev_path=device_item_path,token_name=CommonVariables.AzureDiskEncryptionToken)
                if not ade_primary_token_id:
                    logger.log("primary token type: Azure_Disk_Encryption not found for device {0}".format(device_item.name))
                    continue
                data = cvm_disk_util.read_token(device_name=device_item.name,token_id=ade_primary_token_id)
                #writing primary token data to backup token, update token type to back up.
                data['type']=CommonVariables.AzureDiskEncryptionBackUpToken
                #update backup token data to backup token id:6.
                cvm_disk_util.import_token_data(device_path=device_item_path,token_data=data,token_id=CommonVariables.cvm_ade_vm_encryption_backup_token_id)
                #get the unwrapped passphrase from LUKS2 header.
                passphrase=cvm_disk_util.export_token(device_name=device_item.name)
                if not passphrase:
                    logger.log(level=CommonVariables.WarningLevel,
                            msg="No passphrase found in LUKS2 header, device name: {0}".format(device_item.name))
                    continue
                #remove primary token from Tokens field of LUKS2 header.
                cvm_disk_util.remove_token(device_name=device_item.name,token_id=ade_primary_token_id)
                logger.log("Updating wrapped passphrase to LUKS2 header with current public setting. device name {0}".format(device_item.name))
                #add new slot with new passphrase.
                is_added = CVMLuksUtil.add_new_passphrase_luks2_key_slot(disk_util=disk_util,
                                    existing_passphrase=passphrase,
                                    new_passphrase=extension_parameter.passphrase,
                                    device_path= device_item_path,
                                    luks_header_path=None,
                                    logger= logger)
                if not is_added:
                    logger.log(level=CommonVariables.WarningLevel,
                            msg="new passphrase is not added to LUKS2 slot. Skip operation for device: {0}".format(device_item.name))
                    continue
                #protect passphrase before updating to LUKS2 is done in import_token
                new_passphrase_file = CVMLuksUtil.create_temp_file(extension_parameter.passphrase)
                #save passphrase to LUKS2 header with PassphraseNameValueProtected
                ret = cvm_disk_util.import_token(device_path=device_item_path,
                                            passphrase_file=new_passphrase_file,
                                            public_settings=public_setting,
                                            passphrase_name_value=CommonVariables.PassphraseNameValueProtected)
                if not ret:
                    logger.log(level=CommonVariables.WarningLevel,
                            msg="Update passphrase with current public setting to LUKS2 header is not successful. device path {0}".format(device_item_path))
                    return None
                os.unlink(new_passphrase_file)
                #removing old password form key slot.
                is_removed = CVMLuksUtil.remove_passphrase_luks2_key_slot(disk_util=disk_util,
                                                            passphrase=passphrase,
                                                            device_path=device_item_path,
                                                            luks_header_path=None,
                                                            logger=logger)
                if not is_removed:
                    logger.log(level=CommonVariables.WarningLevel,
                            msg="old passphrase is not removed from LUKS2 slot. Skip operation for device: {0}".format(device_item.name))
                #removing backup token as KEK rotation is successful here.
                cvm_disk_util.remove_token(device_name=device_item.name,
                                    token_id=CommonVariables.cvm_ade_vm_encryption_backup_token_id)
                #update passphrase file for auto unlock
                key_file_name = CommonVariables.encryption_key_file_name
                scsi_lun_numbers = disk_util.get_azure_data_disk_controller_and_lun_numbers([os.path.realpath(device_item_path)])
                if len(scsi_lun_numbers) != 0:
                    scsi_controller, lun_number = scsi_lun_numbers[0]
                    key_file_name = "{0}_{1}_{2}".format(key_file_name,str(scsi_controller),str(lun_number))
                bek_util.store_bek_passphrase_file_name(encryption_config=encryption_config,
                                                        passphrase=extension_parameter.passphrase,
                                                        key_file_name=key_file_name)
            #committing the extension parameter if KEK rotation is successful.
            extension_parameter.commit()

            if len(extra_items_to_encrypt) > 0:
                hutil.do_status_report(operation='UpdateEncryptionSettingsLuks2Header',
                                    status=CommonVariables.extension_success_status,
                                    status_code=str(CommonVariables.success),
                                    message='Encryption settings updated in LUKS2 header')
            else:
                hutil.do_exit(exit_code=0,
                            operation='UpdateEncryptionSettingsLuks2Header',
                            status=CommonVariables.extension_success_status,
                            code=str(CommonVariables.success),
                            message='Encryption settings updated in LUKS2 header')
        except Exception as e:
            hutil.save_seq()
            message = "Failed to update encryption settings Luks2 header with error: {0}, stack trace: {1}".format(e, traceback.format_exc())
            logger.log(msg=message, level=CommonVariables.ErrorLevel)
            hutil.do_exit(exit_code=CommonVariables.unknown_error,
                        operation='UpdateEncryptionSettingsLuks2Header',
                        status=CommonVariables.extension_error_status,
                        code=str(CommonVariables.unknown_error),
                        message=message)
