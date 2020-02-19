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

import os

def get_build_version_from_file():
    # Note, version.txt is expected to be within the same directory as this file
    file_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'version.txt')
    if not os.path.exists(file_path):
        raise IOError('Unexpected: version.txt file cannot be found at [%s]' % file_path)
    
    with open(file_path) as text_file:
        return text_file.read()