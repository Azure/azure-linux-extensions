from Utils import Status

class ExtensionErrorCodeEnum():
    success = 1
    ExtensionTempTerminalState = 4
    error_parameter = 11
    error_12 = 12
    error_wrong_time = 13
    error_same_taskid = 14
    error_http_failure = 15
    error_upload_status_blob = 16
    error = 2
    FailedRetryableSnapshotFailedNoNetwork = 76
    FailedRetryableSnapshotFailedRestrictedNetwork = 761

    FailedRetryableFsFreezeFailed = 201

class ExtensionErrorCodeHelper:
    ExtensionErrorCodeDict = {
            ExtensionErrorCodeEnum.success : Status.ExtVmHealthStateEnum.green,
            ExtensionErrorCodeEnum.ExtensionTempTerminalState : Status.ExtVmHealthStateEnum.green,
            ExtensionErrorCodeEnum.error : Status.ExtVmHealthStateEnum.green,
            ExtensionErrorCodeEnum.error_12 : Status.ExtVmHealthStateEnum.green,

            ExtensionErrorCodeEnum.FailedRetryableFsFreezeFailed : Status.ExtVmHealthStateEnum.yellow,
            ExtensionErrorCodeEnum.error_parameter : Status.ExtVmHealthStateEnum.yellow,

            ExtensionErrorCodeEnum.error_http_failure : Status.ExtVmHealthStateEnum.red,
            ExtensionErrorCodeEnum.FailedRetryableSnapshotFailedRestrictedNetwork : Status.ExtVmHealthStateEnum.red,
            ExtensionErrorCodeEnum.FailedRetryableSnapshotFailedNoNetwork : Status.ExtVmHealthStateEnum.red
            }

    ExtensionErrorCodeNameDict = {
            ExtensionErrorCodeEnum.success : "success",
            ExtensionErrorCodeEnum.ExtensionTempTerminalState : "ExtensionTempTerminalState",
            ExtensionErrorCodeEnum.error : "error",
            ExtensionErrorCodeEnum.error_12 : "error_12",

            ExtensionErrorCodeEnum.FailedRetryableFsFreezeFailed : "FailedRetryableFsFreezeFailed",
            ExtensionErrorCodeEnum.error_parameter : "error_parameter",

            ExtensionErrorCodeEnum.error_http_failure : "error_http_failure",
            ExtensionErrorCodeEnum.FailedRetryableSnapshotFailedRestrictedNetwork : "FailedRetryableSnapshotFailedRestrictedNetwork",
            ExtensionErrorCodeEnum.FailedRetryableSnapshotFailedNoNetwork : "FailedRetryableSnapshotFailedNoNetwork"
            }
    
    @staticmethod
    def StatusCodeStringBuilder(ExtErrorCodeEnum):
        return " StatusCode." + ExtensionErrorCodeHelper.ExtensionErrorCodeNameDict[ExtErrorCodeEnum] + ","

