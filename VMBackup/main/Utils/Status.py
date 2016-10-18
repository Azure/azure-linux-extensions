import json

class TopLevelStatus:
    def __init__(self, version, timestampUTC, status):
        self.version = version
        self.timestampUTC = timestampUTC
        self.status = status

    def convertToDictionary(self):
        return dict(version = self.version, timestampUTC = self.timestampUTC, status = self.status)

class StatusObj:
    def __init__(self, name, operation, status, substatus, code, formattedMessage, telemetrydata, storageDetails, uniqueMachineId, taskId, commandStartTimeUTCTicks):
        self.name = name
        self.operation = operation
        self.status = status
        self.substatus = substatus
        self.code = code
        self.formattedMessage = formattedMessage
        self.telemetryData = telemetrydata
        self.storageDetails = storageDetails
        self.uniqueMachineId = uniqueMachineId
        self.taskId = taskId
        self.commandStartTimeUTCTicks = commandStartTimeUTCTicks
        
    def convertToDictionary(self):
        return dict(name = self.name, operation = self.operation, status = self.status, substatus = self.substatus, code = self.code, taskId = self.taskId, formattedMessage = self.formattedMessage, storageDetails = self.storageDetails, commandStartTimeUTCTicks = self.commandStartTimeUTCTicks, telemetryData = self.telemetryData, uniqueMachineId = self.uniqueMachineId)

class SubstatusObj:
    def __init__(self, code, name, status, formattedMessage):
        self.code = code
        self.name = name
        self.status = status
        self.formattedMessage = formattedMessage
        
    def convertToDictionary(self):
        return dict(code = self.code, name = self.name, status = self.status, formattedMessage = self.formattedMessage)

class StorageDetails:
    def __init__(self, partitionCount, totalUsedSize, isStoragespacePresent, isSizeComputationFailed):
        self.partitionCount =  partitionCount
        self.totalUsedSize = totalUsedSize
        self.isStoragespacePresent = isStoragespacePresent
        self.isSizeComputationFailed = isSizeComputationFailed

    def convertToDictionary(self):
        return dict(partitionCount = self.partitionCount, totalUsedSize = self.totalUsedSize, isStoragespacePresent = self.isStoragespacePresent, isSizeComputationFailed = self.isSizeComputationFailed)

class FormattedMessage:
    def __init__(self, lang, message):
        self.lang = lang
        self.message = message

class ComplexEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj,'convertToDictionary'):
            return obj.convertToDictionary()
        else:
            return obj.__dict__
