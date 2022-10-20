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
import datetime
import os.path
import sys
import traceback

from Common import CommonVariables
from ConfigUtil import ConfigUtil
from ConfigUtil import ConfigKeyValuePair


class IMDSStoredResults(object):
    def __init__(self, encryption_environment, logger):
        self.encryption_environment = encryption_environment
        self.security_type = None
        self.encryption_config = ConfigUtil(encryption_environment.imds_stored_results_file_path,
                                            'imds_stored_results',
                                            logger)
        self.logger = logger

    def config_file_exists(self):
        return self.encryption_config.config_file_exists()

    def get_security_type(self):
        securityType = self.encryption_config.get_config(CommonVariables.SecurityTypeKey)
        return securityType if securityType else None

    def get_cfg_val(self, s):
        # return a string type that is compatible with the version of config parser that is in use
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
        key_value_pairs = []
        u_sect_key = CommonVariables.SecurityTypeKey
        u_sect_val = self.get_cfg_val(self.security_type)
        # construct kvp collection
        command = ConfigKeyValuePair(u_sect_key, u_sect_val)
        key_value_pairs.append(command)
        # save settings in the configuration file
        self.encryption_config.save_configs(key_value_pairs)

    def clear_config(self, clear_parameter_file=False):
        try:
            if os.path.exists(self.encryption_environment.imds_stored_results_file_path):
                self.logger.log(msg="archiving the imds stored results file: {0}".format(self.encryption_environment.imds_stored_results_file_path))
                time_stamp = datetime.datetime.now()
                new_name = "{0}_{1}".format(self.encryption_environment.imds_stored_results_file_path, time_stamp)
                os.rename(self.encryption_environment.imds_stored_results_file_path, new_name)
            else:
                self.logger.log(msg=("the imds results file not exist: {0}".format(self.encryption_environment.imds_stored_results_file_path)), level=CommonVariables.WarningLevel)
            return True
        except OSError as e:
            self.logger.log("Failed to archive imds stored results with error: {0}, stack trace: {1}".format(printable(e), traceback.format_exc()))
            return False
