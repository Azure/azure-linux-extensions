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

import filecmp
import json
import os
import os.path
import re
import subprocess
import sys
import time
import tempfile
import traceback
import uuid
import shutil

from Utils import HandlerUtil
from Common import CommonVariables, CryptItem
from ExtensionParameter import ExtensionParameter
from DiskUtil import DiskUtil
from CryptMountConfigUtil import CryptMountConfigUtil
from ResourceDiskUtil import ResourceDiskUtil
from BackupLogger import BackupLogger
from EncryptionSettingsUtil import EncryptionSettingsUtil
from EncryptionConfig import EncryptionConfig
from patch import GetDistroPatcher
from BekUtil import BekUtil
from check_util import CheckUtil
from DecryptionMarkConfig import DecryptionMarkConfig
from EncryptionMarkConfig import EncryptionMarkConfig
from EncryptionEnvironment import EncryptionEnvironment
from OnGoingItemConfig import OnGoingItemConfig
from ProcessLock import ProcessLock
from CommandExecutor import CommandExecutor, ProcessCommunicator
from io import open


def install():
    hutil.do_parse_context('Install')
    hutil.do_exit(0, 'Install', CommonVariables.extension_success_status, str(CommonVariables.success), 'Install Succeeded')


def disable():
    hutil.do_parse_context('Disable')
    # archiving old configs during disable rather than uninstall will allow subsequent versions
    # to restore these configs in their update step rather than their install step once all
    # released versions of the extension are at this version or above
    hutil.archive_old_configs()
    hutil.do_exit(0, 'Disable', CommonVariables.extension_success_status, '0', 'Disable succeeded')


def uninstall():
    hutil.do_parse_context('Uninstall')
    hutil.do_exit(0, 'Uninstall', CommonVariables.extension_success_status, '0', 'Uninstall succeeded')


def disable_encryption():
    hutil.do_parse_context('DisableEncryption')

    logger.log('Disabling encryption')

    decryption_marker = DecryptionMarkConfig(logger, encryption_environment)

    exit_status = {
        'operation': 'DisableEncryption',
        'status': CommonVariables.extension_success_status,
        'status_code': str(CommonVariables.success),
        'message': 'Decryption completed'
    }

    hutil.exit_if_same_seq(exit_status)
    hutil.save_seq()

    try:
        extension_parameter = ExtensionParameter(hutil, logger, DistroPatcher, encryption_environment, get_protected_settings(), get_public_settings())

        disk_util = DiskUtil(hutil=hutil, patching=DistroPatcher, logger=logger, encryption_environment=encryption_environment)
        crypt_mount_config_util = CryptMountConfigUtil(logger=logger, encryption_environment=encryption_environment, disk_util=disk_util)

        encryption_status = json.loads(disk_util.get_encryption_status())

        if encryption_status["os"] != "NotEncrypted":
            raise Exception("Disabling encryption is not supported when OS volume is encrypted")

        bek_util = BekUtil(disk_util, logger)
        encryption_config = EncryptionConfig(encryption_environment, logger)
        bek_passphrase_file = bek_util.get_bek_passphrase_file(encryption_config)
        crypt_mount_config_util.consolidate_azure_crypt_mount(bek_passphrase_file)
        crypt_items = crypt_mount_config_util.get_crypt_items()

        logger.log('Found {0} items to decrypt'.format(len(crypt_items)))

        for crypt_item in crypt_items:
            disk_util.create_cleartext_key(crypt_item.mapper_name)

            add_result = disk_util.luks_add_cleartext_key(bek_passphrase_file,
                                                          crypt_item.dev_path,
                                                          crypt_item.mapper_name,
                                                          crypt_item.luks_header_path)
            if add_result != CommonVariables.process_success:
                if disk_util.is_luks_device(crypt_item.dev_path, crypt_item.luks_header_path):
                    raise Exception("luksAdd failed with return code {0}".format(add_result))
                else:
                    logger.log("luksAdd failed with return code {0}".format(add_result))
                    logger.log("Ignoring for now, as device ({0}) does not seem to be a luks device".format(crypt_item.dev_path))

            if crypt_item.dev_path.startswith("/dev/sd"):
                logger.log('Updating crypt item entry to use mapper name')
                logger.log('Device name before update: {0}'.format(crypt_item.dev_path))
                crypt_item.dev_path = disk_util.get_persistent_path_by_sdx_path(crypt_item.dev_path)
                logger.log('Device name after update: {0}'.format(crypt_item.dev_path))

            crypt_item.uses_cleartext_key = True
            crypt_mount_config_util.update_crypt_item(crypt_item)

            logger.log('Added cleartext key for {0}'.format(crypt_item))

        decryption_marker.command = extension_parameter.command
        decryption_marker.volume_type = extension_parameter.VolumeType
        decryption_marker.commit()

        settings_util = EncryptionSettingsUtil(logger)
        settings_util.clear_encryption_settings(disk_util)

        hutil.do_status_report(operation='DisableEncryption',
                               status=CommonVariables.extension_success_status,
                               status_code=str(CommonVariables.success),
                               message='Encryption settings cleared')

        bek_util.store_bek_passphrase(encryption_config, '')

        bek_util.delete_bek_passphrase_file(encryption_config)

        if decryption_marker.config_file_exists():
            logger.log(msg="decryption is marked, starting daemon.", level=CommonVariables.InfoLevel)
            start_daemon('DisableEncryption')
            hutil.do_exit(exit_code=0,
                          operation='DisableEncryption',
                          status=CommonVariables.extension_success_status,
                          code=str(CommonVariables.success),
                          message='Decryption started')

    except Exception as e:
        message = "Failed to disable the extension with error: {0}, stack trace: {1}".format(e, traceback.format_exc())

        logger.log(msg=message, level=CommonVariables.ErrorLevel)
        hutil.do_exit(exit_code=CommonVariables.unknown_error,
                      operation='DisableEncryption',
                      status=CommonVariables.extension_error_status,
                      code=str(CommonVariables.unknown_error),
                      message=message)


def stamp_disks_with_settings(items_to_encrypt, encryption_config):

    disk_util = DiskUtil(hutil=hutil, patching=DistroPatcher, logger=logger, encryption_environment=encryption_environment)
    crypt_mount_config_util = CryptMountConfigUtil(logger=logger, encryption_environment=encryption_environment, disk_util=disk_util)
    bek_util = BekUtil(disk_util, logger)
    current_passphrase_file = bek_util.get_bek_passphrase_file(encryption_config)
    extension_parameter = ExtensionParameter(hutil, logger, DistroPatcher, encryption_environment, get_protected_settings(), get_public_settings())

    # post new encryption settings via wire server protocol
    settings = EncryptionSettingsUtil(logger)
    new_protector_name = settings.get_new_protector_name()
    settings.create_protector_file(current_passphrase_file, new_protector_name)

    data = settings.get_settings_data(
        protector_name=new_protector_name,
        kv_url=extension_parameter.KeyVaultURL,
        kv_id=extension_parameter.KeyVaultResourceId,
        kek_url=extension_parameter.KeyEncryptionKeyURL,
        kek_kv_id=extension_parameter.KekVaultResourceId,
        kek_algorithm=extension_parameter.KeyEncryptionAlgorithm,
        extra_device_items=items_to_encrypt,
        disk_util=disk_util,
        crypt_mount_config_util=crypt_mount_config_util)

    settings.post_to_wireserver(data)

    # exit transitioning state by issuing a status report indicating
    # that the necessary encryption settings are stamped successfully
    hutil.do_status_report(operation='StartEncryption',
                           status=CommonVariables.extension_success_status,
                           status_code=str(CommonVariables.success),
                           message='Encryption settings stamped')

    filenames = []
    for disk in data.get("Disks", []):
        for volume in disk.get("Volumes", []):
            for tag in volume.get("SecretTags", []):
                if tag.get("Name") == 'DiskEncryptionKeyFileName':
                    if tag.get("Value") is not None:
                        filenames.append(str(tag["Value"]))

    for filename in filenames:
        filepath = os.path.join(CommonVariables.encryption_key_mount_point, filename)
        if filepath != current_passphrase_file:
            shutil.copyfile(current_passphrase_file, filepath)

    settings.remove_protector_file(new_protector_name)

    encryption_config.passphrase_file_name = extension_parameter.DiskEncryptionKeyFileName
    encryption_config.volume_type = extension_parameter.VolumeType
    encryption_config.secret_id = new_protector_name
    encryption_config.secret_seq_num = hutil.get_current_seq()
    encryption_config.commit()
    extension_parameter.commit()


def are_disks_stamped_with_current_config(encryption_config):
    return encryption_config.get_secret_seq_num() == str(hutil.get_current_seq())


def get_public_settings():
    public_settings_str = hutil._context._config['runtimeSettings'][0]['handlerSettings'].get('publicSettings')
    if isinstance(public_settings_str, str):
        return json.loads(public_settings_str)
    else:
        return public_settings_str


def get_protected_settings():
    protected_settings_str = hutil._context._config['runtimeSettings'][0]['handlerSettings'].get('protectedSettings')
    if isinstance(protected_settings_str, str):
        return json.loads(protected_settings_str)
    else:
        return protected_settings_str


def update_encryption_settings(extra_items_to_encrypt=[]):
    hutil.do_parse_context('UpdateEncryptionSettings')
    logger.log('Updating encryption settings')

    # ensure cryptsetup package is still available in case it was for some reason removed after enable
    try:
        DistroPatcher.install_cryptsetup()
    except Exception as e:
        hutil.save_seq()
        message = "Failed to update encryption settings with error: {0}, stack trace: {1}".format(e, traceback.format_exc())
        hutil.do_exit(exit_code=CommonVariables.missing_dependency,
                      operation='UpdateEncryptionSettings',
                      status=CommonVariables.extension_error_status,
                      code=str(CommonVariables.missing_dependency),
                      message=message)

    encryption_config = EncryptionConfig(encryption_environment, logger)
    config_secret_seq = encryption_config.get_secret_seq_num()
    if config_secret_seq is None:
        current_secret_seq_num = -1
    else:
        current_secret_seq_num = int(config_secret_seq)

    update_call_seq_num = hutil.get_current_seq()

    logger.log("Current secret was created in operation #{0}".format(current_secret_seq_num))
    logger.log("The update call is operation #{0}".format(update_call_seq_num))

    executor = CommandExecutor(logger)
    executor.Execute("mount /boot")

    settings_stamped = False
    updated_crypt_items = []
    old_passphrase = None

    try:
        extension_parameter = ExtensionParameter(hutil, logger, DistroPatcher, encryption_environment, get_protected_settings(), get_public_settings())

        disk_util = DiskUtil(hutil=hutil, patching=DistroPatcher, logger=logger, encryption_environment=encryption_environment)
        crypt_mount_config_util = CryptMountConfigUtil(logger=logger, encryption_environment=encryption_environment, disk_util=disk_util)
        bek_util = BekUtil(disk_util, logger)
        existing_passphrase_file = bek_util.get_bek_passphrase_file(encryption_config)
        if not existing_passphrase_file:
            hutil.save_seq()
            message = "Cannot find current passphrase file. This could happen if BEK volume is not mounted or LinuxPassPhrase file is missing from BEK volume."
            hutil.do_exit(exit_code=CommonVariables.configuration_error,
                          operation='UpdateEncryptionSettings',
                          status=CommonVariables.extension_error_status,
                          code=str(CommonVariables.configuration_error),
                          message=message)

        with open(existing_passphrase_file, 'r') as f:
            old_passphrase = f.read()

        if current_secret_seq_num < update_call_seq_num:
            if extension_parameter.passphrase is None or extension_parameter.passphrase == "":
                extension_parameter.passphrase = bek_util.generate_passphrase()

            logger.log('Recreating secret to store in the KeyVault')

            temp_keyfile = tempfile.NamedTemporaryFile(delete=False)
            temp_keyfile.write(extension_parameter.passphrase)
            temp_keyfile.close()

            crypt_mount_config_util.consolidate_azure_crypt_mount(existing_passphrase_file)
            for crypt_item in crypt_mount_config_util.get_crypt_items():
                if not crypt_item:
                    continue

                before_keyslots = disk_util.luks_dump_keyslots(crypt_item.dev_path, crypt_item.luks_header_path)

                logger.log("Before key addition, keyslots for {0}: {1}".format(crypt_item.dev_path, before_keyslots))

                logger.log("Adding new key for {0}".format(crypt_item.dev_path))

                luks_add_result = disk_util.luks_add_key(passphrase_file=existing_passphrase_file,
                                                         dev_path=crypt_item.dev_path,
                                                         mapper_name=crypt_item.mapper_name,
                                                         header_file=crypt_item.luks_header_path,
                                                         new_key_path=temp_keyfile.name)

                logger.log("luks add result is {0}".format(luks_add_result))

                after_keyslots = disk_util.luks_dump_keyslots(crypt_item.dev_path, crypt_item.luks_header_path)

                logger.log("After key addition, keyslots for {0}: {1}".format(crypt_item.dev_path, after_keyslots))

                new_keyslot = list([x[0] != x[1] for x in zip(before_keyslots, after_keyslots)]).index(True)

                logger.log("New key was added in keyslot {0}".format(new_keyslot))

                updated_crypt_items.append(crypt_item)

            logger.log("New key successfully added to all encrypted devices")

            if DistroPatcher.distro_info[0] == "Ubuntu":
                executor.Execute("update-initramfs -u -k all", True)

            if DistroPatcher.distro_info[0] == "redhat" or DistroPatcher.distro_info[0] == "centos":
                distro_version = DistroPatcher.distro_info[1]

                if distro_version.startswith('7.'):
                    executor.ExecuteInBash("/usr/sbin/dracut -f -v --kver `grubby --default-kernel | sed 's|/boot/vmlinuz-||g'`", True)
                    logger.log("Update initrd image with new osluksheader.")

            os.unlink(temp_keyfile.name)

            # store new passphrase and overwrite old encryption key file
            bek_util.store_bek_passphrase(encryption_config, extension_parameter.passphrase)

            stamp_disks_with_settings(items_to_encrypt=extra_items_to_encrypt, encryption_config=encryption_config)
            settings_stamped = True

            existing_passphrase_file = bek_util.get_bek_passphrase_file(encryption_config)

            logger.log('Secret has already been updated')
            disk_util.log_lsblk_output()

            if extension_parameter.passphrase and extension_parameter.passphrase != file(existing_passphrase_file).read():
                logger.log("The new passphrase has not been placed in BEK volume yet")
                logger.log("Skipping removal of old passphrase")
                exit_without_status_report()

            logger.log('Removing old passphrase')

            temp_oldkeyfile = tempfile.NamedTemporaryFile(delete=False)
            temp_oldkeyfile.write(old_passphrase)
            temp_oldkeyfile.close()

            for crypt_item in crypt_mount_config_util.get_crypt_items():
                if not crypt_item:
                    continue

                if filecmp.cmp(existing_passphrase_file, temp_oldkeyfile.name):
                    logger.log('Current BEK and backup are the same, skipping removal')
                    continue

                logger.log('Removing old passphrase from {0}'.format(crypt_item.dev_path))

                keyslots = disk_util.luks_dump_keyslots(crypt_item.dev_path, crypt_item.luks_header_path)
                logger.log("Keyslots before removal: {0}".format(keyslots))

                luks_remove_result = disk_util.luks_remove_key(passphrase_file=temp_oldkeyfile.name,
                                                               dev_path=crypt_item.dev_path,
                                                               header_file=crypt_item.luks_header_path)
                logger.log("luks remove result is {0}".format(luks_remove_result))

                keyslots = disk_util.luks_dump_keyslots(crypt_item.dev_path, crypt_item.luks_header_path)
                logger.log("Keyslots after removal: {0}".format(keyslots))

            logger.log("Old key successfully removed from all encrypted devices")
            hutil.save_seq()
            extension_parameter.commit()
            os.unlink(temp_oldkeyfile.name)
            bek_util.umount_azure_passhprase(encryption_config)

        if len(extra_items_to_encrypt) > 0:
            hutil.do_status_report(operation='UpdateEncryptionSettings',
                                   status=CommonVariables.extension_success_status,
                                   status_code=str(CommonVariables.success),
                                   message='Encryption settings updated')
        else:
            hutil.do_exit(exit_code=0,
                          operation='UpdateEncryptionSettings',
                          status=CommonVariables.extension_success_status,
                          code=str(CommonVariables.success),
                          message='Encryption settings updated')
    except Exception as e:
        hutil.save_seq()
        if not settings_stamped:
            clear_new_luks_keys(disk_util, old_passphrase, extension_parameter.passphrase, bek_util, encryption_config, updated_crypt_items)
        message = "Failed to update encryption settings with error: {0}, stack trace: {1}".format(e, traceback.format_exc())
        logger.log(msg=message, level=CommonVariables.ErrorLevel)
        bek_util.umount_azure_passhprase(encryption_config)
        hutil.do_exit(exit_code=CommonVariables.unknown_error,
                      operation='UpdateEncryptionSettings',
                      status=CommonVariables.extension_error_status,
                      code=str(CommonVariables.unknown_error),
                      message=message)


def clear_new_luks_keys(disk_util, old_passphrase, new_passphrase, bek_util, encryption_config, updated_crypt_items):
    try:

        if not old_passphrase:
            logger.log("Old passphrase does not exist. Nothing to revert.")
            return

        if not new_passphrase:
            logger.log("New passphrase does not exist. Nothing to clear.")
            return

        temp_keyfile = tempfile.NamedTemporaryFile(delete=False)
        temp_keyfile.write(new_passphrase)
        temp_keyfile.close()

        executor = CommandExecutor(logger)
        for crypt_item in updated_crypt_items:
            if not crypt_item:
                continue

            logger.log('Removing new passphrase from {0}'.format(crypt_item.dev_path))
            before_keyslots = disk_util.luks_dump_keyslots(crypt_item.dev_path, crypt_item.luks_header_path)
            logger.log("Keyslots before removal: {0}".format(before_keyslots))

            luks_remove_result = disk_util.luks_remove_key(passphrase_file=temp_keyfile.name,
                                                           dev_path=crypt_item.dev_path,
                                                           header_file=crypt_item.luks_header_path)

            logger.log("luks remove result is {0}".format(luks_remove_result))

            after_keyslots = disk_util.luks_dump_keyslots(crypt_item.dev_path, crypt_item.luks_header_path)
            logger.log("Keyslots after removal: {0}".format(after_keyslots))

        if DistroPatcher.distro_info[0] == "Ubuntu":
            executor.Execute("update-initramfs -u -k all", True)

        if DistroPatcher.distro_info[0] == "redhat" or DistroPatcher.distro_info[0] == "centos":
            distro_version = DistroPatcher.distro_info[1]

            if distro_version.startswith('7.'):
                executor.ExecuteInBash("/usr/sbin/dracut -f -v --kver `grubby --default-kernel | sed 's|/boot/vmlinuz-||g'`", True)
                logger.log("Update initrd image with new osluksheader.")

        bek_util.store_bek_passphrase(encryption_config, old_passphrase)
        os.unlink(temp_keyfile.name)
        logger.log("Cleared new luks keys.")
    except Exception as e:
        msg = "Failed to clear new luks key with error: {0}, stack trace: {1}".format(e, traceback.format_exc())
        logger.log(msg=msg, level=CommonVariables.WarningLevel)


def update():
    # The extension update handshake is [old:disable][new:update][old:uninstall][new:install]
    # this method is called when updating an older version of the extension to a newer version
    hutil.do_parse_context('Update')
    logger.log("Installing pre-requisites")
    DistroPatcher.install_extras()
    DistroPatcher.update_prereq()
    hutil.do_exit(0, 'Update', CommonVariables.extension_success_status, '0', 'Update Succeeded')


def exit_without_status_report():
    sys.exit(0)


def not_support_header_option_distro(patching):
    if patching.distro_info[0].lower() == "centos" and patching.distro_info[1].startswith('6.'):
        return True
    if patching.distro_info[0].lower() == "redhat" and patching.distro_info[1].startswith('6.'):
        return True
    if patching.distro_info[0].lower() == "suse" and patching.distro_info[1].startswith('11'):
        return True
    return False


def none_or_empty(obj):
    if obj is None or obj == "":
        return True
    else:
        return False


def toggle_se_linux_for_centos7(disable):
    if DistroPatcher.distro_info[0].lower() == 'centos' and DistroPatcher.distro_info[1].startswith('7.0'):
        if disable:
            se_linux_status = encryption_environment.get_se_linux()
            if se_linux_status.lower() == 'enforcing':
                encryption_environment.disable_se_linux()
                return True
        else:
            encryption_environment.enable_se_linux()
    return False


def mount_encrypted_disks(disk_util, crypt_mount_config_util, bek_util, passphrase_file, encryption_config):

    # mount encrypted resource disk
    resource_disk_util = ResourceDiskUtil(logger, disk_util, crypt_mount_config_util, passphrase_file, get_public_settings(), DistroPatcher.distro_info)
    if encryption_config.config_file_exists():
        volume_type = encryption_config.get_volume_type().lower()
        if volume_type == CommonVariables.VolumeTypeData.lower() or volume_type == CommonVariables.VolumeTypeAll.lower():
            resource_disk_util.automount()
            logger.log("mounted resource disk")
    else:
        # Probably a re-image scenario: Just do a best effort
        if resource_disk_util.try_remount():
            logger.log("mounted resource disk")

    # add walkaround for the centos 7.0
    se_linux_status = None
    if DistroPatcher.distro_info[0].lower() == 'centos' and DistroPatcher.distro_info[1].startswith('7.0'):
        se_linux_status = encryption_environment.get_se_linux()
        if se_linux_status.lower() == 'enforcing':
            encryption_environment.disable_se_linux()

    # mount any data disks - make sure the azure disk config path exists.
    for crypt_item in crypt_mount_config_util.get_crypt_items():
        if not crypt_item:
            continue

        if not os.path.exists(os.path.join(CommonVariables.dev_mapper_root, crypt_item.mapper_name)):
            luks_open_result = disk_util.luks_open(passphrase_file=passphrase_file,
                                                   dev_path=crypt_item.dev_path,
                                                   mapper_name=crypt_item.mapper_name,
                                                   header_file=crypt_item.luks_header_path,
                                                   uses_cleartext_key=crypt_item.uses_cleartext_key)
            logger.log("luks open result is {0}".format(luks_open_result))

        disk_util.mount_crypt_item(crypt_item, passphrase_file)

    if DistroPatcher.distro_info[0].lower() == 'centos' and DistroPatcher.distro_info[1].startswith('7.0'):
        if se_linux_status is not None and se_linux_status.lower() == 'enforcing':
            encryption_environment.enable_se_linux()


def main():
    global hutil, DistroPatcher, logger, encryption_environment
    HandlerUtil.waagent.Log("{0} started to handle.".format(CommonVariables.extension_name))

    hutil = HandlerUtil.HandlerUtility(HandlerUtil.waagent.Log, HandlerUtil.waagent.Error, CommonVariables.extension_name)
    logger = BackupLogger(hutil)
    DistroPatcher = GetDistroPatcher(logger)
    hutil.patching = DistroPatcher

    encryption_environment = EncryptionEnvironment(patching=DistroPatcher, logger=logger)

    disk_util = DiskUtil(hutil=hutil, patching=DistroPatcher, logger=logger, encryption_environment=encryption_environment)
    hutil.disk_util = disk_util

    for a in sys.argv[1:]:
        if re.match("^([-/]*)(disable)", a):
            disable()
        elif re.match("^([-/]*)(uninstall)", a):
            uninstall()
        elif re.match("^([-/]*)(install)", a):
            install()
        elif re.match("^([-/]*)(enable)", a):
            if DistroPatcher is None:
                hutil.do_exit(exit_code=CommonVariables.os_not_supported,
                              operation='Enable',
                              status=CommonVariables.extension_error_status,
                              code=(CommonVariables.os_not_supported),
                              message='Enable failed: OS distribution is not supported')
            else:
                enable()
        elif re.match("^([-/]*)(update)", a):
            update()
        elif re.match("^([-/]*)(daemon)", a):
            daemon()


def mark_encryption(command, volume_type, disk_format_query):
    encryption_marker = EncryptionMarkConfig(logger, encryption_environment)
    encryption_marker.command = command
    encryption_marker.volume_type = volume_type
    encryption_marker.diskFormatQuery = disk_format_query
    encryption_marker.commit()
    return encryption_marker


def is_daemon_running():
    handler_path = os.path.join(os.getcwd(), __file__)
    daemon_arg = "-daemon"

    psproc = subprocess.Popen(['ps', 'aux'], stdout=subprocess.PIPE)
    pslist, _ = psproc.communicate()

    for line in pslist.split("\n"):
        if handler_path in line and daemon_arg in line:
            return True

    return False


def enable():
    try:
        hutil.do_parse_context('Enable')
        logger.log('Enabling extension')

        public_settings = get_public_settings()
        logger.log('Public settings:\n{0}'.format(json.dumps(public_settings, sort_keys=True, indent=4)))
        cutil = CheckUtil(logger)
        # Mount already encrypted disks before running fatal prechecks
        disk_util = DiskUtil(hutil=hutil, patching=DistroPatcher, logger=logger, encryption_environment=encryption_environment)
        crypt_mount_config_util = CryptMountConfigUtil(logger=logger, encryption_environment=encryption_environment, disk_util=disk_util)
        bek_util = BekUtil(disk_util, logger)
        existing_passphrase_file = None
        existing_volume_type = None
        encryption_config = EncryptionConfig(encryption_environment=encryption_environment, logger=logger)
        if encryption_config.config_file_exists():
            existing_volume_type = encryption_config.get_volume_type()

        is_migrate_operation = False
        if CommonVariables.MigrateKey in public_settings:
            if public_settings.get(CommonVariables.MigrateKey) == CommonVariables.MigrateValue:
                is_migrate_operation = True

        existing_passphrase_file = bek_util.get_bek_passphrase_file(encryption_config)
        if existing_passphrase_file is not None:
            crypt_mount_config_util.consolidate_azure_crypt_mount(existing_passphrase_file)
            mount_encrypted_disks(disk_util=disk_util,
                                  crypt_mount_config_util=crypt_mount_config_util,
                                  bek_util=bek_util,
                                  encryption_config=encryption_config,
                                  passphrase_file=existing_passphrase_file)
            # Migrate to early unlock if using crypt mount
            if crypt_mount_config_util.should_use_azure_crypt_mount():
                crypt_mount_config_util.migrate_crypt_items()
        elif ResourceDiskUtil.RD_MAPPER_NAME in [ci.mapper_name for ci in crypt_mount_config_util.get_crypt_items()]:
            # If there are crypt items but no passphrase file. This might be a RD-Only scenario
            # Generate password but don't push it
            # Do a mount_all_disks

            generated_passphrase = bek_util.generate_passphrase()
            bek_util.store_bek_passphrase(encryption_config, generated_passphrase)
            generated_passphrase_file = bek_util.get_bek_passphrase_file(encryption_config)
            mount_encrypted_disks(disk_util=disk_util,
                                  crypt_mount_config_util=crypt_mount_config_util,
                                  bek_util=bek_util,
                                  encryption_config=encryption_config,
                                  passphrase_file=generated_passphrase_file)

        encryption_status = json.loads(disk_util.get_encryption_status())
        logger.log('Data Disks Status: {0}'.format(encryption_status['data']))
        logger.log('OS Disk Status: {0}'.format(encryption_status['os']))

        encryption_operation = public_settings.get(CommonVariables.EncryptionEncryptionOperationKey)

        # run fatal prechecks, report error if exceptions are caught
        try:
            if not is_migrate_operation:
                cutil.precheck_for_fatal_failures(public_settings, encryption_status, DistroPatcher, existing_volume_type)
        except Exception as e:
            logger.log("PRECHECK: Fatal Exception thrown during precheck")
            logger.log(traceback.format_exc(e))
            # Reject settings if fatal exception occurs while a daemon is running
            if is_daemon_running():
                hutil.reject_settings()
            msg = str(traceback.format_exc(e))
            hutil.do_exit(exit_code=CommonVariables.configuration_error,
                          operation='Enable',
                          status=CommonVariables.extension_error_status,
                          code=(CommonVariables.configuration_error),
                          message=msg)

        hutil.disk_util.log_lsblk_output()

        # run prechecks and log any failures detected
        try:
            if cutil.is_non_fatal_precheck_failure():
                logger.log("PRECHECK: Precheck failure, incompatible environment suspected")
            else:
                logger.log("PRECHECK: Prechecks successful")
        except Exception as e:
            logger.log("PRECHECK: Exception thrown during precheck")
            logger.log(traceback.format_exc(e))

        if encryption_operation in [CommonVariables.EnableEncryption, CommonVariables.EnableEncryptionFormat, CommonVariables.EnableEncryptionFormatAll]:
            if is_migrate_operation:
                perform_migration(encryption_config, crypt_mount_config_util)
                return  # Control should not reach here but added return just to be safe
            logger.log("handle.py found enable encryption operation")

            handle_encryption(public_settings, encryption_status, disk_util, bek_util, encryption_operation)

        elif encryption_operation == CommonVariables.DisableEncryption:
            logger.log("handle.py found disable encryption operation")
            disable_encryption()

        else:
            msg = "Encryption operation {0} is not supported".format(encryption_operation)
            logger.log(msg)
            hutil.do_exit(exit_code=CommonVariables.configuration_error,
                          operation='Enable',
                          status=CommonVariables.extension_error_status,
                          code=(CommonVariables.configuration_error),
                          message=msg)

    except Exception as e:
        msg = "Unexpected Error during enable: {0}".format(traceback.format_exc(e))
        logger.log(msg)
        hutil.do_exit(exit_code=CommonVariables.unknown_error,
                      operation='Enable',
                      status=CommonVariables.extension_error_status,
                      code=str(CommonVariables.unknown_error),
                      message=msg)


def are_required_devices_encrypted(volume_type, encryption_status, disk_util, bek_util, encryption_operation):
    are_data_disk_encrypted = True if encryption_status['data'] == 'Encrypted' else False
    is_os_disk_encrypted = True if encryption_status['os'] == 'Encrypted' else False
    items_to_encrypt = []
    if volume_type.lower() == CommonVariables.VolumeTypeData.lower():
        if are_data_disk_encrypted:
            logger.log('All data drives are encrypted.')
            return True, items_to_encrypt
        else:
            logger.log('Not all data drives are encrypted.')
            items_to_encrypt = find_all_devices_to_encrypt(None, disk_util, bek_util, volume_type, encryption_operation)
            return False, items_to_encrypt
    elif volume_type.lower() == CommonVariables.VolumeTypeOS.lower():
        if is_os_disk_encrypted:
            logger.log('OS drive is encrypted.')
            return True, items_to_encrypt
        else:
            logger.log('OS Drive is not encrypted.')
            items_to_encrypt = os_device_to_encrypt(disk_util)
            return False, items_to_encrypt
    elif volume_type.lower() == CommonVariables.VolumeTypeAll.lower():
        if are_data_disk_encrypted and is_os_disk_encrypted:
            logger.log('Both OS and Data drives are encrypted.')
            return True, items_to_encrypt
        else:
            if not are_data_disk_encrypted:
                items_to_encrypt = find_all_devices_to_encrypt(None, disk_util, bek_util, volume_type, encryption_operation)
            if not is_os_disk_encrypted:
                items_to_encrypt = items_to_encrypt + os_device_to_encrypt(disk_util)
            return False, items_to_encrypt


def handle_encryption(public_settings, encryption_status, disk_util, bek_util, encryption_operation):
    extension_parameter = ExtensionParameter(hutil, logger, DistroPatcher, encryption_environment, get_protected_settings(), public_settings)
    volume_type = public_settings.get(CommonVariables.VolumeTypeKey)

    if extension_parameter.config_file_exists() and extension_parameter.config_changed():
        logger.log("Config has changed, updating encryption settings")
        hutil.exit_if_same_seq()
        # If a daemon is already running reject and exit an update encryption settings request
        if is_daemon_running():
            logger.log("An operation already running. Cannot accept an update settings request.")
            hutil.reject_settings()
        are_devices_encrypted, items_to_encrypt = are_required_devices_encrypted(volume_type, encryption_status, disk_util, bek_util, encryption_operation)
        if not are_devices_encrypted:
            logger.log('Required devices not encrypted for volume type {0}. Calling update to stamp encryption settings.'.format(volume_type))
            update_encryption_settings(items_to_encrypt)
            logger.log('Encryption Settings stamped. Calling enable to encrypt new devices.')
            enable_encryption()
        else:
            logger.log('Calling Update Encryption Setting.')
            update_encryption_settings()
    else:
        logger.log("Config did not change or first call, enabling encryption")
        encryption_marker = EncryptionMarkConfig(logger, encryption_environment)
        if encryption_marker.config_file_exists():
            logger.log('Encryption marker exists. Calling Enable')
            enable_encryption()
        else:
            hutil.exit_if_same_seq()
            are_devices_encrypted, items_to_encrypt = are_required_devices_encrypted(volume_type, encryption_status, disk_util, bek_util, encryption_operation)
            if are_devices_encrypted:
                hutil.do_exit(exit_code=CommonVariables.success,
                              operation='EnableEncryption',
                              status=CommonVariables.extension_success_status,
                              code=str(CommonVariables.success),
                              message=CommonVariables.SuccessMessage[volume_type.lower()])
            else:
                logger.log('Calling enable for volume type {0}.'.format(volume_type))
                enable_encryption()


def enable_encryption():
    hutil.do_parse_context('EnableEncryption')
    # we need to start another subprocess to do it, because the initial process
    # would be killed by the wala in 5 minutes.
    logger.log('Enabling encryption')

    """
    trying to mount the crypted items.
    """
    disk_util = DiskUtil(hutil=hutil, patching=DistroPatcher, logger=logger, encryption_environment=encryption_environment)
    bek_util = BekUtil(disk_util, logger)

    existing_passphrase_file = None
    encryption_config = EncryptionConfig(encryption_environment=encryption_environment, logger=logger)
    config_path_result = disk_util.make_sure_path_exists(encryption_environment.encryption_config_path)

    if config_path_result != CommonVariables.process_success:
        logger.log(msg="azure encryption path creation failed.",
                   level=CommonVariables.ErrorLevel)

    existing_passphrase_file = bek_util.get_bek_passphrase_file(encryption_config)
    if existing_passphrase_file is None and encryption_config.config_file_exists():
        msg = "EncryptionConfig is present, but could not get the key file."
        try:
            hutil.redo_last_status()
            logger.log(msg=msg, level=CommonVariables.WarningLevel)
            exit_without_status_report()
        except Exception:
            logger.log(msg=msg, level=CommonVariables.ErrorLevel)
            hutil.do_exit(exit_code=CommonVariables.configuration_error,
                          operation='EnableEncyption',
                          status=CommonVariables.extension_error_status,
                          code=str(CommonVariables.configuration_error),
                          message=msg)

    ps = subprocess.Popen(["ps", "aux"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    ps_stdout, ps_stderr = ps.communicate()

    # ps_stdout is data, so decode to string prior to regex for python2 and python3 compat
    if re.search(r"dd.*of={0}".format(disk_util.get_osmapper_path()), ps_stdout.decode("utf-8")):
        logger.log(msg="OS disk encryption already in progress, exiting",
                   level=CommonVariables.WarningLevel)
        try:
            hutil.redo_last_status()
            exit_without_status_report()
        except Exception:
            hutil.do_exit(exit_code=CommonVariables.success,
                          operation='EnableEncyption',
                          status=CommonVariables.extension_success_status,
                          code=str(CommonVariables.success),
                          message="OS disk encryption already in progress")

    # handle the re-call scenario.  the re-call would resume?
    # if there's one tag for the next reboot.
    encryption_marker = EncryptionMarkConfig(logger, encryption_environment)

    try:
        extension_parameter = ExtensionParameter(hutil, logger, DistroPatcher, encryption_environment, get_protected_settings(), get_public_settings())

        encryption_marker = EncryptionMarkConfig(logger, encryption_environment)
        if encryption_marker.config_file_exists():
            # verify the encryption mark
            logger.log(msg="encryption mark is there, starting daemon.", level=CommonVariables.InfoLevel)
            start_daemon('EnableEncryption')
        else:
            encryption_config = EncryptionConfig(encryption_environment, logger)

            hutil.save_seq()

            encryption_config.volume_type = extension_parameter.VolumeType
            encryption_config.commit()

            if encryption_config.config_file_exists() and existing_passphrase_file is not None:
                logger.log(msg="config file exists and passphrase file exists.", level=CommonVariables.WarningLevel)
                encryption_marker = mark_encryption(command=extension_parameter.command,
                                                    volume_type=extension_parameter.VolumeType,
                                                    disk_format_query=extension_parameter.DiskFormatQuery)
                start_daemon('EnableEncryption')
            else:
                # prepare to create secret, place on key volume, and request key vault update via wire protocol

                # validate parameters
                if extension_parameter.command not in [CommonVariables.EnableEncryption, CommonVariables.EnableEncryptionFormat, CommonVariables.EnableEncryptionFormatAll]:
                    encryption_config.clear_config()
                    hutil.do_exit(exit_code=CommonVariables.configuration_error,
                                  operation='EnableEncryption',
                                  status=CommonVariables.extension_error_status,
                                  code=str(CommonVariables.configuration_error),
                                  message='Command "{0}" is not supported'.format(extension_parameter.command))

                # generate passphrase and passphrase file if needed
                if existing_passphrase_file is None:
                    if extension_parameter.passphrase is None or extension_parameter.passphrase == "":
                        extension_parameter.passphrase = bek_util.generate_passphrase()
                    else:
                        logger.log(msg="the extension_parameter.passphrase is already defined")

                    bek_util.store_bek_passphrase(encryption_config, extension_parameter.passphrase)

                if extension_parameter.command == CommonVariables.EnableEncryptionFormatAll:
                    current_volume_type = extension_parameter.VolumeType.lower()
                    if current_volume_type == CommonVariables.VolumeTypeData.lower() or current_volume_type == CommonVariables.VolumeTypeAll.lower():
                        try:
                            DistroPatcher.install_cryptsetup()
                        except Exception as e:
                            hutil.save_seq()
                            message = "Failed to install cryptsetup package(s) with error: {0}, stack trace: {1}".format(e, traceback.format_exc())
                            hutil.do_exit(exit_code=CommonVariables.missing_dependency,
                                          operation='EnableEncryption',
                                          status=CommonVariables.extension_error_status,
                                          code=str(CommonVariables.missing_dependency),
                                          message=message)
                        passphrase_file = bek_util.get_bek_passphrase_file(encryption_config)
                        crypt_mount_config_util = CryptMountConfigUtil(logger=logger, encryption_environment=encryption_environment, disk_util=disk_util)
                        resource_disk_util = ResourceDiskUtil(logger, disk_util, crypt_mount_config_util, passphrase_file, get_public_settings(), DistroPatcher.distro_info)
                        rd_encrypted = resource_disk_util.encrypt_resource_disk()
                        if not rd_encrypted:
                            hutil.save_seq()
                            hutil.do_exit(exit_code=CommonVariables.configuration_error,
                                          operation='EnableEncryption',
                                          status=CommonVariables.extension_error_status,
                                          code=str(CommonVariables.configuration_error),
                                          message='Failed to encrypt resource disk. Please make sure no process is using it.')
                        else:
                            logger.log("Resource Disk is either absent or encrypted successfully.")
                encryption_marker = mark_encryption(command=extension_parameter.command,
                                                    volume_type=extension_parameter.VolumeType,
                                                    disk_format_query=extension_parameter.DiskFormatQuery)
                start_daemon('EnableEncryption')

    except Exception as e:
        hutil.save_seq()
        message = "Failed to enable the extension with error: {0}, stack trace: {1}".format(e, traceback.format_exc())
        logger.log(msg=message, level=CommonVariables.ErrorLevel)
        hutil.do_exit(exit_code=CommonVariables.unknown_error,
                      operation='EnableEncryption',
                      status=CommonVariables.extension_error_status,
                      code=str(CommonVariables.unknown_error),
                      message=message)


def perform_migration(encryption_config, crypt_mount_config_util):
    logger.log("Migrate operation found. Starting migration flow.")
    hutil.exit_if_same_seq()

    extension_parameter = ExtensionParameter(hutil, logger, DistroPatcher, encryption_environment, get_protected_settings(), get_public_settings())
    extension_parameter.VolumeType = encryption_config.get_volume_type()  # After migration config file has current volume type

    encryption_config.volume_type = encryption_config.get_volume_type()
    encryption_config.passphrase_file_name = encryption_config.get_bek_filename()
    encryption_config.secret_seq_num = encryption_config.get_secret_seq_num()

    # Clear 2 pass params and save a new 1 pass config
    encryption_config.clear_config()
    extension_parameter.clear_config()
    encryption_config.commit()
    extension_parameter.commit()

    for crypt_item in crypt_mount_config_util.get_crypt_items():
        if crypt_item.mount_point == "/":
            continue
        backup_folder = os.path.join(crypt_item.mount_point, ".azure_ade_backup_mount_info/")
        crypt_mount_config_util.update_crypt_item(crypt_item, backup_folder=backup_folder)

    hutil.save_seq()
    hutil.do_exit(exit_code=CommonVariables.success,
                  operation='Migrate',
                  status=CommonVariables.extension_success_status,
                  code=(CommonVariables.success),
                  message="Migration Succeeded")


def enable_encryption_format(passphrase, encryption_format_items, disk_util, crypt_mount_config_util, force=False, os_items_to_stamp=[]):
    logger.log('enable_encryption_format')
    logger.log('disk format query is {0}'.format(json.dumps(encryption_format_items)))

    device_items_to_encrypt = []
    encrypt_format_items_to_encrypt = []
    query_dev_paths_to_encrypt = []

    for encryption_item in encryption_format_items:
        dev_path_in_query = None

        if "scsi" in encryption_item and encryption_item["scsi"] != '':
            dev_path_in_query = disk_util.query_dev_sdx_path_by_scsi_id(encryption_item["scsi"])
        if "dev_path" in encryption_item and encryption_item["dev_path"] != '':
            dev_path_in_query = encryption_item["dev_path"]

        if not dev_path_in_query:
            raise Exception("Could not find dev_path in diskFormatQuery part: {0}".format(encryption_item))
        devices = disk_util.get_device_items(dev_path_in_query)
        if len(devices) != 1:
            logger.log(msg=("the device with this path {0} have more than one sub device. so skip it.".format(dev_path_in_query)), level=CommonVariables.WarningLevel)
            continue
        device_item = devices[0]
        if device_item.file_system is None or device_item.file_system == "" or force:
            device_items_to_encrypt.append(device_item)
            encrypt_format_items_to_encrypt.append(encryption_item)
            query_dev_paths_to_encrypt.append(dev_path_in_query)
        else:
            logger.log(msg=("the item fstype is not empty {0}".format(device_item.file_system)))

    # If anything needs to be stamped, do the stamping here
    device_items_to_stamp = device_items_to_encrypt + os_items_to_stamp
    if len(device_items_to_stamp) > 0:
        encryption_config = EncryptionConfig(encryption_environment, logger)
        if not are_disks_stamped_with_current_config(encryption_config):
            stamp_disks_with_settings(items_to_encrypt=device_items_to_stamp,
                                      encryption_config=encryption_config)

    for device_item, encryption_item, dev_path_in_query in zip(device_items_to_encrypt, encrypt_format_items_to_encrypt, query_dev_paths_to_encrypt):
        if device_item.mount_point:
            disk_util.swapoff()
            disk_util.umount(device_item.mount_point)
        mapper_name = str(uuid.uuid4())
        logger.log("encrypting " + str(device_item))
        encrypted_device_path = os.path.join(CommonVariables.dev_mapper_root, mapper_name)
        try:
            se_linux_status = None
            if DistroPatcher.distro_info[0].lower() == 'centos' and DistroPatcher.distro_info[1].startswith('7.0'):
                se_linux_status = encryption_environment.get_se_linux()
                if se_linux_status.lower() == 'enforcing':
                    encryption_environment.disable_se_linux()
            encrypt_result = disk_util.encrypt_disk(dev_path=dev_path_in_query, passphrase_file=passphrase, mapper_name=mapper_name, header_file=None)
        finally:
            if DistroPatcher.distro_info[0].lower() == 'centos' and DistroPatcher.distro_info[1].startswith('7.0'):
                if se_linux_status is not None and se_linux_status.lower() == 'enforcing':
                    encryption_environment.enable_se_linux()

        if encrypt_result == CommonVariables.process_success:
            # TODO: let customer specify the default file system in the
            # parameter
            file_system = None
            if "file_system" in encryption_item and encryption_item["file_system"] != "":
                file_system = encryption_item["file_system"]
            else:
                file_system = CommonVariables.default_file_system
            format_disk_result = disk_util.format_disk(dev_path=encrypted_device_path, file_system=file_system)
            if format_disk_result != CommonVariables.process_success:
                logger.log(msg=("format of disk {0} failed with result: {1}".format(encrypted_device_path, format_disk_result)), level=CommonVariables.ErrorLevel)
                return device_item
            crypt_item_to_update = CryptItem()
            crypt_item_to_update.mapper_name = mapper_name
            crypt_item_to_update.dev_path = dev_path_in_query
            crypt_item_to_update.luks_header_path = None
            crypt_item_to_update.file_system = file_system
            crypt_item_to_update.uses_cleartext_key = False
            crypt_item_to_update.current_luks_slot = 0

            if "name" in encryption_item and encryption_item["name"] != "":
                crypt_item_to_update.mount_point = os.path.join("/mnt/", str(encryption_item["name"]))
            else:
                crypt_item_to_update.mount_point = os.path.join("/mnt/", mapper_name)

            # allow override through the new full_mount_point field
            if "full_mount_point" in encryption_item and encryption_item["full_mount_point"] != "":
                crypt_item_to_update.mount_point = os.path.join(str(encryption_item["full_mount_point"]))

            disk_util.make_sure_path_exists(crypt_item_to_update.mount_point)
            mount_result = disk_util.mount_filesystem(dev_path=encrypted_device_path, mount_point=crypt_item_to_update.mount_point)
            logger.log(msg=("mount result is {0}".format(mount_result)))

            logger.log(msg="modifying/removing the entry for unencrypted drive in fstab", level=CommonVariables.InfoLevel)
            crypt_mount_config_util.modify_fstab_entry_encrypt(crypt_item_to_update.mount_point, os.path.join(CommonVariables.dev_mapper_root, mapper_name))

            backup_folder = os.path.join(crypt_item_to_update.mount_point, ".azure_ade_backup_mount_info/")
            update_crypt_item_result = crypt_mount_config_util.add_crypt_item(crypt_item_to_update, backup_folder=backup_folder)
            if not update_crypt_item_result:
                logger.log(msg="update crypt item failed", level=CommonVariables.ErrorLevel)
        else:
            logger.log(msg="encryption failed with code {0}".format(encrypt_result), level=CommonVariables.ErrorLevel)
            return device_item


def encrypt_inplace_without_separate_header_file(passphrase_file,
                                                 device_item,
                                                 disk_util,
                                                 crypt_mount_config_util,
                                                 bek_util,
                                                 status_prefix='',
                                                 ongoing_item_config=None):
    """
    if ongoing_item_config is not None, then this is a resume case.
    this function will return the phase
    """
    logger.log("encrypt_inplace_without_seperate_header_file")
    current_phase = CommonVariables.EncryptionPhaseBackupHeader
    if ongoing_item_config is None:
        ongoing_item_config = OnGoingItemConfig(encryption_environment=encryption_environment, logger=logger)
        ongoing_item_config.current_block_size = CommonVariables.default_block_size
        ongoing_item_config.current_slice_index = 0
        ongoing_item_config.device_size = device_item.size
        ongoing_item_config.file_system = device_item.file_system
        ongoing_item_config.luks_header_file_path = None
        ongoing_item_config.mapper_name = str(uuid.uuid4())
        ongoing_item_config.mount_point = device_item.mount_point
        if os.path.exists(os.path.join('/dev/', device_item.name)):
            ongoing_item_config.original_dev_name_path = os.path.join('/dev/', device_item.name)
            ongoing_item_config.original_dev_path = os.path.join('/dev/', device_item.name)
        else:
            ongoing_item_config.original_dev_name_path = os.path.join(CommonVariables.dev_mapper_root, device_item.name)
            ongoing_item_config.original_dev_path = os.path.join(CommonVariables.dev_mapper_root, device_item.name)
        ongoing_item_config.phase = CommonVariables.EncryptionPhaseBackupHeader
        ongoing_item_config.commit()
    else:
        logger.log(msg="ongoing item config is not none, this is resuming, info: {0}".format(ongoing_item_config),
                   level=CommonVariables.WarningLevel)

    logger.log(msg=("encrypting device item: {0}".format(ongoing_item_config.get_original_dev_path())))
    # we only support ext file systems.
    current_phase = ongoing_item_config.get_phase()

    original_dev_path = ongoing_item_config.get_original_dev_path()
    mapper_name = ongoing_item_config.get_mapper_name()
    device_size = ongoing_item_config.get_device_size()

    luks_header_size = CommonVariables.luks_header_size
    size_shrink_to = (device_size - luks_header_size) / CommonVariables.sector_size

    while current_phase != CommonVariables.EncryptionPhaseDone:
        if current_phase == CommonVariables.EncryptionPhaseBackupHeader:
            logger.log(msg="the current phase is " + str(CommonVariables.EncryptionPhaseBackupHeader),
                       level=CommonVariables.InfoLevel)

            device_fs = ongoing_item_config.get_file_system().lower()
            if device_fs not in CommonVariables.inplace_supported_file_systems:
                if device_fs in CommonVariables.format_supported_file_systems:
                    msg = "Encrypting {0} file system is not supported for data-preserving encryption. Consider using the encrypt-format-all option.".format(device_fs)
                else:
                    msg = "AzureDiskEncryption does not support the {0} file system".format(device_fs)
                logger.log(msg=msg, level=CommonVariables.WarningLevel)

                ongoing_item_config.clear_config()
                return current_phase

            chk_shrink_result = disk_util.check_shrink_fs(dev_path=original_dev_path, size_shrink_to=size_shrink_to)

            if chk_shrink_result != CommonVariables.process_success:
                logger.log(msg="check shrink fs failed with code {0} for {1}".format(chk_shrink_result, original_dev_path),
                           level=CommonVariables.ErrorLevel)
                logger.log(msg="your file system may not have enough space to do the encryption.")

                # remove the ongoing item.
                ongoing_item_config.clear_config()
                return current_phase
            else:
                ongoing_item_config.current_slice_index = 0
                ongoing_item_config.current_source_path = original_dev_path
                ongoing_item_config.current_destination = encryption_environment.copy_header_slice_file_path
                ongoing_item_config.current_total_copy_size = CommonVariables.default_block_size
                ongoing_item_config.from_end = False
                ongoing_item_config.header_slice_file_path = encryption_environment.copy_header_slice_file_path
                ongoing_item_config.original_dev_path = original_dev_path
                ongoing_item_config.commit()
                if os.path.exists(encryption_environment.copy_header_slice_file_path):
                    logger.log(msg="the header slice file is there, remove it.", level=CommonVariables.WarningLevel)
                    os.remove(encryption_environment.copy_header_slice_file_path)

                copy_result = disk_util.copy(ongoing_item_config=ongoing_item_config, status_prefix=status_prefix)

                if copy_result != CommonVariables.process_success:
                    logger.log(msg="copy the header block failed, return code is: {0}".format(copy_result),
                               level=CommonVariables.ErrorLevel)
                    return current_phase
                else:
                    ongoing_item_config.current_slice_index = 0
                    ongoing_item_config.phase = CommonVariables.EncryptionPhaseEncryptDevice
                    ongoing_item_config.commit()
                    current_phase = CommonVariables.EncryptionPhaseEncryptDevice

        elif current_phase == CommonVariables.EncryptionPhaseEncryptDevice:
            logger.log(msg="the current phase is {0}".format(CommonVariables.EncryptionPhaseEncryptDevice),
                       level=CommonVariables.InfoLevel)

            encrypt_result = disk_util.encrypt_disk(dev_path=original_dev_path,
                                                    passphrase_file=passphrase_file,
                                                    mapper_name=mapper_name,
                                                    header_file=None)

            # after the encrypt_disk without seperate header, then the uuid
            # would change.
            if encrypt_result != CommonVariables.process_success:
                logger.log(msg="encrypt file system failed.", level=CommonVariables.ErrorLevel)
                return current_phase
            else:
                ongoing_item_config.current_slice_index = 0
                ongoing_item_config.phase = CommonVariables.EncryptionPhaseCopyData
                ongoing_item_config.commit()
                current_phase = CommonVariables.EncryptionPhaseCopyData

        elif current_phase == CommonVariables.EncryptionPhaseCopyData:
            logger.log(msg="the current phase is {0}".format(CommonVariables.EncryptionPhaseCopyData),
                       level=CommonVariables.InfoLevel)
            device_mapper_path = os.path.join(CommonVariables.dev_mapper_root, mapper_name)
            ongoing_item_config.current_destination = device_mapper_path
            ongoing_item_config.current_source_path = original_dev_path
            ongoing_item_config.current_total_copy_size = (device_size - luks_header_size)
            ongoing_item_config.from_end = True
            ongoing_item_config.phase = CommonVariables.EncryptionPhaseCopyData
            ongoing_item_config.commit()

            copy_result = disk_util.copy(ongoing_item_config=ongoing_item_config, status_prefix=status_prefix)
            if copy_result != CommonVariables.process_success:
                logger.log(msg="copy the main content block failed, return code is: {0}".format(copy_result),
                           level=CommonVariables.ErrorLevel)
                return current_phase
            else:
                ongoing_item_config.phase = CommonVariables.EncryptionPhaseRecoverHeader
                ongoing_item_config.commit()
                current_phase = CommonVariables.EncryptionPhaseRecoverHeader

        elif current_phase == CommonVariables.EncryptionPhaseRecoverHeader:
            logger.log(msg="the current phase is " + str(CommonVariables.EncryptionPhaseRecoverHeader),
                       level=CommonVariables.InfoLevel)
            ongoing_item_config.from_end = False
            backed_up_header_slice_file_path = ongoing_item_config.get_header_slice_file_path()
            ongoing_item_config.current_slice_index = 0
            ongoing_item_config.current_source_path = backed_up_header_slice_file_path
            device_mapper_path = os.path.join(CommonVariables.dev_mapper_root, mapper_name)
            ongoing_item_config.current_destination = device_mapper_path
            ongoing_item_config.current_total_copy_size = CommonVariables.default_block_size
            ongoing_item_config.commit()

            copy_result = disk_util.copy(ongoing_item_config=ongoing_item_config, status_prefix=status_prefix)

            if copy_result == CommonVariables.process_success:
                crypt_item_to_update = CryptItem()
                crypt_item_to_update.mapper_name = mapper_name
                original_dev_name_path = ongoing_item_config.get_original_dev_name_path()
                crypt_item_to_update.dev_path = disk_util.get_persistent_path_by_sdx_path(original_dev_name_path)
                crypt_item_to_update.luks_header_path = "None"
                crypt_item_to_update.file_system = ongoing_item_config.get_file_system()
                crypt_item_to_update.uses_cleartext_key = False
                crypt_item_to_update.current_luks_slot = 0
                # if the original mountpoint is empty, then leave
                # it as None
                mount_point = ongoing_item_config.get_mount_point()
                if mount_point == "" or mount_point is None:
                    crypt_item_to_update.mount_point = "None"
                else:
                    crypt_item_to_update.mount_point = mount_point

                if crypt_item_to_update.mount_point != "None":
                    disk_util.mount_filesystem(device_mapper_path, ongoing_item_config.get_mount_point())
                    backup_folder = os.path.join(crypt_item_to_update.mount_point, ".azure_ade_backup_mount_info/")
                    update_crypt_item_result = crypt_mount_config_util.add_crypt_item(crypt_item_to_update, backup_folder)
                else:
                    logger.log("the crypt_item_to_update.mount_point is None, so we do not mount it.")
                    update_crypt_item_result = crypt_mount_config_util.add_crypt_item(crypt_item_to_update)

                if not update_crypt_item_result:
                    logger.log(msg="update crypt item failed", level=CommonVariables.ErrorLevel)

                if mount_point:
                    logger.log(msg="removing entry for unencrypted drive from fstab",
                               level=CommonVariables.InfoLevel)
                    crypt_mount_config_util.modify_fstab_entry_encrypt(mount_point, os.path.join(CommonVariables.dev_mapper_root, mapper_name))
                else:
                    logger.log(msg=original_dev_name_path + " is not defined in fstab, no need to update",
                               level=CommonVariables.InfoLevel)

                if os.path.exists(encryption_environment.copy_header_slice_file_path):
                    os.remove(encryption_environment.copy_header_slice_file_path)

                current_phase = CommonVariables.EncryptionPhaseDone
                ongoing_item_config.phase = current_phase
                ongoing_item_config.commit()
                expand_fs_result = disk_util.expand_fs(dev_path=device_mapper_path)

                ongoing_item_config.clear_config()
                if expand_fs_result != CommonVariables.process_success:
                    logger.log(msg="expand fs result is: {0}".format(expand_fs_result),
                               level=CommonVariables.ErrorLevel)
                return current_phase
            else:
                logger.log(msg="recover header failed result is: {0}".format(copy_result),
                           level=CommonVariables.ErrorLevel)
                return current_phase


def encrypt_inplace_with_separate_header_file(passphrase_file,
                                              device_item,
                                              disk_util,
                                              crypt_mount_config_util,
                                              bek_util,
                                              status_prefix='',
                                              ongoing_item_config=None):
    """
    if ongoing_item_config is not None, then this is a resume case.
    """
    logger.log("encrypt_inplace_with_seperate_header_file")
    current_phase = CommonVariables.EncryptionPhaseEncryptDevice
    if ongoing_item_config is None:
        ongoing_item_config = OnGoingItemConfig(encryption_environment=encryption_environment,
                                                logger=logger)
        mapper_name = str(uuid.uuid4())
        ongoing_item_config.current_block_size = CommonVariables.default_block_size
        ongoing_item_config.current_slice_index = 0
        ongoing_item_config.device_size = device_item.size
        ongoing_item_config.file_system = device_item.file_system
        ongoing_item_config.mapper_name = mapper_name
        ongoing_item_config.mount_point = device_item.mount_point
        # TODO improve this.
        if os.path.exists(os.path.join('/dev/', device_item.name)):
            ongoing_item_config.original_dev_name_path = os.path.join('/dev/', device_item.name)
        else:
            ongoing_item_config.original_dev_name_path = os.path.join(CommonVariables.dev_mapper_root, device_item.name)
        ongoing_item_config.original_dev_path = os.path.join('/dev/disk/by-uuid', device_item.uuid)
        luks_header_file_path = disk_util.create_luks_header(mapper_name=mapper_name)
        if luks_header_file_path is None:
            logger.log(msg="create header file failed", level=CommonVariables.ErrorLevel)
            return current_phase
        else:
            ongoing_item_config.luks_header_file_path = luks_header_file_path
            ongoing_item_config.phase = CommonVariables.EncryptionPhaseEncryptDevice
            ongoing_item_config.commit()
    else:
        logger.log(msg="ongoing item config is not none, this is resuming: {0}".format(ongoing_item_config),
                   level=CommonVariables.WarningLevel)
        current_phase = ongoing_item_config.get_phase()

    while current_phase != CommonVariables.EncryptionPhaseDone:
        if current_phase == CommonVariables.EncryptionPhaseEncryptDevice:
            try:
                mapper_name = ongoing_item_config.get_mapper_name()
                original_dev_path = ongoing_item_config.get_original_dev_path()
                luks_header_file_path = ongoing_item_config.get_header_file_path()
                toggle_se_linux_for_centos7(True)

                encrypt_result = disk_util.encrypt_disk(dev_path=original_dev_path,
                                                        passphrase_file=passphrase_file,
                                                        mapper_name=mapper_name,
                                                        header_file=luks_header_file_path)

                if encrypt_result != CommonVariables.process_success:
                    logger.log(msg="the encrypton for {0} failed".format(original_dev_path),
                               level=CommonVariables.ErrorLevel)
                    return current_phase
                else:
                    ongoing_item_config.phase = CommonVariables.EncryptionPhaseCopyData
                    ongoing_item_config.commit()
                    current_phase = CommonVariables.EncryptionPhaseCopyData
            finally:
                toggle_se_linux_for_centos7(False)

        elif current_phase == CommonVariables.EncryptionPhaseCopyData:
            try:
                mapper_name = ongoing_item_config.get_mapper_name()
                original_dev_path = ongoing_item_config.get_original_dev_path()
                luks_header_file_path = ongoing_item_config.get_header_file_path()
                toggle_se_linux_for_centos7(True)
                device_mapper_path = os.path.join(CommonVariables.dev_mapper_root, mapper_name)
                if not os.path.exists(device_mapper_path):
                    open_result = disk_util.luks_open(passphrase_file=passphrase_file,
                                                      dev_path=original_dev_path,
                                                      mapper_name=mapper_name,
                                                      header_file=luks_header_file_path,
                                                      uses_cleartext_key=False)

                    if open_result != CommonVariables.process_success:
                        logger.log(msg="the luks open for {0} failed.".format(original_dev_path),
                                   level=CommonVariables.ErrorLevel)
                        return current_phase
                else:
                    logger.log(msg="the device mapper path existed, so skip the luks open.",
                               level=CommonVariables.InfoLevel)

                device_size = ongoing_item_config.get_device_size()

                current_slice_index = ongoing_item_config.get_current_slice_index()
                if current_slice_index is None:
                    ongoing_item_config.current_slice_index = 0
                ongoing_item_config.current_source_path = original_dev_path
                ongoing_item_config.current_destination = device_mapper_path
                ongoing_item_config.current_total_copy_size = device_size
                ongoing_item_config.from_end = True
                ongoing_item_config.commit()

                copy_result = disk_util.copy(ongoing_item_config=ongoing_item_config, status_prefix=status_prefix)

                if copy_result != CommonVariables.success:
                    error_message = "the copying result is {0} so skip the mounting".format(copy_result)
                    logger.log(msg=error_message, level=CommonVariables.ErrorLevel)
                    return current_phase
                else:
                    crypt_item_to_update = CryptItem()
                    crypt_item_to_update.mapper_name = mapper_name
                    original_dev_name_path = ongoing_item_config.get_original_dev_name_path()
                    crypt_item_to_update.dev_path = disk_util.get_persistent_path_by_sdx_path(original_dev_name_path)
                    crypt_item_to_update.luks_header_path = luks_header_file_path
                    crypt_item_to_update.file_system = ongoing_item_config.get_file_system()
                    crypt_item_to_update.uses_cleartext_key = False
                    crypt_item_to_update.current_luks_slot = 0

                    # if the original mountpoint is empty, then leave
                    # it as None
                    mount_point = ongoing_item_config.get_mount_point()
                    if mount_point is None or mount_point == "":
                        crypt_item_to_update.mount_point = "None"
                    else:
                        crypt_item_to_update.mount_point = mount_point

                    if crypt_item_to_update.mount_point != "None":
                        disk_util.mount_filesystem(device_mapper_path, mount_point)
                        backup_folder = os.path.join(crypt_item_to_update.mount_point, ".azure_ade_backup_mount_info/")
                        update_crypt_item_result = crypt_mount_config_util.add_crypt_item(crypt_item_to_update, backup_folder)
                    else:
                        logger.log("the crypt_item_to_update.mount_point is None, so we do not mount it.")
                        update_crypt_item_result = crypt_mount_config_util.add_crypt_item(crypt_item_to_update)

                    if not update_crypt_item_result:
                        logger.log(msg="update crypt item failed", level=CommonVariables.ErrorLevel)

                    if mount_point:
                        logger.log(msg="removing entry for unencrypted drive from fstab",
                                   level=CommonVariables.InfoLevel)
                        crypt_mount_config_util.modify_fstab_entry_encrypt(mount_point, os.path.join(CommonVariables.dev_mapper_root, mapper_name))
                    else:
                        logger.log(msg=original_dev_name_path + " is not defined in fstab, no need to update",
                                   level=CommonVariables.InfoLevel)

                    current_phase = CommonVariables.EncryptionPhaseDone
                    ongoing_item_config.phase = current_phase
                    ongoing_item_config.commit()
                    ongoing_item_config.clear_config()
                    return current_phase
            finally:
                toggle_se_linux_for_centos7(False)


def decrypt_inplace_copy_data(passphrase_file,
                              crypt_item,
                              raw_device_item,
                              mapper_device_item,
                              disk_util,
                              crypt_mount_config_util,
                              status_prefix='',
                              ongoing_item_config=None):
    logger.log(msg="decrypt_inplace_copy_data")

    if ongoing_item_config:
        logger.log(msg="ongoing item config is not none, resuming decryption, info: {0}".format(ongoing_item_config),
                   level=CommonVariables.WarningLevel)
    else:
        logger.log(msg="starting decryption of {0}".format(crypt_item))
        ongoing_item_config = OnGoingItemConfig(encryption_environment=encryption_environment, logger=logger)
        ongoing_item_config.current_destination = crypt_item.dev_path
        ongoing_item_config.current_source_path = os.path.join(CommonVariables.dev_mapper_root,
                                                               crypt_item.mapper_name)
        ongoing_item_config.current_total_copy_size = mapper_device_item.size
        ongoing_item_config.from_end = True
        ongoing_item_config.phase = CommonVariables.DecryptionPhaseCopyData
        ongoing_item_config.current_slice_index = 0
        ongoing_item_config.current_block_size = CommonVariables.default_block_size
        ongoing_item_config.mount_point = crypt_item.mount_point
        ongoing_item_config.commit()

    current_phase = ongoing_item_config.get_phase()

    while current_phase != CommonVariables.DecryptionPhaseDone:
        logger.log(msg=("the current phase is {0}".format(CommonVariables.EncryptionPhaseBackupHeader)),
                   level=CommonVariables.InfoLevel)

        if current_phase == CommonVariables.DecryptionPhaseCopyData:
            copy_result = disk_util.copy(ongoing_item_config=ongoing_item_config, status_prefix=status_prefix)
            if copy_result == CommonVariables.process_success:
                mount_point = ongoing_item_config.get_mount_point()
                if mount_point and mount_point != "None":
                    logger.log(msg="restoring entry for unencrypted drive from fstab", level=CommonVariables.InfoLevel)
                    crypt_mount_config_util.restore_mount_info(ongoing_item_config.get_mount_point())
                elif crypt_item.mapper_name:
                    crypt_mount_config_util.restore_mount_info(crypt_item.mapper_name)
                else:
                    logger.log(msg=crypt_item.dev_path + " was not in fstab when encryption was enabled, no need to restore",
                               level=CommonVariables.InfoLevel)

                ongoing_item_config.phase = CommonVariables.DecryptionPhaseDone
                ongoing_item_config.commit()
                current_phase = CommonVariables.DecryptionPhaseDone
            else:
                logger.log(msg="decryption: block copy failed, result: {0}".format(copy_result),
                           level=CommonVariables.ErrorLevel)
                return current_phase

    ongoing_item_config.clear_config()

    return current_phase


def decrypt_inplace_without_separate_header_file(passphrase_file,
                                                 crypt_item,
                                                 raw_device_item,
                                                 mapper_device_item,
                                                 disk_util,
                                                 crypt_mount_config_util,
                                                 status_prefix='',
                                                 ongoing_item_config=None):
    logger.log(msg="decrypt_inplace_without_separate_header_file")

    proc_comm = ProcessCommunicator()
    executor = CommandExecutor(logger)
    executor.Execute(DistroPatcher.cryptsetup_path + " luksDump " + crypt_item.dev_path, communicator=proc_comm)

    luks_header_size = int(re.findall(r"Payload.*?(\d+)", proc_comm.stdout)[0]) * CommonVariables.sector_size

    if raw_device_item.size - mapper_device_item.size != luks_header_size:
        logger.log(msg="mismatch between raw and mapper device found for crypt_item {0}".format(crypt_item),
                   level=CommonVariables.ErrorLevel)
        logger.log(msg="raw_device_item: {0}".format(raw_device_item),
                   level=CommonVariables.ErrorLevel)
        logger.log(msg="mapper_device_item {0}".format(mapper_device_item),
                   level=CommonVariables.ErrorLevel)

        return None

    return decrypt_inplace_copy_data(passphrase_file,
                                     crypt_item,
                                     raw_device_item,
                                     mapper_device_item,
                                     disk_util,
                                     crypt_mount_config_util,
                                     status_prefix,
                                     ongoing_item_config)


def decrypt_inplace_with_separate_header_file(passphrase_file,
                                              crypt_item,
                                              raw_device_item,
                                              mapper_device_item,
                                              disk_util,
                                              crypt_mount_config_util,
                                              status_prefix='',
                                              ongoing_item_config=None):
    logger.log(msg="decrypt_inplace_with_separate_header_file")

    if raw_device_item.size != mapper_device_item.size:
        logger.log(msg="mismatch between raw and mapper device found for crypt_item {0}".format(crypt_item),
                   level=CommonVariables.ErrorLevel)
        logger.log(msg="raw_device_item: {0}".format(raw_device_item),
                   level=CommonVariables.ErrorLevel)
        logger.log(msg="mapper_device_item {0}".format(mapper_device_item),
                   level=CommonVariables.ErrorLevel)

        return

    return decrypt_inplace_copy_data(passphrase_file,
                                     crypt_item,
                                     raw_device_item,
                                     mapper_device_item,
                                     disk_util,
                                     crypt_mount_config_util,
                                     status_prefix,
                                     ongoing_item_config)


def enable_encryption_all_format(passphrase_file, encryption_marker, disk_util, crypt_mount_config_util, bek_util, os_items_to_stamp):
    """
    In case of success return None, otherwise return the device item which failed.
    """
    logger.log(msg="executing the enable_encryption_all_format command")

    device_items_to_encrypt = find_all_devices_to_encrypt(encryption_marker, disk_util, bek_util)

    msg = 'Encrypting and formatting {0} data volumes'.format(len(device_items_to_encrypt))
    logger.log(msg)

    hutil.do_status_report(operation='EnableEncryptionFormatAll',
                           status=CommonVariables.extension_transitioning_status,
                           status_code=str(CommonVariables.success),
                           message=msg)

    return encrypt_format_device_items(passphrase_file, device_items_to_encrypt, disk_util, crypt_mount_config_util, True, os_items_to_stamp)


def encrypt_format_device_items(passphrase, device_items, disk_util, crypt_mount_config_util, force=False, os_items_to_stamp=[]):
    """
    Formats the block devices represented by the supplied device_item.

    This is done by constructing a disk format query based on the supplied device items
    and passing it on to the enable_encryption_format method.

    Returns None if all items are successfully format-encrypted
    Otherwise returns the device item which failed.
    """

    # use the new udev names for formatting and later on for cryptmounting
    dev_path_reference_table = disk_util.get_block_device_to_azure_udev_table()

    def device_item_to_encryption_format_item(device_item):
        """
        Converts a single device_item into an encryption format item (a.k.a. a disk format query element)
        """
        encryption_format_item = {}
        dev_path = os.path.join('/dev/', device_item.name)
        if dev_path in dev_path_reference_table:
            encryption_format_item["dev_path"] = dev_path_reference_table[dev_path]
        else:
            encryption_format_item["dev_path"] = dev_path

        # introduce a new "full_mount_point" field below to avoid the /mnt/ prefix that automatically gets appended
        encryption_format_item["full_mount_point"] = str(device_item.mount_point)
        encryption_format_item["file_system"] = str(device_item.file_system)
        return encryption_format_item

    encryption_format_items = list(map(device_item_to_encryption_format_item, device_items))

    return enable_encryption_format(passphrase, encryption_format_items, disk_util, crypt_mount_config_util, force, os_items_to_stamp=os_items_to_stamp)


def os_device_to_encrypt(disk_util):
    os_items_to_stamp = []
    device_items = disk_util.get_device_items(None)
    for device_item in device_items:
        if device_item.mount_point == "/":
            os_items_to_stamp.append(device_item)
    return os_items_to_stamp


def find_all_devices_to_encrypt(encryption_marker, disk_util, bek_util, volume_type=None, current_command=None):
    device_items = disk_util.get_device_items(None)
    dev_path_reference_table = disk_util.get_block_device_to_azure_udev_table()
    device_items_to_encrypt = []
    special_azure_devices_to_skip = disk_util.get_azure_devices()
    if not volume_type:
        volume_type = encryption_marker.get_volume_type()
    if not current_command:
        current_command = encryption_marker.get_current_command()
    for device_item in device_items:
        logger.log("device_item == " + str(device_item))

        if any(di.name == device_item.name for di in device_items_to_encrypt):
            continue
        if disk_util.should_skip_for_inplace_encryption(device_item, special_azure_devices_to_skip, volume_type):
            continue

        if current_command == CommonVariables.EnableEncryptionFormatAll:
            if device_item.mount_point is None or device_item.mount_point == "":
                # Don't encrypt partitions that are not even mounted
                continue
            if os.path.join('/dev/', device_item.name) not in dev_path_reference_table:
                # Only format device_items that have an azure udev name
                continue
        device_items_to_encrypt.append(device_item)

    return device_items_to_encrypt


def enable_encryption_all_in_place(passphrase_file, encryption_marker, disk_util, crypt_mount_config_util, bek_util, os_items_to_stamp):
    """
    if return None for the success case, or return the device item which failed.
    """
    logger.log(msg="executing the enable_encryption_all_in_place command.")

    device_items_to_encrypt = find_all_devices_to_encrypt(encryption_marker, disk_util, bek_util)

    # If anything needs to be stamped, do the stamping here
    device_items_to_stamp = device_items_to_encrypt + os_items_to_stamp
    if len(device_items_to_stamp) > 0:
        encryption_config = EncryptionConfig(encryption_environment, logger)
        if not are_disks_stamped_with_current_config(encryption_config):
            stamp_disks_with_settings(items_to_encrypt=device_items_to_stamp,
                                      encryption_config=encryption_config)

    msg = 'Encrypting {0} data volumes'.format(len(device_items_to_encrypt))
    logger.log(msg)

    hutil.do_status_report(operation='EnableEncryption',
                           status=CommonVariables.extension_success_status,
                           status_code=str(CommonVariables.success),
                           message=msg)

    for device_num, device_item in enumerate(device_items_to_encrypt):
        umount_status_code = CommonVariables.success
        if device_item.mount_point is not None and device_item.mount_point != "":
            umount_status_code = disk_util.umount(device_item.mount_point)
        if umount_status_code != CommonVariables.success:
            logger.log("error occured when do the umount for: {0} with code: {1}".format(device_item.mount_point, umount_status_code))
        else:
            logger.log(msg=("encrypting: {0}".format(device_item)))
            status_prefix = "Encrypting data volume {0}/{1}".format(device_num + 1,
                                                                    len(device_items_to_encrypt))

            # TODO check the file system before encrypting it.
            logger.log(msg="For VMSS we only do inplace headers",
                       level=CommonVariables.WarningLevel)

            encryption_result_phase = encrypt_inplace_without_separate_header_file(passphrase_file=passphrase_file,
                                                                                   device_item=device_item,
                                                                                   disk_util=disk_util,
                                                                                   crypt_mount_config_util=crypt_mount_config_util,
                                                                                   bek_util=bek_util,
                                                                                   status_prefix=status_prefix)

            if encryption_result_phase == CommonVariables.EncryptionPhaseDone:
                continue
            else:
                # do exit to exit from this round
                return device_item
    return None


def disable_encryption_all_in_place(passphrase_file, decryption_marker, disk_util, crypt_mount_config_util):
    """
    On success, returns None. Otherwise returns the crypt item for which decryption failed.
    """

    logger.log(msg="executing disable_encryption_all_in_place")

    device_items = disk_util.get_device_items(None)
    crypt_items = crypt_mount_config_util.get_crypt_items()

    msg = 'Decrypting {0} data volumes'.format(len(crypt_items))
    logger.log(msg)

    hutil.do_status_report(operation='DisableEncryption',
                           status=CommonVariables.extension_success_status,
                           status_code=str(CommonVariables.success),
                           message=msg)

    for crypt_item_num, crypt_item in enumerate(crypt_items):
        logger.log("processing crypt_item: " + str(crypt_item))

        def raw_device_item_match(device_item):
            sdx_device_name = os.path.join("/dev/", device_item.name)
            return os.path.realpath(sdx_device_name) == os.path.realpath(crypt_item.dev_path)

        def mapped_device_item_match(device_item):
            return crypt_item.mapper_name == device_item.name

        raw_device_item = next((d for d in device_items if raw_device_item_match(d)), None)
        mapper_device_item = next((d for d in device_items if mapped_device_item_match(d)), None)

        if not raw_device_item:
            logger.log("raw device not found for crypt_item {0}".format(crypt_item), level='Warn')
            logger.log("Skipping device", level='Warn')
            continue

        if not mapper_device_item:
            logger.log("mapper device not found for crypt_item {0}".format(crypt_item))
            if disk_util.is_luks_device(crypt_item.dev_path, crypt_item.luks_header_path):
                logger.log("Found a luks device for this device item, yet couldn't open mapper: {0}".format(crypt_item))
                logger.log("Failing")
                return crypt_item
            else:
                continue

        decryption_result_phase = None

        status_prefix = "Decrypting data volume {0}/{1}".format(crypt_item_num + 1,
                                                                len(crypt_items))

        if crypt_item.luks_header_path:
            decryption_result_phase = decrypt_inplace_with_separate_header_file(passphrase_file=passphrase_file,
                                                                                crypt_item=crypt_item,
                                                                                raw_device_item=raw_device_item,
                                                                                mapper_device_item=mapper_device_item,
                                                                                disk_util=disk_util,
                                                                                crypt_mount_config_util=crypt_mount_config_util,
                                                                                status_prefix=status_prefix)
        else:
            decryption_result_phase = decrypt_inplace_without_separate_header_file(passphrase_file=passphrase_file,
                                                                                   crypt_item=crypt_item,
                                                                                   raw_device_item=raw_device_item,
                                                                                   mapper_device_item=mapper_device_item,
                                                                                   disk_util=disk_util,
                                                                                   crypt_mount_config_util=crypt_mount_config_util,
                                                                                   status_prefix=status_prefix)

        if decryption_result_phase == CommonVariables.DecryptionPhaseDone:
            disk_util.luks_close(crypt_item.mapper_name)
            backup_folder = os.path.join(crypt_item.mount_point, ".azure_ade_backup_mount_info/") if crypt_item.mount_point else None
            crypt_mount_config_util.remove_crypt_item(crypt_item, backup_folder)

            continue
        else:
            # decryption failed for a crypt_item, return the failed item to caller
            return crypt_item

    disk_util.mount_all()

    return None


def daemon_encrypt():
    # Ensure the same configuration is executed only once
    # If the previous enable failed, we do not have retry logic here.
    # TODO Remount all
    encryption_marker = EncryptionMarkConfig(logger, encryption_environment)
    if encryption_marker.config_file_exists():
        logger.log("encryption is marked.")

    """
    search for the bek volume, then mount it:)
    """
    disk_util = DiskUtil(hutil, DistroPatcher, logger, encryption_environment)
    crypt_mount_config_util = CryptMountConfigUtil(logger, encryption_environment, disk_util)

    encryption_config = EncryptionConfig(encryption_environment, logger)
    bek_passphrase_file = None
    """
    try to find the attached bek volume, and use the file to mount the crypted volumes,
    and if the passphrase file is found, then we will re-use it for the future.
    """
    bek_util = BekUtil(disk_util, logger)
    if encryption_config.config_file_exists():
        bek_passphrase_file = bek_util.get_bek_passphrase_file(encryption_config)

    if bek_passphrase_file is None:
        hutil.do_exit(exit_code=CommonVariables.passphrase_file_not_found,
                      operation='EnableEncryption',
                      status=CommonVariables.extension_error_status,
                      code=CommonVariables.passphrase_file_not_found,
                      message='Passphrase file not found.')

    executor = CommandExecutor(logger)
    is_not_in_stripped_os = bool(executor.Execute("mountpoint /oldroot"))
    volume_type = encryption_config.get_volume_type().lower()

    # identify os item to stamp when os volume is selected for encryption
    os_items_to_stamp = []
    if (volume_type == CommonVariables.VolumeTypeAll.lower() or volume_type == CommonVariables.VolumeTypeOS.lower()) and \
            not are_disks_stamped_with_current_config(encryption_config) and is_not_in_stripped_os:
        device_items = disk_util.get_device_items(None)
        for device_item in device_items:
            if device_item.mount_point == "/":
                os_items_to_stamp.append(device_item)

    if (volume_type == CommonVariables.VolumeTypeData.lower() or volume_type == CommonVariables.VolumeTypeAll.lower()) and \
            is_not_in_stripped_os:
        try:
            while not daemon_encrypt_data_volumes(encryption_marker=encryption_marker,
                                                  encryption_config=encryption_config,
                                                  disk_util=disk_util,
                                                  crypt_mount_config_util=crypt_mount_config_util,
                                                  bek_util=bek_util,
                                                  bek_passphrase_file=bek_passphrase_file,
                                                  os_items_to_stamp=os_items_to_stamp):
                logger.log("Calling daemon_encrypt_data_volumes again")
        except Exception as e:
            message = "Failed to encrypt data volumes with error: {0}, stack trace: {1}".format(e, traceback.format_exc())
            logger.log(msg=message, level=CommonVariables.ErrorLevel)
            encryption_marker.clear_config()
            hutil.do_exit(exit_code=CommonVariables.encryption_failed,
                          operation='EnableEncryptionDataVolumes',
                          status=CommonVariables.extension_error_status,
                          code=CommonVariables.encryption_failed,
                          message=message)
        else:
            hutil.do_status_report(operation='EnableEncryptionDataVolumes',
                                   status=CommonVariables.extension_success_status,
                                   status_code=str(CommonVariables.success),
                                   message='Encryption succeeded for data volumes')
            disk_util.log_lsblk_output()
            mount_encrypted_disks(disk_util=disk_util,
                                  crypt_mount_config_util=crypt_mount_config_util,
                                  bek_util=bek_util,
                                  encryption_config=encryption_config,
                                  passphrase_file=bek_passphrase_file)

    if volume_type == CommonVariables.VolumeTypeOS.lower() or \
       volume_type == CommonVariables.VolumeTypeAll.lower():
        # import OSEncryption here instead of at the top because it relies
        # on pre-req packages being installed (specifically, python-six on Ubuntu)
        distro_name = DistroPatcher.distro_info[0]
        distro_name = distro_name.replace('ubuntu', 'Ubuntu')  # to upper if needed
        distro_version = DistroPatcher.distro_info[1]

        os_encryption = None

        if ((distro_name == 'redhat' and distro_version == '7.2') or
            (distro_name == 'redhat' and distro_version == '7.3') or
            (distro_name == 'redhat' and distro_version == '7.4') or
            (distro_name == 'redhat' and distro_version == '7.5') or
            (distro_name == 'redhat' and distro_version == '7.6') or
            (distro_name == 'redhat' and distro_version == '7.7') or
            (distro_name == 'redhat' and distro_version == '7.8') or
            (distro_name == 'redhat' and distro_version == '7.9') or
            (distro_name == 'centos' and distro_version.startswith('7.9')) or
            (distro_name == 'centos' and distro_version.startswith('7.8')) or
            (distro_name == 'centos' and distro_version.startswith('7.7')) or
            (distro_name == 'centos' and distro_version.startswith('7.6')) or
            (distro_name == 'centos' and distro_version.startswith('7.5')) or
            (distro_name == 'centos' and distro_version.startswith('7.4')) or
            (distro_name == 'centos' and distro_version == '7.3.1611') or
                (distro_name == 'centos' and distro_version == '7.2.1511')):
            if disk_util.is_os_disk_lvm() or os.path.exists('/volumes.lvm'):
                from oscrypto.rhel_72_lvm import RHEL72LVMEncryptionStateMachine
                os_encryption = RHEL72LVMEncryptionStateMachine(hutil=hutil,
                                                                distro_patcher=DistroPatcher,
                                                                logger=logger,
                                                                encryption_environment=encryption_environment)
            else:
                from oscrypto.rhel_72 import RHEL72EncryptionStateMachine
                os_encryption = RHEL72EncryptionStateMachine(hutil=hutil,
                                                             distro_patcher=DistroPatcher,
                                                             logger=logger,
                                                             encryption_environment=encryption_environment)
        elif ((distro_name == 'redhat' and distro_version.startswith('8.1')) or
              (distro_name == 'redhat' and distro_version.startswith('8.2')) or
              (distro_name == 'redhat' and distro_version.startswith('8.3')) or
              (distro_name == 'centos' and distro_version.startswith('8.3')) or
              (distro_name == 'centos' and distro_version.startswith('8.2')) or
              (distro_name == 'centos' and distro_version.startswith('8.1'))):
            from oscrypto.rhel_81 import RHEL81EncryptionStateMachine
            os_encryption = RHEL81EncryptionStateMachine(hutil=hutil,
                                                         distro_patcher=DistroPatcher,
                                                         logger=logger,
                                                         encryption_environment=encryption_environment)
        elif distro_name == 'redhat' and distro_version == '6.8':
            from oscrypto.rhel_68 import RHEL68EncryptionStateMachine
            os_encryption = RHEL68EncryptionStateMachine(hutil=hutil,
                                                         distro_patcher=DistroPatcher,
                                                         logger=logger,
                                                         encryption_environment=encryption_environment)
        elif distro_name == 'centos' and (distro_version == '6.8' or distro_version == '6.9'):
            from oscrypto.centos_68 import CentOS68EncryptionStateMachine
            os_encryption = CentOS68EncryptionStateMachine(hutil=hutil,
                                                           distro_patcher=DistroPatcher,
                                                           logger=logger,
                                                           encryption_environment=encryption_environment)
        elif distro_name == 'Ubuntu' and distro_version in ['16.04', '18.04', '20.04']:
            from oscrypto.ubuntu_1604 import Ubuntu1604EncryptionStateMachine
            os_encryption = Ubuntu1604EncryptionStateMachine(hutil=hutil,
                                                             distro_patcher=DistroPatcher,
                                                             logger=logger,
                                                             encryption_environment=encryption_environment)
        elif distro_name == 'Ubuntu' and distro_version == '14.04':
            from oscrypto.ubuntu_1404 import Ubuntu1404EncryptionStateMachine
            os_encryption = Ubuntu1404EncryptionStateMachine(hutil=hutil,
                                                             distro_patcher=DistroPatcher,
                                                             logger=logger,
                                                             encryption_environment=encryption_environment)
        elif distro_name == 'Mariner' and distro_version == '1.0':
            from oscrypto.mariner_10 import Mariner10EncryptionStateMachine
            os_encryption = Mariner10EncryptionStateMachine(hutil=hutil,
                                                            distro_patcher=DistroPatcher,
                                                            logger=logger,
                                                            encryption_environment=encryption_environment)
        else:
            message = "OS volume encryption is not supported on {0} {1}".format(distro_name,
                                                                                distro_version)
            logger.log(msg=message, level=CommonVariables.ErrorLevel)
            hutil.do_exit(exit_code=CommonVariables.encryption_failed,
                          operation='EnableEncryptionOSVolume',
                          status=CommonVariables.extension_error_status,
                          code=CommonVariables.encryption_failed,
                          message=message)

        try:
            if not disk_util.is_in_memfs_root() and not are_disks_stamped_with_current_config(encryption_config):
                stamp_disks_with_settings(os_items_to_stamp, encryption_config)

            os_encryption.start_encryption()

            if not os_encryption.state == 'completed':
                raise Exception("did not reach completed state")
            else:
                encryption_marker.clear_config()

        except Exception as e:
            message = "Failed to encrypt OS volume with error: {0}, stack trace: {1}, machine state: {2}".format(e,
                                                                                                                 traceback.format_exc(),
                                                                                                                 os_encryption.state)
            logger.log(msg=message, level=CommonVariables.ErrorLevel)
            encryption_marker.clear_config()
            hutil.do_exit(exit_code=CommonVariables.encryption_failed,
                          operation='EnableEncryptionOSVolume',
                          status=CommonVariables.extension_error_status,
                          code=CommonVariables.encryption_failed,
                          message=message)

        message = ''
        if volume_type == CommonVariables.VolumeTypeAll.lower():
            message = 'Encryption succeeded for all volumes'
        else:
            message = 'Encryption succeeded for OS volume'

        logger.log(msg=message)
        hutil.do_status_report(operation='EnableEncryptionOSVolume',
                               status=CommonVariables.extension_success_status,
                               status_code=str(CommonVariables.success),
                               message=message)


def daemon_encrypt_data_volumes(encryption_marker, encryption_config, disk_util, crypt_mount_config_util, bek_util, bek_passphrase_file, os_items_to_stamp):
    try:
        """
        check whether there's a scheduled encryption task
        """
        mount_all_result = disk_util.mount_all()

        if mount_all_result != CommonVariables.process_success:
            logger.log(msg="mount all failed with code:{0}".format(mount_all_result),
                       level=CommonVariables.ErrorLevel)
        """
        TODO: resuming the encryption for rebooting suddenly scenario
        we need the special handling is because the half done device can be a error state: say, the file system header missing.so it could be
        identified.
        """
        ongoing_item_config = OnGoingItemConfig(encryption_environment=encryption_environment, logger=logger)

        if ongoing_item_config.config_file_exists():
            logger.log("OngoingItemConfig exists.")
            ongoing_item_config.load_value_from_file()
            header_file_path = ongoing_item_config.get_header_file_path()
            mount_point = ongoing_item_config.get_mount_point()
            status_prefix = "Resuming encryption after reboot"
            if not none_or_empty(mount_point):
                logger.log("mount point is not empty {0}, trying to unmount it first.".format(mount_point))
                umount_status_code = disk_util.umount(mount_point)
                logger.log("unmount return code is {0}".format(umount_status_code))
            if none_or_empty(header_file_path):
                encryption_result_phase = encrypt_inplace_without_separate_header_file(passphrase_file=bek_passphrase_file,
                                                                                       device_item=None,
                                                                                       disk_util=disk_util,
                                                                                       crypt_mount_config_util=crypt_mount_config_util,
                                                                                       bek_util=bek_util,
                                                                                       status_prefix=status_prefix,
                                                                                       ongoing_item_config=ongoing_item_config)
                # TODO mount it back when shrink failed
            else:
                encryption_result_phase = encrypt_inplace_with_separate_header_file(passphrase_file=bek_passphrase_file,
                                                                                    device_item=None,
                                                                                    disk_util=disk_util,
                                                                                    crypt_mount_config_util=crypt_mount_config_util,
                                                                                    bek_util=bek_util,
                                                                                    status_prefix=status_prefix,
                                                                                    ongoing_item_config=ongoing_item_config)
            """
            if the resuming failed, we should fail.
            """
            if encryption_result_phase != CommonVariables.EncryptionPhaseDone:
                original_dev_path = ongoing_item_config.get_original_dev_path
                message = 'EnableEncryption: resuming encryption for {0} failed'.format(original_dev_path)
                raise Exception(message)
            else:
                ongoing_item_config.clear_config()
        else:
            logger.log("OngoingItemConfig does not exist")
            failed_item = None

            if not encryption_marker.config_file_exists():
                logger.log("Data volumes are not marked for encryption")
                return True

            if encryption_marker.get_current_command() == CommonVariables.EnableEncryption:
                failed_item = enable_encryption_all_in_place(passphrase_file=bek_passphrase_file,
                                                             encryption_marker=encryption_marker,
                                                             disk_util=disk_util,
                                                             crypt_mount_config_util=crypt_mount_config_util,
                                                             bek_util=bek_util,
                                                             os_items_to_stamp=os_items_to_stamp)
            elif encryption_marker.get_current_command() == CommonVariables.EnableEncryptionFormat:
                try:
                    disk_format_query = encryption_marker.get_encryption_disk_format_query()
                    json_parsed = json.loads(disk_format_query)

                    if type(json_parsed) is dict:
                        encryption_format_items = [json_parsed, ]
                    elif type(json_parsed) is list:
                        encryption_format_items = json_parsed
                    else:
                        raise Exception("JSON parse error. Input: {0}".format(disk_format_query))
                except Exception:
                    encryption_marker.clear_config()
                    raise

                failed_item = enable_encryption_format(passphrase=bek_passphrase_file,
                                                       encryption_format_items=encryption_format_items,
                                                       disk_util=disk_util,
                                                       crypt_mount_config_util=crypt_mount_config_util,
                                                       os_items_to_stamp=os_items_to_stamp)
            elif encryption_marker.get_current_command() == CommonVariables.EnableEncryptionFormatAll:
                failed_item = enable_encryption_all_format(passphrase_file=bek_passphrase_file,
                                                           encryption_marker=encryption_marker,
                                                           disk_util=disk_util,
                                                           crypt_mount_config_util=crypt_mount_config_util,
                                                           bek_util=bek_util,
                                                           os_items_to_stamp=os_items_to_stamp)
            else:
                message = "Command {0} not supported.".format(encryption_marker.get_current_command())
                logger.log(msg=message, level=CommonVariables.ErrorLevel)
                raise Exception(message)

            if failed_item:
                message = 'Encryption failed for {0}'.format(failed_item)
                raise Exception(message)
            else:
                return True
    except Exception:
        raise


def daemon_decrypt():
    decryption_marker = DecryptionMarkConfig(logger, encryption_environment)

    if not decryption_marker.config_file_exists():
        logger.log("decryption is not marked.")
        return

    logger.log("decryption is marked.")

    # mount and then unmount all the encrypted items
    # in order to set-up all the mapper devices
    # we don't need the BEK since all the drives that need decryption were made cleartext-key unlockable by first call to disable

    disk_util = DiskUtil(hutil, DistroPatcher, logger, encryption_environment)
    crypt_mount_config_util = CryptMountConfigUtil(logger, encryption_environment, disk_util)
    encryption_config = EncryptionConfig(encryption_environment, logger)
    mount_encrypted_disks(disk_util=disk_util,
                          crypt_mount_config_util=crypt_mount_config_util,
                          bek_util=None,
                          encryption_config=encryption_config,
                          passphrase_file=None)
    for crypt_item in crypt_mount_config_util.get_crypt_items():
        logger.log("Unmounting {0}".format(os.path.join(CommonVariables.dev_mapper_root, crypt_item.mapper_name)))
        disk_util.umount(os.path.join(CommonVariables.dev_mapper_root, crypt_item.mapper_name))

    # at this point all the /dev/mapper/* crypt devices should be open

    ongoing_item_config = OnGoingItemConfig(encryption_environment=encryption_environment, logger=logger)

    if ongoing_item_config.config_file_exists():
        logger.log("ongoing item config exists.")
    else:
        logger.log("ongoing item config does not exist.")

        failed_item = None

        if decryption_marker.get_current_command() == CommonVariables.DisableEncryption:
            failed_item = disable_encryption_all_in_place(passphrase_file=None,
                                                          decryption_marker=decryption_marker,
                                                          disk_util=disk_util,
                                                          crypt_mount_config_util=crypt_mount_config_util)
        else:
            raise Exception("command {0} not supported.".format(decryption_marker.get_current_command()))

        if failed_item is not None:
            hutil.do_exit(exit_code=CommonVariables.encryption_failed,
                          operation='Disable',
                          status=CommonVariables.extension_error_status,
                          code=CommonVariables.encryption_failed,
                          message='Decryption failed for {0}'.format(failed_item))
        else:
            encryption_config.clear_config(clear_parameter_file=True)
            logger.log("clearing the decryption mark after successful decryption")
            decryption_marker.clear_config()

            hutil.do_exit(exit_code=0,
                          operation='Disable',
                          status=CommonVariables.extension_success_status,
                          code=str(CommonVariables.success),
                          message='Decryption succeeded')


def daemon():
    hutil.find_last_nonquery_operation = True
    hutil.do_parse_context('Executing')
    lock = ProcessLock(logger, encryption_environment.daemon_lock_file_path)
    if not lock.try_lock():
        logger.log("there's another daemon running, please wait it to exit.", level=CommonVariables.WarningLevel)
        return

    logger.log("daemon lock acquired sucessfully.")

    logger.log("waiting for 1 minute before continuing the daemon")
    time.sleep(60)

    logger.log("Installing pre-requisites")
    DistroPatcher.install_extras()

    # try decrypt, if decryption marker exists
    decryption_marker = DecryptionMarkConfig(logger, encryption_environment)
    if decryption_marker.config_file_exists():
        try:
            daemon_decrypt()
        except Exception as e:
            error_msg = ("Failed to disable the extension with error: {0}, stack trace: {1}".format(e, traceback.format_exc()))

            logger.log(msg=error_msg,
                       level=CommonVariables.ErrorLevel)

            hutil.do_exit(exit_code=CommonVariables.encryption_failed,
                          operation='Disable',
                          status=CommonVariables.extension_error_status,
                          code=str(CommonVariables.encryption_failed),
                          message=error_msg)
        finally:
            lock.release_lock()
            logger.log("returned to daemon")
            logger.log("exiting daemon")

            return

    # try encrypt, in absence of decryption marker
    try:
        daemon_encrypt()
    except Exception as e:
        # mount the file systems back.
        error_msg = ("Failed to enable the extension with error: {0}, stack trace: {1}".format(e, traceback.format_exc()))
        logger.log(msg=error_msg,
                   level=CommonVariables.ErrorLevel)
        hutil.do_exit(exit_code=CommonVariables.encryption_failed,
                      operation='Enable',
                      status=CommonVariables.extension_error_status,
                      code=str(CommonVariables.encryption_failed),
                      message=error_msg)
    else:
        encryption_marker = EncryptionMarkConfig(logger, encryption_environment)
        # TODO not remove it, backed it up.
        logger.log("returned to daemon successfully after encryption")
        logger.log("clearing the encryption mark.")
        encryption_marker.clear_config()
        hutil.redo_current_status()
    finally:
        lock.release_lock()
        logger.log("exiting daemon")


def start_daemon(operation):
    # This process will start a new background process by calling
    #     extension_shim.sh -c handle.py -daemon
    # to run the script and will exit itself immediatelly.
    shim_path = os.path.join(os.getcwd(), CommonVariables.extension_shim_filename)
    shim_opts = '-c ' + os.path.join(os.getcwd(), __file__) + ' -daemon'
    args = [shim_path, shim_opts]
    logger.log("start_daemon with args: {0}".format(args))

    # Redirect stdout and stderr to /dev/null.  Otherwise daemon process will
    # throw broken pipe exception when parent process exit.
    # use 'wb' for python3 compat since stdout and stderr are bytes not strings
    devnull = open(os.devnull, 'wb')
    subprocess.Popen(args, stdout=devnull, stderr=devnull)

    encryption_config = EncryptionConfig(encryption_environment, logger)
    if encryption_config.config_file_exists():
        if are_disks_stamped_with_current_config(encryption_config):
            hutil.do_exit(exit_code=0,
                          operation=operation,
                          status=CommonVariables.extension_success_status,
                          code=str(CommonVariables.success),
                          message="")
        else:
            hutil.do_exit(exit_code=0,
                          operation=operation,
                          status=CommonVariables.extension_transitioning_status,
                          code=str(CommonVariables.success),
                          message="")
    else:
        hutil.do_exit(exit_code=CommonVariables.encryption_failed,
                      operation=operation,
                      status=CommonVariables.extension_error_status,
                      code=str(CommonVariables.encryption_failed),
                      message='Encryption config not found.')


if __name__ == '__main__':
    main()
