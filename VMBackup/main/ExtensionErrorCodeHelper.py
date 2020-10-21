from Utils import Status

class ExtensionErrorCodeEnum():
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
    FailedRetryableSnapshotFailedRestrictedNetwork = 761

    FailedRetryableFsFreezeFailed = 121
    FailedRetryableFsFreezeTimeout = 122
    FailedRetryableUnableToOpenMount = 123

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

class ExtensionErrorCodeHelper:
    ExtensionErrorCodeDict = {
            ExtensionErrorCodeEnum.success_appconsistent : Status.ExtVmHealthStateEnum.green,
            ExtensionErrorCodeEnum.success : Status.ExtVmHealthStateEnum.green,
            ExtensionErrorCodeEnum.ExtensionTempTerminalState : Status.ExtVmHealthStateEnum.green,
            ExtensionErrorCodeEnum.error : Status.ExtVmHealthStateEnum.green,
            ExtensionErrorCodeEnum.error_12 : Status.ExtVmHealthStateEnum.green,
            ExtensionErrorCodeEnum.SuccessAlreadyProcessedInput : Status.ExtVmHealthStateEnum.green,
            ExtensionErrorCodeEnum.FailedRetryableSnapshotRateExceeded : Status.ExtVmHealthStateEnum.green,

            ExtensionErrorCodeEnum.FailedRetryableFsFreezeFailed : Status.ExtVmHealthStateEnum.yellow,
            ExtensionErrorCodeEnum.FailedRetryableFsFreezeTimeout : Status.ExtVmHealthStateEnum.yellow,
            ExtensionErrorCodeEnum.FailedRetryableUnableToOpenMount : Status.ExtVmHealthStateEnum.yellow,
            ExtensionErrorCodeEnum.error_parameter : Status.ExtVmHealthStateEnum.yellow,
            ExtensionErrorCodeEnum.FailedHandlerGuestAgentCertificateNotFound : Status.ExtVmHealthStateEnum.yellow,

            ExtensionErrorCodeEnum.FailedPrepostPreScriptFailed : Status.ExtVmHealthStateEnum.yellow,
            ExtensionErrorCodeEnum.FailedPrepostPostScriptFailed : Status.ExtVmHealthStateEnum.yellow,
            ExtensionErrorCodeEnum.FailedPrepostPreScriptNotFound : Status.ExtVmHealthStateEnum.yellow,
            ExtensionErrorCodeEnum.FailedPrepostPostScriptNotFound : Status.ExtVmHealthStateEnum.yellow,
            ExtensionErrorCodeEnum.FailedPrepostPluginhostConfigParsing : Status.ExtVmHealthStateEnum.yellow,
            ExtensionErrorCodeEnum.FailedPrepostPluginConfigParsing : Status.ExtVmHealthStateEnum.yellow,
            ExtensionErrorCodeEnum.FailedPrepostPreScriptPermissionError : Status.ExtVmHealthStateEnum.yellow,
            ExtensionErrorCodeEnum.FailedPrepostPostScriptPermissionError : Status.ExtVmHealthStateEnum.yellow,
            ExtensionErrorCodeEnum.FailedPrepostPreScriptTimeout : Status.ExtVmHealthStateEnum.yellow,
            ExtensionErrorCodeEnum.FailedPrepostPostScriptTimeout : Status.ExtVmHealthStateEnum.yellow,
            ExtensionErrorCodeEnum.FailedPrepostPluginhostPreTimeout : Status.ExtVmHealthStateEnum.yellow,
            ExtensionErrorCodeEnum.FailedPrepostPluginhostPostTimeout : Status.ExtVmHealthStateEnum.yellow,
            ExtensionErrorCodeEnum.FailedPrepostCheckSumMismatch : Status.ExtVmHealthStateEnum.yellow,
            ExtensionErrorCodeEnum.FailedPrepostPluginhostConfigNotFound : Status.ExtVmHealthStateEnum.yellow,
            ExtensionErrorCodeEnum.FailedPrepostPluginhostConfigPermissionError : Status.ExtVmHealthStateEnum.yellow,
            ExtensionErrorCodeEnum.FailedPrepostPluginhostConfigOwnershipError : Status.ExtVmHealthStateEnum.yellow,
            ExtensionErrorCodeEnum.FailedPrepostPluginConfigNotFound : Status.ExtVmHealthStateEnum.yellow,
            ExtensionErrorCodeEnum.FailedPrepostPluginConfigPermissionError : Status.ExtVmHealthStateEnum.yellow,
            ExtensionErrorCodeEnum.FailedPrepostPluginConfigOwnershipError : Status.ExtVmHealthStateEnum.yellow,


            ExtensionErrorCodeEnum.error_http_failure : Status.ExtVmHealthStateEnum.red,
            ExtensionErrorCodeEnum.FailedRetryableSnapshotFailedRestrictedNetwork : Status.ExtVmHealthStateEnum.red,
            ExtensionErrorCodeEnum.FailedRetryableSnapshotFailedNoNetwork : Status.ExtVmHealthStateEnum.red,
            ExtensionErrorCodeEnum.FailedSnapshotLimitReached : Status.ExtVmHealthStateEnum.red,
            ExtensionErrorCodeEnum.FailedGuestAgentInvokedCommandTooLate : Status.ExtVmHealthStateEnum.red,
            
            ExtensionErrorCodeEnum.FailedWorkloadPreError : Status.ExtVmHealthStateEnum.yellow,
            ExtensionErrorCodeEnum.FailedWorkloadConfParsingError : Status.ExtVmHealthStateEnum.yellow,
            ExtensionErrorCodeEnum.FailedWorkloadInvalidRole : Status.ExtVmHealthStateEnum.yellow,
            ExtensionErrorCodeEnum.FailedWorkloadInvalidWorkloadName : Status.ExtVmHealthStateEnum.yellow,
            ExtensionErrorCodeEnum.FailedWorkloadPostError : Status.ExtVmHealthStateEnum.yellow,
            ExtensionErrorCodeEnum.FailedWorkloadAuthorizationMissing : Status.ExtVmHealthStateEnum.yellow,
            ExtensionErrorCodeEnum.FailedWorkloadConnectionError : Status.ExtVmHealthStateEnum.yellow,
            ExtensionErrorCodeEnum.FailedWorkloadIPCDirectoryMissing : Status.ExtVmHealthStateEnum.yellow,
            ExtensionErrorCodeEnum.FailedWorkloadDatabaseNotOpen : Status.ExtVmHealthStateEnum.yellow,
            ExtensionErrorCodeEnum.FailedWorkloadQuiescingError : Status.ExtVmHealthStateEnum.yellow,
            ExtensionErrorCodeEnum.FailedWorkloadQuiescingTimeout : Status.ExtVmHealthStateEnum.yellow,
            ExtensionErrorCodeEnum.FailedWorkloadDatabaseInNoArchiveLog : Status.ExtVmHealthStateEnum.yellow
            }

    ExtensionErrorCodeNameDict = {
            ExtensionErrorCodeEnum.success : "success",
            ExtensionErrorCodeEnum.success_appconsistent : "success_appconsistent",
            ExtensionErrorCodeEnum.ExtensionTempTerminalState : "ExtensionTempTerminalState",
            ExtensionErrorCodeEnum.error : "error",
            ExtensionErrorCodeEnum.error_12 : "error_12",
            ExtensionErrorCodeEnum.SuccessAlreadyProcessedInput : "SuccessAlreadyProcessedInput",

            ExtensionErrorCodeEnum.FailedRetryableFsFreezeFailed : "FailedRetryableFsFreezeFailed",
            ExtensionErrorCodeEnum.FailedRetryableFsFreezeTimeout : "FailedRetryableFsFreezeTimeout",
            ExtensionErrorCodeEnum.FailedRetryableUnableToOpenMount : "FailedRetryableUnableToOpenMount",
            ExtensionErrorCodeEnum.error_parameter : "error_parameter",
            ExtensionErrorCodeEnum.FailedHandlerGuestAgentCertificateNotFound : "FailedHandlerGuestAgentCertificateNotFound",

            ExtensionErrorCodeEnum.FailedPrepostPreScriptFailed : "FailedPrepostPreScriptFailed",
            ExtensionErrorCodeEnum.FailedPrepostPostScriptFailed : "FailedPrepostPostScriptFailed",
            ExtensionErrorCodeEnum.FailedPrepostPreScriptNotFound : "FailedPrepostPreScriptNotFound",
            ExtensionErrorCodeEnum.FailedPrepostPostScriptNotFound : "FailedPrepostPostScriptNotFound",
            ExtensionErrorCodeEnum.FailedPrepostPluginhostConfigParsing : "FailedPrepostPluginhostConfigParsing",
            ExtensionErrorCodeEnum.FailedPrepostPluginConfigParsing : "FailedPrepostPluginConfigParsing",
            ExtensionErrorCodeEnum.FailedPrepostPreScriptPermissionError : "FailedPrepostPreScriptPermissionError",
            ExtensionErrorCodeEnum.FailedPrepostPostScriptPermissionError : "FailedPrepostPostScriptPermissionError",
            ExtensionErrorCodeEnum.FailedPrepostPreScriptTimeout : "FailedPrepostPreScriptTimeout",
            ExtensionErrorCodeEnum.FailedPrepostPostScriptTimeout : "FailedPrepostPostScriptTimeout",
            ExtensionErrorCodeEnum.FailedPrepostPluginhostPreTimeout : "FailedPrepostPluginhostPreTimeout",
            ExtensionErrorCodeEnum.FailedPrepostPluginhostPostTimeout : "FailedPrepostPluginhostPostTimeout",
            ExtensionErrorCodeEnum.FailedPrepostCheckSumMismatch : "FailedPrepostCheckSumMismatch",
            ExtensionErrorCodeEnum.FailedPrepostPluginhostConfigNotFound : "FailedPrepostPluginhostConfigNotFound",
            ExtensionErrorCodeEnum.FailedPrepostPluginhostConfigPermissionError : "FailedPrepostPluginhostConfigPermissionError",
            ExtensionErrorCodeEnum.FailedPrepostPluginhostConfigOwnershipError : "FailedPrepostPluginhostConfigOwnershipError",
            ExtensionErrorCodeEnum.FailedPrepostPluginConfigNotFound : "FailedPrepostPluginConfigNotFound",
            ExtensionErrorCodeEnum.FailedPrepostPluginConfigPermissionError : "FailedPrepostPluginConfigPermissionError",
            ExtensionErrorCodeEnum.FailedPrepostPluginConfigOwnershipError : "FailedPrepostPluginConfigOwnershipError",

            ExtensionErrorCodeEnum.error_http_failure : "error_http_failure",
            ExtensionErrorCodeEnum.FailedRetryableSnapshotFailedRestrictedNetwork : "FailedRetryableSnapshotFailedRestrictedNetwork",
            ExtensionErrorCodeEnum.FailedRetryableSnapshotFailedNoNetwork : "FailedRetryableSnapshotFailedNoNetwork",
            ExtensionErrorCodeEnum.FailedSnapshotLimitReached : "FailedSnapshotLimitReached",
            ExtensionErrorCodeEnum.FailedGuestAgentInvokedCommandTooLate : "FailedGuestAgentInvokedCommandTooLate",
            
            ExtensionErrorCodeEnum.FailedWorkloadPreError : "FailedWorkloadPreError",
            ExtensionErrorCodeEnum.FailedWorkloadConfParsingError : "FailedWorkloadConfParsingError",
            ExtensionErrorCodeEnum.FailedWorkloadInvalidRole : "FailedWorkloadInvalidRole",
            ExtensionErrorCodeEnum.FailedWorkloadInvalidWorkloadName : "FailedWorkloadInvalidWorkloadName",
            ExtensionErrorCodeEnum.FailedWorkloadPostError : "FailedWorkloadPostError",
            ExtensionErrorCodeEnum.FailedWorkloadAuthorizationMissing : "FailedWorkloadAuthorizationMissing",
            ExtensionErrorCodeEnum.FailedWorkloadConnectionError : "FailedWorkloadConnectionError",
            ExtensionErrorCodeEnum.FailedWorkloadIPCDirectoryMissing : "FailedWorkloadIPCDirectoryMissing",
            ExtensionErrorCodeEnum.FailedWorkloadDatabaseNotOpen : "FailedWorkloadDatabaseNotOpen",
            ExtensionErrorCodeEnum.FailedWorkloadQuiescingError : "FailedWorkloadQuiescingError",
            ExtensionErrorCodeEnum.FailedWorkloadQuiescingTimeout : "FailedWorkloadQuiescingTimeout",
            ExtensionErrorCodeEnum.FailedWorkloadDatabaseInNoArchiveLog : "FailedWorkloadDatabaseInNoArchiveLog"
            }
    
    @staticmethod
    def StatusCodeStringBuilder(ExtErrorCodeEnum):
        return " StatusCode." + ExtensionErrorCodeHelper.ExtensionErrorCodeNameDict[ExtErrorCodeEnum] + ","

