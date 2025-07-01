import json

class HostDoSnapshotRequestBody:
    def __init__(self, taskId, diskIds, settings, snapshotTaskToken, snapshotMetadata, instantAccessDurationMinutes = None):
        self.taskId = taskId
        self.diskIds = diskIds
        self.snapshotMetadata = snapshotMetadata
        self.snapshotTaskToken = snapshotTaskToken
        self.settings = settings
        self.instantAccessDurationMinutes = instantAccessDurationMinutes

    def convertToDictionary(self):
        return dict(taskId = self.taskId, diskIds = self.diskIds, settings = self.settings, snapshotTaskToken = self.snapshotTaskToken, snapshotMetadata = self.snapshotMetadata, instantAccessDurationMinutes = self.instantAccessDurationMinutes)

class HostPreSnapshotRequestBody:
    def __init__(self, taskId, snapshotTaskToken, instantAccessDurationMinutes = None):
        self.taskId = taskId
        self.snapshotTaskToken = snapshotTaskToken
        self.instantAccessDurationMinutes = instantAccessDurationMinutes

    def convertToDictionary(self):
        return dict(taskId = self.taskId, snapshotTaskToken = self.snapshotTaskToken, instantAccessDurationMinutes = self.instantAccessDurationMinutes)

class BlobSnapshotInfo:
    def __init__(self, isSuccessful, snapshotUri, errorMessage, statusCode, ddSnapshotIdentifier = None):
        self.isSuccessful = isSuccessful
        self.snapshotUri = snapshotUri
        self.errorMessage = errorMessage
        self.statusCode = statusCode
        self.ddSnapshotIdentifier = ddSnapshotIdentifier

    def convertToDictionary(self):
        return dict(isSuccessful = self.isSuccessful, snapshotUri = self.snapshotUri, errorMessage = self.errorMessage, statusCode = self.statusCode, ddSnapshotIdentifier = self.ddSnapshotIdentifier)

class DDSnapshotIdentifier:
    def __init__(self, creationTime, id, token, instantAccessDurationMinutes = None):
        self.creationTime = creationTime
        self.id = id
        self.token = token
        self.instantAccessDurationMinutes = instantAccessDurationMinutes

    def convertToDictionary(self):
        return dict(creationTime = self.creationTime, id = self.id, token = self.token, instantAccessDurationMinutes = self.instantAccessDurationMinutes)

