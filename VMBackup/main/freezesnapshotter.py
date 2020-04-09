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
import time
import json
from common import CommonVariables
from HttpUtil import HttpUtil
from Utils import Status
from Utils import HandlerUtil
from fsfreezer import FsFreezer
from guestsnapshotter import GuestSnapshotter
from hostsnapshotter import HostSnapshotter
from Utils import HostSnapshotObjects
import ExtensionErrorCodeHelper
import sys

# need to be implemented in next release
#from dhcpHandler import DhcpHandler

class FreezeSnapshotter(object):
    """description of class"""
    def __init__(self, logger, hutil , freezer, g_fsfreeze_on, para_parser, takeCrashConsistentSnapshot):
        self.logger = logger
        self.configfile = '/etc/azure/vmbackup.conf'
        self.hutil = hutil
        self.freezer = freezer
        self.g_fsfreeze_on = g_fsfreeze_on
        self.para_parser = para_parser
        if(para_parser.snapshotTaskToken == None):
            para_parser.snapshotTaskToken = '' #making snaoshot string empty when snapshotTaskToken is null
        self.logger.log('snapshotTaskToken : ' + str(para_parser.snapshotTaskToken))
        self.takeSnapshotFrom = CommonVariables.firstGuestThenHost
        self.isManaged = False
        self.taskId = self.para_parser.taskId
        self.hostIp = '168.63.129.16'
        self.extensionErrorCode = ExtensionErrorCodeHelper.ExtensionErrorCodeEnum.success
        self.takeCrashConsistentSnapshot = takeCrashConsistentSnapshot
        self.logger.log('FreezeSnapshotter : takeCrashConsistentSnapshot = ' + str(self.takeCrashConsistentSnapshot))

        #implement in next release
        '''
        # fetching wireserver IP from DHCP
        self.dhcpHandlerObj = None
        try:
            self.dhcpHandlerObj = DhcpHandler(self.logger)
            self.hostIp = self.dhcpHandlerObj.getHostEndoint()
        except Exception as e:
            errorMsg = "Failed to get hostIp from DHCP with error: %s, stack trace: %s" % (str(e), traceback.format_exc())
            self.logger.log(errorMsg, True, 'Error')
            self.hostIp = '168.63.129.16'
        '''

        self.logger.log( "hostIp : " + self.hostIp)

        try:
            if(para_parser.customSettings != None and para_parser.customSettings != ''):
                self.logger.log('customSettings : ' + str(para_parser.customSettings))
                customSettings = json.loads(para_parser.customSettings)
                snapshotMethodConfigValue = self.hutil.get_strvalue_from_configfile(CommonVariables.SnapshotMethod,customSettings['takeSnapshotFrom'])
                self.logger.log('snapshotMethodConfigValue : ' + str(snapshotMethodConfigValue))
                if snapshotMethodConfigValue != None and snapshotMethodConfigValue != '':
                    self.takeSnapshotFrom = snapshotMethodConfigValue
                else:
                    self.takeSnapshotFrom = customSettings['takeSnapshotFrom']
                
                if(para_parser.includedDisks != None and CommonVariables.isAnyDiskExcluded in para_parser.includedDisks.keys()):
                    if (para_parser.includedDisks[CommonVariables.isAnyDiskExcluded] == True):
                        self.logger.log('Some disks are excluded from backup. Setting the snapshot mode to onlyGuest.')
                        self.takeSnapshotFrom = CommonVariables.onlyGuest

                #Not hitting host when snapshot uri has special characters
                if self.hutil.UriHasSpecialCharacters(self.para_parser.blobs):
                    self.logger.log('Some disk blob Uris have special characters. Setting the snapshot mode to onlyGuest.')
                    self.takeSnapshotFrom = CommonVariables.onlyGuest

                self.isManaged = customSettings['isManagedVm']
                if( "backupTaskId" in customSettings.keys()):
                    self.taskId = customSettings["backupTaskId"]
        except Exception as e:
            errMsg = 'Failed to serialize customSettings with error: %s, stack trace: %s' % (str(e), traceback.format_exc())
            self.logger.log(errMsg, True, 'Error')
            self.isManaged = True

        self.logger.log('[FreezeSnapshotter] isManaged flag : ' + str(self.isManaged))

    def doFreezeSnapshot(self):
        run_result = CommonVariables.success
        run_status = 'success'
        all_failed = False
        unable_to_sleep = False

        """ Do Not remove below HttpUtil object creation. This is to ensure HttpUtil singleton object is created before freeze."""
        http_util = HttpUtil(self.logger)

        if(self.takeSnapshotFrom == CommonVariables.onlyGuest):
            run_result, run_status, blob_snapshot_info_array, all_failed, all_snapshots_failed, unable_to_sleep, is_inconsistent = self.takeSnapshotFromGuest()
        elif(self.takeSnapshotFrom == CommonVariables.firstGuestThenHost):
            run_result, run_status, blob_snapshot_info_array, all_failed, unable_to_sleep, is_inconsistent = self.takeSnapshotFromFirstGuestThenHost()
        elif(self.takeSnapshotFrom == CommonVariables.firstHostThenGuest):
            run_result, run_status, blob_snapshot_info_array, all_failed, unable_to_sleep, is_inconsistent = self.takeSnapshotFromFirstHostThenGuest()
        elif(self.takeSnapshotFrom == CommonVariables.onlyHost):
            run_result, run_status, blob_snapshot_info_array, all_failed, unable_to_sleep, is_inconsistent = self.takeSnapshotFromOnlyHost()
        else :
            self.logger.log('Snapshot method did not match any listed type, taking  firstHostThenGuest as default')
            run_result, run_status, blob_snapshot_info_array, all_failed, unable_to_sleep, is_inconsistent = self.takeSnapshotFromFirstHostThenGuest()

        self.logger.log('doFreezeSnapshot : run_result - {0} run_status - {1} all_failed - {2} unable_to_sleep - {3} is_inconsistent - {4} values post snapshot'.format(str(run_result), str(run_status), str(all_failed), str(unable_to_sleep), str(is_inconsistent)))

        if (run_result == CommonVariables.success):
            run_result, run_status = self.updateErrorCode(blob_snapshot_info_array, all_failed, unable_to_sleep, is_inconsistent)

        snapshot_info_array = self.update_snapshotinfoarray(blob_snapshot_info_array)

        if not (run_result == CommonVariables.success):
            self.hutil.SetExtErrorCode(self.extensionErrorCode)

        return run_result, run_status, snapshot_info_array
    
    def update_snapshotinfoarray(self, blob_snapshot_info_array):
        snapshot_info_array = []

        self.logger.log('updating snapshot info array from blob snapshot info')
        if blob_snapshot_info_array != None and blob_snapshot_info_array !=[]:
            for blob_snapshot_info in blob_snapshot_info_array:
                if blob_snapshot_info != None:
                    snapshot_info_array.append(Status.SnapshotInfoObj(blob_snapshot_info.isSuccessful, blob_snapshot_info.snapshotUri, blob_snapshot_info.errorMessage))

        return snapshot_info_array

    def updateErrorCode(self, blob_snapshot_info_array, all_failed, unable_to_sleep, is_inconsistent):
        run_result = CommonVariables.success
        any_failed = False
        run_status = 'success'

        if unable_to_sleep:
            run_result = CommonVariables.error
            run_status = 'error'
            error_msg = 'T:S Machine unable to sleep'
            self.logger.log(error_msg, True, 'Error')
        elif is_inconsistent == True :
            run_result = CommonVariables.error
            run_status = 'error'
            error_msg = 'Snapshots are inconsistent'
            self.logger.log(error_msg, True, 'Error')
        elif blob_snapshot_info_array != None:
            for blob_snapshot_info in blob_snapshot_info_array:
                if blob_snapshot_info != None and blob_snapshot_info.errorMessage != None :
                    if 'The rate of snapshot blob calls is exceeded' in blob_snapshot_info.errorMessage:
                        run_result = CommonVariables.FailedRetryableSnapshotRateExceeded
                        run_status = 'error'
                        error_msg = 'Retrying when snapshot failed with SnapshotRateExceeded'
                        self.extensionErrorCode = ExtensionErrorCodeHelper.ExtensionErrorCodeEnum.FailedRetryableSnapshotRateExceeded
                        self.logger.log(error_msg, True, 'Error')
                        break
                    elif 'The snapshot count against this blob has been exceeded' in blob_snapshot_info.errorMessage:
                        run_result = CommonVariables.FailedSnapshotLimitReached
                        run_status = 'error'
                        error_msg = 'T:S Enable failed with FailedSnapshotLimitReached errror'
                        self.extensionErrorCode = ExtensionErrorCodeHelper.ExtensionErrorCodeEnum.FailedSnapshotLimitReached
                        error_msg = error_msg + ExtensionErrorCodeHelper.ExtensionErrorCodeHelper.StatusCodeStringBuilder(self.extensionErrorCode)
                        self.logger.log(error_msg, True, 'Error')
                        break
                    elif blob_snapshot_info.isSuccessful == False and not all_failed:
                        any_failed = True
                elif blob_snapshot_info != None and blob_snapshot_info.isSuccessful == False:
                    any_failed = True

        if run_result == CommonVariables.success and all_failed:
            run_status = 'error'
            run_result = CommonVariables.FailedRetryableSnapshotFailedNoNetwork
            error_msg = 'T:S Enable failed with FailedRetryableSnapshotFailedNoNetwork errror'
            self.extensionErrorCode = ExtensionErrorCodeHelper.ExtensionErrorCodeEnum.FailedRetryableSnapshotFailedNoNetwork
            error_msg = error_msg + ExtensionErrorCodeHelper.ExtensionErrorCodeHelper.StatusCodeStringBuilder(self.extensionErrorCode)
            self.logger.log(error_msg, True, 'Error')
        elif run_result == CommonVariables.success and any_failed:
            run_result = CommonVariables.FailedRetryableSnapshotFailedNoNetwork
            error_msg = 'T:S Enable failed with FailedRetryableSnapshotFailedRestrictedNetwork errror'
            self.extensionErrorCode = ExtensionErrorCodeHelper.ExtensionErrorCodeEnum.FailedRetryableSnapshotFailedRestrictedNetwork
            error_msg = error_msg + ExtensionErrorCodeHelper.ExtensionErrorCodeHelper.StatusCodeStringBuilder(self.extensionErrorCode)
            run_status = 'error'
            self.logger.log(error_msg, True, 'Error')
        
        return run_result, run_status

    def freeze(self):
        try:
            timeout = self.hutil.get_intvalue_from_configfile('timeout',60)
            self.logger.log('T:S freeze, timeout value ' + str(timeout))
            time_before_freeze = datetime.datetime.now()
            freeze_result,timedout = self.freezer.freeze_safe(timeout)
            time_after_freeze = datetime.datetime.now()
            freezeTimeTaken = time_after_freeze-time_before_freeze
            self.logger.log('T:S ***** freeze, time_before_freeze=' + str(time_before_freeze) + ", time_after_freeze=" + str(time_after_freeze) + ", freezeTimeTaken=" + str(freezeTimeTaken))
            HandlerUtil.HandlerUtility.add_to_telemetery_data("FreezeTime", str(time_after_freeze-time_before_freeze-datetime.timedelta(seconds=5)))
            run_result = CommonVariables.success
            run_status = 'success'
            all_failed= False
            is_inconsistent =  False
            self.logger.log('T:S freeze result ' + str(freeze_result) + ', timedout :' + str(timedout))
            if (timedout == True):
                run_result = CommonVariables.FailedFsFreezeTimeout
                run_status = 'error'
                error_msg = 'T:S ###### Enable failed with error: freeze took longer than timeout'
                self.extensionErrorCode = ExtensionErrorCodeHelper.ExtensionErrorCodeEnum.FailedRetryableFsFreezeTimeout
                error_msg = error_msg + ExtensionErrorCodeHelper.ExtensionErrorCodeHelper.StatusCodeStringBuilder(self.extensionErrorCode)
                self.logger.log(error_msg, True, 'Error')
            elif(freeze_result is not None and len(freeze_result.errors) > 0 and CommonVariables.unable_to_open_err_string in str(freeze_result)):
                run_result = CommonVariables.FailedUnableToOpenMount
                run_status = 'error'
                error_msg = 'T:S Enable failed with error: ' + str(freeze_result)
                self.extensionErrorCode = ExtensionErrorCodeHelper.ExtensionErrorCodeEnum.FailedRetryableUnableToOpenMount
                error_msg = error_msg + ExtensionErrorCodeHelper.ExtensionErrorCodeHelper.StatusCodeStringBuilder(self.extensionErrorCode)
                self.logger.log(error_msg, True, 'Warning')
            elif(freeze_result is not None and len(freeze_result.errors) > 0):
                run_result = CommonVariables.FailedFsFreezeFailed
                run_status = 'error'
                error_msg = 'T:S Enable failed with error: ' + str(freeze_result)
                self.extensionErrorCode = ExtensionErrorCodeHelper.ExtensionErrorCodeEnum.FailedRetryableFsFreezeFailed
                error_msg = error_msg + ExtensionErrorCodeHelper.ExtensionErrorCodeHelper.StatusCodeStringBuilder(self.extensionErrorCode)
                self.logger.log(error_msg, True, 'Warning')
        except Exception as e:
            errMsg = 'Failed to do the freeze with error: %s, stack trace: %s' % (str(e), traceback.format_exc())
            self.logger.log(errMsg, True, 'Error')
            run_result = CommonVariables.error
            run_status = 'error'
        
        return run_result, run_status

    def GetBlobProperties(self, blobUri):
        blobProperties = None
        if(blobUri is not None):     
            try:
                http_util = HttpUtil(self.logger)
                sasuri_obj = urlparser.urlparse(blobUri+ '&comp=metadata')
                headers = {}
                result, httpResp, errMsg = http_util.HttpCallGetResponse('GET', sasuri_obj, None, headers = headers)
                self.logger.log("GetBlobProperties: HttpCallGetResponse : result :" + str(result) + ", errMsg :" + str(errMsg))
                blobProperties = self.httpresponse_get_blob_properties(httpResp)
            except Exception as e:
                self.logger.log("GetBlobProperties: Failed to get blob properties with error: %s, stack trace: %s" % (str(e), traceback.format_exc()))
        return blobProperties

    def GetHeaderSize(self, headers):
    # max size of blob metadata 
            return sys.getsizeof(json.dumps(headers))


    def httpresponse_get_blob_properties(self, httpResp):
        blobProperties = {}
        if(httpResp != None):
            self.hutil.log("httpresponse_get_blob_properties: Blob-properties response status:"+str(httpResp.status))
            if(httpResp.status == 200):
                resp_headers = httpResp.getheaders()
                blobProperties = resp_headers
        return blobProperties

    def populate_snapshotreq_headers_perblob(self, sasuri, sasuri_index, backup_meta_data):
        headers= {}
        headers["Content-Length"] = '0'
        blobMetdataMaxSizeBytes = 8000

        original_blob_metadata = self.GetBlobProperties(sasuri)
        
        if(original_blob_metadata is not None): 
            for meta in original_blob_metadata:
                Key,Value = meta
                headers[Key] = Value

        if(backup_meta_data is not None):
            for meta in backup_meta_data:
                key = meta['Key']
                value = meta['Value']
                headers["x-ms-meta-" + key] = value
     
        level1BlobMetadataSize = self.GetHeaderSize(headers)
        
        if level1BlobMetadataSize > blobMetdataMaxSizeBytes:
            if sasuri_index not in blobMetadataTelemetryMessage :
                blobMetadataTelemetryMessage[sasuri_index] = ""

            blobMetadataTelemetryMessage[sasuri_index]+="Level 1 : " + str(level1BlobMetadataSize);

            headers = {}
            if(original_blob_metadata is not None): 
                for meta in original_blob_metadata:
                    Key,Value = meta
                    if Key == "x-ms-meta-diskencryptionsettings" :
                        headers[Key] = Value
                        break

            if(backup_meta_data is not None):
                for meta in backup_meta_data:
                    key = meta['Key']
                    value = meta['Value']
                    headers["x-ms-meta-" + key] = value

            level2BlobMetadataSize = self.GetHeaderSize(headers)
            
            if level2BlobMetadataSize > blobMetdataMaxSizeBytes :
                blobMetadataTelemetryMessage[sasuri_index]+= ", Level 2 : " + str(level2BlobMetadataSize);

                headers = {}
                if(backup_meta_data is not None):
                    for meta in backup_meta_data:
                        key = meta['Key']
                        value = meta['Value']
                        headers["x-ms-meta-" + key] = value
                
        return headers


    def populate_blob_metadata_all(self, paras):
        blob_metadata = {}
        try:
            blobs = paras.blobs
            if blobs is not None:
                blob_index = 0
                self.logger.log('****** Starting metadata retrieval for all blobs')
                
                for blob in blobs:
                    blobUri = blob.split("?")[0]
                    self.logger.log("index: " + str(blob_index) + " blobUri: " + str(blobUri))
                    blob_metadata[blob_index] = self.populate_snapshotreq_headers_perblob(blobUri,blob_index,paras.backup_metadadata)
                    self.logger.log("Metadata count added : " + str(len(blob_metadata[blob_index])))
                    blob_index = blob_index + 1

        except Exception as e:
            errorMsg = " Unable to retreive metadata for blobs : %s, stack trace: %s" % (str(e), traceback.format_exc())
            self.logger.log(errorMsg)

        return blob_metadata
     
    def takeSnapshotFromGuest(self):
        run_result = CommonVariables.success
        run_status = 'success'

        all_failed= False
        is_inconsistent =  False
        unable_to_sleep = False
        blob_snapshot_info_array = None
        all_snapshots_failed = False
        try:
            if( self.para_parser.blobs == None or len(self.para_parser.blobs) == 0) :
                run_result = CommonVariables.FailedRetryableSnapshotFailedNoNetwork
                run_status = 'error'
                error_msg = 'T:S taking snapshot failed as blobs are empty or none'
                self.logger.log(error_msg, True, 'Error')
                all_failed = True
                all_snapshots_failed = True
                return run_result, run_status, blob_snapshot_info_array, all_failed, all_snapshots_failed, unable_to_sleep, is_inconsistent

            # populate metadata for all blobs
            blob_metadata = self.populate_blob_metadata_all(self.para_parser)

            if self.g_fsfreeze_on :
                run_result, run_status = self.freeze()

            if(run_result == CommonVariables.success or self.takeCrashConsistentSnapshot == True):
                HandlerUtil.HandlerUtility.add_to_telemetery_data(CommonVariables.snapshotCreator, CommonVariables.guestExtension)
                snap_shotter = GuestSnapshotter(self.logger, self.hutil)
                self.logger.log('T:S doing snapshot now...')
                time_before_snapshot = datetime.datetime.now()
                snapshot_result, blob_snapshot_info_array, all_failed, is_inconsistent, unable_to_sleep, all_snapshots_failed = snap_shotter.snapshotall(self.para_parser, self.freezer, self.g_fsfreeze_on, self.blob_metadata)
                time_after_snapshot = datetime.datetime.now()
                snapshotTimeTaken = time_after_snapshot-time_before_snapshot
                self.logger.log('T:S ***** takeSnapshotFromGuest, time_before_snapshot=' + str(time_before_snapshot) + ", time_after_snapshot=" + str(time_after_snapshot) + ", snapshotTimeTaken=" + str(snapshotTimeTaken))
                HandlerUtil.HandlerUtility.add_to_telemetery_data("snapshotTimeTaken", str(snapshotTimeTaken))
                self.logger.log('T:S snapshotall ends...', True)

        except Exception as e:
            errMsg = 'Failed to do the snapshot with error: %s, stack trace: %s' % (str(e), traceback.format_exc())
            self.logger.log(errMsg, True, 'Error')
            run_result = CommonVariables.error
            run_status = 'error'

        return run_result, run_status, blob_snapshot_info_array, all_failed, all_snapshots_failed, unable_to_sleep, is_inconsistent

    def takeSnapshotFromFirstGuestThenHost(self):
        run_result = CommonVariables.success
        run_status = 'success'

        all_failed= False
        is_inconsistent =  False
        unable_to_sleep = False
        blob_snapshot_info_array = None
        all_snapshots_failed = False

        run_result, run_status, blob_snapshot_info_array, all_failed, all_snapshots_failed, unable_to_sleep, is_inconsistent  = self.takeSnapshotFromGuest()

        if(all_snapshots_failed):
            try:
                #to make sure binary is thawed
                self.logger.log('[takeSnapshotFromFirstGuestThenHost] : Thawing again post the guest snapshotting failure')
                self.freezer.thaw_safe()
            except Exception as e:
                self.logger.log('[takeSnapshotFromFirstGuestThenHost] : Exception in Thaw %s, stack trace: %s' % (str(e), traceback.format_exc()))

            run_result, run_status, blob_snapshot_info_array,all_failed, unable_to_sleep, is_inconsistent = self.takeSnapshotFromOnlyHost()

        return run_result, run_status, blob_snapshot_info_array, all_failed, unable_to_sleep, is_inconsistent

    def takeSnapshotFromFirstHostThenGuest(self):

        run_result = CommonVariables.success
        run_status = 'success'

        all_failed= False
        is_inconsistent =  False
        unable_to_sleep = False
        blob_snapshot_info_array = None
        snap_shotter = HostSnapshotter(self.logger, self.hostIp)
        pre_snapshot_statuscode = snap_shotter.pre_snapshot(self.para_parser, self.taskId)

        if(pre_snapshot_statuscode == 200 or pre_snapshot_statuscode == 201):
            run_result, run_status, blob_snapshot_info_array, all_failed, unable_to_sleep, is_inconsistent = self.takeSnapshotFromOnlyHost()
        else:
            run_result, run_status, blob_snapshot_info_array, all_failed, all_snapshots_failed, unable_to_sleep, is_inconsistent  = self.takeSnapshotFromGuest()

            if all_snapshots_failed and run_result != CommonVariables.success:
                self.extensionErrorCode = ExtensionErrorCodeHelper.ExtensionErrorCodeEnum.FailedRetryableSnapshotFailedNoNetwork
            elif run_result != CommonVariables.success :
                self.extensionErrorCode = ExtensionErrorCodeHelper.ExtensionErrorCodeEnum.FailedRetryableSnapshotFailedRestrictedNetwork

        return run_result, run_status, blob_snapshot_info_array, all_failed, unable_to_sleep, is_inconsistent

    def takeSnapshotFromOnlyHost(self):
        run_result = CommonVariables.success
        run_status = 'success'
        all_failed= False
        is_inconsistent =  False
        unable_to_sleep = False
        blob_snapshot_info_array = None
        self.logger.log('Taking Snapshot through Host')
        HandlerUtil.HandlerUtility.add_to_telemetery_data(CommonVariables.snapshotCreator, CommonVariables.backupHostService)

        if self.g_fsfreeze_on :
            run_result, run_status = self.freeze()
        if(run_result == CommonVariables.success or self.takeCrashConsistentSnapshot == True):
            snap_shotter = HostSnapshotter(self.logger, self.hostIp)
            self.logger.log('T:S doing snapshot now...')
            time_before_snapshot = datetime.datetime.now()
            blob_snapshot_info_array, all_failed, is_inconsistent, unable_to_sleep  = snap_shotter.snapshotall(self.para_parser, self.freezer, self.g_fsfreeze_on, self.taskId)
            time_after_snapshot = datetime.datetime.now()
            snapshotTimeTaken = time_after_snapshot-time_before_snapshot
            self.logger.log('T:S takeSnapshotFromHost, time_before_snapshot=' + str(time_before_snapshot) + ", time_after_snapshot=" + str(time_after_snapshot) + ", snapshotTimeTaken=" + str(snapshotTimeTaken))
            HandlerUtil.HandlerUtility.add_to_telemetery_data("snapshotTimeTaken", str(snapshotTimeTaken))
            self.logger.log('T:S snapshotall ends...', True)

        return run_result, run_status, blob_snapshot_info_array, all_failed, unable_to_sleep, is_inconsistent
