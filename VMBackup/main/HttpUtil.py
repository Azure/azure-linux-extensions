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
try:
    import httplib as httplibs
except ImportError:
    import http.client as httplibs
import shlex
import subprocess
import sys
from common import CommonVariables
from subprocess import *
from Utils.WAAgentUtil import waagent
import sys

class HttpUtil(object):
    """description of class"""
    __instance = None
    """Singleton class initialization"""
    def __new__(cls, hutil):
        if(cls.__instance is None):
            hutil.log("Creating HttpUtil")
            cls.__instance = super(HttpUtil, cls).__new__(cls)
            try:
                waagent.MyDistro = waagent.GetMyDistro()
                Config = waagent.ConfigurationProvider(None)
            except Exception as e:
                errorMsg = "Failed to construct ConfigurationProvider, which may due to the old wala code with error: %s, stack trace: %s" % (str(e), traceback.format_exc())
                hutil.log(errorMsg)
                Config = None
            cls.__instance.logger = hutil
            if Config != None:
                cls.__instance.proxyHost = Config.get("HttpProxy.Host")
                cls.__instance.proxyPort = Config.get("HttpProxy.Port")
            cls.__instance.tmpFile = './tmp_file_FD76C85E-406F-4CFA-8EB0-CF18B123365C'
        else:
            cls.__instance.logger = hutil
            cls.__instance.logger.log("Returning HttpUtil")
        return cls.__instance

    """
    snapshot also called this. so we should not write the file/read the file in this method.
    """
    def CallUsingCurl(self,method,sasuri_obj,data,headers):
        header_str = ""
        for key, value in headers.iteritems():
            header_str = header_str + '-H ' + '"' + str(key) + ':' + str(value) + '"'

        if(self.proxyHost == None or self.proxyPort == None):
            commandToExecute = 'curl --request PUT --connect-timeout 10 --data-binary @-' + ' ' + header_str + ' "' + sasuri_obj.scheme + '://' + sasuri_obj.hostname + sasuri_obj.path + '?' + sasuri_obj.query + '"' + ' -v'
        else:
            commandToExecute = 'curl --request PUT --connect-timeout 10 --data-binary @-' + ' ' + header_str + ' "' + sasuri_obj.scheme + '://' + sasuri_obj.hostname + sasuri_obj.path + '?' + sasuri_obj.query + '"'\
                + '--proxy ' + self.proxyHost + ':' + self.proxyPort + ' -v'
        args = shlex.split(commandToExecute.encode('ascii'))
        proc = Popen(args,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        proc.stdin.write(data)
        curlResult,err = proc.communicate()
        returnCode = proc.wait()
        self.logger.log("curl error is: " + str(err))
        self.logger.log("curl return code is : " + str(returnCode))
        # what if the curl is returned successfully, but the http response is
        # 403
        if(returnCode == 0):
            return CommonVariables.success
        else:
            return CommonVariables.error_http_failure

    def Call(self, method, sasuri_obj, data, headers, fallback_to_curl = False):
        try:
            result, resp, errorMsg = self.HttpCallGetResponse(method, sasuri_obj, data, headers)
            self.logger.log("HttpUtil Call : result: " + str(result) + ", errorMsg: " + str(errorMsg))
            if(result == CommonVariables.success and resp != None):
                self.logger.log("resp-header: " + str(resp.getheaders()))
            else:
                self.logger.log("Http connection response is None")

            responseBody = resp.read()
            self.logger.log(" resp status: " + str(resp.status))
            if(responseBody is not None):
                self.logger.log("responseBody: " + (responseBody).decode('utf-8-sig'))

            if(resp.status == 200 or resp.status == 201):
                return CommonVariables.success
            else:
                return resp.status
        except Exception as e:
            errorMsg = "Failed to call http with error: %s, stack trace: %s" % (str(e), traceback.format_exc())
            self.logger.log(errorMsg)
            if(fallback_to_curl):
                return self.CallUsingCurl(method,sasuri_obj,data,headers)
            else:
                return CommonVariables.error_http_failure

    def HttpCallGetResponse(self, method, sasuri_obj, data, headers , responseBodyRequired = False, isHostCall = False):
        result = CommonVariables.error_http_failure
        resp = None
        responeBody = ""
        errorMsg = None
        responseBody = None
        try:
            resp = None
            self.logger.log("Entered HttpCallGetResponse, isHostCall: " + str(isHostCall))

            if(isHostCall or self.proxyHost == None or self.proxyPort != None):
                if(isHostCall):
                    connection = httplibs.HTTPConnection(sasuri_obj.hostname, timeout = 10) # making call with port 80 to make it http call
                else:
                    connection = httplibs.HTTPSConnection(sasuri_obj.hostname, timeout = 10)
                self.logger.log("Details of sas uri object  hostname: " + str(sasuri_obj.hostname) + " path: " + str(sasuri_obj.path))
                connection.request(method=method, url=(sasuri_obj.path + '?' + sasuri_obj.query), body=data, headers = headers)
                resp = connection.getresponse()
                if(responseBodyRequired):
                    responeBody = resp.read().decode('utf-8-sig')
                connection.close()
            else:
                connection = httplibs.HTTPSConnection(self.proxyHost, self.proxyPort, timeout = 10)
                connection.set_tunnel(sasuri_obj.hostname, 443)
                # If proxy is used, full url is needed.
                path = "https://{0}:{1}{2}".format(sasuri_obj.hostname, 443, (sasuri_obj.path + '?' + sasuri_obj.query))
                connection.request(method=method, url=(path), body=data, headers=headers)
                resp = connection.getresponse()
                connection.close()
            result = CommonVariables.success
        except Exception as e:
            errorMsg = str(datetime.datetime.now()) +  " Failed to call http with error: %s, stack trace: %s" % (str(e), traceback.format_exc())
            self.logger.log(errorMsg)
            if sys.version[0] == 2 and sys.version[1] == 6:
                self.CallUsingCurl(method,sasuri_obj,data,headers)
        if(responseBodyRequired):
            return result, resp, errorMsg, responeBody
        else:
            return result, resp, errorMsg
