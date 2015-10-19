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
import time
import datetime
import traceback
import urlparse
import httplib
from Utils.WAAgentUtil import waagent


class HttpUtil(object):
    """description of class"""
    def __init__(self):
        Config = waagent.ConfigurationProvider(None)
        self.proxyHost = Config.get("HttpProxy.Host")
        self.proxyPort = Config.get("HttpProxy.Port")

    def Call(self,method,sasuri_obj,data,headers):
        if(self.proxyHost == None or self.proxyPort == None):
            connection = httplib.HTTPSConnection(sasuri_obj.hostname)
            connection.request(method=method, uri=(sasuri_obj.path + '?' + sasuri_obj.query), body=data, headers = headers)
            resp = connection.getresponse()
            connection.close()
        else:
            connection = httplib.HTTPSConnection(proxyHost, proxyPort)
            connection.set_tunnel(sasuri_obj.hostname, 443)
            connection.request(method=method, uri=(sasuri_obj.path + '?' + sasuri_obj.query), body=data, headers=headers)
            resp = connection.getresponse()
            connection.close()
        return resp