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
import urlparse
import httplib
import traceback
import datetime
import ConfigParser
import multiprocessing as mp
from common import CommonVariables
from HttpUtil import HttpUtil
from Utils import Status

class SnapshotInfoIndexerObj():
    def __init__(self, index, isSuccessful, snapshotTs, errorMessage):
        self.index = index
        self.isSuccessful = isSuccessful
        self.snapshotTs = snapshotTs
        self.errorMessage = errorMessage
    def __str__(self):
        return 'index: ' + str(self.index) + ' isSuccessful: ' + str(self.isSuccessful) + ' snapshotTs: ' + str(self.snapshotTs) + ' errorMessage: ' + str(self.errorMessage)

class SnapshotError(object):
    def __init__(self):
        self.errorcode = CommonVariables.success
        self.sasuri = None
    def __str__(self):
        return 'errorcode: ' + str(self.errorcode) + ' sasuri: ' + str(self.sasuri)

class SnapshotResult(object):
    def __init__(self):
        self.errors = []

    def __str__(self):
        error_str = ""
        for error in self.errors:
            error_str+=(str(error)) + "\n"
        return error_str

class Snapshotter(object):
    """description of class"""
    def __init__(self, logger):
        self.logger = logger
        self.configfile='/etc/azure/vmbackup.conf'

    def snapshot(self, sasuri, sasuri_index, meta_data, snapshot_result_error, snapshot_info_indexer_queue, global_logger, global_error_logger):
        temp_logger=''
        error_logger=''
        snapshot_error = SnapshotError()
        snapshot_info_indexer = SnapshotInfoIndexerObj(sasuri_index, False, None, None)
        if(sasuri is None):
            error_logger = error_logger + " Failed to do the snapshot because sasuri is none "
            snapshot_error.errorcode = CommonVariables.error
            snapshot_error.sasuri = sasuri
        try:
            sasuri_obj = urlparse.urlparse(sasuri)
            if(sasuri_obj is None or sasuri_obj.hostname is None):
                error_logger = error_logger + " Failed to parse the sasuri "
                snapshot_error.errorcode = CommonVariables.error
                snapshot_error.sasuri = sasuri
            else:
                start_time = datetime.datetime.utcnow()
                body_content = ''
                headers = {}
                headers["Content-Length"] = '0'
                for meta in meta_data:
                    key = meta['Key']
                    value = meta['Value']
                    headers["x-ms-meta-" + key] = value
                temp_logger = temp_logger + str(headers)
                http_util = HttpUtil(self.logger)
                sasuri_obj = urlparse.urlparse(sasuri + '&comp=snapshot')
                temp_logger = temp_logger + 'start calling the snapshot rest api. '
                # initiate http call for blob-snapshot and get http response
                resp = http_util.HttpCallGetResponse('PUT', sasuri_obj, body_content, headers = headers)
                # retrieve snapshot infor from http response
                snapshot_info_indexer, snapshot_error, message = self.httpresponse_get_snapshot_info(resp, sasuri_index, sasuri)
                temp_logger = temp_logger + ' handle_snapshot_http_response message: ' + str(message)
                
                end_time = datetime.datetime.utcnow()
                time_taken=end_time-start_time
                temp_logger = temp_logger + ' time taken for snapshot ' + str(time_taken)
        except Exception as e:
            errorMsg = " Failed to do the snapshot with error: %s, stack trace: %s" % (str(e), traceback.format_exc())
            error_logger = error_logger + errorMsg
            snapshot_error.errorcode = CommonVariables.error
            snapshot_error.sasuri = sasuri
        temp_logger=temp_logger + ' snapshot ends..'
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
            sasuri_obj = urlparse.urlparse(sasuri)
            if(sasuri_obj is None or sasuri_obj.hostname is None):
                self.logger.log("Failed to parse the sasuri",False,'Error')
                snapshot_error.errorcode = CommonVariables.error
                snapshot_error.sasuri = sasuri
            else:
                body_content = ''
                headers = {}
                headers["Content-Length"] = '0'
                for meta in meta_data:
                    key = meta['Key']
                    value = meta['Value']
                    headers["x-ms-meta-" + key] = value
                self.logger.log(str(headers))
                http_util = HttpUtil(self.logger)
                sasuri_obj = urlparse.urlparse(sasuri + '&comp=snapshot')
                self.logger.log("start calling the snapshot rest api")
                # initiate http call for blob-snapshot and get http response
                resp = http_util.HttpCallGetResponse('PUT', sasuri_obj, body_content, headers = headers)
                # retrieve snapshot infor from http response
                snapshot_info_indexer, snapshot_error, message = self.httpresponse_get_snapshot_info(resp, sasuri_index, sasuri)
                self.logger.log("get_snapshot_info: " + str(message))
        except Exception as e:
            errorMsg = "Failed to do the snapshot with error: %s, stack trace: %s" % (str(e), traceback.format_exc())
            self.logger.log(errorMsg, False, 'Error')
            snapshot_error.errorcode = CommonVariables.error
            snapshot_error.sasuri = sasuri
        return snapshot_error, snapshot_info_indexer

    def snapshotall_parallel(self, paras):
        self.logger.log("doing snapshotall now in parallel...")
        snapshot_result = SnapshotResult()
        snapshot_info_array = []
        all_failed = True
        mp_jobs = []
        global_logger = mp.Queue()
        global_error_logger = mp.Queue()
        snapshot_result_error = mp.Queue()
        snapshot_info_indexer_queue = mp.Queue()
        is_inconsistent = False
        time_before_snapshot_start = datetime.datetime.now()
        blobs = paras.blobs
        if blobs is not None:
            # initialize snapshot_info_array
            mp_jobs = []
            blob_index = 0
            for blob in blobs:
                blobUri = blob.split("?")[0]
                self.logger.log("index: " + str(blob_index) + " blobUri: " + str(blobUri))
                snapshot_info_array.append(Status.SnapshotInfoObj(False, blobUri, None))
                mp_jobs.append(mp.Process(target=self.snapshot,args=(blob, blob_index, paras.backup_metadata, snapshot_result_error, snapshot_info_indexer_queue, global_logger, global_error_logger)))
                blob_index = blob_index + 1

            for job in mp_jobs:
                job.start()

            time_after_snapshot_start = datetime.datetime.now()
            timeout = self.get_value_from_configfile('timeout')
            if timeout == None:
                timeout = 60

            if datetime.timedelta.total_seconds(time_after_snapshot_start - time_before_snapshot_start) > int(timeout):
                is_inconsistent = True

            for job in mp_jobs:
                job.join()
            self.logger.log('end of snapshot process')
            logging = [global_logger.get() for job in mp_jobs]
            self.logger.log(str(logging))
            error_logging = [global_error_logger.get() for job in mp_jobs]
            self.logger.log(error_logging,False,'Error')
            if not snapshot_result_error.empty():
                results = [snapshot_result_error.get() for job in mp_jobs]
                for result in results:
                    if(result.errorcode != CommonVariables.success):
                        snapshot_result.errors.append(result)
            if not snapshot_info_indexer_queue.empty():
                snapshot_info_indexers = [snapshot_info_indexer_queue.get() for job in mp_jobs]
                for snapshot_info_indexer in snapshot_info_indexers:
                    # update snapshot_info_array element properties from snapshot_info_indexer object
                    self.get_snapshot_info(snapshot_info_indexer, snapshot_info_array[snapshot_info_indexer.index])
                    if (snapshot_info_array[snapshot_info_indexer.index].isSuccessful == True):
                        all_failed = False
                    self.logger.log("index: " + str(snapshot_info_indexer.index) + " blobSnapshotUri: " + str(snapshot_info_array[snapshot_info_indexer.index].snapshotUri))

            return snapshot_result, snapshot_info_array, all_failed, is_inconsistent
        else:
            self.logger.log("the blobs are None")
            return snapshot_result, snapshot_info_array, all_failed, is_inconsistent

    def snapshotall_seq(self, paras):
        self.logger.log("doing snapshotall now in sequence...")
        snapshot_result = SnapshotResult()
        snapshot_info_array = []
        all_failed = True
        is_inconsistent = False
        blobs = paras.blobs
        if blobs is not None:
            blob_index = 0
            for blob in blobs:
                blobUri = blob.split("?")[0]
                self.logger.log("index: " + str(blob_index) + " blobUri: " + str(blobUri))
                snapshot_info_array.append(Status.SnapshotInfoObj(False, blobUri, None))
                snapshotError, snapshot_info_indexer = self.snapshot_seq(blob, blob_index, paras.backup_metadata)
                if(snapshotError.errorcode != CommonVariables.success):
                    snapshot_result.errors.append(snapshotError)
                # update snapshot_info_array element properties from snapshot_info_indexer object
                self.get_snapshot_info(snapshot_info_indexer, snapshot_info_array[blob_index])
                if (snapshot_info_array[blob_index].isSuccessful == True):
                    all_failed = False
                blob_index = blob_index + 1
            return snapshot_result, snapshot_info_array, all_failed, is_inconsistent
        else:
            self.logger.log("the blobs are None")
            return snapshot_result, snapshot_info_array, all_failed, is_inconsistent

    def get_value_from_configfile(self, key):
        value = None
        configfile = '/etc/azure/vmbackup.conf'
        try :
            if os.path.exists(configfile):
                config = ConfigParser.ConfigParser()
                config.read(configfile)
                if config.has_option('SnapshotThread',key):
                    value = config.get('SnapshotThread',key)
                else:
                    self.logger.log("Config File doesn't have the key :" + key
            return value
        except Exception as e:
            self.logger.log("Unable to read config file.key is : " + key + "with exception " + str(e))
            return value


    def snapshotall(self, paras):
        try:
            if self.get_value_from_configfile('doseq') == '1':
                snapshot_result, snapshot_info_array, all_failed, is_inconsistent =  self.snapshotall_seq(paras)
            else:
                snapshot_result, snapshot_info_array, all_failed, is_inconsistent =  self.snapshotall_parallel(paras)
            return snapshot_result, snapshot_info_array, all_failed, is_inconsistent
        except Exception as e:
            errorMsg = "Failed to do the snapshot with error: %s, stack trace: %s" % (str(e), traceback.format_exc())
            self.logger.log(errorMsg, False, 'Error')
            self.logger.log("Do sequential snapshoting")
            snapshot_result, snapshot_info_array, all_failed, is_inconsistent =  self.snapshotall_seq(paras)
            return snapshot_result, snapshot_info_array, all_failed, is_inconsistent

    def httpresponse_get_snapshot_info(self, resp, sasuri_index, sasuri):
        snapshot_error = SnapshotError()
        snapshot_info_indexer = SnapshotInfoIndexerObj(sasuri_index, False, None, None)
        result = CommonVariables.error_http_failure
        message = ""
        if(resp != None):
            resp_headers = resp.getheaders()
            message = message + "snapshot resp-header: " + str(resp_headers)
            message = message + "snapshot resp status: " + str(resp.status)
            responseBody = resp.read()
            if(responseBody is not None):
                message = message + "snapshot responseBody: " + (responseBody).decode('utf-8-sig')

            if(resp.status == 200 or resp.status == 201):
                result = CommonVariables.success
                snapshot_info_indexer.isSuccessful = True
                snapshot_info_indexer.snapshotTs = resp.getheader('x-ms-snapshot')
            else:
                result = resp.status
                snapshot_info_indexer.errorMessage = resp.status
        else:
            message = message + "snapshot Http connection response is None"

        message = message + ' snapshot api returned: {0} '.format(result)
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
        else:
            snapshot_info.isSuccessful = False
            snapshot_info.snapshotUri = None

