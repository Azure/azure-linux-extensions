# Copyright (C) Microsoft Corporation
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

import adal
import json
import sys
import base64

def get_key(filename):
    with open(filename, 'r') as key_file:
        private_key = key_file.read()
    return private_key

try:
    with open('data.json') as json_file:
        d = json.load(json_file)
    key = get_key(d['certificate'])
    context = adal.AuthenticationContext(d['auth'])
    token = context.acquire_token_with_client_certificate(d['client'],d['client'],key,d['thumbprint'])
    if token and 'accessToken' in token:
        print(token['accessToken'])
except:
    exit(1)