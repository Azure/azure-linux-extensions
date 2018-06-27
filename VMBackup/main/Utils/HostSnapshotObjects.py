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
