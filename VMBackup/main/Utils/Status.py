import json

class TopLevelStatus:
        def __init__(self, version, timestampUTC, status):
            self.version = version
            self.timestampUTC = timestampUTC
            self.status = status

        def reprJSON(self):
                    return dict(version = self.version, timestampUTC = self.timestampUTC, status = self.status)

class StatusObj:
        def __init__(self, name, operation, status, substatus, code, message, taskId = None, commandStartTimeUTCTicks = None):
            self.name = name
            self.operation = operation
            self.status = status
            self.substatus = substatus
            self.code = code
            self.taskId = taskId
            self.formattedMessage = {
                    "lang" : "en-US",
                    "message" : message
                    }
            self.commandStartTimeUTCTicks = commandStartTimeUTCTicks
            self.telemetryData = {}

class ComplexEncoder(json.JSONEncoder):
        def default(self, obj):
            if hasattr(obj,'reprJSON'):
                return obj.reprJSON()
            else:
                return obj.__dict__
