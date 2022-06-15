import json

class HostDoSnapshotRequestBody:
    def __init__(self, taskId, diskIds, snapshotTaskToken, snapshotMetadata):
        self.taskId = taskId
        self.diskIds = diskIds
        self.snapshotMetadata = snapshotMetadata
        self.snapshotTaskToken = snapshotTaskToken

    def convertToDictionary(self):
        return dict(taskId = self.taskId, diskIds = self.diskIds, snapshotTaskToken = self.snapshotTaskToken, snapshotMetadata = self.snapshotMetadata)

class HostPreSnapshotRequestBody:
    def __init__(self, taskId, snapshotTaskToken):
        self.taskId = taskId
        self.snapshotTaskToken = snapshotTaskToken

    def convertToDictionary(self):
        return dict(taskId = self.taskId, snapshotTaskToken = self.snapshotTaskToken)

class BlobSnapshotInfo:
    def __init__(self, isSuccessful, snapshotUri, errorMessage, statusCode, blobUri, DDSnapshotIdentifier = None):
        self.isSuccessful = isSuccessful
        self.snapshotUri = snapshotUri
        self.errorMessage = errorMessage
        self.statusCode = statusCode
        self.blobUri = blobUri
        self.DDSnapshotIdentifier = DDSnapshotIdentifier

    def convertToDictionary(self):
        return dict(isSuccessful = self.isSuccessful, snapshotUri = self.snapshotUri, errorMessage = self.errorMessage, statusCode = self.statusCode, blobUri = self.blobUri, DDSnapshotIdentifier = self.DDSnapshotIdentifier)

class DDSnapshotIdentifier:
    def __init__(self, creationTime, id, token):
        self.creationTime = creationTime
        self.id = id
        self.token = token

    def convertToDictionary(self):
        return dict(creationTime = self.creationTime, id = self.id, token = self.token)
        