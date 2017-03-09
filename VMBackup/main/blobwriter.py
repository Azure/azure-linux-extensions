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
from common import CommonVariables
from HttpUtil import HttpUtil

class BlobProperties():
    def __init__(self, blobType, contentLength):
        self.blobType = blobType
        self.contentLength = contentLength
    def __str__(self):
        return ' blobType: ' + str(self.blobType) + ' contentLength: ' + str(self.contentLength)

class BlobWriter(object):
    """description of class"""
    def __init__(self, hutil):
        self.hutil = hutil
    """
    network call should have retry.
    """
    def WriteBlob(self,msg,blobUri):
        try:
            # get the blob type
            if(blobUri is not None):
                blobType = self.GetBlobType(blobUri)
                if (str(blobType).lower() == "pageblob"):
                    # Clear Page-Blob Contents
                    self.ClearPageBlob(blobUri)
                    # Write to Page-Blob
                    self.WritePageBlob(msg, blobUri)
                else:
                    self.WriteBlockBlob(msg, blobUri)
            else:
                self.hutil.log("bloburi is None")
        except Exception as e:
            self.hutil.log("Failed to committing the log with error: %s, stack trace: %s" % (str(e), traceback.format_exc()))

    def WriteBlockBlob(self,msg,blobUri):
        retry_times = 3
        while(retry_times > 0):
            try:
                # get the blob type
                if(blobUri is not None):
                    http_util = HttpUtil(self.hutil)
                    sasuri_obj = urlparse.urlparse(blobUri)
                    headers = {}
                    headers["x-ms-blob-type"] = 'BlockBlob'
                    self.hutil.log(str(headers))
                    result = http_util.Call(method = 'PUT', sasuri_obj = sasuri_obj, data = msg, headers = headers, fallback_to_curl = True)
                    if(result == CommonVariables.success):
                        self.hutil.log("blob written succesfully")
                        retry_times = 0
                    else:
                        self.hutil.log("blob failed to write")
                else:
                    self.hutil.log("bloburi is None")
                    retry_times = 0
            except Exception as e:
                self.hutil.log("Failed to committing the log with error: %s, stack trace: %s" % (str(e), traceback.format_exc()))
            self.hutil.log("retry times is " + str(retry_times))
            retry_times = retry_times - 1

    def WritePageBlob(self, message, blobUri):
        if(blobUri is not None):
            retry_times = 3
            while(retry_times > 0):
                msg = message
                try:
                    PAGE_SIZE_BYTES = 512
                    PAGE_UPLOAD_LIMIT_BYTES = 4194304 # 4 MB
                    STATUS_BLOB_LIMIT_BYTES = 10485760 # 10 MB
                    http_util = HttpUtil(self.hutil)
                    sasuri_obj = urlparse.urlparse(blobUri + '&comp=page')
                    # Get Blob-properties to know content-length
                    blobProperties = self.GetBlobProperties(blobUri)
                    blobContentLength = int(blobProperties.contentLength)
                    self.hutil.log("WritePageBlob: contentLength:"+str(blobContentLength))
                    maxMsgLen = STATUS_BLOB_LIMIT_BYTES
                    if (blobContentLength > STATUS_BLOB_LIMIT_BYTES):
                        maxMsgLen = blobContentLength
                    msgLen = len(msg)
                    self.hutil.log("WritePageBlob: msg length:"+str(msgLen))
                    if(len(msg) > maxMsgLen):
                        msg = msg[msgLen-maxMsgLen:msgLen]
                        msgLen = len(msg)
                        self.hutil.log("WritePageBlob: msg length after aligning to maxMsgLen:"+str(msgLen))
                    if((msgLen % PAGE_SIZE_BYTES) != 0):
                        # Add padding to message to make its legth multiple of 512
                        paddedLen = msgLen + (512 - (msgLen % PAGE_SIZE_BYTES))
                        msg = msg.ljust(paddedLen)
                        msgLen = len(msg)
                        self.hutil.log("WritePageBlob: msg length after aligning to page-size(512):"+str(msgLen))
                    if(blobContentLength < msgLen):
                        # Try to resize blob to increase its size
                        isSuccessful = self.try_resize_page_blob(blobUri, msgLen)
                        if(isSuccessful == True):
                            self.hutil.log("WritePageBlob: page-blob resized successfully new size(blobContentLength):"+str(msgLen))
                            blobContentLength = msgLen
                        else:
                            self.hutil.log("WritePageBlob: page-blob resize failed")
                    if(msgLen > blobContentLength):
                        msg = msg[msgLen-blobContentLength:msgLen]
                        msgLen = len(msg)
                        self.hutil.log("WritePageBlob: msg length after aligning to blobContentLength:"+str(msgLen))
                    # Write Pages
                    result = CommonVariables.error
                    bytes_sent = 0
                    while (bytes_sent < msgLen):
                        bytes_remaining = msgLen - bytes_sent
                        pageContent = None
                        if(bytes_remaining > PAGE_UPLOAD_LIMIT_BYTES): # more than 4 MB
                            pageContent = msg[bytes_sent:bytes_sent+PAGE_UPLOAD_LIMIT_BYTES]
                        else:
                            pageContent = msg[bytes_sent:msgLen]
                        self.hutil.log("WritePageBlob: pageContentLen:"+str(len(pageContent)))
                        result = self.put_page_update(pageContent, blobUri, bytes_sent)
                        if(result == CommonVariables.success):
                            self.hutil.log("WritePageBlob: page written succesfully")
                        else:
                            self.hutil.log("WritePageBlob: page failed to write")
                            break
                        bytes_sent = bytes_sent + len(pageContent)                      
                    if(result == CommonVariables.success):
                        self.hutil.log("WritePageBlob: page-blob written succesfully")
                        retry_times = 0
                    else:
                        self.hutil.log("WritePageBlob: page-blob failed to write")
                except Exception as e:
                    self.hutil.log("WritePageBlob: Failed to write to page-blob with error: %s, stack trace: %s" % (str(e), traceback.format_exc()))
                self.hutil.log("WritePageBlob: retry times is " + str(retry_times))
                retry_times = retry_times - 1
        else:
            self.hutil.log("WritePageBlob: bloburi is None")

    def ClearPageBlob(self, blobUri):
        if(blobUri is not None):
            retry_times = 3
            while(retry_times > 0):
                try:
                    http_util = HttpUtil(self.hutil)
                    sasuri_obj = urlparse.urlparse(blobUri + '&comp=page')
                    # Get Blob-properties to know content-length
                    blobProperties = self.GetBlobProperties(blobUri)
                    contentLength = int(blobProperties.contentLength)
                    # Clear Pages
                    if(contentLength > 0):
                        result = self.put_page_clear(blobUri, 0, contentLength)
                        if(result == CommonVariables.success):
                            self.hutil.log("ClearPageBlob: page-blob cleared succesfully")
                            retry_times = 0
                        else:
                            self.hutil.log("ClearPageBlob: page-blob failed to clear")
                    else:
                        self.hutil.log("ClearPageBlob: page-blob contentLength is 0")
                        retry_times = 0
                except Exception as e:
                    self.hutil.log("ClearPageBlob: Failed to clear to page-blob with error: %s, stack trace: %s" % (str(e), traceback.format_exc()))
                self.hutil.log("ClearPageBlob: retry times is " + str(retry_times))
                retry_times = retry_times - 1
        else:
            self.hutil.log("ClearPageBlob: bloburi is None")

    def GetBlobType(self, blobUri):
        blobType = "BlockBlob"
        if(blobUri is not None):
            # Get Blob Properties
            blobProperties = self.GetBlobProperties(blobUri)
            if(blobProperties is not None):
                blobType = blobProperties.blobType
        self.hutil.log("GetBlobType: Blob-Type :"+str(blobType))
        return blobType

    def GetBlobProperties(self, blobUri):
        blobProperties = None
        if(blobUri is not None):
            retry_times = 3
            while(retry_times > 0):
                try:
                    http_util = HttpUtil(self.hutil)
                    sasuri_obj = urlparse.urlparse(blobUri)
                    headers = {}
                    result, httpResp, errMsg = http_util.HttpCallGetResponse('GET', sasuri_obj, None, headers = headers)
                    self.hutil.log("GetBlobProperties: HttpCallGetResponse : result :" + str(result) + ", errMsg :" + str(errMsg))
                    blobProperties = self.httpresponse_get_blob_properties(httpResp)
                    self.hutil.log("GetBlobProperties: blobProperties :" + str(blobProperties))
                    retry_times = 0
                except Exception as e:
                    self.hutil.log("GetBlobProperties: Failed to get blob properties with error: %s, stack trace: %s" % (str(e), traceback.format_exc()))
                    self.hutil.log("GetBlobProperties: retry times is " + str(retry_times))
                    retry_times = retry_times - 1
        return blobProperties

    def put_page_clear(self, blobUri, pageBlobIndex, clearLength):
        http_util = HttpUtil(self.hutil)
        sasuri_obj = urlparse.urlparse(blobUri + '&comp=page')
        headers = {}
        headers["x-ms-page-write"] = 'clear'
        headers["x-ms-range"] = 'bytes={0}-{1}'.format(pageBlobIndex, pageBlobIndex + clearLength - 1)
        headers["Content-Length"] = 0
        result = http_util.Call(method = 'PUT', sasuri_obj = sasuri_obj, data = None, headers = headers, fallback_to_curl = True)
        return result

    def put_page_update(self, pageContent, blobUri, pageBlobIndex):
        http_util = HttpUtil(self.hutil)
        sasuri_obj = urlparse.urlparse(blobUri + '&comp=page')
        headers = {}
        headers["x-ms-page-write"] = 'update'
        headers["x-ms-range"] = 'bytes={0}-{1}'.format(pageBlobIndex, pageBlobIndex + len(pageContent) - 1)
        headers["Content-Length"] = len(str(pageContent))
        result = http_util.Call(method = 'PUT', sasuri_obj = sasuri_obj, data = pageContent, headers = headers, fallback_to_curl = True)
        return result
    
    def try_resize_page_blob(self, blobUri, size):
        isSuccessful = False
        if (size % 512 == 0):
            try:
                http_util = HttpUtil(self.hutil)
                sasuri_obj = urlparse.urlparse(blobUri + '&comp=properties')
                headers = {}
                headers["x-ms-blob-content-length"] = size
                headers["Content-Length"] = size
                result = http_util.Call(method = 'PUT', sasuri_obj = sasuri_obj, data = None, headers = headers, fallback_to_curl = True)
                if(result == CommonVariables.success):
                    isSuccessful = True
                else:
                    self.hutil.log("try_resize_page_blob: page-blob resize failed, size :"+str(size)+", result :"+str(result))
            except Exception as e:
                self.hutil.log("try_resize_page_blob: failed to resize page-blob with error: %s, stack trace: %s" % (str(e), traceback.format_exc()))
        else:
            self.hutil.log("try_resize_page_blob: invalid size : " + str(size))
        return isSuccessful

    def httpresponse_get_blob_properties(self, httpResp):
        blobProperties = None
        if(httpResp != None):
            self.hutil.log("httpresponse_get_blob_properties: Blob-properties response status:"+str(httpResp.status))
            if(httpResp.status == 200):
                resp_headers = httpResp.getheaders()
                blobType = httpResp.getheader('x-ms-blob-type')
                contentLength = httpResp.getheader('Content-Length')
                blobProperties = BlobProperties(blobType, contentLength)
        return blobProperties

