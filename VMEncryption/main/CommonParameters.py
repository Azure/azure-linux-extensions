#!/usr/bin/env python
#
# Azure Disk Encryption For Linux extension
#
# Copyright 2020 Microsoft Corporation
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

class CommonParameters:
    def __init__(self):
        self.file_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "common_parameters.json")
        with open(self.file_path, "r") as content:
            self.json_object = json.load(content)

    def get_extension_name(self):
        return self.json_object["extension_name"]

    def set_extension_name(self, value):
        self.json_object["extension_name"] = value

    def get_extension_version(self):
        return self.json_object["extension_version"]

    def set_extension_version(self, value):
        self.json_object["extension_version"] = value

    def get_extension_provider_namespace(self):
        return self.json_object["extension_provider_namespace"]

    def set_extension_provider_namespace(self, value):
        self.json_object["extension_provider_namespace"] = value

    def save(self):
        with open(self.file_path, 'w') as outfile:
            json.dump(self.json_object, outfile)

inst = CommonParameters()