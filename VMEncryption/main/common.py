#!/usr/bin/env python
#
# VM Backup extension
#
# Copyright 2014 Microsoft Corporation
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
#
# Requires Python 2.7+
#
class CommonVariables:
    azure_path = 'main/azure'
    utils_path_name = 'Utils'
    extension_name = 'VMEncryption'
    extension_version = 1.0
    extension_type = extension_name
    extension_media_link = 'https://andliu.blob.core.windows.net/extensions/' + extension_name + '-' + str(extension_version) + '.zip'
    extension_label = 'Windows Azure VMEncryption Extension for Linux IaaS'
    extension_description = extension_label
