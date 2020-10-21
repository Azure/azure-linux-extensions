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

class CommonVariables:
    azure_path = 'main/azure'
    utils_path_name = 'Utils'
    extension_name = 'MyBackupTestLinuxInt'
    extension_version = "1.0.9120.0"
    extension_zip_version = "1"
    extension_type = extension_name
    extension_media_link = 'https://sopattna.blob.core.windows.net/extensions/' + extension_name + '-' + str(extension_version) + '.zip'
    extension_label = 'Windows Azure VMBackup Extension for Linux IaaS'
    extension_description = extension_label
    object_str = 'objectStr'
    logs_blob_uri = 'logsBlobUri'
    status_blob_uri = 'statusBlobUri'
    commandStartTimeUTCTicks = "commandStartTimeUTCTicks"
    task_id = 'taskId'
    command_to_execute = 'commandToExecute'
    iaas_vmbackup_command = 'snapshot'
    iaas_install_command = 'install'
    locale = 'locale'
    vmType = 'vmType'
    VmTypeV1 = 'microsoft.classiccompute/virtualmachines'
    VmTypeV2 = 'microsoft.compute/virtualmachines'
    customSettings = 'customSettings'
    statusBlobUploadError = 'statusBlobUploadError'

    snapshotTaskToken = 'snapshotTaskToken'
    snapshotCreator = 'snapshotCreator'
    hostStatusCodePreSnapshot = 'hostStatusCodePreSnapshot'
    hostStatusCodeDoSnapshot = 'hostStatusCodeDoSnapshot'
    guestExtension = 'guestExtension'
    backupHostService = 'backupHostService'
    includedDisks = 'includedDisks'
    isAnyDiskExcluded = 'isAnyDiskExcluded'
    dataDiskLunList = 'dataDiskLunList'
    isOSDiskIncluded = 'isOSDiskIncluded'

    onlyGuest = 'onlyGuest'
    firstGuestThenHost = 'firstGuestThenHost'
    firstHostThenGuest = 'firstHostThenGuest'
    onlyHost = 'onlyHost'

    SnapshotMethod = 'SnapshotMethod'
    IsAnySnapshotFailed = 'IsAnySnapshotFailed'
    SnapshotRateExceededFailureCount = 'SnapshotRateExceededFailureCount'

    status_transitioning = 'transitioning'
    status_warning = 'warning'
    status_success = 'success'
    status_error = 'error'

    unable_to_open_err_string= 'file open failed for some mount'

    """
    error code definitions
    """
    success_appconsistent = 0
    success = 1
    error = 2
    SuccessAlreadyProcessedInput = 3
    ExtensionTempTerminalState = 4

    error_parameter = 11
    error_12 = 12
    error_wrong_time = 13
    error_same_taskid = 14
    error_http_failure = 15
    FailedHandlerGuestAgentCertificateNotFound = 16
    #error_upload_status_blob = 16
    FailedRetryableSnapshotFailedNoNetwork = 76
    FailedSnapshotLimitReached = 85
    FailedRetryableSnapshotRateExceeded = 173
    FailedFsFreezeFailed = 121
    FailedFsFreezeTimeout = 122
    FailedUnableToOpenMount = 123

    """
    Pre-Post Plugin error code definitions
    """

    PrePost_PluginStatus_Success = 0
    PrePost_ScriptStatus_Success = 0
    PrePost_ScriptStatus_Error = 1
    PrePost_ScriptStatus_Warning = 2

    FailedPrepostPreScriptFailed = 300
    FailedPrepostPostScriptFailed = 301
    FailedPrepostPreScriptNotFound = 302
    FailedPrepostPostScriptNotFound = 303
    FailedPrepostPluginhostConfigParsing = 304
    FailedPrepostPluginConfigParsing = 305
    FailedPrepostPreScriptPermissionError = 306
    FailedPrepostPostScriptPermissionError = 307
    FailedPrepostPreScriptTimeout = 308
    FailedPrepostPostScriptTimeout = 309
    FailedPrepostPluginhostPreTimeout = 310
    FailedPrepostPluginhostPostTimeout = 311
    FailedPrepostCheckSumMismatch = 312
    FailedPrepostPluginhostConfigNotFound = 313
    FailedPrepostPluginhostConfigPermissionError = 314
    FailedPrepostPluginhostConfigOwnershipError = 315
    FailedPrepostPluginConfigNotFound = 316
    FailedPrepostPluginConfigPermissionError = 317
    FailedPrepostPluginConfigOwnershipError = 318
    FailedGuestAgentInvokedCommandTooLate = 402
    
    FailedWorkloadPreError = 500
    FailedWorkloadConfParsingError = 501
    FailedWorkloadInvalidRole = 502
    FailedWorkloadInvalidWorkloadName = 503
    FailedWorkloadPostError = 504
    FailedWorkloadAuthorizationMissing = 505
    FailedWorkloadConnectionError = 506
    FailedWorkloadIPCDirectoryMissing = 507
    FailedWorkloadDatabaseNotOpen = 508
    FailedWorkloadQuiescingError = 509
    FailedWorkloadQuiescingTimeout = 510
    FailedWorkloadDatabaseInNoArchiveLog = 511

    """
    Consistency-Types
    """
    consistency_none = 'none'
    consistency_crashConsistent = 'crashConsistent'
    consistency_fileSystemConsistent = 'fileSystemConsistent'
    consistency_applicationConsistent = 'applicationConsistent'

    @staticmethod
    def isTerminalStatus(status):
        return (status==CommonVariables.status_success or status==CommonVariables.status_error)

class DeviceItem(object):
    def __init__(self):
        #NAME,TYPE,FSTYPE,MOUNTPOINT,LABEL,UUID,MODEL
        self.name = None
        self.type = None
        self.file_system = None
        self.mount_point = None
        self.label = None
        self.uuid = None
        self.model = None
        self.size = None
    def __str__(self):
        return "name:" + str(self.name) + " type:" + str(self.type) + " fstype:" + str(self.file_system) + " mountpoint:" + str(self.mount_point) + " label:" + str(self.label) + " model:" + str(self.model)
