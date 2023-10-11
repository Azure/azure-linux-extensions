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

import json
import os
import os.path
import socket
import re
import time
import base64

from check_util import CheckUtil
from shutil import copyfile
import uuid
from Common import CommonVariables
from io import open
try:
    import http.client as httpclient #python3+
except ImportError:
    import httplib as httpclient #python2

import xml.etree.ElementTree as ET
    
class EncryptionSettingsUtil(object):
    """ Provides capability to update encryption settings via wire server """

    def __init__(self, logger):
        self.logger = logger
        self._DISK_ENCRYPTION_DATA_VERSION_V4 = "4.0"
        self._DISK_ENCRYPTION_DATA_VERSION_V5 = "5.0"
        self._DISK_ENCRYPTION_KEY_SOURCE = None

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
        # use mode = "w" and encoding = "ascii" since writing text only
        with open(CommonVariables.encryption_settings_counter_path, mode="w", buffering=0, encoding="ascii") as outfile:
            output = str(index + 1) + "\n"  # str allows for a python2 + python3 compatible integer to string conversion
            outfile.write(output)
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

    def check_kv_url(self, test_kv_url, message):
        """basic sanity check of key vault url"""
        expected = "https://keyvault-name}.{vault-endpoint}"
        pattern = re.compile(r'^https://([a-zA-Z0-9\-]+)[\.]([a-zA-Z0-9\-\.]+)([/]?)$')
        if not (test_kv_url and pattern.match(test_kv_url)):
            raise Exception('\n' + message + '\nActual: ' + test_kv_url + '\nExpected: ' + expected + "\n")
        return

    def check_kek_url(self, test_kek_url, message):
        """basic sanity check of the key vault key url"""
        expected = "https://{keyvault-name}.{vault-endpoint}/keys/{object-name}/{object-version}"
        pattern = re.compile(r'^https://([a-zA-Z0-9\-]+)[\.]([a-zA-Z0-9\-\.]+)/keys/([a-zA-Z0-9\-]+)/([a-zA-Z0-9]+)([/]?)$')
        if not (test_kek_url and pattern.match(test_kek_url)):
            raise Exception('\n' + message + '\nActual: ' + test_kek_url + '\nExpected: ' + expected + "\n")
        return

    def check_kv_id(self, test_kv_id, message):
        """basic sanity check of the key vault id"""
        expected = "/subscriptions/{subid}/resourceGroups/{rgname}/providers/Microsoft.KeyVault/vaults/{vaultname}"
        pattern = re.compile(r'^/subscriptions/([a-zA-Z0-9\-]+)/resourceGroups/([a-zA-Z0-9\-\_]+)/providers/Microsoft.KeyVault/vaults/([a-zA-Z0-9\-\_]+)(/)?$')
        if not (test_kv_id and pattern.match(test_kv_id)):
            raise Exception('\n' + message + '\nActual: ' + test_kv_id + '\nExpected: ' + expected + "\n")
        return

    def get_kv_id_name(self, kv_id):
        """extract key vault name from KV ID"""
        match = re.search(r'^/subscriptions/([a-zA-Z0-9\-]+)/resourceGroups/([a-zA-Z0-9\-\_]+)/providers/Microsoft.KeyVault/vaults/([a-zA-Z0-9\-\_]+)(/)?$', kv_id)
        if match:
            return match.group(3)
        else:
            return None

    def get_kv_url_name(self, kv_url):
        """extract key vault name from KV URL"""
        match = re.search(r'^https://([a-zA-Z0-9\-]+)[\.]([a-zA-Z0-9\-\.]+)([/]?)$', kv_url)
        if match:
            return match.group(1)
        else:
            return None

    def get_kek_url_name(self, kek_url):
        """extract key vault name from kek url"""
        match = re.search(r'^https://([a-zA-Z0-9\-]+)[\.]([a-zA-Z0-9\-\.]+)/keys/([a-zA-Z0-9\-]+)/([a-zA-Z0-9]+)([/]?)$', kek_url)
        if match:
            return match.group(1)
        else:
            return None

    def check_kv_name(self, kv_id, kv_url, message):
        """ensure KV ID vault name matches KV URL"""
        if not (kv_id and kv_url and get_kv_id_name(kv_id).lower() == get_kv_url_name(kv_url).lower()):
            raise Exception('\n' + message + '\nKey Vault ID: ' + kv_id + '\nKey Vault URL: ' + kv_url + '\n')
        return

    def check_kek_name(self, kek_kv_id, kek_url, message):
        """ensure KEK KV ID vault name matches KEK URL vault name"""
        if not (kek_kv_id and kek_url and get_kv_id_name(kek_kv_id).lower() == get_kek_url_name(kek_url).lower()):
            raise Exception('\n' +message + '\nKEK Key Vault ID: ' + kek_kv_id + '\nKEK URL: ' + kek_url + '\n')
        return

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

    def get_settings_data(self, protector_name, kv_url, kv_id, kek_url, kek_kv_id, kek_algorithm, extra_device_items, disk_util, crypt_mount_config_util, key_store_type, keystoretype_flag_exists):
        """ returns encryption settings object in format required by wire server """

        cutil = CheckUtil(self.logger)

        # Perform algorithm check regaurdless of ManagedHSM or Keyvault
        if kek_url and kek_algorithm not in CommonVariables.encryption_algorithms:
                    if kek_algorithm:
                        raise Exception("The KEK encryption algorithm requested was not recognized")
                    else:
                        kek_algorithm = CommonVariables.default_encryption_algorithm
                        self.logger.log("No KEK algorithm specified, defaulting to {0}".format(kek_algorithm))

        # ManagedHSM Checks
        if key_store_type and key_store_type.lower() == CommonVariables.KeyStoreTypeManagedHSM.lower():
            # validate mhsm parameters prior to creating the encryption settings object
            if kv_url or kv_id:
                raise Exception("KeyvaultUrl or KeyvaultresourceId are not empty, and 'KeyStoreType' parameter is set to ManagedHSM. Please remove KeyvaultUrl KeyvaultresourceId for ManagedHSM.")
            self.logger.log("get_settings_data: KeyVault Url is empty, validating KeyEncryptionKeyKVURL and KeyEncryptionKeyKVId for ManagedHSM")
            cutil.check_mhsm_url(kek_url, "A ManagedHSM URL is specified, but it is invalid for ManagedHSM.")
            cutil.check_mhsm_id(kek_kv_id, "A ManagedHSM ID is required, but is missing or invalid.")
            cutil.check_mhsm_name(kek_kv_id, kek_url, "A ManagedHSM ID and ManagedHSM URL were provided, but their ManagedHSM names did not match")
            # for private preview data collection, set key source to MHSM
            self._DISK_ENCRYPTION_KEY_SOURCE = CommonVariables.KeyStoreTypeManagedHSM
        elif keystoretype_flag_exists:
            raise Exception("The expected flag name and value to enable ManagedHSM is 'KeyStoreType':'{0}'. " +
            "Please correct the flag name and value and retry enabling ManagedHSM, or remove the flag for KeyVault use.".format(CommonVariables.KeyStoreTypeManagedHSM))
       # Keyvault Checks
        else:
            # validate key vault parameters prior to creating the encryption settings object
            cutil.check_kv_id(kv_id, "A KeyVault ID is required, but is missing or invalid")
            cutil.check_kv_url(kv_url, "A KeyVault URL is required, but is missing or invalid")
            cutil.check_kv_name(kv_id, kv_url, "A KeyVault ID and KeyVault URL were provided, but their key vault names did not match")
            if kek_url:
                cutil.check_kv_id(kek_kv_id, "A KEK URL was specified, but its KEK KeyVault ID was missing or invalid")
                cutil.check_kek_url(kek_url, "A KEK URL was specified, but it was invalid")
                cutil.check_kek_name(kek_kv_id, kek_url, "A KEK ID and KEK URL were provided, but their key vault names did not match")
            else:
                if kek_kv_id:
                    raise Exception("The KEK KeyVault ID was specified but the KEK URL was missing")
            # for private preview data collection, set key source to KeyVault
            self._DISK_ENCRYPTION_KEY_SOURCE = CommonVariables.KeyStoreTypeKeyVault

        # create encryption settings object
        self.logger.log("Creating encryption settings object")
        self.logger.log("The disk encryption key source used is: {0}".format(self._DISK_ENCRYPTION_KEY_SOURCE))

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

        root_device_path = os.path.join(CommonVariables.azure_symlinks_dir, "root")
        root_device_path_scsi = os.path.join(CommonVariables.azure_symlinks_dir, "scsi0/lun0")
        is_os_nvme, root_device_path_nvme = disk_util.is_os_disk_nvme()
        if os.path.exists(root_device_path):
            root_device_path = os.path.realpath(root_device_path)
        elif os.path.exists(root_device_path_scsi):
            root_device_path = os.path.realpath(root_device_path_scsi)
        elif is_os_nvme and os.path.exists(root_device_path_nvme):
            root_device_path = os.path.realpath(root_device_path_nvme)
        else:
            self.logger.log("Cannot locate root device")
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
        # b64encode takes a bytes like object, so read as binary data
        with open(full_protector_path, "rb") as protector_file:
            protector_data = protector_file.read()
            protector_base64 = base64.standard_b64encode(protector_data).decode('utf_8')
            protectors = [{"Name": protector_name, "Base64Key": protector_base64}]

        protectors_name_only = [{"Name": protector["Name"], "Base64Key": "REDACTED"} for protector in protectors]

        if self._DISK_ENCRYPTION_KEY_SOURCE == CommonVariables.KeyStoreTypeManagedHSM:
            data_version = self._DISK_ENCRYPTION_DATA_VERSION_V5
        else:
            data_version = self._DISK_ENCRYPTION_DATA_VERSION_V4

        data = {
            "DiskEncryptionDataVersion": data_version,
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
        # encode as utf-8 and write as binary data for consistency across python2 + python3
        with open(self.get_settings_file_path(), 'wb', 0) as outfile:
            outfile.write(output.encode('utf-8')) 
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

    def get_wireserver_endpoint_uri(self):

        wireserver_endpoint_file = CommonVariables.wireserver_endpoint_file
        wireserver_IP = None
        wireserver_endpoint_uri = CommonVariables.wireserver_endpoint_uri

        if os.path.exists(wireserver_endpoint_file):
            with open(wireserver_endpoint_file, 'r') as wip:
                wireserver_IP = wip.readline().strip()
                self.logger.log("wireserver_IP found in {0} = {1}".format(wireserver_endpoint_file, wireserver_IP))

                # validate the IP address found in wireserver_endpoint_file
                if re.match(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', wireserver_IP) is None:
                    wireserver_IP = None
                    self.logger.log("wireserver_IP found in file is not valid.")

        if wireserver_IP is None:
            self.logger.log("Using static wireServer_IP from CommonVariables")
            wireserver_IP = CommonVariables.static_wireserver_IP

        wireserver_endpoint = "http://" + wireserver_IP + wireserver_endpoint_uri
        self.logger.log("wireserver_endpoint = {0}".format(wireserver_endpoint))
        return wireserver_endpoint

    def _post_to_wireserver_helper(self, msg_data, http_util):

        retry_count_max = 3
        retry_count = 0
        wireserver_endpoint_uri = self.get_wireserver_endpoint_uri()
        while retry_count < retry_count_max:
            try:
                result = http_util.Call(method='POST',
                                        http_uri=wireserver_endpoint_uri,
                                        headers=CommonVariables.wireprotocol_msg_headers,
                                        data=msg_data,
                                        use_https=False)

                if result is not None:
                    self.logger.log("{0} {1}".format(result.status, result.getheaders()))

                    result_content = result.read()
                    self.logger.log("result_content is {0}".format(result_content))

                    http_util.connection.close()
                    # cast to httpclient constants to int for python2 + python3 compatibility
                    if result.status != int(httpclient.OK) and result.status != int(httpclient.ACCEPTED):
                        reason = self.get_fault_reason(result_content)
                        raise Exception("Encryption settings post request was not accepted. Error: {0}".format(reason))
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

    def get_fault_reason(self, content_xml):
        try:
            xml_root = ET.fromstring(content_xml)
        except:
            self.logger.log("Exception occured while parsing error xml.")
            return "Unknown"
        detail_element = xml_root.find('Details')
        if detail_element is not None and (detail_element.text is not None and len(detail_element.text) > 0):
            return detail_element.text
        else:
            return "Unknown"

    def post_to_wireserver(self, data):
        """ Request EnableEncryption operation on settings file via wire server """
        http_util = self.get_http_util()

        # V3 message content
        msg_data = CommonVariables.wireprotocol_msg_template_v3.format(settings_json_blob=json.dumps(data))
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

        # Send version 4.0 for disable in KeyVault and ManagedHSM Scenarios 
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
