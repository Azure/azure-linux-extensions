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

import time
import datetime
import traceback
import urlparse
import httplib
import shlex
import subprocess
from Common import CommonVariables
from subprocess import *
from Utils.WAAgentUtil import waagent

class HttpUtil(object):
    """description of class"""
    def __init__(self,logger):
        self.logger = logger
        try:
            waagent.MyDistro = waagent.GetMyDistro()
            Config = waagent.ConfigurationProvider(None)
        except Exception as e:
            errorMsg = "Failed to construct ConfigurationProvider, which may due to the old wala code."
            self.logger.log(errorMsg)
            Config = waagent.ConfigurationProvider()
        self.proxyHost = Config.get("HttpProxy.Host")
        self.proxyPort = Config.get("HttpProxy.Port")
        self.connection = None

    """
    snapshot also called this. so we should not write the file/read the file in this method.
    """

    def Call(self,method,http_uri,data,headers):
        try:
            uri_obj = urlparse.urlparse(http_uri)
            #parse the uri str here
            if(self.proxyHost is None or self.proxyPort is None):
                self.connection = httplib.HTTPSConnection(uri_obj.hostname, timeout = 10)
                if(uri_obj.query is not None):
                    self.connection.request(method = method, url=(uri_obj.path +'?'+ uri_obj.query), body = data, headers = headers)
                else:
                    self.connection.request(method = method, url=(uri_obj.path), body = data, headers = headers)
                resp = self.connection.getresponse()
            else:
                self.logger.log("proxyHost is not empty, so use the proxy to call the http.")
                self.connection = httplib.HTTPSConnection(self.proxyHost, self.proxyPort, timeout = 10)
                if(uri_obj.scheme.lower() == "https"):
                    self.connection.set_tunnel(uri_obj.hostname, 443)
                else:
                    self.connection.set_tunnel(uri_obj.hostname, 80)
                self.connection.request(method = method, url = (http_uri), body = data, headers = headers)
                resp = self.connection.getresponse()
            return resp
        except Exception as e:
            errorMsg = "Failed to call http with error: {0}, stack trace: {1}".format(e, traceback.format_exc())
            self.logger.log(errorMsg)
            return None