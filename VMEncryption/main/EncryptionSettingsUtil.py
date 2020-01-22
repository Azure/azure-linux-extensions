#!/usr/bin/env python
#
# Copyright (c) Microsoft Corporation
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

import http.client
import json
import os
import os.path
import socket
import re
import time
import base64

from shutil import copyfile
import uuid
from Common import CommonVariables


class EncryptionSettingsUtil(object):
    """ Provides capability to update encryption settings via wire server """

    def __init__(self, logger):
        self.logger = logger
        self._DISK_ENCRYPTION_DATA_VERSION_V4 = "4.0"

    def get_index(self):
        """get the integer value of the current index in the counter"""
        index = 0
        if os.path.isfile(CommonVariables.encryption_settings_counter_path):
            with open(CommonVariables.encryption_settings_counter_path, "r") as infile:
                index_string = infile.readline().strip()
            try:
                index = int(index_string)
            except ValueError:
                self.logger.log("counter file contents were invalid, returning index value 0")
        else:
            self.logger.log("encryption settings counter file not found, returning index value 0")
        return abs(index)

    def increment_index(self):
        """increment the internal counter used to index the encryption settings json file"""
        index = self.get_index()
        # specify buffering = 0 and then use os.fsync to flush
        # https://docs.python.org/2/library/functions.html#open
        # https://linux.die.net/man/2/fsync
        with open(CommonVariables.encryption_settings_counter_path, "wb", 0) as outfile:
            output = str(index + 1) + "\n"
            outfile.write(output.encode())
            outfile.flush()
            os.fsync(outfile.fileno())
        return

    def get_new_protector_name(self):
        """get a new guid to use as the protector name to pass to host"""
        # https://docs.microsoft.com/en-us/powershell/module/azurerm.keyvault/add-azurekeyvaultkey
        # The name must be a string of 1 through 63 characters in length
        # that contains only 0-9, a-z, A-Z, and - (the dash symbol).
        return str(uuid.uuid4())

    def create_protector_file(self, existing_passphrase_file, protector_name):
        """create temporary protector file corresponding to protector name"""
        dst = os.path.join(CommonVariables.encryption_key_mount_point, protector_name)
        copyfile(existing_passphrase_file, dst)
        import ctypes
        libc = ctypes.CDLL("libc.so.6")
        libc.sync()
        return

    def remove_protector_file(self, protector_name):
        """remove temporary protector file corresponding to protector name parameter"""
        os.remove(os.path.join(CommonVariables.encryption_key_mount_point, protector_name))
        return

    def get_settings_file_path(self):
        """get the full path to the current encryption settings file"""
        return os.path.join(CommonVariables.encryption_key_mount_point, self.get_settings_file_name())

    def get_settings_file_name(self):
        """get the base file name of the current encryption settings file"""
        padded_index = str(self.get_index()).zfill(2)
        return CommonVariables.encryption_settings_file_name_pattern.format(padded_index)

    def get_disk_items_from_crypt_items(self, crypt_items, disk_util):
        crypt_dev_items = []
        for crypt_item in crypt_items:
            dev_items = disk_util.get_device_items(crypt_item.dev_path)
            crypt_item_real_path = os.path.realpath(crypt_item.dev_path)
            for dev_item in dev_items:
                if os.path.realpath(disk_util.get_device_path(dev_item.name)) == crypt_item_real_path:
                    crypt_dev_items.append(dev_item)
                    break
        return crypt_dev_items

    # Helper function to make sure that we don't send secret tags with Null values (this causes HostAgent to error)
    def _dict_to_name_value_array(self, values):
        array = []
        for key in values:
            value = values[key]
            if value is not None:
                array.append({
                    "Name": key,
                    "Value": value
                    })
        return array

    def get_settings_data(self, protector_name, kv_url, kv_id, kek_url, kek_kv_id, kek_algorithm, extra_device_items, disk_util, crypt_mount_config_util):
        """ returns encryption settings object in format required by wire server """

        # validate key vault parameters prior to creating the encryption settings object
        # self.validate_key_vault_params(kv_url, kv_id, kek_url, kek_kv_id, kek_algorithm)

        # create encryption settings object
        self.logger.log("Creating encryption settings object")

        # validate machine name string or use empty string
        machine_name = socket.gethostname()
        if re.match('^[\\w-]+$', machine_name) is None:
            machine_name = ''

        # Get all the currently encrypted items from the Azure Crypt Mount file (hopefully this has been consolidated by now)
        existing_crypt_items = crypt_mount_config_util.get_crypt_items()
        existing_crypt_dev_items = self.get_disk_items_from_crypt_items(existing_crypt_items, disk_util)

        all_device_items = existing_crypt_dev_items + extra_device_items

        all_dev_items_real_paths = set([os.path.realpath(disk_util.get_device_path(di.name)) for di in all_device_items])

        self.logger.log("device items which will be used to find vhds to stamp: {0}".format(all_dev_items_real_paths))

        root_device_path = os.path.realpath(os.path.join(CommonVariables.azure_symlinks_dir, "root"))
        root_vhd_needs_stamping = disk_util.is_parent_of_any(root_device_path, all_dev_items_real_paths)

        # Get disk data from disk_util
        # We get a list of tuples i.e. [(scsi_controller_id, lun_number),.]
        data_disk_controller_ids_and_luns = disk_util.get_azure_data_disk_controller_and_lun_numbers(all_dev_items_real_paths)

        def controller_id_and_lun_to_settings_data(scsi_controller, lun_number):
            return {
                "ControllerType": "SCSI",
                "ControllerId": scsi_controller,
                "SlotId": lun_number,
                "Volumes": [{
                    "VolumeType": "DataVolume",
                    "ProtectorFileName": protector_name,
                    "SecretTags": self._dict_to_name_value_array({
                        "DiskEncryptionKeyFileName": CommonVariables.encryption_key_file_name + "_" + str(scsi_controller) + "_" + str(lun_number),
                        "DiskEncryptionKeyEncryptionKeyURL": kek_url,
                        "DiskEncryptionKeyEncryptionAlgorithm": kek_algorithm,
                        "MachineName": machine_name})
                    }]
                }

        data_disks_settings_data = [controller_id_and_lun_to_settings_data(scsi_controller, lun_number)
                                    for (scsi_controller, lun_number) in data_disk_controller_ids_and_luns]

        if root_vhd_needs_stamping:
            data_disks_settings_data.append({
                "ControllerType": "IDE",
                "ControllerId": 0,
                "SlotId": 0,
                "Volumes": [{
                    "VolumeType": "OsVolume",
                    "ProtectorFileName": protector_name,
                    "SecretTags": self._dict_to_name_value_array({
                        "DiskEncryptionKeyFileName": CommonVariables.encryption_key_file_name,
                        "DiskEncryptionKeyEncryptionKeyURL": kek_url,
                        "DiskEncryptionKeyEncryptionAlgorithm": kek_algorithm,
                        "MachineName": machine_name})
                    }]
                })

        full_protector_path = os.path.join(CommonVariables.encryption_key_mount_point, protector_name)
        with open(full_protector_path, "rb") as protector_file:
            protector_content = protector_file.read()
            protector_base64 = base64.standard_b64encode(protector_content)
            protectors = [{"Name": protector_name, "Base64Key": protector_base64}]

        protectors_name_only = [{"Name": protector["Name"], "Base64Key": "REDACTED"} for protector in protectors]

        data = {
            "DiskEncryptionDataVersion": self._DISK_ENCRYPTION_DATA_VERSION_V4,
            "DiskEncryptionOperation": "EnableEncryption",
            "KeyVaultUrl": kv_url,
            "KeyVaultResourceId": kv_id,
            "KekUrl": kek_url,
            "KekVaultResourceId": kek_kv_id,
            "KekAlgorithm": kek_algorithm,
            "Protectors": protectors_name_only,
            "Disks": data_disks_settings_data
        }

        self.logger.log("Settings without the protectors array: " + json.dumps(data, sort_keys=True, indent=4))
        self.logger.log("Full Settings JSON might be found later in the BEK VOLUME")

        data["Protectors"] = protectors

        return data

    def write_settings_file(self, data):
        """ Dump encryption settings data to JSON formatted file on key volume """
        self.increment_index()
        output = json.dumps(data)
        with open(self.get_settings_file_path(), 'wb', 0) as outfile:
            outfile.write(output.encode())
            outfile.flush()
            os.fsync(outfile.fileno())

        return

    def get_http_util(self):
        """
        Importing WAAgentUtil automatically causes unit tests to fail because WAAgentUtil
        tries to find and load waagent's source code right when you import it.
        And HttpUtil imports WAAgentUtil internally (again, causing unittests to fail very unproductively).
        Therefore putting the import here and mocking this method in the test helps the test proceed productively.
        """
        from HttpUtil import HttpUtil
        return HttpUtil(self.logger)

    def _post_to_wireserver_helper(self, msg_data, http_util):

        retry_count_max = 3
        retry_count = 0
        while retry_count < retry_count_max:
            try:
                result = http_util.Call(method='POST',
                                        http_uri=CommonVariables.wireserver_endpoint,
                                        headers=CommonVariables.wireprotocol_msg_headers,
                                        data=msg_data,
                                        use_https=False)

                if result is not None:
                    self.logger.log("{0} {1}".format(result.status, result.getheaders()))

                    result_content = result.read()
                    self.logger.log("result_content is {0}".format(result_content))

                    http_util.connection.close()
                    if result.status != http.client.OK and result.status != http.client.ACCEPTED:
                        raise Exception("Encryption settings post request was not accepted")
                    return
                else:
                    raise Exception("No response from encryption settings post request")
            except Exception as e:
                retry_count += 1
                self.logger.log("Encountered exception while posting encryption settings to Wire Server (attempt #{0}):\n{1}".format(str(retry_count), str(e)))
                if retry_count < retry_count_max:
                    time.sleep(5)  # sleep for 5 seconds before retrying.
                else:
                    raise e

    def post_to_wireserver(self, data):
        """ Request EnableEncryption operation on settings file via wire server """
        http_util = self.get_http_util()

        # V3 message content
        msg_data = CommonVariables.wireprotocol_msg_template_v3.format(settings_json_blob=json.dumps(data))
        try:
            self._post_to_wireserver_helper(msg_data, http_util)
        except Exception:
            self.logger.log("Falling back on old Wire Server protocol")
            data_copy = data.copy()
            data_copy.pop("Protectors")
            data_copy["DiskEncryptionDataVersion"] = self._DISK_ENCRYPTION_DATA_VERSION_V3

            self.write_settings_file(data_copy)
            if not os.path.isfile(self.get_settings_file_path()):
                raise Exception(
                    'Disk encryption settings file not found: ' + self.get_settings_file_path())

            msg_data = CommonVariables.wireprotocol_msg_template_v2.format(settings_file_name=self.get_settings_file_name())
            self._post_to_wireserver_helper(msg_data, http_util)

    def clear_encryption_settings(self, disk_util):
        """
        Clear settings by calling DisableEncryption operation via wire server

        finds all azure data disks and clears their encryption settings
        """

        self.logger.log("Clearing encryption settings for all data drives")

        data_disk_controller_ids_and_luns = disk_util.get_all_azure_data_disk_controller_and_lun_numbers()

        # validate machine name string or use empty string
        machine_name = socket.gethostname()
        if re.match('^[\\w-]+$', machine_name) is None:
            machine_name = ''

        def controller_id_and_lun_to_settings_data(scsi_controller, lun_number):
            return {
                "ControllerType": "SCSI",
                "ControllerId": scsi_controller,
                "SlotId": lun_number,
                "Volumes": [{
                    "VolumeType": "DataVolume",
                    "ProtectorFileName": "nullProtector.bek",
                    "SecretTags": self._dict_to_name_value_array({
                        "DiskEncryptionKeyFileName": "nullProtector.bek",
                        "MachineName": machine_name})
                    }]
                }

        protectors_null = []

        data_disks_settings_data = [controller_id_and_lun_to_settings_data(scsi_controller, lun_number)
                                    for (scsi_controller, lun_number) in data_disk_controller_ids_and_luns]

        data = {"DiskEncryptionDataVersion": self._DISK_ENCRYPTION_DATA_VERSION_V4,
                "DiskEncryptionOperation": "DisableEncryption",
                "Disks": data_disks_settings_data,
                "KekAlgorithm": "",
                "Protectors": protectors_null,
                "KekUrl": "",
                "KekVaultResourceId": "",
                "KeyVaultResourceId": "",
                "KeyVaultUrl": ""}
        self.logger.log("Settings to be sent for clear_encryption_settings: " + json.dumps(data, sort_keys=True, indent=4))
        self.post_to_wireserver(data)
        return
