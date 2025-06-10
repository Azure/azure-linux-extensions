import json

class HostDoSnapshotRequestBody:
    def __init__(self, taskId, diskIds, settings, snapshotTaskToken, snapshotMetadata):
        self.taskId = taskId
        self.diskIds = diskIds
        self.snapshotMetadata = snapshotMetadata
        self.snapshotTaskToken = snapshotTaskToken
        self.settings = settings

    def convertToDictionary(self):
        return dict(taskId = self.taskId, diskIds = self.diskIds, settings = self.settings, snapshotTaskToken = self.snapshotTaskToken, snapshotMetadata = self.snapshotMetadata)

class HostPreSnapshotRequestBody:
    def __init__(self, taskId, snapshotTaskToken, isVMADEEnabled = False):
        self.taskId = taskId
        self.snapshotTaskToken = snapshotTaskToken
        if (isVMADEEnabled):
            self.preSnapshotSettings = dict(isVMADEEnabled = isVMADEEnabled)
        else:
            self.preSnapshotSettings = None

    def convertToDictionary(self):
        return dict(taskId = self.taskId, snapshotTaskToken = self.snapshotTaskToken, preSnapshotSettings = self.preSnapshotSettings)

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
    def __init__(self, creationTime, id, token):
        self.creationTime = creationTime
        self.id = id
        self.token = token

    def convertToDictionary(self):
        return dict(creationTime = self.creationTime, id = self.id, token = self.token)

