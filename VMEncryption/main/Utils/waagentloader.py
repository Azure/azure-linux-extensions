# Wrapper module for waagent
#
# waagent is not written as a module. This wrapper module is created 
# to use the waagent code as a module.
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

import imp
import os

def load_waagent(path=None):
    if path is None:
        pwd = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(pwd, 'waagent')
    waagent = imp.load_source('waagent', path)
    waagent.LoggerInit('/var/log/waagent.log','/dev/stdout')
    waagent.MyDistro = waagent.GetMyDistro()
    waagent.Config = waagent.ConfigurationProvider(None)
    return waagent

