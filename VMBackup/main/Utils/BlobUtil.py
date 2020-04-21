#!/usr/bin/env python
#
# VMEncryption extension
#
# Copyright 2015 Microsoft Corporation
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
import json
from HttpUtil import HttpUtil
from Utils import HandlerUtil
import ExtensionErrorCodeHelper
import sys

class BlobUtil(object):
    def __init__(self, logger):
        self.logger = logger

    # retreives the blob metadata through rest call to <blobUri>&comp=metadata
    def GetBlobMetadata(self, blobUri):
        blobProperties = None
        if(blobUri is not None):     
            try:
                http_util = HttpUtil(self.logger)
                sasuri_obj = urlparser.urlparse(blobUri+ '&comp=metadata')
                headers = {}

                result, httpResp, errMsg = http_util.HttpCallGetResponse('GET', sasuri_obj, None, headers = headers)
                self.logger.log("FS : GetBlobMetadata: HttpCallGetResponse : result :" + str(result) + ", errMsg :" + str(errMsg))
                blobProperties = self.httpresponse_parse_metadata(httpResp)
            except Exception as e:
                self.logger.log("FS : GetBlobMetadata: Failed to get blob properties with error: %s, stack trace: %s" % (str(e), traceback.format_exc()))
        return blobProperties

    def GetHeaderSize(self, headers):
    # max size of blob metadata 
            return sys.getsizeof(json.dumps(headers))


    def httpresponse_parse_metadata(self, httpResp):
        blobMetadata = {}
        if(httpResp != None):
            self.hutil.log("httpresponse_get_blob_properties: Blob-properties response status:"+str(httpResp.status))
            if(httpResp.status == 200):
                resp_headers = httpResp.getheaders()
                blobMetadata = resp_headers
        return blobMetadata

    def populate_blobMetadata_perblob(self, sasuri, sasuri_index, backup_meta_data, blobMetadataTelemetryMessage):
        blobMetadataDict= {}
        blobMetadataDict["Content-Length"] = '0'

        blobMetdataMaxSizeBytes = CommonVariables.blobMetdataMaxSizeBytes

        original_blob_metadata = self.GetBlobMetadata(sasuri)
        
        if(original_blob_metadata is not None): 
            for meta in original_blob_metadata:
                Key,Value = meta
                blobMetadataDict[Key] = Value

        if(backup_meta_data is not None):
            for meta in backup_meta_data:
                key = meta['Key']
                value = meta['Value']
                blobMetadataDict["x-ms-meta-" + key] = value
        
        level1BlobMetadataSize = self.GetHeaderSize(headers)
        
        if level1BlobMetadataSize > blobMetdataMaxSizeBytes:
            if sasuri_index not in blobMetadataTelemetryMessage :
                blobMetadataTelemetryMessage[sasuri_index] = ""

            blobMetadataTelemetryMessage[sasuri_index]+= str(level1BlobMetadataSize) + ", ";

            blobMetadataDict = {}
            blobMetadataDict["Content-Length"] = '0'
            if(original_blob_metadata is not None): 
                for meta in original_blob_metadata:
                    Key,Value = meta
                    if Key == "x-ms-meta-diskencryptionsettings" :
                        blobMetadataDict[Key] = Value
                        break

            if(backup_meta_data is not None):
                for meta in backup_meta_data:
                    key = meta['Key']
                    value = meta['Value']
                    blobMetadataDict["x-ms-meta-" + key] = value

            level2BlobMetadataSize = self.GetHeaderSize(headers)
            
            if level2BlobMetadataSize > blobMetdataMaxSizeBytes :
                blobMetadataTelemetryMessage[sasuri_index]+= str(level2BlobMetadataSize) + ", ";

                blobMetadataDict = {}
                blobMetadataDict["Content-Length"] = '0'
                if(backup_meta_data is not None):
                    for meta in backup_meta_data:
                        key = meta['Key']
                        value = meta['Value']
                        blobMetadataDict["x-ms-meta-" + key] = value
                
        return blobMetadataDict


    def populate_blobMetadata_allblobs(self, paras):
        #Dict <DiskIndex, Disk Metadata Size>
        blob_metadata = {}
        
        #Dict <DiskIndex where Size exceeded threshold, size at various levels>
        blobMetadataTelemetryMessage = {}

        try:
            blobs = paras.blobs
            if blobs is not None:
                blob_index = 0
                self.logger.log('****** Starting metadata retrieval for all blobs')
                
                for blob in blobs:
                    blobUri = blob.split("?")[0]
                    self.logger.log("index: " + str(blob_index) + " blobUri: " + str(blobUri))
                    blob_metadata[blob_index] = self.populate_snapshotreq_headers_perblob(blob,blob_index,paras.backup_metadata, blobMetadataTelemetryMessage)
                    self.logger.log("Metadata retreived : " + str(blob_metadata[blob_index]))

                    # log if the metadata size was found to be greater than the max limit allowed
                    if blobMetadataTelemetryMessage is not None and len(blobMetadataTelemetryMessage) > 0 and blob_index in blobMetadataTelemetryMessage :
                        self.logger.log("Metadata was found to be greater than the max limit. The metadata size was : " + blobMetadataTelemetryMessage[blob_index])
                    
                    blob_index = blob_index + 1

        except Exception as e:
            errorMsg = " Unable to retreive metadata for blobs : %s, stack trace: %s" % (str(e), traceback.format_exc())
            self.logger.log(errorMsg)

        if blobMetadataTelemetryMessage is not None and len(blobMetadataTelemetryMessage) > 0:
                HandlerUtil.HandlerUtility.add_to_telemetery_data("MetadataSizeExceedBlobCount", str(len(blobMetadataTelemetryMessage)))

        return blob_metadata
