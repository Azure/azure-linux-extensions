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

import os
try:
    import urlparse as urlparser
except ImportError:
    import urllib.parse as urlparser
import traceback
import datetime
try:
    import ConfigParser as ConfigParsers
except ImportError:
    import configparser as ConfigParsers
import multiprocessing as mp
import datetime
import json
from common import CommonVariables
from HttpUtil import HttpUtil
from Utils import Status
from Utils import HostSnapshotObjects
from Utils import HandlerUtil
from fsfreezer import FsFreezer
import sys

class HostSnapshotter(object):
    """description of class"""
    def __init__(self, logger):
        self.logger = logger
        self.configfile='/etc/azure/vmbackup.conf'
        self.snapshoturi = 'http://168.63.129.16/metadata/recsvc/snapshot/dosnapshot?api-version=2017-12-01'

    def snapshotall(self, paras, freezer):
        result = None
        snapshot_info_array = []
        all_failed = True
        is_inconsistent = False
        unable_to_sleep = False
        meta_data = paras.backup_metadata
        if(self.snapshoturi is None):
            self.logger.log("Failed to do the snapshot because snapshoturi is none",False,'Error')
            all_failed = True
        try:
            snapshoturi_obj = urlparser.urlparse(self.snapshoturi)
            if(snapshoturi_obj is None or snapshoturi_obj.hostname is None):
                self.logger.log("Failed to parse the snapshoturi",False,'Error')
                all_failed = True
            else:
                diskIds = []
                body_content = ''
                headers = {}
                headers['Backup'] = 'true'
                headers['Content-type'] = 'application/json'
                hostRequestBodyObj = HostSnapshotObjects.HostRequestBody(paras.taskId, diskIds, paras.snapshotTaskToken, meta_data)
                body_content = json.dumps(hostRequestBodyObj, cls = HandlerUtil.ComplexEncoder)
                self.logger.log('Headers : ' + str(headers))
                self.logger.log('Host Request body : ' + str(body_content))
                http_util = HttpUtil(self.logger)
                self.logger.log("start calling the snapshot rest api")
                # initiate http call for blob-snapshot and get http response
                result, httpResp, errMsg,responseBody = http_util.HttpCallGetResponse('POST', snapshoturi_obj, body_content, headers = headers, responseBodyRequired = True, isHttpCall = True)
                self.logger.log("responseBody: " + responseBody)
                if(httpResp != None):
                    snapshot_info_array, all_failed = self.get_snapshot_info(responseBody)
                    HandlerUtil.HandlerUtility.add_to_telemetery_data("statusCodeFromHost", str(httpResp.status))
                #performing thaw
                time_before_thaw = datetime.datetime.now()
                thaw_result, unable_to_sleep = freezer.thaw_safe()
                time_after_thaw = datetime.datetime.now()
                HandlerUtil.HandlerUtility.add_to_telemetery_data("ThawTime", str(time_after_thaw-time_before_thaw))
                self.logger.log('T:S thaw result ' + str(thaw_result))
                if(thaw_result is not None and len(thaw_result.errors) > 0):
                    is_inconsistent = True
                else:
                    # HttpCall failed
                    self.logger.log(" snapshot HttpCallGetResponse failed ")
                    self.logger.log(str(errMsg))
        except Exception as e:
            errorMsg = "Failed to do the snapshot in host with error: %s, stack trace: %s" % (str(e), traceback.format_exc())
            self.logger.log(errorMsg, False, 'Error')
            all_failed = True
        return snapshot_info_array, all_failed, is_inconsistent, unable_to_sleep

    def get_snapshot_info(self, responseBody):
        snapshotinfo_array = []
        all_failed = True
        try:
            if(responseBody != None):
                json_reponseBody = json.loads(responseBody)
                for snapshot_info in json_reponseBody['snapshotInfo']:
                    snapshotinfo_array.append(Status.SnapshotInfoObj(snapshot_info['isSuccessful'], snapshot_info['snapshotUri'], snapshot_info['errorMessage']))
                    self.logger.log("IsSuccessful:{0}, SnapshotUri:{1}, ErrorMessage:{2}, StatusCode:{3}".format(snapshot_info['isSuccessful'], snapshot_info['snapshotUri'], snapshot_info['errorMessage'], snapshot_info['statusCode']))
                    if (snapshot_info['isSuccessful'] == 'true'):
                        all_failed = False
        except Exception as e:
            errorMsg = " deserialization of response body failed with error: %s, stack trace: %s" % (str(e), traceback.format_exc())
            self.logger.log(errorMsg)

        return snapshotinfo_array, all_failed
