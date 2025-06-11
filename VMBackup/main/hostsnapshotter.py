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

from asyncio.windows_events import NULL
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
    def __init__(self, logger, hostIp):
        self.logger = logger
        self.configfile='/etc/azure/vmbackup.conf'
        self.snapshoturi = 'http://' + hostIp + '/metadata/recsvc/snapshot/dosnapshot?api-version=2017-12-01'
        self.presnapshoturi = 'http://' + hostIp + '/metadata/recsvc/snapshot/presnapshot?api-version=2017-12-01'
        self.isOsDiskADEEncrypted = False
        self.areDataDisksADEEncrypted = False
        self.encryptionDetails = {}

    def snapshotall(self, paras, freezer, g_fsfreeze_on, taskId):
        result = None
        blob_snapshot_info_array = []
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
                settings = []
                if (paras.includeLunList != None and paras.includeLunList.count != 0):
                    diskIds = paras.includeLunList
                if(paras.wellKnownSettingFlags != None):
                    for flag in paras.wellKnownSettingFlags:
                        temp_dict = {}
                        temp_dict[CommonVariables.key] = flag
                        temp_dict[CommonVariables.value] = paras.wellKnownSettingFlags[flag]
                        settings.append(temp_dict)
                if(paras.isVMADEEnabled == True):
                    settings.append({CommonVariables.key:CommonVariables.isOsDiskADEEncrypted, CommonVariables.value:self.isOsDiskADEEncrypted})
                    settings.append({CommonVariables.key:CommonVariables.areDataDisksADEEncrypted, CommonVariables.value:self.areDataDisksADEEncrypted})
                    meta_data.append({CommonVariables.key:CommonVariables.encryptionDetails, CommonVariables.value:self.encryptionDetails})

                hostDoSnapshotRequestBodyObj = HostSnapshotObjects.HostDoSnapshotRequestBody(taskId, diskIds, settings, paras.snapshotTaskToken, meta_data)
                body_content = json.dumps(hostDoSnapshotRequestBodyObj, cls = HandlerUtil.ComplexEncoder)
                self.logger.log('Headers : ' + str(headers))
                self.logger.log('Host Request body : ' + str(body_content))
                http_util = HttpUtil(self.logger)
                self.logger.log("start calling the snapshot rest api")
                # initiate http call for blob-snapshot and get http response
                self.logger.log('****** 5. Snaphotting (Host) Started')
                result, httpResp, errMsg,responseBody = http_util.HttpCallGetResponse('POST', snapshoturi_obj, body_content, headers = headers, responseBodyRequired = True, isHostCall = True)
                self.logger.log('****** 6. Snaphotting (Host) Completed')
                self.logger.log("dosnapshot responseBody: " + responseBody)
                #performing thaw
                if g_fsfreeze_on :
                    time_before_thaw = datetime.datetime.now()
                    thaw_result, unable_to_sleep = freezer.thaw_safe()
                    time_after_thaw = datetime.datetime.now()
                    HandlerUtil.HandlerUtility.add_to_telemetery_data("ThawTime", str(time_after_thaw-time_before_thaw))
                    self.logger.log('T:S thaw result ' + str(thaw_result))
                    if(thaw_result is not None and len(thaw_result.errors) > 0):
                        is_inconsistent = True
                
                # Http response check(After thawing)
                if(httpResp != None):
                    HandlerUtil.HandlerUtility.add_to_telemetery_data(CommonVariables.hostStatusCodeDoSnapshot, str(httpResp.status))
                    if(int(httpResp.status) == 200 or int(httpResp.status) == 201) and (responseBody == None or responseBody == "") :
                        self.logger.log("DoSnapshot: responseBody is empty but http status code is success")
                        HandlerUtil.HandlerUtility.add_to_telemetery_data(CommonVariables.hostStatusCodeDoSnapshot, str(557))
                        all_failed = True
                    elif(int(httpResp.status) == 200 or int(httpResp.status) == 201):
                        blob_snapshot_info_array, all_failed = self.get_snapshot_info(responseBody)
                    if(httpResp.status == 500 and not responseBody.startswith("{ \"error\"")):
                        HandlerUtil.HandlerUtility.add_to_telemetery_data(CommonVariables.hostStatusCodeDoSnapshot, str(556))
                        all_failed = True
                else:
                    # HttpCall failed
                    HandlerUtil.HandlerUtility.add_to_telemetery_data(CommonVariables.hostStatusCodeDoSnapshot, str(555))
                    self.logger.log("presnapshot Hitting wrong WireServer IP")
        except Exception as e:
            errorMsg = "Failed to do the snapshot in host with error: %s, stack trace: %s" % (str(e), traceback.format_exc())
            self.logger.log(errorMsg, False, 'Error')
            HandlerUtil.HandlerUtility.add_to_telemetery_data(CommonVariables.hostStatusCodeDoSnapshot, str(558))
            all_failed = True
        return blob_snapshot_info_array, all_failed, is_inconsistent, unable_to_sleep

    def pre_snapshot(self, paras, taskId, fetch_disk_details = False):
        statusCode = 555
        if(self.presnapshoturi is None):
            self.logger.log("Failed to do the snapshot because presnapshoturi is none",False,'Error')
            all_failed = True
        try:
            presnapshoturi_obj = urlparser.urlparse(self.presnapshoturi)
            if(presnapshoturi_obj is None or presnapshoturi_obj.hostname is None):
                self.logger.log("Failed to parse the presnapshoturi",False,'Error')
                all_failed = True
            else:
                headers = {}
                headers['Backup'] = 'true'
                headers['Content-type'] = 'application/json'
                if(fetch_disk_details == True):
                    hostPreSnapshotRequestBodyObj = HostSnapshotObjects.HostPreSnapshotRequestBody(taskId, paras.snapshotTaskToken, paras.isVMADEEnabled)
                else:
                    hostPreSnapshotRequestBodyObj = HostSnapshotObjects.HostPreSnapshotRequestBody(taskId, paras.snapshotTaskToken)
                body_content = json.dumps(hostPreSnapshotRequestBodyObj, cls = HandlerUtil.ComplexEncoder)
                self.logger.log('Headers : ' + str(headers))
                self.logger.log('Host Request body : ' + str(body_content))
                http_util = HttpUtil(self.logger)
                self.logger.log("start calling the presnapshot rest api")
                # initiate http call for blob-snapshot and get http response
                result, httpResp, errMsg,responseBody = http_util.HttpCallGetResponse('POST', presnapshoturi_obj, body_content, headers = headers, responseBodyRequired = True, isHostCall = True)
                self.logger.log("presnapshot responseBody: " + responseBody)
                if(httpResp != None):
                    statusCode = httpResp.status
                    self.logger.log("PreSnapshot: Status Code: " + str(statusCode))
                    if(int(statusCode) == 200 or int(statusCode) == 201) and (responseBody == None or responseBody == "") :
                        self.logger.log("PreSnapshot:responseBody is empty but http status code is success")
                        statusCode = 557
                    elif(responseBody != None):
                        if (paras.isVMADEEnabled == True):
                            response = json.loads(responseBody)
                            self.isOsDiskADEEncrypted = response[CommonVariables.isOsDiskADEEncrypted]
                            self.areDataDisksADEEncrypted = response[CommonVariables.areDataDisksADEEncrypted]
                            self.encryptionDetails = response[CommonVariables.encryptionDetails]
                            self.logger.log("PreSnapshotResponse: isOsDiskADEEncrypted: "+ self.isOsDiskADEEncrypted)
                            self.logger.log("PreSnapshotResponse: areDataDisksADEEncrypted: "+ self.areDataDisksADEEncrypted)
                            if(self.encryptionDetails != NULL):
                                self.logger.log("PreSnapshotResponse: encryptionDetails: "+ len(self.encryptionDetails))
                            else:
                                self.logger.log("PreSnapshotResponse: EncryptionDetails are null")
                        else:
                            self.logger.log("VM is not ADE Enabled")
                    elif(httpResp.status == 500 and not responseBody.startswith("{ \"error\"")):
                        self.logger.log("BHS is not runnning on host machine")
                        statusCode = 556
                else:
                    # HttpCall failed
                    statusCode = 555
                    self.logger.log("presnapshot Hitting wrong WireServer IP")
        except Exception as e:
            errorMsg = "Failed to do the pre snapshot in host with error: %s, stack trace: %s" % (str(e), traceback.format_exc())
            self.logger.log(errorMsg, False, 'Error')
            statusCode = 558
        HandlerUtil.HandlerUtility.add_to_telemetery_data(CommonVariables.hostStatusCodePreSnapshot, str(statusCode))
        return statusCode, responseBody

    def get_snapshot_info(self, responseBody):
        blobsnapshotinfo_array = []
        all_failed = True
        try:
            if(responseBody != None):
                json_reponseBody = json.loads(responseBody)
                epochTime = datetime.datetime(1970, 1, 1, 0, 0, 0)
                for snapshot_info in json_reponseBody['snapshotInfo']:
                    self.logger.log("From Host- IsSuccessful:{0}, SnapshotUri:{1}, ErrorMessage:{2}, StatusCode:{3}".format(snapshot_info['isSuccessful'], snapshot_info['snapshotUri'], snapshot_info['errorMessage'], snapshot_info['statusCode']))
                    
                    ddSnapshotIdentifierInfo = None
                    if('ddSnapshotIdentifier' in snapshot_info and snapshot_info['ddSnapshotIdentifier'] != None):
                        creationTimeString = snapshot_info['ddSnapshotIdentifier']['creationTime']
                        self.logger.log("creationTime string from BHS : {0} ".format(creationTimeString))
                        try:
                            creationTimeObj = datetime.datetime.strptime(creationTimeString, "%Y-%m-%dT%H:%M:%S.%fZ")
                        except:
                            creationTimeObj = datetime.datetime.strptime(creationTimeString, "%Y-%m-%dT%H:%M:%SZ")
                        self.logger.log("Converting the creationTime string received in UTC format to UTC Ticks")
                        delta = creationTimeObj - epochTime
                        timestamp = self.get_total_seconds(delta)
                        creationTimeUTCTicks = str(int(timestamp * 1000)) 
                        ddSnapshotIdentifierInfo = HostSnapshotObjects.DDSnapshotIdentifier(creationTimeUTCTicks , snapshot_info['ddSnapshotIdentifier']['id'], snapshot_info['ddSnapshotIdentifier']['token'])
                        self.logger.log("ddSnapshotIdentifier Information from Host- creationTime : {0}, id : {1}".format(ddSnapshotIdentifierInfo.creationTime, ddSnapshotIdentifierInfo.id))
                    else:
                        self.logger.log("ddSnapshotIdentifier absent/None in Host Response")

                    blobsnapshotinfo_array.append(HostSnapshotObjects.BlobSnapshotInfo(snapshot_info['isSuccessful'], snapshot_info['snapshotUri'], snapshot_info['errorMessage'], snapshot_info['statusCode'], ddSnapshotIdentifierInfo))
                    
                    if (snapshot_info['isSuccessful'] == 'true'):
                        all_failed = False
        except Exception as e:
            errorMsg = " deserialization of response body failed with error: %s, stack trace: %s" % (str(e), traceback.format_exc())
            self.logger.log(errorMsg)

        return blobsnapshotinfo_array, all_failed
    
    def get_total_seconds(self, delta):
        # Check if total_seconds method exists in current Python version
        if hasattr(delta, 'total_seconds'):
            return delta.total_seconds()
        else:
            self.logger.log("Calculating total seconds manually for version compatibility.")
            return delta.days * 86400 + delta.seconds + delta.microseconds / 1e6
