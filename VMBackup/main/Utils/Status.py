import json

class TopLevelStatus:
    def __init__(self, version, timestampUTC, status):
        self.version = version
        self.timestampUTC = timestampUTC
        self.status = status

    def convertToDictionary(self):
        return dict(version = self.version, timestampUTC = self.timestampUTC, status = self.status)

class StatusObj:
    def __init__(self, name, operation, status, substatus, code, formattedMessage, telemetrydata, taskId, commandStartTimeUTCTicks):
        self.name = name
        self.operation = operation
        self.status = status
        self.substatus = substatus
        self.code = code
        self.formattedMessage = formattedMessage
        self.telemetryData = telemetrydata
        self.taskId = taskId
        self.commandStartTimeUTCTicks = commandStartTimeUTCTicks
        
    def convertToDictionary(self):
        return dict(name= self.name, operation = self.operation, status = self.status, substatus = self.substatus, code = self.code, taskId = self.taskId, formattedMessage = self.formattedMessage,commandStartTimeUTCTicks = self.commandStartTimeUTCTicks, telemetryData = self.telemetryData)

class SubstatusObj:
    def __init__(self, code, name, status, formattedMessage):
        self.code = code
        self.name = name
        self.status = status
        self.formattedMessage = formattedMessage
        
    def convertToDictionary(self):
        return dict(code = self.code, name = self.name, status = self.status, formattedMessage = self.formattedMessage)

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
