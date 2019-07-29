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
from common import CommonVariables
from HttpUtil import HttpUtil
from Utils import Status
from Utils import HandlerUtil
from fsfreezer import FsFreezer
from Utils import HostSnapshotObjects

class SnapshotInfoIndexerObj():
    def __init__(self, index, isSuccessful, snapshotTs, errorMessage):
        self.index = index
        self.isSuccessful = isSuccessful
        self.snapshotTs = snapshotTs
        self.errorMessage = errorMessage
        self.statusCode = 500
    def __str__(self):
        return 'index: ' + str(self.index) + ' isSuccessful: ' + str(self.isSuccessful) + ' snapshotTs: ' + str(self.snapshotTs) + ' errorMessage: ' + str(self.errorMessage) + ' statusCode: ' + str(self.statusCode)

class SnapshotError(object):
    def __init__(self):
        self.errorcode = CommonVariables.success
        self.sasuri = None
    def __str__(self):
        return 'errorcode: ' + str(self.errorcode)

class SnapshotResult(object):
    def __init__(self):
        self.errors = []

    def __str__(self):
        error_str = ""
        for error in self.errors:
            error_str+=(str(error)) + "\n"
        return error_str

class GuestSnapshotter(object):
    """description of class"""
    def __init__(self, logger, hutil):
        self.logger = logger
        self.configfile='/etc/azure/vmbackup.conf'
        self.hutil = hutil

    def snapshot(self, sasuri, sasuri_index, meta_data, snapshot_result_error, snapshot_info_indexer_queue, global_logger, global_error_logger):
        temp_logger=''
        error_logger=''
        snapshot_error = SnapshotError()
        snapshot_info_indexer = SnapshotInfoIndexerObj(sasuri_index, False, None, None)
        if(sasuri is None):
            error_logger = error_logger + str(datetime.datetime.now()) + " Failed to do the snapshot because sasuri is none "
            snapshot_error.errorcode = CommonVariables.error
            snapshot_error.sasuri = sasuri
        try:
            sasuri_obj = urlparser.urlparse(sasuri)
            if(sasuri_obj is None or sasuri_obj.hostname is None):
                error_logger = error_logger + str(datetime.datetime.now()) + " Failed to parse the sasuri "
                snapshot_error.errorcode = CommonVariables.error
                snapshot_error.sasuri = sasuri
            else:
                start_time = datetime.datetime.utcnow()
                body_content = ''
                headers = {}
                headers["Content-Length"] = '0'
                if(meta_data is not None): 
                    for meta in meta_data:
                        key = meta['Key']
                        value = meta['Value']
                        headers["x-ms-meta-" + key] = value
                temp_logger = temp_logger + str(headers)
                http_util = HttpUtil(self.logger)
                sasuri_obj = urlparser.urlparse(sasuri + '&comp=snapshot')
                temp_logger = temp_logger + str(datetime.datetime.now()) + ' start calling the snapshot rest api. '
                # initiate http call for blob-snapshot and get http response
                result, httpResp, errMsg, responseBody  = http_util.HttpCallGetResponse('PUT', sasuri_obj, body_content, headers = headers, responseBodyRequired = True)
                temp_logger = temp_logger + str("responseBody: " + responseBody)
                if(result == CommonVariables.success and httpResp != None):
                    # retrieve snapshot information from http response
                    snapshot_info_indexer, snapshot_error, message = self.httpresponse_get_snapshot_info(httpResp, sasuri_index, sasuri, responseBody)
                    temp_logger = temp_logger + str(datetime.datetime.now()) + ' httpresponse_get_snapshot_info message: ' + str(message)
                else:
                    # HttpCall failed
                    error_logger = error_logger + str(datetime.datetime.now()) + " snapshot HttpCallGetResponse failed "
                    error_logger = error_logger + str(datetime.datetime.now()) + str(errMsg)
                    snapshot_error.errorcode = CommonVariables.error
                    snapshot_error.sasuri = sasuri
                end_time = datetime.datetime.utcnow()
                time_taken=end_time-start_time
                temp_logger = temp_logger + str(datetime.datetime.now()) + ' time taken for snapshot ' + str(time_taken)
        except Exception as e:
            errorMsg = " Failed to do the snapshot with error: %s, stack trace: %s" % (str(e), traceback.format_exc())
            error_logger = error_logger + str(datetime.datetime.now()) + errorMsg
            snapshot_error.errorcode = CommonVariables.error
            snapshot_error.sasuri = sasuri
        temp_logger=temp_logger + str(datetime.datetime.now()) + ' snapshot ends..'
        global_logger.put(temp_logger)
        global_error_logger.put(error_logger)
        snapshot_result_error.put(snapshot_error)
        snapshot_info_indexer_queue.put(snapshot_info_indexer)

    def snapshot_seq(self, sasuri, sasuri_index, meta_data):
        result = None
        snapshot_error = SnapshotError()
        snapshot_info_indexer = SnapshotInfoIndexerObj(sasuri_index, False, None, None)
        if(sasuri is None):
            self.logger.log("Failed to do the snapshot because sasuri is none",False,'Error')
            snapshot_error.errorcode = CommonVariables.error
            snapshot_error.sasuri = sasuri
        try:
            sasuri_obj = urlparser.urlparse(sasuri)
            if(sasuri_obj is None or sasuri_obj.hostname is None):
                self.logger.log("Failed to parse the sasuri",False,'Error')
                snapshot_error.errorcode = CommonVariables.error
                snapshot_error.sasuri = sasuri
            else:
                body_content = ''
                headers = {}
                headers["Content-Length"] = '0'
                if(meta_data is not None):
                    for meta in meta_data:
                        key = meta['Key']
                        value = meta['Value']
                        headers["x-ms-meta-" + key] = value
                self.logger.log(str(headers))
                http_util = HttpUtil(self.logger)
                sasuri_obj = urlparser.urlparse(sasuri + '&comp=snapshot')
                self.logger.log("start calling the snapshot rest api")
                # initiate http call for blob-snapshot and get http response
                result, httpResp, errMsg, responseBody  = http_util.HttpCallGetResponse('PUT', sasuri_obj, body_content, headers = headers, responseBodyRequired = True)
                self.logger.log("responseBody: " + responseBody)
                if(result == CommonVariables.success and httpResp != None):
                    # retrieve snapshot information from http response
                    snapshot_info_indexer, snapshot_error, message = self.httpresponse_get_snapshot_info(httpResp, sasuri_index, sasuri, responseBody)
                    self.logger.log(' httpresponse_get_snapshot_info message: ' + str(message))
                else:
                    # HttpCall failed
                    self.logger.log(" snapshot HttpCallGetResponse failed ")
                    self.logger.log(str(errMsg))
                    snapshot_error.errorcode = CommonVariables.error
                    snapshot_error.sasuri = sasuri
        except Exception as e:
            errorMsg = "Failed to do the snapshot with error: %s, stack trace: %s" % (str(e), traceback.format_exc())
            self.logger.log(errorMsg, False, 'Error')
            snapshot_error.errorcode = CommonVariables.error
            snapshot_error.sasuri = sasuri
        return snapshot_error, snapshot_info_indexer

    def snapshotall_parallel(self, paras, freezer, thaw_done, g_fsfreeze_on):
        self.logger.log("doing snapshotall now in parallel...")
        snapshot_result = SnapshotResult()
        blob_snapshot_info_array = []
        all_failed = True
        exceptOccurred = False
        is_inconsistent = False
        thaw_done_local = thaw_done
        unable_to_sleep = False
        all_snapshots_failed = False
        set_next_backup_to_seq = False
        try:
            self.logger.log("before start of multiprocessing queues..")
            mp_jobs = []
            queue_creation_starttime = datetime.datetime.now()
            global_logger = mp.Queue()
            global_error_logger = mp.Queue()
            snapshot_result_error = mp.Queue()
            snapshot_info_indexer_queue = mp.Queue()
            time_before_snapshot_start = datetime.datetime.now()
            blobs = paras.blobs

            if blobs is not None:
                # initialize blob_snapshot_info_array
                mp_jobs = []
                blob_index = 0
                for blob in blobs:
                    blobUri = blob.split("?")[0]
                    self.logger.log("index: " + str(blob_index) + " blobUri: " + str(blobUri))
                    blob_snapshot_info_array.append(HostSnapshotObjects.BlobSnapshotInfo(False, blobUri, None, 500))
                    try:
                        mp_jobs.append(mp.Process(target=self.snapshot,args=(blob, blob_index, paras.backup_metadata, snapshot_result_error, snapshot_info_indexer_queue, global_logger, global_error_logger)))
                    except Exception as e:
                        self.logger.log("multiprocess queue creation failed")
                        all_snapshots_failed = True
                        raise Exception("Exception while creating multiprocess queue")

                    blob_index = blob_index + 1

                counter = 0
                for job in mp_jobs:
                    job.start()
                    if(counter == 0):
                        queue_creation_endtime = datetime.datetime.now()
                        timediff = queue_creation_endtime - queue_creation_starttime
                        if(timediff.seconds >= 10):
                            self.logger.log("mp queue creation took more than 10 secs. Setting next backup to sequential")
                            set_next_backup_to_seq = True
                    counter = counter + 1

                time_after_snapshot_start = datetime.datetime.now()
                timeout = self.get_value_from_configfile('timeout')
                if timeout == None:
                    timeout = 60

                for job in mp_jobs:
                    job.join()
                thaw_result = None
                if g_fsfreeze_on and thaw_done_local == False:
                    time_before_thaw = datetime.datetime.now()
                    thaw_result, unable_to_sleep = freezer.thaw_safe()
                    time_after_thaw = datetime.datetime.now()
                    HandlerUtil.HandlerUtility.add_to_telemetery_data("ThawTime", str(time_after_thaw-time_before_thaw))
                    thaw_done_local = True
                    if(set_next_backup_to_seq == True):
                        self.logger.log("Setting to sequential snapshot")
                        self.hutil.set_value_to_configfile('seqsnapshot', '1')
                    self.logger.log('T:S thaw result ' + str(thaw_result))
                    if(thaw_result is not None and len(thaw_result.errors) > 0  and (snapshot_result is None or len(snapshot_result.errors) == 0)):
                        is_inconsistent = True
                        snapshot_result.errors.append(thaw_result.errors)
                        return snapshot_result, blob_snapshot_info_array, all_failed, exceptOccurred, is_inconsistent, thaw_done_local, unable_to_sleep, all_snapshots_failed
                self.logger.log('end of snapshot process')
                logging = [global_logger.get() for job in mp_jobs]
                self.logger.log(str(logging))
                error_logging = [global_error_logger.get() for job in mp_jobs]
                self.logger.log(str(error_logging),False,'Error')
                if not snapshot_result_error.empty():
                    results = [snapshot_result_error.get() for job in mp_jobs]
                    for result in results:
                        if(result.errorcode != CommonVariables.success):
                            snapshot_result.errors.append(result)
                if not snapshot_info_indexer_queue.empty():
                    snapshot_info_indexers = [snapshot_info_indexer_queue.get() for job in mp_jobs]
                    for snapshot_info_indexer in snapshot_info_indexers:
                        # update blob_snapshot_info_array element properties from snapshot_info_indexer object
                        self.get_snapshot_info(snapshot_info_indexer, blob_snapshot_info_array[snapshot_info_indexer.index])
                        if (blob_snapshot_info_array[snapshot_info_indexer.index].isSuccessful == True):
                            all_failed = False
                        self.logger.log("index: " + str(snapshot_info_indexer.index) + " blobSnapshotUri: " + str(blob_snapshot_info_array[snapshot_info_indexer.index].snapshotUri))

                    all_snapshots_failed = all_failed
                    self.logger.log("Setting all_snapshots_failed to " + str(all_snapshots_failed))

                return snapshot_result, blob_snapshot_info_array, all_failed, exceptOccurred, is_inconsistent, thaw_done_local, unable_to_sleep, all_snapshots_failed
            else:
                self.logger.log("the blobs are None")
                return snapshot_result, blob_snapshot_info_array, all_failed, exceptOccurred, is_inconsistent, thaw_done_local, unable_to_sleep
        except Exception as e:
            errorMsg = " Unable to perform parallel snapshot with error: %s, stack trace: %s" % (str(e), traceback.format_exc())
            self.logger.log(errorMsg)
            exceptOccurred = True
            return snapshot_result, blob_snapshot_info_array, all_failed, exceptOccurred, is_inconsistent, thaw_done_local, unable_to_sleep, all_snapshots_failed


    def snapshotall_seq(self, paras, freezer, thaw_done, g_fsfreeze_on):
        exceptOccurred = False
        self.logger.log("doing snapshotall now in sequence...")
        snapshot_result = SnapshotResult()
        blob_snapshot_info_array = []
        all_failed = True
        is_inconsistent = False
        thaw_done_local = thaw_done
        unable_to_sleep = False
        all_snapshots_failed = False
        try:
            blobs = paras.blobs
            if blobs is not None:
                blob_index = 0
                for blob in blobs:
                    blobUri = blob.split("?")[0]
                    self.logger.log("index: " + str(blob_index) + " blobUri: " + str(blobUri))
                    blob_snapshot_info_array.append(HostSnapshotObjects.BlobSnapshotInfo(False, blobUri, None, 500))
                    snapshotError, snapshot_info_indexer = self.snapshot_seq(blob, blob_index, paras.backup_metadata)
                    if(snapshotError.errorcode != CommonVariables.success):
                        snapshot_result.errors.append(snapshotError)
                    # update blob_snapshot_info_array element properties from snapshot_info_indexer object
                    self.get_snapshot_info(snapshot_info_indexer, blob_snapshot_info_array[blob_index])
                    if (blob_snapshot_info_array[blob_index].isSuccessful == True):
                        all_failed = False
                    blob_index = blob_index + 1

                all_snapshots_failed = all_failed
                self.logger.log("Setting all_snapshots_failed to " + str(all_snapshots_failed))

                thaw_result= None
                if g_fsfreeze_on and thaw_done_local== False:
                    time_before_thaw = datetime.datetime.now()
                    thaw_result, unable_to_sleep = freezer.thaw_safe()
                    time_after_thaw = datetime.datetime.now()
                    HandlerUtil.HandlerUtility.add_to_telemetery_data("ThawTime", str(time_after_thaw-time_before_thaw))
                    thaw_done_local = True
                    self.logger.log('T:S thaw result ' + str(thaw_result))
                    if(thaw_result is not None and len(thaw_result.errors) > 0 and (snapshot_result is None or len(snapshot_result.errors) == 0)):
                        snapshot_result.errors.append(thaw_result.errors)
                        is_inconsistent= True
                return snapshot_result, blob_snapshot_info_array, all_failed, exceptOccurred, is_inconsistent, thaw_done_local, unable_to_sleep, all_snapshots_failed
            else:
                self.logger.log("the blobs are None")
                return snapshot_result, blob_snapshot_info_array, all_failed, exceptOccurred, is_inconsistent, thaw_done_local, unable_to_sleep
        except Exception as e:
            errorMsg = " Unable to perform sequential snapshot with error: %s, stack trace: %s" % (str(e), traceback.format_exc())
            self.logger.log(errorMsg)
            exceptOccurred = True
            return snapshot_result, blob_snapshot_info_array, all_failed, exceptOccurred, is_inconsistent, thaw_done_local, unable_to_sleep, all_snapshots_failed

    def get_value_from_configfile(self, key):
        value = None
        configfile = '/etc/azure/vmbackup.conf'
        try :
            if os.path.exists(configfile):
                config = ConfigParsers.ConfigParser()
                config.read(configfile)
                if config.has_option('SnapshotThread',key):
                    value = config.get('SnapshotThread',key)
                else:
                    self.logger.log("Config File doesn't have the key :" + key)
        except Exception as e:
            errorMsg = " Unable to ed config file.key is "+ key +"with error: %s, stack trace: %s" % (str(e), traceback.format_exc())
            self.logger.log(errorMsg)
        return value

    def snapshotall(self, paras, freezer, g_fsfreeze_on):
        thaw_done = False
        if (self.get_value_from_configfile('seqsnapshot') == '1' or self.get_value_from_configfile('seqsnapshot') == '2' or (len(paras.blobs) <= 4)):
            snapshot_result, blob_snapshot_info_array, all_failed, exceptOccurred, is_inconsistent, thaw_done, unable_to_sleep, all_snapshots_failed =  self.snapshotall_seq(paras, freezer, thaw_done, g_fsfreeze_on)
        else:
            snapshot_result, blob_snapshot_info_array, all_failed, exceptOccurred, is_inconsistent, thaw_done, unable_to_sleep, all_snapshots_failed =  self.snapshotall_parallel(paras, freezer, thaw_done, g_fsfreeze_on)
            self.logger.log("exceptOccurred : " + str(exceptOccurred) + " thaw_done : " + str(thaw_done) + " all_snapshots_failed : " + str(all_snapshots_failed))
            if exceptOccurred and thaw_done == False and all_snapshots_failed:
                self.logger.log("Trying sequential snapshotting as parallel snapshotting failed")
                snapshot_result, blob_snapshot_info_array, all_failed, exceptOccurred, is_inconsistent,thaw_done, unable_to_sleep, all_snapshots_failed =  self.snapshotall_seq(paras, freezer, thaw_done, g_fsfreeze_on)
        return snapshot_result, blob_snapshot_info_array, all_failed, is_inconsistent, unable_to_sleep, all_snapshots_failed

    def httpresponse_get_snapshot_info(self, resp, sasuri_index, sasuri, responseBody):
        snapshot_error = SnapshotError()
        snapshot_info_indexer = SnapshotInfoIndexerObj(sasuri_index, False, None, None)
        result = CommonVariables.error_http_failure
        message = ""
        if(resp != None):
            message = message + str(datetime.datetime.now()) + " snapshot resp status: " + str(resp.status) + " "
            resp_headers = resp.getheaders()
            message = message + str(datetime.datetime.now()) + " snapshot resp-header: " + str(resp_headers) + " "

            if(resp.status == 200 or resp.status == 201):
                result = CommonVariables.success
                snapshot_info_indexer.isSuccessful = True
                snapshot_info_indexer.snapshotTs = resp.getheader('x-ms-snapshot')
            else:
                result = resp.status
            snapshot_info_indexer.errorMessage = responseBody
            snapshot_info_indexer.statusCode = resp.status
        else:
            message = message + str(datetime.datetime.now()) + " snapshot Http connection response is None" + " "

        message = message + str(datetime.datetime.now()) + ' snapshot api returned: {0} '.format(result) + " "
        if(result != CommonVariables.success):
            snapshot_error.errorcode = result
            snapshot_error.sasuri = sasuri

        return snapshot_info_indexer, snapshot_error, message

    def get_snapshot_info(self, snapshot_info_indexer, snapshot_info):
        if (snapshot_info_indexer != None):
            self.logger.log("snapshot_info_indexer: " + str(snapshot_info_indexer))
            snapshot_info.isSuccessful = snapshot_info_indexer.isSuccessful
            if (snapshot_info.isSuccessful == True):
                snapshot_info.snapshotUri = snapshot_info.snapshotUri + "?snapshot=" + str(snapshot_info_indexer.snapshotTs)
            else:
                snapshot_info.snapshotUri = None
            snapshot_info.errorMessage = snapshot_info_indexer.errorMessage
            snapshot_info.statusCode = snapshot_info_indexer.statusCode
        else:
            snapshot_info.isSuccessful = False
            snapshot_info.snapshotUri = None
