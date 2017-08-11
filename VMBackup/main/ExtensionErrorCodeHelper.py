from Utils import Status

class ExtensionErrorCodeEnum():
    success = 1
    success_appconsistent = 0
    ExtensionTempTerminalState = 4
    error_parameter = 11
    error_12 = 12
    error_wrong_time = 13
    error_same_taskid = 14
    error_http_failure = 15
    FailedHandlerGuestAgentCertificateNotFound = 16
    #error_upload_status_blob = 16
    error = 2
    FailedRetryableSnapshotFailedNoNetwork = 76
    FailedRetryableSnapshotFailedRestrictedNetwork = 761

    FailedRetryableFsFreezeFailed = 201

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
    SuccessAlreadyProcessedInput = 3

class ExtensionErrorCodeHelper:
    ExtensionErrorCodeDict = {
            ExtensionErrorCodeEnum.success_appconsistent : Status.ExtVmHealthStateEnum.green,
            ExtensionErrorCodeEnum.success : Status.ExtVmHealthStateEnum.green,
            ExtensionErrorCodeEnum.ExtensionTempTerminalState : Status.ExtVmHealthStateEnum.green,
            ExtensionErrorCodeEnum.error : Status.ExtVmHealthStateEnum.green,
            ExtensionErrorCodeEnum.error_12 : Status.ExtVmHealthStateEnum.green,
            ExtensionErrorCodeEnum.SuccessAlreadyProcessedInput : Status.ExtVmHealthStateEnum.green,

            ExtensionErrorCodeEnum.FailedRetryableFsFreezeFailed : Status.ExtVmHealthStateEnum.yellow,
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
            ExtensionErrorCodeEnum.FailedRetryableSnapshotFailedNoNetwork : Status.ExtVmHealthStateEnum.red
            }

    ExtensionErrorCodeNameDict = {
            ExtensionErrorCodeEnum.success : "success",
            ExtensionErrorCodeEnum.success_appconsistent : "success_appconsistent",
            ExtensionErrorCodeEnum.ExtensionTempTerminalState : "ExtensionTempTerminalState",
            ExtensionErrorCodeEnum.error : "error",
            ExtensionErrorCodeEnum.error_12 : "error_12",
            ExtensionErrorCodeEnum.SuccessAlreadyProcessedInput : "SuccessAlreadyProcessedInput",

            ExtensionErrorCodeEnum.FailedRetryableFsFreezeFailed : "FailedRetryableFsFreezeFailed",
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
            ExtensionErrorCodeEnum.FailedRetryableSnapshotFailedNoNetwork : "FailedRetryableSnapshotFailedNoNetwork"
            }
    
    @staticmethod
    def StatusCodeStringBuilder(ExtErrorCodeEnum):
        return " StatusCode." + ExtensionErrorCodeHelper.ExtensionErrorCodeNameDict[ExtErrorCodeEnum] + ","

