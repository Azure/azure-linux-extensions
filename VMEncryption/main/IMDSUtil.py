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

import os
import json
import time
import datetime
import traceback
import os.path
import sys
import math

from Common import CommonVariables
from ConfigUtil import ConfigUtil
from ConfigUtil import ConfigKeyValuePair
try:
    import http.client as httpclient #python3+
except ImportError:
    import httplib as httpclient #python2

import xml.etree.ElementTree as ET

class IMDSUtil(object):
    '''this class is used for reading VM information from IMDS'''
    def __init__(self, logger):
        self.logger = logger
    
    def get_http_util(self):
        """
        Importing WAAgentUtil automatically causes unit tests to fail because WAAgentUtil
        tries to find and load waagent's source code right when you import it.
        And HttpUtil imports WAAgentUtil internally (again, causing unittests to fail very unproductively).
        Therefore putting the import here and mocking this method in the test helps the test proceed productively.
        """
        from HttpUtil import HttpUtil
        return HttpUtil(self.logger)

    def get_fault_reason(self, content_xml):
        '''This function parse the xml content '''
        try:
            xml_root = ET.fromstring(content_xml)
        except:
            self.logger.log("Exception occured while parsing error xml.\n XML content: {0}".format(content_xml))
            return "Unknown"
        detail_element = xml_root.find('Details')
        if detail_element is not None and (detail_element.text is not None and len(detail_element.text) > 0):
            return detail_element.text
        else:
            return "Unknown"

    
    def _get_security_type_IMDS_helper(self,http_util):
        '''helper function to read VM's security type from IMDS'''
        retry_count_max = 7
        retry_count = 0
        imds_endpoint_uri = self.getUri(CommonVariables.IMDS_API_Version,CommonVariables.IMDS_SecurityProfile_subDir)   
        self.logger.log("IMDS end point url: {0}".format(imds_endpoint_uri))
        while retry_count<retry_count_max:
            try:
                result = http_util.Call(method ='GET',
                         http_uri=imds_endpoint_uri,
                         headers=CommonVariables.IMDS_msg_headers,
                         data = "",
                         use_https=False,
                         noProxy=True)
                if result is not None:
                    self.logger.log("{0} {1}".format(result.status,result.getheaders()))
                    result_content = result.read()
                    self.logger.log("result content is {0}".format(result_content))

                    http_util.connection.close()
                    if result.status != int(httpclient.OK) and result.status != int(httpclient.ACCEPTED):
                        reason = self.get_fault_reason(result_content)
                        raise Exception("IMDS call GET request was not accepted. Error: {0}".format(reason))
                    return result_content.decode()
                else:
                    raise Exception("No response from IMDS GET request.")
            except Exception as ex:
                retry_count += 1
                self.logger.log("Encountered exception from IMDS GET request to IMDS (attempt #{0}) \n{1}".format(str(retry_count),str(ex)))
                if retry_count<retry_count_max:
                    #execution:  1 2 3 4 5  6  7
                    #postrunwait:6 6 6 8 16 32 no_wait i.e. wait for 7th execution 74sec
                    sleeping_time = max(math.pow(2,retry_count-1),retry_count_max-1)
                    self.logger.log("sleeping for {0}s.".format(sleeping_time))
                    time.sleep(sleeping_time) 
                else:
                    raise Exception("IMDS request is failed to retrive VM's security profile, retry:{0} ref: https://aka.ms/imds".format(retry_count_max))

    def getUri(self,api_version,subdirectory):
        '''This function creates IMDS Uri'''
        uri = "http://{0}/{1}?api-version={2}".format(CommonVariables.static_IMDS_IP,subdirectory,api_version)
        return uri

    def get_vm_security_type(self):
        '''This function returns security type of VM.'''
        '''['','TrustedLaunch','ConfidentialVM']'''
        http_util = self.get_http_util()
        security_profile = json.loads(self._get_security_type_IMDS_helper(http_util=http_util))
        if not CommonVariables.SecurityTypeKey in security_profile:
            raise Exception("VM security profile does not have securityType.")
        return security_profile[CommonVariables.SecurityTypeKey]

class IMDSStoredResults(object):
    '''This class is used to store IMDS result in imds encryption config file'''
    def __init__(self, encryption_environment, logger):
        '''init call'''
        self.encryption_environment = encryption_environment
        self.security_type = None
        self.encryption_config = ConfigUtil(encryption_environment.imds_stored_results_file_path,
                                            'imds_stored_results',
                                            logger)
        self.logger = logger

    def config_file_exists(self):
        '''checking if encryption config file exist'''
        return self.encryption_config.config_file_exists()

    def get_security_type(self):
        '''read VM security type from file'''
        securityType = self.encryption_config.get_config(CommonVariables.SecurityTypeKey)
        return securityType if securityType else None

    def get_cfg_val(self, s):
        ''' return a string type that is compatible with the version of config parser that is in use'''
        if s is None:
            return ""

        if (sys.version_info > (3, 0)):
            return s  # python 3+ , preserve unicode
        else:
            if isinstance(s, unicode):
                # python2 ConfigParser does not properly support unicode, convert to ascii
                return s.encode('ascii', 'ignore')
            else:
                return s
                
    def commit(self):
        '''commit VM security type information in file.'''
        key_value_pairs = []
        sec_key = CommonVariables.SecurityTypeKey
        sec_val = self.get_cfg_val(self.security_type)
        # construct kvp collection
        command = ConfigKeyValuePair(sec_key, sec_val)
        key_value_pairs.append(command)
        # save settings in the configuration file
        self.encryption_config.save_configs(key_value_pairs)

    def clear_config(self, clear_parameter_file=False):
        '''clear configuration file'''
        try:
            if os.path.exists(self.encryption_environment.imds_stored_results_file_path):
                self.logger.log(msg="archiving the imds stored results file: {0}".format(self.encryption_environment.imds_stored_results_file_path))
                time_stamp = datetime.datetime.utcnow()
                new_name = "{0}_{1}".format(self.encryption_environment.imds_stored_results_file_path, time_stamp.isoformat())
                os.rename(self.encryption_environment.imds_stored_results_file_path, new_name)
            else:
                self.logger.log(msg=("the imds results file not exist: {0}".format(self.encryption_environment.imds_stored_results_file_path)), level=CommonVariables.WarningLevel)
            return True
        except OSError as e:
            self.logger.log("Failed to archive imds stored results with error: {0}, stack trace: {1}".format(printable(e), traceback.format_exc()))
            return False

