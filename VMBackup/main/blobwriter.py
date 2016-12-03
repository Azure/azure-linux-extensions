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

    def WritePageBlob(self, msg, blobUri):
        if(blobUri is not None):
            retry_times = 3
            while(retry_times > 0):
                try:
                    PAGE_SIZE_BYTES = 512
                    PAGE_UPLOAD_LIMIT_BYTES = 4194304 # 4 MB
                    http_util = HttpUtil(self.hutil)
                    sasuri_obj = urlparse.urlparse(blobUri + '&comp=page')
                    # Get Blob-properties to know content-length
                    blobProperties = self.GetBlobProperties(blobUri)
                    blobContentLength = int(blobProperties.contentLength)
                    #self.hutil.log("WritePageBlob contentLength:"+str(blobContentLength))
                    # Add padding to message to make its legth multiple of 512
                    msgLen = len(msg)
                    self.hutil.log("msg length:"+str(msgLen))
                    if(msgLen > blobContentLength):
                        msg = msg[msgLen-blobContentLength:msgLen]
                    elif((msgLen % PAGE_SIZE_BYTES) != 0):
                        paddedLen = msgLen + (512 - (msgLen % PAGE_SIZE_BYTES))
                        msg = msg.ljust(paddedLen)
                    msgLen = len(msg)
                    self.hutil.log("msg length after aligning:"+str(len(msg)))
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
                        self.hutil.log("pageContentLen:"+str(len(pageContent)))
                        result = self.put_page_update(pageContent, blobUri, bytes_sent)
                        if(result == CommonVariables.success):
                            self.hutil.log("page written succesfully")
                        else:
                            self.hutil.log("page failed to write")
                            break
                        bytes_sent = bytes_sent + len(pageContent)                      
                    if(result == CommonVariables.success):
                        self.hutil.log("page-blob written succesfully")
                        retry_times = 0
                    else:
                        self.hutil.log("page-blob failed to write")
                except Exception as e:
                    self.hutil.log("Failed to write to page-blob with error: %s, stack trace: %s" % (str(e), traceback.format_exc()))
                self.hutil.log("retry times is " + str(retry_times))
                retry_times = retry_times - 1
        else:
            self.hutil.log("bloburi is None")

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
                    #self.hutil.log("ClearPageBlob contentLength:"+str(contentLength))
                    # Clear Pages
                    if(contentLength > 0):
                        result = self.put_page_clear(blobUri, 0, contentLength)
                        if(result == CommonVariables.success):
                            self.hutil.log("page-blob cleared succesfully")
                            retry_times = 0
                        else:
                            self.hutil.log("page-blob failed to clear")
                    else:
                        retry_times = 0
                except Exception as e:
                    self.hutil.log("Failed to clear to page-blob with error: %s, stack trace: %s" % (str(e), traceback.format_exc()))
                self.hutil.log("retry times is " + str(retry_times))
                retry_times = retry_times - 1
        else:
            self.hutil.log("bloburi is None")

    def GetBlobType(self, blobUri):
        blobType = "BlockBlob"
        if(blobUri is not None):
            # Get Blob Properties
            blobProperties = self.GetBlobProperties(blobUri)
            if(blobProperties is not None):
                blobType = blobProperties.blobType
        self.hutil.log("Blob-Type :"+str(blobType))
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
                    httpResp = http_util.HttpCallGetResponse('GET', sasuri_obj, None, headers = headers)
                    blobProperties = self.httpresponse_get_blob_properties(httpResp)
                    self.hutil.log("blobProperties :" + str(blobProperties))
                    retry_times = 0
                except Exception as e:
                    self.hutil.log("Failed to get blob properties with error: %s, stack trace: %s" % (str(e), traceback.format_exc()))
                    self.hutil.log("retry times is " + str(retry_times))
                    retry_times = retry_times - 1
        return blobProperties

    def put_page_clear(self, blobUri, pageBlobIndex, clearLength):
         http_util = HttpUtil(self.hutil)
         sasuri_obj = urlparse.urlparse(blobUri + '&comp=page')
         headers = {}
         headers["x-ms-page-write"] = 'clear'
         headers["x-ms-range"] = 'bytes={}-{}'.format(pageBlobIndex, pageBlobIndex + clearLength - 1)
         headers["Content-Length"] = 0
         #self.hutil.log(str(headers))
         result = http_util.Call(method = 'PUT', sasuri_obj = sasuri_obj, data = None, headers = headers, fallback_to_curl = False)
         return result

    def put_page_update(self, pageContent, blobUri, pageBlobIndex):
         http_util = HttpUtil(self.hutil)
         sasuri_obj = urlparse.urlparse(blobUri + '&comp=page')
         headers = {}
         headers["x-ms-page-write"] = 'update'
         headers["x-ms-range"] = 'bytes={}-{}'.format(pageBlobIndex, pageBlobIndex + len(pageContent) - 1)
         headers["Content-Length"] = len(str(pageContent))
         #self.hutil.log(str(headers))
         result = http_util.Call(method = 'PUT', sasuri_obj = sasuri_obj, data = pageContent, headers = headers, fallback_to_curl = False)
         return result

    def httpresponse_get_blob_properties(self, httpResp):
        blobProperties = None
        if(httpResp != None):
            self.hutil.log("Blob-properties response status:"+str(httpResp.status))
            if(httpResp.status == 200):
                resp_headers = httpResp.getheaders()
                #self.hutil.log("Blob-properties resp_headers:"+str(resp_headers))
                blobType = httpResp.getheader('x-ms-blob-type')
                contentLength = httpResp.getheader('Content-Length')
                blobProperties = BlobProperties(blobType, contentLength)
        return blobProperties

