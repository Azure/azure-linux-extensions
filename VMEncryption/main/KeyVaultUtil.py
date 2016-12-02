#!/usr/bin/env python
#
# VM Backup extension
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

import httplib
import urlparse
import urllib
import json
import uuid
import base64
import traceback
import re
import os

from HttpUtil import HttpUtil
from Common import *
from urlparse import urlparse

class KeyVaultUtil(object):
    def __init__(self, logger):
        self.api_version = "2015-06-01"
        self.logger = logger

    def urljoin(self,*args):
        """
        Joins given arguments into a url. Trailing but not leading slashes are
        stripped for each argument.
        """
        return "/".join(map(lambda x: str(x).rstrip('/'), args))

    """
    The Passphrase is a plain encoded string. before the encryption it would be base64encoding.
    return the secret uri if creation successfully.
    """
    def create_kek_secret(self, Passphrase, KeyVaultURL, KeyEncryptionKeyURL, AADClientID, AADClientCertThumbprint, KeyEncryptionAlgorithm, AADClientSecret, DiskEncryptionKeyFileName):
        try:
            self.logger.log("start creating kek secret")
            passphrase_encoded = base64.standard_b64encode(Passphrase)
            keys_uri = self.urljoin(KeyVaultURL, "keys")

            http_util = HttpUtil(self.logger)
            headers = {}
            result = http_util.Call(method='GET', http_uri=keys_uri, data=None, headers=headers)
            http_util.connection.close()
            """
            get the access token 
            """
            self.logger.log("getting the access token.")
            bearerHeader = result.getheader("www-authenticate")

            authorize_uri = self.get_authorize_uri(bearerHeader)
            if authorize_uri is None:
                self.logger.log("the authorize uri is None")
                return None

            parsed_url = urlparse(KeyVaultURL)
            vault_domain = re.findall(r".*(vault.*)", parsed_url.netloc)[0]
            kv_resource_name = parsed_url.scheme + '://' + vault_domain

            access_token = self.get_access_token(kv_resource_name, authorize_uri, AADClientID, AADClientCertThumbprint, AADClientSecret)
            if access_token is None:
                self.logger.log("the access token is None")
                return None

            """
            we should skip encrypting the passphrase if the KeyVaultURL and KeyEncryptionKeyURL is empty
            """
            if KeyEncryptionKeyURL is None or KeyEncryptionKeyURL == "":
                secret_value = passphrase_encoded
            else:
                secret_value = self.encrypt_passphrase(access_token, passphrase_encoded, KeyVaultURL, KeyEncryptionKeyURL, AADClientID, KeyEncryptionAlgorithm, AADClientSecret)
            if secret_value is None:
                self.logger.log("secret value is None")
                return None

            secret_id = self.create_secret(access_token, KeyVaultURL, secret_value, KeyEncryptionAlgorithm, DiskEncryptionKeyFileName)

            return secret_id
        except Exception as e:
            self.logger.log("Failed to create_kek_secret with error: {0}, stack trace: {1}".format(e, traceback.format_exc()))
            return None

    def get_access_token(self, KeyVaultResourceName, AuthorizeUri, AADClientID, AADClientCertThumbprint, AADClientSecret):
        if not AADClientSecret and not AADClientCertThumbprint:
            raise Exception("Neither AADClientSecret nor AADClientCertThumbprint were specified")

        if AADClientSecret and AADClientCertThumbprint:
            raise Exception("Both AADClientSecret nor AADClientCertThumbprint were specified")

        if AADClientCertThumbprint:
            try:
                import adal
            except:
                raise Exception("adal library is not available on the VM")

            import waagent

            prv_path = os.path.join(waagent.LibDir, AADClientCertThumbprint.upper() + '.prv')
            prv_data = waagent.GetFileContents(prv_path)

            context = adal.AuthenticationContext(AuthorizeUri)
            result_json = context.acquire_token_with_client_certificate(KeyVaultResourceName, AADClientID, prv_data, AADClientCertThumbprint)
            access_token = result_json["accessToken"]
            return access_token


        token_uri = AuthorizeUri + "/oauth2/token"
        request_content = "resource=" + urllib.quote(KeyVaultResourceName) + "&client_id=" + AADClientID + "&client_secret=" + urllib.quote(AADClientSecret) + "&grant_type=client_credentials"
        headers = {}
        http_util = HttpUtil(self.logger)
        result = http_util.Call(method='POST', http_uri=token_uri, data=request_content, headers=headers)

        self.logger.log("{0} {1}".format(result.status, result.getheaders()))
        result_content = result.read()
        if result.status != httplib.OK and result.status != httplib.ACCEPTED:
            self.logger.log(str(result_content))
            return None
        http_util.connection.close()

        result_json = json.loads(result_content)
        access_token = result_json["access_token"]
        return access_token

    """
    return the encrypted secret uri if success. else return None
    """
    def encrypt_passphrase(self, AccessToken, Passphrase, KeyVaultURL, KeyEncryptionKeyURL, AADClientID, KeyEncryptionAlgorithm, AADClientSecret):
        try:
            """
            wrap our passphrase using the encryption key
            api ref for wrapkey: https://msdn.microsoft.com/en-us/library/azure/dn878066.aspx
            """
            self.logger.log("encrypting the secret using key: " + KeyEncryptionKeyURL)

            request_content = '{"alg":"' + str(KeyEncryptionAlgorithm) + '","value":"' + str(Passphrase) + '"}'
            headers = {}
            headers["Content-Type"] = "application/json"
            headers["Authorization"] = "Bearer " + str(AccessToken)
            relative_path = KeyEncryptionKeyURL + "/wrapkey" + '?api-version=' + self.api_version
            http_util = HttpUtil(self.logger)
            result = http_util.Call(method='POST', http_uri=relative_path, data=request_content, headers=headers)

            result_content = result.read()
            self.logger.log("result_content is: {0}".format(result_content))
            self.logger.log("{0} {1}".format(result.status, result.getheaders()))
            if result.status != httplib.OK and result.status != httplib.ACCEPTED:
                return None
            http_util.connection.close()
            result_json = json.loads(result_content)
            secret_value = result_json[u'value']
            return secret_value
        except Exception as e:
            self.logger.log("Failed to encrypt_passphrase with error: {0}, stack trace: %s".format(e, traceback.format_exc()))
            return None

    def create_secret(self, AccessToken, KeyVaultURL, secret_value, KeyEncryptionAlgorithm, DiskEncryptionKeyFileName):
        """
        create secret api https://msdn.microsoft.com/en-us/library/azure/dn903618.aspx
        https://mykeyvault.vault.azure.net/secrets/{secret-name}?api-version={api-version}
        """
        try:
            secret_name = str(uuid.uuid4())
            secret_keyvault_uri = self.urljoin(KeyVaultURL, "secrets", secret_name)
            self.logger.log("secret_keyvault_uri is: {0} and keyvault_uri is:{1}".format(secret_keyvault_uri, KeyVaultURL))
            if KeyEncryptionAlgorithm is None:
                request_content = '{{"value":"{0}","attributes":{{"enabled":"true"}},"tags":{{"DiskEncryptionKeyFileName":"{1}"}}}}'\
                    .format(str(secret_value), DiskEncryptionKeyFileName)
            else:
                request_content = '{{"value":"{0}","attributes":{{"enabled":"true"}},"tags":{{"DiskEncryptionKeyEncryptionAlgorithm":"{1}","DiskEncryptionKeyFileName":"{2}"}}}}'\
                    .format(str(secret_value), KeyEncryptionAlgorithm, DiskEncryptionKeyFileName)
            http_util = HttpUtil(self.logger)
            headers = {}
            headers["Content-Type"] = "application/json"
            headers["Authorization"] = "Bearer " + AccessToken
            result = http_util.Call(method='PUT', http_uri=secret_keyvault_uri + '?api-version=' + self.api_version, data=request_content, headers=headers)

            self.logger.log("{0} {1}".format(result.status, result.getheaders()))
            result_content = result.read()
            self.logger.log("result_content is {0}".format(result_content))
            result_json = json.loads(result_content)
            secret_id = result_json["id"]
            http_util.connection.close()
            if result.status != httplib.OK and result.status != httplib.ACCEPTED:
                self.logger.log("the result status failed.")
                return None
            return secret_id
        except Exception as e:
            self.logger.log("Failed to create_secret with error: {0}, stack trace: {1}".format(e, traceback.format_exc()))
            return None

    def get_authorize_uri(self, bearerHeader):
        """
        Bearer authorization="https://login.windows.net/72f988bf-86f1-41af-91ab-2d7cd011db47", resource="https://vault.azure.net"
        """
        try:
            self.logger.log("trying to get the authorize uri from: " + str(bearerHeader))
            bearerString = str(bearerHeader)
            authoirzation_key = 'authorization="'
            authoirzation_index = bearerString.index(authoirzation_key)
            bearerString = bearerString[(authoirzation_index + len(authoirzation_key)):]
            bearerString = bearerString[0:bearerString.index('"')]

            return bearerString
        except Exception as e:
            self.logger.log("Failed to get_authorize_uri with error: {0}, stack trace: {1}".format(e, traceback.format_exc()))
            return None
