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

import os.path
from Common import *
from ConfigParser import *

class ConfigKeyValuePair(object):
    def __init__(self,prop_name,prop_value):
        self.prop_name = prop_name
        self.prop_value = prop_value

class ConfigUtil(object):
    def __init__(self, config_file_path, section_name, logger):
        """
        this should not create the config file with path: config_file_path
        """
        self.config_file_path = config_file_path
        self.logger = logger
        self.azure_crypt_config_section = section_name
    
    def config_file_exists(self):
        return os.path.exists(self.config_file_path)

    def save_config(self, prop_name, prop_value):
        #TODO make the operation an transaction.
        config = ConfigParser()
        if(os.path.exists(self.config_file_path)):
            config.read(self.config_file_path)
        # read values from a section
        if(not config.has_section(self.azure_crypt_config_section)):
            config.add_section(self.azure_crypt_config_section)
        config.set(self.azure_crypt_config_section, prop_name, prop_value)
        with open(self.config_file_path, 'wb') as configfile:
            config.write(configfile)

    def save_configs(self, key_value_pairs):
        config = ConfigParser()
        if(os.path.exists(self.config_file_path)):
            config.read(self.config_file_path)
        # read values from a section
        if(not config.has_section(self.azure_crypt_config_section)):
            config.add_section(self.azure_crypt_config_section)
        for key_value_pair in key_value_pairs:
            if(key_value_pair.prop_value is not None):
                config.set(self.azure_crypt_config_section, key_value_pair.prop_name, key_value_pair.prop_value)
        with open(self.config_file_path, 'wb') as configfile:
            config.write(configfile)

    def get_config(self,prop_name):
        # write the configs, the bek file name and so on.
        if(os.path.exists(self.config_file_path)):
            try:
                config = ConfigParser()
                config.read(self.config_file_path)
                # read values from a section
                prop_value = config.get(self.azure_crypt_config_section, prop_name)
                return prop_value
            except (NoSectionError, NoOptionError) as e:
                self.logger.log(msg="value of prop_name:{0} not found.".format(prop_name))
                return None
        else:
            self.logger.log("the config file {0} not exists.".format(self.config_file_path))
            return None