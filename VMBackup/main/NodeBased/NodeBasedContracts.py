import json

class GetSnapshotResponseBody:
    def __init__(self, snapshotId, diskInfo=None, extensionSettings=None):
        self.snapshotId = snapshotId
        self.diskInfo = diskInfo
        self.extensionSettings = extensionSettings

    def convertToDictionary(self):
        return dict(
            snapshotId=self.snapshotId,
            diskInfo=self.diskInfo.convertToDictionary() if self.diskInfo else None,
            extensionSettings=self.extensionSettings
        )

class StartSnapshotHostResponseBody:
    def __init__(self, snapshotId, error=None):
        self.snapshotId = snapshotId
        self.error = error

    def convertToDictionary(self):
        return dict(
            snapshotId=self.snapshotId,
            error=self.error.convertToDictionary() if self.error else None
        )

class StartSnapshotHostRequestBody:
    def __init__(self, snapshotId):
        self.snapshotId = snapshotId

    def serialize_to_json_string(self):
        return json.dumps(self.convertToDictionary())

    def convertToDictionary(self):
        return dict(snapshotId=self.snapshotId)
    
class EndSnapshotHostRequestBody:
    def __init__(self, snapshotId, error=None, provisioningDetails=None):
        self.snapshotId = snapshotId
        self.error = error
        self.provisioningDetails = provisioningDetails

    def serialize_to_json_string(self):
        return json.dumps(self.convertToDictionary())

    def convertToDictionary(self):
        return dict(
            snapshotId=self.snapshotId,
            error=self.error.convertToDictionary() if self.error else None,
            provisioningDetails=self.provisioningDetails
        )

class EndSnapshotHostResponseBody:
    def __init__(self, snapshotId, error=None):
        self.snapshotId = snapshotId
        self.error = error

    def convertToDictionary(self):
        return dict(
            snapshotId=self.snapshotId,
            error=self.error.convertToDictionary() if self.error else None
        )

class Error:
    def __init__(self, code, message=None):
        self.code = code
        self.message = message

    def convertToDictionary(self):
        return dict(
            code=self.code,
            message=self.message
        )

class DiskInfo:
    def __init__(self, dataDiskInfo=None, isOSDiskIncluded=False):
        self.dataDiskInfo = dataDiskInfo or []
        self.isOSDiskIncluded = isOSDiskIncluded

    def convertToDictionary(self):
        return dict(
            dataDiskInfo=[disk.convertToDictionary() for disk in self.dataDiskInfo],
            isOSDiskIncluded=self.isOSDiskIncluded
        )

class DataDiskInfo:
    def __init__(self, controllerType, controllerId, lunId):
        self.controllerType = controllerType
        self.controllerId = controllerId
        self.lunId = lunId

    def convertToDictionary(self):
        return dict(
            controllerType=self.controllerType,
            controllerId=self.controllerId,
            lunId=self.lunId
        )

class XDiskSvcError:
    def __init__(self, code, message=None):
        self.code = code
        self.message = message

    def convertToDictionary(self):
        return dict(
            code=self.code,
            message=self.message
        )

class ProvisioningDetails:
    def __init__(self, code, vmHealthInfo=None, storageDetails=None, message=None):
        self.code = code
        self.vmHealthInfo = vmHealthInfo
        self.storageDetails = storageDetails
        self.message = message

    def convertToDictionary(self):
        return dict(
            code=self.code,
            vmHealthInfo=self.vmHealthInfo.convertToDictionary() if self.vmHealthInfo else None,
            storageDetails=self.storageDetails.convertToDictionary() if self.storageDetails else None,
            message=self.message
        )
